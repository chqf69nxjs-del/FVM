from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_hugoniot_8_step as base
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    load_b1_contract,
    load_contract,
)


PARENT_SOURCE_SHA = "559f34e9e578b8335295dc2ee16f975b9fdad586"
PARENT_WORKFLOW_RUN = 31653551138
PARENT_JOB = 94302870493
PARENT_ARTIFACT = 9163478011
PARENT_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-7-31653551138"
)
PARENT_ARTIFACT_SHA256 = (
    "f208ac3a5125c7cd5265af6e0b19ef7705eee85614d282a639a3263223734de1"
)
PARENT_OUTCOME = "FINITE_COMPRESSION_INCREMENT_7_HUGONIOT_8_STEP_PASS"
STARTING_SOLVER_STEP = 492
REQUESTED_ACCEPTED_STEPS = 32
FINAL_SOLVER_STEP = 524
STARTING_SOLVER_TIME_S = 0.003296941966003099
OUTCOME = "FINITE_COMPRESSION_INCREMENT_8_HUGONIOT_32_STEP_PASS"

PARENT_REQUIRED_FILES = {
    "finite_compression_steps.csv",
    "finite_compression_roots.csv",
    "hugoniot_fixed_scans.csv",
    "hugoniot_density_search.csv",
    "branch_sequence.csv",
    "finite_compression_8_step_states.npz",
    "authority_verification.json",
    "stop_evidence.json",
    "summary.json",
    "report.md",
    "artifact_sha256.txt",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_manifest(directory: Path) -> None:
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != PARENT_REQUIRED_FILES:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            f"Increment 7 file set mismatch: {sorted(actual)}",
        )
    manifest: dict[str, str] = {}
    for line in (directory / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    if set(manifest) != PARENT_REQUIRED_FILES - {"artifact_sha256.txt"}:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 internal manifest names mismatch",
        )
    for name, digest in manifest.items():
        if _sha256(directory / name) != digest:
            raise base.FiniteCompressionShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 7 internal SHA256 mismatch for {name}",
            )


def _verify_parent(
    parent_dir: Path,
    *,
    artifact_digest: str,
) -> tuple[dict[str, Any], np.ndarray, dict[str, str]]:
    if artifact_digest != PARENT_ARTIFACT_SHA256:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 GitHub artifact digest mismatch",
        )
    _verify_manifest(parent_dir)
    summary = json.loads(
        (parent_dir / "summary.json").read_text(encoding="utf-8")
    )
    expected = {
        "source_git_sha": PARENT_SOURCE_SHA,
        "outcome": PARENT_OUTCOME,
        "increment_7_eight_step_gate_passed": True,
        "accepted_steps_completed": 8,
        "final_solver_step": STARTING_SOLVER_STEP,
        "final_solver_time_s": STARTING_SOLVER_TIME_S,
        "branch_transition_count": 0,
        "clear_branch_chatter_detected": False,
        "stop_classification": None,
        "stop_reason": None,
        "finite_compression_branch_approved": False,
        "multi_step_finite_compression_continuation_authorized": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            raise base.FiniteCompressionShortRunStop(
                "PARENT_ARTIFACT_MISMATCH",
                f"Increment 7 summary mismatch for {key}: {summary.get(key)!r}",
            )

    with np.load(parent_dir / "finite_compression_8_step_states.npz") as states:
        U_final = np.asarray(states["U_final"], dtype=float).copy()
        step_after = int(states["solver_step_after"][0])
        time_after = float(states["solver_time_after_s"][0])
    if U_final.shape != (32, 4):
        raise base.FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 7 final state shape is not (32, 4)",
        )
    if step_after != STARTING_SOLVER_STEP or time_after != STARTING_SOLVER_TIME_S:
        raise base.FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 7 solver identity mismatch",
        )
    if not np.all(np.isfinite(U_final)):
        raise base.FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 7 final state contains nonfinite values",
        )
    rho = U_final[:, 0]
    velocity = U_final[:, 1] / rho
    internal = U_final[:, 2] / rho - 0.5 * velocity**2
    if not np.all(rho > 0.0) or not np.all(internal > 0.0):
        raise base.FiniteCompressionShortRunStop(
            "NONFINITE_OR_NONPOSITIVE_STATE",
            "Increment 7 final state has nonpositive density or internal energy",
        )
    if not np.all(U_final[:, 3] == 0.0):
        raise base.FiniteCompressionShortRunStop(
            "STATE_REPRODUCTION_MISMATCH",
            "Increment 7 final rho*xv is not exact zero",
        )

    step_rows = _read_csv(parent_dir / "finite_compression_steps.csv")
    root_rows = _read_csv(parent_dir / "finite_compression_roots.csv")
    if len(step_rows) != 8 or len(root_rows) != 8:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 does not contain eight step/root rows",
        )
    last_step = step_rows[-1]
    last_root = root_rows[-1]
    if int(last_step["solver_step_count"]) != STARTING_SOLVER_STEP:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 last step is not solver step 492",
        )
    if float(last_step["time_after_s"]) != STARTING_SOLVER_TIME_S:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 last-step time mismatch",
        )
    if last_step.get("accepted_step") != "True" or last_step.get(
        "increment_7_per_step_gate_passed"
    ) != "True":
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 last step did not pass",
        )
    if int(last_root["requested_solver_step"]) != STARTING_SOLVER_STEP:
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 last root is not for step 492",
        )
    if last_root.get("root_gate_passed") != "True":
        raise base.FiniteCompressionShortRunStop(
            "PARENT_ARTIFACT_MISMATCH",
            "Increment 7 last root gate did not pass",
        )
    summary = dict(summary)
    summary["root_pressure_pa"] = float(last_root["root_pressure_pa"])
    return summary, U_final, last_step


def _configure_base() -> None:
    base.PARENT_SOURCE_SHA = PARENT_SOURCE_SHA
    base.PARENT_WORKFLOW_RUN = PARENT_WORKFLOW_RUN
    base.PARENT_JOB = PARENT_JOB
    base.PARENT_ARTIFACT = PARENT_ARTIFACT
    base.PARENT_ARTIFACT_NAME = PARENT_ARTIFACT_NAME
    base.PARENT_ARTIFACT_SHA256 = PARENT_ARTIFACT_SHA256
    base.PARENT_OUTCOME = PARENT_OUTCOME
    base.STARTING_SOLVER_STEP = STARTING_SOLVER_STEP
    base.REQUESTED_ACCEPTED_STEPS = REQUESTED_ACCEPTED_STEPS
    base.FINAL_SOLVER_STEP = FINAL_SOLVER_STEP
    base.STARTING_SOLVER_TIME_S = STARTING_SOLVER_TIME_S
    base.OUTCOME = OUTCOME


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

    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)
    _configure_base()
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U_step492, parent_step_row = _verify_parent(
        args.parent_artifact_dir,
        artifact_digest=args.parent_artifact_digest,
    )
    (
        summary,
        step_rows,
        root_rows,
        scan_rows,
        density_rows,
        branch_rows,
        U_start,
        U_final,
    ) = base._run_short(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary=parent_summary,
        U_step484=U_step492,
        parent_step_row=parent_step_row,
    )
    original_gate = bool(summary.pop("increment_7_eight_step_gate_passed"))
    summary.update(
        {
            "schema_version": "stage7_u3_b2_a1_finite_compression_increment_8",
            "scope": "model_review_thirty_two_actual_fvm_steps_general_eos_hugoniot",
            "source_git_sha": args.source_git_sha,
            "model_review_spec_sha256": _sha256(args.model_review_spec),
            "increment_8_32_step_gate_passed": original_gate,
            "outcome": OUTCOME if original_gate else "INCREMENT_8_STOPPED",
            "solver_step_493_authorized": None,
            "solver_step_525_authorized": False,
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

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "finite_compression_steps.csv", step_rows)
    _write_csv(output / "finite_compression_roots.csv", root_rows)
    _write_csv(output / "hugoniot_fixed_scans.csv", scan_rows)
    _write_csv(output / "hugoniot_density_search.csv", density_rows)
    _write_csv(output / "branch_sequence.csv", branch_rows)
    np.savez_compressed(
        output / "finite_compression_32_step_states.npz",
        U_start=np.asarray(U_start, dtype=float),
        U_final=np.asarray(U_final, dtype=float),
        solver_step_before=np.asarray([STARTING_SOLVER_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["final_solver_step"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_SOLVER_TIME_S]),
        solver_time_after_s=np.asarray([summary["final_solver_time_s"]]),
    )
    authority = {
        "increment_7_parent": {
            "source_sha": PARENT_SOURCE_SHA,
            "workflow_run": PARENT_WORKFLOW_RUN,
            "job": PARENT_JOB,
            "artifact": PARENT_ARTIFACT,
            "artifact_name": PARENT_ARTIFACT_NAME,
            "artifact_sha256": PARENT_ARTIFACT_SHA256,
            "outcome": parent_summary["outcome"],
            "verified": True,
        }
    }
    (output / "authority_verification.json").write_text(
        json.dumps(authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    stop = {
        "classification": summary["stop_classification"],
        "reason": summary["stop_reason"],
        "diagnostic_keys": summary["stop_diagnostics_keys"],
    }
    (output / "stop_evidence.json").write_text(
        json.dumps(stop, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 finite-compression Increment 8\n\n"
        "MODEL_REVIEW / THIRTY_TWO ACTUAL FVM STEPS evidence. The exact "
        "authoritative Increment 7 step-492 state was loaded and verified. A "
        "new general-EOS Hugoniot and unchanged B1-compatible root were solved "
        "at each requested step. No result authorizes step 525, formal branch "
        "approval, benchmark acceptance, Physical Validation, design use, or "
        "production activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "finite_compression_steps.csv",
        "finite_compression_roots.csv",
        "hugoniot_fixed_scans.csv",
        "hugoniot_density_search.csv",
        "branch_sequence.csv",
        "finite_compression_32_step_states.npz",
        "authority_verification.json",
        "stop_evidence.json",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_8_32_step_gate_passed"]:
        raise SystemExit(
            "Increment 8 Hugoniot 32-step gate did not pass: "
            f"{summary['stop_classification']} {summary['stop_reason']}"
        )


if __name__ == "__main__":
    main()
