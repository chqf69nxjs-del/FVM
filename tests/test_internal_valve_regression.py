from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.verification.internal_valve_regression import (
    evaluate_internal_valve_regression,
    run_internal_valve_regression,
)


def _base(item: str) -> dict:
    return {
        "verification_item": item,
        "n_cells": 50,
        "cfl": 0.5,
        "execution_pass": True,
        "analysis_complete": True,
        "summary_extraction_complete": True,
        "all_history_finite": True,
        "positive_pressure": True,
        "positive_temperature": True,
        "positive_density": True,
        "positive_sound_speed": True,
        "remained_single_phase": True,
        "missing_budget_fields": "",
        "property_backend_name": "coolprop_co2",
        "coolprop_version": "8.0.0",
        "property_backend_design_status": "not_approved_for_design_use",
        "mach_cap_activation_count": 0,
        "budget_mass_relative_residual": 0.0,
        "energy_budget_balance_relative_residual": 2.0e-16,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "max_abs_opening_error": 0.0,
        "max_abs_mass_flux_mismatch_kg_m2_s": 0.0,
        "max_abs_energy_flux_mismatch_w_m2": 0.0,
        "max_abs_vapor_mass_flux_mismatch_kg_m2_s": 0.0,
        "max_abs_flux_q_minus_applied_q_m3_s": 1.0e-20,
    }


def healthy_rows() -> list[dict]:
    a = {
        **_base("V-012A"),
        "max_abs_raw_target_q_m3_s_extracted": 0.0,
        "max_abs_applied_q_m3_s_extracted": 0.0,
        "max_abs_flux_derived_q_m3_s_extracted": 0.0,
        "max_abs_pressure_disturbance_pa": 0.0,
        "max_abs_velocity_m_s": 0.0,
        "hydraulic_separation_fraction_extracted": 1.0,
        "no_flow_direction_fraction_extracted": 1.0,
    }
    b = {
        **_base("V-012B"),
        "max_raw_applied_relative_difference_extracted": 0.0,
        "max_applied_flux_relative_difference_extracted": 2.0e-16,
        "near_probe_characteristic_direction_pass": True,
        "near_probe_characteristic_max_leakage_ratio": 1.6e-6,
        "flow_sign_consistency_fraction": 1.0,
        "initial_applied_q_m3_s_extracted": 3.53e-5,
        "final_applied_q_m3_s_extracted": 2.74e-5,
        "near_probe_characteristic_p50_time_offset_max_abs_s": 4.57e-3,
        "near_probe_characteristic_peak_abs_mean_pa": 108.0,
        "hydraulic_separation_fraction_extracted": 0.0,
    }
    c = {
        **_base("V-012C"),
        "max_raw_applied_relative_difference_extracted": 0.0,
        "max_applied_flux_relative_difference_extracted": 2.0e-16,
        "near_probe_characteristic_direction_pass": True,
        "near_probe_characteristic_max_leakage_ratio": 1.9e-6,
        "flow_sign_consistency_fraction": 1.0,
        "initial_applied_q_m3_s_extracted": 0.0,
        "max_applied_q_m3_s_extracted": 4.31e-5,
        "final_applied_q_m3_s_extracted": 4.31e-5,
        "near_probe_characteristic_p50_time_offset_max_abs_s": 1.91e-3,
        "near_probe_characteristic_peak_abs_mean_pa": 276.0,
        "opening_monotonic_non_decreasing": True,
        "upstream_decompression_observed": True,
        "downstream_compression_observed": True,
    }
    d = {
        **_base("V-012D"),
        "max_raw_applied_relative_difference_extracted": 0.0,
        "max_applied_flux_relative_difference_extracted": 2.0e-16,
        "near_probe_characteristic_direction_pass": True,
        "near_probe_characteristic_max_leakage_ratio": 1.1e-6,
        "flow_sign_consistency_fraction": 1.0,
        "initial_applied_q_m3_s_extracted": 7.07e-5,
        "final_applied_q_m3_s_extracted": 0.0,
        "near_probe_characteristic_p50_time_offset_max_abs_s": 4.88e-3,
        "near_probe_characteristic_peak_abs_mean_pa": 194.0,
        "opening_monotonic_non_increasing": True,
        "upstream_compression_observed": True,
        "downstream_decompression_observed": True,
        "post_closure_hydraulic_separation_fraction_extracted": 1.0,
        "post_closure_no_flow_direction_fraction_extracted": 1.0,
        "max_abs_post_closure_raw_target_q_m3_s_extracted": 0.0,
        "max_abs_post_closure_applied_q_m3_s_extracted": 0.0,
        "max_abs_post_closure_flux_derived_q_m3_s_extracted": 3.0e-25,
        "max_abs_post_closure_mass_flux_kg_m2_s_extracted": 4.0e-21,
        "max_abs_post_closure_energy_flux_w_m2_extracted": 0.0,
        "max_abs_post_closure_vapor_mass_flux_kg_m2_s_extracted": 0.0,
        "max_abs_finite_opening_momentum_residual_pa_extracted": 0.0,
        "finite_opening_momentum_relation_applied_to_closed_rows_extracted": False,
    }
    return [a, b, c, d]


def test_healthy_internal_valve_regression_payload_passes() -> None:
    result = evaluate_internal_valve_regression(healthy_rows())
    assert result["overall_regression_pass"] is True
    assert result["failed_checks"] == []
    assert result["validation"] is False
    assert result["design_evaluation"] is False
    assert result["acceptance_gate"] is False


def test_missing_case_is_explicit_failure() -> None:
    result = evaluate_internal_valve_regression(healthy_rows()[:-1])
    assert result["overall_regression_pass"] is False
    assert "row_count" in result["failed_checks"]
    assert "expected_items_present_once" in result["failed_checks"]
    assert result["checks"]["v012d.row_present"]["missing"] is True


def test_wrong_backend_status_fails() -> None:
    rows = healthy_rows()
    rows[1]["property_backend_design_status"] = "approved_for_design_use"
    result = evaluate_internal_valve_regression(rows)
    assert "v012b.property_backend_design_status" in result["failed_checks"]


def test_dynamic_timing_band_failure_is_detected() -> None:
    rows = healthy_rows()
    rows[2]["near_probe_characteristic_p50_time_offset_max_abs_s"] = 0.02
    result = evaluate_internal_valve_regression(rows)
    assert "v012c.p50_timing_offset" in result["failed_checks"]


def test_complete_closure_leakage_failure_is_detected() -> None:
    rows = healthy_rows()
    rows[3]["max_abs_post_closure_mass_flux_kg_m2_s_extracted"] = 1.0e-6
    rows[3]["finite_opening_momentum_relation_applied_to_closed_rows_extracted"] = True
    result = evaluate_internal_valve_regression(rows)
    assert "v012d.post_closure_mass_flux" in result["failed_checks"]
    assert (
        "v012d.finite_opening_relation_not_applied_to_closed_rows"
        in result["failed_checks"]
    )


def test_zero_reference_checks_use_absolute_limits() -> None:
    rows = healthy_rows()
    rows[0]["max_abs_applied_q_m3_s_extracted"] = 2.0e-15
    rows[3]["max_abs_post_closure_flux_derived_q_m3_s_extracted"] = 2.0e-15
    result = evaluate_internal_valve_regression(rows)
    assert "v012a.max_applied_q" in result["failed_checks"]
    assert "v012d.post_closure_flux_derived_q" in result["failed_checks"]


def test_input_rows_are_not_mutated() -> None:
    rows = healthy_rows()
    expected = deepcopy(rows)
    evaluate_internal_valve_regression(rows)
    assert rows == expected


@pytest.mark.numerical_regression
@pytest.mark.coolprop_installed
@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_installed_coolprop_internal_valve_regression(tmp_path: Path) -> None:
    output = tmp_path / "internal_valve_ci_light.json"
    artifact_dir = tmp_path / "cases"
    result = run_internal_valve_regression(output, artifact_dir=artifact_dir)
    assert result["overall_regression_pass"] is True
    assert result["case_result"]["failed_checks"] == []
    assert result["executed_run_count"] == 4
    assert result["sweep_execution_pass"] is True
    assert result["ci_profile"] == {
        "n_cells": 50,
        "cfl": 0.5,
        "verification_items": ["V-012A", "V-012B", "V-012C", "V-012D"],
    }
    assert output.is_file()
