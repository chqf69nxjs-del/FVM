from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.verification.boundary_reflection_regression import (
    evaluate_boundary_reflection_regression,
    run_boundary_reflection_regression,
)


def healthy_metrics(boundary: str) -> dict:
    expected = 1.0 if boundary == "rigid_wall" else -1.0
    boundary_metrics = (
        {"max_abs_wall_velocity_m_s": 0.0}
        if boundary == "rigid_wall"
        else {"normalized_fixed_pressure_residual": 0.06}
    )
    return {
        "boundary_kind": boundary,
        "overall_observation_execution_pass": True,
        "execution_complete": True,
        "reached_target_time": True,
        "within_max_steps": True,
        "all_history_finite": True,
        "positive_pressure": True,
        "positive_temperature": True,
        "positive_density": True,
        "positive_sound_speed": True,
        "remained_single_phase": True,
        "reflection_detected": True,
        "expected_sign_observed": True,
        "evaluation_window_contaminated": False,
        "missing_budget_fields": [],
        "property_backend_design_status": "not_approved_for_design_use",
        "budget_mass_relative_residual": 0.0,
        "energy_budget_balance_relative_residual": 4.0e-16,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "pressure_amplitude_pa": 1000.0,
        "Z0": 1.0e6,
        "boundary_metrics": boundary_metrics,
        "probes": [
            {
                "probe_name": "x_over_L_0.9",
                "pressure_reflection_coefficient": expected * 0.8,
                "reflected_arrival_time_relative_error": 1.0e-4 if boundary == "rigid_wall" else 0.02,
                "reflected_A_plus_leakage_peak_pa": 100.0,
                "reflected_A_minus_signed_extremum_pa": expected * 800.0,
            }
        ],
    }


@pytest.mark.parametrize("boundary", ["rigid_wall", "fixed_pressure"])
def test_healthy_metrics_pass(boundary: str) -> None:
    result = evaluate_boundary_reflection_regression(healthy_metrics(boundary))
    assert result["overall_regression_pass"] is True
    assert result["failed_checks"] == []
    assert result["design_evaluation"] is False
    assert result["validation"] is False


def test_wrong_sign_guard_fails() -> None:
    metrics = healthy_metrics("rigid_wall")
    metrics["expected_sign_observed"] = False
    result = evaluate_boundary_reflection_regression(metrics)
    assert result["overall_regression_pass"] is False
    assert "expected_sign_observed" in result["failed_checks"]


def test_missing_field_is_explicit_failure() -> None:
    metrics = healthy_metrics("fixed_pressure")
    del metrics["positive_pressure"]
    result = evaluate_boundary_reflection_regression(metrics)
    assert result["overall_regression_pass"] is False
    assert result["checks"]["positive_pressure"]["missing"] is True


@pytest.mark.parametrize(
    ("key", "check"),
    [
        ("budget_mass_relative_residual", "mass_relative_residual"),
        ("energy_budget_balance_relative_residual", "energy_balance_relative_residual"),
        ("phase_vapor_mass_balance_relative_residual", "vapor_mass_balance_relative_residual"),
    ],
)
def test_budget_excess_fails(key: str, check: str) -> None:
    metrics = healthy_metrics("rigid_wall")
    metrics[key] = 2.0e-12
    result = evaluate_boundary_reflection_regression(metrics)
    assert check in result["failed_checks"]


def test_regression_band_failure_is_detected() -> None:
    metrics = healthy_metrics("fixed_pressure")
    metrics["probes"][0]["pressure_reflection_coefficient"] = -0.5
    result = evaluate_boundary_reflection_regression(metrics)
    assert "reflection_magnitude_error" in result["failed_checks"]


def test_design_status_guard_fails() -> None:
    metrics = healthy_metrics("rigid_wall")
    metrics["property_backend_design_status"] = "approved_for_design_use"
    result = evaluate_boundary_reflection_regression(metrics)
    assert "property_backend_design_status_not_approved_for_design_use" in result["failed_checks"]


@pytest.mark.numerical_regression
@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_installed_coolprop_boundary_reflection_regression(tmp_path: Path) -> None:
    result = run_boundary_reflection_regression(tmp_path / "boundary_reflection_ci_light.json")
    assert result["overall_regression_pass"] is True
    assert result["failed_cases"] == []
    assert set(result["case_results"]) == {"rigid_wall", "fixed_pressure"}
    assert (tmp_path / "boundary_reflection_ci_light.json").is_file()
