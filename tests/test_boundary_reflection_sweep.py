from __future__ import annotations

import csv
from pathlib import Path

import pytest

import liquid_gas_transient.cases.coolprop_boundary_reflection_sweep as sweep
from liquid_gas_transient.cases.coolprop_boundary_reflection_sweep import (
    CoolPropBoundaryReflectionSweepConfig,
    build_run_plan,
    case_id_for,
    classify_mesh_observation,
    run_coolprop_boundary_reflection_sweep,
)


def test_case_id_and_unique_run_plan() -> None:
    cfg = CoolPropBoundaryReflectionSweepConfig()
    plan = build_run_plan(cfg)
    assert case_id_for("rigid_wall", 100, 0.5) == "rigid_wall_n0100_cfl050"
    assert len(plan) == 8
    assert len({item["case_id"] for item in plan}) == 8
    for boundary in cfg.boundary_kinds:
        selected = [item for item in plan if item["boundary_kind"] == boundary]
        assert len(selected) == 4
        shared = [item for item in selected if item["n_cells"] == 100 and item["cfl"] == 0.5]
        assert len(shared) == 1
        assert set(shared[0]["comparison_groups"]) == {"mesh_comparison", "cfl_comparison"}


def test_sweep_config_rejects_invalid_plan() -> None:
    with pytest.raises(ValueError, match="unique, ascending"):
        CoolPropBoundaryReflectionSweepConfig(mesh_cells=(100, 50, 100))
    with pytest.raises(ValueError, match="primary_probe_fraction"):
        CoolPropBoundaryReflectionSweepConfig(primary_probe_fraction=0.8)


def test_mesh_classification_reports_monotonic_improvement() -> None:
    rows = []
    for n, error in ((50, 0.3), (100, 0.2), (200, 0.1)):
        rows.append(
            {
                "n_cells": n,
                "pressure_reflection_magnitude_error": error,
                "reflected_arrival_time_relative_error": error,
                "boundary_residual": error,
                "reflected_characteristic_leakage_ratio": error,
                "waveform_l2_difference_vs_finest": 0.0 if n == 200 else error,
            }
        )
    result = classify_mesh_observation(rows)
    assert result["overall_classification"] == "monotonic_improvement"


def _write_probe_history(path: Path, case_name: str, coefficient: float) -> None:
    fields = ["time_s", "probe_name", "A_plus_pa", "A_minus_pa"]
    rows = []
    for probe_name in ("x_over_L_0.75", "x_over_L_0.9"):
        for time_s, a_plus, a_minus in (
            (0.00, 0.0, 0.0),
            (0.05, 500.0, 0.0),
            (0.06, 1000.0, 0.0),
            (0.07, 500.0, 0.0),
            (0.10, 0.0, 0.0),
            (0.11, 0.0, coefficient * 500.0),
            (0.12, 0.0, coefficient * 1000.0),
            (0.13, 0.0, coefficient * 500.0),
            (0.15, 0.0, 0.0),
        ):
            rows.append(
                {
                    "time_s": time_s,
                    "probe_name": probe_name,
                    "A_plus_pa": a_plus,
                    "A_minus_pa": a_minus,
                }
            )
    with (path / f"{case_name}_probe_history.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fake_runner(output_dir: Path | str, config) -> dict:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    expected = 1.0 if config.boundary_kind == "rigid_wall" else -1.0
    mesh_error = 5.0 / config.n_cells
    coefficient = expected * (1.0 - mesh_error)
    _write_probe_history(directory, str(config.case_name), coefficient)
    probe = {
        "probe_name": "x_over_L_0.9",
        "incident_window_start_s": 0.04,
        "incident_window_end_s": 0.08,
        "reflected_window_start_s": 0.10,
        "reflected_window_end_s": 0.14,
        "expected_pressure_reflection_coefficient": expected,
        "pressure_reflection_coefficient": coefficient,
        "reflected_arrival_time_relative_error": mesh_error,
        "incident_A_minus_leakage_peak_pa": mesh_error,
        "incident_A_plus_peak_pa": 1000.0,
        "reflected_A_plus_leakage_peak_pa": mesh_error,
        "reflected_A_minus_signed_extremum_pa": coefficient * 1000.0,
    }
    boundary_metrics = (
        {"max_abs_wall_velocity_m_s": mesh_error * 1.0e-3}
        if config.boundary_kind == "rigid_wall"
        else {"normalized_fixed_pressure_residual": mesh_error}
    )
    return {
        "boundary_kind": config.boundary_kind,
        "n_cells": config.n_cells,
        "dx_m": config.pipe_length_m / config.n_cells,
        "cfl_target": config.cfl,
        "overall_observation_execution_pass": True,
        "pressure_amplitude_pa": config.pressure_amplitude_pa,
        "Z0": 1.0e6,
        "boundary_metrics": boundary_metrics,
        "budget_mass_relative_residual": 1.0e-12,
        "energy_budget_balance_relative_residual": 1.0e-12,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "remained_single_phase": True,
        "property_backend_design_status": "not_approved_for_design_use",
        "probes": [probe],
    }


def test_sweep_runner_writes_summary_artifacts_without_duplicate_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "run_coolprop_boundary_reflection", _fake_runner)
    cfg = CoolPropBoundaryReflectionSweepConfig(generate_comparison_plots=False)
    metrics = run_coolprop_boundary_reflection_sweep(tmp_path, cfg)

    assert metrics["unique_run_count"] == 8
    assert metrics["overall_sweep_execution_pass"] is True
    assert len(metrics["summary_rows"]) == 8
    assert metrics["formal_accuracy_threshold_applied"] is False
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert set(metrics["mesh_observations"]) == {"rigid_wall", "fixed_pressure"}

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
    assert len(rows) == 8
    shared = [row for row in rows if row["boundary_kind"] == "rigid_wall" and row["n_cells"] == "100" and row["cfl"] == "0.5"]
    assert len(shared) == 1
    assert set(shared[0]["comparison_groups"].split(";")) == {"mesh_comparison", "cfl_comparison"}
