from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_full_horizon_guard_front_refined as base
import u3_b2_a1_weak_compression_bridge_full_horizon_guard_front_refined_evidence_gate as evidence_gate
import u3_b2_a1_weak_compression_bridge_short_run as short_run
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import normalize_phase


CORRECTION_PARENT_SOURCE_SHA = "618f49c0a75620751cb517d669a4da868e82f41e"
CORRECTION_PARENT_WORKFLOW_RUN = 31619671593
CORRECTION_PARENT_JOB = 94191039227
CORRECTION_PARENT_ARTIFACT = 9150769457
CORRECTION_PARENT_ARTIFACT_SHA256 = (
    "2d00f5fc739a218657de9cc82d0fb1193649decfa3d4813d15ef0782d8dc6927"
)
CORRECTION_PARENT_STOP = "SUCCESS_DOMAIN_NONMONOTONE"
CORRECTION_SCOPE = (
    "guard_front_evidence_rows_separated_from_compatibility_root_topology"
)

_ORIGINAL_SOLVE = base._guard_front_solve_three_branch_boundary
_ORIGINAL_ROOT_EVIDENCE = base._guard_front_root_evidence_row


class RootTopologyCorrectionStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _annotate_fixed_row(row: dict[str, Any]) -> dict[str, Any]:
    item = base._annotate_fixed_row(row)
    item.update(
        {
            "root_topology_member": False,
            "root_topology_order": None,
        }
    )
    return item


def _corrected_guard_front_positive_scan(
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
                    "expected_leading_b1_guard": base._is_unavailable(raw),
                    "scan_coordinate_correction": (
                        "requested_scan_coordinate_authoritative_guard_front_root_topology"
                    ),
                    "selected_sign_change_bracket_member": False,
                    "root_topology_member": False,
                    "root_topology_order": None,
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
            raise base.GuardFrontContinuationStop(
                "FIXED_SCAN_SCOPE_FAILURE",
                f"fixed positive scan node {index} exceeds the unchanged chi scope",
            )
        if bool(row.get("evaluation_succeeded")):
            success_seen = True
            base._require_success(row, f"fixed positive scan node {index}")
            successful_fixed.append(row)
            continue
        if not base._is_unavailable(row):
            raise base.GuardFrontContinuationStop(
                "UNAVAILABLE_FORMAL_OUTCOME_OUTSIDE_SCOPE",
                "unexpected fixed positive scan failure at node "
                f"{index}: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
            )
        if success_seen:
            raise base.GuardFrontContinuationStop(
                "SUCCESSFUL_NODE_FOLLOWED_BY_UNAVAILABLE_NODE",
                "an unavailable fixed scan node occurred after B1 success",
            )
        unavailable_fixed.append(row)

    if not successful_fixed:
        raise base.GuardFrontContinuationStop(
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
        raise base.GuardFrontContinuationStop(
            "ROOT_OR_ADMISSIBILITY_FAILURE",
            "a fixed successful-domain root bracket is inadmissible",
        )
    if len(fixed_admissible) > 1:
        raise base.GuardFrontContinuationStop(
            "MULTIPLE_ROOTS",
            "multiple fixed successful-domain root brackets were observed",
        )

    fixed_evidence = [_annotate_fixed_row(row) for row in fixed_rows]
    if len(fixed_admissible) == 1:
        selected = {
            float(fixed_admissible[0]["lower_offset_pa"]),
            float(fixed_admissible[0]["upper_offset_pa"]),
        }
        topology = sorted(
            successful_fixed,
            key=lambda row: float(row["pressure_offset_pa"]),
        )
        topology_offsets = [
            float(row["pressure_offset_pa"]) for row in topology
        ]
        topology_residuals = [
            float(row["compatibility_residual_kg_s"]) for row in topology
        ]
        rows = []
        topology_order = {
            offset: index
            for index, offset in enumerate(topology_offsets, start=1)
        }
        for row in fixed_evidence:
            offset = float(row["pressure_offset_pa"])
            rows.append(
                {
                    **row,
                    "selected_sign_change_bracket_member": bool(
                        offset in selected
                    ),
                    "root_topology_member": bool(
                        offset in topology_order
                        and row.get("evaluation_succeeded") is True
                    ),
                    "root_topology_order": topology_order.get(offset),
                }
            )
        return {
            "static": static,
            "rows": rows,
            "evaluate_offset": evaluate_offset,
            "evaluable_brackets": fixed_evaluable,
            "admissible_brackets": fixed_admissible,
            "sign_change_count": 1,
            "residual_monotone_nonincreasing": bool(
                len(topology_residuals) >= 2
                and all(
                    topology_residuals[index + 1]
                    <= topology_residuals[index]
                    for index in range(len(topology_residuals) - 1)
                )
            ),
            "delta_p_max_pa": delta_p_max,
            "guard_node_count": len(unavailable_fixed),
            "first_success_offset_pa": topology_offsets[0],
            "first_success_stagnation_pressure_pa": float(
                topology[0]["stagnation_pressure_pa"]
            ),
            "scope_limit_residual_kg_s": topology_residuals[-1],
            "guard_front_refinement_applied": False,
            "guard_front_reverse_pressure_count": sum(
                row.get("formal_outcome") == base.REVERSE_PRESSURE_OUTCOME
                for row in unavailable_fixed
            ),
            "guard_front_nonpositive_head_count": sum(
                row.get("formal_outcome") == base.NONPOSITIVE_HEAD_OUTCOME
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
            "guard_front_evidence_row_count": len(rows),
            "guard_front_successful_intermediate_row_count": 0,
            "root_topology_node_count": len(topology),
            "root_topology_requested_offsets_pa": topology_offsets,
            "root_topology_residuals_kg_s": topology_residuals,
            "root_topology_monotone_nonincreasing": True,
            "root_topology_sign_change_count": 1,
            "root_topology_correction_applied": False,
        }

    if not unavailable_fixed:
        scope_residual = float(
            successful_fixed[-1]["compatibility_residual_kg_s"]
        )
        stop_classification = (
            "FINITE_COMPRESSION_MODEL_REQUIRED"
            if scope_residual
            > base.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
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
            "guard_front_evidence_row_count": len(fixed_evidence),
            "guard_front_successful_intermediate_row_count": 0,
            "root_topology_node_count": len(successful_fixed),
            "root_topology_requested_offsets_pa": [
                float(row["pressure_offset_pa"])
                for row in successful_fixed
            ],
            "root_topology_residuals_kg_s": [
                float(row["compatibility_residual_kg_s"])
                for row in successful_fixed
            ],
            "root_topology_monotone_nonincreasing": True,
            "root_topology_sign_change_count": 0,
            "root_topology_correction_applied": False,
        }

    lower_offset = float(unavailable_fixed[-1]["pressure_offset_pa"])
    upper_offset = float(successful_fixed[0]["pressure_offset_pa"])
    initial_lower = lower_offset
    initial_upper = upper_offset
    lower = evaluate_offset(lower_offset)
    upper = evaluate_offset(upper_offset)
    if not base._is_unavailable(lower):
        raise base.GuardFrontContinuationStop(
            "GUARD_FRONT_BISECTION_FAILURE",
            "initial lower Guard-front endpoint is not B1-unavailable",
        )
    base._require_success(upper, "initial upper Guard-front endpoint")
    bisection_evidence: list[dict[str, Any]] = []

    for iteration in range(1, base.GUARD_FRONT_ITERATIONS + 1):
        before_lower = lower_offset
        before_upper = upper_offset
        midpoint_offset = float(0.5 * (before_lower + before_upper))
        if not before_lower < midpoint_offset < before_upper:
            raise base.GuardFrontContinuationStop(
                "GUARD_FRONT_BISECTION_FAILURE",
                "Guard-front midpoint is not strictly inside the bracket",
            )
        midpoint = evaluate_offset(midpoint_offset)
        if base._is_unavailable(midpoint):
            midpoint_classification = "B1_UNAVAILABLE"
            lower_offset = midpoint_offset
            lower = midpoint
        elif bool(midpoint.get("evaluation_succeeded")):
            base._require_success(
                midpoint,
                f"Guard-front midpoint {iteration}",
            )
            midpoint_classification = "B1_SUCCESS"
            upper_offset = midpoint_offset
            upper = midpoint
        else:
            raise base.GuardFrontContinuationStop(
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
                "root_topology_member": False,
                "root_topology_order": None,
            }
        )
        bisection_evidence.append(evidence)

    if not base._is_unavailable(lower):
        raise base.GuardFrontContinuationStop(
            "GUARD_FRONT_BISECTION_FAILURE",
            "final lower Guard-front endpoint is not B1-unavailable",
        )
    base._require_success(upper, "refined first-success endpoint")

    topology = [upper] + [
        row
        for row in successful_fixed
        if float(row["pressure_offset_pa"]) > upper_offset
    ]
    topology = sorted(
        topology,
        key=lambda row: float(row["pressure_offset_pa"]),
    )
    topology_offsets = [
        float(row["pressure_offset_pa"]) for row in topology
    ]
    if any(
        topology_offsets[index + 1] <= topology_offsets[index]
        for index in range(len(topology_offsets) - 1)
    ):
        raise base.GuardFrontContinuationStop(
            "ROOT_TOPOLOGY_COORDINATE_FAILURE",
            "root-topology requested pressure offsets are not strictly increasing",
        )
    topology_residuals = [
        float(row["compatibility_residual_kg_s"]) for row in topology
    ]
    topology_monotone = bool(
        len(topology_residuals) >= 2
        and all(
            topology_residuals[index + 1]
            <= topology_residuals[index]
            for index in range(len(topology_residuals) - 1)
        )
    )
    if not topology_monotone:
        raise base.GuardFrontContinuationStop(
            "SUCCESS_DOMAIN_NONMONOTONE",
            "root-topology compatibility residual is not monotone",
        )
    evaluable = short_run._brackets(
        topology,
        admissible_only=False,
    )
    admissible = short_run._brackets(
        topology,
        admissible_only=True,
    )
    if len(evaluable) != len(admissible):
        raise base.GuardFrontContinuationStop(
            "ROOT_OR_ADMISSIBILITY_FAILURE",
            "a root-topology bracket is inadmissible",
        )
    if len(admissible) > 1:
        raise base.GuardFrontContinuationStop(
            "MULTIPLE_ROOTS",
            "multiple root-topology brackets were observed",
        )

    refined_residual = float(upper["compatibility_residual_kg_s"])
    scope_residual = float(
        successful_fixed[-1]["compatibility_residual_kg_s"]
    )
    stop_classification: str | None = None
    if len(admissible) == 0:
        if (
            refined_residual
            < -base.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        ):
            stop_classification = "ROOT_LIES_INSIDE_B1_GUARD_DOMAIN"
        elif (
            scope_residual
            > base.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
        ):
            stop_classification = "FINITE_COMPRESSION_MODEL_REQUIRED"
        else:
            stop_classification = "NO_UNIQUE_WEAK_COMPRESSION_ROOT"

    selected_offsets: set[float] = set()
    if admissible:
        selected_offsets = {
            float(admissible[0]["lower_offset_pa"]),
            float(admissible[0]["upper_offset_pa"]),
        }
    topology_order = {
        offset: index
        for index, offset in enumerate(topology_offsets, start=1)
    }
    all_rows = fixed_evidence + bisection_evidence
    all_rows = sorted(
        all_rows,
        key=lambda row: (
            float(row["pressure_offset_pa"]),
            str(row.get("scan_node_role")),
            int(row.get("guard_front_iteration") or 0),
        ),
    )
    all_rows = [
        {
            **row,
            "selected_sign_change_bracket_member": bool(
                float(row["pressure_offset_pa"]) in selected_offsets
            ),
            "root_topology_member": bool(
                float(row["pressure_offset_pa"]) in topology_order
                and row.get("evaluation_succeeded") is True
            ),
            "root_topology_order": topology_order.get(
                float(row["pressure_offset_pa"])
            ),
        }
        for row in all_rows
    ]
    unavailable_rows = [
        row for row in all_rows if base._is_unavailable(row)
    ]
    successful_intermediate_rows = [
        row
        for row in bisection_evidence
        if row.get("evaluation_succeeded") is True
        and float(row["pressure_offset_pa"]) != upper_offset
    ]
    return {
        "static": static,
        "rows": all_rows,
        "evaluate_offset": evaluate_offset,
        "evaluable_brackets": evaluable,
        "admissible_brackets": admissible,
        "sign_change_count": len(admissible),
        "residual_monotone_nonincreasing": topology_monotone,
        "delta_p_max_pa": delta_p_max,
        "guard_node_count": len(unavailable_rows),
        "first_success_offset_pa": upper_offset,
        "first_success_stagnation_pressure_pa": float(
            upper["stagnation_pressure_pa"]
        ),
        "scope_limit_residual_kg_s": scope_residual,
        "guard_front_refinement_applied": True,
        "guard_front_reverse_pressure_count": sum(
            row.get("formal_outcome") == base.REVERSE_PRESSURE_OUTCOME
            for row in unavailable_rows
        ),
        "guard_front_nonpositive_head_count": sum(
            row.get("formal_outcome") == base.NONPOSITIVE_HEAD_OUTCOME
            for row in unavailable_rows
        ),
        "guard_front_success_count": sum(
            row.get("evaluation_succeeded") is True for row in all_rows
        ),
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
        "guard_front_evidence_row_count": len(all_rows),
        "guard_front_successful_intermediate_row_count": len(
            successful_intermediate_rows
        ),
        "root_topology_node_count": len(topology),
        "root_topology_requested_offsets_pa": topology_offsets,
        "root_topology_residuals_kg_s": topology_residuals,
        "root_topology_monotone_nonincreasing": topology_monotone,
        "root_topology_sign_change_count": len(admissible),
        "root_topology_correction_applied": True,
    }


def _corrected_solve_three_branch_boundary(
    *,
    hook: Any,
    U: np.ndarray,
    solver_time_s: float,
) -> dict[str, Any]:
    context = _ORIGINAL_SOLVE(
        hook=hook,
        U=U,
        solver_time_s=solver_time_s,
    )
    rows = list(context.get("positive_scan_rows", []))
    topology_rows = [
        row
        for row in rows
        if bool(row.get("root_topology_member"))
        and bool(row.get("evaluation_succeeded"))
    ]
    topology_rows = sorted(
        topology_rows,
        key=lambda row: int(row["root_topology_order"]),
    )
    topology_offsets = [
        float(row["pressure_offset_pa"]) for row in topology_rows
    ]
    topology_residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in topology_rows
    ]
    context.update(
        {
            "guard_front_evidence_row_count": len(rows),
            "guard_front_successful_intermediate_row_count": sum(
                row.get("scan_node_role") == "GUARD_FRONT_BISECTION"
                and bool(row.get("evaluation_succeeded"))
                and not bool(row.get("root_topology_member"))
                for row in rows
            ),
            "root_topology_node_count": len(topology_rows),
            "root_topology_requested_offsets_pa": topology_offsets,
            "root_topology_residuals_kg_s": topology_residuals,
            "root_topology_monotone_nonincreasing": bool(
                len(topology_residuals) >= 2
                and all(
                    topology_residuals[index + 1]
                    <= topology_residuals[index]
                    for index in range(len(topology_residuals) - 1)
                )
            ),
            "root_topology_sign_change_count": int(
                context.get("positive_scan_sign_change_count", 0)
            ),
            "root_topology_correction_applied": bool(
                context.get("guard_front_refinement_applied", False)
            ),
        }
    )
    return context


def _corrected_root_evidence_row(
    *,
    context: dict[str, Any],
    requested_solver_step: int,
) -> dict[str, Any]:
    row = _ORIGINAL_ROOT_EVIDENCE(
        context=context,
        requested_solver_step=requested_solver_step,
    )
    row.update(
        {
            "guard_front_evidence_row_count": int(
                context.get("guard_front_evidence_row_count", 0)
            ),
            "guard_front_successful_intermediate_row_count": int(
                context.get(
                    "guard_front_successful_intermediate_row_count",
                    0,
                )
            ),
            "root_topology_node_count": int(
                context.get("root_topology_node_count", 0)
            ),
            "root_topology_requested_offsets_pa_json": json.dumps(
                context.get("root_topology_requested_offsets_pa", [])
            ),
            "root_topology_residuals_kg_s_json": json.dumps(
                context.get("root_topology_residuals_kg_s", [])
            ),
            "root_topology_monotone_nonincreasing": bool(
                context.get(
                    "root_topology_monotone_nonincreasing",
                    False,
                )
            ),
            "root_topology_sign_change_count": int(
                context.get("root_topology_sign_change_count", 0)
            ),
            "root_topology_correction_applied": bool(
                context.get("root_topology_correction_applied", False)
            ),
        }
    )
    return row


def _corrected_postprocess_output(
    *,
    output_dir: Path,
    increment_4e_summary: dict[str, Any],
    failed_increment_4d_summary: dict[str, Any],
    failed_increment_4d_artifact_dir: Path,
) -> dict[str, Any]:
    summary = evidence_gate._corrected_postprocess_output(
        output_dir=output_dir,
        increment_4e_summary=increment_4e_summary,
        failed_increment_4d_summary=failed_increment_4d_summary,
        failed_increment_4d_artifact_dir=failed_increment_4d_artifact_dir,
    )
    roots = base._read_csv(
        output_dir / "full_horizon_continuation_roots.csv"
    )
    corrected = [
        row
        for row in roots
        if row.get("root_topology_correction_applied") == "True"
    ]
    topology_gate = bool(
        corrected
        and all(int(row["guard_front_evidence_row_count"]) > 0 for row in corrected)
        and all(int(row["root_topology_node_count"]) >= 2 for row in corrected)
        and all(
            row["root_topology_monotone_nonincreasing"] == "True"
            for row in corrected
        )
        and all(
            int(row["root_topology_sign_change_count"]) == 1
            for row in corrected
        )
        and all(
            json.loads(row["root_topology_requested_offsets_pa_json"])
            for row in corrected
        )
        and all(
            json.loads(row["root_topology_residuals_kg_s_json"])
            for row in corrected
        )
    )
    corrected_working_slice_gate = bool(
        summary["working_vertical_slice_two_l_over_c0_passed"]
        and summary["pre_guard_front_reproduction_passed"]
        and summary["guard_front_refinement_gate_passed"]
        and topology_gate
    )
    original_outcome = summary["outcome"]
    original_gate = bool(summary["increment_4f_working_slice_gate_passed"])
    summary.update(
        {
            "guard_front_root_topology_correction_applied": True,
            "guard_front_root_topology_correction_scope": CORRECTION_SCOPE,
            "guard_front_root_topology_corrected_step_count": len(corrected),
            "guard_front_root_topology_gate_passed": topology_gate,
            "maximum_guard_front_evidence_row_count": (
                max(
                    int(row["guard_front_evidence_row_count"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "maximum_guard_front_successful_intermediate_row_count": (
                max(
                    int(row[
                        "guard_front_successful_intermediate_row_count"
                    ])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "minimum_root_topology_node_count": (
                min(
                    int(row["root_topology_node_count"])
                    for row in corrected
                )
                if corrected
                else None
            ),
            "original_increment_4f_outcome_before_topology_correction": (
                original_outcome
            ),
            "original_increment_4f_gate_before_topology_correction": (
                original_gate
            ),
            "outcome": (
                base.OUTCOME
                if corrected_working_slice_gate
                else "INCREMENT_4F_STOPPED"
            ),
            "increment_4f_working_slice_gate_passed": (
                corrected_working_slice_gate
            ),
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
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    correction = {
        "scope": CORRECTION_SCOPE,
        "parent_failed_run": {
            "source_sha": CORRECTION_PARENT_SOURCE_SHA,
            "workflow_run": CORRECTION_PARENT_WORKFLOW_RUN,
            "job": CORRECTION_PARENT_JOB,
            "artifact": CORRECTION_PARENT_ARTIFACT,
            "artifact_sha256": CORRECTION_PARENT_ARTIFACT_SHA256,
            "stop_classification": CORRECTION_PARENT_STOP,
        },
        "corrected_step_count": len(corrected),
        "root_topology_gate_passed": topology_gate,
        "b1_behavior_changed": False,
        "intermediate_evidence_discarded": False,
        "intermediate_success_used_as_root_topology": False,
        "failed_state_used_as_root_endpoint": False,
        "failed_state_used_to_construct_flux": False,
        "tolerance_or_scope_changed": False,
    }
    (output_dir / "root_topology_correction.json").write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Guard-front root-topology correction\n\n"
        + "All categorical-bisection midpoint rows remain in the evidence. "
        + "Compatibility-root topology uses only the final refined first-success "
        + "state and higher fixed B1-success states. No failed B1 state or "
        + "intermediate evidence row was converted into a root endpoint or "
        + "applied flux.\n\n"
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
        "refinement_evidence_gate_correction.json",
        "root_topology_correction.json",
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
    parser.add_argument("--evidence-gate-correction-spec", type=Path, required=True)
    parser.add_argument("--root-topology-correction-spec", type=Path, required=True)
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
    if not args.evidence_gate_correction_spec.is_file():
        raise FileNotFoundError(args.evidence_gate_correction_spec)
    if not args.root_topology_correction_spec.is_file():
        raise FileNotFoundError(args.root_topology_correction_spec)

    base._guard_front_positive_scan = _corrected_guard_front_positive_scan
    base._guard_front_solve_three_branch_boundary = (
        _corrected_solve_three_branch_boundary
    )
    base._guard_front_root_evidence_row = _corrected_root_evidence_row
    base._postprocess_output = _corrected_postprocess_output

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
            "--increment-4e-artifact-dir",
            str(args.increment_4e_artifact_dir),
            "--increment-4e-artifact-digest",
            args.increment_4e_artifact_digest,
            "--failed-increment-4d-artifact-dir",
            str(args.failed_increment_4d_artifact_dir),
            "--failed-increment-4d-artifact-digest",
            args.failed_increment_4d_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        base.main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
