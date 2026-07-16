from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_driven import (
    build_coolprop_internal_valve_driven_solver,
    run_coolprop_internal_valve_driven,
)
from liquid_gas_transient.cases.internal_valve_driven_config import (
    CoolPropInternalValveDrivenConfig,
    opening_roundoff_tolerance,
)
from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.state import IDX_RHO


def test_driven_config_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="even integer"):
        CoolPropInternalValveDrivenConfig(n_cells=21)
    with pytest.raises(ValueError, match="must exceed"):
        CoolPropInternalValveDrivenConfig(
            left_pressure_pa=8.0e6,
            right_pressure_pa=8.0e6,
        )
    with pytest.raises(ValueError, match="unique and ascending"):
        CoolPropInternalValveDrivenConfig(probe_fractions=(0.75, 0.25))


def test_driven_opening_tolerance_is_machine_scale() -> None:
    cfg = CoolPropInternalValveDrivenConfig()
    assert opening_roundoff_tolerance(cfg) == pytest.approx(8.0 * np.spacing(1.0))


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_driven_solver_builds_with_positive_forward_flow() -> None:
    cfg = CoolPropInternalValveDrivenConfig(
        n_cells=20,
        probe_fractions=(0.375, 0.625),
        t_end_s=0.01,
    )
    solver, context = build_coolprop_internal_valve_driven_solver(cfg)
    interface = context["interface"]
    F_l, F_r, flow = interface.evaluate_fluxes(
        U=solver.U,
        eos=solver.eos,
        t=0.0,
        flux_function=solver.flux_function,
    )
    flux_q = float(
        solver.grid.geometry.area_m2
        * F_l[IDX_RHO]
        / flow["rho_upwind_kg_m3"]
    )

    assert flow["delta_p_pa"] == pytest.approx(cfg.initial_delta_p_pa, abs=1.0e-2)
    assert flow["raw_target_q_m3_s"] > 0.0
    assert flow["applied_q_m3_s"] == pytest.approx(flow["raw_target_q_m3_s"])
    assert flux_q == pytest.approx(flow["applied_q_m3_s"])
    assert flow["mach_cap_active"] is False
    assert flow["hydraulic_separation_active"] is False
    assert F_l[IDX_RHO] == pytest.approx(F_r[IDX_RHO])


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_driven_mini_run_and_artifacts(tmp_path: Path) -> None:
    cfg = CoolPropInternalValveDrivenConfig(
        n_cells=20,
        cfl=0.5,
        probe_fractions=(0.375, 0.625),
        t_end_s=0.01,
        max_steps=1000,
        relative_budget_tolerance=1.0e-8,
    )
    metrics = run_coolprop_internal_valve_driven(tmp_path, cfg)

    assert metrics["reached_target_time"] is True
    assert metrics["all_history_finite"] is True
    assert metrics["remained_single_phase"] is True
    assert metrics["initial_raw_target_q_m3_s"] > 0.0
    assert metrics["initial_applied_q_m3_s"] > 0.0
    assert metrics["initial_flux_derived_q_m3_s"] > 0.0
    assert (
        metrics["initial_raw_applied_relative_difference"]
        <= metrics["flow_relative_tolerance"]
    )
    assert (
        metrics["initial_applied_flux_relative_difference"]
        <= metrics["flow_relative_tolerance"]
    )
    assert metrics["flow_sign_consistency_fraction"] == 1.0
    assert metrics["mach_cap_activation_count"] == 0
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["validation"] is False
    assert metrics["overall_observation_execution_pass"] is True

    stem = cfg.case_name
    required = [
        f"{stem}_config.json",
        f"{stem}_metrics.json",
        f"{stem}_valve_schedule.csv",
        f"{stem}_valve_history.csv",
        f"{stem}_interface_flux_history.csv",
        f"{stem}_probe_history.csv",
        f"{stem}_boundary_history.csv",
        f"{stem}_final_profile.csv",
        f"{stem}_observation_report.md",
    ]
    for name in required:
        assert (tmp_path / name).stat().st_size > 0
    saved = json.loads(
        (tmp_path / f"{stem}_metrics.json").read_text(encoding="utf-8")
    )
    assert saved["overall_observation_execution_pass"] is True
