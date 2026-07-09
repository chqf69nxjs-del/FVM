"""Equation-of-state interfaces and simple verification EOS models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import numpy as np

from .state import (
    IDX_RHO,
    IDX_MOM,
    IDX_RHOE,
    IDX_RHO_XV,
    PrimitiveState,
)


class EOSModel(Protocol):
    """Minimal EOS interface required by the FVM solver."""

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        """Convert conservative state to primitive/thermodynamic state."""

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        """Return density for pressure boundary construction when supported."""


@dataclass(frozen=True)
class LinearLiquidEOS:
    """Linear weakly-compressible liquid EOS for verification.

    p = p_ref + c_ref^2 (rho - rho_ref)

    This EOS is intentionally simple. It is useful for single-phase acoustic
    and water-hammer verification, but it is not a complete real-fluid CO2 EOS.
    """

    rho_ref: float = 1000.0
    p_ref: float = 1.0e5
    c_ref: float = 1000.0
    T_ref: float = 293.15
    cv: float = 2000.0
    e_ref: float = 1.0e5

    def __post_init__(self) -> None:
        if self.rho_ref <= 0.0:
            raise ValueError("rho_ref must be positive")
        if self.c_ref <= 0.0:
            raise ValueError("c_ref must be positive")
        if self.cv <= 0.0:
            raise ValueError("cv must be positive")

    def pressure_from_density(self, rho: np.ndarray | float) -> np.ndarray:
        rho_arr = np.asarray(rho, dtype=float)
        return self.p_ref + self.c_ref**2 * (rho_arr - self.rho_ref)

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        p_arr = np.asarray(p, dtype=float)
        return self.rho_ref + (p_arr - self.p_ref) / self.c_ref**2

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        rho = U[..., IDX_RHO]
        u = U[..., IDX_MOM] / rho
        E = U[..., IDX_RHOE] / rho
        e = E - 0.5 * u**2
        xv = U[..., IDX_RHO_XV] / rho
        p = self.pressure_from_density(rho)
        c = np.full_like(rho, self.c_ref, dtype=float)
        T = self.T_ref + (e - self.e_ref) / self.cv

        # Ver.0.2 has no two-phase thermodynamics. Keep alpha as a diagnostic
        # proxy only. HEM/HNE will replace this with phase-density calculation.
        alpha = np.clip(xv, 0.0, 1.0)
        return PrimitiveState(rho=rho, u=u, p=p, e=e, E=E, T=T, xv=xv, alpha=alpha, c=c)


@dataclass(frozen=True)
class StiffenedGasEOS:
    """Optional stiffened-gas EOS skeleton.

    p = (gamma - 1) rho e - gamma pi
    c^2 = gamma (p + pi) / rho

    This is provided as a future verification alternative. It is not used by
    the default Case C skeleton.
    """

    gamma: float = 4.4
    pi: float = 6.0e8
    cv: float = 2000.0

    def __post_init__(self) -> None:
        if self.gamma <= 1.0:
            raise ValueError("gamma must be > 1")
        if self.pi < 0.0:
            raise ValueError("pi must be non-negative")
        if self.cv <= 0.0:
            raise ValueError("cv must be positive")

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        rho = U[..., IDX_RHO]
        u = U[..., IDX_MOM] / rho
        E = U[..., IDX_RHOE] / rho
        e = E - 0.5 * u**2
        xv = U[..., IDX_RHO_XV] / rho
        p = (self.gamma - 1.0) * rho * e - self.gamma * self.pi
        c2 = self.gamma * (p + self.pi) / rho
        if np.any(c2 <= 0.0):
            raise ValueError("stiffened-gas EOS produced non-positive sound-speed squared")
        c = np.sqrt(c2)
        T = e / self.cv
        alpha = np.clip(xv, 0.0, 1.0)
        return PrimitiveState(rho=rho, u=u, p=p, e=e, E=E, T=T, xv=xv, alpha=alpha, c=c)

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        raise NotImplementedError(
            "StiffenedGasEOS needs an additional thermodynamic variable to invert pressure."
        )


@dataclass(frozen=True)
class ToyHEMEOS:
    """Toy homogeneous-equilibrium two-phase EOS for Ver.0.3 verification.

    This is not a real LCO2 property model. It is a deliberately small EOS
    used to verify the software path for HEM flash:

    * density determines the equilibrium vapor mass fraction through the
      saturated mixture specific-volume relation,
    * pressure is clamped near ``p_sat`` inside the two-phase density interval,
    * the diagnostic void fraction is computed from phase volumes,
    * the sound speed is reduced in the two-phase interval.

    The model is useful for code verification because all important quantities
    are analytic and monotone. Real-fluid CO2 properties are planned for a later
    version.
    """

    rho_l_sat: float = 930.0
    rho_v_sat: float = 40.0
    p_sat: float = 1.9e6
    c_liquid: float = 1000.0
    c_vapor: float = 250.0
    c_two_phase_min: float = 80.0
    T_sat: float = 253.15
    cv_liquid: float = 2100.0
    e_ref: float = 1.0e5

    def __post_init__(self) -> None:
        if self.rho_l_sat <= 0.0 or self.rho_v_sat <= 0.0:
            raise ValueError("saturated phase densities must be positive")
        if self.rho_l_sat <= self.rho_v_sat:
            raise ValueError("rho_l_sat must be greater than rho_v_sat")
        if self.p_sat <= 0.0:
            raise ValueError("p_sat must be positive")
        if min(self.c_liquid, self.c_vapor, self.c_two_phase_min) <= 0.0:
            raise ValueError("sound speeds must be positive")
        if self.cv_liquid <= 0.0:
            raise ValueError("cv_liquid must be positive")

    def equilibrium_vapor_mass_fraction_from_density(self, rho: np.ndarray | float) -> np.ndarray:
        """Return equilibrium vapor mass fraction from mixture density.

        Uses

            1/rho = (1-x)/rho_l + x/rho_v

        clipped to [0, 1].
        """

        rho_arr = np.asarray(rho, dtype=float)
        inv_rho = 1.0 / rho_arr
        inv_l = 1.0 / self.rho_l_sat
        inv_v = 1.0 / self.rho_v_sat
        x = (inv_rho - inv_l) / (inv_v - inv_l)
        return np.clip(x, 0.0, 1.0)

    def alpha_from_rho_xv(self, rho: np.ndarray | float, xv: np.ndarray | float) -> np.ndarray:
        """Return vapor volume fraction from mixture density and vapor mass fraction."""

        x = np.clip(np.asarray(xv, dtype=float), 0.0, 1.0)
        v_v = x / self.rho_v_sat
        v_l = (1.0 - x) / self.rho_l_sat
        denom = v_v + v_l
        alpha = np.divide(v_v, denom, out=np.zeros_like(v_v, dtype=float), where=denom > 0.0)
        return np.clip(alpha, 0.0, 1.0)

    def equilibrium_vapor_mass_fraction(self, prim: PrimitiveState) -> np.ndarray:
        """Return HEM equilibrium x_v for a primitive state."""

        return self.equilibrium_vapor_mass_fraction_from_density(prim.rho)

    def pressure_from_density(self, rho: np.ndarray | float) -> np.ndarray:
        """Return a simple pressure compatible with the toy HEM density law."""

        rho_arr = np.asarray(rho, dtype=float)
        p = np.empty_like(rho_arr, dtype=float)

        liquid = rho_arr >= self.rho_l_sat
        vapor = rho_arr <= self.rho_v_sat
        two_phase = ~(liquid | vapor)

        p[liquid] = self.p_sat + self.c_liquid**2 * (rho_arr[liquid] - self.rho_l_sat)
        p[two_phase] = self.p_sat
        p[vapor] = self.p_sat + self.c_vapor**2 * (rho_arr[vapor] - self.rho_v_sat)
        return p

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        """Approximate density inversion for pressure boundary construction.

        Pressure is not one-to-one in the two-phase plateau. For boundary use we
        choose saturated liquid density at p_sat.
        """

        p_arr = np.asarray(p, dtype=float)
        rho = np.empty_like(p_arr, dtype=float)
        above = p_arr >= self.p_sat
        rho[above] = self.rho_l_sat + (p_arr[above] - self.p_sat) / self.c_liquid**2
        rho[~above] = self.rho_v_sat + (p_arr[~above] - self.p_sat) / self.c_vapor**2
        return np.maximum(rho, 1.0e-6)

    def sound_speed_from_rho_xv(self, rho: np.ndarray | float, xv: np.ndarray | float) -> np.ndarray:
        """Return a bounded diagnostic mixture sound speed."""

        x = np.clip(np.asarray(xv, dtype=float), 0.0, 1.0)
        c_single = np.where(x <= 0.0, self.c_liquid, self.c_vapor)
        c_mix = self.c_two_phase_min + (self.c_liquid - self.c_two_phase_min) * (1.0 - 4.0 * x * (1.0 - x))
        c_mix = np.maximum(c_mix, self.c_two_phase_min)
        two_phase = (x > 0.0) & (x < 1.0)
        return np.where(two_phase, c_mix, c_single)

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        rho = U[..., IDX_RHO]
        u = U[..., IDX_MOM] / rho
        E = U[..., IDX_RHOE] / rho
        e = E - 0.5 * u**2
        xv = np.clip(U[..., IDX_RHO_XV] / rho, 0.0, 1.0)
        p = self.pressure_from_density(rho)
        alpha = self.alpha_from_rho_xv(rho, xv)
        c = self.sound_speed_from_rho_xv(rho, xv)
        T = self.T_sat + (e - self.e_ref) / self.cv_liquid
        return PrimitiveState(rho=rho, u=u, p=p, e=e, E=E, T=T, xv=xv, alpha=alpha, c=c)


@dataclass(frozen=True)
class LCO2PropertyEOSAdapter:
    """EOS adapter that connects the FVM solver to a real-fluid property backend.

    The solver stores only ``rho``, ``rho*u``, ``rho*E`` and ``rho*x_v``.  A
    real-fluid property package generally wants thermodynamic pairs such as
    ``rho``/``e``.  This adapter performs that conversion and exposes the same
    ``EOSModel`` methods used by the existing FVM code.

    The adapter is deliberately conservative in Ver.0.5.0:

    * ``rhoE`` is not thermodynamically projected during HEM/HNE.
    * pressure-boundary inversion uses ``density_from_pT`` at a configured
      boundary temperature, because density is not a unique function of pressure
      for a real fluid.
    * actual property calls are delegated to a backend.  The default verified
      backend is the dependency-free ``SurrogateLCO2PropertyBackend``.
    """

    backend: object
    boundary_temperature_K: float = 253.15
    quality_source: str = "transported"  # transported or backend
    quality_clip: bool = True

    def __post_init__(self) -> None:
        if not np.isfinite(self.boundary_temperature_K) or self.boundary_temperature_K <= 0.0:
            raise ValueError("boundary_temperature_K must be positive and finite")
        if self.quality_source not in {"transported", "backend"}:
            raise ValueError("quality_source must be transported or backend")
        for method in ("state_from_rho_e", "density_from_pT", "saturation_state"):
            if not hasattr(self.backend, method):
                raise TypeError(f"backend must provide {method}()")

    @property
    def backend_name(self) -> str:
        return str(getattr(self.backend, "name", type(self.backend).__name__))

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        rho = U[..., IDX_RHO]
        u = U[..., IDX_MOM] / rho
        E = U[..., IDX_RHOE] / rho
        e = E - 0.5 * u**2
        transported_xv = U[..., IDX_RHO_XV] / rho
        prop = self.backend.state_from_rho_e(rho, e)  # type: ignore[attr-defined]
        xv = transported_xv if self.quality_source == "transported" else prop.quality
        if self.quality_clip:
            xv = np.clip(xv, 0.0, 1.0)
        alpha = self._alpha_for_quality(xv, prop)
        c = self._sound_speed_for_quality(xv, prop)
        return PrimitiveState(
            rho=rho,
            u=u,
            p=np.asarray(prop.p, dtype=float),
            e=e,
            E=E,
            T=np.asarray(prop.T, dtype=float),
            xv=xv,
            alpha=alpha,
            c=c,
        )

    def _alpha_for_quality(self, quality: np.ndarray, prop) -> np.ndarray:
        if hasattr(self.backend, "alpha_from_quality"):
            return np.asarray(self.backend.alpha_from_quality(quality), dtype=float)  # type: ignore[attr-defined]
        try:
            sat = self.backend.saturation_state(prop.p)  # type: ignore[attr-defined]
            q = np.clip(np.asarray(quality, dtype=float), 0.0, 1.0)
            v_v = q / sat.rho_v
            v_l = (1.0 - q) / sat.rho_l
            denom = v_v + v_l
            return np.divide(v_v, denom, out=np.zeros_like(v_v, dtype=float), where=denom > 0.0)
        except Exception:
            return np.asarray(prop.alpha, dtype=float)

    def _sound_speed_for_quality(self, quality: np.ndarray, prop) -> np.ndarray:
        if hasattr(self.backend, "sound_speed_from_quality"):
            return np.asarray(self.backend.sound_speed_from_quality(quality), dtype=float)  # type: ignore[attr-defined]
        return np.asarray(prop.c, dtype=float)

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        p_arr = np.asarray(p, dtype=float)
        T_arr = np.full_like(p_arr, self.boundary_temperature_K, dtype=float)
        return self.backend.density_from_pT(p_arr, T_arr)  # type: ignore[attr-defined]

    def equilibrium_vapor_mass_fraction(self, prim: PrimitiveState) -> np.ndarray:
        prop = self.backend.state_from_rho_e(prim.rho, prim.e)  # type: ignore[attr-defined]
        return np.clip(np.asarray(prop.quality, dtype=float), 0.0, 1.0)

    def saturation_state(self, p: np.ndarray | float):
        return self.backend.saturation_state(p)  # type: ignore[attr-defined]
