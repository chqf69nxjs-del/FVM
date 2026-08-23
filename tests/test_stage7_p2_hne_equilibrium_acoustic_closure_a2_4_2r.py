from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from liquid_gas_transient.hne_equilibrium_acoustic_closure import (
    ACOUSTIC_AUTHORITY,
    DEFAULT_CONFIG,
    FORMAL_OUTCOME,
    FORMAL_STATUS,
    MODEL_FORM,
    NEXT_ACTION,
    SOLVER_AUTHORITY,
    evaluate_equilibrium_acoustic,
    evaluate_focused_gates,
    recover_equilibrium_state,
    representative_cases,
    state_from_pressure_quality,
    write_evidence,
)


def test_pressure_quality_state_round_trip_is_deterministic() -> None:
    for case in representative_cases():
        source = state_from_pressure_quality(
            case.pressure_pa,
            case.vapor_mass_fraction,
        )
        recovered = recover_equilibrium_state(source.rho_kg_m3, source.e_j_kg)
        assert recovered.within_claimed_domain
        assert recovered.pressure_pa == pytest.approx(case.pressure_pa, abs=2.0e-4)
        assert recovered.vapor_mass_fraction == pytest.approx(
            case.vapor_mass_fraction,
            abs=2.0e-11,
        )
        assert abs(recovered.volume_residual_m3_kg) <= (
            DEFAULT_CONFIG.volume_residual_tolerance_m3_kg
        )


def test_representative_equilibrium_c2_is_finite_and_positive() -> None:
    for case in representative_cases():
        source = state_from_pressure_quality(case.pressure_pa, case.vapor_mass_fraction)
        result = evaluate_equilibrium_acoustic(source.rho_kg_m3, source.e_j_kg)
        assert result.valid, result.failure_reason
        assert result.positive_hyperbolicity_satisfied is True
        assert result.equilibrium_sound_speed_squared_m2_s2 is not None
        assert result.equilibrium_sound_speed_m_s is not None
        assert math.isfinite(result.equilibrium_sound_speed_squared_m2_s2)
        assert result.equilibrium_sound_speed_squared_m2_s2 > 0.0
        assert result.equilibrium_sound_speed_m_s > 0.0


def test_centered_directional_derivative_matches_implicit_derivative() -> None:
    for case in representative_cases():
        source = state_from_pressure_quality(case.pressure_pa, case.vapor_mass_fraction)
        result = evaluate_equilibrium_acoustic(source.rho_kg_m3, source.e_j_kg)
        assert result.valid, result.failure_reason
        assert result.derivative_crosscheck_satisfied is True
        assert result.derivative_relative_error is not None
        assert result.derivative_relative_error <= DEFAULT_CONFIG.derivative_relative_tolerance
        assert result.finite_difference_sound_speed_squared_m2_s2 == pytest.approx(
            result.equilibrium_sound_speed_squared_m2_s2,
            rel=DEFAULT_CONFIG.derivative_relative_tolerance,
        )


def test_subcharacteristic_relation_holds_in_claimed_liquid_rich_domain() -> None:
    for case in representative_cases():
        source = state_from_pressure_quality(case.pressure_pa, case.vapor_mass_fraction)
        result = evaluate_equilibrium_acoustic(source.rho_kg_m3, source.e_j_kg)
        assert result.valid, result.failure_reason
        assert result.subcharacteristic_satisfied is True
        assert result.equilibrium_sound_speed_squared_m2_s2 is not None
        assert result.frozen_sound_speed_squared_m2_s2 is not None
        assert result.equilibrium_sound_speed_squared_m2_s2 <= (
            result.frozen_sound_speed_squared_m2_s2
            * (1.0 + DEFAULT_CONFIG.subcharacteristic_relative_tolerance)
        )


def test_outside_claimed_quality_domain_fails_closed_without_acoustic_value() -> None:
    for pressure_pa, quality in ((2.5e6, 0.80), (2.5e6, 0.45), (1.5e6, 0.10)):
        source = state_from_pressure_quality(pressure_pa, quality)
        result = evaluate_equilibrium_acoustic(source.rho_kg_m3, source.e_j_kg)
        assert not result.valid
        assert result.failure_reason == "OUTSIDE_CLAIMED_LIQUID_RICH_DOMAIN"
        assert result.state is not None
        assert not result.state.within_claimed_domain
        assert result.equilibrium_sound_speed_squared_m2_s2 is None
        assert result.frozen_sound_speed_squared_m2_s2 is None
        assert result.solver_authority_granted is False


def test_invalid_rho_fails_closed_without_hidden_fallback() -> None:
    result = evaluate_equilibrium_acoustic(-1.0, 1.0e5)
    assert not result.valid
    assert "rho must be finite and positive" in result.failure_reason
    assert result.state is None
    assert result.equilibrium_sound_speed_m_s is None
    assert result.acoustic_authority == ACOUSTIC_AUTHORITY
    assert result.model_form == MODEL_FORM


def test_focused_gates_and_maturity_boundary_are_explicit() -> None:
    records, gates = evaluate_focused_gates()
    assert len(records) == len(representative_cases()) == 5
    assert all(gates.values())
    assert all(record["valid"] is True for record in records)
    assert all(value is False for value in SOLVER_AUTHORITY.values())
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["working_verification_slice"] is True
    assert FORMAL_STATUS["working_vertical_slice"] is False
    for key in (
        "finite_pipeline_acoustic_shadow",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False
    assert FORMAL_OUTCOME == (
        "A2_4_2R_WORKING_VERIFICATION_SLICE_WITH_SOLVER_AUTHORITY_CLOSED"
    )
    assert NEXT_ACTION == "PROCEED_TO_A2_4_3_FINITE_PIPELINE_READ_ONLY_ACOUSTIC_SHADOW"


def test_evidence_is_complete_and_byte_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANALYSIS_SOURCE_GIT_SHA", "TEST_SHA")
    first = tmp_path / "first"
    second = tmp_path / "second"
    summary_first = write_evidence(first)
    summary_second = write_evidence(second)
    expected = {
        "summary.json",
        "equilibrium_acoustic_cases.csv",
        "operator_report.md",
        "manifest.json",
    }
    assert {path.name for path in first.iterdir()} == expected
    assert {path.name for path in second.iterdir()} == expected
    for name in expected:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    assert summary_first == summary_second
    loaded = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert loaded["green_for_a2_4_3_read_only_shadow"] is True
    assert loaded["failed_gates"] == []
    assert all(loaded["gate_results"].values())
    assert all(value is False for value in loaded["solver_authority"].values())
    assert loaded["real_fluid_reference"]["numerical_comparison_in_this_slice"] is False
    assert loaded["real_fluid_reference"]["required_before_physical_validation"] is True
    assert manifest["green_for_a2_4_3_read_only_shadow"] is True
    assert manifest["hydrodynamic_coupling_allowed"] is False
