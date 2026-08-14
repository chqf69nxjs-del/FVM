"""Post-solver state-history projection for Working Tool v0-B.

The solver/backend always produces the full ``WorkingToolResult`` first.  This
module validates that result and creates an independent public-storage
projection without mutating or sharing NumPy storage with the source result.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from numbers import Real
from typing import Mapping

import numpy as np

from .operation_policy import (
    WorkingToolStateStorageMode,
    storage_mode_for_sample_interval,
)
from .results import WorkingToolResult


WORKING_TOOL_PUBLIC_STATE_LAYOUT_VERSION = "WORKING_TOOL_PUBLIC_STATE_LAYOUT_V1"

SAMPLE_AXIS_STATE_ARRAYS = (
    "time_s",
    "conserved",
    "rho_kg_m3",
    "velocity_m_s",
    "pressure_pa",
    "temperature_k",
    "internal_energy_j_kg",
    "vapor_mass_fraction",
)
STATIC_STATE_ARRAYS = ("x_m",)
REQUIRED_STATE_ARRAYS = SAMPLE_AXIS_STATE_ARRAYS + STATIC_STATE_ARRAYS
_REQUIRED_STATE_ARRAY_SET = frozenset(REQUIRED_STATE_ARRAYS)
_SAMPLE_AXIS_STATE_ARRAY_SET = frozenset(SAMPLE_AXIS_STATE_ARRAYS)
_STATIC_STATE_ARRAY_SET = frozenset(STATIC_STATE_ARRAYS)
_PRIMITIVE_STATE_ARRAYS = (
    "rho_kg_m3",
    "velocity_m_s",
    "pressure_pa",
    "temperature_k",
    "internal_energy_j_kg",
    "vapor_mass_fraction",
)


class StateStorageProjectionError(ValueError):
    """Fail-closed classification for an invalid full-result projection."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


@dataclass(frozen=True)
class ValidatedFullStateLayout:
    """Validated dimensions needed by deterministic projection."""

    accepted_steps: int
    full_state_samples: int
    n_cells: int
    layout_version: str = WORKING_TOOL_PUBLIC_STATE_LAYOUT_VERSION


@dataclass(frozen=True)
class StateStorageProjection:
    """Independent projected result plus retained-index evidence."""

    result: WorkingToolResult
    retained_state_indices: tuple[int, ...]
    full_state_samples: int
    stored_state_samples: int
    state_sample_interval_accepted_steps: int
    storage_mode: WorkingToolStateStorageMode
    layout_version: str = WORKING_TOOL_PUBLIC_STATE_LAYOUT_VERSION

    @property
    def raw_state_payload_reduction_ratio(self) -> float:
        """Return sample-count-basis reduction, not measured file reduction."""

        return 1.0 - self.stored_state_samples / self.full_state_samples


def _fail(classification: str, message: str) -> None:
    raise StateStorageProjectionError(classification, message)


def _require_nonnegative_builtin_int(value: object, *, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be a built-in int")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def retained_state_indices(
    accepted_steps: object,
    state_sample_interval_accepted_steps: object,
) -> tuple[int, ...]:
    """Return ``{0} ∪ periodic accepted steps ∪ {final}`` in order."""

    resolved_steps = _require_nonnegative_builtin_int(
        accepted_steps,
        field_name="accepted_steps",
    )
    storage_mode_for_sample_interval(state_sample_interval_accepted_steps)
    interval = int(state_sample_interval_accepted_steps)

    if resolved_steps == 0:
        return (0,)

    retained = [0]
    retained.extend(range(interval, resolved_steps + 1, interval))
    if retained[-1] != resolved_steps:
        retained.append(resolved_steps)
    return tuple(retained)


def _require_float_array(
    state_history: Mapping[str, np.ndarray],
    name: str,
) -> np.ndarray:
    value = state_history[name]
    if not isinstance(value, np.ndarray):
        _fail(
            "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
            f"state_history[{name!r}] must be a numpy.ndarray",
        )
    if not np.issubdtype(value.dtype, np.floating):
        _fail(
            "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
            f"state_history[{name!r}] must have a real floating dtype",
        )
    if not bool(np.all(np.isfinite(value))):
        _fail(
            "WORKING_TOOL_V0_B_STATE_NONFINITE",
            f"state_history[{name!r}] contains a nonfinite value",
        )
    return value


def validate_full_state_result(
    result: WorkingToolResult,
) -> ValidatedFullStateLayout:
    """Validate the explicit v1 full-state layout and scalar-log alignment."""

    if not isinstance(result, WorkingToolResult):
        raise TypeError("result must be WorkingToolResult")

    if "accepted_steps" not in result.summary:
        _fail(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "summary.accepted_steps is missing",
        )
    try:
        accepted_steps = _require_nonnegative_builtin_int(
            result.summary["accepted_steps"],
            field_name="summary.accepted_steps",
        )
    except (TypeError, ValueError) as exc:
        _fail(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            str(exc),
        )

    if accepted_steps != len(result.history):
        _fail(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "summary.accepted_steps does not equal len(history)",
        )

    actual_names = frozenset(result.state_history)
    if actual_names != _REQUIRED_STATE_ARRAY_SET:
        missing = sorted(_REQUIRED_STATE_ARRAY_SET - actual_names)
        unknown = sorted(actual_names - _REQUIRED_STATE_ARRAY_SET)
        _fail(
            "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
            f"state array names are not exact; missing={missing}, unknown={unknown}",
        )

    arrays = {
        name: _require_float_array(result.state_history, name)
        for name in REQUIRED_STATE_ARRAYS
    }

    time_s = arrays["time_s"]
    x_m = arrays["x_m"]
    if time_s.ndim != 1:
        _fail(
            "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
            "time_s must have shape (samples,)",
        )
    if x_m.ndim != 1 or x_m.shape[0] < 1:
        _fail(
            "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
            "x_m must have non-empty shape (cells,)",
        )

    full_state_samples = accepted_steps + 1
    if time_s.shape[0] != full_state_samples:
        _fail(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "state sample count does not equal accepted_steps + 1",
        )

    for name in SAMPLE_AXIS_STATE_ARRAYS:
        if arrays[name].ndim < 1 or arrays[name].shape[0] != full_state_samples:
            _fail(
                "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
                f"sample-axis array {name!r} has an inconsistent leading dimension",
            )

    n_cells = int(x_m.shape[0])
    if arrays["conserved"].shape != (full_state_samples, n_cells, 4):
        _fail(
            "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
            "conserved must have shape (samples, cells, 4)",
        )
    for name in _PRIMITIVE_STATE_ARRAYS:
        if arrays[name].shape != (full_state_samples, n_cells):
            _fail(
                "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
                f"{name} must have shape (samples, cells)",
            )

    history_times: list[float] = []
    for expected_step, row in enumerate(result.history, start=1):
        if not isinstance(row, Mapping):
            _fail(
                "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
                f"history row {expected_step} is not a mapping",
            )
        if row.get("step") != expected_step or type(row.get("step")) is not int:
            _fail(
                "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
                "history steps must equal the exact sequence 1..accepted_steps",
            )
        history_time = row.get("time_s")
        if isinstance(history_time, bool) or not isinstance(history_time, Real):
            _fail(
                "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
                f"history row {expected_step} has a non-real time_s",
            )
        resolved_history_time = float(history_time)
        if not np.isfinite(resolved_history_time):
            _fail(
                "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
                f"history row {expected_step} has a nonfinite time_s",
            )
        history_times.append(resolved_history_time)

    if not np.array_equal(
        np.asarray(history_times, dtype=time_s.dtype),
        time_s[1:],
    ):
        _fail(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "history times do not equal state_history.time_s[1:]",
        )

    return ValidatedFullStateLayout(
        accepted_steps=accepted_steps,
        full_state_samples=full_state_samples,
        n_cells=n_cells,
    )


def project_state_storage(
    result: WorkingToolResult,
    state_sample_interval_accepted_steps: object,
) -> StateStorageProjection:
    """Create an independent post-solver public state-storage projection."""

    storage_mode = storage_mode_for_sample_interval(
        state_sample_interval_accepted_steps
    )
    interval = int(state_sample_interval_accepted_steps)
    layout = validate_full_state_result(result)
    retained = retained_state_indices(layout.accepted_steps, interval)
    retained_array = np.asarray(retained, dtype=np.intp)

    projected_state_history: dict[str, np.ndarray] = {}
    for name, source in result.state_history.items():
        if name in _SAMPLE_AXIS_STATE_ARRAY_SET:
            projected_state_history[name] = np.array(
                np.take(source, retained_array, axis=0),
                copy=True,
            )
        elif name in _STATIC_STATE_ARRAY_SET:
            projected_state_history[name] = np.array(source, copy=True)
        else:  # pragma: no cover - validate_full_state_result fails first.
            _fail(
                "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR",
                f"unclassified state array: {name!r}",
            )

    projected_result = WorkingToolResult(
        case_id=result.case_id,
        model_profile=result.model_profile,
        summary=deepcopy(dict(result.summary)),
        history=tuple(deepcopy(dict(row)) for row in result.history),
        transitions=tuple(result.transitions),
        state_history=projected_state_history,
        warnings=tuple(result.warnings),
        schema_version=result.schema_version,
        verified=result.verified,
        accepted=result.accepted,
        validated=result.validated,
        design_use_approved=result.design_use_approved,
    )

    return StateStorageProjection(
        result=projected_result,
        retained_state_indices=retained,
        full_state_samples=layout.full_state_samples,
        stored_state_samples=len(retained),
        state_sample_interval_accepted_steps=interval,
        storage_mode=storage_mode,
    )
