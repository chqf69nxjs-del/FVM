"""Strict UTF-8 JSON loading for the Working Tool v0-A case contract."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from ..config import NumericsConfig, PipeGeometry, TimeConfig
from .case_schema import (
    CASE_SCHEMA_VERSION,
    InitialCondition,
    ModelProfile,
    OutletCondition,
    WorkingToolCase,
)


class CaseFileError(ValueError):
    """Fail-closed case-file parsing or schema error."""

    def __init__(self, classification: str, message: str) -> None:
        super().__init__(f"{classification}: {message}")
        self.classification = classification


_ROOT_KEYS = frozenset(
    {
        "schema_version",
        "case_id",
        "fluid",
        "model_profile",
        "geometry",
        "numerics",
        "time",
        "initial",
        "outlet",
    }
)
_GEOMETRY_KEYS = frozenset({"length_m", "diameter_m", "roughness_m"})
_NUMERICS_KEYS = frozenset({"n_cells", "n_ghost", "cfl"})
_TIME_KEYS = frozenset({"t_end_s", "max_steps"})
_INITIAL_KEYS = frozenset({"pressure_pa", "temperature_k", "velocity_m_s"})
_OUTLET_KEYS = frozenset(
    {"back_pressure_pa", "opening_fraction", "discharge_coefficient"}
)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CaseFileError(
                "WORKING_TOOL_CASE_FILE_DUPLICATE_KEY",
                f"duplicate JSON object key: {key!r}",
            )
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> None:
    raise CaseFileError(
        "WORKING_TOOL_CASE_FILE_NONFINITE_JSON",
        f"non-finite JSON constant is not permitted: {value}",
    )


def _require_exact_object(
    value: Any,
    *,
    field: str,
    expected_keys: frozenset[str],
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
            f"{field} must be a JSON object",
        )
    actual_keys = frozenset(value)
    missing = sorted(expected_keys - actual_keys)
    unknown = sorted(actual_keys - expected_keys)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing keys={missing}")
        if unknown:
            details.append(f"unknown keys={unknown}")
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_SCHEMA_ERROR",
            f"{field} has an invalid key set: " + "; ".join(details),
        )
    return value


def _require_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
            f"{field} must be a string",
        )
    return value


def _require_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
            f"{field} must be a JSON number",
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_NONFINITE_VALUE",
            f"{field} must be finite",
        )
    return numeric


def _require_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
            f"{field} must be a JSON integer",
        )
    return int(value)


def _case_from_mapping(root: Mapping[str, Any]) -> WorkingToolCase:
    root = _require_exact_object(root, field="case", expected_keys=_ROOT_KEYS)
    geometry = _require_exact_object(
        root["geometry"], field="geometry", expected_keys=_GEOMETRY_KEYS
    )
    numerics = _require_exact_object(
        root["numerics"], field="numerics", expected_keys=_NUMERICS_KEYS
    )
    time = _require_exact_object(root["time"], field="time", expected_keys=_TIME_KEYS)
    initial = _require_exact_object(
        root["initial"], field="initial", expected_keys=_INITIAL_KEYS
    )
    outlet = _require_exact_object(
        root["outlet"], field="outlet", expected_keys=_OUTLET_KEYS
    )

    schema_version = _require_string(root["schema_version"], field="schema_version")
    if schema_version != CASE_SCHEMA_VERSION:
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_UNSUPPORTED_SCHEMA",
            f"unsupported schema_version: {schema_version!r}",
        )

    fluid = _require_string(root["fluid"], field="fluid")
    profile_text = _require_string(root["model_profile"], field="model_profile")
    try:
        model_profile = ModelProfile(profile_text)
    except ValueError as exc:
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_UNSUPPORTED_MODEL_PROFILE",
            f"unsupported model_profile: {profile_text!r}",
        ) from exc

    try:
        return WorkingToolCase(
            schema_version=schema_version,
            case_id=_require_string(root["case_id"], field="case_id"),
            fluid=fluid,
            model_profile=model_profile,
            geometry=PipeGeometry(
                length_m=_require_float(
                    geometry["length_m"], field="geometry.length_m"
                ),
                diameter_m=_require_float(
                    geometry["diameter_m"], field="geometry.diameter_m"
                ),
                roughness_m=_require_float(
                    geometry["roughness_m"], field="geometry.roughness_m"
                ),
            ),
            numerics=NumericsConfig(
                n_cells=_require_int(
                    numerics["n_cells"], field="numerics.n_cells"
                ),
                n_ghost=_require_int(
                    numerics["n_ghost"], field="numerics.n_ghost"
                ),
                cfl=_require_float(numerics["cfl"], field="numerics.cfl"),
            ),
            time=TimeConfig(
                t_end_s=_require_float(time["t_end_s"], field="time.t_end_s"),
                max_steps=_require_int(
                    time["max_steps"], field="time.max_steps"
                ),
            ),
            initial=InitialCondition(
                pressure_pa=_require_float(
                    initial["pressure_pa"], field="initial.pressure_pa"
                ),
                temperature_k=_require_float(
                    initial["temperature_k"], field="initial.temperature_k"
                ),
                velocity_m_s=_require_float(
                    initial["velocity_m_s"], field="initial.velocity_m_s"
                ),
            ),
            outlet=OutletCondition(
                back_pressure_pa=_require_float(
                    outlet["back_pressure_pa"], field="outlet.back_pressure_pa"
                ),
                opening_fraction=_require_float(
                    outlet["opening_fraction"], field="outlet.opening_fraction"
                ),
                discharge_coefficient=_require_float(
                    outlet["discharge_coefficient"],
                    field="outlet.discharge_coefficient",
                ),
            ),
        )
    except CaseFileError:
        raise
    except (TypeError, ValueError) as exc:
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_VALUE_ERROR",
            str(exc),
        ) from exc


def load_case_file(path: str | Path) -> WorkingToolCase:
    """Load one exact Working Tool case from a strict UTF-8 JSON file."""

    case_path = Path(path)
    if not case_path.exists():
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_NOT_FOUND",
            f"case file does not exist: {case_path}",
        )
    if not case_path.is_file():
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_NOT_REGULAR",
            f"case path is not a regular file: {case_path}",
        )
    try:
        text = case_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_INVALID_UTF8",
            f"case file is not valid UTF-8: {case_path}",
        ) from exc
    except OSError as exc:
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_READ_ERROR",
            f"could not read case file {case_path}: {exc}",
        ) from exc

    try:
        raw = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
    except CaseFileError:
        raise
    except json.JSONDecodeError as exc:
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_INVALID_JSON",
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
        ) from exc

    if not isinstance(raw, dict):
        raise CaseFileError(
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
            "case root must be a JSON object",
        )
    return _case_from_mapping(raw)
