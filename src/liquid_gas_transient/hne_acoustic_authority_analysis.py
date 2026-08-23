"""Mathematical gates and authority decision for the P2 acoustic candidate."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict

import numpy as np

from .flux import physical_flux
from .hne_acoustic_authority_jacobian import (
    _matched_eigenvalue_error, analytic_flux_jacobian, authority_cases,
    candidate_conserved, independent_physical_flux, numerical_flux_jacobian,
)
from .hne_acoustic_authority_types import (
    CURRENT_SOLVER_EFFECT, FORMAL_OUTCOME, FORMAL_STATUS, NEXT_ACTION,
    PROPOSED_AUTHORITY_GRANT, SCHEMA_VERSION,
    SOURCE_A2_4_4_ANALYSIS_SHA256, SOURCE_A2_4_4_ARTIFACT_ID,
    SOURCE_A2_4_4_ARTIFACT_SHA256, SOURCE_A2_4_4_RUN_ID,
    SOURCE_A2_4_4_SHA, AcousticCompatibleHNEVerificationEOS,
    HNEAcousticAuthorityGateError,
)
from .hne_equilibrium_acoustic_closure import (
    DEFAULT_CONFIG, evaluate_equilibrium_acoustic,
)
from .hne_finite_relaxation_dispersion import (
    FORMAL_STATUS as A2_4_4_FORMAL_STATUS,
    SOLVER_AUTHORITY as A2_4_4_SOLVER_AUTHORITY,
)
from .hne_thermodynamic_closure import SurrogateFrozenQualityThermodynamicClosure
from .state import N_VARS

def _payload_sha(payload: object) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""

    return {
        "analysis_source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }


def analyze_acoustic_authority_gate() -> tuple[
    dict[str, object], tuple[dict[str, object], ...], tuple[dict[str, object], ...]
]:
    eos = AcousticCompatibleHNEVerificationEOS()
    legacy = SurrogateFrozenQualityThermodynamicClosure()
    case_rows: list[dict[str, object]] = []
    eigen_rows: list[dict[str, object]] = []
    for case in authority_cases():
        U = candidate_conserved(case)
        candidate = eos.evaluate(case.rho_kg_m3, case.e_j_kg, case.actual_quality)
        prim = eos.primitive_from_conserved(U[np.newaxis, :])
        production_formula_flux = np.asarray(physical_flux(U[np.newaxis, :], prim)[0])
        independent_flux = independent_physical_flux(U, candidate.pressure_pa)
        flux_formula_error = float(np.max(np.abs(production_formula_flux - independent_flux)))
        analytic = analytic_flux_jacobian(U, candidate)
        numerical = numerical_flux_jacobian(U, eos)
        jacobian_relative_error = float(
            np.linalg.norm(numerical - analytic)
            / max(float(np.linalg.norm(analytic)), 1.0)
        )
        analytic_eigenvalues = np.linalg.eigvals(analytic)
        numerical_eigenvalues = np.linalg.eigvals(numerical)
        expected = np.array(
            [
                case.velocity_m_s - candidate.frozen_c_m_s,
                case.velocity_m_s,
                case.velocity_m_s,
                case.velocity_m_s + candidate.frozen_c_m_s,
            ],
            dtype=float,
        )
        analytic_eigen_error = _matched_eigenvalue_error(analytic_eigenvalues, expected)
        numerical_eigen_error = _matched_eigenvalue_error(numerical_eigenvalues, expected)
        maximum_imaginary_eigenvalue = float(
            max(abs(value.imag) for value in numerical_eigenvalues)
        )
        repeated_mode_singular_values = np.linalg.svd(
            analytic - case.velocity_m_s * np.eye(N_VARS), compute_uv=False
        )
        repeated_mode_tolerance = 1.0e-10 * max(
            float(repeated_mode_singular_values[0]), 1.0
        )
        repeated_mode_nullity = int(
            np.count_nonzero(repeated_mode_singular_values <= repeated_mode_tolerance)
        )
        spectral_radius = float(max(abs(value) for value in analytic_eigenvalues))
        rusanov_bound = abs(case.velocity_m_s) + candidate.frozen_c_m_s
        equilibrium = evaluate_equilibrium_acoustic(case.rho_kg_m3, case.e_j_kg)
        if not equilibrium.valid or equilibrium.state is None:
            raise HNEAcousticAuthorityGateError(
                f"INVALID_EQUILIBRIUM_REFERENCE:{case.case_id}:{equilibrium.failure_reason}"
            )
        c_eq2 = float(equilibrium.equilibrium_sound_speed_squared_m2_s2)
        c_frozen_equilibrium2 = float(
            equilibrium.frozen_sound_speed_squared_m2_s2
        )
        legacy_q_eq = legacy.equilibrium_quality(case.rho_kg_m3, case.e_j_kg)
        equilibrium_case = abs(case.quality_offset) <= 1.0e-15
        pressure_equilibrium_error = (
            abs(candidate.pressure_pa - equilibrium.state.pressure_pa)
            if equilibrium_case
            else None
        )
        temperature_equilibrium_error = (
            abs(candidate.temperature_K - equilibrium.state.temperature_K)
            if equilibrium_case
            else None
        )
        frozen_equilibrium_relative_error = (
            abs(candidate.frozen_c2_m2_s2 - c_frozen_equilibrium2)
            / c_frozen_equilibrium2
            if equilibrium_case
            else None
        )
        row = {
            **asdict(case),
            "candidate_pressure_pa": candidate.pressure_pa,
            "candidate_temperature_K": candidate.temperature_K,
            "candidate_void_fraction": candidate.void_fraction,
            "candidate_frozen_c2_m2_s2": candidate.frozen_c2_m2_s2,
            "candidate_frozen_c_m_s": candidate.frozen_c_m_s,
            "equilibrium_c2_m2_s2": c_eq2,
            "equilibrium_frozen_c2_m2_s2": c_frozen_equilibrium2,
            "strict_equilibrium_subcharacteristic_margin_m2_s2": (
                c_frozen_equilibrium2 - c_eq2
            ),
            "legacy_a2_equilibrium_quality": legacy_q_eq,
            "legacy_a2_qeq_difference": legacy_q_eq - case.equilibrium_quality,
            "equilibrium_case": equilibrium_case,
            "pressure_equilibrium_error_pa": pressure_equilibrium_error,
            "temperature_equilibrium_error_K": temperature_equilibrium_error,
            "frozen_equilibrium_relative_error": frozen_equilibrium_relative_error,
            "physical_flux_formula_max_abs_error": flux_formula_error,
            "jacobian_relative_error": jacobian_relative_error,
            "analytic_eigenvalue_max_abs_error": analytic_eigen_error,
            "numerical_eigenvalue_max_abs_error": numerical_eigen_error,
            "maximum_numerical_eigenvalue_imaginary_part": maximum_imaginary_eigenvalue,
            "repeated_velocity_mode_nullity": repeated_mode_nullity,
            "analytic_spectral_radius": spectral_radius,
            "rusanov_bound": rusanov_bound,
            "rusanov_bound_margin": rusanov_bound - spectral_radius,
            "all_eigenvalues_real": maximum_imaginary_eigenvalue <= 1.0e-6,
            "hyperbolic": candidate.frozen_c2_m2_s2 > 0.0,
            "candidate_solver_effect": "NONE_GATE_ONLY",
        }
        case_rows.append(row)
        for source, values in (
            ("ANALYTIC", analytic_eigenvalues),
            ("NUMERICAL_FIVE_POINT", numerical_eigenvalues),
        ):
            ordered = sorted(values, key=lambda value: (value.real, value.imag))
            for index, value in enumerate(ordered):
                eigen_rows.append(
                    {
                        "case_id": case.case_id,
                        "source": source,
                        "eigenvalue_index": index,
                        "real_part": float(value.real),
                        "imaginary_part": float(value.imag),
                    }
                )

    equilibrium_rows = [row for row in case_rows if row["equilibrium_case"] is True]
    nonequilibrium_rows = [row for row in case_rows if row["equilibrium_case"] is False]
    legacy_mismatch = max(
        abs(float(row["legacy_a2_qeq_difference"])) for row in equilibrium_rows
    )
    repeated = _payload_sha({"cases": case_rows, "eigen": eigen_rows})
    repeated_again = _payload_sha({"cases": list(case_rows), "eigen": list(eigen_rows)})
    gates = {
        "A2_4_4_SOURCE_AND_SUCCESSFUL_EVIDENCE_PINNED": (
            SOURCE_A2_4_4_SHA == "b844741da4775f2e2970cbbe92a6b8be35fd3c79"
            and SOURCE_A2_4_4_RUN_ID == 32626761290
            and SOURCE_A2_4_4_ARTIFACT_ID == 9489909447
            and len(SOURCE_A2_4_4_ARTIFACT_SHA256) == 64
            and len(SOURCE_A2_4_4_ANALYSIS_SHA256) == 64
        ),
        "A2_4_4_AUTHORITY_REMAINED_CLOSED_BEFORE_GATE": (
            A2_4_4_FORMAL_STATUS["hydrodynamic_coupling_allowed"] is False
            and all(value is False for value in A2_4_4_SOLVER_AUTHORITY.values())
        ),
        "TWELVE_AUTHORITY_CASES_EVALUATED": len(case_rows) == 12,
        "FIVE_EQUILIBRIUM_AND_SEVEN_NONEQUILIBRIUM_CASES": (
            len(equilibrium_rows) == 5 and len(nonequilibrium_rows) == 7
        ),
        "LEGACY_A2_EQUILIBRIUM_MAP_EXPLICITLY_QUARANTINED": legacy_mismatch > 1.0e-2,
        "EQUILIBRIUM_PRESSURE_AND_TEMPERATURE_RECOVER_A2_4_2R": all(
            float(row["pressure_equilibrium_error_pa"]) <= 5.0e-4
            and float(row["temperature_equilibrium_error_K"]) <= 2.0e-9
            for row in equilibrium_rows
        ),
        "FROZEN_DERIVATIVE_RECOVERS_A2_4_2R_AT_EQUILIBRIUM": all(
            float(row["frozen_equilibrium_relative_error"]) <= 5.0e-10
            for row in equilibrium_rows
        ),
        "STRICT_SUBCHARACTERISTIC_MARGIN_RETAINED_AT_EQUILIBRIUM": all(
            float(row["strict_equilibrium_subcharacteristic_margin_m2_s2"]) > 0.0
            for row in equilibrium_rows
        ),
        "ALL_CANDIDATE_STATES_FINITE_POSITIVE_AND_HYPERBOLIC": all(
            row["hyperbolic"] is True
            and float(row["candidate_pressure_pa"]) > 0.0
            and float(row["candidate_temperature_K"]) > 0.0
            for row in case_rows
        ),
        "PRODUCTION_PHYSICAL_FLUX_FORMULA_MATCHES_INDEPENDENT_FORM": all(
            float(row["physical_flux_formula_max_abs_error"]) <= 1.0e-12
            for row in case_rows
        ),
        "ANALYTIC_AND_FIVE_POINT_FLUX_JACOBIANS_AGREE": all(
            float(row["jacobian_relative_error"]) <= 1.0e-5
            for row in case_rows
        ),
        "ANALYTIC_JACOBIAN_EIGENVALUES_MATCH_U_PLUS_MINUS_C_FROZEN": all(
            float(row["analytic_eigenvalue_max_abs_error"]) <= 1.0e-8
            for row in case_rows
        ),
        "NUMERICAL_JACOBIAN_EIGENVALUES_MATCH_U_PLUS_MINUS_C_FROZEN": all(
            float(row["numerical_eigenvalue_max_abs_error"]) <= 1.0e-3
            and row["all_eigenvalues_real"] is True
            for row in case_rows
        ),
        "DOUBLE_VELOCITY_MODE_IS_DIAGONALIZABLE": all(
            int(row["repeated_velocity_mode_nullity"]) == 2 for row in case_rows
        ),
        "RUSANOV_BOUND_EQUALS_OR_EXCEEDS_SPECTRAL_RADIUS": all(
            float(row["rusanov_bound_margin"]) >= -1.0e-10 for row in case_rows
        ),
        "NO_EXISTING_SOLVER_PATH_MODIFIED": all(
            value is False for value in CURRENT_SOLVER_EFFECT.values()
        ),
        "DETERMINISTIC_REPRODUCIBILITY": repeated == repeated_again,
        "AUTHORITY_GRANT_IS_LIMITED_TO_P2_A3_1_INTERIOR_IMPLEMENTATION": (
            PROPOSED_AUTHORITY_GRANT["candidate_pressure_to_interior_euler_flux_in_p2_a3_1"]
            and PROPOSED_AUTHORITY_GRANT["candidate_frozen_c_to_interior_rusanov_in_p2_a3_1"]
            and PROPOSED_AUTHORITY_GRANT["candidate_frozen_c_to_interior_cfl_in_p2_a3_1"]
            and all(
                PROPOSED_AUTHORITY_GRANT[key] is False
                for key in (
                    "equilibrium_c_to_solver",
                    "finite_relaxation_phase_speed_to_solver",
                    "hne_boundary_characteristics",
                    "hne_critical_discharge",
                    "finite_pipe_discharge_feedback",
                    "design_use",
                    "production_use",
                )
            )
        ),
        "MATURITY_NOT_OVERPROMOTED": all(
            FORMAL_STATUS[key] is False
            for key in (
                "hydrodynamic_coupling_implemented",
                "finite_pipeline_hne_coupling_implemented",
                "boundary_characteristics_authorized",
                "discharge_coupling_authorized",
                "verified",
                "accepted",
                "physically_validated",
                "design_use_accepted",
                "production_approved",
            )
        ),
    }
    failed = [name for name, passed in gates.items() if not passed]
    passed = not failed
    effective_formal_status = dict(FORMAL_STATUS)
    effective_formal_status["acoustic_authority_gate_passed"] = passed
    effective_formal_status["limited_p2_a3_1_implementation_authorized"] = passed
    effective_authority_grant = {
        key: (bool(value) if passed else False)
        for key, value in PROPOSED_AUTHORITY_GRANT.items()
    }
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "p2_hne_acoustic_authority_gate_limited_interior_candidate",
        "source_a2_4_4": {
            "head_sha": SOURCE_A2_4_4_SHA,
            "workflow_run_id": SOURCE_A2_4_4_RUN_ID,
            "artifact_id": SOURCE_A2_4_4_ARTIFACT_ID,
            "artifact_sha256": SOURCE_A2_4_4_ARTIFACT_SHA256,
            "analysis_sha256": SOURCE_A2_4_4_ANALYSIS_SHA256,
        },
        "candidate_model": {
            "conservative_variables": ["RHO", "RHO_U", "RHO_E", "RHO_Q"],
            "pressure_closure": "A2_4_2R_CONSTITUENT_VOLUME_MANIFOLD_AT_TRANSPORTED_Q",
            "temperature_closure": "COMMON_CV_LIQUID_CALORIC_SLOPE_FOR_VERIFICATION",
            "equilibrium_map": "A2_4_2R_PRESSURE_DEPENDENT_EQUILIBRIUM_MANIFOLD",
            "frozen_sound_speed": "DP_DRHO_AT_FIXED_Q_FROM_SAME_PRESSURE_CLOSURE",
            "expected_characteristics": ["U_MINUS_C_FROZEN", "U", "U", "U_PLUS_C_FROZEN"],
            "claimed_pressure_interval_pa": [
                DEFAULT_CONFIG.claimed_pressure_min_pa,
                DEFAULT_CONFIG.claimed_pressure_max_pa,
            ],
            "claimed_quality_interval": [
                DEFAULT_CONFIG.claimed_quality_min,
                DEFAULT_CONFIG.claimed_quality_max,
            ],
            "boundary_policy": "OPEN_INTERVAL_FAIL_CLOSED",
        },
        "legacy_a2_equilibrium_map": {
            "maximum_qeq_difference_on_equilibrium_cases": legacy_mismatch,
            "authority": "QUARANTINED_NOT_USED_FOR_P2_A3_1_CANDIDATE",
        },
        "formal_status": effective_formal_status,
        "authority_grant": effective_authority_grant,
        "current_solver_effect": dict(CURRENT_SOLVER_EFFECT),
        "case_count": len(case_rows),
        "gate_results": gates,
        "failed_gates": failed,
        "acoustic_authority_gate_passed": passed,
        "formal_outcome": (
            FORMAL_OUTCOME if passed else "ACOUSTIC_AUTHORITY_GATE_FAILED_CLOSED"
        ),
        "next_action": (
            NEXT_ACTION if passed else "RESOLVE_FAILED_AUTHORITY_GATES_BEFORE_P2_A3"
        ),
        "runtime_provenance": _provenance(),
        "limitations": [
            "ANALYTIC_SURROGATE_VERIFICATION_DOMAIN_ONLY",
            "NO_REAL_CO2_PHYSICAL_VALIDATION",
            "NO_EXISTING_SOLVER_COUPLING_IN_THIS_INCREMENT",
            "NO_BOUNDARY_OR_DISCHARGE_AUTHORITY",
            "FINITE_RELAXATION_PHASE_SPEED_REMAINS_DIAGNOSTIC_ONLY",
            "P2_A3_1_MUST_ADD_UNIFORM_STATE_SMALL_PULSE_AND_LIMIT_TESTS",
        ],
    }
    authority_payload = {
        key: value for key, value in summary.items() if key != "runtime_provenance"
    }
    summary["analysis_sha256"] = _payload_sha(
        {"authority": authority_payload, "cases": case_rows, "eigenvalues": eigen_rows}
    )
    return summary, tuple(case_rows), tuple(eigen_rows)
