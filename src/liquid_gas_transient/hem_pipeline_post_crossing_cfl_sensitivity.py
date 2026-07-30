"""Verification-only Gate 8 increment for CFL 0.10 and 0.05.

The locked Gate 8 sequence remains 0.10 / 0.05 / 0.025.  This increment first
replays the authoritative Gate 6 CFL=0.10 path and requires its complete
identity.  Only after that exact replay passes does it execute the independent
CFL=0.05 column from the fixed all-liquid initial state.  CFL=0.025 and all
cross-CFL interpretation remain pending.

This module changes no production solver, flux, boundary, phase classifier,
sound-speed formula, quality projection, threshold, or tolerance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .boundary import LinearPressureRamp, ReflectiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .hem_liquid_to_two_phase_crossing import detect_raw_transition_events
from .hem_mixed_liquid_open_two_phase_eos import VerificationHEMLiquidOpenTwoPhaseEOS
from .hem_pipeline_depressurization_boundary import (
    VerificationHEMPrescribedSubcooledOutletBoundary,
    VerificationHEMPrescribedSubcooledStateProvider,
)
from .hem_pipeline_depressurization_first_crossing import (
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    _incremental_boundary_budget,
    _state_sha256,
    _validate_cumulative_budgets,
    run_pipeline_depressurization_case,
)
from .hem_pipeline_post_crossing_propagation import (
    BASELINE_CASE_ID,
    PostCrossingStepRecord,
    _baseline_case_spec,
    _baseline_regions,
    _classify_raw_state,
    _failure_category,
    _git_provenance,
    _project_and_accept,
    _raw_case,
    _require_exact_baseline,
    run_post_crossing_propagation_review,
)
from .phase_budget import PhaseChangeBudgetTracker
from .solver import FvmSolver
from .state import internal_energy, inventory, vapor_mass_fraction

GATE8_CFL_SEQUENCE: tuple[float, ...] = (0.10, 0.05, 0.025)
IMPLEMENTED_CFL_COLUMNS: tuple[float, ...] = (0.10, 0.05)
PENDING_CFL_COLUMNS: tuple[float, ...] = (0.025,)
FIRST_CROSSING_STEP_CAPS = {0.10: 2000, 0.05: 4000, 0.025: 8000}
POST_CROSSING_STEP_CAPS = {0.10: 128, 0.05: 256, 0.025: 512}
PHYSICAL_CHECKPOINTS_S: tuple[tuple[str, float], ...] = (
    ("T1", 6.016940923599307e-6),
    ("T2", 2.402911232474538e-5),
    ("T3", 9.544429181626145e-5),
    ("T4", 3.696527559334590e-4),
)
GATE6_REFERENCE_POST_STEPS = {"T1": 1, "T2": 4, "T3": 16, "T4": 64}
FOCUS_CELLS = (29, 30, 31)
CHATTER_CELL = 30
EXPECTED_GATE6_FINAL_TIME_S = 1.1695853254669838e-3
EXPECTED_GATE6_FINAL_STATE_SHA256 = (
    "62bbaf5d7014af258180fe29622324a2228a0c5eec507ef10eb6b9f3e411d440"
)
EXPECTED_GATE6_CELL30_REGION_CHANGES = 49

APPROVAL_BOUNDARY = {
    "Gate_8_execution_complete": False,
    "post_crossing_CFL_sensitivity_characterized": False,
    "CFL_independent_post_crossing_verified": False,
    "mesh_independent_post_crossing_verified": False,
    "post_crossing_propagation_approved": False,
    "phase_chatter_root_cause_approved": False,
    "chatter_mitigation_authorized": False,
    "near_saturation_acoustic_continuity_approved": False,
    "two_phase_acoustic_accuracy_band_approved": False,
    "Gate_P2_passed": False,
    "physical_validation": False,
    "design_use_acceptance": False,
    "production_hem_activation_approved": False,
}


class HEMGate8CflSensitivityError(RuntimeError):
    """Raised when the locked increment cannot proceed safely."""


@dataclass(frozen=True)
class HEMGate8PipelineConfig(HEMPipelineDepressurizationConfig):
    """Fixed PR #77 configuration with only CFL and its step cap variable."""

    cfl: float = 0.10
    max_steps: int = 2000

    def __post_init__(self) -> None:
        if isinstance(self.cfl, bool) or float(self.cfl) not in GATE8_CFL_SEQUENCE:
            raise ValueError(f"Gate 8 CFL must be one of {GATE8_CFL_SEQUENCE}")
        value = float(self.cfl)
        if self.max_steps != FIRST_CROSSING_STEP_CAPS[value]:
            raise ValueError(
                f"Gate 8 max_steps is fixed at {FIRST_CROSSING_STEP_CAPS[value]} "
                f"for CFL={value}"
            )
        fixed = HEMPipelineDepressurizationConfig()
        for item in fields(HEMPipelineDepressurizationConfig):
            if item.name in {"cfl", "max_steps"}:
                continue
            actual = getattr(self, item.name)
            expected = getattr(fixed, item.name)
            if actual != expected:
                raise ValueError(
                    f"Gate 8 may not change {item.name}: "
                    f"expected {expected!r}, received {actual!r}"
                )

    @classmethod
    def for_cfl(cls, cfl: float) -> "HEMGate8PipelineConfig":
        if isinstance(cfl, bool):
            raise ValueError(f"Gate 8 CFL must be one of {GATE8_CFL_SEQUENCE}")
        value = float(cfl)
        if value not in FIRST_CROSSING_STEP_CAPS:
            raise ValueError(f"Gate 8 CFL must be one of {GATE8_CFL_SEQUENCE}")
        return cls(cfl=value, max_steps=FIRST_CROSSING_STEP_CAPS[value])


@dataclass(frozen=True)
class Gate8CheckpointRecord:
    cfl: float
    checkpoint: str
    target_elapsed_s: float
    reached: bool
    status: str
    actual_elapsed_s: float | None
    overshoot_s: float | None
    local_dt_s: float | None
    absolute_step: int | None
    post_crossing_step: int | None
    open_two_phase_cell_count: int | None
    open_two_phase_cell_indices: tuple[int, ...]
    furthest_upstream_distance_from_outlet_m: float | None
    front_displacement_m: float | None
    average_front_speed_m_s: float | None
    maximum_equilibrium_quality: float | None
    maximum_void_fraction: float | None
    vapor_mass_total_kg: float | None
    pressure_min_pa: float | None
    pressure_max_pa: float | None
    boundary_mass_residual_kg: float | None
    boundary_momentum_residual_kg_m_s: float | None
    boundary_energy_residual_J: float | None
    phase_vapor_residual_kg: float | None
    accepted_state_sha256: str


@dataclass(frozen=True)
class Gate8FocusedCellRecord:
    cfl: float
    absolute_step: int
    post_crossing_step: int
    elapsed_s: float
    dt_s: float
    cell_index: int
    previous_region: str
    raw_region: str
    post_region: str
    transition_event: str
    pressure_pa: float
    temperature_K: float
    q_equilibrium: float
    q_post: float
    void_fraction: float
    sound_speed_m_s: float
    projection_applied: bool
    delta_rho_q: float
    accepted_state_sha256: str


@dataclass(frozen=True)
class Gate8ColumnResult:
    cfl: float
    config: HEMGate8PipelineConfig
    baseline: PipelineCaseResult
    continuation_outcome: str
    failure_category: str
    failure_reason: str
    steps: tuple[PostCrossingStepRecord, ...]
    focused_cells: tuple[Gate8FocusedCellRecord, ...]
    checkpoints: tuple[Gate8CheckpointRecord, ...]
    region_toggle_counts: tuple[int, ...]
    last_valid_state_sha256: str

    def summary(self) -> dict[str, object]:
        elapsed = (
            self.steps[-1].time_after_s - self.baseline.crossing_time_s
            if self.steps and self.baseline.crossing_time_s is not None
            else None
        )
        cell30_changes = self.region_toggle_counts[CHATTER_CELL]
        return {
            "cfl": self.cfl,
            "first_crossing": self.baseline.summary(),
            "continuation_outcome": self.continuation_outcome,
            "failure_category": self.failure_category,
            "failure_reason": self.failure_reason,
            "successful_post_crossing_step_count": len(self.steps),
            "final_post_crossing_elapsed_s": elapsed,
            "reached_checkpoints": [
                row.checkpoint for row in self.checkpoints if row.reached
            ],
            "region_toggle_counts": list(self.region_toggle_counts),
            "cell30_region_changes": cell30_changes,
            "cell30_region_changes_per_1e-4_s": (
                None if elapsed is None or elapsed <= 0.0
                else cell30_changes * 1.0e-4 / elapsed
            ),
            "last_valid_state_sha256": self.last_valid_state_sha256,
        }


@dataclass(frozen=True)
class Gate8IncrementResult:
    columns: tuple[Gate8ColumnResult, ...]
    provenance: Mapping[str, object]

    def summary(self) -> dict[str, object]:
        by_cfl = {column.cfl: column for column in self.columns}
        return {
            "schema_version": "stage7_gate8_cfl_0p10_0p05_increment_v1",
            "scope": "verification_only",
            "case_id": BASELINE_CASE_ID,
            "mesh_cells": 32,
            "locked_full_cfl_sequence": list(GATE8_CFL_SEQUENCE),
            "implemented_cfl_columns": list(IMPLEMENTED_CFL_COLUMNS),
            "pending_cfl_columns": list(PENDING_CFL_COLUMNS),
            "physical_checkpoints_s": dict(PHYSICAL_CHECKPOINTS_S),
            "gate6_identity_reproduced_exactly": _gate6_identity_matches(
                by_cfl[0.10]
            ),
            "full_gate8_sequence_executed": False,
            "cross_cfl_interpretation_authorized": False,
            "cross_cfl_classifications": [],
            "columns": [column.summary() for column in self.columns],
            "provenance": dict(self.provenance),
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "boundary_changed": False,
            "phase_classifier_changed": False,
            "sound_speed_formula_changed": False,
            "quality_projection_changed": False,
            "threshold_or_tolerance_tuned": False,
            **APPROVAL_BOUNDARY,
        }


def _first_crossing_distance(baseline: PipelineCaseResult) -> float | None:
    if not baseline.crossing_distances_from_outlet_m:
        return None
    return float(min(baseline.crossing_distances_from_outlet_m))


def _blank_checkpoint(
    cfl: float,
    name: str,
    target: float,
    status: str,
    state_sha256: str,
) -> Gate8CheckpointRecord:
    return Gate8CheckpointRecord(
        cfl=cfl,
        checkpoint=name,
        target_elapsed_s=target,
        reached=False,
        status=status,
        actual_elapsed_s=None,
        overshoot_s=None,
        local_dt_s=None,
        absolute_step=None,
        post_crossing_step=None,
        open_two_phase_cell_count=None,
        open_two_phase_cell_indices=(),
        furthest_upstream_distance_from_outlet_m=None,
        front_displacement_m=None,
        average_front_speed_m_s=None,
        maximum_equilibrium_quality=None,
        maximum_void_fraction=None,
        vapor_mass_total_kg=None,
        pressure_min_pa=None,
        pressure_max_pa=None,
        boundary_mass_residual_kg=None,
        boundary_momentum_residual_kg_m_s=None,
        boundary_energy_residual_J=None,
        phase_vapor_residual_kg=None,
        accepted_state_sha256=state_sha256,
    )


def _checkpoint_from_step(
    *,
    cfl: float,
    name: str,
    target: float,
    baseline: PipelineCaseResult,
    step: PostCrossingStepRecord,
) -> Gate8CheckpointRecord:
    if baseline.crossing_time_s is None:
        raise HEMGate8CflSensitivityError("accepted crossing time is missing")
    actual = float(step.time_after_s - baseline.crossing_time_s)
    overshoot = float(actual - target)
    if actual < target:
        raise HEMGate8CflSensitivityError(
            f"checkpoint {name} selected before target: {actual} < {target}"
        )
    if overshoot > step.dt_s:
        raise HEMGate8CflSensitivityError(
            f"checkpoint {name} overshoot exceeds one local dt: "
            f"{overshoot} > {step.dt_s}"
        )
    crossing_distance = _first_crossing_distance(baseline)
    front_distance = step.furthest_upstream_distance_from_outlet_m
    displacement = (
        None
        if crossing_distance is None or front_distance is None
        else front_distance - crossing_distance
    )
    speed = (
        None if displacement is None or actual <= 0.0 else displacement / actual
    )
    return Gate8CheckpointRecord(
        cfl=cfl,
        checkpoint=name,
        target_elapsed_s=target,
        reached=True,
        status="REACHED_FIRST_ACCEPTED_STATE_AT_OR_AFTER_TARGET",
        actual_elapsed_s=actual,
        overshoot_s=overshoot,
        local_dt_s=step.dt_s,
        absolute_step=step.absolute_step,
        post_crossing_step=step.post_crossing_step,
        open_two_phase_cell_count=step.open_two_phase_cell_count,
        open_two_phase_cell_indices=step.open_two_phase_cell_indices,
        furthest_upstream_distance_from_outlet_m=front_distance,
        front_displacement_m=displacement,
        average_front_speed_m_s=speed,
        maximum_equilibrium_quality=step.maximum_equilibrium_quality,
        maximum_void_fraction=step.maximum_void_fraction,
        vapor_mass_total_kg=step.vapor_mass_total_kg,
        pressure_min_pa=step.pressure_min_pa,
        pressure_max_pa=step.pressure_max_pa,
        boundary_mass_residual_kg=step.boundary_mass_residual_kg,
        boundary_momentum_residual_kg_m_s=(
            step.boundary_momentum_residual_kg_m_s
        ),
        boundary_energy_residual_J=step.boundary_energy_residual_J,
        phase_vapor_residual_kg=step.phase_vapor_residual_kg,
        accepted_state_sha256=step.state_sha256,
    )


def _focus_from_gate6(column_cfl: float, gate6) -> tuple[Gate8FocusedCellRecord, ...]:
    if gate6.baseline.crossing_time_s is None:
        return ()
    step_by_index = {step.post_crossing_step: step for step in gate6.steps}
    rows: list[Gate8FocusedCellRecord] = []
    for cell in gate6.cells:
        if cell.cell_index not in FOCUS_CELLS:
            continue
        step = step_by_index[cell.post_crossing_step]
        if cell.sound_speed_m_s is None:
            raise HEMGate8CflSensitivityError(
                "Gate 6 focused cell lacks accepted sound-speed evidence"
            )
        rows.append(
            Gate8FocusedCellRecord(
                cfl=column_cfl,
                absolute_step=cell.absolute_step,
                post_crossing_step=cell.post_crossing_step,
                elapsed_s=cell.time_s - gate6.baseline.crossing_time_s,
                dt_s=step.dt_s,
                cell_index=cell.cell_index,
                previous_region=cell.previous_region,
                raw_region=cell.raw_region,
                post_region=cell.post_region,
                transition_event=cell.transition_event,
                pressure_pa=cell.pressure_pa,
                temperature_K=cell.temperature_K,
                q_equilibrium=cell.q_equilibrium,
                q_post=cell.q_post,
                void_fraction=cell.void_fraction,
                sound_speed_m_s=cell.sound_speed_m_s,
                projection_applied=cell.projection_applied,
                delta_rho_q=cell.delta_rho_q,
                accepted_state_sha256=step.state_sha256,
            )
        )
    return tuple(rows)


def _gate6_identity_matches(column: Gate8ColumnResult) -> bool:
    if column.cfl != 0.10 or column.continuation_outcome != "COMPLETED_FIXED_CHECKPOINTS":
        return False
    if len(column.steps) != 64 or not column.steps:
        return False
    if column.steps[-1].time_after_s != EXPECTED_GATE6_FINAL_TIME_S:
        return False
    if column.last_valid_state_sha256 != EXPECTED_GATE6_FINAL_STATE_SHA256:
        return False
    if column.region_toggle_counts[CHATTER_CELL] != EXPECTED_GATE6_CELL30_REGION_CHANGES:
        return False
    reached = {
        row.checkpoint: row.post_crossing_step
        for row in column.checkpoints
        if row.reached
    }
    return reached == GATE6_REFERENCE_POST_STEPS


def _require_gate6_identity(column: Gate8ColumnResult) -> None:
    if not _gate6_identity_matches(column):
        raise HEMGate8CflSensitivityError(
            "CFL 0.10 did not reproduce the complete Gate 6 identity; "
            "CFL 0.05 execution is prohibited"
        )


def _run_gate6_column() -> Gate8ColumnResult:
    gate6 = run_post_crossing_propagation_review()
    _require_exact_baseline(gate6.baseline)
    if gate6.outcome != "COMPLETED_FIXED_CHECKPOINTS" or len(gate6.steps) != 64:
        raise HEMGate8CflSensitivityError(
            "authoritative Gate 6 replay did not complete the fixed 64 steps"
        )
    by_step = {step.post_crossing_step: step for step in gate6.steps}
    checkpoints = tuple(
        _checkpoint_from_step(
            cfl=0.10,
            name=name,
            target=target,
            baseline=gate6.baseline,
            step=by_step[GATE6_REFERENCE_POST_STEPS[name]],
        )
        for name, target in PHYSICAL_CHECKPOINTS_S
    )
    result = Gate8ColumnResult(
        cfl=0.10,
        config=HEMGate8PipelineConfig.for_cfl(0.10),
        baseline=gate6.baseline,
        continuation_outcome=gate6.outcome,
        failure_category=gate6.failure_category,
        failure_reason=gate6.failure_reason,
        steps=gate6.steps,
        focused_cells=_focus_from_gate6(0.10, gate6),
        checkpoints=checkpoints,
        region_toggle_counts=gate6.region_toggle_counts,
        last_valid_state_sha256=gate6.last_valid_state_sha256,
    )
    _require_gate6_identity(result)
    return result


def _run_refined_column(cfl: float) -> Gate8ColumnResult:
    if cfl == 0.10:
        raise ValueError("CFL 0.10 must use the authoritative Gate 6 replay")
    config = HEMGate8PipelineConfig.for_cfl(cfl)
    case = _baseline_case_spec()
    baseline = run_pipeline_depressurization_case(case, config)
    zero_toggles = tuple(0 for _ in range(config.n_cells))
    if baseline.outcome != "ACCEPTED_FIRST_CROSSING":
        status = f"NO_CONTINUATION__{baseline.outcome}"
        return Gate8ColumnResult(
            cfl=cfl,
            config=config,
            baseline=baseline,
            continuation_outcome="NOT_STARTED_NO_ACCEPTED_FIRST_CROSSING",
            failure_category=baseline.outcome,
            failure_reason=baseline.failure_reason,
            steps=(),
            focused_cells=(),
            checkpoints=tuple(
                _blank_checkpoint(cfl, name, target, status, baseline.final_state_sha256)
                for name, target in PHYSICAL_CHECKPOINTS_S
            ),
            region_toggle_counts=zero_toggles,
            last_valid_state_sha256=baseline.final_state_sha256,
        )
    if baseline.crossing_time_s is None:
        raise HEMGate8CflSensitivityError("accepted first crossing lacks time")

    crossing_U = np.array(baseline.accepted_state_history[-1], dtype=float, copy=True)
    schedule = LinearPressureRamp(
        p_initial_pa=config.initial_pressure_pa,
        p_final_pa=case.final_boundary_pressure_pa,
        t_start_s=0.0,
        duration_s=baseline.ramp_duration_s,
    )
    provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=config.subcooling_K,
        phase_config=config.phase_config,
    )
    right_boundary = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    grid = UniformGrid(
        PipeGeometry(length_m=config.length_m, diameter_m=config.diameter_m),
        n_cells=config.n_cells,
    )
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=config.accepted_state_quality_tolerance,
        phase_config=config.phase_config,
        quality_sync_config=config.projection_config,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=crossing_U,
        cfl=config.cfl,
        n_ghost=config.n_ghost,
        left_boundary=ReflectiveBoundary(),
        right_boundary=right_boundary,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=baseline.final_time_s,
        step_count=baseline.step_count,
    )
    initial_inventory = inventory(crossing_U, grid.dx, grid.geometry.area_m2)
    phase_tracker = PhaseChangeBudgetTracker(initial_inventory=initial_inventory)
    previous_regions = list(_baseline_regions(baseline))
    toggle_counts = [0] * config.n_cells
    steps: list[PostCrossingStepRecord] = []
    focused: list[Gate8FocusedCellRecord] = []
    checkpoints: dict[str, Gate8CheckpointRecord] = {}
    latest_projected_budget: dict[str, float] = {}
    outcome = "COMPLETED_FIXED_CHECKPOINTS"
    failure_category = ""
    failure_reason = ""
    last_hash = _state_sha256(solver.U)

    for post_step in range(1, POST_CROSSING_STEP_CAPS[cfl] + 1):
        try:
            time_before = float(solver.t)
            previous_U = np.array(solver.U, dtype=float, copy=True)
            previous_primitive = solver.primitive()
            previous_inventory = inventory(previous_U, grid.dx, grid.geometry.area_m2)
            if solver.boundary_budget is None:
                raise HEMGate8CflSensitivityError("boundary budget tracker is required")
            left_before = np.array(
                solver.boundary_budget.cumulative_left, dtype=float, copy=True
            )
            right_before = np.array(
                solver.boundary_budget.cumulative_right, dtype=float, copy=True
            )
            reverse_before = right_boundary.reverse_flow_fallback_count
            dt = float(solver.compute_dt())
            if not np.isfinite(dt) or dt <= 0.0:
                raise HEMGate8CflSensitivityError("dt must be finite and positive")
            solver.step(dt)
            raw_U = np.array(solver.U, dtype=float, copy=True)
            raw_inventory = inventory(raw_U, grid.dx, grid.geometry.area_m2)
            raw_budget = _incremental_boundary_budget(
                previous_inventory=previous_inventory,
                raw_inventory=raw_inventory,
                step_left=solver.boundary_budget.cumulative_left - left_before,
                step_right=solver.boundary_budget.cumulative_right - right_before,
                config=config,
            )
            if right_boundary.reverse_flow_fallback_count - reverse_before > 0:
                raise HEMGate8CflSensitivityError("reverse flow fallback was activated")
            detection = detect_raw_transition_events(
                previous_U, raw_U, phase_config=config.phase_config
            )
            raw_class = _classify_raw_state(detection)
            if raw_class not in {"OPEN_TWO_PHASE", "ALL_LIQUID"}:
                raise HEMGate8CflSensitivityError(
                    f"raw continuation entered {raw_class}"
                )
            boundary_state = right_boundary.last_state or provider.state_at(time_before)
            raw_case = _raw_case(
                case=case,
                config=config,
                grid=grid,
                previous_U=previous_U,
                raw_U=raw_U,
                previous_primitive=previous_primitive,
                detection=detection,
                boundary_state=boundary_state,
                dt=dt,
                raw_budget=raw_budget,
            )
            first, second, post_U, primitive, post_regions, projected_budget = (
                _project_and_accept(
                    raw_case=raw_case,
                    detection=detection,
                    config=config,
                )
            )
            latest_projected_budget = dict(projected_budget)
            phase_tracker.record_phase_change(
                U_before=raw_U,
                U_after=post_U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
                dt=dt,
            )
            solver.U = np.array(post_U, dtype=float, copy=True)
            boundary_diag, phase_diag = _validate_cumulative_budgets(
                solver=solver,
                phase_tracker=phase_tracker,
                initial_inventory=initial_inventory,
                latest_projected_budget=latest_projected_budget,
                config=config,
            )

            regions = np.asarray(post_regions).astype(str)
            raw_regions = np.asarray(detection.raw.region).astype(str)
            prior_regions = np.asarray(detection.previous.region).astype(str)
            events = np.asarray(detection.transitions.event).astype(str)
            q_eq = np.asarray(first.q_equilibrium, dtype=float)
            q_post = np.asarray(vapor_mass_fraction(post_U), dtype=float)
            alpha = np.asarray(primitive.alpha, dtype=float)
            pressure = np.asarray(primitive.p, dtype=float)
            temperature = np.asarray(primitive.T, dtype=float)
            sound = np.asarray(primitive.c, dtype=float)
            open_cells = tuple(
                int(index) for index in np.flatnonzero(regions == "OPEN_TWO_PHASE")
            )
            furthest = min(open_cells) if open_cells else None
            furthest_distance = (
                None
                if furthest is None
                else float(config.length_m - grid.cell_centers[furthest])
            )
            for index, region in enumerate(regions):
                if str(region) != previous_regions[index]:
                    toggle_counts[index] += 1
                previous_regions[index] = str(region)

            current_inventory = inventory(post_U, grid.dx, grid.geometry.area_m2)
            liquid_values = sound[regions == "LIQUID_CANDIDATE"]
            two_phase_values = sound[regions == "OPEN_TWO_PHASE"]
            state_hash = _state_sha256(post_U)
            record = PostCrossingStepRecord(
                case_id=case.case_id,
                absolute_step=int(solver.step_count),
                post_crossing_step=post_step,
                time_before_s=time_before,
                dt_s=dt,
                time_after_s=float(solver.t),
                raw_state_class=raw_class,
                accepted_state_class=(
                    "OPEN_TWO_PHASE_PRESENT" if open_cells else "ALL_LIQUID"
                ),
                open_two_phase_cell_count=len(open_cells),
                open_two_phase_cell_indices=open_cells,
                furthest_upstream_two_phase_cell=furthest,
                furthest_upstream_distance_from_outlet_m=furthest_distance,
                liquid_to_two_phase_event_count=int(
                    np.count_nonzero(events == "LIQUID_TO_TWO_PHASE_CROSSING")
                ),
                reverse_transition_event_count=int(
                    np.count_nonzero(events == "REVERSE_TRANSITION")
                ),
                projection_cell_count=int(np.count_nonzero(first.projection_applied)),
                second_projection_cell_count=int(
                    np.count_nonzero(second.projection_applied)
                ),
                maximum_equilibrium_quality=float(np.max(q_eq, initial=0.0)),
                integrated_equilibrium_quality=float(np.sum(q_eq) * grid.dx),
                maximum_void_fraction=float(np.max(alpha, initial=0.0)),
                pressure_min_pa=float(np.min(pressure)),
                pressure_max_pa=float(np.max(pressure)),
                liquid_sound_speed_min_m_s=(
                    float(np.min(liquid_values)) if liquid_values.size else None
                ),
                liquid_sound_speed_max_m_s=(
                    float(np.max(liquid_values)) if liquid_values.size else None
                ),
                two_phase_sound_speed_min_m_s=(
                    float(np.min(two_phase_values)) if two_phase_values.size else None
                ),
                two_phase_sound_speed_max_m_s=(
                    float(np.max(two_phase_values)) if two_phase_values.size else None
                ),
                mass_total_kg=float(current_inventory["mass_total"]),
                momentum_total_kg_m_s=float(current_inventory["momentum_total"]),
                energy_total_J=float(current_inventory["energy_total"]),
                vapor_mass_total_kg=float(current_inventory["vapor_mass_total"]),
                boundary_mass_residual_kg=float(
                    boundary_diag["budget_mass_residual"]
                ),
                boundary_momentum_residual_kg_m_s=float(
                    boundary_diag["budget_momentum_residual"]
                ),
                boundary_energy_residual_J=float(
                    boundary_diag["budget_energy_residual"]
                ),
                phase_vapor_residual_kg=float(
                    phase_diag["phase_vapor_mass_balance_residual_kg"]
                ),
                projection_vapor_source_step_kg=float(
                    projected_budget["projection_vapor_source_kg"]
                ),
                boundary_vapor_step_kg=float(
                    raw_budget["budget_vapor_mass_net_boundary"]
                ),
                second_projection_noop=bool(
                    not np.any(second.projection_applied)
                    and np.array_equal(second.U_after, post_U)
                ),
                state_sha256=state_hash,
            )
            steps.append(record)
            last_hash = state_hash

            for index in FOCUS_CELLS:
                focused.append(
                    Gate8FocusedCellRecord(
                        cfl=cfl,
                        absolute_step=record.absolute_step,
                        post_crossing_step=post_step,
                        elapsed_s=record.time_after_s - baseline.crossing_time_s,
                        dt_s=dt,
                        cell_index=index,
                        previous_region=str(prior_regions[index]),
                        raw_region=str(raw_regions[index]),
                        post_region=str(regions[index]),
                        transition_event=str(events[index]),
                        pressure_pa=float(pressure[index]),
                        temperature_K=float(temperature[index]),
                        q_equilibrium=float(q_eq[index]),
                        q_post=float(q_post[index]),
                        void_fraction=float(alpha[index]),
                        sound_speed_m_s=float(sound[index]),
                        projection_applied=bool(first.projection_applied[index]),
                        delta_rho_q=float(first.delta_rho_q[index]),
                        accepted_state_sha256=state_hash,
                    )
                )

            elapsed = record.time_after_s - baseline.crossing_time_s
            for name, target in PHYSICAL_CHECKPOINTS_S:
                if name not in checkpoints and elapsed >= target:
                    checkpoints[name] = _checkpoint_from_step(
                        cfl=cfl,
                        name=name,
                        target=target,
                        baseline=baseline,
                        step=record,
                    )
            if len(checkpoints) == len(PHYSICAL_CHECKPOINTS_S):
                break
        except Exception as exc:
            outcome = "FAIL_SAFE_STOP"
            failure_category = _failure_category(exc)
            failure_reason = f"{type(exc).__name__}: {exc}"
            break
    else:
        outcome = "FAIL_SAFE_STOP"
        failure_category = "FIXED_POST_CROSSING_STEP_CAP_REACHED"
        failure_reason = (
            f"CFL={cfl} did not reach all targets within the fixed "
            f"{POST_CROSSING_STEP_CAPS[cfl]}-step cap"
        )

    if len(checkpoints) != len(PHYSICAL_CHECKPOINTS_S) and not failure_category:
        outcome = "FAIL_SAFE_STOP"
        failure_category = "FIXED_PHYSICAL_HORIZON_NOT_REACHED"
        failure_reason = "not all fixed physical checkpoints were reached"
    checkpoint_rows = tuple(
        checkpoints.get(
            name,
            _blank_checkpoint(cfl, name, target, failure_category, last_hash),
        )
        for name, target in PHYSICAL_CHECKPOINTS_S
    )
    return Gate8ColumnResult(
        cfl=cfl,
        config=config,
        baseline=baseline,
        continuation_outcome=outcome,
        failure_category=failure_category,
        failure_reason=failure_reason,
        steps=tuple(steps),
        focused_cells=tuple(focused),
        checkpoints=checkpoint_rows,
        region_toggle_counts=tuple(toggle_counts),
        last_valid_state_sha256=last_hash,
    )


def run_gate8_cfl_0p10_0p05_increment() -> Gate8IncrementResult:
    """Execute the exact replay gate and, only after it passes, CFL=0.05."""

    gate6 = _run_gate6_column()
    _require_gate6_identity(gate6)
    refined = _run_refined_column(0.05)
    return Gate8IncrementResult(columns=(gate6, refined), provenance=_git_provenance())


def _flatten(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    if any(list(row) != fieldnames for row in rows):
        raise HEMGate8CflSensitivityError(f"inconsistent fields for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten(value) for key, value in row.items()})


def _case_rows(result: Gate8IncrementResult) -> list[dict[str, object]]:
    rows = []
    for column in result.columns:
        rows.append(
            {
                "cfl": column.cfl,
                "implementation_status": "EXECUTED_INCREMENT_COLUMN",
                "first_crossing_outcome": column.baseline.outcome,
                "first_crossing_step": column.baseline.crossing_step,
                "first_crossing_time_s": column.baseline.crossing_time_s,
                "first_crossing_cells": column.baseline.crossing_cell_indices,
                "maximum_crossing_quality": column.baseline.maximum_crossing_quality,
                "continuation_outcome": column.continuation_outcome,
                "successful_post_crossing_step_count": len(column.steps),
                "reached_checkpoints": tuple(
                    row.checkpoint for row in column.checkpoints if row.reached
                ),
                "cell30_region_changes": column.region_toggle_counts[CHATTER_CELL],
                "last_valid_state_sha256": column.last_valid_state_sha256,
                "failure_category": column.failure_category,
                "failure_reason": column.failure_reason,
            }
        )
    rows.append(
        {
            "cfl": 0.025,
            "implementation_status": "PENDING_LOCKED_SEQUENCE_COLUMN",
            "first_crossing_outcome": "NOT_EXECUTED_IN_INCREMENT_1",
            "first_crossing_step": None,
            "first_crossing_time_s": None,
            "first_crossing_cells": (),
            "maximum_crossing_quality": None,
            "continuation_outcome": "NOT_EXECUTED_IN_INCREMENT_1",
            "successful_post_crossing_step_count": 0,
            "reached_checkpoints": (),
            "cell30_region_changes": None,
            "last_valid_state_sha256": "",
            "failure_category": "",
            "failure_reason": "",
        }
    )
    return rows


def _transition_rows(result: Gate8IncrementResult) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for column in result.columns:
        for row in column.focused_cells:
            if row.previous_region == row.post_region:
                continue
            rows.append(asdict(row))
    return rows


def _report(result: Gate8IncrementResult) -> str:
    lines = [
        "# Stage 7 Gate 8 — CFL 0.10 / 0.05 Implementation Increment",
        "",
        "```text",
        "scope:                         verification only",
        "locked sequence:               0.10 / 0.05 / 0.025",
        "implemented columns:           0.10 / 0.05",
        "pending column:                0.025",
        "full Gate 8 execution:         false",
        "cross-CFL interpretation:      withheld",
        "physical validation:           false",
        "design-use acceptance:         false",
        "```",
        "",
        "The CFL 0.05 column is started only after the complete Gate 6 CFL 0.10 "
        "identity passes. This increment emits no convergence or sensitivity label.",
        "",
        "| CFL | first crossing | continuation | checkpoints | cell 30 changes |",
        "|---:|---|---|---|---:|",
    ]
    for column in result.columns:
        reached = ", ".join(
            row.checkpoint for row in column.checkpoints if row.reached
        ) or "none"
        lines.append(
            f"| {column.cfl:g} | {column.baseline.outcome} | "
            f"{column.continuation_outcome} | {reached} | "
            f"{column.region_toggle_counts[CHATTER_CELL]} |"
        )
    lines.extend(
        [
            "| 0.025 | pending | pending | none | — |",
            "",
            "No root-cause, physical-accuracy, design-use, or production approval is "
            "created by this increment.",
            "",
        ]
    )
    return "\n".join(lines)


def write_gate8_cfl_0p10_0p05_artifacts(
    output_dir: str | Path,
    result: Gate8IncrementResult | None = None,
) -> tuple[Gate8IncrementResult, dict[str, Path]]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    executed = result or run_gate8_cfl_0p10_0p05_increment()
    summary = executed.summary()
    if summary["gate6_identity_reproduced_exactly"] is not True:
        raise HEMGate8CflSensitivityError("exact Gate 6 identity is required")
    paths = {
        "summary": target / "summary.json",
        "cases": target / "cfl_cases.csv",
        "checkpoints": target / "physical_checkpoints.csv",
        "focus": target / "cell_29_30_31_history.csv",
        "transitions": target / "transition_events.csv",
        "inventory": target / "inventory_budget.csv",
        "report": target / "report.md",
        "digest": target / "artifact_sha256.txt",
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_rows(paths["cases"], _case_rows(executed))
    checkpoint_rows = [
        asdict(row) for column in executed.columns for row in column.checkpoints
    ]
    checkpoint_rows.extend(
        asdict(
            _blank_checkpoint(
                0.025,
                name,
                target_s,
                "PENDING_LOCKED_SEQUENCE_COLUMN",
                "",
            )
        )
        for name, target_s in PHYSICAL_CHECKPOINTS_S
    )
    _write_rows(paths["checkpoints"], checkpoint_rows)
    _write_rows(
        paths["focus"],
        [asdict(row) for column in executed.columns for row in column.focused_cells],
    )
    _write_rows(paths["transitions"], _transition_rows(executed))
    _write_rows(
        paths["inventory"],
        [
            {"cfl": column.cfl, **asdict(step)}
            for column in executed.columns
            for step in column.steps
        ],
    )
    paths["report"].write_text(_report(executed), encoding="utf-8")
    digest_lines = []
    for path in sorted(
        (path for key, path in paths.items() if key != "digest"),
        key=lambda item: item.name,
    ):
        digest_lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        )
    paths["digest"].write_text("\n".join(digest_lines) + "\n", encoding="utf-8")
    return executed, paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result, paths = write_gate8_cfl_0p10_0p05_artifacts(args.output_dir)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
