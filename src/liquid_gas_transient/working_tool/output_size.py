"""Truthful pre-run state-payload estimates for Working Tool v0-B.

The estimate in this module covers only sample-dependent public float64 state
arrays.  It is not an NPZ size, directory size, or runtime-memory estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .operation_policy import (
    WorkingToolStateStorageMode,
    storage_mode_for_sample_interval,
)


FLOAT64_BYTES = 8
CONSERVEd_VALUES_PER_CELL = 4
PUBLIC_PRIMITIVE_VALUES_PER_CELL = 6
MEBIBYTE_BYTES = 1024**2

RAW_STATE_PAYLOAD_ESTIMATE_LABEL = (
    "raw sample-dependent state-array payload estimate"
)
RAW_STATE_PAYLOAD_ESTIMATE_BASIS = "CONFIGURED_MAX_STEPS_UPPER_BOUND"
RAW_STATE_PAYLOAD_SCOPE = "SAMPLE_DEPENDENT_PUBLIC_STATE_ARRAYS_ONLY"
RUNTIME_STATE_CAPTURE_MODE = "FULL"

RAW_STATE_PAYLOAD_EXCLUSIONS = (
    "STATIC_X_M_ARRAY",
    "CSV_PAYLOAD",
    "JSON_PAYLOAD",
    "NPZ_CONTAINER_METADATA_AND_OVERHEAD",
    "FILESYSTEM_ALLOCATION_OVERHEAD",
    "TEMPORARY_PUBLICATION_STORAGE",
    "PYTHON_AND_NUMPY_RUNTIME_MEMORY",
    "BACKEND_FULL_HISTORY_MEMORY",
)


def _require_positive_builtin_int(value: object, *, field_name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be a built-in int")
    if value < 1:
        raise ValueError(f"{field_name} must be greater than or equal to 1")
    return value


def maximum_state_sample_count(
    max_steps: object,
    state_sample_interval_accepted_steps: object,
) -> int:
    """Return the retained-sample upper bound for the configured step limit."""

    resolved_max_steps = _require_positive_builtin_int(
        max_steps,
        field_name="max_steps",
    )
    interval = _require_positive_builtin_int(
        state_sample_interval_accepted_steps,
        field_name="state_sample_interval_accepted_steps",
    )
    return (
        1
        + resolved_max_steps // interval
        + int(resolved_max_steps % interval != 0)
    )


def raw_state_payload_bytes_per_sample(n_cells: object) -> int:
    """Return raw bytes for one sample of the sample-dependent v1 arrays."""

    resolved_n_cells = _require_positive_builtin_int(
        n_cells,
        field_name="n_cells",
    )
    values_per_sample = 1 + (
        CONSERVEd_VALUES_PER_CELL + PUBLIC_PRIMITIVE_VALUES_PER_CELL
    ) * resolved_n_cells
    return FLOAT64_BYTES * values_per_sample


@dataclass(frozen=True)
class RawStatePayloadEstimate:
    """Immutable, explicitly limited pre-run storage disclosure."""

    label: str
    estimate_basis: str
    payload_scope: str
    n_cells: int
    max_steps: int
    state_sample_interval_accepted_steps: int
    storage_mode: WorkingToolStateStorageMode
    maximum_state_samples: int
    bytes_per_sample: int
    estimated_raw_payload_bytes: int
    estimated_raw_payload_mib: float
    excluded_payloads: tuple[str, ...]
    runtime_state_capture_mode: str
    runtime_memory_optimized: bool
    exact_directory_size: bool

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready operational disclosure."""

        return {
            "label": self.label,
            "estimate_basis": self.estimate_basis,
            "payload_scope": self.payload_scope,
            "n_cells": self.n_cells,
            "max_steps": self.max_steps,
            "state_sample_interval_accepted_steps": (
                self.state_sample_interval_accepted_steps
            ),
            "storage_mode": self.storage_mode.value,
            "maximum_state_samples": self.maximum_state_samples,
            "bytes_per_sample": self.bytes_per_sample,
            "estimated_raw_payload_bytes": self.estimated_raw_payload_bytes,
            "estimated_raw_payload_mib": self.estimated_raw_payload_mib,
            "excluded_payloads": list(self.excluded_payloads),
            "runtime_state_capture_mode": self.runtime_state_capture_mode,
            "runtime_memory_optimized": self.runtime_memory_optimized,
            "exact_directory_size": self.exact_directory_size,
        }


def estimate_maximum_raw_state_payload(
    *,
    n_cells: object,
    max_steps: object,
    state_sample_interval_accepted_steps: object,
) -> RawStatePayloadEstimate:
    """Build the configured-upper-bound raw state-payload estimate."""

    resolved_n_cells = _require_positive_builtin_int(
        n_cells,
        field_name="n_cells",
    )
    resolved_max_steps = _require_positive_builtin_int(
        max_steps,
        field_name="max_steps",
    )
    interval = _require_positive_builtin_int(
        state_sample_interval_accepted_steps,
        field_name="state_sample_interval_accepted_steps",
    )
    storage_mode = storage_mode_for_sample_interval(interval)
    maximum_samples = maximum_state_sample_count(resolved_max_steps, interval)
    bytes_per_sample = raw_state_payload_bytes_per_sample(resolved_n_cells)
    estimated_bytes = maximum_samples * bytes_per_sample

    return RawStatePayloadEstimate(
        label=RAW_STATE_PAYLOAD_ESTIMATE_LABEL,
        estimate_basis=RAW_STATE_PAYLOAD_ESTIMATE_BASIS,
        payload_scope=RAW_STATE_PAYLOAD_SCOPE,
        n_cells=resolved_n_cells,
        max_steps=resolved_max_steps,
        state_sample_interval_accepted_steps=interval,
        storage_mode=storage_mode,
        maximum_state_samples=maximum_samples,
        bytes_per_sample=bytes_per_sample,
        estimated_raw_payload_bytes=estimated_bytes,
        estimated_raw_payload_mib=estimated_bytes / MEBIBYTE_BYTES,
        excluded_payloads=RAW_STATE_PAYLOAD_EXCLUSIONS,
        runtime_state_capture_mode=RUNTIME_STATE_CAPTURE_MODE,
        runtime_memory_optimized=False,
        exact_directory_size=False,
    )
