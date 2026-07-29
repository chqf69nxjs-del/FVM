"""Verification-only post-crossing propagation review for the fixed Stage 7 case.

This module replays the merged PR #77 5 -> 2 MPa first-crossing case exactly,
then reconstructs the same first-order FVM state at the accepted crossing and
continues it for the fixed +1 / +4 / +16 / +64 accepted-step offsets.

The module is orchestration and evidence only.  It does not change the production
solver, Rusanov flux, boundary model, phase classifier, equilibrium sound-speed
formula, quality projection, crossing threshold, or any tolerance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Sequence

import numpy as np

from .boundary import LinearPressureRamp, ReflectiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .hem_equilibrium_quality_sync import HEMEquilibriumQualityProjection
from .hem_equilibrium_sound_speed import estimate_coolprop_equilibrium_sound_speed
from .hem_liquid_to_two_phase_crossing import detect_raw_transition_events
from .hem_liquid_to_two_phase_minimal_fvm_dry_run import (
    DryRunEndpointState,
    MinimalFvmDryRunCaseSpec,
    MinimalRawFvmCaseResult,
)
from .hem_liquid_to_two_phase_projected_fvm_dry_run import _budget_diagnostics
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_pipeline_depressurization_boundary import (
    VerificationHEMPrescribedSubcooledOutletBoundary,
    VerificationHEMPrescribedSubcooledStateProvider,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    HEMPipelineDepressurizationError,
    PipelineCaseResult,
    _incremental_boundary_budget,
    _minimal_raw_cells,
    _state_sha256,
    _validate_cumulative_budgets,
    run_pipeline_depressurization_case,
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
    vapor_mass_fraction,
    velocity,
)

BASELINE_CASE_ID = "pipeline_crossing_candidate_p5m5_to_p2m5"
CONTINUATION_OFFSETS = (1, 4, 16, 64)
EXPECTED_BASELINE = {
    "outcome": "ACCEPTED_FIRST_CROSSING",
    "step_count": 125,
    "final_time_s": 7.999325695335248e-4,
    "crossing_step": 125,
    "crossing_time_s": 7.999325695335248e-4,
    "crossing_cell_indices": (29,),
    "crossing_distances_from_outlet_m": (0.078125,),
    "maximum_crossing_quality": 3.773646403587342e-6,
    "final_state_sha256": (
        "170ce66c02a320d50389d0cf26fed78f21042f83dec6f64a0978e451cd91e361"
    ),
    "run_signature_sha256": (
        "28a5f8b1fd43f6208807bd15d96eaf09a568349007a1994273717aa264505fea"
    ),
}
APPROVAL_BOUNDARY = {
    "Gate_6_execution_complete": False,
    "post_crossing_propagation_approved": False,
    "near_saturation_acoustic_continuity_approved": False,
    "two_phase_acoustic_accuracy_band_approved": False,
    "CFL_independent_crossing_verified": False,
    "mesh_independent_crossing_verified": False,
    "Gate_P2_passed": False,
    "physical_validation": False,
    "design_use_acceptance": False,
    "production_hem_activation_approved": False,
}

ContinuationOutcome = Literal[
    "COMPLETED_FIXED_CHECKPOINTS",
    "FAIL_SAFE_STOP",
]


class HEMPostCrossingPropagationError(RuntimeError):
    """Raised when the fixed Gate 6 continuation cannot proceed safely."""


@dataclass(frozen=True)
class HEMPostCrossingPropagationConfig:
    """Locked Gate 6 first-increment configuration."""

    pipeline: HEMPipelineDepressurizationConfig = field(
        default_factory=HEMPipelineDepressurizationConfig
    )
    continuation_offsets: tuple[int, ...] = CONTINUATION_OFFSETS

    def __post_init__(self) -> None:
        if self.pipeline != HEMPipelineDepressurizationConfig():
            raise ValueError("Gate 6 pipeline configuration is fixed to PR #77")
        if self.continuation_offsets != CONTINUATION_OFFSETS:
            raise ValueError(
                "Gate 6 continuation offsets are fixed at +1 / +4 / +16 / +64"
            )

    @property
    def maximum_post_crossing_steps(self) -> int:
        return self.continuation_offsets[-1]


@dataclass(frozen=True)
class PostCrossingStepRecord:
    case_id: str
    absolute_step: int
    post_crossing_step: int
    time_before_s: float
    dt_s: float
    time_after_s: float
    raw_state_class: str
    accepted_state_class: str
    open_two_phase_cell_count: int
    open_two_phase_cell_indices: tuple[int, ...]
    furthest_upstream_two_phase_cell: int | None
    furthest_upstream_distance_from_outlet_m: float | None
    liquid_to_two_phase_event_count: int
    reverse_transition_event_count: int
    projection_cell_count: int
    second_projection_cell_count: int
    maximum_equilibrium_quality: float
    integrated_equilibrium_quality: float
    maximum_void_fraction: float
    pressure_min_pa: float
    pressure_max_pa: float
    liquid_sound_speed_min_m_s: float | None
    liquid_sound_speed_max_m_s: float | None
    two_phase_sound_speed_min_m_s: float | None
    two_phase_sound_speed_max_m_s: float | None
    mass_total_kg: float
    momentum_total_kg_m_s: float
    energy_total_J: float
    vapor_mass_total_kg: float
    boundary_mass_residual_kg: float
    boundary_momentum_residual_kg_m_s: float
    boundary_energy_residual_J: float
    phase_vapor_residual_kg: float
    projection_vapor_source_step_kg: float
    boundary_vapor_step_kg: float
    second_projection_noop: bool
    state_sha256: str


@dataclass(frozen=True)
class PostCrossingCellRecord:
    case_id: str
    absolute_step: int
    post_crossing_step: int
    time_s: float
    cell_index: int
    cell_center_m: float
    distance_from_outlet_m: float
    previous_region: str
    raw_region: str
    post_region: str
    transition_event: str
    rho_kg_m3: float
    momentum_kg_m2_s: float
    rhoE_J_m3: float
    rho_q_kg_m3: float
    velocity_m_s: float
    internal_energy_j_kg: float
    pressure_pa: float
    temperature_K: float
    q_transport_raw: float
    q_equilibrium: float
    q_post: float
    void_fraction: float
    projection_applied: bool
    delta_rho_q: float
    sound_speed_status: str
    sound_speed_failure_category: str
    sound_speed_failure_reason: str
    sound_speed_m_s: float | None
    sound_speed_squared_m2_s2: float | None
    dp_drho_at_e: float | None
    dp_de_at_rho: float | None
    density_term_m2_s2: float | None
    energy_term_m2_s2: float | None
    density_step_kg_m3: float | None
    energy_step_j_kg: float | None
    density_step_halvings: int | None
    energy_step_halvings: int | None


@dataclass(frozen=True)
class PostCrossingCheckpointRecord:
    case_id: str
    post_crossing_step: int
    absolute_step: int
    time_s: float
    reached: bool
    open_two_phase_cell_count: int | None
    open_two_phase_cell_indices: tuple[int, ...]
    furthest_upstream_two_phase_cell: int | None
    furthest_upstream_distance_from_outlet_m: float | None
    maximum_equilibrium_quality: float | None
    maximum_void_fraction: float | None
    pressure_min_pa: float | None
    pressure_max_pa: float | None
    sound_speed_min_m_s: float | None
    sound_speed_max_m_s: float | None
    mass_total_kg: float | None
    momentum_total_kg_m_s: float | None
    energy_total_J: float | None
    vapor_mass_total_kg: float | None
    phase_vapor_residual_kg: float | None
    state_sha256: str


@dataclass(frozen=True)
class PostCrossingPropagationResult:
    config: HEMPostCrossingPropagationConfig
    baseline: PipelineCaseResult
    outcome: ContinuationOutcome
    failure_category: str
    failure_reason: str
    failure_absolute_step: int | None
    failure_post_crossing_step: int | None
    last_valid_state_sha256: str
    steps: tuple[PostCrossingStepRecord, ...]
    cells: tuple[PostCrossingCellRecord, ...]
    checkpoints: tuple[PostCrossingCheckpointRecord, ...]
    classifications: tuple[str, ...]
    classification_rationale: tuple[str, ...]
    baseline_open_two_phase_cell_indices: tuple[int, ...]
    region_toggle_counts: tuple[int, ...]
    provenance: dict[str, object]

    def summary(self) -> dict[str, object]:
        reached = [
            checkpoint.post_crossing_step
            for checkpoint in self.checkpoints
            if checkpoint.reached
        ]
        return {
            "schema_version": "stage7_gate6_post_crossing_propagation_v1",
            "scope": "verification_only",
            "case_id": self.baseline.case.case_id,
            "baseline_reproduced_exactly": True,
            "baseline": {
                "outcome": self.baseline.outcome,
                "step_count": self.baseline.step_count,
                "final_time_s": self.baseline.final_time_s,
                "crossing_step": self.baseline.crossing_step,
                "crossing_time_s": self.baseline.crossing_time_s,
                "crossing_cell_indices": list(self.baseline.crossing_cell_indices),
                "crossing_distances_from_outlet_m": list(
                    self.baseline.crossing_distances_from_outlet_m
                ),
                "maximum_crossing_quality": self.baseline.maximum_crossing_quality,
                "final_state_sha256": self.baseline.final_state_sha256,
                "run_signature_sha256": self.baseline.run_signature_sha256,
            },
            "fixed_continuation_offsets": list(self.config.continuation_offsets),
            "reached_continuation_offsets": reached,
            "outcome": self.outcome,
            "failure_category": self.failure_category,
            "failure_reason": self.failure_reason,
            "failure_absolute_step": self.failure_absolute_step,
            "failure_post_crossing_step": self.failure_post_crossing_step,
            "last_valid_state_sha256": self.last_valid_state_sha256,
            "successful_post_crossing_step_count": len(self.steps),
            "cell_record_count": len(self.cells),
            "checkpoint_record_count": len(self.checkpoints),
            "baseline_open_two_phase_cell_indices": list(
                self.baseline_open_two_phase_cell_indices
            ),
            "region_toggle_counts": list(self.region_toggle_counts),
            "classifications": list(self.classifications),
            "classification_rationale": list(self.classification_rationale),
            "provenance": dict(self.provenance),
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            **APPROVAL_BOUNDARY,
        }


def _coolprop_version() -> str:
    import CoolProp  # type: ignore

    return str(CoolProp.__version__)


def _git_provenance() -> dict[str, object]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""

    return {
        "source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
        "property_backend_version": _coolprop_version(),
        "python_version": os.sys.version,
    }


def _baseline_case_spec():
    for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        if case.case_id == BASELINE_CASE_ID:
            return case
    raise HEMPostCrossingPropagationError(
        f"fixed PR #77 baseline case not found: {BASELINE_CASE_ID}"
    )


def _require_exact_baseline(result: PipelineCaseResult) -> None:
    comparisons = {
        "outcome": result.outcome,
        "step_count": result.step_count,
        "final_time_s": result.final_time_s,
        "crossing_step": result.crossing_step,
        "crossing_time_s": result.crossing_time_s,
        "crossing_cell_indices": result.crossing_cell_indices,
        "crossing_distances_from_outlet_m": result.crossing_distances_from_outlet_m,
        "maximum_crossing_quality": result.maximum_crossing_quality,
        "final_state_sha256": result.final_state_sha256,
        "run_signature_sha256": result.run_signature_sha256,
    }
    mismatches = {
        name: {"actual": actual, "expected": EXPECTED_BASELINE[name]}
        for name, actual in comparisons.items()
        if actual != EXPECTED_BASELINE[name]
    }
    if mismatches:
        raise HEMPostCrossingPropagationError(
            "PR #77 5->2 MPa baseline replay mismatch: "
            + json.dumps(mismatches, sort_keys=True, default=list)
        )
    if result.failure_reason:
        raise HEMPostCrossingPropagationError(
            f"baseline retained unexpected failure: {result.failure_reason}"
        )
    if result.accepted_state_history.shape[-2:] != (
        result.config.n_cells,
        N_VARS,
    ):
        raise HEMPostCrossingPropagationError(
            "baseline accepted-state history has an incompatible shape"
        )


def _classify_raw_state(detection) -> str:
    raw_regions = np.asarray(detection.raw.region).astype(str)
    events = np.asarray(detection.transitions.event).astype(str)
    if np.any(
        np.isin(
            raw_regions,
            ["SATURATED_VAPOR_ENDPOINT", "VAPOR_CANDIDATE"],
        )
    ) or np.any(events == "FORBIDDEN_TRANSITION"):
        return "FORBIDDEN_REGION"
    if np.any(raw_regions == "SATURATED_LIQUID_ENDPOINT") or np.any(
        events == "BOUNDARY_TOUCH"
    ):
        return "ENDPOINT_LANDING"
    if np.any(raw_regions == "OPEN_TWO_PHASE"):
        return "OPEN_TWO_PHASE"
    if np.all(raw_regions == "LIQUID_CANDIDATE"):
        return "ALL_LIQUID"
    return "UNSUPPORTED_REGION"


def _failure_category(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if "reverse flow" in text:
        return "REVERSE_FLOW_GUARD"
    if (
        "sound-speed" in text
        or "sound speed" in text
        or "no valid central" in text
        or "acoustic" in text
    ):
        return "ACOUSTIC_REFUSAL"
    if "endpoint" in text or "boundary_touch" in text:
        return "ENDPOINT_GUARD"
    if "forbidden" in text or "unsupported_region" in text:
        return "PHASE_GUARD"
    if "projection" in text or "quality" in text:
        return "PROJECTION_GUARD"
    if "budget" in text or "residual" in text:
        return "BUDGET_GUARD"
    if "coolprop" in text or "backend" in text or "property evaluation" in text:
        return "BACKEND_FAILURE"
    if "accepted-state" in text or "eos" in text:
        return "ACCEPTED_EOS_GUARD"
    return "SOLVER_GUARD"


def _baseline_regions(baseline: PipelineCaseResult) -> tuple[str, ...]:
    if baseline.crossing_step is None:
        raise HEMPostCrossingPropagationError("baseline does not retain a crossing step")
    rows = [
        cell
        for cell in baseline.cells
        if cell.step_index == baseline.crossing_step
    ]
    if len(rows) != baseline.config.n_cells:
        raise HEMPostCrossingPropagationError(
            "baseline final cell records are incomplete"
        )
    ordered = sorted(rows, key=lambda cell: cell.cell_index)
    return tuple(cell.post_region for cell in ordered)


def _sound_speed_evidence(rho: float, e: float) -> dict[str, object]:
    try:
        estimate = estimate_coolprop_equilibrium_sound_speed(rho, e)
        return {
            "sound_speed_status": "SUCCESS",
            "sound_speed_failure_category": "",
            "sound_speed_failure_reason": "",
            "sound_speed_m_s": float(estimate.sound_speed_m_s),
            "sound_speed_squared_m2_s2": float(
                estimate.sound_speed_squared_m2_s2
            ),
            "dp_drho_at_e": float(estimate.dp_drho_at_e),
            "dp_de_at_rho": float(estimate.dp_de_at_rho),
            "density_term_m2_s2": float(estimate.density_term_m2_s2),
            "energy_term_m2_s2": float(estimate.energy_term_m2_s2),
            "density_step_kg_m3": float(estimate.density_step_kg_m3),
            "energy_step_j_kg": float(estimate.energy_step_j_kg),
            "density_step_halvings": int(estimate.density_step_halvings),
            "energy_step_halvings": int(estimate.energy_step_halvings),
        }
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        return {
            "sound_speed_status": "REFUSED",
            "sound_speed_failure_category": _failure_category(exc),
            "sound_speed_failure_reason": reason,
            "sound_speed_m_s": None,
            "sound_speed_squared_m2_s2": None,
            "dp_drho_at_e": None,
            "dp_de_at_rho": None,
            "density_term_m2_s2": None,
            "energy_term_m2_s2": None,
            "density_step_kg_m3": None,
            "energy_step_j_kg": None,
            "density_step_halvings": None,
            "energy_step_halvings": None,
        }


def _raw_case(
    *,
    case,
    config: HEMPipelineDepressurizationConfig,
    grid: UniformGrid,
    previous_U: np.ndarray,
    raw_U: np.ndarray,
    previous_primitive,
    detection,
    boundary_state,
    dt: float,
    raw_budget: dict[str, float],
) -> MinimalRawFvmCaseResult:
    raw_class = _classify_raw_state(detection)
    if raw_class not in {"OPEN_TWO_PHASE", "ALL_LIQUID"}:
        raise HEMPostCrossingPropagationError(
            f"raw continuation entered {raw_class}"
        )
    cells = _minimal_raw_cells(
        case_id=case.case_id,
        grid=grid,
        previous_U=previous_U,
        raw_U=raw_U,
        previous_primitive=previous_primitive,
        detection=detection,
    )
    spec = MinimalFvmDryRunCaseSpec(
        case_id=case.case_id,
        role="post_crossing_propagation",
        left_candidate_id="accepted_crossing_state",
        right_candidate_id=f"prescribed_boundary_{case.final_boundary_pressure_pa:.17g}",
    )
    left_state = DryRunEndpointState(
        candidate_id="accepted_crossing_state",
        pressure_pa=float(np.asarray(previous_primitive.p)[-1]),
        subcooling_K=config.subcooling_K,
        rho_kg_m3=float(previous_U[-1, IDX_RHO]),
        e_j_kg=float(internal_energy(previous_U[-1])),
    )
    right_state = DryRunEndpointState(
        candidate_id=spec.right_candidate_id,
        pressure_pa=boundary_state.pressure_requested_pa,
        subcooling_K=boundary_state.subcooling_K,
        rho_kg_m3=boundary_state.rho_kg_m3,
        e_j_kg=boundary_state.e_j_kg,
    )
    measured_cfl = float(
        np.max(
            (np.abs(previous_primitive.u) + previous_primitive.c)
            * dt
            / grid.dx
        )
    )
    return MinimalRawFvmCaseResult(
        spec=spec,
        left_state=left_state,
        right_state=right_state,
        dt_s=dt,
        dx_m=grid.dx,
        target_cfl=config.cfl,
        measured_initial_cfl=measured_cfl,
        interface_cell=config.n_cells - 1,
        outcome=raw_class,
        failure_reason="",
        initial_U=np.array(previous_U, copy=True),
        raw_U=np.array(raw_U, copy=True),
        cells=cells,
        budget_diagnostics=dict(raw_budget),
        fvm_step_exercised=True,
    )


def _project_and_accept(
    *,
    raw_case: MinimalRawFvmCaseResult,
    detection,
    config: HEMPipelineDepressurizationConfig,
):
    projection = HEMEquilibriumQualityProjection(config=config.projection_config)
    first = projection.project(np.array(raw_case.raw_U, copy=True))
    first_summary = first.summary()
    for key in (
        "mass_bitwise_unchanged",
        "momentum_bitwise_unchanged",
        "energy_bitwise_unchanged",
        "quality_synchronized_within_tolerance",
    ):
        if first_summary[key] is not True:
            raise HEMPostCrossingPropagationError(
                f"first projection invariant failed: {key}"
            )

    post_U = np.array(first.U_after, dtype=float, copy=True)
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=config.accepted_state_quality_tolerance,
        phase_config=config.phase_config,
        quality_sync_config=config.projection_config,
    )
    primitive = eos.primitive_from_conserved(post_U)
    regions_value = eos.last_regions
    if regions_value is None:
        raise HEMPostCrossingPropagationError(
            "accepted-state EOS did not retain post regions"
        )
    post_regions = np.asarray(regions_value).astype(str)
    raw_regions = np.asarray(detection.raw.region).astype(str)
    if not np.array_equal(post_regions, raw_regions):
        raise HEMPostCrossingPropagationError(
            "post accepted-state regions differ from raw rho/e regions"
        )

    second = HEMEquilibriumQualityProjection(
        config=config.projection_config
    ).project(np.array(post_U, copy=True))
    if np.any(second.projection_applied) or not np.array_equal(
        second.U_after, post_U
    ):
        raise HEMPostCrossingPropagationError(
            "second equilibrium-quality projection must be an exact no-op"
        )

    q_post = np.asarray(vapor_mass_fraction(post_U), dtype=float)
    q_eq = np.asarray(first.q_equilibrium, dtype=float)
    if np.any(
        np.abs(q_post - q_eq) > config.projection_config.activation_tolerance
    ):
        raise HEMPostCrossingPropagationError(
            "post-projection transported quality does not match equilibrium quality"
        )

    budget = _budget_diagnostics(
        raw_case=raw_case,
        first=first,
        post_U=post_U,
        config=config.projected_config(),
    )
    for key in (
        "phase_vapor_mass_balance_residual_kg",
        "projection_source_consistency_residual_kg",
        "combined_post_vapor_balance_residual_kg",
    ):
        if abs(float(budget[key])) > config.vapor_budget_absolute_tolerance_kg:
            raise HEMPostCrossingPropagationError(
                f"projected step vapor budget does not close: {key}={budget[key]}"
            )
    return first, second, post_U, primitive, post_regions, budget


def _checkpoint_from_step(
    record: PostCrossingStepRecord,
) -> PostCrossingCheckpointRecord:
    sound_values = [
        value
        for value in (
            record.liquid_sound_speed_min_m_s,
            record.liquid_sound_speed_max_m_s,
            record.two_phase_sound_speed_min_m_s,
            record.two_phase_sound_speed_max_m_s,
        )
        if value is not None
    ]
    return PostCrossingCheckpointRecord(
        case_id=record.case_id,
        post_crossing_step=record.post_crossing_step,
        absolute_step=record.absolute_step,
        time_s=record.time_after_s,
        reached=True,
        open_two_phase_cell_count=record.open_two_phase_cell_count,
        open_two_phase_cell_indices=record.open_two_phase_cell_indices,
        furthest_upstream_two_phase_cell=record.furthest_upstream_two_phase_cell,
        furthest_upstream_distance_from_outlet_m=(
            record.furthest_upstream_distance_from_outlet_m
        ),
        maximum_equilibrium_quality=record.maximum_equilibrium_quality,
        maximum_void_fraction=record.maximum_void_fraction,
        pressure_min_pa=record.pressure_min_pa,
        pressure_max_pa=record.pressure_max_pa,
        sound_speed_min_m_s=min(sound_values) if sound_values else None,
        sound_speed_max_m_s=max(sound_values) if sound_values else None,
        mass_total_kg=record.mass_total_kg,
        momentum_total_kg_m_s=record.momentum_total_kg_m_s,
        energy_total_J=record.energy_total_J,
        vapor_mass_total_kg=record.vapor_mass_total_kg,
        phase_vapor_residual_kg=record.phase_vapor_residual_kg,
        state_sha256=record.state_sha256,
    )


def _missing_checkpoint(
    case_id: str,
    post_step: int,
    absolute_step: int,
    time_s: float,
    state_sha256: str,
) -> PostCrossingCheckpointRecord:
    return PostCrossingCheckpointRecord(
        case_id=case_id,
        post_crossing_step=post_step,
        absolute_step=absolute_step,
        time_s=time_s,
        reached=False,
        open_two_phase_cell_count=None,
        open_two_phase_cell_indices=(),
        furthest_upstream_two_phase_cell=None,
        furthest_upstream_distance_from_outlet_m=None,
        maximum_equilibrium_quality=None,
        maximum_void_fraction=None,
        pressure_min_pa=None,
        pressure_max_pa=None,
        sound_speed_min_m_s=None,
        sound_speed_max_m_s=None,
        mass_total_kg=None,
        momentum_total_kg_m_s=None,
        energy_total_J=None,
        vapor_mass_total_kg=None,
        phase_vapor_residual_kg=None,
        state_sha256=state_sha256,
    )


def _review_classifications(
    *,
    outcome: ContinuationOutcome,
    steps: Sequence[PostCrossingStepRecord],
    baseline_open_cells: tuple[int, ...],
    region_toggle_counts: Sequence[int],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    labels: list[str] = []
    rationale: list[str] = []
    final = steps[-1] if steps else None

    if final is not None and final.open_two_phase_cell_count > 0:
        labels.append("POST_CROSSING_REGION_PERSISTS")
        rationale.append(
            "At least one OPEN_TWO_PHASE cell remains in the last valid accepted state."
        )
    if final is not None and final.open_two_phase_cell_count == 0:
        labels.append("POST_CROSSING_REGION_DECAYS")
        rationale.append(
            "The last valid accepted state contains no OPEN_TWO_PHASE cell."
        )
    baseline_upstream = min(baseline_open_cells) if baseline_open_cells else None
    propagated = any(
        step.furthest_upstream_two_phase_cell is not None
        and baseline_upstream is not None
        and step.furthest_upstream_two_phase_cell < baseline_upstream
        for step in steps
    )
    if propagated:
        labels.append("POST_CROSSING_REGION_PROPAGATES")
        rationale.append(
            "The furthest upstream OPEN_TWO_PHASE cell moved upstream of the "
            "baseline crossing cell."
        )
    if any(count > 1 for count in region_toggle_counts):
        labels.append("PHASE_CLASSIFIER_CHATTER_OBSERVED")
        rationale.append(
            "At least one cell changed between liquid and open-two-phase regions "
            "more than once."
        )
    if steps and all(step.second_projection_noop for step in steps):
        labels.append("PROJECTION_RECOVERY_STABLE")
        rationale.append(
            "Every successful continuation step synchronized quality and retained "
            "an exact second-projection no-op."
        )
    if steps:
        labels.append("CONSERVATION_BUDGET_STABLE")
        rationale.append(
            "All retained successful continuation steps passed the fixed "
            "conservative and vapor-budget guards."
        )
    if outcome != "COMPLETED_FIXED_CHECKPOINTS":
        labels.append("POST_CROSSING_GUARD_LIMIT_REACHED")
        rationale.append(
            "Continuation stopped through an explicit categorized fail-safe before "
            "all fixed checkpoints were reached."
        )
        labels.append("PROPAGATION_REVIEW_INCONCLUSIVE")
        rationale.append(
            "The fixed +64-step sequence was not completed, so the long-checkpoint "
            "propagation disposition remains incomplete."
        )
    if not labels:
        labels.append("PROPAGATION_REVIEW_INCONCLUSIVE")
        rationale.append("No stronger permitted classification was supported.")
    return tuple(labels), tuple(rationale)


def run_post_crossing_propagation_review(
    config: HEMPostCrossingPropagationConfig | None = None,
) -> PostCrossingPropagationResult:
    """Replay PR #77 exactly and continue the accepted state to fixed offsets."""

    cfg = config or HEMPostCrossingPropagationConfig()
    pipeline = cfg.pipeline
    case = _baseline_case_spec()
    baseline = run_pipeline_depressurization_case(case, pipeline)
    _require_exact_baseline(baseline)

    crossing_U = np.array(
        baseline.accepted_state_history[-1], dtype=float, copy=True
    )
    schedule = LinearPressureRamp(
        p_initial_pa=pipeline.initial_pressure_pa,
        p_final_pa=case.final_boundary_pressure_pa,
        t_start_s=0.0,
        duration_s=baseline.ramp_duration_s,
    )
    provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=pipeline.subcooling_K,
        phase_config=pipeline.phase_config,
    )
    right_boundary = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    grid = UniformGrid(
        PipeGeometry(
            length_m=pipeline.length_m,
            diameter_m=pipeline.diameter_m,
        ),
        n_cells=pipeline.n_cells,
    )
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=pipeline.accepted_state_quality_tolerance,
        phase_config=pipeline.phase_config,
        quality_sync_config=pipeline.projection_config,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=crossing_U,
        cfl=pipeline.cfl,
        n_ghost=pipeline.n_ghost,
        left_boundary=ReflectiveBoundary(),
        right_boundary=right_boundary,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=baseline.final_time_s,
        step_count=baseline.step_count,
    )
    continuation_initial_inventory = inventory(
        crossing_U, grid.dx, grid.geometry.area_m2
    )
    phase_tracker = PhaseChangeBudgetTracker(
        initial_inventory=continuation_initial_inventory
    )
    baseline_regions = _baseline_regions(baseline)
    baseline_open_cells = tuple(
        index
        for index, region in enumerate(baseline_regions)
        if region == "OPEN_TWO_PHASE"
    )
    previous_regions = list(baseline_regions)
    toggle_counts = [0] * pipeline.n_cells
    step_records: list[PostCrossingStepRecord] = []
    cell_records: list[PostCrossingCellRecord] = []
    checkpoint_by_offset: dict[int, PostCrossingCheckpointRecord] = {}
    latest_projected_budget: dict[str, float] = {}
    outcome: ContinuationOutcome = "COMPLETED_FIXED_CHECKPOINTS"
    failure_category = ""
    failure_reason = ""
    failure_absolute_step: int | None = None
    failure_post_step: int | None = None
    last_valid_hash = _state_sha256(solver.U)

    for post_step in range(1, cfg.maximum_post_crossing_steps + 1):
        try:
            time_before = float(solver.t)
            previous_U = np.array(solver.U, dtype=float, copy=True)
            previous_primitive = solver.primitive()
            previous_inventory = inventory(
                previous_U, grid.dx, grid.geometry.area_m2
            )
            if solver.boundary_budget is None:
                raise HEMPostCrossingPropagationError(
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
            dt = float(solver.compute_dt())
            if not np.isfinite(dt) or dt <= 0.0:
                raise HEMPostCrossingPropagationError(
                    "computed continuation dt must be finite and positive"
                )

            solver.step(dt)
            raw_U = np.array(solver.U, dtype=float, copy=True)
            raw_inventory = inventory(raw_U, grid.dx, grid.geometry.area_m2)
            raw_budget = _incremental_boundary_budget(
                previous_inventory=previous_inventory,
                raw_inventory=raw_inventory,
                step_left=solver.boundary_budget.cumulative_left - left_before,
                step_right=solver.boundary_budget.cumulative_right - right_before,
                config=pipeline,
            )
            if (
                right_boundary.reverse_flow_fallback_count - reverse_before
            ) > 0:
                raise HEMPostCrossingPropagationError(
                    "reverse flow fallback was activated"
                )

            detection = detect_raw_transition_events(
                previous_U,
                raw_U,
                phase_config=pipeline.phase_config,
            )
            raw_class = _classify_raw_state(detection)
            if raw_class not in {"OPEN_TWO_PHASE", "ALL_LIQUID"}:
                raise HEMPostCrossingPropagationError(
                    f"raw continuation entered {raw_class}"
                )
            boundary_state = right_boundary.last_state or provider.state_at(
                time_before
            )
            raw_case = _raw_case(
                case=case,
                config=pipeline,
                grid=grid,
                previous_U=previous_U,
                raw_U=raw_U,
                previous_primitive=previous_primitive,
                detection=detection,
                boundary_state=boundary_state,
                dt=dt,
                raw_budget=raw_budget,
            )
            (
                first,
                second,
                post_U,
                primitive,
                post_regions,
                projected_budget,
            ) = _project_and_accept(
                raw_case=raw_case,
                detection=detection,
                config=pipeline,
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
                initial_inventory=continuation_initial_inventory,
                latest_projected_budget=latest_projected_budget,
                config=pipeline,
            )

            regions = np.asarray(post_regions).astype(str)
            events = np.asarray(detection.transitions.event).astype(str)
            raw_regions = np.asarray(detection.raw.region).astype(str)
            previous_detection_regions = np.asarray(
                detection.previous.region
            ).astype(str)
            q_raw = np.asarray(vapor_mass_fraction(raw_U), dtype=float)
            q_eq = np.asarray(first.q_equilibrium, dtype=float)
            q_post = np.asarray(vapor_mass_fraction(post_U), dtype=float)
            alpha = np.asarray(primitive.alpha, dtype=float)
            pressure = np.asarray(primitive.p, dtype=float)
            temperature = np.asarray(primitive.T, dtype=float)
            sound = np.asarray(primitive.c, dtype=float)
            speed = np.asarray(velocity(post_U), dtype=float)
            e = np.asarray(internal_energy(post_U), dtype=float)

            open_cells = tuple(
                int(index)
                for index in np.flatnonzero(regions == "OPEN_TWO_PHASE")
            )
            furthest = min(open_cells) if open_cells else None
            furthest_distance = (
                None
                if furthest is None
                else float(pipeline.length_m - grid.cell_centers[furthest])
            )
            for index, region in enumerate(regions):
                if region != previous_regions[index]:
                    toggle_counts[index] += 1
                previous_regions[index] = str(region)

            acoustic_by_cell: list[dict[str, object]] = []
            for index in range(pipeline.n_cells):
                acoustic_by_cell.append(
                    _sound_speed_evidence(
                        float(post_U[index, IDX_RHO]),
                        float(e[index]),
                    )
                )

            for index in range(pipeline.n_cells):
                acoustic = acoustic_by_cell[index]
                cell_records.append(
                    PostCrossingCellRecord(
                        case_id=case.case_id,
                        absolute_step=int(solver.step_count),
                        post_crossing_step=post_step,
                        time_s=float(solver.t),
                        cell_index=index,
                        cell_center_m=float(grid.cell_centers[index]),
                        distance_from_outlet_m=float(
                            pipeline.length_m - grid.cell_centers[index]
                        ),
                        previous_region=str(previous_detection_regions[index]),
                        raw_region=str(raw_regions[index]),
                        post_region=str(regions[index]),
                        transition_event=str(events[index]),
                        rho_kg_m3=float(post_U[index, IDX_RHO]),
                        momentum_kg_m2_s=float(post_U[index, IDX_MOM]),
                        rhoE_J_m3=float(post_U[index, IDX_RHOE]),
                        rho_q_kg_m3=float(post_U[index, IDX_RHO_XV]),
                        velocity_m_s=float(speed[index]),
                        internal_energy_j_kg=float(e[index]),
                        pressure_pa=float(pressure[index]),
                        temperature_K=float(temperature[index]),
                        q_transport_raw=float(q_raw[index]),
                        q_equilibrium=float(q_eq[index]),
                        q_post=float(q_post[index]),
                        void_fraction=float(alpha[index]),
                        projection_applied=bool(first.projection_applied[index]),
                        delta_rho_q=float(first.delta_rho_q[index]),
                        **acoustic,
                    )
                )

            current_inventory = inventory(
                post_U, grid.dx, grid.geometry.area_m2
            )
            liquid_mask = regions == "LIQUID_CANDIDATE"
            two_phase_mask = regions == "OPEN_TWO_PHASE"

            def extrema(mask: np.ndarray):
                values = sound[mask]
                if values.size == 0:
                    return None, None
                return float(np.min(values)), float(np.max(values))

            liquid_c_min, liquid_c_max = extrema(liquid_mask)
            two_phase_c_min, two_phase_c_max = extrema(two_phase_mask)
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
                    np.count_nonzero(
                        events == "LIQUID_TO_TWO_PHASE_CROSSING"
                    )
                ),
                reverse_transition_event_count=int(
                    np.count_nonzero(events == "REVERSE_TRANSITION")
                ),
                projection_cell_count=int(
                    np.count_nonzero(first.projection_applied)
                ),
                second_projection_cell_count=int(
                    np.count_nonzero(second.projection_applied)
                ),
                maximum_equilibrium_quality=float(
                    np.max(q_eq, initial=0.0)
                ),
                integrated_equilibrium_quality=float(
                    np.sum(q_eq) * grid.dx
                ),
                maximum_void_fraction=float(np.max(alpha, initial=0.0)),
                pressure_min_pa=float(np.min(pressure)),
                pressure_max_pa=float(np.max(pressure)),
                liquid_sound_speed_min_m_s=liquid_c_min,
                liquid_sound_speed_max_m_s=liquid_c_max,
                two_phase_sound_speed_min_m_s=two_phase_c_min,
                two_phase_sound_speed_max_m_s=two_phase_c_max,
                mass_total_kg=float(current_inventory["mass_total"]),
                momentum_total_kg_m_s=float(
                    current_inventory["momentum_total"]
                ),
                energy_total_J=float(current_inventory["energy_total"]),
                vapor_mass_total_kg=float(
                    current_inventory["vapor_mass_total"]
                ),
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
                state_sha256=_state_sha256(post_U),
            )
            step_records.append(record)
            last_valid_hash = record.state_sha256
            if post_step in cfg.continuation_offsets:
                checkpoint_by_offset[post_step] = _checkpoint_from_step(
                    record
                )
        except Exception as exc:
            outcome = "FAIL_SAFE_STOP"
            failure_category = _failure_category(exc)
            failure_reason = f"{type(exc).__name__}: {exc}"
            failure_absolute_step = int(solver.step_count)
            failure_post_step = post_step
            break

    checkpoints = tuple(
        checkpoint_by_offset.get(
            offset,
            _missing_checkpoint(
                case.case_id,
                offset,
                int(solver.step_count),
                float(solver.t),
                last_valid_hash,
            ),
        )
        for offset in cfg.continuation_offsets
    )
    labels, rationale = _review_classifications(
        outcome=outcome,
        steps=step_records,
        baseline_open_cells=baseline_open_cells,
        region_toggle_counts=toggle_counts,
    )
    return PostCrossingPropagationResult(
        config=cfg,
        baseline=baseline,
        outcome=outcome,
        failure_category=failure_category,
        failure_reason=failure_reason,
        failure_absolute_step=failure_absolute_step,
        failure_post_crossing_step=failure_post_step,
        last_valid_state_sha256=last_valid_hash,
        steps=tuple(step_records),
        cells=tuple(cell_records),
        checkpoints=checkpoints,
        classifications=labels,
        classification_rationale=rationale,
        baseline_open_two_phase_cell_indices=baseline_open_cells,
        region_toggle_counts=tuple(toggle_counts),
        provenance=_git_provenance(),
    )


def _flatten(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten(value) for key, value in row.items()})


def _figure_metadata(result: PostCrossingPropagationResult) -> dict[str, str]:
    provenance = result.provenance
    return {
        "analysis_id": "stage7_gate6_post_crossing_propagation",
        "case": result.baseline.case.case_id,
        "model": "HEM",
        "backend": "CoolProp",
        "version": str(provenance.get("property_backend_version", "")),
        "source_git_sha": str(provenance.get("source_git_sha", "")),
    }


def _write_figures(
    target: Path,
    result: PostCrossingPropagationResult,
) -> tuple[str, ...]:
    import matplotlib.pyplot as plt

    names: list[str] = []
    steps = sorted({row.post_crossing_step for row in result.cells})
    metadata = _figure_metadata(result)
    if not steps:
        for name, title in (
            ("phase_region_space_time.png", "No accepted post-crossing step"),
            ("quality_void_fraction_space_time.png", "No accepted post-crossing step"),
            ("pressure_sound_speed_space_time.png", "No accepted post-crossing step"),
            ("inventory_residual.png", "No accepted post-crossing step"),
        ):
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, title, ha="center", va="center")
            ax.set_axis_off()
            fig.tight_layout()
            fig.savefig(target / name, dpi=160, metadata=metadata)
            plt.close(fig)
            names.append(name)
        return tuple(names)

    n_cells = result.config.pipeline.n_cells
    by_key = {
        (row.post_crossing_step, row.cell_index): row for row in result.cells
    }
    phase = np.zeros((len(steps), n_cells), dtype=float)
    q = np.zeros_like(phase)
    alpha = np.zeros_like(phase)
    pressure = np.zeros_like(phase)
    sound = np.zeros_like(phase)
    mapping = {"LIQUID_CANDIDATE": 0.0, "OPEN_TWO_PHASE": 1.0}
    for i, step in enumerate(steps):
        for cell in range(n_cells):
            row = by_key[(step, cell)]
            phase[i, cell] = mapping.get(row.post_region, 2.0)
            q[i, cell] = row.q_equilibrium
            alpha[i, cell] = row.void_fraction
            pressure[i, cell] = row.pressure_pa
            sound[i, cell] = (
                np.nan if row.sound_speed_m_s is None else row.sound_speed_m_s
            )

    fig, ax = plt.subplots()
    image = ax.imshow(
        phase,
        aspect="auto",
        origin="lower",
        extent=(0, n_cells - 1, steps[0], steps[-1]),
    )
    ax.set_xlabel("cell index")
    ax.set_ylabel("post-crossing step")
    ax.set_title("Phase region space-time map")
    fig.colorbar(image, ax=ax, label="0=liquid, 1=open two-phase")
    fig.tight_layout()
    name = "phase_region_space_time.png"
    fig.savefig(target / name, dpi=160, metadata=metadata)
    plt.close(fig)
    names.append(name)

    fig, ax = plt.subplots()
    image = ax.imshow(
        q,
        aspect="auto",
        origin="lower",
        extent=(0, n_cells - 1, steps[0], steps[-1]),
    )
    ax.set_xlabel("cell index")
    ax.set_ylabel("post-crossing step")
    ax.set_title("Equilibrium quality space-time map")
    fig.colorbar(image, ax=ax, label="q_eq")
    ax.plot(
        np.argmax(alpha, axis=1),
        steps,
        marker=".",
        linestyle="none",
        label="max alpha cell",
    )
    ax.legend()
    fig.tight_layout()
    name = "quality_void_fraction_space_time.png"
    fig.savefig(target / name, dpi=160, metadata=metadata)
    plt.close(fig)
    names.append(name)

    fig, ax = plt.subplots()
    ax.plot(steps, np.min(pressure, axis=1) / 1.0e6, label="p min [MPa]")
    ax.plot(steps, np.max(pressure, axis=1) / 1.0e6, label="p max [MPa]")
    ax.set_xlabel("post-crossing step")
    ax.set_ylabel("pressure [MPa]")
    second = ax.twinx()
    second.plot(steps, np.nanmin(sound, axis=1), linestyle="--", label="c min")
    second.plot(steps, np.nanmax(sound, axis=1), linestyle="--", label="c max")
    second.set_ylabel("c_eq [m/s]")
    ax.set_title("Pressure and sound-speed ranges")
    ax.legend(loc="upper left")
    second.legend(loc="upper right")
    fig.tight_layout()
    name = "pressure_sound_speed_space_time.png"
    fig.savefig(target / name, dpi=160, metadata=metadata)
    plt.close(fig)
    names.append(name)

    fig, ax = plt.subplots()
    step_rows = list(result.steps)
    x = [row.post_crossing_step for row in step_rows]
    ax.plot(
        x,
        [abs(row.boundary_mass_residual_kg) for row in step_rows],
        label="mass",
    )
    ax.plot(
        x,
        [abs(row.boundary_energy_residual_J) for row in step_rows],
        label="energy",
    )
    ax.plot(
        x,
        [abs(row.phase_vapor_residual_kg) for row in step_rows],
        label="vapor",
    )
    ax.set_xlabel("post-crossing step")
    ax.set_ylabel("absolute residual")
    ax.set_yscale("symlog", linthresh=1.0e-16)
    ax.set_title("Continuation inventory residuals")
    ax.legend()
    fig.tight_layout()
    name = "inventory_residual.png"
    fig.savefig(target / name, dpi=160, metadata=metadata)
    plt.close(fig)
    names.append(name)
    return tuple(names)


def write_post_crossing_propagation_artifacts(
    output_dir: str | Path,
    result: PostCrossingPropagationResult,
) -> dict[str, Path]:
    """Write the fixed Gate 6 evidence bundle."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_json": target / "summary.json",
        "checkpoints_csv": target / "checkpoints.csv",
        "cell_history_csv": target / "cell_history.csv",
        "transition_events_csv": target / "transition_events.csv",
        "inventory_csv": target / "inventory_vapor_budget.csv",
        "markdown": target / "report.md",
        "digest": target / "artifact_sha256.txt",
    }
    figures = _write_figures(target, result)
    payload = {
        **result.summary(),
        "config": {
            "baseline_case_id": BASELINE_CASE_ID,
            "continuation_offsets": list(result.config.continuation_offsets),
            "n_cells": result.config.pipeline.n_cells,
            "cfl": result.config.pipeline.cfl,
            "crossing_evidence_min_quality": (
                result.config.pipeline.crossing_evidence_min_quality
            ),
            "production_solver_changed": False,
            "sound_speed_formula_changed": False,
            "rusanov_flux_changed": False,
            "boundary_changed": False,
            "quality_projection_changed": False,
            "threshold_or_tolerance_tuned": False,
        },
        "steps": [asdict(record) for record in result.steps],
        "checkpoints": [asdict(record) for record in result.checkpoints],
        "cells": [asdict(record) for record in result.cells],
        "generated_figures": list(figures),
    }
    paths["summary_json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        paths["checkpoints_csv"],
        [asdict(record) for record in result.checkpoints],
    )
    cell_rows = [asdict(record) for record in result.cells]
    _write_csv(paths["cell_history_csv"], cell_rows)
    _write_csv(
        paths["transition_events_csv"],
        [
            row
            for row in cell_rows
            if row["transition_event"] != "NO_TRANSITION"
        ],
    )
    _write_csv(
        paths["inventory_csv"],
        [
            {
                key: value
                for key, value in asdict(record).items()
                if key
                in {
                    "absolute_step",
                    "post_crossing_step",
                    "time_after_s",
                    "mass_total_kg",
                    "momentum_total_kg_m_s",
                    "energy_total_J",
                    "vapor_mass_total_kg",
                    "boundary_mass_residual_kg",
                    "boundary_momentum_residual_kg_m_s",
                    "boundary_energy_residual_J",
                    "phase_vapor_residual_kg",
                    "projection_vapor_source_step_kg",
                    "boundary_vapor_step_kg",
                }
            }
            for record in result.steps
        ],
    )
    lines = [
        "# Stage 7 Gate 6 post-crossing propagation review",
        "",
        "`VERIFICATION ONLY; FIRST-ORDER FVM; NO PHYSICAL VALIDATION`",
        "",
        "## Baseline",
        "",
        f"- case: `{BASELINE_CASE_ID}`",
        f"- exact baseline replay: `true`",
        f"- crossing step: `{result.baseline.crossing_step}`",
        f"- crossing time: `{result.baseline.crossing_time_s}`",
        "",
        "## Continuation",
        "",
        f"- outcome: `{result.outcome}`",
        f"- reached offsets: `{result.summary()['reached_continuation_offsets']}`",
        f"- failure category: `{result.failure_category}`",
        f"- failure reason: `{result.failure_reason}`",
        "",
        "## Initial classifications",
        "",
        *(f"- `{label}`" for label in result.classifications),
        "",
        *(f"- {item}" for item in result.classification_rationale),
        "",
        "## Approval boundary",
        "",
        *(f"- `{key} = false`" for key in APPROVAL_BOUNDARY),
        "",
    ]
    paths["markdown"].write_text("\n".join(lines), encoding="utf-8")

    digest = hashlib.sha256()
    for path in sorted(target.iterdir()):
        if path.name != paths["digest"].name and path.is_file():
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
    paths["digest"].write_text(digest.hexdigest() + "\n", encoding="utf-8")
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    result = run_post_crossing_propagation_review()
    paths = write_post_crossing_propagation_artifacts(output_dir, result)
    summary = result.summary()
    summary["artifact_paths"] = {name: str(path) for name, path in paths.items()}
    return summary


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed Stage 7 Gate 6 post-crossing propagation review."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    print(json.dumps(execute(args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
