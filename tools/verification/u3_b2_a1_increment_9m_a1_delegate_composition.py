"""Verification-side composition of the 9M manager and existing 9L delegates.

This module contains no flow equation, EOS closure, root search, or flux formula.
It routes an evaluation request to bound Increment 9L preparation methods and
stages any requested model transition in a shadow manager before committing it.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MethodType
from typing import Any, Final

from liquid_gas_transient.physics_model_manager import (
    BoundaryRegime,
    ModelAxis,
    ModelSelection,
    ModelTransitionEvent,
    ModelTransitionRejected,
    OutwardFlowModel,
    PhysicsBoundaryModelManager,
)


DELEGATE_SOURCE: Final[str] = "INCREMENT_9L_EXISTING_PREPARE_METHODS"
MAX_TRANSITIONS_PER_EVALUATION: Final[int] = 2


class DelegateTransitionRequested(RuntimeError):
    """A legacy preparation method requested a registered manager transition."""

    def __init__(
        self,
        *,
        axis: ModelAxis,
        classification: str,
        message: str,
        solver_time_s: float,
        observed_solver_step: int | None,
    ) -> None:
        super().__init__(message)
        self.axis = axis
        self.classification = classification
        self.message = message
        self.solver_time_s = float(solver_time_s)
        self.observed_solver_step = observed_solver_step


class DelegateEvaluationFailed(RuntimeError):
    """An existing delegate failed without requesting a supported transition."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


class DelegateCompositionFailed(RuntimeError):
    """Fail-closed A1 integration error."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


@dataclass(frozen=True)
class DelegateEvaluationRequest:
    conserved_state: Any
    solver_time_s: float
    observed_solver_step: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.solver_time_s, bool):
            raise ValueError("solver_time_s must be finite and non-negative")
        numeric_time = float(self.solver_time_s)
        if not math.isfinite(numeric_time) or numeric_time < 0.0:
            raise ValueError("solver_time_s must be finite and non-negative")
        if self.observed_solver_step is not None and (
            isinstance(self.observed_solver_step, bool)
            or not isinstance(self.observed_solver_step, int)
            or self.observed_solver_step < 0
        ):
            raise ValueError(
                "observed_solver_step must be a non-negative integer or None"
            )


@dataclass(frozen=True)
class ComposedDelegateResult:
    context: dict[str, Any]
    selection: ModelSelection
    transition_events: tuple[ModelTransitionEvent, ...]


class Increment9LHookDelegateAdapter:
    """Bind manager selection to the existing Increment 9L prepare methods.

    The wrapped hook is expected to provide `_prepare_three_branch`,
    `_prepare_finite`, `_prepare_closed`, `_invalidate_cache`, and
    `root_context`. The two legacy transition callbacks are replaced only on
    this hook instance so that they request a manager transition instead of
    mutating legacy state.
    """

    _REQUIRED_METHODS: Final[tuple[str, ...]] = (
        "_prepare_three_branch",
        "_prepare_finite",
        "_prepare_closed",
        "_invalidate_cache",
    )

    def __init__(self, hook: Any) -> None:
        missing = [
            name
            for name in self._REQUIRED_METHODS
            if not callable(getattr(hook, name, None))
        ]
        if missing:
            raise TypeError(
                "Increment 9L hook is missing required delegate methods: "
                + ", ".join(missing)
            )
        if not hasattr(hook, "root_context"):
            raise TypeError("Increment 9L hook must expose root_context")
        self._hook = hook
        hook._switch_outward_model = MethodType(
            self._request_finite_transition,
            hook,
        )
        hook._transition_to_closed = MethodType(
            self._request_closed_transition,
            hook,
        )

    @property
    def hook(self) -> Any:
        return self._hook

    @staticmethod
    def _request_finite_transition(
        legacy_hook: Any,
        *,
        t: float,
        classification: str,
        message: str,
    ) -> None:
        raise DelegateTransitionRequested(
            axis=ModelAxis.OUTWARD_FLOW_MODEL,
            classification=str(classification),
            message=str(message),
            solver_time_s=float(t),
            observed_solver_step=getattr(
                legacy_hook,
                "requested_solver_step",
                None,
            ),
        )

    @staticmethod
    def _request_closed_transition(
        legacy_hook: Any,
        *,
        t: float,
        classification: str,
        message: str,
    ) -> None:
        raise DelegateTransitionRequested(
            axis=ModelAxis.BOUNDARY_REGIME,
            classification=str(classification),
            message=str(message),
            solver_time_s=float(t),
            observed_solver_step=getattr(
                legacy_hook,
                "requested_solver_step",
                None,
            ),
        )

    def sync_selection(
        self,
        selection: ModelSelection,
        transition_history: tuple[ModelTransitionEvent, ...],
        *,
        observed_solver_step: int | None,
    ) -> None:
        self._hook.boundary_state = selection.boundary_regime.value
        self._hook.outward_model = selection.outward_flow_model.value
        self._hook.requested_solver_step = observed_solver_step

        if selection.boundary_regime is BoundaryRegime.ZERO_TRANSFER_CLOSED:
            boundary_events = [
                event
                for event in transition_history
                if event.axis is ModelAxis.BOUNDARY_REGIME
            ]
            if boundary_events:
                event = boundary_events[-1]
                self._hook.closure_trigger_classification = (
                    event.trigger_classification
                )
                self._hook.closure_trigger_message = (
                    "accepted by PhysicsBoundaryModelManager"
                )

        self._hook._invalidate_cache()

    def evaluate(
        self,
        *,
        selection: ModelSelection,
        transition_history: tuple[ModelTransitionEvent, ...],
        request: DelegateEvaluationRequest,
    ) -> dict[str, Any]:
        self.sync_selection(
            selection,
            transition_history,
            observed_solver_step=request.observed_solver_step,
        )

        try:
            if selection.boundary_regime is BoundaryRegime.ZERO_TRANSFER_CLOSED:
                self._hook._prepare_closed(
                    request.conserved_state,
                    request.solver_time_s,
                )
            elif (
                selection.outward_flow_model
                is OutwardFlowModel.THREE_BRANCH_WAVE_MODEL
            ):
                self._hook._prepare_three_branch(
                    request.conserved_state,
                    request.solver_time_s,
                )
            elif (
                selection.outward_flow_model
                is OutwardFlowModel.GENERAL_EOS_FINITE_COMPRESSION
            ):
                self._hook._prepare_finite(
                    request.conserved_state,
                    request.solver_time_s,
                )
            else:
                raise DelegateCompositionFailed(
                    "UNREGISTERED_MODEL_SELECTION",
                    f"unsupported outward model {selection.outward_flow_model.value}",
                )
        except DelegateTransitionRequested:
            raise
        except DelegateCompositionFailed:
            raise
        except Exception as exc:
            classification = str(
                getattr(exc, "classification", type(exc).__name__)
            )
            raise DelegateEvaluationFailed(
                classification,
                f"{type(exc).__name__}: {exc}",
            ) from exc

        context = getattr(self._hook, "root_context", None)
        if not isinstance(context, dict):
            raise DelegateEvaluationFailed(
                "DELEGATE_CONTEXT_MISSING",
                "selected Increment 9L delegate did not install a context",
            )
        return dict(context)


class ModelManagedIncrement9LDelegateComposer:
    """Transactionally compose the A0 manager with existing 9L delegates."""

    def __init__(
        self,
        *,
        manager: PhysicsBoundaryModelManager,
        adapter: Increment9LHookDelegateAdapter,
    ) -> None:
        self.manager = manager
        self.adapter = adapter

    def evaluate(
        self,
        *,
        conserved_state: Any,
        solver_time_s: float,
        observed_solver_step: int | None = None,
    ) -> ComposedDelegateResult:
        try:
            request = DelegateEvaluationRequest(
                conserved_state=conserved_state,
                solver_time_s=solver_time_s,
                observed_solver_step=observed_solver_step,
            )
        except (TypeError, ValueError) as exc:
            raise DelegateCompositionFailed(
                "INVALID_EVALUATION_OBSERVATION",
                str(exc),
            ) from exc

        real_identity = self._manager_identity(self.manager)
        shadow = self._clone_manager(self.manager)
        staged_requests: list[DelegateTransitionRequested] = []

        try:
            for _ in range(MAX_TRANSITIONS_PER_EVALUATION + 1):
                try:
                    context = self.adapter.evaluate(
                        selection=shadow.selection,
                        transition_history=shadow.transition_history,
                        request=request,
                    )
                except DelegateTransitionRequested as transition_request:
                    if len(staged_requests) >= MAX_TRANSITIONS_PER_EVALUATION:
                        raise DelegateCompositionFailed(
                            "TRANSITION_CHAIN_LIMIT_EXCEEDED",
                            "more than two transitions were requested for one evaluation",
                        )
                    self._apply_transition(shadow, transition_request)
                    staged_requests.append(transition_request)
                    continue
                except DelegateEvaluationFailed as exc:
                    raise DelegateCompositionFailed(
                        exc.classification,
                        str(exc),
                    ) from exc

                self._validate_context_identity(context, shadow.selection)
                if self._manager_identity(self.manager) != real_identity:
                    raise DelegateCompositionFailed(
                        "AUTHORITATIVE_MANAGER_CHANGED_DURING_EVALUATION",
                        "real manager changed before staged transition commit",
                    )

                event_count_before = len(self.manager.transition_history)
                for transition_request in staged_requests:
                    self._apply_transition(self.manager, transition_request)
                committed_events = self.manager.transition_history[
                    event_count_before:
                ]

                self.adapter.sync_selection(
                    self.manager.selection,
                    self.manager.transition_history,
                    observed_solver_step=observed_solver_step,
                )
                result_context = dict(context)
                result_context.update(
                    {
                        "model_manager_profile": self.manager.profile_name,
                        "model_manager_selection": (
                            self.manager.selection.as_dict()
                        ),
                        "model_manager_transition_events_for_request": [
                            event.as_dict() for event in committed_events
                        ],
                        "model_manager_transition_count_for_request": len(
                            committed_events
                        ),
                        "absolute_step_number_trigger_used": False,
                        "physics_flux_modified_by_manager": False,
                        "delegate_source": DELEGATE_SOURCE,
                    }
                )
                return ComposedDelegateResult(
                    context=result_context,
                    selection=self.manager.selection,
                    transition_events=tuple(committed_events),
                )

            raise DelegateCompositionFailed(
                "DELEGATE_EVALUATION_DID_NOT_CONVERGE",
                "delegate routing exhausted the transition loop",
            )
        except Exception:
            self.adapter.sync_selection(
                self.manager.selection,
                self.manager.transition_history,
                observed_solver_step=observed_solver_step,
            )
            if self._manager_identity(self.manager) != real_identity:
                raise DelegateCompositionFailed(
                    "TRANSACTIONAL_ROLLBACK_FAILURE",
                    "real manager changed during a failed staged evaluation",
                )
            raise

    @staticmethod
    def _apply_transition(
        manager: PhysicsBoundaryModelManager,
        request: DelegateTransitionRequested,
    ) -> ModelTransitionEvent:
        try:
            if request.axis is ModelAxis.OUTWARD_FLOW_MODEL:
                return manager.activate_finite_compression(
                    trigger_classification=request.classification,
                    solver_time_s=request.solver_time_s,
                    observed_solver_step=request.observed_solver_step,
                )
            if request.axis is ModelAxis.BOUNDARY_REGIME:
                return manager.close_zero_transfer(
                    trigger_classification=request.classification,
                    solver_time_s=request.solver_time_s,
                    observed_solver_step=request.observed_solver_step,
                )
        except ModelTransitionRejected as exc:
            raise DelegateCompositionFailed(
                exc.classification,
                str(exc),
            ) from exc
        raise DelegateCompositionFailed(
            "UNREGISTERED_TRANSITION_AXIS",
            f"unsupported transition axis {request.axis.value}",
        )

    @classmethod
    def _clone_manager(
        cls,
        source: PhysicsBoundaryModelManager,
    ) -> PhysicsBoundaryModelManager:
        clone = PhysicsBoundaryModelManager()
        for event in source.transition_history:
            request = DelegateTransitionRequested(
                axis=event.axis,
                classification=event.trigger_classification,
                message="replay accepted manager history",
                solver_time_s=(
                    0.0 if event.solver_time_s is None else event.solver_time_s
                ),
                observed_solver_step=event.observed_solver_step,
            )
            cls._apply_transition(clone, request)
        if clone.selection != source.selection:
            raise DelegateCompositionFailed(
                "MANAGER_HISTORY_REPLAY_MISMATCH",
                "selection reconstructed from history does not match source",
            )
        return clone

    @staticmethod
    def _manager_identity(
        manager: PhysicsBoundaryModelManager,
    ) -> tuple[ModelSelection, tuple[ModelTransitionEvent, ...]]:
        return manager.selection, manager.transition_history

    @staticmethod
    def _validate_context_identity(
        context: dict[str, Any],
        selection: ModelSelection,
    ) -> None:
        public_state = context.get("public_boundary_state")
        if public_state != selection.boundary_regime.value:
            raise DelegateCompositionFailed(
                "DELEGATE_CONTEXT_SELECTION_MISMATCH",
                "delegate public boundary state does not match staged manager",
            )

        outward_model = context.get("outward_internal_model")
        if selection.boundary_regime is BoundaryRegime.OUTWARD_FLOW:
            if outward_model != selection.outward_flow_model.value:
                raise DelegateCompositionFailed(
                    "DELEGATE_CONTEXT_SELECTION_MISMATCH",
                    "delegate outward model does not match staged manager",
                )
        elif outward_model is not None:
            raise DelegateCompositionFailed(
                "DELEGATE_CONTEXT_SELECTION_MISMATCH",
                "closed delegate must not report an active outward model",
            )


__all__ = [
    "ComposedDelegateResult",
    "DELEGATE_SOURCE",
    "DelegateCompositionFailed",
    "DelegateEvaluationFailed",
    "DelegateEvaluationRequest",
    "DelegateTransitionRequested",
    "Increment9LHookDelegateAdapter",
    "ModelManagedIncrement9LDelegateComposer",
]
