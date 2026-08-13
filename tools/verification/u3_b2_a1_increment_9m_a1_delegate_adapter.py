"""Adapter for existing Increment 9L preparation methods.

No physical equation, root search, or flux formula is implemented here.
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
    OutwardFlowModel,
)


DELEGATE_SOURCE: Final[str] = "INCREMENT_9L_EXISTING_PREPARE_METHODS"


class DelegateTransitionRequested(RuntimeError):
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


class Increment9LHookDelegateAdapter:
    """Route manager selections to bound Increment 9L prepare methods."""

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
        self.hook = hook
        hook._switch_outward_model = MethodType(
            self._request_finite_transition,
            hook,
        )
        hook._transition_to_closed = MethodType(
            self._request_closed_transition,
            hook,
        )

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
        self.hook.boundary_state = selection.boundary_regime.value
        self.hook.outward_model = selection.outward_flow_model.value
        self.hook.requested_solver_step = observed_solver_step
        if selection.boundary_regime is BoundaryRegime.ZERO_TRANSFER_CLOSED:
            events = [
                event
                for event in transition_history
                if event.axis is ModelAxis.BOUNDARY_REGIME
            ]
            if events:
                self.hook.closure_trigger_classification = (
                    events[-1].trigger_classification
                )
                self.hook.closure_trigger_message = (
                    "accepted by PhysicsBoundaryModelManager"
                )
        self.hook._invalidate_cache()

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
                self.hook._prepare_closed(
                    request.conserved_state,
                    request.solver_time_s,
                )
            elif (
                selection.outward_flow_model
                is OutwardFlowModel.THREE_BRANCH_WAVE_MODEL
            ):
                self.hook._prepare_three_branch(
                    request.conserved_state,
                    request.solver_time_s,
                )
            elif (
                selection.outward_flow_model
                is OutwardFlowModel.GENERAL_EOS_FINITE_COMPRESSION
            ):
                self.hook._prepare_finite(
                    request.conserved_state,
                    request.solver_time_s,
                )
            else:
                raise DelegateEvaluationFailed(
                    "UNREGISTERED_MODEL_SELECTION",
                    selection.outward_flow_model.value,
                )
        except DelegateTransitionRequested:
            raise
        except DelegateEvaluationFailed:
            raise
        except Exception as exc:
            classification = str(
                getattr(exc, "classification", type(exc).__name__)
            )
            raise DelegateEvaluationFailed(
                classification,
                f"{type(exc).__name__}: {exc}",
            ) from exc

        context = getattr(self.hook, "root_context", None)
        if not isinstance(context, dict):
            raise DelegateEvaluationFailed(
                "DELEGATE_CONTEXT_MISSING",
                "selected delegate did not install a context",
            )
        return dict(context)
