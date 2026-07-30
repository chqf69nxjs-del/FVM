"""Verification-only boundary-adjacent phase-chatter diagnosis.

This Gate 7 diagnostic replays the exact Gate 6 5 -> 2 MPa continuation and
records focused evidence for cells 29, 30, and 31 plus interfaces 29|30,
30|31, and the prescribed right boundary.

The module does not change the production solver, Rusanov flux, boundary
model, phase classifier, equilibrium sound-speed formula, quality projection,
crossing threshold, or any tolerance. It records correlation and temporal
ordering only; it does not establish root cause or authorize mitigation.
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
from typing import Sequence

import numpy as np
from CoolProp.CoolProp import PropsSI  # type: ignore

from .boundary import LinearPressureRamp, ReflectiveBoundary
from .config import PipeGeometry
from .grid import UniformGrid
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_pipeline_depressurization_boundary import (
    VerificationHEMPrescribedSubcooledOutletBoundary,
    VerificationHEMPrescribedSubcooledStateProvider,
)
from .hem_pipeline_depressurization_first_crossing import (
    _incremental_boundary_budget,
    _state_sha256,
    _validate_cumulative_budgets,
    run_pipeline_depressurization_case,
)
from .hem_pipeline_post_crossing_propagation import (
    BASELINE_CASE_ID,
    HEMPostCrossingPropagationConfig,
    HEMPostCrossingPropagationError,
    _baseline_case_spec,
    _baseline_regions,
    _classify_raw_state,
    _git_provenance,
    _project_and_accept,
    _raw_case,
    _require_exact_baseline,
    _sound_speed_evidence,
)
from .hem_liquid_to_two_phase_crossing import detect_raw_transition_events
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

FOCUS_CELLS = (29, 30, 31)
CHATTER_CELL = 30
FIXED_INTERFACE_SPECS = (
    ("cell_29_30", 29, 30),
    ("cell_30_31", 30, 31),
    ("right_boundary", 31, None),
)
EXPECTED_GATE6_FINAL_STATE_SHA256 = (
    "62bbaf5d7014af258180fe29622324a2228a0c5eec507ef10eb6b9f3e411d440"
)
EXPECTED_CELL30_TOGGLE_COUNT = 49
EXPECTED_POST_CROSSING_STEPS = 64
CORRELATION_FRACTION = 0.90

APPROVAL_BOUNDARY = {
    "Gate_7_execution_complete": False,
    "phase_chatter_root_cause_approved": False,
    "chatter_mitigation_authorized": False,
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


class HEMPhaseChatterDiagnosisError(RuntimeError):
    """Raised when the fixed Gate 7 diagnostic contract cannot be satisfied."""


@dataclass(frozen=True)
class HEMPhaseChatterDiagnosisConfig:
    """Locked Gate 7 diagnostic configuration."""

    propagation: HEMPostCrossingPropagationConfig = field(
        default_factory=HEMPostCrossingPropagationConfig
    )
    focus_cells: tuple[int, ...] = FOCUS_CELLS
    chatter_cell: int = CHATTER_CELL
    correlation_fraction: float = CORRELATION_FRACTION

    def __post_init__(self) -> None:
        if self.propagation != HEMPostCrossingPropagationConfig():
            raise ValueError("Gate 7 must reuse the exact Gate 6 configuration")
        if self.focus_cells != FOCUS_CELLS:
            raise ValueError("Gate 7 focus cells are fixed at 29 / 30 / 31")
        if self.chatter_cell != CHATTER_CELL:
            raise ValueError("Gate 7 chatter target is fixed at cell 30")
        if self.correlation_fraction != CORRELATION_FRACTION:
            raise ValueError("Gate 7 correlation fraction is fixed at 0.90")


@dataclass(frozen=True)
class FocusedCellRecord:
    case_id: str
    absolute_step: int
    post_crossing_step: int
    time_s: float
    dt_s: float
    cell_index: int
    state_stage: str
    rho_kg_m3: float
    momentum_kg_m2_s: float
    rhoE_J_m3: float
    rho_q_kg_m3: float
    velocity_m_s: float
    internal_energy_j_kg: float
    pressure_pa: float
    temperature_K: float
    raw_phase: str
    phase_class: str
    scope_status: str
    boundary_region: str
    transition_event: str
    q_transport: float
    q_equilibrium: float
    q_after_projection: float
    void_fraction: float
    projection_applied: bool
    delta_q: float
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
    saturation_temperature_K: float
    saturated_liquid_rho_kg_m3: float
    saturated_liquid_e_j_kg: float
    delta_e_from_saturated_liquid_j_kg: float
    delta_v_from_saturated_liquid_m3_kg: float


@dataclass(frozen=True)
class InterfaceFluxRecord:
    case_id: str
    absolute_step: int
    post_crossing_step: int
    time_before_s: float
    dt_s: float
    interface_label: str
    flux_array_index: int
    left_cell_index: int
    right_cell_index: int | None
    state_stage: str
    left_rho_kg_m3: float
    left_momentum_kg_m2_s: float
    left_rhoE_J_m3: float
    left_rho_q_kg_m3: float
    right_rho_kg_m3: float
    right_momentum_kg_m2_s: float
    right_rhoE_J_m3: float
    right_rho_q_kg_m3: float
    left_velocity_m_s: float
    right_velocity_m_s: float
    left_sound_speed_m_s: float
    right_sound_speed_m_s: float
    left_wave_speed_m_s: float
    right_wave_speed_m_s: float
    mass_flux: float
    momentum_flux: float
    energy_flux: float
    vapor_flux: float
    boundary_pressure_requested_pa: float | None
    boundary_temperature_requested_K: float | None
    boundary_rho_kg_m3: float | None
    boundary_e_j_kg: float | None


@dataclass(frozen=True)
class Cell30TransitionEventRecord:
    case_id: str
    absolute_step: int
    post_crossing_step: int
    time_s: float
    transition_event: str
    previous_region: str
    event_region: str
    previous_delta_e_j_kg: float
    event_delta_e_j_kg: float
    delta_e_sign_changed: bool
    previous_delta_v_m3_kg: float
    event_delta_v_m3_kg: float
    delta_v_sign_changed: bool
    previous_sound_speed_m_s: float
    event_sound_speed_m_s: float
    acoustic_branch_switched: bool
    previous_q_equilibrium: float
    event_q_equilibrium: float
    previous_projection_delta_rho_q: float
    event_projection_delta_rho_q: float
    previous_dt_s: float
    event_dt_s: float
    previous_boundary_pressure_pa: float
    event_boundary_pressure_pa: float
    boundary_pressure_change_pa: float
    previous_net_mass_flux_cell30: float
    event_net_mass_flux_cell30: float
    net_mass_flux_sign_changed: bool
    previous_net_energy_flux_cell30: float
    event_net_energy_flux_cell30: float
    net_energy_flux_sign_changed: bool
    previous_net_vapor_flux_cell30: float
    event_net_vapor_flux_cell30: float
    net_vapor_flux_sign_changed: bool
    cell29_transition_event: str
    cell31_transition_event: str
    cell29_changed_region: bool
    cell31_changed_region: bool


@dataclass(frozen=True)
class PhaseChatterDiagnosisResult:
    config: HEMPhaseChatterDiagnosisConfig
    final_state_sha256: str
    cell_toggle_counts: tuple[int, ...]
    focused_cells: tuple[FocusedCellRecord, ...]
    interface_fluxes: tuple[InterfaceFluxRecord, ...]
    transition_events: tuple[Cell30TransitionEventRecord, ...]
    classifications: tuple[str, ...]
    classification_rationale: tuple[str, ...]
    correlation_metrics: dict[str, object]
    provenance: dict[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "stage7_gate7_phase_chatter_diagnosis_v1",
            "scope": "verification_only",
            "case_id": BASELINE_CASE_ID,
            "focus_cells": list(self.config.focus_cells),
            "chatter_cell": self.config.chatter_cell,
            "fixed_post_crossing_steps": EXPECTED_POST_CROSSING_STEPS,
            "final_state_sha256": self.final_state_sha256,
            "expected_final_state_sha256": EXPECTED_GATE6_FINAL_STATE_SHA256,
            "gate6_final_state_reproduced_exactly": (
                self.final_state_sha256 == EXPECTED_GATE6_FINAL_STATE_SHA256
            ),
            "cell_toggle_counts": list(self.cell_toggle_counts),
            "cell30_toggle_count": self.cell_toggle_counts[CHATTER_CELL],
            "expected_cell30_toggle_count": EXPECTED_CELL30_TOGGLE_COUNT,
            "focused_cell_record_count": len(self.focused_cells),
            "interface_flux_record_count": len(self.interface_fluxes),
            "transition_event_record_count": len(self.transition_events),
            "classifications": list(self.classifications),
            "classification_rationale": list(self.classification_rationale),
            "correlation_metrics": dict(self.correlation_metrics),
            "provenance": dict(self.provenance),
            "algorithms_or_tolerances_tuned": False,
            "production_default_changed": False,
            **APPROVAL_BOUNDARY,
        }


def _sign(value: float) -> int:
    if value > 0.0:
        return 1
    if value < 0.0:
        return -1
    return 0


def _saturation_margin(
    rho_kg_m3: float,
    e_j_kg: float,
    pressure_pa: float,
) -> dict[str, float]:
    if not all(np.isfinite(value) for value in (rho_kg_m3, e_j_kg, pressure_pa)):
        raise HEMPhaseChatterDiagnosisError(
            "saturation-margin inputs must be finite"
        )
    if rho_kg_m3 <= 0.0 or pressure_pa <= 0.0:
        raise HEMPhaseChatterDiagnosisError(
            "saturation-margin density and pressure must be positive"
        )
    try:
        saturation_temperature = float(
            PropsSI("T", "P", pressure_pa, "Q", 0.0, "CO2")
        )
        saturated_rho = float(
            PropsSI("DMASS", "P", pressure_pa, "Q", 0.0, "CO2")
        )
        saturated_e = float(
            PropsSI("UMASS", "P", pressure_pa, "Q", 0.0, "CO2")
        )
    except Exception as exc:
        raise HEMPhaseChatterDiagnosisError(
            f"saturated-liquid reference evaluation failed: {exc}"
        ) from exc
    values = (saturation_temperature, saturated_rho, saturated_e)
    if not all(np.isfinite(value) for value in values):
        raise HEMPhaseChatterDiagnosisError(
            "saturated-liquid reference contains a non-finite value"
        )
    if saturation_temperature <= 0.0 or saturated_rho <= 0.0:
        raise HEMPhaseChatterDiagnosisError(
            "saturated-liquid temperature and density must be positive"
        )
    return {
        "saturation_temperature_K": saturation_temperature,
        "saturated_liquid_rho_kg_m3": saturated_rho,
        "saturated_liquid_e_j_kg": saturated_e,
        "delta_e_from_saturated_liquid_j_kg": e_j_kg - saturated_e,
        "delta_v_from_saturated_liquid_m3_kg": (
            1.0 / rho_kg_m3 - 1.0 / saturated_rho
        ),
    }


def _phase_strings(phase_state, index: int) -> tuple[str, str, str]:
    return (
        str(np.asarray(phase_state.raw_phase).astype(str)[index]),
        str(np.asarray(phase_state.phase_class).astype(str)[index]),
        str(np.asarray(phase_state.scope_status).astype(str)[index]),
    )


def _focused_cell_record(
    *,
    case_id: str,
    absolute_step: int,
    post_step: int,
    time_s: float,
    dt_s: float,
    cell_index: int,
    state_stage: str,
    U: np.ndarray,
    pressure_pa: float,
    temperature_K: float,
    phase_state,
    region: str,
    transition_event: str,
    q_equilibrium: float,
    q_after_projection: float,
    void_fraction: float,
    projection_applied: bool,
    delta_q: float,
    delta_rho_q: float,
) -> FocusedCellRecord:
    rho = float(U[cell_index, IDX_RHO])
    e = float(internal_energy(U[cell_index]))
    q_transport = float(U[cell_index, IDX_RHO_XV] / rho)
    raw_phase, phase_class, scope_status = _phase_strings(
        phase_state, cell_index
    )
    acoustic = _sound_speed_evidence(rho, e)
    margin = _saturation_margin(rho, e, pressure_pa)
    return FocusedCellRecord(
        case_id=case_id,
        absolute_step=absolute_step,
        post_crossing_step=post_step,
        time_s=time_s,
        dt_s=dt_s,
        cell_index=cell_index,
        state_stage=state_stage,
        rho_kg_m3=rho,
        momentum_kg_m2_s=float(U[cell_index, IDX_MOM]),
        rhoE_J_m3=float(U[cell_index, IDX_RHOE]),
        rho_q_kg_m3=float(U[cell_index, IDX_RHO_XV]),
        velocity_m_s=float(velocity(U[cell_index])),
        internal_energy_j_kg=e,
        pressure_pa=float(pressure_pa),
        temperature_K=float(temperature_K),
        raw_phase=raw_phase,
        phase_class=phase_class,
        scope_status=scope_status,
        boundary_region=str(region),
        transition_event=str(transition_event),
        q_transport=q_transport,
        q_equilibrium=float(q_equilibrium),
        q_after_projection=float(q_after_projection),
        void_fraction=float(void_fraction),
        projection_applied=bool(projection_applied),
        delta_q=float(delta_q),
        delta_rho_q=float(delta_rho_q),
        **acoustic,
        **margin,
    )


def _interface_flux_records(
    *,
    case_id: str,
    absolute_step: int,
    post_step: int,
    time_before_s: float,
    dt_s: float,
    solver: FvmSolver,
    right_boundary,
) -> tuple[InterfaceFluxRecord, ...]:
    U_ext = solver.extend_with_ghosts(time_before_s)
    primitive_ext = solver.eos.primitive_from_conserved(U_ext)
    fluxes = solver.flux_function(U_ext[:-1], U_ext[1:], solver.eos)
    boundary_state = right_boundary.last_state
    records: list[InterfaceFluxRecord] = []
    for label, left_cell, right_cell in FIXED_INTERFACE_SPECS:
        flux_index = solver.n_ghost + left_cell
        left_ext_index = solver.n_ghost + left_cell
        right_ext_index = left_ext_index + 1
        left_U = U_ext[left_ext_index]
        right_U = U_ext[right_ext_index]
        left_u = float(np.asarray(primitive_ext.u)[left_ext_index])
        right_u = float(np.asarray(primitive_ext.u)[right_ext_index])
        left_c = float(np.asarray(primitive_ext.c)[left_ext_index])
        right_c = float(np.asarray(primitive_ext.c)[right_ext_index])
        flux = np.asarray(fluxes[flux_index], dtype=float)
        if flux.shape != (N_VARS,) or not np.all(np.isfinite(flux)):
            raise HEMPhaseChatterDiagnosisError(
                f"interface {label} returned an invalid flux"
            )
        is_boundary = right_cell is None
        records.append(
            InterfaceFluxRecord(
                case_id=case_id,
                absolute_step=absolute_step,
                post_crossing_step=post_step,
                time_before_s=time_before_s,
                dt_s=dt_s,
                interface_label=label,
                flux_array_index=flux_index,
                left_cell_index=left_cell,
                right_cell_index=right_cell,
                state_stage="pre_step_accepted_flux_evaluation",
                left_rho_kg_m3=float(left_U[IDX_RHO]),
                left_momentum_kg_m2_s=float(left_U[IDX_MOM]),
                left_rhoE_J_m3=float(left_U[IDX_RHOE]),
                left_rho_q_kg_m3=float(left_U[IDX_RHO_XV]),
                right_rho_kg_m3=float(right_U[IDX_RHO]),
                right_momentum_kg_m2_s=float(right_U[IDX_MOM]),
                right_rhoE_J_m3=float(right_U[IDX_RHOE]),
                right_rho_q_kg_m3=float(right_U[IDX_RHO_XV]),
                left_velocity_m_s=left_u,
                right_velocity_m_s=right_u,
                left_sound_speed_m_s=left_c,
                right_sound_speed_m_s=right_c,
                left_wave_speed_m_s=abs(left_u) + left_c,
                right_wave_speed_m_s=abs(right_u) + right_c,
                mass_flux=float(flux[IDX_RHO]),
                momentum_flux=float(flux[IDX_MOM]),
                energy_flux=float(flux[IDX_RHOE]),
                vapor_flux=float(flux[IDX_RHO_XV]),
                boundary_pressure_requested_pa=(
                    float(boundary_state.pressure_requested_pa)
                    if is_boundary and boundary_state is not None
                    else None
                ),
                boundary_temperature_requested_K=(
                    float(boundary_state.temperature_requested_K)
                    if is_boundary and boundary_state is not None
                    else None
                ),
                boundary_rho_kg_m3=(
                    float(boundary_state.rho_kg_m3)
                    if is_boundary and boundary_state is not None
                    else None
                ),
                boundary_e_j_kg=(
                    float(boundary_state.e_j_kg)
                    if is_boundary and boundary_state is not None
                    else None
                ),
            )
        )
    return tuple(records)


def _build_transition_events(
    focused_cells: Sequence[FocusedCellRecord],
    interface_fluxes: Sequence[InterfaceFluxRecord],
) -> tuple[Cell30TransitionEventRecord, ...]:
    post_by_key = {
        (row.post_crossing_step, row.cell_index): row
        for row in focused_cells
        if row.state_stage == "post_projection_accepted"
    }
    flux_by_key = {
        (row.post_crossing_step, row.interface_label): row
        for row in interface_fluxes
    }
    events: list[Cell30TransitionEventRecord] = []
    for step in range(2, EXPECTED_POST_CROSSING_STEPS + 1):
        current = post_by_key[(step, CHATTER_CELL)]
        previous = post_by_key[(step - 1, CHATTER_CELL)]
        if current.boundary_region == previous.boundary_region:
            continue
        left_now = flux_by_key[(step, "cell_29_30")]
        right_now = flux_by_key[(step, "cell_30_31")]
        boundary_now = flux_by_key[(step, "right_boundary")]
        left_previous = flux_by_key[(step - 1, "cell_29_30")]
        right_previous = flux_by_key[(step - 1, "cell_30_31")]
        boundary_previous = flux_by_key[(step - 1, "right_boundary")]

        previous_net_mass = (
            left_previous.mass_flux - right_previous.mass_flux
        )
        event_net_mass = left_now.mass_flux - right_now.mass_flux
        previous_net_energy = (
            left_previous.energy_flux - right_previous.energy_flux
        )
        event_net_energy = left_now.energy_flux - right_now.energy_flux
        previous_net_vapor = (
            left_previous.vapor_flux - right_previous.vapor_flux
        )
        event_net_vapor = left_now.vapor_flux - right_now.vapor_flux

        cell29 = post_by_key[(step, 29)]
        cell31 = post_by_key[(step, 31)]
        events.append(
            Cell30TransitionEventRecord(
                case_id=current.case_id,
                absolute_step=current.absolute_step,
                post_crossing_step=step,
                time_s=current.time_s,
                transition_event=current.transition_event,
                previous_region=previous.boundary_region,
                event_region=current.boundary_region,
                previous_delta_e_j_kg=(
                    previous.delta_e_from_saturated_liquid_j_kg
                ),
                event_delta_e_j_kg=(
                    current.delta_e_from_saturated_liquid_j_kg
                ),
                delta_e_sign_changed=(
                    _sign(previous.delta_e_from_saturated_liquid_j_kg)
                    != _sign(current.delta_e_from_saturated_liquid_j_kg)
                ),
                previous_delta_v_m3_kg=(
                    previous.delta_v_from_saturated_liquid_m3_kg
                ),
                event_delta_v_m3_kg=(
                    current.delta_v_from_saturated_liquid_m3_kg
                ),
                delta_v_sign_changed=(
                    _sign(previous.delta_v_from_saturated_liquid_m3_kg)
                    != _sign(current.delta_v_from_saturated_liquid_m3_kg)
                ),
                previous_sound_speed_m_s=float(previous.sound_speed_m_s),
                event_sound_speed_m_s=float(current.sound_speed_m_s),
                acoustic_branch_switched=(
                    previous.boundary_region != current.boundary_region
                ),
                previous_q_equilibrium=previous.q_equilibrium,
                event_q_equilibrium=current.q_equilibrium,
                previous_projection_delta_rho_q=previous.delta_rho_q,
                event_projection_delta_rho_q=current.delta_rho_q,
                previous_dt_s=previous.dt_s,
                event_dt_s=current.dt_s,
                previous_boundary_pressure_pa=float(
                    boundary_previous.boundary_pressure_requested_pa
                ),
                event_boundary_pressure_pa=float(
                    boundary_now.boundary_pressure_requested_pa
                ),
                boundary_pressure_change_pa=float(
                    boundary_now.boundary_pressure_requested_pa
                    - boundary_previous.boundary_pressure_requested_pa
                ),
                previous_net_mass_flux_cell30=previous_net_mass,
                event_net_mass_flux_cell30=event_net_mass,
                net_mass_flux_sign_changed=(
                    _sign(previous_net_mass) != _sign(event_net_mass)
                ),
                previous_net_energy_flux_cell30=previous_net_energy,
                event_net_energy_flux_cell30=event_net_energy,
                net_energy_flux_sign_changed=(
                    _sign(previous_net_energy) != _sign(event_net_energy)
                ),
                previous_net_vapor_flux_cell30=previous_net_vapor,
                event_net_vapor_flux_cell30=event_net_vapor,
                net_vapor_flux_sign_changed=(
                    _sign(previous_net_vapor) != _sign(event_net_vapor)
                ),
                cell29_transition_event=cell29.transition_event,
                cell31_transition_event=cell31.transition_event,
                cell29_changed_region=(
                    cell29.boundary_region
                    != post_by_key[(step - 1, 29)].boundary_region
                ),
                cell31_changed_region=(
                    cell31.boundary_region
                    != post_by_key[(step - 1, 31)].boundary_region
                ),
            )
        )
    return tuple(events)


def _fraction(
    events: Sequence[Cell30TransitionEventRecord],
    attribute: str,
) -> float:
    if not events:
        return 0.0
    return sum(bool(getattr(event, attribute)) for event in events) / len(events)


def _review_classifications(
    *,
    toggle_counts: Sequence[int],
    focused_cells: Sequence[FocusedCellRecord],
    events: Sequence[Cell30TransitionEventRecord],
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, object]]:
    labels: list[str] = []
    rationale: list[str] = []
    metrics: dict[str, object] = {
        "event_count": len(events),
        "delta_e_sign_change_fraction": _fraction(
            events, "delta_e_sign_changed"
        ),
        "delta_v_sign_change_fraction": _fraction(
            events, "delta_v_sign_changed"
        ),
        "acoustic_branch_switch_fraction": _fraction(
            events, "acoustic_branch_switched"
        ),
        "net_mass_flux_sign_change_fraction": _fraction(
            events, "net_mass_flux_sign_changed"
        ),
        "net_energy_flux_sign_change_fraction": _fraction(
            events, "net_energy_flux_sign_changed"
        ),
        "net_vapor_flux_sign_change_fraction": _fraction(
            events, "net_vapor_flux_sign_changed"
        ),
    }
    post30 = [
        row
        for row in focused_cells
        if row.cell_index == CHATTER_CELL
        and row.state_stage == "post_projection_accepted"
    ]
    liquid_speeds = [
        float(row.sound_speed_m_s)
        for row in post30
        if row.boundary_region == "LIQUID_CANDIDATE"
        and row.sound_speed_m_s is not None
    ]
    two_phase_speeds = [
        float(row.sound_speed_m_s)
        for row in post30
        if row.boundary_region == "OPEN_TWO_PHASE"
        and row.sound_speed_m_s is not None
    ]
    metrics.update(
        {
            "cell29_toggle_count": int(toggle_counts[29]),
            "cell30_toggle_count": int(toggle_counts[30]),
            "cell31_toggle_count": int(toggle_counts[31]),
            "cell30_liquid_sound_speed_min_m_s": (
                min(liquid_speeds) if liquid_speeds else None
            ),
            "cell30_liquid_sound_speed_max_m_s": (
                max(liquid_speeds) if liquid_speeds else None
            ),
            "cell30_two_phase_sound_speed_min_m_s": (
                min(two_phase_speeds) if two_phase_speeds else None
            ),
            "cell30_two_phase_sound_speed_max_m_s": (
                max(two_phase_speeds) if two_phase_speeds else None
            ),
        }
    )

    if (
        toggle_counts[29] <= 1
        and toggle_counts[30] == EXPECTED_CELL30_TOGGLE_COUNT
        and toggle_counts[31] <= 1
    ):
        labels.append("STABLE_FRONT_SEPARATED_FROM_CHATTER")
        rationale.append(
            "Cell 30 retained the fixed 49 region changes while cells 29 and "
            "31 did not exhibit repeated toggling."
        )

    margin_fraction = min(
        float(metrics["delta_e_sign_change_fraction"]),
        float(metrics["delta_v_sign_change_fraction"]),
    )
    if events and margin_fraction >= CORRELATION_FRACTION:
        labels.append("PHASE_MARGIN_OSCILLATION_CORRELATED")
        rationale.append(
            "At least 90% of cell-30 region changes coincided with sign "
            "changes in both fixed saturated-liquid margin coordinates."
        )

    acoustic_fraction = float(metrics["acoustic_branch_switch_fraction"])
    bands_separated = bool(
        liquid_speeds
        and two_phase_speeds
        and min(liquid_speeds) > max(two_phase_speeds)
    )
    metrics["acoustic_bands_non_overlapping"] = bands_separated
    if (
        events
        and acoustic_fraction >= CORRELATION_FRACTION
        and bands_separated
    ):
        labels.append("ACOUSTIC_BRANCH_SWITCH_CORRELATED")
        rationale.append(
            "At least 90% of region changes switched between non-overlapping "
            "liquid and open-two-phase sound-speed bands."
        )

    flux_fraction = max(
        float(metrics["net_mass_flux_sign_change_fraction"]),
        float(metrics["net_energy_flux_sign_change_fraction"]),
        float(metrics["net_vapor_flux_sign_change_fraction"]),
    )
    if events and flux_fraction >= CORRELATION_FRACTION:
        labels.append("INTERFACE_FLUX_OSCILLATION_CORRELATED")
        rationale.append(
            "At least one fixed cell-30 net interface-flux component changed "
            "sign on at least 90% of region-change events."
        )

    projection_fraction = (
        sum(
            abs(event.event_projection_delta_rho_q) > 0.0
            for event in events
        )
        / len(events)
        if events
        else 0.0
    )
    metrics["projection_activity_fraction_at_events"] = projection_fraction
    if events and projection_fraction >= CORRELATION_FRACTION:
        labels.append("PROJECTION_ACTIVITY_CORRELATED")
        rationale.append(
            "Cell-30 quality projection was active on at least 90% of fixed "
            "region-change events."
        )

    boundary_changes = [
        event.boundary_pressure_change_pa for event in events
    ]
    monotonic_boundary = bool(
        boundary_changes and all(value <= 0.0 for value in boundary_changes)
    )
    metrics["boundary_pressure_monotonic_at_events"] = monotonic_boundary
    metrics["boundary_pressure_change_min_pa"] = (
        min(boundary_changes) if boundary_changes else None
    )
    metrics["boundary_pressure_change_max_pa"] = (
        max(boundary_changes) if boundary_changes else None
    )
    # A monotonic ramp is retained as context, not labeled as oscillatory forcing.

    correlation_labels = [
        label
        for label in labels
        if label.endswith("_CORRELATED")
    ]
    if len(correlation_labels) >= 2:
        labels.append("MULTI_FACTOR_CHATTER")
        rationale.append(
            "Multiple predeclared event-aligned correlations are present; "
            "none is treated as a proven root cause."
        )
    labels.append("CHATTER_REVIEW_INCONCLUSIVE")
    rationale.append(
        "The diagnostic records correlation and temporal ordering only; "
        "root cause and mitigation remain unapproved."
    )
    return tuple(labels), tuple(rationale), metrics


def run_phase_chatter_diagnosis(
    config: HEMPhaseChatterDiagnosisConfig | None = None,
) -> PhaseChatterDiagnosisResult:
    """Execute the fixed Gate 7 focused diagnostic."""

    cfg = config or HEMPhaseChatterDiagnosisConfig()
    propagation = cfg.propagation
    pipeline = propagation.pipeline
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
    initial_inventory = inventory(
        crossing_U, grid.dx, grid.geometry.area_m2
    )
    phase_tracker = PhaseChangeBudgetTracker(
        initial_inventory=initial_inventory
    )
    previous_regions = list(_baseline_regions(baseline))
    toggle_counts = [0] * pipeline.n_cells
    focused_records: list[FocusedCellRecord] = []
    interface_records: list[InterfaceFluxRecord] = []
    latest_projected_budget: dict[str, float] = {}

    for post_step in range(1, EXPECTED_POST_CROSSING_STEPS + 1):
        time_before = float(solver.t)
        previous_U = np.array(solver.U, dtype=float, copy=True)
        previous_primitive = solver.primitive()
        previous_inventory = inventory(
            previous_U, grid.dx, grid.geometry.area_m2
        )
        if solver.boundary_budget is None:
            raise HEMPhaseChatterDiagnosisError(
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
            raise HEMPhaseChatterDiagnosisError(
                "computed continuation dt must be finite and positive"
            )

        interface_records.extend(
            _interface_flux_records(
                case_id=case.case_id,
                absolute_step=int(solver.step_count + 1),
                post_step=post_step,
                time_before_s=time_before,
                dt_s=dt,
                solver=solver,
                right_boundary=right_boundary,
            )
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
            raise HEMPhaseChatterDiagnosisError(
                "reverse flow fallback was activated"
            )

        detection = detect_raw_transition_events(
            previous_U,
            raw_U,
            phase_config=pipeline.phase_config,
        )
        raw_class = _classify_raw_state(detection)
        if raw_class not in {"OPEN_TWO_PHASE", "ALL_LIQUID"}:
            raise HEMPhaseChatterDiagnosisError(
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
        _validate_cumulative_budgets(
            solver=solver,
            phase_tracker=phase_tracker,
            initial_inventory=initial_inventory,
            latest_projected_budget=latest_projected_budget,
            config=pipeline,
        )

        previous_phase_state = detection.previous.phase_state
        raw_phase_state = detection.raw.phase_state
        previous_detection_regions = np.asarray(
            detection.previous.region
        ).astype(str)
        raw_regions = np.asarray(detection.raw.region).astype(str)
        events = np.asarray(detection.transitions.event).astype(str)
        post_regions_array = np.asarray(post_regions).astype(str)
        raw_pressure = np.asarray(raw_phase_state.p, dtype=float)
        raw_temperature = np.asarray(raw_phase_state.T, dtype=float)
        raw_quality = np.asarray(raw_phase_state.quality, dtype=float)
        raw_alpha = np.asarray(raw_phase_state.alpha, dtype=float)
        previous_pressure = np.asarray(
            previous_phase_state.p, dtype=float
        )
        previous_temperature = np.asarray(
            previous_phase_state.T, dtype=float
        )
        previous_quality = np.asarray(
            previous_phase_state.quality, dtype=float
        )
        previous_alpha = np.asarray(
            previous_phase_state.alpha, dtype=float
        )
        post_pressure = np.asarray(primitive.p, dtype=float)
        post_temperature = np.asarray(primitive.T, dtype=float)
        post_alpha = np.asarray(primitive.alpha, dtype=float)
        q_post = np.asarray(vapor_mass_fraction(post_U), dtype=float)

        for index, region in enumerate(post_regions_array):
            if str(region) != previous_regions[index]:
                toggle_counts[index] += 1
            previous_regions[index] = str(region)

        for cell_index in cfg.focus_cells:
            focused_records.append(
                _focused_cell_record(
                    case_id=case.case_id,
                    absolute_step=int(solver.step_count),
                    post_step=post_step,
                    time_s=time_before,
                    dt_s=dt,
                    cell_index=cell_index,
                    state_stage="pre_step_accepted",
                    U=previous_U,
                    pressure_pa=float(previous_pressure[cell_index]),
                    temperature_K=float(previous_temperature[cell_index]),
                    phase_state=previous_phase_state,
                    region=str(previous_detection_regions[cell_index]),
                    transition_event="PRE_STEP_STATE",
                    q_equilibrium=float(previous_quality[cell_index]),
                    q_after_projection=float(
                        previous_U[cell_index, IDX_RHO_XV]
                        / previous_U[cell_index, IDX_RHO]
                    ),
                    void_fraction=float(previous_alpha[cell_index]),
                    projection_applied=False,
                    delta_q=0.0,
                    delta_rho_q=0.0,
                )
            )
            focused_records.append(
                _focused_cell_record(
                    case_id=case.case_id,
                    absolute_step=int(solver.step_count),
                    post_step=post_step,
                    time_s=float(solver.t),
                    dt_s=dt,
                    cell_index=cell_index,
                    state_stage="raw_post_fvm",
                    U=raw_U,
                    pressure_pa=float(raw_pressure[cell_index]),
                    temperature_K=float(raw_temperature[cell_index]),
                    phase_state=raw_phase_state,
                    region=str(raw_regions[cell_index]),
                    transition_event=str(events[cell_index]),
                    q_equilibrium=float(raw_quality[cell_index]),
                    q_after_projection=float(q_post[cell_index]),
                    void_fraction=float(raw_alpha[cell_index]),
                    projection_applied=bool(
                        first.projection_applied[cell_index]
                    ),
                    delta_q=float(first.delta_q[cell_index]),
                    delta_rho_q=float(first.delta_rho_q[cell_index]),
                )
            )
            focused_records.append(
                _focused_cell_record(
                    case_id=case.case_id,
                    absolute_step=int(solver.step_count),
                    post_step=post_step,
                    time_s=float(solver.t),
                    dt_s=dt,
                    cell_index=cell_index,
                    state_stage="post_projection_accepted",
                    U=post_U,
                    pressure_pa=float(post_pressure[cell_index]),
                    temperature_K=float(post_temperature[cell_index]),
                    phase_state=raw_phase_state,
                    region=str(post_regions_array[cell_index]),
                    transition_event=str(events[cell_index]),
                    q_equilibrium=float(first.q_equilibrium[cell_index]),
                    q_after_projection=float(q_post[cell_index]),
                    void_fraction=float(post_alpha[cell_index]),
                    projection_applied=bool(
                        first.projection_applied[cell_index]
                    ),
                    delta_q=float(first.delta_q[cell_index]),
                    delta_rho_q=float(first.delta_rho_q[cell_index]),
                )
            )

        if np.any(second.projection_applied) or not np.array_equal(
            second.U_after, post_U
        ):
            raise HEMPhaseChatterDiagnosisError(
                "second projection must remain an exact no-op"
            )

    final_hash = _state_sha256(solver.U)
    if final_hash != EXPECTED_GATE6_FINAL_STATE_SHA256:
        raise HEMPhaseChatterDiagnosisError(
            "Gate 6 final accepted-state identity mismatch: "
            f"{final_hash}"
        )
    if toggle_counts[CHATTER_CELL] != EXPECTED_CELL30_TOGGLE_COUNT:
        raise HEMPhaseChatterDiagnosisError(
            "cell 30 toggle count mismatch: "
            f"{toggle_counts[CHATTER_CELL]}"
        )

    transition_records = _build_transition_events(
        focused_records, interface_records
    )
    if len(transition_records) != EXPECTED_CELL30_TOGGLE_COUNT:
        raise HEMPhaseChatterDiagnosisError(
            "cell 30 transition-event record count mismatch: "
            f"{len(transition_records)}"
        )
    labels, rationale, metrics = _review_classifications(
        toggle_counts=toggle_counts,
        focused_cells=focused_records,
        events=transition_records,
    )
    return PhaseChatterDiagnosisResult(
        config=cfg,
        final_state_sha256=final_hash,
        cell_toggle_counts=tuple(toggle_counts),
        focused_cells=tuple(focused_records),
        interface_fluxes=tuple(interface_records),
        transition_events=transition_records,
        classifications=labels,
        classification_rationale=rationale,
        correlation_metrics=metrics,
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
            writer.writerow(
                {key: _flatten(value) for key, value in row.items()}
            )


def _write_figures(
    target: Path,
    result: PhaseChatterDiagnosisResult,
) -> tuple[str, ...]:
    import matplotlib.pyplot as plt

    post30 = sorted(
        (
            row
            for row in result.focused_cells
            if row.cell_index == CHATTER_CELL
            and row.state_stage == "post_projection_accepted"
        ),
        key=lambda row: row.post_crossing_step,
    )
    steps = [row.post_crossing_step for row in post30]
    region = [
        1.0 if row.boundary_region == "OPEN_TWO_PHASE" else 0.0
        for row in post30
    ]

    fig, ax = plt.subplots()
    ax.step(steps, region, where="post", label="cell 30 region")
    ax.set_xlabel("post-crossing step")
    ax.set_ylabel("region (0=liquid, 1=open two-phase)")
    ax2 = ax.twinx()
    ax2.plot(
        steps,
        [row.delta_e_from_saturated_liquid_j_kg for row in post30],
        label="delta e from saturated liquid",
    )
    ax2.plot(
        steps,
        [row.sound_speed_m_s for row in post30],
        label="sound speed",
    )
    ax2.set_ylabel("margin / sound speed")
    ax.set_title("Cell 30 phase, saturation margin, and sound speed")
    fig.tight_layout()
    name1 = "phase_margin_sound_speed.png"
    fig.savefig(target / name1, dpi=160)
    plt.close(fig)

    by_label = {
        label: sorted(
            (
                row
                for row in result.interface_fluxes
                if row.interface_label == label
            ),
            key=lambda row: row.post_crossing_step,
        )
        for label, _, _ in FIXED_INTERFACE_SPECS
    }
    left = by_label["cell_29_30"]
    right = by_label["cell_30_31"]
    boundary = by_label["right_boundary"]
    fig, ax = plt.subplots()
    ax.plot(
        [row.post_crossing_step for row in left],
        [row.mass_flux for row in left],
        label="mass flux 29|30",
    )
    ax.plot(
        [row.post_crossing_step for row in right],
        [row.mass_flux for row in right],
        label="mass flux 30|31",
    )
    ax.set_xlabel("post-crossing step")
    ax.set_ylabel("mass flux")
    ax2 = ax.twinx()
    ax2.plot(
        [row.post_crossing_step for row in boundary],
        [row.boundary_pressure_requested_pa for row in boundary],
        label="boundary pressure",
    )
    ax2.set_ylabel("boundary pressure [Pa]")
    ax.set_title("Cell-30 interface fluxes and boundary pressure")
    fig.tight_layout()
    name2 = "interface_flux_boundary_pressure.png"
    fig.savefig(target / name2, dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.plot(
        steps,
        [row.q_equilibrium for row in post30],
        label="cell 30 q_eq",
    )
    ax.plot(
        steps,
        [row.q_after_projection for row in post30],
        label="cell 30 q_post",
    )
    ax.set_xlabel("post-crossing step")
    ax.set_ylabel("quality")
    ax2 = ax.twinx()
    ax2.plot(
        steps,
        [row.delta_rho_q for row in post30],
        label="projection delta rho*q",
    )
    ax2.set_ylabel("delta rho*q")
    ax.set_title("Cell 30 quality and projection activity")
    fig.tight_layout()
    name3 = "projection_quality.png"
    fig.savefig(target / name3, dpi=160)
    plt.close(fig)
    return (name1, name2, name3)


def _digest_files(target: Path, names: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(names):
        path = target / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def write_phase_chatter_diagnosis_artifacts(
    output_dir: str | Path,
    result: PhaseChatterDiagnosisResult,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_json": target / "summary.json",
        "cell_history_csv": target / "cell_29_30_31_history.csv",
        "transition_events_csv": target / "cell_30_transition_events.csv",
        "interface_flux_csv": target / "interface_flux_history.csv",
        "saturation_margin_csv": target / "saturation_margin_history.csv",
        "markdown": target / "report.md",
        "digest": target / "artifact_sha256.txt",
    }
    payload = {
        **result.summary(),
        "config": {
            "focus_cells": list(result.config.focus_cells),
            "chatter_cell": result.config.chatter_cell,
            "correlation_fraction": result.config.correlation_fraction,
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "boundary_changed": False,
            "phase_classifier_changed": False,
            "sound_speed_formula_changed": False,
            "quality_projection_changed": False,
            "threshold_or_tolerance_tuned": False,
            "chatter_suppression_added": False,
        },
        "focused_cells": [asdict(row) for row in result.focused_cells],
        "interface_fluxes": [
            asdict(row) for row in result.interface_fluxes
        ],
        "transition_events": [
            asdict(row) for row in result.transition_events
        ],
    }
    paths["summary_json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        paths["cell_history_csv"],
        [asdict(row) for row in result.focused_cells],
    )
    _write_csv(
        paths["transition_events_csv"],
        [asdict(row) for row in result.transition_events],
    )
    _write_csv(
        paths["interface_flux_csv"],
        [asdict(row) for row in result.interface_fluxes],
    )
    margin_rows = [
        {
            "case_id": row.case_id,
            "absolute_step": row.absolute_step,
            "post_crossing_step": row.post_crossing_step,
            "time_s": row.time_s,
            "cell_index": row.cell_index,
            "state_stage": row.state_stage,
            "boundary_region": row.boundary_region,
            "pressure_pa": row.pressure_pa,
            "saturation_temperature_K": row.saturation_temperature_K,
            "saturated_liquid_rho_kg_m3": (
                row.saturated_liquid_rho_kg_m3
            ),
            "saturated_liquid_e_j_kg": row.saturated_liquid_e_j_kg,
            "delta_e_from_saturated_liquid_j_kg": (
                row.delta_e_from_saturated_liquid_j_kg
            ),
            "delta_v_from_saturated_liquid_m3_kg": (
                row.delta_v_from_saturated_liquid_m3_kg
            ),
        }
        for row in result.focused_cells
    ]
    _write_csv(paths["saturation_margin_csv"], margin_rows)

    lines = [
        "# Stage 7 Gate 7 Boundary-Adjacent Phase-Chatter Diagnosis",
        "",
        "`VERIFICATION ONLY; CORRELATION IS NOT ROOT CAUSE`",
        "",
        f"- final Gate 6 state reproduced exactly: {str(result.final_state_sha256 == EXPECTED_GATE6_FINAL_STATE_SHA256).lower()}",
        f"- cell 30 region changes: {result.cell_toggle_counts[CHATTER_CELL]}",
        f"- event records: {len(result.transition_events)}",
        "",
        "## Reviewed correlation labels",
        "",
    ]
    lines.extend(f"- `{label}`" for label in result.classifications)
    lines.extend(
        [
            "",
            "## Correlation metrics",
            "",
            "```json",
            json.dumps(result.correlation_metrics, indent=2, sort_keys=True),
            "```",
            "",
            "## Approval boundary",
            "",
            "```text",
        ]
    )
    lines.extend(
        f"{key} = false" for key in APPROVAL_BOUNDARY
    )
    lines.extend(["```", ""])
    paths["markdown"].write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    figure_names = _write_figures(target, result)
    evidence_names = [
        path.name
        for key, path in paths.items()
        if key != "digest"
    ] + list(figure_names)
    digest = _digest_files(target, evidence_names)
    paths["digest"].write_text(digest + "\n", encoding="utf-8")
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed Stage 7 Gate 7 phase-chatter diagnosis."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run_phase_chatter_diagnosis()
    paths = write_phase_chatter_diagnosis_artifacts(
        args.output_dir, result
    )
    output = result.summary()
    output["artifact_paths"] = {
        key: str(path) for key, path in paths.items()
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
