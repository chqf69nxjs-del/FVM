"""Public, non-verification run manifest support for Working Tool v0-B."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .case_schema import WorkingToolCase
from .operation_policy import WorkingToolOperationPolicy
from .output import RESULT_FILENAMES
from .storage_projection import StateStorageProjection


RUN_MANIFEST_FILENAME = "run_manifest.json"
RUN_MANIFEST_SCHEMA = "liquid_gas_transient.working_tool.run_manifest"
RUN_MANIFEST_SCHEMA_VERSION = 1
V0_B_OUTPUT_CONTRACT = "WORKING_TOOL_V0_B_SIX_FILE_V1"
SAMPLING_BASIS = "ACCEPTED_SOLVER_STEP"
RUNTIME_STATE_CAPTURE_MODE = "FULL"

_LOCAL_RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TARGET_REACHED_SUMMARY_KEYS = (
    "target_horizon_reached",
    "target_reached",
)
_FORBIDDEN_PUBLIC_MANIFEST_KEYS = frozenset(
    {
        "workflow_id",
        "workflow_run_id",
        "job_id",
        "artifact_id",
        "artifact_digest",
        "a2_authority",
        "parent_authority",
        "exact_regression_pass",
        "exact_regression_passed",
        "mismatch_count",
        "mismatch_counts",
        "context_restoration_evidence",
        "pytest_result",
        "ci_success",
        "verification_approval",
    }
)


class RunManifestError(ValueError):
    """Fail-closed classification for invalid public manifest construction."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


@dataclass(frozen=True)
class CoreFileIntegrity:
    """Actual byte-level integrity metadata for one completed core file."""

    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise TypeError("size_bytes must be a non-negative built-in int")
        if not isinstance(self.sha256, str) or not _SHA256_PATTERN.fullmatch(
            self.sha256
        ):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")

    def as_dict(self) -> dict[str, object]:
        return {
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def canonical_working_tool_case_bytes(case: WorkingToolCase) -> bytes:
    """Serialize a validated case deterministically for its resolved digest."""

    if not isinstance(case, WorkingToolCase):
        raise TypeError("case must be WorkingToolCase")
    return json.dumps(
        case.as_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def resolved_case_sha256(case: WorkingToolCase) -> str:
    """Return SHA-256 of canonical ``WorkingToolCase.as_dict()`` serialization."""

    return hashlib.sha256(canonical_working_tool_case_bytes(case)).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the lowercase SHA-256 of a completed regular file."""

    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if type(chunk_size) is not int or chunk_size < 1:
        raise ValueError("chunk_size must be a positive built-in int")
    if path.is_symlink() or not path.is_file():
        raise RunManifestError(
            "WORKING_TOOL_V0_B_CORE_FILE_ERROR",
            f"core path is not a regular non-symlink file: {path}",
        )

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def measure_core_files(output_dir: Path) -> dict[str, CoreFileIntegrity]:
    """Measure the existing v0-A five-file package after it is fully written."""

    if not isinstance(output_dir, Path):
        raise TypeError("output_dir must be pathlib.Path")
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise RunManifestError(
            "WORKING_TOOL_V0_B_OUTPUT_DIRECTORY_ERROR",
            f"output directory is not a regular directory: {output_dir}",
        )

    measured: dict[str, CoreFileIntegrity] = {}
    for filename in RESULT_FILENAMES:
        path = output_dir / filename
        if path.is_symlink() or not path.is_file():
            raise RunManifestError(
                "WORKING_TOOL_V0_B_CORE_FILE_ERROR",
                f"required core file is missing or not regular: {filename}",
            )
        measured[filename] = CoreFileIntegrity(
            size_bytes=path.stat().st_size,
            sha256=sha256_file(path),
        )
    return measured


def _format_utc_timestamp(value: datetime, *, field_name: str) -> str:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    resolved = value.astimezone(timezone.utc)
    return resolved.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_published_directory_name(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("published_directory_name must be a non-empty string")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("published_directory_name must be one path component")
    if Path(value).name != value:
        raise ValueError("published_directory_name must be one path component")
    return value


def _resolve_target_reached(summary: Mapping[str, object]) -> bool:
    present = [key for key in _TARGET_REACHED_SUMMARY_KEYS if key in summary]
    if len(present) != 1:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "summary must contain exactly one supported target-reached field",
        )
    value = summary[present[0]]
    if type(value) is not bool:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            f"summary.{present[0]} must be a built-in bool",
        )
    return value


def _validate_core_integrity(
    core_files: Mapping[str, CoreFileIntegrity],
) -> dict[str, CoreFileIntegrity]:
    if not isinstance(core_files, Mapping):
        raise TypeError("core_files must be a mapping")
    if frozenset(core_files) != frozenset(RESULT_FILENAMES):
        missing = sorted(set(RESULT_FILENAMES) - set(core_files))
        unknown = sorted(set(core_files) - set(RESULT_FILENAMES))
        raise RunManifestError(
            "WORKING_TOOL_V0_B_CORE_FILE_ERROR",
            f"core-file set is not exact; missing={missing}, unknown={unknown}",
        )

    ordered: dict[str, CoreFileIntegrity] = {}
    for filename in RESULT_FILENAMES:
        value = core_files[filename]
        if not isinstance(value, CoreFileIntegrity):
            raise TypeError(
                f"core_files[{filename!r}] must be CoreFileIntegrity"
            )
        ordered[filename] = value
    return ordered


def _assert_public_evidence_separation(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key in _FORBIDDEN_PUBLIC_MANIFEST_KEYS:
                raise RunManifestError(
                    "WORKING_TOOL_V0_B_PUBLIC_EVIDENCE_SEPARATION_ERROR",
                    f"forbidden verification field in public manifest: {key}",
                )
            _assert_public_evidence_separation(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_public_evidence_separation(nested)


def build_run_manifest(
    *,
    case: WorkingToolCase,
    policy: WorkingToolOperationPolicy,
    projection: StateStorageProjection,
    published_directory_name: str,
    started_at_utc: datetime,
    completed_at_utc: datetime,
    local_run_id: str,
    core_files: Mapping[str, CoreFileIntegrity],
) -> dict[str, object]:
    """Build the schema-v1 public manifest without verification authority."""

    if not isinstance(case, WorkingToolCase):
        raise TypeError("case must be WorkingToolCase")
    if not isinstance(policy, WorkingToolOperationPolicy):
        raise TypeError("policy must be WorkingToolOperationPolicy")
    if not isinstance(projection, StateStorageProjection):
        raise TypeError("projection must be StateStorageProjection")
    directory_name = _validate_published_directory_name(
        published_directory_name
    )
    if not isinstance(local_run_id, str) or not _LOCAL_RUN_ID_PATTERN.fullmatch(
        local_run_id
    ):
        raise ValueError(
            "local_run_id must be 32 lowercase hexadecimal characters"
        )

    started_text = _format_utc_timestamp(
        started_at_utc,
        field_name="started_at_utc",
    )
    completed_text = _format_utc_timestamp(
        completed_at_utc,
        field_name="completed_at_utc",
    )
    if completed_at_utc.astimezone(timezone.utc) < started_at_utc.astimezone(
        timezone.utc
    ):
        raise ValueError("completed_at_utc must not precede started_at_utc")

    if projection.state_sample_interval_accepted_steps != (
        policy.state_sample_interval_accepted_steps
    ):
        raise RunManifestError(
            "WORKING_TOOL_V0_B_POLICY_PROJECTION_MISMATCH",
            "policy interval does not match projection interval",
        )
    if projection.storage_mode is not policy.storage_mode:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_POLICY_PROJECTION_MISMATCH",
            "policy storage mode does not match projection storage mode",
        )
    if projection.result.case_id != case.case_id:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "result case_id does not match resolved case",
        )
    if projection.result.model_profile is not case.model_profile:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "result model_profile does not match resolved case",
        )
    if any(
        (
            projection.result.verified,
            projection.result.accepted,
            projection.result.validated,
            projection.result.design_use_approved,
        )
    ):
        raise RunManifestError(
            "WORKING_TOOL_V0_B_FORMAL_STATUS_ERROR",
            "v0-B public package requires unchanged false formal status",
        )

    if projection.full_state_samples < 1:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "full_state_samples must be positive",
        )
    if not 1 <= projection.stored_state_samples <= projection.full_state_samples:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "stored_state_samples is outside the full-state range",
        )

    final_time_s = float(projection.result.state_history["time_s"][-1])
    if not math.isfinite(final_time_s):
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "final state time is nonfinite",
        )
    target_reached = _resolve_target_reached(projection.result.summary)
    accepted_steps = projection.full_state_samples - 1
    measured = _validate_core_integrity(core_files)
    reduction_ratio = projection.raw_state_payload_reduction_ratio
    if not math.isfinite(reduction_ratio) or not 0.0 <= reduction_ratio < 1.0:
        raise RunManifestError(
            "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR",
            "raw state payload reduction ratio is invalid",
        )

    manifest: dict[str, object] = {
        "schema": RUN_MANIFEST_SCHEMA,
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "output_contract": V0_B_OUTPUT_CONTRACT,
        "local_run_id": local_run_id,
        "case": {
            "case_id": case.case_id,
            "resolved_case_sha256": resolved_case_sha256(case),
            "model_profile": case.model_profile.value,
            "fluid": case.fluid,
        },
        "storage": {
            "mode": projection.storage_mode.value,
            "state_sample_interval_accepted_steps": (
                projection.state_sample_interval_accepted_steps
            ),
            "sampling_basis": SAMPLING_BASIS,
            "sampling_applied_after_solver": True,
            "runtime_state_capture_mode": RUNTIME_STATE_CAPTURE_MODE,
            "state_layout": projection.layout_version,
            "full_state_samples": projection.full_state_samples,
            "stored_state_samples": projection.stored_state_samples,
            "raw_state_payload_reduction_ratio": reduction_ratio,
        },
        "destination": {
            "mode": policy.destination_mode.value,
            "published_directory_name": directory_name,
        },
        "started_at_utc": started_text,
        "completed_at_utc": completed_text,
        "result": {
            "accepted_steps": accepted_steps,
            "final_time_s": final_time_s,
            "target_reached": target_reached,
        },
        "core_files": {
            filename: integrity.as_dict()
            for filename, integrity in measured.items()
        },
        "core_total_bytes": sum(
            integrity.size_bytes for integrity in measured.values()
        ),
        "formal_status": {
            "provisional_engineering_end_to_end_working_slice": True,
            "verified": False,
            "accepted": False,
            "physically_validated": False,
            "design_use_accepted": False,
            "production_approved": False,
        },
    }
    _assert_public_evidence_separation(manifest)
    return manifest
