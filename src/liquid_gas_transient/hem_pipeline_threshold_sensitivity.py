"""P1-A2 exact pressure-front threshold sensitivity for the fixed Stage 7 HEM case.

This successor postprocessor reuses the accepted Gate 6 history and the P1-A1
pressure/phase relationship machinery.  It evaluates the predeclared narrow
engineering envelope 0.5e-6, 1.0e-6, and 2.0e-6 without changing the solver,
EOS, mesh, CFL, boundary condition, phase classifier, or accepted state history.

The decision is deliberately narrow: whether the conclusion "the pressure
front precedes the accepted equilibrium phase front" survives the threshold
choice.  Arrival times and discrete cell-center front speeds remain diagnostic
and may move with the threshold.  This module does not establish a physical
nucleation delay, mesh/CFL independence, or physical front-speed validation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Literal, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .hem_pipeline_post_crossing_analysis import analyze_post_crossing_propagation
from .hem_pipeline_post_crossing_propagation import (
    run_post_crossing_propagation_review,
)
from .hem_pipeline_pressure_phase_relationship import (
    _arrival_index_for_threshold,
    _arrival_source,
    _build_snapshot_history,
    _front_events,
    analyze_pressure_phase_relationship,
)

P1_A2_SCHEMA_VERSION = "stage7_p1_threshold_sensitivity_a2_v1"
P1_A2_MODEL_ID = "HEM_EQUILIBRIUM"
P1_A2_THRESHOLD_MULTIPLIERS = (0.5, 1.0, 2.0)
P1_A2_OUTPUT_FILES = (
    "threshold_summary.json",
    "threshold_comparison.csv",
    "threshold_cell_arrivals.csv",
    "threshold_front_history.csv",
    "threshold_pressure_front_speed.csv",
    "threshold_front_position.png",
    "threshold_phase_lag.png",
    "operator_report.md",
    "threshold_manifest.json",
)
P1_A2_FORMAL_STATUS = {
    "implemented": True,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

SensitivityExecutionStatus = Literal["SENSITIVITY_READY", "FAIL_CLOSED"]
SensitivityVerdict = Literal["ROBUST", "SENSITIVE", "INCONCLUSIVE"]


class P1ThresholdSensitivityError(RuntimeError):
    """Raised when the inherited history cannot support the A2 comparison."""


@dataclass(frozen=True)
class P1A2GateRecord:
    gate: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class P1A2CellArrivalRecord:
    case_id: str
    model_id: str
    threshold_multiplier: float
    pressure_drop_threshold_relative: float
    reference_threshold: bool
    cell_index: int
    cell_center_m: float
    distance_from_outlet_m: float
    pressure_arrival_time_s: float | None
    pressure_arrival_source: str
    arrival_shift_from_reference_s: float | None
    first_phase_onset_time_s: float | None
    first_phase_onset_source: str
    pressure_to_phase_lag_s: float | None
    pressure_arrived_before_phase: bool | None


@dataclass(frozen=True)
class P1A2FrontHistoryRecord:
    case_id: str
    model_id: str
    threshold_multiplier: float
    pressure_drop_threshold_relative: float
    snapshot_index: int
    absolute_step: int
    source_segment: str
    time_s: float
    pressure_front_distance_from_outlet_m: float | None
    phase_front_distance_from_outlet_m: float | None
    pressure_phase_separation_m: float | None
    pressure_strictly_ahead_of_phase: bool | None
    pressure_not_behind_phase: bool | None


@dataclass(frozen=True)
class P1A2PressureFrontSpeedRecord:
    case_id: str
    model_id: str
    threshold_multiplier: float
    pressure_drop_threshold_relative: float
    event_index: int
    from_cell_index: int
    to_cell_index: int
    from_time_s: float
    to_time_s: float
    from_distance_from_outlet_m: float
    to_distance_from_outlet_m: float
    delta_time_s: float
    delta_distance_m: float
    discrete_segment_speed_m_s: float
    destination_local_sound_speed_m_s: float
    speed_to_local_sound_ratio: float
    diagnostic_definition: str


@dataclass(frozen=True)
class P1A2ThresholdComparisonRecord:
    threshold_multiplier: float
    pressure_drop_threshold_relative: float
    available_pressure_arrival_cell_count: int
    comparable_phase_cell_count: int
    first_pressure_arrival_time_s: float | None
    last_pressure_arrival_time_s: float | None
    median_arrival_shift_from_reference_s: float | None
    maximum_absolute_arrival_shift_from_reference_s: float | None
    minimum_pressure_to_phase_lag_s: float | None
    median_pressure_to_phase_lag_s: float | None
    mean_pressure_to_phase_lag_s: float | None
    maximum_pressure_to_phase_lag_s: float | None
    positive_pressure_to_phase_lag_all_comparable_cells: bool
    phase_bearing_snapshot_count: int
    pressure_strictly_ahead_snapshot_count: int
    pressure_strictly_ahead_all_phase_bearing_snapshots: bool
    final_pressure_front_distance_from_outlet_m: float | None
    final_phase_front_distance_from_outlet_m: float | None
    final_pressure_phase_separation_m: float | None
    pressure_front_speed_segment_count: int
    minimum_discrete_pressure_front_speed_m_s: float | None
    median_discrete_pressure_front_speed_m_s: float | None
    maximum_discrete_pressure_front_speed_m_s: float | None


@dataclass(frozen=True)
class P1ThresholdSensitivityResult:
    schema_version: str
    model_id: str
    case_id: str
    source_last_valid_state_sha256: str
    source_a0_analysis_sha256: str
    source_a1_relationship_sha256: str
    reference_pressure_drop_threshold_relative: float
    threshold_multipliers: tuple[float, ...]
    cell_arrivals: tuple[P1A2CellArrivalRecord, ...]
    front_history: tuple[P1A2FrontHistoryRecord, ...]
    pressure_front_speeds: tuple[P1A2PressureFrontSpeedRecord, ...]
    threshold_comparisons: tuple[P1A2ThresholdComparisonRecord, ...]
    gates: tuple[P1A2GateRecord, ...]
    decision_checks: dict[str, bool]
    warnings: tuple[str, ...]
    sensitivity_execution_status: SensitivityExecutionStatus
    sensitivity_verdict: SensitivityVerdict
    sensitivity_sha256: str

    @property
    def sensitivity_ready(self) -> bool:
        return self.sensitivity_execution_status == "SENSITIVITY_READY"

    def summary(self) -> dict[str, object]:
        comparisons = [asdict(row) for row in self.threshold_comparisons]
        reference = next(
            row
            for row in self.threshold_comparisons
            if math.isclose(row.threshold_multiplier, 1.0, rel_tol=0.0, abs_tol=0.0)
        )
        reference_speed = reference.median_discrete_pressure_front_speed_m_s
        speed_changes: list[dict[str, float | None]] = []
        for row in self.threshold_comparisons:
            current = row.median_discrete_pressure_front_speed_m_s
            relative = (
                None
                if current is None
                or reference_speed is None
                or reference_speed == 0.0
                else (current - reference_speed) / reference_speed
            )
            speed_changes.append(
                {
                    "threshold_multiplier": row.threshold_multiplier,
                    "median_speed_relative_change_from_reference": relative,
                }
            )
        return {
            "schema_version": self.schema_version,
            "scope": "fixed_case_pressure_front_threshold_postprocessing_only",
            "model_id": self.model_id,
            "case_id": self.case_id,
            "source_last_valid_state_sha256": self.source_last_valid_state_sha256,
            "source_a0_analysis_sha256": self.source_a0_analysis_sha256,
            "source_a1_relationship_sha256": self.source_a1_relationship_sha256,
            "reference_pressure_drop_threshold_relative": (
                self.reference_pressure_drop_threshold_relative
            ),
            "threshold_multipliers": list(self.threshold_multipliers),
            "effective_thresholds": [
                self.reference_pressure_drop_threshold_relative * multiplier
                for multiplier in self.threshold_multipliers
            ],
            "threshold_comparisons": comparisons,
            "pressure_front_speed_relative_changes": speed_changes,
            "cell_arrival_record_count": len(self.cell_arrivals),
            "front_history_record_count": len(self.front_history),
            "pressure_front_speed_record_count": len(self.pressure_front_speeds),
            "gate_results": {gate.gate: gate.passed for gate in self.gates},
            "gates": [asdict(gate) for gate in self.gates],
            "decision_checks": dict(self.decision_checks),
            "sensitivity_execution_status": self.sensitivity_execution_status,
            "sensitivity_ready": self.sensitivity_ready,
            "sensitivity_verdict": self.sensitivity_verdict,
            "verdict_scope": (
                "pressure-front-precedes-accepted-equilibrium-phase-front "
                "ordering over thresholds 0.5e-6, 1.0e-6, and 2.0e-6"
            ),
            "decision_statement": (
                "The pressure-front-first interpretation is retained across "
                "the predeclared threshold envelope."
                if self.sensitivity_verdict == "ROBUST"
                else (
                    "The pressure-front-first interpretation changes within "
                    "the predeclared threshold envelope."
                    if self.sensitivity_verdict == "SENSITIVE"
                    else "No engineering sensitivity verdict is available."
                )
            ),
            "warnings": list(self.warnings),
            "output_contract": list(P1_A2_OUTPUT_FILES),
            "physics_or_numerics_changed": False,
            "formal_status": dict(P1_A2_FORMAL_STATUS),
        }


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _numeric_summary(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {
            "minimum": None,
            "median": None,
            "mean": None,
            "maximum": None,
        }
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise P1ThresholdSensitivityError("numeric summary contains nonfinite values")
    return {
        "minimum": float(np.min(array)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "maximum": float(np.max(array)),
    }


def _front_distance(mask: np.ndarray, distances_m: np.ndarray) -> float | None:
    active = np.flatnonzero(mask)
    if active.size == 0:
        return None
    return float(np.max(distances_m[active]))


def _build_cell_arrivals(
    source: object,
    history: object,
    a1_result: object,
) -> tuple[P1A2CellArrivalRecord, ...]:
    pipeline = source.config.pipeline
    reference = float(pipeline.pressure_drop_evidence_relative)
    reference_indices = tuple(
        _arrival_index_for_threshold(
            history,
            initial_pressure_pa=float(pipeline.initial_pressure_pa),
            threshold_relative=reference,
            cell_index=cell,
        )
        for cell in range(pipeline.n_cells)
    )
    output: list[P1A2CellArrivalRecord] = []
    for multiplier in P1_A2_THRESHOLD_MULTIPLIERS:
        threshold = reference * multiplier
        for cell in range(pipeline.n_cells):
            index = _arrival_index_for_threshold(
                history,
                initial_pressure_pa=float(pipeline.initial_pressure_pa),
                threshold_relative=threshold,
                cell_index=cell,
            )
            reference_index = reference_indices[cell]
            arrival_time = None if index is None else float(history.times_s[index])
            reference_time = (
                None
                if reference_index is None
                else float(history.times_s[reference_index])
            )
            shift = (
                None
                if arrival_time is None or reference_time is None
                else arrival_time - reference_time
            )
            inherited_phase = a1_result.cell_lags[cell]
            phase_time = inherited_phase.first_phase_onset_time_s
            lag = (
                None
                if arrival_time is None or phase_time is None
                else float(phase_time) - arrival_time
            )
            order = None if lag is None else lag > 1.0e-15
            output.append(
                P1A2CellArrivalRecord(
                    case_id=source.baseline.case.case_id,
                    model_id=P1_A2_MODEL_ID,
                    threshold_multiplier=multiplier,
                    pressure_drop_threshold_relative=threshold,
                    reference_threshold=math.isclose(
                        multiplier, 1.0, rel_tol=0.0, abs_tol=0.0
                    ),
                    cell_index=cell,
                    cell_center_m=float(history.cell_centers_m[cell]),
                    distance_from_outlet_m=float(
                        history.distances_from_outlet_m[cell]
                    ),
                    pressure_arrival_time_s=arrival_time,
                    pressure_arrival_source=_arrival_source(history, index),
                    arrival_shift_from_reference_s=shift,
                    first_phase_onset_time_s=(
                        None if phase_time is None else float(phase_time)
                    ),
                    first_phase_onset_source=str(
                        inherited_phase.first_phase_onset_source
                    ),
                    pressure_to_phase_lag_s=lag,
                    pressure_arrived_before_phase=order,
                )
            )
    return tuple(output)


def _build_front_history(
    source: object,
    history: object,
) -> tuple[P1A2FrontHistoryRecord, ...]:
    pipeline = source.config.pipeline
    reference = float(pipeline.pressure_drop_evidence_relative)
    initial = float(pipeline.initial_pressure_pa)
    output: list[P1A2FrontHistoryRecord] = []
    for multiplier in P1_A2_THRESHOLD_MULTIPLIERS:
        threshold = reference * multiplier
        for snapshot in range(history.times_s.size):
            pressure_drop = (
                initial - history.pressures_pa[snapshot]
            ) / initial
            pressure_distance = _front_distance(
                pressure_drop >= threshold,
                history.distances_from_outlet_m,
            )
            phase_distance = _front_distance(
                history.regions[snapshot] == "OPEN_TWO_PHASE",
                history.distances_from_outlet_m,
            )
            separation = (
                None
                if pressure_distance is None or phase_distance is None
                else pressure_distance - phase_distance
            )
            strictly_ahead = (
                None if separation is None else separation > 1.0e-15
            )
            not_behind = (
                None if separation is None else separation >= -1.0e-15
            )
            output.append(
                P1A2FrontHistoryRecord(
                    case_id=source.baseline.case.case_id,
                    model_id=P1_A2_MODEL_ID,
                    threshold_multiplier=multiplier,
                    pressure_drop_threshold_relative=threshold,
                    snapshot_index=snapshot,
                    absolute_step=int(history.absolute_steps[snapshot]),
                    source_segment=str(history.segments[snapshot]),
                    time_s=float(history.times_s[snapshot]),
                    pressure_front_distance_from_outlet_m=pressure_distance,
                    phase_front_distance_from_outlet_m=phase_distance,
                    pressure_phase_separation_m=separation,
                    pressure_strictly_ahead_of_phase=strictly_ahead,
                    pressure_not_behind_phase=not_behind,
                )
            )
    return tuple(output)


def _build_pressure_front_speeds(
    source: object,
    history: object,
) -> tuple[P1A2PressureFrontSpeedRecord, ...]:
    pipeline = source.config.pipeline
    reference = float(pipeline.pressure_drop_evidence_relative)
    output: list[P1A2PressureFrontSpeedRecord] = []
    for multiplier in P1_A2_THRESHOLD_MULTIPLIERS:
        threshold = reference * multiplier
        events = _front_events(
            kind="PRESSURE_FRONT",
            history=history,
            initial_pressure_pa=float(pipeline.initial_pressure_pa),
            pressure_threshold_relative=threshold,
        )
        for event_index, (previous, current) in enumerate(
            zip(events, events[1:]), start=1
        ):
            from_cell, from_time, from_distance, _ = previous
            to_cell, to_time, to_distance, to_sound = current
            delta_time = to_time - from_time
            delta_distance = to_distance - from_distance
            if delta_time <= 0.0 or delta_distance <= 0.0:
                raise P1ThresholdSensitivityError(
                    "pressure-front events must advance in time and distance"
                )
            speed = delta_distance / delta_time
            ratio = speed / to_sound
            if not all(math.isfinite(value) and value > 0.0 for value in (speed, to_sound, ratio)):
                raise P1ThresholdSensitivityError(
                    "pressure-front speed record contains invalid values"
                )
            output.append(
                P1A2PressureFrontSpeedRecord(
                    case_id=source.baseline.case.case_id,
                    model_id=P1_A2_MODEL_ID,
                    threshold_multiplier=multiplier,
                    pressure_drop_threshold_relative=threshold,
                    event_index=event_index,
                    from_cell_index=int(from_cell),
                    to_cell_index=int(to_cell),
                    from_time_s=float(from_time),
                    to_time_s=float(to_time),
                    from_distance_from_outlet_m=float(from_distance),
                    to_distance_from_outlet_m=float(to_distance),
                    delta_time_s=float(delta_time),
                    delta_distance_m=float(delta_distance),
                    discrete_segment_speed_m_s=float(speed),
                    destination_local_sound_speed_m_s=float(to_sound),
                    speed_to_local_sound_ratio=float(ratio),
                    diagnostic_definition=(
                        "cell-center pressure-threshold advancement slope; "
                        "not a validated physical wave speed"
                    ),
                )
            )
    return tuple(output)


def _build_threshold_comparisons(
    cell_arrivals: tuple[P1A2CellArrivalRecord, ...],
    front_history: tuple[P1A2FrontHistoryRecord, ...],
    pressure_front_speeds: tuple[P1A2PressureFrontSpeedRecord, ...],
) -> tuple[P1A2ThresholdComparisonRecord, ...]:
    output: list[P1A2ThresholdComparisonRecord] = []
    for multiplier in P1_A2_THRESHOLD_MULTIPLIERS:
        cells = [
            row for row in cell_arrivals if row.threshold_multiplier == multiplier
        ]
        fronts = [
            row for row in front_history if row.threshold_multiplier == multiplier
        ]
        speeds = [
            row
            for row in pressure_front_speeds
            if row.threshold_multiplier == multiplier
        ]
        arrivals = [
            row.pressure_arrival_time_s
            for row in cells
            if row.pressure_arrival_time_s is not None
        ]
        shifts = [
            row.arrival_shift_from_reference_s
            for row in cells
            if row.arrival_shift_from_reference_s is not None
        ]
        lag_rows = [
            row
            for row in cells
            if row.first_phase_onset_time_s is not None
            and row.pressure_arrival_time_s is not None
            and row.pressure_to_phase_lag_s is not None
        ]
        lags = [float(row.pressure_to_phase_lag_s) for row in lag_rows]
        lag_summary = _numeric_summary(lags)
        phase_front_rows = [
            row
            for row in fronts
            if row.phase_front_distance_from_outlet_m is not None
        ]
        strict_count = sum(
            row.pressure_strictly_ahead_of_phase is True
            for row in phase_front_rows
        )
        final = fronts[-1]
        speed_values = [row.discrete_segment_speed_m_s for row in speeds]
        speed_summary = _numeric_summary(speed_values)
        output.append(
            P1A2ThresholdComparisonRecord(
                threshold_multiplier=multiplier,
                pressure_drop_threshold_relative=(
                    cells[0].pressure_drop_threshold_relative
                ),
                available_pressure_arrival_cell_count=len(arrivals),
                comparable_phase_cell_count=len(lag_rows),
                first_pressure_arrival_time_s=(
                    min(arrivals) if arrivals else None
                ),
                last_pressure_arrival_time_s=(
                    max(arrivals) if arrivals else None
                ),
                median_arrival_shift_from_reference_s=(
                    float(np.median(shifts)) if shifts else None
                ),
                maximum_absolute_arrival_shift_from_reference_s=(
                    max(abs(value) for value in shifts) if shifts else None
                ),
                minimum_pressure_to_phase_lag_s=lag_summary["minimum"],
                median_pressure_to_phase_lag_s=lag_summary["median"],
                mean_pressure_to_phase_lag_s=lag_summary["mean"],
                maximum_pressure_to_phase_lag_s=lag_summary["maximum"],
                positive_pressure_to_phase_lag_all_comparable_cells=bool(
                    lag_rows and all(value > 1.0e-15 for value in lags)
                ),
                phase_bearing_snapshot_count=len(phase_front_rows),
                pressure_strictly_ahead_snapshot_count=strict_count,
                pressure_strictly_ahead_all_phase_bearing_snapshots=bool(
                    phase_front_rows and strict_count == len(phase_front_rows)
                ),
                final_pressure_front_distance_from_outlet_m=(
                    final.pressure_front_distance_from_outlet_m
                ),
                final_phase_front_distance_from_outlet_m=(
                    final.phase_front_distance_from_outlet_m
                ),
                final_pressure_phase_separation_m=(
                    final.pressure_phase_separation_m
                ),
                pressure_front_speed_segment_count=len(speeds),
                minimum_discrete_pressure_front_speed_m_s=(
                    speed_summary["minimum"]
                ),
                median_discrete_pressure_front_speed_m_s=(
                    speed_summary["median"]
                ),
                maximum_discrete_pressure_front_speed_m_s=(
                    speed_summary["maximum"]
                ),
            )
        )
    return tuple(output)


def _arrival_order_is_monotone(
    cell_arrivals: tuple[P1A2CellArrivalRecord, ...],
    n_cells: int,
) -> bool:
    for cell in range(n_cells):
        rows = {
            row.threshold_multiplier: row
            for row in cell_arrivals
            if row.cell_index == cell
        }
        times = [
            rows[multiplier].pressure_arrival_time_s
            for multiplier in P1_A2_THRESHOLD_MULTIPLIERS
        ]
        available = [value for value in times if value is not None]
        if any(
            later < earlier - 1.0e-15
            for earlier, later in zip(available, available[1:])
        ):
            return False
    return True


def analyze_threshold_sensitivity(
    source: object,
    a0_analysis: object | None = None,
    a1_relationship: object | None = None,
) -> P1ThresholdSensitivityResult:
    """Evaluate the exact 0.5/1.0/2.0 threshold envelope on one fixed history."""

    if a0_analysis is None:
        a0_analysis = analyze_post_crossing_propagation(source)
    if a1_relationship is None:
        a1_relationship = analyze_pressure_phase_relationship(source, a0_analysis)
    history = _build_snapshot_history(source)
    cell_arrivals = _build_cell_arrivals(source, history, a1_relationship)
    front_history = _build_front_history(source, history)
    speeds = _build_pressure_front_speeds(source, history)
    comparisons = _build_threshold_comparisons(
        cell_arrivals,
        front_history,
        speeds,
    )

    exact_thresholds = P1_A2_THRESHOLD_MULTIPLIERS == (0.5, 1.0, 2.0)
    history_complete = bool(
        history.pressures_pa.shape
        == (history.times_s.size, source.config.pipeline.n_cells)
        and history.regions.shape == history.pressures_pa.shape
        and np.all(np.isfinite(history.times_s))
        and np.all(np.diff(history.times_s) > 0.0)
    )
    arrivals_complete = len(cell_arrivals) == (
        source.config.pipeline.n_cells * len(P1_A2_THRESHOLD_MULTIPLIERS)
    )
    front_history_complete = len(front_history) == (
        history.times_s.size * len(P1_A2_THRESHOLD_MULTIPLIERS)
    )
    monotone = _arrival_order_is_monotone(
        cell_arrivals,
        source.config.pipeline.n_cells,
    )
    finite_speeds = bool(
        speeds
        and all(
            math.isfinite(row.discrete_segment_speed_m_s)
            and row.discrete_segment_speed_m_s > 0.0
            for row in speeds
        )
    )
    source_hashes = bool(
        source.last_valid_state_sha256
        and a0_analysis.analysis_sha256
        and a1_relationship.relationship_sha256
    )
    gates = (
        P1A2GateRecord(
            "SOURCE_A1_RELATIONSHIP_READY",
            bool(a1_relationship.relationship_ready),
            "The inherited P1-A1 relationship must be RELATIONSHIP_READY.",
        ),
        P1A2GateRecord(
            "EXACT_PREDECLARED_THRESHOLD_ENVELOPE",
            exact_thresholds,
            "Threshold multipliers are exactly 0.5, 1.0, and 2.0.",
        ),
        P1A2GateRecord(
            "COMBINED_HISTORY_COMPLETE_AND_ORDERED",
            history_complete,
            "The inherited accepted history is complete, finite, and ordered.",
        ),
        P1A2GateRecord(
            "CELL_ARRIVAL_MATRIX_COMPLETE",
            arrivals_complete,
            "Every threshold/cell pair has one comparison record.",
        ),
        P1A2GateRecord(
            "FRONT_HISTORY_MATRIX_COMPLETE",
            front_history_complete,
            "Every threshold/snapshot pair has one front-history record.",
        ),
        P1A2GateRecord(
            "THRESHOLD_ARRIVAL_ORDERING_MONOTONE",
            monotone,
            "Higher pressure-drop thresholds never arrive earlier.",
        ),
        P1A2GateRecord(
            "DISCRETE_PRESSURE_FRONT_SPEEDS_FINITE",
            finite_speeds,
            "All retained discrete pressure-front slopes are finite and positive.",
        ),
        P1A2GateRecord(
            "DETERMINISTIC_SOURCE_HASHES_PRESENT",
            source_hashes,
            "Gate 6, P1-A0, and P1-A1 source evidence hashes are present.",
        ),
    )
    decision_checks = {
        "all_phase_cells_comparable_at_every_threshold": all(
            row.comparable_phase_cell_count
            == a1_relationship.summary()["phase_onset_cell_count"]
            for row in comparisons
        ),
        "pressure_to_phase_lag_positive_at_every_threshold": all(
            row.positive_pressure_to_phase_lag_all_comparable_cells
            for row in comparisons
        ),
        "pressure_front_strictly_ahead_at_every_phase_bearing_snapshot": all(
            row.pressure_strictly_ahead_all_phase_bearing_snapshots
            for row in comparisons
        ),
        "final_pressure_front_not_behind_phase_front": all(
            row.final_pressure_phase_separation_m is not None
            and row.final_pressure_phase_separation_m >= -1.0e-15
            for row in comparisons
        ),
    }
    status: SensitivityExecutionStatus = (
        "SENSITIVITY_READY"
        if all(gate.passed for gate in gates)
        else "FAIL_CLOSED"
    )
    verdict: SensitivityVerdict
    if status != "SENSITIVITY_READY":
        verdict = "INCONCLUSIVE"
    elif all(decision_checks.values()):
        verdict = "ROBUST"
    else:
        verdict = "SENSITIVE"
    warnings = [
        "VERDICT_IS_LIMITED_TO_PRESSURE_FRONT_PHASE_FRONT_ORDERING",
        "ARRIVAL_TIME_AND_DISCRETE_SPEED_REMAIN_THRESHOLD_DEPENDENT",
        "DISCRETE_FRONT_SPEED_NOT_PHYSICALLY_VALIDATED",
        "HEM_EQUILIBRIUM_DOES_NOT_MODEL_PHYSICAL_FLASHING_DELAY",
        "MESH_AND_CFL_SENSITIVITY_NOT_ESTABLISHED",
        "PHYSICS_OR_NUMERICS_UNCHANGED",
    ]
    for gate in gates:
        if not gate.passed:
            warnings.append(f"FAILED_GATE:{gate.gate}")
    for check, passed in decision_checks.items():
        if not passed:
            warnings.append(f"FAILED_DECISION_CHECK:{check}")
    digest_payload = {
        "schema_version": P1_A2_SCHEMA_VERSION,
        "model_id": P1_A2_MODEL_ID,
        "case_id": source.baseline.case.case_id,
        "source_last_valid_state_sha256": source.last_valid_state_sha256,
        "source_a0_analysis_sha256": a0_analysis.analysis_sha256,
        "source_a1_relationship_sha256": a1_relationship.relationship_sha256,
        "reference_pressure_drop_threshold_relative": (
            source.config.pipeline.pressure_drop_evidence_relative
        ),
        "threshold_multipliers": P1_A2_THRESHOLD_MULTIPLIERS,
        "cell_arrivals": [asdict(row) for row in cell_arrivals],
        "front_history": [asdict(row) for row in front_history],
        "pressure_front_speeds": [asdict(row) for row in speeds],
        "threshold_comparisons": [asdict(row) for row in comparisons],
        "gates": [asdict(gate) for gate in gates],
        "decision_checks": decision_checks,
        "warnings": warnings,
        "sensitivity_execution_status": status,
        "sensitivity_verdict": verdict,
        "formal_status": P1_A2_FORMAL_STATUS,
    }
    sensitivity_sha256 = _canonical_json_sha256(digest_payload)
    return P1ThresholdSensitivityResult(
        schema_version=P1_A2_SCHEMA_VERSION,
        model_id=P1_A2_MODEL_ID,
        case_id=source.baseline.case.case_id,
        source_last_valid_state_sha256=source.last_valid_state_sha256,
        source_a0_analysis_sha256=a0_analysis.analysis_sha256,
        source_a1_relationship_sha256=a1_relationship.relationship_sha256,
        reference_pressure_drop_threshold_relative=float(
            source.config.pipeline.pressure_drop_evidence_relative
        ),
        threshold_multipliers=P1_A2_THRESHOLD_MULTIPLIERS,
        cell_arrivals=cell_arrivals,
        front_history=front_history,
        pressure_front_speeds=speeds,
        threshold_comparisons=comparisons,
        gates=gates,
        decision_checks=decision_checks,
        warnings=tuple(warnings),
        sensitivity_execution_status=status,
        sensitivity_verdict=verdict,
        sensitivity_sha256=sensitivity_sha256,
    )


def _write_dataclass_csv(path: Path, rows: Sequence[object], row_type: type) -> None:
    names = [item.name for item in fields(row_type)]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _plot_threshold_front_position(
    path: Path,
    result: P1ThresholdSensitivityResult,
) -> None:
    phase_rows = [
        row
        for row in result.front_history
        if math.isclose(row.threshold_multiplier, 1.0, rel_tol=0.0, abs_tol=0.0)
    ]
    phase_onset = [
        row.time_s
        for row in phase_rows
        if row.phase_front_distance_from_outlet_m is not None
    ]
    origin = min(phase_onset) if phase_onset else 0.0
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    for multiplier in P1_A2_THRESHOLD_MULTIPLIERS:
        rows = [
            row
            for row in result.front_history
            if row.threshold_multiplier == multiplier
        ]
        time_ms = np.asarray([row.time_s - origin for row in rows]) * 1.0e3
        distance = np.asarray(
            [
                np.nan
                if row.pressure_front_distance_from_outlet_m is None
                else row.pressure_front_distance_from_outlet_m
                for row in rows
            ]
        )
        ax.plot(
            time_ms,
            distance,
            label=f"Pressure front ({multiplier:g}e-6)",
        )
    phase_time_ms = np.asarray([row.time_s - origin for row in phase_rows]) * 1.0e3
    phase_distance = np.asarray(
        [
            np.nan
            if row.phase_front_distance_from_outlet_m is None
            else row.phase_front_distance_from_outlet_m
            for row in phase_rows
        ]
    )
    ax.plot(phase_time_ms, phase_distance, label="Accepted phase front")
    ax.set_xlabel("Time relative to first accepted phase onset [ms]")
    ax.set_ylabel("Distance from outlet [m]")
    ax.set_title("P1-A2 pressure-front threshold sensitivity")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_threshold_phase_lag(
    path: Path,
    result: P1ThresholdSensitivityResult,
) -> None:
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    for multiplier in P1_A2_THRESHOLD_MULTIPLIERS:
        rows = [
            row
            for row in result.cell_arrivals
            if row.threshold_multiplier == multiplier
            and row.pressure_to_phase_lag_s is not None
        ]
        rows.sort(key=lambda item: item.distance_from_outlet_m)
        distance = np.asarray([row.distance_from_outlet_m for row in rows])
        lag_ms = np.asarray(
            [float(row.pressure_to_phase_lag_s) * 1.0e3 for row in rows]
        )
        ax.plot(
            distance,
            lag_ms,
            marker="o",
            label=f"Threshold {multiplier:g}e-6",
        )
    ax.set_xlabel("Distance from outlet [m]")
    ax.set_ylabel("Pressure-arrival to first phase-onset lag [ms]")
    ax.set_title("P1-A2 cellwise pressure-to-phase lag sensitivity")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _operator_report(result: P1ThresholdSensitivityResult) -> str:
    lines = [
        "# P1-A2 Pressure-Front Threshold Sensitivity Report",
        "",
        f"- case: `{result.case_id}`",
        f"- model: `{result.model_id}`",
        f"- execution status: `{result.sensitivity_execution_status}`",
        f"- bounded verdict: `{result.sensitivity_verdict}`",
        "- thresholds: `0.5e-6`, `1.0e-6`, `2.0e-6` relative pressure drop",
        "",
        "## Threshold comparison",
        "",
        "| threshold | arrivals | comparable phase cells | lag min/mean/max [ms] | phase-bearing snapshots with pressure strictly ahead | final separation [m] | median discrete pressure-front slope [m/s] |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result.threshold_comparisons:
        lag_text = (
            "n/a"
            if row.minimum_pressure_to_phase_lag_s is None
            else (
                f"{row.minimum_pressure_to_phase_lag_s * 1.0e3:.6f} / "
                f"{row.mean_pressure_to_phase_lag_s * 1.0e3:.6f} / "
                f"{row.maximum_pressure_to_phase_lag_s * 1.0e3:.6f}"
            )
        )
        speed_text = (
            "n/a"
            if row.median_discrete_pressure_front_speed_m_s is None
            else f"{row.median_discrete_pressure_front_speed_m_s:.6f}"
        )
        separation_text = (
            "n/a"
            if row.final_pressure_phase_separation_m is None
            else f"{row.final_pressure_phase_separation_m:.6f}"
        )
        lines.append(
            "| "
            f"{row.pressure_drop_threshold_relative:.1e} | "
            f"{row.available_pressure_arrival_cell_count} | "
            f"{row.comparable_phase_cell_count} | "
            f"{lag_text} | "
            f"{row.pressure_strictly_ahead_snapshot_count}/"
            f"{row.phase_bearing_snapshot_count} | "
            f"{separation_text} | {speed_text} |"
        )
    lines.extend(
        [
            "",
            "## Engineering interpretation",
            "",
            (
                "The verdict applies only to whether the pressure front remains "
                "ahead of the accepted equilibrium OPEN_TWO_PHASE front across "
                "the predeclared threshold envelope. Exact arrival times and "
                "discrete cell-center slopes are reported rather than treated "
                "as threshold-independent physical quantities."
            ),
            "",
            "## Interpretation boundary",
            "",
            "- Postprocessing only; solver physics and numerical settings are unchanged.",
            "- HEM does not represent a physical nucleation or non-equilibrium flashing delay.",
            "- Discrete front slopes are diagnostic cell-center event slopes, not validated wave speeds.",
            "- Mesh and CFL sensitivity remain separate work.",
            "- No physical Validation, design-use acceptance, or production approval is claimed.",
            "",
            "## Formal status",
            "",
            "- IMPLEMENTED: true",
            "- WORKING VERTICAL SLICE: false",
            "- VERIFIED: false",
            "- ACCEPTED: false",
            "- PHYSICALLY VALIDATED: false",
            "- DESIGN-USE ACCEPTED: false",
            "- PRODUCTION APPROVED: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_threshold_sensitivity_artifacts(
    output_dir: str | Path,
    result: P1ThresholdSensitivityResult,
) -> dict[str, Path]:
    """Write the exact nine-file P1-A2 evidence contract."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P1_A2_OUTPUT_FILES)
    existing = {path.name for path in target.iterdir() if path.is_file()}
    unexpected = existing - expected
    if unexpected:
        raise P1ThresholdSensitivityError(
            f"output directory contains files outside the A2 contract: {sorted(unexpected)}"
        )
    paths = {
        "threshold_summary": target / "threshold_summary.json",
        "threshold_comparison": target / "threshold_comparison.csv",
        "threshold_cell_arrivals": target / "threshold_cell_arrivals.csv",
        "threshold_front_history": target / "threshold_front_history.csv",
        "threshold_pressure_front_speed": (
            target / "threshold_pressure_front_speed.csv"
        ),
        "threshold_front_position": target / "threshold_front_position.png",
        "threshold_phase_lag": target / "threshold_phase_lag.png",
        "operator_report": target / "operator_report.md",
        "threshold_manifest": target / "threshold_manifest.json",
    }
    paths["threshold_summary"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_dataclass_csv(
        paths["threshold_comparison"],
        result.threshold_comparisons,
        P1A2ThresholdComparisonRecord,
    )
    _write_dataclass_csv(
        paths["threshold_cell_arrivals"],
        result.cell_arrivals,
        P1A2CellArrivalRecord,
    )
    _write_dataclass_csv(
        paths["threshold_front_history"],
        result.front_history,
        P1A2FrontHistoryRecord,
    )
    _write_dataclass_csv(
        paths["threshold_pressure_front_speed"],
        result.pressure_front_speeds,
        P1A2PressureFrontSpeedRecord,
    )
    _plot_threshold_front_position(paths["threshold_front_position"], result)
    _plot_threshold_phase_lag(paths["threshold_phase_lag"], result)
    paths["operator_report"].write_text(
        _operator_report(result), encoding="utf-8"
    )
    payload_files: dict[str, dict[str, object]] = {}
    for key, path in paths.items():
        if key == "threshold_manifest":
            continue
        payload_files[path.name] = {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    manifest = {
        "schema_version": P1_A2_SCHEMA_VERSION,
        "artifact_contract": "stage7_p1_threshold_sensitivity_exactly_9_files",
        "declared_file_count": len(P1_A2_OUTPUT_FILES),
        "declared_file_names": list(P1_A2_OUTPUT_FILES),
        "case_id": result.case_id,
        "model_id": result.model_id,
        "sensitivity_execution_status": result.sensitivity_execution_status,
        "sensitivity_verdict": result.sensitivity_verdict,
        "sensitivity_sha256": result.sensitivity_sha256,
        "source_last_valid_state_sha256": result.source_last_valid_state_sha256,
        "source_a0_analysis_sha256": result.source_a0_analysis_sha256,
        "source_a1_relationship_sha256": result.source_a1_relationship_sha256,
        "payload_files": payload_files,
        "physics_or_numerics_changed": False,
        "formal_status": dict(P1_A2_FORMAL_STATUS),
    }
    paths["threshold_manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P1ThresholdSensitivityError(
            f"A2 output contract mismatch: expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    source = run_post_crossing_propagation_review()
    a0_analysis = analyze_post_crossing_propagation(source)
    a1_relationship = analyze_pressure_phase_relationship(source, a0_analysis)
    result = analyze_threshold_sensitivity(source, a0_analysis, a1_relationship)
    paths = write_threshold_sensitivity_artifacts(output_dir, result)
    summary = result.summary()
    summary["artifact_paths"] = {key: str(path) for key, path in paths.items()}
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage 7 P1-A2 exact 0.5/1.0/2.0 pressure-front "
            "threshold sensitivity without changing the physical solve."
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
