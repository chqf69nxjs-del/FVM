"""Verification-only repeated Case A/B first-crossing runner for pure-CO2 HEM.

This increment follows the merged one-step projected crossing path.  It freezes a
single strong crossing case and a matched liquid control only after repeated,
deterministic short runs satisfy the reviewed transition, projection,
accepted-state, and budget invariants.

The runner remains verification-only.  It does not change the production solver,
Rusanov flux, CFL algorithm, EOS, phase classifier, acoustic closure, projection
operator, boundary/source algorithms, or any tolerance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Sequence

import numpy as np

from .boundary import TransmissiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .hem_liquid_to_two_phase_crossing import (
    HEMBoundaryPhaseEvaluator,
    HEMRawTransitionDetection,
    detect_raw_transition_events,
)
from .hem_liquid_to_two_phase_minimal_fvm_dry_run import (
    DryRunEndpointState,
    MinimalFvmDryRunCaseSpec,
    MinimalRawFvmCaseResult,
    MinimalRawFvmCellRecord,
    build_piecewise_liquid_initial_state,
)
from .hem_liquid_to_two_phase_projected_fvm_dry_run import (
    HEMProjectedFvmDryRunConfig,
    ProjectedFvmCaseResult,
    run_one_projected_fvm_case,
)
from .hem_liquid_to_two_phase_state_pair_survey import (
    HEMLiquidStatePairSurveyResult,
    run_liquid_state_pair_survey,
)
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_phase_classification import (
    evaluate_coolprop_hem_phase_state,
)
from .phase_budget import PhaseChangeBudgetTracker
from .solver import FvmSolver
from .state import (
    IDX_RHO,
    internal_energy,
    inventory,
    vapor_mass_fraction,
    velocity,
)


CaseRunOutcome = Literal[
    "ACCEPTED_CROSSING",
    "MATCHED_ALL_LIQUID",
    "NO_CROSSING_WITHIN_LIMIT",
    "ENDPOINT_LANDING",
    "FORBIDDEN_TRANSITION",
    "RAW_STATE_REJECTED",
    "GUARD_FAILURE",
    "BACKEND_FAILURE",
]


class HEMFirstCrossingCaseABError(RuntimeError):
    """Raised when the narrow repeated Case A/B verification contract fails."""


@dataclass(frozen=True)
class HEMFirstCrossingCaseABConfig:
    """Fixed settings for repeated first-crossing and matched-control runs."""

    projected_config: HEMProjectedFvmDryRunConfig = field(
        default_factory=HEMProjectedFvmDryRunConfig
    )
    case_a_case_id: str = "strong_p5m5_to_p2m5"
    case_b_case_id: str = "control_p5m5_to_p4m5"
    repeat_count: int = 3
    case_a_max_steps: int = 8
    crossing_evidence_min_quality: float = 1.0e-6
    time_match_absolute_tolerance_s: float = 1.0e-15
    conservative_budget_absolute_tolerance: float = 1.0e-9
    vapor_budget_absolute_tolerance_kg: float = 1.0e-12

    def __post_init__(self) -> None:
        if not self.case_a_case_id.strip() or not self.case_b_case_id.strip():
            raise ValueError("Case A and Case B IDs must not be empty")
        if self.case_a_case_id == self.case_b_case_id:
            raise ValueError("Case A and Case B must be different cases")
        if self.repeat_count < 2:
            raise ValueError("repeat_count must be at least 2")
        if self.case_a_max_steps <= 0:
            raise ValueError("case_a_max_steps must be positive")
        if (
            not np.isfinite(self.crossing_evidence_min_quality)
            or not 0.0 < self.crossing_evidence_min_quality < 1.0
        ):
            raise ValueError(
                "crossing_evidence_min_quality must be finite and lie in (0, 1)"
            )
        for name, value in (
            (
                "time_match_absolute_tolerance_s",
                self.time_match_absolute_tolerance_s,
            ),
            (
                "conservative_budget_absolute_tolerance",
                self.conservative_budget_absolute_tolerance,
            ),
            (
                "vapor_budget_absolute_tolerance_kg",
                self.vapor_budget_absolute_tolerance_kg,
            ),
        ):
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")

        raw = self.projected_config.raw_config
        known = {spec.case_id for spec in raw.case_specs}
        missing = {self.case_a_case_id, self.case_b_case_id} - known
        if missing:
            raise ValueError(f"Case A/B IDs are missing from raw case specs: {sorted(missing)}")
        if raw.phase_config != raw.survey_config.phase_config:
            raise ValueError(
                "raw dry-run phase_config must match the state-pair survey phase_config"
            )
        if (
            self.vapor_budget_absolute_tolerance_kg
            != self.projected_config.vapor_budget_absolute_tolerance_kg
        ):
            raise ValueError(
                "Case A/B vapor tolerance must match the projected one-step tolerance"
            )

    @property
    def raw_config(self):
        return self.projected_config.raw_config


@dataclass(frozen=True)
class CaseABStepRecord:
    """Compact evidence for one accepted FVM/projection step."""

    case_id: str
    repeat_index: int
    step_index: int
    time_before_s: float
    dt_s: float
    time_after_s: float
    raw_outcome: str
    projected_outcome: str
    crossing_cell_indices: tuple[int, ...]
    first_projection_cell_indices: tuple[int, ...]
    second_projection_cell_indices: tuple[int, ...]
    max_raw_equilibrium_quality: float
    max_post_quality_mismatch: float
    projection_vapor_source_kg: float
    state_sha256: str


@dataclass(frozen=True)
class CaseABCellRecord:
    """Final-step cell evidence retained for each repeated run."""

    case_id: str
    repeat_index: int
    step_index: int
    cell_index: int
    raw_region: str
    post_region: str
    transition_event: str
    q_transport_raw: float
    q_equilibrium: float
    q_post: float
    post_pressure_pa: float
    post_temperature_K: float
    post_void_fraction: float
    post_sound_speed_m_s: float


@dataclass(frozen=True)
class CaseABRunRecord:
    """One complete Case A or matched Case B run."""

    case_id: str
    role: str
    repeat_index: int
    outcome: CaseRunOutcome
    failure_reason: str
    step_count: int
    final_time_s: float
    target_time_s: float | None
    crossing_step: int | None
    crossing_time_s: float | None
    crossing_cell_indices: tuple[int, ...]
    projection_cell_indices: tuple[int, ...]
    maximum_crossing_quality: float
    cumulative_projection_vapor_source_kg: float
    final_state_sha256: str
    repeatability_signature: str
    steps: tuple[CaseABStepRecord, ...]
    cells: tuple[CaseABCellRecord, ...]
    boundary_budget_diagnostics: dict[str, float]
    phase_budget_diagnostics: dict[str, float]

    @property
    def accepted(self) -> bool:
        return self.outcome in {"ACCEPTED_CROSSING", "MATCHED_ALL_LIQUID"}


@dataclass(frozen=True)
class HEMFirstCrossingCaseABResult:
    """Repeated short-run evidence and Case A/B freeze decision."""

    config: HEMFirstCrossingCaseABConfig
    survey_summary: dict[str, object]
    case_a_runs: tuple[CaseABRunRecord, ...]
    case_b_runs: tuple[CaseABRunRecord, ...]

    def summary(self) -> dict[str, object]:
        case_a_signatures = [run.repeatability_signature for run in self.case_a_runs]
        case_b_signatures = [run.repeatability_signature for run in self.case_b_runs]
        case_a_repeatable = bool(
            self.case_a_runs
            and all(run.outcome == "ACCEPTED_CROSSING" for run in self.case_a_runs)
            and len(set(case_a_signatures)) == 1
        )
        case_b_repeatable = bool(
            self.case_b_runs
            and all(run.outcome == "MATCHED_ALL_LIQUID" for run in self.case_b_runs)
            and len(set(case_b_signatures)) == 1
        )
        canonical_a = self.case_a_runs[0] if self.case_a_runs else None
        target_time = canonical_a.crossing_time_s if canonical_a is not None else None
        time_matched = bool(
            target_time is not None
            and self.case_b_runs
            and all(
                abs(run.final_time_s - target_time)
                <= self.config.time_match_absolute_tolerance_s
                for run in self.case_b_runs
            )
        )
        case_a_frozen = case_a_repeatable
        case_b_frozen = case_b_repeatable and time_matched
        verified = case_a_frozen and case_b_frozen

        return {
            "schema_version": "stage7_lco2_hem_first_crossing_case_ab_v1",
            "scope": "verification_only",
            "repeat_count": self.config.repeat_count,
            "case_a_case_id": self.config.case_a_case_id,
            "case_b_case_id": self.config.case_b_case_id,
            "case_a_repeatable": case_a_repeatable,
            "case_b_repeatable": case_b_repeatable,
            "case_b_matched_physical_time": time_matched,
            "case_a_repeatability_signature": (
                case_a_signatures[0] if case_a_repeatable else None
            ),
            "case_b_repeatability_signature": (
                case_b_signatures[0] if case_b_repeatable else None
            ),
            "case_a_crossing_step": (
                canonical_a.crossing_step if canonical_a is not None else None
            ),
            "case_a_crossing_time_s": target_time,
            "case_a_crossing_cell_indices": (
                list(canonical_a.crossing_cell_indices)
                if canonical_a is not None
                else []
            ),
            "case_a_frozen": case_a_frozen,
            "case_b_frozen": case_b_frozen,
            "actual_first_order_fvm_crossing_verified": verified,
            "software_verification_only": True,
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            "production_hem_activation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "two_phase_acoustic_accuracy_band_approved": False,
        }


def _state_sha256(U: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(U, dtype="<f8"))
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _hex_float(value: float | None) -> str | None:
    return None if value is None else float(value).hex()


def _signature(
    *,
    role: str,
    outcome: str,
    step_count: int,
    final_time_s: float,
    target_time_s: float | None,
    crossing_step: int | None,
    crossing_time_s: float | None,
    crossing_cells: Sequence[int],
    projection_cells: Sequence[int],
    maximum_crossing_quality: float,
    cumulative_projection_vapor_source_kg: float,
    final_state_sha256: str,
    boundary_budget: dict[str, float],
    phase_budget: dict[str, float],
) -> str:
    payload = {
        "role": role,
        "outcome": outcome,
        "step_count": int(step_count),
        "final_time_s": _hex_float(final_time_s),
        "target_time_s": _hex_float(target_time_s),
        "crossing_step": crossing_step,
        "crossing_time_s": _hex_float(crossing_time_s),
        "crossing_cells": [int(value) for value in crossing_cells],
        "projection_cells": [int(value) for value in projection_cells],
        "maximum_crossing_quality": _hex_float(maximum_crossing_quality),
        "cumulative_projection_vapor_source_kg": _hex_float(
            cumulative_projection_vapor_source_kg
        ),
        "final_state_sha256": final_state_sha256,
        "budget_mass_residual": _hex_float(
            boundary_budget.get("budget_mass_residual", 0.0)
        ),
        "budget_momentum_residual": _hex_float(
            boundary_budget.get("budget_momentum_residual", 0.0)
        ),
        "budget_energy_residual": _hex_float(
            boundary_budget.get("budget_energy_residual", 0.0)
        ),
        "phase_vapor_residual": _hex_float(
            phase_budget.get("phase_vapor_mass_balance_residual_kg", 0.0)
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _raw_outcome(detection: HEMRawTransitionDetection) -> str:
    raw_regions = np.asarray(detection.raw.region).astype(str)
    events = np.asarray(detection.transitions.event).astype(str)
    if np.any(events == "FORBIDDEN_TRANSITION"):
        return "FORBIDDEN_REGION"
    if np.any(raw_regions == "SATURATED_LIQUID_ENDPOINT"):
        return "ENDPOINT_LANDING"
    if np.any(events == "LIQUID_TO_TWO_PHASE_CROSSING"):
        return "OPEN_TWO_PHASE"
    return "ALL_LIQUID"


def _failure_outcome(exc: Exception) -> CaseRunOutcome:
    text = f"{type(exc).__name__}: {exc}".lower()
    backend_terms = (
        "coolprop",
        "backend",
        "phase evaluation failed",
        "property evaluation failed",
        "sound-speed evaluation failed",
    )
    return (
        "BACKEND_FAILURE"
        if any(term in text for term in backend_terms)
        else "GUARD_FAILURE"
    )


def _build_raw_cells(
    *,
    case_id: str,
    grid: UniformGrid,
    initial_U: np.ndarray,
    raw_U: np.ndarray,
    initial_primitive,
    detection: HEMRawTransitionDetection,
) -> tuple[MinimalRawFvmCellRecord, ...]:
    previous_phase = detection.previous.phase_state
    raw_phase = detection.raw.phase_state
    initial_q_transport = np.asarray(vapor_mass_fraction(initial_U), dtype=float)
    raw_q_transport = np.asarray(vapor_mass_fraction(raw_U), dtype=float)
    initial_q_eq = np.asarray(previous_phase.quality, dtype=float)
    raw_q_eq = np.asarray(raw_phase.quality, dtype=float)
    initial_alpha = np.asarray(previous_phase.alpha, dtype=float)
    raw_alpha = np.asarray(raw_phase.alpha, dtype=float)
    initial_p = np.asarray(previous_phase.p, dtype=float)
    raw_p = np.asarray(raw_phase.p, dtype=float)
    initial_T = np.asarray(previous_phase.T, dtype=float)
    raw_T = np.asarray(raw_phase.T, dtype=float)
    initial_regions = np.asarray(detection.previous.region).astype(str)
    raw_regions = np.asarray(detection.raw.region).astype(str)
    events = np.asarray(detection.transitions.event).astype(str)
    raw_e = np.asarray(internal_energy(raw_U), dtype=float)
    raw_u = np.asarray(velocity(raw_U), dtype=float)

    expected = (grid.n_cells,)
    arrays = (
        initial_q_transport,
        raw_q_transport,
        initial_q_eq,
        raw_q_eq,
        initial_alpha,
        raw_alpha,
        initial_p,
        raw_p,
        initial_T,
        raw_T,
        initial_regions,
        raw_regions,
        events,
        raw_e,
        raw_u,
    )
    if any(np.asarray(value).shape != expected for value in arrays):
        raise HEMFirstCrossingCaseABError(
            "raw cell evidence returned an incompatible shape"
        )

    return tuple(
        MinimalRawFvmCellRecord(
            case_id=case_id,
            cell_index=index,
            cell_center_m=float(grid.cell_centers[index]),
            initial_region=str(initial_regions[index]),
            raw_region=str(raw_regions[index]),
            transition_event=str(events[index]),
            rho_initial_kg_m3=float(initial_U[index, IDX_RHO]),
            rho_raw_kg_m3=float(raw_U[index, IDX_RHO]),
            velocity_initial_m_s=float(initial_primitive.u[index]),
            velocity_raw_m_s=float(raw_u[index]),
            e_initial_j_kg=float(initial_primitive.e[index]),
            e_raw_j_kg=float(raw_e[index]),
            pressure_initial_pa=float(initial_p[index]),
            pressure_raw_pa=float(raw_p[index]),
            temperature_initial_K=float(initial_T[index]),
            temperature_raw_K=float(raw_T[index]),
            q_transport_initial=float(initial_q_transport[index]),
            q_transport_raw=float(raw_q_transport[index]),
            q_equilibrium_initial=float(initial_q_eq[index]),
            q_equilibrium_raw=float(raw_q_eq[index]),
            alpha_initial=float(initial_alpha[index]),
            alpha_raw=float(raw_alpha[index]),
        )
        for index in range(grid.n_cells)
    )


def _advance_raw_step(
    *,
    solver: FvmSolver,
    spec: MinimalFvmDryRunCaseSpec,
    left: DryRunEndpointState,
    right: DryRunEndpointState,
    projected_config: HEMProjectedFvmDryRunConfig,
    dt: float,
    phase_evaluator: HEMBoundaryPhaseEvaluator,
) -> MinimalRawFvmCaseResult:
    previous_U = np.array(solver.U, dtype=float, copy=True)
    initial_primitive = solver.primitive()
    measured_cfl = float(
        np.max(
            (np.abs(initial_primitive.u) + initial_primitive.c)
            * dt
            / solver.grid.dx
        )
    )
    solver.step(dt)
    raw_U = np.array(solver.U, dtype=float, copy=True)
    detection = detect_raw_transition_events(
        previous_U,
        raw_U,
        evaluator=phase_evaluator,
        phase_config=projected_config.raw_config.phase_config,
    )
    cells = _build_raw_cells(
        case_id=spec.case_id,
        grid=solver.grid,
        initial_U=previous_U,
        raw_U=raw_U,
        initial_primitive=initial_primitive,
        detection=detection,
    )
    current_inventory = inventory(
        raw_U,
        solver.grid.dx,
        solver.grid.geometry.area_m2,
    )
    budget = (
        solver.boundary_budget.diagnostics(current_inventory)
        if solver.boundary_budget is not None
        else {}
    )
    return MinimalRawFvmCaseResult(
        spec=spec,
        left_state=left,
        right_state=right,
        dt_s=float(dt),
        dx_m=float(solver.grid.dx),
        target_cfl=float(projected_config.raw_config.cfl),
        measured_initial_cfl=measured_cfl,
        interface_cell=projected_config.raw_config.resolved_interface_cell,
        outcome=_raw_outcome(detection),
        failure_reason="",
        initial_U=previous_U,
        raw_U=raw_U,
        cells=cells,
        budget_diagnostics=budget,
        fvm_step_exercised=True,
    )


def _validate_final_budgets(
    *,
    solver: FvmSolver,
    phase_tracker: PhaseChangeBudgetTracker,
    config: HEMFirstCrossingCaseABConfig,
) -> tuple[dict[str, float], dict[str, float]]:
    current = inventory(
        solver.U,
        solver.grid.dx,
        solver.grid.geometry.area_m2,
    )
    boundary = (
        solver.boundary_budget.diagnostics(current)
        if solver.boundary_budget is not None
        else {}
    )
    phase = phase_tracker.diagnostics(
        current,
        boundary_budget=solver.boundary_budget,
    )
    for key in (
        "budget_mass_residual",
        "budget_momentum_residual",
        "budget_energy_residual",
    ):
        if abs(float(boundary.get(key, 0.0))) > (
            config.conservative_budget_absolute_tolerance
        ):
            raise HEMFirstCrossingCaseABError(
                f"conservative budget residual exceeds tolerance: "
                f"{key}={boundary.get(key)}"
            )
    if abs(float(phase["phase_vapor_mass_balance_residual_kg"])) > (
        config.vapor_budget_absolute_tolerance_kg
    ):
        raise HEMFirstCrossingCaseABError(
            "phase-vapor budget residual exceeds tolerance: "
            f"{phase['phase_vapor_mass_balance_residual_kg']}"
        )
    return (
        {str(key): float(value) for key, value in boundary.items()},
        {str(key): float(value) for key, value in phase.items()},
    )


def _make_solver(
    *,
    left: DryRunEndpointState,
    right: DryRunEndpointState,
    config: HEMFirstCrossingCaseABConfig,
) -> FvmSolver:
    raw = config.raw_config
    grid = UniformGrid(
        PipeGeometry(length_m=raw.length_m, diameter_m=raw.diameter_m),
        n_cells=raw.n_cells,
    )
    initial_U = build_piecewise_liquid_initial_state(
        left,
        right,
        n_cells=raw.n_cells,
        interface_cell=raw.resolved_interface_cell,
    )
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_config=raw.phase_config,
        quality_sync_config=config.projected_config.projection_config,
        quality_tolerance=config.projected_config.accepted_state_quality_tolerance,
    )
    return FvmSolver(
        grid=grid,
        eos=eos,
        U=initial_U,
        cfl=raw.cfl,
        n_ghost=raw.n_ghost,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )


def _cell_records(
    projected: ProjectedFvmCaseResult,
    *,
    repeat_index: int,
    step_index: int,
) -> tuple[CaseABCellRecord, ...]:
    return tuple(
        CaseABCellRecord(
            case_id=projected.raw_case.spec.case_id,
            repeat_index=repeat_index,
            step_index=step_index,
            cell_index=cell.cell_index,
            raw_region=cell.raw_region,
            post_region=cell.post_region,
            transition_event=cell.transition_event,
            q_transport_raw=cell.q_transport_raw,
            q_equilibrium=cell.q_equilibrium,
            q_post=cell.q_after_first_projection,
            post_pressure_pa=cell.post_pressure_pa,
            post_temperature_K=cell.post_temperature_K,
            post_void_fraction=cell.post_void_fraction,
            post_sound_speed_m_s=cell.post_sound_speed_m_s,
        )
        for cell in projected.cells
    )


def _run_once(
    *,
    spec: MinimalFvmDryRunCaseSpec,
    role: str,
    repeat_index: int,
    left: DryRunEndpointState,
    right: DryRunEndpointState,
    config: HEMFirstCrossingCaseABConfig,
    target_time_s: float | None,
    require_crossing: bool,
    phase_evaluator: HEMBoundaryPhaseEvaluator,
) -> CaseABRunRecord:
    solver = _make_solver(left=left, right=right, config=config)
    initial_inventory = inventory(
        solver.U,
        solver.grid.dx,
        solver.grid.geometry.area_m2,
    )
    phase_tracker = PhaseChangeBudgetTracker(initial_inventory=initial_inventory)
    step_records: list[CaseABStepRecord] = []
    final_cells: tuple[CaseABCellRecord, ...] = ()
    crossing_step: int | None = None
    crossing_time: float | None = None
    crossing_cells: tuple[int, ...] = ()
    projection_cells: tuple[int, ...] = ()
    maximum_crossing_quality = 0.0
    outcome: CaseRunOutcome = (
        "NO_CROSSING_WITHIN_LIMIT" if require_crossing else "MATCHED_ALL_LIQUID"
    )
    failure_reason = ""

    try:
        for step_index in range(1, config.case_a_max_steps + 1):
            time_before = float(solver.t)
            if target_time_s is not None:
                if solver.t >= target_time_s:
                    break
                dt = float(solver.compute_dt(t_end=target_time_s))
            else:
                dt = float(solver.compute_dt())
            if not np.isfinite(dt) or dt <= 0.0:
                raise HEMFirstCrossingCaseABError("computed time step must be positive")

            raw_case = _advance_raw_step(
                solver=solver,
                spec=spec,
                left=left,
                right=right,
                projected_config=config.projected_config,
                dt=dt,
                phase_evaluator=phase_evaluator,
            )
            if raw_case.outcome == "ENDPOINT_LANDING":
                outcome = "ENDPOINT_LANDING"
                raise HEMFirstCrossingCaseABError(
                    "saturated-liquid endpoint landing is not accepted"
                )
            if raw_case.outcome == "FORBIDDEN_REGION":
                outcome = "FORBIDDEN_TRANSITION"
                raise HEMFirstCrossingCaseABError(
                    "forbidden transition was detected"
                )

            projected = run_one_projected_fvm_case(
                raw_case,
                config.projected_config,
            )
            if projected.outcome not in {
                "ACCEPTED_CROSSING",
                "ACCEPTED_ALL_LIQUID_NOOP",
            }:
                raise HEMFirstCrossingCaseABError(
                    f"projected step was rejected: {projected.outcome}: "
                    f"{projected.failure_reason}"
                )

            phase_tracker.record_phase_change(
                U_before=raw_case.raw_U,
                U_after=projected.post_U,
                dx=solver.grid.dx,
                area_m2=solver.grid.geometry.area_m2,
                dt=dt,
            )
            solver.U = np.array(projected.post_U, dtype=float, copy=True)

            summary = projected.summary()
            current_crossing = tuple(
                int(value) for value in summary["crossing_cell_indices"]
            )
            current_projection = tuple(
                int(value) for value in summary["first_projection_cell_indices"]
            )
            max_raw_q = float(
                summary["raw_case_summary"]["max_raw_equilibrium_quality"]
            )
            budget = summary["budget_diagnostics"] or {}
            step_records.append(
                CaseABStepRecord(
                    case_id=spec.case_id,
                    repeat_index=repeat_index,
                    step_index=step_index,
                    time_before_s=time_before,
                    dt_s=dt,
                    time_after_s=float(solver.t),
                    raw_outcome=raw_case.outcome,
                    projected_outcome=projected.outcome,
                    crossing_cell_indices=current_crossing,
                    first_projection_cell_indices=current_projection,
                    second_projection_cell_indices=tuple(
                        int(value)
                        for value in summary["second_projection_cell_indices"]
                    ),
                    max_raw_equilibrium_quality=max_raw_q,
                    max_post_quality_mismatch=float(
                        summary["max_post_quality_mismatch"]
                    ),
                    projection_vapor_source_kg=float(
                        budget.get("projection_vapor_source_kg", 0.0)
                    ),
                    state_sha256=_state_sha256(solver.U),
                )
            )
            final_cells = _cell_records(
                projected,
                repeat_index=repeat_index,
                step_index=step_index,
            )

            if current_crossing:
                if not require_crossing:
                    outcome = "FORBIDDEN_TRANSITION"
                    raise HEMFirstCrossingCaseABError(
                        "matched liquid control produced a crossing"
                    )
                if projected.outcome != "ACCEPTED_CROSSING":
                    raise HEMFirstCrossingCaseABError(
                        "crossing did not produce an accepted projected state"
                    )
                if current_projection != current_crossing:
                    raise HEMFirstCrossingCaseABError(
                        "crossing cells and projection cells do not match"
                    )
                if max_raw_q < config.crossing_evidence_min_quality:
                    raise HEMFirstCrossingCaseABError(
                        "crossing quality evidence is below the fixed minimum"
                    )
                crossing_step = step_index
                crossing_time = float(solver.t)
                crossing_cells = current_crossing
                projection_cells = current_projection
                maximum_crossing_quality = max_raw_q
                outcome = "ACCEPTED_CROSSING"
                break

            if require_crossing:
                if projected.outcome != "ACCEPTED_ALL_LIQUID_NOOP":
                    raise HEMFirstCrossingCaseABError(
                        "pre-crossing step must remain an accepted liquid no-op"
                    )
            else:
                if projected.outcome != "ACCEPTED_ALL_LIQUID_NOOP":
                    raise HEMFirstCrossingCaseABError(
                        "matched control must remain an accepted liquid no-op"
                    )
                if current_projection:
                    raise HEMFirstCrossingCaseABError(
                        "matched control projection must remain a no-op"
                    )
                if target_time_s is not None and solver.t >= target_time_s:
                    break

        if require_crossing and crossing_step is None:
            outcome = "NO_CROSSING_WITHIN_LIMIT"
            raise HEMFirstCrossingCaseABError(
                "Case A did not cross within case_a_max_steps"
            )
        if not require_crossing:
            if target_time_s is None:
                raise HEMFirstCrossingCaseABError(
                    "matched control requires target_time_s"
                )
            if (
                abs(float(solver.t) - target_time_s)
                > config.time_match_absolute_tolerance_s
            ):
                raise HEMFirstCrossingCaseABError(
                    "Case B did not reach the matched physical-time horizon"
                )
            outcome = "MATCHED_ALL_LIQUID"

        boundary_budget, phase_budget = _validate_final_budgets(
            solver=solver,
            phase_tracker=phase_tracker,
            config=config,
        )
        cumulative_source = float(
            phase_budget["phase_vapor_mass_source_cumulative_kg"]
        )
        final_hash = _state_sha256(solver.U)
        signature = _signature(
            role=role,
            outcome=outcome,
            step_count=int(solver.step_count),
            final_time_s=float(solver.t),
            target_time_s=target_time_s,
            crossing_step=crossing_step,
            crossing_time_s=crossing_time,
            crossing_cells=crossing_cells,
            projection_cells=projection_cells,
            maximum_crossing_quality=maximum_crossing_quality,
            cumulative_projection_vapor_source_kg=cumulative_source,
            final_state_sha256=final_hash,
            boundary_budget=boundary_budget,
            phase_budget=phase_budget,
        )
        return CaseABRunRecord(
            case_id=spec.case_id,
            role=role,
            repeat_index=repeat_index,
            outcome=outcome,
            failure_reason="",
            step_count=int(solver.step_count),
            final_time_s=float(solver.t),
            target_time_s=target_time_s,
            crossing_step=crossing_step,
            crossing_time_s=crossing_time,
            crossing_cell_indices=crossing_cells,
            projection_cell_indices=projection_cells,
            maximum_crossing_quality=maximum_crossing_quality,
            cumulative_projection_vapor_source_kg=cumulative_source,
            final_state_sha256=final_hash,
            repeatability_signature=signature,
            steps=tuple(step_records),
            cells=final_cells,
            boundary_budget_diagnostics=boundary_budget,
            phase_budget_diagnostics=phase_budget,
        )
    except Exception as exc:
        if outcome not in {
            "ENDPOINT_LANDING",
            "FORBIDDEN_TRANSITION",
            "NO_CROSSING_WITHIN_LIMIT",
        }:
            outcome = _failure_outcome(exc)
        empty_budget: dict[str, float] = {}
        final_hash = _state_sha256(solver.U)
        signature = _signature(
            role=role,
            outcome=outcome,
            step_count=int(solver.step_count),
            final_time_s=float(solver.t),
            target_time_s=target_time_s,
            crossing_step=crossing_step,
            crossing_time_s=crossing_time,
            crossing_cells=crossing_cells,
            projection_cells=projection_cells,
            maximum_crossing_quality=maximum_crossing_quality,
            cumulative_projection_vapor_source_kg=float(
                phase_tracker.cumulative_source_kg
            ),
            final_state_sha256=final_hash,
            boundary_budget=empty_budget,
            phase_budget=empty_budget,
        )
        return CaseABRunRecord(
            case_id=spec.case_id,
            role=role,
            repeat_index=repeat_index,
            outcome=outcome,
            failure_reason=f"{type(exc).__name__}: {exc}",
            step_count=int(solver.step_count),
            final_time_s=float(solver.t),
            target_time_s=target_time_s,
            crossing_step=crossing_step,
            crossing_time_s=crossing_time,
            crossing_cell_indices=crossing_cells,
            projection_cell_indices=projection_cells,
            maximum_crossing_quality=maximum_crossing_quality,
            cumulative_projection_vapor_source_kg=float(
                phase_tracker.cumulative_source_kg
            ),
            final_state_sha256=final_hash,
            repeatability_signature=signature,
            steps=tuple(step_records),
            cells=final_cells,
            boundary_budget_diagnostics={},
            phase_budget_diagnostics={},
        )


def run_first_crossing_case_ab_freeze(
    config: HEMFirstCrossingCaseABConfig | None = None,
    *,
    survey_result: HEMLiquidStatePairSurveyResult | None = None,
    phase_evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state,
) -> HEMFirstCrossingCaseABResult:
    """Run repeated Case A and matched Case B, then make the freeze decision."""

    cfg = config or HEMFirstCrossingCaseABConfig()
    survey = survey_result or run_liquid_state_pair_survey(
        cfg.raw_config.survey_config
    )
    candidates = {record.candidate_id: record for record in survey.candidates}
    specs = {spec.case_id: spec for spec in cfg.raw_config.case_specs}
    case_a_spec = specs[cfg.case_a_case_id]
    case_b_spec = specs[cfg.case_b_case_id]

    case_a_left = DryRunEndpointState.from_candidate(
        candidates[case_a_spec.left_candidate_id]
    )
    case_a_right = DryRunEndpointState.from_candidate(
        candidates[case_a_spec.right_candidate_id]
    )
    case_b_left = DryRunEndpointState.from_candidate(
        candidates[case_b_spec.left_candidate_id]
    )
    case_b_right = DryRunEndpointState.from_candidate(
        candidates[case_b_spec.right_candidate_id]
    )

    case_a_runs = tuple(
        _run_once(
            spec=case_a_spec,
            role="Case A",
            repeat_index=repeat_index,
            left=case_a_left,
            right=case_a_right,
            config=cfg,
            target_time_s=None,
            require_crossing=True,
            phase_evaluator=phase_evaluator,
        )
        for repeat_index in range(cfg.repeat_count)
    )
    if not all(run.outcome == "ACCEPTED_CROSSING" for run in case_a_runs):
        return HEMFirstCrossingCaseABResult(
            config=cfg,
            survey_summary=survey.summary(),
            case_a_runs=case_a_runs,
            case_b_runs=(),
        )

    target_time = case_a_runs[0].crossing_time_s
    if target_time is None:
        raise HEMFirstCrossingCaseABError(
            "accepted Case A runs must retain a crossing time"
        )
    if any(
        abs(float(run.crossing_time_s) - target_time)
        > cfg.time_match_absolute_tolerance_s
        for run in case_a_runs
        if run.crossing_time_s is not None
    ):
        return HEMFirstCrossingCaseABResult(
            config=cfg,
            survey_summary=survey.summary(),
            case_a_runs=case_a_runs,
            case_b_runs=(),
        )

    case_b_runs = tuple(
        _run_once(
            spec=case_b_spec,
            role="Case B",
            repeat_index=repeat_index,
            left=case_b_left,
            right=case_b_right,
            config=cfg,
            target_time_s=float(target_time),
            require_crossing=False,
            phase_evaluator=phase_evaluator,
        )
        for repeat_index in range(cfg.repeat_count)
    )
    return HEMFirstCrossingCaseABResult(
        config=cfg,
        survey_summary=survey.summary(),
        case_a_runs=case_a_runs,
        case_b_runs=case_b_runs,
    )


def evaluate_case_ab_freeze(
    config: HEMFirstCrossingCaseABConfig,
    *,
    survey_summary: dict[str, object],
    case_a_runs: Sequence[CaseABRunRecord],
    case_b_runs: Sequence[CaseABRunRecord],
) -> HEMFirstCrossingCaseABResult:
    """Pure helper used by dependency-free tests for the freeze decision."""

    return HEMFirstCrossingCaseABResult(
        config=config,
        survey_summary=dict(survey_summary),
        case_a_runs=tuple(case_a_runs),
        case_b_runs=tuple(case_b_runs),
    )


def _config_payload(config: HEMFirstCrossingCaseABConfig) -> dict[str, object]:
    raw = config.raw_config
    return {
        "case_a_case_id": config.case_a_case_id,
        "case_b_case_id": config.case_b_case_id,
        "repeat_count": config.repeat_count,
        "case_a_max_steps": config.case_a_max_steps,
        "crossing_evidence_min_quality": config.crossing_evidence_min_quality,
        "time_match_absolute_tolerance_s": (
            config.time_match_absolute_tolerance_s
        ),
        "conservative_budget_absolute_tolerance": (
            config.conservative_budget_absolute_tolerance
        ),
        "vapor_budget_absolute_tolerance_kg": (
            config.vapor_budget_absolute_tolerance_kg
        ),
        "raw_numerics": {
            "n_cells": raw.n_cells,
            "length_m": raw.length_m,
            "diameter_m": raw.diameter_m,
            "cfl": raw.cfl,
            "n_ghost": raw.n_ghost,
            "interface_cell": raw.resolved_interface_cell,
        },
        "projection_config": asdict(config.projected_config.projection_config),
        "accepted_state_quality_tolerance": (
            config.projected_config.accepted_state_quality_tolerance
        ),
    }


def write_first_crossing_case_ab_artifacts(
    output_dir: str | Path,
    result: HEMFirstCrossingCaseABResult,
) -> dict[str, Path]:
    """Write JSON, CSV, Markdown, and NPZ evidence for the frozen Case A/B gate."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_first_crossing_case_ab"
    paths = {
        "json": target / f"{stem}.json",
        "runs_csv": target / f"{stem}_runs.csv",
        "steps_csv": target / f"{stem}_steps.csv",
        "cells_csv": target / f"{stem}_cells.csv",
        "markdown": target / f"{stem}.md",
        "npz": target / f"{stem}.npz",
    }

    runs = list(result.case_a_runs) + list(result.case_b_runs)
    payload = {
        **result.summary(),
        "config": _config_payload(result.config),
        "survey_summary": dict(result.survey_summary),
        "runs": [
            {
                **{
                    key: value
                    for key, value in asdict(run).items()
                    if key not in {"steps", "cells"}
                },
                "steps": [asdict(step) for step in run.steps],
                "cells": [asdict(cell) for cell in run.cells],
            }
            for run in runs
        ],
    }
    paths["json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    run_rows = []
    for run in runs:
        run_rows.append(
            {
                "case_id": run.case_id,
                "role": run.role,
                "repeat_index": run.repeat_index,
                "outcome": run.outcome,
                "failure_reason": run.failure_reason,
                "step_count": run.step_count,
                "final_time_s": run.final_time_s,
                "target_time_s": run.target_time_s,
                "crossing_step": run.crossing_step,
                "crossing_time_s": run.crossing_time_s,
                "crossing_cell_indices": json.dumps(
                    list(run.crossing_cell_indices)
                ),
                "projection_cell_indices": json.dumps(
                    list(run.projection_cell_indices)
                ),
                "maximum_crossing_quality": run.maximum_crossing_quality,
                "cumulative_projection_vapor_source_kg": (
                    run.cumulative_projection_vapor_source_kg
                ),
                "final_state_sha256": run.final_state_sha256,
                "repeatability_signature": run.repeatability_signature,
            }
        )
    with paths["runs_csv"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(run_rows[0]))
        writer.writeheader()
        writer.writerows(run_rows)

    step_rows = [asdict(step) for run in runs for step in run.steps]
    with paths["steps_csv"].open("w", newline="", encoding="utf-8") as handle:
        if step_rows:
            writer = csv.DictWriter(handle, fieldnames=list(step_rows[0]))
            writer.writeheader()
            writer.writerows(step_rows)
        else:
            handle.write("case_id,repeat_index,step_index\n")

    cell_rows = [asdict(cell) for run in runs for cell in run.cells]
    with paths["cells_csv"].open("w", newline="", encoding="utf-8") as handle:
        if cell_rows:
            writer = csv.DictWriter(handle, fieldnames=list(cell_rows[0]))
            writer.writeheader()
            writer.writerows(cell_rows)
        else:
            handle.write("case_id,repeat_index,step_index,cell_index\n")

    summary = result.summary()
    lines = [
        "# Stage 7 First-Crossing Case A/B Freeze",
        "",
        "Verification-only repeated short-run evidence.",
        "",
        f"- Case A frozen: {summary['case_a_frozen']}",
        f"- Case B frozen: {summary['case_b_frozen']}",
        (
            "- first-order software crossing verified: "
            f"{summary['actual_first_order_fvm_crossing_verified']}"
        ),
        f"- repeat count: {summary['repeat_count']}",
        f"- Case A crossing step: {summary['case_a_crossing_step']}",
        f"- Case A crossing time [s]: {summary['case_a_crossing_time_s']}",
        f"- Case A crossing cells: {summary['case_a_crossing_cell_indices']}",
        "",
        "| role | repeat | outcome | steps | final time | crossing cells | signature |",
        "|---|---:|---|---:|---:|---|---|",
    ]
    for run in runs:
        lines.append(
            "| {role} | {repeat} | {outcome} | {steps} | {time} | {cells} | "
            "`{signature}` |".format(
                role=run.role,
                repeat=run.repeat_index,
                outcome=run.outcome,
                steps=run.step_count,
                time=run.final_time_s,
                cells=list(run.crossing_cell_indices),
                signature=run.repeatability_signature,
            )
        )
    lines.extend(
        [
            "",
            "Physical Validation, production HEM activation, design use, and an "
            "acoustic accuracy band remain unapproved.",
        ]
    )
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")

    np.savez(
        paths["npz"],
        case_a_final_times_s=np.asarray(
            [run.final_time_s for run in result.case_a_runs],
            dtype=float,
        ),
        case_b_final_times_s=np.asarray(
            [run.final_time_s for run in result.case_b_runs],
            dtype=float,
        ),
        case_a_crossing_steps=np.asarray(
            [
                -1 if run.crossing_step is None else run.crossing_step
                for run in result.case_a_runs
            ],
            dtype=int,
        ),
        case_a_projection_sources_kg=np.asarray(
            [
                run.cumulative_projection_vapor_source_kg
                for run in result.case_a_runs
            ],
            dtype=float,
        ),
        case_a_signature=np.asarray(
            [run.repeatability_signature for run in result.case_a_runs]
        ),
        case_b_signature=np.asarray(
            [run.repeatability_signature for run in result.case_b_runs]
        ),
    )
    return paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run repeated first-crossing Case A and matched liquid Case B, "
            "then write freeze evidence."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="verification/stage7_lco2_hem_first_crossing_case_ab",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = run_first_crossing_case_ab_freeze()
    paths = write_first_crossing_case_ab_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
