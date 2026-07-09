"""Phase-change model interfaces.

Ver.0.2 uses NoPhaseChange. Ver.0.3 adds an instantaneous HEM flash
operator. Ver.0.4 adds a finite-rate HNE relaxation operator while keeping the
solver control flow unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import numpy as np

from .eos import EOSModel
from .state import IDX_RHO, IDX_RHO_XV


class PhaseChangeModel(Protocol):
    """Phase-change operator interface."""

    def apply(self, U: np.ndarray, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        """Return phase-change-updated conservative state."""


@dataclass(frozen=True)
class NoPhaseChange:
    """Disable phase change. Vapor mass is transported only by FVM flux."""

    def apply(self, U: np.ndarray, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        return U


@dataclass(frozen=True)
class HEMPhaseChange:
    """Instantaneous homogeneous-equilibrium flash operator.

    The operator keeps the conservative mass, momentum and total energy
    unchanged and projects only the vapor mass conservation variable to the
    local equilibrium value supplied by the EOS:

        rho*x_v <- rho*x_v,eq

    This is the Ver.0.3 skeleton. It verifies the data path for equilibrium
    flashing, void-fraction diagnostics and two-phase sound-speed reduction.
    A later real-fluid implementation may also need a thermodynamically
    consistent energy projection; that is intentionally not hidden here.
    """

    enforce_bounds: bool = True

    def apply(self, U: np.ndarray, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        if not hasattr(eos, "equilibrium_vapor_mass_fraction"):
            raise NotImplementedError("EOS must provide equilibrium_vapor_mass_fraction for HEM")
        prim = eos.primitive_from_conserved(U)
        x_eq = eos.equilibrium_vapor_mass_fraction(prim)  # type: ignore[attr-defined]
        if self.enforce_bounds:
            x_eq = np.clip(x_eq, 0.0, 1.0)
        out = U.copy()
        out[..., IDX_RHO_XV] = out[..., IDX_RHO] * x_eq
        return out


@dataclass(frozen=True)
class HNERelaxationPhaseChange:
    """Finite-rate homogeneous nonequilibrium flash operator.

    The FVM update transports ``rho*x_v`` conservatively. This split source
    operator then relaxes the cell vapor mass fraction toward the local HEM
    equilibrium value,

        x_v^{n+1} = x_{v,eq} + (x_v^n - x_{v,eq}) exp(-dt/tau).

    Mass, momentum and total energy are intentionally unchanged by this toy
    operator. The Ver.0.4 purpose is to verify the software pathway for
    phase-change lag before adding a thermodynamically complete LCO2 HNE model.
    """

    tau_s: float

    def __post_init__(self) -> None:
        if self.tau_s <= 0.0:
            raise ValueError("tau_s must be positive")

    def relaxation_factor(self, dt: float) -> float:
        """Return exp(-dt/tau), the exact scalar relaxation factor."""

        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        return float(np.exp(-dt / self.tau_s))

    def apply(self, U: np.ndarray, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        if not hasattr(eos, "equilibrium_vapor_mass_fraction"):
            raise NotImplementedError("EOS must provide equilibrium_vapor_mass_fraction for HNE")
        prim = eos.primitive_from_conserved(U)
        x_eq = eos.equilibrium_vapor_mass_fraction(prim)  # type: ignore[attr-defined]
        r = self.relaxation_factor(dt)
        x_new = x_eq + (prim.xv - x_eq) * r
        out = U.copy()
        out[..., IDX_RHO_XV] = out[..., IDX_RHO] * np.clip(x_new, 0.0, 1.0)
        return out
