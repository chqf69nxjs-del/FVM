"""Verification-only LCO2 pipeline depressurization first-crossing runner.

Increment 2 connects the reviewed prescribed-subcooled right boundary to the fixed
1.0 m / 32-cell first-order Rusanov prototype.  It runs the fixed 5 -> 2/3/4 MPa
matrix, classifies raw rho/e transitions before projection, applies the existing
quality projection and mixed accepted-state EOS, and retains separate boundary and
projection vapor accounts.

The module is deliberately orchestration-only.  It does not change the production
solver, flux, CFL algorithm, EOS, phase classifier, acoustic closure, projection,
or any tolerance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Sequence

import numpy as np

from .boundary import ConstantPressure, LinearPressureRamp, ReflectiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .hem_equilibrium_quality_sync import HEMEquilibriumQualitySyncConfig
from .hem_liquid_to_two_phase_crossing import (
    HEMBoundaryPhaseEvaluator,
    HEMRawTransitionDetection,
    detect_raw_transition_events,
)
from .hem_liquid_to_two_phase_minimal_fvm_dry_run import (
    DryRunEndpointState,
    HEMMinimalRawFvmDryRunConfig,
    MinimalFvmDryRunCaseSpec,
    MinimalRawFvmCaseResult,
    MinimalRawFvmCellRecord,
)
from .hem_liquid_to_two_phase_projected_fvm_dry_run import (
    HEMProjectedFvmDryRunConfig,
    ProjectedFvmCaseResult,
    run_one_projected_fvm_case,
)
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_phase_classification import (
    HEMPhaseClassificationConfig,
    evaluate_coolprop_hem_phase_state,
)
from .hem_pipeline_depressurization_boundary import (
    HEMBoundaryPathCaseSpec,
    HEMBoundaryPathPreflightResult,
    HEMBoundaryPathSampleRecord,
    HEMPrescribedBoundaryError,
    HEMPrescribedBoundaryState,
    VerificationHEMPrescribedSubcooledOutletBoundary,
    VerificationHEMPrescribedSubcooledStateProvider,
)
from .phase_budget import PhaseChangeBudgetTracker
from .solver import FvmSolver
from .state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    N_VARS,
    internal_energy,
    inventory,
    make_conserved,
    vapor_mass_fraction,
    velocity,
)

PipelineRunOutcome = Literal[
    "ACCEPTED_FIRST_CROSSING",
    "NO_CROSSING_WITHIN_HORIZON",
    "ENDPOINT_LANDING",
    "FORBIDDEN_TRANSITION",
    "REVERSE_FLOW_GUARD",
    "GUARD_FAILURE",
    "BACKEND_FAILURE",
]


class HEMPipelineDepressurizationError(RuntimeError):
    """Raised when the fixed Increment 2 contract cannot be applied safely."""


@dataclass(frozen=True)
class PipelineDepressurizationCaseSpec:
    """One fixed boundary-driven pipeline case."""

    case_id: str
    role: str
    final_boundary_pressure_pa: float

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.role.strip():
            raise ValueError("case_id and role must not be empty")
        if (
            not np.isfinite(self.final_boundary_pressure_pa)
            or self.final_boundary_pressure_pa <= 0.0
        ):
            raise ValueError("final_boundary_pressure_pa must be finite and positive")


FIXED_PIPELINE_DEPRESSURIZATION_CASES: tuple[
    PipelineDepressurizationCaseSpec, ...
] = (
    PipelineDepressurizationCaseSpec(
        case_id="pipeline_crossing_candidate_p5m5_to_p2m5",
        role="first_crossing_candidate",
        final_boundary_pressure_pa=2.0e6,
    ),
    PipelineDepressurizationCaseSpec(
        case_id="pipeline_moderate_diagnostic_p5m5_to_p3m5",
        role="moderate_diagnostic",
        final_boundary_pressure_pa=3.0e6,
    ),
    PipelineDepressurizationCaseSpec(
        case_id="pipeline_liquid_control_p5m5_to_p4m5",
        role="liquid_negative_control",
        final_boundary_pressure_pa=4.0e6,
    ),
)


@dataclass(frozen=True)
class HEMPipelineDepressurizationConfig:
    """Fixed geometry, numerics, stop rules, and software tolerances."""

    length_m: float = 1.0
    diameter_m: float = 0.10
    n_cells: int = 32
    n_ghost: int = 2
    cfl: float = 0.10
    initial_pressure_pa: float = 5.0e6
    subcooling_K: float = 5.0
    ramp_acoustic_time_ratio: float = 1.0
    horizon_acoustic_time_ratio: float = 3.0
    max_steps: int = 2000
    preflight_sample_count: int = 65
    pressure_drop_evidence_relative: float = 1.0e-6
    crossing_evidence_min_quality: float = 1.0e-6
    phase_config: HEMPhaseClassificationConfig = field(
        default_factory=HEMPhaseClassificationConfig
    )
    projection_config: HEMEquilibriumQualitySyncConfig = field(
        default_factory=HEMEquilibriumQualitySyncConfig
    )
    accepted_state_quality_tolerance: float = 1.0e-10
    mass_budget_relative_tolerance: float = 1.0e-10
    mass_budget_absolute_tolerance_kg: float = 1.0e-12
    momentum_budget_relative_tolerance: float = 1.0e-10
    momentum_budget_absolute_tolerance_kg_m_s: float = 1.0e-10
    energy_budget_relative_tolerance: float = 1.0e-10
    energy_budget_absolute_tolerance_J: float = 1.0e-6
    vapor_budget_absolute_tolerance_kg: float = 1.0e-12

    def __post_init__(self) -> None:
        if self.length_m != 1.0 or self.diameter_m != 0.10:
            raise ValueError("Increment 2 geometry is fixed at 1.0 m x 0.10 m")
        if self.n_cells != 32 or self.n_ghost != 2:
            raise ValueError("Increment 2 mesh is fixed at 32 cells and 2 ghosts")
        if self.cfl != 0.10:
            raise ValueError("Increment 2 CFL is fixed at 0.10")
        if self.initial_pressure_pa != 5.0e6 or self.subcooling_K != 5.0:
            raise ValueError("Increment 2 initial state is fixed at 5 MPa / 5 K")
        if (
            self.ramp_acoustic_time_ratio != 1.0
            or self.horizon_acoustic_time_ratio != 3.0
        ):
            raise ValueError("Increment 2 time-scale ratios are fixed at 1 and 3")
        if self.max_steps != 2000 or self.preflight_sample_count != 65:
            raise ValueError("Increment 2 limits are fixed at 2000 steps and 65 samples")
        fixed_scalars = (
            ("pressure_drop_evidence_relative", self.pressure_drop_evidence_relative, 1.0e-6),
            ("crossing_evidence_min_quality", self.crossing_evidence_min_quality, 1.0e-6),
            ("accepted_state_quality_tolerance", self.accepted_state_quality_tolerance, 1.0e-10),
            ("mass_budget_relative_tolerance", self.mass_budget_relative_tolerance, 1.0e-10),
            ("mass_budget_absolute_tolerance_kg", self.mass_budget_absolute_tolerance_kg, 1.0e-12),
            ("momentum_budget_relative_tolerance", self.momentum_budget_relative_tolerance, 1.0e-10),
            ("momentum_budget_absolute_tolerance_kg_m_s", self.momentum_budget_absolute_tolerance_kg_m_s, 1.0e-10),
            ("energy_budget_relative_tolerance", self.energy_budget_relative_tolerance, 1.0e-10),
            ("energy_budget_absolute_tolerance_J", self.energy_budget_absolute_tolerance_J, 1.0e-6),
            ("vapor_budget_absolute_tolerance_kg", self.vapor_budget_absolute_tolerance_kg, 1.0e-12),
        )
        for name, value, expected in fixed_scalars:
            if value != expected:
                raise ValueError(
                    f"Increment 2 {name} is fixed at {expected!r}; received {value!r}"
                )
        if self.phase_config != HEMPhaseClassificationConfig():
            raise ValueError("Increment 2 phase_config is fixed by the PR #74 contract")
        if self.projection_config != HEMEquilibriumQualitySyncConfig():
            raise ValueError("Increment 2 projection_config is fixed by the PR #74 contract")
        if (
            not np.isfinite(self.pressure_drop_evidence_relative)
            or self.pressure_drop_evidence_relative <= 0.0
        ):
            raise ValueError("pressure-drop evidence threshold must be positive")
        if (
            not np.isfinite(self.crossing_evidence_min_quality)
            or not 0.0 < self.crossing_evidence_min_quality < 1.0
        ):
            raise ValueError("crossing evidence quality must lie in (0, 1)")
        if (
            self.accepted_state_quality_tolerance
            < self.projection_config.activation_tolerance
        ):
            raise ValueError(
                "accepted-state quality tolerance must not be tighter than projection"
            )
        for name, value in (
            ("mass_budget_relative_tolerance", self.mass_budget_relative_tolerance),
            (
                "mass_budget_absolute_tolerance_kg",
                self.mass_budget_absolute_tolerance_kg,
            ),
            (
                "momentum_budget_relative_tolerance",
                self.momentum_budget_relative_tolerance,
            ),
            (
                "momentum_budget_absolute_tolerance_kg_m_s",
                self.momentum_budget_absolute_tolerance_kg_m_s,
            ),
            ("energy_budget_relative_tolerance", self.energy_budget_relative_tolerance),
            (
                "energy_budget_absolute_tolerance_J",
                self.energy_budget_absolute_tolerance_J,
            ),
            (
                "vapor_budget_absolute_tolerance_kg",
                self.vapor_budget_absolute_tolerance_kg,
            ),
        ):
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")

    @property
    def dx_m(self) -> float:
        return self.length_m / self.n_cells

    @property
    def area_m2(self) -> float:
        return math.pi * self.diameter_m**2 / 4.0

    def projected_config(self) -> HEMProjectedFvmDryRunConfig:
        raw = HEMMinimalRawFvmDryRunConfig(
            n_cells=self.n_cells,
            length_m=self.length_m,
            diameter_m=self.diameter_m,
            cfl=self.cfl,
            n_ghost=self.n_ghost,
            phase_config=self.phase_config,
        )
        return HEMProjectedFvmDryRunConfig(
            raw_config=raw,
            projection_config=self.projection_config,
            accepted_state_quality_tolerance=self.accepted_state_quality_tolerance,
            vapor_budget_absolute_tolerance_kg=self.vapor_budget_absolute_tolerance_kg,
        )


@dataclass(frozen=True)
class PipelineStepRecord:
    """Compact step-level transition, boundary, and budget evidence."""

    case_id: str
    step_index: int
    time_before_s: float
    dt_s: float
    time_after_s: float
    boundary_pressure_pa: float | None
    boundary_temperature_K: float | None
    boundary_rho_kg_m3: float | None
    boundary_e_j_kg: float | None
    boundary_equilibrium_quality: float | None
    boundary_void_fraction: float | None
    boundary_sound_speed_m_s: float | None
    boundary_region: str
    reverse_flow_fallback_count: int
    raw_outcome: str
    projected_outcome: str
    crossing_cell_indices: tuple[int, ...]
    first_projection_cell_indices: tuple[int, ...]
    second_projection_cell_indices: tuple[int, ...]
    max_raw_equilibrium_quality: float
    max_post_quality_mismatch: float
    pressure_min_pa: float | None
    pressure_max_pa: float | None
    left_mass_flux_rate_kg_s: float
    right_mass_flux_rate_kg_s: float
    left_energy_flux_rate_W: float
    right_energy_flux_rate_W: float
    boundary_vapor_step_kg: float
    projection_vapor_step_kg: float
    raw_boundary_vapor_residual_kg: float
    projection_source_consistency_residual_kg: float
    combined_vapor_balance_residual_kg: float
    state_sha256: str


@dataclass(frozen=True)
class PipelineCellRecord:
    """Cellwise raw and accepted evidence for one step."""

    case_id: str
    step_index: int
    time_s: float
    cell_index: int
    cell_center_m: float
    distance_from_outlet_m: float
    previous_region: str
    raw_region: str
    post_region: str
    transition_event: str
    rho_raw_kg_m3: float
    velocity_raw_m_s: float
    e_raw_j_kg: float
    pressure_raw_pa: float
    temperature_raw_K: float
    q_transport_raw: float
    q_equilibrium: float
    q_post: float
    alpha_post: float | None
    sound_speed_post_m_s: float | None
    first_projection_applied: bool
    second_projection_applied: bool
    relative_pressure_drop: float | None
    first_pressure_drop_arrival_time_s: float | None


@dataclass(frozen=True)
class PipelineCaseResult:
    """One fixed pipeline case, including partial evidence on fail-fast outcomes."""

    case: PipelineDepressurizationCaseSpec
    config: HEMPipelineDepressurizationConfig
    initial_state: HEMPrescribedBoundaryState
    initial_acoustic_time_s: float
    ramp_duration_s: float
    maximum_horizon_s: float
    preflight: HEMBoundaryPathPreflightResult
    outcome: PipelineRunOutcome
    failure_reason: str
    step_count: int
    final_time_s: float
    crossing_step: int | None
    crossing_time_s: float | None
    crossing_cell_indices: tuple[int, ...]
    crossing_distances_from_outlet_m: tuple[float, ...]
    maximum_crossing_quality: float
    reverse_flow_fallback_count: int
    pressure_drop_arrival_times_s: tuple[float | None, ...]
    steps: tuple[PipelineStepRecord, ...]
    cells: tuple[PipelineCellRecord, ...]
    boundary_budget_diagnostics: dict[str, float]
    phase_budget_diagnostics: dict[str, float]
    final_state_sha256: str
    run_signature_sha256: str
    time_history_s: np.ndarray
    pressure_history_pa: np.ndarray
    accepted_state_history: np.ndarray

    @property
    def completed_without_guard_failure(self) -> bool:
        return self.outcome in {
            "ACCEPTED_FIRST_CROSSING",
            "NO_CROSSING_WITHIN_HORIZON",
        }

    def summary(self) -> dict[str, object]:
        return {
            "case_id": self.case.case_id,
            "role": self.case.role,
            "final_boundary_pressure_pa": self.case.final_boundary_pressure_pa,
            "outcome": self.outcome,
            "failure_reason": self.failure_reason,
            "step_count": self.step_count,
            "final_time_s": self.final_time_s,
            "initial_acoustic_time_s": self.initial_acoustic_time_s,
            "ramp_duration_s": self.ramp_duration_s,
            "maximum_horizon_s": self.maximum_horizon_s,
            "preflight_accepted_sample_count": len(self.preflight.records),
            "crossing_step": self.crossing_step,
            "crossing_time_s": self.crossing_time_s,
            "crossing_cell_indices": list(self.crossing_cell_indices),
            "crossing_distances_from_outlet_m": list(
                self.crossing_distances_from_outlet_m
            ),
            "maximum_crossing_quality": self.maximum_crossing_quality,
            "reverse_flow_fallback_count": self.reverse_flow_fallback_count,
            "pressure_drop_arrival_times_s": list(
                self.pressure_drop_arrival_times_s
            ),
            "boundary_budget_diagnostics": dict(self.boundary_budget_diagnostics),
            "phase_budget_diagnostics": dict(self.phase_budget_diagnostics),
            "final_state_sha256": self.final_state_sha256,
            "run_signature_sha256": self.run_signature_sha256,
            "completed_without_guard_failure": self.completed_without_guard_failure,
        }


def _gate_p2_passes(cases: Sequence[PipelineCaseResult]) -> bool:
    """Return the reviewed Gate P2 decision for the fixed three-case matrix."""

    by_id = {case.case.case_id: case for case in cases}
    expected_ids = {case.case_id for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES}
    if set(by_id) != expected_ids:
        return False
    accepted_or_honest_no_crossing = {
        "ACCEPTED_FIRST_CROSSING",
        "NO_CROSSING_WITHIN_HORIZON",
    }
    strong = by_id["pipeline_crossing_candidate_p5m5_to_p2m5"]
    moderate = by_id["pipeline_moderate_diagnostic_p5m5_to_p3m5"]
    control = by_id["pipeline_liquid_control_p5m5_to_p4m5"]
    return bool(
        strong.outcome in accepted_or_honest_no_crossing
        and moderate.outcome in accepted_or_honest_no_crossing
        and control.outcome == "NO_CROSSING_WITHIN_HORIZON"
        and all(case.reverse_flow_fallback_count == 0 for case in cases)
    )


@dataclass(frozen=True)
class HEMPipelineDepressurizationResult:
    """Fixed 5 -> 2/3/4 MPa Increment 2 matrix."""

    config: HEMPipelineDepressurizationConfig
    cases: tuple[PipelineCaseResult, ...]

    def summary(self) -> dict[str, object]:
        outcome_counts = {
            outcome: sum(case.outcome == outcome for case in self.cases)
            for outcome in (
                "ACCEPTED_FIRST_CROSSING",
                "NO_CROSSING_WITHIN_HORIZON",
                "ENDPOINT_LANDING",
                "FORBIDDEN_TRANSITION",
                "REVERSE_FLOW_GUARD",
                "GUARD_FAILURE",
                "BACKEND_FAILURE",
            )
        }
        by_id = {case.case.case_id: case for case in self.cases}
        crossing_candidate = by_id.get(
            "pipeline_crossing_candidate_p5m5_to_p2m5"
        )
        liquid_control = by_id.get("pipeline_liquid_control_p5m5_to_p4m5")
        return {
            "schema_version": (
                "stage7_lco2_hem_pipeline_depressurization_increment2_v1"
            ),
            "scope": "verification_only",
            "case_count": len(self.cases),
            "outcome_counts": outcome_counts,
            "case_ids": [case.case.case_id for case in self.cases],
            "all_fixed_cases_completed": bool(
                self.cases
                and all(case.completed_without_guard_failure for case in self.cases)
            ),
            "fixed_matrix_explicit_outcomes_retained": bool(
                self.cases and all(case.step_count > 0 for case in self.cases)
            ),
            "gate_p2_passed": _gate_p2_passes(self.cases),
            "gate_p2_rule": "4_mpa_control_must_finish_no_crossing_within_horizon",
            "four_mpa_control_outcome": (
                liquid_control.outcome if liquid_control is not None else None
            ),
            "four_mpa_control_remained_all_liquid": bool(
                liquid_control is not None
                and liquid_control.outcome == "NO_CROSSING_WITHIN_HORIZON"
            ),
            "subthreshold_crossing_case_ids": [
                case.case.case_id
                for case in self.cases
                if case.outcome == "GUARD_FAILURE"
                and case.crossing_step is not None
                and 0.0 < case.maximum_crossing_quality
                < self.config.crossing_evidence_min_quality
            ],
            "two_mpa_candidate_outcome": (
                crossing_candidate.outcome if crossing_candidate is not None else None
            ),
            "pipeline_depressurization_executed": any(
                case.step_count > 0 for case in self.cases
            ),
            "first_crossing_stop_implemented": True,
            "boundary_and_projection_vapor_separated": True,
            "frozen_case_ab_regression_required": True,
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            "production_hem_activation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "two_phase_acoustic_accuracy_band_approved": False,
        }


CaseRunner = Callable[
    [
        PipelineDepressurizationCaseSpec,
        HEMPipelineDepressurizationConfig,
    ],
    PipelineCaseResult,
]


def _state_sha256(U: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(U, dtype="<f8"))
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _failure_outcome(exc: Exception) -> PipelineRunOutcome:
    if isinstance(exc, HEMPrescribedBoundaryError):
        return (
            "BACKEND_FAILURE"
            if exc.category == "PROPERTY_BACKEND_FAILURE"
            else "GUARD_FAILURE"
        )
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


def _raw_outcome(detection: HEMRawTransitionDetection) -> str:
    raw_regions = np.asarray(detection.raw.region).astype(str)
    events = np.asarray(detection.transitions.event).astype(str)
    if np.any(events == "FORBIDDEN_TRANSITION") or np.any(
        events == "REVERSE_TRANSITION"
    ):
        return "FORBIDDEN_REGION"
    if np.any(
        np.isin(
            raw_regions,
            ["SATURATED_VAPOR_ENDPOINT", "VAPOR_CANDIDATE"],
        )
    ):
        return "FORBIDDEN_REGION"
    if np.any(events == "BOUNDARY_TOUCH") or np.any(
        raw_regions == "SATURATED_LIQUID_ENDPOINT"
    ):
        return "ENDPOINT_LANDING"
    if np.any(events == "LIQUID_TO_TWO_PHASE_CROSSING"):
        return "OPEN_TWO_PHASE"
    return "ALL_LIQUID"


def _raw_event_stop(
    *,
    reverse_flow_delta: int,
    raw_outcome: str,
) -> PipelineRunOutcome | None:
    if reverse_flow_delta > 0:
        return "REVERSE_FLOW_GUARD"
    if raw_outcome == "FORBIDDEN_REGION":
        return "FORBIDDEN_TRANSITION"
    if raw_outcome == "ENDPOINT_LANDING":
        return "ENDPOINT_LANDING"
    return None


def _budget_limit(
    *,
    absolute: float,
    relative: float,
    actual: float,
    expected: float,
    reference: float,
) -> float:
    scale = max(abs(actual), abs(expected), abs(reference), 1.0)
    return max(absolute, relative * scale)


def _check_budget_residual(
    *,
    name: str,
    residual: float,
    absolute: float,
    relative: float,
    actual: float,
    expected: float,
    reference: float,
) -> None:
    limit = _budget_limit(
        absolute=absolute,
        relative=relative,
        actual=actual,
        expected=expected,
        reference=reference,
    )
    if not np.isfinite(residual) or abs(residual) > limit:
        raise HEMPipelineDepressurizationError(
            f"{name} residual exceeds tolerance: residual={residual}, limit={limit}"
        )


def _run_boundary_preflight(
    *,
    case: PipelineDepressurizationCaseSpec,
    provider: VerificationHEMPrescribedSubcooledStateProvider,
    ramp_duration_s: float,
    config: HEMPipelineDepressurizationConfig,
) -> HEMBoundaryPathPreflightResult:
    path_case = HEMBoundaryPathCaseSpec(
        case_id=case.case_id,
        role=case.role,
        initial_pressure_pa=config.initial_pressure_pa,
        final_pressure_pa=case.final_boundary_pressure_pa,
        subcooling_K=config.subcooling_K,
        sample_count=config.preflight_sample_count,
    )
    records: list[HEMBoundaryPathSampleRecord] = []
    denominator = config.preflight_sample_count - 1
    for sample_index in range(config.preflight_sample_count):
        fraction = sample_index / denominator
        time_s = fraction * ramp_duration_s
        state = provider.state_at(time_s)
        expected_pressure = (
            (1.0 - fraction) * config.initial_pressure_pa
            + fraction * case.final_boundary_pressure_pa
        )
        if not np.isclose(
            state.pressure_requested_pa,
            expected_pressure,
            rtol=0.0,
            atol=1.0e-8,
        ):
            raise HEMPipelineDepressurizationError(
                "boundary schedule did not preserve the fixed pressure path"
            )
        records.append(
            HEMBoundaryPathSampleRecord(
                case_id=case.case_id,
                role=case.role,
                sample_index=sample_index,
                fraction=fraction,
                pressure_requested_pa=state.pressure_requested_pa,
                saturation_temperature_K=state.saturation_temperature_K,
                temperature_requested_K=state.temperature_requested_K,
                rho_kg_m3=state.rho_kg_m3,
                e_j_kg=state.e_j_kg,
                pressure_recovered_pa=state.pressure_recovered_pa,
                temperature_recovered_K=state.temperature_recovered_K,
                equilibrium_quality=state.equilibrium_quality,
                void_fraction=state.void_fraction,
                raw_phase=state.raw_phase,
                phase_class=state.phase_class,
                boundary_region=state.boundary_region,
                scope_status=state.scope_status,
                sound_speed_m_s=state.sound_speed_m_s,
                mixed_eos_accepted=state.mixed_eos_accepted,
                accepted=True,
                failure_reason="",
            )
        )
    return HEMBoundaryPathPreflightResult(
        case=path_case,
        records=tuple(records),
        provider_diagnostics=dict(provider.diagnostics()),
    )


def _minimal_raw_cells(
    *,
    case_id: str,
    grid: UniformGrid,
    previous_U: np.ndarray,
    raw_U: np.ndarray,
    previous_primitive,
    detection: HEMRawTransitionDetection,
) -> tuple[MinimalRawFvmCellRecord, ...]:
    previous_phase = detection.previous.phase_state
    raw_phase = detection.raw.phase_state
    previous_q_transport = np.asarray(vapor_mass_fraction(previous_U), dtype=float)
    raw_q_transport = np.asarray(vapor_mass_fraction(raw_U), dtype=float)
    previous_q_eq = np.asarray(previous_phase.quality, dtype=float)
    raw_q_eq = np.asarray(raw_phase.quality, dtype=float)
    previous_alpha = np.asarray(previous_phase.alpha, dtype=float)
    raw_alpha = np.asarray(raw_phase.alpha, dtype=float)
    previous_p = np.asarray(previous_phase.p, dtype=float)
    raw_p = np.asarray(raw_phase.p, dtype=float)
    previous_T = np.asarray(previous_phase.T, dtype=float)
    raw_T = np.asarray(raw_phase.T, dtype=float)
    previous_regions = np.asarray(detection.previous.region).astype(str)
    raw_regions = np.asarray(detection.raw.region).astype(str)
    events = np.asarray(detection.transitions.event).astype(str)
    raw_e = np.asarray(internal_energy(raw_U), dtype=float)
    raw_u = np.asarray(velocity(raw_U), dtype=float)
    expected = (grid.n_cells,)
    arrays = (
        previous_q_transport,
        raw_q_transport,
        previous_q_eq,
        raw_q_eq,
        previous_alpha,
        raw_alpha,
        previous_p,
        raw_p,
        previous_T,
        raw_T,
        previous_regions,
        raw_regions,
        events,
        raw_e,
        raw_u,
    )
    if any(np.asarray(value).shape != expected for value in arrays):
        raise HEMPipelineDepressurizationError(
            "raw cell evidence returned an incompatible shape"
        )
    return tuple(
        MinimalRawFvmCellRecord(
            case_id=case_id,
            cell_index=index,
            cell_center_m=float(grid.cell_centers[index]),
            initial_region=str(previous_regions[index]),
            raw_region=str(raw_regions[index]),
            transition_event=str(events[index]),
            rho_initial_kg_m3=float(previous_U[index, IDX_RHO]),
            rho_raw_kg_m3=float(raw_U[index, IDX_RHO]),
            velocity_initial_m_s=float(previous_primitive.u[index]),
            velocity_raw_m_s=float(raw_u[index]),
            e_initial_j_kg=float(previous_primitive.e[index]),
            e_raw_j_kg=float(raw_e[index]),
            pressure_initial_pa=float(previous_p[index]),
            pressure_raw_pa=float(raw_p[index]),
            temperature_initial_K=float(previous_T[index]),
            temperature_raw_K=float(raw_T[index]),
            q_transport_initial=float(previous_q_transport[index]),
            q_transport_raw=float(raw_q_transport[index]),
            q_equilibrium_initial=float(previous_q_eq[index]),
            q_equilibrium_raw=float(raw_q_eq[index]),
            alpha_initial=float(previous_alpha[index]),
            alpha_raw=float(raw_alpha[index]),
        )
        for index in range(grid.n_cells)
    )


def _incremental_boundary_budget(
    *,
    previous_inventory: dict[str, float],
    raw_inventory: dict[str, float],
    step_left: np.ndarray,
    step_right: np.ndarray,
    config: HEMPipelineDepressurizationConfig,
) -> dict[str, float]:
    net = np.asarray(step_left, dtype=float) - np.asarray(step_right, dtype=float)
    if net.shape != (N_VARS,) or not np.all(np.isfinite(net)):
        raise HEMPipelineDepressurizationError(
            "incremental boundary contribution must be a finite N_VARS vector"
        )
    keys = (
        (IDX_RHO, "mass", "mass_total", config.mass_budget_absolute_tolerance_kg,
         config.mass_budget_relative_tolerance),
        (
            IDX_MOM,
            "momentum",
            "momentum_total",
            config.momentum_budget_absolute_tolerance_kg_m_s,
            config.momentum_budget_relative_tolerance,
        ),
        (
            IDX_RHOE,
            "energy",
            "energy_total",
            config.energy_budget_absolute_tolerance_J,
            config.energy_budget_relative_tolerance,
        ),
        (
            IDX_RHO_XV,
            "vapor_mass",
            "vapor_mass_total",
            config.vapor_budget_absolute_tolerance_kg,
            0.0,
        ),
    )
    out: dict[str, float] = {}
    for idx, name, inv_key, absolute, relative in keys:
        before = float(previous_inventory[inv_key])
        actual = float(raw_inventory[inv_key])
        contribution = float(net[idx])
        expected = before + contribution
        residual = actual - expected
        _check_budget_residual(
            name=f"raw incremental {name}",
            residual=residual,
            absolute=absolute,
            relative=relative,
            actual=actual,
            expected=expected,
            reference=before,
        )
        out[f"budget_{name}_net_boundary"] = contribution
        out[f"budget_{name}_expected_total"] = expected
        out[f"budget_{name}_residual"] = residual
    return out


def _validate_cumulative_budgets(
    *,
    solver: FvmSolver,
    phase_tracker: PhaseChangeBudgetTracker,
    initial_inventory: dict[str, float],
    latest_projected_budget: dict[str, float],
    config: HEMPipelineDepressurizationConfig,
) -> tuple[dict[str, float], dict[str, float]]:
    if solver.boundary_budget is None:
        raise HEMPipelineDepressurizationError("boundary budget tracker is required")
    current = inventory(
        solver.U,
        solver.grid.dx,
        solver.grid.geometry.area_m2,
    )
    boundary = solver.boundary_budget.diagnostics(current)
    for name, inv_key, absolute, relative in (
        (
            "mass",
            "mass_total",
            config.mass_budget_absolute_tolerance_kg,
            config.mass_budget_relative_tolerance,
        ),
        (
            "momentum",
            "momentum_total",
            config.momentum_budget_absolute_tolerance_kg_m_s,
            config.momentum_budget_relative_tolerance,
        ),
        (
            "energy",
            "energy_total",
            config.energy_budget_absolute_tolerance_J,
            config.energy_budget_relative_tolerance,
        ),
    ):
        _check_budget_residual(
            name=f"cumulative boundary {name}",
            residual=float(boundary[f"budget_{name}_residual"]),
            absolute=absolute,
            relative=relative,
            actual=float(current[inv_key]),
            expected=float(boundary[f"budget_{name}_expected_total"]),
            reference=float(initial_inventory[inv_key]),
        )
    if (
        abs(float(solver.boundary_budget.cumulative_left[IDX_RHO]))
        > config.mass_budget_absolute_tolerance_kg
    ):
        raise HEMPipelineDepressurizationError(
            "reflective left boundary cumulative mass flux is non-zero"
        )
    if (
        abs(float(solver.boundary_budget.cumulative_left[IDX_RHOE]))
        > config.energy_budget_absolute_tolerance_J
    ):
        raise HEMPipelineDepressurizationError(
            "reflective left boundary cumulative energy flux is non-zero"
        )

    phase = phase_tracker.diagnostics(
        current,
        boundary_budget=solver.boundary_budget,
    )
    if (
        abs(float(phase["phase_vapor_mass_balance_residual_kg"]))
        > config.vapor_budget_absolute_tolerance_kg
    ):
        raise HEMPipelineDepressurizationError(
            "combined boundary-plus-projection vapor budget does not close"
        )
    for key in (
        "projection_source_consistency_residual_kg",
        "combined_post_vapor_balance_residual_kg",
    ):
        if key in latest_projected_budget and (
            abs(float(latest_projected_budget[key]))
            > config.vapor_budget_absolute_tolerance_kg
        ):
            raise HEMPipelineDepressurizationError(
                f"projected step vapor budget does not close: {key}"
            )

    boundary_out = {
        str(key): float(value) for key, value in boundary.items()
    }
    boundary_out["boundary_vapor_transport_cumulative_kg"] = float(
        solver.boundary_budget.cumulative_left[IDX_RHO_XV]
        - solver.boundary_budget.cumulative_right[IDX_RHO_XV]
    )
    phase_out = {str(key): float(value) for key, value in phase.items()}
    return boundary_out, phase_out


def _pipeline_cell_records(
    *,
    case_id: str,
    step_index: int,
    time_s: float,
    grid: UniformGrid,
    detection: HEMRawTransitionDetection,
    projected: ProjectedFvmCaseResult | None,
    pressure_initial_pa: float,
    arrival_times: Sequence[float | None],
) -> tuple[PipelineCellRecord, ...]:
    raw_U = (
        projected.raw_case.raw_U
        if projected is not None
        else np.empty((0, N_VARS), dtype=float)
    )
    if projected is not None:
        cells_by_index = {cell.cell_index: cell for cell in projected.cells}
        raw_e = np.asarray(internal_energy(raw_U), dtype=float)
        raw_u = np.asarray(velocity(raw_U), dtype=float)
        raw_p = np.asarray(detection.raw.phase_state.p, dtype=float)
        raw_T = np.asarray(detection.raw.phase_state.T, dtype=float)
        q_raw = np.asarray(vapor_mass_fraction(raw_U), dtype=float)
        previous_regions = np.asarray(detection.previous.region).astype(str)
        raw_regions = np.asarray(detection.raw.region).astype(str)
        events = np.asarray(detection.transitions.event).astype(str)
        records = []
        for index in range(grid.n_cells):
            cell = cells_by_index[index]
            relative_drop = (
                pressure_initial_pa - float(cell.post_pressure_pa)
            ) / pressure_initial_pa
            records.append(
                PipelineCellRecord(
                    case_id=case_id,
                    step_index=step_index,
                    time_s=time_s,
                    cell_index=index,
                    cell_center_m=float(grid.cell_centers[index]),
                    distance_from_outlet_m=float(
                        grid.geometry.length_m - grid.cell_centers[index]
                    ),
                    previous_region=str(previous_regions[index]),
                    raw_region=str(raw_regions[index]),
                    post_region=cell.post_region,
                    transition_event=str(events[index]),
                    rho_raw_kg_m3=float(raw_U[index, IDX_RHO]),
                    velocity_raw_m_s=float(raw_u[index]),
                    e_raw_j_kg=float(raw_e[index]),
                    pressure_raw_pa=float(raw_p[index]),
                    temperature_raw_K=float(raw_T[index]),
                    q_transport_raw=float(q_raw[index]),
                    q_equilibrium=float(cell.q_equilibrium),
                    q_post=float(cell.q_after_first_projection),
                    alpha_post=float(cell.post_void_fraction),
                    sound_speed_post_m_s=float(cell.post_sound_speed_m_s),
                    first_projection_applied=bool(
                        cell.first_projection_applied
                    ),
                    second_projection_applied=bool(
                        cell.second_projection_applied
                    ),
                    relative_pressure_drop=float(relative_drop),
                    first_pressure_drop_arrival_time_s=arrival_times[index],
                )
            )
        return tuple(records)
    return ()


def _make_signature(
    *,
    case: PipelineDepressurizationCaseSpec,
    outcome: PipelineRunOutcome,
    step_count: int,
    final_time_s: float,
    crossing_step: int | None,
    crossing_time_s: float | None,
    crossing_cells: Sequence[int],
    max_crossing_quality: float,
    reverse_flow_count: int,
    final_state_sha256: str,
    boundary_budget: dict[str, float],
    phase_budget: dict[str, float],
) -> str:
    payload = {
        "case_id": case.case_id,
        "outcome": outcome,
        "step_count": step_count,
        "final_time_s": float(final_time_s).hex(),
        "crossing_step": crossing_step,
        "crossing_time_s": (
            None if crossing_time_s is None else float(crossing_time_s).hex()
        ),
        "crossing_cells": [int(value) for value in crossing_cells],
        "max_crossing_quality": float(max_crossing_quality).hex(),
        "reverse_flow_count": reverse_flow_count,
        "final_state_sha256": final_state_sha256,
        "mass_residual": float(
            boundary_budget.get("budget_mass_residual", 0.0)
        ).hex(),
        "momentum_residual": float(
            boundary_budget.get("budget_momentum_residual", 0.0)
        ).hex(),
        "energy_residual": float(
            boundary_budget.get("budget_energy_residual", 0.0)
        ).hex(),
        "phase_vapor_residual": float(
            phase_budget.get("phase_vapor_mass_balance_residual_kg", 0.0)
        ).hex(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def run_pipeline_depressurization_case(
    case: PipelineDepressurizationCaseSpec,
    config: HEMPipelineDepressurizationConfig | None = None,
    *,
    phase_evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state,
) -> PipelineCaseResult:
    """Run one fixed boundary-driven case to first crossing or explicit outcome."""

    cfg = config or HEMPipelineDepressurizationConfig()
    initial_provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=ConstantPressure(cfg.initial_pressure_pa),
        subcooling_K=cfg.subcooling_K,
        phase_config=cfg.phase_config,
    )
    initial_state = initial_provider.state_at(0.0)
    acoustic_time = cfg.length_m / initial_state.sound_speed_m_s
    ramp_duration = cfg.ramp_acoustic_time_ratio * acoustic_time
    horizon = cfg.horizon_acoustic_time_ratio * acoustic_time

    schedule = LinearPressureRamp(
        p_initial_pa=cfg.initial_pressure_pa,
        p_final_pa=case.final_boundary_pressure_pa,
        t_start_s=0.0,
        duration_s=ramp_duration,
    )
    provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=cfg.subcooling_K,
        phase_config=cfg.phase_config,
    )
    preflight = _run_boundary_preflight(
        case=case,
        provider=provider,
        ramp_duration_s=ramp_duration,
        config=cfg,
    )
    right_boundary = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    grid = UniformGrid(
        PipeGeometry(length_m=cfg.length_m, diameter_m=cfg.diameter_m),
        n_cells=cfg.n_cells,
    )
    initial_U = np.repeat(
        make_conserved(
            initial_state.rho_kg_m3,
            0.0,
            initial_state.e_j_kg,
            0.0,
        )[np.newaxis, :],
        cfg.n_cells,
        axis=0,
    )
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=cfg.accepted_state_quality_tolerance,
        phase_config=cfg.phase_config,
        quality_sync_config=cfg.projection_config,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=initial_U,
        cfl=cfg.cfl,
        n_ghost=cfg.n_ghost,
        left_boundary=ReflectiveBoundary(),
        right_boundary=right_boundary,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    initial_primitive = solver.primitive()
    initial_regions = eos.last_regions
    if initial_regions is None or not np.all(
        np.asarray(initial_regions).astype(str) == "LIQUID_CANDIDATE"
    ):
        raise HEMPipelineDepressurizationError(
            "uniform initial state must be accepted as LIQUID_CANDIDATE"
        )

    initial_inventory = inventory(initial_U, grid.dx, grid.geometry.area_m2)
    phase_tracker = PhaseChangeBudgetTracker(initial_inventory=initial_inventory)
    projected_config = cfg.projected_config()
    pipeline_spec = MinimalFvmDryRunCaseSpec(
        case_id=case.case_id,
        role=case.role,
        left_candidate_id="uniform_pipe_initial",
        right_candidate_id=(
            f"prescribed_boundary_{case.final_boundary_pressure_pa:.17g}"
        ),
    )
    initial_endpoint = DryRunEndpointState(
        candidate_id="uniform_pipe_initial",
        pressure_pa=initial_state.pressure_requested_pa,
        subcooling_K=initial_state.subcooling_K,
        rho_kg_m3=initial_state.rho_kg_m3,
        e_j_kg=initial_state.e_j_kg,
    )

    arrival_times: list[float | None] = [None] * cfg.n_cells
    step_records: list[PipelineStepRecord] = []
    cell_records: list[PipelineCellRecord] = []
    time_history = [0.0]
    pressure_history = [np.array(initial_primitive.p, dtype=float, copy=True)]
    state_history = [np.array(initial_U, dtype=float, copy=True)]
    crossing_step: int | None = None
    crossing_time: float | None = None
    crossing_cells: tuple[int, ...] = ()
    crossing_distances: tuple[float, ...] = ()
    maximum_crossing_quality = 0.0
    outcome: PipelineRunOutcome = "NO_CROSSING_WITHIN_HORIZON"
    failure_reason = ""
    latest_projected_budget: dict[str, float] = {}
    boundary_budget: dict[str, float] = {}
    phase_budget: dict[str, float] = {}

    try:
        for step_index in range(1, cfg.max_steps + 1):
            if solver.t >= horizon:
                break
            time_before = float(solver.t)
            dt = float(solver.compute_dt(t_end=horizon))
            if not np.isfinite(dt) or dt <= 0.0:
                raise HEMPipelineDepressurizationError(
                    "computed time step must be finite and positive"
                )
            previous_U = np.array(solver.U, dtype=float, copy=True)
            previous_primitive = solver.primitive()
            previous_inventory = inventory(
                previous_U,
                grid.dx,
                grid.geometry.area_m2,
            )
            if solver.boundary_budget is None:
                raise HEMPipelineDepressurizationError(
                    "boundary budget tracker is required"
                )
            left_before = np.array(
                solver.boundary_budget.cumulative_left,
                dtype=float,
                copy=True,
            )
            right_before = np.array(
                solver.boundary_budget.cumulative_right,
                dtype=float,
                copy=True,
            )
            reverse_before = right_boundary.reverse_flow_fallback_count

            solver.step(dt)
            raw_U = np.array(solver.U, dtype=float, copy=True)
            raw_inventory = inventory(raw_U, grid.dx, grid.geometry.area_m2)
            step_left = solver.boundary_budget.cumulative_left - left_before
            step_right = solver.boundary_budget.cumulative_right - right_before
            raw_budget = _incremental_boundary_budget(
                previous_inventory=previous_inventory,
                raw_inventory=raw_inventory,
                step_left=step_left,
                step_right=step_right,
                config=cfg,
            )

            detection = detect_raw_transition_events(
                previous_U,
                raw_U,
                evaluator=phase_evaluator,
                phase_config=cfg.phase_config,
            )
            raw_outcome = _raw_outcome(detection)
            reverse_delta = (
                right_boundary.reverse_flow_fallback_count - reverse_before
            )
            explicit_stop = _raw_event_stop(
                reverse_flow_delta=reverse_delta,
                raw_outcome=raw_outcome,
            )
            boundary_state = right_boundary.last_state

            if explicit_stop is not None:
                outcome = explicit_stop
                raise HEMPipelineDepressurizationError(
                    f"explicit stop outcome: {explicit_stop}"
                )

            raw_cells = _minimal_raw_cells(
                case_id=case.case_id,
                grid=grid,
                previous_U=previous_U,
                raw_U=raw_U,
                previous_primitive=previous_primitive,
                detection=detection,
            )
            boundary_for_record = boundary_state or provider.state_at(time_before)
            raw_case = MinimalRawFvmCaseResult(
                spec=pipeline_spec,
                left_state=initial_endpoint,
                right_state=DryRunEndpointState(
                    candidate_id=pipeline_spec.right_candidate_id,
                    pressure_pa=boundary_for_record.pressure_requested_pa,
                    subcooling_K=boundary_for_record.subcooling_K,
                    rho_kg_m3=boundary_for_record.rho_kg_m3,
                    e_j_kg=boundary_for_record.e_j_kg,
                ),
                dt_s=dt,
                dx_m=grid.dx,
                target_cfl=cfg.cfl,
                measured_initial_cfl=float(
                    np.max(
                        (
                            np.abs(previous_primitive.u)
                            + previous_primitive.c
                        )
                        * dt
                        / grid.dx
                    )
                ),
                interface_cell=cfg.n_cells - 1,
                outcome=raw_outcome,
                failure_reason="",
                initial_U=previous_U,
                raw_U=raw_U,
                cells=raw_cells,
                budget_diagnostics=raw_budget,
                fvm_step_exercised=True,
            )
            projected = run_one_projected_fvm_case(
                raw_case,
                projected_config,
            )
            if projected.outcome not in {
                "ACCEPTED_CROSSING",
                "ACCEPTED_ALL_LIQUID_NOOP",
            }:
                raise HEMPipelineDepressurizationError(
                    f"projected step was rejected: {projected.outcome}: "
                    f"{projected.failure_reason}"
                )

            phase_tracker.record_phase_change(
                U_before=raw_U,
                U_after=projected.post_U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
                dt=dt,
            )
            solver.U = np.array(projected.post_U, dtype=float, copy=True)
            post_primitive = solver.primitive()
            current_crossing = tuple(
                int(cell.cell_index)
                for cell in projected.cells
                if cell.transition_event
                == "LIQUID_TO_TWO_PHASE_CROSSING"
            )
            first_projection = tuple(
                int(cell.cell_index)
                for cell in projected.cells
                if cell.first_projection_applied
            )
            second_projection = tuple(
                int(cell.cell_index)
                for cell in projected.cells
                if cell.second_projection_applied
            )
            max_raw_q = max(
                (float(cell.q_equilibrium) for cell in projected.cells),
                default=0.0,
            )
            max_post_mismatch = max(
                (
                    abs(
                        float(cell.q_after_first_projection)
                        - float(cell.q_equilibrium)
                    )
                    for cell in projected.cells
                ),
                default=0.0,
            )
            latest_projected_budget = dict(projected.budget_diagnostics)
            boundary_budget, phase_budget = _validate_cumulative_budgets(
                solver=solver,
                phase_tracker=phase_tracker,
                initial_inventory=initial_inventory,
                latest_projected_budget=latest_projected_budget,
                config=cfg,
            )

            p_post = np.asarray(post_primitive.p, dtype=float)
            relative_drop = (
                cfg.initial_pressure_pa - p_post
            ) / cfg.initial_pressure_pa
            for index in range(cfg.n_cells):
                if (
                    arrival_times[index] is None
                    and relative_drop[index]
                    >= cfg.pressure_drop_evidence_relative
                ):
                    arrival_times[index] = float(solver.t)

            new_cells = _pipeline_cell_records(
                case_id=case.case_id,
                step_index=step_index,
                time_s=float(solver.t),
                grid=grid,
                detection=detection,
                projected=projected,
                pressure_initial_pa=cfg.initial_pressure_pa,
                arrival_times=arrival_times,
            )
            cell_records.extend(new_cells)

            right_flux = solver.boundary_budget.last_right_flux
            left_flux = solver.boundary_budget.last_left_flux
            area = grid.geometry.area_m2
            step_records.append(
                PipelineStepRecord(
                    case_id=case.case_id,
                    step_index=step_index,
                    time_before_s=time_before,
                    dt_s=dt,
                    time_after_s=float(solver.t),
                    boundary_pressure_pa=(
                        None
                        if boundary_state is None
                        else boundary_state.pressure_requested_pa
                    ),
                    boundary_temperature_K=(
                        None
                        if boundary_state is None
                        else boundary_state.temperature_requested_K
                    ),
                    boundary_rho_kg_m3=(
                        None if boundary_state is None else boundary_state.rho_kg_m3
                    ),
                    boundary_e_j_kg=(
                        None if boundary_state is None else boundary_state.e_j_kg
                    ),
                    boundary_equilibrium_quality=(
                        None
                        if boundary_state is None
                        else boundary_state.equilibrium_quality
                    ),
                    boundary_void_fraction=(
                        None
                        if boundary_state is None
                        else boundary_state.void_fraction
                    ),
                    boundary_sound_speed_m_s=(
                        None
                        if boundary_state is None
                        else boundary_state.sound_speed_m_s
                    ),
                    boundary_region=(
                        ""
                        if boundary_state is None
                        else boundary_state.boundary_region
                    ),
                    reverse_flow_fallback_count=(
                        right_boundary.reverse_flow_fallback_count
                    ),
                    raw_outcome=raw_outcome,
                    projected_outcome=projected.outcome,
                    crossing_cell_indices=current_crossing,
                    first_projection_cell_indices=first_projection,
                    second_projection_cell_indices=second_projection,
                    max_raw_equilibrium_quality=max_raw_q,
                    max_post_quality_mismatch=max_post_mismatch,
                    pressure_min_pa=float(np.min(p_post)),
                    pressure_max_pa=float(np.max(p_post)),
                    left_mass_flux_rate_kg_s=float(area * left_flux[IDX_RHO]),
                    right_mass_flux_rate_kg_s=float(area * right_flux[IDX_RHO]),
                    left_energy_flux_rate_W=float(area * left_flux[IDX_RHOE]),
                    right_energy_flux_rate_W=float(area * right_flux[IDX_RHOE]),
                    boundary_vapor_step_kg=float(
                        raw_budget["budget_vapor_mass_net_boundary"]
                    ),
                    projection_vapor_step_kg=float(
                        latest_projected_budget.get(
                            "projection_vapor_source_kg",
                            0.0,
                        )
                    ),
                    raw_boundary_vapor_residual_kg=float(
                        raw_budget["budget_vapor_mass_residual"]
                    ),
                    projection_source_consistency_residual_kg=float(
                        latest_projected_budget.get(
                            "projection_source_consistency_residual_kg",
                            0.0,
                        )
                    ),
                    combined_vapor_balance_residual_kg=float(
                        phase_budget.get(
                            "phase_vapor_mass_balance_residual_kg",
                            0.0,
                        )
                    ),
                    state_sha256=_state_sha256(solver.U),
                )
            )
            time_history.append(float(solver.t))
            pressure_history.append(np.array(p_post, dtype=float, copy=True))
            state_history.append(np.array(solver.U, dtype=float, copy=True))

            if current_crossing:
                if projected.outcome != "ACCEPTED_CROSSING":
                    raise HEMPipelineDepressurizationError(
                        "crossing did not produce an accepted projected state"
                    )
                if first_projection != current_crossing:
                    raise HEMPipelineDepressurizationError(
                        "crossing cells and projection cells do not match"
                    )
                if second_projection:
                    raise HEMPipelineDepressurizationError(
                        "second projection must be a no-op"
                    )
                crossing_step = step_index
                crossing_time = float(solver.t)
                crossing_cells = current_crossing
                crossing_distances = tuple(
                    float(cfg.length_m - grid.cell_centers[index])
                    for index in crossing_cells
                )
                maximum_crossing_quality = max_raw_q
                if max_raw_q < cfg.crossing_evidence_min_quality:
                    raise HEMPipelineDepressurizationError(
                        "crossing quality evidence is below the fixed minimum"
                    )
                outcome = "ACCEPTED_FIRST_CROSSING"
                break
            if projected.outcome != "ACCEPTED_ALL_LIQUID_NOOP":
                raise HEMPipelineDepressurizationError(
                    "pre-crossing step must remain an accepted liquid no-op"
                )
        else:
            raise HEMPipelineDepressurizationError(
                "max_steps reached before the fixed horizon"
            )

        if crossing_step is None:
            outcome = "NO_CROSSING_WITHIN_HORIZON"
        boundary_budget, phase_budget = _validate_cumulative_budgets(
            solver=solver,
            phase_tracker=phase_tracker,
            initial_inventory=initial_inventory,
            latest_projected_budget=latest_projected_budget,
            config=cfg,
        )
    except Exception as exc:
        failure_reason = f"{type(exc).__name__}: {exc}"
        if outcome not in {
            "ENDPOINT_LANDING",
            "FORBIDDEN_TRANSITION",
            "REVERSE_FLOW_GUARD",
        }:
            outcome = _failure_outcome(exc)
        try:
            boundary_budget, phase_budget = _validate_cumulative_budgets(
                solver=solver,
                phase_tracker=phase_tracker,
                initial_inventory=initial_inventory,
                latest_projected_budget=latest_projected_budget,
                config=cfg,
            )
        except Exception:
            boundary_budget = {}
            phase_budget = {}

    final_hash = _state_sha256(solver.U)
    signature = _make_signature(
        case=case,
        outcome=outcome,
        step_count=int(solver.step_count),
        final_time_s=float(solver.t),
        crossing_step=crossing_step,
        crossing_time_s=crossing_time,
        crossing_cells=crossing_cells,
        max_crossing_quality=maximum_crossing_quality,
        reverse_flow_count=right_boundary.reverse_flow_fallback_count,
        final_state_sha256=final_hash,
        boundary_budget=boundary_budget,
        phase_budget=phase_budget,
    )
    return PipelineCaseResult(
        case=case,
        config=cfg,
        initial_state=initial_state,
        initial_acoustic_time_s=float(acoustic_time),
        ramp_duration_s=float(ramp_duration),
        maximum_horizon_s=float(horizon),
        preflight=preflight,
        outcome=outcome,
        failure_reason=failure_reason,
        step_count=int(solver.step_count),
        final_time_s=float(solver.t),
        crossing_step=crossing_step,
        crossing_time_s=crossing_time,
        crossing_cell_indices=crossing_cells,
        crossing_distances_from_outlet_m=crossing_distances,
        maximum_crossing_quality=maximum_crossing_quality,
        reverse_flow_fallback_count=right_boundary.reverse_flow_fallback_count,
        pressure_drop_arrival_times_s=tuple(arrival_times),
        steps=tuple(step_records),
        cells=tuple(cell_records),
        boundary_budget_diagnostics=boundary_budget,
        phase_budget_diagnostics=phase_budget,
        final_state_sha256=final_hash,
        run_signature_sha256=signature,
        time_history_s=np.asarray(time_history, dtype=float),
        pressure_history_pa=np.asarray(pressure_history, dtype=float),
        accepted_state_history=np.asarray(state_history, dtype=float),
    )


def run_fixed_pipeline_depressurization_matrix(
    config: HEMPipelineDepressurizationConfig | None = None,
    *,
    case_runner: CaseRunner = run_pipeline_depressurization_case,
) -> HEMPipelineDepressurizationResult:
    """Run the fixed 2/3/4 MPa matrix without tuning any case or tolerance."""

    cfg = config or HEMPipelineDepressurizationConfig()
    cases = tuple(case_runner(case, cfg) for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES)
    return HEMPipelineDepressurizationResult(config=cfg, cases=cases)


def _flatten_csv_value(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def write_pipeline_depressurization_artifacts(
    output_dir: str | Path,
    result: HEMPipelineDepressurizationResult,
) -> dict[str, Path]:
    """Write JSON, case/step/cell/preflight CSV, Markdown, and NPZ evidence."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_pipeline_depressurization_increment2"
    paths = {
        "json": target / f"{stem}.json",
        "cases_csv": target / f"{stem}_cases.csv",
        "steps_csv": target / f"{stem}_steps.csv",
        "cells_csv": target / f"{stem}_cells.csv",
        "boundary_path_csv": target / f"{stem}_boundary_path.csv",
        "markdown": target / f"{stem}.md",
        "npz": target / f"{stem}.npz",
    }
    case_summaries = [case.summary() for case in result.cases]
    payload = {
        **result.summary(),
        "config": {
            "length_m": result.config.length_m,
            "diameter_m": result.config.diameter_m,
            "n_cells": result.config.n_cells,
            "n_ghost": result.config.n_ghost,
            "cfl": result.config.cfl,
            "initial_pressure_pa": result.config.initial_pressure_pa,
            "subcooling_K": result.config.subcooling_K,
            "ramp_acoustic_time_ratio": (
                result.config.ramp_acoustic_time_ratio
            ),
            "horizon_acoustic_time_ratio": (
                result.config.horizon_acoustic_time_ratio
            ),
            "max_steps": result.config.max_steps,
            "preflight_sample_count": result.config.preflight_sample_count,
            "pressure_drop_evidence_relative": (
                result.config.pressure_drop_evidence_relative
            ),
            "crossing_evidence_min_quality": (
                result.config.crossing_evidence_min_quality
            ),
            "accepted_state_quality_tolerance": (
                result.config.accepted_state_quality_tolerance
            ),
            "mass_budget_relative_tolerance": (
                result.config.mass_budget_relative_tolerance
            ),
            "mass_budget_absolute_tolerance_kg": (
                result.config.mass_budget_absolute_tolerance_kg
            ),
            "momentum_budget_relative_tolerance": (
                result.config.momentum_budget_relative_tolerance
            ),
            "momentum_budget_absolute_tolerance_kg_m_s": (
                result.config.momentum_budget_absolute_tolerance_kg_m_s
            ),
            "energy_budget_relative_tolerance": (
                result.config.energy_budget_relative_tolerance
            ),
            "energy_budget_absolute_tolerance_J": (
                result.config.energy_budget_absolute_tolerance_J
            ),
            "vapor_budget_absolute_tolerance_kg": (
                result.config.vapor_budget_absolute_tolerance_kg
            ),
            "phase_config": asdict(result.config.phase_config),
            "projection_config": asdict(result.config.projection_config),
            "fixed_case_matrix": [
                asdict(case) for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
            ],
        },
        "cases": case_summaries,
        "steps": [
            asdict(step) for case in result.cases for step in case.steps
        ],
        "cells": [
            asdict(cell) for case in result.cases for cell in case.cells
        ],
        "boundary_path": [
            asdict(record)
            for case in result.cases
            for record in case.preflight.records
        ],
    }
    paths["json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {key: _flatten_csv_value(value) for key, value in row.items()}
                )

    write_rows(paths["cases_csv"], case_summaries)
    write_rows(
        paths["steps_csv"],
        [asdict(step) for case in result.cases for step in case.steps],
    )
    write_rows(
        paths["cells_csv"],
        [asdict(cell) for case in result.cases for cell in case.cells],
    )
    write_rows(
        paths["boundary_path_csv"],
        [
            asdict(record)
            for case in result.cases
            for record in case.preflight.records
        ],
    )

    lines = [
        "# Stage 7 LCO2 HEM Pipeline Depressurization Increment 2",
        "",
        "`VERIFICATION ONLY; FIRST-ORDER FVM; NO PHYSICAL VALIDATION`",
        "",
        "| case | outcome | steps | final time [s] | crossing cells | max crossing q | reverse fallback |",
        "|---|---|---:|---:|---|---:|---:|",
    ]
    for case in result.cases:
        lines.append(
            f"| {case.case.case_id} | {case.outcome} | {case.step_count} | "
            f"{case.final_time_s:.17g} | "
            f"{list(case.crossing_cell_indices)} | "
            f"{case.maximum_crossing_quality:.17g} | "
            f"{case.reverse_flow_fallback_count} |"
        )
    lines.extend(
        [
            "",
            f"- pipeline depressurization executed: {str(result.summary()['pipeline_depressurization_executed']).lower()}",
            "- boundary and projection vapor accounts separated: true",
            "- algorithms or tolerances tuned: false",
            "- production HEM activation approved: false",
            "- physical Validation: false",
            "- design use acceptance: false",
            "- two-phase acoustic accuracy band approved: false",
        ]
    )
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")

    arrays: dict[str, np.ndarray] = {}
    for case in result.cases:
        prefix = case.case.case_id
        arrays[f"{prefix}__time_history_s"] = case.time_history_s
        arrays[f"{prefix}__pressure_history_pa"] = case.pressure_history_pa
        arrays[f"{prefix}__accepted_state_history"] = (
            case.accepted_state_history
        )
        arrays[f"{prefix}__pressure_drop_arrival_times_s"] = np.asarray(
            [
                np.nan if value is None else value
                for value in case.pressure_drop_arrival_times_s
            ],
            dtype=float,
        )
    np.savez_compressed(paths["npz"], **arrays)
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage 7 fixed LCO2 pipeline-depressurization Increment 2 matrix."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run_fixed_pipeline_depressurization_matrix()
    paths = write_pipeline_depressurization_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
