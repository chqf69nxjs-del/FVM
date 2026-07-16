from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.cases.coolprop_internal_valve_closing_ramp import (
    _characteristic_summary,
    build_coolprop_internal_valve_closing_ramp_solver,
    closing_ramp_timing,
    run_coolprop_internal_valve_closing_ramp,
)
from liquid_gas_transient.cases.internal_valve_closing_ramp_config import (
    CoolPropInternalValveClosingRampConfig,
    opening_roundoff_tolerance,
)
from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.state import IDX_RHO, IDX_RHOE, IDX_RHO_XV


def test_closing_ramp_config_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="even integer"):
        CoolPropInternalValveClosingRampConfig(n_cells=21)
    with pytest.raises(ValueError, match="final < initial"):
        CoolPropInternalValveClosingRampConfig(
            open_initial=0.5,
            open_final=0.5,
        )
    with pytest.raises(ValueError, match="ramp_duration_s"):
        CoolPropInternalValveClosingRampConfig(ramp_duration_s=0.0)
    with pytest.raises(ValueError, match="post_closure_hold_s"):
        CoolPropInternalValveClosingRampConfig(post_closure_hold_s=0.0)
    with pytest.raises(ValueError, match="post-closure hold"):
        CoolPropInternalValveClosingRampConfig(t_end_s=0.016)
    with pytest.raises(ValueError, match="upstream probe"):
        CoolPropInternalValveClosingRampConfig(
            probe_fractions=(0.625, 0.75),
        )


def test_closing_ramp_tolerance_is_machine_scale() -> None:
    cfg = CoolPropInternalValveClosingRampConfig()
    assert opening_roundoff_tolerance(cfg) == pytest.approx(8.0 * np.spacing(1.0))


def test_closing_characteristic_summary_rebases_pre_arrival_background() -> None:
    cfg = CoolPropInternalValveClosingRampConfig(
        ramp_start_s=0.001,
        ramp_duration_s=0.002,
        post_closure_hold_s=0.001,
        t_end_s=0.01,
        probe_fractions=(0.45, 0.55),
    )
    probes = [
        {
            "probe_name": "left",
            "probe_cell_center_x_m": 45.0,
            "probe_side": "left",
        },
        {
            "probe_name": "right",
            "probe_cell_center_x_m": 55.0,
            "probe_side": "right",
        },
    ]
    context = {
        "valve_x_m": 50.0,
        "left_state": {"c_m_s": 1000.0},
        "right_state": {"c_m_s": 1000.0},
    }
    rows = [
        {
            "probe_name": "left",
            "time_s": 0.005,
            "delta_pressure_pa": -5.0,
            "velocity_m_s": -0.01,
            "A_plus_pa": -1.0,
            "A_minus_pa": -10.0,
        },
        {
            "probe_name": "left",
            "time_s": 0.006,
            "delta_pressure_pa": 7.0,
            "velocity_m_s": 0.01,
            "A_plus_pa": 0.0,
            "A_minus_pa": 10.0,
        },
        {
            "probe_name": "right",
            "time_s": 0.005,
            "delta_pressure_pa": 5.0,
            "velocity_m_s": 0.01,
            "A_plus_pa": 10.0,
            "A_minus_pa": 1.0,
        },
        {
            "probe_name": "right",
            "time_s": 0.006,
            "delta_pressure_pa": -7.0,
            "velocity_m_s": -0.01,
            "A_plus_pa": -10.0,
            "A_minus_pa": 0.0,
        },
    ]

    summary = _characteristic_summary(rows, probes, cfg, context)

    assert len(summary) == 2
    assert summary[0]["baseline_time_s"] == pytest.approx(0.005)
    assert summary[0]["desired_increment_peak_pa"] == pytest.approx(20.0)
    assert summary[0]["pressure_increment_extreme_pa"] == pytest.approx(12.0)
    assert summary[0]["direction_observation_pass"] is True
    assert summary[1]["desired_increment_peak_pa"] == pytest.approx(-20.0)
    assert summary[1]["pressure_increment_extreme_pa"] == pytest.approx(-12.0)
    assert summary[1]["direction_observation_pass"] is True


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_closing_ramp_solver_starts_open_and_reaches_reflective_closure() -> None:
    cfg = CoolPropInternalValveClosingRampConfig(
        n_cells=20,
        probe_fractions=(0.45, 0.55),
        ramp_start_s=0.001,
        ramp_duration_s=0.002,
        post_closure_hold_s=0.001,
        t_end_s=0.015,
    )
    solver, context = build_coolprop_internal_valve_closing_ramp_solver(cfg)
    interface = context["interface"]
    schedule = context["opening_schedule"]

    F_l_open, F_r_open, flow_open = interface.evaluate_fluxes(
        U=solver.U,
        eos=solver.eos,
        t=0.0,
        flux_function=solver.flux_function,
    )
    F_l_closed, F_r_closed, flow_closed = interface.evaluate_fluxes(
        U=solver.U,
        eos=solver.eos,
        t=cfg.ramp_end_s,
        flux_function=solver.flux_function,
    )

    assert schedule.opening(0.0) == pytest.approx(cfg.open_initial)
    assert schedule.opening(cfg.ramp_start_s) == pytest.approx(cfg.open_initial)
    assert schedule.opening(
        cfg.ramp_start_s + 0.5 * cfg.ramp_duration_s
    ) == pytest.approx(0.5)
    assert schedule.opening(cfg.ramp_end_s) == pytest.approx(cfg.open_final)
    assert flow_open["applied_q_m3_s"] > 0.0
    assert flow_open["hydraulic_separation_active"] is False
    assert F_l_open[IDX_RHO] == pytest.approx(F_r_open[IDX_RHO])
    assert flow_closed["applied_q_m3_s"] == pytest.approx(0.0)
    assert flow_closed["hydraulic_separation_active"] is True
    for flux in (F_l_closed, F_r_closed):
        assert flux[IDX_RHO] == pytest.approx(0.0)
        assert flux[IDX_RHOE] == pytest.approx(0.0)
        assert flux[IDX_RHO_XV] == pytest.approx(0.0)


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_closing_ramp_timing_is_probe_complete_and_before_initial_boundary_arrival() -> (
    None
):
    cfg = CoolPropInternalValveClosingRampConfig(
        n_cells=20,
        probe_fractions=(0.45, 0.55),
        ramp_start_s=0.001,
        ramp_duration_s=0.002,
        post_closure_hold_s=0.001,
    )
    solver, context = build_coolprop_internal_valve_closing_ramp_solver(cfg)
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
    timing = closing_ramp_timing(cfg, context, probes)
    assert timing["target_time_s"] >= cfg.minimum_post_closure_end_s
    assert timing["target_time_s"] >= timing["full_ramp_probe_observation_time_s"]
    assert timing["first_boundary_arrival_time_s"] == pytest.approx(
        timing["boundary_travel_time_s"]
    )
    assert timing["target_time_s"] < timing["first_boundary_arrival_time_s"]


@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_closing_ramp_mini_run_and_artifacts(tmp_path: Path) -> None:
    cfg = CoolPropInternalValveClosingRampConfig(
        n_cells=20,
        cfl=0.5,
        probe_fractions=(0.45, 0.55),
        ramp_start_s=0.001,
        ramp_duration_s=0.002,
        post_closure_hold_s=0.005,
        t_end_s=0.015,
        max_steps=1000,
        relative_budget_tolerance=1.0e-8,
    )
    metrics = run_coolprop_internal_valve_closing_ramp(tmp_path, cfg)

    assert metrics["reached_target_time"] is True
    assert metrics["included_configured_post_closure_hold"] is True
    assert metrics["all_history_finite"] is True
    assert metrics["remained_single_phase"] is True
    assert metrics["opening_monotonic_non_increasing"] is True
    assert metrics["max_abs_opening_error"] <= metrics["opening_roundoff_tolerance"]
    assert metrics["initial_applied_q_m3_s"] > 0.0
    assert abs(metrics["final_applied_q_m3_s"]) <= metrics["q_roundoff_tolerance_m3_s"]
    assert metrics["post_closure_sample_count"] > 0
    assert metrics["post_closure_hydraulic_separation_fraction"] == 1.0
    assert metrics["post_closure_no_flow_direction_fraction"] == 1.0
    assert (
        metrics["max_abs_post_closure_mass_flux_kg_m2_s"]
        <= metrics["mass_flux_roundoff_tolerance_kg_m2_s"]
    )
    assert (
        metrics["max_abs_post_closure_energy_flux_w_m2"]
        <= metrics["energy_flux_roundoff_tolerance_w_m2"]
    )
    assert (
        metrics["max_abs_post_closure_vapor_mass_flux_kg_m2_s"]
        <= metrics["vapor_flux_roundoff_tolerance_kg_m2_s"]
    )
    assert metrics["flow_sign_consistency_fraction"] == 1.0
    assert metrics["mach_cap_activation_count"] == 0
    assert metrics["primary_characteristic_direction_pass"] is True
    assert metrics["upstream_compression_observed"] is True
    assert metrics["downstream_decompression_observed"] is True
    assert metrics["overall_observation_execution_pass"] is True
    assert metrics["property_backend_design_status"] == ("not_approved_for_design_use")
    assert metrics["validation"] is False
    assert metrics["esd_event_verification"] is False
    assert metrics["finite_opening_momentum_relation_applied_to_closed_rows"] is False

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
    saved = json.loads((tmp_path / f"{stem}_metrics.json").read_text(encoding="utf-8"))
    assert saved["verification_item"] == "V-012D"
    assert saved["overall_observation_execution_pass"] is True
