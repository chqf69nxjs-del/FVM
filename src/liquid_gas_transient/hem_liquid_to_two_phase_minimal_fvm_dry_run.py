"""Verification-only one-step FVM dry run for the first liquid-to-two-phase gate.

The runner uses the existing first-order ``FvmSolver`` with Rusanov flux,
transmissive boundaries, no source, and no phase-change projection. It advances
one real conservative step from ledger-backed liquid state pairs, then evaluates
the raw post-step thermodynamic regions directly from ``rho/e``.

This increment deliberately stops before equilibrium-quality projection and
post-projection accepted-state evaluation. A raw crossing observation is not a
formal crossing verification, physical Validation result, production HEM
activation, or design-use approval.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Protocol, Sequence

import numpy as np

from .boundary import TransmissiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .hem_liquid_to_two_phase_crossing import (
    HEMBoundaryPhaseEvaluator,
    HEMRawTransitionDetection,
    detect_raw_transition_events,
)
from .hem_liquid_to_two_phase_state_pair_survey import (
    HEMLiquidStatePairSurveyConfig,
    HEMLiquidStatePairSurveyResult,
    LiquidCandidateRecord,
    run_liquid_state_pair_survey,
)
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_phase_classification import (
    HEMPhaseClassificationConfig,
    evaluate_coolprop_hem_phase_state,
)
from .solver import FvmSolver
from .state import (
    IDX_RHO,
    N_VARS,
    internal_energy,
    inventory,
    make_conserved,
    vapor_mass_fraction,
    velocity,
)

DryRunOutcome = Literal[
    "ALL_LIQUID",
    "ENDPOINT_LANDING",
    "OPEN_TWO_PHASE",
    "FORBIDDEN_REGION",
    "GUARD_FAILURE",
    "BACKEND_FAILURE",
]


class HEMMinimalRawFvmDryRunError(RuntimeError):
    """Raised when the minimal raw-FVM dry-run contract cannot be applied."""


class DryRunEosFactory(Protocol):
    def __call__(
        self,
        phase_config: HEMPhaseClassificationConfig,
    ) -> VerificationHEMLiquidOpenTwoPhaseEOS:
        """Return a strict accepted-state EOS for the initial liquid array."""


RawTransitionDetector = Callable[..., HEMRawTransitionDetection]


@dataclass(frozen=True)
class MinimalFvmDryRunCaseSpec:
    """One ledger-backed ordered liquid pair for a one-step dry run."""

    case_id: str
    role: str
    left_candidate_id: str
    right_candidate_id: str

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be empty")
        if not self.role.strip():
            raise ValueError("role must not be empty")
        if not self.left_candidate_id.strip() or not self.right_candidate_id.strip():
            raise ValueError("candidate IDs must not be empty")
        if self.left_candidate_id == self.right_candidate_id:
            raise ValueError("left and right candidate IDs must differ")


def default_minimal_fvm_dry_run_case_specs() -> tuple[MinimalFvmDryRunCaseSpec, ...]:
    """Return the strong, moderate, and liquid-control pairs selected in PR #68."""

    return (
        MinimalFvmDryRunCaseSpec(
            case_id="strong_p5m5_to_p2m5",
            role="strong crossing candidate",
            left_candidate_id="p5_m5",
            right_candidate_id="p2_m5",
        ),
        MinimalFvmDryRunCaseSpec(
            case_id="moderate_p5m5_to_p3m5",
            role="moderate candidate",
            left_candidate_id="p5_m5",
            right_candidate_id="p3_m5",
        ),
        MinimalFvmDryRunCaseSpec(
            case_id="control_p5m5_to_p4m5",
            role="liquid negative control candidate",
            left_candidate_id="p5_m5",
            right_candidate_id="p4_m5",
        ),
    )


@dataclass(frozen=True)
class HEMMinimalRawFvmDryRunConfig:
    """Numerical and traceability settings for the first one-step dry-run matrix."""

    n_cells: int = 8
    length_m: float = 1.0
    diameter_m: float = 0.10
    cfl: float = 0.20
    n_ghost: int = 2
    interface_cell: int | None = None
    case_specs: tuple[MinimalFvmDryRunCaseSpec, ...] = field(
        default_factory=default_minimal_fvm_dry_run_case_specs
    )
    survey_config: HEMLiquidStatePairSurveyConfig = field(
        default_factory=HEMLiquidStatePairSurveyConfig
    )
    phase_config: HEMPhaseClassificationConfig = field(
        default_factory=HEMPhaseClassificationConfig
    )

    def __post_init__(self) -> None:
        if self.n_cells < 4:
            raise ValueError("n_cells must be at least 4")
        if not np.isfinite(self.length_m) or self.length_m <= 0.0:
            raise ValueError("length_m must be finite and positive")
        if not np.isfinite(self.diameter_m) or self.diameter_m <= 0.0:
            raise ValueError("diameter_m must be finite and positive")
        if not np.isfinite(self.cfl) or not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be finite and lie in (0, 1]")
        if self.n_ghost <= 0:
            raise ValueError("n_ghost must be positive")
        split = self.resolved_interface_cell
        if not 1 <= split < self.n_cells:
            raise ValueError("interface_cell must lie between internal cells")
        if not self.case_specs:
            raise ValueError("case_specs must not be empty")
        case_ids = [spec.case_id for spec in self.case_specs]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case IDs must be unique")
        if self.phase_config != self.survey_config.phase_config:
            raise ValueError(
                "dry-run phase_config must match the state-pair survey phase_config"
            )
        known_candidates = {
            spec.candidate_id for spec in self.survey_config.candidate_specs
        }
        for spec in self.case_specs:
            missing = {
                spec.left_candidate_id,
                spec.right_candidate_id,
            } - known_candidates
            if missing:
                raise ValueError(
                    f"dry-run case {spec.case_id} references unknown candidates: "
                    f"{sorted(missing)}"
                )

    @property
    def resolved_interface_cell(self) -> int:
        return self.n_cells // 2 if self.interface_cell is None else self.interface_cell


@dataclass(frozen=True)
class DryRunEndpointState:
    """The minimal accepted liquid data needed to build a piecewise FVM state."""

    candidate_id: str
    pressure_pa: float
    subcooling_K: float
    rho_kg_m3: float
    e_j_kg: float

    @classmethod
    def from_candidate(cls, record: LiquidCandidateRecord) -> "DryRunEndpointState":
        if not record.accepted or record.status != "ACCEPTED_LIQUID":
            raise HEMMinimalRawFvmDryRunError(
                f"candidate {record.candidate_id} is not an accepted liquid: "
                f"{record.status}"
            )
        required = (
            record.pressure_recovered_pa,
            record.rho_kg_m3,
            record.e_j_kg,
        )
        if any(value is None or not np.isfinite(value) for value in required):
            raise HEMMinimalRawFvmDryRunError(
                f"candidate {record.candidate_id} lacks finite accepted state data"
            )
        rho = float(record.rho_kg_m3)
        e = float(record.e_j_kg)
        pressure = float(record.pressure_recovered_pa)
        if rho <= 0.0 or e < 0.0 or pressure <= 0.0:
            raise HEMMinimalRawFvmDryRunError(
                f"candidate {record.candidate_id} violates dry-run state guards"
            )
        return cls(
            candidate_id=record.candidate_id,
            pressure_pa=pressure,
            subcooling_K=float(record.subcooling_K),
            rho_kg_m3=rho,
            e_j_kg=e,
        )


@dataclass(frozen=True)
class MinimalRawFvmCellRecord:
    """Cellwise evidence from the initial and raw post-step states."""

    case_id: str
    cell_index: int
    cell_center_m: float
    initial_region: str
    raw_region: str
    transition_event: str
    rho_initial_kg_m3: float
    rho_raw_kg_m3: float
    velocity_initial_m_s: float
    velocity_raw_m_s: float
    e_initial_j_kg: float
    e_raw_j_kg: float
    pressure_initial_pa: float
    pressure_raw_pa: float
    temperature_initial_K: float
    temperature_raw_K: float
    q_transport_initial: float
    q_transport_raw: float
    q_equilibrium_initial: float
    q_equilibrium_raw: float
    alpha_initial: float
    alpha_raw: float


@dataclass(frozen=True)
class MinimalRawFvmCaseResult:
    """One one-step FVM result and its direct raw-region classification."""

    spec: MinimalFvmDryRunCaseSpec
    left_state: DryRunEndpointState
    right_state: DryRunEndpointState
    dt_s: float
    dx_m: float
    target_cfl: float
    measured_initial_cfl: float
    interface_cell: int
    outcome: DryRunOutcome
    failure_reason: str
    initial_U: np.ndarray
    raw_U: np.ndarray
    cells: tuple[MinimalRawFvmCellRecord, ...]
    budget_diagnostics: dict[str, float]
    fvm_step_exercised: bool

    def summary(self) -> dict[str, object]:
        event_counts = {
            event: sum(cell.transition_event == event for cell in self.cells)
            for event in (
                "NO_TRANSITION",
                "BOUNDARY_TOUCH",
                "LIQUID_TO_TWO_PHASE_CROSSING",
                "REVERSE_TRANSITION",
                "FORBIDDEN_TRANSITION",
            )
        }
        raw_region_counts = {
            region: sum(cell.raw_region == region for cell in self.cells)
            for region in (
                "LIQUID_CANDIDATE",
                "SATURATED_LIQUID_ENDPOINT",
                "OPEN_TWO_PHASE",
                "SATURATED_VAPOR_ENDPOINT",
                "VAPOR_CANDIDATE",
            )
        }
        max_q_eq = max(
            (cell.q_equilibrium_raw for cell in self.cells),
            default=0.0,
        )
        max_q_mismatch = max(
            (
                abs(cell.q_transport_raw - cell.q_equilibrium_raw)
                for cell in self.cells
            ),
            default=0.0,
        )
        changed_cells = [
            cell.cell_index
            for cell in self.cells
            if not np.array_equal(
                self.initial_U[cell.cell_index],
                self.raw_U[cell.cell_index],
            )
        ]
        return {
            "case_id": self.spec.case_id,
            "role": self.spec.role,
            "left_candidate_id": self.left_state.candidate_id,
            "right_candidate_id": self.right_state.candidate_id,
            "left_pressure_pa": self.left_state.pressure_pa,
            "right_pressure_pa": self.right_state.pressure_pa,
            "left_subcooling_K": self.left_state.subcooling_K,
            "right_subcooling_K": self.right_state.subcooling_K,
            "dt_s": self.dt_s,
            "dx_m": self.dx_m,
            "target_cfl": self.target_cfl,
            "measured_initial_cfl": self.measured_initial_cfl,
            "interface_cell": self.interface_cell,
            "outcome": self.outcome,
            "failure_reason": self.failure_reason,
            "event_counts": event_counts,
            "raw_region_counts": raw_region_counts,
            "changed_cell_indices": changed_cells,
            "max_raw_equilibrium_quality": float(max_q_eq),
            "max_raw_quality_mismatch": float(max_q_mismatch),
            "initial_transport_quality_exactly_zero": bool(
                all(cell.q_transport_initial == 0.0 for cell in self.cells)
            ),
            "raw_transport_quality_exactly_zero": bool(
                all(cell.q_transport_raw == 0.0 for cell in self.cells)
            ),
            "fvm_step_exercised": self.fvm_step_exercised,
            "projection_exercised": False,
            "accepted_state_eos_after_raw_exercised": False,
            "budget_diagnostics": dict(self.budget_diagnostics),
        }


@dataclass(frozen=True)
class HEMMinimalRawFvmDryRunResult:
    """The fixed three-case one-step dry-run matrix."""

    config: HEMMinimalRawFvmDryRunConfig
    survey_summary: dict[str, object]
    cases: tuple[MinimalRawFvmCaseResult, ...]

    def summary(self) -> dict[str, object]:
        outcome_counts = {
            outcome: sum(case.outcome == outcome for case in self.cases)
            for outcome in (
                "ALL_LIQUID",
                "ENDPOINT_LANDING",
                "OPEN_TWO_PHASE",
                "FORBIDDEN_REGION",
                "GUARD_FAILURE",
                "BACKEND_FAILURE",
            )
        }
        crossing_cases = [
            case.spec.case_id for case in self.cases if case.outcome == "OPEN_TWO_PHASE"
        ]
        return {
            "schema_version": "stage7_lco2_hem_minimal_raw_fvm_dry_run_v1",
            "scope": "verification_only",
            "case_count": len(self.cases),
            "outcome_counts": outcome_counts,
            "raw_crossing_case_ids": crossing_cases,
            "raw_fvm_crossing_observed": bool(crossing_cases),
            "all_cases_exercised_one_fvm_step": bool(
                self.cases and all(case.fvm_step_exercised for case in self.cases)
            ),
            "fvm_solver_step_exercised": True,
            "rusanov_flux_exercised": True,
            "cfl_path_exercised": True,
            "transmissive_boundaries_used": True,
            "physical_source_used": False,
            "phase_projection_exercised": False,
            "accepted_state_eos_after_raw_exercised": False,
            "actual_first_order_fvm_crossing_verified": False,
            "case_a_frozen": False,
            "case_b_frozen": False,
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            "production_hem_activation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "two_phase_acoustic_accuracy_band_approved": False,
        }


def _default_eos_factory(
    phase_config: HEMPhaseClassificationConfig,
) -> VerificationHEMLiquidOpenTwoPhaseEOS:
    return VerificationHEMLiquidOpenTwoPhaseEOS(phase_config=phase_config)


def build_piecewise_liquid_initial_state(
    left: DryRunEndpointState,
    right: DryRunEndpointState,
    *,
    n_cells: int,
    interface_cell: int,
) -> np.ndarray:
    """Build an exact all-``q=0`` stationary liquid discontinuity."""

    if n_cells < 2:
        raise HEMMinimalRawFvmDryRunError("n_cells must be at least 2")
    if not 1 <= interface_cell < n_cells:
        raise HEMMinimalRawFvmDryRunError(
            "interface_cell must separate at least one cell on each side"
        )
    rho = np.empty(n_cells, dtype=float)
    e = np.empty(n_cells, dtype=float)
    rho[:interface_cell] = left.rho_kg_m3
    rho[interface_cell:] = right.rho_kg_m3
    e[:interface_cell] = left.e_j_kg
    e[interface_cell:] = right.e_j_kg
    U = make_conserved(rho, np.zeros(n_cells), e, np.zeros(n_cells))
    if U.shape != (n_cells, N_VARS) or not np.all(np.isfinite(U)):
        raise HEMMinimalRawFvmDryRunError("initial conservative state is invalid")
    if not np.all(vapor_mass_fraction(U) == 0.0):
        raise HEMMinimalRawFvmDryRunError(
            "initial transported quality must be exactly zero"
        )
    return U


def _dry_run_outcome(detection: HEMRawTransitionDetection) -> DryRunOutcome:
    raw_regions = np.asarray(detection.raw.region).astype(str)
    events = np.asarray(detection.transitions.event).astype(str)
    if np.any(events == "FORBIDDEN_TRANSITION"):
        return "FORBIDDEN_REGION"
    if np.any(raw_regions == "SATURATED_LIQUID_ENDPOINT"):
        return "ENDPOINT_LANDING"
    if np.any(events == "LIQUID_TO_TWO_PHASE_CROSSING"):
        return "OPEN_TWO_PHASE"
    return "ALL_LIQUID"


def _failure_outcome(exc: Exception) -> DryRunOutcome:
    text = f"{type(exc).__name__}: {exc}".lower()
    backend_terms = (
        "coolprop",
        "backend",
        "phase evaluation failed",
        "property evaluation failed",
    )
    return "BACKEND_FAILURE" if any(term in text for term in backend_terms) else "GUARD_FAILURE"


def _build_cell_records(
    *,
    case_id: str,
    grid: UniformGrid,
    initial_U: np.ndarray,
    raw_U: np.ndarray,
    initial_primitive,
    detection: HEMRawTransitionDetection,
) -> tuple[MinimalRawFvmCellRecord, ...]:
    initial_phase = detection.previous.phase_state
    raw_phase = detection.raw.phase_state
    initial_q_transport = np.asarray(vapor_mass_fraction(initial_U), dtype=float)
    raw_q_transport = np.asarray(vapor_mass_fraction(raw_U), dtype=float)
    initial_q_eq = np.asarray(initial_phase.quality, dtype=float)
    raw_q_eq = np.asarray(raw_phase.quality, dtype=float)
    initial_alpha = np.asarray(initial_phase.alpha, dtype=float)
    raw_alpha = np.asarray(raw_phase.alpha, dtype=float)
    initial_p = np.asarray(initial_phase.p, dtype=float)
    raw_p = np.asarray(raw_phase.p, dtype=float)
    initial_T = np.asarray(initial_phase.T, dtype=float)
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
        raise HEMMinimalRawFvmDryRunError(
            "cellwise dry-run evidence returned an incompatible shape"
        )

    records: list[MinimalRawFvmCellRecord] = []
    for index in range(grid.n_cells):
        records.append(
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
        )
    return tuple(records)


def run_one_minimal_raw_fvm_case(
    spec: MinimalFvmDryRunCaseSpec,
    left: DryRunEndpointState,
    right: DryRunEndpointState,
    config: HEMMinimalRawFvmDryRunConfig,
    *,
    eos_factory: DryRunEosFactory = _default_eos_factory,
    phase_evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state,
    transition_detector: RawTransitionDetector = detect_raw_transition_events,
) -> MinimalRawFvmCaseResult:
    """Advance one real FVM step and classify the raw post-step state."""

    grid = UniformGrid(
        PipeGeometry(length_m=config.length_m, diameter_m=config.diameter_m),
        n_cells=config.n_cells,
    )
    initial_U = build_piecewise_liquid_initial_state(
        left,
        right,
        n_cells=config.n_cells,
        interface_cell=config.resolved_interface_cell,
    )
    eos = eos_factory(config.phase_config)
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=initial_U,
        cfl=config.cfl,
        n_ghost=config.n_ghost,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )

    initial_primitive = solver.primitive()
    dt = solver.compute_dt()
    measured_cfl = float(
        np.max((np.abs(initial_primitive.u) + initial_primitive.c) * dt / grid.dx)
    )
    try:
        solver.step(dt)
        raw_U = np.array(solver.U, dtype=float, copy=True)
        detection = transition_detector(
            np.array(initial_U, copy=True),
            np.array(raw_U, copy=True),
            evaluator=phase_evaluator,
            phase_config=config.phase_config,
        )
        if not np.all(np.asarray(detection.previous.region) == "LIQUID_CANDIDATE"):
            raise HEMMinimalRawFvmDryRunError(
                "every initial dry-run cell must be a LIQUID_CANDIDATE"
            )
        outcome = _dry_run_outcome(detection)
        cells = _build_cell_records(
            case_id=spec.case_id,
            grid=grid,
            initial_U=initial_U,
            raw_U=raw_U,
            initial_primitive=initial_primitive,
            detection=detection,
        )
        current_inventory = inventory(raw_U, grid.dx, grid.geometry.area_m2)
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
            dx_m=float(grid.dx),
            target_cfl=float(config.cfl),
            measured_initial_cfl=measured_cfl,
            interface_cell=config.resolved_interface_cell,
            outcome=outcome,
            failure_reason="",
            initial_U=np.array(initial_U, copy=True),
            raw_U=raw_U,
            cells=cells,
            budget_diagnostics=budget,
            fvm_step_exercised=bool(solver.step_count == 1),
        )
    except Exception as exc:
        raw_U = np.array(solver.U, dtype=float, copy=True)
        return MinimalRawFvmCaseResult(
            spec=spec,
            left_state=left,
            right_state=right,
            dt_s=float(dt),
            dx_m=float(grid.dx),
            target_cfl=float(config.cfl),
            measured_initial_cfl=measured_cfl,
            interface_cell=config.resolved_interface_cell,
            outcome=_failure_outcome(exc),
            failure_reason=f"{type(exc).__name__}: {exc}",
            initial_U=np.array(initial_U, copy=True),
            raw_U=raw_U,
            cells=(),
            budget_diagnostics={},
            fvm_step_exercised=bool(solver.step_count == 1),
        )


def run_minimal_raw_fvm_dry_run_matrix(
    config: HEMMinimalRawFvmDryRunConfig | None = None,
    *,
    survey_result: HEMLiquidStatePairSurveyResult | None = None,
    survey_runner: Callable[..., HEMLiquidStatePairSurveyResult] = (
        run_liquid_state_pair_survey
    ),
    eos_factory: DryRunEosFactory = _default_eos_factory,
    phase_evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state,
    transition_detector: RawTransitionDetector = detect_raw_transition_events,
) -> HEMMinimalRawFvmDryRunResult:
    """Run the fixed three-case one-step raw-FVM dry-run matrix."""

    cfg = config or HEMMinimalRawFvmDryRunConfig()
    survey = survey_result or survey_runner(cfg.survey_config)
    by_id = {record.candidate_id: record for record in survey.candidates}
    cases: list[MinimalRawFvmCaseResult] = []
    for spec in cfg.case_specs:
        left = DryRunEndpointState.from_candidate(by_id[spec.left_candidate_id])
        right = DryRunEndpointState.from_candidate(by_id[spec.right_candidate_id])
        cases.append(
            run_one_minimal_raw_fvm_case(
                spec,
                left,
                right,
                cfg,
                eos_factory=eos_factory,
                phase_evaluator=phase_evaluator,
                transition_detector=transition_detector,
            )
        )
    return HEMMinimalRawFvmDryRunResult(
        config=cfg,
        survey_summary=survey.summary(),
        cases=tuple(cases),
    )


def _config_payload(config: HEMMinimalRawFvmDryRunConfig) -> dict[str, object]:
    return {
        "n_cells": config.n_cells,
        "length_m": config.length_m,
        "diameter_m": config.diameter_m,
        "cfl": config.cfl,
        "n_ghost": config.n_ghost,
        "interface_cell": config.resolved_interface_cell,
        "phase_config": asdict(config.phase_config),
        "case_specs": [asdict(spec) for spec in config.case_specs],
    }


def write_minimal_raw_fvm_dry_run_artifacts(
    output_dir: str | Path,
    result: HEMMinimalRawFvmDryRunResult,
) -> dict[str, Path]:
    """Write JSON, CSV, Markdown, and NPZ evidence for the dry-run matrix."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_minimal_raw_fvm_dry_run"
    paths = {
        "json": target / f"{stem}.json",
        "cases_csv": target / f"{stem}_cases.csv",
        "cells_csv": target / f"{stem}_cells.csv",
        "markdown": target / f"{stem}.md",
        "npz": target / f"{stem}.npz",
    }
    case_summaries = [case.summary() for case in result.cases]
    payload = {
        **result.summary(),
        "config": _config_payload(result.config),
        "survey_summary": result.survey_summary,
        "cases": case_summaries,
        "cells": [asdict(cell) for case in result.cases for cell in case.cells],
    }
    paths["json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    case_rows: list[dict[str, object]] = []
    for summary in case_summaries:
        row = dict(summary)
        row["event_counts"] = json.dumps(row["event_counts"], sort_keys=True)
        row["raw_region_counts"] = json.dumps(
            row["raw_region_counts"], sort_keys=True
        )
        row["changed_cell_indices"] = json.dumps(row["changed_cell_indices"])
        row["budget_diagnostics"] = json.dumps(
            row["budget_diagnostics"], sort_keys=True
        )
        case_rows.append(row)
    with paths["cases_csv"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(case_rows[0]))
        writer.writeheader()
        writer.writerows(case_rows)

    cell_rows = [asdict(cell) for case in result.cases for cell in case.cells]
    with paths["cells_csv"].open("w", encoding="utf-8", newline="") as handle:
        if cell_rows:
            writer = csv.DictWriter(handle, fieldnames=list(cell_rows[0]))
            writer.writeheader()
            writer.writerows(cell_rows)
        else:
            handle.write("case_id,cell_index\n")

    lines = [
        "# Stage 7 Minimal Raw FVM Dry Run",
        "",
        "`VERIFICATION ONLY; ONE RAW FVM STEP; NO PROJECTION; NOT FORMAL CROSSING VERIFICATION`",
        "",
        f"- cells: `{result.config.n_cells}`",
        f"- target CFL: `{result.config.cfl}`",
        f"- interface cell: `{result.config.resolved_interface_cell}`",
        f"- raw crossing observed: `{result.summary()['raw_fvm_crossing_observed']}`",
        "",
        "| case | role | outcome | crossing cells | max raw q_eq | measured CFL |",
        "|---|---|---|---:|---:|---:|",
    ]
    for case, summary in zip(result.cases, case_summaries):
        crossing_count = summary["event_counts"]["LIQUID_TO_TWO_PHASE_CROSSING"]
        lines.append(
            "| {case} | {role} | {outcome} | {crossings} | {q:.12g} | {cfl:.12g} |".format(
                case=case.spec.case_id,
                role=case.spec.role,
                outcome=case.outcome,
                crossings=crossing_count,
                q=float(summary["max_raw_equilibrium_quality"]),
                cfl=case.measured_initial_cfl,
            )
        )
    lines.extend(
        [
            "",
            "## Scope boundary",
            "",
            "```text",
            "FvmSolver.step exercised: true",
            "raw rho/e transition classification: true",
            "quality projection: false",
            "post-projection accepted EOS: false",
            "Case A frozen: false",
            "Case B frozen: false",
            "physical Validation: false",
            "production HEM: false",
            "design use: false",
            "```",
            "",
        ]
    )
    paths["markdown"].write_text("\n".join(lines), encoding="utf-8")

    arrays: dict[str, np.ndarray] = {}
    for case in result.cases:
        key = case.spec.case_id.replace("-", "_")
        arrays[f"{key}_initial_U"] = np.asarray(case.initial_U)
        arrays[f"{key}_raw_U"] = np.asarray(case.raw_U)
        arrays[f"{key}_initial_regions"] = np.asarray(
            [cell.initial_region for cell in case.cells], dtype="<U36"
        )
        arrays[f"{key}_raw_regions"] = np.asarray(
            [cell.raw_region for cell in case.cells], dtype="<U36"
        )
        arrays[f"{key}_events"] = np.asarray(
            [cell.transition_event for cell in case.cells], dtype="<U40"
        )
    np.savez_compressed(paths["npz"], **arrays)
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--n-cells", type=int, default=8)
    parser.add_argument("--cfl", type=float, default=0.20)
    parser.add_argument("--length-m", type=float, default=1.0)
    parser.add_argument("--diameter-m", type=float, default=0.10)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = HEMMinimalRawFvmDryRunConfig(
        n_cells=args.n_cells,
        cfl=args.cfl,
        length_m=args.length_m,
        diameter_m=args.diameter_m,
    )
    result = run_minimal_raw_fvm_dry_run_matrix(config)
    files = write_minimal_raw_fvm_dry_run_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in files.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
