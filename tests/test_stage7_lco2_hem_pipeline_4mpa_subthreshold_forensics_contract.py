from __future__ import annotations

import json
from pathlib import Path

import pytest

from liquid_gas_transient.hem_pipeline_4mpa_subthreshold_forensics import (
    EXPECTED_BASELINE,
    PERTURBATION_LEVELS,
    SELECTED_CELLS,
    SELECTED_STEPS,
    run_fixed_4mpa_forensic_diagnostic,
)


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs/verification/"
    "stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_contract_v1.json"
)


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_forensic_contract_fixes_scope_baseline_and_approval_boundary() -> None:
    contract = _contract()
    assert contract["schema_version"] == (
        "stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_v1"
    )
    assert contract["scope"] == "verification_only"
    assert contract["status"] == (
        "FIXED_PR77_BASELINE_REPRODUCED_SOFTWARE_DIAGNOSTIC_COMPLETE"
    )

    baseline = contract["immutable_baseline"]
    assert baseline["formal_outcome"] == EXPECTED_BASELINE["outcome"]
    assert baseline["crossing_step"] == EXPECTED_BASELINE["crossing_step"]
    assert baseline["crossing_time_s"] == EXPECTED_BASELINE["crossing_time_s"]
    assert tuple(baseline["crossing_cell_indices"]) == EXPECTED_BASELINE[
        "crossing_cell_indices"
    ]
    assert tuple(baseline["crossing_distances_from_outlet_m"]) == EXPECTED_BASELINE[
        "crossing_distances_from_outlet_m"
    ]
    assert baseline["maximum_crossing_quality"] == EXPECTED_BASELINE[
        "maximum_crossing_quality"
    ]
    assert baseline["final_state_sha256"] == EXPECTED_BASELINE[
        "final_state_sha256"
    ]
    assert baseline["run_signature_sha256"] == EXPECTED_BASELINE[
        "run_signature_sha256"
    ]
    assert baseline["reproduced_exactly"] is True
    assert baseline["reclassified"] is False

    window = contract["fixed_diagnostic_window"]
    assert tuple(window["steps"]) == SELECTED_STEPS
    assert tuple(window["cells"]) == SELECTED_CELLS
    assert window["local_state_record_count"] == 210
    assert window["saturation_margin_record_count"] == 70
    assert window["flux_decomposition_record_count"] == 70
    assert window["perturbation_record_count"] == len(PERTURBATION_LEVELS) ** 2

    conclusion = contract["diagnostic_conclusion"]
    assert conclusion["categories"] == [
        "THERMODYNAMIC_TWO_PHASE_SUPPORTED",
        "NEAR_SATURATION_PROPERTY_SENSITIVE",
        "MULTI_FACTOR_EVIDENCE",
    ]
    assert conclusion["not_triggered_by_reviewed_criteria"] == [
        "NUMERICAL_DIFFUSION_CONSISTENT",
        "BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT",
    ]
    assert conclusion["diagnostic_execution_passed"] is True
    assert conclusion["gate_p2_passed"] is False

    approval = contract["approval_boundary"]
    assert approval["verification_only"] is True
    assert approval["software_diagnostic_only"] is True
    assert approval["PR77_observation_reclassified"] is False
    assert approval["Gate_P2_passed"] is False
    assert approval["physical_validation"] is False
    assert approval["design_use_acceptance"] is False
    assert approval["production_hem_activation_approved"] is False
    assert approval["two_phase_acoustic_accuracy_band_approved"] is False


@pytest.mark.coolprop_installed
def test_installed_forensic_result_matches_machine_readable_contract_exactly() -> None:
    pytest.importorskip("CoolProp")
    contract = _contract()
    result = run_fixed_4mpa_forensic_diagnostic(generate_plots=False)

    assert result.baseline_summary["outcome"] == contract["immutable_baseline"][
        "formal_outcome"
    ]
    assert result.perturbation_sensitivity == contract["perturbation_sensitivity"][
        "classification"
    ]
    assert list(result.diagnostic_categories) == contract["diagnostic_conclusion"][
        "categories"
    ]
    assert result.reconstruction_max_abs_error == contract[
        "rusanov_decomposition"
    ]["maximum_reconstruction_absolute_error"]
    assert result.reconstruction_max_relative_error == contract[
        "rusanov_decomposition"
    ]["maximum_reconstruction_relative_error"]

    raw = next(
        record
        for record in result.local_states
        if record.step_index == 313
        and record.cell_index == 25
        and record.stage == "raw_fvm"
    )
    raw_expected = contract["crossing_raw_state"]
    assert raw.pressure_pa == raw_expected["pressure_pa"]
    assert raw.rho_kg_m3 == raw_expected["rho_kg_m3"]
    assert raw.e_j_kg == raw_expected["internal_energy_j_kg"]
    assert raw.temperature_K == raw_expected["temperature_K"]
    assert raw.q_equilibrium == raw_expected["equilibrium_quality"]
    assert raw.void_fraction == raw_expected["void_fraction"]
    assert raw.sound_speed_m_s == raw_expected["sound_speed_candidate_m_s"]
    assert raw.boundary_region == raw_expected["boundary_region"]
    assert raw.transition_event == raw_expected["transition_event"]

    margin = next(
        record
        for record in result.saturation_margins
        if record.step_index == 313 and record.cell_index == 25
    )
    thermo = contract["thermodynamic_saturation_evidence"]
    assert margin.saturated_liquid_e_j_kg == thermo[
        "saturated_liquid_internal_energy_j_kg"
    ]
    assert margin.delta_u_sat_j_kg == thermo["delta_u_sat_j_kg"]
    assert margin.delta_v_sat_m3_kg == thermo["delta_v_sat_m3_kg"]
    assert margin.q_from_internal_energy == thermo["quality_from_internal_energy"]
    assert margin.q_from_specific_volume == thermo["quality_from_specific_volume"]
    assert margin.q_equilibrium == thermo["coolprop_equilibrium_quality"]
    assert margin.coordinate_support == thermo["coordinate_support"]

    isentropic = contract["isentropic_reference"]
    assert result.isentropic_reference.initial_entropy_j_kg_K == isentropic[
        "initial_entropy_j_kg_K"
    ]
    assert result.isentropic_reference.flash_pressure_pa == isentropic[
        "flash_pressure_pa"
    ]
    assert result.isentropic_reference.residual_j_kg_K == isentropic[
        "root_residual_j_kg_K"
    ]

    crossing_flux = next(
        record
        for record in result.flux_decomposition
        if record.step_index == 313 and record.cell_index == 25
    )
    flux_expected = contract["rusanov_decomposition"]
    assert crossing_flux.central_only_boundary_region == flux_expected[
        "crossing_cell_central_only_boundary_region"
    ]
    assert crossing_flux.central_only_q_equilibrium == flux_expected[
        "crossing_cell_central_only_quality"
    ]
    assert crossing_flux.central_only_delta_u_sat_j_kg == flux_expected[
        "crossing_cell_central_only_delta_u_sat_j_kg"
    ]
    assert crossing_flux.central_only_delta_v_sat_m3_kg == flux_expected[
        "crossing_cell_central_only_delta_v_sat_m3_kg"
    ]
