"""Working Tool v0-B one-solve canonical authoritative regression harness."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

import u3_b2_a1_working_tool_w2_regression as w2reg
from liquid_gas_transient.working_tool.backend import WorkingToolBackend
from liquid_gas_transient.working_tool.case_io import load_case_file
from liquid_gas_transient.working_tool.operation_policy import (
    WorkingToolOperationPolicy,
)
from liquid_gas_transient.working_tool.output import (
    RESULT_FILENAMES,
    write_result_package,
)
from liquid_gas_transient.working_tool.output_v0_b import (
    V0_B_RUN_FILENAMES,
    write_v0_b_result_package,
)
from liquid_gas_transient.working_tool.results import (
    BackendRunData,
    PROVISIONAL_WARNING_CODE,
    WorkingToolResult,
)
from liquid_gas_transient.working_tool.runtime import execute_case
from liquid_gas_transient.working_tool.storage_projection import (
    SAMPLE_AXIS_STATE_ARRAYS,
    STATIC_STATE_ARRAYS,
    project_state_storage,
)
from u3_b2_a1_working_tool_w2_full_horizon_backend import (
    A2FullHorizonWorkingToolBackend,
    EXPECTED_ACCEPTED_STEPS,
    EXPECTED_TARGET_TIME_S,
)


OUTCOME = "WORKING_TOOL_V0_B_CANONICAL_AUTHORITATIVE_REGRESSION_PASS"
SAMPLED_INTERVALS = (10, 64, 100, 1000)
EXPECTED_SAMPLE_COUNTS = {10: 65, 64: 11, 100: 8, 1000: 2}
STARTED_AT = datetime(2026, 8, 14, 6, 15, 30, tzinfo=timezone.utc)
COMPLETED_AT = datetime(2026, 8, 14, 6, 35, 30, tzinfo=timezone.utc)
FORBIDDEN_PUBLIC_MANIFEST_KEYS = frozenset(
    {
        "workflow_id",
        "workflow_run_id",
        "job_id",
        "artifact_id",
        "artifact_digest",
        "a2_authority",
        "parent_authority",
        "exact_regression_pass",
        "exact_regression_passed",
        "mismatch_count",
        "mismatch_counts",
        "context_restoration_evidence",
        "pytest_result",
        "ci_success",
        "verification_approval",
    }
)


class ReplayBackend(WorkingToolBackend):
    """Replay a completed full result without a second physical solve."""

    def __init__(self, result: WorkingToolResult) -> None:
        self.result = result
        self.calls = 0

    def run_case(self, case) -> BackendRunData:
        self.calls += 1
        backend_warnings = tuple(
            warning
            for warning in self.result.warnings
            if warning.code != PROVISIONAL_WARNING_CODE
        )
        return BackendRunData(
            summary=dict(self.result.summary),
            history=tuple(dict(row) for row in self.result.history),
            transitions=tuple(self.result.transitions),
            state_history={
                name: np.array(value, copy=True)
                for name, value in self.result.state_history.items()
            },
            warnings=backend_warnings,
        )


def _load_v0_a_cli(repository_root: Path):
    path = repository_root / "tools" / "working_tool" / "run_working_tool_v0_a.py"
    spec = importlib.util.spec_from_file_location("v0_a_cli_for_v0_b_regression", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load v0-A CLI: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _mapping_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_mapping_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            keys.update(_mapping_keys(nested))
    return keys


def _compare_public_core(expected_dir: Path, actual_dir: Path) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    comparison["summary.json"] = {
        "exact_match": json.loads((expected_dir / "summary.json").read_text())
        == json.loads((actual_dir / "summary.json").read_text())
    }
    for filename in ("history.csv", "transitions.csv", "warnings.csv"):
        comparison[filename] = {
            "exact_match": (expected_dir / filename).read_bytes()
            == (actual_dir / filename).read_bytes()
        }
    with np.load(expected_dir / "state_history.npz") as expected:
        with np.load(actual_dir / "state_history.npz") as actual:
            names = sorted(set(expected.files) | set(actual.files))
            arrays = {}
            for name in names:
                present = name in expected.files and name in actual.files
                arrays[name] = {
                    "exact_match": bool(
                        present
                        and expected[name].dtype == actual[name].dtype
                        and expected[name].shape == actual[name].shape
                        and np.array_equal(expected[name], actual[name])
                    )
                }
            comparison["state_history.npz"] = {
                "array_comparison": arrays,
                "exact_match": all(row["exact_match"] for row in arrays.values()),
            }
    return comparison


def _sampled_gate(
    *,
    full_dir: Path,
    sampled_dir: Path,
    expected_samples: int,
) -> dict[str, Any]:
    full_summary = json.loads((full_dir / "summary.json").read_text())
    sampled_summary = json.loads((sampled_dir / "summary.json").read_text())
    scalar_files_exact = {
        filename: (full_dir / filename).read_bytes()
        == (sampled_dir / filename).read_bytes()
        for filename in ("history.csv", "transitions.csv", "warnings.csv")
    }
    with np.load(full_dir / "state_history.npz") as full:
        with np.load(sampled_dir / "state_history.npz") as sampled:
            final_arrays_exact = {
                name: bool(np.array_equal(sampled[name][-1], full[name][-1]))
                for name in SAMPLE_AXIS_STATE_ARRAYS
            }
            static_arrays_exact = {
                name: bool(np.array_equal(sampled[name], full[name]))
                for name in STATIC_STATE_ARRAYS
            }
            sample_count = int(sampled["time_s"].shape[0])
            initial_exact = all(
                np.array_equal(sampled[name][0], full[name][0])
                for name in SAMPLE_AXIS_STATE_ARRAYS
            )
    manifest = json.loads((sampled_dir / "run_manifest.json").read_text())
    public_keys = _mapping_keys(manifest)
    gate = bool(
        full_summary == sampled_summary
        and all(scalar_files_exact.values())
        and sample_count == expected_samples
        and initial_exact
        and all(final_arrays_exact.values())
        and all(static_arrays_exact.values())
        and not (public_keys & FORBIDDEN_PUBLIC_MANIFEST_KEYS)
        and manifest["storage"]["sampling_applied_after_solver"] is True
        and manifest["storage"]["runtime_state_capture_mode"] == "FULL"
        and manifest["formal_status"]["verified"] is False
        and manifest["formal_status"]["accepted"] is False
        and manifest["formal_status"]["physically_validated"] is False
        and manifest["formal_status"]["design_use_accepted"] is False
        and manifest["formal_status"]["production_approved"] is False
    )
    return {
        "gate_passed": gate,
        "solver_summary_mismatch_count": int(full_summary != sampled_summary),
        "scalar_file_mismatch_count": sum(
            not exact for exact in scalar_files_exact.values()
        ),
        "expected_state_samples": expected_samples,
        "actual_state_samples": sample_count,
        "initial_state_exact": initial_exact,
        "final_state_mismatch_count": sum(
            not exact for exact in final_arrays_exact.values()
        ),
        "static_array_mismatch_count": sum(
            not exact for exact in static_arrays_exact.values()
        ),
        "public_verification_key_count": len(
            public_keys & FORBIDDEN_PUBLIC_MANIFEST_KEYS
        ),
    }


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

    case = load_case_file(args.case)
    backend = A2FullHorizonWorkingToolBackend(
        contract_path=args.contract,
        b1_contract_path=args.b1_contract,
    )

    # The only fresh physical solve in this harness.
    full_result = execute_case(case, backend)
    if backend.solver_instances_created != 1:
        raise RuntimeError("authoritative harness did not create exactly one solver")
    evidence = backend.runtime_evidence
    if evidence is None:
        raise RuntimeError("authoritative runtime evidence was not retained")

    runtime_dir = w2reg._write_runtime_evidence(args.output_dir, evidence)
    _write_json(args.output_dir / "resolved_case.json", case.as_dict())

    authority = json.loads(args.a2_authority_json.read_text(encoding="utf-8"))
    parent_summary = json.loads(
        (args.a2_artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    authority_passed = w2reg._authority_gate(authority, parent_summary)
    _write_json(args.output_dir / "parent_authority_verification.json", authority)

    field_comparison = {
        name: {
            "a2": parent_summary.get(name),
            "v0_b": evidence.summary.get(name),
            "exact_match": evidence.summary.get(name) == parent_summary.get(name),
        }
        for name in w2reg.EXACT_SUMMARY_FIELDS
    }
    csv_comparison = {
        name: {
            "a2_sha256": w2reg._sha256(args.a2_artifact_dir / name),
            "v0_b_sha256": w2reg._sha256(runtime_dir / name),
            "exact_match": w2reg._sha256(args.a2_artifact_dir / name)
            == w2reg._sha256(runtime_dir / name),
        }
        for name in w2reg.EXACT_CSV_FILES
    }
    npz_comparison = w2reg._compare_npz(
        runtime_dir / "initial_and_final_states.npz",
        args.a2_artifact_dir / "initial_and_final_states.npz",
    )

    legacy_dir = args.output_dir / "legacy-v0-a-direct-result"
    write_result_package(full_result, legacy_dir)
    legacy_public_passed, legacy_public_details = w2reg._public_result_gate(legacy_dir)

    full_dir = args.output_dir / "v0-b-full-result"
    full_dir.mkdir()
    full_projection = project_state_storage(full_result, 1)
    full_package = write_v0_b_result_package(
        case=case,
        policy=WorkingToolOperationPolicy.explicit(full_dir),
        projection=full_projection,
        output_dir=full_dir,
        published_directory_name=full_dir.name,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
        local_run_id="00000000000000000000000000000001",
    )
    full_core_comparison = _compare_public_core(legacy_dir, full_dir)
    full_core_mismatch_count = sum(
        not row["exact_match"] for row in full_core_comparison.values()
    )
    full_manifest = json.loads((full_dir / "run_manifest.json").read_text())
    full_keys = _mapping_keys(full_manifest)
    full_package_gate = bool(
        sorted(path.name for path in full_dir.iterdir())
        == sorted(V0_B_RUN_FILENAMES)
        and full_projection.full_state_samples == EXPECTED_ACCEPTED_STEPS + 1
        and full_projection.stored_state_samples == EXPECTED_ACCEPTED_STEPS + 1
        and full_core_mismatch_count == 0
        and full_package.core_total_bytes == full_manifest["core_total_bytes"]
        and not (full_keys & FORBIDDEN_PUBLIC_MANIFEST_KEYS)
        and full_manifest["result"]["accepted_steps"] == EXPECTED_ACCEPTED_STEPS
        and full_manifest["result"]["final_time_s"] == EXPECTED_TARGET_TIME_S
        and full_manifest["result"]["target_reached"] is True
    )

    sampled_gates: dict[str, Any] = {}
    for interval in SAMPLED_INTERVALS:
        sampled_dir = args.output_dir / f"v0-b-sampled-{interval}"
        sampled_dir.mkdir()
        projection = project_state_storage(full_result, interval)
        write_v0_b_result_package(
            case=case,
            policy=WorkingToolOperationPolicy.explicit(
                sampled_dir,
                state_sample_interval_accepted_steps=interval,
            ),
            projection=projection,
            output_dir=sampled_dir,
            published_directory_name=sampled_dir.name,
            started_at_utc=STARTED_AT,
            completed_at_utc=COMPLETED_AT,
            local_run_id=f"{interval:032x}",
        )
        sampled_gates[str(interval)] = _sampled_gate(
            full_dir=full_dir,
            sampled_dir=sampled_dir,
            expected_samples=EXPECTED_SAMPLE_COUNTS[interval],
        )

    repository_root = Path(__file__).resolve().parents[2]
    v0_a_cli = _load_v0_a_cli(repository_root)
    replay = ReplayBackend(full_result)
    legacy_cli_dir = args.output_dir / "legacy-v0-a-cli-result"
    cli_stdout = io.StringIO()
    cli_stderr = io.StringIO()
    with redirect_stdout(cli_stdout), redirect_stderr(cli_stderr):
        cli_return_code = v0_a_cli.main(
            [
                "--case",
                str(args.case),
                "--output-dir",
                str(legacy_cli_dir),
            ],
            backend_factory=lambda: replay,
        )
    (args.output_dir / "legacy_v0_a_cli_stdout.json").write_text(
        cli_stdout.getvalue(), encoding="utf-8"
    )
    (args.output_dir / "legacy_v0_a_cli_stderr.txt").write_text(
        cli_stderr.getvalue(), encoding="utf-8"
    )
    legacy_cli_comparison = _compare_public_core(legacy_dir, legacy_cli_dir)
    legacy_cli_gate = bool(
        cli_return_code == 0
        and replay.calls == 1
        and sorted(path.name for path in legacy_cli_dir.iterdir())
        == sorted(RESULT_FILENAMES)
        and all(row["exact_match"] for row in legacy_cli_comparison.values())
    )

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
    exact_a2 = bool(
        authority_passed
        and execution_gate
        and manager_gate
        and all(row["exact_match"] for row in field_comparison.values())
        and all(row["exact_match"] for row in csv_comparison.values())
        and all(row["exact_match"] for row in npz_comparison.values())
    )
    regression_passed = bool(
        exact_a2
        and legacy_public_passed
        and legacy_cli_gate
        and full_package_gate
        and all(row["gate_passed"] for row in sampled_gates.values())
    )

    regression: dict[str, Any] = {
        "schema_version": "stage7_u3_b2_a1_working_tool_v0_b_regression_v1",
        "source_git_sha": args.source_git_sha,
        "outcome": OUTCOME if regression_passed else "WORKING_TOOL_V0_B_REGRESSION_FAIL",
        "fresh_physical_solve_count": backend.solver_instances_created,
        "a2_source_git_sha": w2reg.A2_SOURCE_SHA,
        "a2_workflow_run": w2reg.A2_RUN_ID,
        "a2_workflow_job": w2reg.A2_JOB_ID,
        "a2_artifact_id": w2reg.A2_ARTIFACT_ID,
        "a2_artifact_sha256": w2reg.A2_ARTIFACT_SHA256,
        "parent_authority_gate_passed": authority_passed,
        "full_horizon_execution_gate_passed": execution_gate,
        "manager_and_restoration_gate_passed": manager_gate,
        "exact_summary_field_comparison": field_comparison,
        "exact_csv_comparison": csv_comparison,
        "exact_npz_array_comparison": npz_comparison,
        "exact_a2_behavioral_regression_passed": exact_a2,
        "legacy_v0_a_public_gate_passed": legacy_public_passed,
        "legacy_v0_a_public_details": legacy_public_details,
        "legacy_v0_a_cli_five_file_gate_passed": legacy_cli_gate,
        "full_core_file_comparison": full_core_comparison,
        "full_core_mismatch_count": full_core_mismatch_count,
        "v0_b_full_package_gate_passed": full_package_gate,
        "sampled_storage_gates": sampled_gates,
        "sampled_solver_summary_mismatch_count": sum(
            row["solver_summary_mismatch_count"] for row in sampled_gates.values()
        ),
        "sampled_final_state_mismatch_count": sum(
            row["final_state_mismatch_count"] for row in sampled_gates.values()
        ),
        "public_evidence_separation_passed": bool(
            not (full_keys & FORBIDDEN_PUBLIC_MANIFEST_KEYS)
            and all(
                row["public_verification_key_count"] == 0
                for row in sampled_gates.values()
            )
        ),
        "runtime_memory_optimized": False,
        "streaming_capable": False,
        "arbitrary_input_supported": False,
        "verified": False,
        "accepted": False,
        "physically_validated": False,
        "design_use_accepted": False,
        "production_approved": False,
    }
    _write_json(args.output_dir / "v0_b_behavioral_regression.json", regression)
    (args.output_dir / "report.md").write_text(
        "# Working Tool v0-B authoritative canonical regression\n\n"
        "One fresh A2/W2 solve produced one full WorkingToolResult. The harness "
        "then projected FULL and sampled public packages, and replayed the same "
        "result through the unchanged v0-A CLI without another physical solve.\n\n"
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
