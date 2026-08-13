from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_guard_front_8_step as runner
import u3_b2_a1_finite_compression_guard_front_8_step_dynamic_topology_fix  # noqa: F401


PARENT_SOURCE_SHA = "c3368b99c7429490feba0b86d1605138f80e29d5"
PARENT_RUN = 31663509236
PARENT_JOB = 94333135976
PARENT_ARTIFACT = 9167066290
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-8c-dynamic-31663509236"
)
PARENT_DIGEST = (
    "faa90e1c4968e9cbed1b615726d6080c90ec100b9bf6f6ebb78069e32ba43611"
)
PARENT_OUTCOME = "FINITE_COMPRESSION_INCREMENT_8C_GUARD_FRONT_8_STEP_PASS"
STARTING_STEP = 502
FINAL_STEP = 534
REQUESTED_STEPS = 32
STARTING_TIME_S = 0.0033640121156822815
OUTCOME = "FINITE_COMPRESSION_INCREMENT_8D_DYNAMIC_32_STEP_PASS"

PARENT_REQUIRED_FILES = {
    "finite_compression_steps.csv",
    "finite_compression_roots.csv",
    "hugoniot_fixed_scans.csv",
    "guard_front_refinement.csv",
    "root_topology.csv",
    "hugoniot_density_search.csv",
    "branch_sequence.csv",
    "finite_compression_8_step_states.npz",
    "authority_verification.json",
    "stop_evidence.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}

OUTPUT_STATE_OLD = "finite_compression_8_step_states.npz"
OUTPUT_STATE_NEW = "finite_compression_32_step_states.npz"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        rows = [{"no_rows_recorded": True}]
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _verify_parent(
    directory: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str], dict[str, str]]:
    if artifact_digest != PARENT_DIGEST:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C GitHub artifact digest mismatch",
        )
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"Increment 8C file set mismatch: {sorted(actual)}",
        )

    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise runner.ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 8C internal SHA256 mismatch for {name}",
            )

    summary = json.loads(
        (directory / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": PARENT_OUTCOME,
        "increment_8c_8_step_gate_passed": True,
        "starting_solver_step": 494,
        "accepted_steps_completed": 8,
        "final_solver_step": STARTING_STEP,
        "final_solver_time_s": STARTING_TIME_S,
        "branch_transition_count": 0,
        "stop_classification": None,
        "stop_reason": None,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise runner.ShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 8C summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(directory / OUTPUT_STATE_OLD) as states:
        U_after = np.asarray(states["U_after"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_after.shape != (32, 4):
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8C final state shape is not (32, 4)",
        )
    if step_after != STARTING_STEP or time_after != STARTING_TIME_S:
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8C solver identity mismatch",
        )
    if not np.all(np.isfinite(U_after)):
        raise runner.ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 8C final state contains nonfinite values",
        )
    rho = np.asarray(U_after[:, 0], dtype=float)
    velocity = np.asarray(U_after[:, 1] / rho, dtype=float)
    internal = np.asarray(U_after[:, 2] / rho - 0.5 * velocity**2, dtype=float)
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise runner.ShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 8C final density or internal energy is nonpositive",
        )
    if not np.all(U_after[:, 3] == 0.0):
        raise runner.ShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 8C final rho*xv is not exact zero",
        )

    step_rows = _read_csv(directory / "finite_compression_steps.csv")
    root_rows = _read_csv(directory / "finite_compression_roots.csv")
    if len(step_rows) != 8 or len(root_rows) != 8:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C step/root row count mismatch",
        )
    last_step = step_rows[-1]
    last_root = root_rows[-1]
    if int(last_step["solver_step_count"]) != STARTING_STEP:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C last accepted step is not 502",
        )
    if float(last_step["time_after_s"]) != STARTING_TIME_S:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C last-step time mismatch",
        )
    if last_step.get("accepted_step") != "True" or last_step.get(
        "increment_8c_per_step_gate_passed"
    ) != "True":
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C last accepted-step gate did not pass",
        )
    if int(last_root["requested_solver_step"]) != STARTING_STEP:
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C last root is not for requested step 502",
        )
    if last_root.get("root_gate_passed") != "True":
        raise runner.ShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 8C last selected-root gate did not pass",
        )

    parent_root = dict(last_root)
    parent_root["pressure_pa"] = last_root["root_pressure_pa"]
    return summary, U_after, last_step, parent_root


def _postprocess(output: Path) -> dict[str, Any]:
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    base_gate = bool(summary.pop("increment_8c_8_step_gate_passed"))
    summary.pop("solver_step_503_authorized", None)
    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_finite_compression_increment_8d"
            ),
            "scope": (
                "model_review_thirty_two_actual_dynamic_hugoniot_steps"
            ),
            "increment_8d_32_step_gate_passed": base_gate,
            "outcome": OUTCOME if base_gate else "INCREMENT_8D_STOPPED",
            "solver_step_535_authorized": False,
            "checkpoint_step_524_recorded": False,
            "previous_route_step_524_comparison_status": (
                "PENDING_SEPARATE_REVIEW"
            ),
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

    step_path = output / "finite_compression_steps.csv"
    step_rows: list[dict[str, Any]] = _read_csv(step_path)
    for row in step_rows:
        old_gate = row.pop("increment_8c_per_step_gate_passed", None)
        row["increment_8d_per_step_gate_passed"] = old_gate == "True"
    _write_csv(step_path, step_rows)

    root_rows = _read_csv(output / "finite_compression_roots.csv")
    checkpoint_steps = [
        row for row in step_rows if int(row["solver_step_count"]) == 524
    ]
    checkpoint_roots = [
        row for row in root_rows if int(row["requested_solver_step"]) == 524
    ]
    if len(checkpoint_steps) == 1 and len(checkpoint_roots) == 1:
        checkpoint = {
            "route": "CORRECTED_DYNAMIC_ROOT_TOPOLOGY",
            "source_git_sha": summary.get("source_git_sha"),
            "solver_step": 524,
            "step": checkpoint_steps[0],
            "root": checkpoint_roots[0],
            "comparison_status": "PENDING_SEPARATE_REVIEW",
        }
        (output / "step524_checkpoint.json").write_text(
            json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        summary["checkpoint_step_524_recorded"] = True

    old_state = output / OUTPUT_STATE_OLD
    new_state = output / OUTPUT_STATE_NEW
    if old_state.is_file():
        old_state.replace(new_state)

    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Increment 8D dynamic 32-step finite-compression checkpoint\n\n"
        "The authoritative corrected step-502 state was loaded. Before every "
        "actual `FvmSolver` update, the evolving outlet state was classified "
        "with the corrected dynamic root topology. A fixed successful-domain "
        "bracket was used directly when available; otherwise the retained B1 "
        "unavailable/success front was refined before constructing one "
        "successful-domain root bracket. Failed B1 states never formed a root "
        "endpoint or applied flux. The run crosses step 524 and records that "
        "checkpoint for a separate old/new route comparison. Formal project "
        "states remain false.\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )

    names = (
        "finite_compression_steps.csv",
        "finite_compression_roots.csv",
        "hugoniot_fixed_scans.csv",
        "guard_front_refinement.csv",
        "root_topology.csv",
        "hugoniot_density_search.csv",
        "branch_sequence.csv",
        OUTPUT_STATE_NEW,
        "authority_verification.json",
        "stop_evidence.json",
        "step524_checkpoint.json",
        "summary.json",
        "report.md",
    )
    missing = [name for name in names if not (output / name).is_file()]
    if missing:
        summary["increment_8d_32_step_gate_passed"] = False
        summary["outcome"] = "INCREMENT_8D_STOPPED"
        summary["postprocess_missing_files"] = missing
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(output / name)}  {name}\n"
            for name in names
            if (output / name).is_file()
        ),
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
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    runner.PARENT_SOURCE_SHA = PARENT_SOURCE_SHA
    runner.PARENT_RUN = PARENT_RUN
    runner.PARENT_JOB = PARENT_JOB
    runner.PARENT_ARTIFACT = PARENT_ARTIFACT
    runner.PARENT_ARTIFACT_NAME = PARENT_ARTIFACT_NAME
    runner.PARENT_DIGEST = PARENT_DIGEST
    runner.PARENT_OUTCOME = PARENT_OUTCOME
    runner.STARTING_STEP = STARTING_STEP
    runner.FINAL_STEP = FINAL_STEP
    runner.REQUESTED_STEPS = REQUESTED_STEPS
    runner.STARTING_TIME_S = STARTING_TIME_S
    runner.OUTCOME = OUTCOME
    runner.PARENT_REQUIRED_FILES = set(PARENT_REQUIRED_FILES)
    runner._verify_parent = _verify_parent

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
            runner.main()
        except SystemExit as exc:
            base_exit = exc
    finally:
        sys.argv = original_argv

    if not (args.output_dir / "summary.json").is_file():
        if base_exit is not None:
            raise base_exit
        raise SystemExit("Increment 8D base runner did not create summary evidence")

    summary = _postprocess(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_8d_32_step_gate_passed"]:
        raise SystemExit(
            "Increment 8D 32-step gate did not pass: "
            f"{summary.get('stop_classification')} {summary.get('stop_reason')}"
        )


if __name__ == "__main__":
    main()
