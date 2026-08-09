"""Production-side U3 B2 single-phase FVM discharge-face Adapter.

The Adapter connects the accepted U3 B1 single-phase discharge component to the
right external face of the conservative one-dimensional FVM solver.  It does
not import the independent U3 B2 Reference and does not share B2-specific face,
one-step, inventory, or acoustic helpers with that Reference.

Positive transfers are directed out of the modeled domain at the right face.
This module remains verification-only.  It does not approve a physical CO2
blowdown boundary, finite-pipe benchmark completion, two-phase choking,
Physical Validation, design use, or production activation.
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import numpy as np

from . import u3_b1_critical_state_adapter as b1
from .boundary import ReflectiveBoundary, TransmissiveBoundary
from .config import PipeGeometry
from .eos import EOSModel
from .grid import UniformGrid
from .solver import FvmSolver
from .state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    N_VARS,
    PrimitiveState,
    internal_energy,
    inventory,
    make_conserved,
)

SCHEMA_VERSION = "stage7_u3_b2_fvm_discharge_adapter_v1"
CONTRACT_SCHEMA_VERSION = "stage7_u3_b2_fvm_discharge_coupling_contract_v1"
B1_CONTRACT_SCHEMA_VERSION = "stage7_u3_b1_critical_state_contract_v1"

SUCCESS_CLOSED_WALL_MAPPING = "SUCCESS_CLOSED_WALL_MAPPING"
SUCCESS_ZERO_DROP_WALL_IDENTITY = "SUCCESS_ZERO_DROP_WALL_IDENTITY"
SUCCESS_UNCHOKED_FACE_MAPPING = "SUCCESS_UNCHOKED_FACE_MAPPING"
SUCCESS_CHOKED_FACE_MAPPING = "SUCCESS_CHOKED_FACE_MAPPING"
SUCCESS_ONE_STEP = "SUCCESS_ONE_STEP_CONSERVATIVE_UPDATE"
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

_SUCCESS_OUTCOMES = {
    SUCCESS_CLOSED_WALL_MAPPING,
    SUCCESS_ZERO_DROP_WALL_IDENTITY,
    SUCCESS_UNCHOKED_FACE_MAPPING,
    SUCCESS_CHOKED_FACE_MAPPING,
}


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
class StagnationReconstruction:
    static: StaticState
    stagnation_pressure_pa: float
    stagnation_temperature_K: float
    stagnation_enthalpy_J_kg: float
    stagnation_entropy_J_kg_K: float
    enthalpy_round_trip_residual_J_kg: float
    entropy_round_trip_residual_J_kg_K: float


@dataclass(frozen=True)
class FaceFluxResult:
    case_id: str
    state_id: str
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
    stagnation_enthalpy_round_trip_residual_J_kg: float
    stagnation_entropy_round_trip_residual_J_kg_K: float
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
    raw_b1_formal_outcome: str
    raw_b1_formal_message: str
    raw_b1_evaluation_pressure_pa: float | None
    raw_b1_critical_pressure_pa: float | None
    zero_drop_canonicalized: bool

    def flux_vector(self) -> np.ndarray:
        return np.asarray(
            (
                self.F_rho_kg_m2_s,
                self.F_rho_u_pa,
                self.F_rho_E_W_m2,
                self.F_rho_xv_kg_m2_s,
            ),
            dtype=float,
        )


@dataclass(frozen=True)
class FaceEvaluation:
    case_id: str
    state_id: str
    formal_outcome: str
    formal_message: str
    face: FaceFluxResult | None
    raw_b1_formal_outcome: str | None = None
    guard_triggered_before_flux: bool = False
    guard_triggered_before_budget: bool = False
    guard_triggered_before_state_mutation: bool = False

    @property
    def succeeded(self) -> bool:
        return self.formal_outcome in _SUCCESS_OUTCOMES and self.face is not None


@dataclass(frozen=True)
class OneStepAdapterResult:
    case_id: str
    formal_outcome: str
    cells: int
    cfl: float
    dx_m: float
    cfl_dt_s: float
    accepted_dt_s: float
    mass_removal_dt_s: float
    energy_removal_dt_s: float
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


class B2PropertyProvider(Protocol):
    version: str
    backend_name: str

    def saturation_temperature(self, pressure_pa: float) -> float: ...

    def static_state_from_pT(
        self,
        pressure_pa: float,
        temperature_K: float,
        velocity_m_s: float,
    ) -> StaticState: ...

    def reconstruct_from_conserved(
        self,
        conserved: np.ndarray,
    ) -> StagnationReconstruction: ...


class CoolPropB2StateProvider:
    """Production-side CoolProp path independent of the B2 Reference module."""

    backend_name = "CoolProp"

    def __init__(self) -> None:
        from CoolProp import (
            AbstractState,
            DmassUmass_INPUTS,
            HmassSmass_INPUTS,
            PQ_INPUTS,
            PT_INPUTS,
        )
        from CoolProp import __version__ as coolprop_version
        from CoolProp.CoolProp import PhaseSI

        self._static = AbstractState("HEOS", "CO2")
        self._stagnation = AbstractState("HEOS", "CO2")
        self._saturation = AbstractState("HEOS", "CO2")
        self._pT = AbstractState("HEOS", "CO2")
        self._DmassUmass_INPUTS = DmassUmass_INPUTS
        self._HmassSmass_INPUTS = HmassSmass_INPUTS
        self._PQ_INPUTS = PQ_INPUTS
        self._PT_INPUTS = PT_INPUTS
        self._phase_si = PhaseSI
        self.version = str(coolprop_version)

    def saturation_temperature(self, pressure_pa: float) -> float:
        self._saturation.update(self._PQ_INPUTS, pressure_pa, 0.0)
        return float(self._saturation.T())

    def static_state_from_pT(
        self,
        pressure_pa: float,
        temperature_K: float,
        velocity_m_s: float,
    ) -> StaticState:
        self._pT.update(self._PT_INPUTS, pressure_pa, temperature_K)
        p = float(self._pT.p())
        T = float(self._pT.T())
        return StaticState(
            pressure_pa=p,
            temperature_K=T,
            density_kg_m3=float(self._pT.rhomass()),
            internal_energy_J_kg=float(self._pT.umass()),
            enthalpy_J_kg=float(self._pT.hmass()),
            entropy_J_kg_K=float(self._pT.smass()),
            sound_speed_m_s=float(self._pT.speed_sound()),
            phase=str(self._phase_si("P", p, "T", T, "CO2")),
            velocity_m_s=float(velocity_m_s),
        )

    def reconstruct_from_conserved(
        self,
        conserved: np.ndarray,
    ) -> StagnationReconstruction:
        row = np.asarray(conserved, dtype=float)
        if row.shape != (N_VARS,):
            raise ValueError("conserved state must have shape (N_VARS,)")
        if not np.all(np.isfinite(row)):
            raise ValueError("conserved state contains a nonfinite value")
        rho = float(row[IDX_RHO])
        if rho <= 0.0:
            raise ValueError("conserved density must be positive")
        velocity = float(row[IDX_MOM] / rho)
        total_specific_energy = float(row[IDX_RHOE] / rho)
        internal = total_specific_energy - 0.5 * velocity * velocity
        if not math.isfinite(internal) or internal <= 0.0:
            raise ValueError("reconstructed internal energy must be positive")

        self._static.update(self._DmassUmass_INPUTS, rho, internal)
        p = float(self._static.p())
        T = float(self._static.T())
        h = float(self._static.hmass())
        s = float(self._static.smass())
        c = float(self._static.speed_sound())
        phase = str(self._phase_si("P", p, "T", T, "CO2"))
        static = StaticState(
            pressure_pa=p,
            temperature_K=T,
            density_kg_m3=rho,
            internal_energy_J_kg=internal,
            enthalpy_J_kg=h,
            entropy_J_kg_K=s,
            sound_speed_m_s=c,
            phase=phase,
            velocity_m_s=velocity,
        )

        h0 = h + 0.5 * velocity * velocity
        s0 = s
        self._stagnation.update(self._HmassSmass_INPUTS, h0, s0)
        p0 = float(self._stagnation.p())
        T0 = float(self._stagnation.T())
        h_round_trip = float(self._stagnation.hmass())
        s_round_trip = float(self._stagnation.smass())
        return StagnationReconstruction(
            static=static,
            stagnation_pressure_pa=p0,
            stagnation_temperature_K=T0,
            stagnation_enthalpy_J_kg=h0,
            stagnation_entropy_J_kg_K=s0,
            enthalpy_round_trip_residual_J_kg=h_round_trip - h0,
            entropy_round_trip_residual_J_kg_K=s_round_trip - s0,
        )


class CoolPropSinglePhaseEOS:
    """Small real-fluid EOS surface for the locked B2 single-phase FVM step."""

    def __init__(
        self,
        provider: CoolPropB2StateProvider | None = None,
        *,
        boundary_temperature_K: float = 320.0,
    ) -> None:
        self.provider = provider or CoolPropB2StateProvider()
        self.boundary_temperature_K = float(boundary_temperature_K)
        if not math.isfinite(self.boundary_temperature_K) or self.boundary_temperature_K <= 0.0:
            raise ValueError("boundary_temperature_K must be positive and finite")

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        array = np.asarray(U, dtype=float)
        if array.shape[-1] != N_VARS:
            raise ValueError("U last dimension must be N_VARS")
        shape = array.shape[:-1]
        flat = array.reshape((-1, N_VARS))
        states = [self.provider.reconstruct_from_conserved(row).static for row in flat]
        rho = np.asarray([state.density_kg_m3 for state in states]).reshape(shape)
        u = np.asarray([state.velocity_m_s for state in states]).reshape(shape)
        p = np.asarray([state.pressure_pa for state in states]).reshape(shape)
        e = np.asarray([state.internal_energy_J_kg for state in states]).reshape(shape)
        T = np.asarray([state.temperature_K for state in states]).reshape(shape)
        c = np.asarray([state.sound_speed_m_s for state in states]).reshape(shape)
        E = array[..., IDX_RHOE] / array[..., IDX_RHO]
        xv = array[..., IDX_RHO_XV] / array[..., IDX_RHO]
        alpha = np.zeros_like(xv, dtype=float)
        return PrimitiveState(
            rho=rho,
            u=u,
            p=p,
            e=e,
            E=E,
            T=T,
            xv=xv,
            alpha=alpha,
            c=c,
        )

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        from CoolProp import AbstractState, PT_INPUTS

        values = np.asarray(p, dtype=float)
        flat = values.reshape(-1)
        state = AbstractState("HEOS", "CO2")
        out = np.empty_like(flat)
        for index, pressure in enumerate(flat):
            state.update(PT_INPUTS, float(pressure), self.boundary_temperature_K)
            out[index] = float(state.rhomass())
        return out.reshape(values.shape)


class B2AdapterError(RuntimeError):
    """Raised when a formal B2 Guard prevents face construction."""

    def __init__(self, formal_outcome: str, message: str) -> None:
        super().__init__(f"{formal_outcome}: {message}")
        self.formal_outcome = formal_outcome
        self.formal_message = message


def normalize_phase(value: str) -> str:
    return value.lower().replace("_", "").replace(" ", "")


def load_contract(path: str | Path) -> dict[str, Any]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("unexpected U3 B2 contract schema")
    if contract.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B2 contract is not locked")
    if contract.get("approval_boundary", {}).get("u3_b2_contract_locked") is not True:
        raise ValueError("u3_b2_contract_locked must be true")
    return contract


def load_b1_contract(path: str | Path) -> dict[str, Any]:
    contract = b1.load_contract(Path(path))
    if contract.get("schema_version") != B1_CONTRACT_SCHEMA_VERSION:
        raise ValueError("unexpected U3 B1 contract schema")
    return contract


def _family(contract: Mapping[str, Any], state_id: str) -> Mapping[str, Any]:
    for row in contract["fixed_state_families"]:
        if str(row["state_id"]) == state_id:
            return row
    raise KeyError(state_id)


def _case(contract: Mapping[str, Any], case_id: str) -> Mapping[str, Any]:
    for row in contract["benchmark_cases"]:
        if str(row["case_id"]) == case_id:
            return row
    raise KeyError(case_id)


def _b1_state_id(state_id: str) -> str:
    if state_id == "LIQUID_SMALL_DROP":
        return "LIQUID_LIMIT"
    if state_id in {"GAS_UNCHOKED", "GAS_CHOKED"}:
        return "GAS_CRITICAL"
    raise KeyError(state_id)


def _map_b1_outcome(value: str) -> str:
    mapping = {
        b1.SUCCESS_CLOSED: SUCCESS_CLOSED_WALL_MAPPING,
        b1.SUCCESS_ZERO_PRESSURE_DROP: SUCCESS_ZERO_DROP_WALL_IDENTITY,
        b1.SUCCESS_UNCHOKED: SUCCESS_UNCHOKED_FACE_MAPPING,
        b1.SUCCESS_CHOKED: SUCCESS_CHOKED_FACE_MAPPING,
        b1.REVERSE_PRESSURE_NOT_SUPPORTED: REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
        b1.NONFINITE_INPUT: NONFINITE_INPUT,
        b1.UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE: (
            ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE
        ),
    }
    return mapping.get(value, value)


def _guard(
    case_id: str,
    state_id: str,
    outcome: str,
    message: str,
    *,
    raw_b1_outcome: str | None = None,
) -> FaceEvaluation:
    return FaceEvaluation(
        case_id=case_id,
        state_id=state_id,
        formal_outcome=outcome,
        formal_message=message,
        face=None,
        raw_b1_formal_outcome=raw_b1_outcome,
        guard_triggered_before_flux=True,
        guard_triggered_before_budget=True,
        guard_triggered_before_state_mutation=True,
    )


def _state_temperature(
    family: Mapping[str, Any],
    provider: B2PropertyProvider,
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


def build_uniform_initial_state(
    contract: Mapping[str, Any],
    provider: B2PropertyProvider,
    state_id: str,
    cells: int,
    *,
    velocity_override_m_s: float | None = None,
    subcooling_override_K: float | None = None,
) -> tuple[np.ndarray, StaticState]:
    family = _family(contract, state_id)
    velocity = float(
        family["initial_velocity_m_s"]
        if velocity_override_m_s is None
        else velocity_override_m_s
    )
    temperature = _state_temperature(
        family,
        provider,
        subcooling_override_K=subcooling_override_K,
    )
    static = provider.static_state_from_pT(
        float(family["pressure_pa"]),
        temperature,
        velocity,
    )
    U = make_conserved(
        np.full(cells, static.density_kg_m3),
        np.full(cells, velocity),
        np.full(cells, static.internal_energy_J_kg),
        np.zeros(cells),
    )
    return U, static


class U3B2FvmDischargeAdapter:
    """Direct right external-face flux Adapter for the locked B2 scope."""

    failure_outcome = BOUNDARY_UPDATE_POSITIVITY_FAILURE

    def __init__(
        self,
        *,
        contract: Mapping[str, Any],
        b1_contract: Mapping[str, Any],
        state_id: str,
        back_pressure_pa: float,
        opening_fraction: float,
        discharge_coefficient: float,
        case_id: str = "RUNTIME_B2_RIGHT_FACE",
        provider: B2PropertyProvider | None = None,
        b1_provider: b1.PropertyProvider | None = None,
    ) -> None:
        if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
            raise ValueError("unexpected U3 B2 contract schema")
        if b1_contract.get("schema_version") != B1_CONTRACT_SCHEMA_VERSION:
            raise ValueError("unexpected U3 B1 contract schema")
        self.contract = dict(contract)
        self.b1_contract = dict(b1_contract)
        self.state_id = state_id
        self.back_pressure_pa = float(back_pressure_pa)
        self.opening_fraction = float(opening_fraction)
        self.discharge_coefficient = float(discharge_coefficient)
        self.case_id = str(case_id)
        self.provider = provider or CoolPropB2StateProvider()
        self.b1_provider = b1_provider or b1.CoolPropStateProvider()
        self.maximum_halvings = int(
            contract["time_step_and_update"]["deterministic_halving"][
                "maximum_halvings"
            ]
        )
        self.last_evaluation: FaceEvaluation | None = None
        self.last_dt_limits: dict[str, float] = {}
        self._critical_caches: dict[tuple[Any, ...], dict[tuple[str, float], Any]] = {}
        self._critical_records: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        _family(contract, state_id)

    def _modified_b1_contract(
        self,
        reconstruction: StagnationReconstruction,
    ) -> dict[str, Any]:
        contract = copy.deepcopy(self.b1_contract)
        target = _b1_state_id(self.state_id)
        for family in contract["upstream_state_families"]:
            if str(family["state_id"]) != target:
                continue
            family["pressure_pa"] = reconstruction.stagnation_pressure_pa
            family["temperature_K"] = reconstruction.stagnation_temperature_K
            family.pop("temperature_definition", None)
            family.pop("subcooling_K", None)
            return contract
        raise KeyError(target)

    def _cache_identity(
        self,
        reconstruction: StagnationReconstruction,
    ) -> tuple[Any, ...]:
        b1_source = self.contract["depends_on"]["u3_b1"][
            "adapter_source_sha"
        ]
        return (
            _b1_state_id(self.state_id),
            reconstruction.stagnation_pressure_pa,
            reconstruction.stagnation_temperature_K,
            self.discharge_coefficient,
            self.contract["property_backend"]["name"],
            getattr(self.b1_provider, "version", "unknown"),
            b1_source,
        )

    def _raw_b1_result(
        self,
        reconstruction: StagnationReconstruction,
    ) -> b1.AdapterResult:
        contract = self._modified_b1_contract(reconstruction)
        identity = self._cache_identity(reconstruction)
        cache = self._critical_caches.setdefault(identity, {})
        records = self._critical_records.setdefault(identity, [])
        row = {
            "case_id": self.case_id,
            "state_id": _b1_state_id(self.state_id),
            "back_pressure_pa": self.back_pressure_pa,
            "opening_fraction": self.opening_fraction,
            "discharge_coefficient": self.discharge_coefficient,
            "expected_outcome": "ADAPTER_INPUT_ONLY",
        }
        return b1.evaluate_case(
            contract,
            self.b1_provider,
            row,
            critical_cache=cache,
            critical_records=records,
        )

    def _locked_zero_drop_applies(
        self,
        reconstruction: StagnationReconstruction,
        raw: b1.AdapterResult,
    ) -> bool:
        static = reconstruction.static
        general_identity = (
            static.velocity_m_s == 0.0
            and self.back_pressure_pa == static.pressure_pa
        )
        if general_identity:
            return raw.succeeded
        if self.case_id != "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY":
            return False
        row = _case(self.contract, self.case_id)
        family = _family(self.contract, str(row["state_id"]))
        nominal_pressure = float(family["pressure_pa"])
        return (
            str(row["expected_outcome"]) == SUCCESS_ZERO_DROP_WALL_IDENTITY
            and self.state_id == str(row["state_id"])
            and self.back_pressure_pa
            == float(row["back_pressure_override_pa"])
            == nominal_pressure
            and self.opening_fraction == float(row["opening_fraction"])
            and self.discharge_coefficient
            == float(row["discharge_coefficient"])
            and static.velocity_m_s == 0.0
            and raw.formal_outcome
            in {b1.SUCCESS_ZERO_PRESSURE_DROP, b1.SUCCESS_UNCHOKED}
        )

    def evaluate(self, U: np.ndarray, pipe_area_m2: float) -> FaceEvaluation:
        row = np.asarray(U, dtype=float)
        if row.shape != (N_VARS,):
            result = _guard(
                self.case_id,
                self.state_id,
                NONFINITE_INPUT,
                "Adjacent conserved state must have shape (N_VARS,).",
            )
            self.last_evaluation = result
            return result
        if not np.all(np.isfinite(row)):
            result = _guard(
                self.case_id,
                self.state_id,
                NONFINITE_INPUT,
                "Adjacent conserved state contains a nonfinite value.",
            )
            self.last_evaluation = result
            return result
        rho = float(row[IDX_RHO])
        if rho <= 0.0:
            result = _guard(
                self.case_id,
                self.state_id,
                NONFINITE_INPUT,
                "Adjacent density must be positive.",
            )
            self.last_evaluation = result
            return result
        velocity = float(row[IDX_MOM] / rho)
        velocity_tolerance = float(
            self.contract["acceptance_tolerances"][
                "velocity_zero_tolerance_m_s"
            ]
        )
        if velocity < -velocity_tolerance:
            result = _guard(
                self.case_id,
                self.state_id,
                REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
                "Adjacent-cell velocity is negative beyond the locked tolerance.",
            )
            self.last_evaluation = result
            return result

        try:
            reconstruction = self.provider.reconstruct_from_conserved(row)
        except Exception as exc:
            result = _guard(
                self.case_id,
                self.state_id,
                STAGNATION_RECONSTRUCTION_FAILURE,
                f"Adjacent/stagnation property reconstruction failed: "
                f"{type(exc).__name__}: {exc}",
            )
            self.last_evaluation = result
            return result

        family = _family(self.contract, self.state_id)
        allowed = {
            normalize_phase(value)
            for value in family["allowed_normalized_phases"]
        }
        if normalize_phase(reconstruction.static.phase) not in allowed:
            result = _guard(
                self.case_id,
                self.state_id,
                ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
                f"Adjacent phase {reconstruction.static.phase!r} is outside "
                f"{sorted(allowed)}.",
            )
            self.last_evaluation = result
            return result
        tolerances = self.contract["acceptance_tolerances"]
        if abs(reconstruction.enthalpy_round_trip_residual_J_kg) > float(
            tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
        ) or abs(reconstruction.entropy_round_trip_residual_J_kg_K) > float(
            tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
        ):
            result = _guard(
                self.case_id,
                self.state_id,
                STAGNATION_RECONSTRUCTION_FAILURE,
                "Stagnation Hmass/Smass round trip exceeds the locked tolerance.",
            )
            self.last_evaluation = result
            return result

        try:
            raw = self._raw_b1_result(reconstruction)
        except Exception as exc:
            result = _guard(
                self.case_id,
                self.state_id,
                STAGNATION_RECONSTRUCTION_FAILURE,
                f"Accepted B1 component invocation failed: {type(exc).__name__}: {exc}",
            )
            self.last_evaluation = result
            return result
        mapped = _map_b1_outcome(raw.formal_outcome)
        if mapped not in _SUCCESS_OUTCOMES:
            result = _guard(
                self.case_id,
                self.state_id,
                mapped,
                raw.formal_message,
                raw_b1_outcome=raw.formal_outcome,
            )
            self.last_evaluation = result
            return result

        locked_area = float(self.contract["geometry"]["pipe_area_m2"])
        if not math.isclose(
            float(pipe_area_m2), locked_area, rel_tol=0.0, abs_tol=1.0e-15
        ):
            result = _guard(
                self.case_id,
                self.state_id,
                NONFINITE_INPUT,
                f"Pipe area {pipe_area_m2!r} does not match locked area {locked_area!r}.",
                raw_b1_outcome=raw.formal_outcome,
            )
            self.last_evaluation = result
            return result

        A_pipe = locked_area
        A_open = A_pipe * self.opening_fraction
        A_closed = A_pipe - A_open
        p_i = reconstruction.static.pressure_pa
        zero_drop = self._locked_zero_drop_applies(reconstruction, raw)
        if zero_drop:
            formal_outcome = SUCCESS_ZERO_DROP_WALL_IDENTITY
            p_d = p_i
            effective_velocity = 0.0
            effective_mass_flux = 0.0
            mass = 0.0
            advective = 0.0
            energy = 0.0
            message = (
                "Locked B2 static-coordinate zero-drop identity applied exactly. "
                f"Raw B1 outcome {raw.formal_outcome!r} is retained; no B1 law, "
                "contract value, or tolerance was changed. "
                f"stagnation-minus-static="
                f"{reconstruction.stagnation_pressure_pa - p_i:.17g} Pa."
            )
        else:
            formal_outcome = mapped
            if mapped == SUCCESS_CLOSED_WALL_MAPPING:
                p_d = p_i
            else:
                if raw.evaluation_pressure_pa is None:
                    result = _guard(
                        self.case_id,
                        self.state_id,
                        STAGNATION_RECONSTRUCTION_FAILURE,
                        "Successful B1 stream lacks an evaluation pressure.",
                        raw_b1_outcome=raw.formal_outcome,
                    )
                    self.last_evaluation = result
                    return result
                p_d = float(raw.evaluation_pressure_pa)
            effective_velocity = float(raw.effective_velocity_m_s)
            effective_mass_flux = float(raw.effective_mass_flux_kg_m2_s)
            mass = float(raw.mass_transfer_outward_kg_s)
            advective = float(raw.momentum_stream_transfer_outward_N)
            energy = float(raw.energy_transfer_outward_W)
            message = (
                "Production-side B2 Adapter mapped the accepted B1 stream and "
                "separately retained open/closed static pressure forces."
            )

        open_pressure = p_d * A_open
        closed_pressure = p_i * A_closed
        total_momentum = advective + open_pressure + closed_pressure
        F_rho = mass / A_pipe
        F_rho_u = total_momentum / A_pipe
        F_rho_E = energy / A_pipe
        reconstructed_momentum_flux = (
            advective / A_pipe
            + p_d * self.opening_fraction
            + p_i * (1.0 - self.opening_fraction)
        )
        face = FaceFluxResult(
            case_id=self.case_id,
            state_id=self.state_id,
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
            stagnation_temperature_K=reconstruction.stagnation_temperature_K,
            stagnation_enthalpy_J_kg=reconstruction.stagnation_enthalpy_J_kg,
            stagnation_entropy_J_kg_K=reconstruction.stagnation_entropy_J_kg_K,
            stagnation_enthalpy_round_trip_residual_J_kg=(
                reconstruction.enthalpy_round_trip_residual_J_kg
            ),
            stagnation_entropy_round_trip_residual_J_kg_K=(
                reconstruction.entropy_round_trip_residual_J_kg_K
            ),
            back_pressure_pa=self.back_pressure_pa,
            critical_pressure_pa=raw.critical_pressure_pa,
            discharge_state_pressure_pa=p_d,
            opening_fraction=self.opening_fraction,
            discharge_coefficient=self.discharge_coefficient,
            pipe_area_m2=A_pipe,
            open_area_m2=A_open,
            closed_area_m2=A_closed,
            effective_velocity_m_s=effective_velocity,
            effective_mass_flux_kg_m2_s=effective_mass_flux,
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
            pressure_decomposition_residual_pa=(
                F_rho_u - reconstructed_momentum_flux
            ),
            raw_b1_formal_outcome=raw.formal_outcome,
            raw_b1_formal_message=raw.formal_message,
            raw_b1_evaluation_pressure_pa=raw.evaluation_pressure_pa,
            raw_b1_critical_pressure_pa=raw.critical_pressure_pa,
            zero_drop_canonicalized=zero_drop,
        )
        evaluation = FaceEvaluation(
            case_id=self.case_id,
            state_id=self.state_id,
            formal_outcome=formal_outcome,
            formal_message=message,
            face=face,
            raw_b1_formal_outcome=raw.formal_outcome,
        )
        self.last_evaluation = evaluation
        return evaluation

    def _require_success(self, U: np.ndarray, area_m2: float) -> FaceFluxResult:
        evaluation = self.evaluate(U, area_m2)
        if not evaluation.succeeded or evaluation.face is None:
            raise B2AdapterError(
                evaluation.formal_outcome,
                evaluation.formal_message,
            )
        return evaluation.face

    def limit_dt(
        self,
        *,
        U: np.ndarray,
        eos: EOSModel,
        grid: UniformGrid,
        t: float,
        candidate_dt: float,
    ) -> float:
        del eos, t
        if not math.isfinite(candidate_dt) or candidate_dt <= 0.0:
            raise ValueError("candidate_dt must be positive and finite")
        face = self._require_success(U[-1], grid.geometry.area_m2)
        cell_volume = grid.geometry.area_m2 * grid.dx
        mass_dt = math.inf
        if face.mass_transfer_outward_kg_s > 0.0:
            mass_dt = (
                float(
                    self.contract["time_step_and_update"][
                        "boundary_mass_removal_fraction_limit"
                    ]
                )
                * float(U[-1, IDX_RHO])
                * cell_volume
                / face.mass_transfer_outward_kg_s
            )
        energy_dt = math.inf
        if face.energy_transfer_outward_W > 0.0:
            energy_dt = (
                float(
                    self.contract["time_step_and_update"][
                        "boundary_energy_removal_fraction_limit"
                    ]
                )
                * float(U[-1, IDX_RHOE])
                * cell_volume
                / face.energy_transfer_outward_W
            )
        accepted = min(float(candidate_dt), mass_dt, energy_dt)
        self.last_dt_limits = {
            "candidate_dt_s": float(candidate_dt),
            "mass_removal_dt_s": float(mass_dt),
            "energy_removal_dt_s": float(energy_dt),
            "accepted_dt_s": float(accepted),
        }
        return float(accepted)

    def evaluate_flux(
        self,
        *,
        U: np.ndarray,
        eos: EOSModel,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> np.ndarray:
        del eos, t, dt
        return self._require_success(U[-1], grid.geometry.area_m2).flux_vector()

    def validate_trial(
        self,
        *,
        U_before: np.ndarray,
        U_trial: np.ndarray,
        eos: EOSModel,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> None:
        del U_before, eos, grid, t, dt
        if not np.all(np.isfinite(U_trial)):
            raise ValueError("trial conserved state contains a nonfinite value")
        rho = U_trial[..., IDX_RHO]
        if np.any(rho <= 0.0):
            raise ValueError("trial density must be positive")
        e = internal_energy(U_trial)
        if np.any(~np.isfinite(e)) or np.any(e <= 0.0):
            raise ValueError("trial internal energy must be positive")
        if not np.all(U_trial[..., IDX_RHO_XV] == 0.0):
            raise ValueError("single-phase rho*xv identity must remain exact zero")
        family = _family(self.contract, self.state_id)
        allowed = {
            normalize_phase(value)
            for value in family["allowed_normalized_phases"]
        }
        for row in np.asarray(U_trial, dtype=float):
            reconstruction = self.provider.reconstruct_from_conserved(row)
            if normalize_phase(reconstruction.static.phase) not in allowed:
                raise ValueError(
                    f"trial phase {reconstruction.static.phase!r} is outside "
                    f"{sorted(allowed)}"
                )


def adapter_for_case(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    case: Mapping[str, Any],
    *,
    provider: B2PropertyProvider | None = None,
    b1_provider: b1.PropertyProvider | None = None,
) -> U3B2FvmDischargeAdapter:
    state_id = str(case["state_id"])
    family = _family(contract, state_id)
    back_pressure = float(
        case.get("back_pressure_override_pa", family["back_pressure_pa"])
    )
    return U3B2FvmDischargeAdapter(
        contract=contract,
        b1_contract=b1_contract,
        state_id=state_id,
        back_pressure_pa=back_pressure,
        opening_fraction=float(case.get("opening_fraction", 0.5)),
        discharge_coefficient=float(case.get("discharge_coefficient", 0.8)),
        case_id=str(case["case_id"]),
        provider=provider,
        b1_provider=b1_provider,
    )


def evaluate_face_case(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    case: Mapping[str, Any],
    *,
    provider: B2PropertyProvider | None = None,
    b1_provider: b1.PropertyProvider | None = None,
) -> FaceEvaluation:
    property_provider = provider or CoolPropB2StateProvider()
    state_id = str(case["state_id"])
    velocity_override = (
        float(case["adjacent_velocity_override_m_s"])
        if "adjacent_velocity_override_m_s" in case
        else None
    )
    subcooling_override = (
        float(case["upstream_subcooling_override_K"])
        if "upstream_subcooling_override_K" in case
        else None
    )
    U, _ = build_uniform_initial_state(
        contract,
        property_provider,
        state_id,
        1,
        velocity_override_m_s=velocity_override,
        subcooling_override_K=subcooling_override,
    )
    mutation = case.get("synthetic_mutation")
    if mutation and mutation.get("field") == "rhoE":
        if mutation.get("value_token") == "NaN":
            U[0, IDX_RHOE] = math.nan
    adapter = adapter_for_case(
        contract,
        b1_contract,
        case,
        provider=property_provider,
        b1_provider=b1_provider,
    )
    return adapter.evaluate(U[0], float(contract["geometry"]["pipe_area_m2"]))


def evaluate_face_matrix(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    *,
    provider: B2PropertyProvider | None = None,
    b1_provider: b1.PropertyProvider | None = None,
) -> tuple[FaceEvaluation, ...]:
    property_provider = provider or CoolPropB2StateProvider()
    rows: list[FaceEvaluation] = []
    for case in contract["benchmark_cases"]:
        if str(case.get("execution_level", "")) not in {"face_mapping", "one_step"}:
            continue
        evaluation = evaluate_face_case(
            contract,
            b1_contract,
            case,
            provider=property_provider,
            b1_provider=b1_provider,
        )
        if str(case["case_id"]) == "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE":
            expected = SUCCESS_UNCHOKED_FACE_MAPPING
        else:
            expected = str(case["expected_outcome"])
        if evaluation.formal_outcome != expected:
            raise AssertionError(
                f"{case['case_id']}: {evaluation.formal_outcome} != {expected}"
            )
        rows.append(evaluation)
    return tuple(rows)


def run_one_step_case(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    *,
    provider: CoolPropB2StateProvider | None = None,
    b1_provider: b1.PropertyProvider | None = None,
) -> OneStepAdapterResult:
    case = _case(contract, "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE")
    property_provider = provider or CoolPropB2StateProvider()
    cells = int(case["cells"])
    cfl = float(case["cfl"])
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, cells)
    U_initial, static = build_uniform_initial_state(
        contract,
        property_provider,
        str(case["state_id"]),
        cells,
    )
    eos = CoolPropSinglePhaseEOS(
        property_provider,
        boundary_temperature_K=static.temperature_K,
    )
    adapter = adapter_for_case(
        contract,
        b1_contract,
        case,
        provider=property_provider,
        b1_provider=b1_provider,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U_initial,
        cfl=cfl,
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=adapter,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    primitive = solver.primitive()
    cfl_dt = cfl * grid.dx / float(
        np.max(np.abs(primitive.u) + primitive.c)
    )
    U_before = np.array(solver.U[-1], copy=True)
    initial_inventory = inventory(
        solver.U,
        grid.dx,
        grid.geometry.area_m2,
    )
    accepted_dt = solver.step()
    if adapter.last_evaluation is None or adapter.last_evaluation.face is None:
        raise AssertionError("one-step Adapter lacks accepted face evaluation")
    face = adapter.last_evaluation.face
    limits = adapter.last_dt_limits
    if solver.boundary_budget is None:
        raise AssertionError("one-step boundary budget is disabled")
    left_flux = np.asarray(solver.boundary_budget.last_left_flux, dtype=float)
    right_flux = np.asarray(solver.boundary_budget.last_right_flux, dtype=float)
    U_after = np.array(solver.U[-1], copy=True)
    expected_after = U_before - accepted_dt / grid.dx * (
        right_flux - left_flux
    )
    scale = max(float(np.max(np.abs(expected_after))), 1.0)
    normalized = float(np.max(np.abs(U_after - expected_after)) / scale)
    final_inventory = inventory(
        solver.U,
        grid.dx,
        grid.geometry.area_m2,
    )
    mass_residual = (
        final_inventory["mass_total"]
        + face.mass_transfer_outward_kg_s * accepted_dt
        - initial_inventory["mass_total"]
    )
    energy_residual = (
        final_inventory["energy_total"]
        + face.energy_transfer_outward_W * accepted_dt
        - initial_inventory["energy_total"]
    )
    expected_momentum = (
        initial_inventory["momentum_total"]
        + grid.geometry.area_m2
        * accepted_dt
        * (left_flux[IDX_MOM] - right_flux[IDX_MOM])
    )
    momentum_residual = (
        final_inventory["momentum_total"] - expected_momentum
    )
    vapor_residual = (
        final_inventory["vapor_mass_total"]
        - initial_inventory["vapor_mass_total"]
    )
    return OneStepAdapterResult(
        case_id=str(case["case_id"]),
        formal_outcome=SUCCESS_ONE_STEP,
        cells=cells,
        cfl=cfl,
        dx_m=grid.dx,
        cfl_dt_s=cfl_dt,
        accepted_dt_s=accepted_dt,
        mass_removal_dt_s=float(limits["mass_removal_dt_s"]),
        energy_removal_dt_s=float(limits["energy_removal_dt_s"]),
        U_before_rho=float(U_before[IDX_RHO]),
        U_before_rho_u=float(U_before[IDX_MOM]),
        U_before_rho_E=float(U_before[IDX_RHOE]),
        U_before_rho_xv=float(U_before[IDX_RHO_XV]),
        left_F_rho=float(left_flux[IDX_RHO]),
        left_F_rho_u=float(left_flux[IDX_MOM]),
        left_F_rho_E=float(left_flux[IDX_RHOE]),
        left_F_rho_xv=float(left_flux[IDX_RHO_XV]),
        right_F_rho=float(right_flux[IDX_RHO]),
        right_F_rho_u=float(right_flux[IDX_MOM]),
        right_F_rho_E=float(right_flux[IDX_RHOE]),
        right_F_rho_xv=float(right_flux[IDX_RHO_XV]),
        U_after_rho=float(U_after[IDX_RHO]),
        U_after_rho_u=float(U_after[IDX_MOM]),
        U_after_rho_E=float(U_after[IDX_RHOE]),
        U_after_rho_xv=float(U_after[IDX_RHO_XV]),
        mass_inventory_residual_kg=float(mass_residual),
        momentum_inventory_residual_kg_m_s=float(momentum_residual),
        energy_inventory_residual_J=float(energy_residual),
        vapor_inventory_residual_kg=float(vapor_residual),
        normalized_balance_residual=normalized,
    )


def face_rows_as_dicts(rows: Sequence[FaceEvaluation]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        payload = {
            "case_id": row.case_id,
            "state_id": row.state_id,
            "formal_outcome": row.formal_outcome,
            "formal_message": row.formal_message,
            "raw_b1_formal_outcome": row.raw_b1_formal_outcome,
            "guard_triggered_before_flux": row.guard_triggered_before_flux,
            "guard_triggered_before_budget": row.guard_triggered_before_budget,
            "guard_triggered_before_state_mutation": (
                row.guard_triggered_before_state_mutation
            ),
        }
        if row.face is not None:
            payload.update(asdict(row.face))
        output.append(payload)
    return output


def evaluate_inventory_orientation_guard(
    *,
    right_outward_sign: int,
) -> FaceEvaluation:
    """Return the locked synthetic ledger-orientation Guard outcome."""

    if right_outward_sign == 1:
        raise ValueError("synthetic orientation guard requires a wrong sign")
    return _guard(
        "G-07_INVENTORY_ORIENTATION_MISMATCH",
        "LIQUID_SMALL_DROP",
        INVENTORY_ORIENTATION_CONTRACT_MISMATCH,
        "Right-outward cumulative discharge was entered with the wrong sign.",
    )
