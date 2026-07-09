"""State-vector utilities.

The solver stores only conservative variables. Primitive quantities are
computed through an EOS model and passed around as a structured object.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import numpy as np

IDX_RHO = 0
IDX_MOM = 1
IDX_RHOE = 2
IDX_RHO_XV = 3
N_VARS = 4


@dataclass(frozen=True)
class PrimitiveState:
    """Primitive and thermodynamic state arrays."""

    rho: np.ndarray
    u: np.ndarray
    p: np.ndarray
    e: np.ndarray
    E: np.ndarray
    T: np.ndarray
    xv: np.ndarray
    alpha: np.ndarray
    c: np.ndarray


def make_conserved(
    rho: np.ndarray | float,
    u: np.ndarray | float,
    e: np.ndarray | float,
    xv: np.ndarray | float = 0.0,
) -> np.ndarray:
    """Build conservative variables from primitive-like inputs.

    Parameters
    ----------
    rho:
        Density [kg/m3].
    u:
        Velocity [m/s].
    e:
        Internal energy [J/kg].
    xv:
        Vapor mass fraction [-].

    Returns
    -------
    numpy.ndarray
        Conservative state with last dimension length 4.
    """

    rho_arr, u_arr, e_arr, xv_arr = np.broadcast_arrays(rho, u, e, xv)
    U = np.empty(rho_arr.shape + (N_VARS,), dtype=float)
    E = e_arr + 0.5 * u_arr**2
    U[..., IDX_RHO] = rho_arr
    U[..., IDX_MOM] = rho_arr * u_arr
    U[..., IDX_RHOE] = rho_arr * E
    U[..., IDX_RHO_XV] = rho_arr * xv_arr
    return U


def velocity(U: np.ndarray) -> np.ndarray:
    """Return velocity from conservative variables."""

    return U[..., IDX_MOM] / U[..., IDX_RHO]


def total_energy(U: np.ndarray) -> np.ndarray:
    """Return specific total energy from conservative variables."""

    return U[..., IDX_RHOE] / U[..., IDX_RHO]


def internal_energy(U: np.ndarray) -> np.ndarray:
    """Return specific internal energy from conservative variables."""

    u = velocity(U)
    return total_energy(U) - 0.5 * u**2


def vapor_mass_fraction(U: np.ndarray) -> np.ndarray:
    """Return vapor mass fraction from conservative variables."""

    return U[..., IDX_RHO_XV] / U[..., IDX_RHO]


def check_physical_state(
    U: np.ndarray,
    *,
    require_xv_bounds: bool = True,
    names: Iterable[str] | None = None,
) -> None:
    """Raise ValueError if a conservative state is non-physical.

    This function intentionally fails fast. Silent clipping should be added
    only as an explicit, documented limiter.
    """

    labels = list(names) if names is not None else ["state"]
    label = ", ".join(labels)

    if not np.all(np.isfinite(U)):
        raise ValueError(f"{label}: state contains NaN or infinity")
    rho = U[..., IDX_RHO]
    if np.any(rho <= 0.0):
        raise ValueError(f"{label}: density must be positive")
    e = internal_energy(U)
    if np.any(e < 0.0):
        raise ValueError(f"{label}: internal energy became negative")
    if require_xv_bounds:
        xv = vapor_mass_fraction(U)
        if np.any(xv < -1.0e-12) or np.any(xv > 1.0 + 1.0e-12):
            raise ValueError(f"{label}: vapor mass fraction outside [0, 1]")


def inventory(U: np.ndarray, dx: float, area: float) -> dict[str, float]:
    """Return domain-integrated conservative inventories."""

    factor = dx * area
    return {
        "mass_total": float(np.sum(U[..., IDX_RHO]) * factor),
        "momentum_total": float(np.sum(U[..., IDX_MOM]) * factor),
        "energy_total": float(np.sum(U[..., IDX_RHOE]) * factor),
        "vapor_mass_total": float(np.sum(U[..., IDX_RHO_XV]) * factor),
    }
