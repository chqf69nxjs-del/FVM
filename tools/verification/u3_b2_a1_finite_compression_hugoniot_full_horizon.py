from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from liquid_gas_transient.u3_b2_fvm_discharge_adapter import load_b1_contract, load_contract
from u3_b2_a1_finite_compression_hugoniot_full_horizon_engine import _run_full_horizon
from u3_b2_a1_finite_compression_hugoniot_full_horizon_support import (
    HORIZON_ROUNDOFF_TOLERANCE_S,
    MAXIMUM_OPERATIONAL_SOLVER_STEP,
    OUTCOME,
    PARENT_ARTIFACT,
    PARENT_ARTIFACT_NAME,
    PARENT_ARTIFACT_SHA256,
    PARENT_JOB,
    PARENT_SOURCE_SHA,
    PARENT_WORKFLOW_RUN,
    STARTING_SOLVER_STEP,
    STARTING_SOLVER_TIME_S,
    TARGET_TIME_S,
    _sha256,
    _verify_parent,
    _write_csv,
)


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
    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    parent_summary, U_step524, parent_step_row = _verify_parent(
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
    ) = _run_full_horizon(
        contract=contract,
        b1_contract=b1_contract,
        parent_summary=parent_summary,
        U_step524=U_step524,
        parent_step_row=parent_step_row,
    )
    summary["source_git_sha"] = args.source_git_sha
    summary["model_review_spec_sha256"] = _sha256(args.model_review_spec)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "finite_compression_steps.csv", step_rows)
    _write_csv(output / "finite_compression_roots.csv", root_rows)
    _write_csv(output / "hugoniot_fixed_scans.csv", scan_rows)
    _write_csv(output / "hugoniot_density_search.csv", density_rows)
    _write_csv(output / "branch_sequence.csv", branch_rows)
    np.savez_compressed(
        output / "finite_compression_full_horizon_states.npz",
        U_start=np.asarray(U_start, dtype=float),
        U_final=np.asarray(U_final, dtype=float),
        solver_step_before=np.asarray([STARTING_SOLVER_STEP], dtype=np.int64),
        solver_step_after=np.asarray([summary["final_solver_step"]], dtype=np.int64),
        solver_time_before_s=np.asarray([STARTING_SOLVER_TIME_S]),
        solver_time_after_s=np.asarray([summary["final_solver_time_s"]]),
        target_time_s=np.asarray([TARGET_TIME_S]),
        horizon_time_error_s=np.asarray([summary["horizon_time_error_s"]]),
    )
    authority = {
        "increment_8_parent": {
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
        "# U3 B2 A1 finite-compression Increment 9\n\n"
        "MODEL_REVIEW / FULL NOMINAL 2L/c0 ATTEMPT evidence. The exact "
        "authoritative Increment 8 step-524 state was loaded and verified. A "
        "new general-EOS Hugoniot and unchanged B1-compatible root were solved "
        "before every requested actual FVM step. The final accepted step was "
        "clipped to the fixed nominal target. A pass establishes a working "
        "vertical slice only and does not promote any formal project state.\n\n"
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
        "finite_compression_full_horizon_states.npz",
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
    if not summary["increment_9_full_horizon_gate_passed"]:
        raise SystemExit(
            "Increment 9 full-horizon gate did not pass: "
            f"{summary['stop_classification']} {summary['stop_reason']}"
        )


if __name__ == "__main__":
    main()
