"""P1-A1 pressure-to-phase relationship analysis for the fixed Stage 7 HEM case.

This successor layer consumes the existing Gate 6 continuation and the P1-A0
analysis result.  It derives per-cell pressure-arrival-to-phase-onset lag,
discrete pressure/phase-front advancement speeds, and a predeclared pressure
threshold sensitivity envelope.  It also writes two operator-facing plots.

The module is postprocessing only.  It does not change the solver, EOS, CoolProp
backend, boundary, flux, phase classifier, quality projection, mesh, CFL,
threshold used by the authoritative A0 result, or any tolerance.  Discrete front
speeds are diagnostic slopes of cell-center events, not validated physical wave
or boiling-front velocities.
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

P1_A1_SCHEMA_VERSION = "stage7_p1_pressure_phase_relationship_a1_v1"
P1_A1_MODEL_ID = "HEM_EQUILIBRIUM"
P1_A1_THRESHOLD_MULTIPLIERS = (0.1, 1.0, 10.0)
P1_A1_MIN_PERSISTENT_SAMPLES = 2
P1_A1_OUTPUT_FILES = (
    "relationship_summary.json",
    "cell_lag.csv",
    "front_speed.csv",
    "threshold_sensitivity.csv",
    "front_relationship.png",
    "cell_phase_lag.png",
    "operator_report.md",
    "relationship_manifest.json",
)
P1_A1_FORMAL_STATUS = {
    "implemented": True,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

RelationshipExecutionStatus = Literal["RELATIONSHIP_READY", "FAIL_CLOSED"]
ArrivalSource = Literal[
    "PRE_CROSSING",
    "CROSSING",
    "POST_CROSSING",
    "UNAVAILABLE",
]
FrontKind = Literal["PRESSURE_FRONT", "PHASE_FRONT"]


class P1PressurePhaseRelationshipError(RuntimeError):
    """Raised when the inherited histories cannot be related unambiguously."""


@dataclass(frozen=True)
class P1A1GateRecord:
    gate: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class P1CellLagRecord:
    case_id: str
    model_id: str
    cell_index: int
    cell_center_m: float
    distance_from_outlet_m: float
    pressure_drop_threshold_relative: float
    pressure_arrival_time_s: float | None
    pressure_arrival_source: ArrivalSource
    sound_speed_at_pressure_arrival_m_s: float | None
    first_phase_onset_time_s: float | None
    first_phase_onset_source: ArrivalSource
    sound_speed_at_first_phase_onset_m_s: float | None
    first_phase_lag_s: float | None
    persistent_phase_onset_time_s: float | None
    persistent_phase_onset_source: ArrivalSource
    sound_speed_at_persistent_phase_onset_m_s: float | None
    persistent_phase_lag_s: float | None
    persistent_phase_sample_count: int
    liquid_to_two_phase_transition_count: int
    two_phase_to_liquid_transition_count: int
    phase_toggled: bool
    open_two_phase_at_final_horizon: bool
    first_onset_persistent_through_horizon: bool | None
    pressure_arrived_before_or_at_first_phase: bool | None
    pressure_arrived_before_or_at_persistent_phase: bool | None


@dataclass(frozen=True)
class P1FrontSpeedRecord:
    case_id: str
    model_id: str
    front_kind: FrontKind
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
class P1ThresholdSensitivityRecord:
    case_id: str
    model_id: str
    threshold_multiplier: float
    pressure_drop_threshold_relative: float
    reference_threshold: bool
    cell_index: int
    cell_center_m: float
    distance_from_outlet_m: float
    arrival_time_s: float | None
    arrival_source: ArrivalSource
    arrival_available: bool
    arrival_shift_from_reference_s: float | None


@dataclass(frozen=True)
class _SnapshotHistory:
    times_s: np.ndarray
    segments: tuple[ArrivalSource, ...]
    absolute_steps: tuple[int, ...]
    pressures_pa: np.ndarray
    sound_speeds_m_s: np.ndarray
    regions: np.ndarray
    transition_events: np.ndarray
    cell_centers_m: np.ndarray
    distances_from_outlet_m: np.ndarray


@dataclass(frozen=True)
class P1PressurePhaseRelationshipResult:
    schema_version: str
    model_id: str
    case_id: str
    source_outcome: str
    source_last_valid_state_sha256: str
    source_a0_analysis_sha256: str
    pressure_drop_threshold_relative: float
    threshold_multipliers: tuple[float, ...]
    cell_lags: tuple[P1CellLagRecord, ...]
    front_speeds: tuple[P1FrontSpeedRecord, ...]
    threshold_sensitivity: tuple[P1ThresholdSensitivityRecord, ...]
    pressure_front_history_time_s: tuple[float, ...]
    pressure_front_history_distance_m: tuple[float | None, ...]
    phase_front_history_time_s: tuple[float, ...]
    phase_front_history_distance_m: tuple[float | None, ...]
    gates: tuple[P1A1GateRecord, ...]
    warnings: tuple[str, ...]
    relationship_execution_status: RelationshipExecutionStatus
    relationship_sha256: str

    @property
    def relationship_ready(self) -> bool:
        return self.relationship_execution_status == "RELATIONSHIP_READY"

    def summary(self) -> dict[str, object]:
        phase_rows = [
            row for row in self.cell_lags if row.first_phase_onset_time_s is not None
        ]
        persistent_rows = [
            row
            for row in self.cell_lags
            if row.persistent_phase_onset_time_s is not None
        ]
        first_lags = [
            row.first_phase_lag_s
            for row in phase_rows
            if row.first_phase_lag_s is not None
        ]
        persistent_lags = [
            row.persistent_phase_lag_s
            for row in persistent_rows
            if row.persistent_phase_lag_s is not None
        ]
        pressure_speeds = [
            row.discrete_segment_speed_m_s
            for row in self.front_speeds
            if row.front_kind == "PRESSURE_FRONT"
        ]
        phase_speeds = [
            row.discrete_segment_speed_m_s
            for row in self.front_speeds
            if row.front_kind == "PHASE_FRONT"
        ]
        threshold_summaries = []
        for multiplier in self.threshold_multipliers:
            rows = [
                row
                for row in self.threshold_sensitivity
                if math.isclose(
                    row.threshold_multiplier,
                    multiplier,
                    rel_tol=0.0,
                    abs_tol=0.0,
                )
            ]
            arrivals = [
                row.arrival_time_s for row in rows if row.arrival_time_s is not None
            ]
            shifts = [
                row.arrival_shift_from_reference_s
                for row in rows
                if row.arrival_shift_from_reference_s is not None
            ]
            threshold_summaries.append(
                {
                    "threshold_multiplier": multiplier,
                    "pressure_drop_threshold_relative": (
                        self.pressure_drop_threshold_relative * multiplier
                    ),
                    "available_cell_count": len(arrivals),
                    "first_arrival_time_s": min(arrivals) if arrivals else None,
                    "last_arrival_time_s": max(arrivals) if arrivals else None,
                    "median_shift_from_reference_s": (
                        float(np.median(shifts)) if shifts else None
                    ),
                    "maximum_absolute_shift_from_reference_s": (
                        max(abs(value) for value in shifts) if shifts else None
                    ),
                }
            )
        return {
            "schema_version": self.schema_version,
            "scope": "bounded_pressure_to_phase_relationship_postprocessing_only",
            "model_id": self.model_id,
            "case_id": self.case_id,
            "source_outcome": self.source_outcome,
            "source_last_valid_state_sha256": self.source_last_valid_state_sha256,
            "source_a0_analysis_sha256": self.source_a0_analysis_sha256,
            "pressure_drop_threshold_relative": (
                self.pressure_drop_threshold_relative
            ),
            "threshold_multipliers": list(self.threshold_multipliers),
            "minimum_persistent_phase_samples": P1_A1_MIN_PERSISTENT_SAMPLES,
            "cell_lag_record_count": len(self.cell_lags),
            "phase_onset_cell_count": len(phase_rows),
            "persistent_phase_onset_cell_count": len(persistent_rows),
            "phase_toggle_cell_indices": [
                row.cell_index for row in self.cell_lags if row.phase_toggled
            ],
            "first_phase_lag_summary_s": _numeric_summary(first_lags),
            "persistent_phase_lag_summary_s": _numeric_summary(persistent_lags),
            "pressure_front_speed_summary_m_s": _numeric_summary(pressure_speeds),
            "phase_front_speed_summary_m_s": _numeric_summary(phase_speeds),
            "threshold_sensitivity_summary": threshold_summaries,
            "relationship_execution_status": self.relationship_execution_status,
            "relationship_ready": self.relationship_ready,
            "gate_results": {gate.gate: gate.passed for gate in self.gates},
            "gates": [asdict(gate) for gate in self.gates],
            "warnings": list(self.warnings),
            "relationship_sha256": self.relationship_sha256,
            "output_contract": list(P1_A1_OUTPUT_FILES),
            "diagnostic_interpretation": {
                "cell_lag": (
                    "pressure threshold arrival to first/persistent accepted "
                    "OPEN_TWO_PHASE onset at the same cell"
                ),
                "front_speed": (
                    "discrete cell-center advancement slope; not a validated "
                    "physical wave or phase-front velocity"
                ),
                "threshold_sensitivity": (
                    "predeclared one-decade envelope around the inherited A0 "
                    "pressure-drop evidence threshold; no threshold is tuned"
                ),
            },
            "model_comparison_interface": {
                "current_model_id": self.model_id,
                "future_model_id": "HNE_RELAXATION",
                "shared_cell_lag_schema": True,
                "shared_front_speed_schema": True,
                "shared_threshold_sensitivity_schema": True,
            },
            "physics_or_numerics_changed": False,
            "formal_status": dict(P1_A1_FORMAL_STATUS),
        }


def _numeric_summary(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "minimum": None, "median": None, "maximum": None}
    array = np.asarray(values, dtype=float)
    return {
        "count": int(array.size),
        "minimum": float(np.min(array)),
        "median": float(np.median(array)),
        "maximum": float(np.max(array)),
    }


def _canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finite_optional(value: float | None) -> bool:
    return value is None or math.isfinite(value)


def _source_segment(
    *, time_s: float,
    crossing_time_s: float,
    post_crossing: bool,
) -> ArrivalSource:
    if post_crossing:
        return "POST_CROSSING"
    if math.isclose(time_s, crossing_time_s, rel_tol=0.0, abs_tol=1.0e-15):
        return "CROSSING"
    return "PRE_CROSSING"


def _group_exact_cell_records(
    records: Sequence[object],
    *,
    step_attribute: str,
    expected_steps: Sequence[int],
    n_cells: int,
) -> dict[int, tuple[object, ...]]:
    grouped: dict[int, dict[int, object]] = {}
    for record in records:
        step = int(getattr(record, step_attribute))
        cell = int(record.cell_index)
        if cell in grouped.setdefault(step, {}):
            raise P1PressurePhaseRelationshipError(
                f"duplicate cell record at step={step}, cell={cell}"
            )
        grouped[step][cell] = record
    expected_indices = set(range(n_cells))
    output: dict[int, tuple[object, ...]] = {}
    for step in expected_steps:
        actual = set(grouped.get(step, {}))
        if actual != expected_indices:
            raise P1PressurePhaseRelationshipError(
                "incomplete cell history at step "
                f"{step}: missing={sorted(expected_indices-actual)}, "
                f"extra={sorted(actual-expected_indices)}"
            )
        output[step] = tuple(grouped[step][cell] for cell in range(n_cells))
    unexpected = set(grouped) - set(expected_steps)
    if unexpected:
        raise P1PressurePhaseRelationshipError(
            f"cell records exist for unexpected steps: {sorted(unexpected)}"
        )
    return output


def _build_snapshot_history(source: object) -> _SnapshotHistory:
    baseline = source.baseline
    pipeline = source.config.pipeline
    n_cells = pipeline.n_cells
    length_m = pipeline.length_m
    dx_m = length_m / n_cells
    cell_centers = (np.arange(n_cells, dtype=float) + 0.5) * dx_m
    distances = length_m - cell_centers

    baseline_times = np.asarray(baseline.time_history_s, dtype=float)
    baseline_pressures = np.asarray(baseline.pressure_history_pa, dtype=float)
    if baseline_times.ndim != 1:
        raise P1PressurePhaseRelationshipError("baseline time history must be 1-D")
    if baseline_pressures.shape != (baseline_times.size, n_cells):
        raise P1PressurePhaseRelationshipError(
            "baseline pressure history shape does not match time and mesh"
        )
    if baseline_times.size != baseline.step_count + 1:
        raise P1PressurePhaseRelationshipError(
            "baseline history must include the initial state plus every accepted step"
        )
    if not np.all(np.isfinite(baseline_times)) or not np.all(
        np.isfinite(baseline_pressures)
    ):
        raise P1PressurePhaseRelationshipError(
            "baseline time/pressure history contains nonfinite values"
        )

    baseline_steps = tuple(range(1, baseline.step_count + 1))
    baseline_cells = _group_exact_cell_records(
        baseline.cells,
        step_attribute="step_index",
        expected_steps=baseline_steps,
        n_cells=n_cells,
    )
    post_steps = tuple(
        int(step.post_crossing_step)
        for step in sorted(source.steps, key=lambda item: item.post_crossing_step)
    )
    post_cells = _group_exact_cell_records(
        source.cells,
        step_attribute="post_crossing_step",
        expected_steps=post_steps,
        n_cells=n_cells,
    )

    times: list[float] = [float(baseline_times[0])]
    segments: list[ArrivalSource] = ["PRE_CROSSING"]
    absolute_steps: list[int] = [0]
    pressure_rows: list[np.ndarray] = [baseline_pressures[0].copy()]
    sound_rows: list[np.ndarray] = [np.full(n_cells, np.nan, dtype=float)]
    region_rows: list[np.ndarray] = [
        np.full(n_cells, "LIQUID_CANDIDATE", dtype=object)
    ]
    transition_rows: list[np.ndarray] = [
        np.full(n_cells, "NO_TRANSITION", dtype=object)
    ]

    for step_index in baseline_steps:
        rows = baseline_cells[step_index]
        time_s = float(baseline_times[step_index])
        if any(
            not math.isclose(
                float(row.time_s), time_s, rel_tol=0.0, abs_tol=1.0e-15
            )
            for row in rows
        ):
            raise P1PressurePhaseRelationshipError(
                f"baseline cell time mismatch at step {step_index}"
            )
        times.append(time_s)
        segments.append(
            _source_segment(
                time_s=time_s,
                crossing_time_s=float(baseline.crossing_time_s),
                post_crossing=False,
            )
        )
        absolute_steps.append(step_index)
        pressure_rows.append(baseline_pressures[step_index].copy())
        sound_rows.append(
            np.asarray(
                [
                    np.nan
                    if row.sound_speed_post_m_s is None
                    else float(row.sound_speed_post_m_s)
                    for row in rows
                ],
                dtype=float,
            )
        )
        region_rows.append(
            np.asarray([str(row.post_region) for row in rows], dtype=object)
        )
        transition_rows.append(
            np.asarray([str(row.transition_event) for row in rows], dtype=object)
        )

    step_by_id = {int(step.post_crossing_step): step for step in source.steps}
    for post_step in post_steps:
        step = step_by_id[post_step]
        rows = post_cells[post_step]
        time_s = float(step.time_after_s)
        if any(
            not math.isclose(
                float(row.time_s), time_s, rel_tol=0.0, abs_tol=1.0e-15
            )
            for row in rows
        ):
            raise P1PressurePhaseRelationshipError(
                f"post-crossing cell time mismatch at step {post_step}"
            )
        times.append(time_s)
        segments.append("POST_CROSSING")
        absolute_steps.append(int(step.absolute_step))
        pressure_rows.append(
            np.asarray([float(row.pressure_pa) for row in rows], dtype=float)
        )
        sound_rows.append(
            np.asarray(
                [
                    np.nan
                    if row.sound_speed_m_s is None
                    else float(row.sound_speed_m_s)
                    for row in rows
                ],
                dtype=float,
            )
        )
        region_rows.append(
            np.asarray([str(row.post_region) for row in rows], dtype=object)
        )
        transition_rows.append(
            np.asarray([str(row.transition_event) for row in rows], dtype=object)
        )

    time_array = np.asarray(times, dtype=float)
    if not np.all(np.isfinite(time_array)) or np.any(np.diff(time_array) <= 0.0):
        raise P1PressurePhaseRelationshipError(
            "combined accepted history times must be finite and strictly increasing"
        )
    pressures = np.vstack(pressure_rows)
    sounds = np.vstack(sound_rows)
    regions = np.vstack(region_rows)
    transitions = np.vstack(transition_rows)
    if not np.all(np.isfinite(pressures)) or np.any(pressures <= 0.0):
        raise P1PressurePhaseRelationshipError(
            "combined pressure history must remain finite and positive"
        )
    supported = {"LIQUID_CANDIDATE", "OPEN_TWO_PHASE"}
    unexpected_regions = sorted(set(regions.ravel()) - supported)
    if unexpected_regions:
        raise P1PressurePhaseRelationshipError(
            f"unsupported accepted regions: {unexpected_regions}"
        )
    finite_sound = sounds[np.isfinite(sounds)]
    if finite_sound.size == 0 or np.any(finite_sound <= 0.0):
        raise P1PressurePhaseRelationshipError(
            "retained finite sound speeds must be positive"
        )
    return _SnapshotHistory(
        times_s=time_array,
        segments=tuple(segments),
        absolute_steps=tuple(absolute_steps),
        pressures_pa=pressures,
        sound_speeds_m_s=sounds,
        regions=regions,
        transition_events=transitions,
        cell_centers_m=cell_centers,
        distances_from_outlet_m=distances,
    )


def _arrival_index_for_threshold(
    history: _SnapshotHistory,
    *,
    initial_pressure_pa: float,
    threshold_relative: float,
    cell_index: int,
) -> int | None:
    relative_drop = (
        initial_pressure_pa - history.pressures_pa[:, cell_index]
    ) / initial_pressure_pa
    indices = np.flatnonzero(relative_drop >= threshold_relative)
    return None if indices.size == 0 else int(indices[0])


def _arrival_source(history: _SnapshotHistory, index: int | None) -> ArrivalSource:
    return "UNAVAILABLE" if index is None else history.segments[index]


def _sound_at(history: _SnapshotHistory, index: int | None, cell: int) -> float | None:
    if index is None:
        return None
    value = float(history.sound_speeds_m_s[index, cell])
    return value if math.isfinite(value) else None


def _first_and_persistent_open_indices(mask: np.ndarray) -> tuple[int | None, int | None]:
    active = np.flatnonzero(mask)
    if active.size == 0:
        return None, None
    first = int(active[0])
    persistent: int | None = None
    for index in active:
        candidate = int(index)
        retained_sample_count = mask.size - candidate
        if (
            retained_sample_count >= P1_A1_MIN_PERSISTENT_SAMPLES
            and bool(np.all(mask[candidate:]))
        ):
            persistent = candidate
            break
    return first, persistent


def _transition_counts(mask: np.ndarray) -> tuple[int, int]:
    previous = False
    opens = 0
    closes = 0
    for current in mask.astype(bool):
        if current and not previous:
            opens += 1
        elif previous and not current:
            closes += 1
        previous = bool(current)
    return opens, closes


def _build_cell_lags(
    source: object,
    history: _SnapshotHistory,
) -> tuple[P1CellLagRecord, ...]:
    pipeline = source.config.pipeline
    threshold = float(pipeline.pressure_drop_evidence_relative)
    crossing_time = float(source.baseline.crossing_time_s)
    output: list[P1CellLagRecord] = []
    for cell in range(pipeline.n_cells):
        pressure_index = _arrival_index_for_threshold(
            history,
            initial_pressure_pa=float(pipeline.initial_pressure_pa),
            threshold_relative=threshold,
            cell_index=cell,
        )
        open_mask = history.regions[:, cell] == "OPEN_TWO_PHASE"
        first_index, persistent_index = _first_and_persistent_open_indices(open_mask)
        opens, closes = _transition_counts(open_mask)
        pressure_time = (
            None if pressure_index is None else float(history.times_s[pressure_index])
        )
        first_time = (
            None if first_index is None else float(history.times_s[first_index])
        )
        persistent_time = (
            None
            if persistent_index is None
            else float(history.times_s[persistent_index])
        )
        first_lag = (
            None
            if pressure_time is None or first_time is None
            else first_time - pressure_time
        )
        persistent_lag = (
            None
            if pressure_time is None or persistent_time is None
            else persistent_time - pressure_time
        )
        first_order = (
            None
            if first_lag is None
            else first_lag >= -1.0e-15
        )
        persistent_order = (
            None
            if persistent_lag is None
            else persistent_lag >= -1.0e-15
        )
        output.append(
            P1CellLagRecord(
                case_id=source.baseline.case.case_id,
                model_id=P1_A1_MODEL_ID,
                cell_index=cell,
                cell_center_m=float(history.cell_centers_m[cell]),
                distance_from_outlet_m=float(
                    history.distances_from_outlet_m[cell]
                ),
                pressure_drop_threshold_relative=threshold,
                pressure_arrival_time_s=pressure_time,
                pressure_arrival_source=_arrival_source(history, pressure_index),
                sound_speed_at_pressure_arrival_m_s=_sound_at(
                    history, pressure_index, cell
                ),
                first_phase_onset_time_s=first_time,
                first_phase_onset_source=_arrival_source(history, first_index),
                sound_speed_at_first_phase_onset_m_s=_sound_at(
                    history, first_index, cell
                ),
                first_phase_lag_s=first_lag,
                persistent_phase_onset_time_s=persistent_time,
                persistent_phase_onset_source=_arrival_source(
                    history, persistent_index
                ),
                sound_speed_at_persistent_phase_onset_m_s=_sound_at(
                    history, persistent_index, cell
                ),
                persistent_phase_lag_s=persistent_lag,
                persistent_phase_sample_count=(
                    0 if persistent_index is None else history.times_s.size - persistent_index
                ),
                liquid_to_two_phase_transition_count=opens,
                two_phase_to_liquid_transition_count=closes,
                phase_toggled=opens > 1 or closes > 0,
                open_two_phase_at_final_horizon=bool(open_mask[-1]),
                first_onset_persistent_through_horizon=(
                    None
                    if first_index is None
                    else first_index == persistent_index
                ),
                pressure_arrived_before_or_at_first_phase=first_order,
                pressure_arrived_before_or_at_persistent_phase=persistent_order,
            )
        )
    # Crossing identity must remain visible in the combined history.
    crossing_cells = tuple(int(value) for value in source.baseline.crossing_cell_indices)
    for cell in crossing_cells:
        row = output[cell]
        if row.first_phase_onset_time_s is None or not math.isclose(
            row.first_phase_onset_time_s,
            crossing_time,
            rel_tol=0.0,
            abs_tol=1.0e-15,
        ):
            raise P1PressurePhaseRelationshipError(
                "combined history does not preserve the exact first-crossing identity"
            )
    return tuple(output)


def _build_threshold_sensitivity(
    source: object,
    history: _SnapshotHistory,
) -> tuple[P1ThresholdSensitivityRecord, ...]:
    pipeline = source.config.pipeline
    reference = float(pipeline.pressure_drop_evidence_relative)
    reference_indices = [
        _arrival_index_for_threshold(
            history,
            initial_pressure_pa=float(pipeline.initial_pressure_pa),
            threshold_relative=reference,
            cell_index=cell,
        )
        for cell in range(pipeline.n_cells)
    ]
    output: list[P1ThresholdSensitivityRecord] = []
    for multiplier in P1_A1_THRESHOLD_MULTIPLIERS:
        threshold = reference * multiplier
        for cell in range(pipeline.n_cells):
            index = _arrival_index_for_threshold(
                history,
                initial_pressure_pa=float(pipeline.initial_pressure_pa),
                threshold_relative=threshold,
                cell_index=cell,
            )
            reference_index = reference_indices[cell]
            time_s = None if index is None else float(history.times_s[index])
            reference_time = (
                None
                if reference_index is None
                else float(history.times_s[reference_index])
            )
            shift = (
                None
                if time_s is None or reference_time is None
                else time_s - reference_time
            )
            output.append(
                P1ThresholdSensitivityRecord(
                    case_id=source.baseline.case.case_id,
                    model_id=P1_A1_MODEL_ID,
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
                    arrival_time_s=time_s,
                    arrival_source=_arrival_source(history, index),
                    arrival_available=index is not None,
                    arrival_shift_from_reference_s=shift,
                )
            )
    return tuple(output)


def _front_events(
    *,
    kind: FrontKind,
    history: _SnapshotHistory,
    initial_pressure_pa: float,
    pressure_threshold_relative: float,
) -> list[tuple[int, float, float, float]]:
    """Return (cell, time, distance, local sound) advancement events."""

    events: list[tuple[int, float, float, float]] = []
    previous_distance = -math.inf
    for snapshot in range(history.times_s.size):
        if kind == "PRESSURE_FRONT":
            mask = (
                (initial_pressure_pa - history.pressures_pa[snapshot])
                / initial_pressure_pa
                >= pressure_threshold_relative
            )
        else:
            mask = history.regions[snapshot] == "OPEN_TWO_PHASE"
        active = np.flatnonzero(mask)
        if active.size == 0:
            continue
        distances = history.distances_from_outlet_m[active]
        local = int(np.argmax(distances))
        cell = int(active[local])
        distance = float(history.distances_from_outlet_m[cell])
        if distance <= previous_distance + 1.0e-15:
            continue
        sound = float(history.sound_speeds_m_s[snapshot, cell])
        if not math.isfinite(sound) or sound <= 0.0:
            raise P1PressurePhaseRelationshipError(
                f"{kind} event lacks a positive local sound speed"
            )
        events.append((cell, float(history.times_s[snapshot]), distance, sound))
        previous_distance = distance
    return events


def _speed_records_from_events(
    *,
    source: object,
    kind: FrontKind,
    events: Sequence[tuple[int, float, float, float]],
) -> list[P1FrontSpeedRecord]:
    output: list[P1FrontSpeedRecord] = []
    for event_index, (previous, current) in enumerate(
        zip(events, events[1:]), start=1
    ):
        from_cell, from_time, from_distance, _ = previous
        to_cell, to_time, to_distance, to_sound = current
        dt = to_time - from_time
        dx = to_distance - from_distance
        if not math.isfinite(dt) or not math.isfinite(dx) or dt <= 0.0 or dx <= 0.0:
            raise P1PressurePhaseRelationshipError(
                f"{kind} advancement events must increase in time and distance"
            )
        speed = dx / dt
        ratio = speed / to_sound
        output.append(
            P1FrontSpeedRecord(
                case_id=source.baseline.case.case_id,
                model_id=P1_A1_MODEL_ID,
                front_kind=kind,
                event_index=event_index,
                from_cell_index=from_cell,
                to_cell_index=to_cell,
                from_time_s=from_time,
                to_time_s=to_time,
                from_distance_from_outlet_m=from_distance,
                to_distance_from_outlet_m=to_distance,
                delta_time_s=dt,
                delta_distance_m=dx,
                discrete_segment_speed_m_s=speed,
                destination_local_sound_speed_m_s=to_sound,
                speed_to_local_sound_ratio=ratio,
                diagnostic_definition=(
                    "cell-center threshold advancement slope"
                    if kind == "PRESSURE_FRONT"
                    else "cell-center accepted OPEN_TWO_PHASE advancement slope"
                ),
            )
        )
    return output


def _build_front_speeds(
    source: object,
    history: _SnapshotHistory,
) -> tuple[P1FrontSpeedRecord, ...]:
    pipeline = source.config.pipeline
    pressure_events = _front_events(
        kind="PRESSURE_FRONT",
        history=history,
        initial_pressure_pa=float(pipeline.initial_pressure_pa),
        pressure_threshold_relative=float(
            pipeline.pressure_drop_evidence_relative
        ),
    )
    phase_events = _front_events(
        kind="PHASE_FRONT",
        history=history,
        initial_pressure_pa=float(pipeline.initial_pressure_pa),
        pressure_threshold_relative=float(
            pipeline.pressure_drop_evidence_relative
        ),
    )
    output = _speed_records_from_events(
        source=source,
        kind="PRESSURE_FRONT",
        events=pressure_events,
    )
    output.extend(
        _speed_records_from_events(
            source=source,
            kind="PHASE_FRONT",
            events=phase_events,
        )
    )
    return tuple(output)


def _front_history_series(
    source: object,
    history: _SnapshotHistory,
) -> tuple[
    tuple[float, ...],
    tuple[float | None, ...],
    tuple[float, ...],
    tuple[float | None, ...],
]:
    pipeline = source.config.pipeline
    pressure_positions: list[float | None] = []
    phase_positions: list[float | None] = []
    for snapshot in range(history.times_s.size):
        pressure_mask = (
            (float(pipeline.initial_pressure_pa) - history.pressures_pa[snapshot])
            / float(pipeline.initial_pressure_pa)
            >= float(pipeline.pressure_drop_evidence_relative)
        )
        phase_mask = history.regions[snapshot] == "OPEN_TWO_PHASE"
        pressure_active = np.flatnonzero(pressure_mask)
        phase_active = np.flatnonzero(phase_mask)
        pressure_positions.append(
            None
            if pressure_active.size == 0
            else float(
                np.max(history.distances_from_outlet_m[pressure_active])
            )
        )
        phase_positions.append(
            None
            if phase_active.size == 0
            else float(np.max(history.distances_from_outlet_m[phase_active]))
        )
    times = tuple(float(value) for value in history.times_s)
    return times, tuple(pressure_positions), times, tuple(phase_positions)


def _evaluate_gates(
    source: object,
    a0_analysis: object,
    history: _SnapshotHistory,
    cell_lags: tuple[P1CellLagRecord, ...],
    front_speeds: tuple[P1FrontSpeedRecord, ...],
    sensitivity: tuple[P1ThresholdSensitivityRecord, ...],
) -> tuple[P1A1GateRecord, ...]:
    pipeline = source.config.pipeline
    a0_ready = bool(getattr(a0_analysis, "analysis_ready", False))
    fixed_source = bool(
        source.outcome == "COMPLETED_FIXED_CHECKPOINTS"
        and len(source.steps) == source.config.maximum_post_crossing_steps
    )
    history_complete = bool(
        history.pressures_pa.shape
        == (history.times_s.size, pipeline.n_cells)
        and history.regions.shape == history.pressures_pa.shape
        and history.sound_speeds_m_s.shape == history.pressures_pa.shape
        and np.all(np.diff(history.times_s) > 0.0)
    )
    baseline_arrivals_match = True
    for cell, inherited in enumerate(source.baseline.pressure_drop_arrival_times_s):
        if inherited is None:
            continue
        observed = cell_lags[cell].pressure_arrival_time_s
        if observed is None or not math.isclose(
            observed, float(inherited), rel_tol=0.0, abs_tol=1.0e-15
        ):
            baseline_arrivals_match = False
            break
    lag_ordering = all(
        row.pressure_arrived_before_or_at_first_phase is not False
        and row.pressure_arrived_before_or_at_persistent_phase is not False
        for row in cell_lags
    )
    threshold_monotone = True
    by_cell: dict[int, dict[float, float | None]] = {}
    for row in sensitivity:
        by_cell.setdefault(row.cell_index, {})[
            row.threshold_multiplier
        ] = row.arrival_time_s
    for arrivals in by_cell.values():
        ordered = [arrivals[m] for m in P1_A1_THRESHOLD_MULTIPLIERS]
        available = [value for value in ordered if value is not None]
        if any(
            later < earlier - 1.0e-15
            for earlier, later in zip(available, available[1:])
        ):
            threshold_monotone = False
            break
    speed_finite = bool(
        front_speeds
        and all(
            row.delta_time_s > 0.0
            and row.delta_distance_m > 0.0
            and math.isfinite(row.discrete_segment_speed_m_s)
            and row.discrete_segment_speed_m_s > 0.0
            and math.isfinite(row.destination_local_sound_speed_m_s)
            and row.destination_local_sound_speed_m_s > 0.0
            and math.isfinite(row.speed_to_local_sound_ratio)
            and row.speed_to_local_sound_ratio > 0.0
            for row in front_speeds
        )
        and {row.front_kind for row in front_speeds}
        == {"PRESSURE_FRONT", "PHASE_FRONT"}
    )
    cell_values_finite = all(
        all(
            _finite_optional(value)
            for value in (
                row.pressure_arrival_time_s,
                row.sound_speed_at_pressure_arrival_m_s,
                row.first_phase_onset_time_s,
                row.sound_speed_at_first_phase_onset_m_s,
                row.first_phase_lag_s,
                row.persistent_phase_onset_time_s,
                row.sound_speed_at_persistent_phase_onset_m_s,
                row.persistent_phase_lag_s,
            )
        )
        for row in cell_lags
    )
    evidence_keys = bool(
        source.last_valid_state_sha256
        and getattr(a0_analysis, "analysis_sha256", "")
    )
    return (
        P1A1GateRecord(
            "SOURCE_A0_ANALYSIS_READY",
            a0_ready,
            "P1-A0 must be ANALYSIS_READY before relationship analysis.",
        ),
        P1A1GateRecord(
            "SOURCE_FIXED_64_STEP_COMPLETION",
            fixed_source,
            "The inherited Gate 6 fixed continuation must complete all 64 steps.",
        ),
        P1A1GateRecord(
            "COMBINED_HISTORY_COMPLETE_AND_ORDERED",
            history_complete,
            (
                "Initial, pre-crossing, crossing, and post-crossing histories "
                "are complete and strictly ordered."
            ),
        ),
        P1A1GateRecord(
            "REFERENCE_PRESSURE_ARRIVALS_MATCH_A0_SOURCE",
            baseline_arrivals_match,
            (
                "Inherited pre-crossing 1e-6 arrival times match the "
                "combined-history derivation exactly."
            ),
        ),
        P1A1GateRecord(
            "PRESSURE_PRECEDES_ACCEPTED_PHASE_ONSET",
            lag_ordering,
            (
                "No accepted phase onset precedes the inherited pressure-drop "
                "arrival at the same cell."
            ),
        ),
        P1A1GateRecord(
            "THRESHOLD_ARRIVAL_ORDERING_MONOTONE",
            threshold_monotone,
            (
                "Higher predeclared pressure-drop thresholds do not arrive "
                "earlier than lower thresholds."
            ),
        ),
        P1A1GateRecord(
            "DISCRETE_FRONT_SPEED_RECORDS_FINITE",
            speed_finite,
            "Pressure and phase advancement slopes are finite, positive diagnostic records.",
        ),
        P1A1GateRecord(
            "CELL_RELATIONSHIP_VALUES_FINITE",
            cell_values_finite,
            "All available pressure-arrival, onset, lag, and local acoustic values are finite.",
        ),
        P1A1GateRecord(
            "DETERMINISTIC_EVIDENCE_KEYS_PRESENT",
            evidence_keys,
            "Gate 6 and P1-A0 source hashes are present.",
        ),
    )


def analyze_pressure_phase_relationship(
    source: object,
    a0_analysis: object | None = None,
) -> P1PressurePhaseRelationshipResult:
    """Derive P1-A1 relationship metrics without changing the physical solve."""

    if a0_analysis is None:
        a0_analysis = analyze_post_crossing_propagation(source)
    history = _build_snapshot_history(source)
    cell_lags = _build_cell_lags(source, history)
    sensitivity = _build_threshold_sensitivity(source, history)
    front_speeds = _build_front_speeds(source, history)
    (
        pressure_times,
        pressure_positions,
        phase_times,
        phase_positions,
    ) = _front_history_series(source, history)
    gates = _evaluate_gates(
        source,
        a0_analysis,
        history,
        cell_lags,
        front_speeds,
        sensitivity,
    )
    warnings: list[str] = [
        "DISCRETE_FRONT_SPEED_NOT_PHYSICALLY_VALIDATED",
        "PRESSURE_THRESHOLD_SENSITIVITY_IS_DIAGNOSTIC_NOT_TUNING",
        "HEM_EQUILIBRIUM_BASELINE_DOES_NOT_MODEL_FLASHING_DELAY",
    ]
    for gate in gates:
        if not gate.passed:
            warnings.append(f"FAILED_GATE:{gate.gate}")
    for row in cell_lags:
        if row.phase_toggled:
            warnings.append(f"PHASE_TOGGLE_OBSERVED:cell={row.cell_index}")
    status: RelationshipExecutionStatus = (
        "RELATIONSHIP_READY"
        if all(gate.passed for gate in gates)
        else "FAIL_CLOSED"
    )
    digest_payload = {
        "schema_version": P1_A1_SCHEMA_VERSION,
        "model_id": P1_A1_MODEL_ID,
        "case_id": source.baseline.case.case_id,
        "source_outcome": source.outcome,
        "source_last_valid_state_sha256": source.last_valid_state_sha256,
        "source_a0_analysis_sha256": a0_analysis.analysis_sha256,
        "pressure_drop_threshold_relative": (
            source.config.pipeline.pressure_drop_evidence_relative
        ),
        "threshold_multipliers": P1_A1_THRESHOLD_MULTIPLIERS,
        "minimum_persistent_phase_samples": P1_A1_MIN_PERSISTENT_SAMPLES,
        "cell_lags": [asdict(row) for row in cell_lags],
        "front_speeds": [asdict(row) for row in front_speeds],
        "threshold_sensitivity": [asdict(row) for row in sensitivity],
        "pressure_front_history_time_s": pressure_times,
        "pressure_front_history_distance_m": pressure_positions,
        "phase_front_history_time_s": phase_times,
        "phase_front_history_distance_m": phase_positions,
        "gates": [asdict(gate) for gate in gates],
        "warnings": warnings,
        "relationship_execution_status": status,
        "formal_status": P1_A1_FORMAL_STATUS,
    }
    relationship_sha256 = _canonical_json_sha256(digest_payload)
    return P1PressurePhaseRelationshipResult(
        schema_version=P1_A1_SCHEMA_VERSION,
        model_id=P1_A1_MODEL_ID,
        case_id=source.baseline.case.case_id,
        source_outcome=source.outcome,
        source_last_valid_state_sha256=source.last_valid_state_sha256,
        source_a0_analysis_sha256=a0_analysis.analysis_sha256,
        pressure_drop_threshold_relative=float(
            source.config.pipeline.pressure_drop_evidence_relative
        ),
        threshold_multipliers=P1_A1_THRESHOLD_MULTIPLIERS,
        cell_lags=cell_lags,
        front_speeds=front_speeds,
        threshold_sensitivity=sensitivity,
        pressure_front_history_time_s=pressure_times,
        pressure_front_history_distance_m=pressure_positions,
        phase_front_history_time_s=phase_times,
        phase_front_history_distance_m=phase_positions,
        gates=gates,
        warnings=tuple(warnings),
        relationship_execution_status=status,
        relationship_sha256=relationship_sha256,
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


def _plot_front_relationship(
    path: Path,
    result: P1PressurePhaseRelationshipResult,
) -> None:
    crossing_candidates = [
        row.first_phase_onset_time_s
        for row in result.cell_lags
        if row.first_phase_onset_source == "CROSSING"
        and row.first_phase_onset_time_s is not None
    ]
    origin = min(crossing_candidates) if crossing_candidates else 0.0
    pressure_time_ms = (
        np.asarray(result.pressure_front_history_time_s) - origin
    ) * 1.0e3
    phase_time_ms = (
        np.asarray(result.phase_front_history_time_s) - origin
    ) * 1.0e3
    pressure_distance = np.asarray(
        [np.nan if value is None else value for value in result.pressure_front_history_distance_m]
    )
    phase_distance = np.asarray(
        [np.nan if value is None else value for value in result.phase_front_history_distance_m]
    )
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(pressure_time_ms, pressure_distance, label="Pressure front (1e-6)")
    ax.plot(phase_time_ms, phase_distance, label="Accepted phase front")
    ax.set_xlabel("Time relative to first crossing [ms]")
    ax.set_ylabel("Distance from outlet [m]")
    ax.set_title("P1-A1 pressure-front / phase-front relationship")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_cell_lag(path: Path, result: P1PressurePhaseRelationshipResult) -> None:
    distance = np.asarray([row.distance_from_outlet_m for row in result.cell_lags])
    first_lag_ms = np.asarray(
        [
            np.nan if row.first_phase_lag_s is None else row.first_phase_lag_s * 1.0e3
            for row in result.cell_lags
        ]
    )
    persistent_lag_ms = np.asarray(
        [
            np.nan
            if row.persistent_phase_lag_s is None
            else row.persistent_phase_lag_s * 1.0e3
            for row in result.cell_lags
        ]
    )
    order = np.argsort(distance)
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(distance[order], first_lag_ms[order], marker="o", label="First accepted onset lag")
    ax.plot(
        distance[order],
        persistent_lag_ms[order],
        marker="s",
        label="Persistent-through-horizon onset lag",
    )
    ax.set_xlabel("Distance from outlet [m]")
    ax.set_ylabel("Pressure-arrival to phase-onset lag [ms]")
    ax.set_title("P1-A1 cellwise pressure-to-phase lag")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _operator_report(result: P1PressurePhaseRelationshipResult) -> str:
    summary = result.summary()
    first = summary["first_phase_lag_summary_s"]
    persistent = summary["persistent_phase_lag_summary_s"]
    pressure_speed = summary["pressure_front_speed_summary_m_s"]
    phase_speed = summary["phase_front_speed_summary_m_s"]
    toggles = summary["phase_toggle_cell_indices"]
    return "\n".join(
        [
            "# P1-A1 Pressure-to-Phase Relationship Report",
            "",
            f"- case: `{result.case_id}`",
            f"- model: `{result.model_id}`",
            f"- execution status: `{result.relationship_execution_status}`",
            (
                "- inherited pressure threshold: "
                f"`{result.pressure_drop_threshold_relative:.6g}` relative"
            ),
            f"- cells with a first accepted phase onset: `{summary['phase_onset_cell_count']}`",
            (
                "- cells persistent through the observed horizon: "
                f"`{summary['persistent_phase_onset_cell_count']}`"
            ),
            f"- cells with accepted phase toggles: `{toggles}`",
            "",
            "## Bounded observations",
            "",
            (
                "- first-onset lag [s], min/median/max: "
                f"`{first['minimum']}` / `{first['median']}` / "
                f"`{first['maximum']}`"
            ),
            (
                "- persistent-onset lag [s], min/median/max: "
                f"`{persistent['minimum']}` / `{persistent['median']}` / "
                f"`{persistent['maximum']}`"
            ),
            (
                "- discrete pressure-front slope [m/s], min/median/max: "
                f"`{pressure_speed['minimum']}` / "
                f"`{pressure_speed['median']}` / "
                f"`{pressure_speed['maximum']}`"
            ),
            (
                "- discrete phase-front slope [m/s], min/median/max: "
                f"`{phase_speed['minimum']}` / `{phase_speed['median']}` / "
                f"`{phase_speed['maximum']}`"
            ),
            "",
            "## Interpretation boundary",
            "",
            (
                "The pressure and phase slopes are discrete cell-center event "
                "slopes. They are not a physical wave-speed or boiling-front "
                "validation. HEM assumes instantaneous equilibrium and therefore "
                "cannot establish a real nucleation or flashing delay. The "
                "one-decade pressure-threshold envelope is a diagnostic "
                "sensitivity check, not threshold calibration."
            ),
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


def write_pressure_phase_relationship_artifacts(
    output_dir: str | Path,
    result: P1PressurePhaseRelationshipResult,
) -> dict[str, Path]:
    """Write the exact P1-A1 eight-file relationship bundle."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P1_A1_OUTPUT_FILES)
    existing = {path.name for path in target.iterdir() if path.is_file()}
    unexpected = existing - expected
    if unexpected:
        raise P1PressurePhaseRelationshipError(
            f"output directory contains files outside the A1 contract: {sorted(unexpected)}"
        )
    paths = {
        "relationship_summary": target / "relationship_summary.json",
        "cell_lag": target / "cell_lag.csv",
        "front_speed": target / "front_speed.csv",
        "threshold_sensitivity": target / "threshold_sensitivity.csv",
        "front_relationship": target / "front_relationship.png",
        "cell_phase_lag": target / "cell_phase_lag.png",
        "operator_report": target / "operator_report.md",
        "relationship_manifest": target / "relationship_manifest.json",
    }
    paths["relationship_summary"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_dataclass_csv(paths["cell_lag"], result.cell_lags, P1CellLagRecord)
    _write_dataclass_csv(
        paths["front_speed"], result.front_speeds, P1FrontSpeedRecord
    )
    _write_dataclass_csv(
        paths["threshold_sensitivity"],
        result.threshold_sensitivity,
        P1ThresholdSensitivityRecord,
    )
    _plot_front_relationship(paths["front_relationship"], result)
    _plot_cell_lag(paths["cell_phase_lag"], result)
    paths["operator_report"].write_text(
        _operator_report(result), encoding="utf-8"
    )
    payload_files: dict[str, dict[str, object]] = {}
    for key, path in paths.items():
        if key == "relationship_manifest":
            continue
        payload_files[path.name] = {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    manifest = {
        "schema_version": P1_A1_SCHEMA_VERSION,
        "artifact_contract": "stage7_p1_pressure_phase_relationship_exactly_8_files",
        "declared_file_count": len(P1_A1_OUTPUT_FILES),
        "declared_file_names": list(P1_A1_OUTPUT_FILES),
        "case_id": result.case_id,
        "model_id": result.model_id,
        "relationship_execution_status": result.relationship_execution_status,
        "relationship_sha256": result.relationship_sha256,
        "source_a0_analysis_sha256": result.source_a0_analysis_sha256,
        "source_last_valid_state_sha256": result.source_last_valid_state_sha256,
        "payload_files": payload_files,
        "physics_or_numerics_changed": False,
        "formal_status": dict(P1_A1_FORMAL_STATUS),
    }
    paths["relationship_manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P1PressurePhaseRelationshipError(
            f"A1 output contract mismatch: expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    source = run_post_crossing_propagation_review()
    a0_analysis = analyze_post_crossing_propagation(source)
    result = analyze_pressure_phase_relationship(source, a0_analysis)
    paths = write_pressure_phase_relationship_artifacts(output_dir, result)
    summary = result.summary()
    summary["artifact_paths"] = {key: str(path) for key, path in paths.items()}
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage 7 P1-A1 pressure-arrival / phase-onset relationship "
            "analysis without changing the physical solve."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["relationship_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
