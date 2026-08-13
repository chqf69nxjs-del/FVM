from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

import u3_b2_a1_increment_9l_two_state_boundary_state_machine as base
import u3_b2_characteristic_port_two_l_over_c0 as connected


FAILED_RUN = 31686007487
FAILED_JOB = 94402114920
FAILED_SOURCE_SHA = "74d636bf43d2eb4b47d6759a626ccd2ad79783a9"
FAILED_ARTIFACT = 9175422808
FAILED_ARTIFACT_SHA256 = (
    "57e9d1900936195bb05ae426dc6efaa8881335890d137dcc6d27770b4c350f35"
)
HANDOFF_TRIGGER = "CONNECTED_ROOT_SIGN_CHANGES_ZERO"
CONNECTED_ALGORITHM = "CONNECTED_RAREFACTION"
GENERAL_ALGORITHM = "GENERAL_THREE_BRANCH_CLASSIFICATION"
CORRECTION_FILE = "initial_rarefaction_handoff_correction.json"
HANDOFF_EVENTS_FILE = "three_branch_algorithm_transition_events.csv"


class Increment9LHandoffStop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CorrectedTwoStateBoundaryStateMachineHook(
    base.TwoStateBoundaryStateMachineHook
):
    """Retain the established connected rarefaction path before 3-branch logic."""

    last_instance: ClassVar[
        "CorrectedTwoStateBoundaryStateMachineHook | None"
    ] = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.three_branch_algorithm = CONNECTED_ALGORITHM
        self.three_branch_algorithm_transition_events: list[dict[str, Any]] = []
        type(self).last_instance = self

    @staticmethod
    def _handoff_supported(exc: Exception) -> bool:
        message = str(exc)
        return bool(
            "connected subsonic scan did not retain exactly one root branch"
            in message
            and "sign_changes=0" in message
        )

    def _prepare_connected_rarefaction(self, U: np.ndarray, t: float) -> None:
        try:
            context = connected._solve_two_l_over_c0_root(
                contract=self.contract,
                case_id=self.case_id,
                state_id=self.state_id,
                provider=self.provider,
                adapter=self.adapter,
                area_m2=self.area_m2,
                outlet_conserved=np.asarray(U[-1], dtype=float),
                solver_time_s=float(t),
                previous_root_pressure_pa=self._previous_root_pressure_pa,
            )
        except Exception as exc:
            if not self._handoff_supported(exc):
                classification = str(
                    getattr(exc, "classification", type(exc).__name__)
                )
                raise base.Increment9LStop(
                    classification,
                    "connected-rarefaction outward model failed outside the "
                    f"authorized handoff: {type(exc).__name__}: {exc}",
                ) from exc
            self.three_branch_algorithm_transition_events.append(
                {
                    "requested_solver_step": self.requested_solver_step,
                    "solver_time_s": float(t),
                    "from_algorithm": CONNECTED_ALGORITHM,
                    "to_algorithm": GENERAL_ALGORITHM,
                    "trigger_classification": HANDOFF_TRIGGER,
                    "trigger_message": str(exc),
                    "absolute_step_number_trigger_used": False,
                    "failed_candidate_used_as_root": False,
                    "failed_candidate_used_as_flux": False,
                    "solver_state_mutated_before_handoff": False,
                }
            )
            self.three_branch_algorithm = GENERAL_ALGORITHM
            self._invalidate_cache()
            super()._prepare_three_branch(U, t)
            if self.root_context is not None:
                self.root_context["three_branch_algorithm"] = GENERAL_ALGORITHM
                self.root_context[
                    "initial_rarefaction_handoff_correction_applied"
                ] = True
            return

        context = dict(context)
        root = context["root"]
        pressure_delta = float(
            root["pressure_pa"] - context["interior_pressure_pa"]
        )
        branch = (
            "NEUTRAL_ENDPOINT"
            if pressure_delta == 0.0
            else "CONNECTED_RAREFACTION"
            if pressure_delta < 0.0
            else "CONNECTED_COMPRESSION"
        )
        context.update(
            {
                "branch_classification": branch,
                "public_boundary_state": base.PUBLIC_OUTWARD,
                "outward_internal_model": base.MODEL_THREE_BRANCH,
                "three_branch_algorithm": CONNECTED_ALGORITHM,
                "state_machine_transition_triggered": False,
                "initial_rarefaction_handoff_correction_applied": True,
            }
        )
        self.pending_branch_classification = branch
        self._install_context(context=context, U=U, t=t)

    def _prepare_three_branch(self, U: np.ndarray, t: float) -> None:
        if self.three_branch_algorithm == CONNECTED_ALGORITHM:
            self._prepare_connected_rarefaction(U, t)
            return
        if self.three_branch_algorithm == GENERAL_ALGORITHM:
            super()._prepare_three_branch(U, t)
            if self.root_context is not None:
                self.root_context["three_branch_algorithm"] = GENERAL_ALGORITHM
                self.root_context[
                    "initial_rarefaction_handoff_correction_applied"
                ] = True
            return
        raise base.Increment9LStop(
            "STATE_MACHINE_INTERNAL_ERROR",
            f"unknown three-branch algorithm {self.three_branch_algorithm!r}",
        )


def _postprocess(
    *,
    output: Path,
    correction_spec: Path,
    source_git_sha: str,
) -> dict[str, Any]:
    instance = CorrectedTwoStateBoundaryStateMachineHook.last_instance
    if instance is None:
        raise Increment9LHandoffStop("corrected state-machine instance was not created")
    events = list(instance.three_branch_algorithm_transition_events)
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    original_gate = bool(summary["increment_9l_state_machine_gate_passed"])
    handoff_gate = bool(
        len(events) == 1
        and events[0]["from_algorithm"] == CONNECTED_ALGORITHM
        and events[0]["to_algorithm"] == GENERAL_ALGORITHM
        and events[0]["trigger_classification"] == HANDOFF_TRIGGER
        and events[0]["absolute_step_number_trigger_used"] is False
        and events[0]["failed_candidate_used_as_root"] is False
        and events[0]["failed_candidate_used_as_flux"] is False
        and events[0]["solver_state_mutated_before_handoff"] is False
    )
    corrected_gate = bool(original_gate and handoff_gate)

    base._write_csv(output / HANDOFF_EVENTS_FILE, events)
    correction = {
        "correction": "increment_9l_initial_connected_rarefaction_handoff",
        "failed_run": FAILED_RUN,
        "failed_job": FAILED_JOB,
        "failed_source_git_sha": FAILED_SOURCE_SHA,
        "failed_artifact": FAILED_ARTIFACT,
        "failed_artifact_sha256": FAILED_ARTIFACT_SHA256,
        "failed_classification": "POSITIVE_SCAN_EVALUATION_FAILURE",
        "corrected_source_git_sha": source_git_sha,
        "correction_spec": str(correction_spec),
        "correction_spec_sha256": _sha256(correction_spec),
        "handoff_event_count": len(events),
        "handoff_gate_passed": handoff_gate,
        "public_boundary_state_changed_by_correction": False,
        "finite_compression_trigger_changed": False,
        "closure_trigger_changed": False,
        "b1_changed": False,
        "production_adapter_changed": False,
        "fvm_solver_changed": False,
        "locked_contract_changed": False,
        "tolerance_changed": False,
        "chi_cap_changed": False,
    }
    (output / CORRECTION_FILE).write_text(
        json.dumps(correction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_increment_9l_two_state_boundary_state_machine_v2"
            ),
            "initial_connected_rarefaction_algorithm": CONNECTED_ALGORITHM,
            "general_three_branch_algorithm": GENERAL_ALGORITHM,
            "three_branch_algorithm_transition_event_count": len(events),
            "three_branch_algorithm_transition_events": events,
            "initial_rarefaction_handoff_trigger": HANDOFF_TRIGGER,
            "initial_rarefaction_handoff_gate_passed": handoff_gate,
            "initial_rarefaction_handoff_correction_spec": str(correction_spec),
            "initial_rarefaction_handoff_correction_spec_sha256": (
                _sha256(correction_spec)
            ),
            "original_increment_9l_state_machine_gate_passed": original_gate,
            "increment_9l_state_machine_gate_passed": corrected_gate,
            "working_vertical_slice": corrected_gate,
            "provisional_engineering_two_l_over_c0_reached": bool(
                corrected_gate and summary["target_horizon_reached"]
            ),
            "outcome": (
                base.OUTCOME if corrected_gate else "INCREMENT_9L_V2_STOPPED"
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
        + "\n## Initial connected-rarefaction handoff correction\n\n"
        + "The uniform initial state remained on the established connected "
        + "rarefaction root path. Only the exact sign_changes=0 end of that "
        + "connected path handed the same requested step to the general "
        + "three-branch classifier. This was an internal algorithm handoff; the "
        + "public boundary state remained OUTWARD_FLOW. No failed candidate "
        + "became a root, flux, or solver-state update.\n\n"
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
        raise Increment9LHandoffStop(
            "corrected Increment 9L handoff/state-machine gate did not pass"
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--correction-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    for path in (
        args.contract,
        args.b1_contract,
        args.model_review_spec,
        args.correction_spec,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    base.TwoStateBoundaryStateMachineHook = (
        CorrectedTwoStateBoundaryStateMachineHook
    )
    CorrectedTwoStateBoundaryStateMachineHook.last_instance = None
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
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        base.main()
    finally:
        sys.argv = original_argv

    summary = _postprocess(
        output=args.output_dir,
        correction_spec=args.correction_spec,
        source_git_sha=args.source_git_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
