"""Exact six-file public package writer for Working Tool v0-B."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from .case_schema import WorkingToolCase
from .operation_policy import WorkingToolOperationPolicy
from .output import RESULT_FILENAMES, write_result_package
from .run_manifest import (
    RUN_MANIFEST_FILENAME,
    CoreFileIntegrity,
    build_run_manifest,
    measure_core_files,
)
from .storage_projection import StateStorageProjection


V0_B_RUN_FILENAMES = RESULT_FILENAMES + (RUN_MANIFEST_FILENAME,)


class V0BOutputError(ValueError):
    """Fail-closed classification for v0-B package writing."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


@dataclass(frozen=True)
class V0BPackageReceipt:
    """Operational receipt for a completed temporary six-file package."""

    output_dir: Path
    manifest: Mapping[str, object]
    core_files: Mapping[str, CoreFileIntegrity]
    core_total_bytes: int


def _require_empty_output_directory(output_dir: Path) -> None:
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir must be pathlib.Path")
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise V0BOutputError(
            "WORKING_TOOL_V0_B_OUTPUT_DIRECTORY_ERROR",
            f"output directory must be an existing regular directory: {output_dir}",
        )
    if any(output_dir.iterdir()):
        raise V0BOutputError(
            "WORKING_TOOL_V0_B_OUTPUT_NOT_EMPTY",
            f"output directory must be empty: {output_dir}",
        )


def validate_v0_b_package(output_dir: Path) -> tuple[Path, ...]:
    """Require exactly six regular non-symlink files and no subdirectories."""

    if not isinstance(output_dir, Path):
        raise TypeError("output_dir must be pathlib.Path")
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise V0BOutputError(
            "WORKING_TOOL_V0_B_OUTPUT_DIRECTORY_ERROR",
            f"output directory is not a regular directory: {output_dir}",
        )

    entries = tuple(output_dir.iterdir())
    actual_names = frozenset(path.name for path in entries)
    expected_names = frozenset(V0_B_RUN_FILENAMES)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unknown = sorted(actual_names - expected_names)
        raise V0BOutputError(
            "WORKING_TOOL_V0_B_OUTPUT_CONTRACT_ERROR",
            f"six-file package is not exact; missing={missing}, unknown={unknown}",
        )
    if len(entries) != len(V0_B_RUN_FILENAMES):
        raise V0BOutputError(
            "WORKING_TOOL_V0_B_OUTPUT_CONTRACT_ERROR",
            "six-file package contains duplicate-equivalent directory entries",
        )

    ordered: list[Path] = []
    for filename in V0_B_RUN_FILENAMES:
        path = output_dir / filename
        if path.is_symlink() or not path.is_file():
            raise V0BOutputError(
                "WORKING_TOOL_V0_B_OUTPUT_CONTRACT_ERROR",
                f"package member is not a regular non-symlink file: {filename}",
            )
        ordered.append(path)
    return tuple(ordered)


def write_v0_b_result_package(
    *,
    case: WorkingToolCase,
    policy: WorkingToolOperationPolicy,
    projection: StateStorageProjection,
    output_dir: Path,
    published_directory_name: str,
    started_at_utc: datetime,
    completed_at_utc: datetime,
    local_run_id: str,
) -> V0BPackageReceipt:
    """Write core files, hash them, then create the public manifest last."""

    _require_empty_output_directory(output_dir)

    write_result_package(projection.result, output_dir)
    core_files = measure_core_files(output_dir)
    manifest = build_run_manifest(
        case=case,
        policy=policy,
        projection=projection,
        published_directory_name=published_directory_name,
        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,
        local_run_id=local_run_id,
        core_files=core_files,
    )
    manifest_path = output_dir / RUN_MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    validate_v0_b_package(output_dir)

    core_total_bytes = sum(
        integrity.size_bytes for integrity in core_files.values()
    )
    if manifest["core_total_bytes"] != core_total_bytes:
        raise V0BOutputError(
            "WORKING_TOOL_V0_B_MANIFEST_CONSISTENCY_ERROR",
            "manifest core_total_bytes does not match measured core files",
        )

    return V0BPackageReceipt(
        output_dir=output_dir,
        manifest=manifest,
        core_files=core_files,
        core_total_bytes=core_total_bytes,
    )
