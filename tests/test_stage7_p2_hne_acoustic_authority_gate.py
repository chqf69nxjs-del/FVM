from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.flux import physical_flux
from liquid_gas_transient.hne_acoustic_authority_gate import (
    CURRENT_SOLVER_EFFECT,
    FORMAL_STATUS,
    NEXT_ACTION,
    OUTPUT_FILES,
    PROPOSED_AUTHORITY_GRANT,
    SCHEMA_VERSION,
    SOURCE_A2_4_4_ANALYSIS_SHA256,
    SOURCE_A2_4_4_ARTIFACT_ID,
    SOURCE_A2_4_4_ARTIFACT_SHA256,
    SOURCE_A2_4_4_RUN_ID,
    SOURCE_A2_4_4_SHA,
    AcousticCompatibleHNEVerificationEOS,
    HNEAcousticAuthorityGateError,
    analytic_flux_jacobian,
    analyze_acoustic_authority_gate,
    authority_cases,
    candidate_conserved,
    independent_physical_flux,
    numerical_flux_jacobian,
    write_artifacts,
)
from liquid_gas_transient.hne_equilibrium_acoustic_closure import (
    evaluate_equilibrium_acoustic,
)
from liquid_gas_transient.hne_thermodynamic_closure import (
    SurrogateFrozenQualityThermodynamicClosure,
)
from liquid_gas_transient.state import N_VARS


def test_source_pin_and_pre_gate_authority_boundary() -> None:
    assert SCHEMA_VERSION == "stage7_p2_hne_acoustic_authority_gate_v1"
    assert SOURCE_A2_4_4_SHA == "b844741da4775f2e2970cbbe92a6b8be35fd3c79"
    assert SOURCE_A2_4_4_RUN_ID == 32626761290
    assert SOURCE_A2_4_4_ARTIFACT_ID == 9489909447
    assert SOURCE_A2_4_4_ARTIFACT_SHA256 == (
        "0164a54af61696aa6c955a4f5854589f4ad9b164c095d914e3f30446c865a4b2"
    )
    assert SOURCE_A2_4_4_ANALYSIS_SHA256 == (
        "1357f0c768df7834a84d8c3d00dbb27e7524d7c9df9c6e1e744b23aca3b326cd"
    )
    assert FORMAL_STATUS["acoustic_authority_gate_passed"] is False
    assert FORMAL_STATUS["limited_p2_a3_1_implementation_authorized"] is False
    assert all(value is False for value in CURRENT_SOLVER_EFFECT.values())


def test_proposed_authority_is_narrow_and_does_not_activate_solver() -> None:
    assert PROPOSED_AUTHORITY_GRANT[
        "candidate_pressure_to_interior_euler_flux_in_p2_a3_1"
    ] is True
    assert PROPOSED_AUTHORITY_GRANT[
        "candidate_frozen_c_to_interior_rusanov_in_p2_a3_1"
    ] is True
    assert PROPOSED_AUTHORITY_GRANT[
        "candidate_frozen_c_to_interior_cfl_in_p2_a3_1"
    ] is True
    for key in (
        "equilibrium_c_to_solver",
        "finite_relaxation_phase_speed_to_solver",
        "hne_boundary_characteristics",
        "hne_critical_discharge",
        "finite_pipe_discharge_feedback",
        "design_use",
        "production_use",
    ):
        assert PROPOSED_AUTHORITY_GRANT[key] is False
    assert all(value is False for value in CURRENT_SOLVER_EFFECT.values())


def test_equilibrium_cases_recover_parent_pressure_temperature_and_frozen_c2() -> None:
    eos = AcousticCompatibleHNEVerificationEOS()
    for case in authority_cases():
        if abs(case.quality_offset) > 1.0e-15:
            continue
        candidate = eos.evaluate(case.rho_kg_m3, case.e_j_kg, case.actual_quality)
        parent = evaluate_equilibrium_acoustic(case.rho_kg_m3, case.e_j_kg)
        assert parent.valid, parent.failure_reason
        assert parent.state is not None
        assert parent.frozen_sound_speed_squared_m2_s2 is not None
        assert candidate.pressure_pa == pytest.approx(
            parent.state.pressure_pa, abs=5.0e-4
        )
        assert candidate.temperature_K == pytest.approx(
            parent.state.temperature_K, abs=2.0e-9
        )
        assert candidate.frozen_c2_m2_s2 == pytest.approx(
            parent.frozen_sound_speed_squared_m2_s2, rel=5.0e-10
        )


def test_nonequilibrium_cases_are_finite_hyperbolic_and_pressure_sensitive_to_q() -> None:
    eos = AcousticCompatibleHNEVerificationEOS()
    for case in authority_cases():
        candidate = eos.evaluate(case.rho_kg_m3, case.e_j_kg, case.actual_quality)
        assert math.isfinite(candidate.pressure_pa) and candidate.pressure_pa > 0.0
        assert math.isfinite(candidate.temperature_K) and candidate.temperature_K > 0.0
        assert math.isfinite(candidate.frozen_c2_m2_s2)
        assert candidate.frozen_c2_m2_s2 > 0.0
        assert candidate.dp_drho_at_q_m2_s2 == candidate.frozen_c2_m2_s2
        if abs(case.quality_offset) > 1.0e-15:
            assert abs(candidate.pressure_pa - case.equilibrium_pressure_pa) > 1.0


def test_production_flux_formula_matches_independent_four_variable_form() -> None:
    eos = AcousticCompatibleHNEVerificationEOS()
    for case in authority_cases():
        U = candidate_conserved(case)
        state = eos.evaluate(case.rho_kg_m3, case.e_j_kg, case.actual_quality)
        prim = eos.primitive_from_conserved(U[np.newaxis, :])
        actual = np.asarray(physical_flux(U[np.newaxis, :], prim)[0])
        expected = independent_physical_flux(U, state.pressure_pa)
        assert np.array_equal(actual, expected)


def test_analytic_and_five_point_flux_jacobians_agree() -> None:
    eos = AcousticCompatibleHNEVerificationEOS()
    for case in authority_cases():
        U = candidate_conserved(case)
        state = eos.evaluate(case.rho_kg_m3, case.e_j_kg, case.actual_quality)
        analytic = analytic_flux_jacobian(U, state)
        numerical = numerical_flux_jacobian(U, eos)
        relative = np.linalg.norm(numerical - analytic) / max(
            float(np.linalg.norm(analytic)), 1.0
        )
        assert relative <= 1.0e-5


def test_flux_jacobian_has_expected_hyperbolic_characteristics() -> None:
    eos = AcousticCompatibleHNEVerificationEOS()
    for case in authority_cases():
        U = candidate_conserved(case)
        state = eos.evaluate(case.rho_kg_m3, case.e_j_kg, case.actual_quality)
        analytic = analytic_flux_jacobian(U, state)
        eigenvalues = np.linalg.eigvals(analytic)
        expected = np.sort(
            np.array(
                [
                    case.velocity_m_s - state.frozen_c_m_s,
                    case.velocity_m_s,
                    case.velocity_m_s,
                    case.velocity_m_s + state.frozen_c_m_s,
                ]
            )
        )
        assert np.max(np.abs(np.sort(eigenvalues.real) - expected)) <= 1.0e-8
        assert np.max(np.abs(eigenvalues.imag)) <= 1.0e-10
        singular = np.linalg.svd(
            analytic - case.velocity_m_s * np.eye(N_VARS), compute_uv=False
        )
        tolerance = 1.0e-10 * max(float(singular[0]), 1.0)
        assert int(np.count_nonzero(singular <= tolerance)) == 2
        spectral_radius = max(abs(value) for value in eigenvalues)
        assert abs(case.velocity_m_s) + state.frozen_c_m_s >= spectral_radius - 1.0e-10


def test_legacy_density_only_equilibrium_map_is_detected_and_not_promoted() -> None:
    legacy = SurrogateFrozenQualityThermodynamicClosure()
    differences = []
    for case in authority_cases():
        if abs(case.quality_offset) <= 1.0e-15:
            differences.append(
                legacy.equilibrium_quality(case.rho_kg_m3, case.e_j_kg)
                - case.equilibrium_quality
            )
    assert max(abs(value) for value in differences) > 1.0e-2


def test_full_gate_passes_with_effective_authority_but_no_active_coupling() -> None:
    summary, case_rows, eigen_rows = analyze_acoustic_authority_gate()
    assert summary["acoustic_authority_gate_passed"] is True
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert len(case_rows) == 12
    assert len(eigen_rows) == 12 * 2 * 4
    assert summary["formal_status"]["acoustic_authority_gate_passed"] is True
    assert summary["formal_status"][
        "limited_p2_a3_1_implementation_authorized"
    ] is True
    assert summary["formal_status"]["hydrodynamic_coupling_implemented"] is False
    assert summary["authority_grant"][
        "candidate_pressure_to_interior_euler_flux_in_p2_a3_1"
    ] is True
    assert all(value is False for value in summary["current_solver_effect"].values())
    assert summary["next_action"] == NEXT_ACTION
    for key in (
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert summary["formal_status"][key] is False


def test_fail_closed_and_byte_deterministic_evidence(tmp_path: Path) -> None:
    eos = AcousticCompatibleHNEVerificationEOS()
    reference = authority_cases()[0]
    with pytest.raises(HNEAcousticAuthorityGateError):
        eos.evaluate(reference.rho_kg_m3, reference.e_j_kg, 0.0)
    with pytest.raises(HNEAcousticAuthorityGateError):
        eos.evaluate(reference.rho_kg_m3, reference.e_j_kg, 0.45)

    summary, case_rows, eigen_rows = analyze_acoustic_authority_gate()
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_artifacts(first, summary, case_rows, eigen_rows)
    write_artifacts(second, summary, case_rows, eigen_rows)
    assert {path.name for path in first.iterdir()} == set(OUTPUT_FILES)
    assert {path.name for path in second.iterdir()} == set(OUTPUT_FILES)
    for name in OUTPUT_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    loaded = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert loaded["acoustic_authority_gate_passed"] is True
    assert manifest["acoustic_authority_gate_passed"] is True
    assert manifest["limited_p2_a3_1_implementation_authorized"] is True
    assert manifest["hydrodynamic_coupling_active"] is False
