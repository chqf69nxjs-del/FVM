"""Diagnostic-only raw capture for the Stage 7 Gate 3 runtime comparison.

This module deliberately does not call the exact PR #82 baseline assertion. It
runs the immutable 128-cell / CFL=0.10 cases through the existing runner and
writes scalar metrics plus normalized little-endian float64 histories. The
capture is evidence for a later tolerance-aware comparison; it does not accept
any result and does not change solver logic, thresholds, or approval flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .hem_pipeline_4mpa_mesh_sensitivity import _case_metrics
from .hem_pipeline_cfl_sensitivity import (
    EXPECTED_128_CELL_CFL_0P10,
    HEMPipelineCflSensitivityConfig,
    collect_cfl_runtime_provenance,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    run_pipeline_depressurization_case,
)


CAPTURE_SCHEMA_VERSION = "stage7_gate3_numeric_capture_v1"
CAPTURE_ANALYSIS_ID = "stage7_gate3_numeric_equivalence_capture"
BASELINE_CFL = 0.10

_DISCRETE_FIELDS = (
    "case_id",
    "n_cells",
    "cfl",
    "maximum_steps",
    "outcome",
    "failure_reason",
    "step_count",
    "crossing_step",
    "crossing_cell_index",
    "crossing_distance_from_outlet_m",
)

_HASH_FIELDS = (
    "final_state_sha256",
    "run_signature_sha256",
)


class HEMGate3NumericCaptureError(RuntimeError):
    """Raised when a diagnostic capture cannot be written safely."""


def _normalized_f64(array: np.ndarray) -> np.ndarray:
    """Return a contiguous, platform-neutral little-endian float64 array."""

    result = np.ascontiguousarray(np.asarray(array, dtype="<f8"))
    if not np.all(np.isfinite(result)):
        raise HEMGate3NumericCaptureError("capture arrays must contain only finite values")
    return result


def _array_sha256(array: np.ndarray) -> str:
    normalized = _normalized_f64(array)
    digest = hashlib.sha256()
    digest.update(str(normalized.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(normalized.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(normalized.tobytes(order="C"))
    return digest.hexdigest()


def _relative_difference(actual: float, expected: float) -> float:
    denominator = max(abs(actual), abs(expected), np.finfo(float).tiny)
    return abs(actual - expected) / denominator


def compare_metrics_to_authoritative(
    actual: Mapping[str, object],
    expected: Mapping[str, object],
) -> dict[str, object]:
    """Describe exact/discrete and numeric differences without accepting them."""

    discrete: dict[str, object] = {}
    numeric: dict[str, object] = {}
    hashes: dict[str, object] = {}

    for key, expected_value in expected.items():
        if key not in actual:
            raise HEMGate3NumericCaptureError(f"actual metric is missing {key!r}")
        actual_value = actual[key]

        if key in _HASH_FIELDS:
            hashes[key] = {
                "actual": str(actual_value),
                "expected": str(expected_value),
                "exact": actual_value == expected_value,
            }
            continue

        if key in _DISCRETE_FIELDS or isinstance(expected_value, (str, bool, int)):
            discrete[key] = {
                "actual": actual_value,
                "expected": expected_value,
                "exact": actual_value == expected_value,
            }
            continue

        if expected_value is None:
            discrete[key] = {
                "actual": actual_value,
                "expected": None,
                "exact": actual_value is None,
            }
            continue

        actual_float = float(actual_value)
        expected_float = float(expected_value)
        numeric[key] = {
            "actual": actual_float,
            "expected": expected_float,
            "absolute_difference": abs(actual_float - expected_float),
            "relative_difference": _relative_difference(actual_float, expected_float),
            "exact": actual_float == expected_float,
        }

    return {
        "discrete": discrete,
        "numeric": numeric,
        "hashes": hashes,
        "all_discrete_fields_exact": all(
            bool(item["exact"]) for item in discrete.values()
        ),
        "all_numeric_fields_exact": all(
            bool(item["exact"]) for item in numeric.values()
        ),
        "all_hash_fields_exact": all(bool(item["exact"]) for item in hashes.values()),
    }


def _write_array(path: Path, array: np.ndarray) -> dict[str, object]:
    normalized = _normalized_f64(array)
    np.save(path, normalized, allow_pickle=False)
    return {
        "file": path.name,
        "shape": list(normalized.shape),
        "dtype": normalized.dtype.str,
        "minimum": float(np.min(normalized)),
        "maximum": float(np.max(normalized)),
        "sha256": _array_sha256(normalized),
    }


def write_gate3_numeric_capture(output_dir: str | Path) -> dict[str, object]:
    """Run the fixed cases and write diagnostic evidence without exact assertions."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    provenance = collect_cfl_runtime_provenance()
    provenance = dict(provenance)
    provenance["parent_analysis_id"] = provenance.get("analysis_id")
    provenance["analysis_id"] = CAPTURE_ANALYSIS_ID

    config = HEMPipelineCflSensitivityConfig.for_cfl(BASELINE_CFL)
    case_summaries: list[dict[str, object]] = []

    for case_spec in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        case = run_pipeline_depressurization_case(case_spec, config)
        metrics = asdict(_case_metrics(case))
        expected = EXPECTED_128_CELL_CFL_0P10[case_spec.case_id]
        comparison = compare_metrics_to_authoritative(metrics, expected)

        case_dir = target / case_spec.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        arrays = {
            "time_history_s": _write_array(
                case_dir / "time_history_s.npy",
                case.time_history_s,
            ),
            "pressure_history_pa": _write_array(
                case_dir / "pressure_history_pa.npy",
                case.pressure_history_pa,
            ),
            "accepted_state_history": _write_array(
                case_dir / "accepted_state_history.npy",
                case.accepted_state_history,
            ),
        }

        case_summary = {
            "case_id": case_spec.case_id,
            "metrics": metrics,
            "authoritative_pr82_comparison": comparison,
            "arrays": arrays,
        }
        (case_dir / "case_capture.json").write_text(
            json.dumps(case_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        case_summaries.append(case_summary)

    summary = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "scope": "diagnostic_only",
        "analysis_identity": {
            "analysis_id": CAPTURE_ANALYSIS_ID,
            "model": "HEM",
            "backend": "coolprop_co2",
            "version": provenance["property_backend_version"],
        },
        "provenance": provenance,
        "n_cells": config.n_cells,
        "cfl": config.cfl,
        "maximum_steps": config.max_steps,
        "case_count": len(case_summaries),
        "case_ids": [item["case_id"] for item in case_summaries],
        "exact_baseline_assertion_invoked": False,
        "solver_logic_changed": False,
        "algorithm_or_tolerance_changed": False,
        "capture_contains_raw_histories": True,
        "automatic_numeric_equivalence_acceptance": False,
        "cases": case_summaries,
        "Gate_P2_passed": False,
        "mesh_independent_crossing_verified": False,
        "CFL_independent_crossing_verified": False,
        "near_saturation_acoustic_continuity_approved": False,
        "post_crossing_propagation_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    (target / "gate3_numeric_capture_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture raw Stage 7 Gate 3 histories without invoking exact baseline guards."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = write_gate3_numeric_capture(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
