"""Pure control layer for the Increment 9M model-selection profile.

The module has no CoolProp or solver dependency.  Solver time and step are
recorded as evidence only; they never authorize a transition.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Any, Final


FINITE_COMPRESSION_MODEL_REQUIRED: Final[str] = "FINITE_COMPRESSION_MODEL_REQUIRED"
NO_ADMISSIBLE_ISLAND: Final[str] = "NO_ADMISSIBLE_ISLAND"


class ModelAxis(str, Enum):
    THERMODYNAMIC_REGIME = "thermodynamic_regime"
    BULK_FLOW_MODEL = "bulk_flow_model"
    BOUNDARY_REGIME = "boundary_regime"
    OUTWARD_FLOW_MODEL = "outward_flow_model"


class ThermodynamicRegime(str, Enum):
    LIQUID = "LIQUID"


class BulkFlowModel(str, Enum):
    SINGLE_PHASE_FVM = "SINGLE_PHASE_FVM"


class BoundaryRegime(str, Enum):
    OUTWARD_FLOW = "OUTWARD_FLOW"
    ZERO_TRANSFER_CLOSED = "ZERO_TRANSFER_CLOSED"


class OutwardFlowModel(str, Enum):
    THREE_BRANCH_WAVE_MODEL = "THREE_BRANCH_WAVE_MODEL"
    GENERAL_EOS_FINITE_COMPRESSION = "GENERAL_EOS_FINITE_COMPRESSION"


@dataclass(frozen=True)
class ModelSelection:
    thermodynamic_regime: ThermodynamicRegime = ThermodynamicRegime.LIQUID
    bulk_flow_model: BulkFlowModel = BulkFlowModel.SINGLE_PHASE_FVM
    boundary_regime: BoundaryRegime = BoundaryRegime.OUTWARD_FLOW
    outward_flow_model: OutwardFlowModel = OutwardFlowModel.THREE_BRANCH_WAVE_MODEL

    def as_dict(self) -> dict[str, str]:
        return {
            "thermodynamic_regime": self.thermodynamic_regime.value,
            "bulk_flow_model": self.bulk_flow_model.value,
            "boundary_regime": self.boundary_regime.value,
            "outward_flow_model": self.outward_flow_model.value,
        }


@dataclass(frozen=True)
class ModelTransitionEvent:
    sequence: int
    axis: ModelAxis
    from_state: str
    to_state: str
    trigger_classification: str
    solver_time_s: float | None
    observed_solver_step: int | None
    absolute_step_number_trigger_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "axis": self.axis.value,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "trigger_classification": self.trigger_classification,
            "solver_time_s": self.solver_time_s,
            "observed_solver_step": self.observed_solver_step,
            "absolute_step_number_trigger_used": self.absolute_step_number_trigger_used,
        }


class ModelTransitionRejected(RuntimeError):
    """Explicit fail-closed control-layer rejection."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


class PhysicsBoundaryModelManager:
    """Narrow two-transition manager demonstrated by Increment 9L."""

    profile_name: Final[str] = "U3_B2_A1_INCREMENT_9M_A0"

    def __init__(self) -> None:
        self._selection = ModelSelection()
        self._events: list[ModelTransitionEvent] = []
        self._selection_history: list[ModelSelection] = [self._selection]

    @property
    def selection(self) -> ModelSelection:
        return self._selection

    @property
    def transition_history(self) -> tuple[ModelTransitionEvent, ...]:
        return tuple(self._events)

    @property
    def selection_history(self) -> tuple[ModelSelection, ...]:
        return tuple(self._selection_history)

    def transition_history_as_dicts(self) -> list[dict[str, Any]]:
        return [event.as_dict() for event in self._events]

    def activate_finite_compression(
        self,
        *,
        trigger_classification: str,
        solver_time_s: float | None = None,
        observed_solver_step: int | None = None,
    ) -> ModelTransitionEvent:
        self._validate_observation(solver_time_s, observed_solver_step)
        if self._selection.boundary_regime is not BoundaryRegime.OUTWARD_FLOW:
            self._reject("TRANSITION_PRECONDITION_NOT_MET", "boundary is not outward")
        if (
            self._selection.outward_flow_model
            is OutwardFlowModel.GENERAL_EOS_FINITE_COMPRESSION
        ):
            self._reject("REPEATED_TRANSITION_NOT_SUPPORTED", "finite model is active")
        if trigger_classification != FINITE_COMPRESSION_MODEL_REQUIRED:
            self._reject("TRANSITION_TRIGGER_MISMATCH", "unexpected finite trigger")
        return self._apply(
            axis=ModelAxis.OUTWARD_FLOW_MODEL,
            from_state=self._selection.outward_flow_model.value,
            to_state=OutwardFlowModel.GENERAL_EOS_FINITE_COMPRESSION.value,
            trigger_classification=trigger_classification,
            solver_time_s=solver_time_s,
            observed_solver_step=observed_solver_step,
        )

    def close_zero_transfer(
        self,
        *,
        trigger_classification: str,
        solver_time_s: float | None = None,
        observed_solver_step: int | None = None,
    ) -> ModelTransitionEvent:
        self._validate_observation(solver_time_s, observed_solver_step)
        if self._selection.boundary_regime is BoundaryRegime.ZERO_TRANSFER_CLOSED:
            self._reject("REPEATED_TRANSITION_NOT_SUPPORTED", "boundary is closed")
        if (
            self._selection.outward_flow_model
            is not OutwardFlowModel.GENERAL_EOS_FINITE_COMPRESSION
        ):
            self._reject(
                "TRANSITION_PRECONDITION_NOT_MET",
                "finite-compression model must be active before closure",
            )
        if trigger_classification != NO_ADMISSIBLE_ISLAND:
            self._reject("TRANSITION_TRIGGER_MISMATCH", "unexpected closure trigger")
        return self._apply(
            axis=ModelAxis.BOUNDARY_REGIME,
            from_state=self._selection.boundary_regime.value,
            to_state=BoundaryRegime.ZERO_TRANSFER_CLOSED.value,
            trigger_classification=trigger_classification,
            solver_time_s=solver_time_s,
            observed_solver_step=observed_solver_step,
        )

    def request_reverse_boundary_transition(self) -> None:
        """Expose the explicit A0 re-entry rejection for integration callers."""

        self._reject("REVERSE_TRANSITION_NOT_SUPPORTED", "closed re-entry is disabled")

    def _apply(
        self,
        *,
        axis: ModelAxis,
        from_state: str,
        to_state: str,
        trigger_classification: str,
        solver_time_s: float | None,
        observed_solver_step: int | None,
    ) -> ModelTransitionEvent:
        if axis is ModelAxis.OUTWARD_FLOW_MODEL:
            next_selection = replace(
                self._selection,
                outward_flow_model=OutwardFlowModel(to_state),
            )
        elif axis is ModelAxis.BOUNDARY_REGIME:
            next_selection = replace(
                self._selection,
                boundary_regime=BoundaryRegime(to_state),
            )
        else:
            self._reject("UNREGISTERED_TRANSITION", f"unsupported axis {axis.value}")
        event = ModelTransitionEvent(
            sequence=len(self._events) + 1,
            axis=axis,
            from_state=from_state,
            to_state=to_state,
            trigger_classification=trigger_classification,
            solver_time_s=None if solver_time_s is None else float(solver_time_s),
            observed_solver_step=observed_solver_step,
            absolute_step_number_trigger_used=False,
        )
        self._selection = next_selection
        self._events.append(event)
        self._selection_history.append(next_selection)
        return event

    @staticmethod
    def _validate_observation(
        solver_time_s: float | None,
        observed_solver_step: int | None,
    ) -> None:
        if solver_time_s is not None:
            if isinstance(solver_time_s, bool):
                valid_time = False
            else:
                try:
                    numeric_time = float(solver_time_s)
                except (TypeError, ValueError):
                    valid_time = False
                else:
                    valid_time = math.isfinite(numeric_time) and numeric_time >= 0.0
            if not valid_time:
                raise ModelTransitionRejected(
                    "INVALID_TRANSITION_OBSERVATION",
                    "solver_time_s must be finite and non-negative",
                )
        if observed_solver_step is not None and (
            isinstance(observed_solver_step, bool)
            or not isinstance(observed_solver_step, int)
            or observed_solver_step < 0
        ):
            raise ModelTransitionRejected(
                "INVALID_TRANSITION_OBSERVATION",
                "observed_solver_step must be a non-negative integer",
            )

    @staticmethod
    def _reject(classification: str, message: str) -> None:
        raise ModelTransitionRejected(classification, message)
