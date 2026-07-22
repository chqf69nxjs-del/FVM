"""Verification-only liquid-to-two-phase region and transition classification.

This module implements the first code increment selected by the reviewed Stage 7
boundary-crossing specification. It derives a narrow boundary-region view from
the existing pure-CO2 HEM phase-state contract and classifies changes between a
previous accepted state and a raw post-FVM state.

It does not connect to ``FvmSolver``, project quality, evaluate sound speed, or
change production behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np

from .hem_phase_classification import (
    HEMPhaseClassificationConfig,
    HEMPhaseState,
    evaluate_coolprop_hem_phase_state,
)
from .state import IDX_RHO, N_VARS, internal_energy

BoundaryRegion = Literal[
    "LIQUID_CANDIDATE",
    "SATURATED_LIQUID_ENDPOINT",
    "OPEN_TWO_PHASE",
    "SATURATED_VAPOR_ENDPOINT",
    "VAPOR_CANDIDATE",
]
TransitionEvent = Literal[
    "NO_TRANSITION",
    "BOUNDARY_TOUCH",
    "LIQUID_TO_TWO_PHASE_CROSSING",
    "REVERSE_TRANSITION",
    "FORBIDDEN_TRANSITION",
]

_BOUNDARY_REGIONS: frozenset[str] = frozenset(
    {
        "LIQUID_CANDIDATE",
        "SATURATED_LIQUID_ENDPOINT",
        "OPEN_TWO_PHASE",
        "SATURATED_VAPOR_ENDPOINT",
        "VAPOR_CANDIDATE",
    }
)
_LIQUID_SIDE_REGIONS: frozenset[str] = frozenset(
    {"LIQUID_CANDIDATE", "SATURATED_LIQUID_ENDPOINT"}
)


class HEMLiquidToTwoPhaseCrossingError(RuntimeError):
    """Raised when phase-boundary classification cannot be applied safely."""


class HEMBoundaryPhaseEvaluator(Protocol):
    """Callable contract for direct phase evaluation from ``rho/e``."""

    def __call__(
        self,
        rho: np.ndarray,
        e: np.ndarray,
        *,
        config: HEMPhaseClassificationConfig | None = None,
    ) -> HEMPhaseState:
        """Return the reviewed HEM phase-state arrays."""


@dataclass(frozen=True)
class HEMBoundaryRegionEvaluation:
    """Direct ``rho/e`` phase evaluation plus the derived boundary region."""

    rho: np.ndarray
    e: np.ndarray
    phase_state: HEMPhaseState
    region: np.ndarray
    endpoint_tolerance: float

    def __post_init__(self) -> None:
        expected = self.rho.shape
        if self.e.shape != expected or self.region.shape != expected:
            raise ValueError("rho, e, and region must have matching shapes")

        state_rho = np.asarray(self.phase_state.rho, dtype=float)
        state_e = np.asarray(self.phase_state.e, dtype=float)
        if state_rho.shape != expected or state_e.shape != expected:
            raise ValueError("phase-state shape must match rho/e")
        if not np.array_equal(state_rho, self.rho) or not np.array_equal(
            state_e,
            self.e,
        ):
            raise ValueError("phase-state rho/e must match the evaluated input")


@dataclass(frozen=True)
class HEMTransitionClassification:
    """Cellwise transition events between previous and raw boundary regions."""

    previous_region: np.ndarray
    raw_region: np.ndarray
    event: np.ndarray

    def __post_init__(self) -> None:
        expected = self.previous_region.shape
        if self.raw_region.shape != expected or self.event.shape != expected:
            raise ValueError("previous_region, raw_region, and event must match")

    def summary(self) -> dict[str, int]:
        """Return deterministic event counts for tests and later artifacts."""

        return {
            "cell_count": int(self.event.size),
            "no_transition_count": int(
                np.count_nonzero(self.event == "NO_TRANSITION")
            ),
            "boundary_touch_count": int(
                np.count_nonzero(self.event == "BOUNDARY_TOUCH")
            ),
            "liquid_to_two_phase_crossing_count": int(
                np.count_nonzero(
                    self.event == "LIQUID_TO_TWO_PHASE_CROSSING"
                )
            ),
            "reverse_transition_count": int(
                np.count_nonzero(self.event == "REVERSE_TRANSITION")
            ),
            "forbidden_transition_count": int(
                np.count_nonzero(self.event == "FORBIDDEN_TRANSITION")
            ),
        }


@dataclass(frozen=True)
class HEMRawTransitionDetection:
    """Previous/raw direct evaluations and their cellwise transition events."""

    previous: HEMBoundaryRegionEvaluation
    raw: HEMBoundaryRegionEvaluation
    transitions: HEMTransitionClassification


def _validated_endpoint_tolerance(
    config: HEMPhaseClassificationConfig,
) -> float:
    tolerance = float(config.endpoint_tolerance)
    if not np.isfinite(tolerance) or not 0.0 <= tolerance < 0.5:
        raise HEMLiquidToTwoPhaseCrossingError(
            "endpoint_tolerance must be finite and lie in [0, 0.5)"
        )
    return tolerance


def derive_boundary_regions(
    state: HEMPhaseState,
    *,
    config: HEMPhaseClassificationConfig | None = None,
) -> np.ndarray:
    """Map a reviewed phase state to the crossing specification's regions.

    Required equilibrium qualities are validated but never clipped. Guarded,
    unknown, undefined, non-finite, out-of-range, or internally inconsistent
    phase states fail atomically.
    """

    cfg = config or HEMPhaseClassificationConfig()
    endpoint_tolerance = _validated_endpoint_tolerance(cfg)

    quality = np.asarray(state.quality, dtype=float)
    quality_defined = np.asarray(state.quality_defined, dtype=bool)
    phase_class = np.asarray(state.phase_class).astype(str)
    scope_status = np.asarray(state.scope_status).astype(str)
    raw_phase = np.asarray(state.raw_phase).astype(str)
    expected = quality.shape

    for name, value in (
        ("quality_defined", quality_defined),
        ("phase_class", phase_class),
        ("scope_status", scope_status),
        ("raw_phase", raw_phase),
    ):
        if value.shape != expected:
            raise HEMLiquidToTwoPhaseCrossingError(
                f"{name} must have shape {expected}"
            )

    if not np.all(scope_status == "supported_candidate"):
        statuses = sorted(
            set(scope_status.ravel()) - {"supported_candidate"}
        )
        raise HEMLiquidToTwoPhaseCrossingError(
            f"phase state is guarded, unknown, or unsupported: {statuses}"
        )
    if not np.all(quality_defined):
        raise HEMLiquidToTwoPhaseCrossingError(
            "equilibrium quality is undefined for one or more cells"
        )
    if not np.all(np.isfinite(quality)):
        raise HEMLiquidToTwoPhaseCrossingError(
            "equilibrium quality contains NaN or infinity"
        )
    if np.any(quality < 0.0) or np.any(quality > 1.0):
        raise HEMLiquidToTwoPhaseCrossingError(
            "equilibrium quality lies outside [0, 1]"
        )

    region = np.empty(expected, dtype="<U36")
    for index in np.ndindex(expected):
        phase_i = phase_class[index]
        quality_i = float(quality[index])

        if phase_i == "compressed_or_subcooled_liquid":
            if quality_i > endpoint_tolerance:
                raise HEMLiquidToTwoPhaseCrossingError(
                    "liquid candidate has inconsistent positive equilibrium "
                    "quality"
                )
            region[index] = "LIQUID_CANDIDATE"
        elif phase_i == "liquid_vapor_two_phase":
            if quality_i <= endpoint_tolerance:
                region[index] = "SATURATED_LIQUID_ENDPOINT"
            elif quality_i >= 1.0 - endpoint_tolerance:
                region[index] = "SATURATED_VAPOR_ENDPOINT"
            else:
                region[index] = "OPEN_TWO_PHASE"
        elif phase_i == "single_phase_vapor":
            if quality_i < 1.0 - endpoint_tolerance:
                raise HEMLiquidToTwoPhaseCrossingError(
                    "vapor candidate has inconsistent equilibrium quality"
                )
            region[index] = "VAPOR_CANDIDATE"
        else:
            raise HEMLiquidToTwoPhaseCrossingError(
                f"unsupported phase class for boundary mapping: {phase_i}"
            )

    return region


def evaluate_boundary_regions_from_conserved(
    U: np.ndarray,
    *,
    evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state,
    phase_config: HEMPhaseClassificationConfig | None = None,
) -> HEMBoundaryRegionEvaluation:
    """Evaluate boundary regions directly from the conservative ``rho/e`` state.

    The transported fourth component is not used for phase classification. The
    current global solver guard requiring non-negative internal energy is retained
    for this first integration path.
    """

    cfg = phase_config or HEMPhaseClassificationConfig()
    _validated_endpoint_tolerance(cfg)

    array = np.asarray(U, dtype=float)
    if array.ndim < 1 or array.shape[-1] != N_VARS:
        raise HEMLiquidToTwoPhaseCrossingError(
            "U must have N_VARS entries in its last dimension"
        )
    if not np.all(np.isfinite(array)):
        raise HEMLiquidToTwoPhaseCrossingError(
            "conserved state contains NaN or infinity"
        )

    rho = np.asarray(array[..., IDX_RHO], dtype=float)
    if np.any(rho <= 0.0):
        raise HEMLiquidToTwoPhaseCrossingError(
            "density must be strictly positive"
        )
    e = np.asarray(internal_energy(array), dtype=float)
    if not np.all(np.isfinite(e)):
        raise HEMLiquidToTwoPhaseCrossingError(
            "internal energy must be finite"
        )
    if np.any(e < 0.0):
        raise HEMLiquidToTwoPhaseCrossingError(
            "internal energy must be non-negative under the current solver guard"
        )

    try:
        phase_state = evaluator(
            np.array(rho, copy=True),
            np.array(e, copy=True),
            config=cfg,
        )
    except HEMLiquidToTwoPhaseCrossingError:
        raise
    except Exception as exc:
        raise HEMLiquidToTwoPhaseCrossingError(
            "direct rho/e phase evaluation failed"
        ) from exc

    state_rho = np.asarray(phase_state.rho, dtype=float)
    state_e = np.asarray(phase_state.e, dtype=float)
    if state_rho.shape != rho.shape or state_e.shape != e.shape:
        raise HEMLiquidToTwoPhaseCrossingError(
            "direct phase evaluation returned an incompatible rho/e shape"
        )
    if not np.array_equal(state_rho, rho) or not np.array_equal(state_e, e):
        raise HEMLiquidToTwoPhaseCrossingError(
            "direct phase evaluation did not preserve the requested rho/e state"
        )

    region = derive_boundary_regions(phase_state, config=cfg)
    if region.shape != rho.shape:
        raise HEMLiquidToTwoPhaseCrossingError(
            f"derived boundary region must have shape {rho.shape}"
        )

    return HEMBoundaryRegionEvaluation(
        rho=np.array(rho, copy=True),
        e=np.array(e, copy=True),
        phase_state=phase_state,
        region=np.array(region, copy=True),
        endpoint_tolerance=float(cfg.endpoint_tolerance),
    )


def _classify_transition_event(
    previous: str,
    raw: str,
) -> TransitionEvent:
    if previous == raw:
        return "NO_TRANSITION"
    if (
        previous == "LIQUID_CANDIDATE"
        and raw == "SATURATED_LIQUID_ENDPOINT"
    ):
        return "BOUNDARY_TOUCH"
    if previous in _LIQUID_SIDE_REGIONS and raw == "OPEN_TWO_PHASE":
        return "LIQUID_TO_TWO_PHASE_CROSSING"
    if (
        previous == "SATURATED_LIQUID_ENDPOINT"
        and raw == "LIQUID_CANDIDATE"
    ) or (
        previous == "OPEN_TWO_PHASE"
        and raw in _LIQUID_SIDE_REGIONS
    ):
        return "REVERSE_TRANSITION"
    return "FORBIDDEN_TRANSITION"


def classify_transition_events(
    previous_region: np.ndarray,
    raw_region: np.ndarray,
) -> HEMTransitionClassification:
    """Classify cellwise changes between previous accepted and raw regions."""

    previous = np.asarray(previous_region).astype(str)
    raw = np.asarray(raw_region).astype(str)
    if previous.shape != raw.shape:
        raise HEMLiquidToTwoPhaseCrossingError(
            "previous and raw region arrays must have matching shapes"
        )

    invalid = (set(previous.ravel()) | set(raw.ravel())) - _BOUNDARY_REGIONS
    if invalid:
        raise HEMLiquidToTwoPhaseCrossingError(
            f"unknown boundary region values: {sorted(invalid)}"
        )

    event = np.empty(previous.shape, dtype="<U40")
    for index in np.ndindex(previous.shape):
        event[index] = _classify_transition_event(
            str(previous[index]),
            str(raw[index]),
        )

    return HEMTransitionClassification(
        previous_region=np.array(previous, copy=True),
        raw_region=np.array(raw, copy=True),
        event=event,
    )


def detect_raw_transition_events(
    U_previous: np.ndarray,
    U_raw: np.ndarray,
    *,
    evaluator: HEMBoundaryPhaseEvaluator = evaluate_coolprop_hem_phase_state,
    phase_config: HEMPhaseClassificationConfig | None = None,
) -> HEMRawTransitionDetection:
    """Detect transitions using direct phase evaluations of both ``rho/e`` states."""

    previous = evaluate_boundary_regions_from_conserved(
        U_previous,
        evaluator=evaluator,
        phase_config=phase_config,
    )
    raw = evaluate_boundary_regions_from_conserved(
        U_raw,
        evaluator=evaluator,
        phase_config=phase_config,
    )
    if previous.region.shape != raw.region.shape:
        raise HEMLiquidToTwoPhaseCrossingError(
            "previous and raw conservative states must have matching cell shapes"
        )

    transitions = classify_transition_events(
        previous.region,
        raw.region,
    )
    return HEMRawTransitionDetection(
        previous=previous,
        raw=raw,
        transitions=transitions,
    )
