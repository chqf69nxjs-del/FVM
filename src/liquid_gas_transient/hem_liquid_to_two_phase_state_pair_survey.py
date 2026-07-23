"""Verification-only liquid-state pair survey for the first HEM crossing gate.

The survey screens a small, fixed set of pure-CO2 liquid candidates and ordered
left/right pairs before any FVM time step is attempted.  Candidate states are
constructed from pressure and subcooling margin, converted to the canonical
``rho/e`` representation, and re-evaluated through the reviewed phase and
equilibrium-sound-speed paths.

Pair screening uses a linear blend of the two stationary conservative endpoint
states only as a deterministic numerical-mixing proxy.  It is not an FVM
solution, a thermodynamic process path, or formal crossing evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Protocol, Sequence

import numpy as np

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
from .state import IDX_RHO, N_VARS, internal_energy, make_conserved


CandidateStatus = Literal[
    "ACCEPTED_LIQUID",
    "ENDPOINT_LANDING",
    "OPEN_TWO_PHASE",
    "FORBIDDEN_REGION",
    "GUARD_FAILURE",
    "BACKEND_FAILURE",
]
PointStatus = Literal[
    "LIQUID_POINT",
    "ENDPOINT_LANDING",
    "OPEN_TWO_PHASE",
    "FORBIDDEN_REGION",
    "GUARD_FAILURE",
    "BACKEND_FAILURE",
]
PairOutcome = Literal[
    "ALL_LIQUID",
    "ENDPOINT_LANDING",
    "OPEN_TWO_PHASE",
    "FORBIDDEN_REGION",
    "GUARD_FAILURE",
    "BACKEND_FAILURE",
]


class HEMLiquidStatePairSurveyError(RuntimeError):
    """Raised when the narrow state-pair survey contract is invalid."""


class HEMSurveySoundSpeedEstimator(Protocol):
    """Callable contract for the reviewed scalar equilibrium sound-speed path."""

    def __call__(
        self,
        rho_kg_m3: float,
        e_j_kg: float,
        *,
        config: HEMEquilibriumSoundSpeedConfig | None = None,
    ) -> HEMEquilibriumSoundSpeedEstimate:
        """Return one equilibrium sound-speed estimate."""


PropsSICallable = Callable[..., float]


@dataclass(frozen=True)
class LiquidCandidateSpec:
    """One pressure/subcooling liquid-state construction request."""

    candidate_id: str
    pressure_pa: float
    subcooling_K: float

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id must not be empty")
        if not np.isfinite(self.pressure_pa) or self.pressure_pa <= 0.0:
            raise ValueError("pressure_pa must be finite and positive")
        if not np.isfinite(self.subcooling_K) or self.subcooling_K <= 0.0:
            raise ValueError("subcooling_K must be finite and positive")


@dataclass(frozen=True)
class LiquidStatePairSpec:
    """One ordered left/right candidate pair and its controlled change label."""

    pair_id: str
    left_candidate_id: str
    right_candidate_id: str
    changed_parameter: str
    change_note: str

    def __post_init__(self) -> None:
        if not self.pair_id.strip():
            raise ValueError("pair_id must not be empty")
        if not self.left_candidate_id.strip() or not self.right_candidate_id.strip():
            raise ValueError("pair candidate IDs must not be empty")
        if self.left_candidate_id == self.right_candidate_id:
            raise ValueError("left and right candidate IDs must differ")
        if not self.changed_parameter.strip():
            raise ValueError("changed_parameter must not be empty")


def default_liquid_candidate_specs() -> tuple[LiquidCandidateSpec, ...]:
    """Return the fixed first survey's deliberately small liquid-candidate set."""

    return (
        LiquidCandidateSpec("p5_m10", 5.0e6, 10.0),
        LiquidCandidateSpec("p5_m5", 5.0e6, 5.0),
        LiquidCandidateSpec("p4_m5", 4.0e6, 5.0),
        LiquidCandidateSpec("p4_m2", 4.0e6, 2.0),
        LiquidCandidateSpec("p3_m5", 3.0e6, 5.0),
        LiquidCandidateSpec("p3_m2", 3.0e6, 2.0),
        LiquidCandidateSpec("p3_m1", 3.0e6, 1.0),
        LiquidCandidateSpec("p2_m5", 2.0e6, 5.0),
        LiquidCandidateSpec("p2_m2", 2.0e6, 2.0),
        LiquidCandidateSpec("p2_m1", 2.0e6, 1.0),
        LiquidCandidateSpec("p2_m0p5", 2.0e6, 0.5),
    )


def default_liquid_pair_specs() -> tuple[LiquidStatePairSpec, ...]:
    """Return controlled pressure-span and subcooling variants for screening."""

    return (
        LiquidStatePairSpec(
            "baseline_p5m5_p4m5",
            "p5_m5",
            "p4_m5",
            "baseline",
            "nearest pressure-span baseline at common 5 K subcooling",
        ),
        LiquidStatePairSpec(
            "pressure_span_p5m5_p3m5",
            "p5_m5",
            "p3_m5",
            "right pressure",
            "increase pressure span while retaining common 5 K subcooling",
        ),
        LiquidStatePairSpec(
            "pressure_span_p5m5_p2m5",
            "p5_m5",
            "p2_m5",
            "right pressure",
            "largest fixed-pressure span at common 5 K subcooling",
        ),
        LiquidStatePairSpec(
            "right_subcool_p5m5_p3m2",
            "p5_m5",
            "p3_m2",
            "right subcooling",
            "reduce only the lower-pressure state's subcooling to 2 K",
        ),
        LiquidStatePairSpec(
            "right_subcool_p5m5_p3m1",
            "p5_m5",
            "p3_m1",
            "right subcooling",
            "reduce only the lower-pressure state's subcooling to 1 K",
        ),
        LiquidStatePairSpec(
            "right_subcool_p5m5_p2m2",
            "p5_m5",
            "p2_m2",
            "right subcooling",
            "reduce the 2 MPa right-state subcooling from 5 K to 2 K",
        ),
        LiquidStatePairSpec(
            "right_subcool_p5m5_p2m1",
            "p5_m5",
            "p2_m1",
            "right subcooling",
            "reduce the 2 MPa right-state subcooling to 1 K",
        ),
        LiquidStatePairSpec(
            "right_subcool_p5m5_p2m0p5",
            "p5_m5",
            "p2_m0p5",
            "right subcooling",
            "reduce the 2 MPa right-state subcooling to 0.5 K",
        ),
        LiquidStatePairSpec(
            "left_subcool_p5m10_p2m1",
            "p5_m10",
            "p2_m1",
            "left subcooling",
            "increase only the high-pressure state's subcooling to 10 K",
        ),
    )


@dataclass(frozen=True)
class HEMLiquidStatePairSurveyConfig:
    """Configuration for the fixed property-level screening increment."""

    candidate_specs: tuple[LiquidCandidateSpec, ...] = field(
        default_factory=default_liquid_candidate_specs
    )
    pair_specs: tuple[LiquidStatePairSpec, ...] = field(
        default_factory=default_liquid_pair_specs
    )
    blend_fractions: tuple[float, ...] = tuple(i / 10.0 for i in range(11))
    crossing_evidence_min_quality: float = 1.0e-6
    fluid: str = "CO2"
    phase_config: HEMPhaseClassificationConfig = field(
        default_factory=HEMPhaseClassificationConfig
    )
    sound_speed_config: HEMEquilibriumSoundSpeedConfig = field(
        default_factory=HEMEquilibriumSoundSpeedConfig
    )

    def __post_init__(self) -> None:
        if not self.fluid.strip():
            raise ValueError("fluid must not be empty")
        if not self.candidate_specs:
            raise ValueError("candidate_specs must not be empty")
        candidate_ids = [spec.candidate_id for spec in self.candidate_specs]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        if not self.pair_specs:
            raise ValueError("pair_specs must not be empty")
        pair_ids = [spec.pair_id for spec in self.pair_specs]
        if len(pair_ids) != len(set(pair_ids)):
            raise ValueError("pair IDs must be unique")
        known = set(candidate_ids)
        for spec in self.pair_specs:
            missing = {spec.left_candidate_id, spec.right_candidate_id} - known
            if missing:
                raise ValueError(
                    f"pair {spec.pair_id} references unknown candidates: "
                    f"{sorted(missing)}"
                )

        fractions = np.asarray(self.blend_fractions, dtype=float)
        if fractions.ndim != 1 or fractions.size < 3:
            raise ValueError("blend_fractions must contain at least three values")
        if not np.all(np.isfinite(fractions)):
            raise ValueError("blend_fractions must be finite")
        if np.any(fractions < 0.0) or np.any(fractions > 1.0):
            raise ValueError("blend_fractions must lie in [0, 1]")
        if np.any(np.diff(fractions) <= 0.0):
            raise ValueError("blend_fractions must be strictly increasing")
        if fractions[0] != 0.0 or fractions[-1] != 1.0:
            raise ValueError("blend_fractions must include exact 0 and 1 endpoints")
        if (
            not np.isfinite(self.crossing_evidence_min_quality)
            or not 0.0 < self.crossing_evidence_min_quality < 1.0
        ):
            raise ValueError(
                "crossing_evidence_min_quality must be finite and lie in (0, 1)"
            )


@dataclass(frozen=True)
class CoolPropLimits:
    critical_temperature_K: float
    critical_pressure_pa: float
    triple_temperature_K: float


@dataclass(frozen=True)
class LiquidCandidateRecord:
    candidate_id: str
    pressure_input_pa: float
    subcooling_K: float
    saturation_temperature_K: float | None
    temperature_input_K: float | None
    rho_kg_m3: float | None
    e_j_kg: float | None
    pressure_recovered_pa: float | None
    temperature_recovered_K: float | None
    equilibrium_quality: float | None
    void_fraction: float | None
    raw_phase: str | None
    phase_class: str | None
    scope_status: str | None
    boundary_region: str | None
    sound_speed_m_s: float | None
    critical_temperature_distance_K: float | None
    critical_pressure_distance_pa: float | None
    triple_temperature_margin_K: float | None
    status: CandidateStatus
    accepted: bool
    reason: str


@dataclass(frozen=True)
class BlendPointRecord:
    pair_id: str
    fraction: float
    rho_kg_m3: float | None
    e_j_kg: float | None
    pressure_pa: float | None
    temperature_K: float | None
    equilibrium_quality: float | None
    void_fraction: float | None
    raw_phase: str | None
    phase_class: str | None
    scope_status: str | None
    boundary_region: str | None
    sound_speed_m_s: float | None
    point_status: PointStatus
    reason: str


@dataclass(frozen=True)
class LiquidStatePairRecord:
    pair_id: str
    left_candidate_id: str
    right_candidate_id: str
    changed_parameter: str
    change_note: str
    pressure_span_pa: float | None
    left_subcooling_K: float | None
    right_subcooling_K: float | None
    outcome: PairOutcome
    first_endpoint_fraction: float | None
    first_open_two_phase_fraction: float | None
    endpoint_point_count: int
    open_two_phase_point_count: int
    max_equilibrium_quality: float | None
    minimum_sound_speed_m_s: float | None
    promising_for_dry_run: bool
    reason: str


@dataclass(frozen=True)
class HEMLiquidStatePairSurveyResult:
    config: HEMLiquidStatePairSurveyConfig
    limits: CoolPropLimits
    candidates: tuple[LiquidCandidateRecord, ...]
    pairs: tuple[LiquidStatePairRecord, ...]
    blend_points: tuple[BlendPointRecord, ...]

    def summary(self) -> dict[str, object]:
        candidate_status_counts = {
            status: sum(record.status == status for record in self.candidates)
            for status in (
                "ACCEPTED_LIQUID",
                "ENDPOINT_LANDING",
                "OPEN_TWO_PHASE",
                "FORBIDDEN_REGION",
                "GUARD_FAILURE",
                "BACKEND_FAILURE",
            )
        }
        pair_outcome_counts = {
            outcome: sum(record.outcome == outcome for record in self.pairs)
            for outcome in (
                "ALL_LIQUID",
                "ENDPOINT_LANDING",
                "OPEN_TWO_PHASE",
                "FORBIDDEN_REGION",
                "GUARD_FAILURE",
                "BACKEND_FAILURE",
            )
        }
        promising = [
            record.pair_id for record in self.pairs if record.promising_for_dry_run
        ]
        ranked = sorted(
            (
                (record.max_equilibrium_quality, record.pair_id)
                for record in self.pairs
                if record.max_equilibrium_quality is not None
            ),
            reverse=True,
        )
        return {
            "schema_version": "stage7_lco2_hem_liquid_state_pair_survey_v1",
            "scope": "verification_only",
            "screening_method": "linear_stationary_conservative_blend_proxy",
            "screening_is_fvm_solution": False,
            "candidate_count": len(self.candidates),
            "accepted_liquid_candidate_count": sum(
                record.accepted for record in self.candidates
            ),
            "candidate_status_counts": candidate_status_counts,
            "pair_count": len(self.pairs),
            "pair_outcome_counts": pair_outcome_counts,
            "promising_pair_ids": promising,
            "highest_quality_pair_id": ranked[0][1] if ranked else None,
            "highest_screened_equilibrium_quality": ranked[0][0] if ranked else None,
            "crossing_evidence_min_quality": self.config.crossing_evidence_min_quality,
            "algorithms_or_tolerances_tuned": False,
            "fvm_step_exercised": False,
            "case_a_frozen": False,
            "case_b_frozen": False,
            "production_default_changed": False,
            "production_hem_activation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "two_phase_acoustic_accuracy_band_approved": False,
        }


@dataclass(frozen=True)
class _CanonicalPointState:
    pressure_pa: float | None
    temperature_K: float | None
    equilibrium_quality: float | None
    void_fraction: float | None
    raw_phase: str | None
    phase_class: str | None
    scope_status: str | None
    boundary_region: str | None
    sound_speed_m_s: float | None
    point_status: PointStatus
    reason: str


@dataclass
class _CanonicalPointEvaluator:
    phase_config: HEMPhaseClassificationConfig
    sound_speed_config: HEMEquilibriumSoundSpeedConfig
    phase_evaluator: HEMBoundaryPhaseEvaluator
    sound_speed_estimator: HEMSurveySoundSpeedEstimator
    _cache: dict[tuple[float, float], _CanonicalPointState] = field(
        default_factory=dict
    )

    def evaluate(self, rho: float, e: float) -> _CanonicalPointState:
        key = (float(rho), float(e))
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if not np.isfinite(rho) or rho <= 0.0:
            result = _CanonicalPointState(
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "GUARD_FAILURE",
                "density must be finite and positive",
            )
            self._cache[key] = result
            return result
        if not np.isfinite(e) or e < 0.0:
            result = _CanonicalPointState(
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "GUARD_FAILURE",
                "internal energy must be finite and non-negative under the current solver guard",
            )
            self._cache[key] = result
            return result

        try:
            state = self.phase_evaluator(
                np.asarray([rho], dtype=float),
                np.asarray([e], dtype=float),
                config=self.phase_config,
            )
        except Exception as exc:
            result = _CanonicalPointState(
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "BACKEND_FAILURE",
                f"phase/property evaluation failed: {exc}",
            )
            self._cache[key] = result
            return result

        try:
            state_rho = np.asarray(state.rho, dtype=float)
            state_e = np.asarray(state.e, dtype=float)
            if state_rho.shape != (1,) or state_e.shape != (1,):
                raise ValueError("phase evaluator returned an invalid scalar shape")
            if float(state_rho[0]) != float(rho) or float(state_e[0]) != float(e):
                raise ValueError("phase evaluator did not preserve requested rho/e")

            pressure = float(np.asarray(state.p, dtype=float)[0])
            temperature = float(np.asarray(state.T, dtype=float)[0])
            quality = float(np.asarray(state.quality, dtype=float)[0])
            alpha = float(np.asarray(state.alpha, dtype=float)[0])
            raw_phase = str(np.asarray(state.raw_phase).astype(str)[0])
            phase_class = str(np.asarray(state.phase_class).astype(str)[0])
            scope_status = str(np.asarray(state.scope_status).astype(str)[0])
            quality_defined = bool(np.asarray(state.quality_defined, dtype=bool)[0])
            alpha_defined = bool(np.asarray(state.alpha_defined, dtype=bool)[0])
        except Exception as exc:
            result = _CanonicalPointState(
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "BACKEND_FAILURE",
                f"phase/property contract failed: {exc}",
            )
            self._cache[key] = result
            return result

        if (
            not np.isfinite(pressure)
            or pressure <= 0.0
            or not np.isfinite(temperature)
            or temperature <= 0.0
        ):
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality if np.isfinite(quality) else None,
                alpha if np.isfinite(alpha) else None,
                raw_phase,
                phase_class,
                scope_status,
                None,
                None,
                "BACKEND_FAILURE",
                "phase/property evaluator returned invalid pressure or temperature",
            )
            self._cache[key] = result
            return result

        if scope_status != "supported_candidate":
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality if np.isfinite(quality) else None,
                alpha if np.isfinite(alpha) else None,
                raw_phase,
                phase_class,
                scope_status,
                None,
                None,
                "FORBIDDEN_REGION",
                f"state is outside supported scope: {phase_class}/{scope_status}",
            )
            self._cache[key] = result
            return result

        if not quality_defined or not alpha_defined:
            result = _CanonicalPointState(
                pressure,
                temperature,
                None,
                None,
                raw_phase,
                phase_class,
                scope_status,
                None,
                None,
                "BACKEND_FAILURE",
                "supported liquid/two-phase state requires defined quality and void fraction",
            )
            self._cache[key] = result
            return result
        if (
            not np.isfinite(quality)
            or not 0.0 <= quality <= 1.0
            or not np.isfinite(alpha)
            or not 0.0 <= alpha <= 1.0
        ):
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality if np.isfinite(quality) else None,
                alpha if np.isfinite(alpha) else None,
                raw_phase,
                phase_class,
                scope_status,
                None,
                None,
                "BACKEND_FAILURE",
                "quality or void fraction is invalid",
            )
            self._cache[key] = result
            return result

        try:
            regions = derive_boundary_regions(state, config=self.phase_config)
            if regions.shape != (1,):
                raise ValueError("boundary-region mapping returned an invalid shape")
            region = str(regions[0])
        except HEMLiquidToTwoPhaseCrossingError as exc:
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality,
                alpha,
                raw_phase,
                phase_class,
                scope_status,
                None,
                None,
                "FORBIDDEN_REGION",
                f"boundary-region mapping rejected state: {exc}",
            )
            self._cache[key] = result
            return result
        except Exception as exc:
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality,
                alpha,
                raw_phase,
                phase_class,
                scope_status,
                None,
                None,
                "BACKEND_FAILURE",
                f"boundary-region mapping failed: {exc}",
            )
            self._cache[key] = result
            return result

        if region == "SATURATED_LIQUID_ENDPOINT":
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality,
                alpha,
                raw_phase,
                phase_class,
                scope_status,
                region,
                None,
                "ENDPOINT_LANDING",
                "endpoint_acoustic_closure_not_established",
            )
            self._cache[key] = result
            return result
        if region in {"SATURATED_VAPOR_ENDPOINT", "VAPOR_CANDIDATE"}:
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality,
                alpha,
                raw_phase,
                phase_class,
                scope_status,
                region,
                None,
                "FORBIDDEN_REGION",
                f"{region} is outside the first liquid-to-two-phase survey scope",
            )
            self._cache[key] = result
            return result
        if region not in {"LIQUID_CANDIDATE", "OPEN_TWO_PHASE"}:
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality,
                alpha,
                raw_phase,
                phase_class,
                scope_status,
                region,
                None,
                "FORBIDDEN_REGION",
                f"unsupported boundary region: {region}",
            )
            self._cache[key] = result
            return result

        try:
            acoustic = self.sound_speed_estimator(
                float(rho),
                float(e),
                config=self.sound_speed_config,
            )
            if (
                float(acoustic.rho_kg_m3) != float(rho)
                or float(acoustic.e_j_kg) != float(e)
            ):
                raise ValueError("sound-speed estimator did not preserve rho/e")
            if str(acoustic.phase_class) != phase_class:
                raise ValueError(
                    "phase classification and sound-speed center phase disagree"
                )
            sound_speed = float(acoustic.sound_speed_m_s)
            if not np.isfinite(sound_speed) or sound_speed <= 0.0:
                raise ValueError("sound speed must be finite and positive")
        except Exception as exc:
            result = _CanonicalPointState(
                pressure,
                temperature,
                quality,
                alpha,
                raw_phase,
                phase_class,
                scope_status,
                region,
                None,
                "GUARD_FAILURE",
                f"equilibrium sound-speed evaluation failed: {exc}",
            )
            self._cache[key] = result
            return result

        point_status: PointStatus = (
            "LIQUID_POINT" if region == "LIQUID_CANDIDATE" else "OPEN_TWO_PHASE"
        )
        result = _CanonicalPointState(
            pressure,
            temperature,
            quality,
            alpha,
            raw_phase,
            phase_class,
            scope_status,
            region,
            sound_speed,
            point_status,
            "",
        )
        self._cache[key] = result
        return result


def _coolprop_props_si() -> PropsSICallable:
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover - installed-only path
        raise ImportError("CoolProp is required for the state-pair survey") from exc
    return PropsSI


def _load_limits(props_si: PropsSICallable, fluid: str) -> CoolPropLimits:
    try:
        values = (
            float(props_si("Tcrit", fluid)),
            float(props_si("Pcrit", fluid)),
            float(props_si("Ttriple", fluid)),
        )
    except Exception as exc:
        raise HEMLiquidStatePairSurveyError(
            "CoolProp failed to provide critical/triple limits"
        ) from exc
    if not all(np.isfinite(value) and value > 0.0 for value in values):
        raise HEMLiquidStatePairSurveyError(
            "CoolProp returned invalid critical/triple limits"
        )
    return CoolPropLimits(*values)


def _candidate_failure(
    spec: LiquidCandidateSpec,
    *,
    status: CandidateStatus,
    reason: str,
    saturation_temperature_K: float | None = None,
    temperature_input_K: float | None = None,
    rho_kg_m3: float | None = None,
    e_j_kg: float | None = None,
    point: _CanonicalPointState | None = None,
    limits: CoolPropLimits | None = None,
) -> LiquidCandidateRecord:
    recovered_T = point.temperature_K if point is not None else None
    recovered_p = point.pressure_pa if point is not None else None
    return LiquidCandidateRecord(
        candidate_id=spec.candidate_id,
        pressure_input_pa=spec.pressure_pa,
        subcooling_K=spec.subcooling_K,
        saturation_temperature_K=saturation_temperature_K,
        temperature_input_K=temperature_input_K,
        rho_kg_m3=rho_kg_m3,
        e_j_kg=e_j_kg,
        pressure_recovered_pa=recovered_p,
        temperature_recovered_K=recovered_T,
        equilibrium_quality=(
            point.equilibrium_quality if point is not None else None
        ),
        void_fraction=point.void_fraction if point is not None else None,
        raw_phase=point.raw_phase if point is not None else None,
        phase_class=point.phase_class if point is not None else None,
        scope_status=point.scope_status if point is not None else None,
        boundary_region=point.boundary_region if point is not None else None,
        sound_speed_m_s=point.sound_speed_m_s if point is not None else None,
        critical_temperature_distance_K=(
            abs(recovered_T - limits.critical_temperature_K)
            if recovered_T is not None and limits is not None
            else None
        ),
        critical_pressure_distance_pa=(
            abs(recovered_p - limits.critical_pressure_pa)
            if recovered_p is not None and limits is not None
            else None
        ),
        triple_temperature_margin_K=(
            recovered_T - limits.triple_temperature_K
            if recovered_T is not None and limits is not None
            else None
        ),
        status=status,
        accepted=False,
        reason=reason,
    )


def evaluate_liquid_candidate(
    spec: LiquidCandidateSpec,
    *,
    props_si: PropsSICallable,
    fluid: str,
    limits: CoolPropLimits,
    point_evaluator: _CanonicalPointEvaluator,
) -> LiquidCandidateRecord:
    """Construct and validate one subcooled-liquid candidate."""

    try:
        saturation_temperature = float(
            props_si("T", "P", spec.pressure_pa, "Q", 0.0, fluid)
        )
        temperature = saturation_temperature - spec.subcooling_K
        rho = float(
            props_si("Dmass", "P", spec.pressure_pa, "T", temperature, fluid)
        )
        e = float(
            props_si("Umass", "P", spec.pressure_pa, "T", temperature, fluid)
        )
    except Exception as exc:
        return _candidate_failure(
            spec,
            status="BACKEND_FAILURE",
            reason=f"candidate construction failed: {exc}",
        )

    if not all(
        np.isfinite(value)
        for value in (saturation_temperature, temperature, rho, e)
    ):
        return _candidate_failure(
            spec,
            status="GUARD_FAILURE",
            reason="candidate construction returned a non-finite value",
            saturation_temperature_K=saturation_temperature,
            temperature_input_K=temperature,
            rho_kg_m3=rho,
            e_j_kg=e,
        )
    if temperature <= limits.triple_temperature_K or rho <= 0.0 or e < 0.0:
        return _candidate_failure(
            spec,
            status="GUARD_FAILURE",
            reason=(
                "candidate violates the current triple-temperature, positive-density, "
                "or non-negative-energy guard"
            ),
            saturation_temperature_K=saturation_temperature,
            temperature_input_K=temperature,
            rho_kg_m3=rho,
            e_j_kg=e,
        )

    point = point_evaluator.evaluate(rho, e)
    status_map: dict[PointStatus, CandidateStatus] = {
        "LIQUID_POINT": "ACCEPTED_LIQUID",
        "ENDPOINT_LANDING": "ENDPOINT_LANDING",
        "OPEN_TWO_PHASE": "OPEN_TWO_PHASE",
        "FORBIDDEN_REGION": "FORBIDDEN_REGION",
        "GUARD_FAILURE": "GUARD_FAILURE",
        "BACKEND_FAILURE": "BACKEND_FAILURE",
    }
    status = status_map[point.point_status]
    if status != "ACCEPTED_LIQUID":
        return _candidate_failure(
            spec,
            status=status,
            reason=point.reason or f"candidate classified as {point.point_status}",
            saturation_temperature_K=saturation_temperature,
            temperature_input_K=temperature,
            rho_kg_m3=rho,
            e_j_kg=e,
            point=point,
            limits=limits,
        )

    if point.equilibrium_quality != 0.0 or point.void_fraction != 0.0:
        return _candidate_failure(
            spec,
            status="BACKEND_FAILURE",
            reason="accepted liquid candidate must have software q=0 and alpha=0",
            saturation_temperature_K=saturation_temperature,
            temperature_input_K=temperature,
            rho_kg_m3=rho,
            e_j_kg=e,
            point=point,
            limits=limits,
        )

    return LiquidCandidateRecord(
        candidate_id=spec.candidate_id,
        pressure_input_pa=spec.pressure_pa,
        subcooling_K=spec.subcooling_K,
        saturation_temperature_K=saturation_temperature,
        temperature_input_K=temperature,
        rho_kg_m3=rho,
        e_j_kg=e,
        pressure_recovered_pa=point.pressure_pa,
        temperature_recovered_K=point.temperature_K,
        equilibrium_quality=point.equilibrium_quality,
        void_fraction=point.void_fraction,
        raw_phase=point.raw_phase,
        phase_class=point.phase_class,
        scope_status=point.scope_status,
        boundary_region=point.boundary_region,
        sound_speed_m_s=point.sound_speed_m_s,
        critical_temperature_distance_K=abs(
            float(point.temperature_K) - limits.critical_temperature_K
        ),
        critical_pressure_distance_pa=abs(
            float(point.pressure_pa) - limits.critical_pressure_pa
        ),
        triple_temperature_margin_K=(
            float(point.temperature_K) - limits.triple_temperature_K
        ),
        status="ACCEPTED_LIQUID",
        accepted=True,
        reason="",
    )


def _pair_outcome_from_points(points: Sequence[BlendPointRecord]) -> PairOutcome:
    statuses = {point.point_status for point in points}
    if "BACKEND_FAILURE" in statuses:
        return "BACKEND_FAILURE"
    if "GUARD_FAILURE" in statuses:
        return "GUARD_FAILURE"
    if "FORBIDDEN_REGION" in statuses:
        return "FORBIDDEN_REGION"
    if "OPEN_TWO_PHASE" in statuses:
        return "OPEN_TWO_PHASE"
    if "ENDPOINT_LANDING" in statuses:
        return "ENDPOINT_LANDING"
    return "ALL_LIQUID"


def screen_liquid_state_pair(
    spec: LiquidStatePairSpec,
    left: LiquidCandidateRecord,
    right: LiquidCandidateRecord,
    *,
    blend_fractions: Sequence[float],
    crossing_evidence_min_quality: float,
    point_evaluator: _CanonicalPointEvaluator,
) -> tuple[LiquidStatePairRecord, tuple[BlendPointRecord, ...]]:
    """Screen one ordered pair using a deterministic conservative-blend proxy."""

    if not left.accepted or not right.accepted:
        statuses = {left.status, right.status}
        if "BACKEND_FAILURE" in statuses:
            outcome: PairOutcome = "BACKEND_FAILURE"
        elif "GUARD_FAILURE" in statuses:
            outcome = "GUARD_FAILURE"
        elif "FORBIDDEN_REGION" in statuses:
            outcome = "FORBIDDEN_REGION"
        elif "OPEN_TWO_PHASE" in statuses:
            outcome = "OPEN_TWO_PHASE"
        else:
            outcome = "ENDPOINT_LANDING"
        record = LiquidStatePairRecord(
            pair_id=spec.pair_id,
            left_candidate_id=left.candidate_id,
            right_candidate_id=right.candidate_id,
            changed_parameter=spec.changed_parameter,
            change_note=spec.change_note,
            pressure_span_pa=None,
            left_subcooling_K=left.subcooling_K,
            right_subcooling_K=right.subcooling_K,
            outcome=outcome,
            first_endpoint_fraction=None,
            first_open_two_phase_fraction=None,
            endpoint_point_count=0,
            open_two_phase_point_count=0,
            max_equilibrium_quality=None,
            minimum_sound_speed_m_s=None,
            promising_for_dry_run=False,
            reason=(
                "pair endpoint candidate was rejected: "
                f"{left.candidate_id}={left.status}, {right.candidate_id}={right.status}"
            ),
        )
        return record, ()

    assert left.rho_kg_m3 is not None and left.e_j_kg is not None
    assert right.rho_kg_m3 is not None and right.e_j_kg is not None
    U_left = make_conserved(left.rho_kg_m3, 0.0, left.e_j_kg, 0.0)
    U_right = make_conserved(right.rho_kg_m3, 0.0, right.e_j_kg, 0.0)

    points: list[BlendPointRecord] = []
    for fraction_raw in blend_fractions:
        fraction = float(fraction_raw)
        U = (1.0 - fraction) * U_left + fraction * U_right
        array = np.asarray(U, dtype=float)
        if array.shape != (N_VARS,) or not np.all(np.isfinite(array)):
            points.append(
                BlendPointRecord(
                    spec.pair_id,
                    fraction,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "GUARD_FAILURE",
                    "conservative blend is invalid",
                )
            )
            continue
        rho = float(array[IDX_RHO])
        e = float(internal_energy(array))
        canonical = point_evaluator.evaluate(rho, e)
        points.append(
            BlendPointRecord(
                pair_id=spec.pair_id,
                fraction=fraction,
                rho_kg_m3=rho,
                e_j_kg=e,
                pressure_pa=canonical.pressure_pa,
                temperature_K=canonical.temperature_K,
                equilibrium_quality=canonical.equilibrium_quality,
                void_fraction=canonical.void_fraction,
                raw_phase=canonical.raw_phase,
                phase_class=canonical.phase_class,
                scope_status=canonical.scope_status,
                boundary_region=canonical.boundary_region,
                sound_speed_m_s=canonical.sound_speed_m_s,
                point_status=canonical.point_status,
                reason=canonical.reason,
            )
        )

    outcome = _pair_outcome_from_points(points)
    endpoint_fractions = [
        point.fraction
        for point in points
        if point.point_status == "ENDPOINT_LANDING"
    ]
    open_fractions = [
        point.fraction for point in points if point.point_status == "OPEN_TWO_PHASE"
    ]
    finite_qualities = [
        float(point.equilibrium_quality)
        for point in points
        if point.equilibrium_quality is not None
        and np.isfinite(point.equilibrium_quality)
    ]
    finite_speeds = [
        float(point.sound_speed_m_s)
        for point in points
        if point.sound_speed_m_s is not None and np.isfinite(point.sound_speed_m_s)
    ]
    max_quality = max(finite_qualities) if finite_qualities else None
    minimum_speed = min(finite_speeds) if finite_speeds else None
    promising = bool(
        outcome == "OPEN_TWO_PHASE"
        and max_quality is not None
        and max_quality >= crossing_evidence_min_quality
        and all(
            point.sound_speed_m_s is not None and point.sound_speed_m_s > 0.0
            for point in points
            if point.point_status == "OPEN_TWO_PHASE"
        )
    )

    reason = ""
    if outcome in {"BACKEND_FAILURE", "GUARD_FAILURE", "FORBIDDEN_REGION"}:
        first = next(
            point
            for point in points
            if point.point_status
            in {"BACKEND_FAILURE", "GUARD_FAILURE", "FORBIDDEN_REGION"}
        )
        reason = first.reason
    elif outcome == "ENDPOINT_LANDING":
        reason = "blend proxy reached only the unresolved saturated-liquid endpoint"
    elif outcome == "ALL_LIQUID":
        reason = "all sampled conservative blends remained liquid candidates"
    elif not promising:
        reason = (
            "open-two-phase points were found, but the screening quality evidence "
            "or acoustic requirement was not met"
        )

    return (
        LiquidStatePairRecord(
            pair_id=spec.pair_id,
            left_candidate_id=left.candidate_id,
            right_candidate_id=right.candidate_id,
            changed_parameter=spec.changed_parameter,
            change_note=spec.change_note,
            pressure_span_pa=(
                float(left.pressure_recovered_pa)
                - float(right.pressure_recovered_pa)
            ),
            left_subcooling_K=left.subcooling_K,
            right_subcooling_K=right.subcooling_K,
            outcome=outcome,
            first_endpoint_fraction=(
                min(endpoint_fractions) if endpoint_fractions else None
            ),
            first_open_two_phase_fraction=(
                min(open_fractions) if open_fractions else None
            ),
            endpoint_point_count=len(endpoint_fractions),
            open_two_phase_point_count=len(open_fractions),
            max_equilibrium_quality=max_quality,
            minimum_sound_speed_m_s=minimum_speed,
            promising_for_dry_run=promising,
            reason=reason,
        ),
        tuple(points),
    )


def run_liquid_state_pair_survey(
    config: HEMLiquidStatePairSurveyConfig | None = None,
    *,
    props_si: PropsSICallable | None = None,
    phase_evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state,
    sound_speed_estimator: HEMSurveySoundSpeedEstimator = (
        estimate_coolprop_equilibrium_sound_speed
    ),
) -> HEMLiquidStatePairSurveyResult:
    """Run the fixed candidate and conservative-blend screening survey."""

    cfg = config or HEMLiquidStatePairSurveyConfig()
    props = props_si or _coolprop_props_si()
    limits = _load_limits(props, cfg.fluid)
    point_evaluator = _CanonicalPointEvaluator(
        phase_config=cfg.phase_config,
        sound_speed_config=cfg.sound_speed_config,
        phase_evaluator=phase_evaluator,
        sound_speed_estimator=sound_speed_estimator,
    )

    candidates = tuple(
        evaluate_liquid_candidate(
            spec,
            props_si=props,
            fluid=cfg.fluid,
            limits=limits,
            point_evaluator=point_evaluator,
        )
        for spec in cfg.candidate_specs
    )
    by_id = {record.candidate_id: record for record in candidates}

    pairs: list[LiquidStatePairRecord] = []
    points: list[BlendPointRecord] = []
    for spec in cfg.pair_specs:
        pair, pair_points = screen_liquid_state_pair(
            spec,
            by_id[spec.left_candidate_id],
            by_id[spec.right_candidate_id],
            blend_fractions=cfg.blend_fractions,
            crossing_evidence_min_quality=cfg.crossing_evidence_min_quality,
            point_evaluator=point_evaluator,
        )
        pairs.append(pair)
        points.extend(pair_points)

    return HEMLiquidStatePairSurveyResult(
        config=cfg,
        limits=limits,
        candidates=candidates,
        pairs=tuple(pairs),
        blend_points=tuple(points),
    )


def _config_payload(config: HEMLiquidStatePairSurveyConfig) -> dict[str, object]:
    return {
        "fluid": config.fluid,
        "crossing_evidence_min_quality": config.crossing_evidence_min_quality,
        "blend_fractions": list(config.blend_fractions),
        "phase_config": asdict(config.phase_config),
        "sound_speed_config": asdict(config.sound_speed_config),
        "candidate_specs": [asdict(spec) for spec in config.candidate_specs],
        "pair_specs": [asdict(spec) for spec in config.pair_specs],
    }


def write_liquid_state_pair_survey_artifacts(
    output_dir: str | Path,
    result: HEMLiquidStatePairSurveyResult,
) -> dict[str, Path]:
    """Write JSON, CSV, Markdown, and NPZ evidence for one survey."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_liquid_state_pair_survey"
    paths = {
        "json": target / f"{stem}.json",
        "candidates_csv": target / f"{stem}_candidates.csv",
        "pairs_csv": target / f"{stem}_pairs.csv",
        "blend_points_csv": target / f"{stem}_blend_points.csv",
        "markdown": target / f"{stem}.md",
        "npz": target / f"{stem}.npz",
    }

    summary = result.summary()
    payload = {
        **summary,
        "config": _config_payload(result.config),
        "coolprop_limits": asdict(result.limits),
        "candidates": [asdict(record) for record in result.candidates],
        "pairs": [asdict(record) for record in result.pairs],
        "blend_points": [asdict(record) for record in result.blend_points],
    }
    paths["json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    for key, records in (
        ("candidates_csv", result.candidates),
        ("pairs_csv", result.pairs),
        ("blend_points_csv", result.blend_points),
    ):
        rows = [asdict(record) for record in records]
        with paths[key].open("w", encoding="utf-8", newline="") as handle:
            if rows:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            else:
                handle.write("")

    lines = [
        "# Stage 7 Liquid-to-Two-Phase State-Pair Survey",
        "",
        "`VERIFICATION ONLY; PROPERTY-LEVEL SCREENING; NOT AN FVM CROSSING RESULT`",
        "",
        "## Summary",
        "",
        f"- candidate count: `{summary['candidate_count']}`",
        f"- accepted liquid candidates: `{summary['accepted_liquid_candidate_count']}`",
        f"- pair count: `{summary['pair_count']}`",
        f"- promising pair IDs: `{summary['promising_pair_ids']}`",
        f"- highest screened quality: `{summary['highest_screened_equilibrium_quality']}`",
        "",
        "The linear conservative blend is a deterministic screening proxy only. It is not",
        "a finite-volume time step, a thermodynamic process path, or formal crossing evidence.",
        "",
        "## Candidate ledger",
        "",
        "| candidate | P [MPa] | subcool [K] | T [K] | e [J/kg] | region | c [m/s] | status |",
        "|---|---:|---:|---:|---:|---|---:|---|",
    ]
    for record in result.candidates:
        lines.append(
            "| {id} | {p:.6g} | {m:.6g} | {T} | {e} | {region} | {c} | {status} |".format(
                id=record.candidate_id,
                p=record.pressure_input_pa / 1.0e6,
                m=record.subcooling_K,
                T=(
                    f"{record.temperature_recovered_K:.9g}"
                    if record.temperature_recovered_K is not None
                    else "—"
                ),
                e=(
                    f"{record.e_j_kg:.9g}"
                    if record.e_j_kg is not None
                    else "—"
                ),
                region=record.boundary_region or "—",
                c=(
                    f"{record.sound_speed_m_s:.9g}"
                    if record.sound_speed_m_s is not None
                    else "—"
                ),
                status=record.status,
            )
        )
    lines.extend(
        [
            "",
            "## Pair screening ledger",
            "",
            "| pair | changed parameter | outcome | first open fraction | max q_eq | promising |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for record in result.pairs:
        lines.append(
            "| {id} | {changed} | {outcome} | {first} | {q} | {promising} |".format(
                id=record.pair_id,
                changed=record.changed_parameter,
                outcome=record.outcome,
                first=(
                    f"{record.first_open_two_phase_fraction:.6g}"
                    if record.first_open_two_phase_fraction is not None
                    else "—"
                ),
                q=(
                    f"{record.max_equilibrium_quality:.9g}"
                    if record.max_equilibrium_quality is not None
                    else "—"
                ),
                promising=record.promising_for_dry_run,
            )
        )
    lines.extend(
        [
            "",
            "## Approval boundary",
            "",
            "```text",
            "fvm_step_exercised = false",
            "case_a_frozen = false",
            "case_b_frozen = false",
            "production_hem_activation_approved = false",
            "physical_validation = false",
            "design_use_acceptance = false",
            "two_phase_acoustic_accuracy_band_approved = false",
            "```",
        ]
    )
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")

    np.savez_compressed(
        paths["npz"],
        candidate_ids=np.asarray(
            [record.candidate_id for record in result.candidates], dtype="<U64"
        ),
        candidate_status=np.asarray(
            [record.status for record in result.candidates], dtype="<U32"
        ),
        candidate_pressure_pa=np.asarray(
            [record.pressure_input_pa for record in result.candidates], dtype=float
        ),
        candidate_subcooling_K=np.asarray(
            [record.subcooling_K for record in result.candidates], dtype=float
        ),
        pair_ids=np.asarray([record.pair_id for record in result.pairs], dtype="<U96"),
        pair_outcome=np.asarray(
            [record.outcome for record in result.pairs], dtype="<U32"
        ),
        pair_max_quality=np.asarray(
            [
                np.nan
                if record.max_equilibrium_quality is None
                else record.max_equilibrium_quality
                for record in result.pairs
            ],
            dtype=float,
        ),
        blend_pair_ids=np.asarray(
            [record.pair_id for record in result.blend_points], dtype="<U96"
        ),
        blend_fraction=np.asarray(
            [record.fraction for record in result.blend_points], dtype=float
        ),
        blend_status=np.asarray(
            [record.point_status for record in result.blend_points], dtype="<U32"
        ),
        blend_quality=np.asarray(
            [
                np.nan
                if record.equilibrium_quality is None
                else record.equilibrium_quality
                for record in result.blend_points
            ],
            dtype=float,
        ),
    )
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Stage 7 liquid state-pair property survey"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("verification/stage7_lco2_hem_liquid_state_pair_survey"),
    )
    args = parser.parse_args(argv)
    result = run_liquid_state_pair_survey()
    write_liquid_state_pair_survey_artifacts(args.output_dir, result)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
