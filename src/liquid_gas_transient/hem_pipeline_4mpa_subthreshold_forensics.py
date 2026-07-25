"""Verification-only forensic diagnostics for the fixed Stage 7 4 MPa case.

The diagnostic replays the merged PR #77 fixed case, requires exact baseline
identity, and then derives thermodynamic, flux-decomposition, isentropic, and
rho/e perturbation evidence without changing the solver update.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .boundary import LinearPressureRamp, ReflectiveBoundary
from .config import PipeGeometry
from .flux import physical_flux, rusanov_flux
from .grid import UniformGrid
from .hem_equilibrium_sound_speed import estimate_coolprop_equilibrium_sound_speed
from .hem_liquid_to_two_phase_crossing import derive_boundary_regions
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_phase_classification import evaluate_coolprop_hem_phase_state
from .hem_pipeline_depressurization_boundary import (
    VerificationHEMPrescribedSubcooledOutletBoundary,
    VerificationHEMPrescribedSubcooledStateProvider,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    run_pipeline_depressurization_case,
)
from .solver import FvmSolver
from .state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    N_VARS,
    check_physical_state,
    internal_energy,
    make_conserved,
    vapor_mass_fraction,
    velocity,
)

CASE_ID = "pipeline_liquid_control_p5m5_to_p4m5"
SELECTED_STEPS = tuple(range(300, 314))
SELECTED_CELLS = tuple(range(23, 28))
PERTURBATION_LEVELS = (
    -1.0e-6,
    -1.0e-8,
    -1.0e-10,
    -1.0e-12,
    0.0,
    1.0e-12,
    1.0e-10,
    1.0e-8,
    1.0e-6,
)
RECONSTRUCTION_RELATIVE_TOLERANCE = 2.0e-12
RECONSTRUCTION_ABSOLUTE_TOLERANCE = 1.0e-8

EXPECTED_BASELINE = {
    "outcome": "GUARD_FAILURE",
    "failure_reason": (
        "HEMPipelineDepressurizationError: "
        "crossing quality evidence is below the fixed minimum"
    ),
    "step_count": 313,
    "final_time_s": 0.001996923102525957,
    "crossing_step": 313,
    "crossing_time_s": 0.001996923102525957,
    "crossing_cell_indices": (25,),
    "crossing_distances_from_outlet_m": (0.203125,),
    "maximum_crossing_quality": 9.672588429198319e-9,
    "final_state_sha256": (
        "7e8b6a6bc715755e0419d8a469140c02a79ec5e8bb419eb4868553c3228242e1"
    ),
    "run_signature_sha256": (
        "fdd25cbf669428790d1f3d877ab3b86ec329726d7b10e3a8461443ba6340b202"
    ),
}


class HEM4MPaForensicError(RuntimeError):
    """Raised when the fixed forensic diagnostic cannot be completed safely."""


@dataclass(frozen=True)
class LocalStateRecord:
    case_id: str
    step_index: int
    cell_index: int
    stage: str
    time_s: float
    cell_center_m: float
    distance_from_outlet_m: float
    rho_kg_m3: float
    velocity_m_s: float
    e_j_kg: float
    pressure_pa: float
    temperature_K: float
    enthalpy_j_kg: float
    entropy_j_kg_K: float
    q_transport: float
    q_equilibrium: float
    void_fraction: float
    phase_class: str
    boundary_region: str
    transition_event: str
    sound_speed_m_s: float
    conserved_rho: float
    conserved_momentum: float
    conserved_energy: float
    conserved_rho_q: float
    boundary_pressure_pa: float | None
    boundary_temperature_K: float | None
    boundary_rho_kg_m3: float | None
    boundary_e_j_kg: float | None
    reverse_flow_fallback_count: int


@dataclass(frozen=True)
class SaturationMarginRecord:
    case_id: str
    step_index: int
    cell_index: int
    time_s: float
    pressure_pa: float
    rho_kg_m3: float
    e_j_kg: float
    specific_volume_m3_kg: float
    saturated_liquid_e_j_kg: float
    saturated_vapor_e_j_kg: float
    saturated_liquid_v_m3_kg: float
    saturated_vapor_v_m3_kg: float
    saturated_liquid_s_j_kg_K: float
    saturated_vapor_s_j_kg_K: float
    delta_u_sat_j_kg: float
    delta_v_sat_m3_kg: float
    q_from_internal_energy: float
    q_from_specific_volume: float
    q_equilibrium: float
    boundary_region: str
    coordinate_support: str
    entropy_raw_j_kg_K: float
    entropy_offset_from_initial_j_kg_K: float
    isentropic_flash_pressure_pa: float | None
    pressure_offset_from_isentropic_pa: float | None


@dataclass(frozen=True)
class FluxDecompositionRecord:
    case_id: str
    step_index: int
    cell_index: int
    time_before_s: float
    dt_s: float
    left_face_index: int
    right_face_index: int
    left_s_max_m_s: float
    right_s_max_m_s: float
    left_total_flux: tuple[float, ...]
    right_total_flux: tuple[float, ...]
    left_central_flux: tuple[float, ...]
    right_central_flux: tuple[float, ...]
    left_dissipative_flux: tuple[float, ...]
    right_dissipative_flux: tuple[float, ...]
    delta_U_central: tuple[float, ...]
    delta_U_dissipative: tuple[float, ...]
    delta_U_total: tuple[float, ...]
    reconstructed_raw_max_abs_error: float
    reconstructed_raw_max_relative_error: float
    central_only_finite_physical: bool
    central_only_eos_accepted: bool
    central_only_failure_reason: str
    central_only_boundary_region: str
    central_only_q_equilibrium: float | None
    central_only_delta_u_sat_j_kg: float | None
    central_only_delta_v_sat_m3_kg: float | None
    left_face_rhoE_update_contribution: float
    right_face_rhoE_update_contribution: float
    right_to_left_rhoE_contribution_ratio: float


@dataclass(frozen=True)
class PerturbationRecord:
    delta_rho_relative: float
    delta_e_relative: float
    rho_kg_m3: float
    e_j_kg: float
    pressure_pa: float | None
    temperature_K: float | None
    phase_class: str
    boundary_region: str
    q_equilibrium: float | None
    void_fraction: float | None
    delta_u_sat_j_kg: float | None
    delta_v_sat_m3_kg: float | None
    pressure_round_trip_residual_pa: float | None
    temperature_round_trip_residual_K: float | None
    rho_round_trip_residual_kg_m3: float | None
    e_round_trip_residual_j_kg: float | None
    accepted_state_eos: bool
    failure_reason: str


@dataclass(frozen=True)
class IsentropicReference:
    initial_entropy_j_kg_K: float
    bracketed: bool
    bracket_low_pa: float | None
    bracket_high_pa: float | None
    flash_pressure_pa: float | None
    residual_j_kg_K: float | None
    failure_reason: str


@dataclass(frozen=True)
class HEM4MPaForensicResult:
    baseline_summary: dict[str, object]
    local_states: tuple[LocalStateRecord, ...]
    saturation_margins: tuple[SaturationMarginRecord, ...]
    isentropic_reference: IsentropicReference
    flux_decomposition: tuple[FluxDecompositionRecord, ...]
    perturbations: tuple[PerturbationRecord, ...]
    perturbation_sensitivity: str
    diagnostic_categories: tuple[str, ...]
    diagnostic_rationale: dict[str, str]
    reconstruction_max_abs_error: float
    reconstruction_max_relative_error: float
    generated_plots: tuple[str, ...]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "stage7_lco2_hem_4mpa_subthreshold_forensics_v1",
            "scope": "verification_only",
            "case_id": CASE_ID,
            "selected_steps": list(SELECTED_STEPS),
            "selected_cells": list(SELECTED_CELLS),
            "baseline_reproduced_exactly": True,
            "baseline_summary": dict(self.baseline_summary),
            "provenance": {
                "pr77_merge_commit": "5657d26b3f37443ef63971245dce66ddd72c681e",
                "pr77_validated_runner_blob": "87df463996ea68789764e11f4ce9799ec214440e",
                "pr77_validated_test_blob": "817cb1c8c42658481ab0babcdddc34ab7966c4a2",
                "required_coolprop_version": "8.0.0",
            },
            "local_state_record_count": len(self.local_states),
            "saturation_margin_record_count": len(self.saturation_margins),
            "flux_decomposition_record_count": len(self.flux_decomposition),
            "perturbation_record_count": len(self.perturbations),
            "perturbation_sensitivity": self.perturbation_sensitivity,
            "diagnostic_categories": list(self.diagnostic_categories),
            "diagnostic_rationale": dict(self.diagnostic_rationale),
            "reconstruction_max_abs_error": self.reconstruction_max_abs_error,
            "reconstruction_max_relative_error": self.reconstruction_max_relative_error,
            "generated_plots": list(self.generated_plots),
            "PR77_observation_reclassified": False,
            "Gate_P2_passed": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }


def _props_si():
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("CoolProp is required for the 4 MPa forensic diagnostic") from exc
    return PropsSI


def _scalar(value: object) -> float:
    array = np.asarray(value, dtype=float)
    if array.size != 1:
        raise HEM4MPaForensicError(f"expected scalar value, received shape {array.shape}")
    result = float(array.reshape(-1)[0])
    if not np.isfinite(result):
        raise HEM4MPaForensicError("diagnostic property value is non-finite")
    return result


def _region_and_phase(rho: float, e: float, config: HEMPipelineDepressurizationConfig):
    phase = evaluate_coolprop_hem_phase_state(
        np.asarray([rho], dtype=float),
        np.asarray([e], dtype=float),
        config=config.phase_config,
    )
    regions = derive_boundary_regions(phase, config=config.phase_config)
    if regions.shape != (1,):
        raise HEM4MPaForensicError("phase-region diagnostic must return one cell")
    return phase, str(regions[0])


def _quality_alpha(phase) -> tuple[float, float]:
    q_defined = bool(np.asarray(phase.quality_defined)[0])
    a_defined = bool(np.asarray(phase.alpha_defined)[0])
    if not q_defined or not a_defined:
        raise HEM4MPaForensicError("diagnostic liquid/two-phase state requires q and alpha")
    return (
        float(np.asarray(phase.quality, dtype=float)[0]),
        float(np.asarray(phase.alpha, dtype=float)[0]),
    )


def _state_thermodynamics(
    U: np.ndarray,
    *,
    config: HEMPipelineDepressurizationConfig,
) -> dict[str, object]:
    state = np.asarray(U, dtype=float)
    if state.shape != (N_VARS,):
        raise HEM4MPaForensicError(f"state must have shape ({N_VARS},)")
    check_physical_state(state[np.newaxis, :], names=["forensic state"])
    rho = float(state[IDX_RHO])
    u = float(velocity(state))
    e = float(internal_energy(state))
    q_transport = float(vapor_mass_fraction(state))
    phase, region = _region_and_phase(rho, e, config)
    q_eq, alpha = _quality_alpha(phase)
    p = float(np.asarray(phase.p, dtype=float)[0])
    T = float(np.asarray(phase.T, dtype=float)[0])
    phase_class = str(np.asarray(phase.phase_class).astype(str)[0])
    props = _props_si()
    h = float(props("Hmass", "Dmass", rho, "Umass", e, "CO2"))
    s = float(props("Smass", "Dmass", rho, "Umass", e, "CO2"))
    acoustic = estimate_coolprop_equilibrium_sound_speed(
        rho,
        e,
    )
    return {
        "rho_kg_m3": rho,
        "velocity_m_s": u,
        "e_j_kg": e,
        "pressure_pa": p,
        "temperature_K": T,
        "enthalpy_j_kg": h,
        "entropy_j_kg_K": s,
        "q_transport": q_transport,
        "q_equilibrium": q_eq,
        "void_fraction": alpha,
        "phase_class": phase_class,
        "boundary_region": region,
        "sound_speed_m_s": float(acoustic.sound_speed_m_s),
    }


def _saturated_properties(pressure_pa: float) -> dict[str, float]:
    props = _props_si()
    values = {
        "uf": float(props("Umass", "P", pressure_pa, "Q", 0.0, "CO2")),
        "ug": float(props("Umass", "P", pressure_pa, "Q", 1.0, "CO2")),
        "rhof": float(props("Dmass", "P", pressure_pa, "Q", 0.0, "CO2")),
        "rhog": float(props("Dmass", "P", pressure_pa, "Q", 1.0, "CO2")),
        "sf": float(props("Smass", "P", pressure_pa, "Q", 0.0, "CO2")),
        "sg": float(props("Smass", "P", pressure_pa, "Q", 1.0, "CO2")),
    }
    if not all(np.isfinite(value) for value in values.values()):
        raise HEM4MPaForensicError("saturation backend returned a non-finite property")
    if values["ug"] <= values["uf"] or values["rhof"] <= values["rhog"]:
        raise HEM4MPaForensicError("saturation property ordering is invalid")
    values["vf"] = 1.0 / values["rhof"]
    values["vg"] = 1.0 / values["rhog"]
    return values


def _saturation_margin_values(
    rho: float,
    e: float,
    pressure_pa: float,
) -> dict[str, float | str]:
    sat = _saturated_properties(pressure_pa)
    v = 1.0 / rho
    delta_u = e - sat["uf"]
    delta_v = v - sat["vf"]
    q_u = delta_u / (sat["ug"] - sat["uf"])
    q_v = delta_v / (sat["vg"] - sat["vf"])
    if delta_u < 0.0 and delta_v < 0.0:
        support = "LIQUID_SIDE_SUPPORT"
    elif delta_u > 0.0 and delta_v > 0.0:
        support = "TWO_PHASE_SIDE_SUPPORT"
    elif delta_u == 0.0 and delta_v == 0.0:
        support = "SATURATION_BOUNDARY"
    else:
        support = "COORDINATE_DISAGREEMENT"
    return {
        **sat,
        "v": v,
        "delta_u": delta_u,
        "delta_v": delta_v,
        "q_u": q_u,
        "q_v": q_v,
        "coordinate_support": support,
    }


def _raw_state_from_cell(cell) -> np.ndarray:
    return make_conserved(
        float(cell.rho_raw_kg_m3),
        float(cell.velocity_raw_m_s),
        float(cell.e_raw_j_kg),
        float(cell.q_transport_raw),
    )


def _assert_baseline(case: PipelineCaseResult) -> None:
    actual = {
        "outcome": case.outcome,
        "failure_reason": case.failure_reason,
        "step_count": case.step_count,
        "final_time_s": case.final_time_s,
        "crossing_step": case.crossing_step,
        "crossing_time_s": case.crossing_time_s,
        "crossing_cell_indices": case.crossing_cell_indices,
        "crossing_distances_from_outlet_m": case.crossing_distances_from_outlet_m,
        "maximum_crossing_quality": case.maximum_crossing_quality,
        "final_state_sha256": case.final_state_sha256,
        "run_signature_sha256": case.run_signature_sha256,
    }
    if actual != EXPECTED_BASELINE:
        raise HEM4MPaForensicError(
            "PR #77 baseline mismatch; forensic diagnosis is not allowed: "
            + json.dumps(
                {
                    "actual": {
                        key: list(value) if isinstance(value, tuple) else value
                        for key, value in actual.items()
                    },
                    "expected": {
                        key: list(value) if isinstance(value, tuple) else value
                        for key, value in EXPECTED_BASELINE.items()
                    },
                },
                sort_keys=True,
            )
        )


def _case_spec():
    for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        if case.case_id == CASE_ID:
            return case
    raise HEM4MPaForensicError("fixed 4 MPa case specification was not found")


def _local_records(
    case: PipelineCaseResult,
    config: HEMPipelineDepressurizationConfig,
    isentropic: IsentropicReference,
) -> tuple[tuple[LocalStateRecord, ...], tuple[SaturationMarginRecord, ...]]:
    cell_map = {(cell.step_index, cell.cell_index): cell for cell in case.cells}
    step_map = {step.step_index: step for step in case.steps}
    local_records: list[LocalStateRecord] = []
    margins: list[SaturationMarginRecord] = []

    for step_index in SELECTED_STEPS:
        if step_index not in step_map:
            raise HEM4MPaForensicError(f"missing selected step {step_index}")
        step = step_map[step_index]
        for cell_index in SELECTED_CELLS:
            cell = cell_map.get((step_index, cell_index))
            if cell is None:
                raise HEM4MPaForensicError(
                    f"missing selected cell evidence at step={step_index}, cell={cell_index}"
                )
            states = (
                (
                    "accepted_before",
                    float(step.time_before_s),
                    np.asarray(case.accepted_state_history[step_index - 1, cell_index]),
                    "",
                ),
                (
                    "raw_fvm",
                    float(step.time_after_s),
                    _raw_state_from_cell(cell),
                    str(cell.transition_event),
                ),
                (
                    "post_projection",
                    float(step.time_after_s),
                    np.asarray(case.accepted_state_history[step_index, cell_index]),
                    str(cell.transition_event),
                ),
            )
            for stage, time_s, U, event in states:
                data = _state_thermodynamics(U, config=config)
                local_records.append(
                    LocalStateRecord(
                        case_id=CASE_ID,
                        step_index=step_index,
                        cell_index=cell_index,
                        stage=stage,
                        time_s=time_s,
                        cell_center_m=float(cell.cell_center_m),
                        distance_from_outlet_m=float(cell.distance_from_outlet_m),
                        transition_event=event,
                        conserved_rho=float(U[IDX_RHO]),
                        conserved_momentum=float(U[IDX_MOM]),
                        conserved_energy=float(U[IDX_RHOE]),
                        conserved_rho_q=float(U[IDX_RHO_XV]),
                        boundary_pressure_pa=(
                            None if step.boundary_pressure_pa is None
                            else float(step.boundary_pressure_pa)
                        ),
                        boundary_temperature_K=(
                            None if step.boundary_temperature_K is None
                            else float(step.boundary_temperature_K)
                        ),
                        boundary_rho_kg_m3=(
                            None if step.boundary_rho_kg_m3 is None
                            else float(step.boundary_rho_kg_m3)
                        ),
                        boundary_e_j_kg=(
                            None if step.boundary_e_j_kg is None
                            else float(step.boundary_e_j_kg)
                        ),
                        reverse_flow_fallback_count=int(
                            step.reverse_flow_fallback_count
                        ),
                        **data,
                    )
                )
                if stage == "raw_fvm":
                    margin = _saturation_margin_values(
                        float(data["rho_kg_m3"]),
                        float(data["e_j_kg"]),
                        float(data["pressure_pa"]),
                    )
                    margins.append(
                        SaturationMarginRecord(
                            case_id=CASE_ID,
                            step_index=step_index,
                            cell_index=cell_index,
                            time_s=time_s,
                            pressure_pa=float(data["pressure_pa"]),
                            rho_kg_m3=float(data["rho_kg_m3"]),
                            e_j_kg=float(data["e_j_kg"]),
                            specific_volume_m3_kg=float(margin["v"]),
                            saturated_liquid_e_j_kg=float(margin["uf"]),
                            saturated_vapor_e_j_kg=float(margin["ug"]),
                            saturated_liquid_v_m3_kg=float(margin["vf"]),
                            saturated_vapor_v_m3_kg=float(margin["vg"]),
                            saturated_liquid_s_j_kg_K=float(margin["sf"]),
                            saturated_vapor_s_j_kg_K=float(margin["sg"]),
                            delta_u_sat_j_kg=float(margin["delta_u"]),
                            delta_v_sat_m3_kg=float(margin["delta_v"]),
                            q_from_internal_energy=float(margin["q_u"]),
                            q_from_specific_volume=float(margin["q_v"]),
                            q_equilibrium=float(data["q_equilibrium"]),
                            boundary_region=str(data["boundary_region"]),
                            coordinate_support=str(margin["coordinate_support"]),
                            entropy_raw_j_kg_K=float(data["entropy_j_kg_K"]),
                            entropy_offset_from_initial_j_kg_K=(
                                float(data["entropy_j_kg_K"])
                                - isentropic.initial_entropy_j_kg_K
                            ),
                            isentropic_flash_pressure_pa=(
                                isentropic.flash_pressure_pa
                            ),
                            pressure_offset_from_isentropic_pa=(
                                None
                                if isentropic.flash_pressure_pa is None
                                else float(data["pressure_pa"])
                                - isentropic.flash_pressure_pa
                            ),
                        )
                    )
    return tuple(local_records), tuple(margins)


def _solve_isentropic_reference(case: PipelineCaseResult) -> IsentropicReference:
    props = _props_si()
    rho0 = case.initial_state.rho_kg_m3
    e0 = case.initial_state.e_j_kg
    s0 = float(props("Smass", "Dmass", rho0, "Umass", e0, "CO2"))
    try:
        p_triple = float(props("ptriple", "CO2"))
    except Exception:
        p_triple = float(props("P", "T", props("Ttriple", "CO2"), "Q", 0.0, "CO2"))
    p_high = min(case.config.initial_pressure_pa, float(props("Pcrit", "CO2")) * (1.0 - 1.0e-9))
    p_low = p_triple * (1.0 + 1.0e-8)

    scan = np.linspace(p_low, p_high, 512)
    values: list[tuple[float, float]] = []
    for p in scan:
        try:
            g = float(props("Smass", "P", float(p), "Q", 0.0, "CO2")) - s0
        except Exception:
            continue
        if np.isfinite(g):
            values.append((float(p), g))
    bracket: tuple[float, float] | None = None
    for (p0, g0), (p1, g1) in zip(values, values[1:]):
        if g0 == 0.0:
            bracket = (p0, p0)
            break
        if g0 * g1 <= 0.0:
            bracket = (p0, p1)
            break
    if bracket is None:
        return IsentropicReference(
            initial_entropy_j_kg_K=s0,
            bracketed=False,
            bracket_low_pa=None,
            bracket_high_pa=None,
            flash_pressure_pa=None,
            residual_j_kg_K=None,
            failure_reason="saturated-liquid entropy root was not bracketed",
        )
    low, high = bracket
    if low == high:
        root = low
    else:
        def residual(p: float) -> float:
            return float(props("Smass", "P", p, "Q", 0.0, "CO2")) - s0

        g_low = residual(low)
        for _ in range(120):
            mid = 0.5 * (low + high)
            g_mid = residual(mid)
            if abs(g_mid) <= 1.0e-10 or abs(high - low) <= 1.0e-8:
                low = high = mid
                break
            if g_low * g_mid <= 0.0:
                high = mid
            else:
                low = mid
                g_low = g_mid
        root = 0.5 * (low + high)
    residual_value = float(props("Smass", "P", root, "Q", 0.0, "CO2")) - s0
    return IsentropicReference(
        initial_entropy_j_kg_K=s0,
        bracketed=True,
        bracket_low_pa=float(bracket[0]),
        bracket_high_pa=float(bracket[1]),
        flash_pressure_pa=float(root),
        residual_j_kg_K=float(residual_value),
        failure_reason="",
    )


def _raw_state_map(case: PipelineCaseResult) -> dict[tuple[int, int], np.ndarray]:
    return {
        (cell.step_index, cell.cell_index): _raw_state_from_cell(cell)
        for cell in case.cells
    }


def _evaluate_counterfactual(
    U: np.ndarray,
    config: HEMPipelineDepressurizationConfig,
) -> dict[str, object]:
    state = np.asarray(U, dtype=float)
    try:
        check_physical_state(
            state[np.newaxis, :],
            require_xv_bounds=False,
            names=["central-only counterfactual"],
        )
        finite_physical = True
    except Exception as exc:
        return {
            "finite_physical": False,
            "eos_accepted": False,
            "failure_reason": f"{type(exc).__name__}: {exc}",
            "region": "",
            "q": None,
            "delta_u": None,
            "delta_v": None,
        }
    try:
        data = _state_thermodynamics(state, config=config)
        q_eq = float(data["q_equilibrium"])
        eos = VerificationHEMLiquidOpenTwoPhaseEOS(
            quality_tolerance=config.accepted_state_quality_tolerance,
            phase_config=config.phase_config,
            quality_sync_config=config.projection_config,
        )
        synchronized = make_conserved(
            float(data["rho_kg_m3"]),
            float(data["velocity_m_s"]),
            float(data["e_j_kg"]),
            q_eq,
        )
        eos.primitive_from_conserved(synchronized[np.newaxis, :])
        margin = _saturation_margin_values(
            float(data["rho_kg_m3"]),
            float(data["e_j_kg"]),
            float(data["pressure_pa"]),
        )
        return {
            "finite_physical": finite_physical,
            "eos_accepted": True,
            "failure_reason": "",
            "region": str(data["boundary_region"]),
            "q": q_eq,
            "delta_u": float(margin["delta_u"]),
            "delta_v": float(margin["delta_v"]),
        }
    except Exception as exc:
        return {
            "finite_physical": finite_physical,
            "eos_accepted": False,
            "failure_reason": f"{type(exc).__name__}: {exc}",
            "region": "",
            "q": None,
            "delta_u": None,
            "delta_v": None,
        }


def _flux_decomposition(
    case: PipelineCaseResult,
    config: HEMPipelineDepressurizationConfig,
) -> tuple[FluxDecompositionRecord, ...]:
    grid = UniformGrid(
        PipeGeometry(length_m=config.length_m, diameter_m=config.diameter_m),
        n_cells=config.n_cells,
    )
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        quality_tolerance=config.accepted_state_quality_tolerance,
        phase_config=config.phase_config,
        quality_sync_config=config.projection_config,
    )
    schedule = LinearPressureRamp(
        p_initial_pa=config.initial_pressure_pa,
        p_final_pa=4.0e6,
        t_start_s=0.0,
        duration_s=case.ramp_duration_s,
    )
    provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=config.subcooling_K,
        phase_config=config.phase_config,
    )
    right_boundary = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    step_map = {step.step_index: step for step in case.steps}
    raw_map = _raw_state_map(case)
    records: list[FluxDecompositionRecord] = []

    for step_index in SELECTED_STEPS:
        step = step_map[step_index]
        U_before = np.asarray(case.accepted_state_history[step_index - 1], dtype=float)
        solver = FvmSolver(
            grid=grid,
            eos=eos,
            U=U_before,
            cfl=config.cfl,
            n_ghost=config.n_ghost,
            left_boundary=ReflectiveBoundary(),
            right_boundary=right_boundary,
            enable_boundary_budget=False,
            enable_phase_budget=False,
            enable_energy_budget=False,
            enable_interface_budget=False,
            t=float(step.time_before_s),
        )
        U_ext = solver.extend_with_ghosts(float(step.time_before_s))
        U_left = U_ext[:-1]
        U_right = U_ext[1:]
        prim_l = eos.primitive_from_conserved(U_left)
        prim_r = eos.primitive_from_conserved(U_right)
        F_l = physical_flux(U_left, prim_l)
        F_r = physical_flux(U_right, prim_r)
        s_max = np.maximum(np.abs(prim_l.u) + prim_l.c, np.abs(prim_r.u) + prim_r.c)
        central = 0.5 * (F_l + F_r)
        dissipative = -0.5 * s_max[..., np.newaxis] * (U_right - U_left)
        total = central + dissipative
        direct_total = rusanov_flux(U_left, U_right, eos)
        if not np.allclose(total, direct_total, rtol=0.0, atol=1.0e-12):
            raise HEM4MPaForensicError("Rusanov decomposition did not reproduce flux")
        i0 = config.n_ghost
        dt_dx = float(step.dt_s) / grid.dx

        for cell_index in SELECTED_CELLS:
            left_face = i0 - 1 + cell_index
            right_face = i0 + cell_index
            delta_central = -dt_dx * (
                central[right_face] - central[left_face]
            )
            delta_dissipative = -dt_dx * (
                dissipative[right_face] - dissipative[left_face]
            )
            delta_total = delta_central + delta_dissipative
            reconstructed = U_before[cell_index] + delta_total
            raw = raw_map[(step_index, cell_index)]
            error = reconstructed - raw
            scale = np.maximum(np.abs(raw), 1.0)
            max_abs = float(np.max(np.abs(error)))
            max_rel = float(np.max(np.abs(error) / scale))
            if not np.allclose(
                reconstructed,
                raw,
                rtol=RECONSTRUCTION_RELATIVE_TOLERANCE,
                atol=RECONSTRUCTION_ABSOLUTE_TOLERANCE,
            ):
                raise HEM4MPaForensicError(
                    f"flux decomposition failed to reconstruct raw state at "
                    f"step={step_index}, cell={cell_index}: "
                    f"max_abs={max_abs}, max_rel={max_rel}"
                )
            central_only = U_before[cell_index] + delta_central
            counter = _evaluate_counterfactual(central_only, config)
            left_energy = dt_dx * float(total[left_face, IDX_RHOE])
            right_energy = -dt_dx * float(total[right_face, IDX_RHOE])
            ratio = abs(right_energy) / max(abs(left_energy), 1.0e-300)
            records.append(
                FluxDecompositionRecord(
                    case_id=CASE_ID,
                    step_index=step_index,
                    cell_index=cell_index,
                    time_before_s=float(step.time_before_s),
                    dt_s=float(step.dt_s),
                    left_face_index=int(left_face),
                    right_face_index=int(right_face),
                    left_s_max_m_s=float(s_max[left_face]),
                    right_s_max_m_s=float(s_max[right_face]),
                    left_total_flux=tuple(float(v) for v in total[left_face]),
                    right_total_flux=tuple(float(v) for v in total[right_face]),
                    left_central_flux=tuple(float(v) for v in central[left_face]),
                    right_central_flux=tuple(float(v) for v in central[right_face]),
                    left_dissipative_flux=tuple(
                        float(v) for v in dissipative[left_face]
                    ),
                    right_dissipative_flux=tuple(
                        float(v) for v in dissipative[right_face]
                    ),
                    delta_U_central=tuple(float(v) for v in delta_central),
                    delta_U_dissipative=tuple(
                        float(v) for v in delta_dissipative
                    ),
                    delta_U_total=tuple(float(v) for v in delta_total),
                    reconstructed_raw_max_abs_error=max_abs,
                    reconstructed_raw_max_relative_error=max_rel,
                    central_only_finite_physical=bool(counter["finite_physical"]),
                    central_only_eos_accepted=bool(counter["eos_accepted"]),
                    central_only_failure_reason=str(counter["failure_reason"]),
                    central_only_boundary_region=str(counter["region"]),
                    central_only_q_equilibrium=(
                        None if counter["q"] is None else float(counter["q"])
                    ),
                    central_only_delta_u_sat_j_kg=(
                        None
                        if counter["delta_u"] is None
                        else float(counter["delta_u"])
                    ),
                    central_only_delta_v_sat_m3_kg=(
                        None
                        if counter["delta_v"] is None
                        else float(counter["delta_v"])
                    ),
                    left_face_rhoE_update_contribution=left_energy,
                    right_face_rhoE_update_contribution=right_energy,
                    right_to_left_rhoE_contribution_ratio=float(ratio),
                )
            )
    return tuple(records)


def _round_trip(
    rho: float,
    e: float,
    phase,
    region: str,
) -> tuple[float | None, float | None, float | None, float | None]:
    props = _props_si()
    p = float(np.asarray(phase.p, dtype=float)[0])
    T = float(np.asarray(phase.T, dtype=float)[0])
    try:
        if region == "OPEN_TWO_PHASE":
            q = float(np.asarray(phase.quality, dtype=float)[0])
            rho_back = float(props("Dmass", "P", p, "Q", q, "CO2"))
            e_back = float(props("Umass", "P", p, "Q", q, "CO2"))
            p_back = float(props("P", "Dmass", rho_back, "Umass", e_back, "CO2"))
            T_back = float(props("T", "Dmass", rho_back, "Umass", e_back, "CO2"))
        else:
            rho_back = float(props("Dmass", "P", p, "T", T, "CO2"))
            e_back = float(props("Umass", "P", p, "T", T, "CO2"))
            p_back = float(props("P", "Dmass", rho_back, "Umass", e_back, "CO2"))
            T_back = float(props("T", "Dmass", rho_back, "Umass", e_back, "CO2"))
        return (
            p_back - p,
            T_back - T,
            rho_back - rho,
            e_back - e,
        )
    except Exception:
        return (None, None, None, None)


def _perturbation_records(
    crossing_raw: np.ndarray,
    config: HEMPipelineDepressurizationConfig,
) -> tuple[PerturbationRecord, ...]:
    rho0 = float(crossing_raw[IDX_RHO])
    e0 = float(internal_energy(crossing_raw))
    u0 = float(velocity(crossing_raw))
    records: list[PerturbationRecord] = []
    for delta_rho in PERTURBATION_LEVELS:
        for delta_e in PERTURBATION_LEVELS:
            rho = rho0 * (1.0 + delta_rho)
            e = e0 * (1.0 + delta_e)
            try:
                phase, region = _region_and_phase(rho, e, config)
                q, alpha = _quality_alpha(phase)
                p = float(np.asarray(phase.p, dtype=float)[0])
                T = float(np.asarray(phase.T, dtype=float)[0])
                phase_class = str(np.asarray(phase.phase_class).astype(str)[0])
                margin = _saturation_margin_values(rho, e, p)
                rt = _round_trip(rho, e, phase, region)
                accepted = False
                failure = ""
                try:
                    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
                        quality_tolerance=config.accepted_state_quality_tolerance,
                        phase_config=config.phase_config,
                        quality_sync_config=config.projection_config,
                    )
                    U = make_conserved(rho, u0, e, q)
                    eos.primitive_from_conserved(U[np.newaxis, :])
                    accepted = True
                except Exception as exc:
                    failure = f"{type(exc).__name__}: {exc}"
                records.append(
                    PerturbationRecord(
                        delta_rho_relative=float(delta_rho),
                        delta_e_relative=float(delta_e),
                        rho_kg_m3=rho,
                        e_j_kg=e,
                        pressure_pa=p,
                        temperature_K=T,
                        phase_class=phase_class,
                        boundary_region=region,
                        q_equilibrium=q,
                        void_fraction=alpha,
                        delta_u_sat_j_kg=float(margin["delta_u"]),
                        delta_v_sat_m3_kg=float(margin["delta_v"]),
                        pressure_round_trip_residual_pa=rt[0],
                        temperature_round_trip_residual_K=rt[1],
                        rho_round_trip_residual_kg_m3=rt[2],
                        e_round_trip_residual_j_kg=rt[3],
                        accepted_state_eos=accepted,
                        failure_reason=failure,
                    )
                )
            except Exception as exc:
                records.append(
                    PerturbationRecord(
                        delta_rho_relative=float(delta_rho),
                        delta_e_relative=float(delta_e),
                        rho_kg_m3=rho,
                        e_j_kg=e,
                        pressure_pa=None,
                        temperature_K=None,
                        phase_class="",
                        boundary_region="",
                        q_equilibrium=None,
                        void_fraction=None,
                        delta_u_sat_j_kg=None,
                        delta_v_sat_m3_kg=None,
                        pressure_round_trip_residual_pa=None,
                        temperature_round_trip_residual_K=None,
                        rho_round_trip_residual_kg_m3=None,
                        e_round_trip_residual_j_kg=None,
                        accepted_state_eos=False,
                        failure_reason=f"{type(exc).__name__}: {exc}",
                    )
                )
    return tuple(records)


def classify_perturbation_sensitivity(
    records: Sequence[PerturbationRecord],
) -> str:
    baseline = next(
        record
        for record in records
        if record.delta_rho_relative == 0.0 and record.delta_e_relative == 0.0
    )
    if not baseline.boundary_region:
        return "INCONCLUSIVE"
    first_change: float | None = None
    for magnitude in (1.0e-12, 1.0e-10, 1.0e-8, 1.0e-6):
        changed = any(
            max(abs(record.delta_rho_relative), abs(record.delta_e_relative))
            <= magnitude
            and (record.delta_rho_relative != 0.0 or record.delta_e_relative != 0.0)
            and record.boundary_region != baseline.boundary_region
            for record in records
        )
        if changed:
            first_change = magnitude
            break
    if first_change is None:
        return "ROBUST_IN_TESTED_ENVELOPE"
    if first_change <= 1.0e-10:
        return "ROUND_OFF_SENSITIVE"
    if first_change == 1.0e-8:
        return "HIGHLY_SENSITIVE"
    return "WEAKLY_RESOLVED"


def _diagnostic_categories(
    margins: Sequence[SaturationMarginRecord],
    fluxes: Sequence[FluxDecompositionRecord],
    sensitivity: str,
) -> tuple[tuple[str, ...], dict[str, str]]:
    crossing_margin = next(
        record
        for record in margins
        if record.step_index == 313 and record.cell_index == 25
    )
    crossing_flux = next(
        record
        for record in fluxes
        if record.step_index == 313 and record.cell_index == 25
    )
    categories: list[str] = []
    rationale: dict[str, str] = {}

    thermodynamic = (
        crossing_margin.boundary_region == "OPEN_TWO_PHASE"
        and crossing_margin.delta_u_sat_j_kg > 0.0
        and crossing_margin.delta_v_sat_m3_kg > 0.0
        and crossing_margin.q_from_internal_energy > 0.0
        and crossing_margin.q_from_specific_volume > 0.0
    )
    if thermodynamic:
        categories.append("THERMODYNAMIC_TWO_PHASE_SUPPORTED")
        rationale["THERMODYNAMIC_TWO_PHASE_SUPPORTED"] = (
            "At the fixed crossing state, both independent saturation margins and both "
            "quality estimates are positive while the direct rho/e classifier is open two phase."
        )

    numerical = (
        crossing_flux.central_only_eos_accepted
        and crossing_flux.central_only_boundary_region == "LIQUID_CANDIDATE"
        and crossing_margin.boundary_region == "OPEN_TWO_PHASE"
    )
    if numerical:
        categories.append("NUMERICAL_DIFFUSION_CONSISTENT")
        rationale["NUMERICAL_DIFFUSION_CONSISTENT"] = (
            "The offline central-only update remains an accepted liquid while the exact "
            "central-plus-dissipative Rusanov update reaches the open two-phase side."
        )

    boundary = (
        crossing_flux.cell_index >= 30
        and crossing_flux.right_to_left_rhoE_contribution_ratio >= 2.0
        and crossing_flux.right_face_rhoE_update_contribution
        * crossing_flux.left_face_rhoE_update_contribution
        <= 0.0
    )
    if boundary:
        categories.append("BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT")
        rationale["BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT"] = (
            "At the crossing cell, the downstream/right-face conservative-energy update "
            "contribution dominates the upstream/left-face contribution by at least two."
        )

    if sensitivity != "ROBUST_IN_TESTED_ENVELOPE":
        categories.append("NEAR_SATURATION_PROPERTY_SENSITIVE")
        rationale["NEAR_SATURATION_PROPERTY_SENSITIVE"] = (
            f"The rho/e perturbation map is classified as {sensitivity}."
        )

    causal_count = len(categories)
    if causal_count >= 2:
        categories.append("MULTI_FACTOR_EVIDENCE")
        rationale["MULTI_FACTOR_EVIDENCE"] = (
            "More than one independently defined diagnostic mechanism is consistent "
            "with the fixed observation."
        )
    if not categories:
        categories.append("INCONCLUSIVE")
        rationale["INCONCLUSIVE"] = (
            "None of the reviewed diagnostic criteria was satisfied."
        )
    return tuple(categories), rationale


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


def _generate_plots(
    output_dir: Path,
    *,
    local_states: Sequence[LocalStateRecord],
    margins: Sequence[SaturationMarginRecord],
    fluxes: Sequence[FluxDecompositionRecord],
    perturbations: Sequence[PerturbationRecord],
) -> tuple[str, ...]:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return ()

    generated: list[str] = []
    crossing_local = [
        record
        for record in local_states
        if record.cell_index == 25 and record.stage == "raw_fvm"
    ]
    crossing_local.sort(key=lambda record: record.step_index)
    p_values = np.asarray([record.pressure_pa for record in crossing_local])
    p_grid = np.linspace(float(np.min(p_values)), float(np.max(p_values)), 200)
    sat_rho = []
    sat_e = []
    for p in p_grid:
        sat = _saturated_properties(float(p))
        sat_rho.append(float(sat["rhof"]))
        sat_e.append(float(sat["uf"]))

    fig, ax = plt.subplots(figsize=(8.0, 5.5))
    ax.plot(sat_rho, np.asarray(sat_e) / 1.0e3, label="saturated liquid")
    ax.plot(
        [record.rho_kg_m3 for record in crossing_local],
        [record.e_j_kg / 1.0e3 for record in crossing_local],
        marker="o",
        label="cell 25 raw trajectory",
    )
    ax.set_xlabel("density [kg/m3]")
    ax.set_ylabel("internal energy [kJ/kg]")
    ax.set_title("4 MPa crossing cell: rho-e saturation zoom")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    name = "rho_e_saturation_zoom.png"
    fig.savefig(output_dir / name, dpi=180, bbox_inches="tight")
    plt.close(fig)
    generated.append(name)

    margin_cell = [record for record in margins if record.cell_index == 25]
    margin_cell.sort(key=lambda record: record.step_index)
    fig, ax = plt.subplots(figsize=(8.0, 5.5))
    ax.plot(
        [record.time_s for record in margin_cell],
        [record.q_from_internal_energy for record in margin_cell],
        marker="o",
        label="q from internal energy",
    )
    ax.plot(
        [record.time_s for record in margin_cell],
        [record.q_from_specific_volume for record in margin_cell],
        marker="o",
        label="q from specific volume",
    )
    ax.plot(
        [record.time_s for record in margin_cell],
        [record.q_equilibrium for record in margin_cell],
        marker="o",
        label="CoolProp q_eq",
    )
    ax.axhline(0.0)
    ax.set_xlabel("time [s]")
    ax.set_ylabel("quality-like saturation coordinate [-]")
    ax.set_title("4 MPa cell 25: saturation margin history")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    name = "saturation_margin_vs_time.png"
    fig.savefig(output_dir / name, dpi=180, bbox_inches="tight")
    plt.close(fig)
    generated.append(name)

    crossing_flux = next(
        record
        for record in fluxes
        if record.step_index == 313 and record.cell_index == 25
    )
    labels = ("rho", "rho*u", "rho*E", "rho*q")
    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8.0, 5.5))
    ax.bar(
        x - width,
        np.asarray(crossing_flux.delta_U_central),
        width,
        label="central",
    )
    ax.bar(
        x,
        np.asarray(crossing_flux.delta_U_dissipative),
        width,
        label="dissipative",
    )
    ax.bar(
        x + width,
        np.asarray(crossing_flux.delta_U_total),
        width,
        label="total",
    )
    ax.set_xticks(x, labels)
    ax.set_ylabel("one-step conservative update")
    ax.set_title("Step 313 / cell 25: Rusanov update decomposition")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    name = "central_vs_dissipative_update.png"
    fig.savefig(output_dir / name, dpi=180, bbox_inches="tight")
    plt.close(fig)
    generated.append(name)

    region_names = sorted(
        {record.boundary_region or "FAILED" for record in perturbations}
    )
    region_code = {name: index for index, name in enumerate(region_names)}
    matrix = np.empty((len(PERTURBATION_LEVELS), len(PERTURBATION_LEVELS)))
    for record in perturbations:
        i = PERTURBATION_LEVELS.index(record.delta_e_relative)
        j = PERTURBATION_LEVELS.index(record.delta_rho_relative)
        matrix[i, j] = region_code[record.boundary_region or "FAILED"]
    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    image = ax.imshow(matrix, origin="lower", aspect="auto")
    ax.set_xticks(
        np.arange(len(PERTURBATION_LEVELS)),
        [f"{value:.0e}" if value else "0" for value in PERTURBATION_LEVELS],
        rotation=45,
        ha="right",
    )
    ax.set_yticks(
        np.arange(len(PERTURBATION_LEVELS)),
        [f"{value:.0e}" if value else "0" for value in PERTURBATION_LEVELS],
    )
    ax.set_xlabel("relative density perturbation")
    ax.set_ylabel("relative internal-energy perturbation")
    ax.set_title("Crossing-state rho/e perturbation classification")
    colorbar = fig.colorbar(image, ax=ax, ticks=list(region_code.values()))
    colorbar.ax.set_yticklabels(region_names)
    fig.tight_layout()
    name = "perturbation_classification_map.png"
    fig.savefig(output_dir / name, dpi=180, bbox_inches="tight")
    plt.close(fig)
    generated.append(name)

    return tuple(generated)


def run_fixed_4mpa_forensic_diagnostic(
    config: HEMPipelineDepressurizationConfig | None = None,
    *,
    generate_plots: bool = True,
    plot_output_dir: str | Path | None = None,
) -> HEM4MPaForensicResult:
    cfg = config or HEMPipelineDepressurizationConfig()
    case = run_pipeline_depressurization_case(_case_spec(), cfg)
    _assert_baseline(case)
    isentropic = _solve_isentropic_reference(case)
    local_states, margins = _local_records(case, cfg, isentropic)
    fluxes = _flux_decomposition(case, cfg)
    cell_map = {(cell.step_index, cell.cell_index): cell for cell in case.cells}
    crossing_raw = _raw_state_from_cell(cell_map[(313, 25)])
    perturbations = _perturbation_records(crossing_raw, cfg)
    sensitivity = classify_perturbation_sensitivity(perturbations)
    categories, rationale = _diagnostic_categories(margins, fluxes, sensitivity)
    max_abs = max(record.reconstructed_raw_max_abs_error for record in fluxes)
    max_rel = max(record.reconstructed_raw_max_relative_error for record in fluxes)

    generated: tuple[str, ...] = ()
    if generate_plots and plot_output_dir is not None:
        destination = Path(plot_output_dir)
        destination.mkdir(parents=True, exist_ok=True)
        generated = _generate_plots(
            destination,
            local_states=local_states,
            margins=margins,
            fluxes=fluxes,
            perturbations=perturbations,
        )

    return HEM4MPaForensicResult(
        baseline_summary={
            key: list(value) if isinstance(value, tuple) else value
            for key, value in EXPECTED_BASELINE.items()
        },
        local_states=local_states,
        saturation_margins=margins,
        isentropic_reference=isentropic,
        flux_decomposition=fluxes,
        perturbations=perturbations,
        perturbation_sensitivity=sensitivity,
        diagnostic_categories=categories,
        diagnostic_rationale=rationale,
        reconstruction_max_abs_error=max_abs,
        reconstruction_max_relative_error=max_rel,
        generated_plots=generated,
    )


def write_fixed_4mpa_forensic_artifacts(
    output_dir: str | Path,
    result: HEM4MPaForensicResult | None = None,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    diagnostic = result or run_fixed_4mpa_forensic_diagnostic(
        generate_plots=True,
        plot_output_dir=target,
    )
    if result is not None and not diagnostic.generated_plots:
        generated = _generate_plots(
            target,
            local_states=diagnostic.local_states,
            margins=diagnostic.saturation_margins,
            fluxes=diagnostic.flux_decomposition,
            perturbations=diagnostic.perturbations,
        )
        diagnostic = HEM4MPaForensicResult(
            baseline_summary=diagnostic.baseline_summary,
            local_states=diagnostic.local_states,
            saturation_margins=diagnostic.saturation_margins,
            isentropic_reference=diagnostic.isentropic_reference,
            flux_decomposition=diagnostic.flux_decomposition,
            perturbations=diagnostic.perturbations,
            perturbation_sensitivity=diagnostic.perturbation_sensitivity,
            diagnostic_categories=diagnostic.diagnostic_categories,
            diagnostic_rationale=diagnostic.diagnostic_rationale,
            reconstruction_max_abs_error=diagnostic.reconstruction_max_abs_error,
            reconstruction_max_relative_error=diagnostic.reconstruction_max_relative_error,
            generated_plots=generated,
        )

    paths = {
        "summary_json": target / "4mpa_forensic_summary.json",
        "local_history_csv": target / "4mpa_local_cell_history.csv",
        "saturation_margin_csv": target / "4mpa_saturation_margin.csv",
        "isentropic_json": target / "4mpa_isentropic_reference.json",
        "flux_csv": target / "4mpa_flux_decomposition.csv",
        "perturbation_csv": target / "4mpa_property_perturbation.csv",
        "perturbation_npz": target / "4mpa_property_perturbation.npz",
        "markdown": target / "4mpa_forensic_evidence.md",
    }
    payload = {
        **diagnostic.summary(),
        "isentropic_reference": asdict(diagnostic.isentropic_reference),
    }
    paths["summary_json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths["isentropic_json"].write_text(
        json.dumps(asdict(diagnostic.isentropic_reference), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        paths["local_history_csv"],
        [asdict(record) for record in diagnostic.local_states],
    )
    _write_csv(
        paths["saturation_margin_csv"],
        [asdict(record) for record in diagnostic.saturation_margins],
    )
    _write_csv(
        paths["flux_csv"],
        [asdict(record) for record in diagnostic.flux_decomposition],
    )
    _write_csv(
        paths["perturbation_csv"],
        [asdict(record) for record in diagnostic.perturbations],
    )
    np.savez_compressed(
        paths["perturbation_npz"],
        delta_rho_relative=np.asarray(
            [record.delta_rho_relative for record in diagnostic.perturbations],
            dtype=float,
        ),
        delta_e_relative=np.asarray(
            [record.delta_e_relative for record in diagnostic.perturbations],
            dtype=float,
        ),
        q_equilibrium=np.asarray(
            [
                np.nan if record.q_equilibrium is None else record.q_equilibrium
                for record in diagnostic.perturbations
            ],
            dtype=float,
        ),
        delta_u_sat_j_kg=np.asarray(
            [
                np.nan if record.delta_u_sat_j_kg is None else record.delta_u_sat_j_kg
                for record in diagnostic.perturbations
            ],
            dtype=float,
        ),
        delta_v_sat_m3_kg=np.asarray(
            [
                np.nan if record.delta_v_sat_m3_kg is None else record.delta_v_sat_m3_kg
                for record in diagnostic.perturbations
            ],
            dtype=float,
        ),
        boundary_region=np.asarray(
            [record.boundary_region for record in diagnostic.perturbations],
            dtype="<U40",
        ),
    )
    lines = [
        "# Stage 7 Fixed 4 MPa Subthreshold-Crossing Forensics",
        "",
        "`VERIFICATION-ONLY DIAGNOSTIC; PR #77 OBSERVATION UNCHANGED; GATE P2 FALSE`",
        "",
        f"- baseline reproduced exactly: true",
        f"- perturbation sensitivity: {diagnostic.perturbation_sensitivity}",
        f"- diagnostic categories: {list(diagnostic.diagnostic_categories)}",
        f"- flux reconstruction maximum absolute error: {diagnostic.reconstruction_max_abs_error:.17g}",
        f"- flux reconstruction maximum relative error: {diagnostic.reconstruction_max_relative_error:.17g}",
        f"- selected local-state records: {len(diagnostic.local_states)}",
        f"- saturation-margin records: {len(diagnostic.saturation_margins)}",
        f"- flux-decomposition records: {len(diagnostic.flux_decomposition)}",
        f"- perturbation records: {len(diagnostic.perturbations)}",
        "",
        "## Rationale",
        "",
    ]
    for category in diagnostic.diagnostic_categories:
        lines.append(
            f"- **{category}**: "
            f"{diagnostic.diagnostic_rationale.get(category, '')}"
        )
    lines.extend(
        [
            "",
            "## Approval boundary",
            "",
            "```text",
            "physical_validation = false",
            "design_use_acceptance = false",
            "production_hem_activation_approved = false",
            "Gate_P2_passed = false",
            "```",
        ]
    )
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    for filename in diagnostic.generated_plots:
        paths[f"plot_{Path(filename).stem}"] = target / filename
    return paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run fixed Stage 7 4 MPa subthreshold-crossing diagnostics."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run_fixed_4mpa_forensic_diagnostic(
        generate_plots=True,
        plot_output_dir=args.output_dir,
    )
    paths = write_fixed_4mpa_forensic_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
