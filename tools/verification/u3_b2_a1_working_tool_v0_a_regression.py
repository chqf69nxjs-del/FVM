"""Working Tool v0-A JSON/CLI full-horizon regression harness."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from typing import Any

import u3_b2_a1_working_tool_w2_regression as w2reg
from liquid_gas_transient.working_tool import load_case_file
from u3_b2_a1_working_tool_w2_full_horizon_backend import (
    A2FullHorizonWorkingToolBackend,
    EXPECTED_ACCEPTED_STEPS,
    EXPECTED_TARGET_TIME_S,
)


OUTCOME = "WORKING_TOOL_V0_A_EXACT_A2_BEHAVIORAL_REGRESSION_PASS"


def _load_cli_module(repository_root: Path):
    path = repository_root / "tools" / "working_tool" / "run_working_tool_v0_a.py"
    spec = importlib.util.spec_from_file_location("working_tool_v0_a_cli", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load v0-A CLI module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--a2-artifact-dir", type=Path, required=True)
    parser.add_argument("--a2-authority-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (
        args.case,
        args.contract,
        args.b1_contract,
        args.a2_artifact_dir / "summary.json",
        args.a2_artifact_dir / "initial_and_final_states.npz",
        args.a2_authority_json,
    ):
        if not path.exists():
            raise FileNotFoundError(path)
    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    args.output_dir.mkdir(parents=True)

    repository_root = Path(__file__).resolve().parents[2]
    cli = _load_cli_module(repository_root)
    case = load_case_file(args.case)
    backend = A2FullHorizonWorkingToolBackend(
        contract_path=args.contract,
        b1_contract_path=args.b1_contract,
    )
    cli_stdout = io.StringIO()
    cli_stderr = io.StringIO()
    public_dir = args.output_dir / "public-result"
    with redirect_stdout(cli_stdout), redirect_stderr(cli_stderr):
        return_code = cli.main(
            [
                "--case",
                str(args.case),
                "--output-dir",
                str(public_dir),
            ],
            backend_factory=lambda: backend,
        )
    stdout_text = cli_stdout.getvalue()
    stderr_text = cli_stderr.getvalue()
    (args.output_dir / "cli_stdout.json").write_text(
        stdout_text,
        encoding="utf-8",
    )
    (args.output_dir / "cli_stderr.txt").write_text(
        stderr_text,
        encoding="utf-8",
    )
    if return_code != 0:
        raise RuntimeError(
            f"WORKING_TOOL_V0_A_CLI_FAILED: return_code={return_code}: {stderr_text}"
        )
    cli_completion = json.loads(stdout_text)

    evidence = backend.runtime_evidence
    if evidence is None:
        raise RuntimeError("v0-A runtime evidence was not retained")
    runtime_dir = w2reg._write_runtime_evidence(args.output_dir, evidence)
    w2reg._write_json(args.output_dir / "case.json", case.as_dict())

    authority = json.loads(args.a2_authority_json.read_text(encoding="utf-8"))
    parent_summary = json.loads(
        (args.a2_artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    authority_passed = w2reg._authority_gate(authority, parent_summary)
    w2reg._write_json(
        args.output_dir / "parent_authority_verification.json",
        authority,
    )

    field_comparison = {
        name: {
            "a2": parent_summary.get(name),
            "v0_a": evidence.summary.get(name),
            "exact_match": evidence.summary.get(name) == parent_summary.get(name),
        }
        for name in w2reg.EXACT_SUMMARY_FIELDS
    }
    csv_comparison = {
        name: {
            "a2_sha256": w2reg._sha256(args.a2_artifact_dir / name),
            "v0_a_sha256": w2reg._sha256(runtime_dir / name),
            "exact_match": w2reg._sha256(args.a2_artifact_dir / name)
            == w2reg._sha256(runtime_dir / name),
        }
        for name in w2reg.EXACT_CSV_FILES
    }
    npz_comparison = w2reg._compare_npz(
        runtime_dir / "initial_and_final_states.npz",
        args.a2_artifact_dir / "initial_and_final_states.npz",
    )
    public_passed, public_details = w2reg._public_result_gate(public_dir)

    manager_gate = bool(
        len(evidence.manager_transition_rows) == 2
        and len(evidence.manager_selection_rows) == 3
        and len(evidence.context_restoration_rows) == EXPECTED_ACCEPTED_STEPS
        and all(
            row["context_restored_without_root_reconstruction"] is True
            and row["flux_modified_by_manager"] is False
            and row["restoration_gate_passed"] is True
            for row in evidence.context_restoration_rows
        )
    )
    execution_gate = bool(
        backend.solver_instances_created == 1
        and evidence.summary["accepted_steps_completed"] == EXPECTED_ACCEPTED_STEPS
        and evidence.summary["final_solver_step"] == EXPECTED_ACCEPTED_STEPS
        and evidence.summary["final_solver_time_s"] == EXPECTED_TARGET_TIME_S
        and evidence.summary["target_two_l_over_c0_time_s"]
        == EXPECTED_TARGET_TIME_S
        and evidence.summary["horizon_time_error_s"] == 0.0
        and evidence.summary["target_horizon_reached"] is True
    )
    cli_application_gate = bool(
        return_code == 0
        and cli_completion["case_id"] == case.case_id
        and cli_completion["accepted_steps"] == EXPECTED_ACCEPTED_STEPS
        and cli_completion["final_solver_time_s"] == EXPECTED_TARGET_TIME_S
        and cli_completion["target_horizon_reached"] is True
        and cli_completion["warning_codes"]
        == [
            "PROVISIONAL_ENGINEERING_MODEL",
            "WORKING_TOOL_W2_CANONICAL_FULL_HORIZON_SCOPE",
        ]
        and stderr_text.count("PROVISIONAL ENGINEERING MODEL") == 2
        and "not VERIFIED" in stderr_text
        and "DESIGN-USE APPROVED" in stderr_text
    )
    regression_passed = bool(
        authority_passed
        and execution_gate
        and manager_gate
        and cli_application_gate
        and public_passed
        and all(row["exact_match"] for row in field_comparison.values())
        and all(row["exact_match"] for row in csv_comparison.values())
        and all(row["exact_match"] for row in npz_comparison.values())
    )

    regression: dict[str, Any] = {
        "schema_version": "stage7_u3_b2_a1_working_tool_v0_a_regression_v1",
        "source_git_sha": args.source_git_sha,
        "outcome": OUTCOME if regression_passed else "WORKING_TOOL_V0_A_REGRESSION_FAIL",
        "case_file": str(args.case),
        "case_id": case.case_id,
        "cli_return_code": return_code,
        "cli_application_gate_passed": cli_application_gate,
        "a2_source_git_sha": w2reg.A2_SOURCE_SHA,
        "a2_workflow_run": w2reg.A2_RUN_ID,
        "a2_workflow_job": w2reg.A2_JOB_ID,
        "a2_artifact_id": w2reg.A2_ARTIFACT_ID,
        "a2_artifact_name": w2reg.A2_ARTIFACT_NAME,
        "a2_artifact_sha256": w2reg.A2_ARTIFACT_SHA256,
        "parent_authority_gate_passed": authority_passed,
        "public_result_gate_passed": public_passed,
        "public_result_details": public_details,
        "full_horizon_execution_gate_passed": execution_gate,
        "manager_and_restoration_gate_passed": manager_gate,
        "exact_summary_field_comparison": field_comparison,
        "exact_csv_comparison": csv_comparison,
        "exact_npz_array_comparison": npz_comparison,
        "exact_a2_behavioral_regression_passed": regression_passed,
        "arbitrary_input_supported": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_approval": False,
    }
    w2reg._write_json(
        args.output_dir / "v0_a_behavioral_regression.json",
        regression,
    )
    (args.output_dir / "report.md").write_text(
        "# Working Tool v0-A JSON/CLI regression\n\n"
        "The canonical JSON example was loaded through the strict public case "
        "loader and executed through the repository-local CLI application path. "
        "A separate verification harness compared the retained runtime evidence "
        "with the immutable Increment 9M A2 authority.\n\n"
        "```json\n"
        + json.dumps(regression, indent=2, sort_keys=True, allow_nan=False)
        + "\n```\n",
        encoding="utf-8",
    )
    w2reg._manifest(args.output_dir)

    print(json.dumps(regression, indent=2, sort_keys=True, allow_nan=False))
    if not regression_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
