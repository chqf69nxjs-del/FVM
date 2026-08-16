"""Stage 7 P1-A3 mesh/CFL sensitivity characterization.

The locked 32-cell/CFL=0.10 Gate 6 runner is reused unchanged.  Four additional
verification-only cases vary only mesh count or CFL.  Results are compared at a
common physical post-crossing horizon and retain separate ordering and
quantitative-sensitivity verdicts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import hem_pipeline_post_crossing_propagation as gate6
from .hem_pipeline_mesh_cfl_variant import (
    HEMMeshCflPipelineConfig,
    HEMMeshCflPropagationConfig,
    run_mesh_cfl_variant,
)
from .hem_pipeline_pressure_phase_relationship import _build_snapshot_history

P1_A3_SCHEMA_VERSION = "stage7_p1_mesh_cfl_sensitivity_a3_v1"
P1_A3_MODEL_ID = "HEM_EQUILIBRIUM"
P1_A3_PRESSURE_THRESHOLD_RELATIVE = 1.0e-6
P1_A3_CFL_LOW_LIMIT = 0.02
P1_A3_CFL_MODERATE_LIMIT = 0.10
P1_A3_OUTPUT_FILES = (
    "mesh_cfl_summary.json",
    "case_metrics.csv",
    "mesh_convergence.csv",
    "cfl_sensitivity.csv",
    "front_history.csv",
    "front_comparison.png",
    "decision_metrics.png",
    "operator_report.md",
    "mesh_cfl_manifest.json",
)
P1_A3_FORMAL_STATUS = {
    "implemented": True,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "mesh_independent_crossing_verified": False,
    "cfl_independent_crossing_verified": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

SensitivityExecutionStatus = Literal["SENSITIVITY_READY", "FAIL_CLOSED"]
OrderingVerdict = Literal["ROBUST", "SENSITIVE", "INCONCLUSIVE"]
NumericalVerdict = Literal[
    "ROBUST_ORDERING_WITH_BOUNDED_NUMERICAL_SENSITIVITY",
    "ROBUST_ORDERING_BUT_NUMERICALLY_SENSITIVE",
    "SENSITIVE",
    "INCONCLUSIVE",
]


class P1MeshCflSensitivityError(RuntimeError):
    """Raised when the P1-A3 evidence contract cannot be written safely."""


@dataclass(frozen=True)
class P1A3CaseSpec:
    case_id: str
    role: str
    n_cells: int
    cfl: float
    use_locked_gate6_authority: bool


P1_A3_CASE_SPECS = (
    P1A3CaseSpec("mesh_16_cfl_0p10", "coarse_mesh", 16, 0.10, False),
    P1A3CaseSpec("baseline_32_cfl_0p10", "locked_gate6_baseline", 32, 0.10, True),
    P1A3CaseSpec("mesh_64_cfl_0p10", "fine_mesh", 64, 0.10, False),
    P1A3CaseSpec("cfl_32_0p05", "low_cfl", 32, 0.05, False),
    P1A3CaseSpec("cfl_32_0p20", "high_cfl", 32, 0.20, False),
)


@dataclass(frozen=True)
class P1MeshCflSensitivityResult:
    common_horizon_s: float | None
    case_metrics: tuple[dict[str, object], ...]
    mesh_convergence: tuple[dict[str, object], ...]
    cfl_sensitivity: tuple[dict[str, object], ...]
    front_history: tuple[dict[str, object], ...]
    gates: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    sensitivity_execution_status: SensitivityExecutionStatus
    ordering_verdict: OrderingVerdict
    numerical_verdict: NumericalVerdict
    sensitivity_sha256: str

    @property
    def sensitivity_ready(self) -> bool:
        return self.sensitivity_execution_status == "SENSITIVITY_READY"

    def summary(self) -> dict[str, object]:
        mesh_counts = _count_values(self.mesh_convergence, "trend")
        cfl_counts = _count_values(self.cfl_sensitivity, "classification")
        return {
            "schema_version": P1_A3_SCHEMA_VERSION,
            "scope": (
                "predeclared_mesh_cfl_characterization_with_locked_gate6_baseline"
            ),
            "model_id": P1_A3_MODEL_ID,
            "pressure_drop_threshold_relative": (
                P1_A3_PRESSURE_THRESHOLD_RELATIVE
            ),
            "case_count": len(P1_A3_CASE_SPECS),
            "case_specs": [asdict(spec) for spec in P1_A3_CASE_SPECS],
            "common_post_crossing_horizon_s": self.common_horizon_s,
            "case_metrics": list(self.case_metrics),
            "mesh_convergence": list(self.mesh_convergence),
            "mesh_trend_counts": mesh_counts,
            "cfl_sensitivity": list(self.cfl_sensitivity),
            "cfl_classification_counts": cfl_counts,
            "front_history_record_count": len(self.front_history),
            "gate_results": {
                str(gate["gate"]): bool(gate["passed"]) for gate in self.gates
            },
            "gates": list(self.gates),
            "warnings": list(self.warnings),
            "sensitivity_execution_status": self.sensitivity_execution_status,
            "sensitivity_ready": self.sensitivity_ready,
            "ordering_verdict": self.ordering_verdict,
            "numerical_verdict": self.numerical_verdict,
            "interpretation_boundary": {
                "mesh_convergence": (
                    "Three mesh levels characterize trend only; no formal GCI "
                    "or mesh-independent verification is claimed."
                ),
                "cfl_sensitivity": (
                    "LOW <=2%, MODERATE <=10%, HIGH >10% maximum relative "
                    "deviation from CFL=0.10 for the declared metrics."
                ),
                "common_horizon": (
                    "Each case is sampled at the latest accepted snapshot not "
                    "later than the shortest completed +64-step duration."
                ),
                "fronts": (
                    "Pressure front is the inherited 1e-6 relative-drop "
                    "diagnostic; phase front is accepted equilibrium "
                    "OPEN_TWO_PHASE."
                ),
                "phase_delay": (
                    "HEM does not represent real nucleation or flashing delay."
                ),
            },
            "physics_or_production_numerics_changed": False,
            "locked_gate6_contract_changed": False,
            "formal_status": dict(P1_A3_FORMAL_STATUS),
            "sensitivity_sha256": self.sensitivity_sha256,
            "output_contract": list(P1_A3_OUTPUT_FILES),
        }


_METRICS = (
    ("first_crossing_time_s", "s"),
    ("furthest_upstream_crossing_distance_from_outlet_m", "m"),
    ("common_pressure_front_distance_from_outlet_m", "m"),
    ("common_phase_front_distance_from_outlet_m", "m"),
    ("common_pressure_phase_separation_m", "m"),
    ("common_vapor_mass_total_kg", "kg"),
    ("maximum_equilibrium_quality_to_common_horizon", "1"),
    ("maximum_void_fraction_to_common_horizon", "1"),
)


def _count_values(rows: Sequence[dict[str, object]], key: str) -> dict[str, int]:
    output: dict[str, int] = {}
    for row in rows:
        value = str(row[key])
        output[value] = output.get(value, 0) + 1
    return output


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_case(spec: P1A3CaseSpec) -> dict[str, object]:
    try:
        if spec.use_locked_gate6_authority:
            execution = gate6.run_post_crossing_propagation_review()
        else:
            pipeline = HEMMeshCflPipelineConfig(
                n_cells=spec.n_cells,
                cfl=spec.cfl,
            )
            execution = run_mesh_cfl_variant(
                HEMMeshCflPropagationConfig(pipeline=pipeline)
            )
        return {"spec": spec, "execution": execution, "error": ""}
    except Exception as exc:
        return {
            "spec": spec,
            "execution": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _front_positions(
    history: object,
    initial_pressure_pa: float,
) -> tuple[np.ndarray, np.ndarray]:
    drop = (initial_pressure_pa - history.pressures_pa) / initial_pressure_pa
    pressure = np.full(history.times_s.shape, np.nan, dtype=float)
    phase = np.full(history.times_s.shape, np.nan, dtype=float)
    for index in range(history.times_s.size):
        pressure_cells = np.flatnonzero(
            drop[index] >= P1_A3_PRESSURE_THRESHOLD_RELATIVE
        )
        phase_cells = np.flatnonzero(
            history.regions[index] == "OPEN_TWO_PHASE"
        )
        if pressure_cells.size:
            pressure[index] = float(
                np.max(history.distances_from_outlet_m[pressure_cells])
            )
        if phase_cells.size:
            phase[index] = float(
                np.max(history.distances_from_outlet_m[phase_cells])
            )
    return pressure, phase


def _front_history(envelope: dict[str, object]) -> tuple[dict[str, object], ...]:
    spec = envelope["spec"]
    execution = envelope["execution"]
    if execution is None:
        return ()
    history = _build_snapshot_history(execution)
    crossing_time = execution.baseline.crossing_time_s
    if crossing_time is None:
        return ()
    pressure, phase = _front_positions(
        history,
        float(execution.config.pipeline.initial_pressure_pa),
    )
    rows = []
    for index, time_s in enumerate(history.times_s):
        relative_time = float(time_s - crossing_time)
        if relative_time < -1.0e-15:
            continue
        p_value = _finite_or_none(pressure[index])
        ph_value = _finite_or_none(phase[index])
        separation = (
            None if p_value is None or ph_value is None else p_value - ph_value
        )
        ahead = (
            None
            if ph_value is None
            else p_value is not None and p_value > ph_value + 1.0e-15
        )
        rows.append(
            {
                "case_id": spec.case_id,
                "role": spec.role,
                "n_cells": spec.n_cells,
                "cfl": spec.cfl,
                "snapshot_index": index,
                "source_segment": str(history.segments[index]),
                "absolute_step": int(history.absolute_steps[index]),
                "time_s": float(time_s),
                "time_after_crossing_s": relative_time,
                "pressure_front_distance_from_outlet_m": p_value,
                "phase_front_distance_from_outlet_m": ph_value,
                "pressure_phase_separation_m": separation,
                "pressure_strictly_ahead_when_phase_present": ahead,
            }
        )
    return tuple(rows)


def _finite_or_none(value: object) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def _completed_duration(envelope: dict[str, object]) -> float | None:
    execution = envelope["execution"]
    if (
        execution is None
        or execution.outcome != "COMPLETED_FIXED_CHECKPOINTS"
        or len(execution.steps) != execution.config.maximum_post_crossing_steps
        or execution.baseline.crossing_time_s is None
    ):
        return None
    return float(
        execution.steps[-1].time_after_s
        - execution.baseline.crossing_time_s
    )


def _baseline_crossing_alpha(execution: object) -> float:
    values = [
        float(row.alpha_post)
        for row in execution.baseline.cells
        if row.step_index == execution.baseline.crossing_step
        and row.alpha_post is not None
    ]
    return max(values, default=0.0)


def _empty_case_metric(
    spec: P1A3CaseSpec,
    error: str,
    common_horizon_s: float | None,
) -> dict[str, object]:
    return {
        "case_id": spec.case_id,
        "role": spec.role,
        "n_cells": spec.n_cells,
        "cfl": spec.cfl,
        "dx_m": 1.0 / spec.n_cells,
        "source_kind": (
            "LOCKED_GATE6_AUTHORITY"
            if spec.use_locked_gate6_authority
            else "P1_A3_VARIANT"
        ),
        "execution_available": False,
        "execution_error": error,
        "baseline_outcome": "UNAVAILABLE",
        "continuation_outcome": "UNAVAILABLE",
        "first_crossing_step": None,
        "first_crossing_time_s": None,
        "first_crossing_cell_count": 0,
        "furthest_upstream_crossing_distance_from_outlet_m": None,
        "maximum_crossing_quality": None,
        "successful_post_crossing_step_count": 0,
        "actual_post_crossing_duration_s": None,
        "common_horizon_s": common_horizon_s,
        "common_horizon_sample_post_step": None,
        "common_horizon_sample_time_after_crossing_s": None,
        "common_horizon_shortfall_s": None,
        "common_pressure_front_distance_from_outlet_m": None,
        "common_phase_front_distance_from_outlet_m": None,
        "common_pressure_phase_separation_m": None,
        "common_vapor_mass_total_kg": None,
        "common_maximum_equilibrium_quality": None,
        "common_maximum_void_fraction": None,
        "maximum_equilibrium_quality_to_common_horizon": None,
        "maximum_void_fraction_to_common_horizon": None,
        "final_pressure_front_distance_from_outlet_m": None,
        "final_phase_front_distance_from_outlet_m": None,
        "final_pressure_phase_separation_m": None,
        "final_vapor_mass_total_kg": None,
        "phase_bearing_snapshot_count_to_common_horizon": 0,
        "pressure_ahead_snapshot_count_to_common_horizon": 0,
        "pressure_ahead_all_phase_bearing_snapshots": None,
        "source_first_crossing_sha256": "",
        "source_last_valid_state_sha256": "",
    }


def _case_metric(
    envelope: dict[str, object],
    common_horizon_s: float | None,
    fronts: Sequence[dict[str, object]],
) -> dict[str, object]:
    spec = envelope["spec"]
    execution = envelope["execution"]
    if execution is None:
        return _empty_case_metric(spec, str(envelope["error"]), common_horizon_s)

    baseline = execution.baseline
    crossing_time = baseline.crossing_time_s
    crossing_distance = (
        max(baseline.crossing_distances_from_outlet_m)
        if baseline.crossing_distances_from_outlet_m
        else None
    )
    common_step = None
    common_front = None
    if common_horizon_s is not None and crossing_time is not None:
        eligible_steps = [
            row
            for row in execution.steps
            if row.time_after_s - crossing_time
            <= common_horizon_s + 1.0e-15
        ]
        eligible_fronts = [
            row
            for row in fronts
            if float(row["time_after_crossing_s"])
            <= common_horizon_s + 1.0e-15
        ]
        common_step = eligible_steps[-1] if eligible_steps else None
        common_front = eligible_fronts[-1] if eligible_fronts else None

    through_common = (
        []
        if common_step is None
        else [
            row
            for row in execution.steps
            if row.post_crossing_step <= common_step.post_crossing_step
        ]
    )
    max_quality = (
        None
        if common_horizon_s is None
        else max(
            [float(baseline.maximum_crossing_quality)]
            + [float(row.maximum_equilibrium_quality) for row in through_common]
        )
    )
    max_void = (
        None
        if common_horizon_s is None
        else max(
            [_baseline_crossing_alpha(execution)]
            + [float(row.maximum_void_fraction) for row in through_common]
        )
    )
    phase_rows = [
        row
        for row in fronts
        if common_horizon_s is not None
        and float(row["time_after_crossing_s"])
        <= common_horizon_s + 1.0e-15
        and row["phase_front_distance_from_outlet_m"] is not None
    ]
    ahead_count = sum(
        row["pressure_strictly_ahead_when_phase_present"] is True
        for row in phase_rows
    )
    sample_time = (
        None
        if common_step is None or crossing_time is None
        else float(common_step.time_after_s - crossing_time)
    )
    final_front = fronts[-1] if fronts else None
    final_step = execution.steps[-1] if execution.steps else None
    return {
        "case_id": spec.case_id,
        "role": spec.role,
        "n_cells": spec.n_cells,
        "cfl": spec.cfl,
        "dx_m": float(execution.config.pipeline.length_m / spec.n_cells),
        "source_kind": (
            "LOCKED_GATE6_AUTHORITY"
            if spec.use_locked_gate6_authority
            else "P1_A3_VARIANT"
        ),
        "execution_available": True,
        "execution_error": str(envelope["error"]),
        "baseline_outcome": str(baseline.outcome),
        "continuation_outcome": str(execution.outcome),
        "first_crossing_step": baseline.crossing_step,
        "first_crossing_time_s": (
            None if crossing_time is None else float(crossing_time)
        ),
        "first_crossing_cell_count": len(baseline.crossing_cell_indices),
        "furthest_upstream_crossing_distance_from_outlet_m": crossing_distance,
        "maximum_crossing_quality": float(baseline.maximum_crossing_quality),
        "successful_post_crossing_step_count": len(execution.steps),
        "actual_post_crossing_duration_s": _completed_duration(envelope),
        "common_horizon_s": common_horizon_s,
        "common_horizon_sample_post_step": (
            None if common_step is None else int(common_step.post_crossing_step)
        ),
        "common_horizon_sample_time_after_crossing_s": sample_time,
        "common_horizon_shortfall_s": (
            None
            if common_horizon_s is None or sample_time is None
            else common_horizon_s - sample_time
        ),
        "common_pressure_front_distance_from_outlet_m": _front_value(
            common_front, "pressure_front_distance_from_outlet_m"
        ),
        "common_phase_front_distance_from_outlet_m": _front_value(
            common_front, "phase_front_distance_from_outlet_m"
        ),
        "common_pressure_phase_separation_m": _front_value(
            common_front, "pressure_phase_separation_m"
        ),
        "common_vapor_mass_total_kg": (
            None if common_step is None else float(common_step.vapor_mass_total_kg)
        ),
        "common_maximum_equilibrium_quality": (
            None
            if common_step is None
            else float(common_step.maximum_equilibrium_quality)
        ),
        "common_maximum_void_fraction": (
            None
            if common_step is None
            else float(common_step.maximum_void_fraction)
        ),
        "maximum_equilibrium_quality_to_common_horizon": max_quality,
        "maximum_void_fraction_to_common_horizon": max_void,
        "final_pressure_front_distance_from_outlet_m": _front_value(
            final_front, "pressure_front_distance_from_outlet_m"
        ),
        "final_phase_front_distance_from_outlet_m": _front_value(
            final_front, "phase_front_distance_from_outlet_m"
        ),
        "final_pressure_phase_separation_m": _front_value(
            final_front, "pressure_phase_separation_m"
        ),
        "final_vapor_mass_total_kg": (
            None if final_step is None else float(final_step.vapor_mass_total_kg)
        ),
        "phase_bearing_snapshot_count_to_common_horizon": len(phase_rows),
        "pressure_ahead_snapshot_count_to_common_horizon": ahead_count,
        "pressure_ahead_all_phase_bearing_snapshots": (
            None if not phase_rows else ahead_count == len(phase_rows)
        ),
        "source_first_crossing_sha256": str(baseline.final_state_sha256),
        "source_last_valid_state_sha256": str(execution.last_valid_state_sha256),
    }


def _front_value(
    row: dict[str, object] | None,
    key: str,
) -> float | None:
    if row is None or row[key] is None:
        return None
    return float(row[key])


def _mesh_trend_record(
    metric: str,
    units: str,
    coarse: float | None,
    medium: float | None,
    fine: float | None,
) -> dict[str, object]:
    base = {
        "metric": metric,
        "units": units,
        "coarse_16": coarse,
        "medium_32": medium,
        "fine_64": fine,
    }
    if not _three_finite(coarse, medium, fine):
        return {
            **base,
            "coarse_to_medium_difference": None,
            "medium_to_fine_difference": None,
            "fine_over_coarse_difference_ratio": None,
            "apparent_order": None,
            "trend": "UNAVAILABLE",
        }
    assert coarse is not None and medium is not None and fine is not None
    d_cm = medium - coarse
    d_mf = fine - medium
    tolerance = 1.0e-12 * max(abs(coarse), abs(medium), abs(fine), 1.0)
    ratio = None if abs(d_cm) <= tolerance else d_mf / d_cm
    order = (
        math.log(abs(d_cm / d_mf), 2.0)
        if abs(d_cm) > tolerance and abs(d_mf) > tolerance
        else None
    )
    if abs(d_cm) <= tolerance and abs(d_mf) <= tolerance:
        trend = "INVARIANT_TO_REPORTED_PRECISION"
    elif d_cm * d_mf > 0.0 and abs(d_mf) < abs(d_cm):
        trend = "MONOTONIC_CONVERGENT_TREND"
    elif d_cm * d_mf < 0.0 and abs(d_mf) < abs(d_cm):
        trend = "OSCILLATORY_DAMPED_TREND"
    elif abs(d_mf) >= abs(d_cm) - tolerance:
        trend = "NONCONVERGENT_AT_TESTED_LEVELS"
    else:
        trend = "MIXED_TREND"
    return {
        **base,
        "coarse_to_medium_difference": d_cm,
        "medium_to_fine_difference": d_mf,
        "fine_over_coarse_difference_ratio": ratio,
        "apparent_order": order,
        "trend": trend,
    }


def _three_finite(*values: float | None) -> bool:
    return all(value is not None and math.isfinite(value) for value in values)


def _relative_deviation(value: float, reference: float, metric: str) -> float:
    spatial = metric.endswith("_distance_from_outlet_m") or metric.endswith(
        "_separation_m"
    )
    denominator = 1.0 if spatial else max(abs(reference), 1.0e-30)
    return abs(value - reference) / denominator


def _cfl_record(
    metric: str,
    units: str,
    low: float | None,
    reference: float | None,
    high: float | None,
) -> dict[str, object]:
    base = {
        "metric": metric,
        "units": units,
        "low_cfl_0p05": low,
        "reference_cfl_0p10": reference,
        "high_cfl_0p20": high,
    }
    if not _three_finite(low, reference, high):
        return {
            **base,
            "low_shift_from_reference": None,
            "high_shift_from_reference": None,
            "maximum_absolute_relative_deviation": None,
            "classification": "UNAVAILABLE",
        }
    assert low is not None and reference is not None and high is not None
    maximum = max(
        _relative_deviation(low, reference, metric),
        _relative_deviation(high, reference, metric),
    )
    classification = (
        "LOW"
        if maximum <= P1_A3_CFL_LOW_LIMIT
        else "MODERATE"
        if maximum <= P1_A3_CFL_MODERATE_LIMIT
        else "HIGH"
    )
    return {
        **base,
        "low_shift_from_reference": low - reference,
        "high_shift_from_reference": high - reference,
        "maximum_absolute_relative_deviation": maximum,
        "classification": classification,
    }


def _metric(row: dict[str, object], name: str) -> float | None:
    value = row[name]
    return None if value is None else float(value)


def _gate(name: str, passed: bool, detail: str) -> dict[str, object]:
    return {"gate": name, "passed": bool(passed), "detail": detail}


def _evaluate_gates(
    envelopes: Sequence[dict[str, object]],
    metrics: Sequence[dict[str, object]],
    common_horizon_s: float | None,
) -> tuple[dict[str, object], ...]:
    baseline_envelope = next(
        item
        for item in envelopes
        if item["spec"].case_id == "baseline_32_cfl_0p10"
    )
    baseline_exact = False
    if baseline_envelope["execution"] is not None:
        try:
            gate6._require_exact_baseline(
                baseline_envelope["execution"].baseline
            )
            baseline_exact = True
        except Exception:
            baseline_exact = False
    matrix_exact = tuple(item["spec"] for item in envelopes) == P1_A3_CASE_SPECS
    all_crossings = all(
        row["execution_available"]
        and row["baseline_outcome"] == "ACCEPTED_FIRST_CROSSING"
        and row["first_crossing_time_s"] is not None
        and int(row["first_crossing_cell_count"]) >= 1
        for row in metrics
    )
    all_continuations = all(
        row["continuation_outcome"] == "COMPLETED_FIXED_CHECKPOINTS"
        and int(row["successful_post_crossing_step_count"]) == 64
        for row in metrics
    )
    common_positive = (
        common_horizon_s is not None
        and math.isfinite(common_horizon_s)
        and common_horizon_s > 0.0
    )
    common_samples = common_positive and all(
        row["common_horizon_sample_post_step"] is not None
        and row["common_horizon_sample_time_after_crossing_s"] is not None
        and row["common_horizon_shortfall_s"] is not None
        and float(row["common_horizon_shortfall_s"]) >= -1.0e-15
        for row in metrics
    )
    scalar_keys = (
        "dx_m",
        "first_crossing_time_s",
        "furthest_upstream_crossing_distance_from_outlet_m",
        "maximum_crossing_quality",
        "actual_post_crossing_duration_s",
        "common_horizon_s",
        "common_horizon_sample_time_after_crossing_s",
        "common_horizon_shortfall_s",
        "common_pressure_front_distance_from_outlet_m",
        "common_phase_front_distance_from_outlet_m",
        "common_pressure_phase_separation_m",
        "common_vapor_mass_total_kg",
        "common_maximum_equilibrium_quality",
        "common_maximum_void_fraction",
        "maximum_equilibrium_quality_to_common_horizon",
        "maximum_void_fraction_to_common_horizon",
        "final_pressure_front_distance_from_outlet_m",
        "final_phase_front_distance_from_outlet_m",
        "final_pressure_phase_separation_m",
        "final_vapor_mass_total_kg",
    )
    finite = all(
        row[key] is None or math.isfinite(float(row[key]))
        for row in metrics
        for key in scalar_keys
    )
    hashes = all(
        len(str(row["source_first_crossing_sha256"])) == 64
        and len(str(row["source_last_valid_state_sha256"])) == 64
        for row in metrics
    )
    return (
        _gate(
            "PREDECLARED_MATRIX_EXACT",
            matrix_exact,
            "The five declared mesh/CFL cases are present in fixed order.",
        ),
        _gate(
            "LOCKED_GATE6_BASELINE_REPRODUCED_EXACTLY",
            baseline_exact,
            "The 32-cell/CFL=0.10 case is the unchanged exact Gate 6 authority.",
        ),
        _gate(
            "ALL_VARIANTS_REACHED_ACCEPTED_FIRST_CROSSING",
            all_crossings,
            "Every declared case retains an accepted first crossing.",
        ),
        _gate(
            "ALL_VARIANTS_COMPLETED_FIXED_64_STEPS",
            all_continuations,
            "Every declared case completes all +64 accepted steps.",
        ),
        _gate(
            "COMMON_PHYSICAL_HORIZON_POSITIVE",
            common_positive,
            "The shortest completed physical duration is positive.",
        ),
        _gate(
            "COMMON_HORIZON_SAMPLES_AVAILABLE",
            common_samples,
            "Every case has a sample at or before the common horizon.",
        ),
        _gate(
            "CASE_METRICS_FINITE_WHEN_AVAILABLE",
            finite,
            "Every available scalar decision metric is finite.",
        ),
        _gate(
            "DETERMINISTIC_SOURCE_HASHES_PRESENT",
            hashes,
            "Each case retains first-crossing and last-valid-state hashes.",
        ),
    )


def analyze_mesh_cfl_sensitivity() -> P1MeshCflSensitivityResult:
    """Execute and characterize the complete predeclared P1-A3 matrix."""

    envelopes = tuple(_run_case(spec) for spec in P1_A3_CASE_SPECS)
    histories = {
        item["spec"].case_id: _front_history(item) for item in envelopes
    }
    durations = [_completed_duration(item) for item in envelopes]
    common_horizon = (
        min(float(value) for value in durations if value is not None)
        if durations and all(value is not None for value in durations)
        else None
    )
    case_metrics = tuple(
        _case_metric(
            item,
            common_horizon,
            histories[item["spec"].case_id],
        )
        for item in envelopes
    )
    by_id = {str(row["case_id"]): row for row in case_metrics}
    coarse = by_id["mesh_16_cfl_0p10"]
    reference = by_id["baseline_32_cfl_0p10"]
    fine = by_id["mesh_64_cfl_0p10"]
    low = by_id["cfl_32_0p05"]
    high = by_id["cfl_32_0p20"]
    mesh = tuple(
        _mesh_trend_record(
            name,
            units,
            _metric(coarse, name),
            _metric(reference, name),
            _metric(fine, name),
        )
        for name, units in _METRICS
    )
    cfl = tuple(
        _cfl_record(
            name,
            units,
            _metric(low, name),
            _metric(reference, name),
            _metric(high, name),
        )
        for name, units in _METRICS
    )
    fronts = tuple(
        row
        for spec in P1_A3_CASE_SPECS
        for row in histories[spec.case_id]
    )
    gates = _evaluate_gates(envelopes, case_metrics, common_horizon)
    ready = all(bool(gate["passed"]) for gate in gates)
    ordering = [
        row["pressure_ahead_all_phase_bearing_snapshots"]
        for row in case_metrics
    ]
    if not ready or any(value is None for value in ordering):
        ordering_verdict: OrderingVerdict = "INCONCLUSIVE"
    elif all(value is True for value in ordering):
        ordering_verdict = "ROBUST"
    else:
        ordering_verdict = "SENSITIVE"
    mesh_sensitive = any(
        row["trend"] in {"NONCONVERGENT_AT_TESTED_LEVELS", "UNAVAILABLE"}
        for row in mesh
    )
    cfl_sensitive = any(
        row["classification"] in {"HIGH", "UNAVAILABLE"} for row in cfl
    )
    if not ready:
        numerical_verdict: NumericalVerdict = "INCONCLUSIVE"
    elif ordering_verdict == "SENSITIVE":
        numerical_verdict = "SENSITIVE"
    elif mesh_sensitive or cfl_sensitive:
        numerical_verdict = "ROBUST_ORDERING_BUT_NUMERICALLY_SENSITIVE"
    else:
        numerical_verdict = (
            "ROBUST_ORDERING_WITH_BOUNDED_NUMERICAL_SENSITIVITY"
        )

    warnings = [
        "MESH_INDEPENDENCE_NOT_VERIFIED",
        "CFL_INDEPENDENCE_NOT_VERIFIED",
        "FRONT_POSITIONS_ARE_CELL_CENTER_DIAGNOSTICS",
        "HEM_EQUILIBRIUM_DOES_NOT_MODEL_REAL_FLASHING_DELAY",
        "COMMON_HORIZON_USES_LATEST_SAMPLE_NOT_LATER_THAN_TARGET",
    ]
    for item in envelopes:
        if item["error"]:
            warnings.append(
                f"CASE_EXECUTION_ERROR:{item['spec'].case_id}:{item['error']}"
            )
        execution = item["execution"]
        if execution is not None and execution.outcome != "COMPLETED_FIXED_CHECKPOINTS":
            warnings.append(
                f"CASE_FAIL_SAFE:{item['spec'].case_id}:"
                f"{execution.failure_category}:{execution.failure_reason}"
            )
    warnings.extend(
        f"FAILED_GATE:{gate['gate']}"
        for gate in gates
        if not bool(gate["passed"])
    )
    warnings.extend(
        f"MESH_NONCONVERGENT_METRIC:{row['metric']}"
        for row in mesh
        if row["trend"] == "NONCONVERGENT_AT_TESTED_LEVELS"
    )
    warnings.extend(
        f"HIGH_CFL_SENSITIVITY_METRIC:{row['metric']}"
        for row in cfl
        if row["classification"] == "HIGH"
    )
    status: SensitivityExecutionStatus = (
        "SENSITIVITY_READY" if ready else "FAIL_CLOSED"
    )
    digest_payload = {
        "schema_version": P1_A3_SCHEMA_VERSION,
        "case_specs": [asdict(spec) for spec in P1_A3_CASE_SPECS],
        "common_horizon_s": common_horizon,
        "case_metrics": case_metrics,
        "mesh_convergence": mesh,
        "cfl_sensitivity": cfl,
        "front_history": fronts,
        "gates": gates,
        "warnings": warnings,
        "status": status,
        "ordering_verdict": ordering_verdict,
        "numerical_verdict": numerical_verdict,
        "formal_status": P1_A3_FORMAL_STATUS,
    }
    return P1MeshCflSensitivityResult(
        common_horizon_s=common_horizon,
        case_metrics=case_metrics,
        mesh_convergence=mesh,
        cfl_sensitivity=cfl,
        front_history=fronts,
        gates=gates,
        warnings=tuple(warnings),
        sensitivity_execution_status=status,
        ordering_verdict=ordering_verdict,
        numerical_verdict=numerical_verdict,
        sensitivity_sha256=_canonical_json_sha256(digest_payload),
    )


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, sort_keys=True)
                    if isinstance(value, (tuple, list, dict))
                    else value
                    for key, value in row.items()
                }
            )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _plot_fronts(path: Path, result: P1MeshCflSensitivityResult) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 5.5))
    for spec in P1_A3_CASE_SPECS:
        rows = [row for row in result.front_history if row["case_id"] == spec.case_id]
        times = np.asarray(
            [float(row["time_after_crossing_s"]) * 1.0e3 for row in rows]
        )
        pressure = np.asarray(
            [
                np.nan
                if row["pressure_front_distance_from_outlet_m"] is None
                else float(row["pressure_front_distance_from_outlet_m"])
                for row in rows
            ]
        )
        phase = np.asarray(
            [
                np.nan
                if row["phase_front_distance_from_outlet_m"] is None
                else float(row["phase_front_distance_from_outlet_m"])
                for row in rows
            ]
        )
        ax.plot(times, pressure, linestyle="--", label=f"{spec.case_id} pressure")
        ax.plot(times, phase, label=f"{spec.case_id} phase")
    if result.common_horizon_s is not None:
        ax.axvline(
            result.common_horizon_s * 1.0e3,
            linestyle=":",
            label="common horizon",
        )
    ax.set_xlabel("Time after first crossing [ms]")
    ax.set_ylabel("Distance from outlet [m]")
    ax.set_title("P1-A3 mesh/CFL front histories")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_metrics(path: Path, result: P1MeshCflSensitivityResult) -> None:
    reference = next(
        row
        for row in result.case_metrics
        if row["case_id"] == "baseline_32_cfl_0p10"
    )
    selected = (
        ("first_crossing_time_s", "crossing time / baseline"),
        (
            "common_phase_front_distance_from_outlet_m",
            "phase front / baseline",
        ),
        (
            "common_pressure_phase_separation_m",
            "front separation / baseline",
        ),
        ("common_vapor_mass_total_kg", "vapor inventory / baseline"),
        (
            "maximum_equilibrium_quality_to_common_horizon",
            "max quality / baseline",
        ),
        (
            "maximum_void_fraction_to_common_horizon",
            "max void / baseline",
        ),
    )
    labels = [str(row["case_id"]) for row in result.case_metrics]
    x = np.arange(len(labels), dtype=float)
    fig, ax = plt.subplots(figsize=(10.0, 5.5))
    for field, label in selected:
        denominator = reference[field]
        values = [
            np.nan
            if row[field] is None
            or denominator is None
            or abs(float(denominator)) <= 1.0e-30
            else float(row[field]) / float(denominator)
            for row in result.case_metrics
        ]
        ax.plot(x, values, marker="o", label=label)
    ax.axhline(1.0, linestyle="--")
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_ylabel("Ratio to locked 32-cell / CFL=0.10 baseline")
    ax.set_title("P1-A3 decision metrics normalized to baseline")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _operator_report(result: P1MeshCflSensitivityResult) -> str:
    lines = [
        "# P1-A3 Mesh / CFL Sensitivity Report",
        "",
        f"- execution status: `{result.sensitivity_execution_status}`",
        f"- ordering verdict: `{result.ordering_verdict}`",
        f"- numerical verdict: `{result.numerical_verdict}`",
        f"- common post-crossing horizon [s]: `{result.common_horizon_s}`",
        "",
        "## Case metrics",
        "",
        "| case | cells | CFL | crossing t [ms] | crossing x [m] | common phase front [m] | common separation [m] | vapor [kg] | max q | max alpha | ordering |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in result.case_metrics:
        crossing_ms = (
            None
            if row["first_crossing_time_s"] is None
            else float(row["first_crossing_time_s"]) * 1.0e3
        )
        values = (
            row["case_id"],
            row["n_cells"],
            f"{float(row['cfl']):.3f}",
            crossing_ms,
            row["furthest_upstream_crossing_distance_from_outlet_m"],
            row["common_phase_front_distance_from_outlet_m"],
            row["common_pressure_phase_separation_m"],
            row["common_vapor_mass_total_kg"],
            row["maximum_equilibrium_quality_to_common_horizon"],
            row["maximum_void_fraction_to_common_horizon"],
            row["pressure_ahead_all_phase_bearing_snapshots"],
        )
        lines.append("| " + " | ".join(str(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            (
                "Pressure-first ordering is evaluated separately from quantitative "
                "mesh/CFL sensitivity. A robust ordering verdict does not establish "
                "mesh independence, CFL independence, physical validation, or a "
                "real flashing-delay model."
            ),
            "",
            "## Formal status",
            "",
            "- IMPLEMENTED: true",
            "- WORKING VERTICAL SLICE: false",
            "- VERIFIED: false",
            "- ACCEPTED: false",
            "- MESH-INDEPENDENT CROSSING VERIFIED: false",
            "- CFL-INDEPENDENT CROSSING VERIFIED: false",
            "- PHYSICALLY VALIDATED: false",
            "- DESIGN-USE ACCEPTED: false",
            "- PRODUCTION APPROVED: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_mesh_cfl_sensitivity_artifacts(
    output_dir: str | Path,
    result: P1MeshCflSensitivityResult,
) -> dict[str, Path]:
    """Write the exact nine-file P1-A3 characterization bundle."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P1_A3_OUTPUT_FILES)
    unexpected = {
        path.name for path in target.iterdir() if path.is_file()
    } - expected
    if unexpected:
        raise P1MeshCflSensitivityError(
            f"output directory contains files outside A3 contract: {sorted(unexpected)}"
        )
    paths = {
        "summary": target / "mesh_cfl_summary.json",
        "case_metrics": target / "case_metrics.csv",
        "mesh_convergence": target / "mesh_convergence.csv",
        "cfl_sensitivity": target / "cfl_sensitivity.csv",
        "front_history": target / "front_history.csv",
        "front_comparison": target / "front_comparison.png",
        "decision_metrics": target / "decision_metrics.png",
        "operator_report": target / "operator_report.md",
        "manifest": target / "mesh_cfl_manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["case_metrics"], result.case_metrics)
    _write_csv(paths["mesh_convergence"], result.mesh_convergence)
    _write_csv(paths["cfl_sensitivity"], result.cfl_sensitivity)
    _write_csv(paths["front_history"], result.front_history)
    _plot_fronts(paths["front_comparison"], result)
    _plot_metrics(paths["decision_metrics"], result)
    paths["operator_report"].write_text(_operator_report(result), encoding="utf-8")
    payload = {
        path.name: {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for key, path in paths.items()
        if key != "manifest"
    }
    manifest = {
        "schema_version": P1_A3_SCHEMA_VERSION,
        "artifact_contract": "stage7_p1_mesh_cfl_sensitivity_exactly_9_files",
        "declared_file_count": len(P1_A3_OUTPUT_FILES),
        "declared_file_names": list(P1_A3_OUTPUT_FILES),
        "model_id": P1_A3_MODEL_ID,
        "sensitivity_execution_status": result.sensitivity_execution_status,
        "ordering_verdict": result.ordering_verdict,
        "numerical_verdict": result.numerical_verdict,
        "sensitivity_sha256": result.sensitivity_sha256,
        "payload_files": payload,
        "physics_or_production_numerics_changed": False,
        "locked_gate6_contract_changed": False,
        "formal_status": dict(P1_A3_FORMAL_STATUS),
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P1MeshCflSensitivityError(
            f"A3 output mismatch: expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    result = analyze_mesh_cfl_sensitivity()
    paths = write_mesh_cfl_sensitivity_artifacts(output_dir, result)
    summary = result.summary()
    summary["artifact_paths"] = {
        key: str(path) for key, path in paths.items()
    }
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Stage 7 P1-A3 mesh/CFL characterization without changing "
            "the locked Gate 6 authority."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["sensitivity_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
