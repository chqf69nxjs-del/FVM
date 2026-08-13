from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_step635_seeded_island_diagnostic as base


CORRECTION_PARENT_SOURCE_SHA = "c7dddb08c6bbeff911d25408f607431cc220c2c0"
CORRECTION_PARENT_RUN = 31668979089
CORRECTION_PARENT_JOB = 94349560941
CORRECTION_SCOPE = (
    "retain_boundary_invariants_after_adjacent_binary64_resolution"
)


class FloatResolutionCorrectionStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _corrected_refine_boundary(
    *,
    curve: Any,
    excluded_row: dict[str, Any],
    success_row: dict[str, Any],
    lower_excluded: bool,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    excluded = dict(excluded_row)
    success = dict(success_row)
    excluded_chi = float(excluded["requested_chi"])
    success_chi = float(success["requested_chi"])
    if not base._is_excluded(excluded) or not base.inc8a._is_success(success):
        classification = (
            "LOWER_BOUNDARY_REFINEMENT_FAILURE"
            if lower_excluded
            else "UPPER_BOUNDARY_REFINEMENT_FAILURE"
        )
        raise base.SeededIslandDiagnosticStop(
            classification,
            f"invalid initial corrected {label} boundary bracket",
        )

    if lower_excluded:
        lo = excluded_chi
        hi = success_chi
    else:
        lo = success_chi
        hi = excluded_chi
    if not lo < hi:
        classification = (
            "LOWER_BOUNDARY_REFINEMENT_FAILURE"
            if lower_excluded
            else "UPPER_BOUNDARY_REFINEMENT_FAILURE"
        )
        raise base.SeededIslandDiagnosticStop(
            classification,
            f"corrected {label} boundary coordinates are not ordered",
        )

    rows: list[dict[str, Any]] = []
    hold_started = False
    for iteration in range(1, base.BOUNDARY_ITERATIONS + 1):
        mid_chi = float(0.5 * (lo + hi))
        if not lo < mid_chi < hi:
            if float(np.nextafter(lo, hi)) != hi:
                classification = (
                    "LOWER_BOUNDARY_REFINEMENT_FAILURE"
                    if lower_excluded
                    else "UPPER_BOUNDARY_REFINEMENT_FAILURE"
                )
                raise base.SeededIslandDiagnosticStop(
                    classification,
                    f"{label} midpoint collapsed before adjacent binary64 values",
                )
            hold_started = True
            rows.append(
                {
                    "row_role": f"{label.upper()}_ISLAND_BOUNDARY",
                    "boundary_iteration": iteration,
                    "boundary_action": "FLOAT_RESOLUTION_HOLD",
                    "candidate_evaluated": False,
                    "boundary_classification": "FLOAT_RESOLUTION_HOLD",
                    "lower_chi_after": lo,
                    "upper_chi_after": hi,
                    "boundary_width_after": hi - lo,
                    "adjacent_representable_values": True,
                    "root_topology_member": False,
                    "root_topology_order": None,
                }
            )
            continue
        if hold_started:
            classification = (
                "LOWER_BOUNDARY_REFINEMENT_FAILURE"
                if lower_excluded
                else "UPPER_BOUNDARY_REFINEMENT_FAILURE"
            )
            raise base.SeededIslandDiagnosticStop(
                classification,
                f"{label} produced a midpoint after resolution hold began",
            )

        mid = curve.evaluate(
            mid_chi,
            f"increment_9g_corrected_{label}_boundary",
        )
        mid_class = base._classification(mid)
        if lower_excluded:
            if mid_class == "ADMISSIBLE_SUCCESS":
                hi = mid_chi
                success = dict(mid)
            else:
                lo = mid_chi
                excluded = dict(mid)
        else:
            if mid_class == "ADMISSIBLE_SUCCESS":
                lo = mid_chi
                success = dict(mid)
            else:
                hi = mid_chi
                excluded = dict(mid)
        rows.append(
            {
                **mid,
                "row_role": f"{label.upper()}_ISLAND_BOUNDARY",
                "boundary_iteration": iteration,
                "boundary_action": "CANDIDATE_EVALUATED",
                "candidate_evaluated": True,
                "boundary_classification": mid_class,
                "lower_chi_after": lo,
                "upper_chi_after": hi,
                "boundary_width_after": hi - lo,
                "adjacent_representable_values": bool(
                    float(np.nextafter(lo, hi)) == hi
                ),
                "root_topology_member": False,
                "root_topology_order": None,
            }
        )

    if not base._is_excluded(excluded) or not base.inc8a._is_success(success):
        classification = (
            "LOWER_BOUNDARY_REFINEMENT_FAILURE"
            if lower_excluded
            else "UPPER_BOUNDARY_REFINEMENT_FAILURE"
        )
        raise base.SeededIslandDiagnosticStop(
            classification,
            f"final corrected {label} boundary invariant failed",
        )
    if float(np.nextafter(lo, hi)) != hi:
        classification = (
            "LOWER_BOUNDARY_REFINEMENT_FAILURE"
            if lower_excluded
            else "UPPER_BOUNDARY_REFINEMENT_FAILURE"
        )
        raise base.SeededIslandDiagnosticStop(
            classification,
            f"final corrected {label} boundary is not adjacent representable",
        )
    return excluded, success, rows


def _boundary_stats(rows: list[dict[str, str]]) -> dict[str, Any]:
    evaluated = [
        row for row in rows if row.get("boundary_action") == "CANDIDATE_EVALUATED"
    ]
    holds = [
        row for row in rows if row.get("boundary_action") == "FLOAT_RESOLUTION_HOLD"
    ]
    return {
        "logical_iteration_count": len(rows),
        "candidate_evaluated_iteration_count": len(evaluated),
        "float_resolution_hold_iteration_count": len(holds),
        "first_float_resolution_hold_iteration": (
            None if not holds else int(holds[0]["boundary_iteration"])
        ),
        "final_lower_chi": float(rows[-1]["lower_chi_after"]),
        "final_upper_chi": float(rows[-1]["upper_chi_after"]),
        "final_width_chi": float(rows[-1]["boundary_width_after"]),
        "final_adjacent_representable_values": bool(
            rows[-1]["adjacent_representable_values"] == "True"
        ),
    }


def _postprocess(
    *,
    output: Path,
    correction_spec: Path,
) -> dict[str, Any]:
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    lower_rows = _read_csv(output / "step635_lower_boundary_refinement.csv")
    upper_rows = _read_csv(output / "step635_upper_boundary_refinement.csv")
    lower_stats = _boundary_stats(lower_rows)
    upper_stats = _boundary_stats(upper_rows)
    gate = bool(
        summary["increment_9g_diagnostic_gate_passed"]
        and lower_stats["logical_iteration_count"] == base.BOUNDARY_ITERATIONS
        and upper_stats["logical_iteration_count"] == base.BOUNDARY_ITERATIONS
        and lower_stats["float_resolution_hold_iteration_count"] > 0
        and upper_stats["float_resolution_hold_iteration_count"] > 0
        and lower_stats["final_adjacent_representable_values"]
        and upper_stats["final_adjacent_representable_values"]
        and summary["state_unchanged"] is True
        and summary["fvm_step_636_attempted"] is False
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_finite_compression_increment_9g_rerun"
            ),
            "scope": (
                "diagnostic_only_seeded_island_binary64_resolution_corrected"
            ),
            "float_resolution_boundary_correction_applied": True,
            "float_resolution_boundary_correction_scope": CORRECTION_SCOPE,
            "lower_boundary_resolution_statistics": lower_stats,
            "upper_boundary_resolution_statistics": upper_stats,
            "correction_parent_source_sha": CORRECTION_PARENT_SOURCE_SHA,
            "correction_parent_run": CORRECTION_PARENT_RUN,
            "correction_parent_job": CORRECTION_PARENT_JOB,
            "correction_spec_sha256": _sha256(correction_spec),
            "increment_9g_rerun_gate_passed": gate,
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
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    authority = {
        "scope": CORRECTION_SCOPE,
        "parent_failed_diagnostic": {
            "source_sha": CORRECTION_PARENT_SOURCE_SHA,
            "workflow_run": CORRECTION_PARENT_RUN,
            "job": CORRECTION_PARENT_JOB,
            "failure": "lower boundary midpoint collapsed",
            "artifact": None,
        },
        "b1_behavior_changed": False,
        "local_admissibility_rule_changed": False,
        "candidate_category_changed": False,
        "root_tolerance_changed": False,
        "diagnostic_interval_or_nodes_changed": False,
        "failed_or_inadmissible_state_used_as_root_endpoint": False,
        "failed_or_inadmissible_state_used_to_construct_flux": False,
    }
    (output / "float_resolution_correction_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Binary64 boundary-resolution correction\n\n"
        + "Both categorical boundaries were evaluated until their endpoints "
        + "became adjacent representable binary64 values. Remaining logical "
        + "iterations retained the endpoint invariants without evaluating or "
        + "classifying a new candidate. No tolerance, candidate category, root "
        + "endpoint or flux rule changed.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step635_fixed_scan.csv",
        "step635_seeded_interval_scan.csv",
        "step635_lower_boundary_refinement.csv",
        "step635_upper_boundary_refinement.csv",
        "step635_root_topology.csv",
        "step635_hugoniot_density_search.csv",
        "step635_selected_root.csv",
        "step635_state_identity.npz",
        "authority_verification.json",
        "float_resolution_correction_authority.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--correction-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.correction_spec.is_file():
        raise FileNotFoundError(args.correction_spec)
    base._refine_boundary = _corrected_refine_boundary

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
            base.main()
        except SystemExit as exc:
            base_exit = exc
    finally:
        sys.argv = original_argv

    if not (args.output_dir / "summary.json").is_file():
        if base_exit is not None:
            raise base_exit
        raise FloatResolutionCorrectionStop(
            "base corrected diagnostic did not create summary evidence"
        )
    summary = _postprocess(
        output=args.output_dir,
        correction_spec=args.correction_spec,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9g_rerun_gate_passed"]:
        raise SystemExit("Increment 9G corrected rerun gate did not pass")
    if not summary["actual_continuation_supported"]:
        raise SystemExit(
            "Increment 9G corrected rerun did not support continuation: "
            f"{summary['outcome']}"
        )


if __name__ == "__main__":
    main()
