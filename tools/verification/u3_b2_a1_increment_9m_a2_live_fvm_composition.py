from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, ClassVar

import numpy as np

import u3_b2_a1_increment_9l_two_state_boundary_state_machine_v5 as legacy_v5
from liquid_gas_transient.physics_model_manager import (
    BoundaryRegime,
    ModelAxis,
    ModelTransitionEvent,
    PhysicsBoundaryModelManager,
)
from u3_b2_a1_increment_9m_a1_delegate_composition import (
    DelegateCompositionFailed,
    DelegateEvaluationRequest,
    DelegateTransitionRequested,
    Increment9LHookDelegateAdapter,
    ModelManagedIncrement9LDelegateComposer,
)


OUTCOME = "INCREMENT_9M_A2_EXACT_INCREMENT_9L_BEHAVIORAL_EQUIVALENCE_PASS"
PARENT_SOURCE_SHA = "512723f35addb63fd55f86468c69feb6d24fd457"
PARENT_RUN_ID = 31700264132
PARENT_JOB_ID = 94447447243
PARENT_ARTIFACT_ID = 9181655488
PARENT_ARTIFACT_NAME = "u3-b2-a1-increment-9l-state-based-clean-31700264132"
PARENT_ARTIFACT_SHA256 = (
    "36b8276998871e2939fc7755644d5910689838d78f967e025d2e5ce08f0b89f3"
)
PARENT_STARTING_STATE_SHA256 = (
    "deaae67e672d92fb1da7c40b1a7a03d904b58f35db12bcec81008b55f9014c21"
)
PARENT_FINAL_STATE_SHA256 = (
    "8e73e394f3101840c73c278bbc4521ec4fefeebaee4c7f0db774d87013fd5014"
)
MANAGER_EVENTS_FILE = "model_manager_transition_events.csv"
MANAGER_SELECTION_FILE = "model_manager_selection_history.csv"
RESTORATION_FILE = "model_manager_context_restoration.csv"
COMPARISON_FILE = "increment_9m_a2_behavioral_comparison.json"
INTEGRATION_FILE = "increment_9m_a2_live_composition.json"
PARENT_AUTHORITY_FILE = "parent_authority_verification.json"

_BASE = legacy_v5.previous.previous.previous.base
_LEGACY_BOUNDED_HOOK = legacy_v5.BoundedWindowTwoStateBoundaryStateMachineHook


class Increment9MA2Stop(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    _BASE._write_csv(path, rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class RecordingIncrement9LHookDelegateAdapter(Increment9LHookDelegateAdapter):
    """Retain original transition messages for legacy evidence compatibility."""

    def __init__(self, hook: Any) -> None:
        super().__init__(hook)
        self.transition_requests: list[DelegateTransitionRequested] = []

    def begin_evaluation(self) -> None:
        self.transition_requests.clear()

    def evaluate(
        self,
        *,
        selection: Any,
        transition_history: tuple[ModelTransitionEvent, ...],
        request: DelegateEvaluationRequest,
    ) -> dict[str, Any]:
        try:
            return super().evaluate(
                selection=selection,
                transition_history=transition_history,
                request=request,
            )
        except DelegateTransitionRequested as exc:
            self.transition_requests.append(exc)
            raise


class ModelManagedLiveFvmHook(_LEGACY_BOUNDED_HOOK):
    """Run retained Increment 9L delegates under the A0/A1 manager."""

    last_instance: ClassVar["ModelManagedLiveFvmHook | None"] = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.model_manager = PhysicsBoundaryModelManager()
        self.model_manager_adapter = RecordingIncrement9LHookDelegateAdapter(self)
        self.model_manager_composer = ModelManagedIncrement9LDelegateComposer(
            manager=self.model_manager,
            adapter=self.model_manager_adapter,
        )
        self.model_manager_context_restoration_rows: list[dict[str, Any]] = []
        type(self).last_instance = self

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return

        self.model_manager_adapter.begin_evaluation()
        try:
            result = self.model_manager_composer.evaluate(
                conserved_state=U,
                solver_time_s=float(t),
                observed_solver_step=self.requested_solver_step,
            )
        except DelegateCompositionFailed as exc:
            raise _BASE.Increment9LStop(
                exc.classification,
                f"Increment 9M A2 manager/delegate composition failed: {exc}",
            ) from exc

        requests = tuple(self.model_manager_adapter.transition_requests)
        if len(requests) != len(result.transition_events):
            raise _BASE.Increment9LStop(
                "MANAGER_TRANSITION_EVIDENCE_MISMATCH",
                "delegate transition-request count does not match committed events",
            )

        context = dict(result.context)
        for event, request in zip(result.transition_events, requests):
            self._append_legacy_transition_event(event=event, request=request)
            if event.axis is ModelAxis.BOUNDARY_REGIME:
                self.closure_trigger_classification = request.classification
                self.closure_trigger_message = request.message
                context["closure_trigger_classification"] = request.classification
                context["closure_trigger_message"] = request.message
                context["state_machine_transition_triggered"] = True

        expected_flux = np.asarray(context.get("flux"), dtype=float).copy()
        if expected_flux.shape != (4,) or not np.all(np.isfinite(expected_flux)):
            raise _BASE.Increment9LStop(
                "MANAGER_SUCCESSFUL_CONTEXT_FLUX_INVALID",
                "successful composed delegate context has an invalid flux",
            )

        self._install_context(context=context, U=U, t=float(t))
        restoration_passed = bool(
            self.root_context is context
            and np.array_equal(self.flux, expected_flux)
            and self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.boundary_state == result.selection.boundary_regime.value
            and self.outward_model == result.selection.outward_flow_model.value
        )
        self.model_manager_context_restoration_rows.append(
            {
                "requested_solver_step": self.requested_solver_step,
                "solver_time_s": float(t),
                "public_boundary_state": result.selection.boundary_regime.value,
                "outward_internal_model": result.selection.outward_flow_model.value,
                "transition_count_for_request": len(result.transition_events),
                "context_restored_without_root_reconstruction": True,
                "flux_modified_by_manager": False,
                "restored_flux_rho": float(expected_flux[0]),
                "restored_flux_momentum": float(expected_flux[1]),
                "restored_flux_energy": float(expected_flux[2]),
                "restored_flux_rho_xv": float(expected_flux[3]),
                "restoration_gate_passed": restoration_passed,
            }
        )
        if not restoration_passed:
            raise _BASE.Increment9LStop(
                "SUCCESSFUL_CONTEXT_RESTORATION_MISMATCH",
                "manager commit did not preserve the exact successful delegate context",
            )

    def _append_legacy_transition_event(
        self,
        *,
        event: ModelTransitionEvent,
        request: DelegateTransitionRequested,
    ) -> None:
        if (
            event.axis is not request.axis
            or event.trigger_classification != request.classification
            or event.observed_solver_step != request.observed_solver_step
            or event.solver_time_s != request.solver_time_s
            or event.absolute_step_number_trigger_used
        ):
            raise _BASE.Increment9LStop(
                "MANAGER_TRANSITION_EVIDENCE_MISMATCH",
                "committed manager event does not match delegate request",
            )

        if event.axis is ModelAxis.OUTWARD_FLOW_MODEL:
            self.outward_model_transition_events.append(
                {
                    "requested_solver_step": request.observed_solver_step,
                    "solver_time_s": request.solver_time_s,
                    "from_outward_model": event.from_state,
                    "to_outward_model": event.to_state,
                    "trigger_classification": event.trigger_classification,
                    "trigger_message": request.message,
                    "absolute_step_number_trigger_used": False,
                }
            )
            return

        if event.axis is ModelAxis.BOUNDARY_REGIME:
            self.boundary_transition_events.append(
                {
                    "requested_solver_step": request.observed_solver_step,
                    "solver_time_s": request.solver_time_s,
                    "from_boundary_state": event.from_state,
                    "to_boundary_state": event.to_state,
                    "trigger_classification": event.trigger_classification,
                    "trigger_message": request.message,
                    "failed_candidate_used_as_root": False,
                    "failed_candidate_used_as_flux": False,
                    "solver_state_mutated_before_transition": False,
                    "absolute_step_number_trigger_used": False,
                    "reentry_allowed": False,
                }
            )
            return

        raise _BASE.Increment9LStop(
            "UNREGISTERED_TRANSITION_AXIS",
            f"unsupported manager transition axis {event.axis.value}",
        )


def _manager_event_rows(
    manager: PhysicsBoundaryModelManager,
) -> list[dict[str, Any]]:
    return [event.as_dict() for event in manager.transition_history]


def _manager_selection_rows(
    manager: PhysicsBoundaryModelManager,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, selection in enumerate(manager.selection_history):
        event = manager.transition_history[index - 1] if index else None
        rows.append(
            {
                "selection_sequence": index,
                "after_transition_sequence": None if event is None else event.sequence,
                "transition_axis": None if event is None else event.axis.value,
                "trigger_classification": (
                    None if event is None else event.trigger_classification
                ),
                **selection.as_dict(),
            }
        )
    return rows


def _expected_manager_events(parent_dir: Path) -> list[dict[str, Any]]:
    outward = _read_csv(parent_dir / "outward_model_transition_events.csv")
    boundary = _read_csv(parent_dir / "boundary_transition_events.csv")
    if len(outward) != 1 or len(boundary) != 1:
        raise Increment9MA2Stop("parent transition evidence is not the expected 1 + 1")
    return [
        {
            "sequence": 1,
            "axis": ModelAxis.OUTWARD_FLOW_MODEL.value,
            "from_state": outward[0]["from_outward_model"],
            "to_state": outward[0]["to_outward_model"],
            "trigger_classification": outward[0]["trigger_classification"],
            "solver_time_s": float(outward[0]["solver_time_s"]),
            "observed_solver_step": int(outward[0]["requested_solver_step"]),
            "absolute_step_number_trigger_used": False,
        },
        {
            "sequence": 2,
            "axis": ModelAxis.BOUNDARY_REGIME.value,
            "from_state": boundary[0]["from_boundary_state"],
            "to_state": boundary[0]["to_boundary_state"],
            "trigger_classification": boundary[0]["trigger_classification"],
            "solver_time_s": float(boundary[0]["solver_time_s"]),
            "observed_solver_step": int(boundary[0]["requested_solver_step"]),
            "absolute_step_number_trigger_used": False,
        },
    ]


def _postprocess(
    *,
    output: Path,
    parent_dir: Path,
    parent_authority_json: Path,
    a2_model_review_spec: Path,
    a1_model_review_spec: Path,
    source_git_sha: str,
) -> dict[str, Any]:
    instance = ModelManagedLiveFvmHook.last_instance
    if instance is None:
        raise Increment9MA2Stop("model-managed live FVM hook was not created")

    parent_authority = json.loads(parent_authority_json.read_text(encoding="utf-8"))
    parent_summary = json.loads((parent_dir / "summary.json").read_text(encoding="utf-8"))
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    authority_gate = bool(
        parent_authority.get("live_metadata_verified") is True
        and parent_authority.get("source_git_sha") == PARENT_SOURCE_SHA
        and int(parent_authority.get("workflow_run")) == PARENT_RUN_ID
        and int(parent_authority.get("workflow_job")) == PARENT_JOB_ID
        and int(parent_authority.get("artifact_id")) == PARENT_ARTIFACT_ID
        and parent_authority.get("artifact_name") == PARENT_ARTIFACT_NAME
        and parent_authority.get("artifact_sha256") == PARENT_ARTIFACT_SHA256
        and parent_authority.get("artifact_expired") is False
        and parent_summary.get("source_git_sha") == PARENT_SOURCE_SHA
        and parent_summary.get("starting_state_sha256")
        == PARENT_STARTING_STATE_SHA256
        and parent_summary.get("final_state_sha256") == PARENT_FINAL_STATE_SHA256
    )

    exact_fields = (
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
    field_comparison = {
        name: {
            "parent": parent_summary.get(name),
            "a2": summary.get(name),
            "exact_match": summary.get(name) == parent_summary.get(name),
        }
        for name in exact_fields
    }

    exact_file_names = (
        "step_metrics.csv",
        "boundary_state_history.csv",
        "outward_model_transition_events.csv",
        "boundary_transition_events.csv",
        "three_branch_algorithm_transition_events.csv",
        "finite_compression_bounded_window_fallback_events.csv",
        "guard_front_root_topology_correction_events.csv",
    )
    file_comparison = {
        name: {
            "parent_sha256": _sha256(parent_dir / name),
            "a2_sha256": _sha256(output / name),
            "exact_match": _sha256(parent_dir / name) == _sha256(output / name),
        }
        for name in exact_file_names
    }

    manager_rows = _manager_event_rows(instance.model_manager)
    expected_manager_rows = _expected_manager_events(parent_dir)
    manager_transition_gate = manager_rows == expected_manager_rows
    selection_rows = _manager_selection_rows(instance.model_manager)
    restoration_rows = list(instance.model_manager_context_restoration_rows)
    restoration_gate = bool(
        len(restoration_rows) == int(summary["accepted_steps_completed"])
        and all(bool(row["restoration_gate_passed"]) for row in restoration_rows)
        and all(
            row["context_restored_without_root_reconstruction"] is True
            and row["flux_modified_by_manager"] is False
            for row in restoration_rows
        )
    )

    exact_equivalence_gate = bool(
        authority_gate
        and all(row["exact_match"] for row in field_comparison.values())
        and all(row["exact_match"] for row in file_comparison.values())
        and manager_transition_gate
        and len(selection_rows) == 3
        and restoration_gate
        and summary.get("increment_9l_state_machine_gate_passed") is True
        and summary.get("target_horizon_reached") is True
        and summary.get("stop_classification") is None
        and summary.get("stop_reason") is None
    )

    _write_csv(output / MANAGER_EVENTS_FILE, manager_rows)
    _write_csv(output / MANAGER_SELECTION_FILE, selection_rows)
    _write_csv(output / RESTORATION_FILE, restoration_rows)
    (output / PARENT_AUTHORITY_FILE).write_text(
        json.dumps(parent_authority, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    comparison = {
        "schema_version": "stage7_u3_b2_a1_increment_9m_a2_behavioral_comparison_v1",
        "parent_source_git_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_RUN_ID,
        "parent_workflow_job": PARENT_JOB_ID,
        "parent_artifact_id": PARENT_ARTIFACT_ID,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_authority_gate_passed": authority_gate,
        "exact_field_comparison": field_comparison,
        "exact_file_comparison": file_comparison,
        "expected_manager_transition_events": expected_manager_rows,
        "actual_manager_transition_events": manager_rows,
        "manager_transition_gate_passed": manager_transition_gate,
        "successful_context_restoration_gate_passed": restoration_gate,
        "exact_increment_9l_behavioral_equivalence_passed": exact_equivalence_gate,
    }
    (output / COMPARISON_FILE).write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    integration = {
        "schema_version": "stage7_u3_b2_a1_increment_9m_a2_live_composition_v1",
        "source_git_sha": source_git_sha,
        "a2_model_review_spec": str(a2_model_review_spec),
        "a2_model_review_spec_sha256": _sha256(a2_model_review_spec),
        "a1_model_review_spec": str(a1_model_review_spec),
        "a1_model_review_spec_sha256": _sha256(a1_model_review_spec),
        "model_manager_profile": instance.model_manager.profile_name,
        "manager_transition_count": len(manager_rows),
        "selection_history_count": len(selection_rows),
        "successful_context_restoration_count": len(restoration_rows),
        "context_restored_without_root_reconstruction": restoration_gate,
        "physics_flux_modified_by_manager": False,
        "one_fvm_solver_instance": summary.get("single_fvm_solver_instance") is True,
        "checkpoint_state_used": False,
        "absolute_step_number_transition_condition_used": False,
        "increment_9l_delegate_equations_changed": False,
        "physics_model_manager_changed": False,
        "fvm_solver_changed": False,
        "b1_changed": False,
        "locked_contract_changed": False,
        "production_adapter_changed": False,
        "root_tolerance_changed": False,
        "chi_cap_changed": False,
        "exact_increment_9l_behavioral_equivalence_passed": exact_equivalence_gate,
    }
    (output / INTEGRATION_FILE).write_text(
        json.dumps(integration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary.update(
        {
            "schema_version": (
                "stage7_u3_b2_a1_increment_9m_a2_live_fvm_composition_v1"
            ),
            "increment_9m_a2_model_managed_live_fvm_composition": True,
            "increment_9m_a2_model_manager_profile": (
                instance.model_manager.profile_name
            ),
            "increment_9m_a2_manager_transition_count": len(manager_rows),
            "increment_9m_a2_selection_history_count": len(selection_rows),
            "increment_9m_a2_context_restoration_count": len(restoration_rows),
            "increment_9m_a2_parent_authority_gate_passed": authority_gate,
            "increment_9m_a2_manager_transition_gate_passed": (
                manager_transition_gate
            ),
            "increment_9m_a2_context_restoration_gate_passed": restoration_gate,
            "increment_9m_a2_exact_increment_9l_behavioral_equivalence_passed": (
                exact_equivalence_gate
            ),
            "outcome": OUTCOME if exact_equivalence_gate else "INCREMENT_9M_A2_STOPPED",
            "working_vertical_slice": exact_equivalence_gate,
            "working_vertical_slice_kind": (
                "PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE"
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
        + "\n## Increment 9M A2 model-managed live FVM composition\n\n"
        + "The A0 manager and A1 transactional composer were placed in the "
        + "actual Increment 9L boundary-flux path. After each successful manager "
        + "commit, the exact delegate context and flux were restored through the "
        + "existing hook cache installation method without root or EOS "
        + "reconstruction. The resulting accepted-step evidence and final state "
        + "were compared exactly with the immutable Increment 9L authority.\n\n"
        + "```json\n"
        + json.dumps(comparison, indent=2, sort_keys=True)
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

    if not exact_equivalence_gate:
        raise Increment9MA2Stop(
            "Increment 9M A2 exact Increment 9L behavioral equivalence gate failed"
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
    parser.add_argument("--a1-model-review-spec", type=Path, required=True)
    parser.add_argument("--a2-model-review-spec", type=Path, required=True)
    parser.add_argument("--parent-artifact-dir", type=Path, required=True)
    parser.add_argument("--parent-authority-json", type=Path, required=True)
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
        args.a1_model_review_spec,
        args.a2_model_review_spec,
        args.parent_artifact_dir / "summary.json",
        args.parent_authority_json,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    legacy_v5.BoundedWindowTwoStateBoundaryStateMachineHook = ModelManagedLiveFvmHook
    ModelManagedLiveFvmHook.last_instance = None

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
            "--bounded-window-correction-spec",
            str(args.bounded_window_correction_spec),
            "--output-dir",
            str(args.output_dir),
            "--source-git-sha",
            args.source_git_sha,
        ]
        legacy_v5.main()
    finally:
        sys.argv = original_argv

    summary = _postprocess(
        output=args.output_dir,
        parent_dir=args.parent_artifact_dir,
        parent_authority_json=args.parent_authority_json,
        a2_model_review_spec=args.a2_model_review_spec,
        a1_model_review_spec=args.a1_model_review_spec,
        source_git_sha=args.source_git_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
