"""Real-fluid property backend adapter skeletons for Ver.0.5.0.

The FVM solver should not call a concrete property package directly.  This
module defines a small, array-oriented backend protocol and two backend classes:

* ``SurrogateLCO2PropertyBackend`` is deterministic and dependency-free.  It is
  used for verification of the adapter pathway only; it is not a design-quality
  LCO2 property model.
* ``CoolPropCO2Backend`` is an optional adapter shell.  It is imported only when
  instantiated, so the code base remains runnable without external property
  packages installed.

The real design intent is that future REFPROP/CoolProp/tabular backends satisfy
this same protocol, while the solver continues to see only ``EOSModel``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import numpy as np


class PropertyEvaluationError(RuntimeError):
    """Raised when a property backend cannot evaluate a requested state."""


@dataclass(frozen=True)
class PropertyState:
    """Array-valued thermodynamic state returned by property backends."""

    rho: np.ndarray
    p: np.ndarray
    T: np.ndarray
    e: np.ndarray
    quality: np.ndarray
    alpha: np.ndarray
    c: np.ndarray


@dataclass(frozen=True)
class SaturationState:
    """Saturation properties at a pressure."""

    p: np.ndarray
    T_sat: np.ndarray
    rho_l: np.ndarray
    rho_v: np.ndarray
    e_l: np.ndarray
    e_v: np.ndarray
    h_lv: np.ndarray


class RealFluidPropertyBackend(Protocol):
    """Minimal protocol for a real-fluid property backend."""

    name: str

    def state_from_rho_e(self, rho: np.ndarray | float, e: np.ndarray | float) -> PropertyState:
        """Return p, T, quality, alpha and sound speed from rho/e."""

    def density_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        """Return density from pressure and temperature for boundary construction."""

    def internal_energy_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        """Return mass-specific internal energy from pressure and temperature."""

    def saturation_state(self, p: np.ndarray | float) -> SaturationState:
        """Return saturation properties at pressure."""


@dataclass(frozen=True)
class SurrogateLCO2PropertyBackend:
    """Dependency-free LCO2-like backend used to verify the adapter path.

    This class intentionally resembles the earlier toy HEM model, but exposes a
    real-fluid-like API: states are evaluated from ``rho`` and ``e`` and pressure
    boundaries use ``p`` plus a configured temperature.  The numbers are chosen
    to be numerically plausible for a dense liquid CO2 transfer problem, not to
    replace a certified thermodynamic property package.
    """

    name: str = "surrogate_lco2"
    p_sat_ref_pa: float = 1.9e6
    T_sat_ref_K: float = 253.15
    rho_l_ref_kg_m3: float = 930.0
    rho_v_ref_kg_m3: float = 40.0
    c_liquid_m_s: float = 750.0
    c_vapor_m_s: float = 250.0
    c_two_phase_min_m_s: float = 80.0
    cv_liquid_j_kgK: float = 2100.0
    cv_vapor_j_kgK: float = 900.0
    e_l_ref_j_kg: float = 1.0e5
    latent_heat_ref_j_kg: float = 2.0e5
    liquid_drho_dT_kg_m3K: float = -2.0
    vapor_drho_dT_kg_m3K: float = -0.15

    def __post_init__(self) -> None:
        if self.p_sat_ref_pa <= 0.0:
            raise ValueError("p_sat_ref_pa must be positive")
        if self.rho_l_ref_kg_m3 <= self.rho_v_ref_kg_m3:
            raise ValueError("liquid reference density must exceed vapor reference density")
        if min(self.rho_l_ref_kg_m3, self.rho_v_ref_kg_m3) <= 0.0:
            raise ValueError("reference densities must be positive")
        if min(self.c_liquid_m_s, self.c_vapor_m_s, self.c_two_phase_min_m_s) <= 0.0:
            raise ValueError("sound speeds must be positive")
        if min(self.cv_liquid_j_kgK, self.cv_vapor_j_kgK, self.latent_heat_ref_j_kg) <= 0.0:
            raise ValueError("heat-capacity and latent-heat values must be positive")

    def equilibrium_quality_from_density(self, rho: np.ndarray | float) -> np.ndarray:
        rho_arr = np.asarray(rho, dtype=float)
        inv_rho = 1.0 / rho_arr
        inv_l = 1.0 / self.rho_l_ref_kg_m3
        inv_v = 1.0 / self.rho_v_ref_kg_m3
        q = (inv_rho - inv_l) / (inv_v - inv_l)
        return np.clip(q, 0.0, 1.0)

    def alpha_from_quality(self, quality: np.ndarray | float) -> np.ndarray:
        q = np.clip(np.asarray(quality, dtype=float), 0.0, 1.0)
        v_v = q / self.rho_v_ref_kg_m3
        v_l = (1.0 - q) / self.rho_l_ref_kg_m3
        denom = v_v + v_l
        alpha = np.divide(v_v, denom, out=np.zeros_like(v_v, dtype=float), where=denom > 0.0)
        return np.clip(alpha, 0.0, 1.0)

    def pressure_from_density_quality(self, rho: np.ndarray | float, quality: np.ndarray | float) -> np.ndarray:
        rho_arr, q = np.broadcast_arrays(np.asarray(rho, dtype=float), np.asarray(quality, dtype=float))
        p = np.empty_like(rho_arr, dtype=float)
        liquid = q <= 1.0e-12
        vapor = q >= 1.0 - 1.0e-12
        two_phase = ~(liquid | vapor)
        p[liquid] = self.p_sat_ref_pa + self.c_liquid_m_s**2 * (rho_arr[liquid] - self.rho_l_ref_kg_m3)
        p[two_phase] = self.p_sat_ref_pa
        p[vapor] = self.p_sat_ref_pa + self.c_vapor_m_s**2 * (rho_arr[vapor] - self.rho_v_ref_kg_m3)
        return np.maximum(p, 1.0)

    def sound_speed_from_quality(self, quality: np.ndarray | float) -> np.ndarray:
        q = np.clip(np.asarray(quality, dtype=float), 0.0, 1.0)
        single = np.where(q <= 0.0, self.c_liquid_m_s, self.c_vapor_m_s)
        c_mix = self.c_two_phase_min_m_s + (self.c_liquid_m_s - self.c_two_phase_min_m_s) * (
            1.0 - 4.0 * q * (1.0 - q)
        )
        c_mix = np.maximum(c_mix, self.c_two_phase_min_m_s)
        two_phase = (q > 0.0) & (q < 1.0)
        return np.where(two_phase, c_mix, single)

    def state_from_rho_e(self, rho: np.ndarray | float, e: np.ndarray | float) -> PropertyState:
        rho_arr, e_arr = np.broadcast_arrays(np.asarray(rho, dtype=float), np.asarray(e, dtype=float))
        if np.any(~np.isfinite(rho_arr)) or np.any(rho_arr <= 0.0):
            raise PropertyEvaluationError("rho must be finite and positive")
        if np.any(~np.isfinite(e_arr)):
            raise PropertyEvaluationError("e must be finite")
        q = self.equilibrium_quality_from_density(rho_arr)
        p = self.pressure_from_density_quality(rho_arr, q)
        cv_mix = (1.0 - q) * self.cv_liquid_j_kgK + q * self.cv_vapor_j_kgK
        e_sat_mix = self.e_l_ref_j_kg + q * self.latent_heat_ref_j_kg
        T = self.T_sat_ref_K + (e_arr - e_sat_mix) / cv_mix
        alpha = self.alpha_from_quality(q)
        c = self.sound_speed_from_quality(q)
        return PropertyState(rho=rho_arr, p=p, T=T, e=e_arr, quality=q, alpha=alpha, c=c)

    def density_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        p_arr, T_arr = np.broadcast_arrays(np.asarray(p, dtype=float), np.asarray(T, dtype=float))
        if np.any(p_arr <= 0.0) or np.any(~np.isfinite(p_arr)) or np.any(~np.isfinite(T_arr)):
            raise PropertyEvaluationError("p and T must be finite, with p > 0")
        liquid_branch = T_arr <= self.T_sat_ref_K + 5.0
        rho_l = self.rho_l_ref_kg_m3 + (p_arr - self.p_sat_ref_pa) / self.c_liquid_m_s**2 + self.liquid_drho_dT_kg_m3K * (T_arr - self.T_sat_ref_K)
        rho_v = self.rho_v_ref_kg_m3 + (p_arr - self.p_sat_ref_pa) / self.c_vapor_m_s**2 + self.vapor_drho_dT_kg_m3K * (T_arr - self.T_sat_ref_K)
        rho = np.where(liquid_branch | (p_arr >= self.p_sat_ref_pa), rho_l, rho_v)
        return np.maximum(rho, 1.0e-6)

    def internal_energy_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        p_arr, T_arr = np.broadcast_arrays(np.asarray(p, dtype=float), np.asarray(T, dtype=float))
        if np.any(p_arr <= 0.0) or np.any(~np.isfinite(p_arr)) or np.any(~np.isfinite(T_arr)):
            raise PropertyEvaluationError("p and T must be finite, with p > 0")
        rho = self.density_from_pT(p_arr, T_arr)
        q = self.equilibrium_quality_from_density(rho)
        cv_mix = (1.0 - q) * self.cv_liquid_j_kgK + q * self.cv_vapor_j_kgK
        e_sat_mix = self.e_l_ref_j_kg + q * self.latent_heat_ref_j_kg
        return e_sat_mix + cv_mix * (T_arr - self.T_sat_ref_K)

    def saturation_state(self, p: np.ndarray | float) -> SaturationState:
        p_arr = np.asarray(p, dtype=float)
        if np.any(p_arr <= 0.0) or np.any(~np.isfinite(p_arr)):
            raise PropertyEvaluationError("saturation pressure must be finite and positive")
        dp = p_arr - self.p_sat_ref_pa
        T_sat = self.T_sat_ref_K + dp / 2.0e5  # deliberately mild toy slope
        rho_l = np.maximum(self.rho_l_ref_kg_m3 + dp / self.c_liquid_m_s**2, 1.0e-6)
        rho_v = np.maximum(self.rho_v_ref_kg_m3 + dp / self.c_vapor_m_s**2, 1.0e-6)
        e_l = self.e_l_ref_j_kg + self.cv_liquid_j_kgK * (T_sat - self.T_sat_ref_K)
        e_v = e_l + self.latent_heat_ref_j_kg
        h_lv = np.full_like(p_arr, self.latent_heat_ref_j_kg, dtype=float)
        return SaturationState(p=p_arr, T_sat=T_sat, rho_l=rho_l, rho_v=rho_v, e_l=e_l, e_v=e_v, h_lv=h_lv)


@dataclass(frozen=True)
class CoolPropCO2Backend:
    """Optional CoolProp-backed CO2 property adapter.

    This is intentionally a thin adapter shell.  It is not exercised by default
    verification because the development environment may not have CoolProp.  If
    CoolProp is installed, this class can be used through ``LCO2PropertyEOSAdapter``.
    """

    name: str = "coolprop_co2"
    fluid: str = "CO2"

    def _cp(self):
        try:
            from CoolProp.CoolProp import PropsSI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "CoolProp is not installed. Install CoolProp or use SurrogateLCO2PropertyBackend."
            ) from exc
        return PropsSI

    def state_from_rho_e(self, rho: np.ndarray | float, e: np.ndarray | float) -> PropertyState:
        PropsSI = self._cp()
        rho_arr, e_arr = np.broadcast_arrays(np.asarray(rho, dtype=float), np.asarray(e, dtype=float))
        p = np.empty_like(rho_arr, dtype=float)
        T = np.empty_like(rho_arr, dtype=float)
        q = np.empty_like(rho_arr, dtype=float)
        c = np.empty_like(rho_arr, dtype=float)
        it = np.nditer([rho_arr, e_arr, p, T, q, c], flags=["refs_ok", "multi_index"], op_flags=[["readonly"], ["readonly"], ["writeonly"], ["writeonly"], ["writeonly"], ["writeonly"]])
        for rho_i, e_i, p_o, T_o, q_o, c_o in it:  # pragma: no cover - optional dependency
            try:
                p_val = PropsSI("P", "Dmass", float(rho_i), "Umass", float(e_i), self.fluid)
                T_val = PropsSI("T", "Dmass", float(rho_i), "Umass", float(e_i), self.fluid)
                q_val = PropsSI("Q", "Dmass", float(rho_i), "Umass", float(e_i), self.fluid)
                c_val = PropsSI("A", "Dmass", float(rho_i), "Umass", float(e_i), self.fluid)
            except Exception as exc:
                raise PropertyEvaluationError(f"CoolProp failed at rho={float(rho_i)}, e={float(e_i)}") from exc
            p_o[...] = p_val
            T_o[...] = T_val
            q_o[...] = np.nan if q_val < 0.0 else q_val
            c_o[...] = c_val
        quality = np.where(np.isfinite(q), np.clip(q, 0.0, 1.0), 0.0)
        alpha = self._alpha_from_quality_pressure(quality, p)
        return PropertyState(rho=rho_arr, p=p, T=T, e=e_arr, quality=quality, alpha=alpha, c=c)

    def density_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        PropsSI = self._cp()
        p_arr, T_arr = np.broadcast_arrays(np.asarray(p, dtype=float), np.asarray(T, dtype=float))
        out = np.empty_like(p_arr, dtype=float)
        it = np.nditer([p_arr, T_arr, out], flags=["refs_ok"], op_flags=[["readonly"], ["readonly"], ["writeonly"]])
        for p_i, T_i, out_i in it:  # pragma: no cover - optional dependency
            try:
                value = PropsSI("Dmass", "P", float(p_i), "T", float(T_i), self.fluid)
            except Exception as exc:
                raise PropertyEvaluationError(f"CoolProp density_from_pT failed at p={float(p_i)}, T={float(T_i)}") from exc
            if not np.isfinite(value):
                raise PropertyEvaluationError(f"CoolProp density_from_pT returned non-finite value at p={float(p_i)}, T={float(T_i)}")
            out_i[...] = value
        return out

    def internal_energy_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        PropsSI = self._cp()
        p_arr, T_arr = np.broadcast_arrays(np.asarray(p, dtype=float), np.asarray(T, dtype=float))
        out = np.empty_like(p_arr, dtype=float)
        it = np.nditer([p_arr, T_arr, out], flags=["refs_ok"], op_flags=[["readonly"], ["readonly"], ["writeonly"]])
        for p_i, T_i, out_i in it:  # pragma: no cover - optional dependency
            try:
                value = PropsSI("Umass", "P", float(p_i), "T", float(T_i), self.fluid)
            except Exception as exc:
                raise PropertyEvaluationError(f"CoolProp internal_energy_from_pT failed at p={float(p_i)}, T={float(T_i)}") from exc
            if not np.isfinite(value):
                raise PropertyEvaluationError(f"CoolProp internal_energy_from_pT returned non-finite value at p={float(p_i)}, T={float(T_i)}")
            out_i[...] = value
        return out

    def saturation_state(self, p: np.ndarray | float) -> SaturationState:
        PropsSI = self._cp()
        p_arr = np.asarray(p, dtype=float)
        T_sat = np.empty_like(p_arr, dtype=float)
        rho_l = np.empty_like(p_arr, dtype=float)
        rho_v = np.empty_like(p_arr, dtype=float)
        e_l = np.empty_like(p_arr, dtype=float)
        e_v = np.empty_like(p_arr, dtype=float)
        it = np.nditer([p_arr, T_sat, rho_l, rho_v, e_l, e_v], flags=["refs_ok"], op_flags=[["readonly"], ["writeonly"], ["writeonly"], ["writeonly"], ["writeonly"], ["writeonly"]])
        for p_i, T_o, rl_o, rv_o, el_o, ev_o in it:  # pragma: no cover - optional dependency
            try:
                T_o[...] = PropsSI("T", "P", float(p_i), "Q", 0.0, self.fluid)
                rl_o[...] = PropsSI("Dmass", "P", float(p_i), "Q", 0.0, self.fluid)
                rv_o[...] = PropsSI("Dmass", "P", float(p_i), "Q", 1.0, self.fluid)
                el_o[...] = PropsSI("Umass", "P", float(p_i), "Q", 0.0, self.fluid)
                ev_o[...] = PropsSI("Umass", "P", float(p_i), "Q", 1.0, self.fluid)
            except Exception as exc:
                raise PropertyEvaluationError(f"CoolProp saturation failed at p={float(p_i)}") from exc
        return SaturationState(p=p_arr, T_sat=T_sat, rho_l=rho_l, rho_v=rho_v, e_l=e_l, e_v=e_v, h_lv=e_v - e_l)

    def _alpha_from_quality_pressure(self, quality: np.ndarray, p: np.ndarray) -> np.ndarray:
        q_raw, p_arr = np.broadcast_arrays(np.asarray(quality, dtype=float), np.asarray(p, dtype=float))
        endpoint_tol = 1.0e-12
        alpha = np.empty_like(q_raw, dtype=float)
        liquid = q_raw <= endpoint_tol
        vapor = q_raw >= 1.0 - endpoint_tol
        mixed = ~(liquid | vapor)
        alpha[liquid] = 0.0
        alpha[vapor] = 1.0
        if np.any(mixed):
            q_mixed = q_raw[mixed]
            p_mixed = p_arr[mixed]
            if np.any(~np.isfinite(q_mixed)) or np.any(~np.isfinite(p_mixed)):
                raise PropertyEvaluationError("CoolProp alpha calculation requires finite quality and pressure for mixed states")
            try:
                sat = self.saturation_state(p_mixed)  # pragma: no cover - optional dependency
            except Exception as exc:
                raise PropertyEvaluationError("CoolProp alpha calculation failed while evaluating saturation properties for mixed-quality states") from exc
            q = np.clip(q_mixed, 0.0, 1.0)
            v_v = q / sat.rho_v
            v_l = (1.0 - q) / sat.rho_l
            denom = v_v + v_l
            alpha[mixed] = np.divide(v_v, denom, out=np.zeros_like(v_v, dtype=float), where=denom > 0.0)
        alpha = np.clip(alpha, 0.0, 1.0)
        if np.any(~np.isfinite(alpha)):
            raise PropertyEvaluationError("CoolProp alpha calculation produced non-finite values")
        return alpha


def coolprop_available() -> bool:
    """Return True if the optional CoolProp backend can be imported."""

    try:
        from CoolProp.CoolProp import PropsSI  # noqa: F401  # type: ignore
    except Exception:
        return False
    return True


@dataclass(frozen=True)
class REFPROPCO2Backend:
    """Optional REFPROP-backed CO2 adapter placeholder.

    The project should be able to carry a REFPROP option in configuration
    without making REFPROP a hard dependency.  This shell deliberately raises a
    clear ImportError until a concrete REFPROP Python wrapper and installation
    path are provided by the user environment.
    """

    name: str = "refprop_co2"
    fluid: str = "CO2"

    def _raise_unavailable(self) -> None:
        raise ImportError(
            "REFPROP backend is not configured in this environment. "
            "Install/configure a REFPROP Python wrapper and implement the "
            "REFPROPCO2Backend methods, or use CoolProp/Surrogate/Tabular backend."
        )

    def state_from_rho_e(self, rho: np.ndarray | float, e: np.ndarray | float) -> PropertyState:
        self._raise_unavailable()

    def density_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        self._raise_unavailable()

    def internal_energy_from_pT(self, p: np.ndarray | float, T: np.ndarray | float) -> np.ndarray:
        self._raise_unavailable()

    def saturation_state(self, p: np.ndarray | float) -> SaturationState:
        self._raise_unavailable()


def refprop_available() -> bool:
    """Return True if a REFPROP Python wrapper appears importable.

    This is intentionally conservative.  Many REFPROP deployments rely on
    external DLLs/shared libraries, so importability alone is not a validation.
    The Ver.0.5.2 external-reference comparison remains the recommended gate.
    """

    candidates = ("ctREFPROP.ctREFPROP", "REFPROPConnector")
    for module_name in candidates:
        try:
            __import__(module_name)
            return True
        except Exception:
            continue
    return False


def property_backend_availability() -> dict[str, bool]:
    """Return optional backend availability without importing them eagerly."""

    return {
        "surrogate_lco2": True,
        "coolprop_co2": coolprop_available(),
        "refprop_co2": refprop_available(),
    }


def make_property_backend(name: str) -> RealFluidPropertyBackend:
    """Factory for configured property backends.

    This keeps solver/case configuration independent from concrete dependency
    imports.  Optional backends are instantiated only when requested.
    """

    key = name.strip().lower()
    if key in {"surrogate", "surrogate_lco2", "lco2_surrogate"}:
        return SurrogateLCO2PropertyBackend()
    if key in {"coolprop", "coolprop_co2", "co2_coolprop"}:
        return CoolPropCO2Backend()
    if key in {"refprop", "refprop_co2", "co2_refprop"}:
        return REFPROPCO2Backend()
    raise ValueError(f"unknown property backend: {name!r}")
