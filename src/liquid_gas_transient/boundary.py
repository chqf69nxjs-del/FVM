"""Boundary condition models using ghost cells.

Ver.0.2.6 adds robust pressure/tank boundary primitives.  Earlier versions
used a very small ``PressureReservoirBoundary`` that simply overwrote density to
match a static pressure.  That behavior remains as a compatibility wrapper, but
new code should prefer ``PressureTankBoundary`` with an explicit pressure
schedule and flow-direction policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
import numpy as np

from .eos import EOSModel
from .state import IDX_RHO, IDX_MOM, IDX_RHOE, IDX_RHO_XV
from .valve import KvLiquidValve, OpeningSchedule

Side = Literal["left", "right"]
FlowDirection = Literal["bidirectional", "outlet_only", "inlet_only"]
VelocityPolicy = Literal["copy", "zero", "fixed"]


class BoundaryCondition(Protocol):
    """Boundary condition interface."""

    def apply(self, U_ext: np.ndarray, n_ghost: int, side: Side, t: float, eos: EOSModel) -> None:
        """Modify ghost cells of U_ext in place."""


class PressureSchedule(Protocol):
    """Time-dependent pressure schedule for tank/reservoir boundaries."""

    def pressure_pa(self, t: float) -> float:
        """Return boundary pressure [Pa]."""


@dataclass(frozen=True)
class ConstantPressure:
    """Constant pressure schedule."""

    pressure_pa_value: float

    def __post_init__(self) -> None:
        if self.pressure_pa_value <= 0.0:
            raise ValueError("pressure_pa_value must be positive")

    def pressure_pa(self, t: float) -> float:  # noqa: ARG002 - uniform schedule interface
        return float(self.pressure_pa_value)


@dataclass(frozen=True)
class LinearPressureRamp:
    """Linear pressure transition from an initial to a final pressure.

    This is useful for later tank-pressurization, venting, and boundary
    sensitivity tests without changing the FVM core.
    """

    p_initial_pa: float
    p_final_pa: float
    t_start_s: float
    duration_s: float

    def __post_init__(self) -> None:
        if self.p_initial_pa <= 0.0 or self.p_final_pa <= 0.0:
            raise ValueError("ramp pressures must be positive")
        if self.t_start_s < 0.0:
            raise ValueError("t_start_s must be non-negative")
        if self.duration_s < 0.0:
            raise ValueError("duration_s must be non-negative")

    def pressure_pa(self, t: float) -> float:
        if t < self.t_start_s:
            return float(self.p_initial_pa)
        if self.duration_s == 0.0:
            return float(self.p_final_pa)
        s = min(max((t - self.t_start_s) / self.duration_s, 0.0), 1.0)
        return float((1.0 - s) * self.p_initial_pa + s * self.p_final_pa)


@dataclass(frozen=True)
class TransmissiveBoundary:
    """Zero-gradient boundary condition."""

    def apply(self, U_ext: np.ndarray, n_ghost: int, side: Side, t: float, eos: EOSModel) -> None:  # noqa: ARG002
        if side == "left":
            interior = U_ext[n_ghost]
            for j in range(n_ghost):
                U_ext[j] = interior
        elif side == "right":
            interior = U_ext[-n_ghost - 1]
            for j in range(n_ghost):
                U_ext[-j - 1] = interior
        else:
            raise ValueError(f"unknown side: {side}")


@dataclass(frozen=True)
class ReflectiveBoundary:
    """Slip-wall / closed-end reflection boundary."""

    def apply(self, U_ext: np.ndarray, n_ghost: int, side: Side, t: float, eos: EOSModel) -> None:  # noqa: ARG002
        if side == "left":
            for j in range(n_ghost):
                src = U_ext[n_ghost + j].copy()
                src[IDX_MOM] *= -1.0
                U_ext[n_ghost - j - 1] = src
        elif side == "right":
            for j in range(n_ghost):
                src = U_ext[-n_ghost - j - 1].copy()
                src[IDX_MOM] *= -1.0
                U_ext[-n_ghost + j] = src
        else:
            raise ValueError(f"unknown side: {side}")


@dataclass(frozen=True)
class PressureTankBoundary:
    """Pressure tank/reservoir boundary with explicit flow policy.

    Parameters
    ----------
    pressure_schedule:
        Time-dependent static tank pressure.  The ghost-cell density is obtained
        through ``eos.density_from_pressure``.
    flow_direction:
        ``bidirectional`` always applies the pressure boundary. ``outlet_only``
        allows flow from the pipe domain into the tank and turns forbidden
        reverse flow into a reflective wall. ``inlet_only`` does the opposite.
        This avoids accidental tank injection/extraction caused by pressure
        boundaries in early verification runs.
    velocity_policy:
        Velocity used when the pressure boundary is active. ``copy`` preserves
        the old Ver.0.2 behavior, ``zero`` represents a stagnant large tank, and
        ``fixed`` imposes ``fixed_velocity_m_s``.
    pressure_floor_pa:
        Defensive lower bound checked before EOS inversion.  This is not a
        physical cavitation model; it only catches invalid schedules early.
    """

    pressure_schedule: PressureSchedule
    flow_direction: FlowDirection = "bidirectional"
    velocity_policy: VelocityPolicy = "copy"
    fixed_velocity_m_s: float = 0.0
    pressure_floor_pa: float = 1.0

    def __post_init__(self) -> None:
        if self.flow_direction not in {"bidirectional", "outlet_only", "inlet_only"}:
            raise ValueError("flow_direction must be bidirectional, outlet_only, or inlet_only")
        if self.velocity_policy not in {"copy", "zero", "fixed"}:
            raise ValueError("velocity_policy must be copy, zero, or fixed")
        if self.pressure_floor_pa <= 0.0:
            raise ValueError("pressure_floor_pa must be positive")
        if not np.isfinite(self.fixed_velocity_m_s):
            raise ValueError("fixed_velocity_m_s must be finite")

    def pressure_pa(self, t: float) -> float:
        p = float(self.pressure_schedule.pressure_pa(t))
        if not np.isfinite(p):
            raise ValueError("tank pressure schedule returned non-finite pressure")
        if p < self.pressure_floor_pa:
            raise ValueError("tank pressure is below pressure_floor_pa")
        return p

    def apply(self, U_ext: np.ndarray, n_ghost: int, side: Side, t: float, eos: EOSModel) -> None:
        if side == "left":
            interior_index = n_ghost
        elif side == "right":
            interior_index = -n_ghost - 1
        else:
            raise ValueError(f"unknown side: {side}")

        interior = U_ext[interior_index].copy()
        u_i = float(interior[IDX_MOM] / interior[IDX_RHO])
        if not self._flow_allowed(side, u_i):
            self._apply_reflective(U_ext, n_ghost, side)
            return

        p_b = self.pressure_pa(t)
        rho_b = float(eos.density_from_pressure(p_b))
        if not np.isfinite(rho_b) or rho_b <= 0.0:
            raise ValueError("pressure tank boundary produced non-positive density")

        if self.velocity_policy == "copy":
            u_b = u_i
        elif self.velocity_policy == "zero":
            u_b = 0.0
        elif self.velocity_policy == "fixed":
            u_b = self.fixed_velocity_m_s
        else:  # pragma: no cover - protected by __post_init__
            raise ValueError(f"unknown velocity_policy: {self.velocity_policy}")

        e_b: float | None = None
        internal_energy_from_pressure = getattr(
            eos,
            "internal_energy_from_pressure",
            None,
        )
        if callable(internal_energy_from_pressure):
            e_b = float(
                np.asarray(internal_energy_from_pressure(p_b))
            )
            if not np.isfinite(e_b):
                raise ValueError(
                    "pressure tank boundary produced non-finite internal energy"
                )

        ghost = self._with_density_velocity(
            interior,
            rho_b,
            u_b,
            e_new=e_b,
        )
        if side == "left":
            for j in range(n_ghost):
                U_ext[j] = ghost
        else:
            for j in range(n_ghost):
                U_ext[-j - 1] = ghost

    def diagnostics(self, t: float) -> dict[str, float]:
        return {
            "tank_pressure_pa": float(self.pressure_pa(t)),
            "tank_flow_direction_mode": float({"bidirectional": 0, "outlet_only": 1, "inlet_only": 2}[self.flow_direction]),
        }

    def _flow_allowed(self, side: Side, u_i: float) -> bool:
        if self.flow_direction == "bidirectional":
            return True
        # Positive coordinate points from land tank to ship tank.
        domain_to_tank = (side == "right" and u_i >= 0.0) or (side == "left" and u_i <= 0.0)
        if self.flow_direction == "outlet_only":
            return domain_to_tank
        # inlet_only
        return not domain_to_tank

    @staticmethod
    def _apply_reflective(U_ext: np.ndarray, n_ghost: int, side: Side) -> None:
        if side == "left":
            for j in range(n_ghost):
                src = U_ext[n_ghost + j].copy()
                src[IDX_MOM] *= -1.0
                U_ext[n_ghost - j - 1] = src
        else:
            for j in range(n_ghost):
                src = U_ext[-n_ghost - j - 1].copy()
                src[IDX_MOM] *= -1.0
                U_ext[-n_ghost + j] = src

    @staticmethod
    def _with_density_velocity(
        U: np.ndarray,
        rho_new: float,
        u_new: float,
        *,
        e_new: float | None = None,
    ) -> np.ndarray:
        rho_old = U[IDX_RHO]
        E_old = U[IDX_RHOE] / rho_old
        u_old = U[IDX_MOM] / rho_old
        e_old = E_old - 0.5 * u_old**2
        e_target = e_old if e_new is None else float(e_new)
        if not np.isfinite(e_target):
            raise ValueError("boundary internal energy must be finite")

        xv = U[IDX_RHO_XV] / rho_old
        out = U.copy()
        out[IDX_RHO] = rho_new
        out[IDX_MOM] = rho_new * u_new
        out[IDX_RHOE] = rho_new * (e_target + 0.5 * u_new**2)
        out[IDX_RHO_XV] = rho_new * xv
        return out


@dataclass(frozen=True)
class PressureReservoirBoundary:
    """Compatibility wrapper for the earlier static pressure reservoir.

    New code should use ``PressureTankBoundary(ConstantPressure(...))``.  This
    wrapper intentionally preserves the old default behavior: bidirectional
    pressure boundary and copied adjacent-cell velocity.
    """

    pressure_pa: float

    def apply(self, U_ext: np.ndarray, n_ghost: int, side: Side, t: float, eos: EOSModel) -> None:
        PressureTankBoundary(
            pressure_schedule=ConstantPressure(self.pressure_pa),
            flow_direction="bidirectional",
            velocity_policy="copy",
        ).apply(U_ext, n_ghost, side, t, eos)

    def diagnostics(self, t: float) -> dict[str, float]:  # noqa: ARG002
        return {"reservoir_pressure_pa": float(self.pressure_pa)}


@dataclass(frozen=True)
class ValveOutletBoundary:
    """Right-end liquid valve connected to a downstream pressure reservoir.

    This boundary imposes a target face velocity obtained from a single-phase
    liquid Kv law. Ghost-cell momentum is mirrored around that target velocity:

        u_ghost = 2 u_face,target - u_interior

    Therefore, when opening = 0, the model becomes a reflective closed-end wall.
    This is the key Ver.0.2.1 improvement over the previous large-K internal
    source-term approximation.
    """

    downstream_pressure_pa: float
    area_m2: float
    valve: KvLiquidValve
    opening_schedule: OpeningSchedule
    max_mach: float = 0.8

    def __post_init__(self) -> None:
        if self.downstream_pressure_pa <= 0.0:
            raise ValueError("downstream_pressure_pa must be positive")
        if self.area_m2 <= 0.0:
            raise ValueError("area_m2 must be positive")
        if not 0.0 < self.max_mach <= 1.0:
            raise ValueError("max_mach must be in (0, 1]")

    def apply(self, U_ext: np.ndarray, n_ghost: int, side: Side, t: float, eos: EOSModel) -> None:
        if side != "right":
            raise NotImplementedError("ValveOutletBoundary is currently implemented only for the right boundary")

        interior = U_ext[-n_ghost - 1].copy()
        prim = eos.primitive_from_conserved(interior[np.newaxis, :])
        rho_i = float(prim.rho[0])
        u_i = float(prim.u[0])
        p_i = float(prim.p[0])
        c_i = float(prim.c[0])

        opening = self.opening_schedule.opening(t)
        q_target = self.valve.flow_rate_m3_s(
            p_up_pa=p_i,
            p_down_pa=self.downstream_pressure_pa,
            rho_kg_m3=rho_i,
            opening=opening,
        )
        u_face = q_target / self.area_m2
        u_limit = self.max_mach * c_i
        u_face = float(np.clip(u_face, -u_limit, u_limit))

        ghost = interior.copy()
        u_ghost = 2.0 * u_face - u_i
        ghost[IDX_MOM] = ghost[IDX_RHO] * u_ghost

        # Keep rho, rhoE, and rho*xv extrapolated from the interior. For Ver.0.2.1
        # the valve controls hydraulic flux through momentum only; downstream
        # thermodynamics will be upgraded later for flashing/venting models.
        for j in range(n_ghost):
            U_ext[-j - 1] = ghost

    def target_flow_rate(self, U_interior: np.ndarray, t: float, eos: EOSModel) -> float:
        """Return the current valve-law flow rate for diagnostics/tests."""

        prim = eos.primitive_from_conserved(U_interior[np.newaxis, :])
        return self.valve.flow_rate_m3_s(
            p_up_pa=float(prim.p[0]),
            p_down_pa=self.downstream_pressure_pa,
            rho_kg_m3=float(prim.rho[0]),
            opening=self.opening_schedule.opening(t),
        )
