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
ValveDiagnosticValue = float | bool | str


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

    def _adjacent_states(self, U: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if U.ndim != 2 or U.shape[1] != N_VARS:
            raise ValueError(f"U must have shape (n_cells, {N_VARS})")
        if self.right_cell >= U.shape[0]:
            raise ValueError("internal valve must be between two existing cells")
        return U[self.left_cell].copy(), U[self.right_cell].copy()

    def flow_diagnostics(
        self,
        *,
        U: np.ndarray,
        eos: EOSModel,
        t: float,
    ) -> dict[str, ValveDiagnosticValue]:
        """Return raw and applied valve-flow telemetry without changing state.

        ``raw_target_q_m3_s`` is the direct Kv-law result. ``applied_q_m3_s`` is
        the value after the existing Mach cap and is the value used by
        :meth:`evaluate_fluxes` and therefore by :meth:`apply`.

        This helper is diagnostic-only. It does not alter the valve law, the
        cap, the numerical flux, or the conserved-energy treatment.
        """

        U_l, U_r = self._adjacent_states(U)
        prim_l = eos.primitive_from_conserved(U_l[np.newaxis, :])
        prim_r = eos.primitive_from_conserved(U_r[np.newaxis, :])

        opening = float(self.opening_schedule.opening(t))
        p_l = float(prim_l.p[0])
        p_r = float(prim_r.p[0])
        rho_l = float(prim_l.rho[0])
        rho_r = float(prim_r.rho[0])
        c_l = float(prim_l.c[0])
        c_r = float(prim_r.c[0])
        dp = float(p_l - p_r)

        raw_q = float(self.flow_rate_m3_s(U_l=U_l, U_r=U_r, eos=eos, t=t))
        c_limit = min(c_l, c_r)
        q_limit = float(self.max_mach * c_limit * self.area_m2)
        applied_q = float(np.clip(raw_q, -q_limit, q_limit))
        mach_cap_active = bool(abs(raw_q) > q_limit)
        hydraulic_separation_active = bool(
            opening <= self.closed_opening_tol or abs(applied_q) <= 1.0e-15
        )

        if applied_q > 0.0:
            flow_direction = "left_to_right"
            upwind_side = "left"
            rho_upwind = rho_l
        elif applied_q < 0.0:
            flow_direction = "right_to_left"
            upwind_side = "right"
            rho_upwind = rho_r
        else:
            flow_direction = "none"
            upwind_side = "none"
            rho_upwind = rho_l if p_l >= p_r else rho_r

        applied_face_velocity = float(applied_q / self.area_m2)
        applied_face_mach = float(
            abs(applied_face_velocity) / c_limit if c_limit > 0.0 else np.inf
        )
        applied_loss = valve_loss_from_dp_q(
            delta_p_pa=dp,
            q_m3_s=applied_q,
        )

        return {
            "opening": opening,
            "effective_kv_m3_per_h": float(opening * self.valve.kv_m3_per_h),
            "p_left_pa": p_l,
            "p_right_pa": p_r,
            "delta_p_pa": dp,
            "rho_left_kg_m3": rho_l,
            "rho_right_kg_m3": rho_r,
            "temperature_left_K": float(prim_l.T[0]),
            "temperature_right_K": float(prim_r.T[0]),
            "velocity_left_m_s": float(prim_l.u[0]),
            "velocity_right_m_s": float(prim_r.u[0]),
            "sound_speed_left_m_s": c_l,
            "sound_speed_right_m_s": c_r,
            "upwind_side": upwind_side,
            "rho_upwind_kg_m3": float(rho_upwind),
            "raw_target_q_m3_s": raw_q,
            "q_limit_m3_s": q_limit,
            "applied_q_m3_s": applied_q,
            "applied_face_velocity_m_s": applied_face_velocity,
            "applied_face_mach": applied_face_mach,
            "mach_cap_active": mach_cap_active,
            "hydraulic_separation_active": hydraulic_separation_active,
            "flow_direction": flow_direction,
            "applied_valve_loss_power_proxy_w": float(
                applied_loss["valve_loss_power_w"]
            ),
        }

    def evaluate_fluxes(
        self,
        *,
        U: np.ndarray,
        eos: EOSModel,
        t: float,
        flux_function: FluxFunction,
    ) -> tuple[np.ndarray, np.ndarray, dict[str, ValveDiagnosticValue]]:
        """Return the exact two-sided fluxes and telemetry used by ``apply``.

        The returned left flux is applied to the right face of ``left_cell``.
        The returned right flux is applied to the left face of ``right_cell``.
        Calling this method is the supported route for recording actual
        internal-face flux telemetry without reconstructing it from cell-center
        values.
        """

        U_l, U_r = self._adjacent_states(U)
        telemetry = self.flow_diagnostics(U=U, eos=eos, t=t)
        applied_q = float(telemetry["applied_q_m3_s"])

        if bool(telemetry["hydraulic_separation_active"]):
            F_l, F_r = self._closed_wall_fluxes(U_l, U_r, eos, flux_function)
        else:
            F_l, F_r = self._finite_opening_fluxes(U_l, U_r, eos, applied_q)

        return F_l, F_r, telemetry

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
        if flux_left.shape != U.shape or flux_right.shape != U.shape:
            raise ValueError("flux arrays must have the same shape as U")

        F_l, F_r, _ = self.evaluate_fluxes(
            U=U,
            eos=eos,
            t=t,
            flux_function=flux_function,
        )

        # right face of left cell; left face of right cell
        flux_right[self.left_cell] = F_l
        flux_left[self.right_cell] = F_r

    def flow_rate_m3_s(
        self,
        *,
        U_l: np.ndarray,
        U_r: np.ndarray,
        eos: EOSModel,
        t: float,
    ) -> float:
        """Return raw Kv-law flow [m3/s], positive left-to-right.

        This compatibility method intentionally returns the pre-cap target.
        Use :meth:`flow_diagnostics` for both raw and applied values.
        """

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

    def interface_energy_terms(
        self,
        *,
        U: np.ndarray,
        eos: EOSModel,
        t: float,
    ) -> dict[str, float]:
        """Return hydraulic-loss diagnostics for this internal valve.

        The existing compatibility fields continue to use the raw Kv target so
        this telemetry addition does not silently change prior diagnostic
        histories. New explicit fields expose the applied, post-cap result.

        The loss proxy is diagnostic only and is not removed from ``rhoE``.
        """

        flow = self.flow_diagnostics(U=U, eos=eos, t=t)
        dp = float(flow["delta_p_pa"])
        raw_q = float(flow["raw_target_q_m3_s"])
        applied_q = float(flow["applied_q_m3_s"])

        terms = valve_loss_from_dp_q(delta_p_pa=dp, q_m3_s=raw_q)
        applied_terms = valve_loss_from_dp_q(
            delta_p_pa=dp,
            q_m3_s=applied_q,
        )
        terms.update(
            {
                "valve_raw_q_m3_s": raw_q,
                "valve_applied_q_m3_s": applied_q,
                "valve_q_limit_m3_s": float(flow["q_limit_m3_s"]),
                "valve_mach_cap_active": float(bool(flow["mach_cap_active"])),
                "valve_hydraulic_separation_active": float(
                    bool(flow["hydraulic_separation_active"])
                ),
                "valve_applied_signed_hydraulic_power_w": float(
                    applied_terms["valve_signed_hydraulic_power_w"]
                ),
                "valve_applied_loss_power_w": float(
                    applied_terms["valve_loss_power_w"]
                ),
            }
        )
        return terms

    def diagnostics(
        self,
        *,
        U: np.ndarray,
        eos: EOSModel,
        t: float,
    ) -> dict[str, ValveDiagnosticValue]:
        """Return scalar valve diagnostics for reporting."""

        flow = self.flow_diagnostics(U=U, eos=eos, t=t)
        return {
            "valve_left_cell": float(self.left_cell),
            "valve_right_cell": float(self.right_cell),
            "valve_opening": float(flow["opening"]),
            "valve_q_m3_s": float(flow["raw_target_q_m3_s"]),
            "valve_u_face_m_s": float(
                float(flow["raw_target_q_m3_s"]) / self.area_m2
            ),
            "valve_p_left_pa": float(flow["p_left_pa"]),
            "valve_p_right_pa": float(flow["p_right_pa"]),
            "valve_dp_pa": float(flow["delta_p_pa"]),
            "valve_effective_kv_m3_per_h": float(
                flow["effective_kv_m3_per_h"]
            ),
            "valve_raw_target_q_m3_s": float(flow["raw_target_q_m3_s"]),
            "valve_q_limit_m3_s": float(flow["q_limit_m3_s"]),
            "valve_applied_q_m3_s": float(flow["applied_q_m3_s"]),
            "valve_applied_u_face_m_s": float(
                flow["applied_face_velocity_m_s"]
            ),
            "valve_applied_face_mach": float(flow["applied_face_mach"]),
            "valve_mach_cap_active": bool(flow["mach_cap_active"]),
            "valve_hydraulic_separation_active": bool(
                flow["hydraulic_separation_active"]
            ),
            "valve_flow_direction": str(flow["flow_direction"]),
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
        F_left_segment = flux_function(
            U_l[np.newaxis, :],
            U_l_wall[np.newaxis, :],
            eos,
        )[0]
        # Right segment sees a left boundary: ghost on left, interior state on right.
        F_right_segment = flux_function(
            U_r_wall[np.newaxis, :],
            U_r[np.newaxis, :],
            eos,
        )[0]
        return F_left_segment, F_right_segment

    def _finite_opening_fluxes(
        self,
        U_l: np.ndarray,
        U_r: np.ndarray,
        eos: EOSModel,
        q_m3_s: float,
    ) -> tuple[np.ndarray, np.ndarray]:
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
        h_total_up = float(
            (U_up[IDX_RHOE] + prim_up.p[0]) / U_up[IDX_RHO]
        )
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
