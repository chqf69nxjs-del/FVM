"""Working Tool v0-B output and storage operation policy.

This module is deliberately independent of solver, EOS, boundary-model, and
backend code.  It describes only how an already completed full result will be
published.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class WorkingToolStateStorageMode(str, Enum):
    """State-history storage mode derived from the accepted-step interval."""

    FULL_STATE = "FULL_STATE"
    SAMPLED_STATE = "SAMPLED_STATE"


class WorkingToolDestinationMode(str, Enum):
    """Supported create-only destination-selection modes."""

    EXPLICIT = "EXPLICIT"
    AUTO_RUN_DIRECTORY = "AUTO_RUN_DIRECTORY"


def _require_positive_builtin_int(value: object, *, field_name: str) -> int:
    """Return a strictly positive built-in integer or fail closed."""

    if type(value) is not int:
        raise TypeError(f"{field_name} must be a built-in int")
    if value < 1:
        raise ValueError(f"{field_name} must be greater than or equal to 1")
    return value


def storage_mode_for_sample_interval(
    state_sample_interval_accepted_steps: object,
) -> WorkingToolStateStorageMode:
    """Derive the only valid storage mode from a strict sample interval."""

    interval = _require_positive_builtin_int(
        state_sample_interval_accepted_steps,
        field_name="state_sample_interval_accepted_steps",
    )
    if interval == 1:
        return WorkingToolStateStorageMode.FULL_STATE
    return WorkingToolStateStorageMode.SAMPLED_STATE


@dataclass(frozen=True)
class WorkingToolOperationPolicy:
    """Immutable v0-B storage and destination operation policy.

    The physical case schema intentionally does not contain these fields.
    Callers must resolve CLI text into the strict enum and ``Path`` values
    before constructing this object.
    """

    state_sample_interval_accepted_steps: int
    destination_mode: WorkingToolDestinationMode
    output_dir: Path | None = None
    output_root: Path | None = None

    def __post_init__(self) -> None:
        _require_positive_builtin_int(
            self.state_sample_interval_accepted_steps,
            field_name="state_sample_interval_accepted_steps",
        )
        if type(self.destination_mode) is not WorkingToolDestinationMode:
            raise TypeError(
                "destination_mode must be WorkingToolDestinationMode"
            )
        self._validate_optional_path(self.output_dir, field_name="output_dir")
        self._validate_optional_path(self.output_root, field_name="output_root")

        if self.destination_mode is WorkingToolDestinationMode.EXPLICIT:
            if self.output_dir is None:
                raise ValueError("EXPLICIT destination requires output_dir")
            if self.output_root is not None:
                raise ValueError("EXPLICIT destination forbids output_root")
            return

        if self.destination_mode is WorkingToolDestinationMode.AUTO_RUN_DIRECTORY:
            if self.output_root is None:
                raise ValueError(
                    "AUTO_RUN_DIRECTORY destination requires output_root"
                )
            if self.output_dir is not None:
                raise ValueError(
                    "AUTO_RUN_DIRECTORY destination forbids output_dir"
                )
            return

        # The strict enum type gate above makes this unreachable unless the
        # enum is extended without updating this contract.
        raise ValueError(f"unsupported destination_mode: {self.destination_mode!r}")

    @staticmethod
    def _validate_optional_path(value: object, *, field_name: str) -> None:
        if value is not None and not isinstance(value, Path):
            raise TypeError(f"{field_name} must be pathlib.Path or None")

    @property
    def storage_mode(self) -> WorkingToolStateStorageMode:
        """Return the mode derived from the accepted-step interval."""

        return storage_mode_for_sample_interval(
            self.state_sample_interval_accepted_steps
        )

    @property
    def destination_path(self) -> Path:
        """Return the validated user-selected destination path."""

        if self.destination_mode is WorkingToolDestinationMode.EXPLICIT:
            assert self.output_dir is not None
            return self.output_dir
        assert self.output_root is not None
        return self.output_root

    @classmethod
    def explicit(
        cls,
        output_dir: Path,
        *,
        state_sample_interval_accepted_steps: int = 1,
    ) -> WorkingToolOperationPolicy:
        """Construct a strict explicit-output policy."""

        return cls(
            state_sample_interval_accepted_steps=(
                state_sample_interval_accepted_steps
            ),
            destination_mode=WorkingToolDestinationMode.EXPLICIT,
            output_dir=output_dir,
        )

    @classmethod
    def auto_run_directory(
        cls,
        output_root: Path,
        *,
        state_sample_interval_accepted_steps: int = 1,
    ) -> WorkingToolOperationPolicy:
        """Construct a strict automatic run-directory policy."""

        return cls(
            state_sample_interval_accepted_steps=(
                state_sample_interval_accepted_steps
            ),
            destination_mode=WorkingToolDestinationMode.AUTO_RUN_DIRECTORY,
            output_root=output_root,
        )
