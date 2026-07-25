"""Verification-only prescribed-subcooled HEM outlet boundary.

This module implements Increment 1 of the reviewed Stage 7 LCO2 pipeline-
depressurization prototype.  It provides:

* a pressure-plus-subcooling thermodynamic state provider;
* a right-side, ``outlet_only`` ghost-cell adapter;
* conservative ghost construction using equilibrium quality; and
* a 65-point preflight for the fixed 5 -> 2/3/4 MPa boundary paths.

No FVM time step is executed here.  The implementation does not model a tank,
valve, or release-rate law and does not approve physical Validation, production
HEM activation, design use, or a two-phase acoustic accuracy band.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Protocol, Sequence

import numpy as np

from .boundary import LinearPressureRamp, PressureSchedule, Side
from .eos import EOSModel
from .hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedConfig,
    HEMEquilibriumSoundSpeedEstimate,
    estimate_coolprop_equilibrium_sound_speed,
)
from .hem_liquid_to_two_phase_crossing import (
    HEMBoundaryPhaseEvaluator,
    derive_boundary_regions,
)
from .hem_mixed_liquid_open_two_phase_eos import (
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from .hem_phase_classification import (
    HEMPhaseClassificationConfig,
    evaluate_coolprop_hem_phase_state,
)
from .state import (
    IDX_MOM,
    IDX_RHO,
    N_VARS,
    PrimitiveState,
    internal_energy,
    make_conserved,
    vapor_mass_fraction,
)

BoundaryFailureCategory = Literal[
    "INVALID_SCHEDULE",
    "PROPERTY_BACKEND_FAILURE",
    "NONFINITE_OR_NONPOSITIVE_STATE",
    "NEGATIVE_INTERNAL_ENERGY",
    "UNSUPPORTED_PHASE_REGION",
    "QUALITY_CONTRACT_FAILURE",
    "ACOUSTIC_EVALUATION_FAILURE",
    "ROUND_TRIP_MISMATCH",
    "MIXED_EOS_REJECTION",
    "REVERSE_FLOW_FALLBACK",
    "INVALID_BOUNDARY_APPLICATION",
]


class HEMPrescribedBoundaryError(RuntimeError):
    """Raised when the narrow prescribed-boundary contract fails."""

    def __init__(self, category: BoundaryFailureCategory, message: str):
        self.category = category
        self.detail = str(message)
        super().__init__(f"{category}: {self.detail}")


class HEMBoundaryPropertyBackend(Protocol):
    """Minimal ``P,T`` property contract used by the state provider."""

    @property
    def backend_name(self) -> str:
        """Return a traceable backend identifier."""

    def saturation_temperature_K(self, pressure_pa: float) -> float:
        """Return saturated-liquid temperature at pressure [K]."""

    def density_kg_m3(self, pressure_pa: float, temperature_K: float) -> float:
        """Return mass density from ``P,T`` [kg/m3]."""

    def internal_energy_j_kg(
        self,
        pressure_pa: float,
        temperature_K: float,
    ) -> float:
        """Return specific internal energy from ``P,T`` [J/kg]."""


class HEMAcceptedStateEOS(Protocol):
    """Narrow accepted-state validation contract."""

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        """Accept a conservative state or raise explicitly."""


class HEMAcceptedStateSoundSpeedEstimator(Protocol):
    """Scalar equilibrium sound-speed estimator contract."""

    def __call__(
        self,
        rho_kg_m3: float,
        e_j_kg: float,
        *,
        config: HEMEquilibriumSoundSpeedConfig | None = None,
    ) -> HEMEquilibriumSoundSpeedEstimate:
        """Return one guarded equilibrium acoustic estimate."""


@dataclass(frozen=True)
class CoolPropCO2BoundaryPropertyBackend:
    """Lazy CoolProp ``P,T`` backend for the verification boundary."""

    fluid: str = "CO2"

    def __post_init__(self) -> None:
        if not self.fluid.strip():
            raise ValueError("fluid must not be empty")

    @property
    def backend_name(self) -> str:
        return "coolprop_co2"

    @staticmethod
    def _props_si():
        try:
            from CoolProp.CoolProp import PropsSI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency path
            raise ImportError(
                "CoolProp is required for the prescribed LCO2 boundary"
            ) from exc
        return PropsSI

    def saturation_temperature_K(self, pressure_pa: float) -> float:
        return float(
            self._props_si()("T", "P", pressure_pa, "Q", 0.0, self.fluid)
        )

    def density_kg_m3(self, pressure_pa: float, temperature_K: float) -> float:
        return float(
            self._props_si()(
                "Dmass",
                "P",
                pressure_pa,
                "T",
                temperature_K,
                self.fluid,
            )
        )

    def internal_energy_j_kg(
        self,
        pressure_pa: float,
        temperature_K: float,
    ) -> float:
        return float(
            self._props_si()(
                "Umass",
                "P",
                pressure_pa,
                "T",
                temperature_K,
                self.fluid,
            )
        )


@dataclass(frozen=True)
class HEMPrescribedBoundaryState:
    """Immutable, fully reviewed thermodynamic state for one boundary time."""

    time_s: float
    backend_name: str
    pressure_requested_pa: float
    subcooling_K: float
    saturation_temperature_K: float
    temperature_requested_K: float
    rho_kg_m3: float
    e_j_kg: float
    equilibrium_quality: float
    void_fraction: float
    pressure_recovered_pa: float
    temperature_recovered_K: float
    sound_speed_m_s: float
    raw_phase: str
    phase_class: str
    boundary_region: str
    scope_status: str
    mixed_eos_accepted: bool


@dataclass(frozen=True)
class _CachedHEMBoundaryThermodynamicState:
    """Cache payload independent of schedule time."""

    backend_name: str
    pressure_requested_pa: float
    subcooling_K: float
    saturation_temperature_K: float
    temperature_requested_K: float
    rho_kg_m3: float
    e_j_kg: float
    equilibrium_quality: float
    void_fraction: float
    pressure_recovered_pa: float
    temperature_recovered_K: float
    sound_speed_m_s: float
    raw_phase: str
    phase_class: str
    boundary_region: str
    scope_status: str
    mixed_eos_accepted: bool

    def at_time(self, time_s: float) -> HEMPrescribedBoundaryState:
        return HEMPrescribedBoundaryState(time_s=float(time_s), **asdict(self))


class HEMPrescribedBoundaryStateProvider(Protocol):
    """Boundary-state provider used by the ghost adapter and path preflight."""

    def state_at(self, t: float) -> HEMPrescribedBoundaryState:
        """Return one validated state at physical/schedule time ``t``."""

    def diagnostics(self) -> dict[str, float | str]:
        """Return flat provider diagnostics."""


@dataclass
class VerificationHEMPrescribedSubcooledStateProvider:
    """Build a strict liquid HEM state from pressure and positive subcooling.

    The pressure schedule remains pressure-only.  This provider closes the real-
    fluid state with ``T = T_sat(P) - subcooling`` and evaluates the exact
    resulting ``rho/e`` through the reviewed phase, boundary-region, acoustic,
    and strict accepted-state EOS paths.
    """

    pressure_schedule: PressureSchedule
    subcooling_K: float = 5.0
    property_backend: HEMBoundaryPropertyBackend = field(
        default_factory=CoolPropCO2BoundaryPropertyBackend
    )
    phase_config: HEMPhaseClassificationConfig = field(
        default_factory=HEMPhaseClassificationConfig
    )
    sound_speed_config: HEMEquilibriumSoundSpeedConfig = field(
        default_factory=HEMEquilibriumSoundSpeedConfig
    )
    phase_evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state
    sound_speed_estimator: HEMAcceptedStateSoundSpeedEstimator = (
        estimate_coolprop_equilibrium_sound_speed
    )
    accepted_state_eos: HEMAcceptedStateEOS | None = None
    pressure_recovery_relative_tolerance: float = 1.0e-6
    pressure_recovery_absolute_tolerance_pa: float = 1.0
    temperature_recovery_relative_tolerance: float = 1.0e-8
    temperature_recovery_absolute_tolerance_K: float = 1.0e-6
    accepted_quality_tolerance: float = 1.0e-10
    _cache: dict[
        tuple[float, float], _CachedHEMBoundaryThermodynamicState
    ] = field(init=False, default_factory=dict, repr=False)
    state_provider_evaluation_count: int = field(init=False, default=0)
    state_provider_cache_hit_count: int = field(init=False, default=0)
    _last_state: HEMPrescribedBoundaryState | None = field(
        init=False,
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not np.isfinite(self.subcooling_K) or self.subcooling_K <= 0.0:
            raise ValueError("subcooling_K must be finite and strictly positive")
        for name, value in (
            (
                "pressure_recovery_relative_tolerance",
                self.pressure_recovery_relative_tolerance,
            ),
            (
                "pressure_recovery_absolute_tolerance_pa",
                self.pressure_recovery_absolute_tolerance_pa,
            ),
            (
                "temperature_recovery_relative_tolerance",
                self.temperature_recovery_relative_tolerance,
            ),
            (
                "temperature_recovery_absolute_tolerance_K",
                self.temperature_recovery_absolute_tolerance_K,
            ),
            ("accepted_quality_tolerance", self.accepted_quality_tolerance),
        ):
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")

        if self.accepted_state_eos is None:
            self.accepted_state_eos = VerificationHEMLiquidOpenTwoPhaseEOS(
                quality_tolerance=self.accepted_quality_tolerance,
                phase_config=self.phase_config,
                sound_speed_config=self.sound_speed_config,
                phase_evaluator=self.phase_evaluator,
                sound_speed_estimator=self.sound_speed_estimator,
            )

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    @property
    def last_state(self) -> HEMPrescribedBoundaryState | None:
        return self._last_state

    @staticmethod
    def _finite_scalar(value: object, name: str) -> float:
        try:
            scalar = float(np.asarray(value, dtype=float))
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "NONFINITE_OR_NONPOSITIVE_STATE",
                f"{name} could not be converted to a scalar",
            ) from exc
        if not np.isfinite(scalar):
            raise HEMPrescribedBoundaryError(
                "NONFINITE_OR_NONPOSITIVE_STATE",
                f"{name} must be finite",
            )
        return scalar

    @staticmethod
    def _scalar_array_value(value: object, name: str) -> object:
        array = np.asarray(value)
        if array.shape != (1,):
            raise HEMPrescribedBoundaryError(
                "PROPERTY_BACKEND_FAILURE",
                f"{name} must have scalar-cell shape (1,), received {array.shape}",
            )
        return array[0]

    @staticmethod
    def _within_tolerance(
        recovered: float,
        requested: float,
        *,
        relative_tolerance: float,
        absolute_tolerance: float,
    ) -> bool:
        limit = max(absolute_tolerance, relative_tolerance * abs(requested))
        return abs(recovered - requested) <= limit

    def _requested_pressure(self, t: float) -> float:
        if not np.isfinite(t):
            raise HEMPrescribedBoundaryError(
                "INVALID_SCHEDULE",
                "boundary time must be finite",
            )
        try:
            pressure = float(self.pressure_schedule.pressure_pa(float(t)))
        except HEMPrescribedBoundaryError:
            raise
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "INVALID_SCHEDULE",
                "pressure schedule evaluation failed",
            ) from exc
        if not np.isfinite(pressure) or pressure <= 0.0:
            raise HEMPrescribedBoundaryError(
                "INVALID_SCHEDULE",
                "pressure schedule must return a finite positive pressure",
            )
        return pressure

    def state_at(self, t: float) -> HEMPrescribedBoundaryState:
        time_s = float(t)
        pressure = self._requested_pressure(time_s)
        state = self.state_for_pressure(pressure, time_s=time_s)
        self._last_state = state
        return state

    def state_for_pressure(
        self,
        pressure_pa: float,
        *,
        time_s: float = 0.0,
    ) -> HEMPrescribedBoundaryState:
        """Evaluate an exact pressure/subcooling key through the full contract."""

        pressure = float(pressure_pa)
        time = float(time_s)
        if not np.isfinite(time):
            raise HEMPrescribedBoundaryError(
                "INVALID_SCHEDULE",
                "boundary time must be finite",
            )
        if not np.isfinite(pressure) or pressure <= 0.0:
            raise HEMPrescribedBoundaryError(
                "INVALID_SCHEDULE",
                "requested pressure must be finite and positive",
            )

        key = (pressure, float(self.subcooling_K))
        cached = self._cache.get(key)
        if cached is not None:
            self.state_provider_cache_hit_count += 1
            state = cached.at_time(time)
            self._last_state = state
            return state

        evaluated = self._evaluate_uncached(pressure)
        self._cache[key] = evaluated
        self.state_provider_evaluation_count += 1
        state = evaluated.at_time(time)
        self._last_state = state
        return state

    def _evaluate_uncached(
        self,
        pressure_pa: float,
    ) -> _CachedHEMBoundaryThermodynamicState:
        try:
            saturation_temperature = float(
                self.property_backend.saturation_temperature_K(pressure_pa)
            )
            temperature = saturation_temperature - float(self.subcooling_K)
            rho = float(
                self.property_backend.density_kg_m3(pressure_pa, temperature)
            )
            e = float(
                self.property_backend.internal_energy_j_kg(
                    pressure_pa,
                    temperature,
                )
            )
            backend_name = str(self.property_backend.backend_name)
        except HEMPrescribedBoundaryError:
            raise
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "PROPERTY_BACKEND_FAILURE",
                "P/subcooling property evaluation failed",
            ) from exc

        if not backend_name.strip():
            raise HEMPrescribedBoundaryError(
                "PROPERTY_BACKEND_FAILURE",
                "property backend name must not be empty",
            )
        if (
            not np.isfinite(saturation_temperature)
            or saturation_temperature <= 0.0
            or not np.isfinite(temperature)
            or temperature <= 0.0
            or not np.isfinite(rho)
            or rho <= 0.0
        ):
            raise HEMPrescribedBoundaryError(
                "NONFINITE_OR_NONPOSITIVE_STATE",
                "saturation temperature, boundary temperature, and density "
                "must be finite and positive",
            )
        if not np.isfinite(e):
            raise HEMPrescribedBoundaryError(
                "NONFINITE_OR_NONPOSITIVE_STATE",
                "internal energy must be finite",
            )
        if e < 0.0:
            raise HEMPrescribedBoundaryError(
                "NEGATIVE_INTERNAL_ENERGY",
                "internal energy must be non-negative under the current guard",
            )

        try:
            phase_state = self.phase_evaluator(
                np.asarray([rho], dtype=float),
                np.asarray([e], dtype=float),
                config=self.phase_config,
            )
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "PROPERTY_BACKEND_FAILURE",
                "reviewed rho/e phase evaluation failed",
            ) from exc

        state_rho = self._finite_scalar(
            self._scalar_array_value(phase_state.rho, "phase_state.rho"),
            "phase_state.rho",
        )
        state_e = self._finite_scalar(
            self._scalar_array_value(phase_state.e, "phase_state.e"),
            "phase_state.e",
        )
        if state_rho != rho or state_e != e:
            raise HEMPrescribedBoundaryError(
                "PROPERTY_BACKEND_FAILURE",
                "reviewed phase evaluator did not preserve exact rho/e",
            )

        scope_status = str(
            self._scalar_array_value(phase_state.scope_status, "scope_status")
        )
        phase_class = str(
            self._scalar_array_value(phase_state.phase_class, "phase_class")
        )
        raw_phase = str(
            self._scalar_array_value(phase_state.raw_phase, "raw_phase")
        )
        if scope_status != "supported_candidate":
            raise HEMPrescribedBoundaryError(
                "UNSUPPORTED_PHASE_REGION",
                f"scope status is {scope_status!r}",
            )

        quality_defined = bool(
            self._scalar_array_value(
                phase_state.quality_defined,
                "quality_defined",
            )
        )
        alpha_defined = bool(
            self._scalar_array_value(phase_state.alpha_defined, "alpha_defined")
        )
        if not quality_defined or not alpha_defined:
            raise HEMPrescribedBoundaryError(
                "QUALITY_CONTRACT_FAILURE",
                "boundary quality and void fraction must both be defined",
            )

        quality = self._finite_scalar(
            self._scalar_array_value(phase_state.quality, "quality"),
            "quality",
        )
        alpha = self._finite_scalar(
            self._scalar_array_value(phase_state.alpha, "alpha"),
            "alpha",
        )
        if not 0.0 <= quality <= 1.0 or not 0.0 <= alpha <= 1.0:
            raise HEMPrescribedBoundaryError(
                "QUALITY_CONTRACT_FAILURE",
                "quality and void fraction must lie in [0, 1]",
            )

        try:
            regions = derive_boundary_regions(
                phase_state,
                config=self.phase_config,
            )
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "UNSUPPORTED_PHASE_REGION",
                "boundary-region derivation failed",
            ) from exc
        region = str(self._scalar_array_value(regions, "boundary_region"))
        if (
            phase_class != "compressed_or_subcooled_liquid"
            or region != "LIQUID_CANDIDATE"
        ):
            raise HEMPrescribedBoundaryError(
                "UNSUPPORTED_PHASE_REGION",
                f"required LIQUID_CANDIDATE, received {phase_class}/{region}",
            )
        endpoint_tolerance = float(self.phase_config.endpoint_tolerance)
        if abs(quality) > endpoint_tolerance or abs(alpha) > endpoint_tolerance:
            raise HEMPrescribedBoundaryError(
                "QUALITY_CONTRACT_FAILURE",
                "subcooled liquid boundary requires zero equilibrium quality "
                "and void fraction within endpoint tolerance",
            )

        pressure_recovered = self._finite_scalar(
            self._scalar_array_value(phase_state.p, "pressure_recovered"),
            "pressure_recovered",
        )
        temperature_recovered = self._finite_scalar(
            self._scalar_array_value(
                phase_state.T,
                "temperature_recovered",
            ),
            "temperature_recovered",
        )
        if pressure_recovered <= 0.0 or temperature_recovered <= 0.0:
            raise HEMPrescribedBoundaryError(
                "NONFINITE_OR_NONPOSITIVE_STATE",
                "recovered pressure and temperature must be positive",
            )

        try:
            acoustic = self.sound_speed_estimator(
                rho,
                e,
                config=self.sound_speed_config,
            )
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "ACOUSTIC_EVALUATION_FAILURE",
                "reviewed equilibrium sound-speed evaluation failed",
            ) from exc
        sound_speed = float(acoustic.sound_speed_m_s)
        if (
            not np.isfinite(sound_speed)
            or sound_speed <= 0.0
            or float(acoustic.rho_kg_m3) != rho
            or float(acoustic.e_j_kg) != e
            or str(acoustic.phase_class) != phase_class
        ):
            raise HEMPrescribedBoundaryError(
                "ACOUSTIC_EVALUATION_FAILURE",
                "acoustic estimate is invalid or inconsistent with rho/e/phase",
            )

        if not self._within_tolerance(
            pressure_recovered,
            pressure_pa,
            relative_tolerance=self.pressure_recovery_relative_tolerance,
            absolute_tolerance=self.pressure_recovery_absolute_tolerance_pa,
        ):
            raise HEMPrescribedBoundaryError(
                "ROUND_TRIP_MISMATCH",
                "P,T -> rho,e -> P pressure recovery exceeded tolerance",
            )
        if not self._within_tolerance(
            temperature_recovered,
            temperature,
            relative_tolerance=self.temperature_recovery_relative_tolerance,
            absolute_tolerance=self.temperature_recovery_absolute_tolerance_K,
        ):
            raise HEMPrescribedBoundaryError(
                "ROUND_TRIP_MISMATCH",
                "P,T -> rho,e -> T temperature recovery exceeded tolerance",
            )
        if not self._within_tolerance(
            float(acoustic.pressure_pa),
            pressure_recovered,
            relative_tolerance=self.pressure_recovery_relative_tolerance,
            absolute_tolerance=self.pressure_recovery_absolute_tolerance_pa,
        ):
            raise HEMPrescribedBoundaryError(
                "ACOUSTIC_EVALUATION_FAILURE",
                "acoustic center pressure disagrees with reviewed phase pressure",
            )

        stationary = make_conserved(rho, 0.0, e, quality)
        try:
            assert self.accepted_state_eos is not None
            accepted = self.accepted_state_eos.primitive_from_conserved(
                stationary[np.newaxis, :]
            )
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "MIXED_EOS_REJECTION",
                "strict mixed accepted-state EOS rejected the boundary state",
            ) from exc

        accepted_values: dict[str, float] = {}
        for name in ("p", "T", "xv", "alpha", "c"):
            accepted_values[name] = self._finite_scalar(
                self._scalar_array_value(
                    getattr(accepted, name),
                    f"accepted.{name}",
                ),
                f"accepted.{name}",
            )
        if (
            accepted_values["p"] <= 0.0
            or accepted_values["T"] <= 0.0
            or accepted_values["c"] <= 0.0
        ):
            raise HEMPrescribedBoundaryError(
                "MIXED_EOS_REJECTION",
                "strict mixed EOS returned non-positive p/T/c",
            )
        if abs(accepted_values["xv"] - quality) > self.accepted_quality_tolerance:
            raise HEMPrescribedBoundaryError(
                "MIXED_EOS_REJECTION",
                "strict mixed EOS equilibrium quality disagrees with provider",
            )

        return _CachedHEMBoundaryThermodynamicState(
            backend_name=backend_name,
            pressure_requested_pa=pressure_pa,
            subcooling_K=float(self.subcooling_K),
            saturation_temperature_K=saturation_temperature,
            temperature_requested_K=temperature,
            rho_kg_m3=rho,
            e_j_kg=e,
            equilibrium_quality=quality,
            void_fraction=alpha,
            pressure_recovered_pa=pressure_recovered,
            temperature_recovered_K=temperature_recovered,
            sound_speed_m_s=sound_speed,
            raw_phase=raw_phase,
            phase_class=phase_class,
            boundary_region=region,
            scope_status=scope_status,
            mixed_eos_accepted=True,
        )

    def diagnostics(self) -> dict[str, float | str]:
        diagnostics: dict[str, float | str] = {
            "state_provider_evaluation_count": float(
                self.state_provider_evaluation_count
            ),
            "state_provider_cache_hit_count": float(
                self.state_provider_cache_hit_count
            ),
            "state_provider_cache_size": float(self.cache_size),
            "state_provider_backend_name": str(self.property_backend.backend_name),
        }
        if self._last_state is not None:
            diagnostics.update(
                {
                    "boundary_pressure_requested_pa": self._last_state.pressure_requested_pa,
                    "boundary_temperature_requested_K": self._last_state.temperature_requested_K,
                    "boundary_rho_kg_m3": self._last_state.rho_kg_m3,
                    "boundary_e_j_kg": self._last_state.e_j_kg,
                    "boundary_equilibrium_quality": self._last_state.equilibrium_quality,
                    "boundary_void_fraction": self._last_state.void_fraction,
                    "boundary_sound_speed_m_s": self._last_state.sound_speed_m_s,
                    "boundary_region": self._last_state.boundary_region,
                }
            )
        return diagnostics


@dataclass
class VerificationHEMPrescribedSubcooledOutletBoundary:
    """Right-side ``outlet_only`` ghost adapter for the reviewed HEM provider."""

    state_provider: HEMPrescribedBoundaryStateProvider
    flow_direction: Literal["outlet_only"] = "outlet_only"
    velocity_policy: Literal["copy"] = "copy"
    boundary_active_count: int = field(init=False, default=0)
    reverse_flow_fallback_count: int = field(init=False, default=0)
    last_flow_policy: str = field(init=False, default="not_applied")
    _last_state: HEMPrescribedBoundaryState | None = field(
        init=False,
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.flow_direction != "outlet_only":
            raise ValueError("only flow_direction='outlet_only' is supported")
        if self.velocity_policy != "copy":
            raise ValueError("only velocity_policy='copy' is supported")

    @property
    def last_state(self) -> HEMPrescribedBoundaryState | None:
        return self._last_state

    @staticmethod
    def _validate_application(
        U_ext: np.ndarray,
        n_ghost: int,
        side: Side,
    ) -> None:
        if side != "right":
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "prescribed subcooled outlet is implemented only on the right side",
            )
        if not isinstance(n_ghost, (int, np.integer)) or n_ghost <= 0:
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "n_ghost must be a positive integer",
            )
        if not isinstance(U_ext, np.ndarray):
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "U_ext must be a NumPy array",
            )
        if U_ext.ndim != 2 or U_ext.shape[1] != N_VARS:
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                f"U_ext must have shape (n, {N_VARS})",
            )
        if U_ext.shape[0] < 3 * n_ghost:
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "U_ext must contain at least n_ghost internal cells",
            )
        if not np.issubdtype(U_ext.dtype, np.floating):
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "U_ext must use a floating-point dtype",
            )

    @staticmethod
    def _validate_interior_block(U_ext: np.ndarray, n_ghost: int) -> None:
        reflective_sources = U_ext[-2 * n_ghost : -n_ghost]
        if reflective_sources.shape != (n_ghost, N_VARS):
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "right reflective source block has an invalid shape",
            )
        if not np.all(np.isfinite(reflective_sources)):
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "right interior source block contains NaN or infinity",
            )
        if np.any(reflective_sources[:, IDX_RHO] <= 0.0):
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "right interior source density must be strictly positive",
            )

    @staticmethod
    def _reflect_right(U_ext: np.ndarray, n_ghost: int) -> None:
        for j in range(n_ghost):
            source = U_ext[-n_ghost - j - 1].copy()
            source[IDX_MOM] *= -1.0
            U_ext[-n_ghost + j] = source

    @staticmethod
    def _build_ghost(
        state: HEMPrescribedBoundaryState,
        interior_velocity_m_s: float,
    ) -> np.ndarray:
        ghost = np.asarray(
            make_conserved(
                state.rho_kg_m3,
                interior_velocity_m_s,
                state.e_j_kg,
                state.equilibrium_quality,
            ),
            dtype=float,
        )
        if ghost.shape != (N_VARS,) or not np.all(np.isfinite(ghost)):
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "constructed ghost state is non-finite or has the wrong shape",
            )
        if float(ghost[IDX_RHO]) <= 0.0:
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "constructed ghost density must be positive",
            )
        ghost_e = float(internal_energy(ghost))
        ghost_q = float(vapor_mass_fraction(ghost))
        if not np.isfinite(ghost_e) or ghost_e < 0.0:
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "constructed ghost internal energy is invalid",
            )
        if ghost_q != float(state.equilibrium_quality):
            raise HEMPrescribedBoundaryError(
                "QUALITY_CONTRACT_FAILURE",
                "constructed ghost quality does not equal provider equilibrium quality",
            )
        return ghost

    def apply(
        self,
        U_ext: np.ndarray,
        n_ghost: int,
        side: Side,
        t: float,
        eos: EOSModel,
    ) -> None:
        """Fill right ghost cells without executing an FVM time step."""

        self._validate_application(U_ext, n_ghost, side)
        self._validate_interior_block(U_ext, n_ghost)

        adjacent = U_ext[-n_ghost - 1].copy()
        rho_i = float(adjacent[IDX_RHO])
        u_i = float(adjacent[IDX_MOM] / rho_i)
        if not np.isfinite(u_i):
            raise HEMPrescribedBoundaryError(
                "INVALID_BOUNDARY_APPLICATION",
                "adjacent interior velocity must be finite",
            )

        if u_i < 0.0:
            self._reflect_right(U_ext, n_ghost)
            self.reverse_flow_fallback_count += 1
            self.last_flow_policy = "reflective_fallback_reverse_flow"
            self._last_state = None
            return

        try:
            state = self.state_provider.state_at(float(t))
        except HEMPrescribedBoundaryError:
            raise
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "PROPERTY_BACKEND_FAILURE",
                "boundary state provider failed",
            ) from exc
        ghost = self._build_ghost(state, u_i)

        try:
            eos.primitive_from_conserved(ghost[np.newaxis, :])
        except Exception as exc:
            raise HEMPrescribedBoundaryError(
                "MIXED_EOS_REJECTION",
                "solver accepted-state EOS rejected the constructed ghost",
            ) from exc

        U_ext[-n_ghost:] = ghost
        self.boundary_active_count += 1
        self.last_flow_policy = "prescribed_subcooled_outlet"
        self._last_state = state

    def diagnostics(self) -> dict[str, float | str]:
        diagnostics: dict[str, float | str] = {
            "boundary_active_count": float(self.boundary_active_count),
            "reverse_flow_fallback_count": float(
                self.reverse_flow_fallback_count
            ),
            "last_flow_policy": self.last_flow_policy,
        }
        provider_diagnostics = self.state_provider.diagnostics()
        diagnostics.update(provider_diagnostics)
        return diagnostics


@dataclass(frozen=True)
class HEMBoundaryPathCaseSpec:
    """One fixed pressure-path preflight case."""

    case_id: str
    role: str
    initial_pressure_pa: float
    final_pressure_pa: float
    subcooling_K: float = 5.0
    sample_count: int = 65

    def __post_init__(self) -> None:
        if not self.case_id.strip() or not self.role.strip():
            raise ValueError("case_id and role must not be empty")
        if (
            not np.isfinite(self.initial_pressure_pa)
            or self.initial_pressure_pa <= 0.0
            or not np.isfinite(self.final_pressure_pa)
            or self.final_pressure_pa <= 0.0
        ):
            raise ValueError("path pressures must be finite and positive")
        if not np.isfinite(self.subcooling_K) or self.subcooling_K <= 0.0:
            raise ValueError("subcooling_K must be finite and positive")
        if self.sample_count < 2:
            raise ValueError("sample_count must be at least 2")


FIXED_PIPELINE_BOUNDARY_PREFLIGHT_CASES: tuple[
    HEMBoundaryPathCaseSpec, ...
] = (
    HEMBoundaryPathCaseSpec(
        case_id="pipeline_crossing_candidate_p5m5_to_p2m5",
        role="first_crossing_candidate",
        initial_pressure_pa=5.0e6,
        final_pressure_pa=2.0e6,
    ),
    HEMBoundaryPathCaseSpec(
        case_id="pipeline_moderate_diagnostic_p5m5_to_p3m5",
        role="moderate_diagnostic",
        initial_pressure_pa=5.0e6,
        final_pressure_pa=3.0e6,
    ),
    HEMBoundaryPathCaseSpec(
        case_id="pipeline_liquid_control_p5m5_to_p4m5",
        role="liquid_negative_control",
        initial_pressure_pa=5.0e6,
        final_pressure_pa=4.0e6,
    ),
)


@dataclass(frozen=True)
class HEMBoundaryPathSampleRecord:
    """One accepted sample from the full boundary-state contract."""

    case_id: str
    role: str
    sample_index: int
    fraction: float
    pressure_requested_pa: float
    saturation_temperature_K: float
    temperature_requested_K: float
    rho_kg_m3: float
    e_j_kg: float
    pressure_recovered_pa: float
    temperature_recovered_K: float
    equilibrium_quality: float
    void_fraction: float
    raw_phase: str
    phase_class: str
    boundary_region: str
    scope_status: str
    sound_speed_m_s: float
    mixed_eos_accepted: bool
    accepted: bool
    failure_reason: str


@dataclass(frozen=True)
class HEMBoundaryPathPreflightResult:
    """Successful, complete preflight for one pressure path."""

    case: HEMBoundaryPathCaseSpec
    records: tuple[HEMBoundaryPathSampleRecord, ...]
    provider_diagnostics: dict[str, float | str]

    def __post_init__(self) -> None:
        if len(self.records) != self.case.sample_count:
            raise ValueError("successful preflight must retain every requested sample")
        if not all(record.accepted for record in self.records):
            raise ValueError("successful preflight cannot contain a rejected sample")

    def summary(self) -> dict[str, object]:
        regions = [record.boundary_region for record in self.records]
        return {
            "case_id": self.case.case_id,
            "role": self.case.role,
            "sample_count": len(self.records),
            "accepted_sample_count": sum(
                int(record.accepted) for record in self.records
            ),
            "initial_pressure_pa": self.case.initial_pressure_pa,
            "final_pressure_pa": self.case.final_pressure_pa,
            "subcooling_K": self.case.subcooling_K,
            "liquid_candidate_count": regions.count("LIQUID_CANDIDATE"),
            "saturated_liquid_endpoint_count": regions.count(
                "SATURATED_LIQUID_ENDPOINT"
            ),
            "open_two_phase_count": regions.count("OPEN_TWO_PHASE"),
            "saturated_vapor_endpoint_count": regions.count(
                "SATURATED_VAPOR_ENDPOINT"
            ),
            "vapor_candidate_count": regions.count("VAPOR_CANDIDATE"),
            "guard_or_backend_failure_count": 0,
            "accepted": True,
            "provider_diagnostics": dict(self.provider_diagnostics),
        }


@dataclass(frozen=True)
class HEMBoundaryPathPreflightSuite:
    """Complete fixed 5 -> 2/3/4 MPa preflight matrix."""

    cases: tuple[HEMBoundaryPathPreflightResult, ...]

    def __post_init__(self) -> None:
        expected_ids = [case.case_id for case in FIXED_PIPELINE_BOUNDARY_PREFLIGHT_CASES]
        actual_ids = [result.case.case_id for result in self.cases]
        if actual_ids != expected_ids:
            raise ValueError("preflight suite case order does not match the fixed matrix")

    @property
    def records(self) -> tuple[HEMBoundaryPathSampleRecord, ...]:
        return tuple(record for case in self.cases for record in case.records)

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": (
                "stage7_lco2_hem_pipeline_boundary_increment1_preflight_v1"
            ),
            "scope": "verification_only",
            "boundary_adapter_implemented": True,
            "pipeline_depressurization_executed": False,
            "fvm_time_step_exercised": False,
            "case_count": len(self.cases),
            "total_sample_count": len(self.records),
            "accepted_sample_count": sum(
                int(record.accepted) for record in self.records
            ),
            "all_cases_accepted": all(
                result.summary()["accepted"] is True for result in self.cases
            ),
            "cases": [result.summary() for result in self.cases],
            "production_default_changed": False,
            "production_hem_activation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "two_phase_acoustic_accuracy_band_approved": False,
        }


class HEMBoundaryPathPreflightError(HEMPrescribedBoundaryError):
    """Fail-fast preflight error retaining the exact failing sample."""

    def __init__(
        self,
        *,
        case_id: str,
        sample_index: int,
        fraction: float,
        cause: HEMPrescribedBoundaryError,
        accepted_records: Sequence[HEMBoundaryPathSampleRecord],
    ):
        self.case_id = case_id
        self.sample_index = int(sample_index)
        self.fraction = float(fraction)
        self.accepted_records = tuple(accepted_records)
        super().__init__(
            cause.category,
            f"case={case_id}, sample_index={sample_index}, "
            f"fraction={fraction:.17g}: {cause.detail}",
        )


BoundaryStateProviderFactory = Callable[
    [PressureSchedule, float], HEMPrescribedBoundaryStateProvider
]


def _default_provider_factory(
    schedule: PressureSchedule,
    subcooling_K: float,
) -> HEMPrescribedBoundaryStateProvider:
    return VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=subcooling_K,
    )


def run_boundary_path_preflight(
    case: HEMBoundaryPathCaseSpec,
    *,
    provider_factory: BoundaryStateProviderFactory = _default_provider_factory,
) -> HEMBoundaryPathPreflightResult:
    """Evaluate all samples through ``state_at`` and fail on the first rejection."""

    schedule = LinearPressureRamp(
        p_initial_pa=case.initial_pressure_pa,
        p_final_pa=case.final_pressure_pa,
        t_start_s=0.0,
        duration_s=1.0,
    )
    try:
        provider = provider_factory(schedule, case.subcooling_K)
    except Exception as exc:
        cause = (
            exc
            if isinstance(exc, HEMPrescribedBoundaryError)
            else HEMPrescribedBoundaryError(
                "PROPERTY_BACKEND_FAILURE",
                "boundary state provider construction failed",
            )
        )
        raise HEMBoundaryPathPreflightError(
            case_id=case.case_id,
            sample_index=0,
            fraction=0.0,
            cause=cause,
            accepted_records=(),
        ) from exc

    records: list[HEMBoundaryPathSampleRecord] = []
    denominator = case.sample_count - 1
    for sample_index in range(case.sample_count):
        fraction = sample_index / denominator
        try:
            state = provider.state_at(fraction)
        except Exception as exc:
            cause = (
                exc
                if isinstance(exc, HEMPrescribedBoundaryError)
                else HEMPrescribedBoundaryError(
                    "PROPERTY_BACKEND_FAILURE",
                    "boundary state provider failed without a classified error",
                )
            )
            raise HEMBoundaryPathPreflightError(
                case_id=case.case_id,
                sample_index=sample_index,
                fraction=fraction,
                cause=cause,
                accepted_records=records,
            ) from exc

        expected_pressure = (
            (1.0 - fraction) * case.initial_pressure_pa
            + fraction * case.final_pressure_pa
        )
        if state.pressure_requested_pa != expected_pressure:
            cause = HEMPrescribedBoundaryError(
                "INVALID_SCHEDULE",
                "linear schedule did not preserve the exact requested path sample",
            )
            raise HEMBoundaryPathPreflightError(
                case_id=case.case_id,
                sample_index=sample_index,
                fraction=fraction,
                cause=cause,
                accepted_records=records,
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
        case=case,
        records=tuple(records),
        provider_diagnostics=dict(provider.diagnostics()),
    )


def run_fixed_pipeline_boundary_preflight(
    *,
    provider_factory: BoundaryStateProviderFactory = _default_provider_factory,
) -> HEMBoundaryPathPreflightSuite:
    """Run the fixed 5 -> 2, 5 -> 3, and 5 -> 4 MPa 65-point matrix."""

    return HEMBoundaryPathPreflightSuite(
        cases=tuple(
            run_boundary_path_preflight(
                case,
                provider_factory=provider_factory,
            )
            for case in FIXED_PIPELINE_BOUNDARY_PREFLIGHT_CASES
        )
    )


def write_pipeline_boundary_preflight_artifacts(
    output_dir: str | Path,
    suite: HEMBoundaryPathPreflightSuite,
) -> dict[str, Path]:
    """Write machine-readable and reviewer-readable Increment 1 evidence."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_pipeline_boundary_increment1_preflight"
    summary = suite.summary()
    rows = [asdict(record) for record in suite.records]

    json_path = destination / f"{stem}.json"
    csv_path = destination / f"{stem}.csv"
    markdown_path = destination / f"{stem}.md"

    json_path.write_text(
        json.dumps(
            {
                **summary,
                "records": rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Stage 7 LCO2 HEM Pipeline Boundary Increment 1 Preflight",
        "",
        "`VERIFICATION ONLY; NO FVM TIME STEP; NO PHYSICAL VALIDATION`",
        "",
        "| case | accepted | samples | liquid | endpoints | open two-phase | failures |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for case_summary in summary["cases"]:
        endpoint_count = int(
            case_summary["saturated_liquid_endpoint_count"]
        ) + int(case_summary["saturated_vapor_endpoint_count"])
        lines.append(
            f"| {case_summary['case_id']} | {case_summary['accepted']} | "
            f"{case_summary['accepted_sample_count']} / "
            f"{case_summary['sample_count']} | "
            f"{case_summary['liquid_candidate_count']} | {endpoint_count} | "
            f"{case_summary['open_two_phase_count']} | "
            f"{case_summary['guard_or_backend_failure_count']} |"
        )
    lines.extend(
        [
            "",
            "- boundary adapter implemented: true",
            "- pipeline depressurization executed: false",
            "- FVM time step exercised: false",
            "- production HEM activation approved: false",
            "- physical Validation: false",
            "- design use acceptance: false",
            "- two-phase acoustic accuracy band approved: false",
        ]
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "markdown": markdown_path}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Stage 7 prescribed-subcooled boundary 65-point preflight."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    suite = run_fixed_pipeline_boundary_preflight()
    paths = write_pipeline_boundary_preflight_artifacts(args.output_dir, suite)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
