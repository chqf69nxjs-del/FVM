from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_opening_ramp import (
    build_coolprop_internal_valve_opening_ramp_solver,
    opening_ramp_timing,
    run_coolprop_internal_valve_opening_ramp,
)
from liquid_gas_transient.cases.internal_valve_opening_ramp_config import (
    CoolPropInternalValveOpeningRampConfig,
    opening_roundoff_tolerance,
)
from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.state import IDX_RHO


def test_opening_ramp_config_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="even integer"):
        CoolPropInternalValveOpeningRampConfig(n_cells=21)
    with pytest.raises(ValueError, match="initial < final"):
        CoolPropInternalValveOpeningRampConfig(
            open_initial=0.5,
            open_final=0.5,
        )
    with pytest.raises(ValueError, match="ramp_duration_s"):
        CoolPropInternalValveOpeningRampConfig(ramp_duration_s=0.0)
    with pytest.raises(ValueError, match="upstream probe"):
        CoolPropInternalValveOpeningRampConfig(
            probe_fractions=(0.625, 0.75),
        )


def test_opening_ramp_tolerance_is_machine_scale() -> None:
    cfg = CoolPropInternalValveOpeningRampConfig()
    assert opening_roundoff_tolerance(cfg) == pytest.approx(
        8.0 * np.spacing(1.0)
    )


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_opening_ramp_solver_starts_closed_and_separated() -> None:
    cfg = CoolPropInternalValveOpeningRampConfig(
        n_cells=20,
        probe_fractions=(0.45, 0.55),
        t_end_s=0.02,
    )
    solver, context = build_coolprop_internal_valve_opening_ramp_solver(cfg)
    interface = context["interface"]
    schedule = context["opening_schedule"]
    F_l, F_r, flow = interface.evaluate_fluxes(
        U=solver.U,
        eos=solver.eos,
        t=0.0,
        flux_function=solver.flux_function,
    )

    assert schedule.opening(0.0) == pytest.approx(cfg.open_initial)
    assert schedule.opening(cfg.ramp_start_s) == pytest.approx(cfg.open_initial)
    assert schedule.opening(
        cfg.ramp_start_s + 0.5 * cfg.ramp_duration_s
    ) == pytest.approx(0.5)
    assert schedule.opening(cfg.ramp_end_s) == pytest.approx(cfg.open_final)
    assert flow["applied_q_m3_s"] == pytest.approx(0.0)
    assert flow["hydraulic_separation_active"] is True
    assert F_l[IDX_RHO] == pytest.approx(0.0)
    assert F_r[IDX_RHO] == pytest.approx(0.0)


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_opening_ramp_timing_is_after_ramp_and_before_boundary() -> None:
    cfg = CoolPropInternalValveOpeningRampConfig(
        n_cells=20,
        probe_fractions=(0.45, 0.55),
    )
    solver, context = build_coolprop_internal_valve_opening_ramp_solver(cfg)
    probes = []
    valve_x = float(context["valve_x_m"])
    for fraction in cfg.probe_fractions:
        target = fraction * cfg.pipe_length_m
        index = int(np.argmin(np.abs(solver.grid.cell_centers - target)))
        x_m = float(solver.grid.cell_centers[index])
        probes.append(
            {
                "probe_name": f"x_over_L_{fraction:g}",
                "probe_cell_center_x_m": x_m,
                "probe_side": "left" if x_m < valve_x else "right",
            }
        )
    timing = opening_ramp_timing(cfg, context, probes)
    assert timing["target_time_s"] > cfg.ramp_end_s
    assert (
        timing["target_time_s"]
        < timing["first_boundary_arrival_time_s"]
    )


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_opening_ramp_mini_run_and_artifacts(tmp_path: Path) -> None:
    cfg = CoolPropInternalValveOpeningRampConfig(
        n_cells=20,
        cfl=0.5,
        probe_fractions=(0.45, 0.55),
        ramp_start_s=0.001,
        ramp_duration_s=0.002,
        t_end_s=0.015,
        max_steps=1000,
        relative_budget_tolerance=1.0e-8,
    )
    metrics = run_coolprop_internal_valve_opening_ramp(tmp_path, cfg)

    assert metrics["reached_target_time"] is True
    assert metrics["all_history_finite"] is True
    assert metrics["remained_single_phase"] is True
    assert metrics["opening_monotonic_non_decreasing"] is True
    assert metrics["max_abs_opening_error"] <= metrics[
        "opening_roundoff_tolerance"
    ]
    assert metrics["initial_applied_q_m3_s"] == pytest.approx(0.0)
    assert metrics["max_applied_q_m3_s"] > 0.0
    assert metrics["final_applied_q_m3_s"] > 0.0
    assert metrics["flow_sign_consistency_fraction"] == 1.0
    assert metrics["mach_cap_activation_count"] == 0
    assert metrics["primary_characteristic_direction_pass"] is True
    assert metrics["upstream_decompression_observed"] is True
    assert metrics["downstream_compression_observed"] is True
    assert metrics["overall_observation_execution_pass"] is True
    assert metrics["property_backend_design_status"] == (
        "not_approved_for_design_use"
    )
    assert metrics["validation"] is False

    stem = cfg.case_name
    required = [
        f"{stem}_config.json",
        f"{stem}_metrics.json",
        f"{stem}_valve_schedule.csv",
        f"{stem}_valve_history.csv",
        f"{stem}_interface_flux_history.csv",
        f"{stem}_probe_history.csv",
        f"{stem}_probe_characteristic_summary.csv",
        f"{stem}_boundary_history.csv",
        f"{stem}_final_profile.csv",
        f"{stem}_field_history.npz",
        f"{stem}_observation_report.md",
    ]
    for name in required:
        assert (tmp_path / name).stat().st_size > 0
    saved = json.loads(
        (tmp_path / f"{stem}_metrics.json").read_text(encoding="utf-8")
    )
    assert saved["verification_item"] == "V-012C"
    assert saved["overall_observation_execution_pass"] is True
