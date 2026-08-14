"""Working Tool W2 external full-horizon regression harness."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

import u3_b2_a1_increment_9l_two_state_boundary_state_machine as base
import u3_b2_a1_working_tool_w1_a2_live_backend as w1
from liquid_gas_transient.working_tool import (
    PROVISIONAL_WARNING_CODE,
    RESULT_FILENAMES,
    execute_case,
    write_result_package,
)
from u3_b2_a1_working_tool_w2_full_horizon_backend import (
    A2FullHorizonWorkingToolBackend,
    EXPECTED_ACCEPTED_STEPS,
    EXPECTED_TARGET_TIME_S,
    W2_FULL_HORIZON_WARNING_CODE,
)


A2_SOURCE_SHA = "947b0f0bf006e8015c3c109e57a8aeb7460cca02"
A2_RUN_ID = 31719604102
A2_JOB_ID = 94512927800
A2_ARTIFACT_ID = 9189445884
A2_ARTIFACT_NAME = "u3-b2-a1-increment-9m-a2-31719604102"
A2_ARTIFACT_SHA256 = (
    "4678ecd9f919ea513bed16652a1fe5b484d6c664b74209bf7dbaffa2dc0a2b64"
)
OUTCOME = "WORKING_TOOL_W2_EXACT_A2_BEHAVIORAL_REGRESSION_PASS"


EXACT_SUMMARY_FIELDS = (
    "starting_state_sha256",
    "final_state_sha256",
    "accepted_steps_completed",
    "final_solver_step",
    "final_solver_time_s",
    "target_two_l_over_c0_time_s",
    "horizon_time_error_s",
    "horizon_fraction_reached",
    "public_boundary_state_counts",
    "outward_internal_model_counts",
    "outward_branch_counts",
    "public_state_transition_count",
    "boundary_transition_event_count",
    "outward_model_transition_event_count",
    "maximum_halving_count",
    "maximum_absolute_step_mass_residual_kg",
    "maximum_absolute_step_momentum_residual_kg_m_s",
    "maximum_absolute_step_energy_residual_J",
    "maximum_absolute_cumulative_mass_residual_kg",
    "maximum_absolute_cumulative_momentum_residual_kg_m_s",
    "maximum_absolute_cumulative_energy_residual_J",
    "minimum_density_kg_m3",
    "minimum_internal_energy_J_kg",
    "maximum_absolute_velocity_m_s",
    "final_all_phases_allowed",
    "final_normalized_phases",
    "final_rho_xv_exact_zero",
    "final_outlet_pressure_pa",
    "final_outlet_velocity_m_s",
    "final_outlet_mach",
    "final_outlet_phase",
    "right_mass_transfer_exact_zero_all_closed_steps",
    "right_energy_transfer_exact_zero_all_closed_steps",
    "right_vapor_transfer_exact_zero_all_closed_steps",
    "wall_momentum_identity_exact_all_closed_steps",
)


EXACT_CSV_FILES = (
    "step_metrics.csv",
    "boundary_state_history.csv",
    "outward_model_transition_events.csv",
    "boundary_transition_events.csv",
    "three_branch_algorithm_transition_events.csv",
    "finite_compression_bounded_window_fallback_events.csv",
    "guard_front_root_topology_correction_events.csv",
    "model_manager_transition_events.csv",
    "model_manager_selection_history.csv",
    "model_manager_context_restoration.csv",
)


FORBIDDEN_PUBLIC_KEYS = (
    "workflow_run",
    "workflow_job",
    "artifact_id",
    "artifact_sha256",
    "parent_workflow_run",
    "parent_workflow_job",
    "parent_artifact_id",
    "parent_artifact_sha256",
    "exact_increment_9l_behavioral_equivalence_passed",
    "increment_9m_a2_exact_increment_9l_behavioral_equivalence_passed",
    "exact_a2_behavioral_regression_passed",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_runtime_evidence(output: Path, evidence: Any) -> Path:
    runtime = output / "runtime-evidence"
    runtime.mkdir(parents=True, exist_ok=True)
    rows_by_name = {
        "step_metrics.csv": evidence.step_rows,
        "boundary_state_history.csv": evidence.state_rows,
        "outward_model_transition_events.csv": (
            evidence.outward_model_transition_rows
        ),
        "boundary_transition_events.csv": evidence.boundary_transition_rows,
        "three_branch_algorithm_transition_events.csv": (
            evidence.three_branch_algorithm_rows
        ),
        "finite_compression_bounded_window_fallback_events.csv": (
            evidence.bounded_window_rows
        ),
        "guard_front_root_topology_correction_events.csv": (
            evidence.guard_front_topology_rows
        ),
        "model_manager_transition_events.csv": evidence.manager_transition_rows,
        "model_manager_selection_history.csv": evidence.manager_selection_rows,
        "model_manager_context_restoration.csv": (
            evidence.context_restoration_rows
        ),
    }
    for name, rows in rows_by_name.items():
        base._write_csv(runtime / name, [dict(row) for row in rows])

    np.savez(
        runtime / "initial_and_final_states.npz",
        U_initial=np.asarray(evidence.U_initial, dtype=float),
        U_final=np.asarray(evidence.U_final, dtype=float),
        solver_step_initial=np.asarray([0], dtype=np.int64),
        solver_step_final=np.asarray([EXPECTED_ACCEPTED_STEPS], dtype=np.int64),
        solver_time_initial_s=np.asarray([0.0], dtype=float),
        solver_time_final_s=np.asarray([EXPECTED_TARGET_TIME_S], dtype=float),
        target_time_s=np.asarray([EXPECTED_TARGET_TIME_S], dtype=float),
    )
    np.savez_compressed(
        runtime / "accepted_state_history.npz",
        time_s=np.asarray(evidence.accepted_time_snapshots_s, dtype=float),
        conserved=np.asarray(evidence.accepted_state_snapshots, dtype=float),
    )
    _write_json(runtime / "runtime_summary.json", evidence.summary)
    return runtime


def _authority_gate(
    authority: Mapping[str, Any],
    parent_summary: Mapping[str, Any],
) -> bool:
    expected_digest = f"sha256:{A2_ARTIFACT_SHA256}"
    return bool(
        authority.get("live_metadata_verified") is True
        and authority.get("source_git_sha") == A2_SOURCE_SHA
        and int(authority.get("workflow_run")) == A2_RUN_ID
        and int(authority.get("workflow_job")) == A2_JOB_ID
        and authority.get("run_conclusion") == "success"
        and authority.get("job_conclusion") == "success"
        and int(authority.get("artifact_id")) == A2_ARTIFACT_ID
        and authority.get("artifact_name") == A2_ARTIFACT_NAME
        and authority.get("artifact_digest") == expected_digest
        and authority.get("artifact_sha256") == A2_ARTIFACT_SHA256
        and authority.get("archive_sha256") == A2_ARTIFACT_SHA256
        and authority.get("artifact_expired") is False
        and parent_summary.get("source_git_sha") == A2_SOURCE_SHA
        and parent_summary.get(
            "increment_9m_a2_exact_increment_9l_behavioral_equivalence_passed"
        )
        is True
    )


def _compare_npz(actual_path: Path, parent_path: Path) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    with np.load(actual_path) as actual, np.load(parent_path) as parent:
        keys = sorted(set(actual.files) | set(parent.files))
        for name in keys:
            actual_present = name in actual.files
            parent_present = name in parent.files
            if actual_present and parent_present:
                actual_array = np.asarray(actual[name])
                parent_array = np.asarray(parent[name])
                exact = bool(
                    actual_array.dtype == parent_array.dtype
                    and actual_array.shape == parent_array.shape
                    and np.array_equal(actual_array, parent_array)
                )
                comparison[name] = {
                    "actual_present": True,
                    "parent_present": True,
                    "actual_dtype": str(actual_array.dtype),
                    "parent_dtype": str(parent_array.dtype),
                    "actual_shape": list(actual_array.shape),
                    "parent_shape": list(parent_array.shape),
                    "exact_match": exact,
                }
            else:
                comparison[name] = {
                    "actual_present": actual_present,
                    "parent_present": parent_present,
                    "exact_match": False,
                }
    return comparison


def _public_result_gate(public_dir: Path) -> tuple[bool, dict[str, Any]]:
    files = sorted(path.name for path in public_dir.iterdir() if path.is_file())
    summary = json.loads((public_dir / "summary.json").read_text(encoding="utf-8"))
    transition_rows = _read_csv(public_dir / "transitions.csv")
    history_rows = _read_csv(public_dir / "history.csv")
    with np.load(public_dir / "state_history.npz") as arrays:
        state_gate = bool(
            arrays["time_s"].shape == (EXPECTED_ACCEPTED_STEPS + 1,)
            and arrays["conserved"].shape
            == (EXPECTED_ACCEPTED_STEPS + 1, 32, 4)
            and float(arrays["time_s"][-1]) == EXPECTED_TARGET_TIME_S
        )
    gate = bool(
        files == sorted(RESULT_FILENAMES)
        and len(history_rows) == EXPECTED_ACCEPTED_STEPS
        and len(transition_rows) == 2
        and all(
            row["absolute_step_number_trigger_used"] == "False"
            for row in transition_rows
        )
        and summary["accepted_steps"] == EXPECTED_ACCEPTED_STEPS
        and summary["full_two_l_over_c0_execution_completed"] is True
        and summary["target_horizon_reached"] is True
        and summary["horizon_time_error_s"] == 0.0
        and summary["a2_behavioral_regression_tested"] is False
        and summary["verified"] is False
        and summary["accepted"] is False
        and summary["validated"] is False
        and summary["design_use_approved"] is False
        and summary["warning_codes"]
        == [PROVISIONAL_WARNING_CODE, W2_FULL_HORIZON_WARNING_CODE]
        and not any(key in summary for key in FORBIDDEN_PUBLIC_KEYS)
        and state_gate
    )
    details = {
        "files": files,
        "history_row_count": len(history_rows),
        "transition_row_count": len(transition_rows),
        "warning_codes": summary.get("warning_codes"),
        "formal_authority_false": all(
            summary[name] is False
            for name in (
                "verified",
                "accepted",
                "validated",
                "design_use_approved",
            )
        ),
        "verification_metadata_absent": not any(
            key in summary for key in FORBIDDEN_PUBLIC_KEYS
        ),
        "state_history_gate_passed": state_gate,
        "gate_passed": gate,
    }
    return gate, details


def _manifest(output: Path) -> None:
    names = sorted(
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path.name != "artifact_sha256.txt"
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--a2-artifact-dir", type=Path, required=True)
    parser.add_argument("--a2-authority-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (
        args.contract,
        args.b1_contract,
        args.a2_artifact_dir / "summary.json",
        args.a2_artifact_dir / "initial_and_final_states.npz",
        args.a2_authority_json,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    case = w1.build_canonical_w1_case(
        args.contract,
        case_id="W2-A2-FULL-HORIZON-CANONICAL",
    )
    backend = A2FullHorizonWorkingToolBackend(
        contract_path=args.contract,
        b1_contract_path=args.b1_contract,
    )
    result = execute_case(case, backend)
    public_dir = write_result_package(result, output / "public-result")
    evidence = backend.runtime_evidence
    if evidence is None:
        raise RuntimeError("W2 runtime evidence was not retained")
    runtime_dir = _write_runtime_evidence(output, evidence)
    _write_json(output / "case.json", case.as_dict())

    authority = json.loads(args.a2_authority_json.read_text(encoding="utf-8"))
    parent_summary = json.loads(
        (args.a2_artifact_dir / "summary.json").read_text(encoding="utf-8")
    )
    authority_passed = _authority_gate(authority, parent_summary)
    _write_json(output / "parent_authority_verification.json", authority)

    field_comparison = {
        name: {
            "a2": parent_summary.get(name),
            "w2": evidence.summary.get(name),
            "exact_match": evidence.summary.get(name) == parent_summary.get(name),
        }
        for name in EXACT_SUMMARY_FIELDS
    }
    csv_comparison = {
        name: {
            "a2_sha256": _sha256(args.a2_artifact_dir / name),
            "w2_sha256": _sha256(runtime_dir / name),
            "exact_match": _sha256(args.a2_artifact_dir / name)
            == _sha256(runtime_dir / name),
        }
        for name in EXACT_CSV_FILES
    }
    npz_comparison = _compare_npz(
        runtime_dir / "initial_and_final_states.npz",
        args.a2_artifact_dir / "initial_and_final_states.npz",
    )
    public_passed, public_details = _public_result_gate(public_dir)

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
    regression_passed = bool(
        authority_passed
        and execution_gate
        and manager_gate
        and public_passed
        and all(row["exact_match"] for row in field_comparison.values())
        and all(row["exact_match"] for row in csv_comparison.values())
        and all(row["exact_match"] for row in npz_comparison.values())
    )

    regression = {
        "schema_version": "stage7_u3_b2_a1_working_tool_w2_regression_v1",
        "source_git_sha": args.source_git_sha,
        "outcome": OUTCOME if regression_passed else "WORKING_TOOL_W2_REGRESSION_FAIL",
        "a2_source_git_sha": A2_SOURCE_SHA,
        "a2_workflow_run": A2_RUN_ID,
        "a2_workflow_job": A2_JOB_ID,
        "a2_artifact_id": A2_ARTIFACT_ID,
        "a2_artifact_name": A2_ARTIFACT_NAME,
        "a2_artifact_sha256": A2_ARTIFACT_SHA256,
        "parent_authority_gate_passed": authority_passed,
        "public_result_gate_passed": public_passed,
        "public_result_details": public_details,
        "full_horizon_execution_gate_passed": execution_gate,
        "manager_and_restoration_gate_passed": manager_gate,
        "exact_summary_field_comparison": field_comparison,
        "exact_csv_comparison": csv_comparison,
        "exact_npz_array_comparison": npz_comparison,
        "exact_a2_behavioral_regression_passed": regression_passed,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_approval": False,
    }
    _write_json(output / "w2_behavioral_regression.json", regression)
    (output / "report.md").write_text(
        "# Working Tool W2 full-horizon regression\n\n"
        "The normal Working Tool case path executed the retained A2 "
        "model-managed FVM trajectory to 2L/c0. A separate verification "
        "harness compared runtime evidence with the immutable A2 authority.\n\n"
        "```json\n"
        + json.dumps(regression, indent=2, sort_keys=True, allow_nan=False)
        + "\n```\n",
        encoding="utf-8",
    )
    _manifest(output)

    print(json.dumps(regression, indent=2, sort_keys=True, allow_nan=False))
    if not regression_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
