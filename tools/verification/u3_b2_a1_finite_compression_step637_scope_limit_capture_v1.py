from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from types import TracebackType
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_step637_zero_flow_endpoint_diagnostic_v2 as increment_9j
import u3_b2_a1_finite_compression_step637_zero_flow_endpoint_diagnostic_v4 as schema_correction


PRECURSOR_RUN = 31676910126
PRECURSOR_JOB = 94373367790
PRECURSOR_SOURCE_SHA = "c194068a0c64b46b915b5f31c12a3ec80c7cbbe8"
EXPECTED_CLASSIFICATION = "ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE"
EXPECTED_MESSAGE = "zero-flow endpoint did not meet retained compatibility criteria"
SCOPE_OUTCOME = "A1_NEAR_ZERO_FLOW_TRANSITION_NOT_APPROVED_FAIL_CLOSED"
SCOPE_DECISION_FILE = "scope_limit_decision.json"

BASE_OUTPUT_NAMES = (
    "step637_fixed_scan.csv",
    "step637_ultrafine_scan.csv",
    "step637_broad_endpoint_scan.csv",
    "step637_lower_boundary_refinement.csv",
    "step637_upper_boundary_refinement.csv",
    "step637_root_topology.csv",
    "step637_selected_root.csv",
    "step637_stagnation_pressure_endpoint_bisection.csv",
    "step637_velocity_endpoint_bisection.csv",
    "step637_stagnation_pressure_endpoint.csv",
    "step637_velocity_endpoint.csv",
    "step637_state_identity.npz",
    "authority_verification.json",
    "summary.json",
    "report.md",
)


class ScopeLimitCaptureStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _state_sha256(U: np.ndarray) -> str:
    return increment_9j._state_sha256(np.asarray(U, dtype=float))


def _run_frame(traceback: TracebackType | None) -> dict[str, Any]:
    current = traceback
    while current is not None:
        if current.tb_frame.f_code is increment_9j._run.__code__:
            return current.tb_frame.f_locals
        current = current.tb_next
    raise ScopeLimitCaptureStop("Increment 9J _run frame was not found")


def _copy_rows(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ScopeLimitCaptureStop(f"captured {name} is not a list")
    return [copy.deepcopy(dict(row)) for row in value]


def _capture_locals(
    exc: increment_9j.ZeroFlowEndpointDiagnosticStop,
) -> dict[str, Any]:
    if exc.classification != EXPECTED_CLASSIFICATION:
        raise ScopeLimitCaptureStop(
            f"unexpected Increment 9J classification {exc.classification!r}"
        ) from exc
    if str(exc) != EXPECTED_MESSAGE:
        raise ScopeLimitCaptureStop(
            f"unexpected Increment 9J message {str(exc)!r}"
        ) from exc

    local = _run_frame(exc.__traceback__)
    required = {
        "U",
        "U_after",
        "artifact_digest",
        "parent_root",
        "static",
        "reconstruction",
        "hook",
        "allowed_phases",
        "velocity_zero_tolerance",
        "back_pressure",
        "seed_chi",
        "fixed_rows",
        "ultrafine_lower",
        "ultrafine_upper",
        "ultrafine_rows",
        "ultrafine_blocks",
        "lower_boundary_rows",
        "upper_boundary_rows",
        "root_topology_rows",
        "root_topology_residuals",
        "root_bracket_count",
        "selected_root",
        "ultrafine_gate",
        "broad_lower",
        "broad_upper",
        "broad_rows",
        "p0_brackets",
        "velocity_brackets",
        "p0_endpoint",
        "p0_bisection_rows",
        "p0_bisection_summary",
        "velocity_endpoint",
        "velocity_bisection_rows",
        "velocity_bisection_summary",
        "broad_spacing",
        "zero_endpoint_gate",
        "endpoint_chi_separation",
        "p0_pipe_mass_rate",
        "p0_velocity",
        "p0_mach",
        "p0_phase",
        "p0_margin",
        "state_unchanged",
    }
    missing = sorted(required - set(local))
    if missing:
        raise ScopeLimitCaptureStop(
            f"unsupported Increment 9J frame is missing locals: {missing}"
        )

    static = local["static"]
    reconstruction = local["reconstruction"]
    hook = local["hook"]
    selected_root = local["selected_root"]
    p0_endpoint = local["p0_endpoint"]
    velocity_endpoint = local["velocity_endpoint"]

    return {
        "classification": exc.classification,
        "message": str(exc),
        "artifact_digest": str(local["artifact_digest"]),
        "U": np.asarray(local["U"], dtype=float).copy(),
        "U_after": np.asarray(local["U_after"], dtype=float).copy(),
        "parent_root": copy.deepcopy(dict(local["parent_root"])),
        "interior_static": {
            "pressure_pa": float(static.pressure_pa),
            "velocity_m_s": float(static.velocity_m_s),
            "sound_speed_m_s": float(static.sound_speed_m_s),
            "phase": str(static.phase),
        },
        "interior_stagnation_pressure_pa": float(
            reconstruction.stagnation_pressure_pa
        ),
        "pipe_area_m2": float(hook.area_m2),
        "allowed_phases": sorted(str(value) for value in local["allowed_phases"]),
        "velocity_zero_tolerance_m_s": float(
            local["velocity_zero_tolerance"]
        ),
        "back_pressure_pa": float(local["back_pressure"]),
        "seed_chi": float(local["seed_chi"]),
        "fixed_rows": _copy_rows(local["fixed_rows"], "fixed_rows"),
        "ultrafine_lower_chi": float(local["ultrafine_lower"]),
        "ultrafine_upper_chi": float(local["ultrafine_upper"]),
        "ultrafine_rows": _copy_rows(
            local["ultrafine_rows"], "ultrafine_rows"
        ),
        "ultrafine_block_lengths": [
            len(block) for block in local["ultrafine_blocks"]
        ],
        "lower_boundary_rows": _copy_rows(
            local["lower_boundary_rows"], "lower_boundary_rows"
        ),
        "upper_boundary_rows": _copy_rows(
            local["upper_boundary_rows"], "upper_boundary_rows"
        ),
        "root_topology_rows": _copy_rows(
            local["root_topology_rows"], "root_topology_rows"
        ),
        "root_topology_residuals_kg_s": [
            float(value) for value in local["root_topology_residuals"]
        ],
        "root_bracket_count": int(local["root_bracket_count"]),
        "selected_root": (
            None if selected_root is None else copy.deepcopy(dict(selected_root))
        ),
        "ultrafine_gate": bool(local["ultrafine_gate"]),
        "broad_lower_chi": float(local["broad_lower"]),
        "broad_upper_chi": float(local["broad_upper"]),
        "broad_rows": _copy_rows(local["broad_rows"], "broad_rows"),
        "p0_bracket_count": len(local["p0_brackets"]),
        "velocity_bracket_count": len(local["velocity_brackets"]),
        "p0_endpoint": (
            None if p0_endpoint is None else copy.deepcopy(dict(p0_endpoint))
        ),
        "p0_bisection_rows": _copy_rows(
            local["p0_bisection_rows"], "p0_bisection_rows"
        ),
        "p0_bisection_summary": copy.deepcopy(
            local["p0_bisection_summary"]
        ),
        "velocity_endpoint": (
            None
            if velocity_endpoint is None
            else copy.deepcopy(dict(velocity_endpoint))
        ),
        "velocity_bisection_rows": _copy_rows(
            local["velocity_bisection_rows"], "velocity_bisection_rows"
        ),
        "velocity_bisection_summary": copy.deepcopy(
            local["velocity_bisection_summary"]
        ),
        "broad_spacing": float(local["broad_spacing"]),
        "zero_endpoint_gate": bool(local["zero_endpoint_gate"]),
        "endpoint_chi_separation": (
            None
            if local["endpoint_chi_separation"] is None
            else float(local["endpoint_chi_separation"])
        ),
        "p0_pipe_mass_rate_kg_s": (
            None
            if local["p0_pipe_mass_rate"] is None
            else float(local["p0_pipe_mass_rate"])
        ),
        "p0_velocity_m_s": (
            None
            if local["p0_velocity"] is None
            else float(local["p0_velocity"])
        ),
        "p0_mach": (
            None if local["p0_mach"] is None else float(local["p0_mach"])
        ),
        "p0_phase": (
            None if local["p0_phase"] is None else str(local["p0_phase"])
        ),
        "p0_margin_pa": (
            None if local["p0_margin"] is None else float(local["p0_margin"])
        ),
        "state_unchanged": bool(local["state_unchanged"]),
    }


def _selected_root_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "chi": float(row["requested_chi"]),
        "pressure_pa": float(row["pressure_pa"]),
        "pressure_offset_pa": float(row["pressure_offset_pa"]),
        "residual_kg_s": float(row["root_mass_residual_kg_s"]),
        "local_slope_kg_s_Pa": float(
            row["local_residual_slope_kg_s_Pa"]
        ),
        "velocity_m_s": float(row["velocity_m_s"]),
        "mach": float(row["mach"]),
        "phase": str(row["phase"]),
        "b1_outcome": str(row["formal_outcome"]),
        "root_gate_passed": bool(row["root_gate_passed"]),
    }


def _compatibility_conditions(capture: dict[str, Any]) -> dict[str, bool]:
    p0_velocity = capture["p0_velocity_m_s"]
    p0_mach = capture["p0_mach"]
    p0_phase = capture["p0_phase"]
    p0_mass = capture["p0_pipe_mass_rate_kg_s"]
    velocity_tolerance = capture["velocity_zero_tolerance_m_s"]
    separation = capture["endpoint_chi_separation"]
    spacing = capture["broad_spacing"]

    absolute_velocity = bool(
        p0_velocity is not None and abs(p0_velocity) <= velocity_tolerance
    )
    separation_condition = bool(
        separation is not None and separation <= spacing
    )
    return {
        "no_ultrafine_admissible_island": not bool(
            capture["ultrafine_block_lengths"]
        ),
        "finite_pipe_mass_rate": bool(
            p0_mass is not None and math.isfinite(p0_mass)
        ),
        "pipe_mass_rate_within_root_tolerance": bool(
            p0_mass is not None
            and math.isfinite(p0_mass)
            and abs(p0_mass) <= increment_9j.ROOT_TOLERANCE
        ),
        "nonreverse_velocity_within_locked_tolerance": bool(
            p0_velocity is not None and p0_velocity >= -velocity_tolerance
        ),
        "subsonic_candidate": bool(
            p0_mach is not None and 0.0 <= p0_mach < 1.0
        ),
        "allowed_single_phase": bool(
            p0_phase is not None
            and increment_9j.normalize_phase(p0_phase)
            in set(capture["allowed_phases"])
        ),
        "absolute_velocity_zero": absolute_velocity,
        "endpoint_chi_separation_within_one_broad_spacing": (
            separation_condition
        ),
        "velocity_compatibility": bool(
            absolute_velocity or separation_condition
        ),
    }


def _build_summary(
    *,
    capture: dict[str, Any],
    source_git_sha: str,
    model_review_spec: Path,
    authority_correction_spec: Path,
    schema_correction_spec: Path,
    scope_decision_spec: Path,
) -> dict[str, Any]:
    static = capture["interior_static"]
    parent_root = capture["parent_root"]
    p0_endpoint = capture["p0_endpoint"]
    velocity_endpoint = capture["velocity_endpoint"]
    category_counts = Counter(
        str(row["candidate_classification"])
        for row in capture["ultrafine_rows"]
    )
    conditions = _compatibility_conditions(capture)
    failed_conditions = sorted(
        name for name, passed in conditions.items() if not passed
    )

    if capture["classification"] != EXPECTED_CLASSIFICATION:
        raise ScopeLimitCaptureStop("captured classification changed")
    if capture["ultrafine_gate"] or capture["zero_endpoint_gate"]:
        raise ScopeLimitCaptureStop(
            "unsupported capture unexpectedly has a supported continuation gate"
        )
    if capture["p0_bracket_count"] != 1:
        raise ScopeLimitCaptureStop(
            "expected one stagnation-pressure endpoint bracket"
        )
    if not failed_conditions:
        raise ScopeLimitCaptureStop(
            "zero-flow endpoint gate is false but no failed sub-gate was found"
        )

    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_finite_compression_increment_9j_scope_limit_capture_v1"
        ),
        "scope": (
            "diagnostic_only_step637_fail_closed_scope_decision_no_solver_advance"
        ),
        "source_git_sha": source_git_sha,
        "unsupported_precursor_run": PRECURSOR_RUN,
        "unsupported_precursor_job": PRECURSOR_JOB,
        "unsupported_precursor_source_git_sha": PRECURSOR_SOURCE_SHA,
        "parent_source_sha": increment_9j.PARENT_SOURCE_SHA,
        "parent_run": increment_9j.PARENT_RUN,
        "parent_job": increment_9j.PARENT_JOB,
        "parent_artifact": increment_9j.PARENT_ARTIFACT,
        "parent_artifact_name": increment_9j.PARENT_ARTIFACT_NAME,
        "parent_artifact_sha256": capture["artifact_digest"],
        "parent_artifact_verified": True,
        "solver_step_loaded": increment_9j.EXPECTED_STEP,
        "next_requested_solver_step": increment_9j.NEXT_STEP,
        "solver_time_s": increment_9j.EXPECTED_TIME_S,
        "state_sha256_before": _state_sha256(capture["U"]),
        "state_sha256_after": _state_sha256(capture["U_after"]),
        "state_unchanged": bool(
            capture["state_unchanged"]
            and np.array_equal(capture["U"], capture["U_after"])
        ),
        "fvm_step_638_attempted": False,
        "interior_pressure_pa": static["pressure_pa"],
        "interior_stagnation_pressure_pa": capture[
            "interior_stagnation_pressure_pa"
        ],
        "interior_velocity_m_s": static["velocity_m_s"],
        "interior_mach": float(
            static["velocity_m_s"] / static["sound_speed_m_s"]
        ),
        "interior_phase": static["phase"],
        "back_pressure_pa": capture["back_pressure_pa"],
        "last_accepted_root_chi": float(parent_root["root_requested_chi"]),
        "last_accepted_root_pressure_pa": float(parent_root["root_pressure_pa"]),
        "last_accepted_root_velocity_m_s": float(
            parent_root["root_velocity_m_s"]
        ),
        "last_accepted_root_stagnation_pressure_margin_pa": float(
            parent_root["root_stagnation_pressure_margin_above_back_pa"]
        ),
        "seed_chi": capture["seed_chi"],
        "fixed_scan_node_count": len(capture["fixed_rows"]),
        "ultrafine_lower_factor": increment_9j.ULTRAFINE_LOWER_FACTOR,
        "ultrafine_upper_factor": increment_9j.ULTRAFINE_UPPER_FACTOR,
        "ultrafine_lower_chi": capture["ultrafine_lower_chi"],
        "ultrafine_upper_chi": capture["ultrafine_upper_chi"],
        "ultrafine_node_count": len(capture["ultrafine_rows"]),
        "ultrafine_category_counts": dict(sorted(category_counts.items())),
        "ultrafine_admissible_island_count": len(
            capture["ultrafine_block_lengths"]
        ),
        "ultrafine_admissible_island_node_count": (
            0
            if not capture["ultrafine_block_lengths"]
            else capture["ultrafine_block_lengths"][0]
        ),
        "root_topology_node_count": len(capture["root_topology_rows"]),
        "root_topology_residuals_kg_s": capture[
            "root_topology_residuals_kg_s"
        ],
        "root_topology_sign_change_count": capture["root_bracket_count"],
        "selected_root": _selected_root_summary(capture["selected_root"]),
        "broad_lower_factor": increment_9j.BROAD_LOWER_FACTOR,
        "broad_upper_factor": increment_9j.BROAD_UPPER_FACTOR,
        "broad_lower_chi": capture["broad_lower_chi"],
        "broad_upper_chi": capture["broad_upper_chi"],
        "broad_node_count": len(capture["broad_rows"]),
        "broad_chi_spacing": capture["broad_spacing"],
        "stagnation_pressure_endpoint_bracket_count": capture[
            "p0_bracket_count"
        ],
        "velocity_endpoint_bracket_count": capture["velocity_bracket_count"],
        "stagnation_pressure_endpoint_bisection": capture[
            "p0_bisection_summary"
        ],
        "velocity_endpoint_bisection": capture["velocity_bisection_summary"],
        "stagnation_pressure_endpoint_chi": (
            None
            if p0_endpoint is None
            else float(p0_endpoint["requested_chi"])
        ),
        "stagnation_pressure_endpoint_margin_pa": capture["p0_margin_pa"],
        "stagnation_pressure_endpoint_static_pressure_pa": (
            None if p0_endpoint is None else float(p0_endpoint["pressure_pa"])
        ),
        "stagnation_pressure_endpoint_velocity_m_s": capture[
            "p0_velocity_m_s"
        ],
        "stagnation_pressure_endpoint_mach": capture["p0_mach"],
        "stagnation_pressure_endpoint_phase": capture["p0_phase"],
        "stagnation_pressure_endpoint_pipe_mass_rate_kg_s": capture[
            "p0_pipe_mass_rate_kg_s"
        ],
        "stagnation_pressure_endpoint_b1_outcome": (
            None if p0_endpoint is None else p0_endpoint.get("formal_outcome")
        ),
        "stagnation_pressure_endpoint_local_admissible": (
            None
            if p0_endpoint is None
            else bool(p0_endpoint.get("local_candidate_admissible"))
        ),
        "velocity_endpoint_chi": (
            None
            if velocity_endpoint is None
            else float(velocity_endpoint["requested_chi"])
        ),
        "velocity_endpoint_velocity_m_s": (
            None
            if velocity_endpoint is None
            else float(velocity_endpoint["velocity_m_s"])
        ),
        "velocity_endpoint_b1_outcome": (
            None
            if velocity_endpoint is None
            else velocity_endpoint.get("formal_outcome")
        ),
        "endpoint_chi_separation": capture["endpoint_chi_separation"],
        "root_mass_tolerance_kg_s": increment_9j.ROOT_TOLERANCE,
        "velocity_zero_tolerance_m_s": capture[
            "velocity_zero_tolerance_m_s"
        ],
        "ultrafine_continuation_gate_passed": capture["ultrafine_gate"],
        "zero_flow_endpoint_gate_passed": capture["zero_endpoint_gate"],
        "zero_flow_compatibility_conditions": conditions,
        "failed_zero_flow_compatibility_conditions": failed_conditions,
        "diagnostic_stop_classification": capture["classification"],
        "diagnostic_stop_message": capture["message"],
        "outcome": capture["classification"],
        "increment_9j_diagnostic_classification_complete": False,
        "ultrafine_actual_continuation_supported": False,
        "zero_flow_branch_review_supported": False,
        "scope_limit_supported": True,
        "scope_limit_outcome": SCOPE_OUTCOME,
        "scope_limit_decision_complete": True,
        "recommended_next_action": "SCOPE_LIMIT_AND_HOLD",
        "additional_root_scan_refinement_authorized": False,
        "zero_flow_branch_implementation_authorized": False,
        "model_review_spec_sha256": _sha256(model_review_spec),
        "authority_correction_spec_sha256": _sha256(
            authority_correction_spec
        ),
        "schema_correction_spec_sha256": _sha256(schema_correction_spec),
        "scope_decision_spec_sha256": _sha256(scope_decision_spec),
        "traceback_frame_capture_only": True,
        "inner_scan_node_counts_changed": False,
        "finite_compression_branch_approved": False,
        "multi_step_finite_compression_continuation_authorized": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    return summary


def _write_base_evidence(
    *,
    output: Path,
    capture: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    if output.exists() and any(output.iterdir()):
        raise ScopeLimitCaptureStop("output directory is not empty")
    output.mkdir(parents=True, exist_ok=True)

    increment_9j._write_csv(output / "step637_fixed_scan.csv", capture["fixed_rows"])
    increment_9j._write_csv(
        output / "step637_ultrafine_scan.csv", capture["ultrafine_rows"]
    )
    increment_9j._write_csv(
        output / "step637_broad_endpoint_scan.csv", capture["broad_rows"]
    )
    increment_9j._write_csv(
        output / "step637_lower_boundary_refinement.csv",
        capture["lower_boundary_rows"],
    )
    increment_9j._write_csv(
        output / "step637_upper_boundary_refinement.csv",
        capture["upper_boundary_rows"],
    )
    increment_9j._write_csv(
        output / "step637_root_topology.csv", capture["root_topology_rows"]
    )
    increment_9j._write_csv(
        output / "step637_selected_root.csv",
        [] if capture["selected_root"] is None else [capture["selected_root"]],
    )
    increment_9j._write_csv(
        output / "step637_stagnation_pressure_endpoint_bisection.csv",
        capture["p0_bisection_rows"],
    )
    increment_9j._write_csv(
        output / "step637_velocity_endpoint_bisection.csv",
        capture["velocity_bisection_rows"],
    )
    increment_9j._write_csv(
        output / "step637_stagnation_pressure_endpoint.csv",
        [] if capture["p0_endpoint"] is None else [capture["p0_endpoint"]],
    )
    increment_9j._write_csv(
        output / "step637_velocity_endpoint.csv",
        []
        if capture["velocity_endpoint"] is None
        else [capture["velocity_endpoint"]],
    )

    np.savez_compressed(
        output / "step637_state_identity.npz",
        U_before=np.asarray(capture["U"], dtype=float),
        U_after=np.asarray(capture["U_after"], dtype=float),
        solver_step_before=np.asarray(
            [increment_9j.EXPECTED_STEP], dtype=np.int64
        ),
        solver_step_after=np.asarray(
            [increment_9j.EXPECTED_STEP], dtype=np.int64
        ),
        solver_time_before_s=np.asarray([increment_9j.EXPECTED_TIME_S]),
        solver_time_after_s=np.asarray([increment_9j.EXPECTED_TIME_S]),
    )
    (output / "authority_verification.json").write_text(
        json.dumps(
            {
                "source_sha": increment_9j.PARENT_SOURCE_SHA,
                "workflow_run": increment_9j.PARENT_RUN,
                "job": increment_9j.PARENT_JOB,
                "artifact": increment_9j.PARENT_ARTIFACT,
                "artifact_name": increment_9j.PARENT_ARTIFACT_NAME,
                "artifact_sha256": capture["artifact_digest"],
                "internal_manifest_verified": True,
                "state_identity_verified": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 9J fail-closed scope capture\n\n"
        "The fixed Increment 9J diagnostic reached its expected unsupported "
        "classification. The exception was caught only to materialize the "
        "already-computed `_run` frame as immutable evidence. No scan count, "
        "gate, root, state, flux, or solver step was changed. The resulting "
        "project decision is scope limitation and fail-closed hold at accepted "
        "step 637.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n" for name in BASE_OUTPUT_NAMES
        ),
        encoding="utf-8",
    )


def _finish_scope_decision(
    *,
    output: Path,
    summary: dict[str, Any],
    scope_decision_spec: Path,
) -> dict[str, Any]:
    summary_path = output / "summary.json"
    corrected_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if corrected_summary["outcome"] != EXPECTED_CLASSIFICATION:
        raise ScopeLimitCaptureStop("schema postprocess changed scope outcome")

    conditions = corrected_summary["zero_flow_compatibility_conditions"]
    failed_conditions = corrected_summary[
        "failed_zero_flow_compatibility_conditions"
    ]
    formal_false = (
        "finite_compression_branch_approved",
        "multi_step_finite_compression_continuation_authorized",
        "full_two_l_over_c0_passed",
        "formal_state_promoted",
        "u3_b2_finite_pipe_execution_complete",
        "single_phase_finite_pipe_coupling_verified",
        "u3_b2_verification_benchmark_accepted",
        "physical_validation",
        "design_use_acceptance",
        "production_hem_activation_approved",
    )
    formal_boundary_preserved = all(
        corrected_summary[name] is False for name in formal_false
    )
    capture_gate = bool(
        corrected_summary[
            "broad_candidate_stagnation_schema_correction_gate_passed"
        ]
        and corrected_summary["scope_limit_supported"] is True
        and corrected_summary["scope_limit_decision_complete"] is True
        and corrected_summary["ultrafine_continuation_gate_passed"] is False
        and corrected_summary["zero_flow_endpoint_gate_passed"] is False
        and corrected_summary["fvm_step_638_attempted"] is False
        and corrected_summary["state_unchanged"] is True
        and corrected_summary["fixed_scan_node_count"] == 12
        and corrected_summary["ultrafine_node_count"]
        == increment_9j.ULTRAFINE_NODE_COUNT
        and corrected_summary["broad_node_count"]
        == increment_9j.BROAD_NODE_COUNT
        and bool(failed_conditions)
        and all(conditions[name] is False for name in failed_conditions)
        and formal_boundary_preserved
    )

    decision = {
        "decision": SCOPE_OUTCOME,
        "status": "FAIL_CLOSED_SCOPE_LIMIT_CAPTURED",
        "unsupported_precursor_run": PRECURSOR_RUN,
        "unsupported_precursor_job": PRECURSOR_JOB,
        "unsupported_precursor_source_git_sha": PRECURSOR_SOURCE_SHA,
        "diagnostic_stop_classification": EXPECTED_CLASSIFICATION,
        "diagnostic_stop_message": EXPECTED_MESSAGE,
        "ultrafine_continuation_supported": False,
        "zero_flow_branch_review_supported": False,
        "scope_limit_supported": True,
        "recommended_next_action": "SCOPE_LIMIT_AND_HOLD",
        "additional_root_scan_refinement_authorized": False,
        "step_638_authorized": False,
        "zero_flow_branch_implementation_authorized": False,
        "accepted_trajectory_ends_at_step": increment_9j.EXPECTED_STEP,
        "accepted_trajectory_ends_at_time_s": increment_9j.EXPECTED_TIME_S,
        "zero_flow_compatibility_conditions": conditions,
        "failed_zero_flow_compatibility_conditions": failed_conditions,
        "broad_candidate_schema_correction_gate_passed": corrected_summary[
            "broad_candidate_stagnation_schema_correction_gate_passed"
        ],
        "failed_b1_state_used_as_compatibility_root_endpoint": False,
        "failed_b1_state_used_to_construct_flux": False,
        "state_unchanged": corrected_summary["state_unchanged"],
        "fvm_step_638_attempted": corrected_summary["fvm_step_638_attempted"],
        "formal_boundary_preserved": formal_boundary_preserved,
        "scan_node_counts_changed": False,
        "tolerances_changed": False,
        "chi_scope_changed": False,
        "hugoniot_equations_changed": False,
        "b1_changed": False,
        "production_adapter_changed": False,
        "fvm_solver_changed": False,
        "locked_contract_changed": False,
        "scope_decision_spec": str(scope_decision_spec),
        "scope_decision_spec_sha256": _sha256(scope_decision_spec),
        "scope_capture_gate_passed": capture_gate,
    }
    (output / SCOPE_DECISION_FILE).write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    corrected_summary.update(
        {
            "scope_decision_artifact": SCOPE_DECISION_FILE,
            "scope_decision_spec": str(scope_decision_spec),
            "scope_decision_spec_sha256": _sha256(scope_decision_spec),
            "scope_capture_gate_passed": capture_gate,
            "formal_boundary_preserved": formal_boundary_preserved,
        }
    )
    summary_path.write_text(
        json.dumps(corrected_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = output / "report.md"
    report.write_text(
        report.read_text(encoding="utf-8")
        + "\n## Final scope decision\n\n"
        + "Increment 9J supports neither an outward compatibility-root "
        + "continuation nor a zero-flow branch review under the retained gates. "
        + "The A1 working vertical slice therefore ends at accepted step 637 "
        + "for this trajectory and must fail closed at the unresolved near-zero-"
        + "flow transition. A passing capture gate records this limitation; it "
        + "does not promote verification, acceptance, validation, or design use.\n\n"
        + "```json\n"
        + json.dumps(decision, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    names = sorted(
        {
            path.name
            for path in output.iterdir()
            if path.is_file() and path.name != "artifact_sha256.txt"
        }
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    final_files = {path.name for path in output.iterdir() if path.is_file()}
    expected = set(BASE_OUTPUT_NAMES) | {
        "artifact_sha256.txt",
        schema_correction.CORRECTION_FILE,
        SCOPE_DECISION_FILE,
    }
    if final_files != expected:
        raise ScopeLimitCaptureStop(
            f"unexpected final scope-capture evidence set: {sorted(final_files)}"
        )
    if not capture_gate:
        raise ScopeLimitCaptureStop("scope-limit capture gate failed")
    return corrected_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--authority-correction-spec", type=Path, required=True)
    parser.add_argument("--schema-correction-spec", type=Path, required=True)
    parser.add_argument("--scope-decision-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (
        args.contract,
        args.b1_contract,
        args.model_review_spec,
        args.authority_correction_spec,
        args.schema_correction_spec,
        args.scope_decision_spec,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    original_argv = sys.argv
    capture: dict[str, Any] | None = None
    try:
        sys.argv = [
            original_argv[0],
            "--contract",
            str(args.contract),
            "--b1-contract",
            str(args.b1_contract),
            "--model-review-spec",
            str(args.model_review_spec),
            "--authority-correction-spec",
            str(args.authority_correction_spec),
            "--schema-correction-spec",
            str(args.schema_correction_spec),
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
            schema_correction.main()
        except increment_9j.ZeroFlowEndpointDiagnosticStop as exc:
            capture = _capture_locals(exc)
        else:
            raise ScopeLimitCaptureStop(
                "Increment 9J unexpectedly produced a supported classification"
            )
    finally:
        sys.argv = original_argv

    if capture is None:
        raise ScopeLimitCaptureStop("unsupported Increment 9J state was not captured")

    summary = _build_summary(
        capture=capture,
        source_git_sha=args.source_git_sha,
        model_review_spec=args.model_review_spec,
        authority_correction_spec=args.authority_correction_spec,
        schema_correction_spec=args.schema_correction_spec,
        scope_decision_spec=args.scope_decision_spec,
    )
    _write_base_evidence(
        output=args.output_dir,
        capture=capture,
        summary=summary,
    )
    schema_correction._postprocess(
        output_dir=args.output_dir,
        contract_path=args.contract,
        model_review_spec=args.model_review_spec,
        authority_correction_spec=args.authority_correction_spec,
        schema_correction_spec=args.schema_correction_spec,
    )
    final_summary = _finish_scope_decision(
        output=args.output_dir,
        summary=summary,
        scope_decision_spec=args.scope_decision_spec,
    )
    print(json.dumps(final_summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
