"""Phase-change vapor-mass budget diagnostics.

The boundary budget introduced in Ver.0.2.7 intentionally accounts only for
external-face fluxes.  Once HEM/HNE phase change is active, the conservative
quantity ``rho*x_v`` can also change inside the domain through the split
phase-change operator.  Ver.0.4.1 records that internal source separately so
that vapor inventory changes can be decomposed as

    vapor inventory change = boundary vapor flux + phase-change source + residual.

The tracker is diagnostic only.  It does not alter the numerical update.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import numpy as np

from .budget import BoundaryBudgetTracker
from .state import IDX_RHO_XV, inventory


@dataclass
class PhaseChangeBudgetTracker:
    """Cumulative vapor-mass source budget for split phase-change operators.

    Parameters
    ----------
    initial_inventory:
        Domain-integrated inventories at tracker initialization.  Only
        ``vapor_mass_total`` is required, but the full inventory dictionary is
        accepted for consistency with :class:`BoundaryBudgetTracker`.
    """

    initial_inventory: Mapping[str, float]
    cumulative_source_kg: float = 0.0
    cumulative_generation_kg: float = 0.0
    cumulative_condensation_kg: float = 0.0
    last_source_kg: float = 0.0
    last_source_rate_kg_s: float = 0.0
    last_dt_s: float = 0.0

    def __post_init__(self) -> None:
        self.initial_inventory = dict(self.initial_inventory)
        if "vapor_mass_total" not in self.initial_inventory:
            raise ValueError("initial_inventory must contain vapor_mass_total")

    @property
    def initial_vapor_mass_kg(self) -> float:
        """Initial domain vapor mass [kg]."""

        return float(self.initial_inventory["vapor_mass_total"])

    @staticmethod
    def vapor_mass_kg(U: np.ndarray, dx: float, area_m2: float) -> float:
        """Return domain-integrated vapor mass from a conservative state."""

        return float(np.sum(U[..., IDX_RHO_XV]) * dx * area_m2)

    def record_phase_change(self, *, U_before: np.ndarray, U_after: np.ndarray, dx: float, area_m2: float, dt: float) -> None:
        """Accumulate the vapor-mass change caused by one phase-change step."""

        if dx <= 0.0:
            raise ValueError("dx must be positive")
        if area_m2 <= 0.0:
            raise ValueError("area_m2 must be positive")
        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        before = self.vapor_mass_kg(U_before, dx, area_m2)
        after = self.vapor_mass_kg(U_after, dx, area_m2)
        delta = after - before
        self.last_source_kg = float(delta)
        self.last_dt_s = float(dt)
        self.last_source_rate_kg_s = float(delta / dt) if dt > 0.0 else 0.0
        self.cumulative_source_kg += float(delta)
        if delta >= 0.0:
            self.cumulative_generation_kg += float(delta)
        else:
            self.cumulative_condensation_kg += float(-delta)

    def diagnostics(
        self,
        current_inventory: Mapping[str, float],
        boundary_budget: BoundaryBudgetTracker | None = None,
    ) -> dict[str, float]:
        """Return vapor source and closure diagnostics.

        If a boundary budget is supplied, the expected vapor inventory includes
        both external vapor fluxes and internal phase-change source.  Otherwise,
        the expected inventory uses only the initial inventory and phase source.
        """

        current = dict(current_inventory)
        actual = float(current["vapor_mass_total"])
        if boundary_budget is not None:
            boundary_expected = float(boundary_budget.expected_inventory()["vapor_mass_total"])
            boundary_net = boundary_expected - self.initial_vapor_mass_kg
        else:
            boundary_expected = self.initial_vapor_mass_kg
            boundary_net = 0.0
        expected = boundary_expected + self.cumulative_source_kg
        residual = actual - expected
        scale = max(abs(actual), abs(expected), abs(self.initial_vapor_mass_kg), abs(self.cumulative_source_kg), 1.0)
        return {
            "phase_vapor_mass_initial_kg": self.initial_vapor_mass_kg,
            "phase_vapor_mass_boundary_net_kg": float(boundary_net),
            "phase_vapor_mass_boundary_expected_kg": float(boundary_expected),
            "phase_vapor_mass_source_cumulative_kg": float(self.cumulative_source_kg),
            "phase_vapor_mass_generation_cumulative_kg": float(self.cumulative_generation_kg),
            "phase_vapor_mass_condensation_cumulative_kg": float(self.cumulative_condensation_kg),
            "phase_vapor_mass_last_source_kg": float(self.last_source_kg),
            "phase_vapor_mass_source_rate_kg_s": float(self.last_source_rate_kg_s),
            "phase_vapor_mass_expected_total_kg": float(expected),
            "phase_vapor_mass_actual_total_kg": float(actual),
            "phase_vapor_mass_balance_residual_kg": float(residual),
            "phase_vapor_mass_balance_relative_residual": float(residual / scale),
            "phase_budget_last_dt_s": float(self.last_dt_s),
        }


def phase_budget_residuals(U, dx: float, area: float, tracker: PhaseChangeBudgetTracker, boundary_budget: BoundaryBudgetTracker | None = None) -> dict[str, float]:
    """Convenience helper returning phase budget diagnostics for a state array."""

    return tracker.diagnostics(inventory(U, dx, area), boundary_budget=boundary_budget)
