"""Independent U3 B1 single-phase compressible critical-state reference.

This module is the reference-first implementation for the locked
``stage7_u3_b1_critical_state_contract_v1.json`` contract. It does not import
or share helpers with a future adapter. It evaluates a single-phase isentropic
path, locates an interior maximum mass flux for the GAS_CRITICAL family, and
retains explicit scope and guard outcomes.

Positive transfers are directed out of the modeled domain. Static pressure
force and production FVM coupling remain outside this reference scope.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

SCHEMA_VERSION = "stage7_u3_b1_independent_reference_v1"
CONTRACT_SCHEMA_VERSION = "stage7_u3_b1_critical_state_contract_v1"

SUCCESS_CLOSED = "SUCCESS_CLOSED"
SUCCESS_ZERO_PRESSURE_DROP = "SUCCESS_ZERO_PRESSURE_DROP"
SUCCESS_UNCHOKED = "SUCCESS_UNCHOKED_SINGLE_PHASE_DISCHARGE"
SUCCESS_CHOKED = "SUCCESS_CHOKED_SINGLE_PHASE_DISCHARGE"
NONFINITE_INPUT = "NONFINITE_INPUT"
OPENING_OUTSIDE_UNIT_INTERVAL = "OPENING_OUTSIDE_UNIT_INTERVAL"
NONPOSITIVE_REFERENCE_AREA = "NONPOSITIVE_REFERENCE_AREA"
NONPOSITIVE_DISCHARGE_COEFFICIENT = "NONPOSITIVE_DISCHARGE_COEFFICIENT"
REVERSE_PRESSURE_NOT_SUPPORTED = "REVERSE_PRESSURE_NOT_SUPPORTED"
UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE = (
    "UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE"
)
SINGLE_PHASE_PATH_SCOPE_FAILURE = "SINGLE_PHASE_PATH_SCOPE_FAILURE"
PROPERTY_BACKEND_FAILURE = "PROPERTY_BACKEND_FAILURE"
NONPOSITIVE_KINETIC_ENERGY_HEAD = "NONPOSITIVE_KINETIC_ENERGY_HEAD"
CRITICAL_SEARCH_NOT_BRACKETED = "CRITICAL_SEARCH_NOT_BRACKETED"
CRITICAL_REFINEMENT_FAILURE = "CRITICAL_REFINEMENT_FAILURE"
CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE = (
    "CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE"
)


class PropertyProvider(Protocol):
    version: str

    def saturation_temperature(self, pressure_pa: float) -> float: ...

    def upstream_snapshot(
        self, pressure_pa: float, temperature_K: float
    ) -> "UpstreamState": ...

    def isentropic_candidate(
        self, pressure_pa: float, entropy_J_kg_K: float
    ) -> "CandidateState": ...


@dataclass(frozen=True)
class UpstreamState:
    pressure_pa: float
    temperature_K: float
    density_kg_m3: float
    enthalpy_J_kg: float
    entropy_J_kg_K: float
    phase: str


@dataclass(frozen=True)
class CandidateState:
    pressure_pa: float
    temperature_K: float
    density_kg_m3: float
    enthalpy_J_kg: float
    entropy_J_kg_K: float
    phase: str


@dataclass(frozen=True)
class StreamState:
    candidate: CandidateState
    kinetic_energy_head_J_kg: float
    ideal_velocity_m_s: float
    effective_velocity_m_s: float
    ideal_mass_flux_kg_m2_s: float
    effective_mass_flux_kg_m2_s: float
    entropy_residual_J_kg_K: float


@dataclass(frozen=True)
class CriticalState:
    pressure_pa: float
    pressure_ratio: float
    stream: StreamState
    coarse_index: int
    coarse_neighbor_high_pressure_pa: float
    coarse_neighbor_low_pressure_pa: float
    refinement_iterations: int
    final_bracket_width_pa: float
    peak_prominence_relative: float
    path_termination_outcome: str | None
    path_termination_pressure_pa: float | None


@dataclass(frozen=True)
class ReferenceInput:
    case_id: str
    state_id: str
    upstream_pressure_pa: float
    upstream_temperature_K: float
    back_pressure_pa: float
    reference_area_m2: float
    opening_fraction: float
    discharge_coefficient: float


@dataclass(frozen=True)
class ReferenceResult:
    case_id: str
    state_id: str
    formal_outcome: str
    formal_message: str
    upstream_pressure_pa: float
    upstream_temperature_K: float
    back_pressure_pa: float
    evaluation_pressure_pa: float | None
    critical_pressure_pa: float | None
    critical_pressure_ratio: float | None
    reference_area_m2: float
    opening_fraction: float
    effective_area_m2: float
    discharge_coefficient: float
    upstream_density_kg_m3: float | None
    upstream_enthalpy_J_kg: float | None
    upstream_entropy_J_kg_K: float | None
    upstream_phase: str | None
    candidate_temperature_K: float | None
    candidate_density_kg_m3: float | None
    candidate_enthalpy_J_kg: float | None
    candidate_entropy_J_kg_K: float | None
    candidate_phase: str | None
    kinetic_energy_head_J_kg: float | None
    ideal_velocity_m_s: float
    effective_velocity_m_s: float
    ideal_mass_flux_kg_m2_s: float
    effective_mass_flux_kg_m2_s: float
    mass_transfer_outward_kg_s: float
    momentum_stream_transfer_outward_N: float
    energy_transfer_outward_W: float
    static_pressure_force_included: bool = False
    production_fvm_connected: bool = False

    @property
    def succeeded(self) -> bool:
        return self.formal_outcome.startswith("SUCCESS_")


def normalize_phase(value: str) -> str:
    return value.lower().replace("_", "").replace(" ", "")


def finite(*values: float) -> bool:
    return all(math.isfinite(float(value)) for value in values)


class CoolPropProvider:
    def __init__(self) -> None:
        from CoolProp import __version__ as coolprop_version
        from CoolProp.CoolProp import PhaseSI, PropsSI

        self._PropsSI = PropsSI
        self._PhaseSI = PhaseSI
        self.version = str(coolprop_version)

    def saturation_temperature(self, pressure_pa: float) -> float:
        return float(self._PropsSI("T", "P", pressure_pa, "Q", 0.0, "CO2"))

    def upstream_snapshot(
        self, pressure_pa: float, temperature_K: float
    ) -> UpstreamState:
        props = self._PropsSI
        phase = str(self._PhaseSI("P", pressure_pa, "T", temperature_K, "CO2"))
        return UpstreamState(
            pressure_pa=pressure_pa,
            temperature_K=temperature_K,
            density_kg_m3=float(
                props("DMASS", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            enthalpy_J_kg=float(
                props("HMASS", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            entropy_J_kg_K=float(
                props("SMASS", "P", pressure_pa, "T", temperature_K, "CO2")
            ),
            phase=phase,
        )

    def isentropic_candidate(
        self, pressure_pa: float, entropy_J_kg_K: float
    ) -> CandidateState:
        props = self._PropsSI
        temperature = float(
            props("T", "P", pressure_pa, "SMASS", entropy_J_kg_K, "CO2")
        )
        phase = str(
            self._PhaseSI(
                "P",
                pressure_pa,
                "SMASS",
                entropy_J_kg_K,
                "CO2",
            )
        )
        return CandidateState(
            pressure_pa=pressure_pa,
            temperature_K=temperature,
            density_kg_m3=float(
                props("DMASS", "P", pressure_pa, "SMASS", entropy_J_kg_K, "CO2")
            ),
            enthalpy_J_kg=float(
                props("HMASS", "P", pressure_pa, "SMASS", entropy_J_kg_K, "CO2")
            ),
            entropy_J_kg_K=float(
                props("SMASS", "P", pressure_pa, "T", temperature, "CO2")
            ),
            phase=phase,
        )


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("Unexpected U3 B1 contract schema")
    if contract.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B1 contract must be locked before execution")
    approvals = contract.get("approval_boundary", {})
    if approvals.get("u3_b1_contract_locked") is not True:
        raise ValueError("u3_b1_contract_locked must be true")
    if approvals.get("u3_b1_reference_implemented") is not False:
        raise ValueError("Reference implementation state must be false in contract")
    return contract


def state_family(contract: dict[str, Any], state_id: str) -> dict[str, Any]:
    for row in contract["upstream_state_families"]:
        if row["state_id"] == state_id:
            return row
    raise KeyError(state_id)


def upstream_temperature(
    family: dict[str, Any],
    provider: PropertyProvider,
    *,
    subcooling_override_K: float | None = None,
) -> float:
    if "temperature_K" in family:
        return float(family["temperature_K"])
    subcooling = float(
        family["subcooling_K"]
        if subcooling_override_K is None
        else subcooling_override_K
    )
    return provider.saturation_temperature(float(family["pressure_pa"])) - subcooling


def build_input(
    contract: dict[str, Any],
    row: dict[str, Any],
    provider: PropertyProvider,
) -> ReferenceInput:
    family = state_family(contract, str(row["state_id"]))
    geometry = contract["geometry_and_coefficients"]
    back_pressure = float(row.get("back_pressure_pa", 0.0))
    mutation = row.get("input_mutation")
    if mutation and mutation.get("field") == "back_pressure_pa":
        if mutation.get("value_token") == "NaN":
            back_pressure = math.nan
    return ReferenceInput(
        case_id=str(row["case_id"]),
        state_id=str(row["state_id"]),
        upstream_pressure_pa=float(family["pressure_pa"]),
        upstream_temperature_K=upstream_temperature(
            family,
            provider,
            subcooling_override_K=(
                float(row["upstream_subcooling_override_K"])
                if "upstream_subcooling_override_K" in row
                else None
            ),
        ),
        back_pressure_pa=back_pressure,
        reference_area_m2=float(geometry["reference_area_m2"]),
        opening_fraction=float(row.get("opening_fraction", 0.5)),
        discharge_coefficient=float(row.get("discharge_coefficient", 0.8)),
    )


def zero_result(
    inputs: ReferenceInput,
    outcome: str,
    message: str,
    *,
    upstream: UpstreamState | None = None,
    critical: CriticalState | None = None,
) -> ReferenceResult:
    return ReferenceResult(
        case_id=inputs.case_id,
        state_id=inputs.state_id,
        formal_outcome=outcome,
        formal_message=message,
        upstream_pressure_pa=inputs.upstream_pressure_pa,
        upstream_temperature_K=inputs.upstream_temperature_K,
        back_pressure_pa=inputs.back_pressure_pa,
        evaluation_pressure_pa=None,
        critical_pressure_pa=None if critical is None else critical.pressure_pa,
        critical_pressure_ratio=None if critical is None else critical.pressure_ratio,
        reference_area_m2=inputs.reference_area_m2,
        opening_fraction=inputs.opening_fraction,
        effective_area_m2=inputs.reference_area_m2 * inputs.opening_fraction,
        discharge_coefficient=inputs.discharge_coefficient,
        upstream_density_kg_m3=None if upstream is None else upstream.density_kg_m3,
        upstream_enthalpy_J_kg=None if upstream is None else upstream.enthalpy_J_kg,
        upstream_entropy_J_kg_K=None if upstream is None else upstream.entropy_J_kg_K,
        upstream_phase=None if upstream is None else upstream.phase,
        candidate_temperature_K=None,
        candidate_density_kg_m3=None,
        candidate_enthalpy_J_kg=None,
        candidate_entropy_J_kg_K=None,
        candidate_phase=None,
        kinetic_energy_head_J_kg=None,
        ideal_velocity_m_s=0.0,
        effective_velocity_m_s=0.0,
        ideal_mass_flux_kg_m2_s=0.0,
        effective_mass_flux_kg_m2_s=0.0,
        mass_transfer_outward_kg_s=0.0,
        momentum_stream_transfer_outward_N=0.0,
        energy_transfer_outward_W=0.0,
    )


def evaluate_stream(
    provider: PropertyProvider,
    upstream: UpstreamState,
    pressure_pa: float,
    discharge_coefficient: float,
    allowed_phases: set[str],
    entropy_tolerance: float,
    *,
    allow_exact_zero: bool = False,
) -> tuple[StreamState | None, str | None, str]:
    try:
        candidate = provider.isentropic_candidate(
            pressure_pa, upstream.entropy_J_kg_K
        )
    except Exception as exc:
        return None, PROPERTY_BACKEND_FAILURE, (
            f"Candidate property evaluation failed: {type(exc).__name__}: {exc}"
        )

    values = (
        candidate.temperature_K,
        candidate.density_kg_m3,
        candidate.enthalpy_J_kg,
        candidate.entropy_J_kg_K,
    )
    if not finite(*values) or candidate.density_kg_m3 <= 0.0:
        return None, PROPERTY_BACKEND_FAILURE, (
            "Candidate state contains nonfinite or nonpositive properties."
        )
    normalized = normalize_phase(candidate.phase)
    if normalized not in allowed_phases:
        return None, SINGLE_PHASE_PATH_SCOPE_FAILURE, (
            f"Candidate phase {candidate.phase!r} is outside {sorted(allowed_phases)}."
        )
    entropy_residual = candidate.entropy_J_kg_K - upstream.entropy_J_kg_K
    if abs(entropy_residual) > entropy_tolerance:
        return None, PROPERTY_BACKEND_FAILURE, (
            f"Isentropic entropy residual {entropy_residual} exceeds tolerance."
        )
    head = upstream.enthalpy_J_kg - candidate.enthalpy_J_kg
    if allow_exact_zero and pressure_pa == upstream.pressure_pa and abs(head) <= 1e-9:
        ideal_velocity = 0.0
    elif not math.isfinite(head) or head <= 0.0:
        return None, NONPOSITIVE_KINETIC_ENERGY_HEAD, (
            f"Nonpositive kinetic energy head {head} J/kg."
        )
    else:
        ideal_velocity = math.sqrt(2.0 * head)
    effective_velocity = discharge_coefficient * ideal_velocity
    ideal_flux = candidate.density_kg_m3 * ideal_velocity
    effective_flux = candidate.density_kg_m3 * effective_velocity
    if not finite(ideal_velocity, effective_velocity, ideal_flux, effective_flux):
        return None, CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE, (
            "Stream construction produced a nonfinite value."
        )
    return (
        StreamState(
            candidate=candidate,
            kinetic_energy_head_J_kg=head,
            ideal_velocity_m_s=ideal_velocity,
            effective_velocity_m_s=effective_velocity,
            ideal_mass_flux_kg_m2_s=ideal_flux,
            effective_mass_flux_kg_m2_s=effective_flux,
            entropy_residual_J_kg_K=entropy_residual,
        ),
        None,
        "SUCCESS",
    )


def golden_section_maximize(
    function: Callable[[float], float],
    lower: float,
    upper: float,
    tolerance: float,
    max_iterations: int,
) -> tuple[float, float, int, float]:
    if not finite(lower, upper, tolerance) or not lower < upper or tolerance <= 0:
        raise ValueError("Invalid golden-section bracket")
    inverse_phi = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lower, upper
    c = b - inverse_phi * (b - a)
    d = a + inverse_phi * (b - a)
    fc, fd = function(c), function(d)
    if not finite(fc, fd):
        raise ValueError("Nonfinite refinement objective")
    iterations = 0
    while b - a > tolerance and iterations < max_iterations:
        if fc >= fd:
            b, d, fd = d, c, fc
            c = b - inverse_phi * (b - a)
            fc = function(c)
            if not math.isfinite(fc):
                raise ValueError("Nonfinite refinement objective")
        else:
            a, c, fc = c, d, fd
            d = a + inverse_phi * (b - a)
            fd = function(d)
            if not math.isfinite(fd):
                raise ValueError("Nonfinite refinement objective")
        iterations += 1
    candidates = [(a, function(a)), (b, function(b)), (c, fc), (d, fd)]
    candidates.sort(key=lambda item: (-item[1], -item[0]))
    pressure, value = candidates[0]
    return pressure, value, iterations, b - a


def critical_search(
    contract: dict[str, Any],
    provider: PropertyProvider,
    upstream: UpstreamState,
    allowed_phases: set[str],
    discharge_coefficient: float,
) -> tuple[CriticalState | None, list[dict[str, Any]], str | None, str]:
    search = contract["critical_state_search"]
    tolerances = contract["acceptance_tolerances"]
    p0 = upstream.pressure_pa
    upper_ratio = float(search["coarse_pressure_ratio_upper"])
    lower_ratio = float(search["coarse_pressure_ratio_lower"])
    node_count = int(search["coarse_node_count"])
    entropy_tolerance = float(tolerances["isentropic_entropy_absolute_J_kg_K"])

    records: list[dict[str, Any]] = []
    admissible: list[tuple[int, StreamState]] = []
    termination_outcome: str | None = None
    termination_pressure: float | None = None

    for index in range(node_count):
        ratio = upper_ratio - (upper_ratio - lower_ratio) * index / (node_count - 1)
        pressure = p0 * ratio
        if index == 0:
            candidate = CandidateState(
                pressure_pa=upstream.pressure_pa,
                temperature_K=upstream.temperature_K,
                density_kg_m3=upstream.density_kg_m3,
                enthalpy_J_kg=upstream.enthalpy_J_kg,
                entropy_J_kg_K=upstream.entropy_J_kg_K,
                phase=upstream.phase,
            )
            stream = StreamState(
                candidate=candidate,
                kinetic_energy_head_J_kg=0.0,
                ideal_velocity_m_s=0.0,
                effective_velocity_m_s=0.0,
                ideal_mass_flux_kg_m2_s=0.0,
                effective_mass_flux_kg_m2_s=0.0,
                entropy_residual_J_kg_K=0.0,
            )
            outcome, message = None, "SUCCESS_ZERO_PRESSURE_DROP"
        else:
            stream, outcome, message = evaluate_stream(
                provider,
                upstream,
                pressure,
                discharge_coefficient,
                allowed_phases,
                entropy_tolerance,
            )
        records.append(
            {
                "coarse_index": index,
                "pressure_pa": pressure,
                "pressure_ratio": ratio,
                "admissible": stream is not None,
                "formal_outcome": "SUCCESS" if stream is not None else outcome,
                "formal_message": message,
                "temperature_K": None if stream is None else stream.candidate.temperature_K,
                "density_kg_m3": None if stream is None else stream.candidate.density_kg_m3,
                "enthalpy_J_kg": None if stream is None else stream.candidate.enthalpy_J_kg,
                "entropy_J_kg_K": None if stream is None else stream.candidate.entropy_J_kg_K,
                "phase": None if stream is None else stream.candidate.phase,
                "kinetic_energy_head_J_kg": None
                if stream is None
                else stream.kinetic_energy_head_J_kg,
                "ideal_velocity_m_s": None if stream is None else stream.ideal_velocity_m_s,
                "effective_velocity_m_s": None
                if stream is None
                else stream.effective_velocity_m_s,
                "ideal_mass_flux_kg_m2_s": None
                if stream is None
                else stream.ideal_mass_flux_kg_m2_s,
                "effective_mass_flux_kg_m2_s": None
                if stream is None
                else stream.effective_mass_flux_kg_m2_s,
                "entropy_residual_J_kg_K": None
                if stream is None
                else stream.entropy_residual_J_kg_K,
            }
        )
        if stream is None:
            termination_outcome = outcome
            termination_pressure = pressure
            break
        admissible.append((index, stream))

    if len(admissible) < 3:
        return None, records, CRITICAL_SEARCH_NOT_BRACKETED, (
            "Fewer than three admissible coarse states."
        )
    max_flux = max(item[1].effective_mass_flux_kg_m2_s for item in admissible)
    maxima = [
        item
        for item in admissible
        if item[1].effective_mass_flux_kg_m2_s == max_flux
    ]
    coarse_index, coarse_stream = min(maxima, key=lambda item: item[0])
    position = next(
        idx for idx, item in enumerate(admissible) if item[0] == coarse_index
    )
    if position == 0 or position == len(admissible) - 1:
        return None, records, CRITICAL_SEARCH_NOT_BRACKETED, (
            "Coarse maximum does not have admissible neighbors on both pressure sides."
        )
    higher = admissible[position - 1][1]
    lower = admissible[position + 1][1]
    bracket_low = min(lower.candidate.pressure_pa, higher.candidate.pressure_pa)
    bracket_high = max(lower.candidate.pressure_pa, higher.candidate.pressure_pa)

    cache: dict[float, StreamState] = {
        higher.candidate.pressure_pa: higher,
        lower.candidate.pressure_pa: lower,
        coarse_stream.candidate.pressure_pa: coarse_stream,
    }

    def objective(pressure: float) -> float:
        if pressure not in cache:
            stream, outcome, message = evaluate_stream(
                provider,
                upstream,
                pressure,
                discharge_coefficient,
                allowed_phases,
                entropy_tolerance,
            )
            if stream is None:
                raise ValueError(f"{outcome}: {message}")
            cache[pressure] = stream
        return cache[pressure].effective_mass_flux_kg_m2_s

    try:
        refined_pressure, _, iterations, bracket_width = golden_section_maximize(
            objective,
            bracket_low,
            bracket_high,
            float(search["refinement_pressure_bracket_tolerance_pa"]),
            int(search["refinement_max_iterations"]),
        )
        candidates = [
            coarse_stream,
            higher,
            lower,
            cache.get(refined_pressure),
        ]
        valid_candidates = [item for item in candidates if item is not None]
        best = sorted(
            valid_candidates,
            key=lambda stream: (
                -stream.effective_mass_flux_kg_m2_s,
                -stream.candidate.pressure_pa,
            ),
        )[0]
    except Exception as exc:
        return None, records, CRITICAL_REFINEMENT_FAILURE, (
            f"Critical refinement failed: {type(exc).__name__}: {exc}"
        )

    offset = float(search["peak_neighbor_relative_offset"])
    pressure_offset_pa = offset * p0
    neighbor_pressures = [
        best.candidate.pressure_pa - pressure_offset_pa,
        best.candidate.pressure_pa + pressure_offset_pa,
    ]
    neighbor_fluxes: list[float] = []
    for pressure in neighbor_pressures:
        if pressure <= 0.0 or pressure >= p0:
            continue
        try:
            neighbor_fluxes.append(objective(pressure))
        except Exception:
            continue
    if not neighbor_fluxes:
        prominence = 0.0
    else:
        prominence = (
            best.effective_mass_flux_kg_m2_s - max(neighbor_fluxes)
        ) / best.effective_mass_flux_kg_m2_s

    minimum_prominence = float(search["minimum_peak_prominence_relative"])
    minimum_distance = float(
        tolerances["minimum_critical_pressure_distance_from_search_bounds_pa"]
    )
    retained_low = admissible[-1][1].candidate.pressure_pa
    retained_high = admissible[0][1].candidate.pressure_pa
    if (
        prominence < minimum_prominence
        or best.candidate.pressure_pa - retained_low < minimum_distance
        or retained_high - best.candidate.pressure_pa < minimum_distance
    ):
        return None, records, CRITICAL_SEARCH_NOT_BRACKETED, (
            "Critical maximum does not satisfy locked prominence or interior-distance rules."
        )

    return (
        CriticalState(
            pressure_pa=best.candidate.pressure_pa,
            pressure_ratio=best.candidate.pressure_pa / p0,
            stream=best,
            coarse_index=coarse_index,
            coarse_neighbor_high_pressure_pa=higher.candidate.pressure_pa,
            coarse_neighbor_low_pressure_pa=lower.candidate.pressure_pa,
            refinement_iterations=iterations,
            final_bracket_width_pa=bracket_width,
            peak_prominence_relative=prominence,
            path_termination_outcome=termination_outcome,
            path_termination_pressure_pa=termination_pressure,
        ),
        records,
        None,
        "SUCCESS",
    )


def construct_result(
    inputs: ReferenceInput,
    upstream: UpstreamState,
    stream: StreamState,
    outcome: str,
    critical: CriticalState | None,
) -> ReferenceResult:
    effective_area = inputs.reference_area_m2 * inputs.opening_fraction
    mass = effective_area * stream.effective_mass_flux_kg_m2_s
    momentum = mass * stream.effective_velocity_m_s
    energy = mass * upstream.enthalpy_J_kg
    if not finite(mass, momentum, energy):
        return zero_result(
            inputs,
            CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE,
            "Nonfinite conservative transfer.",
            upstream=upstream,
            critical=critical,
        )
    candidate = stream.candidate
    return ReferenceResult(
        case_id=inputs.case_id,
        state_id=inputs.state_id,
        formal_outcome=outcome,
        formal_message=(
            "Independent unchoked isentropic reference evaluated."
            if outcome == SUCCESS_UNCHOKED
            else "Independent choked critical-state reference evaluated."
        ),
        upstream_pressure_pa=inputs.upstream_pressure_pa,
        upstream_temperature_K=inputs.upstream_temperature_K,
        back_pressure_pa=inputs.back_pressure_pa,
        evaluation_pressure_pa=candidate.pressure_pa,
        critical_pressure_pa=None if critical is None else critical.pressure_pa,
        critical_pressure_ratio=None if critical is None else critical.pressure_ratio,
        reference_area_m2=inputs.reference_area_m2,
        opening_fraction=inputs.opening_fraction,
        effective_area_m2=effective_area,
        discharge_coefficient=inputs.discharge_coefficient,
        upstream_density_kg_m3=upstream.density_kg_m3,
        upstream_enthalpy_J_kg=upstream.enthalpy_J_kg,
        upstream_entropy_J_kg_K=upstream.entropy_J_kg_K,
        upstream_phase=upstream.phase,
        candidate_temperature_K=candidate.temperature_K,
        candidate_density_kg_m3=candidate.density_kg_m3,
        candidate_enthalpy_J_kg=candidate.enthalpy_J_kg,
        candidate_entropy_J_kg_K=candidate.entropy_J_kg_K,
        candidate_phase=candidate.phase,
        kinetic_energy_head_J_kg=stream.kinetic_energy_head_J_kg,
        ideal_velocity_m_s=stream.ideal_velocity_m_s,
        effective_velocity_m_s=stream.effective_velocity_m_s,
        ideal_mass_flux_kg_m2_s=stream.ideal_mass_flux_kg_m2_s,
        effective_mass_flux_kg_m2_s=stream.effective_mass_flux_kg_m2_s,
        mass_transfer_outward_kg_s=mass,
        momentum_stream_transfer_outward_N=momentum,
        energy_transfer_outward_W=energy,
    )


def evaluate_case(
    contract: dict[str, Any],
    provider: PropertyProvider,
    row: dict[str, Any],
    *,
    critical_cache: dict[tuple[str, float], CriticalState],
    candidate_records: list[dict[str, Any]],
) -> ReferenceResult:
    inputs = build_input(contract, row, provider)
    numeric = (
        inputs.upstream_pressure_pa,
        inputs.upstream_temperature_K,
        inputs.back_pressure_pa,
        inputs.reference_area_m2,
        inputs.opening_fraction,
        inputs.discharge_coefficient,
    )
    if not finite(*numeric):
        return zero_result(inputs, NONFINITE_INPUT, "One or more numeric inputs are nonfinite.")
    if inputs.reference_area_m2 <= 0.0:
        return zero_result(
            inputs, NONPOSITIVE_REFERENCE_AREA, "Reference area must be positive."
        )
    if not 0.0 <= inputs.opening_fraction <= 1.0:
        return zero_result(
            inputs,
            OPENING_OUTSIDE_UNIT_INTERVAL,
            "Opening fraction must be in [0,1].",
        )
    if inputs.discharge_coefficient <= 0.0:
        return zero_result(
            inputs,
            NONPOSITIVE_DISCHARGE_COEFFICIENT,
            "Discharge coefficient must be positive.",
        )
    if inputs.back_pressure_pa > inputs.upstream_pressure_pa:
        return zero_result(
            inputs,
            REVERSE_PRESSURE_NOT_SUPPORTED,
            "Back pressure exceeds upstream pressure.",
        )

    family = state_family(contract, inputs.state_id)
    allowed = {normalize_phase(value) for value in family["allowed_normalized_phases"]}
    try:
        upstream = provider.upstream_snapshot(
            inputs.upstream_pressure_pa, inputs.upstream_temperature_K
        )
    except Exception as exc:
        return zero_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            f"Upstream property evaluation failed: {type(exc).__name__}: {exc}",
        )
    if (
        not finite(
            upstream.density_kg_m3,
            upstream.enthalpy_J_kg,
            upstream.entropy_J_kg_K,
        )
        or upstream.density_kg_m3 <= 0.0
    ):
        return zero_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            "Upstream state contains nonfinite or nonpositive properties.",
            upstream=upstream,
        )
    if normalize_phase(upstream.phase) not in allowed:
        return zero_result(
            inputs,
            UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE,
            f"Upstream phase {upstream.phase!r} is outside {sorted(allowed)}.",
            upstream=upstream,
        )

    if row.get("execution_mode") == "synthetic_guard_unit_test":
        if row["case_id"] == "G-04_NONPOSITIVE_KINETIC_ENERGY_HEAD":
            return zero_result(
                inputs,
                NONPOSITIVE_KINETIC_ENERGY_HEAD,
                "Synthetic nonpositive kinetic-head guard retained.",
                upstream=upstream,
            )
        if row["case_id"] == "G-05_CRITICAL_SEARCH_NOT_BRACKETED":
            return zero_result(
                inputs,
                CRITICAL_SEARCH_NOT_BRACKETED,
                "Synthetic unbracketed-search guard retained.",
                upstream=upstream,
            )

    effective_area = inputs.reference_area_m2 * inputs.opening_fraction
    if effective_area == 0.0:
        return zero_result(
            inputs,
            SUCCESS_CLOSED,
            "Closed-element identity retained exactly.",
            upstream=upstream,
        )
    if inputs.back_pressure_pa == inputs.upstream_pressure_pa:
        return zero_result(
            inputs,
            SUCCESS_ZERO_PRESSURE_DROP,
            "Zero-pressure-drop identity retained exactly.",
            upstream=upstream,
        )

    entropy_tolerance = float(
        contract["acceptance_tolerances"]["isentropic_entropy_absolute_J_kg_K"]
    )
    critical: CriticalState | None = None
    if bool(family["critical_state_search_required"]):
        cache_key = (inputs.state_id, inputs.discharge_coefficient)
        critical = critical_cache.get(cache_key)
        if critical is None:
            critical, records, outcome, message = critical_search(
                contract,
                provider,
                upstream,
                allowed,
                inputs.discharge_coefficient,
            )
            for record in records:
                record["state_id"] = inputs.state_id
                record["discharge_coefficient"] = inputs.discharge_coefficient
            candidate_records.extend(records)
            if critical is None:
                return zero_result(
                    inputs,
                    outcome or CRITICAL_SEARCH_NOT_BRACKETED,
                    message,
                    upstream=upstream,
                )
            critical_cache[cache_key] = critical

        tolerance = float(
            contract["critical_state_search"][
                "critical_pressure_classification_tolerance_pa"
            ]
        )
        if inputs.back_pressure_pa <= critical.pressure_pa + tolerance:
            return construct_result(
                inputs, upstream, critical.stream, SUCCESS_CHOKED, critical
            )

    stream, outcome, message = evaluate_stream(
        provider,
        upstream,
        inputs.back_pressure_pa,
        inputs.discharge_coefficient,
        allowed,
        entropy_tolerance,
    )
    if stream is None:
        return zero_result(
            inputs,
            outcome or SINGLE_PHASE_PATH_SCOPE_FAILURE,
            message,
            upstream=upstream,
            critical=critical,
        )
    return construct_result(inputs, upstream, stream, SUCCESS_UNCHOKED, critical)


def evaluate_contract(
    contract: dict[str, Any],
    provider: PropertyProvider | None = None,
) -> tuple[list[ReferenceResult], list[dict[str, Any]], dict[str, CriticalState]]:
    provider = provider or CoolPropProvider()
    critical_cache: dict[tuple[str, float], CriticalState] = {}
    candidate_records: list[dict[str, Any]] = []
    results = [
        evaluate_case(
            contract,
            provider,
            row,
            critical_cache=critical_cache,
            candidate_records=candidate_records,
        )
        for row in contract["benchmark_cases"]
    ]
    critical_by_key = {
        f"{state_id}|Cd={coefficient:g}": critical
        for (state_id, coefficient), critical in critical_cache.items()
    }
    return results, candidate_records, critical_by_key


def relative_error(actual: float, expected: float) -> float:
    scale = max(abs(expected), 1e-300)
    return abs(actual - expected) / scale


def locked_checks(
    contract: dict[str, Any],
    results: list[ReferenceResult],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = {result.case_id: result for result in results}
    tolerances = contract["acceptance_tolerances"]
    expected_outcomes = {
        row["case_id"]: row["expected_outcome"] for row in contract["benchmark_cases"]
    }
    outcome_matches = {
        case_id: by_id[case_id].formal_outcome == expected
        for case_id, expected in expected_outcomes.items()
    }

    b1 = by_id["B1-03_SMALL_DROP_RECOVERS_B0_LIMIT"]
    rho0 = float(b1.upstream_density_kg_m3 or math.nan)
    h0 = float(b1.upstream_enthalpy_J_kg or math.nan)
    dp = b1.upstream_pressure_pa - b1.back_pressure_pa
    area = b1.effective_area_m2
    cd = b1.discharge_coefficient
    b0_velocity = cd * math.sqrt(2.0 * dp / rho0)
    b0_mass = rho0 * area * b0_velocity
    b0_momentum = b0_mass * b0_velocity
    b0_energy = b0_mass * h0
    b0_rows = [
        {
            "measure": "mass_flow",
            "reference_value": b1.mass_transfer_outward_kg_s,
            "b0_value": b0_mass,
            "relative_error": relative_error(b1.mass_transfer_outward_kg_s, b0_mass),
            "tolerance": float(tolerances["B0_limit_mass_flow_relative"]),
        },
        {
            "measure": "effective_velocity",
            "reference_value": b1.effective_velocity_m_s,
            "b0_value": b0_velocity,
            "relative_error": relative_error(b1.effective_velocity_m_s, b0_velocity),
            "tolerance": float(tolerances["B0_limit_effective_velocity_relative"]),
        },
        {
            "measure": "momentum_stream",
            "reference_value": b1.momentum_stream_transfer_outward_N,
            "b0_value": b0_momentum,
            "relative_error": relative_error(
                b1.momentum_stream_transfer_outward_N, b0_momentum
            ),
            "tolerance": float(tolerances["B0_limit_momentum_transfer_relative"]),
        },
        {
            "measure": "energy",
            "reference_value": b1.energy_transfer_outward_W,
            "b0_value": b0_energy,
            "relative_error": relative_error(b1.energy_transfer_outward_W, b0_energy),
            "tolerance": float(tolerances["B0_limit_energy_transfer_relative"]),
        },
    ]
    for row in b0_rows:
        row["passed"] = row["relative_error"] <= row["tolerance"]

    high_pb = by_id["B1-04A_UNCHOKED_HIGH_BACK_PRESSURE"]
    low_pb = by_id["B1-04B_UNCHOKED_LOWER_BACK_PRESSURE"]
    ordering_margin = (
        low_pb.mass_transfer_outward_kg_s - high_pb.mass_transfer_outward_kg_s
    ) / max(high_pb.mass_transfer_outward_kg_s, 1e-300)
    ordering_passed = ordering_margin >= float(
        tolerances["minimum_unchoked_mass_flow_ordering_margin_relative"]
    )

    plateau_a = by_id["B1-06A_BELOW_CRITICAL_PLATEAU_HIGH"]
    plateau_b = by_id["B1-06B_BELOW_CRITICAL_PLATEAU_LOW"]
    plateau_relative = relative_error(
        plateau_a.mass_transfer_outward_kg_s,
        plateau_b.mass_transfer_outward_kg_s,
    )
    plateau_passed = plateau_relative <= float(
        tolerances["below_critical_plateau_relative"]
    )

    area_low = by_id["B1-07A_AREA_SCALING_LOW"]
    area_high = by_id["B1-07B_AREA_SCALING_HIGH"]
    area_ratio = area_high.mass_transfer_outward_kg_s / area_low.mass_transfer_outward_kg_s
    area_passed = abs(area_ratio - 2.0) <= float(
        tolerances["scaling_ratio_absolute"]
    )

    cd_low = by_id["B1-08A_CD_SCALING_LOW"]
    cd_high = by_id["B1-08B_CD_SCALING_HIGH"]
    cd_ratio = cd_high.mass_transfer_outward_kg_s / cd_low.mass_transfer_outward_kg_s
    cd_passed = abs(cd_ratio - 2.0) <= float(tolerances["scaling_ratio_absolute"])
    critical_ratio_relative = relative_error(
        float(cd_high.critical_pressure_pa or math.nan),
        float(cd_low.critical_pressure_pa or math.nan),
    )
    cd_pressure_passed = critical_ratio_relative <= float(
        tolerances["critical_pressure_Cd_independence_relative"]
    )

    check_rows = [
        {
            "check": "expected_formal_outcomes",
            "value": sum(outcome_matches.values()),
            "target": len(outcome_matches),
            "passed": all(outcome_matches.values()),
        },
        {
            "check": "b0_limiting_comparison",
            "value": max(row["relative_error"] for row in b0_rows),
            "target": "measure-specific locked tolerances",
            "passed": all(row["passed"] for row in b0_rows),
        },
        {
            "check": "unchoked_back_pressure_ordering",
            "value": ordering_margin,
            "target": tolerances[
                "minimum_unchoked_mass_flow_ordering_margin_relative"
            ],
            "passed": ordering_passed,
        },
        {
            "check": "below_critical_plateau",
            "value": plateau_relative,
            "target": tolerances["below_critical_plateau_relative"],
            "passed": plateau_passed,
        },
        {
            "check": "area_scaling",
            "value": area_ratio,
            "target": 2.0,
            "passed": area_passed,
        },
        {
            "check": "Cd_scaling",
            "value": cd_ratio,
            "target": 2.0,
            "passed": cd_passed,
        },
        {
            "check": "critical_pressure_Cd_independence",
            "value": critical_ratio_relative,
            "target": tolerances["critical_pressure_Cd_independence_relative"],
            "passed": cd_pressure_passed,
        },
    ]
    summary = {
        "all_expected_outcomes_match": all(outcome_matches.values()),
        "outcome_matches": outcome_matches,
        "b0_limit_passed": all(row["passed"] for row in b0_rows),
        "unchoked_ordering_margin_relative": ordering_margin,
        "unchoked_ordering_passed": ordering_passed,
        "below_critical_plateau_relative": plateau_relative,
        "below_critical_plateau_passed": plateau_passed,
        "area_scaling_ratio": area_ratio,
        "area_scaling_passed": area_passed,
        "Cd_scaling_ratio": cd_ratio,
        "Cd_scaling_passed": cd_passed,
        "critical_pressure_Cd_relative_difference": critical_ratio_relative,
        "critical_pressure_Cd_independence_passed": cd_pressure_passed,
        "all_locked_checks_passed": all(bool(row["passed"]) for row in check_rows),
    }
    return b0_rows + check_rows, summary


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"No rows for {path}")
    fieldnames: list[str] = []
    for row in values:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(values)


def plot_provenance_text(
    case_name: str,
    backend_version: str,
    source_git_sha: str,
) -> str:
    return (
        f"case={case_name} | "
        "model=U3 B1 single-phase isentropic critical-state reference | "
        f"backend=CoolProp | version={backend_version} | "
        f"source={source_git_sha[:12]}"
    )


def write_plots(
    output_dir: Path,
    candidate_records: list[dict[str, Any]],
    sweep_rows: list[dict[str, Any]],
    *,
    backend_version: str,
    source_git_sha: str,
) -> None:
    import matplotlib.pyplot as plt

    gas = [
        row
        for row in candidate_records
        if row.get("state_id") == "GAS_CRITICAL"
        and float(row.get("discharge_coefficient", 0.0)) == 0.8
        and row.get("admissible")
    ]
    plt.figure(figsize=(8, 5))
    plt.plot(
        [float(row["pressure_pa"]) / 1e6 for row in gas],
        [float(row["effective_mass_flux_kg_m2_s"]) for row in gas],
    )
    plt.xlabel("Candidate pressure [MPa]")
    plt.ylabel("Effective mass flux [kg m$^{-2}$ s$^{-1}$]")
    plt.title(
        "U3 B1 single-phase mass-flux path\n"
        + plot_provenance_text(
            "GAS_CRITICAL / Cd=0.8", backend_version, source_git_sha
        ),
        fontsize=9,
    )
    plt.tight_layout()
    plt.savefig(output_dir / "mass_flux_vs_pressure.png", dpi=160)
    plt.close()

    valid_sweep = [row for row in sweep_rows if row["formal_outcome"].startswith("SUCCESS_")]
    plt.figure(figsize=(8, 5))
    plt.plot(
        [float(row["back_pressure_pa"]) / 1e6 for row in valid_sweep],
        [float(row["mass_transfer_outward_kg_s"]) for row in valid_sweep],
    )
    plt.xlabel("Back pressure [MPa]")
    plt.ylabel("Mass flow [kg/s]")
    plt.title(
        "U3 B1 back-pressure response\n"
        + plot_provenance_text(
            "GAS_CRITICAL sweep / Cd=0.8", backend_version, source_git_sha
        ),
        fontsize=9,
    )
    plt.tight_layout()
    plt.savefig(output_dir / "back_pressure_response.png", dpi=160)
    plt.close()


def artifact_manifest(output_dir: Path) -> None:
    entries = []
    for path in sorted(output_dir.iterdir()):
        if path.name == "artifact_sha256.txt" or not path.is_file():
            continue
        entries.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (output_dir / "artifact_sha256.txt").write_text(
        "\n".join(entries) + "\n", encoding="utf-8"
    )


def write_artifact(
    contract_path: Path,
    output_dir: Path,
    *,
    source_git_sha: str,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    provider = CoolPropProvider()
    results, candidate_records, criticals = evaluate_contract(contract, provider)
    check_rows, checks = locked_checks(contract, results)
    output_dir.mkdir(parents=True, exist_ok=True)

    contract_copy = output_dir / "benchmark_contract.json"
    contract_copy.write_text(
        json.dumps(contract, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    write_csv(output_dir / "candidate_states.csv", candidate_records)

    critical_payload = {
        key: {
            "pressure_pa": value.pressure_pa,
            "pressure_ratio": value.pressure_ratio,
            "effective_mass_flux_kg_m2_s": value.stream.effective_mass_flux_kg_m2_s,
            "ideal_mass_flux_kg_m2_s": value.stream.ideal_mass_flux_kg_m2_s,
            "temperature_K": value.stream.candidate.temperature_K,
            "density_kg_m3": value.stream.candidate.density_kg_m3,
            "phase": value.stream.candidate.phase,
            "coarse_index": value.coarse_index,
            "coarse_neighbor_high_pressure_pa": value.coarse_neighbor_high_pressure_pa,
            "coarse_neighbor_low_pressure_pa": value.coarse_neighbor_low_pressure_pa,
            "refinement_iterations": value.refinement_iterations,
            "final_bracket_width_pa": value.final_bracket_width_pa,
            "peak_prominence_relative": value.peak_prominence_relative,
            "path_termination_outcome": value.path_termination_outcome,
            "path_termination_pressure_pa": value.path_termination_pressure_pa,
        }
        for key, value in criticals.items()
    }
    (output_dir / "critical_state_summary.json").write_text(
        json.dumps(critical_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    sweep_rows: list[dict[str, Any]] = []
    family = state_family(contract, "GAS_CRITICAL")
    geometry = contract["geometry_and_coefficients"]
    base_row = {
        "case_id": "SWEEP",
        "state_id": "GAS_CRITICAL",
        "opening_fraction": geometry["base_opening_fraction"],
        "discharge_coefficient": geometry["base_discharge_coefficient"],
    }
    critical_cache: dict[tuple[str, float], CriticalState] = {}
    local_candidates: list[dict[str, Any]] = []
    for index in range(101):
        ratio = 1.0 - 0.95 * index / 100
        row = dict(base_row)
        row["case_id"] = f"SWEEP_{index:03d}"
        row["back_pressure_pa"] = float(family["pressure_pa"]) * ratio
        result = evaluate_case(
            contract,
            provider,
            row,
            critical_cache=critical_cache,
            candidate_records=local_candidates,
        )
        sweep_rows.append(asdict(result))
    write_csv(output_dir / "back_pressure_sweep.csv", sweep_rows)

    b0_rows = [row for row in check_rows if row.get("measure")]
    check_only = [row for row in check_rows if row.get("check")]
    write_csv(output_dir / "b0_limiting_comparison.csv", b0_rows)
    write_csv(output_dir / "scaling_checks.csv", check_only)
    write_csv(
        output_dir / "guard_outcomes.csv",
        [
            asdict(result)
            for result in results
            if not result.formal_outcome.startswith("SUCCESS_")
        ],
    )
    write_csv(
        output_dir / "conservative_transfer_table.csv",
        [asdict(result) for result in results],
    )
    write_plots(
        output_dir,
        candidate_records,
        sweep_rows,
        backend_version=provider.version,
        source_git_sha=source_git_sha,
    )

    expected_files_without_junit = {
        name
        for name in contract["required_artifacts"]
        if not name.endswith("_junit.xml")
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "scope": contract["scope"],
        "issue": contract["issue"],
        "case_count": len(results),
        "physical_case_count": sum(
            1
            for row in contract["benchmark_cases"]
            if row.get("execution_mode") != "synthetic_guard_unit_test"
            and not row["case_id"].startswith("G-")
        ),
        "guard_case_count": sum(
            1 for row in contract["benchmark_cases"] if row["case_id"].startswith("G-")
        ),
        "success_count": sum(result.succeeded for result in results),
        "guard_count": sum(not result.succeeded for result in results),
        "critical_state_keys": sorted(criticals),
        "critical_state_summary": critical_payload,
        **checks,
        "expected_output_files_without_junit": sorted(expected_files_without_junit),
        "u3_b1_contract_locked": True,
        "u3_b1_reference_implemented": True,
        "u3_b1_adapter_implemented": False,
        "u3_b1_component_benchmark_execution_complete": False,
        "u3_b1_component_benchmark_accepted": False,
        "physical_discharge_boundary_approved": False,
        "two_phase_critical_discharge_accuracy_approved": False,
        "integrated_blowdown_model_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
        "provenance": {
            "source_git_sha": source_git_sha,
            "checkout_git_sha": os.environ.get("GITHUB_SHA", ""),
            "git_status_porcelain": "",
            "property_backend": contract["property_backend"]["name"],
            "property_backend_version": provider.version,
            "python_version": platform.python_version(),
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report_lines = [
        "# Stage 7 U3 B1 independent single-phase critical-state reference",
        "",
        f"- cases: {summary['case_count']}",
        f"- successes / guards: {summary['success_count']} / {summary['guard_count']}",
        f"- all expected outcomes match: {summary['all_expected_outcomes_match']}",
        f"- all locked checks passed: {summary['all_locked_checks_passed']}",
        "",
        "## Critical states",
        "",
    ]
    for key, value in critical_payload.items():
        report_lines.extend(
            [
                f"### {key}",
                "",
                f"- pressure: {value['pressure_pa']:.9g} Pa",
                f"- pressure ratio: {value['pressure_ratio']:.12g}",
                f"- effective mass flux: {value['effective_mass_flux_kg_m2_s']:.12g} kg/m2/s",
                f"- phase: {value['phase']}",
                "",
            ]
        )
    report_lines.extend(
        [
            "## Approval boundary",
            "",
            "This artifact implements the independent B1 reference only. "
            "Adapter comparison, two-phase critical discharge, finite-pipe coupling, "
            "physical validation, design use, and production activation remain unapproved.",
            "",
        ]
    )
    (output_dir / "report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )
    artifact_manifest(output_dir)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()
    summary = write_artifact(
        args.contract,
        args.output_dir,
        source_git_sha=args.source_git_sha,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["all_expected_outcomes_match"]:
        raise SystemExit("Expected formal outcomes did not all match")
    if not summary["all_locked_checks_passed"]:
        raise SystemExit("One or more locked B1 reference checks failed")


if __name__ == "__main__":
    main()
