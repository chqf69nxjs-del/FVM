"""Public contracts for the Stage 7 provisional Working Tool shell."""

from .application import CompletedCaseRun, OutputDirectoryError, run_case_file
from .backend import WorkingToolBackend
from .case_io import CaseFileError, load_case_file
from .case_schema import (
    CASE_SCHEMA_VERSION,
    InitialCondition,
    ModelProfile,
    OutletCondition,
    WorkingToolCase,
)
from .output import RESULT_FILENAMES, write_result_package
from .results import (
    BackendRunData,
    PROVISIONAL_MODEL_WARNING,
    PROVISIONAL_WARNING_CODE,
    RESULT_SCHEMA_VERSION,
    TransitionRecord,
    WarningSeverity,
    WorkingToolResult,
    WorkingToolWarning,
)
from .runtime import execute_case

__all__ = [
    "BackendRunData",
    "CASE_SCHEMA_VERSION",
    "CaseFileError",
    "CompletedCaseRun",
    "InitialCondition",
    "ModelProfile",
    "OutletCondition",
    "OutputDirectoryError",
    "PROVISIONAL_MODEL_WARNING",
    "PROVISIONAL_WARNING_CODE",
    "RESULT_FILENAMES",
    "RESULT_SCHEMA_VERSION",
    "TransitionRecord",
    "WarningSeverity",
    "WorkingToolBackend",
    "WorkingToolCase",
    "WorkingToolResult",
    "WorkingToolWarning",
    "execute_case",
    "load_case_file",
    "run_case_file",
    "write_result_package",
]
