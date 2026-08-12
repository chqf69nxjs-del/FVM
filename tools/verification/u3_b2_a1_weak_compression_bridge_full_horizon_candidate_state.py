from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_full_horizon as full_horizon
import u3_b2_a1_weak_compression_bridge_full_horizon_back_pressure_crossing as increment_4b
import u3_b2_a1_weak_compression_bridge_one_step as one_step
import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_a1_weak_compression_bridge_stagnation_pressure_crossing_diagnostic as increment_4c
import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import normalize_phase


INCREMENT_4C_SOURCE_SHA = "2edd55307658e578f880bf99e661fee6753be874"
INCREMENT_4C_WORKFLOW_RUN = 31615812004
INCREMENT_4C_JOB = 94178201383
INCREMENT_4C_ARTIFACT = 9149147400
INCREMENT_4C_ARTIFACT_SHA256 = (
    "260806e46275ff0c5d3bf6b1acd45bfd0f93268743a684342b92e00511f5e80e"
)
INCREMENT_4C_OUTCOME = "STAGNATION_PRESSURE_CROSSING_POSITIVE_ROOT_SUPPORTED"
FAILED_INCREMENT_4B_SOURCE_SHA = "532ba7388915e8d484aae5a65de87dc760c200aa"
FAILED_INCREMENT_4B_WORKFLOW_RUN = 31614869209
FAILED_INCREMENT_4B_JOB = 94175042813
FAILED_INCREMENT_4B_ARTIFACT = 9148819125
FAILED_INCREMENT_4B_ARTIFACT_SHA256 = (
    "71f1e2bfa2959f526466a0effbfd8daaa50e56d416f37697679d829b69c26437"
)
FIRST_CANDIDATE_STATE_CORRECTION_STEP = 448
EXPECTED_ENDPOINT_GUARD = "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED"
OUTCOME = "WEAK_COMPRESSION_INCREMENT_4D_FULL_HORIZON_WORKING_SLICE_PASS"
robustness = robustness_v4.robustness


class CandidateStateContinuationStop(short_run.WeakCompressionShortRunStop):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_increment_4c_artifact(
    artifact_dir: Path,
    *,
    artifact_digest: str,
) -> dict[str, Any]:
    if artifact_digest != INCREMENT_4C_ARTIFACT_SHA256:
        raise CandidateStateContinuationStop(
            "INCREMENT_4C_AUTHORITY_MISMATCH",
            "Increment 4C GitHub artifact digest mismatch",
        )
    required = {
        "step447_local_wave_scans.csv",
        "step447_positive_pressure_scans.csv",
        "step447_weak_compression_root.csv",
        "step447_state_identity.npz",
        "summary.json",
        "report.md",
        "artifact_sha256.txt",
    }
    actual = {path.name for path in artifact_dir.iterdir() if path.is_file()}
    if actual != required:
        raise CandidateStateContinuationStop(
            "INCREMENT_4C_AUTHORITY_MISMATCH",
            f"Increment 4C file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (artifact_dir / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != required - {"artifact_sha256.txt"}:
        raise CandidateStateContinuationStop(
            "INCREMENT_4C_AUTHORITY_MISMATCH",
            "Increment 4C internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(artifact_dir / name) != digest:
            raise CandidateStateContinuationStop(
                "INCREMENT_4C_AUTHORITY_MISMATCH",
                f"Increment 4C internal SHA256 mismatch for {name}",
            )
    summary = json.loads(
        (artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    if summary.get("source_git_sha") != INCREMENT_4C_SOURCE_SHA:
        raise CandidateStateContinuationStop(
            "INCREMENT_4C_AUTHORITY_MISMATCH",
            "Increment 4C source SHA mismatch",
        )
    if summary.get("outcome") != INCREMENT_4C_OUTCOME or not bool(
        summary.get("increment_4c_diagnostic_gate_passed")
    ):
        raise CandidateStateContinuationStop(
            "INCREMENT_4C_AUTHORITY_MISMATCH",
            "Increment 4C outcome or diagnostic gate mismatch",
        )
    if int(summary.get("solver_step_loaded", -1)) != 447:
        raise CandidateStateContinuationStop(
            "INCREMENT_4C_AUTHORITY_MISMATCH",
            "Increment 4C did not diagnose accepted step 447",
        )
    if bool(summary.get("fvm_step_448_attempted")):
        raise CandidateStateContinuationStop(
            "INCREMENT_4C_AUTHORITY_MISMATCH",
            "Increment 4C unexpectedly attempted step 448",
        )
    return summary


def _verify_failed_increment_4b_artifact(
    artifact_dir: Path,
    *,
    artifact_digest: str,
) -> dict[str, Any]:
    try:
        summary, _, _ = increment_4c._verify_parent_artifact(
            artifact_dir,
            parent_artifact_digest=artifact_digest,
        )
    except Exception as exc:
        raise CandidateStateContinuationStop(
            "FAILED_INCREMENT_4B_AUTHORITY_MISMATCH",
            f"failed Increment 4B authority verification failed: {exc}",
        ) from exc
    return summary


def _candidate_state_build_weak_compression_context(
    *,
    contract: dict[str, Any],
    state_id: str,
    provider: Any,
    hook: Any,
    outlet_conserved: np.ndarray,
    solver_time_s: float,
    increment_1_root: dict[str, Any],
    increment_1_scan_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reconstruction = provider.reconstruct_from_conserved(outlet_conserved)
    static = reconstruction.static
    back_pressure = float(hook.adapter.back_pressure_pa)
    if float(reconstruction.stagnation_pressure_pa) > back_pressure:
        context = increment_4b._corrected_build_weak_compression_context(
            contract=contract,
            state_id=state_id,
            provider=provider,
            hook=hook,
            outlet_conserved=outlet_conserved,
            solver_time_s=solver_time_s,
            increment_1_root=increment_1_root,
            increment_1_scan_rows=increment_1_scan_rows,
        )
        context.setdefault("stagnation_pressure_crossing_correction_applied", False)
        context.setdefault("endpoint_guard_bypassed_for_classification", False)
        context.setdefault("endpoint_guard_formal_outcome", None)
        context.setdefault("positive_scan_guard_node_count", 0)
        context.setdefault("positive_scan_first_success_offset_pa", None)
        context.setdefault("root_stagnation_pressure_minus_back_pa", float(
            context["root"]["stagnation_pressure_pa"] - back_pressure
        ))
        return context

    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if normalize_phase(static.phase) not in allowed_phases:
        raise one_step.WeakCompressionOneStepStop(
            f"interior phase {static.phase!r} is outside {sorted(allowed_phases)}"
        )
    if float(static.velocity_m_s) < -velocity_tolerance:
        raise one_step.WeakCompressionOneStepStop(
            f"interior outlet velocity is reverse-directed: {static.velocity_m_s}"
        )

    tolerances = contract["acceptance_tolerances"]
    if abs(float(reconstruction.enthalpy_round_trip_residual_J_kg)) > float(
        tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
    ) or abs(float(reconstruction.entropy_round_trip_residual_J_kg_K)) > float(
        tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
    ):
        raise one_step.WeakCompressionOneStepStop(
            "interior stagnation-state round trip exceeds locked tolerance"
        )

    diagnostic.QUADRATURE_ORDER = horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))

    def evaluate(pressure_pa: float) -> dict[str, Any]:
        return one_step._full_wave_row(
            pressure_pa=float(pressure_pa),
            static=static,
            isentrope=isentrope,
            hook=hook,
            area_m2=hook.area_m2,
            allowed_phases=allowed_phases,
            velocity_tolerance=velocity_tolerance,
            state_id=state_id,
        )

    root_pressure = float(increment_1_root["pressure_pa"])
    raw_root = evaluate(root_pressure)
    if not bool(raw_root.get("evaluation_succeeded")):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state Weak Compression root evaluation failed: "
            f"{raw_root.get('formal_outcome')} {raw_root.get('formal_message')}"
        )
    if not bool(raw_root.get("local_candidate_admissible")):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state Weak Compression root is inadmissible"
        )
    if not float(raw_root["pressure_pa"]) > back_pressure:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root pressure is not above back pressure"
        )
    if not float(raw_root["stagnation_pressure_pa"]) > back_pressure:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root stagnation pressure is not above back pressure"
        )

    completed = horizon._complete_root_row_dynamic_v4(
        root=raw_root,
        evaluate=evaluate,
        adapter=hook.adapter,
        area_m2=hook.area_m2,
        quadrature_order=horizon.ROOT_QUADRATURE_ORDER,
    )
    root = dict(raw_root)
    root.update(completed)
    root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    root_chi = float(root_offset / denominator)
    root.update(
        {
            "branch_classification": "WEAK_COMPRESSION",
            "p_P_minus_p_i_pa": root_offset,
            "chi": root_chi,
            "chi_max": short_run.CHI_MAX,
            "increment_1_bisection_iterations": int(
                increment_1_root["bisection_iterations"]
            ),
        }
    )

    if not root_offset > 0.0:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root is not above the interior pressure"
        )
    if not 0.0 < root_chi <= short_run.CHI_MAX:
        raise one_step.WeakCompressionOneStepStop(
            f"candidate-state root chi is outside scope: {root_chi}"
        )
    if abs(float(root["root_mass_residual_kg_s"])) > float(
        robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
    ):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root mass residual exceeds retained tolerance"
        )
    if float(root["local_residual_slope_kg_s_Pa"]) >= 0.0:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root local residual slope is not negative"
        )
    if float(root["velocity_m_s"]) < -velocity_tolerance:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root velocity is reverse-directed"
        )
    if not 0.0 <= float(root["mach"]) < 1.0:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root is outside the subsonic branch"
        )
    if normalize_phase(str(root["phase"])) not in allowed_phases:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root phase is outside the allowed liquid scope"
        )
    if not bool(root["stagnation_enthalpy_round_trip_passed"]):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root stagnation-enthalpy round trip failed"
        )
    if not bool(root["energy_mass_consistency_passed"]):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root energy/mass decomposition failed"
        )
    if not bool(root["energy_port_closure_passed"]):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root energy-port closure failed"
        )
    if abs(float(root["momentum_ledger_residual_N"])) > float(
        robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
    ):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state root restriction-reaction ledger failed"
        )

    mass_rate = float(root["pipe_mass_rate_kg_s"])
    velocity = float(root["velocity_m_s"])
    pressure = float(root["pressure_pa"])
    h0 = float(root["h0_J_kg"])
    flux = np.asarray(
        [
            mass_rate / hook.area_m2,
            (mass_rate * velocity + pressure * hook.area_m2) / hook.area_m2,
            mass_rate * h0 / hook.area_m2,
            0.0,
        ],
        dtype=float,
    )
    if not np.all(np.isfinite(flux)):
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state Weak Compression pipe-side flux is nonfinite"
        )

    successful_rows = [
        row
        for row in increment_1_scan_rows
        if bool(row.get("evaluation_succeeded"))
    ]
    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in successful_rows
    ]
    positive_residual_monotone = bool(
        len(residuals) >= 2
        and all(
            residuals[index + 1] <= residuals[index]
            for index in range(len(residuals) - 1)
        )
    )
    guard_rows = [
        row
        for row in increment_1_scan_rows
        if bool(row.get("expected_leading_b1_guard"))
    ]
    if not guard_rows or len(successful_rows) < 2:
        raise one_step.WeakCompressionOneStepStop(
            "candidate-state scan does not retain the fixed Guard-to-success topology"
        )
    return {
        "solver_time_s": float(solver_time_s),
        "interior_pressure_pa": float(static.pressure_pa),
        "interior_temperature_K": float(static.temperature_K),
        "interior_density_kg_m3": float(static.density_kg_m3),
        "interior_velocity_m_s": float(static.velocity_m_s),
        "interior_sound_speed_m_s": float(static.sound_speed_m_s),
        "interior_mach": float(static.velocity_m_s / static.sound_speed_m_s),
        "interior_entropy_J_kg_K": float(static.entropy_J_kg_K),
        "interior_phase": static.phase,
        "interior_h0_round_trip_residual_J_kg": float(
            reconstruction.enthalpy_round_trip_residual_J_kg
        ),
        "interior_s0_round_trip_residual_J_kg_K": float(
            reconstruction.entropy_round_trip_residual_J_kg_K
        ),
        "connected_scan_base_node_count": len(increment_1_scan_rows),
        "connected_scan_requested_nodes": len(increment_1_scan_rows),
        "connected_scan_admissible_subsonic_nodes": len(successful_rows),
        "connected_scan_lowest_pressure_pa": float(static.pressure_pa),
        "connected_scan_stop_reason": (
            "endpoint B1 Guard retained; candidate-state scan used"
        ),
        "connected_scan_residual_monotone": positive_residual_monotone,
        "connected_scan_sign_change_count": 1,
        "root": root,
        "flux": flux,
        "allowed_phases": allowed_phases,
        "velocity_tolerance_m_s": velocity_tolerance,
        "branch_classification": "WEAK_COMPRESSION",
        "root_chi": root_chi,
        "positive_scan_sign_change_count": 1,
        "positive_pressure_continuation_flux_applied": True,
        "finite_compression_branch_approved": False,
        "back_pressure_crossing_correction_applied": True,
        "stagnation_pressure_crossing_correction_applied": True,
        "endpoint_guard_bypassed_for_classification": True,
        "endpoint_guard_formal_outcome": EXPECTED_ENDPOINT_GUARD,
        "rarefaction_domain_available": False,
        "rarefaction_domain_reason": (
            "STATIC_AND_STAGNATION_PRESSURE_NOT_ABOVE_BACK"
        ),
        "interior_static_pressure_minus_back_pa": float(
            static.pressure_pa - back_pressure
        ),
        "interior_stagnation_pressure_minus_back_pa": float(
            reconstruction.stagnation_pressure_pa - back_pressure
        ),
        "root_static_pressure_minus_back_pa": float(
            root["pressure_pa"] - back_pressure
        ),
        "root_stagnation_pressure_minus_back_pa": float(
            root["stagnation_pressure_pa"] - back_pressure
        ),
        "positive_scan_guard_node_count": len(guard_rows),
        "positive_scan_first_success_offset_pa": float(
            successful_rows[0]["pressure_offset_pa"]
        ),
    }


def _candidate_state_solve_three_branch_boundary(
    *,
    hook: Any,
    U: np.ndarray,
    solver_time_s: float,
) -> dict[str, Any]:
    details = short_run._classification_diagnostics(
        hook=hook,
        U=U,
        solver_time_s=solver_time_s,
    )
    endpoint = dict(details["endpoint"])
    if bool(endpoint.get("evaluation_succeeded")):
        context = increment_4b._corrected_solve_three_branch_boundary(
            hook=hook,
            U=U,
            solver_time_s=solver_time_s,
        )
        context.setdefault("stagnation_pressure_crossing_correction_applied", False)
        context.setdefault("endpoint_guard_bypassed_for_classification", False)
        context.setdefault("endpoint_guard_formal_outcome", None)
        context.setdefault("endpoint_residual_available", True)
        context.setdefault("endpoint_residual_definition", "standard_B1_compatibility")
        context.setdefault("positive_scan_guard_node_count", 0)
        context.setdefault("positive_scan_first_success_offset_pa", None)
        context.setdefault("root_stagnation_pressure_minus_back_pa", float(
            context["root"]["stagnation_pressure_pa"]
            - float(context["back_pressure_pa"])
            if "back_pressure_pa" in context
            else context["root"]["stagnation_pressure_pa"]
            - float(hook.adapter.back_pressure_pa)
        ))
        return context

    reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    back_pressure = float(hook.adapter.back_pressure_pa)
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(hook.contract, hook.state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        hook.contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    if endpoint.get("formal_outcome") != EXPECTED_ENDPOINT_GUARD:
        raise CandidateStateContinuationStop(
            "UNEXPECTED_ENDPOINT_OUTCOME",
            "endpoint failure is not the retained B1 reverse-pressure Guard",
            details,
        )
    if not float(static.pressure_pa) <= back_pressure:
        raise CandidateStateContinuationStop(
            "ENDPOINT_GUARD_TOPOLOGY_MISMATCH",
            "endpoint Guard occurred while static pressure remained above back",
            details,
        )
    if not float(reconstruction.stagnation_pressure_pa) <= back_pressure:
        raise CandidateStateContinuationStop(
            "ENDPOINT_GUARD_TOPOLOGY_MISMATCH",
            "endpoint Guard occurred while stagnation pressure remained above back",
            details,
        )
    if float(static.velocity_m_s) < -velocity_tolerance:
        raise CandidateStateContinuationStop(
            "REVERSE_VELOCITY",
            "interior outlet velocity is reverse-directed",
            details,
        )
    if not 0.0 <= float(static.velocity_m_s / static.sound_speed_m_s) < 1.0:
        raise CandidateStateContinuationStop(
            "SUBSONIC_SCOPE_DEPARTURE",
            "interior outlet state is outside the subsonic branch",
            details,
        )
    if normalize_phase(str(static.phase)) not in allowed_phases:
        raise CandidateStateContinuationStop(
            "PHASE_SCOPE_DEPARTURE",
            "interior outlet phase is outside the retained liquid scope",
            details,
        )

    connected = dict(details["connected_rarefaction"])
    connected_stop = str(connected.get("stop_reason") or "")
    rarefaction_domain_unavailable = bool(
        int(connected.get("requested_nodes") or 0) == 0
        and int(connected.get("admissible_subsonic_nodes") or 0) == 0
        and int(connected.get("sign_change_count") or 0) == 0
        and "outlet pressure is not above retained back pressure"
        in connected_stop
    )
    if not rarefaction_domain_unavailable:
        raise CandidateStateContinuationStop(
            "RAREFACTION_DOMAIN_CLASSIFICATION_FAILURE",
            "connected rarefaction domain did not match the fixed unavailable topology",
            details,
        )
    if int(details["rarefaction_side_local_sign_change_count"]) != 0:
        raise CandidateStateContinuationStop(
            "RAREFACTION_ROOT_PRESENT",
            "a local rarefaction-side root exists in the candidate-state topology",
            details,
        )

    try:
        positive = increment_4c._permissive_positive_pressure_scan(
            hook=hook,
            U=U,
        )
    except Exception as exc:
        raise CandidateStateContinuationStop(
            "UNEXPECTED_POSITIVE_SCAN_FAILURE",
            f"candidate-state positive scan failed: {type(exc).__name__}: {exc}",
            details,
        ) from exc
    positive_count = int(positive["sign_change_count"])
    if positive_count > 1:
        raise CandidateStateContinuationStop(
            "MULTIPLE_LOCAL_ROOTS",
            "multiple positive-pressure roots were observed",
            {**details, "positive_scan": positive},
        )
    if positive_count == 0:
        if float(positive["scope_limit_residual_kg_s"]) > 0.0:
            raise CandidateStateContinuationStop(
                "FINITE_COMPRESSION_MODEL_REQUIRED",
                "positive residual remained positive through the fixed chi scope",
                {**details, "positive_scan": positive},
            )
        raise CandidateStateContinuationStop(
            "NO_UNIQUE_WEAK_COMPRESSION_ROOT",
            "no in-scope candidate-state positive root was found",
            {**details, "positive_scan": positive},
        )

    context = short_run._solve_weak_compression(
        hook=hook,
        U=U,
        solver_time_s=solver_time_s,
        positive=positive,
    )
    branch = "WEAK_COMPRESSION"
    if short_run._clear_branch_chatter(hook.accepted_branch_history, branch):
        raise CandidateStateContinuationStop(
            "CLEAR_BRANCH_CHATTER",
            "candidate branch forms the fixed five-point chatter pattern",
            details,
        )

    root = context["root"]
    root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    root_chi = float(root_offset / denominator)
    if not 0.0 < root_chi <= short_run.CHI_MAX:
        raise CandidateStateContinuationStop(
            "FINITE_COMPRESSION_MODEL_REQUIRED",
            f"candidate-state root chi is outside scope: {root_chi}",
            details,
        )
    if not float(root["pressure_pa"]) > back_pressure:
        raise CandidateStateContinuationStop(
            "ROOT_PRESSURE_NOT_ABOVE_BACK",
            "candidate-state root pressure is not above back pressure",
            details,
        )
    if not float(root["stagnation_pressure_pa"]) > back_pressure:
        raise CandidateStateContinuationStop(
            "ROOT_STAGNATION_PRESSURE_NOT_ABOVE_BACK",
            "candidate-state root stagnation pressure is not above back pressure",
            details,
        )

    endpoint_pipe_mass_rate = float(
        static.density_kg_m3 * static.velocity_m_s * hook.area_m2
    )
    context.update(
        {
            "branch_classification": branch,
            "endpoint_residual_kg_s": endpoint_pipe_mass_rate,
            "endpoint_residual_available": False,
            "endpoint_residual_definition": (
                "pipe_mass_rate_with_atomic_B1_Guard_zero_transfer_diagnostic_only"
            ),
            "endpoint_formal_outcome": endpoint.get("formal_outcome"),
            "endpoint_formal_message": endpoint.get("formal_message"),
            "endpoint_within_locked_root_mass_tolerance": False,
            "endpoint_admissible": False,
            "endpoint_root_closure_passed": False,
            "retained_root_mass_tolerance_kg_s": float(
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
            "rarefaction_side_local_sign_change_count": 0,
            "connected_rarefaction_sign_change_count": 0,
            "connected_rarefaction_residual_monotone": False,
            "connected_rarefaction_stop_reason": connected.get("stop_reason"),
            "positive_scan_sign_change_count": 1,
            "positive_scan_rows": list(positive["rows"]),
            "positive_scan_residual_monotone_nonincreasing": bool(
                positive["residual_monotone_nonincreasing"]
            ),
            "positive_scan_delta_p_max_pa": float(positive["delta_p_max_pa"]),
            "local_scan_rows": list(details["local_scan_rows"]),
            "p_P_minus_p_i_pa": root_offset,
            "root_chi": root_chi,
            "accepted_branch_history_before": list(hook.accepted_branch_history),
            "clear_branch_chatter_detected": False,
            "positive_pressure_continuation_flux_applied": True,
            "finite_compression_branch_approved": False,
            "back_pressure_crossing_correction_applied": True,
            "stagnation_pressure_crossing_correction_applied": True,
            "endpoint_guard_bypassed_for_classification": True,
            "endpoint_guard_formal_outcome": EXPECTED_ENDPOINT_GUARD,
            "rarefaction_domain_available": False,
            "rarefaction_domain_reason": (
                "STATIC_AND_STAGNATION_PRESSURE_NOT_ABOVE_BACK"
            ),
            "interior_static_pressure_minus_back_pa": float(
                static.pressure_pa - back_pressure
            ),
            "interior_stagnation_pressure_minus_back_pa": float(
                reconstruction.stagnation_pressure_pa - back_pressure
            ),
            "root_static_pressure_minus_back_pa": float(
                root["pressure_pa"] - back_pressure
            ),
            "root_stagnation_pressure_minus_back_pa": float(
                root["stagnation_pressure_pa"] - back_pressure
            ),
            "positive_scan_guard_node_count": int(
                positive["guard_node_count"]
            ),
            "positive_scan_first_success_offset_pa": float(
                positive["first_success_offset_pa"]
            ),
        }
    )
    return context


def _candidate_state_root_evidence_row(
    *,
    context: dict[str, Any],
    requested_solver_step: int,
) -> dict[str, Any]:
    row = increment_4b._corrected_root_evidence_row(
        context=context,
        requested_solver_step=requested_solver_step,
    )
    row.update(
        {
            "stagnation_pressure_crossing_correction_applied": bool(
                context.get("stagnation_pressure_crossing_correction_applied", False)
            ),
            "endpoint_guard_bypassed_for_classification": bool(
                context.get("endpoint_guard_bypassed_for_classification", False)
            ),
            "endpoint_guard_formal_outcome": context.get(
                "endpoint_guard_formal_outcome"
            ),
            "endpoint_formal_outcome": context.get("endpoint_formal_outcome"),
            "endpoint_formal_message": context.get("endpoint_formal_message"),
            "endpoint_residual_available": bool(
                context.get("endpoint_residual_available", True)
            ),
            "endpoint_residual_definition": context.get(
                "endpoint_residual_definition",
                "standard_B1_compatibility",
            ),
            "positive_scan_guard_node_count": int(
                context.get("positive_scan_guard_node_count", 0)
            ),
            "positive_scan_first_success_offset_pa": context.get(
                "positive_scan_first_success_offset_pa"
            ),
            "root_stagnation_pressure_minus_back_pa": float(
                context.get(
                    "root_stagnation_pressure_minus_back_pa",
                    context["root"]["stagnation_pressure_pa"]
                    - float(context.get("back_pressure_pa", 0.0)),
                )
            ),
        }
    )
    return row


def _compare_pre_correction_steps(
    *,
    failed_artifact_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    previous = [
        row
        for row in _read_csv(
            failed_artifact_dir / "full_horizon_continuation_steps.csv"
        )
        if row.get("accepted_step") == "True"
    ]
    current = [
        row
        for row in _read_csv(
            output_dir / "full_horizon_continuation_steps.csv"
        )
        if row.get("accepted_step") == "True"
    ]
    if len(previous) != 78 or len(current) < 78:
        return {
            "passed": False,
            "previous_accepted_rows": len(previous),
            "current_accepted_rows": len(current),
            "mismatches": ["accepted row count mismatch"],
        }
    keys = (
        "requested_step",
        "accepted_step",
        "solver_step_count",
        "time_before_s",
        "time_after_s",
        "accepted_dt_s",
        "branch_classification",
        "interior_pressure_before_root_pa",
        "root_pressure_pa",
        "root_mass_residual_kg_s",
        "p_P_minus_p_i_pa",
        "root_chi",
        "outlet_pressure_after_step_pa",
        "outlet_velocity_after_step_m_s",
        "outlet_phase_after_step",
        "step_mass_residual_kg",
        "step_momentum_residual_kg_m_s",
        "step_energy_residual_J",
        "cumulative_mass_residual_kg",
        "cumulative_momentum_residual_kg_m_s",
        "cumulative_energy_residual_J",
        "step_passed",
        "increment_4_per_step_gate_passed",
    )
    mismatches: list[str] = []
    for index, (old, new) in enumerate(zip(previous, current[:78], strict=True)):
        for key in keys:
            if old.get(key) != new.get(key):
                mismatches.append(
                    f"row {index} step {old.get('solver_step_count')} key {key}: "
                    f"old={old.get(key)!r} new={new.get(key)!r}"
                )
                if len(mismatches) >= 20:
                    break
        if len(mismatches) >= 20:
            break
    return {
        "passed": not mismatches,
        "previous_accepted_rows": len(previous),
        "current_accepted_rows": len(current),
        "compared_rows": 78,
        "compared_keys": list(keys),
        "mismatches": mismatches,
    }


def _postprocess_output(
    *,
    output_dir: Path,
    increment_4c_summary: dict[str, Any],
    failed_increment_4b_summary: dict[str, Any],
    failed_increment_4b_artifact_dir: Path,
) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    roots = _read_csv(output_dir / "full_horizon_continuation_roots.csv")
    corrected = [
        row
        for row in roots
        if row.get("stagnation_pressure_crossing_correction_applied") == "True"
    ]
    reproduction = _compare_pre_correction_steps(
        failed_artifact_dir=failed_increment_4b_artifact_dir,
        output_dir=output_dir,
    )
    first_correction_step = (
        min(int(row["requested_solver_step"]) for row in corrected)
        if corrected
        else None
    )
    correction_gate = bool(
        corrected
        and first_correction_step == FIRST_CANDIDATE_STATE_CORRECTION_STEP
        and all(
            row["endpoint_guard_formal_outcome"] == EXPECTED_ENDPOINT_GUARD
            for row in corrected
        )
        and all(
            row["endpoint_guard_bypassed_for_classification"] == "True"
            for row in corrected
        )
        and all(int(row["positive_scan_guard_node_count"]) > 0 for row in corrected)
        and all(
            float(row["interior_static_pressure_minus_back_pa"]) <= 0.0
            for row in corrected
        )
        and all(
            float(row["interior_stagnation_pressure_minus_back_pa"]) <= 0.0
            for row in corrected
        )
        and all(
            float(row["root_static_pressure_minus_back_pa"]) > 0.0
            for row in corrected
        )
        and all(
            float(row["root_stagnation_pressure_minus_back_pa"]) > 0.0
            for row in corrected
        )
    )
    gate_passed = bool(
        summary["working_vertical_slice_two_l_over_c0_passed"]
        and reproduction["passed"]
        and correction_gate
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4d"
            ),
            "scope": "model_review_working_vertical_slice_candidate_state",
            "increment_4c_source_sha": INCREMENT_4C_SOURCE_SHA,
            "increment_4c_workflow_run": INCREMENT_4C_WORKFLOW_RUN,
            "increment_4c_job": INCREMENT_4C_JOB,
            "increment_4c_artifact": INCREMENT_4C_ARTIFACT,
            "increment_4c_artifact_sha256": INCREMENT_4C_ARTIFACT_SHA256,
            "increment_4c_outcome": increment_4c_summary["outcome"],
            "increment_4c_authority_verified": True,
            "failed_increment_4b_source_sha": FAILED_INCREMENT_4B_SOURCE_SHA,
            "failed_increment_4b_workflow_run": FAILED_INCREMENT_4B_WORKFLOW_RUN,
            "failed_increment_4b_job": FAILED_INCREMENT_4B_JOB,
            "failed_increment_4b_artifact": FAILED_INCREMENT_4B_ARTIFACT,
            "failed_increment_4b_artifact_sha256": (
                FAILED_INCREMENT_4B_ARTIFACT_SHA256
            ),
            "failed_increment_4b_authority_verified": True,
            "pre_candidate_state_reproduction": reproduction,
            "pre_candidate_state_reproduction_passed": bool(
                reproduction["passed"]
            ),
            "candidate_state_correction_count": len(corrected),
            "first_candidate_state_correction_step": first_correction_step,
            "maximum_candidate_state_guard_node_count": (
                max(int(row["positive_scan_guard_node_count"]) for row in corrected)
                if corrected
                else None
            ),
            "minimum_candidate_state_static_pressure_margin_pa": (
                min(
                    float(row["interior_static_pressure_minus_back_pa"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "minimum_candidate_state_stagnation_pressure_margin_pa": (
                min(
                    float(row["interior_stagnation_pressure_minus_back_pa"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "minimum_candidate_root_static_pressure_margin_pa": (
                min(
                    float(row["root_static_pressure_minus_back_pa"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "minimum_candidate_root_stagnation_pressure_margin_pa": (
                min(
                    float(row["root_stagnation_pressure_minus_back_pa"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "candidate_state_correction_gate_passed": correction_gate,
            "outcome": OUTCOME if gate_passed else "INCREMENT_4D_STOPPED",
            "increment_4d_working_slice_gate_passed": gate_passed,
            "finite_compression_branch_approved": False,
            "full_two_l_over_c0_passed": False,
            "formal_state_promoted": False,
            "u3_b2_finite_pipe_execution_complete": False,
            "single_phase_finite_pipe_coupling_verified": False,
            "u3_b2_verification_benchmark_accepted": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    authority = {
        "increment_4c": {
            "source_sha": INCREMENT_4C_SOURCE_SHA,
            "workflow_run": INCREMENT_4C_WORKFLOW_RUN,
            "job": INCREMENT_4C_JOB,
            "artifact": INCREMENT_4C_ARTIFACT,
            "artifact_sha256": INCREMENT_4C_ARTIFACT_SHA256,
            "outcome": increment_4c_summary["outcome"],
            "verified": True,
        },
        "failed_increment_4b": {
            "source_sha": FAILED_INCREMENT_4B_SOURCE_SHA,
            "workflow_run": FAILED_INCREMENT_4B_WORKFLOW_RUN,
            "job": FAILED_INCREMENT_4B_JOB,
            "artifact": FAILED_INCREMENT_4B_ARTIFACT,
            "artifact_sha256": FAILED_INCREMENT_4B_ARTIFACT_SHA256,
            "outcome": failed_increment_4b_summary["outcome"],
            "verified": True,
        },
    }
    (output_dir / "increment_4d_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pre_candidate_state_reproduction.json").write_text(
        json.dumps(reproduction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Increment 4D candidate-state correction\n\n"
        + "The Increment 4C authority was verified. The first 78 continuation "
        + "steps through accepted step 447 were compared with the prior failed "
        + "Increment 4B evidence. Endpoint B1 Guard states were retained as "
        + "failed scan nodes; only later candidate boundary states that "
        + "individually passed the unchanged B1 component and all root/ledger "
        + "checks were permitted to construct a flux. Formal project states "
        + "remain unchanged.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    names = (
        "full_horizon_continuation_steps.csv",
        "full_horizon_continuation_roots.csv",
        "local_wave_scans.csv",
        "positive_pressure_scans.csv",
        "branch_transitions.csv",
        "probe_series.csv",
        "full_horizon_states.npz",
        "parent_verification.json",
        "increment_4d_authority.json",
        "pre_candidate_state_reproduction.json",
        "summary.json",
        "report.md",
    )
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--increment-4c-artifact-dir", type=Path, required=True)
    parser.add_argument("--increment-4c-artifact-digest", required=True)
    parser.add_argument(
        "--failed-increment-4b-artifact-dir",
        type=Path,
        required=True,
    )
    parser.add_argument("--failed-increment-4b-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    increment_4c_summary = _verify_increment_4c_artifact(
        args.increment_4c_artifact_dir,
        artifact_digest=args.increment_4c_artifact_digest,
    )
    failed_increment_4b_summary = _verify_failed_increment_4b_artifact(
        args.failed_increment_4b_artifact_dir,
        artifact_digest=args.failed_increment_4b_artifact_digest,
    )

    short_run._build_weak_compression_context = (
        _candidate_state_build_weak_compression_context
    )
    short_run._solve_three_branch_boundary = (
        _candidate_state_solve_three_branch_boundary
    )
    short_run._root_evidence_row = _candidate_state_root_evidence_row
    full_horizon.OUTCOME = OUTCOME

    original_argv = sys.argv
    try:
        sys.argv = [
            original_argv[0],
            "--contract",
            str(args.contract),
            "--b1-contract",
            str(args.b1_contract),
            "--model-review-spec",
            str(args.model_review_spec),
            "--parent-artifact-dir",
            str(args.parent_artifact_dir),
            "--parent-artifact-digest",
            args.parent_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        full_horizon.main()
    finally:
        sys.argv = original_argv

    summary = _postprocess_output(
        output_dir=args.output_dir,
        increment_4c_summary=increment_4c_summary,
        failed_increment_4b_summary=failed_increment_4b_summary,
        failed_increment_4b_artifact_dir=args.failed_increment_4b_artifact_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_4d_working_slice_gate_passed"]:
        raise SystemExit("Increment 4D candidate-state continuation did not pass")


if __name__ == "__main__":
    main()
