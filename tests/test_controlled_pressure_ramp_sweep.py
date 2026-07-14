from __future__ import annotations

import csv
from pathlib import Path

import pytest

import liquid_gas_transient.cases.coolprop_controlled_pressure_ramp_sweep as sweep
from liquid_gas_transient.cases.coolprop_controlled_pressure_ramp_sweep import (
    CoolPropControlledPressureRampSweepConfig,
    build_run_plan,
    case_id_for,
    classify_mesh_observation,
    run_coolprop_controlled_pressure_ramp_sweep,
)


def test_case_id_and_unique_run_plan() -> None:
    cfg = CoolPropControlledPressureRampSweepConfig()
    plan = build_run_plan(cfg)
    assert case_id_for(100, 0.5) == "n0100_cfl0p5"
    assert len(plan) == 4
    assert len({item["case_id"] for item in plan}) == 4
    shared = [item for item in plan if item["n_cells"] == 100 and item["cfl"] == 0.5]
    assert len(shared) == 1
    assert set(shared[0]["comparison_groups"]) == {"mesh_comparison", "cfl_comparison"}


def test_case_id_preserves_distinct_close_cfl_values() -> None:
    assert case_id_for(100, 0.995) != case_id_for(100, 1.0)
    cfg = CoolPropControlledPressureRampSweepConfig(
        cfl_values=(0.995, 1.0),
        mesh_comparison_cfl=1.0,
    )
    plan = build_run_plan(cfg)
    assert len(plan) == 4
    assert len({item["case_id"] for item in plan}) == 4


def test_sweep_config_rejects_invalid_plan() -> None:
    with pytest.raises(ValueError, match="unique and ascending"):
        CoolPropControlledPressureRampSweepConfig(mesh_cells=(100, 50, 100))
    with pytest.raises(ValueError, match="primary_probe_fraction"):
        CoolPropControlledPressureRampSweepConfig(primary_probe_fraction=0.9)
    with pytest.raises(ValueError, match="mesh_comparison_cfl"):
        CoolPropControlledPressureRampSweepConfig(mesh_comparison_cfl=0.75)


def test_mesh_classification_reports_monotonic_improvement() -> None:
    rows = []
    for n_cells, error in ((50, 0.3), (100, 0.2), (200, 0.1)):
        rows.append({
            "n_cells": n_cells,
            "wave_speed_relative_error": error,
            "abs_common_boundary_launch_delay_s": error,
            "p50_arrival_relative_error_mean": error,
            "primary_peak_amplitude_error": error,
            "primary_opposite_direction_leakage_ratio": error,
        })
    result = classify_mesh_observation(rows)
    assert result["overall_classification"] == "monotonic_improvement"


def test_sweep_runner_writes_summary_without_duplicate_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_data: dict[str, tuple[int, float]] = {}
    baseline_calls: list[str] = []
    analysis_calls: list[str] = []
    fit_calls: list[str] = []

    def fake_baseline(output_dir: Path | str, config) -> dict:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        run_data[config.case_name] = (config.n_cells, config.cfl)
        baseline_calls.append(config.case_name)
        return {
            "n_cells": config.n_cells,
            "dx_m": config.pipe_length_m / config.n_cells,
            "cfl_target": config.cfl,
            "overall_observation_execution_pass": True,
            "remained_single_phase": True,
            "budget_mass_relative_residual": 1.0e-13,
            "energy_budget_balance_relative_residual": -1.0e-13,
            "phase_vapor_mass_balance_relative_residual": 0.0,
            "property_backend_name": "coolprop_co2",
            "coolprop_version": "8.0.0",
            "property_backend_design_status": "not_approved_for_design_use",
        }

    def fake_analysis(output_dir: Path | str, case_name: str, *, generate_plots: bool) -> dict:
        del output_dir, generate_plots
        analysis_calls.append(case_name)
        n_cells, cfl = run_data[case_name]
        mesh_error = 5.0 / n_cells
        cfl_error = 0.001 * cfl
        observations = []
        for fraction in (0.25, 0.50, 0.75):
            observations.append({
                "probe_name": f"x_over_L_{fraction:g}",
                "peak_amplitude_ratio": 1.0 - mesh_error,
                "final_amplitude_ratio": 1.0 - mesh_error,
                "opposite_direction_leakage_ratio": mesh_error * 1.0e-3,
                "linear_velocity_relative_error": mesh_error,
                "p10_arrival_relative_error": mesh_error + cfl_error,
                "p50_arrival_relative_error": mesh_error + cfl_error,
                "p90_arrival_relative_error": mesh_error + cfl_error,
            })
        return {"probe_observations": observations}

    def fake_front_fit(output_dir: Path | str, case_name: str, *, generate_plots: bool) -> dict:
        del output_dir, generate_plots
        fit_calls.append(case_name)
        n_cells, cfl = run_data[case_name]
        error = 5.0 / n_cells + 0.001 * cfl
        return {
            "numerical_p50_front_point_count": 10,
            "p50_propagation_fit": {
                "probe_count": 3,
                "inferred_wave_speed_m_s": 557.0 * (1.0 + error * 1.0e-3),
                "reference_sound_speed_m_s": 557.0,
                "wave_speed_relative_error": error * 1.0e-3,
                "common_boundary_launch_delay_s": error * 1.0e-3,
                "fit_residual_rms_s": 1.0e-8,
                "fit_residual_max_abs_s": 2.0e-8,
                "fit_r_squared": 1.0,
            },
        }

    monkeypatch.setattr(sweep, "run_coolprop_controlled_pressure_ramp", fake_baseline)
    monkeypatch.setattr(sweep, "run_controlled_pressure_ramp_analysis", fake_analysis)
    monkeypatch.setattr(sweep, "run_controlled_pressure_ramp_front_fit", fake_front_fit)

    cfg = CoolPropControlledPressureRampSweepConfig(generate_comparison_plots=False)
    metrics = run_coolprop_controlled_pressure_ramp_sweep(tmp_path, cfg)

    assert metrics["unique_run_count"] == 4
    assert metrics["overall_sweep_execution_pass"] is True
    assert metrics["formal_accuracy_threshold_applied"] is False
    assert metrics["property_backend_name"] == "coolprop_co2"
    assert metrics["coolprop_version"] == "8.0.0"
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["mesh_observation"]["overall_classification"] == "monotonic_improvement"
    assert len(metrics["cfl_observation"]["rows"]) == 2
    assert len(baseline_calls) == len(set(baseline_calls)) == 4
    assert len(analysis_calls) == len(set(analysis_calls)) == 4
    assert len(fit_calls) == len(set(fit_calls)) == 4

    stem = cfg.case_name
    expected = [
        tmp_path / f"{stem}_sweep_config.json",
        tmp_path / f"{stem}_sweep_metrics.json",
        tmp_path / f"{stem}_sweep_summary.csv",
        tmp_path / f"{stem}_sweep_report.md",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in expected)

    with (tmp_path / f"{stem}_sweep_summary.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 4
    assert {row["property_backend_name"] for row in rows} == {"coolprop_co2"}
    assert {row["coolprop_version"] for row in rows} == {"8.0.0"}
    shared = [row for row in rows if row["n_cells"] == "100" and row["cfl"] == "0.5"]
    assert len(shared) == 1
    assert set(shared[0]["comparison_groups"].split(";")) == {"mesh_comparison", "cfl_comparison"}
