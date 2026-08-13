from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

import u3_b2_a1_increment_9l_two_state_boundary_state_machine_v4 as previous
import u3_b2_a1_finite_compression_bounded_window_full_horizon as bounded


FAILED_RUN = 31688222498
FAILED_JOB = 94409230331
FAILED_SOURCE_SHA = "bdf8e22c20b250b93af4e9284d488c62e5c8ebfd"
FAILED_ARTIFACT = 9176846382
FAILED_ARTIFACT_NAME = "u3-b2-a1-increment-9l-v4-31688222498"
FAILED_ARTIFACT_SHA256 = (
    "bbbf977e35661287f012ae15a0febd3dd6fc81630e968e93aa4546cbe5132ad5"
)
BOUNDED_AUTHORITY_SOURCE_SHA = "4b96bee28a6abeb1080256d965be408ebd565d37"
BOUNDED_AUTHORITY_RUN = 31668258876
BOUNDED_AUTHORITY_JOB = 94347432910
BOUNDED_AUTHORITY_ARTIFACT = 9168751076
BOUNDED_AUTHORITY_ARTIFACT_NAME = (
    "u3-b2-a1-finite-compression-increment-9e-admissibility-31668258876"
)
BOUNDED_AUTHORITY_ARTIFACT_SHA256 = (
    "9a5e3c500ba379370827276ce5b098ca51e81e49685b1fab5e4dabbcbf16baaa"
)
BOUNDED_AUTHORITY_OUTCOME = (
    "BOUNDED_B1_SUCCESS_WINDOW_WITH_UNIQUE_ROOT_SUPPORTED"
)
CORRECTION_FILE = "finite_compression_bounded_window_fallback_correction.json"
EVENTS_FILE = "finite_compression_bounded_window_fallback_events.csv"


class Increment9LBoundedStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_V2_MODULE = previous.previous.previous
_BASE_CORRECTED_HOOK = _V2_MODULE.CorrectedTwoStateBoundaryStateMachineHook


class BoundedWindowTwoStateBoundaryStateMachineHook(_BASE_CORRECTED_HOOK):
    """Use the retained bounded success-window topology for seeded edge contact."""

    last_instance: ClassVar[
        "BoundedWindowTwoStateBoundaryStateMachineHook | None"
    ] = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.bounded_window_fallback_events: list[dict[str, Any]] = []
        self._pending_seeded_fallback_classification: str | None = None
        self._pending_seeded_fallback_message: str | None = None
        self._finite_prepare_time_s: float | None = None
        type(self).last_instance = self

    def _prepare_finite(self, U: np.ndarray, t: float) -> None:
        self._finite_prepare_time_s = float(t)
        try:
            super()._prepare_finite(U, t)
        finally:
            self._finite_prepare_time_s = None
            self._pending_seeded_fallback_classification = None
            self._pending_seeded_fallback_message = None

    def _seeded_fallback_allowed(
        self,
        classification: str,
        message: str,
    ) -> bool:
        allowed = bool(super()._seeded_fallback_allowed(classification, message))
        if allowed:
            self._pending_seeded_fallback_classification = str(classification)
            self._pending_seeded_fallback_message = str(message)
        return allowed

    def _run_fixed_finite(
        self,
        U: np.ndarray,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, Any],
    ]:
        if self._previous_root_pressure_pa is None:
            raise previous.previous.previous.base.Increment9LStop(
                "PARENT_ROOT_MISSING",
                "bounded-window continuation has no previous root pressure",
            )
        trigger = self._pending_seeded_fallback_classification
        message = self._pending_seeded_fallback_message
        if trigger not in {
            "SEEDED_INTERVAL_EDGE_CONTACT",
            "STATE_REPRODUCTION_MISMATCH",
        }:
            raise previous.previous.previous.base.Increment9LStop(
                "UNAUTHORIZED_BOUNDED_WINDOW_FALLBACK",
                f"bounded-window fallback received trigger {trigger!r}",
            )
        parent_root = {"root_pressure_pa": str(self._previous_root_pressure_pa)}
        result = bounded._bounded_dynamic_root_run(
            contract=self.contract,
            b1_contract=self.b1_contract,
            U=np.asarray(U, dtype=float),
            parent_root=parent_root,
        )
        (
            diagnostic_summary,
            fixed_rows,
            guard_rows,
            topology_rows,
            density_rows,
            root,
        ) = result
        event = {
            "requested_solver_step": self.requested_solver_step,
            "solver_time_s": self._finite_prepare_time_s,
            "seeded_trigger_classification": trigger,
            "seeded_trigger_message": message,
            "fallback_algorithm": "BOUNDED_B1_SUCCESS_WINDOW_FIXED_TOPOLOGY",
            "bounded_success_window_count": int(
                diagnostic_summary.get("bounded_success_window_count", 0)
            ),
            "leading_excluded_node_count": int(
                diagnostic_summary.get("leading_excluded_node_count", 0)
            ),
            "trailing_excluded_node_count": int(
                diagnostic_summary.get("trailing_excluded_node_count", 0)
            ),
            "trailing_local_inadmissible_node_count": int(
                diagnostic_summary.get(
                    "trailing_local_inadmissible_node_count",
                    0,
                )
            ),
            "fixed_scan_node_count": int(
                diagnostic_summary.get("fixed_scan_node_count", 0)
            ),
            "guard_front_refinement_applied": bool(
                diagnostic_summary.get("guard_front_refinement_applied", False)
            ),
            "guard_front_iterations": int(
                diagnostic_summary.get("guard_front_iterations", 0)
            ),
            "root_topology_node_count": int(
                diagnostic_summary.get("root_topology_node_count", 0)
            ),
            "root_topology_monotone_nonincreasing": bool(
                diagnostic_summary.get(
                    "root_topology_monotone_nonincreasing",
                    False,
                )
            ),
            "root_topology_sign_change_count": int(
                diagnostic_summary.get("root_topology_sign_change_count", 0)
            ),
            "selected_root_present": bool(
                diagnostic_summary.get("selected_root_present", False)
            ),
            "selected_root_chi": diagnostic_summary.get("selected_root_chi"),
            "selected_root_residual_kg_s": diagnostic_summary.get(
                "selected_root_residual_kg_s"
            ),
            "selected_root_gate_passed": bool(
                diagnostic_summary.get("selected_root_gate_passed", False)
            ),
            "diagnostic_outcome": diagnostic_summary.get("outcome"),
            "actual_continuation_supported": bool(
                diagnostic_summary.get("actual_continuation_supported", False)
            ),
            "excluded_candidate_used_as_root_endpoint": False,
            "excluded_candidate_used_to_construct_flux": False,
            "absolute_step_number_trigger_used": False,
            "checkpoint_state_used": False,
        }
        if not any(
            int(row["requested_solver_step"])
            == int(event["requested_solver_step"])
            for row in self.bounded_window_fallback_events
        ):
            self.bounded_window_fallback_events.append(event)
        return (
            diagnostic_summary,
            fixed_rows,
            guard_rows,
            topology_rows,
            density_rows,
            root,
        )


def _install_bounded_window_hook() -> None:
    _V2_MODULE.CorrectedTwoStateBoundaryStateMachineHook = (
        BoundedWindowTwoStateBoundaryStateMachineHook
    )
    BoundedWindowTwoStateBoundaryStateMachineHook.last_instance = None


def _postprocess(
    *,
    output: Path,
    correction_spec: Path,
    source_git_sha: str,
) -> dict[str, Any]:
    instance = BoundedWindowTwoStateBoundaryStateMachineHook.last_instance
    if instance is None:
        raise Increment9LBoundedStop(
            "bounded-window state-machine hook instance was not created"
        )
    summary_path = output / "summary.json"
    if not summary_path.is_file():
        raise Increment9LBoundedStop("Increment 9L v5 summary is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    events = sorted(
        instance.bounded_window_fallback_events,
        key=lambda row: (
            int(row["requested_solver_step"]),
            float(row["solver_time_s"]),
        ),
    )
    event_steps = [int(row["requested_solver_step"]) for row in events]
    bounded_gate = bool(
        events
        and all(
            row["seeded_trigger_classification"]
            in {"SEEDED_INTERVAL_EDGE_CONTACT", "STATE_REPRODUCTION_MISMATCH"}
            for row in events
        )
        and all(int(row["bounded_success_window_count"]) == 1 for row in events)
        and all(int(row["fixed_scan_node_count"]) > 0 for row in events)
        and all(int(row["root_topology_node_count"]) >= 2 for row in events)
        and all(
            row["root_topology_monotone_nonincreasing"] is True
            for row in events
        )
        and all(int(row["root_topology_sign_change_count"]) == 1 for row in events)
        and all(row["selected_root_present"] is True for row in events)
        and all(row["selected_root_gate_passed"] is True for row in events)
        and all(row["actual_continuation_supported"] is True for row in events)
        and all(
            row["excluded_candidate_used_as_root_endpoint"] is False
            and row["excluded_candidate_used_to_construct_flux"] is False
            and row["absolute_step_number_trigger_used"] is False
            and row["checkpoint_state_used"] is False
            for row in events
        )
    )
    state_machine_gate_before = bool(
        summary["increment_9l_state_machine_gate_passed"]
    )
    corrected_gate = bool(
        state_machine_gate_before
        and bounded_gate
        and summary["target_horizon_reached"] is True
        and summary["boundary_transition_event_count"] == 1
        and summary["closure_trigger_classification"] == "NO_ADMISSIBLE_ISLAND"
    )

    previous.previous.previous.base._write_csv(output / EVENTS_FILE, events)
    correction = {
        "correction": "increment_9l_finite_compression_bounded_window_fallback",
        "failed_run": FAILED_RUN,
        "failed_job": FAILED_JOB,
        "failed_source_git_sha": FAILED_SOURCE_SHA,
        "failed_artifact": FAILED_ARTIFACT,
        "failed_artifact_name": FAILED_ARTIFACT_NAME,
        "failed_artifact_sha256": FAILED_ARTIFACT_SHA256,
        "failed_seeded_classification": "SEEDED_INTERVAL_EDGE_CONTACT",
        "failed_fallback_classification": "UNEXPECTED_B1_FAILURE",
        "correction_spec": str(correction_spec),
        "correction_spec_sha256": _sha256(correction_spec),
        "bounded_authority_source_git_sha": BOUNDED_AUTHORITY_SOURCE_SHA,
        "bounded_authority_run": BOUNDED_AUTHORITY_RUN,
        "bounded_authority_job": BOUNDED_AUTHORITY_JOB,
        "bounded_authority_artifact": BOUNDED_AUTHORITY_ARTIFACT,
        "bounded_authority_artifact_name": BOUNDED_AUTHORITY_ARTIFACT_NAME,
        "bounded_authority_artifact_sha256": (
            BOUNDED_AUTHORITY_ARTIFACT_SHA256
        ),
        "bounded_authority_outcome": BOUNDED_AUTHORITY_OUTCOME,
        "bounded_authority_live_metadata_verified": True,
        "fallback_event_count": len(events),
        "first_fallback_requested_step": min(event_steps) if event_steps else None,
        "last_fallback_requested_step": max(event_steps) if event_steps else None,
        "bounded_window_gate_passed": bounded_gate,
        "excluded_candidate_used_as_root_endpoint": False,
        "excluded_candidate_used_to_construct_flux": False,
        "absolute_step_number_trigger_used": False,
        "checkpoint_state_used": False,
        "hugoniot_equations_changed": False,
        "b1_changed": False,
        "production_adapter_changed": False,
        "fvm_solver_changed": False,
        "locked_contract_changed": False,
        "root_tolerance_changed": False,
        "velocity_tolerance_changed": False,
        "chi_cap_changed": False,
        "fixed_scan_nodes_changed": False,
        "seeded_scan_nodes_changed": False,
        "boundary_refinement_iterations_changed": False,
        "state_machine_changed": False,
        "closure_model_changed": False,
        "execution_source_git_sha": source_git_sha,
    }
    (output / CORRECTION_FILE).write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_increment_9l_two_state_boundary_state_machine_v5"
            ),
            "finite_compression_bounded_window_fallback_applied": True,
            "finite_compression_bounded_window_fallback_spec": str(
                correction_spec
            ),
            "finite_compression_bounded_window_fallback_spec_sha256": (
                _sha256(correction_spec)
            ),
            "finite_compression_bounded_window_fallback_event_count": len(events),
            "finite_compression_bounded_window_first_fallback_step": (
                min(event_steps) if event_steps else None
            ),
            "finite_compression_bounded_window_last_fallback_step": (
                max(event_steps) if event_steps else None
            ),
            "finite_compression_bounded_window_gate_passed": bounded_gate,
            "original_increment_9l_state_machine_gate_before_bounded_fallback": (
                state_machine_gate_before
            ),
            "increment_9l_state_machine_gate_passed": corrected_gate,
            "working_vertical_slice": corrected_gate,
            "provisional_engineering_two_l_over_c0_reached": bool(
                corrected_gate and summary["target_horizon_reached"]
            ),
            "outcome": (
                previous.previous.previous.base.OUTCOME
                if corrected_gate
                else "INCREMENT_9L_V5_STOPPED"
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
        + "\n## Finite-compression bounded-window fallback correction\n\n"
        + "A seeded interval edge contact was handed only to the existing "
        + "bounded B1-success-window topology. Leading and trailing excluded "
        + "candidates remained outside root topology and flux construction. "
        + "The fallback was selected by diagnostic classification, not solver "
        + "step, checkpoint state, or transition time. The expected later "
        + "NO_ADMISSIBLE_ISLAND classification remained the only public closure "
        + "trigger.\n\n"
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
        raise Increment9LBoundedStop(
            "corrected Increment 9L bounded-window/state-machine gate did not pass"
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
    parser.add_argument("--bounded-window-correction-spec", type=Path, required=True)
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
        args.bounded_window_correction_spec,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    _install_bounded_window_hook()
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
            "--authority-correction-spec",
            str(args.authority_correction_spec),
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
        correction_spec=args.bounded_window_correction_spec,
        source_git_sha=args.source_git_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
