from __future__ import annotations

import math
from pathlib import Path

import pytest

from liquid_gas_transient.cases.case_c_coolprop_mini_run import (
    CaseCCoolPropMiniRunConfig,
    build_case_c_coolprop_mini_run_parameters,
    run_case_c_coolprop_mini_run,
)


def test_config_validation_rejects_invalid_values() -> None:
    invalid = [
        {"initial_pressure_pa": 0.0},
        {"initial_temperature_K": 0.0},
        {"n_cells": 0},
        {"t_end_s": 0.0},
        {"cfl": 0.0},
        {"cfl": 1.1},
        {"max_steps": 0},
        {"sample_every": 0},
    ]
    for kwargs in invalid:
        with pytest.raises(ValueError):
            CaseCCoolPropMiniRunConfig(**kwargs)


def test_parameter_factory_disables_events_friction_elevation_and_phase_change() -> None:
    cfg = CaseCCoolPropMiniRunConfig()
    params = build_case_c_coolprop_mini_run_parameters(cfg)

    assert params.n_cells == cfg.n_cells
    assert params.t_end_s == cfg.t_end_s
    assert params.cfl == cfg.cfl
    assert params.upstream_initial_pressure_pa == params.downstream_initial_pressure_pa
    assert params.upstream_initial_pressure_pa == cfg.initial_pressure_pa
    assert params.initial_velocity_m_s == 0.0
    assert params.eos_model == "coolprop_lco2"
    assert params.phase_change_model == "none"
    assert params.enable_hem is False
    assert params.lco2_boundary_temperature_K == 280.0
    assert params.lco2_quality_source == "transported"
    assert params.pump_delta_p_nominal_pa == 0.0
    assert params.pump_trip_start_s is None
    assert params.pump_trip_duration_s == 0.0
    assert params.pump_delta_p_final_pa == 0.0
    assert params.valve_close_start_s > cfg.t_end_s
    assert params.valve_close_time_s > 0.0
    assert params.valve_kv_m3_h is not None
    assert math.isfinite(params.valve_kv_m3_h)
    assert params.valve_kv_m3_h > 0.0
    assert params.darcy_friction_factor == 0.0
    assert params.onshore_elevation_start_m == 0.0
    assert params.onshore_elevation_end_m == 0.0
    assert params.jetty_elevation_start_m == 0.0
    assert params.jetty_elevation_end_m == 0.0
    assert params.loading_arm_elevation_start_m == 0.0
    assert params.loading_arm_elevation_end_m == 0.0
    assert params.latent_heat_placeholder_j_kg == 0.0


def test_coolprop_mini_run_completes_and_writes_artifacts(tmp_path: Path) -> None:
    pytest.importorskip("CoolProp")
    cfg = CaseCCoolPropMiniRunConfig(n_cells=8, t_end_s=1.0e-5, max_steps=10000)

    metrics = run_case_c_coolprop_mini_run(output_dir=tmp_path, config=cfg)

    assert metrics["completed_without_exception"] is True
    assert metrics["final_time_s"] == pytest.approx(cfg.t_end_s, rel=1.0e-12, abs=1.0e-15)
    assert metrics["step_count"] <= cfg.max_steps
    assert metrics["mini_run"] is True
    assert metrics["design_evaluation"] is False
    assert metrics["acceptance_gate"] is False
    assert metrics["validation"] is False
    assert metrics["software_path_verification"] is True
    assert metrics["overall_software_path_pass"] is True
    assert metrics["property_backend_name"] == "coolprop_co2"
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["quality_source"] == "transported"
    assert metrics["coolprop_available"] is True
    assert metrics["saturation_temperature_margin_status"] == "not_applicable_above_critical_pressure"

    finite_keys = [
        "initial_density_kg_m3",
        "initial_internal_energy_j_kg",
        "initial_sound_speed_m_s",
        "final_pressure_pa",
        "final_temperature_K",
        "final_density_kg_m3",
        "final_sound_speed_m_s",
        "final_dt_s",
        "max_cfl",
    ]
    for key in finite_keys:
        assert math.isfinite(metrics[key]), key
    assert metrics["min_density_kg_m3"] > 0.0
    assert metrics["min_pressure_pa"] > 0.0
    assert metrics["min_temperature_K"] > 0.0
    assert metrics["min_sound_speed_m_s"] > 0.0
    assert metrics["initial_quality"] == 0.0
    assert metrics["initial_alpha"] == 0.0
    assert metrics["final_vapor_mass_fraction"] == 0.0
    assert metrics["final_alpha"] == 0.0

    expected = [
        "case_c_coolprop_mini_run_config.json",
        "case_c_coolprop_mini_run_metrics.json",
        "case_c_coolprop_mini_run_history.csv",
        "case_c_coolprop_mini_run_final_profile.csv",
        "case_c_coolprop_mini_run_report.md",
    ]
    for name in expected:
        path = tmp_path / name
        assert path.exists(), name
        assert path.stat().st_size > 0, name
