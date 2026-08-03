"""Gate 9 D5: integrate the fixed three CFL event-aligned columns.

This verification-only increment executes and validates the already-reviewed D4
observation paths for CFL 0.10 / 0.05 / 0.025, then writes one same-schema
cross-CFL evidence bundle.  It adds post-run thermodynamic coordinates and
neutral comparison tables, but it does not assign D6 correlation labels or
approve a root cause, mitigation, physical validation, design use, or production
activation.

No production equation, Rusanov expression, CFL calculation, sound-speed
formula, phase classifier, quality projection, crossing threshold, tolerance,
boundary condition, or formal stop is changed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .hem_gate9_event_alignment import (
    D4_CAPTURED_STAGES,
    Gate9D4AlignedAcousticRecord,
    Gate9D4CflDecisionRecord,
    Gate9D4ExactCellStageRecord,
    Gate9D4Result,
    Gate9D4TimelineRecord,
    run_gate9_d4_identity_pair,
)
from .hem_gate9_refined_event_alignment import (
    Gate9D4RefinedColumnResult,
    run_gate9_d4_refined_columns,
)
from .hem_phase_classification import evaluate_coolprop_hem_phase_state
from .hem_pipeline_crossing_depth_diagnosis import (
    GATE9_FOCUS_CELLS,
    Gate9CellStageRecord,
    Gate9InterfaceFluxRecord,
    solver_identity,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineStepRecord,
    run_pipeline_depressurization_case,
)
from .hem_pipeline_post_crossing_cfl_sensitivity import (
    HEMGate8PipelineConfig,
    _git_provenance,
)
from .hem_rusanov_diagnostic_decomposition import (
    RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE,
)

D5_SCHEMA_VERSION = "stage7_gate9_d5_three_cfl_integration_v1"
D5_SCOPE = "verification_only_same_schema_three_cfl_integration"
D5_CFL_SEQUENCE: tuple[float, ...] = (0.10, 0.05, 0.025)
D5_THRESHOLD = 1.0e-6
D4_CFL_0P10_MERGE_SHA = "57ddc562198ad821a70f6ad3e00074cb0dcc732f"
D4_REFINED_MERGE_SHA = "543a6b972d31f0ea0cf7aaab27faa957ba7dcc57"
_STAGE_MAP = {"FINAL_ACCEPTED_IF_AVAILABLE": "FINAL_ACCEPTED"}


class HEMGate9ThreeCflIntegrationError(RuntimeError):
    """Raised when the fixed D5 integration contract cannot be preserved."""


@dataclass(frozen=True)
class Gate9D5ColumnEvidence:
    cfl: float
    formal_outcome: str
    formal_failure_reason: str
    candidate_step: int
    candidate_time_s: float
    candidate_cells: tuple[int, ...]
    candidate_distances_from_outlet_m: tuple[float, ...]
    maximum_candidate_quality: float
    window_steps: tuple[int, ...]
    exact_cell_stage_records: tuple[Gate9D4ExactCellStageRecord, ...]
    d1_cell_stage_records: tuple[Gate9CellStageRecord, ...]
    interface_flux_records: tuple[Gate9InterfaceFluxRecord, ...]
    acoustic_records: tuple[Gate9D4AlignedAcousticRecord, ...]
    cfl_decision_records: tuple[Gate9D4CflDecisionRecord, ...]
    timeline_records: tuple[Gate9D4TimelineRecord, ...]
    solver_identity: Mapping[str, object]
    pipeline_result: PipelineCaseResult


@dataclass(frozen=True)
class Gate9D5CellStageRecord:
    case_id: str
    cfl: float
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    time_relative_to_candidate_s: float
    dt_s: float
    measured_cfl: float
    stage: str
    cell_index: int
    rho: float
    rho_u: float
    rho_E: float
    rho_q: float
    velocity: float
    specific_internal_energy: float
    specific_volume: float
    pressure_pa: float
    temperature_K: float
    phase_class: str
    scope_status: str
    q_internal_energy_coordinate: float | None
    q_specific_volume_coordinate: float | None
    q_equilibrium: float | None
    void_fraction: float | None
    delta_e_from_saturated_liquid_J_kg: float | None
    delta_v_from_saturated_liquid_m3_kg: float | None
    raw_region: str
    post_region: str
    transition_event: str
    sound_speed_m_s: float | None
    sound_speed_squared_m2_s2: float | None
    sound_speed_branch: str
    first_projection_applied: bool
    first_projection_delta_rho_q: float
    second_projection_applied: bool
    second_projection_exact_noop: bool
    final_equals_second_projection: bool
    delta_rho_from_pre: float
    delta_rho_u_from_pre: float
    delta_rho_E_from_pre: float
    delta_rho_q_from_pre: float
    state_sha256: str
    thermodynamic_capture_status: str
    source_capture_status: str


@dataclass(frozen=True)
class Gate9D5InterfaceRecord:
    case_id: str
    cfl: float
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    time_relative_to_candidate_s: float
    dt_s: float
    interface_id: str
    left_cell: int | None
    right_cell: int | None
    left_conserved_state: tuple[float, ...]
    right_conserved_state: tuple[float, ...]
    left_physical_flux: tuple[float, ...]
    right_physical_flux: tuple[float, ...]
    a_max: float
    central_component: tuple[float, ...]
    dissipative_component: tuple[float, ...]
    reconstructed_rusanov_flux: tuple[float, ...]
    production_rusanov_flux: tuple[float, ...]
    normalized_reconstruction_residual: float
    left_cell_increment_over_dt_dx: tuple[float, ...]
    right_cell_increment_over_dt_dx: tuple[float, ...] | None
    capture_status: str


@dataclass(frozen=True)
class Gate9D5TimelineRecord:
    cfl: float
    column_sequence_index: int
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    time_relative_to_candidate_s: float
    stage: str
    entity_type: str
    entity_id: str
    event_kind: str
    detail_json: str


@dataclass(frozen=True)
class Gate9D5ProjectionRecord:
    case_id: str
    cfl: float
    absolute_step: int
    candidate_relative_step: int
    absolute_time_s: float
    cell_index: int
    raw_rho_q: float
    post_first_rho_q: float
    post_second_rho_q: float
    final_rho_q: float
    first_projection_delta_rho_q: float
    second_projection_delta_rho_q: float
    final_after_second_delta_rho_q: float
    first_projection_applied: bool
    second_projection_applied: bool
    second_projection_exact_noop: bool
    final_equals_second_projection: bool


@dataclass(frozen=True)
class Gate9D5BudgetRecord:
    case_id: str
    cfl: float
    absolute_step: int
    candidate_relative_step: int
    time_before_s: float
    time_after_s: float
    dt_s: float
    boundary_pressure_pa: float | None
    left_mass_flux_rate_kg_s: float
    right_mass_flux_rate_kg_s: float
    left_energy_flux_rate_W: float
    right_energy_flux_rate_W: float
    boundary_vapor_step_kg: float
    projection_vapor_step_kg: float
    raw_boundary_vapor_residual_kg: float
    projection_source_consistency_residual_kg: float
    combined_vapor_balance_residual_kg: float
    final_cumulative_mass_residual_kg: float | None
    final_cumulative_momentum_residual_kg_m_s: float | None
    final_cumulative_energy_residual_J: float | None
    final_cumulative_phase_vapor_residual_kg: float | None
    state_sha256: str


@dataclass(frozen=True)
class Gate9D5CandidateMetric:
    case_id: str
    cfl: float
    formal_outcome: str
    formal_failure_reason: str
    candidate_step: int
    candidate_time_s: float
    candidate_cell: int
    distance_from_outlet_m: float
    maximum_candidate_q_eq: float
    threshold_distance_q: float
    candidate_dt_s: float
    measured_cfl: float
    boundary_pressure_pa: float | None
    q_internal_energy_coordinate: float | None
    q_specific_volume_coordinate: float | None
    delta_e_from_saturated_liquid_J_kg: float | None
    delta_v_from_saturated_liquid_m3_kg: float | None
    delta_rho_pre_to_raw: float
    delta_rho_u_pre_to_raw: float
    delta_rho_E_pre_to_raw: float
    delta_rho_q_pre_to_raw: float
    first_projection_delta_rho_q: float
    second_projection_exact_noop: bool
    final_sound_speed_m_s: float | None
    final_sound_speed_branch: str
    cell29_central_mass_increment: float
    cell29_central_momentum_increment: float
    cell29_central_energy_increment: float
    cell29_central_vapor_increment: float
    cell29_dissipative_mass_increment: float
    cell29_dissipative_momentum_increment: float
    cell29_dissipative_energy_increment: float
    cell29_dissipative_vapor_increment: float
    cell31_central_mass_increment: float
    cell31_central_momentum_increment: float
    cell31_central_energy_increment: float
    cell31_central_vapor_increment: float
    cell31_dissipative_mass_increment: float
    cell31_dissipative_momentum_increment: float
    cell31_dissipative_energy_increment: float
    cell31_dissipative_vapor_increment: float
    right_boundary_central_flux: tuple[float, ...]
    right_boundary_dissipative_flux: tuple[float, ...]
    right_boundary_production_flux: tuple[float, ...]
    final_state_sha256: str
    run_signature_sha256: str


@dataclass(frozen=True)
class Gate9D5CandidateComparisonRecord:
    cfl: float
    formal_outcome: str
    candidate_time_s: float
    candidate_time_difference_from_0p10_s: float
    candidate_time_ratio_to_0p10: float
    maximum_candidate_q_eq: float
    candidate_q_difference_from_0p10: float
    candidate_q_ratio_to_0p10: float
    candidate_dt_s: float
    candidate_dt_difference_from_0p10_s: float
    candidate_dt_ratio_to_0p10: float
    delta_e_from_saturated_liquid_J_kg: float | None
    delta_e_difference_from_0p10_J_kg: float | None
    delta_v_from_saturated_liquid_m3_kg: float | None
    delta_v_difference_from_0p10_m3_kg: float | None
    candidate_time_sequence_status: str
    candidate_depth_sequence_status: str
    candidate_dt_sequence_status: str


@dataclass(frozen=True)
class Gate9D5Result:
    columns: tuple[Gate9D5ColumnEvidence, ...]
    cell_stage_records: tuple[Gate9D5CellStageRecord, ...]
    interface_records: tuple[Gate9D5InterfaceRecord, ...]
    acoustic_records: tuple[Gate9D4AlignedAcousticRecord, ...]
    cfl_decision_records: tuple[Gate9D4CflDecisionRecord, ...]
    timeline_records: tuple[Gate9D5TimelineRecord, ...]
    projection_records: tuple[Gate9D5ProjectionRecord, ...]
    budget_records: tuple[Gate9D5BudgetRecord, ...]
    candidate_metrics: tuple[Gate9D5CandidateMetric, ...]
    candidate_comparison: tuple[Gate9D5CandidateComparisonRecord, ...]
    provenance: Mapping[str, object]

    def summary(self) -> dict[str, object]:
        cfl_order = tuple(column.cfl for column in self.columns)
        candidate_times = [row.candidate_time_s for row in self.candidate_metrics]
        candidate_q = [row.maximum_candidate_q_eq for row in self.candidate_metrics]
        candidate_dt = [row.candidate_dt_s for row in self.candidate_metrics]
        complete = bool(
            cfl_order == D5_CFL_SEQUENCE
            and len(self.cell_stage_records) == 3 * 9 * 5 * 4
            and len(self.interface_records) == 3 * 9 * 5
            and len(self.cfl_decision_records) == 3 * 9
            and len(self.projection_records) == 3 * 9 * 4
            and len(self.budget_records) == 3 * 9
            and len(self.candidate_metrics) == 3
        )
        return {
            "schema_version": D5_SCHEMA_VERSION,
            "scope": D5_SCOPE,
            "case_id": FIXED_PIPELINE_DEPRESSURIZATION_CASES[0].case_id,
            "locked_cfl_sequence": list(D5_CFL_SEQUENCE),
            "column_count": len(self.columns),
            "columns": [
                {
                    "cfl": column.cfl,
                    "formal_outcome": column.formal_outcome,
                    "formal_failure_reason": column.formal_failure_reason,
                    "candidate_step": column.candidate_step,
                    "candidate_time_s": column.candidate_time_s,
                    "candidate_cells": list(column.candidate_cells),
                    "maximum_candidate_quality": column.maximum_candidate_quality,
                    "window_steps": list(column.window_steps),
                    "exact_cell_stage_record_count": len(
                        column.exact_cell_stage_records
                    ),
                    "d1_cell_stage_record_count": len(
                        column.d1_cell_stage_records
                    ),
                    "interface_flux_record_count": len(
                        column.interface_flux_records
                    ),
                    "aligned_acoustic_record_count": len(
                        column.acoustic_records
                    ),
                    "cfl_decision_record_count": len(
                        column.cfl_decision_records
                    ),
                    "timeline_record_count": len(column.timeline_records),
                    "solver_identity": dict(column.solver_identity),
                }
                for column in self.columns
            ],
            "focused_cells": list(GATE9_FOCUS_CELLS),
            "captured_exact_stages": list(D4_CAPTURED_STAGES),
            "focused_cell_stage_record_count": len(self.cell_stage_records),
            "focused_interface_flux_record_count": len(self.interface_records),
            "acoustic_attempt_record_count": len(self.acoustic_records),
            "cfl_decision_record_count": len(self.cfl_decision_records),
            "timeline_record_count": len(self.timeline_records),
            "projection_record_count": len(self.projection_records),
            "budget_record_count": len(self.budget_records),
            "candidate_metric_count": len(self.candidate_metrics),
            "candidate_comparison_count": len(self.candidate_comparison),
            "candidate_time_sequence_status": _sequence_status(candidate_times),
            "candidate_depth_sequence_status": _sequence_status(candidate_q),
            "candidate_dt_sequence_status": _sequence_status(candidate_dt),
            "all_gate8_formal_identities_reproduced": all(
                dict(column.solver_identity) == solver_identity(column.pipeline_result)
                for column in self.columns
            ),
            "all_rusanov_reconstruction_guards_passed": all(
                record.normalized_reconstruction_residual
                <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE
                for record in self.interface_records
            ),
            "all_cfl_decisions_match_production_dt": all(
                record.formula_identity_passed
                for record in self.cfl_decision_records
            ),
            "all_timeline_records_have_source_time": all(
                record.absolute_time_s > 0.0 for record in self.timeline_records
            ),
            "all_second_projections_exact_noop": all(
                record.second_projection_exact_noop
                for record in self.projection_records
            ),
            "budgets_traceable": bool(
                all(
                    np.isfinite(record.combined_vapor_balance_residual_kg)
                    for record in self.budget_records
                )
                and all(
                    record.final_cumulative_mass_residual_kg is not None
                    and record.final_cumulative_momentum_residual_kg_m_s is not None
                    and record.final_cumulative_energy_residual_J is not None
                    and record.final_cumulative_phase_vapor_residual_kg is not None
                    for record in self.budget_records
                    if record.candidate_relative_step == 0
                )
            ),
            "D5_three_cfl_integration_complete": complete,
            "D6_temporal_correlation_classification_complete": False,
            "production_solver_changed": False,
            "rusanov_flux_changed": False,
            "cfl_calculation_changed": False,
            "sound_speed_formula_changed": False,
            "production_property_evaluation_order_changed": False,
            "diagnostic_postprocessing_phase_evaluations": True,
            "diagnostic_sound_speed_re_evaluated": False,
            "phase_classifier_changed": False,
            "quality_projection_changed": False,
            "crossing_threshold_changed": False,
            "boundary_changed": False,
            "forced_post_guard_continuation": False,
            "Gate_9_execution_complete": False,
            "crossing_depth_CFL_sensitivity_characterized": False,
            "crossing_depth_root_cause_approved": False,
            "threshold_change_authorized": False,
            "flux_change_authorized": False,
            "sound_speed_change_authorized": False,
            "projection_change_authorized": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
            "d4_cfl_0p10_merge_sha": D4_CFL_0P10_MERGE_SHA,
            "d4_refined_merge_sha": D4_REFINED_MERGE_SHA,
            "provenance": dict(self.provenance),
        }


def _sequence_status(values: Sequence[float]) -> str:
    if len(values) < 2 or any(not np.isfinite(value) for value in values):
        return "INCOMPLETE"
    differences = np.diff(np.asarray(values, dtype=float))
    if np.all(differences == 0.0):
        return "CONSTANT"
    if np.all(differences >= 0.0):
        return "MONOTONE_NONDECREASING"
    if np.all(differences <= 0.0):
        return "MONOTONE_NONINCREASING"
    return "NON_MONOTONE"


def _same_state(
    left: Gate9D4ExactCellStageRecord,
    right: Gate9D4ExactCellStageRecord,
) -> bool:
    return all(
        float(a).hex() == float(b).hex()
        for a, b in zip(
            (left.rho, left.rho_u, left.rho_E, left.rho_q),
            (right.rho, right.rho_u, right.rho_E, right.rho_q),
        )
    )


def _props_si():
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError("CoolProp is required for Gate 9 D5 integration") from exc
    return PropsSI


def _saturation_reference(
    pressure_pa: float,
    cache: dict[str, tuple[float, float, float, float] | None],
) -> tuple[float, float, float, float] | None:
    key = float(pressure_pa).hex()
    if key in cache:
        return cache[key]
    props = _props_si()
    try:
        e_l = float(props("Umass", "P", pressure_pa, "Q", 0.0, "CO2"))
        e_v = float(props("Umass", "P", pressure_pa, "Q", 1.0, "CO2"))
        rho_l = float(props("Dmass", "P", pressure_pa, "Q", 0.0, "CO2"))
        rho_v = float(props("Dmass", "P", pressure_pa, "Q", 1.0, "CO2"))
        values = (e_l, e_v, 1.0 / rho_l, 1.0 / rho_v)
        if (
            not all(np.isfinite(value) for value in values)
            or e_v <= e_l
            or values[3] <= values[2]
        ):
            raise ValueError("invalid saturation reference")
        cache[key] = values
    except Exception:
        cache[key] = None
    return cache[key]


def _normalize_d1_stage(stage: str) -> str:
    return _STAGE_MAP.get(stage, stage)


def _build_projection_records(
    column: Gate9D5ColumnEvidence,
) -> tuple[Gate9D5ProjectionRecord, ...]:
    by_key = {
        (record.absolute_step, record.cell_index, record.stage): record
        for record in column.exact_cell_stage_records
    }
    output: list[Gate9D5ProjectionRecord] = []
    for step in column.window_steps:
        for cell in GATE9_FOCUS_CELLS:
            raw = by_key[(step, cell, "RAW_POST_FVM")]
            first = by_key[(step, cell, "POST_FIRST_PROJECTION")]
            second = by_key[(step, cell, "POST_SECOND_PROJECTION")]
            final = by_key[(step, cell, "FINAL_ACCEPTED")]
            output.append(
                Gate9D5ProjectionRecord(
                    case_id=raw.case_id,
                    cfl=column.cfl,
                    absolute_step=step,
                    candidate_relative_step=step - column.candidate_step,
                    absolute_time_s=raw.absolute_time_s,
                    cell_index=cell,
                    raw_rho_q=raw.rho_q,
                    post_first_rho_q=first.rho_q,
                    post_second_rho_q=second.rho_q,
                    final_rho_q=final.rho_q,
                    first_projection_delta_rho_q=first.rho_q - raw.rho_q,
                    second_projection_delta_rho_q=second.rho_q - first.rho_q,
                    final_after_second_delta_rho_q=final.rho_q - second.rho_q,
                    first_projection_applied=not _same_state(raw, first),
                    second_projection_applied=not _same_state(first, second),
                    second_projection_exact_noop=_same_state(first, second),
                    final_equals_second_projection=_same_state(second, final),
                )
            )
    return tuple(output)


def _build_cell_stage_records(
    columns: Sequence[Gate9D5ColumnEvidence],
    projections: Sequence[Gate9D5ProjectionRecord],
) -> tuple[Gate9D5CellStageRecord, ...]:
    exact = tuple(
        record for column in columns for record in column.exact_cell_stage_records
    )
    rho = np.asarray([record.rho for record in exact], dtype=float)
    internal = np.asarray(
        [record.specific_internal_energy for record in exact], dtype=float
    )
    phase = evaluate_coolprop_hem_phase_state(rho, internal)

    d1_index = {
        (
            float(record.cfl),
            record.absolute_step,
            _normalize_d1_stage(record.stage),
            record.cell_index,
        ): record
        for column in columns
        for record in column.d1_cell_stage_records
    }
    cfl_index = {
        (float(record.cfl), record.absolute_step): record
        for column in columns
        for record in column.cfl_decision_records
    }
    acoustic_index: dict[
        tuple[float, int, str, int], Gate9D4AlignedAcousticRecord
    ] = {}
    for column in columns:
        for record in column.acoustic_records:
            if (
                record.accepted_or_refused == "ACCEPTED"
                and record.computed_sound_speed_squared is not None
                and record.computed_sound_speed_squared > 0.0
            ):
                key = (
                    float(record.cfl),
                    record.absolute_step,
                    record.stage,
                    record.cell_index,
                )
                previous = acoustic_index.get(key)
                if previous is None or record.evaluation_id > previous.evaluation_id:
                    acoustic_index[key] = record
    projection_index = {
        (record.cfl, record.absolute_step, record.cell_index): record
        for record in projections
    }
    exact_index = {
        (float(record.cfl), record.absolute_step, record.stage, record.cell_index): record
        for record in exact
    }
    candidate_time = {column.cfl: column.candidate_time_s for column in columns}
    sat_cache: dict[str, tuple[float, float, float, float] | None] = {}

    output: list[Gate9D5CellStageRecord] = []
    for position, record in enumerate(exact):
        p = float(np.asarray(phase.p)[position])
        T = float(np.asarray(phase.T)[position])
        quality_defined = bool(np.asarray(phase.quality_defined)[position])
        alpha_defined = bool(np.asarray(phase.alpha_defined)[position])
        q_eq = (
            float(np.asarray(phase.quality)[position])
            if quality_defined
            else None
        )
        alpha = (
            float(np.asarray(phase.alpha)[position]) if alpha_defined else None
        )
        sat = _saturation_reference(p, sat_cache)
        if sat is None:
            q_u = q_v = delta_e = delta_v = None
            thermo_status = "D5_PHASE_STATE_OK_SATURATION_REFERENCE_UNAVAILABLE"
        else:
            e_l, e_v, v_l, v_v = sat
            delta_e = record.specific_internal_energy - e_l
            delta_v = record.specific_volume - v_l
            q_u = delta_e / (e_v - e_l)
            q_v = delta_v / (v_v - v_l)
            thermo_status = "D5_PHASE_STATE_AND_SATURATION_REFERENCE_AVAILABLE"

        key = (
            float(record.cfl),
            record.absolute_step,
            record.stage,
            record.cell_index,
        )
        d1 = d1_index.get(key)
        decision = cfl_index[(float(record.cfl), record.absolute_step)]
        acoustic = acoustic_index.get(key)
        projection = projection_index[
            (float(record.cfl), record.absolute_step, record.cell_index)
        ]
        pre = exact_index[
            (
                float(record.cfl),
                record.absolute_step,
                "PRE_STEP_ACCEPTED",
                record.cell_index,
            )
        ]
        sound2 = (
            None
            if acoustic is None
            else float(acoustic.computed_sound_speed_squared)
        )
        sound = None if sound2 is None else math.sqrt(sound2)
        output.append(
            Gate9D5CellStageRecord(
                case_id=record.case_id,
                cfl=float(record.cfl),
                absolute_step=record.absolute_step,
                candidate_relative_step=record.candidate_relative_step,
                absolute_time_s=record.absolute_time_s,
                time_relative_to_candidate_s=(
                    record.absolute_time_s - candidate_time[float(record.cfl)]
                ),
                dt_s=record.dt_s,
                measured_cfl=decision.measured_cfl,
                stage=record.stage,
                cell_index=record.cell_index,
                rho=record.rho,
                rho_u=record.rho_u,
                rho_E=record.rho_E,
                rho_q=record.rho_q,
                velocity=record.velocity,
                specific_internal_energy=record.specific_internal_energy,
                specific_volume=record.specific_volume,
                pressure_pa=p,
                temperature_K=T,
                phase_class=str(np.asarray(phase.phase_class)[position]),
                scope_status=str(np.asarray(phase.scope_status)[position]),
                q_internal_energy_coordinate=q_u,
                q_specific_volume_coordinate=q_v,
                q_equilibrium=q_eq,
                void_fraction=alpha,
                delta_e_from_saturated_liquid_J_kg=delta_e,
                delta_v_from_saturated_liquid_m3_kg=delta_v,
                raw_region=("" if d1 is None else d1.raw_region),
                post_region=("" if d1 is None else d1.post_region),
                transition_event=("" if d1 is None else d1.transition_event),
                sound_speed_m_s=sound,
                sound_speed_squared_m2_s2=sound2,
                sound_speed_branch=(
                    "NOT_OBSERVED_AT_THIS_STAGE"
                    if acoustic is None
                    else acoustic.center_phase_class
                ),
                first_projection_applied=projection.first_projection_applied,
                first_projection_delta_rho_q=(
                    projection.first_projection_delta_rho_q
                ),
                second_projection_applied=projection.second_projection_applied,
                second_projection_exact_noop=(
                    projection.second_projection_exact_noop
                ),
                final_equals_second_projection=(
                    projection.final_equals_second_projection
                ),
                delta_rho_from_pre=record.rho - pre.rho,
                delta_rho_u_from_pre=record.rho_u - pre.rho_u,
                delta_rho_E_from_pre=record.rho_E - pre.rho_E,
                delta_rho_q_from_pre=record.rho_q - pre.rho_q,
                state_sha256=record.state_sha256,
                thermodynamic_capture_status=thermo_status,
                source_capture_status=record.capture_status,
            )
        )
    return tuple(output)


def _build_interface_records(
    columns: Sequence[Gate9D5ColumnEvidence],
) -> tuple[Gate9D5InterfaceRecord, ...]:
    candidate_time = {column.cfl: column.candidate_time_s for column in columns}
    candidate_step = {column.cfl: column.candidate_step for column in columns}
    output: list[Gate9D5InterfaceRecord] = []
    for column in columns:
        for record in column.interface_flux_records:
            if (
                record.left_conserved_state is None
                or record.right_conserved_state is None
                or record.left_physical_flux is None
                or record.right_physical_flux is None
                or record.a_max is None
                or record.central_component is None
                or record.dissipative_component is None
                or record.reconstructed_rusanov_flux is None
                or record.production_rusanov_flux is None
                or record.normalized_reconstruction_residual is None
                or record.left_cell_increment_over_dt_dx is None
            ):
                raise HEMGate9ThreeCflIntegrationError(
                    "D5 received an incomplete D2 interface record"
                )
            output.append(
                Gate9D5InterfaceRecord(
                    case_id=record.case_id,
                    cfl=float(record.cfl),
                    absolute_step=record.absolute_step,
                    candidate_relative_step=(
                        record.absolute_step - candidate_step[float(record.cfl)]
                    ),
                    absolute_time_s=record.absolute_time_s,
                    time_relative_to_candidate_s=(
                        record.absolute_time_s - candidate_time[float(record.cfl)]
                    ),
                    dt_s=record.dt_s,
                    interface_id=record.interface_id,
                    left_cell=record.left_cell,
                    right_cell=record.right_cell,
                    left_conserved_state=tuple(record.left_conserved_state),
                    right_conserved_state=tuple(record.right_conserved_state),
                    left_physical_flux=tuple(record.left_physical_flux),
                    right_physical_flux=tuple(record.right_physical_flux),
                    a_max=float(record.a_max),
                    central_component=tuple(record.central_component),
                    dissipative_component=tuple(record.dissipative_component),
                    reconstructed_rusanov_flux=tuple(
                        record.reconstructed_rusanov_flux
                    ),
                    production_rusanov_flux=tuple(record.production_rusanov_flux),
                    normalized_reconstruction_residual=float(
                        record.normalized_reconstruction_residual
                    ),
                    left_cell_increment_over_dt_dx=tuple(
                        record.left_cell_increment_over_dt_dx
                    ),
                    right_cell_increment_over_dt_dx=(
                        None
                        if record.right_cell_increment_over_dt_dx is None
                        else tuple(record.right_cell_increment_over_dt_dx)
                    ),
                    capture_status=record.capture_status,
                )
            )
    return tuple(output)


def _build_timeline_records(
    columns: Sequence[Gate9D5ColumnEvidence],
) -> tuple[Gate9D5TimelineRecord, ...]:
    output: list[Gate9D5TimelineRecord] = []
    for column in columns:
        for record in column.timeline_records:
            output.append(
                Gate9D5TimelineRecord(
                    cfl=column.cfl,
                    column_sequence_index=record.sequence_index,
                    absolute_step=record.absolute_step,
                    candidate_relative_step=record.candidate_relative_step,
                    absolute_time_s=record.absolute_time_s,
                    time_relative_to_candidate_s=(
                        record.absolute_time_s - column.candidate_time_s
                    ),
                    stage=record.stage,
                    entity_type=record.entity_type,
                    entity_id=record.entity_id,
                    event_kind=record.event_kind,
                    detail_json=record.detail_json,
                )
            )
    return tuple(output)


def _build_budget_records(
    columns: Sequence[Gate9D5ColumnEvidence],
) -> tuple[Gate9D5BudgetRecord, ...]:
    output: list[Gate9D5BudgetRecord] = []
    for column in columns:
        steps = {
            int(step.step_index): step for step in column.pipeline_result.steps
        }
        boundary = column.pipeline_result.boundary_budget_diagnostics
        phase = column.pipeline_result.phase_budget_diagnostics
        for step_index in column.window_steps:
            step: PipelineStepRecord = steps[step_index]
            candidate = step_index == column.candidate_step
            output.append(
                Gate9D5BudgetRecord(
                    case_id=step.case_id,
                    cfl=column.cfl,
                    absolute_step=step_index,
                    candidate_relative_step=step_index - column.candidate_step,
                    time_before_s=step.time_before_s,
                    time_after_s=step.time_after_s,
                    dt_s=step.dt_s,
                    boundary_pressure_pa=step.boundary_pressure_pa,
                    left_mass_flux_rate_kg_s=step.left_mass_flux_rate_kg_s,
                    right_mass_flux_rate_kg_s=step.right_mass_flux_rate_kg_s,
                    left_energy_flux_rate_W=step.left_energy_flux_rate_W,
                    right_energy_flux_rate_W=step.right_energy_flux_rate_W,
                    boundary_vapor_step_kg=step.boundary_vapor_step_kg,
                    projection_vapor_step_kg=step.projection_vapor_step_kg,
                    raw_boundary_vapor_residual_kg=(
                        step.raw_boundary_vapor_residual_kg
                    ),
                    projection_source_consistency_residual_kg=(
                        step.projection_source_consistency_residual_kg
                    ),
                    combined_vapor_balance_residual_kg=(
                        step.combined_vapor_balance_residual_kg
                    ),
                    final_cumulative_mass_residual_kg=(
                        float(boundary["budget_mass_residual"])
                        if candidate and "budget_mass_residual" in boundary
                        else None
                    ),
                    final_cumulative_momentum_residual_kg_m_s=(
                        float(boundary["budget_momentum_residual"])
                        if candidate and "budget_momentum_residual" in boundary
                        else None
                    ),
                    final_cumulative_energy_residual_J=(
                        float(boundary["budget_energy_residual"])
                        if candidate and "budget_energy_residual" in boundary
                        else None
                    ),
                    final_cumulative_phase_vapor_residual_kg=(
                        float(phase["phase_vapor_mass_balance_residual_kg"])
                        if (
                            candidate
                            and "phase_vapor_mass_balance_residual_kg" in phase
                        )
                        else None
                    ),
                    state_sha256=step.state_sha256,
                )
            )
    return tuple(output)


def _net_interface_increment(
    interfaces: Sequence[Gate9D5InterfaceRecord],
    *,
    cfl: float,
    step: int,
    cell: int,
    dx_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    central = np.zeros(4, dtype=float)
    dissipative = np.zeros(4, dtype=float)
    rows = [
        row
        for row in interfaces
        if row.cfl == cfl and row.absolute_step == step
    ]
    for row in rows:
        factor = row.dt_s / dx_m
        if row.left_cell == cell:
            central -= factor * np.asarray(row.central_component, dtype=float)
            dissipative -= factor * np.asarray(
                row.dissipative_component, dtype=float
            )
        if row.right_cell == cell:
            central += factor * np.asarray(row.central_component, dtype=float)
            dissipative += factor * np.asarray(
                row.dissipative_component, dtype=float
            )
    return central, dissipative


def _build_candidate_metrics(
    columns: Sequence[Gate9D5ColumnEvidence],
    cells: Sequence[Gate9D5CellStageRecord],
    projections: Sequence[Gate9D5ProjectionRecord],
    budgets: Sequence[Gate9D5BudgetRecord],
    interfaces: Sequence[Gate9D5InterfaceRecord],
) -> tuple[Gate9D5CandidateMetric, ...]:
    cell_index = {
        (row.cfl, row.absolute_step, row.stage, row.cell_index): row
        for row in cells
    }
    projection_index = {
        (row.cfl, row.absolute_step, row.cell_index): row
        for row in projections
    }
    budget_index = {
        (row.cfl, row.absolute_step): row for row in budgets
    }
    output: list[Gate9D5CandidateMetric] = []
    for column in columns:
        step = column.candidate_step
        raw = cell_index[(column.cfl, step, "RAW_POST_FVM", 29)]
        final = cell_index[(column.cfl, step, "FINAL_ACCEPTED", 29)]
        projection = projection_index[(column.cfl, step, 29)]
        budget = budget_index[(column.cfl, step)]
        decision = next(
            record
            for record in column.cfl_decision_records
            if record.absolute_step == step
        )
        central29, dissipative29 = _net_interface_increment(
            interfaces,
            cfl=column.cfl,
            step=step,
            cell=29,
            dx_m=decision.dx_m,
        )
        central31, dissipative31 = _net_interface_increment(
            interfaces,
            cfl=column.cfl,
            step=step,
            cell=31,
            dx_m=decision.dx_m,
        )
        boundary = next(
            row
            for row in interfaces
            if row.cfl == column.cfl
            and row.absolute_step == step
            and row.interface_id == "RIGHT_BOUNDARY"
        )
        identity = dict(column.solver_identity)
        output.append(
            Gate9D5CandidateMetric(
                case_id=FIXED_PIPELINE_DEPRESSURIZATION_CASES[0].case_id,
                cfl=column.cfl,
                formal_outcome=column.formal_outcome,
                formal_failure_reason=column.formal_failure_reason,
                candidate_step=step,
                candidate_time_s=column.candidate_time_s,
                candidate_cell=column.candidate_cells[0],
                distance_from_outlet_m=column.candidate_distances_from_outlet_m[0],
                maximum_candidate_q_eq=column.maximum_candidate_quality,
                threshold_distance_q=(
                    column.maximum_candidate_quality - D5_THRESHOLD
                ),
                candidate_dt_s=decision.dt_s,
                measured_cfl=decision.measured_cfl,
                boundary_pressure_pa=budget.boundary_pressure_pa,
                q_internal_energy_coordinate=raw.q_internal_energy_coordinate,
                q_specific_volume_coordinate=raw.q_specific_volume_coordinate,
                delta_e_from_saturated_liquid_J_kg=(
                    raw.delta_e_from_saturated_liquid_J_kg
                ),
                delta_v_from_saturated_liquid_m3_kg=(
                    raw.delta_v_from_saturated_liquid_m3_kg
                ),
                delta_rho_pre_to_raw=raw.delta_rho_from_pre,
                delta_rho_u_pre_to_raw=raw.delta_rho_u_from_pre,
                delta_rho_E_pre_to_raw=raw.delta_rho_E_from_pre,
                delta_rho_q_pre_to_raw=raw.delta_rho_q_from_pre,
                first_projection_delta_rho_q=(
                    projection.first_projection_delta_rho_q
                ),
                second_projection_exact_noop=(
                    projection.second_projection_exact_noop
                ),
                final_sound_speed_m_s=final.sound_speed_m_s,
                final_sound_speed_branch=final.sound_speed_branch,
                cell29_central_mass_increment=float(central29[0]),
                cell29_central_momentum_increment=float(central29[1]),
                cell29_central_energy_increment=float(central29[2]),
                cell29_central_vapor_increment=float(central29[3]),
                cell29_dissipative_mass_increment=float(dissipative29[0]),
                cell29_dissipative_momentum_increment=float(dissipative29[1]),
                cell29_dissipative_energy_increment=float(dissipative29[2]),
                cell29_dissipative_vapor_increment=float(dissipative29[3]),
                cell31_central_mass_increment=float(central31[0]),
                cell31_central_momentum_increment=float(central31[1]),
                cell31_central_energy_increment=float(central31[2]),
                cell31_central_vapor_increment=float(central31[3]),
                cell31_dissipative_mass_increment=float(dissipative31[0]),
                cell31_dissipative_momentum_increment=float(dissipative31[1]),
                cell31_dissipative_energy_increment=float(dissipative31[2]),
                cell31_dissipative_vapor_increment=float(dissipative31[3]),
                right_boundary_central_flux=boundary.central_component,
                right_boundary_dissipative_flux=boundary.dissipative_component,
                right_boundary_production_flux=boundary.production_rusanov_flux,
                final_state_sha256=str(identity["final_state_sha256"]),
                run_signature_sha256=str(identity["run_signature_sha256"]),
            )
        )
    return tuple(output)


def _safe_ratio(value: float, reference: float) -> float:
    return float("nan") if reference == 0.0 else value / reference


def _safe_difference(
    value: float | None,
    reference: float | None,
) -> float | None:
    return None if value is None or reference is None else value - reference


def _build_candidate_comparison(
    metrics: Sequence[Gate9D5CandidateMetric],
) -> tuple[Gate9D5CandidateComparisonRecord, ...]:
    reference = metrics[0]
    time_status = _sequence_status([row.candidate_time_s for row in metrics])
    depth_status = _sequence_status(
        [row.maximum_candidate_q_eq for row in metrics]
    )
    dt_status = _sequence_status([row.candidate_dt_s for row in metrics])
    return tuple(
        Gate9D5CandidateComparisonRecord(
            cfl=row.cfl,
            formal_outcome=row.formal_outcome,
            candidate_time_s=row.candidate_time_s,
            candidate_time_difference_from_0p10_s=(
                row.candidate_time_s - reference.candidate_time_s
            ),
            candidate_time_ratio_to_0p10=_safe_ratio(
                row.candidate_time_s,
                reference.candidate_time_s,
            ),
            maximum_candidate_q_eq=row.maximum_candidate_q_eq,
            candidate_q_difference_from_0p10=(
                row.maximum_candidate_q_eq - reference.maximum_candidate_q_eq
            ),
            candidate_q_ratio_to_0p10=_safe_ratio(
                row.maximum_candidate_q_eq,
                reference.maximum_candidate_q_eq,
            ),
            candidate_dt_s=row.candidate_dt_s,
            candidate_dt_difference_from_0p10_s=(
                row.candidate_dt_s - reference.candidate_dt_s
            ),
            candidate_dt_ratio_to_0p10=_safe_ratio(
                row.candidate_dt_s,
                reference.candidate_dt_s,
            ),
            delta_e_from_saturated_liquid_J_kg=(
                row.delta_e_from_saturated_liquid_J_kg
            ),
            delta_e_difference_from_0p10_J_kg=_safe_difference(
                row.delta_e_from_saturated_liquid_J_kg,
                reference.delta_e_from_saturated_liquid_J_kg,
            ),
            delta_v_from_saturated_liquid_m3_kg=(
                row.delta_v_from_saturated_liquid_m3_kg
            ),
            delta_v_difference_from_0p10_m3_kg=_safe_difference(
                row.delta_v_from_saturated_liquid_m3_kg,
                reference.delta_v_from_saturated_liquid_m3_kg,
            ),
            candidate_time_sequence_status=time_status,
            candidate_depth_sequence_status=depth_status,
            candidate_dt_sequence_status=dt_status,
        )
        for row in metrics
    )


def _validate_columns(columns: Sequence[Gate9D5ColumnEvidence]) -> None:
    if tuple(column.cfl for column in columns) != D5_CFL_SEQUENCE:
        raise HEMGate9ThreeCflIntegrationError(
            "D5 columns do not match the locked CFL sequence"
        )
    expected = {
        0.10: (
            "ACCEPTED_FIRST_CROSSING",
            125,
            7.999325695335248e-4,
            3.773646403587342e-6,
        ),
        0.05: (
            "GUARD_FAILURE",
            249,
            7.967173062790038e-4,
            1.1006096906989802e-7,
        ),
        0.025: (
            "ACCEPTED_FIRST_CROSSING",
            499,
            7.981201399992095e-4,
            1.3949366092287805e-6,
        ),
    }
    for column in columns:
        outcome, step, time_s, quality = expected[column.cfl]
        if (
            column.formal_outcome != outcome
            or column.candidate_step != step
            or column.candidate_time_s != time_s
            or column.candidate_cells != (29,)
            or column.maximum_candidate_quality != quality
            or column.window_steps != tuple(range(step - 8, step + 1))
            or len(column.exact_cell_stage_records) != 180
            or len(column.d1_cell_stage_records) != 108
            or len(column.interface_flux_records) != 45
            or len(column.cfl_decision_records) != 9
            or not column.acoustic_records
        ):
            raise HEMGate9ThreeCflIntegrationError(
                f"D5 column contract failed for CFL={column.cfl}"
            )
        if dict(column.solver_identity) != solver_identity(column.pipeline_result):
            raise HEMGate9ThreeCflIntegrationError(
                f"D5 independent budget replay identity failed for CFL={column.cfl}"
            )


def _from_d4_0p10(
    d4: Gate9D4Result,
    pipeline: PipelineCaseResult,
) -> Gate9D5ColumnEvidence:
    return Gate9D5ColumnEvidence(
        cfl=0.10,
        formal_outcome=pipeline.outcome,
        formal_failure_reason=pipeline.failure_reason,
        candidate_step=int(pipeline.crossing_step),
        candidate_time_s=float(pipeline.crossing_time_s),
        candidate_cells=tuple(int(value) for value in pipeline.crossing_cell_indices),
        candidate_distances_from_outlet_m=tuple(
            float(value) for value in pipeline.crossing_distances_from_outlet_m
        ),
        maximum_candidate_quality=float(pipeline.maximum_crossing_quality),
        window_steps=d4.window_steps,
        exact_cell_stage_records=d4.exact_cell_stage_records,
        d1_cell_stage_records=d4.d1_cell_stage_records,
        interface_flux_records=d4.interface_flux_records,
        acoustic_records=d4.acoustic_records,
        cfl_decision_records=d4.cfl_decision_records,
        timeline_records=d4.timeline_records,
        solver_identity=dict(d4.solver_identity_on),
        pipeline_result=pipeline,
    )


def _from_refined(
    d4: Gate9D4RefinedColumnResult,
    pipeline: PipelineCaseResult,
) -> Gate9D5ColumnEvidence:
    return Gate9D5ColumnEvidence(
        cfl=d4.contract.cfl,
        formal_outcome=str(d4.solver_identity_on["outcome"]),
        formal_failure_reason=str(d4.solver_identity_on["failure_reason"]),
        candidate_step=d4.candidate_step,
        candidate_time_s=d4.candidate_time_s,
        candidate_cells=d4.candidate_cells,
        candidate_distances_from_outlet_m=tuple(
            float(value) for value in pipeline.crossing_distances_from_outlet_m
        ),
        maximum_candidate_quality=d4.maximum_candidate_quality,
        window_steps=d4.window_steps,
        exact_cell_stage_records=d4.exact_cell_stage_records,
        d1_cell_stage_records=d4.d1_cell_stage_records,
        interface_flux_records=d4.interface_flux_records,
        acoustic_records=d4.acoustic_records,
        cfl_decision_records=d4.cfl_decision_records,
        timeline_records=d4.timeline_records,
        solver_identity=dict(d4.solver_identity_on),
        pipeline_result=pipeline,
    )


def run_gate9_d5_three_cfl_integration() -> Gate9D5Result:
    """Execute the fixed D4 columns and return one same-schema D5 bundle."""

    case = FIXED_PIPELINE_DEPRESSURIZATION_CASES[0]
    _, baseline_on, baseline_d4 = run_gate9_d4_identity_pair(
        case,
        HEMPipelineDepressurizationConfig(),
    )
    refined = run_gate9_d4_refined_columns()
    refined_pipeline = {
        column.contract.cfl: run_pipeline_depressurization_case(
            case,
            HEMGate8PipelineConfig.for_cfl(column.contract.cfl),
        )
        for column in refined.columns
    }
    columns = (
        _from_d4_0p10(baseline_d4, baseline_on),
        *(
            _from_refined(
                column,
                refined_pipeline[column.contract.cfl],
            )
            for column in refined.columns
        ),
    )
    _validate_columns(columns)

    projection_records = tuple(
        record
        for column in columns
        for record in _build_projection_records(column)
    )
    cell_records = _build_cell_stage_records(columns, projection_records)
    interface_records = _build_interface_records(columns)
    acoustic_records = tuple(
        record for column in columns for record in column.acoustic_records
    )
    cfl_records = tuple(
        record for column in columns for record in column.cfl_decision_records
    )
    timeline_records = _build_timeline_records(columns)
    budget_records = _build_budget_records(columns)
    candidate_metrics = _build_candidate_metrics(
        columns,
        cell_records,
        projection_records,
        budget_records,
        interface_records,
    )
    comparison = _build_candidate_comparison(candidate_metrics)
    result = Gate9D5Result(
        columns=columns,
        cell_stage_records=cell_records,
        interface_records=interface_records,
        acoustic_records=acoustic_records,
        cfl_decision_records=cfl_records,
        timeline_records=timeline_records,
        projection_records=projection_records,
        budget_records=budget_records,
        candidate_metrics=candidate_metrics,
        candidate_comparison=comparison,
        provenance=_git_provenance(),
    )
    summary = result.summary()
    for key in (
        "all_gate8_formal_identities_reproduced",
        "all_rusanov_reconstruction_guards_passed",
        "all_cfl_decisions_match_production_dt",
        "all_timeline_records_have_source_time",
        "all_second_projections_exact_noop",
        "budgets_traceable",
        "D5_three_cfl_integration_complete",
    ):
        if summary[key] is not True:
            raise HEMGate9ThreeCflIntegrationError(
                f"D5 aggregate contract failed: {key}"
            )
    return result


def _flatten(value: object) -> object:
    return (
        json.dumps(value, sort_keys=True)
        if isinstance(value, (tuple, list, dict))
        else value
    )


def _write_dataclass_rows(
    path: Path,
    record_type: type,
    rows: Sequence[object],
) -> None:
    names = [item.name for item in fields(record_type)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow({name: _flatten(payload[name]) for name in names})


def _write_saturation_margin_rows(
    path: Path,
    rows: Sequence[Gate9D5CellStageRecord],
) -> None:
    fields_out = (
        "case_id",
        "cfl",
        "absolute_step",
        "candidate_relative_step",
        "absolute_time_s",
        "time_relative_to_candidate_s",
        "stage",
        "cell_index",
        "pressure_pa",
        "specific_internal_energy",
        "specific_volume",
        "q_internal_energy_coordinate",
        "q_specific_volume_coordinate",
        "q_equilibrium",
        "delta_e_from_saturated_liquid_J_kg",
        "delta_v_from_saturated_liquid_m3_kg",
        "phase_class",
        "thermodynamic_capture_status",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields_out)
        writer.writeheader()
        for row in rows:
            payload = asdict(row)
            writer.writerow({name: _flatten(payload[name]) for name in fields_out})


def _write_report(path: Path, result: Gate9D5Result) -> None:
    summary = result.summary()
    lines = [
        "# Stage 7 Gate 9 D5 — Three-CFL integration",
        "",
        "`VERIFICATION ONLY; D6 CLASSIFICATION NOT YET PERFORMED`",
        "",
        "## Candidate metrics",
        "",
        "| CFL | formal outcome | step | time [s] | q_eq max | dt [s] | boundary p [Pa] |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in result.candidate_metrics:
        pressure = (
            "unavailable"
            if row.boundary_pressure_pa is None
            else f"{row.boundary_pressure_pa:.17g}"
        )
        lines.append(
            f"| {row.cfl:.3g} | `{row.formal_outcome}` | {row.candidate_step} | "
            f"{row.candidate_time_s:.17g} | {row.maximum_candidate_q_eq:.17g} | "
            f"{row.candidate_dt_s:.17g} | {pressure} |"
        )
    lines.extend(
        [
            "",
            "## Integration status",
            "",
            "```text",
            f"candidate time sequence:  {summary['candidate_time_sequence_status']}",
            f"candidate depth sequence: {summary['candidate_depth_sequence_status']}",
            f"candidate dt sequence:    {summary['candidate_dt_sequence_status']}",
            f"cell-stage records:       {summary['focused_cell_stage_record_count']}",
            f"interface records:        {summary['focused_interface_flux_record_count']}",
            f"acoustic records:         {summary['acoustic_attempt_record_count']}",
            f"D5 complete:              {summary['D5_three_cfl_integration_complete']}",
            "D6 classification:        false",
            "Gate 9 execution:         false",
            "```",
            "",
            "No correlation label or causal conclusion is assigned in D5.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_plots(target: Path, result: Gate9D5Result) -> dict[str, Path]:
    import matplotlib.pyplot as plt

    plot_paths = {
        "quality": target / "candidate_quality_vs_physical_time.png",
        "margins": target / "saturation_margins_vs_physical_time.png",
        "flux": target / "candidate_step_flux_decomposition.png",
        "acoustic": target / "acoustic_branch_vs_margin.png",
        "depth": target / "cross_cfl_depth_comparison.png",
    }

    raw29 = [
        row
        for row in result.cell_stage_records
        if row.cell_index == 29 and row.stage == "RAW_POST_FVM"
    ]
    plt.figure(figsize=(8, 5))
    for cfl in D5_CFL_SEQUENCE:
        rows = sorted(
            (row for row in raw29 if row.cfl == cfl),
            key=lambda row: row.absolute_time_s,
        )
        plt.plot(
            [row.time_relative_to_candidate_s for row in rows],
            [0.0 if row.q_equilibrium is None else row.q_equilibrium for row in rows],
            marker="o",
            label=f"CFL {cfl:g}",
        )
    plt.axhline(D5_THRESHOLD, linestyle="--", label="accepted threshold")
    plt.xlabel("time relative to candidate [s]")
    plt.ylabel("equilibrium quality")
    plt.title("Cell 29 raw equilibrium quality")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_paths["quality"])
    plt.close()

    plt.figure(figsize=(8, 5))
    for cfl in D5_CFL_SEQUENCE:
        rows = sorted(
            (row for row in raw29 if row.cfl == cfl),
            key=lambda row: row.absolute_time_s,
        )
        plt.plot(
            [row.time_relative_to_candidate_s for row in rows],
            [row.q_internal_energy_coordinate for row in rows],
            marker="o",
            label=f"q_u CFL {cfl:g}",
        )
        plt.plot(
            [row.time_relative_to_candidate_s for row in rows],
            [row.q_specific_volume_coordinate for row in rows],
            marker="x",
            label=f"q_v CFL {cfl:g}",
        )
    plt.axhline(0.0, linestyle="--")
    plt.xlabel("time relative to candidate [s]")
    plt.ylabel("continuous saturation coordinate")
    plt.title("Cell 29 raw saturation coordinates")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_paths["margins"])
    plt.close()

    x = np.arange(len(D5_CFL_SEQUENCE), dtype=float)
    width = 0.35
    central = [row.cell29_central_energy_increment for row in result.candidate_metrics]
    dissipative = [
        row.cell29_dissipative_energy_increment for row in result.candidate_metrics
    ]
    plt.figure(figsize=(8, 5))
    plt.bar(x - width / 2.0, central, width, label="central")
    plt.bar(x + width / 2.0, dissipative, width, label="dissipative")
    plt.xticks(x, [f"{value:g}" for value in D5_CFL_SEQUENCE])
    plt.xlabel("CFL")
    plt.ylabel("candidate-step cell 29 energy increment")
    plt.title("Rusanov component contribution at candidate step")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_paths["flux"])
    plt.close()

    final29 = [
        row
        for row in result.cell_stage_records
        if row.cell_index == 29
        and row.stage == "FINAL_ACCEPTED"
        and row.sound_speed_m_s is not None
        and row.delta_e_from_saturated_liquid_J_kg is not None
    ]
    plt.figure(figsize=(8, 5))
    for cfl in D5_CFL_SEQUENCE:
        rows = [row for row in final29 if row.cfl == cfl]
        plt.scatter(
            [row.delta_e_from_saturated_liquid_J_kg for row in rows],
            [row.sound_speed_m_s for row in rows],
            label=f"CFL {cfl:g}",
        )
    plt.xlabel("delta e from saturated liquid [J/kg]")
    plt.ylabel("accepted sound speed [m/s]")
    plt.title("Cell 29 acoustic branch versus saturation margin")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_paths["acoustic"])
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(
        [row.cfl for row in result.candidate_metrics],
        [row.maximum_candidate_q_eq for row in result.candidate_metrics],
        marker="o",
    )
    plt.axhline(D5_THRESHOLD, linestyle="--", label="accepted threshold")
    plt.xlabel("CFL")
    plt.ylabel("maximum candidate q_eq")
    plt.title("Cross-CFL candidate depth")
    plt.gca().invert_xaxis()
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_paths["depth"])
    plt.close()
    return plot_paths


def write_gate9_d5_artifacts(
    output_dir: str | Path,
    result: Gate9D5Result,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "summary": target / "summary.json",
        "candidate_metrics": target / "per_cfl_candidate_metrics.csv",
        "cell_stage": target / "focused_cell_stage_history.csv",
        "interfaces": target / "focused_interface_flux_decomposition.csv",
        "comparison": target / "candidate_event_comparison.csv",
        "margins": target / "saturation_margin_history.csv",
        "projection": target / "projection_history.csv",
        "budget": target / "budget_history.csv",
        "acoustic": target / "acoustic_attempt_history.csv",
        "cfl": target / "cfl_decision_history.csv",
        "timeline": target / "candidate_event_timeline.csv",
        "report": target / "report.md",
        "digest": target / "artifact_sha256.txt",
    }
    paths["summary"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_dataclass_rows(
        paths["candidate_metrics"],
        Gate9D5CandidateMetric,
        result.candidate_metrics,
    )
    _write_dataclass_rows(
        paths["cell_stage"],
        Gate9D5CellStageRecord,
        result.cell_stage_records,
    )
    _write_dataclass_rows(
        paths["interfaces"],
        Gate9D5InterfaceRecord,
        result.interface_records,
    )
    _write_dataclass_rows(
        paths["comparison"],
        Gate9D5CandidateComparisonRecord,
        result.candidate_comparison,
    )
    _write_saturation_margin_rows(paths["margins"], result.cell_stage_records)
    _write_dataclass_rows(
        paths["projection"],
        Gate9D5ProjectionRecord,
        result.projection_records,
    )
    _write_dataclass_rows(
        paths["budget"],
        Gate9D5BudgetRecord,
        result.budget_records,
    )
    _write_dataclass_rows(
        paths["acoustic"],
        Gate9D4AlignedAcousticRecord,
        result.acoustic_records,
    )
    _write_dataclass_rows(
        paths["cfl"],
        Gate9D4CflDecisionRecord,
        result.cfl_decision_records,
    )
    _write_dataclass_rows(
        paths["timeline"],
        Gate9D5TimelineRecord,
        result.timeline_records,
    )
    _write_report(paths["report"], result)
    paths.update(_write_plots(target, result))

    digest_sources = sorted(
        (
            path
            for path in target.iterdir()
            if path.is_file() and path != paths["digest"]
        ),
        key=lambda path: path.name,
    )
    paths["digest"].write_text(
        "\n".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
            for path in digest_sources
        )
        + "\n",
        encoding="utf-8",
    )
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    result = run_gate9_d5_three_cfl_integration()
    paths = write_gate9_d5_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    print(f"artifact_digest={paths['digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
