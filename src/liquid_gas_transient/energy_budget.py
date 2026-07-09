"""Energy/source budget diagnostics for Ver.0.4.2.

The boundary budget introduced in Ver.0.2.7 checks whether the change of the
conservative total-energy inventory can be explained by external face fluxes.
Once split source terms and phase-change operators are added, that single
residual is no longer informative enough. Ver.0.4.2 therefore records the
energy changes caused by operator-split steps separately:

    total-energy change = boundary energy flux
                        + split source energy change
                        + split phase-change energy change
                        + residual.

The tracker also carries non-conservative physical placeholders that do not yet
alter ``rhoE`` in the toy model, for example latent heat required by vapor
formation and kinetic-energy dissipation proxies from friction/local loss.  They
are intentionally diagnostics only until the real-fluid energy closure is
introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import numpy as np

from .budget import BoundaryBudgetTracker
from .state import IDX_RHOE, inventory


def _energy_total_j(U: np.ndarray, dx: float, area_m2: float) -> float:
    """Return domain-integrated conservative total energy [J]."""

    return float(np.sum(U[..., IDX_RHOE]) * dx * area_m2)


@dataclass
class EnergySourceBudgetTracker:
    """Cumulative diagnostic ledger for split energy source terms.

    Parameters
    ----------
    initial_inventory:
        Domain-integrated inventories at tracker initialization.
    latent_heat_j_per_kg:
        Optional placeholder latent heat used only to estimate the energy that
        would be required by net vapor generation.  The value does not change
        the numerical solution.
    """

    initial_inventory: Mapping[str, float]
    latent_heat_j_per_kg: float = 0.0

    cumulative_source_energy_delta_j: float = 0.0
    cumulative_phase_energy_delta_j: float = 0.0
    cumulative_gravity_energy_j: float = 0.0
    cumulative_drag_dissipation_proxy_j: float = 0.0
    cumulative_friction_dissipation_proxy_j: float = 0.0
    cumulative_local_loss_dissipation_proxy_j: float = 0.0
    cumulative_latent_requirement_j: float = 0.0
    cumulative_latent_release_j: float = 0.0
    cumulative_net_latent_placeholder_j: float = 0.0

    last_source_energy_delta_j: float = 0.0
    last_phase_energy_delta_j: float = 0.0
    last_gravity_energy_j: float = 0.0
    last_drag_dissipation_proxy_j: float = 0.0
    last_friction_dissipation_proxy_j: float = 0.0
    last_local_loss_dissipation_proxy_j: float = 0.0
    last_latent_placeholder_j: float = 0.0
    last_dt_s: float = 0.0

    def __post_init__(self) -> None:
        self.initial_inventory = dict(self.initial_inventory)
        if "energy_total" not in self.initial_inventory:
            raise ValueError("initial_inventory must contain energy_total")
        if self.latent_heat_j_per_kg < 0.0:
            raise ValueError("latent_heat_j_per_kg must be non-negative")

    @property
    def initial_energy_j(self) -> float:
        """Initial domain total energy [J]."""

        return float(self.initial_inventory["energy_total"])

    def record_source_step(
        self,
        *,
        U_before: np.ndarray,
        U_after: np.ndarray,
        dx: float,
        area_m2: float,
        dt: float,
        source_terms: Mapping[str, float] | None = None,
    ) -> None:
        """Record total-energy changes caused by the split source step."""

        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        before = _energy_total_j(U_before, dx, area_m2)
        after = _energy_total_j(U_after, dx, area_m2)
        delta = after - before
        terms = dict(source_terms or {})

        gravity = float(terms.get("gravity_energy_j", 0.0))
        drag = float(terms.get("drag_dissipation_proxy_j", 0.0))
        friction = float(terms.get("friction_dissipation_proxy_j", 0.0))
        local = float(terms.get("local_loss_dissipation_proxy_j", 0.0))

        self.last_source_energy_delta_j = float(delta)
        self.last_gravity_energy_j = gravity
        self.last_drag_dissipation_proxy_j = drag
        self.last_friction_dissipation_proxy_j = friction
        self.last_local_loss_dissipation_proxy_j = local
        self.last_dt_s = float(dt)

        self.cumulative_source_energy_delta_j += float(delta)
        self.cumulative_gravity_energy_j += gravity
        self.cumulative_drag_dissipation_proxy_j += drag
        self.cumulative_friction_dissipation_proxy_j += friction
        self.cumulative_local_loss_dissipation_proxy_j += local

    def record_phase_change(
        self,
        *,
        U_before: np.ndarray,
        U_after: np.ndarray,
        dx: float,
        area_m2: float,
        dt: float,
        vapor_mass_source_kg: float = 0.0,
    ) -> None:
        """Record total-energy change and latent placeholder for phase change."""

        if dt < 0.0:
            raise ValueError("dt must be non-negative")
        before = _energy_total_j(U_before, dx, area_m2)
        after = _energy_total_j(U_after, dx, area_m2)
        delta = after - before
        latent = self.latent_heat_j_per_kg * float(vapor_mass_source_kg)

        self.last_phase_energy_delta_j = float(delta)
        self.last_latent_placeholder_j = float(latent)
        self.last_dt_s = float(dt)

        self.cumulative_phase_energy_delta_j += float(delta)
        self.cumulative_net_latent_placeholder_j += float(latent)
        if latent >= 0.0:
            self.cumulative_latent_requirement_j += float(latent)
        else:
            self.cumulative_latent_release_j += float(-latent)

    def expected_energy_j(self, boundary_budget: BoundaryBudgetTracker | None = None) -> float:
        """Return expected energy including boundary and applied split sources."""

        if boundary_budget is not None:
            boundary_expected = float(boundary_budget.expected_inventory()["energy_total"])
        else:
            boundary_expected = self.initial_energy_j
        return float(
            boundary_expected
            + self.cumulative_source_energy_delta_j
            + self.cumulative_phase_energy_delta_j
        )

    def diagnostics(
        self,
        current_inventory: Mapping[str, float],
        boundary_budget: BoundaryBudgetTracker | None = None,
    ) -> dict[str, float]:
        """Return flat scalar energy budget diagnostics."""

        current = dict(current_inventory)
        actual = float(current["energy_total"])
        if boundary_budget is not None:
            boundary_expected = float(boundary_budget.expected_inventory()["energy_total"])
            boundary_net = boundary_expected - self.initial_energy_j
        else:
            boundary_expected = self.initial_energy_j
            boundary_net = 0.0
        expected = self.expected_energy_j(boundary_budget)
        residual = actual - expected
        scale = max(abs(actual), abs(expected), abs(self.initial_energy_j), 1.0)
        return {
            "energy_budget_initial_j": self.initial_energy_j,
            "energy_budget_boundary_net_j": float(boundary_net),
            "energy_budget_boundary_expected_j": float(boundary_expected),
            "energy_budget_source_delta_cumulative_j": float(self.cumulative_source_energy_delta_j),
            "energy_budget_phase_delta_cumulative_j": float(self.cumulative_phase_energy_delta_j),
            "energy_budget_expected_total_j": float(expected),
            "energy_budget_actual_total_j": float(actual),
            "energy_budget_balance_residual_j": float(residual),
            "energy_budget_balance_relative_residual": float(residual / scale),
            "energy_source_gravity_cumulative_j": float(self.cumulative_gravity_energy_j),
            "energy_source_drag_dissipation_proxy_cumulative_j": float(self.cumulative_drag_dissipation_proxy_j),
            "energy_source_friction_dissipation_proxy_cumulative_j": float(self.cumulative_friction_dissipation_proxy_j),
            "energy_source_local_loss_dissipation_proxy_cumulative_j": float(self.cumulative_local_loss_dissipation_proxy_j),
            "energy_phase_latent_requirement_cumulative_j": float(self.cumulative_latent_requirement_j),
            "energy_phase_latent_release_cumulative_j": float(self.cumulative_latent_release_j),
            "energy_phase_net_latent_placeholder_cumulative_j": float(self.cumulative_net_latent_placeholder_j),
            "energy_budget_last_source_delta_j": float(self.last_source_energy_delta_j),
            "energy_budget_last_phase_delta_j": float(self.last_phase_energy_delta_j),
            "energy_source_last_gravity_j": float(self.last_gravity_energy_j),
            "energy_source_last_drag_dissipation_proxy_j": float(self.last_drag_dissipation_proxy_j),
            "energy_source_last_friction_dissipation_proxy_j": float(self.last_friction_dissipation_proxy_j),
            "energy_source_last_local_loss_dissipation_proxy_j": float(self.last_local_loss_dissipation_proxy_j),
            "energy_phase_last_latent_placeholder_j": float(self.last_latent_placeholder_j),
            "energy_budget_last_dt_s": float(self.last_dt_s),
        }


def energy_budget_residuals(
    U: np.ndarray,
    dx: float,
    area: float,
    tracker: EnergySourceBudgetTracker,
    boundary_budget: BoundaryBudgetTracker | None = None,
) -> dict[str, float]:
    """Convenience helper returning tracker diagnostics for a state array."""

    return tracker.diagnostics(inventory(U, dx, area), boundary_budget=boundary_budget)
