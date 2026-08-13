"""Normal-user output serialization for Working Tool W0."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .results import RESERVED_SUMMARY_KEYS, WorkingToolResult


RESULT_FILENAMES = (
    "summary.json",
    "history.csv",
    "transitions.csv",
    "warnings.csv",
    "state_history.npz",
)

VERIFICATION_ONLY_SUMMARY_KEYS = frozenset(
    {
        "workflow_run",
        "workflow_job",
        "artifact_id",
        "artifact_sha256",
        "parent_workflow_run",
        "parent_workflow_job",
        "parent_artifact_id",
        "parent_artifact_sha256",
        "exact_increment_9l_behavioral_equivalence_passed",
        "increment_9m_a2_exact_increment_9l_behavioral_equivalence_passed",
    }
)


def _write_rows(path: Path, rows: tuple[Mapping[str, Any], ...]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_result_package(result: WorkingToolResult, output_dir: Path | str) -> Path:
    """Write exactly the five files in the public W0 result contract."""

    if not isinstance(result, WorkingToolResult):
        raise TypeError("result must be WorkingToolResult")
    forbidden = (RESERVED_SUMMARY_KEYS | VERIFICATION_ONLY_SUMMARY_KEYS).intersection(
        result.summary
    )
    if forbidden:
        raise ValueError(f"result summary uses reserved public keys: {sorted(forbidden)}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    summary = {
        **dict(result.summary),
        "schema_version": result.schema_version,
        "case_id": result.case_id,
        "model_profile": result.model_profile.value,
        "verified": False,
        "accepted": False,
        "validated": False,
        "design_use_approved": False,
        "warning_codes": [warning.code for warning in result.warnings],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    _write_rows(output / "history.csv", result.history)
    _write_rows(
        output / "transitions.csv",
        tuple(record.as_dict() for record in result.transitions),
    )
    _write_rows(
        output / "warnings.csv",
        tuple(warning.as_dict() for warning in result.warnings),
    )
    np.savez(
        output / "state_history.npz",
        **{name: np.asarray(values) for name, values in sorted(result.state_history.items())},
    )
    return output
