from __future__ import annotations

from importlib.metadata import version as distribution_version
import json

import pytest

from liquid_gas_transient.cases.v013_rigid_wall_observation import (
    leading_fraction_crossings,
    run_v013_rigid_wall_observation,
)
from liquid_gas_transient.cases.v013_rigid_wall_reflection import (
    V013RigidWallReflectionConfig,
)


def test_reflected_crossing_helper_uses_rising_side() -> None:
    result = leading_fraction_crossings(
        [0.0, 1.0, 2.0, 3.0, 4.0],
        [0.0, 2.0, 10.0, 5.0, 0.0],
    )
    assert result["detected"] is True
    assert result["crossing_times_s"]["p50"] == pytest.approx(1.375)


@pytest.mark.numerical_regression
@pytest.mark.coolprop_installed
def test_v013b_installed_runner_writes_traceable_artifacts(tmp_path) -> None:
    pytest.importorskip("CoolProp")
    coolprop_version = distribution_version("CoolProp")
    cfg = V013RigidWallReflectionConfig(fvm_mesh_cells=(40,))
    metrics = run_v013_rigid_wall_observation(tmp_path, cfg)

    assert metrics["planned_run_count"] == 1
    assert metrics["executed_run_count"] == 1
    assert metrics["overall_execution_pass"] is True
    assert metrics["aggregate_analysis_complete"] is True
    assert metrics["comparison_plots_complete"] is False
    assert metrics["formal_fvm_regression_band_applied"] is False
    assert metrics["reference_calls_coolprop"] is False
    assert metrics["production_solver_behavior_changed"] is False
    assert metrics["validation"] is False
    assert metrics["design_evaluation"] is False
    assert metrics["acceptance_gate"] is False
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["coolprop_version"] == coolprop_version

    case_id = metrics["run_plan"][0]["case_id"]
    run_dir = tmp_path / case_id
    required = [
        tmp_path / "v013b_config.json",
        tmp_path / "v013b_reference_constants.json",
        tmp_path / "v013b_run_plan.json",
        tmp_path / "v013b_matched_sample_plan.json",
        tmp_path / "v013b_probe_plan.json",
        tmp_path / "v013b_summary.csv",
        tmp_path / "v013b_metrics.json",
        tmp_path / "v013b_observation_report.md",
        tmp_path / "v013b_plot_metrics.json",
        run_dir / "fvm_config.json",
        run_dir / "fvm_metrics.json",
        run_dir / "fvm_probe_history.csv",
        run_dir / "fvm_boundary_history.csv",
        run_dir / "fvm_field_history.npz",
        run_dir / "moc_config.json",
        run_dir / "moc_metrics.json",
        run_dir / "moc_history.npz",
        run_dir / "analytical_samples.csv",
        run_dir / "matched_samples.csv",
        run_dir / "probe_comparison.csv",
        run_dir / "comparison_metrics.json",
    ]
    assert all(path.is_file() and path.stat().st_size > 0 for path in required)

    reference = json.loads(
        (tmp_path / "v013b_reference_constants.json").read_text(encoding="utf-8")
    )
    fvm = json.loads((run_dir / "fvm_metrics.json").read_text(encoding="utf-8"))
    moc = json.loads((run_dir / "moc_metrics.json").read_text(encoding="utf-8"))
    comparison = json.loads(
        (run_dir / "comparison_metrics.json").read_text(encoding="utf-8")
    )
    plot_metrics = json.loads(
        (tmp_path / "v013b_plot_metrics.json").read_text(encoding="utf-8")
    )

    assert reference["coolprop_version"] == coolprop_version
    assert reference["moc_calls_coolprop"] is False
    assert fvm["coolprop_version"] == coolprop_version
    assert fvm["overall_fvm_health_pass"] is True
    assert fvm["solver_physics_changed"] is False
    assert fvm["right_boundary"] == "ReflectiveBoundary"
    assert fvm["boundary_metrics"]["wall_window_sample_count"] > 0
    assert moc["overall_moc_reference_pass"] is True
    assert moc["calls_coolprop"] is False
    assert comparison["comparison_analysis_complete"] is True
    assert comparison["fvm_expected_reflection_signs_observed"] is True
    assert comparison["formal_fvm_regression_band_applied"] is False
    assert len(comparison["field_metrics"]) == 7
    assert len(comparison["probe_reflection_metrics"]) == 3
    for probe in comparison["probe_reflection_metrics"]:
        fvm_probe = probe["implementations"]["fvm"]
        assert fvm_probe["detected"] is True
        assert fvm_probe["pressure_reflection_coefficient"] > 0.0
        assert fvm_probe["velocity_reflection_coefficient"] < 0.0
    assert plot_metrics["plotting_status"] == (
        "PENDING_SAVED_ARTIFACT_PLOTTER_INCREMENT"
    )
    assert plot_metrics["solver_rerun"] is False
