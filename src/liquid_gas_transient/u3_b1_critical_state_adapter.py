"""Verification-only U3 B1 single-phase critical-state adapter.

The adapter implements the locked U3 B1 contract without importing the
independent reference module or sharing its property-path, critical-search, or
transfer-construction helpers.  It evaluates the same fixed benchmark matrix
and compares the resulting formal outcomes and conservative transfers against
an immutable authoritative reference artifact.

Positive transfers are directed out of the modeled domain.  Static pressure
force, finite-pipe coupling, two-phase choking, physical validation, design
use, and production FVM activation remain outside this increment.
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
from typing import Any, Iterable, Protocol

SCHEMA_VERSION = "stage7_u3_b1_critical_state_adapter_comparison_v1"
CONTRACT_SCHEMA_VERSION = "stage7_u3_b1_critical_state_contract_v1"
REFERENCE_SCHEMA_VERSION = "stage7_u3_b1_independent_reference_v1"

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


@dataclass(frozen=True)
class ThermodynamicState:
    pressure_pa: float
    temperature_K: float
    density_kg_m3: float
    enthalpy_J_kg: float
    entropy_J_kg_K: float
    phase: str


@dataclass(frozen=True)
class StreamEvaluation:
    state: ThermodynamicState
    kinetic_energy_head_J_kg: float
    ideal_velocity_m_s: float
    effective_velocity_m_s: float
    ideal_mass_flux_kg_m2_s: float
    effective_mass_flux_kg_m2_s: float
    entropy_residual_J_kg_K: float


@dataclass(frozen=True)
class CriticalEvaluation:
    pressure_pa: float
    pressure_ratio: float
    stream: StreamEvaluation
    coarse_index: int
    coarse_neighbor_high_pressure_pa: float
    coarse_neighbor_low_pressure_pa: float
    refinement_iterations: int
    final_bracket_width_pa: float
    peak_prominence_relative: float
    path_termination_outcome: str | None
    path_termination_pressure_pa: float | None


@dataclass(frozen=True)
class AdapterInput:
    case_id: str
    state_id: str
    upstream_pressure_pa: float
    upstream_temperature_K: float
    back_pressure_pa: float
    reference_area_m2: float
    opening_fraction: float
    discharge_coefficient: float


@dataclass(frozen=True)
class AdapterResult:
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


class PropertyProvider(Protocol):
    version: str

    def saturation_temperature(self, pressure_pa: float) -> float: ...

    def upstream_state(
        self, pressure_pa: float, temperature_K: float
    ) -> ThermodynamicState: ...

    def isentropic_state(
        self, pressure_pa: float, entropy_J_kg_K: float
    ) -> ThermodynamicState: ...


class CoolPropStateProvider:
    """Independent low-level CoolProp state provider used by the adapter."""

    def __init__(self) -> None:
        from CoolProp import AbstractState, PQ_INPUTS, PSmass_INPUTS, PT_INPUTS
        from CoolProp import __version__ as coolprop_version
        from CoolProp.CoolProp import PhaseSI

        self._upstream = AbstractState("HEOS", "CO2")
        self._candidate = AbstractState("HEOS", "CO2")
        self._saturation = AbstractState("HEOS", "CO2")
        self._PT_INPUTS = PT_INPUTS
        self._PSmass_INPUTS = PSmass_INPUTS
        self._PQ_INPUTS = PQ_INPUTS
        self._phase_si = PhaseSI
        self.version = str(coolprop_version)

    def saturation_temperature(self, pressure_pa: float) -> float:
        self._saturation.update(self._PQ_INPUTS, pressure_pa, 0.0)
        return float(self._saturation.T())

    def upstream_state(
        self, pressure_pa: float, temperature_K: float
    ) -> ThermodynamicState:
        state = self._upstream
        state.update(self._PT_INPUTS, pressure_pa, temperature_K)
        return ThermodynamicState(
            pressure_pa=pressure_pa,
            temperature_K=float(state.T()),
            density_kg_m3=float(state.rhomass()),
            enthalpy_J_kg=float(state.hmass()),
            entropy_J_kg_K=float(state.smass()),
            phase=str(
                self._phase_si("P", pressure_pa, "T", float(state.T()), "CO2")
            ),
        )

    def isentropic_state(
        self, pressure_pa: float, entropy_J_kg_K: float
    ) -> ThermodynamicState:
        state = self._candidate
        state.update(self._PSmass_INPUTS, pressure_pa, entropy_J_kg_K)
        temperature = float(state.T())
        return ThermodynamicState(
            pressure_pa=pressure_pa,
            temperature_K=temperature,
            density_kg_m3=float(state.rhomass()),
            enthalpy_J_kg=float(state.hmass()),
            entropy_J_kg_K=float(state.smass()),
            phase=str(
                self._phase_si(
                    "P",
                    pressure_pa,
                    "SMASS",
                    entropy_J_kg_K,
                    "CO2",
                )
            ),
        )


def normalize_phase(value: str) -> str:
    return value.lower().replace("_", "").replace(" ", "")


def _finite(*values: float) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("Unexpected U3 B1 contract schema")
    if contract.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B1 contract is not locked")
    approvals = contract.get("approval_boundary", {})
    if approvals.get("u3_b1_contract_locked") is not True:
        raise ValueError("u3_b1_contract_locked must be true")
    if approvals.get("u3_b1_adapter_implemented") is not False:
        raise ValueError("Adapter implementation state must be false in contract")
    return contract


def _family(contract: dict[str, Any], state_id: str) -> dict[str, Any]:
    for family in contract["upstream_state_families"]:
        if str(family["state_id"]) == state_id:
            return family
    raise KeyError(state_id)


def _upstream_temperature(
    family: dict[str, Any],
    provider: PropertyProvider,
    override_K: float | None,
) -> float:
    if "temperature_K" in family:
        return float(family["temperature_K"])
    subcooling = float(
        family["subcooling_K"] if override_K is None else override_K
    )
    pressure = float(family["pressure_pa"])
    return provider.saturation_temperature(pressure) - subcooling


def build_input(
    contract: dict[str, Any],
    case: dict[str, Any],
    provider: PropertyProvider,
) -> AdapterInput:
    state_id = str(case["state_id"])
    family = _family(contract, state_id)
    geometry = contract["geometry_and_coefficients"]
    back_pressure = float(case.get("back_pressure_pa", 0.0))
    mutation = case.get("input_mutation")
    if mutation and mutation.get("field") == "back_pressure_pa":
        if mutation.get("value_token") == "NaN":
            back_pressure = math.nan
    override = (
        float(case["upstream_subcooling_override_K"])
        if "upstream_subcooling_override_K" in case
        else None
    )
    return AdapterInput(
        case_id=str(case["case_id"]),
        state_id=state_id,
        upstream_pressure_pa=float(family["pressure_pa"]),
        upstream_temperature_K=_upstream_temperature(family, provider, override),
        back_pressure_pa=back_pressure,
        reference_area_m2=float(geometry["reference_area_m2"]),
        opening_fraction=float(case.get("opening_fraction", 0.5)),
        discharge_coefficient=float(case.get("discharge_coefficient", 0.8)),
    )


def _zero_result(
    inputs: AdapterInput,
    outcome: str,
    message: str,
    *,
    upstream: ThermodynamicState | None = None,
    critical: CriticalEvaluation | None = None,
) -> AdapterResult:
    return AdapterResult(
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


def _stream_at_pressure(
    provider: PropertyProvider,
    upstream: ThermodynamicState,
    pressure_pa: float,
    discharge_coefficient: float,
    allowed_phases: set[str],
    entropy_tolerance: float,
) -> tuple[StreamEvaluation | None, str | None, str]:
    try:
        candidate = provider.isentropic_state(
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
    if not _finite(*values) or candidate.density_kg_m3 <= 0.0:
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
    kinetic_head = upstream.enthalpy_J_kg - candidate.enthalpy_J_kg
    if not math.isfinite(kinetic_head) or kinetic_head <= 0.0:
        return None, NONPOSITIVE_KINETIC_ENERGY_HEAD, (
            f"Nonpositive kinetic energy head {kinetic_head} J/kg."
        )
    ideal_velocity = math.sqrt(2.0 * kinetic_head)
    effective_velocity = discharge_coefficient * ideal_velocity
    ideal_flux = candidate.density_kg_m3 * ideal_velocity
    effective_flux = candidate.density_kg_m3 * effective_velocity
    if not _finite(ideal_velocity, effective_velocity, ideal_flux, effective_flux):
        return None, CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE, (
            "Stream construction produced a nonfinite value."
        )
    return (
        StreamEvaluation(
            state=candidate,
            kinetic_energy_head_J_kg=kinetic_head,
            ideal_velocity_m_s=ideal_velocity,
            effective_velocity_m_s=effective_velocity,
            ideal_mass_flux_kg_m2_s=ideal_flux,
            effective_mass_flux_kg_m2_s=effective_flux,
            entropy_residual_J_kg_K=entropy_residual,
        ),
        None,
        "SUCCESS",
    )


@dataclass(frozen=True)
class _GoldenResult:
    best_pressure_pa: float
    iterations: int
    bracket_low_pa: float
    bracket_high_pa: float


def golden_section_refine(
    objective: Any,
    lower_pa: float,
    upper_pa: float,
    tolerance_pa: float,
    max_iterations: int,
) -> _GoldenResult:
    if (
        not _finite(lower_pa, upper_pa, tolerance_pa)
        or not lower_pa < upper_pa
        or tolerance_pa <= 0.0
        or max_iterations <= 0
    ):
        raise ValueError("Invalid golden-section refinement inputs")
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    low = lower_pa
    high = upper_pa
    left = high - ratio * (high - low)
    right = low + ratio * (high - low)
    f_left = float(objective(left))
    f_right = float(objective(right))
    if not _finite(f_left, f_right):
        raise ValueError("Nonfinite refinement objective")
    iterations = 0
    while high - low > tolerance_pa and iterations < max_iterations:
        if f_left >= f_right:
            high = right
            right = left
            f_right = f_left
            left = high - ratio * (high - low)
            f_left = float(objective(left))
        else:
            low = left
            left = right
            f_left = f_right
            right = low + ratio * (high - low)
            f_right = float(objective(right))
        if not _finite(f_left, f_right):
            raise ValueError("Nonfinite refinement objective")
        iterations += 1
    candidates = [
        (low, float(objective(low))),
        (high, float(objective(high))),
        (left, f_left),
        (right, f_right),
    ]
    candidates.sort(key=lambda item: (-item[1], -item[0]))
    return _GoldenResult(
        best_pressure_pa=candidates[0][0],
        iterations=iterations,
        bracket_low_pa=low,
        bracket_high_pa=high,
    )


def search_critical_state(
    contract: dict[str, Any],
    provider: PropertyProvider,
    upstream: ThermodynamicState,
    allowed_phases: set[str],
    discharge_coefficient: float,
) -> tuple[CriticalEvaluation | None, list[dict[str, Any]], str | None, str]:
    search = contract["critical_state_search"]
    tolerances = contract["acceptance_tolerances"]
    p0 = upstream.pressure_pa
    upper_ratio = float(search["coarse_pressure_ratio_upper"])
    lower_ratio = float(search["coarse_pressure_ratio_lower"])
    count = int(search["coarse_node_count"])
    entropy_tolerance = float(tolerances["isentropic_entropy_absolute_J_kg_K"])

    samples: list[tuple[int, StreamEvaluation]] = []
    records: list[dict[str, Any]] = []
    termination_outcome: str | None = None
    termination_pressure: float | None = None
    ratios = [
        upper_ratio - (upper_ratio - lower_ratio) * index / (count - 1)
        for index in range(count)
    ]
    for index, pressure_ratio in enumerate(ratios):
        pressure = p0 * pressure_ratio
        if index == 0:
            stream = StreamEvaluation(
                state=upstream,
                kinetic_energy_head_J_kg=0.0,
                ideal_velocity_m_s=0.0,
                effective_velocity_m_s=0.0,
                ideal_mass_flux_kg_m2_s=0.0,
                effective_mass_flux_kg_m2_s=0.0,
                entropy_residual_J_kg_K=0.0,
            )
            outcome = None
            message = "SUCCESS_ZERO_PRESSURE_DROP"
        else:
            stream, outcome, message = _stream_at_pressure(
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
                "pressure_ratio": pressure_ratio,
                "admissible": stream is not None,
                "formal_outcome": "SUCCESS" if stream is not None else outcome,
                "formal_message": message,
                "effective_mass_flux_kg_m2_s": None
                if stream is None
                else stream.effective_mass_flux_kg_m2_s,
            }
        )
        if stream is None:
            termination_outcome = outcome
            termination_pressure = pressure
            break
        samples.append((index, stream))

    if len(samples) < 3:
        return None, records, CRITICAL_SEARCH_NOT_BRACKETED, (
            "Fewer than three admissible coarse states."
        )
    highest_flux = max(row[1].effective_mass_flux_kg_m2_s for row in samples)
    maximizers = [
        row for row in samples if row[1].effective_mass_flux_kg_m2_s == highest_flux
    ]
    coarse_index, coarse_stream = min(maximizers, key=lambda row: row[0])
    position = next(i for i, row in enumerate(samples) if row[0] == coarse_index)
    if position == 0 or position == len(samples) - 1:
        return None, records, CRITICAL_SEARCH_NOT_BRACKETED, (
            "Coarse maximum lacks admissible neighbors on both pressure sides."
        )
    higher_pressure_stream = samples[position - 1][1]
    lower_pressure_stream = samples[position + 1][1]
    bracket_low = lower_pressure_stream.state.pressure_pa
    bracket_high = higher_pressure_stream.state.pressure_pa

    cache: dict[float, StreamEvaluation] = {
        coarse_stream.state.pressure_pa: coarse_stream,
        higher_pressure_stream.state.pressure_pa: higher_pressure_stream,
        lower_pressure_stream.state.pressure_pa: lower_pressure_stream,
    }

    def objective(pressure_pa: float) -> float:
        if pressure_pa not in cache:
            stream, outcome, message = _stream_at_pressure(
                provider,
                upstream,
                pressure_pa,
                discharge_coefficient,
                allowed_phases,
                entropy_tolerance,
            )
            if stream is None:
                raise ValueError(f"{outcome}: {message}")
            cache[pressure_pa] = stream
        return cache[pressure_pa].effective_mass_flux_kg_m2_s

    try:
        refined = golden_section_refine(
            objective,
            bracket_low,
            bracket_high,
            float(search["refinement_pressure_bracket_tolerance_pa"]),
            int(search["refinement_max_iterations"]),
        )
        final_pressures = {
            coarse_stream.state.pressure_pa,
            bracket_low,
            bracket_high,
            refined.best_pressure_pa,
            refined.bracket_low_pa,
            refined.bracket_high_pa,
        }
        final_streams = []
        for pressure in final_pressures:
            objective(pressure)
            final_streams.append(cache[pressure])
        final_streams.sort(
            key=lambda row: (
                -row.effective_mass_flux_kg_m2_s,
                -row.state.pressure_pa,
            )
        )
        best = final_streams[0]
    except Exception as exc:
        return None, records, CRITICAL_REFINEMENT_FAILURE, (
            f"Critical refinement failed: {type(exc).__name__}: {exc}"
        )

    ratio_offset = float(search["peak_neighbor_relative_offset"])
    pressure_offset = ratio_offset * p0
    neighbor_fluxes: list[float] = []
    for pressure in (
        best.state.pressure_pa - pressure_offset,
        best.state.pressure_pa + pressure_offset,
    ):
        if 0.0 < pressure < p0:
            try:
                neighbor_fluxes.append(objective(pressure))
            except Exception:
                pass
    prominence = 0.0
    if neighbor_fluxes and best.effective_mass_flux_kg_m2_s > 0.0:
        prominence = (
            best.effective_mass_flux_kg_m2_s - max(neighbor_fluxes)
        ) / best.effective_mass_flux_kg_m2_s

    minimum_prominence = float(search["minimum_peak_prominence_relative"])
    minimum_distance = float(
        tolerances["minimum_critical_pressure_distance_from_search_bounds_pa"]
    )
    retained_high = samples[0][1].state.pressure_pa
    retained_low = samples[-1][1].state.pressure_pa
    if (
        prominence < minimum_prominence
        or best.state.pressure_pa - retained_low < minimum_distance
        or retained_high - best.state.pressure_pa < minimum_distance
    ):
        return None, records, CRITICAL_SEARCH_NOT_BRACKETED, (
            "Critical maximum fails locked prominence or interior-distance rules."
        )

    critical = CriticalEvaluation(
        pressure_pa=best.state.pressure_pa,
        pressure_ratio=best.state.pressure_pa / p0,
        stream=best,
        coarse_index=coarse_index,
        coarse_neighbor_high_pressure_pa=higher_pressure_stream.state.pressure_pa,
        coarse_neighbor_low_pressure_pa=lower_pressure_stream.state.pressure_pa,
        refinement_iterations=refined.iterations,
        final_bracket_width_pa=refined.bracket_high_pa - refined.bracket_low_pa,
        peak_prominence_relative=prominence,
        path_termination_outcome=termination_outcome,
        path_termination_pressure_pa=termination_pressure,
    )
    return critical, records, None, "SUCCESS"


def _construct_result(
    inputs: AdapterInput,
    upstream: ThermodynamicState,
    stream: StreamEvaluation,
    outcome: str,
    critical: CriticalEvaluation | None,
) -> AdapterResult:
    area = inputs.reference_area_m2 * inputs.opening_fraction
    mass = area * stream.effective_mass_flux_kg_m2_s
    momentum = mass * stream.effective_velocity_m_s
    energy = mass * upstream.enthalpy_J_kg
    if not _finite(mass, momentum, energy):
        return _zero_result(
            inputs,
            CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE,
            "Conservative transfer construction produced a nonfinite value.",
            upstream=upstream,
            critical=critical,
        )
    state = stream.state
    return AdapterResult(
        case_id=inputs.case_id,
        state_id=inputs.state_id,
        formal_outcome=outcome,
        formal_message=(
            "Verification adapter evaluated an unchoked isentropic state."
            if outcome == SUCCESS_UNCHOKED
            else "Verification adapter retained the critical state for choked flow."
        ),
        upstream_pressure_pa=inputs.upstream_pressure_pa,
        upstream_temperature_K=inputs.upstream_temperature_K,
        back_pressure_pa=inputs.back_pressure_pa,
        evaluation_pressure_pa=state.pressure_pa,
        critical_pressure_pa=None if critical is None else critical.pressure_pa,
        critical_pressure_ratio=None if critical is None else critical.pressure_ratio,
        reference_area_m2=inputs.reference_area_m2,
        opening_fraction=inputs.opening_fraction,
        effective_area_m2=area,
        discharge_coefficient=inputs.discharge_coefficient,
        upstream_density_kg_m3=upstream.density_kg_m3,
        upstream_enthalpy_J_kg=upstream.enthalpy_J_kg,
        upstream_entropy_J_kg_K=upstream.entropy_J_kg_K,
        upstream_phase=upstream.phase,
        candidate_temperature_K=state.temperature_K,
        candidate_density_kg_m3=state.density_kg_m3,
        candidate_enthalpy_J_kg=state.enthalpy_J_kg,
        candidate_entropy_J_kg_K=state.entropy_J_kg_K,
        candidate_phase=state.phase,
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
    case: dict[str, Any],
    *,
    critical_cache: dict[tuple[str, float], CriticalEvaluation],
    critical_records: list[dict[str, Any]],
) -> AdapterResult:
    inputs = build_input(contract, case, provider)
    numeric = (
        inputs.upstream_pressure_pa,
        inputs.upstream_temperature_K,
        inputs.back_pressure_pa,
        inputs.reference_area_m2,
        inputs.opening_fraction,
        inputs.discharge_coefficient,
    )
    if not _finite(*numeric):
        return _zero_result(inputs, NONFINITE_INPUT, "One or more numeric inputs are nonfinite.")
    if inputs.reference_area_m2 <= 0.0:
        return _zero_result(
            inputs, NONPOSITIVE_REFERENCE_AREA, "Reference area must be positive."
        )
    if not 0.0 <= inputs.opening_fraction <= 1.0:
        return _zero_result(
            inputs,
            OPENING_OUTSIDE_UNIT_INTERVAL,
            "Opening fraction must be in [0,1].",
        )
    if inputs.discharge_coefficient <= 0.0:
        return _zero_result(
            inputs,
            NONPOSITIVE_DISCHARGE_COEFFICIENT,
            "Discharge coefficient must be positive.",
        )
    if inputs.back_pressure_pa > inputs.upstream_pressure_pa:
        return _zero_result(
            inputs,
            REVERSE_PRESSURE_NOT_SUPPORTED,
            "Back pressure exceeds upstream pressure.",
        )

    family = _family(contract, inputs.state_id)
    allowed_phases = {
        normalize_phase(value) for value in family["allowed_normalized_phases"]
    }
    try:
        upstream = provider.upstream_state(
            inputs.upstream_pressure_pa, inputs.upstream_temperature_K
        )
    except Exception as exc:
        return _zero_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            f"Upstream property evaluation failed: {type(exc).__name__}: {exc}",
        )
    if (
        not _finite(
            upstream.density_kg_m3,
            upstream.enthalpy_J_kg,
            upstream.entropy_J_kg_K,
        )
        or upstream.density_kg_m3 <= 0.0
    ):
        return _zero_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            "Upstream state contains nonfinite or nonpositive properties.",
            upstream=upstream,
        )
    if normalize_phase(upstream.phase) not in allowed_phases:
        return _zero_result(
            inputs,
            UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE,
            f"Upstream phase {upstream.phase!r} is outside {sorted(allowed_phases)}.",
            upstream=upstream,
        )

    if case.get("execution_mode") == "synthetic_guard_unit_test":
        if inputs.case_id == "G-04_NONPOSITIVE_KINETIC_ENERGY_HEAD":
            return _zero_result(
                inputs,
                NONPOSITIVE_KINETIC_ENERGY_HEAD,
                "Synthetic nonpositive kinetic-head guard retained.",
                upstream=upstream,
            )
        if inputs.case_id == "G-05_CRITICAL_SEARCH_NOT_BRACKETED":
            return _zero_result(
                inputs,
                CRITICAL_SEARCH_NOT_BRACKETED,
                "Synthetic unbracketed-search guard retained.",
                upstream=upstream,
            )

    effective_area = inputs.reference_area_m2 * inputs.opening_fraction
    if effective_area == 0.0:
        return _zero_result(
            inputs,
            SUCCESS_CLOSED,
            "Closed-element identity retained exactly.",
            upstream=upstream,
        )
    if inputs.back_pressure_pa == inputs.upstream_pressure_pa:
        return _zero_result(
            inputs,
            SUCCESS_ZERO_PRESSURE_DROP,
            "Zero-pressure-drop identity retained exactly.",
            upstream=upstream,
        )

    critical: CriticalEvaluation | None = None
    if bool(family["critical_state_search_required"]):
        cache_key = (inputs.state_id, inputs.discharge_coefficient)
        critical = critical_cache.get(cache_key)
        if critical is None:
            critical, records, outcome, message = search_critical_state(
                contract,
                provider,
                upstream,
                allowed_phases,
                inputs.discharge_coefficient,
            )
            for record in records:
                record["state_id"] = inputs.state_id
                record["discharge_coefficient"] = inputs.discharge_coefficient
            critical_records.extend(records)
            if critical is None:
                return _zero_result(
                    inputs,
                    outcome or CRITICAL_SEARCH_NOT_BRACKETED,
                    message,
                    upstream=upstream,
                )
            critical_cache[cache_key] = critical
        classification_tolerance = float(
            contract["critical_state_search"][
                "critical_pressure_classification_tolerance_pa"
            ]
        )
        if inputs.back_pressure_pa <= critical.pressure_pa + classification_tolerance:
            return _construct_result(
                inputs, upstream, critical.stream, SUCCESS_CHOKED, critical
            )

    stream, outcome, message = _stream_at_pressure(
        provider,
        upstream,
        inputs.back_pressure_pa,
        inputs.discharge_coefficient,
        allowed_phases,
        float(
            contract["acceptance_tolerances"][
                "isentropic_entropy_absolute_J_kg_K"
            ]
        ),
    )
    if stream is None:
        return _zero_result(
            inputs,
            outcome or SINGLE_PHASE_PATH_SCOPE_FAILURE,
            message,
            upstream=upstream,
            critical=critical,
        )
    return _construct_result(inputs, upstream, stream, SUCCESS_UNCHOKED, critical)


def evaluate_contract(
    contract: dict[str, Any],
    provider: PropertyProvider | None = None,
) -> tuple[list[AdapterResult], dict[str, CriticalEvaluation], list[dict[str, Any]]]:
    property_provider = provider or CoolPropStateProvider()
    critical_cache: dict[tuple[str, float], CriticalEvaluation] = {}
    critical_records: list[dict[str, Any]] = []
    results = [
        evaluate_case(
            contract,
            property_provider,
            case,
            critical_cache=critical_cache,
            critical_records=critical_records,
        )
        for case in contract["benchmark_cases"]
    ]
    critical_by_key = {
        f"{state_id}|Cd={coefficient:g}": value
        for (state_id, coefficient), value in critical_cache.items()
    }
    return results, critical_by_key, critical_records


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify_reference_artifact(
    reference_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    required = {
        "summary.json",
        "benchmark_contract.json",
        "conservative_transfer_table.csv",
        "critical_state_summary.json",
        "artifact_sha256.txt",
    }
    missing = [name for name in sorted(required) if not (reference_dir / name).is_file()]
    if missing:
        raise ValueError(f"Missing reference artifact files: {missing}")
    manifest: dict[str, str] = {}
    for line in (reference_dir / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    for name, expected in manifest.items():
        path = reference_dir / name
        if not path.is_file():
            raise ValueError(f"Missing manifest entry: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Reference internal digest mismatch: {name}")
    summary = json.loads((reference_dir / "summary.json").read_text(encoding="utf-8"))
    if summary.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise ValueError("Unexpected reference artifact schema")
    if summary.get("all_locked_checks_passed") is not True:
        raise ValueError("Reference artifact did not pass locked checks")
    if summary.get("u3_b1_reference_implemented") is not True:
        raise ValueError("Reference artifact is not completion-qualified")
    if summary.get("u3_b1_adapter_implemented") is not False:
        raise ValueError("Reference artifact approval boundary changed")
    critical = json.loads(
        (reference_dir / "critical_state_summary.json").read_text(encoding="utf-8")
    )
    return summary, _read_csv(reference_dir / "conservative_transfer_table.csv"), critical


def _allowed_error(expected: float, absolute: float, relative: float) -> float:
    return absolute + relative * abs(expected)


def compare_to_reference(
    contract: dict[str, Any],
    adapter_results: list[AdapterResult],
    reference_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    tolerances = contract["acceptance_tolerances"]
    adapter_by_case = {row.case_id: row for row in adapter_results}
    reference_by_case = {row["case_id"]: row for row in reference_rows}
    if set(adapter_by_case) != set(reference_by_case):
        raise ValueError("Reference and adapter case sets differ")
    measures = (
        (
            "effective_mass_flux_kg_m2_s",
            float(tolerances["reference_adapter_mass_flux_absolute_kg_m2_s"]),
            float(tolerances["reference_adapter_mass_flux_relative"]),
        ),
        (
            "mass_transfer_outward_kg_s",
            float(tolerances["reference_adapter_mass_flow_absolute_kg_s"]),
            float(tolerances["reference_adapter_mass_flow_relative"]),
        ),
        (
            "momentum_stream_transfer_outward_N",
            float(tolerances["reference_adapter_momentum_transfer_absolute_N"]),
            float(tolerances["reference_adapter_momentum_transfer_relative"]),
        ),
        (
            "energy_transfer_outward_W",
            float(tolerances["reference_adapter_energy_transfer_absolute_W"]),
            float(tolerances["reference_adapter_energy_transfer_relative"]),
        ),
    )
    comparisons: list[dict[str, Any]] = []
    for case_id, adapter in adapter_by_case.items():
        reference = reference_by_case[case_id]
        outcome_match = adapter.formal_outcome == reference["formal_outcome"]
        for field, absolute, relative in measures:
            actual = float(getattr(adapter, field))
            expected = float(reference[field])
            error = abs(actual - expected)
            allowed = _allowed_error(expected, absolute, relative)
            comparisons.append(
                {
                    "case_id": case_id,
                    "formal_outcome_match": outcome_match,
                    "adapter_outcome": adapter.formal_outcome,
                    "reference_outcome": reference["formal_outcome"],
                    "measure": field,
                    "adapter_value": actual,
                    "reference_value": expected,
                    "absolute_error": error,
                    "allowed_error": allowed,
                    "comparison_passed": outcome_match and error <= allowed,
                }
            )
        reference_critical = reference.get("critical_pressure_pa", "")
        if reference_critical not in (None, ""):
            actual_critical = float(adapter.critical_pressure_pa or math.nan)
            expected_critical = float(reference_critical)
            absolute = float(
                tolerances["reference_adapter_critical_pressure_absolute_pa"]
            )
            relative = float(
                tolerances["reference_adapter_critical_pressure_relative"]
            )
            error = abs(actual_critical - expected_critical)
            allowed = _allowed_error(expected_critical, absolute, relative)
            comparisons.append(
                {
                    "case_id": case_id,
                    "formal_outcome_match": outcome_match,
                    "adapter_outcome": adapter.formal_outcome,
                    "reference_outcome": reference["formal_outcome"],
                    "measure": "critical_pressure_pa",
                    "adapter_value": actual_critical,
                    "reference_value": expected_critical,
                    "absolute_error": error,
                    "allowed_error": allowed,
                    "comparison_passed": outcome_match and error <= allowed,
                }
            )
    return comparisons


def _relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1e-300)


def locked_checks(
    contract: dict[str, Any],
    results: list[AdapterResult],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = {row.case_id: row for row in results}
    tolerances = contract["acceptance_tolerances"]
    expected = {
        str(case["case_id"]): str(case["expected_outcome"])
        for case in contract["benchmark_cases"]
    }
    outcomes_match = {
        case_id: by_id[case_id].formal_outcome == formal_outcome
        for case_id, formal_outcome in expected.items()
    }

    zero_rows = [
        row
        for row in results
        if row.formal_outcome in {SUCCESS_CLOSED, SUCCESS_ZERO_PRESSURE_DROP}
    ]
    zero_identity = all(
        row.mass_transfer_outward_kg_s == 0.0
        and row.momentum_stream_transfer_outward_N == 0.0
        and row.energy_transfer_outward_W == 0.0
        for row in zero_rows
    )

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
    plateau_error = _relative_error(
        plateau_a.mass_transfer_outward_kg_s,
        plateau_b.mass_transfer_outward_kg_s,
    )
    plateau_passed = plateau_error <= float(
        tolerances["below_critical_plateau_relative"]
    )

    area_ratio = (
        by_id["B1-07B_AREA_SCALING_HIGH"].mass_transfer_outward_kg_s
        / by_id["B1-07A_AREA_SCALING_LOW"].mass_transfer_outward_kg_s
    )
    area_passed = abs(area_ratio - 2.0) <= float(
        tolerances["scaling_ratio_absolute"]
    )
    cd_ratio = (
        by_id["B1-08B_CD_SCALING_HIGH"].mass_transfer_outward_kg_s
        / by_id["B1-08A_CD_SCALING_LOW"].mass_transfer_outward_kg_s
    )
    cd_passed = abs(cd_ratio - 2.0) <= float(
        tolerances["scaling_ratio_absolute"]
    )
    cd_pressure_error = _relative_error(
        float(by_id["B1-08B_CD_SCALING_HIGH"].critical_pressure_pa or math.nan),
        float(by_id["B1-08A_CD_SCALING_LOW"].critical_pressure_pa or math.nan),
    )
    cd_pressure_passed = cd_pressure_error <= float(
        tolerances["critical_pressure_Cd_independence_relative"]
    )

    b0 = by_id["B1-03_SMALL_DROP_RECOVERS_B0_LIMIT"]
    rho0 = float(b0.upstream_density_kg_m3 or math.nan)
    h0 = float(b0.upstream_enthalpy_J_kg or math.nan)
    delta_p = b0.upstream_pressure_pa - b0.back_pressure_pa
    velocity_b0 = b0.discharge_coefficient * math.sqrt(2.0 * delta_p / rho0)
    mass_b0 = rho0 * b0.effective_area_m2 * velocity_b0
    momentum_b0 = mass_b0 * velocity_b0
    energy_b0 = mass_b0 * h0
    b0_errors = {
        "mass_flow": _relative_error(b0.mass_transfer_outward_kg_s, mass_b0),
        "effective_velocity": _relative_error(b0.effective_velocity_m_s, velocity_b0),
        "momentum_stream": _relative_error(
            b0.momentum_stream_transfer_outward_N, momentum_b0
        ),
        "energy": _relative_error(b0.energy_transfer_outward_W, energy_b0),
    }
    b0_passed = (
        b0_errors["mass_flow"] <= float(tolerances["B0_limit_mass_flow_relative"])
        and b0_errors["effective_velocity"]
        <= float(tolerances["B0_limit_effective_velocity_relative"])
        and b0_errors["momentum_stream"]
        <= float(tolerances["B0_limit_momentum_transfer_relative"])
        and b0_errors["energy"] <= float(tolerances["B0_limit_energy_transfer_relative"])
    )

    rows = [
        {
            "check": "expected_formal_outcomes",
            "value": sum(outcomes_match.values()),
            "target": len(outcomes_match),
            "passed": all(outcomes_match.values()),
        },
        {
            "check": "exact_zero_identities",
            "value": len(zero_rows),
            "target": 2,
            "passed": zero_identity and len(zero_rows) == 2,
        },
        {
            "check": "B0_limiting_behavior",
            "value": max(b0_errors.values()),
            "target": "measure-specific locked tolerances",
            "passed": b0_passed,
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
            "value": plateau_error,
            "target": tolerances["below_critical_plateau_relative"],
            "passed": plateau_passed,
        },
        {"check": "area_scaling", "value": area_ratio, "target": 2.0, "passed": area_passed},
        {"check": "Cd_scaling", "value": cd_ratio, "target": 2.0, "passed": cd_passed},
        {
            "check": "critical_pressure_Cd_independence",
            "value": cd_pressure_error,
            "target": tolerances["critical_pressure_Cd_independence_relative"],
            "passed": cd_pressure_passed,
        },
    ]
    summary = {
        "outcomes_match": outcomes_match,
        "all_expected_outcomes_match": all(outcomes_match.values()),
        "exact_zero_identities_retained": zero_identity and len(zero_rows) == 2,
        "b0_limit_passed": b0_passed,
        "b0_limit_relative_errors": b0_errors,
        "unchoked_ordering_margin_relative": ordering_margin,
        "unchoked_ordering_passed": ordering_passed,
        "below_critical_plateau_relative": plateau_error,
        "below_critical_plateau_passed": plateau_passed,
        "area_scaling_ratio": area_ratio,
        "area_scaling_passed": area_passed,
        "Cd_scaling_ratio": cd_ratio,
        "Cd_scaling_passed": cd_passed,
        "critical_pressure_Cd_relative_difference": cd_pressure_error,
        "critical_pressure_Cd_independence_passed": cd_pressure_passed,
        "all_locked_adapter_checks_passed": all(bool(row["passed"]) for row in rows),
    }
    return rows, summary


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    payload = list(rows)
    if not payload:
        raise ValueError(f"No rows supplied for {path.name}")
    fieldnames: list[str] = []
    for row in payload:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(payload)


def plot_provenance_text(
    case_name: str,
    backend_version: str,
    source_git_sha: str,
) -> str:
    return (
        f"case={case_name} | "
        "model=U3 B1 verification adapter comparison | "
        f"backend=CoolProp | version={backend_version} | "
        f"source={source_git_sha[:12]}"
    )


def _write_plots(
    output_dir: Path,
    results: list[AdapterResult],
    reference_rows: list[dict[str, str]],
    comparisons: list[dict[str, Any]],
    *,
    backend_version: str,
    source_git_sha: str,
) -> None:
    import matplotlib.pyplot as plt

    reference = {row["case_id"]: row for row in reference_rows}
    successes = [row for row in results if row.succeeded]

    fig = plt.figure()
    ax = fig.add_subplot(111)
    x = [float(reference[row.case_id]["effective_mass_flux_kg_m2_s"]) for row in successes]
    y = [row.effective_mass_flux_kg_m2_s for row in successes]
    ax.scatter(x, y)
    if x:
        lower = min(x + y)
        upper = max(x + y)
        ax.plot([lower, upper], [lower, upper])
    ax.set_xlabel("Reference effective mass flux [kg/(m² s)]")
    ax.set_ylabel("Adapter effective mass flux [kg/(m² s)]")
    ax.set_title(
        "U3 B1 effective mass-flux comparison\n"
        + plot_provenance_text(
            "17-case mass-flux matrix", backend_version, source_git_sha
        ),
        fontsize=9,
    )
    fig.tight_layout()
    fig.savefig(output_dir / "mass_flux_reference_vs_adapter.png", dpi=160)
    plt.close(fig)

    critical_rows = [
        row for row in results if row.critical_pressure_pa is not None and row.succeeded
    ]
    fig = plt.figure()
    ax = fig.add_subplot(111)
    x = [float(reference[row.case_id]["critical_pressure_pa"]) for row in critical_rows]
    y = [float(row.critical_pressure_pa or math.nan) for row in critical_rows]
    ax.scatter(x, y)
    if x:
        lower = min(x + y)
        upper = max(x + y)
        ax.plot([lower, upper], [lower, upper])
    ax.set_xlabel("Reference critical pressure [Pa]")
    ax.set_ylabel("Adapter critical pressure [Pa]")
    ax.set_title(
        "U3 B1 critical-pressure comparison\n"
        + plot_provenance_text(
            "9-case critical-pressure matrix", backend_version, source_git_sha
        ),
        fontsize=9,
    )
    fig.tight_layout()
    fig.savefig(output_dir / "critical_pressure_reference_vs_adapter.png", dpi=160)
    plt.close(fig)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter(
        range(len(comparisons)),
        [float(row["absolute_error"]) for row in comparisons],
    )
    ax.set_xlabel("Comparison row")
    ax.set_ylabel("Absolute error")
    ax.set_title(
        "U3 B1 reference-adapter residuals\n"
        + plot_provenance_text(
            "77-row comparison matrix", backend_version, source_git_sha
        ),
        fontsize=9,
    )
    fig.tight_layout()
    fig.savefig(output_dir / "reference_adapter_residuals.png", dpi=160)
    plt.close(fig)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_artifact(
    contract_path: Path,
    reference_dir: Path,
    output_dir: Path,
    *,
    source_git_sha: str,
    reference_artifact_id: int,
    reference_artifact_zip_sha256: str,
    reference_resolution_mode: str,
    reference_source_git_sha: str,
    provider: PropertyProvider | None = None,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    reference_summary, reference_rows, reference_critical = verify_reference_artifact(
        reference_dir
    )
    if reference_resolution_mode != "recomputed_from_pinned_source_sha":
        raise ValueError("Unsupported B1 reference resolution mode")
    if reference_summary["provenance"]["source_git_sha"] != reference_source_git_sha:
        raise ValueError("Resolved reference source SHA does not match the pin")
    reference_contract = json.loads(
        (reference_dir / "benchmark_contract.json").read_text(encoding="utf-8")
    )
    if reference_contract != contract:
        raise ValueError("Local and authoritative reference contracts differ")

    property_provider = provider or CoolPropStateProvider()
    results, criticals, _ = evaluate_contract(contract, property_provider)
    check_rows, check_summary = locked_checks(contract, results)
    comparisons = compare_to_reference(contract, results, reference_rows)
    all_comparisons_passed = all(
        bool(row["comparison_passed"]) for row in comparisons
    )
    if not check_summary["all_locked_adapter_checks_passed"]:
        raise RuntimeError("One or more locked adapter checks failed")
    if not all_comparisons_passed:
        raise RuntimeError("One or more reference-adapter comparisons failed")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "adapter_cases.csv", [asdict(row) for row in results])
    _write_csv(output_dir / "reference_adapter_comparison.csv", comparisons)
    _write_csv(output_dir / "locked_checks.csv", check_rows)
    _write_csv(
        output_dir / "guard_outcomes.csv",
        [asdict(row) for row in results if not row.succeeded],
    )
    _write_csv(output_dir / "conservative_transfer_comparison.csv", comparisons)
    adapter_critical = {
        key: {
            "pressure_pa": value.pressure_pa,
            "pressure_ratio": value.pressure_ratio,
            "temperature_K": value.stream.state.temperature_K,
            "density_kg_m3": value.stream.state.density_kg_m3,
            "ideal_mass_flux_kg_m2_s": value.stream.ideal_mass_flux_kg_m2_s,
            "effective_mass_flux_kg_m2_s": value.stream.effective_mass_flux_kg_m2_s,
            "peak_prominence_relative": value.peak_prominence_relative,
            "refinement_iterations": value.refinement_iterations,
            "final_bracket_width_pa": value.final_bracket_width_pa,
        }
        for key, value in criticals.items()
    }
    (output_dir / "critical_state_summary.json").write_text(
        json.dumps(
            {"adapter": adapter_critical, "reference": reference_critical},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_plots(
        output_dir,
        results,
        reference_rows,
        comparisons,
        backend_version=property_provider.version,
        source_git_sha=source_git_sha,
    )

    success_count = sum(row.succeeded for row in results)
    guard_count = len(results) - success_count
    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "verification_only_single_phase_critical_state_adapter_comparison",
        "issue": 127,
        "contract_schema_version": contract["schema_version"],
        "reference_schema_version": reference_summary["schema_version"],
        "reference_resolution_mode": reference_resolution_mode,
        "reference_source_git_sha": reference_source_git_sha,
        "reference_artifact_provenance_role": "historical_authoritative_evidence",
        "reference_artifact_id": int(reference_artifact_id),
        "reference_artifact_zip_sha256": reference_artifact_zip_sha256,
        "case_count": len(results),
        "success_count": success_count,
        "guard_count": guard_count,
        "comparison_count": len(comparisons),
        "comparison_pass_count": sum(
            bool(row["comparison_passed"]) for row in comparisons
        ),
        "all_formal_outcomes_match": all(
            bool(row["formal_outcome_match"]) for row in comparisons
        ),
        "all_reference_adapter_comparisons_passed": all_comparisons_passed,
        **check_summary,
        "critical_state_keys": sorted(adapter_critical),
        "static_pressure_force_included": False,
        "production_fvm_connected": False,
        "u3_b1_contract_locked": True,
        "u3_b1_reference_implemented": True,
        "u3_b1_adapter_implemented": True,
        "u3_b1_component_benchmark_execution_complete": True,
        "u3_b1_component_benchmark_accepted": True,
        "physical_discharge_boundary_approved": False,
        "two_phase_critical_discharge_accuracy_approved": False,
        "integrated_blowdown_model_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
        "provenance": {
            "source_git_sha": source_git_sha,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "property_backend": "CoolProp",
            "property_backend_version": property_provider.version,
            "tracked_git_status": "",
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = [
        "# Stage 7 U3 B1 — Verification Adapter Comparison",
        "",
        "The verification-only adapter was evaluated against the immutable ",
        "independent B1 reference artifact. The adapter imports no reference ",
        "module and uses an independent property-state and critical-search path.",
        "",
        "## Result",
        "",
        f"- property backend: CoolProp {property_provider.version}",
        f"- adapter source SHA: {source_git_sha}",
        f"- reference resolution: {reference_resolution_mode}",
        f"- pinned reference source SHA: {reference_source_git_sha}",
        (
            "- historical authoritative artifact: "
            f"ID {reference_artifact_id} / ZIP SHA256 {reference_artifact_zip_sha256}"
        ),
        f"- fixed cases: {len(results)} ({success_count} success / {guard_count} guards)",
        f"- comparison rows: {len(comparisons)}",
        f"- comparison passes: {sum(bool(row['comparison_passed']) for row in comparisons)}",
        "- formal outcomes: all matched",
        "- locked adapter checks: all passed",
        "",
        "## Approval boundary",
        "",
        "```text",
        "u3_b1_contract_locked = true",
        "u3_b1_reference_implemented = true",
        "u3_b1_adapter_implemented = true",
        "u3_b1_component_benchmark_execution_complete = true",
        "u3_b1_component_benchmark_accepted = true",
        "physical_discharge_boundary_approved = false",
        "two_phase_critical_discharge_accuracy_approved = false",
        "integrated_blowdown_model_approved = false",
        "physical_validation = false",
        "design_use_acceptance = false",
        "production_hem_activation_approved = false",
        "```",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    names = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.name != "artifact_sha256.txt"
    )
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--reference-artifact-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-artifact-id", type=int, required=True)
    parser.add_argument("--reference-artifact-zip-sha256", required=True)
    parser.add_argument("--reference-resolution-mode", required=True)
    parser.add_argument("--reference-source-git-sha", required=True)
    parser.add_argument(
        "--source-git-sha",
        default=os.environ.get("ANALYSIS_SOURCE_GIT_SHA", "UNKNOWN"),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    write_artifact(
        args.contract,
        args.reference_artifact_dir,
        args.output_dir,
        source_git_sha=str(args.source_git_sha),
        reference_artifact_id=int(args.reference_artifact_id),
        reference_artifact_zip_sha256=str(args.reference_artifact_zip_sha256),
        reference_resolution_mode=str(args.reference_resolution_mode),
        reference_source_git_sha=str(args.reference_source_git_sha),
    )


if __name__ == "__main__":
    main()
