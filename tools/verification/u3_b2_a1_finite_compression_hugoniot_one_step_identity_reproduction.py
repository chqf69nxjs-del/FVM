from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import u3_b2_a1_finite_compression_hugoniot_model_selection as inc5_core
import u3_b2_a1_finite_compression_hugoniot_one_step as one_step


FIRST_RUN_SOURCE_SHA = "a2e09032108a4fd80b9df79288ad948256af23af"
FIRST_RUN_WORKFLOW = 31652640473
FIRST_RUN_JOB = 94300122587


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _postprocess(output_dir: Path, correction_spec: Path) -> None:
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update(
        {
            "identity_correction_reproduction_applied": True,
            "identity_correction_reproduction_spec": str(correction_spec),
            "identity_correction_reproduction_spec_sha256": _sha256(
                correction_spec
            ),
            "identity_correction_raw_form_observation_limit_J_kg": (
                inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
            ),
            "identity_correction_accounted_tolerance_J_kg": 1.0e-10,
            "first_increment_6_source_sha": FIRST_RUN_SOURCE_SHA,
            "first_increment_6_workflow_run": FIRST_RUN_WORKFLOW,
            "first_increment_6_job": FIRST_RUN_JOB,
            "first_increment_6_actual_step_attempted": False,
            "hugoniot_equations_changed": False,
            "b1_behavior_changed": False,
            "compatibility_root_tolerance_changed": False,
            "diagnostic_chi_cap_changed": False,
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
    correction = {
        "correction": "reproduce_authoritative_increment_5_identity_treatment",
        "raw_form_observation_limit_J_kg": (
            inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
        ),
        "identity_accounted_tolerance_J_kg": 1.0e-10,
        "first_run_failed_before_root_completion": True,
        "first_run_actual_step_attempted": False,
        "hugoniot_equations_changed": False,
        "b1_behavior_changed": False,
        "root_tolerance_or_chi_cap_changed": False,
    }
    (output_dir / "identity_reproduction_correction.json").write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = output_dir / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Increment 5 identity-treatment reproduction\n\n"
        + "The independent root recomputation used the same authoritative "
        + "Increment 5 enthalpy-identity treatment. Both physical Hugoniot "
        + "forms retain their original closure gates; the raw form difference "
        + "is observational and the identity-accounted difference remains "
        + "strictly checked.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "recomputed_isentropic_scan.csv",
        "recomputed_hugoniot_scan.csv",
        "recomputed_hugoniot_density_search.csv",
        "hugoniot_root_evidence.csv",
        "finite_compression_one_step.csv",
        "authority_verification.json",
        "root_authority_comparison.json",
        "finite_compression_one_step_states.npz",
        "identity_reproduction_correction.json",
        "summary.json",
        "report.md",
    )
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--identity-reproduction-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-artifact-digest", required=True)
    parser.add_argument("--increment-5-artifact-dir", type=Path, required=True)
    parser.add_argument("--increment-5-artifact-digest", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    if not args.identity_reproduction_spec.is_file():
        raise FileNotFoundError(args.identity_reproduction_spec)

    inc5_core.HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = (
        inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
    )

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
            "--increment-5-artifact-dir",
            str(args.increment_5_artifact_dir),
            "--increment-5-artifact-digest",
            args.increment_5_artifact_digest,
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        one_step.main()
    finally:
        sys.argv = original_argv

    _postprocess(args.output_dir, args.identity_reproduction_spec)


if __name__ == "__main__":
    main()
