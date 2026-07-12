from __future__ import annotations


import pytest

from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.verification.wave_regression import evaluate_coolprop_wave_regression, run_coolprop_wave_regression


def healthy_metrics() -> dict:
    run = {
        "overall_observation_run_pass": True,
        "completed_without_exception": True,
        "reached_target_time": True,
        "within_max_steps": True,
        "property_backend_design_status": "not_approved_for_design_use",
        "all_history_finite": True,
        "positive_pressure": True,
        "positive_temperature": True,
        "positive_density": True,
        "positive_sound_speed": True,
        "remained_single_phase": True,
        "max_alpha": 0.0,
        "max_vapor_mass_fraction": 0.0,
        "missing_budget_fields": [],
        "budget_mass_relative_residual": 1.0e-15,
        "energy_budget_balance_relative_residual": 1.0e-15,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "runtime_seconds": 123.0,
        "step_count": 250,
    }
    row = {
        "interprobe_threshold_speed_relative_error": 0.99,
        "interprobe_peak_speed_relative_error": 8.0e-6,
        "interprobe_centroid_speed_relative_error": 0.03,
        "interprobe_cross_correlation_speed_relative_error": 0.045,
        "cross_correlation_coefficient": 0.633,
        "primary_probe_amplitude_ratio_L2": 0.455,
        "primary_probe_fwhm_broadening_ratio_L2": 2.19,
        "waveform_l2_difference_vs_finest": 0.0,
    }
    return {"overall_sweep_execution_pass": True, "property_backend_design_status": "not_approved_for_design_use", "runs": [run], "summary_rows": [row]}


def assert_fails_when(mutator, expected_check: str) -> None:
    metrics = healthy_metrics()
    mutator(metrics)
    result = evaluate_coolprop_wave_regression(metrics)
    assert result["overall_regression_pass"] is False
    assert expected_check in result["failed_checks"]


def test_healthy_synthetic_metrics_pass_broad_software_regression_band() -> None:
    result = evaluate_coolprop_wave_regression(healthy_metrics())
    assert result["overall_regression_pass"] is True
    assert result["failed_checks"] == []
    assert result["design_evaluation"] is False
    assert result["acceptance_gate"] is False
    assert result["validation"] is False
    assert result["property_backend_design_status"] == "not_approved_for_design_use"


@pytest.mark.parametrize(
    ("key", "check"),
    [
        ("budget_mass_relative_residual", "mass_relative_residual"),
        ("energy_budget_balance_relative_residual", "energy_balance_relative_residual"),
        ("phase_vapor_mass_balance_relative_residual", "vapor_mass_balance_relative_residual"),
    ],
)
def test_budget_residual_excess_fails(key: str, check: str) -> None:
    assert_fails_when(lambda m: m["runs"][0].__setitem__(key, 2.0e-12), check)


def test_missing_budget_field_fails_without_keyerror() -> None:
    assert_fails_when(lambda m: m["runs"][0].__setitem__("missing_budget_fields", ["budget_mass_residual"]), "missing_budget_fields_empty")


@pytest.mark.parametrize(
    ("key", "check", "value"),
    [
        ("interprobe_peak_speed_relative_error", "interprobe_peak_speed_relative_error", 1.0e-3),
        ("interprobe_centroid_speed_relative_error", "interprobe_centroid_speed_relative_error", 6.0e-2),
        ("interprobe_cross_correlation_speed_relative_error", "interprobe_cross_correlation_speed_relative_error", 9.0e-2),
        ("cross_correlation_coefficient", "cross_correlation_coefficient", 0.49),
        ("primary_probe_amplitude_ratio_L2", "L2_amplitude_ratio_broad_regression_band", 0.2),
        ("primary_probe_fwhm_broadening_ratio_L2", "L2_fwhm_broadening_ratio_broad_regression_band", 3.5),
    ],
)
def test_wave_behavior_regressions_fail(key: str, check: str, value: float) -> None:
    assert_fails_when(lambda m: m["summary_rows"][0].__setitem__(key, value), check)


def test_single_phase_and_vapor_guardrails_fail() -> None:
    assert_fails_when(lambda m: m["runs"][0].__setitem__("remained_single_phase", False), "remained_single_phase")
    assert_fails_when(lambda m: m["runs"][0].__setitem__("max_alpha", 2.0e-12), "max_alpha")
    assert_fails_when(lambda m: m["runs"][0].__setitem__("max_vapor_mass_fraction", 2.0e-12), "max_vapor_mass_fraction")


def test_missing_key_is_explicit_failure_not_exception() -> None:
    metrics = healthy_metrics()
    del metrics["runs"][0]["positive_pressure"]
    result = evaluate_coolprop_wave_regression(metrics)
    assert result["overall_regression_pass"] is False
    assert "positive_pressure" in result["failed_checks"]
    assert result["checks"]["positive_pressure"]["missing"] is True


def test_threshold_speed_and_runtime_are_diagnostic_only() -> None:
    metrics = healthy_metrics()
    metrics["summary_rows"][0]["interprobe_threshold_speed_relative_error"] = 10.0
    metrics["runs"][0]["runtime_seconds"] = 99999.0
    result = evaluate_coolprop_wave_regression(metrics)
    assert result["overall_regression_pass"] is True
    assert result["diagnostic_only"]["threshold_speed_relative_error"] == 10.0
    assert result["diagnostic_only"]["runtime_seconds"] == 99999.0


def test_design_use_guardrail_fails_if_status_changes() -> None:
    assert_fails_when(lambda m: m["runs"][0].__setitem__("property_backend_design_status", "approved_for_design_use"), "property_backend_design_status_not_approved_for_design_use")


@pytest.mark.numerical_regression
@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_installed_coolprop_ci_light_regression_run(tmp_path) -> None:
    result = run_coolprop_wave_regression(tmp_path / "coolprop_wave_ci_light_regression_result.json")
    assert result["overall_regression_pass"] is True
    assert result["failed_checks"] == []
    assert result["design_evaluation"] is False
    assert result["acceptance_gate"] is False
    assert result["validation"] is False
    assert result["property_backend_design_status"] == "not_approved_for_design_use"
    assert (tmp_path / "coolprop_wave_ci_light_regression_result.json").exists()
