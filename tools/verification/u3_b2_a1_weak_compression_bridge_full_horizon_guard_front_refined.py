from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_b1_guard_front_root_diagnostic as increment_4e_base
import u3_b2_a1_weak_compression_bridge_full_horizon as full_horizon
import u3_b2_a1_weak_compression_bridge_full_horizon_candidate_state as increment_4d
import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import normalize_phase


INCREMENT_4E_SOURCE_SHA = "d88f9c979c594d0db74eee25ed5769e54d04821f"
INCREMENT_4E_WORKFLOW_RUN = 31618287187
INCREMENT_4E_JOB = 94186438807
INCREMENT_4E_ARTIFACT = 9150166208
INCREMENT_4E_ARTIFACT_SHA256 = (
    "a1bfbee4699cca03b0ddf50c1cf11f4fcdbc9cf066d5d4fbdffd167fd73750f8"
)
INCREMENT_4E_OUTCOME = "B1_GUARD_FRONT_REFINED_POSITIVE_ROOT_SUPPORTED"
FAILED_INCREMENT_4D_SOURCE_SHA = "cb56cfa0f856dc8f1ebe1463eeb80f2a269aa2a8"
FAILED_INCREMENT_4D_WORKFLOW_RUN = 31616654684
FAILED_INCREMENT_4D_JOB = 94181021964
FAILED_INCREMENT_4D_ARTIFACT = 9149565073
FAILED_INCREMENT_4D_ARTIFACT_SHA256 = (
    "a24c491035bbe296b9ad2cc128fc98302025cc90a03f1bda190ee4d9cb5dbd0c"
)
FIRST_GUARD_FRONT_REFINEMENT_STEP = 452
GUARD_FRONT_ITERATIONS = 32
REVERSE_PRESSURE_OUTCOME = "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED"
NONPOSITIVE_HEAD_OUTCOME = "NONPOSITIVE_KINETIC_ENERGY_HEAD"
UNAVAILABLE_OUTCOMES = {
    REVERSE_PRESSURE_OUTCOME,
    NONPOSITIVE_HEAD_OUTCOME,
}
OUTCOME = "WEAK_COMPRESSION_INCREMENT_4F_FULL_HORIZON_WORKING_SLICE_PASS"
robustness = robustness_v4.robustness


class GuardFrontContinuationStop(short_run.WeakCompressionShortRunStop):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_increment_4e_artifact(
    artifact_dir: Path,
    *,
    artifact_digest: str,
) -> dict[str, Any]:
    if artifact_digest != INCREMENT_4E_ARTIFACT_SHA256:
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            "corrected Increment 4E GitHub artifact digest mismatch",
        )
    required = {
        "step451_local_wave_scans.csv",
        "step451_fixed_positive_pressure_scans.csv",
        "step451_guard_front_bisection.csv",
        "step451_refined_success_root.csv",
        "step451_state_identity.npz",
        "correction_authority.json",
        "summary.json",
        "report.md",
        "artifact_sha256.txt",
    }
    actual = {path.name for path in artifact_dir.iterdir() if path.is_file()}
    if actual != required:
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            f"corrected Increment 4E file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (artifact_dir / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != required - {"artifact_sha256.txt"}:
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            "corrected Increment 4E internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(artifact_dir / name) != digest:
            raise GuardFrontContinuationStop(
                "INCREMENT_4E_AUTHORITY_MISMATCH",
                f"corrected Increment 4E internal SHA256 mismatch for {name}",
            )
    summary = json.loads(
        (artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    if summary.get("source_git_sha") != INCREMENT_4E_SOURCE_SHA:
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            "corrected Increment 4E source SHA mismatch",
        )
    if summary.get("outcome") != INCREMENT_4E_OUTCOME:
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            "corrected Increment 4E outcome mismatch",
        )
    if not bool(summary.get("increment_4e_continuation_supported")) or not bool(
        summary.get("increment_4e_rerun_gate_passed")
    ):
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            "corrected Increment 4E continuation or rerun gate mismatch",
        )
    if int(summary.get("solver_step_loaded", -1)) != 451:
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            "corrected Increment 4E did not diagnose accepted step 451",
        )
    if bool(summary.get("fvm_step_452_attempted")):
        raise GuardFrontContinuationStop(
            "INCREMENT_4E_AUTHORITY_MISMATCH",
            "corrected Increment 4E unexpectedly attempted step 452",
        )
    return summary


def _verify_failed_increment_4d_artifact(
    artifact_dir: Path,
    *,
    artifact_digest: str,
) -> dict[str, Any]:
    try:
        summary, _, _ = increment_4e_base._verify_parent_artifact(
            artifact_dir,
            parent_artifact_digest=artifact_digest,
        )
    except Exception as exc:
        raise GuardFrontContinuationStop(
            "FAILED_INCREMENT_4D_AUTHORITY_MISMATCH",
            f"failed Increment 4D authority verification failed: {exc}",
        ) from exc
    return summary


def _is_unavailable(row: dict[str, Any]) -> bool:
    return bool(
        not row.get("evaluation_succeeded")
        and row.get("formal_outcome") in UNAVAILABLE_OUTCOMES
    )


def _require_success(row: dict[str, Any], label: str) -> None:
    if not bool(row.get("evaluation_succeeded")):
        raise GuardFrontContinuationStop(
            "GUARD_FRONT_BISECTION_FAILURE",
            f"{label} did not succeed: "
            f"{row.get('formal_outcome')} {row.get('formal_message')}",
        )
    if not bool(row.get("local_candidate_admissible")):
        raise GuardFrontContinuationStop(
            "GUARD_FRONT_BISECTION_FAILURE",
            f"{label} is not locally admissible",
        )
    residual = row.get("compatibility_residual_kg_s")
    if residual is None or not np.isfinite(float(residual)):
        raise GuardFrontContinuationStop(
            "GUARD_FRONT_BISECTION_FAILURE",
            f"{label} does not have a finite compatibility residual",
        )


def _annotate_fixed_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item.update(
        {
            "scan_node_role": "FIXED_POSITIVE_SCAN",
            "guard_front_refinement_applied": False,
            "guard_front_iteration": None,
            "guard_front_midpoint_classification": None,
            "guard_front_lower_unavailable_offset_after_pa": None,
            "guard_front_upper_success_offset_after_pa": None,
            "guard_front_bracket_width_after_pa": None,
        }
    )
    return item


def _guard_front_positive_scan(
    *,
    hook: Any,
    U: np.ndarray,
) -> dict[str, Any]:
    reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(
            hook.contract,
            hook.state_id,
        )["allowed_normalized_phases"]
    }
    velocity_tolerance = float(
        hook.contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    short_run.diagnostic.QUADRATURE_ORDER = (
        short_run.horizon.ROOT_QUADRATURE_ORDER
    )
    isentrope = short_run.diagnostic.Isentrope(
        float(static.entropy_J_kg_K)
    )
    density = float(static.density_kg_m3)
    sound_speed = float(static.sound_speed_m_s)
    denominator = float(density * sound_speed**2)
    delta_p_max = float(denominator * short_run.CHI_MAX)
    offsets = short_run._positive_scan_offsets(delta_p_max)
    cache: dict[float, dict[str, Any]] = {}

    def evaluate_offset(offset_pa: float) -> dict[str, Any]:
        key = float(offset_pa)
        if key not in cache:
            candidate_pressure = float(static.pressure_pa + key)
            raw = short_run._full_wave_row(
                pressure_pa=candidate_pressure,
                static=static,
                isentrope=isentrope,
                hook=hook,
                area_m2=hook.area_m2,
                allowed_phases=allowed_phases,
                velocity_tolerance=velocity_tolerance,
                state_id=hook.state_id,
            )
            realized_offset = float(raw["pressure_offset_pa"])
            requested_chi = float(
                short_run.CHI_MAX
                if key == delta_p_max
                else key / denominator
            )
            realized_chi = float(realized_offset / denominator)
            item = dict(raw)
            item.update(
                {
                    "pressure_offset_pa": key,
                    "requested_pressure_offset_pa": key,
                    "realized_pressure_offset_pa": realized_offset,
                    "requested_pressure_pa": candidate_pressure,
                    "realized_pressure_pa": float(raw["pressure_pa"]),
                    "chi": requested_chi,
                    "requested_chi": requested_chi,
                    "realized_chi": realized_chi,
                    "chi_max": short_run.CHI_MAX,
                    "within_weak_compression_scope": bool(
                        key == 0.0 or 0.0 < key <= delta_p_max
                    ),
                    "expected_leading_b1_guard": _is_unavailable(raw),
                    "scan_coordinate_correction": (
                        "requested_scan_coordinate_authoritative_guard_front_refinement"
                    ),
                    "selected_sign_change_bracket_member": False,
                }
            )
            cache[key] = item
        return dict(cache[key])

    fixed_rows = [evaluate_offset(offset) for offset in offsets]
    unavailable_fixed: list[dict[str, Any]] = []
    successful_fixed: list[dict[str, Any]] = []
    success_seen = False
    for index, row in enumerate(fixed_rows):
        if not bool(row["within_weak_compression_scope"]):
            raise GuardFrontContinuationStop(
                "FIXED_SCAN_SCOPE_FAILURE",
                f"fixed positive scan node {index} exceeds the unchanged chi scope",
            )
        if bool(row.get("evaluation_succeeded")):
            success_seen = True
            _require_success(row, f"fixed positive scan node {index}")
            successful_fixed.append(row)
            continue
        if not _is_unavailable(row):
            raise GuardFrontContinuationStop(
                "UNAVAILABLE_FORMAL_OUTCOME_OUTSIDE_SCOPE",
                "unexpected fixed positive scan failure at node "
                f"{index}: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
            )
        if success_seen:
            raise GuardFrontContinuationStop(
                "SUCCESSFUL_NODE_FOLLOWED_BY_UNAVAILABLE_NODE",
                "an unavailable fixed scan node occurred after B1 success",
            )
        unavailable_fixed.append(row)

    if not successful_fixed:
        raise GuardFrontContinuationStop(
            "NO_SUCCESSFUL_POSITIVE_PRESSURE_DOMAIN",
            "the fixed positive scan never entered the B1-success domain",
        )
    fixed_evaluable = short_run._brackets(
        successful_fixed,
        admissible_only=False,
    )
    fixed_admissible = short_run._brackets(
        successful_fixed,
        admissible_only=True,
    )
    if len(fixed_evaluable) != len(fixed_admissible):
        raise GuardFrontContinuationStop(
            "ROOT_OR_ADMISSIBILITY_FAILURE",
            "a fixed successful-domain root bracket is inadmissible",
        )
    if len(fixed_admissible) > 1:
        raise GuardFrontContinuationStop(
            "MULTIPLE_ROOTS",
            "multiple fixed successful-domain root brackets were observed",
        )

    fixed_evidence = [_annotate_fixed_row(row) for row in fixed_rows]
    if len(fixed_admissible) == 1:
        selected = {
            float(fixed_admissible[0]["lower_offset_pa"]),
            float(fixed_admissible[0]["upper_offset_pa"]),
        }
        rows = [
            {
                **row,
                "selected_sign_change_bracket_member": bool(
                    float(row["pressure_offset_pa"]) in selected
                ),
            }
            for row in fixed_evidence
        ]
        residuals = [
            float(row["compatibility_residual_kg_s"])
            for row in successful_fixed
        ]
        return {
            "static": static,
            "rows": rows,
            "evaluate_offset": evaluate_offset,
            "evaluable_brackets": fixed_evaluable,
            "admissible_brackets": fixed_admissible,
            "sign_change_count": 1,
            "residual_monotone_nonincreasing": bool(
                len(residuals) >= 2
                and all(
                    residuals[index + 1] <= residuals[index]
                    for index in range(len(residuals) - 1)
                )
            ),
            "delta_p_max_pa": delta_p_max,
            "guard_node_count": len(unavailable_fixed),
            "first_success_offset_pa": float(
                successful_fixed[0]["pressure_offset_pa"]
            ),
            "first_success_stagnation_pressure_pa": float(
                successful_fixed[0]["stagnation_pressure_pa"]
            ),
            "scope_limit_residual_kg_s": float(residuals[-1]),
            "guard_front_refinement_applied": False,
            "guard_front_reverse_pressure_count": sum(
                row.get("formal_outcome") == REVERSE_PRESSURE_OUTCOME
                for row in unavailable_fixed
            ),
            "guard_front_nonpositive_head_count": sum(
                row.get("formal_outcome") == NONPOSITIVE_HEAD_OUTCOME
                for row in unavailable_fixed
            ),
            "guard_front_success_count": len(successful_fixed),
            "guard_front_initial_lower_offset_pa": None,
            "guard_front_initial_upper_offset_pa": None,
            "guard_front_final_lower_offset_pa": None,
            "guard_front_final_upper_offset_pa": None,
            "guard_front_final_width_pa": None,
            "guard_front_refined_success_residual_kg_s": None,
            "guard_front_refined_success_stagnation_margin_pa": None,
            "guard_front_stop_classification": None,
        }

    if not unavailable_fixed:
        scope_residual = float(
            successful_fixed[-1]["compatibility_residual_kg_s"]
        )
        stop_classification = (
            "FINITE_COMPRESSION_MODEL_REQUIRED"
            if scope_residual > robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            else "NO_UNIQUE_WEAK_COMPRESSION_ROOT"
        )
        return {
            "static": static,
            "rows": fixed_evidence,
            "evaluate_offset": evaluate_offset,
            "evaluable_brackets": [],
            "admissible_brackets": [],
            "sign_change_count": 0,
            "residual_monotone_nonincreasing": True,
            "delta_p_max_pa": delta_p_max,
            "guard_node_count": 0,
            "first_success_offset_pa": float(
                successful_fixed[0]["pressure_offset_pa"]
            ),
            "first_success_stagnation_pressure_pa": float(
                successful_fixed[0]["stagnation_pressure_pa"]
            ),
            "scope_limit_residual_kg_s": scope_residual,
            "guard_front_refinement_applied": False,
            "guard_front_reverse_pressure_count": 0,
            "guard_front_nonpositive_head_count": 0,
            "guard_front_success_count": len(successful_fixed),
            "guard_front_initial_lower_offset_pa": None,
            "guard_front_initial_upper_offset_pa": None,
            "guard_front_final_lower_offset_pa": None,
            "guard_front_final_upper_offset_pa": None,
            "guard_front_final_width_pa": None,
            "guard_front_refined_success_residual_kg_s": None,
            "guard_front_refined_success_stagnation_margin_pa": None,
            "guard_front_stop_classification": stop_classification,
        }

    lower_offset = float(unavailable_fixed[-1]["pressure_offset_pa"])
    upper_offset = float(successful_fixed[0]["pressure_offset_pa"])
    initial_lower = lower_offset
    initial_upper = upper_offset
    lower = evaluate_offset(lower_offset)
    upper = evaluate_offset(upper_offset)
    if not _is_unavailable(lower):
        raise GuardFrontContinuationStop(
            "GUARD_FRONT_BISECTION_FAILURE",
            "initial lower Guard-front endpoint is not B1-unavailable",
        )
    _require_success(upper, "initial upper Guard-front endpoint")
    bisection_evidence: list[dict[str, Any]] = []

    for iteration in range(1, GUARD_FRONT_ITERATIONS + 1):
        before_lower = lower_offset
        before_upper = upper_offset
        midpoint_offset = float(0.5 * (before_lower + before_upper))
        if not before_lower < midpoint_offset < before_upper:
            raise GuardFrontContinuationStop(
                "GUARD_FRONT_BISECTION_FAILURE",
                "Guard-front midpoint is not strictly inside the bracket",
            )
        midpoint = evaluate_offset(midpoint_offset)
        if _is_unavailable(midpoint):
            midpoint_classification = "B1_UNAVAILABLE"
            lower_offset = midpoint_offset
            lower = midpoint
        elif bool(midpoint.get("evaluation_succeeded")):
            _require_success(midpoint, f"Guard-front midpoint {iteration}")
            midpoint_classification = "B1_SUCCESS"
            upper_offset = midpoint_offset
            upper = midpoint
        else:
            raise GuardFrontContinuationStop(
                "UNAVAILABLE_FORMAL_OUTCOME_OUTSIDE_SCOPE",
                "unexpected Guard-front midpoint outcome at iteration "
                f"{iteration}: {midpoint.get('formal_outcome')} "
                f"{midpoint.get('formal_message')}",
            )
        evidence = dict(midpoint)
        evidence.update(
            {
                "scan_node_role": "GUARD_FRONT_BISECTION",
                "guard_front_refinement_applied": True,
                "guard_front_iteration": iteration,
                "guard_front_midpoint_classification": (
                    midpoint_classification
                ),
                "guard_front_lower_unavailable_offset_after_pa": lower_offset,
                "guard_front_upper_success_offset_after_pa": upper_offset,
                "guard_front_bracket_width_after_pa": float(
                    upper_offset - lower_offset
                ),
            }
        )
        bisection_evidence.append(evidence)

    if not _is_unavailable(lower):
        raise GuardFrontContinuationStop(
            "GUARD_FRONT_BISECTION_FAILURE",
            "final lower Guard-front endpoint is not B1-unavailable",
        )
    _require_success(upper, "refined first-success endpoint")

    all_rows = fixed_evidence + bisection_evidence
    all_rows = sorted(
        all_rows,
        key=lambda row: (
            float(row["pressure_offset_pa"]),
            str(row.get("scan_node_role")),
        ),
    )
    successful_rows = [
        row for row in all_rows if bool(row.get("evaluation_succeeded"))
    ]
    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in successful_rows
    ]
    monotone = bool(
        len(residuals) >= 2
        and all(
            residuals[index + 1] <= residuals[index]
            for index in range(len(residuals) - 1)
        )
    )
    if not monotone:
        raise GuardFrontContinuationStop(
            "SUCCESS_DOMAIN_NONMONOTONE",
            "successful-domain compatibility residual is not monotone",
        )
    evaluable = short_run._brackets(
        successful_rows,
        admissible_only=False,
    )
    admissible = short_run._brackets(
        successful_rows,
        admissible_only=True,
    )
    if len(evaluable) != len(admissible):
        raise GuardFrontContinuationStop(
            "ROOT_OR_ADMISSIBILITY_FAILURE",
            "a refined successful-domain root bracket is inadmissible",
        )
    if len(admissible) > 1:
        raise GuardFrontContinuationStop(
            "MULTIPLE_ROOTS",
            "multiple refined successful-domain roots were observed",
        )

    refined_residual = float(upper["compatibility_residual_kg_s"])
    scope_residual = float(
        successful_fixed[-1]["compatibility_residual_kg_s"]
    )
    stop_classification: str | None = None
    if len(admissible) == 0:
        if refined_residual < -robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S:
            stop_classification = "ROOT_LIES_INSIDE_B1_GUARD_DOMAIN"
        elif scope_residual > robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S:
            stop_classification = "FINITE_COMPRESSION_MODEL_REQUIRED"
        else:
            stop_classification = "NO_UNIQUE_WEAK_COMPRESSION_ROOT"

    selected_offsets: set[float] = set()
    if admissible:
        selected_offsets = {
            float(admissible[0]["lower_offset_pa"]),
            float(admissible[0]["upper_offset_pa"]),
        }
    all_rows = [
        {
            **row,
            "selected_sign_change_bracket_member": bool(
                float(row["pressure_offset_pa"]) in selected_offsets
            ),
        }
        for row in all_rows
    ]
    unavailable_rows = [row for row in all_rows if _is_unavailable(row)]
    first_success = successful_rows[0]
    return {
        "static": static,
        "rows": all_rows,
        "evaluate_offset": evaluate_offset,
        "evaluable_brackets": evaluable,
        "admissible_brackets": admissible,
        "sign_change_count": len(admissible),
        "residual_monotone_nonincreasing": monotone,
        "delta_p_max_pa": delta_p_max,
        "guard_node_count": len(unavailable_rows),
        "first_success_offset_pa": float(
            first_success["pressure_offset_pa"]
        ),
        "first_success_stagnation_pressure_pa": float(
            first_success["stagnation_pressure_pa"]
        ),
        "scope_limit_residual_kg_s": scope_residual,
        "guard_front_refinement_applied": True,
        "guard_front_reverse_pressure_count": sum(
            row.get("formal_outcome") == REVERSE_PRESSURE_OUTCOME
            for row in unavailable_rows
        ),
        "guard_front_nonpositive_head_count": sum(
            row.get("formal_outcome") == NONPOSITIVE_HEAD_OUTCOME
            for row in unavailable_rows
        ),
        "guard_front_success_count": len(successful_rows),
        "guard_front_initial_lower_offset_pa": initial_lower,
        "guard_front_initial_upper_offset_pa": initial_upper,
        "guard_front_final_lower_offset_pa": lower_offset,
        "guard_front_final_upper_offset_pa": upper_offset,
        "guard_front_final_width_pa": float(upper_offset - lower_offset),
        "guard_front_refined_success_residual_kg_s": refined_residual,
        "guard_front_refined_success_stagnation_margin_pa": float(
            upper["stagnation_pressure_pa"] - hook.adapter.back_pressure_pa
        ),
        "guard_front_stop_classification": stop_classification,
    }


def _guard_front_solve_three_branch_boundary(
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
        context = increment_4d._candidate_state_solve_three_branch_boundary(
            hook=hook,
            U=U,
            solver_time_s=solver_time_s,
        )
        context.setdefault("guard_front_refinement_applied", False)
        context.setdefault("guard_front_reverse_pressure_count", 0)
        context.setdefault("guard_front_nonpositive_head_count", 0)
        context.setdefault("guard_front_success_count", 0)
        context.setdefault("guard_front_initial_lower_offset_pa", None)
        context.setdefault("guard_front_initial_upper_offset_pa", None)
        context.setdefault("guard_front_final_lower_offset_pa", None)
        context.setdefault("guard_front_final_upper_offset_pa", None)
        context.setdefault("guard_front_final_width_pa", None)
        context.setdefault("guard_front_refined_success_residual_kg_s", None)
        context.setdefault(
            "guard_front_refined_success_stagnation_margin_pa",
            None,
        )
        context.setdefault("failed_b1_state_used_as_root_endpoint", False)
        context.setdefault("failed_b1_state_used_to_construct_flux", False)
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
    if endpoint.get("formal_outcome") != REVERSE_PRESSURE_OUTCOME:
        raise GuardFrontContinuationStop(
            "UNEXPECTED_ENDPOINT_OUTCOME",
            "endpoint failure is not the retained B1 reverse-pressure Guard",
            details,
        )
    if float(static.velocity_m_s) < -velocity_tolerance:
        raise GuardFrontContinuationStop(
            "REVERSE_VELOCITY",
            "interior outlet velocity is reverse-directed",
            details,
        )
    if not 0.0 <= float(static.velocity_m_s / static.sound_speed_m_s) < 1.0:
        raise GuardFrontContinuationStop(
            "SUBSONIC_SCOPE_DEPARTURE",
            "interior outlet state is outside the subsonic branch",
            details,
        )
    if normalize_phase(str(static.phase)) not in allowed_phases:
        raise GuardFrontContinuationStop(
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
        raise GuardFrontContinuationStop(
            "RAREFACTION_DOMAIN_CLASSIFICATION_FAILURE",
            "connected rarefaction domain did not match the fixed unavailable topology",
            details,
        )
    if int(details["rarefaction_side_local_sign_change_count"]) != 0:
        raise GuardFrontContinuationStop(
            "RAREFACTION_ROOT_PRESENT",
            "a local rarefaction-side root exists in the Guard-front topology",
            details,
        )

    try:
        positive = _guard_front_positive_scan(hook=hook, U=U)
    except GuardFrontContinuationStop:
        raise
    except Exception as exc:
        raise GuardFrontContinuationStop(
            "GUARD_FRONT_SCAN_FAILURE",
            f"Guard-front positive scan failed: {type(exc).__name__}: {exc}",
            details,
        ) from exc

    stop_classification = positive.get("guard_front_stop_classification")
    if stop_classification is not None:
        messages = {
            "ROOT_LIES_INSIDE_B1_GUARD_DOMAIN": (
                "refined first-success residual is negative beyond root tolerance"
            ),
            "FINITE_COMPRESSION_MODEL_REQUIRED": (
                "successful residual remains positive through the fixed chi scope"
            ),
            "NO_UNIQUE_WEAK_COMPRESSION_ROOT": (
                "no unique successful-domain Weak Compression root exists"
            ),
        }
        raise GuardFrontContinuationStop(
            str(stop_classification),
            messages.get(str(stop_classification), "Guard-front root unavailable"),
            {**details, "positive_scan": positive},
        )

    if int(positive["sign_change_count"]) != 1:
        raise GuardFrontContinuationStop(
            "NO_UNIQUE_WEAK_COMPRESSION_ROOT",
            "Guard-front scan did not retain exactly one successful-domain root",
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
        raise GuardFrontContinuationStop(
            "CLEAR_BRANCH_CHATTER",
            "candidate branch forms the fixed five-point chatter pattern",
            details,
        )

    root = context["root"]
    root_offset = float(root["pressure_pa"] - float(static.pressure_pa))
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    root_chi = float(root_offset / denominator)
    if not 0.0 < root_chi <= short_run.CHI_MAX:
        raise GuardFrontContinuationStop(
            "FINITE_COMPRESSION_MODEL_REQUIRED",
            f"Guard-front root chi is outside scope: {root_chi}",
            details,
        )
    if not float(root["pressure_pa"]) > back_pressure:
        raise GuardFrontContinuationStop(
            "ROOT_PRESSURE_NOT_ABOVE_BACK",
            "Guard-front root pressure is not above back pressure",
            details,
        )
    if not float(root["stagnation_pressure_pa"]) > back_pressure:
        raise GuardFrontContinuationStop(
            "ROOT_STAGNATION_PRESSURE_NOT_ABOVE_BACK",
            "Guard-front root stagnation pressure is not above back pressure",
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
            "endpoint_guard_formal_outcome": REVERSE_PRESSURE_OUTCOME,
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
            "guard_front_refinement_applied": bool(
                positive["guard_front_refinement_applied"]
            ),
            "guard_front_reverse_pressure_count": int(
                positive["guard_front_reverse_pressure_count"]
            ),
            "guard_front_nonpositive_head_count": int(
                positive["guard_front_nonpositive_head_count"]
            ),
            "guard_front_success_count": int(
                positive["guard_front_success_count"]
            ),
            "guard_front_initial_lower_offset_pa": positive[
                "guard_front_initial_lower_offset_pa"
            ],
            "guard_front_initial_upper_offset_pa": positive[
                "guard_front_initial_upper_offset_pa"
            ],
            "guard_front_final_lower_offset_pa": positive[
                "guard_front_final_lower_offset_pa"
            ],
            "guard_front_final_upper_offset_pa": positive[
                "guard_front_final_upper_offset_pa"
            ],
            "guard_front_final_width_pa": positive[
                "guard_front_final_width_pa"
            ],
            "guard_front_refined_success_residual_kg_s": positive[
                "guard_front_refined_success_residual_kg_s"
            ],
            "guard_front_refined_success_stagnation_margin_pa": positive[
                "guard_front_refined_success_stagnation_margin_pa"
            ],
            "failed_b1_state_used_as_root_endpoint": False,
            "failed_b1_state_used_to_construct_flux": False,
        }
    )
    return context


def _guard_front_root_evidence_row(
    *,
    context: dict[str, Any],
    requested_solver_step: int,
) -> dict[str, Any]:
    row = increment_4d._candidate_state_root_evidence_row(
        context=context,
        requested_solver_step=requested_solver_step,
    )
    row.update(
        {
            "guard_front_refinement_applied": bool(
                context.get("guard_front_refinement_applied", False)
            ),
            "guard_front_reverse_pressure_count": int(
                context.get("guard_front_reverse_pressure_count", 0)
            ),
            "guard_front_nonpositive_head_count": int(
                context.get("guard_front_nonpositive_head_count", 0)
            ),
            "guard_front_success_count": int(
                context.get("guard_front_success_count", 0)
            ),
            "guard_front_initial_lower_offset_pa": context.get(
                "guard_front_initial_lower_offset_pa"
            ),
            "guard_front_initial_upper_offset_pa": context.get(
                "guard_front_initial_upper_offset_pa"
            ),
            "guard_front_final_lower_offset_pa": context.get(
                "guard_front_final_lower_offset_pa"
            ),
            "guard_front_final_upper_offset_pa": context.get(
                "guard_front_final_upper_offset_pa"
            ),
            "guard_front_final_width_pa": context.get(
                "guard_front_final_width_pa"
            ),
            "guard_front_refined_success_residual_kg_s": context.get(
                "guard_front_refined_success_residual_kg_s"
            ),
            "guard_front_refined_success_stagnation_margin_pa": context.get(
                "guard_front_refined_success_stagnation_margin_pa"
            ),
            "failed_b1_state_used_as_root_endpoint": bool(
                context.get("failed_b1_state_used_as_root_endpoint", False)
            ),
            "failed_b1_state_used_to_construct_flux": bool(
                context.get("failed_b1_state_used_to_construct_flux", False)
            ),
        }
    )
    return row


def _compare_pre_refinement_steps(
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
    if len(previous) != 82 or len(current) < 82:
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
    for index, (old, new) in enumerate(zip(previous, current[:82], strict=True)):
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
        "compared_rows": 82,
        "compared_keys": list(keys),
        "mismatches": mismatches,
    }


def _postprocess_output(
    *,
    output_dir: Path,
    increment_4e_summary: dict[str, Any],
    failed_increment_4d_summary: dict[str, Any],
    failed_increment_4d_artifact_dir: Path,
) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    roots = _read_csv(output_dir / "full_horizon_continuation_roots.csv")
    refined = [
        row
        for row in roots
        if row.get("guard_front_refinement_applied") == "True"
    ]
    reproduction = _compare_pre_refinement_steps(
        failed_artifact_dir=failed_increment_4d_artifact_dir,
        output_dir=output_dir,
    )
    first_refinement_step = (
        min(int(row["requested_solver_step"]) for row in refined)
        if refined
        else None
    )
    refinement_gate = bool(
        refined
        and first_refinement_step == FIRST_GUARD_FRONT_REFINEMENT_STEP
        and all(int(row["guard_front_reverse_pressure_count"]) >= 0 for row in refined)
        and all(int(row["guard_front_nonpositive_head_count"]) > 0 for row in refined)
        and all(int(row["guard_front_success_count"]) > 0 for row in refined)
        and all(
            float(row["guard_front_final_lower_offset_pa"])
            < float(row["guard_front_final_upper_offset_pa"])
            for row in refined
        )
        and all(float(row["guard_front_final_width_pa"]) > 0.0 for row in refined)
        and all(
            float(row["guard_front_refined_success_residual_kg_s"])
            >= -robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            for row in refined
        )
        and all(
            float(row["guard_front_refined_success_stagnation_margin_pa"])
            > 0.0
            for row in refined
        )
        and all(row["failed_b1_state_used_as_root_endpoint"] == "False" for row in refined)
        and all(row["failed_b1_state_used_to_construct_flux"] == "False" for row in refined)
        and all(float(row["root_static_pressure_minus_back_pa"]) > 0.0 for row in refined)
        and all(
            float(row["root_stagnation_pressure_minus_back_pa"]) > 0.0
            for row in refined
        )
    )
    gate_passed = bool(
        summary["working_vertical_slice_two_l_over_c0_passed"]
        and reproduction["passed"]
        and refinement_gate
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4f"
            ),
            "scope": "model_review_working_vertical_slice_guard_front_refined",
            "increment_4e_source_sha": INCREMENT_4E_SOURCE_SHA,
            "increment_4e_workflow_run": INCREMENT_4E_WORKFLOW_RUN,
            "increment_4e_job": INCREMENT_4E_JOB,
            "increment_4e_artifact": INCREMENT_4E_ARTIFACT,
            "increment_4e_artifact_sha256": INCREMENT_4E_ARTIFACT_SHA256,
            "increment_4e_outcome": increment_4e_summary["outcome"],
            "increment_4e_authority_verified": True,
            "failed_increment_4d_source_sha": FAILED_INCREMENT_4D_SOURCE_SHA,
            "failed_increment_4d_workflow_run": FAILED_INCREMENT_4D_WORKFLOW_RUN,
            "failed_increment_4d_job": FAILED_INCREMENT_4D_JOB,
            "failed_increment_4d_artifact": FAILED_INCREMENT_4D_ARTIFACT,
            "failed_increment_4d_artifact_sha256": FAILED_INCREMENT_4D_ARTIFACT_SHA256,
            "failed_increment_4d_authority_verified": True,
            "pre_guard_front_reproduction": reproduction,
            "pre_guard_front_reproduction_passed": bool(reproduction["passed"]),
            "guard_front_refinement_count": len(refined),
            "first_guard_front_refinement_step": first_refinement_step,
            "maximum_guard_front_nonpositive_head_count": (
                max(int(row["guard_front_nonpositive_head_count"]) for row in refined)
                if refined
                else None
            ),
            "maximum_guard_front_success_count": (
                max(int(row["guard_front_success_count"]) for row in refined)
                if refined
                else None
            ),
            "maximum_guard_front_final_width_pa": (
                max(float(row["guard_front_final_width_pa"]) for row in refined)
                if refined
                else None
            ),
            "minimum_guard_front_refined_success_residual_kg_s": (
                min(
                    float(row["guard_front_refined_success_residual_kg_s"])
                    for row in refined
                )
                if refined
                else None
            ),
            "minimum_guard_front_refined_success_stagnation_margin_pa": (
                min(
                    float(row["guard_front_refined_success_stagnation_margin_pa"])
                    for row in refined
                )
                if refined
                else None
            ),
            "guard_front_refinement_gate_passed": refinement_gate,
            "outcome": OUTCOME if gate_passed else "INCREMENT_4F_STOPPED",
            "increment_4f_working_slice_gate_passed": gate_passed,
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
        "corrected_increment_4e": {
            "source_sha": INCREMENT_4E_SOURCE_SHA,
            "workflow_run": INCREMENT_4E_WORKFLOW_RUN,
            "job": INCREMENT_4E_JOB,
            "artifact": INCREMENT_4E_ARTIFACT,
            "artifact_sha256": INCREMENT_4E_ARTIFACT_SHA256,
            "outcome": increment_4e_summary["outcome"],
            "verified": True,
        },
        "failed_increment_4d": {
            "source_sha": FAILED_INCREMENT_4D_SOURCE_SHA,
            "workflow_run": FAILED_INCREMENT_4D_WORKFLOW_RUN,
            "job": FAILED_INCREMENT_4D_JOB,
            "artifact": FAILED_INCREMENT_4D_ARTIFACT,
            "artifact_sha256": FAILED_INCREMENT_4D_ARTIFACT_SHA256,
            "outcome": failed_increment_4d_summary["outcome"],
            "verified": True,
        },
    }
    (output_dir / "increment_4f_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pre_guard_front_reproduction.json").write_text(
        json.dumps(reproduction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Increment 4F Guard-front refinement\n\n"
        + "The corrected Increment 4E authority was verified. The first 82 "
        + "continuation steps through accepted step 451 were compared with the "
        + "prior failed Increment 4D evidence. Categorical Guard-front "
        + "refinement retained all failed B1 states on the unavailable side; "
        + "only later B1-success states formed compatibility-root brackets and "
        + "constructed fluxes. Formal project states remain unchanged.\n\n"
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
        "increment_4f_authority.json",
        "pre_guard_front_reproduction.json",
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
    parser.add_argument("--increment-4e-artifact-dir", type=Path, required=True)
    parser.add_argument("--increment-4e-artifact-digest", required=True)
    parser.add_argument(
        "--failed-increment-4d-artifact-dir",
        type=Path,
        required=True,
    )
    parser.add_argument("--failed-increment-4d-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    increment_4e_summary = _verify_increment_4e_artifact(
        args.increment_4e_artifact_dir,
        artifact_digest=args.increment_4e_artifact_digest,
    )
    failed_increment_4d_summary = _verify_failed_increment_4d_artifact(
        args.failed_increment_4d_artifact_dir,
        artifact_digest=args.failed_increment_4d_artifact_digest,
    )

    short_run._build_weak_compression_context = (
        increment_4d._candidate_state_build_weak_compression_context
    )
    short_run._solve_three_branch_boundary = (
        _guard_front_solve_three_branch_boundary
    )
    short_run._root_evidence_row = _guard_front_root_evidence_row
    full_horizon.OUTCOME = OUTCOME

    original_argv = sys.argv
    base_exit: SystemExit | None = None
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
        try:
            full_horizon.main()
        except SystemExit as exc:
            base_exit = exc
    finally:
        sys.argv = original_argv

    if not (args.output_dir / "summary.json").is_file():
        if base_exit is not None:
            raise base_exit
        raise GuardFrontContinuationStop(
            "OUTPUT_EVIDENCE_MISSING",
            "full-horizon runner did not create summary evidence",
        )

    summary = _postprocess_output(
        output_dir=args.output_dir,
        increment_4e_summary=increment_4e_summary,
        failed_increment_4d_summary=failed_increment_4d_summary,
        failed_increment_4d_artifact_dir=args.failed_increment_4d_artifact_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_4f_working_slice_gate_passed"]:
        raise SystemExit(
            "Increment 4F Guard-front refined continuation did not pass: "
            f"{summary.get('stop_classification')} {summary.get('stop_reason')}"
        )


if __name__ == "__main__":
    main()
