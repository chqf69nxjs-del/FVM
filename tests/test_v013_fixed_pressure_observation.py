from __future__ import annotations

from importlib.metadata import version as distribution_version
import inspect
import json
import math

import numpy as np
import pytest

import liquid_gas_transient.cases.v013_fixed_pressure_observation as runner_module
import liquid_gas_transient.plot_v013_fixed_pressure_results as plot_module
from liquid_gas_transient.cases.v013_fixed_pressure_observation import (
    _reflection_metrics_for_signal,
    run_v013_fixed_pressure_observation,
)
from liquid_gas_transient.cases.v013_fixed_pressure_reflection import (
    V013FixedPressureReflectionConfig,
)
from liquid_gas_transient.plot_v013_fixed_pressure_results import (
    EXPECTED_PLOT_COUNT,
    build_v013c_plot_traceability,
    plot_v013_fixed_pressure_results,
)


def test_fixed_pressure_reflection_metric_helper_uses_negative_a_minus() -> None:
    time_s = np.linspace(0.0, 4.0, 17)
    a_plus = np.zeros_like(time_s)
    a_minus = np.zeros_like(time_s)
    velocity = np.zeros_like(time_s)
    a_plus[1:6] = [0.0, 5.0, 10.0, 5.0, 0.0]
    velocity[1:6] = a_plus[1:6] / 100.0
    a_minus[10:15] = [0.0, -4.0, -8.0, -4.0, 0.0]
    velocity[10:15] = -a_minus[10:15] / 100.0
    timing = {
        "incident_window_start_s": 0.0,
        "incident_window_end_s": 1.5,
        "reflected_window_start_s": 2.25,
        "reflected_window_end_s": 3.75,
    }
    metrics = _reflection_metrics_for_signal(
        time_s,
        a_plus,
        a_minus,
        velocity,
        timing,
    )
    assert metrics["detected"] is True
    assert metrics["pressure_reflection_coefficient"] == pytest.approx(-0.8)
    assert metrics["velocity_reflection_coefficient"] == pytest.approx(0.8)
    assert metrics["expected_pressure_sign_observed"] is True
    assert metrics["expected_velocity_sign_observed"] is True
    assert metrics["reflected_p50_time_s"] is not None


def test_v013c_runner_source_does_not_modify_production_classes() -> None:
    source = inspect.getsource(runner_module)
    assert "class FvmSolver" not in source
    assert "class PressureTankBoundary" not in source
    assert "solver_physics_changed" in source
    assert '"fixed_pressure"' in source


def test_v013c_plot_traceability_requires_case_model_backend_and_versions() -> None:
    text = build_v013c_plot_traceability(
        {
            "case_name": "v013c_fixed_pressure_reflection",
            "output_version": "v013c_fixed_pressure_reflection_v1",
            "property_backend_name": "coolprop_co2",
            "coolprop_version": "8.0.0",
        }
    )
    assert "case: v013c_fixed_pressure_reflection" in text
    assert "model: production FVM / independent linear-acoustic MOC + analytical" in text
    assert "backend: coolprop_co2" in text
    assert "CoolProp: 8.0.0" in text
    assert "output: v013c_fixed_pressure_reflection_v1" in text
    assert "not physical Validation or design-use acceptance" in text

    with pytest.raises(ValueError, match="coolprop_version"):
        build_v013c_plot_traceability(
            {
                "case_name": "v013c_fixed_pressure_reflection",
                "output_version": "v013c_fixed_pressure_reflection_v1",
                "property_backend_name": "coolprop_co2",
            }
        )


def test_v013c_plotter_has_no_solver_runner_import_or_call() -> None:
    source = inspect.getsource(plot_module)
    assert "run_v013_fixed_pressure_observation" not in source
    assert "FvmSolver" not in source
    assert "PressureTankBoundary" not in source


@pytest.mark.numerical_regression
@pytest.mark.coolprop_installed
def test_v013c_installed_runner_writes_traceable_artifacts(tmp_path) -> None:
    pytest.importorskip("CoolProp")
    pytest.importorskip("matplotlib")
    coolprop_version = distribution_version("CoolProp")
    cfg = V013FixedPressureReflectionConfig(fvm_mesh_cells=(40,))
    metrics = run_v013_fixed_pressure_observation(tmp_path, cfg)

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
    assert metrics["fixed_pressure_boundary_allows_nonzero_mass_flux"] is True
    assert metrics["fixed_pressure_boundary_allows_nonzero_energy_flux"] is True

    case_id = metrics["run_plan"][0]["case_id"]
    run_dir = tmp_path / case_id
    required = [
        tmp_path / "v013c_config.json",
        tmp_path / "v013c_reference_constants.json",
        tmp_path / "v013c_run_plan.json",
        tmp_path / "v013c_matched_sample_plan.json",
        tmp_path / "v013c_probe_plan.json",
        tmp_path / "v013c_summary.csv",
        tmp_path / "v013c_metrics.json",
        tmp_path / "v013c_observation_report.md",
        tmp_path / "v013c_plot_metrics.json",
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
        (tmp_path / "v013c_reference_constants.json").read_text(encoding="utf-8")
    )
    fvm = json.loads((run_dir / "fvm_metrics.json").read_text(encoding="utf-8"))
    moc = json.loads((run_dir / "moc_metrics.json").read_text(encoding="utf-8"))
    comparison = json.loads(
        (run_dir / "comparison_metrics.json").read_text(encoding="utf-8")
    )

    assert reference["coolprop_version"] == coolprop_version
    assert reference["moc_calls_coolprop"] is False
    assert fvm["coolprop_version"] == coolprop_version
    assert fvm["overall_fvm_health_pass"] is True
    assert fvm["solver_physics_changed"] is False
    assert "PressureTankBoundary" in fvm["right_boundary"]
    boundary = fvm["boundary_metrics"]
    assert boundary["boundary_window_sample_count"] > 0
    assert boundary["zero_mass_flux_expected"] is False
    assert boundary["zero_energy_flux_expected"] is False
    for key in (
        "normalized_fixed_pressure_residual",
        "boundary_velocity_amplification_ratio",
        "boundary_velocity_amplification_error",
        "integrated_right_boundary_mass_kg",
        "integrated_right_boundary_energy_j",
    ):
        assert math.isfinite(float(boundary[key]))

    assert moc["overall_moc_reference_pass"] is True
    assert moc["calls_coolprop"] is False
    assert moc["right_boundary"] == "fixed_pressure"
    assert comparison["comparison_analysis_complete"] is True
    assert comparison["fvm_expected_reflection_signs_observed"] is True
    assert comparison["formal_fvm_regression_band_applied"] is False
    assert len(comparison["field_metrics"]) == 7
    assert len(comparison["probe_reflection_metrics"]) == 3

    pressure_policy = (
        "abs(analytical_a_plus_pa) + abs(analytical_a_minus_pa)"
    )
    velocity_policy = (
        "(abs(analytical_a_plus_pa) + abs(analytical_a_minus_pa)) "
        "/ (rho0 * c0)"
    )
    policy = comparison["field_error_normalization_policy"]
    assert policy["pressure_perturbation_pa"] == pressure_policy
    assert policy["velocity_m_s"] == velocity_policy

    contact = next(
        sample
        for sample in comparison["field_metrics"]
        if sample["phase"] == "boundary_contact"
    )
    for sample in comparison["field_metrics"]:
        assert sample["normalization_policy"] == policy
        for implementation in ("fvm", "moc"):
            for field in (
                "pressure_perturbation_pa",
                "velocity_m_s",
                "a_plus_pa",
                "a_minus_pa",
            ):
                norms = sample[implementation][field]
                for metric_name in (
                    "l1_relative",
                    "l2_relative",
                    "linf_relative",
                    "linf_absolute",
                ):
                    assert math.isfinite(float(norms[metric_name]))
    assert contact["fvm"]["pressure_perturbation_pa"]["l2_relative"] < 1.0e6
    assert contact["fvm"]["velocity_m_s"]["l2_relative"] < 1.0e6

    for probe in comparison["probe_reflection_metrics"]:
        assert "theoretical_boundary_time_s" in probe["timing"]
        fvm_probe = probe["implementations"]["fvm"]
        assert fvm_probe["detected"] is True
        assert fvm_probe["pressure_reflection_coefficient"] < 0.0
        assert fvm_probe["velocity_reflection_coefficient"] > 0.0

    plot_result = plot_v013_fixed_pressure_results(tmp_path)
    assert plot_result["plotting_errors"] == {}
    assert plot_result["plot_count"] == EXPECTED_PLOT_COUNT, plot_result[
        "plotting_errors"
    ]
    assert plot_result["expected_plot_count"] == EXPECTED_PLOT_COUNT
    assert plot_result["solver_rerun"] is False
    assert plot_result["numerical_results_changed"] is False
    assert plot_result["property_backend_name"] == "coolprop_co2"
    assert plot_result["coolprop_version"] == coolprop_version
    assert all(
        (tmp_path / name).is_file() and (tmp_path / name).stat().st_size > 0
        for name in plot_result["plot_files"]
    )

    plot_metrics = json.loads(
        (tmp_path / "v013c_plot_metrics.json").read_text(encoding="utf-8")
    )
    aggregate = json.loads(
        (tmp_path / "v013c_metrics.json").read_text(encoding="utf-8")
    )
    assert plot_metrics["plot_count"] == EXPECTED_PLOT_COUNT
    assert plot_metrics["model"] == (
        "production FVM / independent linear-acoustic MOC + analytical"
    )
    assert plot_metrics["solver_rerun"] is False
    assert plot_metrics["numerical_results_changed"] is False
    assert aggregate["comparison_plots_complete"] is True
    assert aggregate["generated_plots"] == plot_result["plot_files"]
    assert aggregate["plotting_errors"] == {}
