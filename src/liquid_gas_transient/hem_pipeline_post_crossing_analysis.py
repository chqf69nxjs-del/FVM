"""Non-invasive P1 analysis layer for the fixed Stage 7 HEM continuation.

This module consumes the existing Gate 6 ``PostCrossingPropagationResult`` and
turns it into a compact analysis contract for pressure-wave / flashing studies.
It does not change the solver, EOS, boundary model, phase classifier, quality
projection, Rusanov flux, CFL, mesh, crossing threshold, or any tolerance.

The output is intentionally model-neutral enough to be reused by the planned
P2 HNE / relaxation comparison.  ``ANALYSIS_READY`` means only that the bounded
analysis contract was populated and its software gates passed.  It is not a
claim of Verification, Acceptance, Physical Validation, design-use acceptance,
or production approval.
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

from .hem_pipeline_post_crossing_propagation import (
    PostCrossingPropagationResult,
    run_post_crossing_propagation_review,
)

P1_SCHEMA_VERSION = "stage7_p1_post_crossing_analysis_a0_v1"
P1_MODEL_ID = "HEM_EQUILIBRIUM"
P1_OUTPUT_FILES = (
    "analysis_summary.json",
    "front_history.csv",
    "pressure_arrival.csv",
    "analysis_manifest.json",
)
P1_FORMAL_STATUS = {
    "implemented": True,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

AnalysisExecutionStatus = Literal["ANALYSIS_READY", "FAIL_CLOSED"]


class P1PostCrossingAnalysisError(RuntimeError):
    """Raised when source evidence cannot be analyzed without ambiguity."""


@dataclass(frozen=True)
class P1AnalysisGateRecord:
    """One explicit software/evidence gate for the P1 analysis layer."""

    gate: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class P1FrontHistoryRecord:
    """Decision-relevant front and inventory metrics for one accepted step."""

    case_id: str
    model_id: str
    absolute_step: int
    post_crossing_step: int
    time_s: float
    pressure_drop_threshold_relative: float
    pressure_front_reached_cell_count: int
    pressure_front_cell_index: int | None
    pressure_front_cell_center_m: float | None
    pressure_front_distance_from_outlet_m: float | None
    pressure_front_region: str
    pressure_front_sound_speed_m_s: float | None
    phase_front_cell_index: int | None
    phase_front_cell_center_m: float | None
    phase_front_distance_from_outlet_m: float | None
    phase_front_region: str
    phase_front_sound_speed_m_s: float | None
    open_two_phase_cell_count: int
    phase_region_occupied_length_m: float
    phase_region_span_m: float
    phase_region_contiguous: bool
    pressure_phase_front_separation_m: float | None
    pressure_front_ahead_of_phase_front: bool | None
    pressure_min_pa: float
    pressure_max_pa: float
    maximum_equilibrium_quality: float
    integrated_equilibrium_quality: float
    maximum_void_fraction: float
    vapor_mass_total_kg: float
    liquid_sound_speed_min_m_s: float | None
    liquid_sound_speed_max_m_s: float | None
    two_phase_sound_speed_min_m_s: float | None
    two_phase_sound_speed_max_m_s: float | None
    boundary_mass_residual_kg: float
    boundary_momentum_residual_kg_m_s: float
    boundary_energy_residual_J: float
    phase_vapor_residual_kg: float
    state_sha256: str


@dataclass(frozen=True)
class P1PressureArrivalRecord:
    """Existing first-pressure-drop arrival evidence in a stable table."""

    case_id: str
    model_id: str
    cell_index: int
    cell_center_m: float
    distance_from_outlet_m: float
    pressure_drop_threshold_relative: float
    arrival_time_s: float | None
    arrival_available: bool
    arrived_before_first_crossing: bool | None
    lead_time_to_first_crossing_s: float | None


@dataclass(frozen=True)
class P1PostCrossingAnalysisResult:
    """Bounded P1 analysis result derived from authoritative Gate 6 evidence."""

    schema_version: str
    model_id: str
    case_id: str
    source_outcome: str
    source_step_count: int
    source_last_valid_state_sha256: str
    source_summary_sha256: str
    first_crossing_step: int | None
    first_crossing_time_s: float | None
    first_crossing_cell_indices: tuple[int, ...]
    first_crossing_distances_from_outlet_m: tuple[float, ...]
    pressure_drop_threshold_relative: float
    front_history: tuple[P1FrontHistoryRecord, ...]
    pressure_arrivals: tuple[P1PressureArrivalRecord, ...]
    gates: tuple[P1AnalysisGateRecord, ...]
    warnings: tuple[str, ...]
    analysis_execution_status: AnalysisExecutionStatus
    analysis_sha256: str

    @property
    def analysis_ready(self) -> bool:
        return self.analysis_execution_status == "ANALYSIS_READY"

    def summary(self) -> dict[str, object]:
        final = self.front_history[-1] if self.front_history else None
        gate_map = {gate.gate: gate.passed for gate in self.gates}
        return {
            "schema_version": self.schema_version,
            "scope": "bounded_post_crossing_analysis_only",
            "model_id": self.model_id,
            "case_id": self.case_id,
            "source_outcome": self.source_outcome,
            "source_step_count": self.source_step_count,
            "source_last_valid_state_sha256": self.source_last_valid_state_sha256,
            "source_summary_sha256": self.source_summary_sha256,
            "first_crossing_step": self.first_crossing_step,
            "first_crossing_time_s": self.first_crossing_time_s,
            "first_crossing_cell_indices": list(self.first_crossing_cell_indices),
            "first_crossing_distances_from_outlet_m": list(
                self.first_crossing_distances_from_outlet_m
            ),
            "pressure_drop_threshold_relative": (
                self.pressure_drop_threshold_relative
            ),
            "front_history_record_count": len(self.front_history),
            "pressure_arrival_record_count": len(self.pressure_arrivals),
            "analysis_execution_status": self.analysis_execution_status,
            "analysis_ready": self.analysis_ready,
            "gate_results": gate_map,
            "gates": [asdict(gate) for gate in self.gates],
            "warnings": list(self.warnings),
            "final_front_state": (
                None
                if final is None
                else {
                    "post_crossing_step": final.post_crossing_step,
                    "time_s": final.time_s,
                    "pressure_front_distance_from_outlet_m": (
                        final.pressure_front_distance_from_outlet_m
                    ),
                    "phase_front_distance_from_outlet_m": (
                        final.phase_front_distance_from_outlet_m
                    ),
                    "pressure_phase_front_separation_m": (
                        final.pressure_phase_front_separation_m
                    ),
                    "open_two_phase_cell_count": (
                        final.open_two_phase_cell_count
                    ),
                    "phase_region_occupied_length_m": (
                        final.phase_region_occupied_length_m
                    ),
                    "phase_region_span_m": final.phase_region_span_m,
                    "maximum_equilibrium_quality": (
                        final.maximum_equilibrium_quality
                    ),
                    "maximum_void_fraction": final.maximum_void_fraction,
                    "vapor_mass_total_kg": final.vapor_mass_total_kg,
                    "state_sha256": final.state_sha256,
                }
            ),
            "analysis_sha256": self.analysis_sha256,
            "output_contract": list(P1_OUTPUT_FILES),
            "model_comparison_interface": {
                "model_id": self.model_id,
                "future_model_id": "HNE_RELAXATION",
                "shared_front_history_schema": True,
                "shared_pressure_arrival_schema": True,
            },
            "physics_or_numerics_changed": False,
            "formal_status": dict(P1_FORMAL_STATUS),
        }


def _canonical_json_sha256(payload: object) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _is_finite_optional(value: float | None) -> bool:
    return value is None or math.isfinite(value)


def _budget_limit(total: float, relative: float, absolute: float) -> float:
    return max(absolute, relative * abs(total))


def _group_cells_by_step(
    result: PostCrossingPropagationResult,
) -> dict[int, dict[int, object]]:
    n_cells = result.config.pipeline.n_cells
    expected_indices = set(range(n_cells))
    grouped: dict[int, dict[int, object]] = {}
    for cell in result.cells:
        step_cells = grouped.setdefault(cell.post_crossing_step, {})
        if cell.cell_index in step_cells:
            raise P1PostCrossingAnalysisError(
                "duplicate cell evidence for post-crossing step "
                f"{cell.post_crossing_step}, cell {cell.cell_index}"
            )
        step_cells[cell.cell_index] = cell

    step_ids = [step.post_crossing_step for step in result.steps]
    if len(step_ids) != len(set(step_ids)):
        raise P1PostCrossingAnalysisError(
            "duplicate post-crossing step records in source evidence"
        )
    unexpected_steps = set(grouped) - set(step_ids)
    if unexpected_steps:
        raise P1PostCrossingAnalysisError(
            "cell evidence exists without a matching step record: "
            f"{sorted(unexpected_steps)}"
        )
    for step_id in step_ids:
        actual = set(grouped.get(step_id, {}))
        if actual != expected_indices:
            missing = sorted(expected_indices - actual)
            extra = sorted(actual - expected_indices)
            raise P1PostCrossingAnalysisError(
                "incomplete cell history at post-crossing step "
                f"{step_id}: missing={missing}, extra={extra}"
            )
    return grouped


def _select_furthest_upstream(cells: Sequence[object]) -> object | None:
    if not cells:
        return None
    return max(
        cells,
        key=lambda cell: (cell.distance_from_outlet_m, -cell.cell_index),
    )


def _phase_region_metrics(
    open_indices: tuple[int, ...],
    dx_m: float,
) -> tuple[float, float, bool]:
    if not open_indices:
        return 0.0, 0.0, True
    occupied = len(open_indices) * dx_m
    span = (max(open_indices) - min(open_indices) + 1) * dx_m
    contiguous = open_indices == tuple(
        range(min(open_indices), max(open_indices) + 1)
    )
    return occupied, span, contiguous


def _build_pressure_arrivals(
    result: PostCrossingPropagationResult,
) -> tuple[P1PressureArrivalRecord, ...]:
    pipeline = result.config.pipeline
    arrivals = tuple(result.baseline.pressure_drop_arrival_times_s)
    if len(arrivals) != pipeline.n_cells:
        raise P1PostCrossingAnalysisError(
            "pressure arrival evidence length does not match the fixed mesh"
        )
    dx_m = pipeline.length_m / pipeline.n_cells
    crossing_time = result.baseline.crossing_time_s
    records: list[P1PressureArrivalRecord] = []
    for cell_index, arrival in enumerate(arrivals):
        if arrival is not None and not math.isfinite(arrival):
            raise P1PostCrossingAnalysisError(
                f"nonfinite pressure arrival time for cell {cell_index}"
            )
        cell_center = (cell_index + 0.5) * dx_m
        distance = pipeline.length_m - cell_center
        before: bool | None = None
        lead: float | None = None
        if arrival is not None and crossing_time is not None:
            before = arrival <= crossing_time
            lead = crossing_time - arrival
        records.append(
            P1PressureArrivalRecord(
                case_id=result.baseline.case.case_id,
                model_id=P1_MODEL_ID,
                cell_index=cell_index,
                cell_center_m=cell_center,
                distance_from_outlet_m=distance,
                pressure_drop_threshold_relative=(
                    pipeline.pressure_drop_evidence_relative
                ),
                arrival_time_s=arrival,
                arrival_available=arrival is not None,
                arrived_before_first_crossing=before,
                lead_time_to_first_crossing_s=lead,
            )
        )
    return tuple(records)


def _build_front_history(
    result: PostCrossingPropagationResult,
    grouped_cells: dict[int, dict[int, object]],
) -> tuple[P1FrontHistoryRecord, ...]:
    pipeline = result.config.pipeline
    dx_m = pipeline.length_m / pipeline.n_cells
    threshold = pipeline.pressure_drop_evidence_relative
    records: list[P1FrontHistoryRecord] = []

    for step in sorted(result.steps, key=lambda item: item.post_crossing_step):
        cells = tuple(
            grouped_cells[step.post_crossing_step][index]
            for index in range(pipeline.n_cells)
        )
        if any(cell.absolute_step != step.absolute_step for cell in cells):
            raise P1PostCrossingAnalysisError(
                f"absolute-step mismatch at post-crossing step {step.post_crossing_step}"
            )
        if any(
            not math.isclose(cell.time_s, step.time_after_s, rel_tol=0.0, abs_tol=0.0)
            for cell in cells
        ):
            raise P1PostCrossingAnalysisError(
                f"time mismatch at post-crossing step {step.post_crossing_step}"
            )

        open_cells = tuple(
            cell for cell in cells if cell.post_region == "OPEN_TWO_PHASE"
        )
        open_indices = tuple(cell.cell_index for cell in open_cells)
        if open_indices != tuple(step.open_two_phase_cell_indices):
            raise P1PostCrossingAnalysisError(
                "derived phase-region indices disagree with source step evidence at "
                f"post-crossing step {step.post_crossing_step}"
            )
        if len(open_indices) != step.open_two_phase_cell_count:
            raise P1PostCrossingAnalysisError(
                "derived phase-region count disagrees with source step evidence at "
                f"post-crossing step {step.post_crossing_step}"
            )

        pressure_cells = tuple(
            cell
            for cell in cells
            if (
                pipeline.initial_pressure_pa - cell.pressure_pa
            )
            / pipeline.initial_pressure_pa
            >= threshold
        )
        pressure_front = _select_furthest_upstream(pressure_cells)
        phase_front = _select_furthest_upstream(open_cells)
        occupied, span, contiguous = _phase_region_metrics(open_indices, dx_m)

        if phase_front is None:
            if step.furthest_upstream_two_phase_cell is not None:
                raise P1PostCrossingAnalysisError(
                    "source reports a phase front while no open two-phase cell exists"
                )
        else:
            if phase_front.cell_index != step.furthest_upstream_two_phase_cell:
                raise P1PostCrossingAnalysisError(
                    "derived phase-front cell disagrees with source step evidence at "
                    f"post-crossing step {step.post_crossing_step}"
                )
            if not math.isclose(
                phase_front.distance_from_outlet_m,
                step.furthest_upstream_distance_from_outlet_m,
                rel_tol=0.0,
                abs_tol=1.0e-15,
            ):
                raise P1PostCrossingAnalysisError(
                    "derived phase-front position disagrees with source step evidence at "
                    f"post-crossing step {step.post_crossing_step}"
                )

        separation: float | None = None
        pressure_ahead: bool | None = None
        if pressure_front is not None and phase_front is not None:
            separation = (
                pressure_front.distance_from_outlet_m
                - phase_front.distance_from_outlet_m
            )
            pressure_ahead = separation >= -1.0e-15

        records.append(
            P1FrontHistoryRecord(
                case_id=result.baseline.case.case_id,
                model_id=P1_MODEL_ID,
                absolute_step=step.absolute_step,
                post_crossing_step=step.post_crossing_step,
                time_s=step.time_after_s,
                pressure_drop_threshold_relative=threshold,
                pressure_front_reached_cell_count=len(pressure_cells),
                pressure_front_cell_index=(
                    None if pressure_front is None else pressure_front.cell_index
                ),
                pressure_front_cell_center_m=(
                    None if pressure_front is None else pressure_front.cell_center_m
                ),
                pressure_front_distance_from_outlet_m=(
                    None
                    if pressure_front is None
                    else pressure_front.distance_from_outlet_m
                ),
                pressure_front_region=(
                    "" if pressure_front is None else pressure_front.post_region
                ),
                pressure_front_sound_speed_m_s=(
                    None if pressure_front is None else pressure_front.sound_speed_m_s
                ),
                phase_front_cell_index=(
                    None if phase_front is None else phase_front.cell_index
                ),
                phase_front_cell_center_m=(
                    None if phase_front is None else phase_front.cell_center_m
                ),
                phase_front_distance_from_outlet_m=(
                    None if phase_front is None else phase_front.distance_from_outlet_m
                ),
                phase_front_region=(
                    "" if phase_front is None else phase_front.post_region
                ),
                phase_front_sound_speed_m_s=(
                    None if phase_front is None else phase_front.sound_speed_m_s
                ),
                open_two_phase_cell_count=len(open_indices),
                phase_region_occupied_length_m=occupied,
                phase_region_span_m=span,
                phase_region_contiguous=contiguous,
                pressure_phase_front_separation_m=separation,
                pressure_front_ahead_of_phase_front=pressure_ahead,
                pressure_min_pa=step.pressure_min_pa,
                pressure_max_pa=step.pressure_max_pa,
                maximum_equilibrium_quality=step.maximum_equilibrium_quality,
                integrated_equilibrium_quality=(
                    step.integrated_equilibrium_quality
                ),
                maximum_void_fraction=step.maximum_void_fraction,
                vapor_mass_total_kg=step.vapor_mass_total_kg,
                liquid_sound_speed_min_m_s=step.liquid_sound_speed_min_m_s,
                liquid_sound_speed_max_m_s=step.liquid_sound_speed_max_m_s,
                two_phase_sound_speed_min_m_s=(
                    step.two_phase_sound_speed_min_m_s
                ),
                two_phase_sound_speed_max_m_s=(
                    step.two_phase_sound_speed_max_m_s
                ),
                boundary_mass_residual_kg=step.boundary_mass_residual_kg,
                boundary_momentum_residual_kg_m_s=(
                    step.boundary_momentum_residual_kg_m_s
                ),
                boundary_energy_residual_J=step.boundary_energy_residual_J,
                phase_vapor_residual_kg=step.phase_vapor_residual_kg,
                state_sha256=step.state_sha256,
            )
        )
    return tuple(records)


def _evaluate_gates(
    result: PostCrossingPropagationResult,
    front_history: tuple[P1FrontHistoryRecord, ...],
    pressure_arrivals: tuple[P1PressureArrivalRecord, ...],
) -> tuple[P1AnalysisGateRecord, ...]:
    pipeline = result.config.pipeline
    all_cells = tuple(result.cells)
    all_steps = tuple(result.steps)

    source_baseline_exact = bool(
        result.summary().get("baseline_reproduced_exactly", False)
    )
    fixed_completion = bool(
        result.outcome == "COMPLETED_FIXED_CHECKPOINTS"
        and len(all_steps) == result.config.maximum_post_crossing_steps
        and len(front_history) == result.config.maximum_post_crossing_steps
    )
    structural_complete = bool(
        len(all_cells) == len(all_steps) * pipeline.n_cells
        and len(pressure_arrivals) == pipeline.n_cells
    )

    finite_step_values = all(
        all(
            math.isfinite(value)
            for value in (
                step.time_before_s,
                step.dt_s,
                step.time_after_s,
                step.maximum_equilibrium_quality,
                step.integrated_equilibrium_quality,
                step.maximum_void_fraction,
                step.pressure_min_pa,
                step.pressure_max_pa,
                step.mass_total_kg,
                step.momentum_total_kg_m_s,
                step.energy_total_J,
                step.vapor_mass_total_kg,
                step.boundary_mass_residual_kg,
                step.boundary_momentum_residual_kg_m_s,
                step.boundary_energy_residual_J,
                step.phase_vapor_residual_kg,
            )
        )
        and all(
            _is_finite_optional(value)
            for value in (
                step.liquid_sound_speed_min_m_s,
                step.liquid_sound_speed_max_m_s,
                step.two_phase_sound_speed_min_m_s,
                step.two_phase_sound_speed_max_m_s,
            )
        )
        for step in all_steps
    )
    finite_cell_values = all(
        all(
            math.isfinite(value)
            for value in (
                cell.rho_kg_m3,
                cell.pressure_pa,
                cell.temperature_K,
                cell.q_equilibrium,
                cell.q_post,
                cell.void_fraction,
            )
        )
        and _is_finite_optional(cell.sound_speed_m_s)
        for cell in all_cells
    )
    finite_core = finite_step_values and finite_cell_values

    quality_tolerance = pipeline.accepted_state_quality_tolerance
    phase_bounds = all(
        cell.rho_kg_m3 > 0.0
        and cell.pressure_pa > 0.0
        and cell.temperature_K > 0.0
        and -quality_tolerance <= cell.q_equilibrium <= 1.0 + quality_tolerance
        and -quality_tolerance <= cell.q_post <= 1.0 + quality_tolerance
        and -quality_tolerance <= cell.void_fraction <= 1.0 + quality_tolerance
        for cell in all_cells
    )
    acoustic_available = all(
        cell.sound_speed_status == "SUCCESS"
        and cell.sound_speed_m_s is not None
        and math.isfinite(cell.sound_speed_m_s)
        and cell.sound_speed_m_s > 0.0
        for cell in all_cells
    )

    mass_budget = all(
        abs(step.boundary_mass_residual_kg)
        <= _budget_limit(
            step.mass_total_kg,
            pipeline.mass_budget_relative_tolerance,
            pipeline.mass_budget_absolute_tolerance_kg,
        )
        for step in all_steps
    )
    momentum_budget = all(
        abs(step.boundary_momentum_residual_kg_m_s)
        <= _budget_limit(
            step.momentum_total_kg_m_s,
            pipeline.momentum_budget_relative_tolerance,
            pipeline.momentum_budget_absolute_tolerance_kg_m_s,
        )
        for step in all_steps
    )
    energy_budget = all(
        abs(step.boundary_energy_residual_J)
        <= _budget_limit(
            step.energy_total_J,
            pipeline.energy_budget_relative_tolerance,
            pipeline.energy_budget_absolute_tolerance_J,
        )
        for step in all_steps
    )
    vapor_budget = all(
        abs(step.phase_vapor_residual_kg)
        <= pipeline.vapor_budget_absolute_tolerance_kg
        for step in all_steps
    )
    pressure_front_available = bool(
        front_history
        and all(
            record.pressure_front_distance_from_outlet_m is not None
            for record in front_history
        )
    )
    phase_front_available = bool(
        front_history
        and all(
            record.phase_front_distance_from_outlet_m is not None
            for record in front_history
        )
    )
    evidence_keys_present = bool(
        result.last_valid_state_sha256
        and result.baseline.final_state_sha256
        and result.baseline.run_signature_sha256
        and all(record.state_sha256 for record in front_history)
    )

    return (
        P1AnalysisGateRecord(
            "SOURCE_BASELINE_EXACT",
            source_baseline_exact,
            "Gate 6 summary retains exact first-crossing replay evidence.",
        ),
        P1AnalysisGateRecord(
            "SOURCE_FIXED_64_STEP_COMPLETION",
            fixed_completion,
            "The bounded P1 slice requires all fixed +1..+64 accepted steps.",
        ),
        P1AnalysisGateRecord(
            "STRUCTURAL_HISTORY_COMPLETE",
            structural_complete,
            "Every accepted step has one complete fixed-mesh cell history.",
        ),
        P1AnalysisGateRecord(
            "FINITE_CORE_OUTPUTS",
            finite_core,
            "Core thermodynamic, front, acoustic, inventory, and budget values are finite.",
        ),
        P1AnalysisGateRecord(
            "POSITIVITY_AND_PHASE_FRACTION_BOUNDS",
            phase_bounds,
            "Density, pressure, and temperature are positive; q and alpha remain bounded.",
        ),
        P1AnalysisGateRecord(
            "LOCAL_ACOUSTIC_OUTPUT_AVAILABLE",
            acoustic_available,
            "Each accepted cell retains a positive successful equilibrium sound speed.",
        ),
        P1AnalysisGateRecord(
            "MASS_MOMENTUM_ENERGY_BUDGETS",
            mass_budget and momentum_budget and energy_budget,
            "Source cumulative residuals remain within the existing fixed tolerances.",
        ),
        P1AnalysisGateRecord(
            "VAPOR_BUDGET",
            vapor_budget,
            "Source vapor residual remains within the existing fixed absolute tolerance.",
        ),
        P1AnalysisGateRecord(
            "PRESSURE_FRONT_AVAILABLE",
            pressure_front_available,
            "The existing 1e-6 relative pressure-drop threshold locates a front at every step.",
        ),
        P1AnalysisGateRecord(
            "PHASE_FRONT_AVAILABLE",
            phase_front_available,
            "At least one accepted open two-phase cell locates the flashing front at every step.",
        ),
        P1AnalysisGateRecord(
            "DETERMINISTIC_EVIDENCE_KEYS_PRESENT",
            evidence_keys_present,
            "Source and accepted states retain stable SHA-256 evidence keys.",
        ),
    )


def analyze_post_crossing_propagation(
    result: PostCrossingPropagationResult,
) -> P1PostCrossingAnalysisResult:
    """Derive P1 analysis metrics without changing the authoritative solve."""

    grouped = _group_cells_by_step(result)
    front_history = _build_front_history(result, grouped)
    pressure_arrivals = _build_pressure_arrivals(result)
    gates = _evaluate_gates(result, front_history, pressure_arrivals)

    warnings: list[str] = []
    for gate in gates:
        if not gate.passed:
            warnings.append(f"FAILED_GATE:{gate.gate}")
    for record in front_history:
        if not record.phase_region_contiguous:
            warnings.append(
                "NONCONTIGUOUS_TWO_PHASE_REGION:"
                f"post_crossing_step={record.post_crossing_step}"
            )
    if result.failure_category:
        warnings.append(f"SOURCE_FAILURE_CATEGORY:{result.failure_category}")
    if result.failure_reason:
        warnings.append(f"SOURCE_FAILURE_REASON:{result.failure_reason}")

    status: AnalysisExecutionStatus = (
        "ANALYSIS_READY" if all(gate.passed for gate in gates) else "FAIL_CLOSED"
    )
    source_summary_sha256 = _canonical_json_sha256(result.summary())
    digest_payload = {
        "schema_version": P1_SCHEMA_VERSION,
        "model_id": P1_MODEL_ID,
        "case_id": result.baseline.case.case_id,
        "source_outcome": result.outcome,
        "source_step_count": len(result.steps),
        "source_last_valid_state_sha256": result.last_valid_state_sha256,
        "source_summary_sha256": source_summary_sha256,
        "front_history": [asdict(record) for record in front_history],
        "pressure_arrivals": [asdict(record) for record in pressure_arrivals],
        "gates": [asdict(gate) for gate in gates],
        "warnings": warnings,
        "analysis_execution_status": status,
        "formal_status": P1_FORMAL_STATUS,
    }
    analysis_sha256 = _canonical_json_sha256(digest_payload)

    return P1PostCrossingAnalysisResult(
        schema_version=P1_SCHEMA_VERSION,
        model_id=P1_MODEL_ID,
        case_id=result.baseline.case.case_id,
        source_outcome=result.outcome,
        source_step_count=len(result.steps),
        source_last_valid_state_sha256=result.last_valid_state_sha256,
        source_summary_sha256=source_summary_sha256,
        first_crossing_step=result.baseline.crossing_step,
        first_crossing_time_s=result.baseline.crossing_time_s,
        first_crossing_cell_indices=tuple(result.baseline.crossing_cell_indices),
        first_crossing_distances_from_outlet_m=tuple(
            result.baseline.crossing_distances_from_outlet_m
        ),
        pressure_drop_threshold_relative=(
            result.config.pipeline.pressure_drop_evidence_relative
        ),
        front_history=front_history,
        pressure_arrivals=pressure_arrivals,
        gates=gates,
        warnings=tuple(warnings),
        analysis_execution_status=status,
        analysis_sha256=analysis_sha256,
    )


def _write_dataclass_csv(path: Path, rows: Sequence[object], row_type: type) -> None:
    field_names = [item.name for item in fields(row_type)]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=field_names)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_p1_post_crossing_analysis_artifacts(
    output_dir: str | Path,
    analysis: P1PostCrossingAnalysisResult,
) -> dict[str, Path]:
    """Write exactly four P1 analysis files, separate from Gate 6 evidence."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(P1_OUTPUT_FILES)
    unexpected_existing = {
        path.name
        for path in target.iterdir()
        if path.is_file() and path.name not in expected
    }
    if unexpected_existing:
        raise P1PostCrossingAnalysisError(
            "P1 output directory contains files outside the exact contract: "
            f"{sorted(unexpected_existing)}"
        )

    paths = {
        "analysis_summary": target / "analysis_summary.json",
        "front_history": target / "front_history.csv",
        "pressure_arrival": target / "pressure_arrival.csv",
        "analysis_manifest": target / "analysis_manifest.json",
    }
    paths["analysis_summary"].write_text(
        json.dumps(analysis.summary(), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    _write_dataclass_csv(
        paths["front_history"],
        analysis.front_history,
        P1FrontHistoryRecord,
    )
    _write_dataclass_csv(
        paths["pressure_arrival"],
        analysis.pressure_arrivals,
        P1PressureArrivalRecord,
    )

    payload_files = {}
    for key in ("analysis_summary", "front_history", "pressure_arrival"):
        path = paths[key]
        payload_files[path.name] = {
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
    manifest = {
        "schema_version": P1_SCHEMA_VERSION,
        "artifact_contract": "stage7_p1_post_crossing_analysis_exactly_4_files",
        "declared_file_count": len(P1_OUTPUT_FILES),
        "declared_file_names": list(P1_OUTPUT_FILES),
        "case_id": analysis.case_id,
        "model_id": analysis.model_id,
        "analysis_execution_status": analysis.analysis_execution_status,
        "analysis_sha256": analysis.analysis_sha256,
        "source_summary_sha256": analysis.source_summary_sha256,
        "source_last_valid_state_sha256": (
            analysis.source_last_valid_state_sha256
        ),
        "payload_files": payload_files,
        "physics_or_numerics_changed": False,
        "formal_status": dict(P1_FORMAL_STATUS),
    }
    paths["analysis_manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != expected:
        raise P1PostCrossingAnalysisError(
            "P1 output contract mismatch: "
            f"expected={sorted(expected)}, actual={sorted(actual)}"
        )
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    source = run_post_crossing_propagation_review()
    analysis = analyze_post_crossing_propagation(source)
    paths = write_p1_post_crossing_analysis_artifacts(output_dir, analysis)
    summary = analysis.summary()
    summary["artifact_paths"] = {name: str(path) for name, path in paths.items()}
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the non-invasive Stage 7 P1 post-crossing pressure-wave / "
            "flashing analysis slice."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = execute(args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["analysis_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
