from __future__ import annotations

import json
from pathlib import Path

import pytest

from liquid_gas_transient.hem_equilibrium_quality_sync import (
    HEMEquilibriumQualitySyncConfig,
)
from liquid_gas_transient.hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from liquid_gas_transient.hem_phase_classification import (
    HEMPhaseClassificationConfig,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "verification"
CONTRACT_PATH = (
    DOCS
    / "stage7_lco2_hem_pipeline_depressurization_prototype_contract_v1.json"
)
SPEC_PATH = DOCS / "stage7_lco2_hem_pipeline_depressurization_prototype_spec.md"
BOUNDARY_PATH = (
    DOCS / "stage7_lco2_hem_pipeline_depressurization_boundary_contract.md"
)
VALIDATION_PATH = (
    DOCS / "stage7_lco2_hem_pipeline_depressurization_validation_plan.md"
)


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_schema_scope_and_approval_boundary_are_explicit() -> None:
    data = _contract()
    assert data["schema_version"] == (
        "stage7_lco2_hem_pipeline_depressurization_prototype_v1"
    )
    assert data["status"] == "SPECIFICATION_ONLY"
    assert data["scope"] == "verification_only"
    assert data["recorded_base_main"] == (
        "3e55b3fae88d813437654c144d0157de5b6d398f"
    )

    claims = data["claims"]
    assert claims["first_crossing_prototype_specified"] is True
    for key in (
        "boundary_adapter_implemented",
        "pipeline_depressurization_executed",
        "interface_propagation_speed_verified",
        "physical_validation",
        "design_use_acceptance",
        "production_hem_activation_approved",
        "two_phase_acoustic_accuracy_band_approved",
    ):
        assert claims[key] is False

    approval = data["approval_boundary"]
    assert approval["verification_only"] is True
    assert approval["software_verification_only"] is True
    assert approval["production_default_changed"] is False
    assert approval["production_hem_activation_approved"] is False
    assert approval["physical_validation"] is False
    assert approval["design_use_acceptance"] is False
    assert approval["two_phase_acoustic_accuracy_band_approved"] is False


def test_geometry_numerics_and_uniform_initial_state_are_fixed() -> None:
    data = _contract()
    geometry = data["geometry"]
    assert geometry["pipe_type"] == "single_horizontal_straight_pipe"
    assert geometry["length_m"] == pytest.approx(1.0)
    assert geometry["diameter_m"] == pytest.approx(0.1)
    assert geometry["n_cells"] == 32
    assert geometry["dx_m"] == pytest.approx(
        geometry["length_m"] / geometry["n_cells"]
    )
    assert geometry["gravity_enabled"] is False
    assert geometry["friction_enabled"] is False
    assert geometry["wall_heat_transfer_enabled"] is False
    assert geometry["internal_interfaces_enabled"] is False

    numerics = data["numerics"]
    assert numerics["spatial_order"] == 1
    assert numerics["numerical_flux"] == "existing_rusanov"
    assert numerics["cfl_limit"] == pytest.approx(0.1)
    assert numerics["n_ghost"] == 2
    assert numerics["physical_source"] == "none"
    assert numerics["core_solver_changes_allowed"] is False
    assert numerics["algorithms_or_tolerances_tuned"] is False

    initial = data["initial_state"]
    assert initial["pressure_pa"] == pytest.approx(5.0e6)
    assert initial["subcooling_K"] == pytest.approx(5.0)
    assert initial["velocity_m_s"] == pytest.approx(0.0)
    assert initial["transported_quality"] == pytest.approx(0.0)
    assert initial["required_boundary_region"] == "LIQUID_CANDIDATE"
    assert initial["all_cells_identical"] is True


def test_boundary_closure_prevents_pressure_only_and_quality_copy_paths() -> None:
    data = _contract()
    left = data["boundaries"]["left"]
    right = data["boundaries"]["right"]

    assert left["type"] == "existing_ReflectiveBoundary"
    assert right["planned_type"] == (
        "VerificationHEMPrescribedSubcooledOutletBoundary"
    )
    assert right["side"] == "right"
    assert right["flow_direction"] == "outlet_only"
    assert right["velocity_policy"] == "copy_adjacent_interior_velocity"
    assert right["thermodynamic_closure"] == (
        "prescribed_pressure_plus_constant_subcooling"
    )
    assert right["boundary_subcooling_K"] == pytest.approx(5.0)
    assert right["quality_policy"] == (
        "use_equilibrium_quality_of_prescribed_rho_e_state"
    )
    assert right["required_boundary_region"] == "LIQUID_CANDIDATE"
    assert right["copy_interior_quality_forbidden"] is True
    assert right["pressure_only_inversion_forbidden"] is True
    assert right["initial_state_matches_pipe"] is True
    assert right["initial_hold_s"] == pytest.approx(0.0)


def test_fixed_case_matrix_changes_only_final_pressure() -> None:
    data = _contract()
    cases = data["fixed_case_matrix"]
    assert [case["boundary_final_pressure_pa"] for case in cases] == [
        2.0e6,
        3.0e6,
        4.0e6,
    ]
    assert [case["role"] for case in cases] == [
        "first_crossing_candidate",
        "moderate_diagnostic",
        "liquid_negative_control",
    ]
    assert all(case["boundary_subcooling_K"] == 5.0 for case in cases)
    assert all(
        case["ramp_duration_acoustic_time_ratio"] == 1.0 for case in cases
    )

    scales = data["time_scales"]
    assert scales["initial_acoustic_time_definition"] == "t_acoustic=L/c_initial"
    assert scales["ramp_duration_acoustic_time_ratio"] == pytest.approx(1.0)
    assert scales["post_ramp_observation_acoustic_time_ratio"] == pytest.approx(2.0)
    assert scales["maximum_horizon_acoustic_time_ratio"] == pytest.approx(3.0)
    assert scales["maximum_steps"] == 2000


def test_preflight_and_tolerances_match_existing_reviewed_configs() -> None:
    data = _contract()
    preflight = data["boundary_path_preflight"]
    assert preflight["required"] is True
    assert preflight["sample_count"] == 65
    assert preflight["include_schedule_endpoints"] is True
    assert preflight["required_region_at_every_sample"] == "LIQUID_CANDIDATE"
    assert preflight["required_quality_at_every_sample"] == pytest.approx(0.0)
    assert preflight["require_nonnegative_internal_energy"] is True
    assert preflight["require_mixed_accepted_state_eos_acceptance"] is True

    fixed = data["phase_and_projection_tolerances"]
    phase_config = HEMPhaseClassificationConfig()
    projection_config = HEMEquilibriumQualitySyncConfig()
    accepted_eos = VerificationHEMLiquidOpenTwoPhaseEOS()

    assert fixed["endpoint_tolerance"] == pytest.approx(
        phase_config.endpoint_tolerance
    )
    assert fixed["projection_activation_tolerance"] == pytest.approx(
        projection_config.activation_tolerance
    )
    assert fixed["accepted_state_quality_tolerance"] == pytest.approx(
        accepted_eos.quality_tolerance
    )
    assert fixed["crossing_evidence_min_quality"] == pytest.approx(1.0e-6)
    assert fixed["crossing_evidence_min_quality_is_solver_switch"] is False


def test_events_stop_priority_and_crossing_contract_are_unambiguous() -> None:
    data = _contract()
    assert data["event_outcomes"] == [
        "ACCEPTED_FIRST_CROSSING",
        "NO_CROSSING_WITHIN_HORIZON",
        "ENDPOINT_LANDING",
        "FORBIDDEN_TRANSITION",
        "REVERSE_FLOW_GUARD",
        "GUARD_FAILURE",
        "BACKEND_FAILURE",
    ]
    assert data["stop_priority"] == [
        "BACKEND_FAILURE",
        "GUARD_FAILURE",
        "REVERSE_FLOW_GUARD",
        "FORBIDDEN_TRANSITION",
        "ENDPOINT_LANDING",
        "ACCEPTED_FIRST_CROSSING",
        "NO_CROSSING_WITHIN_HORIZON",
    ]

    acceptance = data["accepted_first_crossing_contract"]
    assert acceptance["reverse_flow_fallback_count"] == 0
    assert acceptance["minimum_crossing_cell_count"] == 1
    assert acceptance["endpoint_count"] == 0
    assert acceptance["forbidden_transition_count"] == 0
    assert acceptance["crossing_cells_equal_projection_cells"] is True
    assert acceptance["maximum_post_quality_mismatch"] == pytest.approx(1.0e-12)
    assert acceptance["minimum_crossing_equilibrium_quality"] == pytest.approx(
        1.0e-6
    )
    assert acceptance["second_projection_cell_count"] == 0
    assert acceptance["boundary_adjacent_crossing_allowed_for_this_first_gate"] is True
    assert acceptance["interface_speed_claim_allowed"] is False


def test_budget_and_artifact_contracts_are_complete() -> None:
    data = _contract()
    budget = data["budget_contract"]
    assert budget["mass_boundary_relative_tolerance"] == pytest.approx(1.0e-10)
    assert budget["energy_boundary_absolute_tolerance_J"] == pytest.approx(1.0e-6)
    assert budget["phase_vapor_absolute_tolerance_kg"] == pytest.approx(1.0e-12)
    assert budget[
        "combined_boundary_plus_phase_vapor_absolute_tolerance_kg"
    ] == pytest.approx(1.0e-12)
    assert budget["left_reflective_mass_flux_must_be_zero"] is True
    assert budget["left_reflective_energy_flux_must_be_zero"] is True
    assert budget["boundary_and_phase_vapor_terms_must_be_separate"] is True

    formats = set(data["artifacts"]["formats"])
    assert {
        "json",
        "case_csv",
        "step_csv",
        "cell_csv",
        "boundary_path_csv",
        "markdown",
        "npz",
    } <= formats
    fields = set(data["artifacts"]["required_fields"])
    assert {
        "resolved_initial_acoustic_time_s",
        "boundary_pressure_temperature_rho_e_quality_by_step",
        "reverse_flow_fallback_count",
        "pressure_wave_first_threshold_time_by_cell",
        "crossing_step_time_cells",
        "boundary_budget",
        "phase_vapor_budget",
        "combined_vapor_budget",
        "failure_reason",
    } <= fields


def test_frozen_regression_hashes_and_two_increment_plan_are_retained() -> None:
    data = _contract()
    regression = data["frozen_regression_controls"]
    assert regression["case_a_final_state_sha256"] == (
        "78897b5c8ca57221186ccf3e0aa69e1492a942cc2e8dee0abb440a3e2e08e039"
    )
    assert regression["case_a_signature_sha256"] == (
        "914ed2249c9546a1d32f6d6dbcd8b30236e1c1f2b37ecf9306100ad30622b612"
    )
    assert regression["case_b_final_state_sha256"] == (
        "8c09735ee9185cfb34b2186be30b32d78ec73350e211762d92c372e0b9f23a59"
    )
    assert regression["case_b_signature_sha256"] == (
        "3bd7edc37842a00a0c27964a17029f5c66ef973b59bd7670f513c82fc7e85669"
    )
    assert regression["must_pass_before_and_after_prototype_changes"] is True

    increments = data["implementation_increments"]
    assert [item["increment"] for item in increments] == [1, 2]
    assert increments[0]["name"] == "boundary_adapter_and_path_preflight"
    assert increments[0]["fvm_time_step_exercised"] is False
    assert increments[1]["name"] == "short_pipeline_first_crossing_runner"
    assert increments[1]["fvm_time_step_exercised"] is True


def test_markdown_documents_reference_the_authoritative_contract() -> None:
    contract_name = CONTRACT_PATH.name
    for path in (SPEC_PATH, BOUNDARY_PATH, VALIDATION_PATH):
        text = path.read_text(encoding="utf-8")
        assert contract_name in text
        assert "verification" in text.lower()
        assert "physical_validation" in text.lower() or "physical Validation" in text

    spec = SPEC_PATH.read_text(encoding="utf-8")
    assert "pressure plus positive subcooling" in spec
    assert "Copying the interior transported quality" in spec
    assert "NO_CROSSING_WITHIN_HORIZON" in spec
    assert "interface-propagation speed" in spec
