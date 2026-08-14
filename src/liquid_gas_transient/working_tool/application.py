"""Backend-independent case-file application runner for Working Tool v0-A."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile

from .backend import WorkingToolBackend
from .case_io import load_case_file
from .case_schema import WorkingToolCase
from .output import RESULT_FILENAMES, write_result_package
from .results import WorkingToolResult
from .runtime import execute_case


class OutputDirectoryError(ValueError):
    """Fail-closed create-only output-directory policy error."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


@dataclass(frozen=True)
class CompletedCaseRun:
    """Completed public case-file execution receipt."""

    case: WorkingToolCase
    result: WorkingToolResult
    output_dir: Path


def _prepare_output_parent(output: Path) -> Path:
    if os.path.lexists(output):
        raise OutputDirectoryError(
            "WORKING_TOOL_OUTPUT_ALREADY_EXISTS",
            f"output path already exists: {output}",
        )
    parent = output.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputDirectoryError(
            "WORKING_TOOL_OUTPUT_PARENT_ERROR",
            f"could not create output parent {parent}: {exc}",
        ) from exc
    if not parent.is_dir():
        raise OutputDirectoryError(
            "WORKING_TOOL_OUTPUT_PARENT_ERROR",
            f"output parent is not a directory: {parent}",
        )
    return parent


def run_case_file(
    case_path: str | Path,
    output_dir: str | Path,
    backend: WorkingToolBackend,
) -> CompletedCaseRun:
    """Load, execute, and atomically publish one public result package.

    The requested output directory is create-only.  Work is written to a hidden
    sibling directory and renamed into place only after the exact five-file
    public contract has been produced.  A failed run never overwrites or
    partially replaces an earlier result directory.
    """

    output = Path(output_dir)
    parent = _prepare_output_parent(output)
    case = load_case_file(case_path)

    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output.name or 'working-tool'}.tmp-",
            dir=parent,
        )
    )
    try:
        result = execute_case(case, backend)
        write_result_package(result, temporary)
        actual_files = sorted(
            path.name for path in temporary.iterdir() if path.is_file()
        )
        expected_files = sorted(RESULT_FILENAMES)
        if actual_files != expected_files:
            raise RuntimeError(
                "WORKING_TOOL_PUBLIC_RESULT_CONTRACT_MISMATCH: "
                f"expected {expected_files}, got {actual_files}"
            )
        if any(path.is_dir() for path in temporary.iterdir()):
            raise RuntimeError(
                "WORKING_TOOL_PUBLIC_RESULT_CONTRACT_MISMATCH: "
                "public result package contains an unexpected directory"
            )
        if os.path.lexists(output):
            raise OutputDirectoryError(
                "WORKING_TOOL_OUTPUT_RACE_DETECTED",
                f"output path appeared during the run: {output}",
            )
        temporary.rename(output)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    return CompletedCaseRun(case=case, result=result, output_dir=output)
