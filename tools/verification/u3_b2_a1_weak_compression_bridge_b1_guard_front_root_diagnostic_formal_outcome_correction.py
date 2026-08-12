from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_weak_compression_bridge_b1_guard_front_root_diagnostic as base


CORRECTION_PARENT_SOURCE_SHA = "88e8d7f1e343bc7f6e45a7c35df585d2d73e661f"
CORRECTION_PARENT_WORKFLOW_RUN = 31617525217
CORRECTION_PARENT_JOB = 94183955040
CORRECTION_PARENT_FORMAL_OUTCOME = "NONPOSITIVE_KINETIC_ENERGY_HEAD"
REVERSE_PRESSURE_OUTCOME = "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED"
ALLOWED_UNAVAILABLE_OUTCOMES = {
    REVERSE_PRESSURE_OUTCOME,
    CORRECTION_PARENT_FORMAL_OUTCOME,
}
CORRECTION_SCOPE = (
    "requested_scan_coordinate_authoritative_guard_front_formal_outcome_correction"
)


class FormalOutcomeCorrectionStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _is_unavailable_guard_front_state(row: dict[str, Any]) -> bool:
    return bool(
        not row.get("evaluation_succeeded")
        and row.get("formal_outcome") in ALLOWED_UNAVAILABLE_OUTCOMES
    )


def _postprocess_output(
    *,
    output_dir: Path,
    correction_spec: Path,
) -> dict[str, Any]:
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    guard_rows = _read_csv(output_dir / "step451_guard_front_bisection.csv")
    if len(guard_rows) != base.GUARD_FRONT_BISECTION_ITERATIONS:
        raise FormalOutcomeCorrectionStop(
            "corrected Guard-front evidence does not contain exactly 32 rows"
        )

    reverse_pressure_count = sum(
        row.get("midpoint_formal_outcome") == REVERSE_PRESSURE_OUTCOME
        for row in guard_rows
    )
    nonpositive_head_count = sum(
        row.get("midpoint_formal_outcome")
        == CORRECTION_PARENT_FORMAL_OUTCOME
        for row in guard_rows
    )
    success_count = sum(
        row.get("midpoint_classification") == "B1_SUCCESS"
        for row in guard_rows
    )
    unavailable_count = sum(
        row.get("midpoint_classification") == "B1_GUARD"
        for row in guard_rows
    )
    unexpected_unavailable = [
        {
            "iteration": row.get("iteration"),
            "formal_outcome": row.get("midpoint_formal_outcome"),
            "formal_message": row.get("midpoint_formal_message"),
        }
        for row in guard_rows
        if row.get("midpoint_classification") == "B1_GUARD"
        and row.get("midpoint_formal_outcome")
        not in ALLOWED_UNAVAILABLE_OUTCOMES
    ]
    if unexpected_unavailable:
        raise FormalOutcomeCorrectionStop(
            f"unexpected unavailable Guard-front outcomes: {unexpected_unavailable}"
        )
    if nonpositive_head_count <= 0:
        raise FormalOutcomeCorrectionStop(
            "corrected rerun did not reproduce a NONPOSITIVE_KINETIC_ENERGY_HEAD midpoint"
        )
    if success_count <= 0 or unavailable_count <= 0:
        raise FormalOutcomeCorrectionStop(
            "corrected Guard-front evidence does not retain both unavailable and successful midpoints"
        )

    correction_gate = bool(
        summary["increment_4e_diagnostic_classification_complete"]
        and len(guard_rows) == base.GUARD_FRONT_BISECTION_ITERATIONS
        and nonpositive_head_count > 0
        and success_count > 0
        and unavailable_count > 0
        and not unexpected_unavailable
        and summary["state_unchanged"] is True
        and summary["fvm_step_452_attempted"] is False
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_4e_rerun"
            ),
            "scope": (
                "model_review_diagnostic_only_b1_guard_front_formal_outcome_correction"
            ),
            "guard_front_formal_outcome_correction_applied": True,
            "guard_front_formal_outcome_correction_scope": CORRECTION_SCOPE,
            "guard_front_unavailable_formal_outcomes": sorted(
                ALLOWED_UNAVAILABLE_OUTCOMES
            ),
            "guard_front_reverse_pressure_midpoint_count": int(
                reverse_pressure_count
            ),
            "guard_front_nonpositive_kinetic_head_midpoint_count": int(
                nonpositive_head_count
            ),
            "guard_front_success_midpoint_count": int(success_count),
            "guard_front_unavailable_midpoint_count": int(
                unavailable_count
            ),
            "guard_front_unexpected_unavailable_outcomes": unexpected_unavailable,
            "correction_parent_source_sha": CORRECTION_PARENT_SOURCE_SHA,
            "correction_parent_workflow_run": CORRECTION_PARENT_WORKFLOW_RUN,
            "correction_parent_job": CORRECTION_PARENT_JOB,
            "correction_parent_formal_outcome": (
                CORRECTION_PARENT_FORMAL_OUTCOME
            ),
            "correction_spec": str(correction_spec),
            "correction_spec_sha256": _sha256(correction_spec),
            "increment_4e_rerun_gate_passed": correction_gate,
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
        "correction_spec": str(correction_spec),
        "correction_spec_sha256": _sha256(correction_spec),
        "parent_failed_run": {
            "source_sha": CORRECTION_PARENT_SOURCE_SHA,
            "workflow_run": CORRECTION_PARENT_WORKFLOW_RUN,
            "job": CORRECTION_PARENT_JOB,
            "formal_outcome": CORRECTION_PARENT_FORMAL_OUTCOME,
            "artifact": None,
        },
        "classification": {
            "unavailable_formal_outcomes": sorted(
                ALLOWED_UNAVAILABLE_OUTCOMES
            ),
            "b1_behavior_changed": False,
            "failed_state_used_as_root_endpoint": False,
            "failed_state_used_to_construct_flux": False,
            "pressure_or_energy_tolerance_added": False,
        },
    }
    (output_dir / "correction_authority.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Guard-front formal-outcome correction\n\n"
        + "The categorical lower side of the Guard front retained both the "
        + "exact reverse-pressure Guard and `NONPOSITIVE_KINETIC_ENERGY_HEAD` "
        + "as failed B1 states. Neither outcome was converted to success, used "
        + "as a compatibility-root endpoint, or used to construct a flux. "
        + "The successful upper side and all physical/root/ledger gates remain "
        + "unchanged.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    names = (
        "step451_local_wave_scans.csv",
        "step451_fixed_positive_pressure_scans.csv",
        "step451_guard_front_bisection.csv",
        "step451_refined_success_root.csv",
        "step451_state_identity.npz",
        "correction_authority.json",
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
    parser.add_argument("--correction-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    if not args.correction_spec.is_file():
        raise FileNotFoundError(args.correction_spec)

    base._is_expected_guard = _is_unavailable_guard_front_state

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
        raise FormalOutcomeCorrectionStop(
            "base Increment 4E rerun did not create summary evidence"
        )

    summary = _postprocess_output(
        output_dir=args.output_dir,
        correction_spec=args.correction_spec,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_4e_rerun_gate_passed"]:
        raise SystemExit("Increment 4E corrected rerun gate did not pass")
    if not summary["increment_4e_continuation_supported"]:
        raise SystemExit(
            "Increment 4E corrected rerun did not support continuation: "
            f"{summary['outcome']}"
        )


if __name__ == "__main__":
    main()
