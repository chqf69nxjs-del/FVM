from __future__ import annotations

import json
from pathlib import Path


CONTRACT = Path(
    "docs/verification/stage7_u3_b1_critical_state_contract_v1.json"
)


def _load() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_identity_and_lock_state() -> None:
    contract = _load()
    assert contract["schema_version"] == (
        "stage7_u3_b1_critical_state_contract_v1"
    )
    assert contract["status"] == "LOCKED_BEFORE_RESULTS"
    assert contract["scope"] == (
        "verification_only_single_phase_compressible_component_benchmark"
    )
    assert contract["issue"] == 127
    assert contract["fluid"] == "CO2"
    assert contract["property_backend"] == {
        "name": "CoolProp",
        "version": "8.0.0",
    }


def test_state_families_separate_b0_limit_from_critical_search() -> None:
    contract = _load()
    states = {
        row["state_id"]: row
        for row in contract["upstream_state_families"]
    }
    assert set(states) == {"LIQUID_LIMIT", "GAS_CRITICAL"}

    liquid = states["LIQUID_LIMIT"]
    assert liquid["pressure_pa"] == 5.0e6
    assert liquid["subcooling_K"] == 5.0
    assert liquid["allowed_normalized_phases"] == ["liquid"]
    assert liquid["critical_state_search_required"] is False

    gas = states["GAS_CRITICAL"]
    assert gas["pressure_pa"] == 1.0e6
    assert gas["temperature_K"] == 320.0
    assert gas["allowed_normalized_phases"] == [
        "gas",
        "supercriticalgas",
    ]
    assert gas["critical_state_search_required"] is True


def test_equations_and_search_are_frozen_before_results() -> None:
    contract = _load()
    law = contract["isentropic_candidate_law"]
    assert law["entropy_constraint"] == "s_candidate=s0"
    assert law["effective_velocity_m_s"] == "Cd*ideal_velocity_m_s"
    assert law["mass_flow_rate_kg_s"] == (
        "Aeff*effective_mass_flux_kg_m2_s"
    )
    assert "Cd-independent" in law["coefficient_placement"]

    search = contract["critical_state_search"]
    assert search["applies_to_state_id"] == "GAS_CRITICAL"
    assert search["coarse_pressure_ratio_upper"] == 1.0
    assert search["coarse_pressure_ratio_lower"] == 0.05
    assert search["coarse_node_count"] == 4097
    assert search["refinement_method"] == (
        "deterministic_golden_section_maximization_in_pressure"
    )
    assert search["refinement_pressure_bracket_tolerance_pa"] == 1.0
    assert search["refinement_max_iterations"] == 128
    assert search["critical_state_must_be_interior"] is True


def test_fixed_case_matrix_and_predeclared_acceptance() -> None:
    contract = _load()
    cases = contract["benchmark_cases"]
    case_ids = [row["case_id"] for row in cases]
    assert len(case_ids) == 17
    assert len(case_ids) == len(set(case_ids))
    assert set(case_ids) == {
        "B1-01_CLOSED_ELEMENT",
        "B1-02_ZERO_PRESSURE_DROP",
        "B1-03_SMALL_DROP_RECOVERS_B0_LIMIT",
        "B1-04A_UNCHOKED_HIGH_BACK_PRESSURE",
        "B1-04B_UNCHOKED_LOWER_BACK_PRESSURE",
        "B1-05_CRITICAL_STATE_SEARCH",
        "B1-06A_BELOW_CRITICAL_PLATEAU_HIGH",
        "B1-06B_BELOW_CRITICAL_PLATEAU_LOW",
        "B1-07A_AREA_SCALING_LOW",
        "B1-07B_AREA_SCALING_HIGH",
        "B1-08A_CD_SCALING_LOW",
        "B1-08B_CD_SCALING_HIGH",
        "G-01_REVERSE_PRESSURE",
        "G-02_NONFINITE_INPUT",
        "G-03_SINGLE_PHASE_SCOPE_FAILURE",
        "G-04_NONPOSITIVE_KINETIC_ENERGY_HEAD",
        "G-05_CRITICAL_SEARCH_NOT_BRACKETED",
    }

    tolerances = contract["acceptance_tolerances"]
    assert tolerances["exact_zero_absolute"] == 0.0
    assert tolerances["B0_limit_mass_flow_relative"] == 0.01
    assert tolerances["B0_limit_momentum_transfer_relative"] == 0.02
    assert tolerances["below_critical_plateau_relative"] == 5.0e-6
    assert tolerances["reference_adapter_critical_pressure_absolute_pa"] == 250.0
    assert tolerances["scaling_ratio_absolute"] == 1.0e-10


def test_independence_scope_and_approval_boundary() -> None:
    contract = _load()
    independent = contract["independent_paths"]
    assert independent == {
        "reference_first": True,
        "adapter_uses_reference_module": False,
        "shared_critical_search_helper": False,
        "shared_property_path_helper": False,
        "shared_transfer_construction_helper": False,
    }

    assert all(value is False for value in contract["immutable_scope"].values())

    approval = contract["approval_boundary"]
    assert approval["u3_b1_contract_locked"] is True
    for key, value in approval.items():
        if key != "u3_b1_contract_locked":
            assert value is False, key
