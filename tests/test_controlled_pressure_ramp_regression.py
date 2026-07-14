from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.verification.controlled_pressure_ramp_regression import (
    evaluate_controlled_pressure_ramp_regression,
    run_controlled_pressure_ramp_regression,
)


def healthy_metrics() -> dict:
    return {
        "overall_observation_execution_pass": True,
        "reached_target_time": True,
        "within_max_steps": True,
        "all_history_finite": True,
        "positive_pressure": True,
        "positive_temperature": True,
        "positive_density": True,
        "positive_sound_speed": True,
        "remained_single_phase": True,
        "missing_budget_fields": [],
        "property_backend_design_status": "not_approved_for_design_use",
        "max_abs_schedule_pressure_error_pa": 1.0e-9,
        "schedule_pressure_tolerance_pa": 8.0e-9,
        "budget_mass_relative_residual": 0.0,
        "energy_budget_balance_relative_residual": 2.0e-16,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "runtime_s": 10.0,
        "step_count": 100,
        "n_cells": 50,
        "cfl_target": 0.5,
    }


def healthy_observations() -> list[dict]:
    rows = []
    for name, p10, p50, p90 in (
        ("x_over_L_0.25", 0.08, 0.05, 0.23),
        ("x_over_L_0.5", 0.08, 0.05, 0.23),
        ("x_over_L_0.75", 0.08, 0.05, 0.23),
    ):
        rows.append(
            {
                "probe_name": name,
                "observed_propagation_direction": "left_going",
                "peak_amplitude_ratio": 0.9999998,
                "opposite_direction_leakage_ratio": 5.2e-6,
                "linear_velocity_relative_error": 1.0e-5,
                "p10_arrival_relative_error": p10,
                "p50_arrival_relative_error": p50,
                "p90_arrival_relative_error": p90,
            }
        )
    return rows


def healthy_fit() -> dict:
    return {
        "wave_speed_relative_error": 1.3e-3,
        "common_boundary_launch_delay_s": 4.2e-3,
        "fit_residual_rms_s": 1.0e-5,
        "fit_r_squared": 0.9999999,
    }


def test_healthy_regression_payload_passes() -> None:
    result = evaluate_controlled_pressure_ramp_regression(
        healthy_metrics(),
        healthy_observations(),
        healthy_fit(),
    )
    assert result["overall_regression_pass"] is True
    assert result["failed_checks"] == []
    assert result["validation"] is False
    assert result["design_evaluation"] is False


def test_missing_health_field_is_explicit_failure() -> None:
    metrics = healthy_metrics()
    del metrics["positive_pressure"]
    result = evaluate_controlled_pressure_ramp_regression(
        metrics,
        healthy_observations(),
        healthy_fit(),
    )
    assert result["overall_regression_pass"] is False
    assert result["checks"]["positive_pressure"]["missing"] is True


def test_wrong_direction_fails() -> None:
    observations = healthy_observations()
    observations[-1]["observed_propagation_direction"] = "not_left_going_dominant"
    result = evaluate_controlled_pressure_ramp_regression(
        healthy_metrics(),
        observations,
        healthy_fit(),
    )
    assert "left_going_characteristic_dominant" in result["failed_checks"]


def test_timing_band_failure_is_detected() -> None:
    observations = healthy_observations()
    for item in observations:
        item["p50_arrival_relative_error"] = 0.20
    result = evaluate_controlled_pressure_ramp_regression(
        healthy_metrics(),
        observations,
        healthy_fit(),
    )
    assert "mean_p50_arrival_relative_error" in result["failed_checks"]
    assert "max_p50_arrival_relative_error" in result["failed_checks"]


@pytest.mark.parametrize(
    ("key", "check"),
    [
        ("budget_mass_relative_residual", "mass_relative_residual"),
        ("energy_budget_balance_relative_residual", "energy_balance_relative_residual"),
        (
            "phase_vapor_mass_balance_relative_residual",
            "vapor_mass_balance_relative_residual",
        ),
    ],
)
def test_budget_excess_fails(key: str, check: str) -> None:
    metrics = healthy_metrics()
    metrics[key] = 2.0e-12
    result = evaluate_controlled_pressure_ramp_regression(
        metrics,
        healthy_observations(),
        healthy_fit(),
    )
    assert check in result["failed_checks"]


def test_design_status_guard_fails() -> None:
    metrics = healthy_metrics()
    metrics["property_backend_design_status"] = "approved_for_design_use"
    result = evaluate_controlled_pressure_ramp_regression(
        metrics,
        healthy_observations(),
        healthy_fit(),
    )
    assert (
        "property_backend_design_status_not_approved_for_design_use"
        in result["failed_checks"]
    )


def test_input_payloads_are_not_mutated() -> None:
    metrics = healthy_metrics()
    observations = healthy_observations()
    fit = healthy_fit()
    expected = deepcopy((metrics, observations, fit))
    evaluate_controlled_pressure_ramp_regression(metrics, observations, fit)
    assert (metrics, observations, fit) == expected


@pytest.mark.numerical_regression
@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_installed_coolprop_controlled_pressure_ramp_regression(
    tmp_path: Path,
) -> None:
    output = tmp_path / "controlled_pressure_ramp_ci_light.json"
    result = run_controlled_pressure_ramp_regression(output)
    assert result["overall_regression_pass"] is True
    assert result["case_result"]["failed_checks"] == []
    assert result["ci_profile"] == {"n_cells": 50, "cfl": 0.5}
    assert output.is_file()
