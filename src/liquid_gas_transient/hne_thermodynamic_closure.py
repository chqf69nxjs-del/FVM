"""P2-A2 minimal thermodynamic-feedback HNE closure.

This module is intentionally a source-only verification prototype.  It closes a
homogeneous state from independent ``rho``, ``e`` and transported vapor mass
fraction ``q`` using the deterministic surrogate LCO2 reference parameters.
Changing q therefore changes p, T, void fraction and a diagnostic acoustic
response while rho and e remain conserved through the phase-transfer source.

It is NOT a validated physical HNE EOS, nucleation model, metastability model,
slip model, or 1-D hydrodynamic closure.  The acoustic value is a surrogate
diagnostic only and must not be promoted into the FVM flux until a defensible
nonequilibrium acoustic closure is established.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from .properties import SurrogateLCO2PropertyBackend


SCHEMA_VERSION = "stage7_p2_hne_thermodynamic_closure_a2_v1"
ACOUSTIC_AUTHORITY = "SURROGATE_DIAGNOSTIC_ONLY_NOT_HYDRODYNAMIC_CLOSURE"
FORMAL_STATUS = {
    "implemented": True,
    "source_only_thermodynamic_feedback_prototype": True,
    "physical_hne_vertical_slice": False,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}


class HNEThermodynamicClosureError(RuntimeError):
    """Raised when the minimal closure cannot construct an admissible state."""


@dataclass(frozen=True)
class HNEThermodynamicState:
    rho_kg_m3: float
    e_j_kg: float
    vapor_mass_fraction: float
    equilibrium_vapor_mass_fraction: float
    pressure_pa: float
    temperature_K: float
    liquid_density_kg_m3: float
    vapor_density_kg_m3: float
    void_fraction: float
    acoustic_speed_diagnostic_m_s: float
    acoustic_authority: str = ACOUSTIC_AUTHORITY


@dataclass(frozen=True)
class HNESourceStepResult:
    before: HNEThermodynamicState
    after: HNEThermodynamicState
    equilibrium_vapor_mass_fraction: float
    tau_s: float
    dt_s: float
    dt_over_tau: float
    relaxation_factor: float
    mass_density_residual_kg_m3: float
    specific_internal_energy_residual_j_kg: float
    source_integration: str = "EXACT_EXPONENTIAL"


@dataclass(frozen=True)
class SurrogateFrozenQualityThermodynamicClosure:
    """Common-pressure/common-temperature verification closure for independent q.

    Constituent densities use the same pressure slopes as the existing surrogate
    HEM pressure branches.  Constituent internal energies use the same reference
    internal energy, latent heat and heat capacities.  This construction is
    deliberately narrow: it gives a deterministic algebraic closure whose
    equilibrium-q limit recovers the existing surrogate HEM state, while finite
    q disequilibrium feeds back to p/T/alpha.
    """

    backend: SurrogateLCO2PropertyBackend = field(
        default_factory=SurrogateLCO2PropertyBackend
    )
    q_tolerance: float = 1.0e-14
    volume_absolute_tolerance_m3_kg: float = 1.0e-12
    maximum_pressure_pa: float = 1.0e9
    maximum_bisection_iterations: int = 160

    def __post_init__(self) -> None:
        if self.q_tolerance <= 0.0:
            raise ValueError("q_tolerance must be positive")
        if self.volume_absolute_tolerance_m3_kg <= 0.0:
            raise ValueError("volume tolerance must be positive")
        if self.maximum_pressure_pa <= self.backend.p_sat_ref_pa:
            raise ValueError("maximum_pressure_pa must exceed reference pressure")
        if self.maximum_bisection_iterations <= 0:
            raise ValueError("maximum_bisection_iterations must be positive")

    def equilibrium_quality(self, rho_kg_m3: float, e_j_kg: float) -> float:
        self._validate_rho_e(rho_kg_m3, e_j_kg)
        return float(self.backend.equilibrium_quality_from_density(rho_kg_m3))

    def _validate_rho_e(self, rho_kg_m3: float, e_j_kg: float) -> None:
        if not math.isfinite(rho_kg_m3) or rho_kg_m3 <= 0.0:
            raise HNEThermodynamicClosureError("rho must be finite and positive")
        if not math.isfinite(e_j_kg):
            raise HNEThermodynamicClosureError("e must be finite")

    def _validate_q(self, q: float) -> None:
        if not math.isfinite(q) or q < 0.0 or q > 1.0:
            raise HNEThermodynamicClosureError("q must be finite and within [0, 1]")

    def _constituent_densities(self, pressure_pa: float) -> tuple[float, float]:
        if not math.isfinite(pressure_pa) or pressure_pa <= 0.0:
            raise HNEThermodynamicClosureError("pressure must be finite and positive")
        dp = pressure_pa - self.backend.p_sat_ref_pa
        rho_l = (
            self.backend.rho_l_ref_kg_m3
            + dp / self.backend.c_liquid_m_s**2
        )
        rho_v = (
            self.backend.rho_v_ref_kg_m3
            + dp / self.backend.c_vapor_m_s**2
        )
        if not math.isfinite(rho_l) or not math.isfinite(rho_v):
            raise HNEThermodynamicClosureError("nonfinite constituent density")
        if rho_l <= 0.0 or rho_v <= 0.0:
            raise HNEThermodynamicClosureError("nonpositive constituent density")
        return rho_l, rho_v

    def _temperature(self, e_j_kg: float, q: float) -> float:
        cv_mix = (
            (1.0 - q) * self.backend.cv_liquid_j_kgK
            + q * self.backend.cv_vapor_j_kgK
        )
        if not math.isfinite(cv_mix) or cv_mix <= 0.0:
            raise HNEThermodynamicClosureError("invalid mixture heat capacity")
        e_reference = (
            self.backend.e_l_ref_j_kg + q * self.backend.latent_heat_ref_j_kg
        )
        temperature = self.backend.T_sat_ref_K + (e_j_kg - e_reference) / cv_mix
        if not math.isfinite(temperature) or temperature <= 0.0:
            raise HNEThermodynamicClosureError(
                "closure produced nonpositive/nonfinite temperature"
            )
        return temperature

    def _volume_residual(self, pressure_pa: float, rho_kg_m3: float, q: float) -> float:
        rho_l, rho_v = self._constituent_densities(pressure_pa)
        mixture_specific_volume = (1.0 - q) / rho_l + q / rho_v
        return mixture_specific_volume - 1.0 / rho_kg_m3

    def _pressure(self, rho_kg_m3: float, q: float) -> float:
        # Exact single-phase branches recover the existing surrogate HEM formula.
        if q <= self.q_tolerance:
            pressure = self.backend.p_sat_ref_pa + self.backend.c_liquid_m_s**2 * (
                rho_kg_m3 - self.backend.rho_l_ref_kg_m3
            )
            if not math.isfinite(pressure) or pressure <= 0.0:
                raise HNEThermodynamicClosureError(
                    "liquid branch produced nonpositive/nonfinite pressure"
                )
            self._constituent_densities(pressure)
            return pressure
        if q >= 1.0 - self.q_tolerance:
            pressure = self.backend.p_sat_ref_pa + self.backend.c_vapor_m_s**2 * (
                rho_kg_m3 - self.backend.rho_v_ref_kg_m3
            )
            if not math.isfinite(pressure) or pressure <= 0.0:
                raise HNEThermodynamicClosureError(
                    "vapor branch produced nonpositive/nonfinite pressure"
                )
            self._constituent_densities(pressure)
            return pressure

        # The reference pressure is an exact root at equilibrium quality.  Test it
        # explicitly so the tau->0 constructed equilibrium limit is deterministic.
        reference_pressure = self.backend.p_sat_ref_pa
        reference_residual = self._volume_residual(
            reference_pressure, rho_kg_m3, q
        )
        if abs(reference_residual) <= self.volume_absolute_tolerance_m3_kg:
            return reference_pressure

        low = 1.0
        try:
            f_low = self._volume_residual(low, rho_kg_m3, q)
        except HNEThermodynamicClosureError as exc:
            raise HNEThermodynamicClosureError(
                "lower pressure bracket is outside constituent-density scope"
            ) from exc
        high = max(2.0 * reference_pressure, 1.0e7)
        high = min(high, self.maximum_pressure_pa)
        f_high = self._volume_residual(high, rho_kg_m3, q)
        while f_high > 0.0 and high < self.maximum_pressure_pa:
            high = min(2.0 * high, self.maximum_pressure_pa)
            f_high = self._volume_residual(high, rho_kg_m3, q)

        # Specific volume decreases monotonically with pressure in this narrow
        # surrogate closure.  A root requires f(low)>=0 and f(high)<=0.
        if f_low < 0.0 or f_high > 0.0:
            raise HNEThermodynamicClosureError(
                "volume closure has no admissible pressure root in configured scope"
            )

        for _ in range(self.maximum_bisection_iterations):
            mid = 0.5 * (low + high)
            f_mid = self._volume_residual(mid, rho_kg_m3, q)
            if abs(f_mid) <= self.volume_absolute_tolerance_m3_kg:
                return mid
            if f_mid > 0.0:
                low = mid
            else:
                high = mid
        raise HNEThermodynamicClosureError(
            "pressure root did not converge within deterministic iteration limit"
        )

    def evaluate(
        self,
        rho_kg_m3: float,
        e_j_kg: float,
        vapor_mass_fraction: float,
    ) -> HNEThermodynamicState:
        self._validate_rho_e(rho_kg_m3, e_j_kg)
        self._validate_q(vapor_mass_fraction)
        q = float(vapor_mass_fraction)
        q_eq = self.equilibrium_quality(rho_kg_m3, e_j_kg)
        temperature = self._temperature(e_j_kg, q)
        pressure = self._pressure(rho_kg_m3, q)
        rho_l, rho_v = self._constituent_densities(pressure)
        specific_volume = (1.0 - q) / rho_l + q / rho_v
        volume_residual = specific_volume - 1.0 / rho_kg_m3
        if abs(volume_residual) > self.volume_absolute_tolerance_m3_kg:
            raise HNEThermodynamicClosureError(
                "volume closure residual exceeds configured tolerance"
            )
        alpha = (q / rho_v) / specific_volume if q > 0.0 else 0.0
        if not math.isfinite(alpha) or alpha < 0.0 or alpha > 1.0:
            raise HNEThermodynamicClosureError("invalid void fraction")
        acoustic = float(self.backend.sound_speed_from_quality(q))
        if not math.isfinite(acoustic) or acoustic <= 0.0:
            raise HNEThermodynamicClosureError("invalid acoustic diagnostic")
        return HNEThermodynamicState(
            rho_kg_m3=float(rho_kg_m3),
            e_j_kg=float(e_j_kg),
            vapor_mass_fraction=q,
            equilibrium_vapor_mass_fraction=q_eq,
            pressure_pa=pressure,
            temperature_K=temperature,
            liquid_density_kg_m3=rho_l,
            vapor_density_kg_m3=rho_v,
            void_fraction=alpha,
            acoustic_speed_diagnostic_m_s=acoustic,
        )


@dataclass(frozen=True)
class ExactRelaxationThermodynamicSource:
    """Energy-conserving source-only q relaxation with closure feedback."""

    closure: SurrogateFrozenQualityThermodynamicClosure = field(
        default_factory=SurrogateFrozenQualityThermodynamicClosure
    )
    tau_s: float = 1.0e-4

    def __post_init__(self) -> None:
        if math.isnan(self.tau_s) or self.tau_s <= 0.0:
            raise ValueError("tau_s must be positive or +inf")

    def advance(
        self,
        rho_kg_m3: float,
        e_j_kg: float,
        vapor_mass_fraction: float,
        dt_s: float,
    ) -> HNESourceStepResult:
        if not math.isfinite(dt_s) or dt_s < 0.0:
            raise HNEThermodynamicClosureError("dt_s must be finite and nonnegative")
        before = self.closure.evaluate(
            rho_kg_m3, e_j_kg, vapor_mass_fraction
        )
        q_eq = before.equilibrium_vapor_mass_fraction
        if math.isinf(self.tau_s):
            ratio = 0.0
            factor = 1.0
        else:
            ratio = dt_s / self.tau_s
            factor = 0.0 if ratio >= 745.0 else math.exp(-ratio)
        q_new = q_eq + (vapor_mass_fraction - q_eq) * factor
        # Convex exact relaxation should stay bounded; retain a tight numerical
        # guard instead of silently clipping a materially invalid state.
        if q_new < -1.0e-15 or q_new > 1.0 + 1.0e-15:
            raise HNEThermodynamicClosureError("relaxation produced out-of-bounds q")
        q_new = min(max(q_new, 0.0), 1.0)
        after = self.closure.evaluate(rho_kg_m3, e_j_kg, q_new)
        return HNESourceStepResult(
            before=before,
            after=after,
            equilibrium_vapor_mass_fraction=q_eq,
            tau_s=self.tau_s,
            dt_s=dt_s,
            dt_over_tau=ratio,
            relaxation_factor=factor,
            mass_density_residual_kg_m3=after.rho_kg_m3 - before.rho_kg_m3,
            specific_internal_energy_residual_j_kg=after.e_j_kg - before.e_j_kg,
        )
