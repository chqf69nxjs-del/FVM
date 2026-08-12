from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_weak_compression_bridge_full_horizon_guard_front_refined as base


_ORIGINAL_POSTPROCESS = base._postprocess_output
CORRECTION_SCOPE = (
    "per_step_any_fixed_unavailable_outcome_and_global_nonpositive_reproduction"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corrected_postprocess_output(
    *,
    output_dir: Path,
    increment_4e_summary: dict[str, Any],
    failed_increment_4d_summary: dict[str, Any],
    failed_increment_4d_artifact_dir: Path,
) -> dict[str, Any]:
    summary = _ORIGINAL_POSTPROCESS(
        output_dir=output_dir,
        increment_4e_summary=increment_4e_summary,
        failed_increment_4d_summary=failed_increment_4d_summary,
        failed_increment_4d_artifact_dir=failed_increment_4d_artifact_dir,
    )
    roots = base._read_csv(
        output_dir / "full_horizon_continuation_roots.csv"
    )
    refined = [
        row
        for row in roots
        if row.get("guard_front_refinement_applied") == "True"
    ]
    reproduction = dict(summary["pre_guard_front_reproduction"])
    first_refinement_step = (
        min(int(row["requested_solver_step"]) for row in refined)
        if refined
        else None
    )
    total_nonpositive = sum(
        int(row["guard_front_nonpositive_head_count"])
        for row in refined
    )
    total_reverse_pressure = sum(
        int(row["guard_front_reverse_pressure_count"])
        for row in refined
    )
    total_success = sum(
        int(row["guard_front_success_count"])
        for row in refined
    )

    corrected_refinement_gate = bool(
        refined
        and first_refinement_step == base.FIRST_GUARD_FRONT_REFINEMENT_STEP
        and all(
            int(row["guard_front_reverse_pressure_count"])
            + int(row["guard_front_nonpositive_head_count"])
            > 0
            for row in refined
        )
        and total_nonpositive > 0
        and all(
            int(row["guard_front_success_count"]) > 0
            for row in refined
        )
        and all(
            float(row["guard_front_final_lower_offset_pa"])
            < float(row["guard_front_final_upper_offset_pa"])
            for row in refined
        )
        and all(
            float(row["guard_front_final_width_pa"]) > 0.0
            for row in refined
        )
        and all(
            float(row["guard_front_refined_success_residual_kg_s"])
            >= -base.robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            for row in refined
        )
        and all(
            float(row[
                "guard_front_refined_success_stagnation_margin_pa"
            ]) > 0.0
            for row in refined
        )
        and all(
            row["failed_b1_state_used_as_root_endpoint"] == "False"
            for row in refined
        )
        and all(
            row["failed_b1_state_used_to_construct_flux"] == "False"
            for row in refined
        )
        and all(
            float(row["root_static_pressure_minus_back_pa"]) > 0.0
            for row in refined
        )
        and all(
            float(row["root_stagnation_pressure_minus_back_pa"]) > 0.0
            for row in refined
        )
    )
    corrected_working_slice_gate = bool(
        summary["working_vertical_slice_two_l_over_c0_passed"]
        and reproduction["passed"]
        and corrected_refinement_gate
    )
    original_refinement_gate = bool(
        summary["guard_front_refinement_gate_passed"]
    )
    original_working_slice_gate = bool(
        summary["increment_4f_working_slice_gate_passed"]
    )
    summary.update(
        {
            "original_guard_front_refinement_gate_passed": (
                original_refinement_gate
            ),
            "original_increment_4f_working_slice_gate_passed": (
                original_working_slice_gate
            ),
            "guard_front_refinement_evidence_gate_correction_applied": True,
            "guard_front_refinement_evidence_gate_correction_scope": (
                CORRECTION_SCOPE
            ),
            "guard_front_refinement_total_reverse_pressure_count": int(
                total_reverse_pressure
            ),
            "guard_front_refinement_total_nonpositive_head_count": int(
                total_nonpositive
            ),
            "guard_front_refinement_total_success_count": int(total_success),
            "guard_front_refinement_each_step_has_unavailable_state": bool(
                refined
                and all(
                    int(row["guard_front_reverse_pressure_count"])
                    + int(row["guard_front_nonpositive_head_count"])
                    > 0
                    for row in refined
                )
            ),
            "guard_front_refinement_global_nonpositive_reproduced": bool(
                total_nonpositive > 0
            ),
            "guard_front_refinement_gate_passed": (
                corrected_refinement_gate
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
        "original_refinement_gate": original_refinement_gate,
        "corrected_refinement_gate": corrected_refinement_gate,
        "original_working_slice_gate": original_working_slice_gate,
        "corrected_working_slice_gate": corrected_working_slice_gate,
        "refined_step_count": len(refined),
        "total_reverse_pressure_count": total_reverse_pressure,
        "total_nonpositive_head_count": total_nonpositive,
        "total_success_count": total_success,
        "b1_behavior_changed": False,
        "failed_state_used_as_root_endpoint": False,
        "failed_state_used_to_construct_flux": False,
        "tolerance_or_scope_changed": False,
    }
    (output_dir / "refinement_evidence_gate_correction.json").write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Refinement evidence-gate correction\n\n"
        + "The physical/root continuation was not changed. The corrected "
        + "aggregation requires each refined step to retain at least one of "
        + "the two fixed B1-unavailable formal outcomes, while requiring the "
        + "authoritative nonpositive-kinetic-head outcome to be reproduced at "
        + "least once across the complete evidence. All failed B1 states "
        + "remain unusable as root endpoints or applied fluxes.\n\n"
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
    parser.add_argument(
        "--evidence-gate-correction-spec",
        type=Path,
        required=True,
    )
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
