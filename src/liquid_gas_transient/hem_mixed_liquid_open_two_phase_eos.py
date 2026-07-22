"""Verification-only EOS for mixed liquid and open two-phase CO2 states.

This adapter is the accepted-state EOS required by the first liquid-to-two-phase
crossing specification.  It handles heterogeneous arrays cell by cell, accepting
only compressed/subcooled liquid candidates and open liquid-vapor two-phase
states.  Exact saturation endpoints, vapor-side states, guarded states, and
transported/equilibrium quality mismatches fail explicitly.

The adapter is not connected to production defaults and does not approve a
production HEM closure, physical Validation, an acoustic accuracy band, or design
use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from .hem_equilibrium_quality_sync import HEMEquilibriumQualitySyncConfig
from .hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedConfig,
    HEMEquilibriumSoundSpeedEstimate,
    estimate_coolprop_equilibrium_sound_speed,
)
from .hem_liquid_to_two_phase_crossing import (
    HEMBoundaryPhaseEvaluator,
    HEMLiquidToTwoPhaseCrossingError,
    derive_boundary_regions,
)
from .hem_phase_classification import (
    HEMPhaseClassificationConfig,
    evaluate_coolprop_hem_phase_state,
)
from .state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    N_VARS,
    PrimitiveState,
)


class HEMMixedAcceptedStateEOSError(RuntimeError):
    """Raised when the narrow mixed-phase accepted-state EOS cannot be used safely."""


class HEMAcceptedStateSoundSpeedEstimator(Protocol):
    """Callable contract for the reviewed scalar equilibrium sound-speed estimator."""

    def __call__(
        self,
        rho_kg_m3: float,
        e_j_kg: float,
        *,
        config: HEMEquilibriumSoundSpeedConfig | None = None,
    ) -> HEMEquilibriumSoundSpeedEstimate:
        """Return one guarded equilibrium sound-speed estimate."""


@dataclass(frozen=True)
class _AcceptedCellState:
    """Cached primitive and classification data for one exact ``rho/e`` pair."""

    pressure_pa: float
    temperature_K: float
    equilibrium_quality: float
    void_fraction: float
    sound_speed_m_s: float
    phase_class: str
    boundary_region: str


@dataclass
class VerificationHEMLiquidOpenTwoPhaseEOS:
    """Verification-only accepted-state EOS for liquid/open-two-phase arrays.

    Transported quality must already be synchronized with equilibrium quality.
    Raw post-FVM states with a quality mismatch must be classified directly from
    ``rho/e`` and projected before this strict accepted-state adapter is called.
    """

    quality_tolerance: float = 1.0e-10
    phase_config: HEMPhaseClassificationConfig = field(
        default_factory=HEMPhaseClassificationConfig
    )
    quality_sync_config: HEMEquilibriumQualitySyncConfig = field(
        default_factory=HEMEquilibriumQualitySyncConfig
    )
    sound_speed_config: HEMEquilibriumSoundSpeedConfig = field(
        default_factory=HEMEquilibriumSoundSpeedConfig
    )
    phase_evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state
    sound_speed_estimator: HEMAcceptedStateSoundSpeedEstimator = (
        estimate_coolprop_equilibrium_sound_speed
    )
    _cache: dict[tuple[float, float], _AcceptedCellState] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )
    _last_regions: np.ndarray | None = field(
        init=False,
        default=None,
        repr=False,
    )
    phase_evaluation_count: int = field(init=False, default=0)
    sound_speed_evaluation_count: int = field(init=False, default=0)
    liquid_state_evaluation_count: int = field(init=False, default=0)
    open_two_phase_state_evaluation_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        tolerance = float(self.quality_tolerance)
        if not np.isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("quality_tolerance must be finite and non-negative")
        endpoint_tolerance = float(self.phase_config.endpoint_tolerance)
        if (
            not np.isfinite(endpoint_tolerance)
            or endpoint_tolerance < 0.0
            or endpoint_tolerance >= 0.5
        ):
            raise ValueError(
                "phase endpoint_tolerance must be finite and lie in [0, 0.5)"
            )
        activation_tolerance = float(
            self.quality_sync_config.activation_tolerance
        )
        if tolerance < activation_tolerance:
            raise ValueError(
                "accepted-state quality_tolerance must not be tighter than "
                "the projection activation tolerance"
            )

    @property
    def backend_name(self) -> str:
        return "coolprop_pure_co2_hem_liquid_open_two_phase_verification"

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    @property
    def last_regions(self) -> np.ndarray | None:
        if self._last_regions is None:
            return None
        return np.array(self._last_regions, copy=True)

    def _evaluate_scalar(self, rho: float, e: float) -> _AcceptedCellState:
        key = (float(rho), float(e))
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            phase_state = self.phase_evaluator(
                np.asarray([rho], dtype=float),
                np.asarray([e], dtype=float),
                config=self.phase_config,
            )
        except Exception as exc:
            raise HEMMixedAcceptedStateEOSError(
                f"accepted-state phase evaluation failed: {exc}"
            ) from exc
        self.phase_evaluation_count += 1

        state_rho = np.asarray(phase_state.rho, dtype=float)
        state_e = np.asarray(phase_state.e, dtype=float)
        if state_rho.shape != (1,) or state_e.shape != (1,):
            raise HEMMixedAcceptedStateEOSError(
                "accepted-state phase evaluation must return one scalar cell"
            )
        if (
            float(state_rho[0]) != float(rho)
            or float(state_e[0]) != float(e)
        ):
            raise HEMMixedAcceptedStateEOSError(
                "accepted-state phase evaluation did not preserve rho/e"
            )

        try:
            regions = derive_boundary_regions(
                phase_state,
                config=self.phase_config,
            )
        except HEMLiquidToTwoPhaseCrossingError as exc:
            raise HEMMixedAcceptedStateEOSError(
                f"accepted-state boundary-region mapping failed: {exc}"
            ) from exc
        if regions.shape != (1,):
            raise HEMMixedAcceptedStateEOSError(
                "accepted-state boundary-region mapping returned an invalid shape"
            )

        region = str(regions[0])
        phase_class = str(np.asarray(phase_state.phase_class).astype(str)[0])
        if region == "SATURATED_LIQUID_ENDPOINT":
            raise HEMMixedAcceptedStateEOSError(
                "endpoint_acoustic_closure_not_established: "
                "saturated-liquid endpoint is not an accepted state"
            )
        if region == "SATURATED_VAPOR_ENDPOINT":
            raise HEMMixedAcceptedStateEOSError(
                "saturated-vapor endpoint is not an accepted state"
            )
        if region == "VAPOR_CANDIDATE":
            raise HEMMixedAcceptedStateEOSError(
                "single-phase vapor is outside the mixed liquid/open-two-phase "
                "EOS scope"
            )
        if region not in {"LIQUID_CANDIDATE", "OPEN_TWO_PHASE"}:
            raise HEMMixedAcceptedStateEOSError(
                f"unsupported accepted-state boundary region: {region}"
            )

        quality_defined = bool(np.asarray(phase_state.quality_defined)[0])
        alpha_defined = bool(np.asarray(phase_state.alpha_defined)[0])
        if not quality_defined or not alpha_defined:
            raise HEMMixedAcceptedStateEOSError(
                "accepted liquid/open-two-phase cells require defined quality "
                "and void fraction"
            )

        try:
            acoustic = self.sound_speed_estimator(
                float(rho),
                float(e),
                config=self.sound_speed_config,
            )
        except Exception as exc:
            raise HEMMixedAcceptedStateEOSError(
                f"accepted-state equilibrium sound-speed evaluation failed: {exc}"
            ) from exc
        self.sound_speed_evaluation_count += 1

        if (
            float(acoustic.rho_kg_m3) != float(rho)
            or float(acoustic.e_j_kg) != float(e)
        ):
            raise HEMMixedAcceptedStateEOSError(
                "sound-speed estimator did not preserve the requested rho/e state"
            )
        if str(acoustic.phase_class) != phase_class:
            raise HEMMixedAcceptedStateEOSError(
                "phase classification and sound-speed center phase disagree"
            )

        values = (
            float(np.asarray(phase_state.p, dtype=float)[0]),
            float(np.asarray(phase_state.T, dtype=float)[0]),
            float(np.asarray(phase_state.quality, dtype=float)[0]),
            float(np.asarray(phase_state.alpha, dtype=float)[0]),
            float(acoustic.sound_speed_m_s),
        )
        if not all(np.isfinite(value) for value in values):
            raise HEMMixedAcceptedStateEOSError(
                "accepted-state primitive or acoustic value is non-finite"
            )
        pressure, temperature, quality, alpha, sound_speed = values
        if pressure <= 0.0 or temperature <= 0.0 or sound_speed <= 0.0:
            raise HEMMixedAcceptedStateEOSError(
                "pressure, temperature and equilibrium sound speed must be positive"
            )
        if not 0.0 <= quality <= 1.0:
            raise HEMMixedAcceptedStateEOSError(
                "equilibrium quality lies outside [0, 1]"
            )
        if not 0.0 <= alpha <= 1.0:
            raise HEMMixedAcceptedStateEOSError(
                "void fraction lies outside [0, 1]"
            )

        if region == "LIQUID_CANDIDATE":
            self.liquid_state_evaluation_count += 1
        else:
            self.open_two_phase_state_evaluation_count += 1

        result = _AcceptedCellState(
            pressure_pa=pressure,
            temperature_K=temperature,
            equilibrium_quality=quality,
            void_fraction=alpha,
            sound_speed_m_s=sound_speed,
            phase_class=phase_class,
            boundary_region=region,
        )
        self._cache[key] = result
        return result

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        """Return strict accepted primitives for a heterogeneous supported array."""

        self._last_regions = None
        array = np.asarray(U, dtype=float)
        if array.ndim < 1 or array.shape[-1] != N_VARS:
            raise HEMMixedAcceptedStateEOSError(
                "U must have N_VARS entries in its last dimension"
            )
        if not np.all(np.isfinite(array)):
            raise HEMMixedAcceptedStateEOSError(
                "conserved state contains NaN or infinity"
            )

        rho = np.asarray(array[..., IDX_RHO], dtype=float)
        if np.any(rho <= 0.0):
            raise HEMMixedAcceptedStateEOSError(
                "density must be strictly positive"
            )
        u = np.asarray(array[..., IDX_MOM] / rho, dtype=float)
        E = np.asarray(array[..., IDX_RHOE] / rho, dtype=float)
        e = np.asarray(E - 0.5 * u**2, dtype=float)
        if not np.all(np.isfinite(e)):
            raise HEMMixedAcceptedStateEOSError(
                "internal energy must be finite"
            )
        if np.any(e < 0.0):
            raise HEMMixedAcceptedStateEOSError(
                "internal energy must be non-negative under the current solver guard"
            )

        transported_quality = np.asarray(
            array[..., IDX_RHO_XV] / rho,
            dtype=float,
        )
        if not np.all(np.isfinite(transported_quality)):
            raise HEMMixedAcceptedStateEOSError(
                "transported quality must be finite"
            )
        if np.any(transported_quality < 0.0) or np.any(
            transported_quality > 1.0
        ):
            raise HEMMixedAcceptedStateEOSError(
                "transported quality lies outside [0, 1]"
            )

        p = np.empty_like(rho, dtype=float)
        T = np.empty_like(rho, dtype=float)
        quality = np.empty_like(rho, dtype=float)
        alpha = np.empty_like(rho, dtype=float)
        c = np.empty_like(rho, dtype=float)
        regions = np.empty(rho.shape, dtype="<U36")

        for index in np.ndindex(rho.shape):
            cell = self._evaluate_scalar(
                float(rho[index]),
                float(e[index]),
            )
            p[index] = cell.pressure_pa
            T[index] = cell.temperature_K
            quality[index] = cell.equilibrium_quality
            alpha[index] = cell.void_fraction
            c[index] = cell.sound_speed_m_s
            regions[index] = cell.boundary_region

        mismatch = np.abs(transported_quality - quality)
        if np.any(mismatch > self.quality_tolerance):
            raise HEMMixedAcceptedStateEOSError(
                "transported quality does not match equilibrium quality; "
                f"maximum mismatch={float(np.max(mismatch))}"
            )

        self._last_regions = np.array(regions, copy=True)
        return PrimitiveState(
            rho=np.array(rho, copy=True),
            u=np.array(u, copy=True),
            p=p,
            e=np.array(e, copy=True),
            E=np.array(E, copy=True),
            T=T,
            xv=quality,
            alpha=alpha,
            c=c,
        )

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        raise NotImplementedError(
            "mixed HEM verification currently supports transmissive boundaries only"
        )
