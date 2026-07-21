"""Verification-only equilibrium-quality synchronization for pure-CO2 HEM.

The operator is intentionally separate from the generic ``HEMPhaseChange``
skeleton.  It evaluates equilibrium quality directly from ``rho`` and internal
energy, then projects only the fourth conservative component,

    rho*q <- rho*q_eq

while leaving mass, momentum and total energy bitwise unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from .state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, N_VARS, internal_energy


class HEMEquilibriumQualitySyncError(RuntimeError):
    """Raised when equilibrium-quality projection cannot be applied safely."""


@dataclass(frozen=True)
class HEMQualityEvaluation:
    """Minimal phase/quality data required by the synchronization operator."""

    quality: np.ndarray
    quality_defined: np.ndarray
    raw_phase: np.ndarray
    phase_class: np.ndarray
    scope_status: np.ndarray

    def __post_init__(self) -> None:
        expected = np.asarray(self.quality).shape
        for name in (
            "quality_defined",
            "raw_phase",
            "phase_class",
            "scope_status",
        ):
            if np.asarray(getattr(self, name)).shape != expected:
                raise ValueError(f"{name} must have shape {expected}")


class HEMQualityEvaluator(Protocol):
    """Callable contract for equilibrium phase/quality evaluation from rho/e."""

    def __call__(self, rho: np.ndarray, e: np.ndarray) -> HEMQualityEvaluation:
        """Return equilibrium phase/quality arrays for the supplied state."""


@dataclass(frozen=True)
class HEMEquilibriumQualitySyncConfig:
    """Fail-fast settings for the verification-only projection."""

    activation_tolerance: float = 1.0e-12
    supported_phase_classes: tuple[str, ...] = (
        "compressed_or_subcooled_liquid",
        "liquid_vapor_two_phase",
        "single_phase_vapor",
    )

    def __post_init__(self) -> None:
        if not np.isfinite(self.activation_tolerance) or self.activation_tolerance < 0.0:
            raise ValueError("activation_tolerance must be finite and non-negative")
        if not self.supported_phase_classes:
            raise ValueError("supported_phase_classes must not be empty")


@dataclass(frozen=True)
class HEMEquilibriumQualitySyncResult:
    """Cellwise evidence from one equilibrium-quality projection."""

    U_before: np.ndarray
    U_after: np.ndarray
    rho: np.ndarray
    e: np.ndarray
    q_before: np.ndarray
    q_equilibrium: np.ndarray
    q_after: np.ndarray
    delta_q: np.ndarray
    delta_rho_q: np.ndarray
    raw_phase: np.ndarray
    phase_class: np.ndarray
    scope_status: np.ndarray
    projection_applied: np.ndarray
    activation_tolerance: float

    def summary(self) -> dict[str, object]:
        """Return flat scalar/boolean diagnostics suitable for artifacts."""

        tolerance = self.activation_tolerance
        return {
            "cell_count": int(self.q_before.size),
            "projection_cell_count": int(np.count_nonzero(self.projection_applied)),
            "evaporation_cell_count": int(np.count_nonzero(self.delta_q > tolerance)),
            "condensation_cell_count": int(np.count_nonzero(self.delta_q < -tolerance)),
            "max_abs_delta_q": float(np.max(np.abs(self.delta_q), initial=0.0)),
            "sum_delta_rho_q": float(np.sum(self.delta_rho_q)),
            "mass_bitwise_unchanged": bool(
                np.array_equal(
                    self.U_before[..., IDX_RHO],
                    self.U_after[..., IDX_RHO],
                )
            ),
            "momentum_bitwise_unchanged": bool(
                np.array_equal(
                    self.U_before[..., IDX_MOM],
                    self.U_after[..., IDX_MOM],
                )
            ),
            "energy_bitwise_unchanged": bool(
                np.array_equal(
                    self.U_before[..., IDX_RHOE],
                    self.U_after[..., IDX_RHOE],
                )
            ),
            "quality_synchronized_within_tolerance": bool(
                np.all(np.abs(self.q_after - self.q_equilibrium) <= tolerance)
            ),
            "production_hem_activation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
        }


def coolprop_hem_quality_evaluator(
    rho: np.ndarray,
    e: np.ndarray,
) -> HEMQualityEvaluation:
    """Adapt the reviewed explicit CoolProp phase path to this operator."""

    from .hem_phase_classification import evaluate_coolprop_hem_phase_state

    state = evaluate_coolprop_hem_phase_state(rho, e)
    return HEMQualityEvaluation(
        quality=np.array(state.quality, dtype=float, copy=True),
        quality_defined=np.array(state.quality_defined, dtype=bool, copy=True),
        raw_phase=np.array(state.raw_phase, copy=True),
        phase_class=np.array(state.phase_class, copy=True),
        scope_status=np.array(state.scope_status, copy=True),
    )


@dataclass
class HEMEquilibriumQualityProjection:
    """Project transported ``rho*q`` to equilibrium ``rho*q_eq``.

    The class implements the existing ``PhaseChangeModel.apply`` shape, but is
    deliberately verification-only.  It does not call
    ``eos.primitive_from_conserved`` because the pre-projection state may contain
    the quality mismatch that this operator is responsible for removing.
    """

    evaluator: HEMQualityEvaluator = coolprop_hem_quality_evaluator
    config: HEMEquilibriumQualitySyncConfig = field(
        default_factory=HEMEquilibriumQualitySyncConfig
    )
    last_result: HEMEquilibriumQualitySyncResult | None = field(
        init=False,
        default=None,
    )

    def project(self, U: np.ndarray) -> HEMEquilibriumQualitySyncResult:
        """Return a projected copy and detailed cellwise diagnostics."""

        self.last_result = None
        array = np.asarray(U, dtype=float)
        if array.ndim < 1 or array.shape[-1] != N_VARS:
            raise HEMEquilibriumQualitySyncError(
                "U must have N_VARS entries in its last dimension"
            )
        if not np.all(np.isfinite(array)):
            raise HEMEquilibriumQualitySyncError(
                "conserved state contains NaN or infinity"
            )

        rho = np.asarray(array[..., IDX_RHO], dtype=float)
        if np.any(rho <= 0.0):
            raise HEMEquilibriumQualitySyncError(
                "density must be strictly positive"
            )
        e = np.asarray(internal_energy(array), dtype=float)
        if not np.all(np.isfinite(e)):
            raise HEMEquilibriumQualitySyncError(
                "internal energy must be finite"
            )

        q_before = np.asarray(array[..., IDX_RHO_XV] / rho, dtype=float)
        if not np.all(np.isfinite(q_before)):
            raise HEMEquilibriumQualitySyncError(
                "transported quality must be finite"
            )
        if np.any(q_before < 0.0) or np.any(q_before > 1.0):
            raise HEMEquilibriumQualitySyncError(
                "transported quality lies outside [0, 1]"
            )

        try:
            evaluation = self.evaluator(
                np.array(rho, copy=True),
                np.array(e, copy=True),
            )
        except HEMEquilibriumQualitySyncError:
            raise
        except Exception as exc:
            raise HEMEquilibriumQualitySyncError(
                "equilibrium-quality evaluation failed"
            ) from exc

        q_equilibrium = np.asarray(evaluation.quality, dtype=float)
        expected_shape = rho.shape
        for name, value in (
            ("quality", q_equilibrium),
            ("quality_defined", evaluation.quality_defined),
            ("raw_phase", evaluation.raw_phase),
            ("phase_class", evaluation.phase_class),
            ("scope_status", evaluation.scope_status),
        ):
            if np.asarray(value).shape != expected_shape:
                raise HEMEquilibriumQualitySyncError(
                    f"{name} must have shape {expected_shape}"
                )

        quality_defined = np.asarray(evaluation.quality_defined, dtype=bool)
        if not np.all(quality_defined):
            raise HEMEquilibriumQualitySyncError(
                "equilibrium quality is undefined for one or more cells"
            )

        scope_status = np.asarray(evaluation.scope_status).astype(str)
        if not np.all(scope_status == "supported_candidate"):
            unsupported = sorted(
                set(scope_status.ravel()) - {"supported_candidate"}
            )
            raise HEMEquilibriumQualitySyncError(
                f"state is outside supported HEM scope: {unsupported}"
            )

        phase_class = np.asarray(evaluation.phase_class).astype(str)
        allowed = set(self.config.supported_phase_classes)
        unsupported_phase = sorted(set(phase_class.ravel()) - allowed)
        if unsupported_phase:
            raise HEMEquilibriumQualitySyncError(
                f"unsupported phase class: {unsupported_phase}"
            )

        if not np.all(np.isfinite(q_equilibrium)):
            raise HEMEquilibriumQualitySyncError(
                "equilibrium quality contains NaN or infinity"
            )
        if np.any(q_equilibrium < 0.0) or np.any(q_equilibrium > 1.0):
            raise HEMEquilibriumQualitySyncError(
                "equilibrium quality lies outside [0, 1]"
            )

        delta_q = q_equilibrium - q_before
        projection_applied = (
            np.abs(delta_q) > self.config.activation_tolerance
        )
        projected_rho_q = rho * q_equilibrium

        out = np.array(array, copy=True)
        out[..., IDX_RHO_XV] = np.where(
            projection_applied,
            projected_rho_q,
            array[..., IDX_RHO_XV],
        )
        q_after = np.asarray(out[..., IDX_RHO_XV] / rho, dtype=float)

        if not np.array_equal(
            array[..., :IDX_RHO_XV],
            out[..., :IDX_RHO_XV],
        ):
            raise HEMEquilibriumQualitySyncError(
                "projection modified mass, momentum, or total energy"
            )
        if np.any(
            np.abs(q_after - q_equilibrium)
            > self.config.activation_tolerance
        ):
            raise HEMEquilibriumQualitySyncError(
                "projected quality does not match equilibrium quality"
            )

        result = HEMEquilibriumQualitySyncResult(
            U_before=np.array(array, copy=True),
            U_after=out,
            rho=np.array(rho, copy=True),
            e=np.array(e, copy=True),
            q_before=np.array(q_before, copy=True),
            q_equilibrium=np.array(q_equilibrium, copy=True),
            q_after=np.array(q_after, copy=True),
            delta_q=np.array(delta_q, copy=True),
            delta_rho_q=np.array(
                out[..., IDX_RHO_XV] - array[..., IDX_RHO_XV],
                copy=True,
            ),
            raw_phase=np.array(evaluation.raw_phase, copy=True),
            phase_class=np.array(evaluation.phase_class, copy=True),
            scope_status=np.array(evaluation.scope_status, copy=True),
            projection_applied=np.array(projection_applied, copy=True),
            activation_tolerance=self.config.activation_tolerance,
        )
        self.last_result = result
        return result

    def apply(
        self,
        U: np.ndarray,
        eos: object,
        dt: float,
        t: float,
    ) -> np.ndarray:
        """Apply the projection through the existing phase-change slot."""

        del eos
        if not np.isfinite(dt) or dt < 0.0:
            raise HEMEquilibriumQualitySyncError(
                "dt must be finite and non-negative"
            )
        if not np.isfinite(t):
            raise HEMEquilibriumQualitySyncError("t must be finite")
        return self.project(U).U_after
