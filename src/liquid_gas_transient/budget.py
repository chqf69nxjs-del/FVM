"""Boundary mass/energy budget diagnostics for open-boundary FVM runs.

The finite-volume update is conservative inside the computational domain.  When
pressure/tank boundaries are active, however, mass and energy can legitimately
enter or leave through the external faces.  Ver.0.2.7 records those external
flux integrals so that a change in domain inventory can be separated into

    inventory change = boundary contribution + numerical/source/interface residual.

The sign convention follows the one-dimensional positive-x coordinate:

* left boundary flux is positive when it enters the domain,
* right boundary flux is positive when it leaves the domain,
* net boundary contribution to the domain is left - right.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
import numpy as np

from .state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, N_VARS, inventory

_VAR_NAMES = {
    IDX_RHO: "mass",
    IDX_MOM: "momentum",
    IDX_RHOE: "energy",
    IDX_RHO_XV: "vapor_mass",
}
_INV_KEYS = {
    IDX_RHO: "mass_total",
    IDX_MOM: "momentum_total",
    IDX_RHOE: "energy_total",
    IDX_RHO_XV: "vapor_mass_total",
}


@dataclass
class BoundaryBudgetTracker:
    """Cumulative external-face flux budget for a single FVM solver.

    Parameters
    ----------
    initial_inventory:
        Domain-integrated inventories at tracker initialization.
    area_m2:
        Pipe cross-sectional area used to convert flux per area into total
        flow rates and cumulative through-boundary quantities.
    """

    initial_inventory: Mapping[str, float]
    area_m2: float
    cumulative_left: np.ndarray = field(default_factory=lambda: np.zeros(N_VARS, dtype=float))
    cumulative_right: np.ndarray = field(default_factory=lambda: np.zeros(N_VARS, dtype=float))
    last_left_flux: np.ndarray = field(default_factory=lambda: np.zeros(N_VARS, dtype=float))
    last_right_flux: np.ndarray = field(default_factory=lambda: np.zeros(N_VARS, dtype=float))
    last_dt_s: float = 0.0

    def __post_init__(self) -> None:
        if self.area_m2 <= 0.0:
            raise ValueError("area_m2 must be positive")
        self.initial_inventory = dict(self.initial_inventory)

    def record_external_fluxes(self, *, left_flux: np.ndarray, right_flux: np.ndarray, dt: float) -> None:
        """Accumulate external boundary fluxes for one time step.

        ``left_flux`` and ``right_flux`` are the numerical flux vectors at the
        left and right external faces.  They have units of conserved quantity per
        unit area per second.  Multiplication by area and dt converts them into
        total inventory increments.
        """

        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        left = np.asarray(left_flux, dtype=float)
        right = np.asarray(right_flux, dtype=float)
        if left.shape != (N_VARS,) or right.shape != (N_VARS,):
            raise ValueError("boundary flux vectors must have shape (N_VARS,)")
        if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
            raise ValueError("boundary flux vectors must be finite")

        self.last_left_flux = left.copy()
        self.last_right_flux = right.copy()
        self.last_dt_s = float(dt)
        self.cumulative_left += self.area_m2 * dt * left
        self.cumulative_right += self.area_m2 * dt * right

    def expected_inventory(self) -> dict[str, float]:
        """Return inventory expected from external boundary fluxes only."""

        out: dict[str, float] = {}
        net = self.cumulative_left - self.cumulative_right
        for idx, inv_key in _INV_KEYS.items():
            out[inv_key] = float(self.initial_inventory[inv_key] + net[idx])
        return out

    def diagnostics(self, current_inventory: Mapping[str, float]) -> dict[str, float]:
        """Return flat scalar diagnostics comparing inventory and boundary budget."""

        current = dict(current_inventory)
        expected = self.expected_inventory()
        out: dict[str, float] = {}
        net = self.cumulative_left - self.cumulative_right
        for idx, name in _VAR_NAMES.items():
            inv_key = _INV_KEYS[idx]
            initial = float(self.initial_inventory[inv_key])
            actual = float(current[inv_key])
            exp = float(expected[inv_key])
            residual = actual - exp
            scale = max(abs(actual), abs(exp), abs(initial), 1.0)
            out[f"budget_{name}_left_cumulative"] = float(self.cumulative_left[idx])
            out[f"budget_{name}_right_cumulative"] = float(self.cumulative_right[idx])
            out[f"budget_{name}_net_boundary"] = float(net[idx])
            out[f"budget_{name}_expected_total"] = exp
            out[f"budget_{name}_residual"] = residual
            out[f"budget_{name}_relative_residual"] = float(residual / scale)
            out[f"budget_{name}_left_rate"] = float(self.area_m2 * self.last_left_flux[idx])
            out[f"budget_{name}_right_rate"] = float(self.area_m2 * self.last_right_flux[idx])
        out["budget_last_dt_s"] = float(self.last_dt_s)
        return out


def boundary_budget_residuals(U, dx: float, area: float, tracker: BoundaryBudgetTracker) -> dict[str, float]:
    """Convenience helper returning tracker diagnostics for a state array."""

    return tracker.diagnostics(inventory(U, dx, area))
