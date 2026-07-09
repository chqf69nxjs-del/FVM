"""Source-term operators for operator splitting.

Ver.0.2.4 adds cell-wise segment source profiles. The conservative FVM update
is still one-dimensional and first-order, but friction and gravity are no longer
single global constants hidden in a case script. They are explicit arrays derived
from the ordered component network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
import numpy as np

from .config import PipeGeometry
from .grid import UniformGrid
from .state import IDX_MOM, IDX_RHO, IDX_RHOE
from .eos import EOSModel


class SourceTerm(Protocol):
    """Source-term interface."""

    def apply(self, U: np.ndarray, grid: UniformGrid, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        """Return source-updated conservative state."""


@dataclass(frozen=True)
class NoSource:
    """No source terms."""

    def apply(self, U: np.ndarray, grid: UniformGrid, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        return U


def _as_cell_array(value: float | np.ndarray, n_cells: int, name: str) -> np.ndarray:
    """Return a scalar or vector input as a validated cell array."""

    arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        return np.full(n_cells, float(arr), dtype=float)
    if arr.shape != (n_cells,):
        raise ValueError(f"{name} array must have shape (n_cells,)")
    return arr.astype(float, copy=False)


def _loss_array(
    value: float | np.ndarray | Callable[[float, np.ndarray], np.ndarray],
    t: float,
    grid: UniformGrid,
) -> np.ndarray:
    """Return a local-loss coefficient array."""

    if callable(value):
        raw = value(t, grid.cell_centers)
    else:
        raw = value
    k = _as_cell_array(raw, grid.n_cells, "local_loss_k")
    if np.any(k < 0.0):
        raise ValueError("local_loss_k must be non-negative")
    return k


@dataclass(frozen=True)
class CellwisePipeSourceTerms:
    """Cell-wise friction, gravity, and local-loss source terms.

    Momentum source model
    ---------------------
    The applied split update is

        d(rho u)/dt = -rho g dz/dx - rho a u |u|,

    where

        a = f_D/(2D) + K/(2 dx).

    Gravity is updated explicitly. Quadratic drag is integrated by the exact
    scalar decay

        u_new = u_old / (1 + a |u_old| dt),

    which prevents the velocity sign reversal that a naive explicit drag update
    can produce for stiff local losses.
    """

    diameter_m: float | np.ndarray
    darcy_friction_factor: float | np.ndarray = 0.0
    gravity_m_s2: float = 9.80665
    dzdx: float | np.ndarray = 0.0
    local_loss_k: float | np.ndarray | Callable[[float, np.ndarray], np.ndarray] = 0.0
    include_gravity_energy_source: bool = True

    def __post_init__(self) -> None:
        if self.gravity_m_s2 < 0.0:
            raise ValueError("gravity_m_s2 must be non-negative")

    def apply(self, U: np.ndarray, grid: UniformGrid, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        if dt < 0.0:
            raise ValueError("dt must be non-negative")

        out = U.copy()
        diameter = _as_cell_array(self.diameter_m, grid.n_cells, "diameter_m")
        friction = _as_cell_array(self.darcy_friction_factor, grid.n_cells, "darcy_friction_factor")
        dzdx = _as_cell_array(self.dzdx, grid.n_cells, "dzdx")
        if np.any(diameter <= 0.0):
            raise ValueError("diameter_m must be positive")
        if np.any(friction < 0.0):
            raise ValueError("darcy_friction_factor must be non-negative")

        prim = eos.primitive_from_conserved(out)
        rho = prim.rho
        u = prim.u

        if np.any(dzdx != 0.0):
            out[..., IDX_MOM] += dt * (-rho * self.gravity_m_s2 * dzdx)
            if self.include_gravity_energy_source:
                out[..., IDX_RHOE] += dt * (-rho * u * self.gravity_m_s2 * dzdx)

        # Recompute velocity after gravity before applying quadratic drag.
        prim = eos.primitive_from_conserved(out)
        rho = prim.rho
        u = prim.u

        drag_coeff = friction / (2.0 * diameter)
        k = _loss_array(self.local_loss_k, t, grid)
        drag_coeff += k / (2.0 * grid.dx)

        if np.any(drag_coeff != 0.0):
            u_new = u / (1.0 + drag_coeff * np.abs(u) * dt)
            out[..., IDX_MOM] = rho * u_new

        return out

    def energy_budget_terms(self, U: np.ndarray, grid: UniformGrid, eos: EOSModel, dt: float, t: float) -> dict[str, float]:
        """Return diagnostic source-energy terms for one split update.

        The values returned here are diagnostics only. ``gravity_energy_j`` is
        the energy actually added to ``rhoE`` when
        ``include_gravity_energy_source`` is enabled. The drag/friction/local
        loss entries are positive kinetic-energy dissipation proxies computed
        from the same exact velocity-decay update used by :meth:`apply`; the
        present toy model does not yet remove this amount from conservative
        total energy.
        """

        if dt < 0.0:
            raise ValueError("dt must be non-negative")

        diameter = _as_cell_array(self.diameter_m, grid.n_cells, "diameter_m")
        friction = _as_cell_array(self.darcy_friction_factor, grid.n_cells, "darcy_friction_factor")
        dzdx = _as_cell_array(self.dzdx, grid.n_cells, "dzdx")
        if np.any(diameter <= 0.0):
            raise ValueError("diameter_m must be positive")
        if np.any(friction < 0.0):
            raise ValueError("darcy_friction_factor must be non-negative")

        prim0 = eos.primitive_from_conserved(U)
        rho0 = prim0.rho
        u0 = prim0.u
        cell_volume = grid.dx * grid.geometry.area_m2

        gravity_energy_j = 0.0
        U_after_gravity = U.copy()
        if np.any(dzdx != 0.0):
            U_after_gravity[..., IDX_MOM] += dt * (-rho0 * self.gravity_m_s2 * dzdx)
            if self.include_gravity_energy_source:
                d_rhoE = dt * (-rho0 * u0 * self.gravity_m_s2 * dzdx)
                U_after_gravity[..., IDX_RHOE] += d_rhoE
                gravity_energy_j = float(np.sum(d_rhoE) * cell_volume)

        prim_g = eos.primitive_from_conserved(U_after_gravity)
        rho = prim_g.rho
        u_g = prim_g.u

        friction_coeff = friction / (2.0 * diameter)
        k = _loss_array(self.local_loss_k, t, grid)
        local_coeff = k / (2.0 * grid.dx)
        drag_coeff = friction_coeff + local_coeff

        if np.any(drag_coeff != 0.0):
            u_new = u_g / (1.0 + drag_coeff * np.abs(u_g) * dt)
            kinetic_loss_density = 0.5 * rho * (u_g**2 - u_new**2)
            # Roundoff can make tiny negative values when u is near zero.
            kinetic_loss_density = np.maximum(kinetic_loss_density, 0.0)
            drag_loss = float(np.sum(kinetic_loss_density) * cell_volume)
            share_friction = np.divide(
                friction_coeff,
                drag_coeff,
                out=np.zeros_like(drag_coeff, dtype=float),
                where=drag_coeff > 0.0,
            )
            share_local = np.divide(
                local_coeff,
                drag_coeff,
                out=np.zeros_like(drag_coeff, dtype=float),
                where=drag_coeff > 0.0,
            )
            friction_loss = float(np.sum(kinetic_loss_density * share_friction) * cell_volume)
            local_loss = float(np.sum(kinetic_loss_density * share_local) * cell_volume)
        else:
            drag_loss = 0.0
            friction_loss = 0.0
            local_loss = 0.0

        return {
            "gravity_energy_j": float(gravity_energy_j),
            "drag_dissipation_proxy_j": float(drag_loss),
            "friction_dissipation_proxy_j": float(friction_loss),
            "local_loss_dissipation_proxy_j": float(local_loss),
        }

    @classmethod
    def from_discretized_network(
        cls,
        discretized,
        *,
        gravity_m_s2: float = 9.80665,
        local_loss_k: float | np.ndarray | Callable[[float, np.ndarray], np.ndarray] = 0.0,
        include_gravity_energy_source: bool = True,
    ) -> "CellwisePipeSourceTerms":
        """Build source terms from a DiscretizedNetwork without importing it here."""

        return cls(
            diameter_m=discretized.cell_diameter_m,
            darcy_friction_factor=discretized.cell_darcy_friction_factor,
            gravity_m_s2=gravity_m_s2,
            dzdx=discretized.cell_dzdx,
            local_loss_k=local_loss_k,
            include_gravity_energy_source=include_gravity_energy_source,
        )


@dataclass(frozen=True)
class PipeSourceTerms:
    """Backward-compatible pipe source-term wrapper.

    This class keeps the Ver.0.2.0--0.2.3 constructor intact while delegating to
    the Ver.0.2.4 cell-wise implementation. Scalars therefore behave exactly as
    before, and arrays can now be supplied for verification.
    """

    geometry: PipeGeometry
    darcy_friction_factor: float | np.ndarray = 0.0
    gravity_m_s2: float = 9.80665
    dzdx: float | np.ndarray = 0.0
    local_loss_k: float | np.ndarray | Callable[[float, np.ndarray], np.ndarray] = 0.0
    include_gravity_energy_source: bool = True

    def __post_init__(self) -> None:
        if self.gravity_m_s2 < 0.0:
            raise ValueError("gravity_m_s2 must be non-negative")

    def apply(self, U: np.ndarray, grid: UniformGrid, eos: EOSModel, dt: float, t: float) -> np.ndarray:
        impl = CellwisePipeSourceTerms(
            diameter_m=self.geometry.diameter_m,
            darcy_friction_factor=self.darcy_friction_factor,
            gravity_m_s2=self.gravity_m_s2,
            dzdx=self.dzdx,
            local_loss_k=self.local_loss_k,
            include_gravity_energy_source=self.include_gravity_energy_source,
        )
        return impl.apply(U, grid, eos, dt, t)


@dataclass(frozen=True)
class ValveLossSchedule:
    """Time-dependent local loss coefficient for a closing valve.

    This object returns a K array concentrated around a specified valve cell.
    It is a simple Ver.0.2 representation of an ESD valve and should be
    replaced by a calibrated Cv/Kv model for design use.
    """

    valve_x_m: float
    k_open: float
    k_closed: float
    t_start_s: float
    t_close_s: float
    width_cells: int = 1

    def __post_init__(self) -> None:
        if self.k_open < 0.0 or self.k_closed < 0.0:
            raise ValueError("loss coefficients must be non-negative")
        if self.t_close_s <= 0.0:
            raise ValueError("t_close_s must be positive")
        if self.width_cells <= 0:
            raise ValueError("width_cells must be positive")

    def __call__(self, t: float, x: np.ndarray) -> np.ndarray:
        r = np.clip((t - self.t_start_s) / self.t_close_s, 0.0, 1.0)
        k_now = self.k_open + (self.k_closed - self.k_open) * r
        idx = int(np.argmin(np.abs(x - self.valve_x_m)))
        k = np.zeros_like(x)
        half = self.width_cells // 2
        lo = max(0, idx - half)
        hi = min(x.size, lo + self.width_cells)
        k[lo:hi] = k_now
        return k
