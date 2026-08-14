from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from liquid_gas_transient.working_tool import (
    PROVISIONAL_WARNING_CODE,
    RESULT_FILENAMES,
    execute_case,
    write_result_package,
)
from u3_b2_a1_working_tool_w1_a2_live_backend import (
    A2_STARTING_STATE_SHA256,
    A2LiveWorkingToolBackend,
    DEFAULT_SMOKE_ACCEPTED_STEPS,
    W1_SMOKE_WARNING_CODE,
    build_canonical_w1_case,
)


OUTCOME = "WORKING_TOOL_W1_A2_LIVE_BACKEND_SMOKE_PASS"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    parser.add_argument(
        "--smoke-accepted-steps",
        type=int,
        default=DEFAULT_SMOKE_ACCEPTED_STEPS,
    )
    args = parser.parse_args()

    if args.output_dir.exists():
        raise FileExistsError(
            f"output directory already exists: {args.output_dir}"
        )
    args.output_dir.mkdir(parents=True)

    case = build_canonical_w1_case(
        args.contract,
        case_id="W1-A2-LIVE-AUTHORITATIVE-SMOKE",
    )
    backend = A2LiveWorkingToolBackend(
        contract_path=args.contract,
        b1_contract_path=args.b1_contract,
        smoke_accepted_steps=args.smoke_accepted_steps,
    )
    result = execute_case(case, backend)
    public_dir = write_result_package(
        result,
        args.output_dir / "public-result",
    )
    public_summary = json.loads(
        (public_dir / "summary.json").read_text(encoding="utf-8")
    )
    public_files = sorted(path.name for path in public_dir.iterdir() if path.is_file())
    warning_codes = [warning.code for warning in result.warnings]

    gates = {
        "canonical_starting_state_exact": bool(
            result.summary["starting_state_sha256"]
            == A2_STARTING_STATE_SHA256
            and result.summary["starting_state_matches_a2"] is True
        ),
        "one_fvm_solver_instance": bool(
            result.summary["one_fvm_solver_instance"] is True
            and backend.solver_instances_created == 1
        ),
        "accepted_step_target_exact": bool(
            result.summary["accepted_steps"] == args.smoke_accepted_steps
            and result.summary["final_solver_step"] == args.smoke_accepted_steps
            and len(result.history) == args.smoke_accepted_steps
        ),
        "a2_live_path_connected": bool(
            result.summary["a2_live_path_connected"] is True
            and result.summary["a2_model_managed_live_hook_used"] is True
        ),
        "context_restoration_exact": bool(
            result.summary["successful_context_restoration_count"]
            == args.smoke_accepted_steps
            and result.summary["context_restoration_gate_passed"] is True
            and result.summary[
                "context_restored_without_root_reconstruction"
            ]
            is True
            and result.summary["physics_flux_modified_by_manager"] is False
        ),
        "early_manager_state_exact": bool(
            result.summary["manager_transition_count"] == 0
            and result.summary["manager_selection_history_count"] == 1
            and result.transitions == ()
            and all(
                row["public_boundary_state"] == "OUTWARD_FLOW"
                and row["outward_internal_model"]
                == "THREE_BRANCH_WAVE_MODEL"
                for row in result.history
            )
        ),
        "short_run_physical_gate": bool(
            result.summary["short_run_physical_gate_passed"] is True
            and result.summary["final_all_conserved_finite"] is True
            and result.summary["final_minimum_density_kg_m3"] > 0.0
            and result.summary["final_minimum_internal_energy_j_kg"] > 0.0
            and result.summary["final_rho_xv_exact_zero"] is True
        ),
        "mandatory_warning_gate": bool(
            warning_codes
            == [PROVISIONAL_WARNING_CODE, W1_SMOKE_WARNING_CODE]
        ),
        "formal_authority_false": bool(
            result.verified is False
            and result.accepted is False
            and result.validated is False
            and result.design_use_approved is False
            and public_summary["verified"] is False
            and public_summary["accepted"] is False
            and public_summary["validated"] is False
            and public_summary["design_use_approved"] is False
        ),
        "public_file_contract_exact": public_files == sorted(RESULT_FILENAMES),
        "public_verification_metadata_absent": all(
            key not in public_summary
            for key in (
                "workflow_run",
                "workflow_job",
                "artifact_id",
                "artifact_sha256",
                "parent_artifact_id",
                "exact_increment_9l_behavioral_equivalence_passed",
            )
        ),
        "w2_scope_not_claimed": bool(
            result.summary["full_two_l_over_c0_regression_tested"] is False
            and result.summary["target_horizon_reached"] is False
        ),
    }
    passed = all(gates.values())
    evidence: dict[str, Any] = {
        "schema_version": "stage7_u3_b2_a1_working_tool_w1_smoke_v1",
        "source_git_sha": args.source_git_sha,
        "outcome": OUTCOME if passed else "WORKING_TOOL_W1_SMOKE_STOPPED",
        "smoke_accepted_steps": args.smoke_accepted_steps,
        "starting_state_sha256": result.summary["starting_state_sha256"],
        "final_state_sha256": result.summary["final_state_sha256"],
        "final_solver_time_s": result.summary["final_solver_time_s"],
        "manager_transition_count": result.summary["manager_transition_count"],
        "successful_context_restoration_count": result.summary[
            "successful_context_restoration_count"
        ],
        "gates": gates,
        "live_fvm_connected": True,
        "full_two_l_over_c0_regression_tested": False,
        "verified": False,
        "accepted": False,
        "validated": False,
        "design_use_approved": False,
    }
    (args.output_dir / "case.json").write_text(
        json.dumps(case.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "w1_smoke_evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest_files = [
        path
        for path in _relative_files(args.output_dir)
        if path.name != "artifact_sha256.txt"
    ]
    (args.output_dir / "artifact_sha256.txt").write_text(
        "".join(
            f"{_sha256(path)}  {path.relative_to(args.output_dir).as_posix()}\n"
            for path in manifest_files
        ),
        encoding="utf-8",
    )

    print(json.dumps(evidence, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
