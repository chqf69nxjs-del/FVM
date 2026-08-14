"""Safe create-only run-directory application for Working Tool v0-B."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile
from typing import Callable
import unicodedata

from .backend import WorkingToolBackend
from .case_io import load_case_file
from .case_schema import WorkingToolCase
from .operation_policy import (
    WorkingToolDestinationMode,
    WorkingToolOperationPolicy,
)
from .output_v0_b import V0BPackageReceipt, write_v0_b_result_package
from .results import WorkingToolResult
from .runtime import execute_case
from .storage_projection import StateStorageProjection, project_state_storage


AUTO_RUN_DIRECTORY_ATTEMPTS = 16
AUTO_RUN_DIRECTORY_PREFIX = "working-tool-v0-b"
_AUTO_SUFFIX_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_LOCAL_RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class V0BApplicationError(ValueError):
    """Fail-closed classification for v0-B run-directory operation."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


@dataclass(frozen=True)
class CompletedV0BCaseRun:
    """Internal receipt for one completed and atomically published run."""

    case: WorkingToolCase
    full_result: WorkingToolResult
    projection: StateStorageProjection
    package: V0BPackageReceipt
    output_dir: Path
    local_run_id: str
    started_at_utc: datetime
    completed_at_utc: datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_case_slug(case_id: object) -> str:
    """Return a bounded ASCII path-safe slug without using raw case text."""

    if not isinstance(case_id, str):
        raise TypeError("case_id must be a string")
    ascii_text = (
        unicodedata.normalize("NFKD", case_id)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if not slug:
        slug = "case"
    slug = slug[:64].rstrip("-")
    return slug or "case"


def format_auto_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise TypeError("value must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("value must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_auto_run_directory_name(
    *,
    case_id: str,
    started_at_utc: datetime,
    random_suffix: str,
) -> str:
    if not isinstance(random_suffix, str) or not _AUTO_SUFFIX_PATTERN.fullmatch(
        random_suffix
    ):
        raise ValueError("random_suffix must be 12 lowercase hexadecimal characters")
    return (
        f"{AUTO_RUN_DIRECTORY_PREFIX}-{sanitize_case_slug(case_id)}"
        f"__{format_auto_timestamp(started_at_utc)}__{random_suffix}"
    )


def _prepare_parent(path: Path) -> Path:
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise V0BApplicationError(
            "WORKING_TOOL_V0_B_OUTPUT_PARENT_ERROR",
            f"could not create output parent {parent}: {exc}",
        ) from exc
    if parent.is_symlink() or not parent.is_dir():
        raise V0BApplicationError(
            "WORKING_TOOL_V0_B_OUTPUT_PARENT_ERROR",
            f"output parent is not a regular directory: {parent}",
        )
    return parent


def _prepare_auto_root(root: Path) -> Path:
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise V0BApplicationError(
            "WORKING_TOOL_V0_B_OUTPUT_ROOT_ERROR",
            f"could not create output root {root}: {exc}",
        ) from exc
    if root.is_symlink() or not root.is_dir():
        raise V0BApplicationError(
            "WORKING_TOOL_V0_B_OUTPUT_ROOT_ERROR",
            f"output root is not a regular directory: {root}",
        )
    return root


def _require_absent(path: Path, *, classification: str) -> None:
    if os.path.lexists(path):
        raise V0BApplicationError(
            classification,
            f"output path already exists: {path}",
        )


def _resolve_output_directory(
    *,
    case: WorkingToolCase,
    policy: WorkingToolOperationPolicy,
    started_at_utc: datetime,
    token_hex: Callable[[int], str],
) -> Path:
    if policy.destination_mode is WorkingToolDestinationMode.EXPLICIT:
        assert policy.output_dir is not None
        output = policy.output_dir
        _require_absent(
            output,
            classification="WORKING_TOOL_V0_B_OUTPUT_ALREADY_EXISTS",
        )
        _prepare_parent(output)
        return output

    assert policy.output_root is not None
    root = _prepare_auto_root(policy.output_root)
    for _ in range(AUTO_RUN_DIRECTORY_ATTEMPTS):
        suffix = token_hex(6)
        name = build_auto_run_directory_name(
            case_id=case.case_id,
            started_at_utc=started_at_utc,
            random_suffix=suffix,
        )
        candidate = root / name
        if not os.path.lexists(candidate):
            return candidate
    raise V0BApplicationError(
        "WORKING_TOOL_V0_B_AUTO_NAME_COLLISION_LIMIT",
        f"could not allocate a unique run directory after "
        f"{AUTO_RUN_DIRECTORY_ATTEMPTS} attempts under {root}",
    )


def _require_aware_utc(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def run_loaded_case_v0_b(
    case: WorkingToolCase,
    policy: WorkingToolOperationPolicy,
    backend: WorkingToolBackend,
    *,
    clock: Callable[[], datetime] = utc_now,
    token_hex: Callable[[int], str] = secrets.token_hex,
) -> CompletedV0BCaseRun:
    """Execute one full solve, project storage, and atomically publish it."""

    if not isinstance(case, WorkingToolCase):
        raise TypeError("case must be WorkingToolCase")
    if not isinstance(policy, WorkingToolOperationPolicy):
        raise TypeError("policy must be WorkingToolOperationPolicy")
    if not callable(clock):
        raise TypeError("clock must be callable")
    if not callable(token_hex):
        raise TypeError("token_hex must be callable")

    started = _require_aware_utc(clock(), field_name="started_at_utc")
    output = _resolve_output_directory(
        case=case,
        policy=policy,
        started_at_utc=started,
        token_hex=token_hex,
    )
    parent = output.parent
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output.name or AUTO_RUN_DIRECTORY_PREFIX}.tmp-",
            dir=parent,
        )
    )

    try:
        full_result = execute_case(case, backend)
        projection = project_state_storage(
            full_result,
            policy.state_sample_interval_accepted_steps,
        )
        completed = _require_aware_utc(clock(), field_name="completed_at_utc")
        if completed < started:
            raise V0BApplicationError(
                "WORKING_TOOL_V0_B_CLOCK_ERROR",
                "completion time precedes start time",
            )
        local_run_id = token_hex(16)
        if not isinstance(local_run_id, str) or not _LOCAL_RUN_ID_PATTERN.fullmatch(
            local_run_id
        ):
            raise V0BApplicationError(
                "WORKING_TOOL_V0_B_RANDOM_ID_ERROR",
                "local run ID must be 32 lowercase hexadecimal characters",
            )

        package = write_v0_b_result_package(
            case=case,
            policy=policy,
            projection=projection,
            output_dir=temporary,
            published_directory_name=output.name,
            started_at_utc=started,
            completed_at_utc=completed,
            local_run_id=local_run_id,
        )
        if os.path.lexists(output):
            raise V0BApplicationError(
                "WORKING_TOOL_V0_B_OUTPUT_RACE_DETECTED",
                f"output path appeared during the run: {output}",
            )
        temporary.rename(output)
        published_package = replace(package, output_dir=output)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    return CompletedV0BCaseRun(
        case=case,
        full_result=full_result,
        projection=projection,
        package=published_package,
        output_dir=output,
        local_run_id=local_run_id,
        started_at_utc=started,
        completed_at_utc=completed,
    )


def run_case_file_v0_b(
    case_path: str | Path,
    policy: WorkingToolOperationPolicy,
    backend: WorkingToolBackend,
    *,
    clock: Callable[[], datetime] = utc_now,
    token_hex: Callable[[int], str] = secrets.token_hex,
) -> CompletedV0BCaseRun:
    """Load one strict physical case and run it through v0-B operation policy."""

    case = load_case_file(case_path)
    return run_loaded_case_v0_b(
        case,
        policy,
        backend,
        clock=clock,
        token_hex=token_hex,
    )
