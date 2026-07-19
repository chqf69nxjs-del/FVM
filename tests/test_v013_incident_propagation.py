from __future__ import annotations

from importlib.metadata import version as distribution_version
import csv
import json
import math

import numpy as np
import pytest

from liquid_gas_transient.cases.v013_incident_propagation import (
    V013IncidentPropagationConfig,
    build_run_plan,
    case_id_for,
    leading_fraction_crossings,
    normalized_error_norms,
    run_v013_incident_propagation,
    sample_spacetime_history,
)


def test_v013a_default_configuration_and_run_plan_are_stable() -> None:
    cfg = V013IncidentPropagationConfig()
    assert cfg.fvm_mesh_cells == (100, 200, 400)
    assert cfg.pressure_amplitude_pa == 100.0
    assert cfg.validation is False
    assert cfg.design_evaluation is False
    assert cfg.acceptance_gate is False
    plan = build_run_plan(cfg)
    assert [row["case_id"] for row in plan] == [
        "v013a_n0100_fvmcfl0p5_moccfl1",
        "v013a_n0200_fvmcfl0p5_moccfl1",
        "v013a_n0400_fvmcfl0p5_moccfl1",
    ]
    assert all(row["verification_item"] == "V-013A" for row in plan)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pressure_amplitude_pa": 1000.0},
        {"fvm_mesh_cells": (200, 100)},
        {"fvm_mesh_cells": (10,)},
        {"fvm_cfl": 0.0},
        {"moc_cfl": 0.5},
        {"probe_fractions": (0.1,)},
        {"matched_center_travel_m": (0.0, 63.3)},
        {"validation": True},
    ],
)
def test_v013a_configuration_rejects_invalid_or_out_of_scope_values(kwargs) -> None:
    with pytest.raises(ValueError):
        V013IncidentPropagationConfig(**kwargs)


def test_case_id_rejects_nonpositive_cell_count() -> None:
    with pytest.raises(ValueError):
        case_id_for(0)


def test_normalized_error_norms_are_zero_for_identity_and_one_for_double() -> None:
    x = np.linspace(0.0, 1.0, 101)
    reference = np.sin(np.pi * x)
    same = normalized_error_norms(x, reference, reference)
    assert same["l1_relative"] == 0.0
    assert same["l2_relative"] == 0.0
    assert same["linf_relative"] == 0.0
    doubled = normalized_error_norms(x, 2.0 * reference, reference)
    assert math.isclose(doubled["l1_relative"], 1.0, rel_tol=1.0e-12)
    assert math.isclose(doubled["l2_relative"], 1.0, rel_tol=1.0e-12)
    assert math.isclose(doubled["linf_relative"], 1.0, rel_tol=1.0e-12)


def test_zero_reference_can_use_independent_normalization_scale() -> None:
    x = np.linspace(0.0, 1.0, 11)
    candidate = np.ones_like(x)
    zero = np.zeros_like(x)
    result = normalized_error_norms(
        x,
        candidate,
        zero,
        normalization_reference=2.0 * np.ones_like(x),
    )
    assert math.isclose(result["l1_relative"], 0.5)
    assert math.isclose(result["l2_relative"], 0.5)
    assert math.isclose(result["linf_relative"], 0.5)


def test_leading_fraction_crossings_use_rising_side_linear_interpolation() -> None:
    t = np.asarray([0.0, 1.0, 2.0, 3.0, 4.0])
    y = np.asarray([2.0, 4.0, 10.0, 6.0, 2.0])
    result = leading_fraction_crossings(t, y, (0.1, 0.5, 0.9))
    assert result["detected"] is True
    assert math.isclose(result["crossing_times_s"]["p10"], 0.4)
    assert math.isclose(result["crossing_times_s"]["p50"], 1.0 + 2.0 / 6.0)
    assert math.isclose(result["crossing_times_s"]["p90"], 1.0 + 5.2 / 6.0)


def test_spacetime_interpolation_is_exact_for_a_bilinear_plane() -> None:
    times = np.asarray([0.0, 1.0, 2.0])
    x = np.asarray([0.0, 2.0, 4.0])
    values = times[:, None] + 2.0 * x[None, :]
    query_t = np.asarray([0.5, 1.5])
    query_x = np.asarray([1.0, 3.0])
    sampled = sample_spacetime_history(times, x, values, query_t, query_x)
    assert np.allclose(sampled, query_t + 2.0 * query_x)


def test_spacetime_interpolation_rejects_out_of_domain_query() -> None:
    with pytest.raises(ValueError):
        sample_spacetime_history(
            [0.0, 1.0],
            [0.0, 1.0],
            [[0.0, 1.0], [1.0, 2.0]],
            [1.5],
            [0.5],
        )


@pytest.mark.numerical_regression
@pytest.mark.coolprop_installed
def test_v013a_installed_cross_verification_run_and_artifacts(tmp_path) -> None:
    pytest.importorskip("CoolProp")
    pytest.importorskip("matplotlib")
    coolprop_version = distribution_version("CoolProp")
    cfg = V013IncidentPropagationConfig(
        fvm_mesh_cells=(40,),
        generate_plots=True,
    )
    metrics = run_v013_incident_propagation(tmp_path, cfg)

    assert metrics["planned_run_count"] == 1
    assert metrics["executed_run_count"] == 1
    assert metrics["overall_execution_pass"] is True
    assert metrics["aggregate_analysis_complete"] is True
    assert metrics["comparison_plots_complete"] is True
    assert metrics["formal_fvm_regression_band_applied"] is False
    assert metrics["validation"] is False
    assert metrics["design_evaluation"] is False
    assert metrics["acceptance_gate"] is False
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["coolprop_version"] == coolprop_version
    assert len(metrics["generated_plots"]) == 7

    case_id = metrics["run_plan"][0]["case_id"]
    run_dir = tmp_path / case_id
    required = [
        tmp_path / "v013a_config.json",
        tmp_path / "v013a_reference_constants.json",
        tmp_path / "v013a_run_plan.json",
        tmp_path / "v013a_summary.csv",
        tmp_path / "v013a_metrics.json",
        tmp_path / "v013a_observation_report.md",
        tmp_path / "v013a_plot_metrics.json",
        run_dir / "fvm_config.json",
        run_dir / "fvm_metrics.json",
        run_dir / "fvm_probe_history.csv",
        run_dir / "fvm_field_history.npz",
        run_dir / "moc_config.json",
        run_dir / "moc_metrics.json",
        run_dir / "moc_history.npz",
        run_dir / "analytical_samples.csv",
        run_dir / "matched_samples.csv",
        run_dir / "probe_comparison.csv",
        run_dir / "comparison_metrics.json",
    ]
    assert all(path.exists() and path.stat().st_size > 0 for path in required)
    assert all((tmp_path / name).exists() for name in metrics["generated_plots"])

    aggregate = json.loads(
        (tmp_path / "v013a_metrics.json").read_text(encoding="utf-8")
    )
    reference = json.loads(
        (tmp_path / "v013a_reference_constants.json").read_text(encoding="utf-8")
    )
    assert aggregate["coolprop_version"] == coolprop_version
    assert reference["coolprop_version"] == coolprop_version
    assert reference["moc_calls_coolprop"] is False
    assert reference["property_backend_design_status"] == "not_approved_for_design_use"

    fvm_metrics = json.loads((run_dir / "fvm_metrics.json").read_text(encoding="utf-8"))
    moc_metrics = json.loads((run_dir / "moc_metrics.json").read_text(encoding="utf-8"))
    comparison = json.loads(
        (run_dir / "comparison_metrics.json").read_text(encoding="utf-8")
    )
    assert fvm_metrics["coolprop_version"] == coolprop_version
    assert fvm_metrics["overall_fvm_health_pass"] is True
    assert fvm_metrics["solver_physics_changed"] is False
    assert moc_metrics["overall_moc_reference_pass"] is True
    assert moc_metrics["calls_coolprop"] is False
    assert comparison["formal_fvm_regression_band_applied"] is False
    assert comparison["fitted_speed_metrics"]["analytical"]["p50"]["relative_error"] < 5.0e-3

    with (tmp_path / "v013a_summary.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["execution_pass"] == "True"
