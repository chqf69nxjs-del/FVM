"""Working Tool W0 result, warning, and transition contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

import numpy as np

from .case_schema import ModelProfile


RESULT_SCHEMA_VERSION = "stage7_u3_b2_a1_working_tool_result_v0"
PROVISIONAL_WARNING_CODE = "PROVISIONAL_ENGINEERING_MODEL"


class WarningSeverity(str, Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class TransitionRecord:
    """Transition evidence; observed step/time are not transition criteria."""

    axis: str
    from_state: str
    to_state: str
    trigger_classification: str
    solver_time_s: float
    observed_solver_step: int
    absolute_step_number_trigger_used: bool = False

    def __post_init__(self) -> None:
        for name in ("axis", "from_state", "to_state", "trigger_classification"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if not np.isfinite(self.solver_time_s) or self.solver_time_s < 0.0:
            raise ValueError("solver_time_s must be finite and non-negative")
        if self.observed_solver_step < 0:
            raise ValueError("observed_solver_step must be non-negative")
        if self.absolute_step_number_trigger_used:
            raise ValueError("absolute solver-step transition criteria are forbidden")

    def as_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "trigger_classification": self.trigger_classification,
            "solver_time_s": self.solver_time_s,
            "observed_solver_step": self.observed_solver_step,
            "absolute_step_number_trigger_used": False,
        }


@dataclass(frozen=True)
class WorkingToolWarning:
    code: str
    severity: WarningSeverity
    message: str

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("warning code must be non-empty")
        if not self.message.strip():
            raise ValueError("warning message must be non-empty")

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
        }


PROVISIONAL_MODEL_WARNING = WorkingToolWarning(
    code=PROVISIONAL_WARNING_CODE,
    severity=WarningSeverity.WARNING,
    message=(
        "This run includes a provisional engineering model. Results are not "
        "VERIFIED, ACCEPTED, VALIDATED, or DESIGN-USE APPROVED."
    ),
)


@dataclass(frozen=True)
class BackendRunData:
    """Backend payload before the public W0 disclosure wrapper is applied."""

    summary: Mapping[str, Any] = field(default_factory=dict)
    history: tuple[Mapping[str, Any], ...] = ()
    transitions: tuple[TransitionRecord, ...] = ()
    state_history: Mapping[str, np.ndarray] = field(default_factory=dict)
    warnings: tuple[WorkingToolWarning, ...] = ()


@dataclass(frozen=True)
class WorkingToolResult:
    """Normal-user result contract for Working Tool W0."""

    case_id: str
    model_profile: ModelProfile
    summary: Mapping[str, Any]
    history: tuple[Mapping[str, Any], ...]
    transitions: tuple[TransitionRecord, ...]
    state_history: Mapping[str, np.ndarray]
    warnings: tuple[WorkingToolWarning, ...]
    schema_version: str = RESULT_SCHEMA_VERSION
    verified: bool = False
    accepted: bool = False
    validated: bool = False
    design_use_approved: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != RESULT_SCHEMA_VERSION:
            raise ValueError(f"unsupported result schema_version: {self.schema_version}")
        if any((self.verified, self.accepted, self.validated, self.design_use_approved)):
            raise ValueError("W0 formal authority flags must remain false")
        if PROVISIONAL_WARNING_CODE not in {warning.code for warning in self.warnings}:
            raise ValueError("mandatory provisional engineering warning is missing")


RESERVED_SUMMARY_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "model_profile",
        "verified",
        "accepted",
        "validated",
        "design_use_approved",
        "warning_codes",
    }
)
