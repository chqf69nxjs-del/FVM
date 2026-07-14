from __future__ import annotations

import numpy as np

from liquid_gas_transient.boundary import TransmissiveBoundary
from liquid_gas_transient.cases.coolprop_internal_valve_operation import (
    CoolPropInternalValveOperationConfig,
    internal_valve_flux_snapshot,
    opening_history_is_monotonic,
    opening_schedule_for_config,
)
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.eos import LinearLiquidEOS
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.interfaces import InternalValveInterface
from liquid_gas_transient.phase_change import NoPhaseChange
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.source_terms import NoSource
from liquid_gas_transient.state import make_conserved
from liquid_gas_transient.valve import ConstantOpening, KvLiquidValve


def _solver(opening: float, *, kv: float = 10.0, max_mach: float = 0.8):
    eos = LinearLiquidEOS()
    grid = UniformGrid(PipeGeometry(2.0, 0.30), 2)
    rho = eos.density_from_pressure(np.array([2.0e5, 1.0e5]))
    U = make_conserved(rho=rho, u=np.zeros(2), e=np.full(2, eos.e_ref), xv=0.0)
    interface = InternalValveInterface(
        left_cell=0,
        area_m2=grid.geometry.area_m2,
        valve=KvLiquidValve(kv),
        opening_schedule=ConstantOpening(opening),
        max_mach=max_mach,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        source_term=NoSource(),
        phase_change=NoPhaseChange(),
        internal_interfaces=(interface,),
    )
    return solver, interface


def test_opening_schedules_have_expected_monotonicity() -> None:
    times = np.linspace(0.0, 0.03, 31)
    for kind in ("constant", "opening_ramp", "closing_ramp"):
        cfg = CoolPropInternalValveOperationConfig(operation_kind=kind)
        schedule = opening_schedule_for_config(cfg)
        values = [schedule.opening(float(time_s)) for time_s in times]
        assert opening_history_is_monotonic(values, kind)


def test_finite_opening_uses_common_conservative_fluxes() -> None:
    solver, interface = _solver(0.5)
    valve, flux = internal_valve_flux_snapshot(solver, interface)
    assert valve["target_q_limited_m3_s"] > 0.0
    assert valve["mach_cap_active"] is False
    assert abs(valve["actual_q_error_m3_s"]) < 1.0e-15
    assert abs(flux["mass_flux_mismatch_kg_m2_s"]) < 1.0e-15
    assert abs(flux["energy_flux_mismatch_w_m2"]) < 1.0e-10
    assert abs(flux["vapor_mass_flux_mismatch_kg_m2_s"]) < 1.0e-15
    assert flux["momentum_flux_difference_pa"] != 0.0


def test_zero_opening_reduces_to_independent_walls() -> None:
    solver, interface = _solver(0.0)
    valve, flux = internal_valve_flux_snapshot(solver, interface)
    assert valve["target_q_limited_m3_s"] == 0.0
    assert flux["left_mass_flux_kg_m2_s"] == 0.0
    assert flux["right_mass_flux_kg_m2_s"] == 0.0
    assert flux["left_energy_flux_w_m2"] == 0.0
    assert flux["right_energy_flux_w_m2"] == 0.0
    assert flux["left_vapor_mass_flux_kg_m2_s"] == 0.0
    assert flux["right_vapor_mass_flux_kg_m2_s"] == 0.0


def test_mach_clipping_is_explicitly_reported() -> None:
    solver, interface = _solver(1.0, kv=1.0e9, max_mach=1.0e-4)
    valve, _ = internal_valve_flux_snapshot(solver, interface)
    assert valve["mach_cap_active"] is True
    assert abs(valve["target_q_limited_m3_s"]) <= valve["q_mach_limit_m3_s"]
    assert abs(valve["actual_q_error_m3_s"]) < 1.0e-12
