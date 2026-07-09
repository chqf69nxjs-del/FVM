"""Pump-work and valve-loss interface budget diagnostics for Ver.0.4.3.

This module records energy-like diagnostic terms associated with hydraulic
interfaces.  The terms are intentionally diagnostic placeholders: they do not
alter ``rhoE`` in the current toy model.  Their purpose is to separate the
energy bookkeeping into physically meaningful channels before the real-fluid
energy closure is introduced.

Sign convention
---------------

* Pump hydraulic work is positive when a pump pressure rise drives positive
  volumetric flow into the computational domain.
* Valve loss is positive when pressure drop and volumetric flow have the same
  sign across the internal valve, i.e. hydraulic head is dissipated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping
import numpy as np

from .eos import EOSModel
from .state import IDX_RHO


@dataclass
class InterfaceEnergyBudgetTracker:
    """Cumulative diagnostic ledger for hydraulic-interface energy terms."""

    cumulative_pump_hydraulic_work_j: float = 0.0
    cumulative_valve_loss_proxy_j: float = 0.0
    cumulative_interface_net_diagnostic_j: float = 0.0

    last_pump_hydraulic_work_j: float = 0.0
    last_valve_loss_proxy_j: float = 0.0
    last_pump_power_w: float = 0.0
    last_valve_loss_power_w: float = 0.0
    last_pump_q_m3_s: float = 0.0
    last_valve_q_m3_s: float = 0.0
    last_pump_delta_p_pa: float = 0.0
    last_valve_delta_p_pa: float = 0.0
    last_dt_s: float = 0.0

    def record_step(
        self,
        *,
        left_boundary,
        right_boundary,
        left_flux: np.ndarray,
        right_flux: np.ndarray,
        internal_interfaces: Iterable,
        U: np.ndarray,
        eos: EOSModel,
        area_m2: float,
        dt: float,
        t: float,
    ) -> None:
        """Record pump and valve diagnostic terms for one solver step."""

        if area_m2 <= 0.0:
            raise ValueError("area_m2 must be positive")
        if dt < 0.0:
            raise ValueError("dt must be non-negative")

        pump_work = 0.0
        pump_power = 0.0
        pump_q = 0.0
        pump_dp = 0.0

        for boundary, flux, side in ((left_boundary, left_flux, "left"), (right_boundary, right_flux, "right")):
            method = getattr(boundary, "interface_energy_terms", None)
            if method is None:
                continue
            terms = method(boundary_flux=flux, area_m2=area_m2, eos=eos, t=t, side=side)
            pump_power_i = float(terms.get("pump_hydraulic_power_w", 0.0))
            pump_work += pump_power_i * dt
            pump_power += pump_power_i
            pump_q += float(terms.get("pump_q_m3_s", 0.0))
            # For multiple pump-like boundaries this is a diagnostic sum.
            pump_dp += float(terms.get("pump_delta_p_pa", 0.0))

        valve_loss = 0.0
        valve_power = 0.0
        valve_q = 0.0
        valve_dp = 0.0
        for interface in internal_interfaces:
            method = getattr(interface, "interface_energy_terms", None)
            if method is None:
                continue
            terms = method(U=U, eos=eos, t=t)
            valve_power_i = float(terms.get("valve_loss_power_w", 0.0))
            valve_loss += valve_power_i * dt
            valve_power += valve_power_i
            valve_q += float(terms.get("valve_q_m3_s", 0.0))
            valve_dp += float(terms.get("valve_dp_pa", 0.0))

        self.last_pump_hydraulic_work_j = float(pump_work)
        self.last_valve_loss_proxy_j = float(valve_loss)
        self.last_pump_power_w = float(pump_power)
        self.last_valve_loss_power_w = float(valve_power)
        self.last_pump_q_m3_s = float(pump_q)
        self.last_valve_q_m3_s = float(valve_q)
        self.last_pump_delta_p_pa = float(pump_dp)
        self.last_valve_delta_p_pa = float(valve_dp)
        self.last_dt_s = float(dt)

        self.cumulative_pump_hydraulic_work_j += float(pump_work)
        self.cumulative_valve_loss_proxy_j += float(valve_loss)
        self.cumulative_interface_net_diagnostic_j += float(pump_work - valve_loss)

    def diagnostics(self) -> dict[str, float]:
        """Return flat scalar diagnostics."""

        return {
            "energy_interface_pump_hydraulic_work_cumulative_j": float(self.cumulative_pump_hydraulic_work_j),
            "energy_interface_valve_loss_proxy_cumulative_j": float(self.cumulative_valve_loss_proxy_j),
            "energy_interface_net_diagnostic_cumulative_j": float(self.cumulative_interface_net_diagnostic_j),
            "energy_interface_last_pump_hydraulic_work_j": float(self.last_pump_hydraulic_work_j),
            "energy_interface_last_valve_loss_proxy_j": float(self.last_valve_loss_proxy_j),
            "energy_interface_pump_power_w": float(self.last_pump_power_w),
            "energy_interface_valve_loss_power_w": float(self.last_valve_loss_power_w),
            "energy_interface_pump_q_m3_s": float(self.last_pump_q_m3_s),
            "energy_interface_valve_q_m3_s": float(self.last_valve_q_m3_s),
            "energy_interface_pump_delta_p_pa": float(self.last_pump_delta_p_pa),
            "energy_interface_valve_delta_p_pa": float(self.last_valve_delta_p_pa),
            "energy_interface_last_dt_s": float(self.last_dt_s),
        }


def pump_work_from_boundary_flux(*, mass_flux: float, area_m2: float, rho_boundary: float, delta_p_pa: float) -> dict[str, float]:
    """Return pump hydraulic power diagnostics from a boundary mass flux.

    ``mass_flux`` is per unit area and is positive in the numerical flux
    direction.  For the left boundary this is positive into the computational
    domain.  The helper is kept separate for unit verification.
    """

    if area_m2 <= 0.0:
        raise ValueError("area_m2 must be positive")
    if rho_boundary <= 0.0:
        raise ValueError("rho_boundary must be positive")
    mass_rate = float(area_m2 * mass_flux)
    q = mass_rate / float(rho_boundary)
    power = float(delta_p_pa) * q
    return {
        "pump_mass_rate_kg_s": float(mass_rate),
        "pump_q_m3_s": float(q),
        "pump_delta_p_pa": float(delta_p_pa),
        "pump_hydraulic_power_w": float(power),
    }


def valve_loss_from_dp_q(*, delta_p_pa: float, q_m3_s: float) -> dict[str, float]:
    """Return valve hydraulic-loss proxy from pressure drop and flow rate."""

    signed_power = float(delta_p_pa) * float(q_m3_s)
    loss_power = max(signed_power, 0.0)
    return {
        "valve_dp_pa": float(delta_p_pa),
        "valve_q_m3_s": float(q_m3_s),
        "valve_signed_hydraulic_power_w": float(signed_power),
        "valve_loss_power_w": float(loss_power),
    }
