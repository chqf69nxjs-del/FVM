"""Internal hydraulic interfaces for the conservative FVM solver.

Ver.0.2.2 introduces two-sided interface fluxes. This is needed for devices
inside the pipe, such as an ESD valve located between two finite-volume cells.
A closed internal valve is not the same as a standard interior Riemann face:
each pipe segment sees its own wall reaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
import numpy as np

from .eos import EOSModel
from .state import IDX_RHO, IDX_MOM, IDX_RHOE, IDX_RHO_XV, N_VARS
from .valve import KvLiquidValve, OpeningSchedule
from .interface_budget import valve_loss_from_dp_q

FluxFunction = Callable[[np.ndarray, np.ndarray, EOSModel], np.ndarray]


class InternalInterface(Protocol):
    """Interface object that may override left/right cell-face fluxes."""

    def apply(
        self,
        *,
        flux_left: np.ndarray,
        flux_right: np.ndarray,
        U: np.ndarray,
        eos: EOSModel,
        t: float,
        flux_function: FluxFunction,
    ) -> None:
        """Modify cell-face flux arrays in place."""


@dataclass(frozen=True)
class InternalValveInterface:
    """Liquid ESD valve located between two cells.

    Parameters
    ----------
    left_cell:
        Zero-based index of the cell immediately upstream/left of the valve.
        The valve interface is between ``left_cell`` and ``left_cell + 1``.
    area_m2:
        Pipe flow area [m2].
    valve:
        Single-phase liquid Kv law.
    opening_schedule:
        Time-dependent valve opening fraction.
    max_mach:
        Safety cap on the target valve velocity.

    Notes
    -----
    The interface deliberately provides **two-sided fluxes**:

    - the right face flux of the left cell, and
    - the left face flux of the right cell.

    Mass, energy, and vapor-mass flux are matched across the interface for
    finite opening. Momentum is allowed to be non-conservative because the valve
    body exerts an external force and dissipates mechanical energy. For zero
    opening, both sides reduce to independent reflective-wall fluxes.
    """

    left_cell: int
    area_m2: float
    valve: KvLiquidValve
    opening_schedule: OpeningSchedule
    max_mach: float = 0.8
    closed_opening_tol: float = 1.0e-12

    def __post_init__(self) -> None:
        if self.left_cell < 0:
            raise ValueError("left_cell must be non-negative")
        if self.area_m2 <= 0.0:
            raise ValueError("area_m2 must be positive")
        if not 0.0 < self.max_mach <= 1.0:
            raise ValueError("max_mach must be in (0, 1]")
        if self.closed_opening_tol < 0.0:
            raise ValueError("closed_opening_tol must be non-negative")

    @property
    def right_cell(self) -> int:
        return self.left_cell + 1

    def apply(
        self,
        *,
        flux_left: np.ndarray,
        flux_right: np.ndarray,
        U: np.ndarray,
        eos: EOSModel,
        t: float,
        flux_function: FluxFunction,
    ) -> None:
        n_cells = U.shape[0]
        if self.right_cell >= n_cells:
            raise ValueError("internal valve must be between two existing cells")
        if flux_left.shape != U.shape or flux_right.shape != U.shape:
            raise ValueError("flux arrays must have the same shape as U")

        i_l = self.left_cell
        i_r = self.right_cell
        U_l = U[i_l].copy()
        U_r = U[i_r].copy()
        prim_l = eos.primitive_from_conserved(U_l[np.newaxis, :])
        prim_r = eos.primitive_from_conserved(U_r[np.newaxis, :])

        opening = self.opening_schedule.opening(t)
        if opening <= self.closed_opening_tol:
            F_l, F_r = self._closed_wall_fluxes(U_l, U_r, eos, flux_function)
        else:
            q = self.flow_rate_m3_s(U_l=U_l, U_r=U_r, eos=eos, t=t)
            c_limit = min(float(prim_l.c[0]), float(prim_r.c[0]))
            q_limit = self.max_mach * c_limit * self.area_m2
            q = float(np.clip(q, -q_limit, q_limit))
            if abs(q) <= 1.0e-15:
                # No through-flow. Keep hydraulic separation explicit.
                F_l, F_r = self._closed_wall_fluxes(U_l, U_r, eos, flux_function)
            else:
                F_l, F_r = self._finite_opening_fluxes(U_l, U_r, eos, q)

        # right face of left cell; left face of right cell
        flux_right[i_l] = F_l
        flux_left[i_r] = F_r

    def flow_rate_m3_s(self, *, U_l: np.ndarray, U_r: np.ndarray, eos: EOSModel, t: float) -> float:
        """Return valve volumetric flow rate [m3/s], positive left-to-right."""

        prim_l = eos.primitive_from_conserved(U_l[np.newaxis, :])
        prim_r = eos.primitive_from_conserved(U_r[np.newaxis, :])
        p_l = float(prim_l.p[0])
        p_r = float(prim_r.p[0])
        rho_for_law = float(prim_l.rho[0] if p_l >= p_r else prim_r.rho[0])
        return self.valve.flow_rate_m3_s(
            p_up_pa=p_l,
            p_down_pa=p_r,
            rho_kg_m3=rho_for_law,
            opening=self.opening_schedule.opening(t),
        )


    def interface_energy_terms(self, *, U: np.ndarray, eos: EOSModel, t: float) -> dict[str, float]:
        """Return hydraulic-loss diagnostics for this internal valve.

        The loss proxy is ``max((p_left - p_right) * Q, 0)``. It is diagnostic
        only in Ver.0.4.3 and is not removed from ``rhoE``.
        """

        if self.right_cell >= U.shape[0]:
            raise ValueError("internal valve must be between two existing cells")
        U_l = U[self.left_cell]
        U_r = U[self.right_cell]
        prim_l = eos.primitive_from_conserved(U_l[np.newaxis, :])
        prim_r = eos.primitive_from_conserved(U_r[np.newaxis, :])
        dp = float(prim_l.p[0] - prim_r.p[0])
        q = self.flow_rate_m3_s(U_l=U_l, U_r=U_r, eos=eos, t=t)
        return valve_loss_from_dp_q(delta_p_pa=dp, q_m3_s=q)

    def diagnostics(self, *, U: np.ndarray, eos: EOSModel, t: float) -> dict[str, float]:
        """Return scalar valve diagnostics for reporting."""

        if self.right_cell >= U.shape[0]:
            raise ValueError("internal valve must be between two existing cells")
        U_l = U[self.left_cell]
        U_r = U[self.right_cell]
        prim_l = eos.primitive_from_conserved(U_l[np.newaxis, :])
        prim_r = eos.primitive_from_conserved(U_r[np.newaxis, :])
        q = self.flow_rate_m3_s(U_l=U_l, U_r=U_r, eos=eos, t=t)
        return {
            "valve_left_cell": float(self.left_cell),
            "valve_right_cell": float(self.right_cell),
            "valve_opening": float(self.opening_schedule.opening(t)),
            "valve_q_m3_s": float(q),
            "valve_u_face_m_s": float(q / self.area_m2),
            "valve_p_left_pa": float(prim_l.p[0]),
            "valve_p_right_pa": float(prim_r.p[0]),
            "valve_dp_pa": float(prim_l.p[0] - prim_r.p[0]),
        }

    @staticmethod
    def _with_velocity(U: np.ndarray, u_new: float) -> np.ndarray:
        out = U.copy()
        out[IDX_MOM] = out[IDX_RHO] * u_new
        return out

    @classmethod
    def _closed_wall_fluxes(
        cls,
        U_l: np.ndarray,
        U_r: np.ndarray,
        eos: EOSModel,
        flux_function: FluxFunction,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return independent reflective-wall fluxes on both valve sides."""

        u_l = float(U_l[IDX_MOM] / U_l[IDX_RHO])
        u_r = float(U_r[IDX_MOM] / U_r[IDX_RHO])
        U_l_wall = cls._with_velocity(U_l, -u_l)
        U_r_wall = cls._with_velocity(U_r, -u_r)
        # Left segment sees a right boundary: interior state on left, ghost on right.
        F_left_segment = flux_function(U_l[np.newaxis, :], U_l_wall[np.newaxis, :], eos)[0]
        # Right segment sees a left boundary: ghost on left, interior state on right.
        F_right_segment = flux_function(U_r_wall[np.newaxis, :], U_r[np.newaxis, :], eos)[0]
        return F_left_segment, F_right_segment

    def _finite_opening_fluxes(self, U_l: np.ndarray, U_r: np.ndarray, eos: EOSModel, q_m3_s: float) -> tuple[np.ndarray, np.ndarray]:  # type: ignore[override]
        prim_l = eos.primitive_from_conserved(U_l[np.newaxis, :])
        prim_r = eos.primitive_from_conserved(U_r[np.newaxis, :])
        q_per_area = q_m3_s / self.area_m2
        if q_per_area >= 0.0:
            U_up = U_l
            prim_up = prim_l
        else:
            U_up = U_r
            prim_up = prim_r

        rho_up = float(prim_up.rho[0])
        u_up = float(prim_up.u[0])
        h_total_up = float((U_up[IDX_RHOE] + prim_up.p[0]) / U_up[IDX_RHO])
        xv_up = float(U_up[IDX_RHO_XV] / U_up[IDX_RHO])
        m_flux = rho_up * q_per_area

        F_common = np.zeros(N_VARS, dtype=float)
        F_common[IDX_RHO] = m_flux
        F_common[IDX_MOM] = m_flux * u_up
        F_common[IDX_RHOE] = m_flux * h_total_up
        F_common[IDX_RHO_XV] = m_flux * xv_up

        F_left_segment = F_common.copy()
        F_right_segment = F_common.copy()
        F_left_segment[IDX_MOM] += float(prim_l.p[0])
        F_right_segment[IDX_MOM] += float(prim_r.p[0])
        return F_left_segment, F_right_segment
