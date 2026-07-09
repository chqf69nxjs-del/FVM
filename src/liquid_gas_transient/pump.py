"""Quasi-steady pump head models for Ver.0.2.5.

The pump model introduced here is intentionally narrow.  It is a boundary
pressure-rise model for a pump located immediately upstream of the FVM pipe
domain:

    suction reservoir -- pump -- pipe domain

It does not yet solve pump inertia, four-quadrant characteristics, reverse
rotation, check-valve dynamics, or motor trip transients.  Those belong to the
later dedicated pump-stop scenario.  Ver.0.2.5 only provides a verified way to
turn a tank pressure and a pump head schedule into a pump-discharge boundary
pressure that can be used by the conservative FVM solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
import numpy as np

from .eos import EOSModel
from .state import IDX_RHO, IDX_MOM, IDX_RHOE, IDX_RHO_XV
from .interface_budget import pump_work_from_boundary_flux

Side = Literal["left", "right"]


class PumpHeadSchedule(Protocol):
    """Time-dependent pump pressure-rise law."""

    def head_rise_pa(self, t: float) -> float:
        """Return pump pressure rise [Pa] at time ``t``."""


@dataclass(frozen=True)
class ConstantPumpHead:
    """Constant pressure-rise schedule."""

    delta_p_pa: float

    def __post_init__(self) -> None:
        if self.delta_p_pa < 0.0:
            raise ValueError("delta_p_pa must be non-negative")

    def head_rise_pa(self, t: float) -> float:  # noqa: ARG002 - uniform schedule interface
        return float(self.delta_p_pa)


@dataclass(frozen=True)
class LinearPumpTrip:
    """Linear pump-head decay from nominal to final pressure rise.

    Parameters
    ----------
    delta_p_initial_pa:
        Pump pressure rise before the trip begins.
    trip_start_s:
        Time at which the head starts to decay.
    trip_duration_s:
        Duration of the linear decay.  If zero, the head changes instantly at
        ``trip_start_s``.
    delta_p_final_pa:
        Final pressure rise after the trip.  Defaults to zero, representing a
        simple pump coast-down placeholder.
    """

    delta_p_initial_pa: float
    trip_start_s: float
    trip_duration_s: float
    delta_p_final_pa: float = 0.0

    def __post_init__(self) -> None:
        if self.delta_p_initial_pa < 0.0:
            raise ValueError("delta_p_initial_pa must be non-negative")
        if self.delta_p_final_pa < 0.0:
            raise ValueError("delta_p_final_pa must be non-negative")
        if self.trip_start_s < 0.0:
            raise ValueError("trip_start_s must be non-negative")
        if self.trip_duration_s < 0.0:
            raise ValueError("trip_duration_s must be non-negative")

    def head_rise_pa(self, t: float) -> float:
        if t < self.trip_start_s:
            return float(self.delta_p_initial_pa)
        if self.trip_duration_s == 0.0:
            return float(self.delta_p_final_pa)
        s = min(max((t - self.trip_start_s) / self.trip_duration_s, 0.0), 1.0)
        return float((1.0 - s) * self.delta_p_initial_pa + s * self.delta_p_final_pa)


@dataclass(frozen=True)
class PumpInletBoundary:
    """Left-boundary pump discharge connected to an upstream suction reservoir.

    The boundary pressure is

        p_discharge(t) = p_suction + Δp_pump(t)

    and ghost-cell density is constructed from that pressure through the EOS.
    Adjacent-cell velocity, total specific energy, and vapor mass fraction are
    copied into the ghost state, matching the existing pressure-reservoir
    boundary style used by the verification skeleton.
    """

    suction_pressure_pa: float
    head_schedule: PumpHeadSchedule

    def __post_init__(self) -> None:
        if self.suction_pressure_pa <= 0.0:
            raise ValueError("suction_pressure_pa must be positive")

    def discharge_pressure_pa(self, t: float) -> float:
        p = self.suction_pressure_pa + self.head_schedule.head_rise_pa(t)
        if p <= 0.0:
            raise ValueError("pump discharge pressure must be positive")
        return float(p)

    def apply(self, U_ext: np.ndarray, n_ghost: int, side: Side, t: float, eos: EOSModel) -> None:
        if side != "left":
            raise NotImplementedError("PumpInletBoundary is currently implemented only for the left boundary")
        p_b = self.discharge_pressure_pa(t)
        rho_b = float(eos.density_from_pressure(p_b))
        if rho_b <= 0.0:
            raise ValueError("pump boundary produced non-positive density")

        src = U_ext[n_ghost].copy()
        ghost = self._with_density(src, rho_b)
        for j in range(n_ghost):
            U_ext[j] = ghost


    def interface_energy_terms(self, *, boundary_flux: np.ndarray, area_m2: float, eos: EOSModel, t: float, side: str) -> dict[str, float]:
        """Return pump hydraulic-work diagnostics for a boundary flux.

        The current implementation is intended for the left inlet pump.  Work
        is positive when the pump pressure rise and the incoming volumetric flow
        have the same sign.  The term is diagnostic only; it is not added to
        ``rhoE`` in Ver.0.4.3.
        """

        if side != "left":
            return {}
        p_b = self.discharge_pressure_pa(t)
        rho_b = float(eos.density_from_pressure(p_b))
        return pump_work_from_boundary_flux(
            mass_flux=float(boundary_flux[IDX_RHO]),
            area_m2=area_m2,
            rho_boundary=rho_b,
            delta_p_pa=float(self.head_schedule.head_rise_pa(t)),
        )

    def diagnostics(self, t: float) -> dict[str, float]:
        return {
            "pump_suction_pressure_pa": float(self.suction_pressure_pa),
            "pump_delta_p_pa": float(self.head_schedule.head_rise_pa(t)),
            "pump_discharge_pressure_pa": float(self.discharge_pressure_pa(t)),
        }

    @staticmethod
    def _with_density(U: np.ndarray, rho_new: float) -> np.ndarray:
        rho_old = U[IDX_RHO]
        u = U[IDX_MOM] / rho_old
        E = U[IDX_RHOE] / rho_old
        xv = U[IDX_RHO_XV] / rho_old
        out = U.copy()
        out[IDX_RHO] = rho_new
        out[IDX_MOM] = rho_new * u
        out[IDX_RHOE] = rho_new * E
        out[IDX_RHO_XV] = rho_new * xv
        return out
