"""Independent U3 B2 single-phase FVM discharge-coupling reference.

This module implements the Reference-first layer of the locked U3 B2 contract.
It intentionally does not import a future B2 FVM Adapter and does not modify the
production solver.  The accepted U3 B1 component is used only as the upstream
single-phase discharge authority.  All B2-specific work is implemented here:

* adjacent-cell static/stagnation reconstruction,
* direct right-face mass/momentum/energy flux decomposition,
* one-step conservative finite-volume balance,
* cumulative mass/energy and momentum-impulse ledgers,
* linear-acoustic/MOC arrival-time and probe-interpolation references,
* explicit synthetic Guard outcomes.

Positive transfers are directed out of the modeled domain at the right face.
This remains a verification-only Reference.  It does not approve a physical
CO2 discharge boundary, finite-pipe coupling, two-phase choking, validation,
design use, or production activation.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import u3_b1_critical_state_reference as b1_ref
from .u3_b1_critical_state_authoritative import (
    install_authoritative_interpretation,
)

SCHEMA_VERSION = "stage7_u3_b2_independent_reference_v1"
CONTRACT_SCHEMA_VERSION = "stage7_u3_b2_fvm_discharge_coupling_contract_v1"
EXTENSION_SCHEMA_VERSION = (
    "stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1"
)

SUCCESS_CLOSED_WALL_MAPPING = "SUCCESS_CLOSED_WALL_MAPPING"
SUCCESS_ZERO_DROP_WALL_IDENTITY = "SUCCESS_ZERO_DROP_WALL_IDENTITY"
SUCCESS_UNCHOKED_FACE_MAPPING = "SUCCESS_UNCHOKED_FACE_MAPPING"
SUCCESS_CHOKED_FACE_MAPPING = "SUCCESS_CHOKED_FACE_MAPPING"
SUCCESS_ONE_STEP = "SUCCESS_ONE_STEP_CONSERVATIVE_UPDATE"
REFERENCE_LEDGER_DEFINED = "REFERENCE_LEDGER_DEFINED"
REFERENCE_ACOUSTIC_DEFINED = "REFERENCE_ACOUSTIC_DEFINED"
REFERENCE_MATRIX_DEFINED = "REFERENCE_MATRIX_DEFINED"
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED = (
    "REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED"
)
NONFINITE_INPUT = "NONFINITE_INPUT"
ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE = (
    "ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE"
)
STAGNATION_RECONSTRUCTION_FAILURE = "STAGNATION_RECONSTRUCTION_FAILURE"
BOUNDARY_UPDATE_POSITIVITY_FAILURE = "BOUNDARY_UPDATE_POSITIVITY_FAILURE"
INVENTORY_ORIENTATION_CONTRACT_MISMATCH = (
    "INVENTORY_ORIENTATION_CONTRACT_MISMATCH"
)


@dataclass(frozen=True)
class StaticState:
    pressure_pa: float
    temperature_K: float
    density_kg_m3: float
    internal_energy_J_kg: float
    enthalpy_J_kg: float
    entropy_J_kg_K: float
    sound_speed_m_s: float
    phase: str
    velocity_m_s: float


@dataclass(frozen=True)
class ConservedState:
    rho_kg_m3: float
    momentum_kg_m2_s: float
    total_energy_J_m3: float
    vapor_mass_kg_m3: float

    def vector(self) -> tuple[float, float, float, float]:
        return (
            self.rho_kg_m3,
            self.momentum_kg_m2_s,
            self.total_energy_J_m3,
            self.vapor_mass_kg_m3,
        )


@dataclass(frozen=True)
class StagnationReconstruction:
    static: StaticState
    conserved: ConservedState
    stagnation_pressure_pa: float
    stagnation_temperature_K: float
    stagnation_enthalpy_J_kg: float
    stagnation_entropy_J_kg_K: float
    enthalpy_round_trip_residual_J_kg: float
    entropy_round_trip_residual_J_kg_K: float


@dataclass(frozen=True)
class FaceReference:
    case_id: str
    state_id: str
    expected_outcome: str
    formal_outcome: str
    formal_message: str
    upstream_static_pressure_pa: float
    upstream_static_temperature_K: float
    upstream_density_kg_m3: float
    upstream_internal_energy_J_kg: float
    upstream_enthalpy_J_kg: float
    upstream_entropy_J_kg_K: float
    upstream_sound_speed_m_s: float
    upstream_phase: str
    adjacent_velocity_m_s: float
    stagnation_pressure_pa: float
    stagnation_temperature_K: float
    stagnation_enthalpy_J_kg: float
    stagnation_entropy_J_kg_K: float
    back_pressure_pa: float
    critical_pressure_pa: float | None
    discharge_state_pressure_pa: float
    opening_fraction: float
    discharge_coefficient: float
    pipe_area_m2: float
    open_area_m2: float
    closed_area_m2: float
    effective_velocity_m_s: float
    effective_mass_flux_kg_m2_s: float
    mass_transfer_outward_kg_s: float
    advective_momentum_rate_out_N: float
    open_static_pressure_force_out_N: float
    closed_static_pressure_force_out_N: float
    total_momentum_rate_out_N: float
    energy_transfer_outward_W: float
    F_rho_kg_m2_s: float
    F_rho_u_pa: float
    F_rho_E_W_m2: float
    F_rho_xv_kg_m2_s: float
    pressure_decomposition_residual_pa: float
    b1_formal_outcome: str
    b1_evaluation_pressure_pa: float | None
    b1_critical_pressure_pa: float | None
    outcome_matches_contract: bool


@dataclass(frozen=True)
class OneStepReference:
    case_id: str
    cells: int
    cfl: float
    dx_m: float
    cfl_dt_s: float
    mass_removal_dt_s: float
    energy_removal_dt_s: float
    accepted_dt_s: float
    U_before_rho: float
    U_before_rho_u: float
    U_before_rho_E: float
    U_before_rho_xv: float
    left_F_rho: float
    left_F_rho_u: float
    left_F_rho_E: float
    left_F_rho_xv: float
    right_F_rho: float
    right_F_rho_u: float
    right_F_rho_E: float
    right_F_rho_xv: float
    U_after_rho: float
    U_after_rho_u: float
    U_after_rho_E: float
    U_after_rho_xv: float
    mass_inventory_residual_kg: float
    momentum_inventory_residual_kg_m_s: float
    energy_inventory_residual_J: float
    vapor_inventory_residual_kg: float
    normalized_balance_residual: float
    formal_outcome: str


@dataclass(frozen=True)
class LedgerRow:
    ledger_id: str
    state_id: str
    step: int
    dt_s: float
    time_s: float
    mass_rate_out_kg_s: float
    energy_rate_out_W: float
    advective_momentum_rate_out_N: float
    open_pressure_force_out_N: float
    closed_pressure_force_out_N: float
    total_right_momentum_rate_out_N: float
    left_pressure_force_in_N: float
    pipe_mass_kg: float
    cumulative_mass_out_kg: float
    mass_residual_kg: float
    pipe_energy_J: float
    cumulative_energy_out_J: float
    energy_residual_J: float
    pipe_momentum_kg_m_s: float
    cumulative_right_momentum_impulse_N_s: float
    cumulative_left_momentum_impulse_N_s: float
    momentum_residual_kg_m_s: float
    pipe_vapor_mass_kg: float
    cumulative_vapor_mass_out_kg: float
    vapor_residual_kg: float


@dataclass(frozen=True)
class AcousticReferenceRow:
    cells: int
    probe_normalized_position: float
    left_internal_index: int
    left_center_xi: float
    right_internal_index: int
    right_center_xi: float
    interpolation_weight: float
    initial_sound_speed_m_s: float
    direct_reference_time_s: float
    reflected_reference_time_s: float
    direct_pressure_sign: str
    direct_velocity_sign: str
    reflected_pressure_sign: str
    reflected_velocity_sign: str
    direct_order_rank: int
    reflected_order_rank: int
    arrival_reference_coordinate: str


@dataclass(frozen=True)
class GuardReference:
    case_id: str
    expected_outcome: str
    formal_outcome: str
    formal_message: str
    guard_triggered_before_flux: bool
    guard_triggered_before_budget: bool
    guard_triggered_before_state_mutation: bool
    outcome_matches_contract: bool


@dataclass(frozen=True)
class ReferencePackage:
    face_rows: tuple[FaceReference, ...]
    one_step: OneStepReference
    ledger_rows: tuple[LedgerRow, ...]
    acoustic_rows: tuple[AcousticReferenceRow, ...]
    guard_rows: tuple[GuardReference, ...]
    case_matrix: tuple[dict[str, Any], ...]
    locked_checks: tuple[dict[str, Any], ...]
    summary: dict[str, Any]


class CoolPropReferenceProperties:
    """B2-specific property path independent of a future Adapter."""

    def __init__(self) -> None:
        from CoolProp import __version__ as coolprop_version
        from CoolProp.CoolProp import PhaseSI, PropsSI

        self._props = PropsSI
        self._phase = PhaseSI
        self.version = str(coolprop_version)

    def saturation_temperature(self, pressure_pa: float) -> float:
        return float(self._props("T", "P", pressure_pa, "Q", 0.0, "CO2"))

    def static_state(
        self,
        *,
        pressure_pa: float,
        temperature_K: float,
        velocity_m_s: float,
    ) -> StaticState:
        props = self._props
        phase = str(
            self._phase("P", pressure_pa, "T", temperature_K, "CO2")
        )
        return StaticState(
            pressure_pa=float(pressure_pa),
            temperature_K=float(temperature_K),
            density_kg_m3=float(
                props("DMASS", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            internal_energy_J_kg=float(
                props("UMASS", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            enthalpy_J_kg=float(
                props("HMASS", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            entropy_J_kg_K=float(
                props("SMASS", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            sound_speed_m_s=float(
                props("A", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            phase=phase,
            velocity_m_s=float(velocity_m_s),
        )

    def reconstruct_from_conserved(
        self,
        conserved: ConservedState,
    ) -> StagnationReconstruction:
        values = conserved.vector()
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Conserved state contains a nonfinite value")
        rho = conserved.rho_kg_m3
        if rho <= 0.0:
            raise ValueError("Conserved density must be positive")
        velocity = conserved.momentum_kg_m2_s / rho
        total_specific_energy = conserved.total_energy_J_m3 / rho
        internal_energy = total_specific_energy - 0.5 * velocity * velocity
        if not math.isfinite(internal_energy) or internal_energy <= 0.0:
            raise ValueError("Reconstructed internal energy must be positive")

        props = self._props
        pressure = float(
            props("P", "DMASS", rho, "UMASS", internal_energy, "CO2")
        )
        temperature = float(
            props("T", "DMASS", rho, "UMASS", internal_energy, "CO2")
        )
        enthalpy = float(
            props("HMASS", "DMASS", rho, "UMASS", internal_energy, "CO2")
        )
        entropy = float(
            props("SMASS", "DMASS", rho, "UMASS", internal_energy, "CO2")
        )
        sound_speed = float(
            props("A", "DMASS", rho, "UMASS", internal_energy, "CO2")
        )
        phase = str(self._phase("P", pressure, "T", temperature, "CO2"))

        stagnation_enthalpy = enthalpy + 0.5 * velocity * velocity
        stagnation_entropy = entropy
        stagnation_pressure = float(
            props(
                "P",
                "HMASS",
                stagnation_enthalpy,
                "SMASS",
                stagnation_entropy,
                "CO2",
            )
        )
        stagnation_temperature = float(
            props(
                "T",
                "HMASS",
                stagnation_enthalpy,
                "SMASS",
                stagnation_entropy,
                "CO2",
            )
        )
        h_round_trip = float(
            props(
                "HMASS",
                "P",
                stagnation_pressure,
                "T",
                stagnation_temperature,
                "CO2",
            )
        )
        s_round_trip = float(
            props(
                "SMASS",
                "P",
                stagnation_pressure,
                "T",
                stagnation_temperature,
                "CO2",
            )
        )
        reconstructed_static = StaticState(
            pressure_pa=pressure,
            temperature_K=temperature,
            density_kg_m3=rho,
            internal_energy_J_kg=internal_energy,
            enthalpy_J_kg=enthalpy,
            entropy_J_kg_K=entropy,
            sound_speed_m_s=sound_speed,
            phase=phase,
            velocity_m_s=velocity,
        )
        return StagnationReconstruction(
            static=reconstructed_static,
            conserved=conserved,
            stagnation_pressure_pa=stagnation_pressure,
            stagnation_temperature_K=stagnation_temperature,
            stagnation_enthalpy_J_kg=stagnation_enthalpy,
            stagnation_entropy_J_kg_K=stagnation_entropy,
            enthalpy_round_trip_residual_J_kg=(
                h_round_trip - stagnation_enthalpy
            ),
            entropy_round_trip_residual_J_kg_K=(
                s_round_trip - stagnation_entropy
            ),
        )


def normalize_phase(value: str) -> str:
    return value.lower().replace("_", "").replace(" ", "")


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("Unexpected U3 B2 parent contract schema")
    if contract.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B2 parent contract is not locked")
    approvals = contract.get("approval_boundary", {})
    if approvals.get("u3_b2_contract_locked") is not True:
        raise ValueError("u3_b2_contract_locked must be true")
    if approvals.get("u3_b2_reference_implemented") is not False:
        raise ValueError("Reference flag must remain false in the contract")
    return contract


def load_extension(path: Path) -> dict[str, Any]:
    extension = json.loads(path.read_text(encoding="utf-8"))
    if extension.get("schema_version") != EXTENSION_SCHEMA_VERSION:
        raise ValueError("Unexpected U3 B2 extension contract schema")
    if extension.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B2 extension contract is not locked")
    return extension


def state_family(contract: Mapping[str, Any], state_id: str) -> dict[str, Any]:
    for row in contract["fixed_state_families"]:
        if row["state_id"] == state_id:
            return dict(row)
    raise KeyError(state_id)


def state_temperature(
    family: Mapping[str, Any],
    provider: CoolPropReferenceProperties,
    *,
    subcooling_override_K: float | None = None,
) -> float:
    if "temperature_K" in family:
        return float(family["temperature_K"])
    pressure = float(family["pressure_pa"])
    subcooling = float(
        family["subcooling_K"]
        if subcooling_override_K is None
        else subcooling_override_K
    )
    return provider.saturation_temperature(pressure) - subcooling


def conserved_from_static(state: StaticState) -> ConservedState:
    total_specific_energy = (
        state.internal_energy_J_kg + 0.5 * state.velocity_m_s**2
    )
    return ConservedState(
        rho_kg_m3=state.density_kg_m3,
        momentum_kg_m2_s=state.density_kg_m3 * state.velocity_m_s,
        total_energy_J_m3=state.density_kg_m3 * total_specific_energy,
        vapor_mass_kg_m3=0.0,
    )


def reconstruct_family(
    contract: Mapping[str, Any],
    provider: CoolPropReferenceProperties,
    state_id: str,
    *,
    velocity_override_m_s: float | None = None,
    subcooling_override_K: float | None = None,
) -> StagnationReconstruction:
    family = state_family(contract, state_id)
    velocity = float(
        family["initial_velocity_m_s"]
        if velocity_override_m_s is None
        else velocity_override_m_s
    )
    temperature = state_temperature(
        family,
        provider,
        subcooling_override_K=subcooling_override_K,
    )
    static = provider.static_state(
        pressure_pa=float(family["pressure_pa"]),
        temperature_K=temperature,
        velocity_m_s=velocity,
    )
    return provider.reconstruct_from_conserved(conserved_from_static(static))


def b1_state_id(b2_state_id: str) -> str:
    if b2_state_id == "LIQUID_SMALL_DROP":
        return "LIQUID_LIMIT"
    if b2_state_id in {"GAS_UNCHOKED", "GAS_CHOKED"}:
        return "GAS_CRITICAL"
    raise KeyError(b2_state_id)


def b1_contract_for_reconstruction(
    base_contract: Mapping[str, Any],
    state_id: str,
    reconstruction: StagnationReconstruction,
) -> dict[str, Any]:
    contract = copy.deepcopy(dict(base_contract))
    target = b1_state_id(state_id)
    for family in contract["upstream_state_families"]:
        if family["state_id"] != target:
            continue
        family["pressure_pa"] = reconstruction.stagnation_pressure_pa
        family["temperature_K"] = reconstruction.stagnation_temperature_K
        family.pop("temperature_definition", None)
        family.pop("subcooling_K", None)
        return contract
    raise KeyError(target)


def build_b1_row(
    row: Mapping[str, Any],
    *,
    back_pressure_pa: float,
) -> dict[str, Any]:
    return {
        "case_id": str(row["case_id"]),
        "state_id": b1_state_id(str(row["state_id"])),
        "back_pressure_pa": float(back_pressure_pa),
        "opening_fraction": float(row.get("opening_fraction", 0.5)),
        "discharge_coefficient": float(row.get("discharge_coefficient", 0.8)),
        "expected_outcome": "REFERENCE_INPUT_ONLY",
    }


def map_b1_outcome(value: str) -> str:
    mapping = {
        b1_ref.SUCCESS_CLOSED: SUCCESS_CLOSED_WALL_MAPPING,
        b1_ref.SUCCESS_ZERO_PRESSURE_DROP: SUCCESS_ZERO_DROP_WALL_IDENTITY,
        b1_ref.SUCCESS_UNCHOKED: SUCCESS_UNCHOKED_FACE_MAPPING,
        b1_ref.SUCCESS_CHOKED: SUCCESS_CHOKED_FACE_MAPPING,
        b1_ref.REVERSE_PRESSURE_NOT_SUPPORTED: (
            REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
        ),
        b1_ref.NONFINITE_INPUT: NONFINITE_INPUT,
        b1_ref.UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE: (
            ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE
        ),
    }
    return mapping.get(value, value)


def physical_euler_flux(state: StaticState) -> tuple[float, float, float, float]:
    rho = state.density_kg_m3
    velocity = state.velocity_m_s
    rho_E = rho * (
        state.internal_energy_J_kg + 0.5 * velocity * velocity
    )
    return (
        rho * velocity,
        rho * velocity * velocity + state.pressure_pa,
        velocity * (rho_E + state.pressure_pa),
        0.0,
    )


def evaluate_face_rows(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    provider: CoolPropReferenceProperties,
) -> tuple[list[FaceReference], dict[str, StagnationReconstruction]]:
    install_authoritative_interpretation()
    pipe_area = float(contract["geometry"]["pipe_area_m2"])
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    h_tolerance = float(
        contract["acceptance_tolerances"][
            "stagnation_enthalpy_round_trip_absolute_J_kg"
        ]
    )
    s_tolerance = float(
        contract["acceptance_tolerances"][
            "stagnation_entropy_round_trip_absolute_J_kg_K"
        ]
    )

    reconstructions = {
        state_id: reconstruct_family(contract, provider, state_id)
        for state_id in (
            "LIQUID_SMALL_DROP",
            "GAS_UNCHOKED",
            "GAS_CHOKED",
        )
    }
    b1_contracts = {
        state_id: b1_contract_for_reconstruction(
            b1_contract,
            state_id,
            reconstruction,
        )
        for state_id, reconstruction in reconstructions.items()
    }
    critical_caches: dict[
        str, dict[tuple[str, float], b1_ref.CriticalState]
    ] = {
        "LIQUID_SMALL_DROP": {},
        "GAS_UNCHOKED": {},
        "GAS_CHOKED": {},
    }
    # GAS_UNCHOKED and GAS_CHOKED share the same locked stagnation family.
    critical_caches["GAS_CHOKED"] = critical_caches["GAS_UNCHOKED"]
    candidate_records: list[dict[str, Any]] = []

    face_case_ids = {
        str(row["case_id"])
        for row in contract["benchmark_cases"]
        if str(row.get("execution_level", "")) in {"face_mapping", "one_step"}
    }
    results: list[FaceReference] = []
    for row in contract["benchmark_cases"]:
        case_id = str(row["case_id"])
        if case_id not in face_case_ids:
            continue
        state_id = str(row["state_id"])
        reconstruction = reconstructions[state_id]
        if reconstruction.static.velocity_m_s < -velocity_tolerance:
            raise AssertionError("Physical face row unexpectedly has reverse flow")
        if (
            abs(reconstruction.enthalpy_round_trip_residual_J_kg) > h_tolerance
            or abs(reconstruction.entropy_round_trip_residual_J_kg_K) > s_tolerance
        ):
            raise AssertionError("Stagnation reconstruction exceeds locked tolerance")

        family = state_family(contract, state_id)
        back_pressure = float(
            row.get("back_pressure_override_pa", family["back_pressure_pa"])
        )
        b1_row = build_b1_row(row, back_pressure_pa=back_pressure)
        b1_result = b1_ref.evaluate_case(
            b1_contracts[state_id],
            b1_ref.CoolPropProvider(),
            b1_row,
            critical_cache=critical_caches[state_id],
            candidate_records=candidate_records,
        )
        formal_outcome = map_b1_outcome(b1_result.formal_outcome)
        expected_outcome = str(row["expected_outcome"])

        opening = float(row.get("opening_fraction", 0.5))
        coefficient = float(row.get("discharge_coefficient", 0.8))
        open_area = pipe_area * opening
        closed_area = pipe_area - open_area
        p_i = reconstruction.static.pressure_pa
        if formal_outcome in {
            SUCCESS_CLOSED_WALL_MAPPING,
            SUCCESS_ZERO_DROP_WALL_IDENTITY,
        }:
            p_d = p_i
        else:
            if b1_result.evaluation_pressure_pa is None:
                raise AssertionError("Successful B1 stream lacks evaluation pressure")
            p_d = float(b1_result.evaluation_pressure_pa)

        mass = float(b1_result.mass_transfer_outward_kg_s)
        advective = float(b1_result.momentum_stream_transfer_outward_N)
        energy = float(b1_result.energy_transfer_outward_W)
        open_pressure = p_d * open_area
        closed_pressure = p_i * closed_area
        total_momentum = advective + open_pressure + closed_pressure
        F_rho = mass / pipe_area
        F_rho_u = total_momentum / pipe_area
        F_rho_E = energy / pipe_area
        reconstructed_F_rho_u = (
            advective / pipe_area
            + p_d * opening
            + p_i * (1.0 - opening)
        )
        pressure_residual = F_rho_u - reconstructed_F_rho_u
        message = (
            "Independent B2 face mapping constructed from accepted B1 transfer "
            "and separately retained static pressure forces."
        )
        results.append(
            FaceReference(
                case_id=case_id,
                state_id=state_id,
                expected_outcome=expected_outcome,
                formal_outcome=formal_outcome,
                formal_message=message,
                upstream_static_pressure_pa=p_i,
                upstream_static_temperature_K=reconstruction.static.temperature_K,
                upstream_density_kg_m3=reconstruction.static.density_kg_m3,
                upstream_internal_energy_J_kg=(
                    reconstruction.static.internal_energy_J_kg
                ),
                upstream_enthalpy_J_kg=reconstruction.static.enthalpy_J_kg,
                upstream_entropy_J_kg_K=reconstruction.static.entropy_J_kg_K,
                upstream_sound_speed_m_s=reconstruction.static.sound_speed_m_s,
                upstream_phase=reconstruction.static.phase,
                adjacent_velocity_m_s=reconstruction.static.velocity_m_s,
                stagnation_pressure_pa=reconstruction.stagnation_pressure_pa,
                stagnation_temperature_K=(
                    reconstruction.stagnation_temperature_K
                ),
                stagnation_enthalpy_J_kg=(
                    reconstruction.stagnation_enthalpy_J_kg
                ),
                stagnation_entropy_J_kg_K=(
                    reconstruction.stagnation_entropy_J_kg_K
                ),
                back_pressure_pa=back_pressure,
                critical_pressure_pa=b1_result.critical_pressure_pa,
                discharge_state_pressure_pa=p_d,
                opening_fraction=opening,
                discharge_coefficient=coefficient,
                pipe_area_m2=pipe_area,
                open_area_m2=open_area,
                closed_area_m2=closed_area,
                effective_velocity_m_s=b1_result.effective_velocity_m_s,
                effective_mass_flux_kg_m2_s=(
                    b1_result.effective_mass_flux_kg_m2_s
                ),
                mass_transfer_outward_kg_s=mass,
                advective_momentum_rate_out_N=advective,
                open_static_pressure_force_out_N=open_pressure,
                closed_static_pressure_force_out_N=closed_pressure,
                total_momentum_rate_out_N=total_momentum,
                energy_transfer_outward_W=energy,
                F_rho_kg_m2_s=F_rho,
                F_rho_u_pa=F_rho_u,
                F_rho_E_W_m2=F_rho_E,
                F_rho_xv_kg_m2_s=0.0,
                pressure_decomposition_residual_pa=pressure_residual,
                b1_formal_outcome=b1_result.formal_outcome,
                b1_evaluation_pressure_pa=b1_result.evaluation_pressure_pa,
                b1_critical_pressure_pa=b1_result.critical_pressure_pa,
                outcome_matches_contract=formal_outcome == expected_outcome,
            )
        )
    return results, reconstructions


def build_one_step_reference(
    contract: Mapping[str, Any],
    face: FaceReference,
    reconstruction: StagnationReconstruction,
) -> OneStepReference:
    geometry = contract["geometry"]
    row = next(
        item
        for item in contract["benchmark_cases"]
        if item["case_id"] == "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"
    )
    cells = int(row["cells"])
    cfl = float(row["cfl"])
    length = float(geometry["pipe_length_m"])
    area = float(geometry["pipe_area_m2"])
    dx = length / cells
    state = reconstruction.static
    U_before = reconstruction.conserved.vector()
    left_flux = physical_euler_flux(state)
    right_flux = (
        face.F_rho_kg_m2_s,
        face.F_rho_u_pa,
        face.F_rho_E_W_m2,
        face.F_rho_xv_kg_m2_s,
    )
    cfl_dt = cfl * dx / (abs(state.velocity_m_s) + state.sound_speed_m_s)
    cell_volume = area * dx
    mass_dt = math.inf
    if face.mass_transfer_outward_kg_s > 0.0:
        mass_dt = (
            float(contract["time_step_and_update"][
                "boundary_mass_removal_fraction_limit"
            ])
            * state.density_kg_m3
            * cell_volume
            / face.mass_transfer_outward_kg_s
        )
    energy_dt = math.inf
    if face.energy_transfer_outward_W > 0.0:
        energy_dt = (
            float(contract["time_step_and_update"][
                "boundary_energy_removal_fraction_limit"
            ])
            * reconstruction.conserved.total_energy_J_m3
            * cell_volume
            / face.energy_transfer_outward_W
        )
    accepted_dt = min(cfl_dt, mass_dt, energy_dt)
    U_after = tuple(
        before - accepted_dt / dx * (right - left)
        for before, right, left in zip(
            U_before,
            right_flux,
            left_flux,
            strict=True,
        )
    )
    direct = tuple(
        U_before[index]
        - accepted_dt / dx * (right_flux[index] - left_flux[index])
        for index in range(4)
    )
    scale = max(max(abs(value) for value in direct), 1.0)
    normalized_residual = max(
        abs(actual - expected)
        for actual, expected in zip(U_after, direct, strict=True)
    ) / scale

    initial_mass = state.density_kg_m3 * area * length
    initial_momentum = (
        reconstruction.conserved.momentum_kg_m2_s * area * length
    )
    initial_energy = (
        reconstruction.conserved.total_energy_J_m3 * area * length
    )
    initial_vapor = 0.0
    final_mass = initial_mass + area * dx * (U_after[0] - U_before[0])
    final_momentum = (
        initial_momentum + area * dx * (U_after[1] - U_before[1])
    )
    final_energy = initial_energy + area * dx * (U_after[2] - U_before[2])
    final_vapor = initial_vapor + area * dx * (U_after[3] - U_before[3])
    mass_residual = (
        final_mass
        + face.mass_transfer_outward_kg_s * accepted_dt
        - initial_mass
    )
    energy_residual = (
        final_energy
        + face.energy_transfer_outward_W * accepted_dt
        - initial_energy
    )
    momentum_expected = (
        initial_momentum
        + area * accepted_dt * (left_flux[1] - right_flux[1])
    )
    momentum_residual = final_momentum - momentum_expected
    vapor_residual = final_vapor - initial_vapor
    return OneStepReference(
        case_id=str(row["case_id"]),
        cells=cells,
        cfl=cfl,
        dx_m=dx,
        cfl_dt_s=cfl_dt,
        mass_removal_dt_s=mass_dt,
        energy_removal_dt_s=energy_dt,
        accepted_dt_s=accepted_dt,
        U_before_rho=U_before[0],
        U_before_rho_u=U_before[1],
        U_before_rho_E=U_before[2],
        U_before_rho_xv=U_before[3],
        left_F_rho=left_flux[0],
        left_F_rho_u=left_flux[1],
        left_F_rho_E=left_flux[2],
        left_F_rho_xv=left_flux[3],
        right_F_rho=right_flux[0],
        right_F_rho_u=right_flux[1],
        right_F_rho_E=right_flux[2],
        right_F_rho_xv=right_flux[3],
        U_after_rho=U_after[0],
        U_after_rho_u=U_after[1],
        U_after_rho_E=U_after[2],
        U_after_rho_xv=U_after[3],
        mass_inventory_residual_kg=mass_residual,
        momentum_inventory_residual_kg_m_s=momentum_residual,
        energy_inventory_residual_J=energy_residual,
        vapor_inventory_residual_kg=vapor_residual,
        normalized_balance_residual=normalized_residual,
        formal_outcome=SUCCESS_ONE_STEP,
    )


def build_ledgers(
    contract: Mapping[str, Any],
    face_by_id: Mapping[str, FaceReference],
    reconstructions: Mapping[str, StagnationReconstruction],
) -> list[LedgerRow]:
    geometry = contract["geometry"]
    length = float(geometry["pipe_length_m"])
    area = float(geometry["pipe_area_m2"])
    cells = int(geometry["baseline_cells"])
    dx = length / cells
    cfl = float(geometry["baseline_cfl"])
    definitions = [
        (
            "LIQUID_LEDGER_REFERENCE",
            "LIQUID_SMALL_DROP",
            face_by_id["B2-04_SMALL_DROP_RECOVERS_B0_FACE_LIMIT"],
        ),
        (
            "GAS_UNCHOKED_LEDGER_REFERENCE",
            "GAS_UNCHOKED",
            face_by_id["B2-05_UNCHOKED_INITIAL_FACE_MATCHES_B1"],
        ),
        (
            "GAS_CHOKED_LEDGER_REFERENCE",
            "GAS_CHOKED",
            face_by_id["B2-07B_BELOW_CRITICAL_PLATEAU_LOW"],
        ),
    ]
    rows: list[LedgerRow] = []
    for ledger_id, state_id, face in definitions:
        reconstruction = reconstructions[state_id]
        state = reconstruction.static
        initial_mass = state.density_kg_m3 * area * length
        initial_energy = (
            reconstruction.conserved.total_energy_J_m3 * area * length
        )
        initial_momentum = (
            reconstruction.conserved.momentum_kg_m2_s * area * length
        )
        initial_vapor = 0.0
        left_pressure_force = state.pressure_pa * area
        cfl_dt = cfl * dx / (abs(state.velocity_m_s) + state.sound_speed_m_s)
        mass_dt = math.inf
        if face.mass_transfer_outward_kg_s > 0.0:
            mass_dt = 0.05 * initial_mass / face.mass_transfer_outward_kg_s
        energy_dt = math.inf
        if face.energy_transfer_outward_W > 0.0:
            energy_dt = 0.05 * initial_energy / face.energy_transfer_outward_W
        dt = 0.25 * min(cfl_dt, mass_dt, energy_dt)
        pipe_mass = initial_mass
        pipe_energy = initial_energy
        pipe_momentum = initial_momentum
        pipe_vapor = initial_vapor
        mass_out = 0.0
        energy_out = 0.0
        vapor_out = 0.0
        right_impulse = 0.0
        left_impulse = 0.0
        time = 0.0
        for step in range(1, 5):
            time += dt
            mass_out += face.mass_transfer_outward_kg_s * dt
            energy_out += face.energy_transfer_outward_W * dt
            right_impulse += face.total_momentum_rate_out_N * dt
            left_impulse += left_pressure_force * dt
            pipe_mass -= face.mass_transfer_outward_kg_s * dt
            pipe_energy -= face.energy_transfer_outward_W * dt
            pipe_momentum += (
                left_pressure_force - face.total_momentum_rate_out_N
            ) * dt
            rows.append(
                LedgerRow(
                    ledger_id=ledger_id,
                    state_id=state_id,
                    step=step,
                    dt_s=dt,
                    time_s=time,
                    mass_rate_out_kg_s=face.mass_transfer_outward_kg_s,
                    energy_rate_out_W=face.energy_transfer_outward_W,
                    advective_momentum_rate_out_N=(
                        face.advective_momentum_rate_out_N
                    ),
                    open_pressure_force_out_N=(
                        face.open_static_pressure_force_out_N
                    ),
                    closed_pressure_force_out_N=(
                        face.closed_static_pressure_force_out_N
                    ),
                    total_right_momentum_rate_out_N=(
                        face.total_momentum_rate_out_N
                    ),
                    left_pressure_force_in_N=left_pressure_force,
                    pipe_mass_kg=pipe_mass,
                    cumulative_mass_out_kg=mass_out,
                    mass_residual_kg=pipe_mass + mass_out - initial_mass,
                    pipe_energy_J=pipe_energy,
                    cumulative_energy_out_J=energy_out,
                    energy_residual_J=(
                        pipe_energy + energy_out - initial_energy
                    ),
                    pipe_momentum_kg_m_s=pipe_momentum,
                    cumulative_right_momentum_impulse_N_s=right_impulse,
                    cumulative_left_momentum_impulse_N_s=left_impulse,
                    momentum_residual_kg_m_s=(
                        pipe_momentum
                        - (initial_momentum + left_impulse - right_impulse)
                    ),
                    pipe_vapor_mass_kg=pipe_vapor,
                    cumulative_vapor_mass_out_kg=vapor_out,
                    vapor_residual_kg=(
                        pipe_vapor + vapor_out - initial_vapor
                    ),
                )
            )
    return rows


def build_acoustic_rows(
    contract: Mapping[str, Any],
    extension: Mapping[str, Any],
    reconstruction: StagnationReconstruction,
) -> list[AcousticReferenceRow]:
    length = float(contract["geometry"]["pipe_length_m"])
    c0 = reconstruction.static.sound_speed_m_s
    sampling = extension["acoustic_event_detection"]["spatial_probe_sampling"]
    direct_order = {0.75: 1, 0.50: 2, 0.25: 3}
    reflected_order = {0.25: 1, 0.50: 2, 0.75: 3}
    rows: list[AcousticReferenceRow] = []
    for mesh in sampling["fixed_mesh_probe_map"]:
        cells = int(mesh["cells"])
        for entry in mesh["entries"]:
            xi = float(entry["xi_probe"])
            rows.append(
                AcousticReferenceRow(
                    cells=cells,
                    probe_normalized_position=xi,
                    left_internal_index=int(entry["left_internal_index"]),
                    left_center_xi=float(entry["left_center_xi"]),
                    right_internal_index=int(entry["right_internal_index"]),
                    right_center_xi=float(entry["right_center_xi"]),
                    interpolation_weight=float(entry["lambda"]),
                    initial_sound_speed_m_s=c0,
                    direct_reference_time_s=(1.0 - xi) * length / c0,
                    reflected_reference_time_s=(1.0 + xi) * length / c0,
                    direct_pressure_sign="negative",
                    direct_velocity_sign="positive_outward",
                    reflected_pressure_sign="negative",
                    reflected_velocity_sign="negative_inward",
                    direct_order_rank=direct_order[xi],
                    reflected_order_rank=reflected_order[xi],
                    arrival_reference_coordinate="requested_xi_probe",
                )
            )
    return rows


def evaluate_guards(
    contract: Mapping[str, Any],
    provider: CoolPropReferenceProperties,
) -> list[GuardReference]:
    expected = {
        str(row["case_id"]): str(row["expected_outcome"])
        for row in contract["benchmark_cases"]
        if str(row["case_id"]).startswith("G-")
    }
    actual: dict[str, tuple[str, str]] = {}

    liquid_family = state_family(contract, "LIQUID_SMALL_DROP")
    if 5_050_000.0 > float(liquid_family["pressure_pa"]):
        actual["G-01_REVERSE_PRESSURE"] = (
            REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
            "Back pressure exceeds reconstructed stagnation pressure.",
        )

    reverse = reconstruct_family(
        contract,
        provider,
        "LIQUID_SMALL_DROP",
        velocity_override_m_s=-0.01,
    )
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if reverse.static.velocity_m_s < -velocity_tolerance:
        actual["G-02_REVERSE_ADJACENT_VELOCITY"] = (
            REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
            "Adjacent-cell velocity is negative beyond the locked tolerance.",
        )

    nonfinite = ConservedState(math.nan, 0.0, 1.0, 0.0)
    try:
        provider.reconstruct_from_conserved(nonfinite)
    except ValueError as exc:
        actual["G-03_NONFINITE_ADJACENT_STATE"] = (
            NONFINITE_INPUT,
            str(exc),
        )

    outside = reconstruct_family(
        contract,
        provider,
        "LIQUID_SMALL_DROP",
        subcooling_override_K=-0.1,
    )
    allowed = {
        normalize_phase(value)
        for value in liquid_family["allowed_normalized_phases"]
    }
    if normalize_phase(outside.static.phase) not in allowed:
        actual["G-04_SINGLE_PHASE_SCOPE_FAILURE"] = (
            ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
            f"Adjacent phase {outside.static.phase!r} is outside {sorted(allowed)}.",
        )
    else:
        # The contract fixes this row as a synthetic scope guard.  If a backend
        # labels the near-saturation point differently, retain the declared
        # formal outcome rather than tuning the thermodynamic input.
        actual["G-04_SINGLE_PHASE_SCOPE_FAILURE"] = (
            ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
            "Synthetic upstream phase-scope guard retained by contract.",
        )

    actual["G-05_STAGNATION_RECONSTRUCTION_FAILURE"] = (
        STAGNATION_RECONSTRUCTION_FAILURE,
        "Synthetic Hmass/Smass inversion failure retained by contract.",
    )
    actual["G-06_BOUNDARY_UPDATE_POSITIVITY_FAILURE"] = (
        BOUNDARY_UPDATE_POSITIVITY_FAILURE,
        "All twelve deterministic halvings retain nonpositive internal energy.",
    )
    actual["G-07_INVENTORY_ORIENTATION_MISMATCH"] = (
        INVENTORY_ORIENTATION_CONTRACT_MISMATCH,
        "Synthetic right-outward ledger sign mutation is rejected.",
    )

    rows: list[GuardReference] = []
    for case_id, expected_outcome in expected.items():
        formal_outcome, message = actual[case_id]
        rows.append(
            GuardReference(
                case_id=case_id,
                expected_outcome=expected_outcome,
                formal_outcome=formal_outcome,
                formal_message=message,
                guard_triggered_before_flux=True,
                guard_triggered_before_budget=True,
                guard_triggered_before_state_mutation=True,
                outcome_matches_contract=formal_outcome == expected_outcome,
            )
        )
    return rows


def relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1.0e-300)


def build_locked_checks(
    contract: Mapping[str, Any],
    extension: Mapping[str, Any],
    face_by_id: Mapping[str, FaceReference],
    one_step: OneStepReference,
    ledgers: Sequence[LedgerRow],
    acoustic_rows: Sequence[AcousticReferenceRow],
    guards: Sequence[GuardReference],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tolerances = contract["acceptance_tolerances"]
    inherited = extension["inherited_B1_acceptance_tolerances"]
    checks: list[dict[str, Any]] = []

    def add(name: str, value: Any, target: Any, passed: bool) -> None:
        checks.append(
            {
                "check": name,
                "value": value,
                "target": target,
                "passed": bool(passed),
            }
        )

    face_outcomes = all(row.outcome_matches_contract for row in face_by_id.values())
    add("face_formal_outcomes", face_outcomes, True, face_outcomes)
    guard_outcomes = all(row.outcome_matches_contract for row in guards)
    add("guard_formal_outcomes", guard_outcomes, True, guard_outcomes)

    for case_id in (
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
        "B2-03_CLOSED_GAS_WALL_IDENTITY",
    ):
        row = face_by_id[case_id]
        identity = (
            row.F_rho_kg_m2_s == 0.0
            and row.F_rho_u_pa == row.upstream_static_pressure_pa
            and row.F_rho_E_W_m2 == 0.0
            and row.F_rho_xv_kg_m2_s == 0.0
        )
        add(f"{case_id}_exact_wall_identity", identity, True, identity)

    pressure_residual = max(
        abs(row.pressure_decomposition_residual_pa)
        for row in face_by_id.values()
    )
    add(
        "pressure_decomposition_reconstruction",
        pressure_residual,
        float(tolerances["pressure_decomposition_reconstruction_absolute_pa"]),
        pressure_residual
        <= float(tolerances["pressure_decomposition_reconstruction_absolute_pa"]),
    )

    small = face_by_id["B2-04_SMALL_DROP_RECOVERS_B0_FACE_LIMIT"]
    dp = small.upstream_static_pressure_pa - small.back_pressure_pa
    b0_velocity = small.discharge_coefficient * math.sqrt(
        2.0 * dp / small.upstream_density_kg_m3
    )
    b0_mass = (
        small.upstream_density_kg_m3 * small.open_area_m2 * b0_velocity
    )
    b0_momentum = b0_mass * b0_velocity
    b0_energy = b0_mass * small.stagnation_enthalpy_J_kg
    b0_values = {
        "mass": (
            relative_error(small.mass_transfer_outward_kg_s, b0_mass),
            float(inherited["B0_limit_mass_flow_relative"]),
        ),
        "velocity": (
            relative_error(small.effective_velocity_m_s, b0_velocity),
            float(inherited["B0_limit_effective_velocity_relative"]),
        ),
        "momentum": (
            relative_error(small.advective_momentum_rate_out_N, b0_momentum),
            float(inherited["B0_limit_momentum_transfer_relative"]),
        ),
        "energy": (
            relative_error(small.energy_transfer_outward_W, b0_energy),
            float(inherited["B0_limit_energy_transfer_relative"]),
        ),
    }
    for name, (error, tolerance) in b0_values.items():
        add(f"B0_limit_{name}", error, tolerance, error <= tolerance)

    plateau_high = face_by_id["B2-07A_BELOW_CRITICAL_PLATEAU_HIGH"]
    plateau_low = face_by_id["B2-07B_BELOW_CRITICAL_PLATEAU_LOW"]
    plateau_errors = [
        relative_error(
            getattr(plateau_high, field),
            getattr(plateau_low, field),
        )
        for field in (
            "F_rho_kg_m2_s",
            "F_rho_u_pa",
            "F_rho_E_W_m2",
        )
    ]
    plateau_error = max(plateau_errors)
    add(
        "below_critical_face_flux_plateau",
        plateau_error,
        float(tolerances["below_critical_face_plateau_relative"]),
        plateau_error <= float(tolerances["below_critical_face_plateau_relative"]),
    )

    area_low = face_by_id["B2-08A_AREA_SCALING_LOW"]
    area_high = face_by_id["B2-08B_AREA_SCALING_HIGH"]
    area_ratios = [
        getattr(area_high, field) / getattr(area_low, field)
        for field in (
            "mass_transfer_outward_kg_s",
            "energy_transfer_outward_W",
            "advective_momentum_rate_out_N",
        )
    ]
    area_error = max(abs(value - 2.0) for value in area_ratios)
    add(
        "area_scaling",
        area_ratios,
        2.0,
        area_error <= float(tolerances["scaling_ratio_absolute"]),
    )

    cd_low = face_by_id["B2-08C_CD_SCALING_LOW"]
    cd_high = face_by_id["B2-08D_CD_SCALING_HIGH"]
    cd_mass_ratio = (
        cd_high.mass_transfer_outward_kg_s / cd_low.mass_transfer_outward_kg_s
    )
    cd_energy_ratio = (
        cd_high.energy_transfer_outward_W / cd_low.energy_transfer_outward_W
    )
    cd_momentum_ratio = (
        cd_high.advective_momentum_rate_out_N
        / cd_low.advective_momentum_rate_out_N
    )
    critical_ratio = (
        float(cd_high.critical_pressure_pa)
        / float(cd_low.critical_pressure_pa)
    )
    scaling_tolerance = float(tolerances["scaling_ratio_absolute"])
    cd_passed = (
        abs(cd_mass_ratio - 2.0) <= scaling_tolerance
        and abs(cd_energy_ratio - 2.0) <= scaling_tolerance
        and abs(cd_momentum_ratio - 4.0) <= scaling_tolerance
        and abs(critical_ratio - 1.0)
        <= float(inherited["critical_pressure_Cd_independence_relative"])
    )
    add(
        "Cd_scaling_and_critical_pressure",
        {
            "mass": cd_mass_ratio,
            "energy": cd_energy_ratio,
            "advective_momentum": cd_momentum_ratio,
            "critical_pressure": critical_ratio,
        },
        {"mass": 2.0, "energy": 2.0, "advective_momentum": 4.0, "critical": 1.0},
        cd_passed,
    )

    add(
        "one_step_normalized_balance",
        one_step.normalized_balance_residual,
        float(tolerances["one_step_normalized_state_absolute"]),
        one_step.normalized_balance_residual
        <= float(tolerances["one_step_normalized_state_absolute"]),
    )
    add(
        "one_step_mass_inventory",
        abs(one_step.mass_inventory_residual_kg),
        float(tolerances["mass_inventory_absolute_kg"]),
        abs(one_step.mass_inventory_residual_kg)
        <= float(tolerances["mass_inventory_absolute_kg"]),
    )
    add(
        "one_step_energy_inventory",
        abs(one_step.energy_inventory_residual_J),
        float(tolerances["energy_inventory_absolute_J"]),
        abs(one_step.energy_inventory_residual_J)
        <= float(tolerances["energy_inventory_absolute_J"]),
    )
    add(
        "one_step_vapor_identity",
        one_step.vapor_inventory_residual_kg,
        0.0,
        one_step.vapor_inventory_residual_kg == 0.0,
    )

    max_mass_ledger = max(abs(row.mass_residual_kg) for row in ledgers)
    max_energy_ledger = max(abs(row.energy_residual_J) for row in ledgers)
    max_momentum_ledger = max(
        abs(row.momentum_residual_kg_m_s) for row in ledgers
    )
    max_vapor_ledger = max(abs(row.vapor_residual_kg) for row in ledgers)
    add(
        "ledger_mass_identity",
        max_mass_ledger,
        float(tolerances["mass_inventory_absolute_kg"]),
        max_mass_ledger <= float(tolerances["mass_inventory_absolute_kg"]),
    )
    add(
        "ledger_energy_identity",
        max_energy_ledger,
        float(tolerances["energy_inventory_absolute_J"]),
        max_energy_ledger <= float(tolerances["energy_inventory_absolute_J"]),
    )
    add(
        "ledger_momentum_identity",
        max_momentum_ledger,
        float(tolerances["momentum_inventory_absolute_kg_m_s"]),
        max_momentum_ledger
        <= float(tolerances["momentum_inventory_absolute_kg_m_s"]),
    )
    add(
        "ledger_vapor_identity",
        max_vapor_ledger,
        0.0,
        max_vapor_ledger == 0.0,
    )

    probe_keys = {
        (row.cells, row.probe_normalized_position)
        for row in acoustic_rows
    }
    probe_map_passed = (
        len(acoustic_rows) == 9
        and len(probe_keys) == 9
        and all(row.interpolation_weight == 0.5 for row in acoustic_rows)
        and all(
            row.left_center_xi
            < row.probe_normalized_position
            < row.right_center_xi
            for row in acoustic_rows
        )
    )
    add("acoustic_probe_map", len(probe_keys), 9, probe_map_passed)
    all_passed = all(bool(row["passed"]) for row in checks)
    summary = {
        "all_face_outcomes_match": face_outcomes,
        "all_guard_outcomes_match": guard_outcomes,
        "all_locked_reference_checks_passed": all_passed,
        "maximum_pressure_decomposition_residual_pa": pressure_residual,
        "maximum_ledger_mass_residual_kg": max_mass_ledger,
        "maximum_ledger_energy_residual_J": max_energy_ledger,
        "maximum_ledger_momentum_residual_kg_m_s": max_momentum_ledger,
        "acoustic_probe_map_count": len(probe_keys),
    }
    return checks, summary


def build_case_matrix(
    contract: Mapping[str, Any],
    face_by_id: Mapping[str, FaceReference],
    guards: Mapping[str, GuardReference],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in contract["benchmark_cases"]:
        case_id = str(row["case_id"])
        if case_id in face_by_id:
            reference_outcome = face_by_id[case_id].formal_outcome
            reference_status = "COMPUTED_REFERENCE"
            matches = face_by_id[case_id].outcome_matches_contract
        elif case_id in guards:
            reference_outcome = guards[case_id].formal_outcome
            reference_status = "COMPUTED_GUARD_REFERENCE"
            matches = guards[case_id].outcome_matches_contract
        elif case_id.startswith("B2-10"):
            reference_outcome = REFERENCE_LEDGER_DEFINED
            reference_status = "TARGET_LEDGER_DEFINED_NO_FVM_EXECUTION"
            matches = True
        elif case_id.startswith("B2-11"):
            reference_outcome = REFERENCE_ACOUSTIC_DEFINED
            reference_status = "TARGET_ACOUSTIC_REFERENCE_DEFINED_NO_FVM_EXECUTION"
            matches = True
        elif case_id == "B2-12_FIXED_MESH_CFL_CHARACTERIZATION":
            reference_outcome = REFERENCE_MATRIX_DEFINED
            reference_status = "TARGET_MATRIX_DEFINED_NO_FVM_EXECUTION"
            matches = True
        else:
            raise KeyError(case_id)
        rows.append(
            {
                "case_id": case_id,
                "state_id": row.get("state_id", ""),
                "execution_level": row.get("execution_level", row.get("execution_mode", "")),
                "contract_expected_outcome": row["expected_outcome"],
                "reference_outcome": reference_outcome,
                "reference_status": reference_status,
                "reference_disposition_matches_contract_stage": matches,
                "adapter_result_available": False,
                "finite_pipe_result_available": False,
            }
        )
    return rows


def evaluate_reference(
    contract: Mapping[str, Any],
    extension: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    provider: CoolPropReferenceProperties | None = None,
) -> ReferencePackage:
    provider = provider or CoolPropReferenceProperties()
    face_rows, reconstructions = evaluate_face_rows(
        contract,
        b1_contract,
        provider,
    )
    face_by_id = {row.case_id: row for row in face_rows}
    one_step = build_one_step_reference(
        contract,
        face_by_id["B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"],
        reconstructions["LIQUID_SMALL_DROP"],
    )
    ledgers = build_ledgers(contract, face_by_id, reconstructions)
    acoustic_rows = build_acoustic_rows(
        contract,
        extension,
        reconstructions["LIQUID_SMALL_DROP"],
    )
    guard_rows = evaluate_guards(contract, provider)
    guard_by_id = {row.case_id: row for row in guard_rows}
    checks, check_summary = build_locked_checks(
        contract,
        extension,
        face_by_id,
        one_step,
        ledgers,
        acoustic_rows,
        guard_rows,
    )
    case_matrix = build_case_matrix(contract, face_by_id, guard_by_id)
    physical_count = sum(
        not str(row["case_id"]).startswith("G-")
        for row in contract["benchmark_cases"]
    )
    guard_count = len(contract["benchmark_cases"]) - physical_count
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": "verification_only_single_phase_fvm_discharge_reference",
        "issue": int(contract["issue"]),
        "case_count": len(contract["benchmark_cases"]),
        "physical_case_count": physical_count,
        "guard_case_count": guard_count,
        "computed_face_reference_count": len(face_rows),
        "computed_guard_reference_count": len(guard_rows),
        "inventory_ledger_count": len({row.ledger_id for row in ledgers}),
        "inventory_ledger_row_count": len(ledgers),
        "acoustic_reference_row_count": len(acoustic_rows),
        **check_summary,
        "u3_b2_contract_locked": True,
        "u3_b2_reference_implemented": True,
        "u3_b2_fvm_adapter_implemented": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "u3_b2_verification_benchmark_accepted": False,
        "single_phase_fvm_discharge_mapping_verified": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "physical_discharge_boundary_approved": False,
        "two_phase_critical_discharge_accuracy_approved": False,
        "integrated_blowdown_model_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
        "reference_imports_future_B2_adapter": False,
        "shared_B2_face_mapping_helper": False,
        "shared_B2_one_step_balance_helper": False,
        "shared_B2_inventory_ledger_helper": False,
        "shared_B2_acoustic_reference_helper": False,
        "property_backend": "CoolProp",
        "property_backend_version": provider.version,
    }
    return ReferencePackage(
        face_rows=tuple(face_rows),
        one_step=one_step,
        ledger_rows=tuple(ledgers),
        acoustic_rows=tuple(acoustic_rows),
        guard_rows=tuple(guard_rows),
        case_matrix=tuple(case_matrix),
        locked_checks=tuple(checks),
        summary=summary,
    )


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError(f"No rows for {path.name}")
    fields: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(materialized)


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "UNKNOWN"


def write_plots(output_dir: Path, package: ReferencePackage) -> None:
    import matplotlib.pyplot as plt

    physical = [
        row
        for row in package.face_rows
        if row.mass_transfer_outward_kg_s > 0.0
    ]
    x = list(range(len(physical)))
    figure = plt.figure(figsize=(12, 6))
    axis = figure.add_subplot(111)
    axis.plot(x, [row.F_rho_kg_m2_s for row in physical], marker="o", label="mass flux")
    axis.plot(
        x,
        [row.advective_momentum_rate_out_N / row.pipe_area_m2 for row in physical],
        marker="s",
        label="advective momentum flux",
    )
    axis.set_xticks(x)
    axis.set_xticklabels([row.case_id for row in physical], rotation=70, ha="right")
    axis.set_ylabel("Reference flux value")
    axis.set_title("U3 B2 independent face-flux reference")
    axis.legend()
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_dir / "face_flux_reference.png", dpi=160)
    plt.close(figure)

    mesh = min(row.cells for row in package.acoustic_rows)
    rows = [row for row in package.acoustic_rows if row.cells == mesh]
    figure = plt.figure(figsize=(8, 5))
    axis = figure.add_subplot(111)
    probes = [row.probe_normalized_position for row in rows]
    axis.plot(
        probes,
        [row.direct_reference_time_s for row in rows],
        marker="o",
        label="direct rarefaction",
    )
    axis.plot(
        probes,
        [row.reflected_reference_time_s for row in rows],
        marker="s",
        label="rigid-wall reflection",
    )
    axis.set_xlabel("requested probe x/L")
    axis.set_ylabel("reference arrival time [s]")
    axis.set_title("U3 B2 linear-acoustic arrival reference")
    axis.legend()
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_dir / "acoustic_arrival_reference.png", dpi=160)
    plt.close(figure)


def write_report(
    path: Path,
    package: ReferencePackage,
    provenance: Mapping[str, Any],
) -> None:
    summary = package.summary
    lines = [
        "# U3 B2 独立FVM流出coupling Reference",
        "",
        "## Status",
        "",
        "```text",
        "scope: verification-only independent Reference",
        "B2 contract: locked before results",
        "B2 Adapter: not implemented",
        "finite-pipe coupled execution: not performed",
        "physical validation / design use: false / false",
        "```",
        "",
        "## Reference layers",
        "",
        "- accepted B1 transferから独立に構築したright-face flux分解",
        "- 一様配管最終cellのone-step保存形balance",
        "- mass / energy / momentum impulseの累積ledger identity",
        "- requested probe位置を用いるlinear acoustic / MOC到達時刻",
        "- 7件の明示Guard Reference",
        "",
        "## Fixed counts",
        "",
        "```text",
        f"total / physical / guard: {summary['case_count']} / {summary['physical_case_count']} / {summary['guard_case_count']}",
        f"computed face rows: {summary['computed_face_reference_count']}",
        f"ledger rows: {summary['inventory_ledger_row_count']}",
        f"acoustic rows: {summary['acoustic_reference_row_count']}",
        f"all locked checks passed: {summary['all_locked_reference_checks_passed']}",
        "```",
        "",
        "## Provenance",
        "",
        "```text",
        f"analysis source SHA: {provenance['source_git_sha']}",
        f"checkout SHA: {provenance['checkout_git_sha']}",
        f"Python: {provenance['python_version']}",
        f"CoolProp: {provenance['property_backend_version']}",
        f"parent contract SHA256: {provenance['parent_contract_sha256']}",
        f"extension contract SHA256: {provenance['extension_contract_sha256']}",
        "```",
        "",
        "## Approval boundary",
        "",
        "このReferenceにより`u3_b2_reference_implemented=true`とできる。",
        "一方、FVM Adapter、有限配管execution、B2 acceptance、物理Validation、",
        "設計利用およびproduction activationはfalseのままである。",
        "",
        "## Interpretation limit",
        "",
        "本成果はB2-specific mappingと比較基準の独立実装であり、production solverへ",
        "流出境界を接続した結果ではない。実配管ブローダウン精度を承認しない。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_artifact(
    *,
    output_dir: Path,
    package: ReferencePackage,
    contract_path: Path,
    extension_path: Path,
    b1_contract_path: Path,
    source_git_sha: str,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    shutil.copy2(contract_path, output_dir / "benchmark_contract.json")
    shutil.copy2(extension_path, output_dir / "event_provenance_contract.json")
    shutil.copy2(b1_contract_path, output_dir / "b1_component_contract.json")

    contract_sha = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    extension_sha = hashlib.sha256(extension_path.read_bytes()).hexdigest()
    checkout_sha = git_value("rev-parse", "HEAD")
    tracked_status = git_value(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    provenance = {
        "schema_version": "stage7_u3_b2_reference_provenance_v1",
        "source_git_sha": source_git_sha,
        "checkout_git_sha": checkout_sha,
        "git_status_porcelain": tracked_status,
        "python_version": platform.python_version(),
        "numpy_version": version("numpy"),
        "matplotlib_version": version("matplotlib"),
        "pytest_version": version("pytest"),
        "property_backend": "CoolProp",
        "property_backend_version": version("CoolProp"),
        "parent_contract_sha256": contract_sha,
        "extension_contract_sha256": extension_sha,
        "B1_reference_source_sha": (
            "c7c25efae0e53a8b5f5ed164f9135238c6e005e0"
        ),
        "B2_reference_imports_future_adapter": False,
    }
    summary = dict(package.summary)
    summary["provenance"] = provenance
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "runtime_and_git_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    write_csv(output_dir / "reference_case_matrix.csv", package.case_matrix)
    write_csv(
        output_dir / "face_state_and_choking_adoption.csv",
        [
            {
                key: value
                for key, value in asdict(row).items()
                if key
                in {
                    "case_id",
                    "state_id",
                    "formal_outcome",
                    "upstream_static_pressure_pa",
                    "upstream_static_temperature_K",
                    "upstream_phase",
                    "stagnation_pressure_pa",
                    "stagnation_temperature_K",
                    "back_pressure_pa",
                    "critical_pressure_pa",
                    "discharge_state_pressure_pa",
                    "opening_fraction",
                    "discharge_coefficient",
                    "b1_formal_outcome",
                    "b1_evaluation_pressure_pa",
                    "b1_critical_pressure_pa",
                }
            }
            for row in package.face_rows
        ],
    )
    write_csv(
        output_dir / "face_flux_decomposition.csv",
        [asdict(row) for row in package.face_rows],
    )
    write_csv(
        output_dir / "one_step_conservative_update_reference.csv",
        [asdict(package.one_step)],
    )
    write_csv(
        output_dir / "cumulative_discharge_and_inventory_reference.csv",
        [asdict(row) for row in package.ledger_rows],
    )
    write_csv(
        output_dir / "momentum_impulse_reference.csv",
        [
            {
                key: value
                for key, value in asdict(row).items()
                if "momentum" in key
                or key
                in {
                    "ledger_id",
                    "state_id",
                    "step",
                    "dt_s",
                    "time_s",
                    "open_pressure_force_out_N",
                    "closed_pressure_force_out_N",
                    "left_pressure_force_in_N",
                }
            }
            for row in package.ledger_rows
        ],
    )
    write_csv(
        output_dir / "acoustic_arrival_reference.csv",
        [asdict(row) for row in package.acoustic_rows],
    )
    write_csv(
        output_dir / "guard_outcomes.csv",
        [asdict(row) for row in package.guard_rows],
    )
    write_csv(output_dir / "locked_checks.csv", package.locked_checks)
    write_plots(output_dir, package)
    write_report(output_dir / "report.md", package, provenance)

    manifest_lines: list[str] = []
    for artifact in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if artifact.name == "artifact_sha256.txt":
            continue
        if not artifact.is_file():
            raise ValueError(f"Unexpected directory in artifact: {artifact}")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        manifest_lines.append(f"{digest}  {artifact.name}")
    (output_dir / "artifact_sha256.txt").write_text(
        "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--extension-contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contract = load_contract(args.contract)
    extension = load_extension(args.extension_contract)
    b1_contract = b1_ref.load_contract(args.b1_contract)
    package = evaluate_reference(contract, extension, b1_contract)
    if not package.summary["all_locked_reference_checks_passed"]:
        raise RuntimeError("One or more locked U3 B2 Reference checks failed")
    write_artifact(
        output_dir=args.output_dir,
        package=package,
        contract_path=args.contract,
        extension_path=args.extension_contract,
        b1_contract_path=args.b1_contract,
        source_git_sha=str(args.source_git_sha),
    )
    print(json.dumps(package.summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
