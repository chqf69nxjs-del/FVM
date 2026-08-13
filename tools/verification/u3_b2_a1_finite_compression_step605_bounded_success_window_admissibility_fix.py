from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_finite_compression_step605_bounded_success_window_diagnostic as base


CORRECTION_PARENT_SOURCE_SHA = "efb562869058db5a092cae9656726baa35d2f13a"
CORRECTION_PARENT_RUN = 31668071341
CORRECTION_PARENT_JOB = 94346848601
CORRECTION_SCOPE = (
    "upper_boundary_excluded_side_includes_b1_success_local_inadmissible"
)


class AdmissibilityCorrectionStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _is_local_inadmissible_success(row: dict[str, Any]) -> bool:
    return bool(
        row.get("evaluation_succeeded")
        and not row.get("local_candidate_admissible")
    )


def _is_upper_excluded(row: dict[str, Any]) -> bool:
    return bool(base._is_unavailable(row) or _is_local_inadmissible_success(row))


def _corrected_refine_upper_boundary(
    *,
    curve: Any,
    lower_success: dict[str, Any],
    upper_unavailable: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    lower = dict(lower_success)
    upper = dict(upper_unavailable)
    lower_chi = float(lower["requested_chi"])
    upper_chi = float(upper["requested_chi"])
    if not base._is_success(lower) or not _is_upper_excluded(upper):
        raise AdmissibilityCorrectionStop(
            "invalid initial corrected upper-boundary bracket"
        )
    rows: list[dict[str, Any]] = []
    for iteration in range(1, base.BOUNDARY_ITERATIONS + 1):
        mid_chi = float(0.5 * (lower_chi + upper_chi))
        if not lower_chi < mid_chi < upper_chi:
            raise AdmissibilityCorrectionStop(
                "corrected upper-boundary midpoint collapsed"
            )
        mid = curve.evaluate(mid_chi, "increment_9e_corrected_upper_boundary")
        if base._is_success(mid):
            classification = "B1_SUCCESS_LOCAL_ADMISSIBLE"
            lower_chi = mid_chi
            lower = dict(mid)
        elif base._is_unavailable(mid):
            classification = "B1_UNAVAILABLE"
            upper_chi = mid_chi
            upper = dict(mid)
        elif _is_local_inadmissible_success(mid):
            classification = "B1_SUCCESS_LOCAL_INADMISSIBLE"
            upper_chi = mid_chi
            upper = dict(mid)
        else:
            raise AdmissibilityCorrectionStop(
                "unexpected corrected upper-boundary outcome: "
                f"{mid.get('formal_outcome')} {mid.get('formal_message')}"
            )
        rows.append(
            {
                **mid,
                "row_role": "UPPER_SUCCESS_WINDOW_BOUNDARY",
                "boundary_iteration": iteration,
                "boundary_classification": classification,
                "lower_success_chi_after": lower_chi,
                "upper_excluded_chi_after": upper_chi,
                "boundary_width_after": upper_chi - lower_chi,
                "root_topology_member": False,
                "root_topology_order": None,
            }
        )
    if not base._is_success(lower) or not _is_upper_excluded(upper):
        raise AdmissibilityCorrectionStop(
            "final corrected upper-boundary invariant failed"
        )
    return lower, upper, rows


def _postprocess(
    *,
    output: Path,
    correction_spec: Path,
) -> dict[str, Any]:
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    upper_rows = _read_csv(output / "step605_upper_boundary_refinement.csv")
    if len(upper_rows) != base.BOUNDARY_ITERATIONS:
        raise AdmissibilityCorrectionStop(
            "corrected upper-boundary evidence does not contain 48 rows"
        )
    unavailable_count = sum(
        row.get("boundary_classification") == "B1_UNAVAILABLE"
        for row in upper_rows
    )
    inadmissible_success_count = sum(
        row.get("boundary_classification")
        == "B1_SUCCESS_LOCAL_INADMISSIBLE"
        for row in upper_rows
    )
    admissible_success_count = sum(
        row.get("boundary_classification")
        == "B1_SUCCESS_LOCAL_ADMISSIBLE"
        for row in upper_rows
    )
    unexpected = [
        {
            "iteration": row.get("boundary_iteration"),
            "classification": row.get("boundary_classification"),
            "formal_outcome": row.get("formal_outcome"),
            "local_candidate_admissible": row.get(
                "local_candidate_admissible"
            ),
        }
        for row in upper_rows
        if row.get("boundary_classification")
        not in {
            "B1_UNAVAILABLE",
            "B1_SUCCESS_LOCAL_INADMISSIBLE",
            "B1_SUCCESS_LOCAL_ADMISSIBLE",
        }
    ]
    gate = bool(
        summary["increment_9e_diagnostic_gate_passed"]
        and inadmissible_success_count > 0
        and admissible_success_count > 0
        and not unexpected
        and summary["state_unchanged"] is True
        and summary["fvm_step_606_attempted"] is False
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_finite_compression_increment_9e_rerun"
            ),
            "scope": (
                "diagnostic_only_bounded_b1_and_local_admissibility_window"
            ),
            "upper_boundary_local_admissibility_correction_applied": True,
            "upper_boundary_local_admissibility_correction_scope": (
                CORRECTION_SCOPE
            ),
            "upper_boundary_b1_unavailable_midpoint_count": int(
                unavailable_count
            ),
            "upper_boundary_b1_success_local_inadmissible_midpoint_count": int(
                inadmissible_success_count
            ),
            "upper_boundary_b1_success_local_admissible_midpoint_count": int(
                admissible_success_count
            ),
            "upper_boundary_unexpected_classifications": unexpected,
            "correction_parent_source_sha": CORRECTION_PARENT_SOURCE_SHA,
            "correction_parent_run": CORRECTION_PARENT_RUN,
            "correction_parent_job": CORRECTION_PARENT_JOB,
            "correction_spec_sha256": _sha256(correction_spec),
            "increment_9e_rerun_gate_passed": gate,
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
            "observed_formal_outcome": "SUCCESS_UNCHOKED_FACE_MAPPING",
            "observed_local_candidate_admissible": False,
            "artifact": None,
        },
        "b1_behavior_changed": False,
        "local_admissibility_rule_changed": False,
        "failed_or_inadmissible_state_used_as_root_endpoint": False,
        "failed_or_inadmissible_state_used_to_construct_flux": False,
        "tolerance_or_scope_changed": False,
    }
    (output / "admissibility_correction_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Upper-boundary local-admissibility correction\n\n"
        + "The upper excluded side retained both exact B1-unavailable states "
        + "and B1-success/local-inadmissible states. Neither category was used "
        + "as a root-topology node, compatibility-root endpoint or applied "
        + "flux. B1 behavior, local admissibility rules, tolerances and scope "
        + "remain unchanged.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "step605_fixed_scan.csv",
        "step605_lower_boundary_refinement.csv",
        "step605_upper_boundary_refinement.csv",
        "step605_root_topology.csv",
        "step605_hugoniot_density_search.csv",
        "step605_selected_root.csv",
        "step605_state_identity.npz",
        "authority_verification.json",
        "admissibility_correction_authority.json",
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
    base._refine_upper_boundary = _corrected_refine_upper_boundary

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
        raise AdmissibilityCorrectionStop(
            "base corrected diagnostic did not create summary evidence"
        )
    summary = _postprocess(
        output=args.output_dir,
        correction_spec=args.correction_spec,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_9e_rerun_gate_passed"]:
        raise SystemExit("Increment 9E corrected rerun gate did not pass")
    if not summary["actual_continuation_supported"]:
        raise SystemExit(
            "Increment 9E corrected rerun did not support continuation: "
            f"{summary['outcome']}"
        )


if __name__ == "__main__":
    main()
