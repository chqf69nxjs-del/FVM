from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.eos import LinearLiquidEOS
from liquid_gas_transient.flux import rusanov_flux
from liquid_gas_transient.interfaces import InternalValveInterface
from liquid_gas_transient.state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    N_VARS,
    make_conserved,
)
from liquid_gas_transient.valve import ConstantOpening, KvLiquidValve


def _state_from_pressure(
    eos: LinearLiquidEOS,
    *,
    pressure_pa: float,
    velocity_m_s: float = 0.0,
) -> np.ndarray:
    rho = float(np.asarray(eos.density_from_pressure(pressure_pa)))
    return make_conserved(
        rho=rho,
        u=velocity_m_s,
        e=eos.e_ref,
        xv=0.0,
    )


def _two_cell_state(
    eos: LinearLiquidEOS,
    *,
    p_left_pa: float,
    p_right_pa: float,
) -> np.ndarray:
    return np.vstack(
        [
            _state_from_pressure(eos, pressure_pa=p_left_pa),
            _state_from_pressure(eos, pressure_pa=p_right_pa),
        ]
    )


def test_uniform_state_reports_zero_applied_flow_and_wall_fluxes() -> None:
    eos = LinearLiquidEOS()
    U = _two_cell_state(
        eos,
        p_left_pa=eos.p_ref,
        p_right_pa=eos.p_ref,
    )
    interface = InternalValveInterface(
        left_cell=0,
        area_m2=0.1,
        valve=KvLiquidValve(kv_m3_per_h=10.0),
        opening_schedule=ConstantOpening(0.5),
    )

    F_l, F_r, telemetry = interface.evaluate_fluxes(
        U=U,
        eos=eos,
        t=0.0,
        flux_function=rusanov_flux,
    )

    assert telemetry["opening"] == pytest.approx(0.5)
    assert telemetry["raw_target_q_m3_s"] == 0.0
    assert telemetry["applied_q_m3_s"] == 0.0
    assert telemetry["mach_cap_active"] is False
    assert telemetry["hydraulic_separation_active"] is True
    assert telemetry["flow_direction"] == "none"

    assert F_l[IDX_RHO] == 0.0
    assert F_r[IDX_RHO] == 0.0
    assert F_l[IDX_RHOE] == 0.0
    assert F_r[IDX_RHOE] == 0.0
    assert F_l[IDX_RHO_XV] == 0.0
    assert F_r[IDX_RHO_XV] == 0.0
    assert F_l[IDX_MOM] == pytest.approx(eos.p_ref)
    assert F_r[IDX_MOM] == pytest.approx(eos.p_ref)


def test_finite_opening_fluxes_use_applied_flow_and_match_shared_channels() -> None:
    eos = LinearLiquidEOS()
    area_m2 = 0.1
    p_left_pa = eos.p_ref + 1000.0
    p_right_pa = eos.p_ref
    U = _two_cell_state(
        eos,
        p_left_pa=p_left_pa,
        p_right_pa=p_right_pa,
    )
    rho_left = float(U[0, IDX_RHO])
    q_target_m3_s = area_m2 * 1.0e-3
    kv = KvLiquidValve.kv_for_target_flow(
        q_m3_s=q_target_m3_s,
        delta_p_pa=p_left_pa - p_right_pa,
        rho_kg_m3=rho_left,
    )
    interface = InternalValveInterface(
        left_cell=0,
        area_m2=area_m2,
        valve=KvLiquidValve(kv_m3_per_h=kv),
        opening_schedule=ConstantOpening(1.0),
    )

    F_l, F_r, telemetry = interface.evaluate_fluxes(
        U=U,
        eos=eos,
        t=0.0,
        flux_function=rusanov_flux,
    )

    assert telemetry["raw_target_q_m3_s"] == pytest.approx(q_target_m3_s)
    assert telemetry["applied_q_m3_s"] == pytest.approx(q_target_m3_s)
    assert telemetry["mach_cap_active"] is False
    assert telemetry["hydraulic_separation_active"] is False
    assert telemetry["flow_direction"] == "left_to_right"
    assert telemetry["upwind_side"] == "left"

    assert F_l[IDX_RHO] == pytest.approx(F_r[IDX_RHO])
    assert F_l[IDX_RHOE] == pytest.approx(F_r[IDX_RHOE])
    assert F_l[IDX_RHO_XV] == pytest.approx(F_r[IDX_RHO_XV])
    assert F_l[IDX_MOM] - F_r[IDX_MOM] == pytest.approx(
        p_left_pa - p_right_pa
    )

    q_from_flux = float(
        area_m2 * F_l[IDX_RHO] / float(telemetry["rho_upwind_kg_m3"])
    )
    assert q_from_flux == pytest.approx(
        float(telemetry["applied_q_m3_s"]),
        rel=1.0e-14,
        abs=1.0e-18,
    )


def test_mach_cap_is_explicit_and_apply_uses_the_evaluated_flux() -> None:
    eos = LinearLiquidEOS()
    U = _two_cell_state(
        eos,
        p_left_pa=eos.p_ref + 1.0e4,
        p_right_pa=eos.p_ref,
    )
    interface = InternalValveInterface(
        left_cell=0,
        area_m2=0.1,
        valve=KvLiquidValve(kv_m3_per_h=1.0e8),
        opening_schedule=ConstantOpening(1.0),
        max_mach=1.0e-6,
    )

    F_l, F_r, telemetry = interface.evaluate_fluxes(
        U=U,
        eos=eos,
        t=0.0,
        flux_function=rusanov_flux,
    )

    assert telemetry["mach_cap_active"] is True
    assert abs(float(telemetry["raw_target_q_m3_s"])) > float(
        telemetry["q_limit_m3_s"]
    )
    assert abs(float(telemetry["applied_q_m3_s"])) == pytest.approx(
        float(telemetry["q_limit_m3_s"])
    )

    flux_left = np.zeros((2, N_VARS), dtype=float)
    flux_right = np.zeros((2, N_VARS), dtype=float)
    interface.apply(
        flux_left=flux_left,
        flux_right=flux_right,
        U=U,
        eos=eos,
        t=0.0,
        flux_function=rusanov_flux,
    )

    np.testing.assert_allclose(flux_right[0], F_l, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(flux_left[1], F_r, rtol=0.0, atol=0.0)


def test_diagnostics_preserve_legacy_raw_q_and_add_applied_q() -> None:
    eos = LinearLiquidEOS()
    U = _two_cell_state(
        eos,
        p_left_pa=eos.p_ref + 1.0e4,
        p_right_pa=eos.p_ref,
    )
    interface = InternalValveInterface(
        left_cell=0,
        area_m2=0.1,
        valve=KvLiquidValve(kv_m3_per_h=1.0e8),
        opening_schedule=ConstantOpening(1.0),
        max_mach=1.0e-6,
    )

    diagnostics = interface.diagnostics(U=U, eos=eos, t=0.0)
    energy_terms = interface.interface_energy_terms(U=U, eos=eos, t=0.0)

    assert diagnostics["valve_q_m3_s"] == diagnostics[
        "valve_raw_target_q_m3_s"
    ]
    assert abs(float(diagnostics["valve_applied_q_m3_s"])) < abs(
        float(diagnostics["valve_q_m3_s"])
    )
    assert energy_terms["valve_q_m3_s"] == energy_terms["valve_raw_q_m3_s"]
    assert abs(energy_terms["valve_applied_q_m3_s"]) < abs(
        energy_terms["valve_raw_q_m3_s"]
    )
