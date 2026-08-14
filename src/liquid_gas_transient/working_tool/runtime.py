"""Backend-independent public execution facade for the Working Tool shell."""

from __future__ import annotations

from typing import Any

import numpy as np

from .backend import WorkingToolBackend
from .case_schema import WorkingToolCase
from .results import (
    BackendRunData,
    PROVISIONAL_MODEL_WARNING,
    PROVISIONAL_WARNING_CODE,
    TransitionRecord,
    WorkingToolResult,
    WorkingToolWarning,
)


def execute_case(
    case: WorkingToolCase,
    backend: WorkingToolBackend,
) -> WorkingToolResult:
    """Execute one validated case through an injected runtime backend.

    The public facade knows only the backend protocol and result contracts.  It
    deliberately contains no verification-runner, workflow, artifact, or A2
    authority dependency.
    """

    if not isinstance(case, WorkingToolCase):
        raise TypeError("case must be WorkingToolCase")
    run_case = getattr(backend, "run_case", None)
    if not callable(run_case):
        raise TypeError("backend must implement run_case(case)")

    data = run_case(case)
    if not isinstance(data, BackendRunData):
        raise TypeError("backend.run_case must return BackendRunData")

    history = tuple(dict(row) for row in data.history)
    transitions = tuple(data.transitions)
    if not all(isinstance(row, TransitionRecord) for row in transitions):
        raise TypeError("backend transitions must be TransitionRecord values")

    state_history: dict[str, np.ndarray] = {}
    for name, values in data.state_history.items():
        key = str(name)
        if not key:
            raise ValueError("state-history names must be non-empty")
        state_history[key] = np.array(values, copy=True)

    additional_warnings: list[WorkingToolWarning] = []
    seen_codes = {PROVISIONAL_WARNING_CODE}
    for warning in data.warnings:
        if not isinstance(warning, WorkingToolWarning):
            raise TypeError("backend warnings must be WorkingToolWarning values")
        if warning.code in seen_codes:
            continue
        seen_codes.add(warning.code)
        additional_warnings.append(warning)

    return WorkingToolResult(
        case_id=case.case_id,
        model_profile=case.model_profile,
        summary=dict(data.summary),
        history=history,
        transitions=transitions,
        state_history=state_history,
        warnings=(PROVISIONAL_MODEL_WARNING, *additional_warnings),
    )
