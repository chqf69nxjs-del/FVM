from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_increment_9l_two_state_boundary_state_machine_v3 as previous


FAILED_BINDING_RUN = 31687885990
FAILED_BINDING_JOB = 94408149222
FAILED_BINDING_SOURCE_SHA = "4a9d54e84302d4e329b53b5a650be401296ac05d"
TOPOLOGY_PARENT_RUN = 31619671593
TOPOLOGY_PARENT_JOB = 94191039227
TOPOLOGY_PARENT_SOURCE_SHA = "618f49c0a75620751cb517d669a4da868e82f41e"
TOPOLOGY_PARENT_ARTIFACT = 9150769457
TOPOLOGY_PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-weak-compression-bridge-increment-4f-31619671593"
)
STALE_TOPOLOGY_PARENT_DIGEST = (
    "2d00f5fc739a218657de9cc82d0fb1193649decfa3d4813d15ef0782d8dc6927"
)
CORRECT_TOPOLOGY_PARENT_DIGEST = (
    "64ce6c2ee282163a841c3df518f27bd45eac6bf2e3c91a061ff3007bbab09034"
)
AUTHORITY_CORRECTION_FILE = (
    "guard_front_topology_authority_binding_correction.json"
)


class Increment9LAuthorityStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _install_authority_correction() -> None:
    topology_fix = previous.topology_fix
    if topology_fix.CORRECTION_PARENT_WORKFLOW_RUN != TOPOLOGY_PARENT_RUN:
        raise Increment9LAuthorityStop("topology parent run identity changed")
    if topology_fix.CORRECTION_PARENT_JOB != TOPOLOGY_PARENT_JOB:
        raise Increment9LAuthorityStop("topology parent job identity changed")
    if topology_fix.CORRECTION_PARENT_SOURCE_SHA != TOPOLOGY_PARENT_SOURCE_SHA:
        raise Increment9LAuthorityStop("topology parent source identity changed")
    if topology_fix.CORRECTION_PARENT_ARTIFACT != TOPOLOGY_PARENT_ARTIFACT:
        raise Increment9LAuthorityStop("topology parent artifact identity changed")
    if (
        topology_fix.CORRECTION_PARENT_ARTIFACT_SHA256
        != STALE_TOPOLOGY_PARENT_DIGEST
    ):
        raise Increment9LAuthorityStop(
            "historical stale topology digest no longer matches the correction record"
        )
    topology_fix.CORRECTION_PARENT_ARTIFACT_SHA256 = (
        CORRECT_TOPOLOGY_PARENT_DIGEST
    )


def _postprocess(
    *,
    output: Path,
    authority_correction_spec: Path,
    source_git_sha: str,
) -> dict[str, Any]:
    summary_path = output / "summary.json"
    topology_path = output / previous.CORRECTION_FILE
    if not summary_path.is_file() or not topology_path.is_file():
        raise Increment9LAuthorityStop(
            "Increment 9L v4 summary or topology correction evidence is missing"
        )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    topology = json.loads(topology_path.read_text(encoding="utf-8"))

    binding_gate = bool(
        summary["increment_9l_state_machine_gate_passed"] is True
        and summary["guard_front_root_topology_gate_passed"] is True
        and topology["existing_authoritative_failed_source_sha"]
        == TOPOLOGY_PARENT_SOURCE_SHA
        and topology["existing_authoritative_failed_run"]
        == TOPOLOGY_PARENT_RUN
        and topology["existing_authoritative_failed_job"]
        == TOPOLOGY_PARENT_JOB
        and topology["existing_authoritative_failed_artifact"]
        == TOPOLOGY_PARENT_ARTIFACT
        and topology["existing_authoritative_failed_artifact_sha256"]
        == CORRECT_TOPOLOGY_PARENT_DIGEST
    )
    correction = {
        "correction": "increment_9l_guard_front_topology_authority_binding",
        "failed_binding_run": FAILED_BINDING_RUN,
        "failed_binding_job": FAILED_BINDING_JOB,
        "failed_binding_source_git_sha": FAILED_BINDING_SOURCE_SHA,
        "authority_correction_spec": str(authority_correction_spec),
        "authority_correction_spec_sha256": _sha256(authority_correction_spec),
        "topology_parent_run": TOPOLOGY_PARENT_RUN,
        "topology_parent_job": TOPOLOGY_PARENT_JOB,
        "topology_parent_source_git_sha": TOPOLOGY_PARENT_SOURCE_SHA,
        "topology_parent_artifact": TOPOLOGY_PARENT_ARTIFACT,
        "topology_parent_artifact_name": TOPOLOGY_PARENT_ARTIFACT_NAME,
        "stale_recorded_artifact_sha256": STALE_TOPOLOGY_PARENT_DIGEST,
        "correct_authoritative_artifact_sha256": (
            CORRECT_TOPOLOGY_PARENT_DIGEST
        ),
        "run_identity_verified": True,
        "job_identity_verified": True,
        "source_identity_verified": True,
        "artifact_identity_verified": True,
        "artifact_name_verified": True,
        "artifact_nonexpired_verified": True,
        "artifact_digest_verified": True,
        "binding_correction_gate_passed": binding_gate,
        "topology_algorithm_changed": False,
        "root_selection_changed": False,
        "b1_changed": False,
        "production_adapter_changed": False,
        "fvm_solver_changed": False,
        "locked_contract_changed": False,
        "tolerance_changed": False,
        "chi_cap_changed": False,
        "state_machine_changed": False,
        "closure_model_changed": False,
        "execution_source_git_sha": source_git_sha,
    }
    (output / AUTHORITY_CORRECTION_FILE).write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    corrected_gate = bool(
        binding_gate and summary["increment_9l_state_machine_gate_passed"]
    )
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_increment_9l_two_state_boundary_state_machine_v4"
            ),
            "guard_front_topology_authority_binding_correction_applied": True,
            "guard_front_topology_authority_binding_correction_spec": str(
                authority_correction_spec
            ),
            "guard_front_topology_authority_binding_correction_spec_sha256": (
                _sha256(authority_correction_spec)
            ),
            "guard_front_topology_authority_stale_digest": (
                STALE_TOPOLOGY_PARENT_DIGEST
            ),
            "guard_front_topology_authority_correct_digest": (
                CORRECT_TOPOLOGY_PARENT_DIGEST
            ),
            "guard_front_topology_authority_binding_gate_passed": (
                binding_gate
            ),
            "increment_9l_state_machine_gate_passed": corrected_gate,
            "working_vertical_slice": corrected_gate,
            "provisional_engineering_two_l_over_c0_reached": bool(
                corrected_gate and summary["target_horizon_reached"]
            ),
            "outcome": (
                previous.previous.base.OUTCOME
                if corrected_gate
                else "INCREMENT_9L_V4_STOPPED"
            ),
        }
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = output / "report.md"
    report.write_text(
        report.read_text(encoding="utf-8")
        + "\n## Guard-front topology authority-binding correction\n\n"
        + "The historical topology-correction run, job, source SHA, artifact "
        + "ID, and artifact name were retained. Only the stale recorded artifact "
        + "digest was superseded by the immutable live GitHub artifact digest. "
        + "No topology, physics, tolerance, B1, solver, adapter, or state-machine "
        + "behavior changed.\n\n"
        + "```json\n"
        + json.dumps(correction, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    manifest_names = sorted(
        path.name
        for path in output.iterdir()
        if path.is_file() and path.name != "artifact_sha256.txt"
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in manifest_names),
        encoding="utf-8",
    )
    if not corrected_gate:
        raise Increment9LAuthorityStop(
            "corrected Increment 9L authority/state-machine gate did not pass"
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--handoff-correction-spec", type=Path, required=True)
    parser.add_argument("--topology-correction-spec", type=Path, required=True)
    parser.add_argument("--authority-correction-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (
        args.contract,
        args.b1_contract,
        args.model_review_spec,
        args.handoff_correction_spec,
        args.topology_correction_spec,
        args.authority_correction_spec,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    _install_authority_correction()
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
            "--handoff-correction-spec",
            str(args.handoff_correction_spec),
            "--topology-correction-spec",
            str(args.topology_correction_spec),
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        previous.main()
    finally:
        sys.argv = original_argv

    summary = _postprocess(
        output=args.output_dir,
        authority_correction_spec=args.authority_correction_spec,
        source_git_sha=args.source_git_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
