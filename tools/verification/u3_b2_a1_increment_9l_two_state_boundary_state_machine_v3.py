from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import u3_b2_a1_increment_9l_two_state_boundary_state_machine_v2 as previous
import u3_b2_a1_weak_compression_bridge_full_horizon_guard_front_root_topology as topology_fix


FAILED_RUN = 31686545744
FAILED_JOB = 94403827129
FAILED_SOURCE_SHA = "af16ae68d8ce3581416486a3ce55f84441af5623"
FAILED_ARTIFACT = 9175846671
FAILED_ARTIFACT_SHA256 = (
    "cda10e7ff8663daba089b3ca7a4207f69ed4f38ca7a781786b66a82e2dd0eef1"
)
CORRECTION_FILE = "guard_front_root_topology_correction.json"
CORRECTION_EVENTS_FILE = "guard_front_root_topology_correction_events.csv"
CORRECTION_SCOPE = (
    "guard_front_evidence_rows_separated_from_compatibility_root_topology"
)

_TOPOLOGY_EVENTS: list[dict[str, Any]] = []


class Increment9LTopologyStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tracked_corrected_solve_three_branch_boundary(
    *,
    hook: Any,
    U: Any,
    solver_time_s: float,
) -> dict[str, Any]:
    context = topology_fix._corrected_solve_three_branch_boundary(
        hook=hook,
        U=U,
        solver_time_s=solver_time_s,
    )
    if bool(context.get("root_topology_correction_applied")):
        event = {
            "requested_solver_step": getattr(hook, "requested_solver_step", None),
            "solver_time_s": float(solver_time_s),
            "correction_scope": CORRECTION_SCOPE,
            "guard_front_evidence_row_count": int(
                context.get("guard_front_evidence_row_count", 0)
            ),
            "guard_front_successful_intermediate_row_count": int(
                context.get(
                    "guard_front_successful_intermediate_row_count",
                    0,
                )
            ),
            "root_topology_node_count": int(
                context.get("root_topology_node_count", 0)
            ),
            "root_topology_requested_offsets_pa": list(
                context.get("root_topology_requested_offsets_pa", [])
            ),
            "root_topology_residuals_kg_s": list(
                context.get("root_topology_residuals_kg_s", [])
            ),
            "root_topology_monotone_nonincreasing": bool(
                context.get(
                    "root_topology_monotone_nonincreasing",
                    False,
                )
            ),
            "root_topology_sign_change_count": int(
                context.get("root_topology_sign_change_count", 0)
            ),
            "guard_front_stop_classification": context.get(
                "guard_front_stop_classification"
            ),
            "intermediate_evidence_rows_retained": True,
            "intermediate_success_used_as_root_topology": False,
            "failed_b1_state_used_as_root_endpoint": False,
            "failed_b1_state_used_to_construct_flux": False,
            "absolute_step_number_transition_trigger_used": False,
        }
        key = (
            event["requested_solver_step"],
            event["solver_time_s"],
        )
        if not any(
            (
                row["requested_solver_step"],
                row["solver_time_s"],
            )
            == key
            for row in _TOPOLOGY_EVENTS
        ):
            _TOPOLOGY_EVENTS.append(event)
    return context


def _install_correction() -> None:
    weak_refined = previous.base.weak_refined
    weak_refined._guard_front_positive_scan = (
        topology_fix._corrected_guard_front_positive_scan
    )
    weak_refined._guard_front_solve_three_branch_boundary = (
        _tracked_corrected_solve_three_branch_boundary
    )


def _postprocess(
    *,
    output: Path,
    correction_spec: Path,
    source_git_sha: str,
) -> dict[str, Any]:
    summary_path = output / "summary.json"
    if not summary_path.is_file():
        raise Increment9LTopologyStop("Increment 9L v3 summary is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    events = sorted(
        _TOPOLOGY_EVENTS,
        key=lambda row: (
            int(row["requested_solver_step"]),
            float(row["solver_time_s"]),
        ),
    )

    corrected_steps = [int(row["requested_solver_step"]) for row in events]
    topology_gate = bool(
        events
        and min(corrected_steps) == topology_fix.base.FIRST_GUARD_FRONT_REFINEMENT_STEP
        and all(
            int(row["guard_front_evidence_row_count"]) > 0
            for row in events
        )
        and all(
            int(row["guard_front_successful_intermediate_row_count"]) >= 0
            for row in events
        )
        and all(int(row["root_topology_node_count"]) >= 2 for row in events)
        and all(
            bool(row["root_topology_requested_offsets_pa"])
            and bool(row["root_topology_residuals_kg_s"])
            for row in events
        )
        and all(
            bool(row["root_topology_monotone_nonincreasing"])
            for row in events
        )
        and all(
            int(row["root_topology_sign_change_count"]) == 1
            for row in events
        )
        and all(
            row["intermediate_evidence_rows_retained"] is True
            and row["intermediate_success_used_as_root_topology"] is False
            and row["failed_b1_state_used_as_root_endpoint"] is False
            and row["failed_b1_state_used_to_construct_flux"] is False
            and row["absolute_step_number_transition_trigger_used"] is False
            for row in events
        )
    )
    state_machine_gate_before = bool(
        summary["increment_9l_state_machine_gate_passed"]
    )
    handoff_gate = bool(summary["initial_rarefaction_handoff_gate_passed"])
    corrected_gate = bool(
        state_machine_gate_before
        and handoff_gate
        and topology_gate
        and summary["outward_model_transition_event_count"] == 1
        and summary["boundary_transition_event_count"] == 1
        and summary["target_horizon_reached"] is True
    )

    previous.base._write_csv(output / CORRECTION_EVENTS_FILE, events)
    correction = {
        "correction": "increment_9l_guard_front_root_topology",
        "scope": CORRECTION_SCOPE,
        "failed_run": FAILED_RUN,
        "failed_job": FAILED_JOB,
        "failed_source_git_sha": FAILED_SOURCE_SHA,
        "failed_artifact": FAILED_ARTIFACT,
        "failed_artifact_sha256": FAILED_ARTIFACT_SHA256,
        "failed_classification": "SUCCESS_DOMAIN_NONMONOTONE",
        "corrected_source_git_sha": source_git_sha,
        "correction_spec": str(correction_spec),
        "correction_spec_sha256": _sha256(correction_spec),
        "existing_authoritative_correction_source": (
            "tools/verification/"
            "u3_b2_a1_weak_compression_bridge_full_horizon_"
            "guard_front_root_topology.py"
        ),
        "existing_authoritative_failed_source_sha": (
            topology_fix.CORRECTION_PARENT_SOURCE_SHA
        ),
        "existing_authoritative_failed_run": (
            topology_fix.CORRECTION_PARENT_WORKFLOW_RUN
        ),
        "existing_authoritative_failed_job": topology_fix.CORRECTION_PARENT_JOB,
        "existing_authoritative_failed_artifact": (
            topology_fix.CORRECTION_PARENT_ARTIFACT
        ),
        "existing_authoritative_failed_artifact_sha256": (
            topology_fix.CORRECTION_PARENT_ARTIFACT_SHA256
        ),
        "first_corrected_requested_step": (
            min(corrected_steps) if corrected_steps else None
        ),
        "last_corrected_requested_step": (
            max(corrected_steps) if corrected_steps else None
        ),
        "corrected_step_count": len(events),
        "maximum_guard_front_evidence_row_count": (
            max(int(row["guard_front_evidence_row_count"]) for row in events)
            if events
            else None
        ),
        "maximum_guard_front_successful_intermediate_row_count": (
            max(
                int(row["guard_front_successful_intermediate_row_count"])
                for row in events
            )
            if events
            else None
        ),
        "minimum_root_topology_node_count": (
            min(int(row["root_topology_node_count"]) for row in events)
            if events
            else None
        ),
        "root_topology_gate_passed": topology_gate,
        "intermediate_evidence_discarded": False,
        "intermediate_success_used_as_root_topology": False,
        "failed_b1_state_used_as_root_endpoint": False,
        "failed_b1_state_used_to_construct_flux": False,
        "b1_changed": False,
        "production_adapter_changed": False,
        "fvm_solver_changed": False,
        "locked_contract_changed": False,
        "root_tolerance_changed": False,
        "velocity_tolerance_changed": False,
        "chi_cap_changed": False,
        "scan_node_counts_changed": False,
        "guard_front_iterations_changed": False,
    }
    (output / CORRECTION_FILE).write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_increment_9l_two_state_boundary_state_machine_v3"
            ),
            "guard_front_root_topology_correction_applied": True,
            "guard_front_root_topology_correction_scope": CORRECTION_SCOPE,
            "guard_front_root_topology_correction_spec": str(correction_spec),
            "guard_front_root_topology_correction_spec_sha256": (
                _sha256(correction_spec)
            ),
            "guard_front_root_topology_corrected_step_count": len(events),
            "guard_front_root_topology_first_corrected_step": (
                min(corrected_steps) if corrected_steps else None
            ),
            "guard_front_root_topology_last_corrected_step": (
                max(corrected_steps) if corrected_steps else None
            ),
            "guard_front_root_topology_gate_passed": topology_gate,
            "original_increment_9l_state_machine_gate_before_topology_correction": (
                state_machine_gate_before
            ),
            "increment_9l_state_machine_gate_passed": corrected_gate,
            "working_vertical_slice": corrected_gate,
            "provisional_engineering_two_l_over_c0_reached": bool(
                corrected_gate and summary["target_horizon_reached"]
            ),
            "outcome": (
                previous.base.OUTCOME
                if corrected_gate
                else "INCREMENT_9L_V3_STOPPED"
            ),
        }
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = output / "report.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n## Guard-front root-topology correction\n\n"
        + "All categorical Guard-front rows remain in the immutable evidence. "
        + "Compatibility-root topology uses only the final refined first-success "
        + "endpoint and higher fixed B1-success states. Intermediate successful "
        + "bisection rows remain evidence-only. No failed B1 state or evidence-"
        + "only row became a root endpoint, flux state, or solver-step authority.\n\n"
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
        raise Increment9LTopologyStop(
            "corrected Increment 9L topology/state-machine gate did not pass"
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--handoff-correction-spec", type=Path, required=True)
    parser.add_argument("--topology-correction-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (
        args.contract,
        args.b1_contract,
        args.model_review_spec,
        args.handoff_correction_spec,
        args.topology_correction_spec,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    _TOPOLOGY_EVENTS.clear()
    _install_correction()
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
            "--correction-spec",
            str(args.handoff_correction_spec),
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
        correction_spec=args.topology_correction_spec,
        source_git_sha=args.source_git_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
