"""Conservative finite-volume solver core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
import numpy as np

from .boundary import BoundaryCondition, TransmissiveBoundary
from .budget import BoundaryBudgetTracker
from .energy_budget import EnergySourceBudgetTracker
from .eos import EOSModel
from .flux import rusanov_flux
from .interfaces import InternalInterface
from .interface_budget import InterfaceEnergyBudgetTracker
from .grid import UniformGrid
from .phase_change import NoPhaseChange, PhaseChangeModel
from .phase_budget import PhaseChangeBudgetTracker
from .source_terms import NoSource, SourceTerm
from .state import IDX_RHO, IDX_MOM, IDX_RHOE, IDX_RHO_XV, N_VARS, check_physical_state, inventory

FluxFunction = Callable[[np.ndarray, np.ndarray, EOSModel], np.ndarray]


@dataclass
class FvmSolver:
    """First-order conservative FVM solver for Ver.0.2.

    Parameters
    ----------
    grid:
        Uniform 1-D finite-volume grid.
    eos:
        Equation-of-state model.
    U:
        Conservative state array of shape (n_cells, 4).
    cfl:
        CFL number.
    n_ghost:
        Number of ghost cells at each boundary.
    left_boundary, right_boundary:
        Boundary condition models.
    source_term:
        Operator-split source-term model.
    phase_change:
        Operator-split phase-change model.
    flux_function:
        Numerical flux function. Defaults to Rusanov.
    """

    grid: UniformGrid
    eos: EOSModel
    U: np.ndarray
    cfl: float = 0.5
    n_ghost: int = 2
    left_boundary: BoundaryCondition = field(default_factory=TransmissiveBoundary)
    right_boundary: BoundaryCondition = field(default_factory=TransmissiveBoundary)
    source_term: SourceTerm = field(default_factory=NoSource)
    phase_change: PhaseChangeModel = field(default_factory=NoPhaseChange)
    flux_function: FluxFunction = rusanov_flux
    internal_interfaces: tuple[InternalInterface, ...] = ()
    enable_boundary_budget: bool = True
    enable_phase_budget: bool = True
    enable_energy_budget: bool = True
    enable_interface_budget: bool = True
    latent_heat_placeholder_j_kg: float = 0.0
    boundary_budget: BoundaryBudgetTracker | None = field(init=False, default=None)
    phase_budget: PhaseChangeBudgetTracker | None = field(init=False, default=None)
    energy_budget: EnergySourceBudgetTracker | None = field(init=False, default=None)
    interface_budget: InterfaceEnergyBudgetTracker | None = field(init=False, default=None)
    t: float = 0.0
    step_count: int = 0

    def __post_init__(self) -> None:
        if self.U.shape != (self.grid.n_cells, N_VARS):
            raise ValueError(f"U must have shape ({self.grid.n_cells}, {N_VARS})")
        if self.n_ghost <= 0:
            raise ValueError("n_ghost must be positive")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        self.U = np.array(self.U, dtype=float, copy=True)
        check_physical_state(self.U, names=["initial U"])
        initial_inv = inventory(self.U, self.grid.dx, self.grid.geometry.area_m2)
        if self.enable_boundary_budget:
            self.boundary_budget = BoundaryBudgetTracker(
                initial_inventory=initial_inv,
                area_m2=self.grid.geometry.area_m2,
            )
        if self.enable_phase_budget:
            self.phase_budget = PhaseChangeBudgetTracker(initial_inventory=initial_inv)
        if self.enable_energy_budget:
            self.energy_budget = EnergySourceBudgetTracker(
                initial_inventory=initial_inv,
                latent_heat_j_per_kg=self.latent_heat_placeholder_j_kg,
            )
        if self.enable_interface_budget:
            self.interface_budget = InterfaceEnergyBudgetTracker()

    def primitive(self):
        """Return primitive state for current internal cells."""

        return self.eos.primitive_from_conserved(self.U)

    def compute_dt(self, t_end: float | None = None) -> float:
        """Compute stable explicit time step from CFL condition."""

        prim = self.primitive()
        wave_speed = np.abs(prim.u) + prim.c
        max_speed = float(np.max(wave_speed))
        if max_speed <= 0.0 or not np.isfinite(max_speed):
            raise ValueError("invalid maximum wave speed")
        dt = self.cfl * self.grid.dx / max_speed
        if t_end is not None:
            dt = min(dt, max(t_end - self.t, 0.0))
        return dt

    def extend_with_ghosts(self, t: float) -> np.ndarray:
        """Return state extended with ghost cells."""

        U_ext = np.empty((self.grid.n_cells + 2 * self.n_ghost, N_VARS), dtype=float)
        U_ext[self.n_ghost : -self.n_ghost] = self.U
        self.left_boundary.apply(U_ext, self.n_ghost, "left", t, self.eos)
        self.right_boundary.apply(U_ext, self.n_ghost, "right", t, self.eos)
        check_physical_state(U_ext, names=["U with ghost cells"])
        return U_ext

    def step(self, dt: float | None = None) -> float:
        """Advance one time step and return the actual dt used."""

        if dt is None:
            dt = self.compute_dt()
        if dt <= 0.0:
            raise ValueError("dt must be positive")

        check_physical_state(self.U, names=["pre-step U"])

        # 1. Boundary and interface fluxes.
        U_ext = self.extend_with_ghosts(self.t)
        U_left = U_ext[:-1]
        U_right = U_ext[1:]
        flux = self.flux_function(U_left, U_right, self.eos)

        # Flux interfaces adjacent to internal cells.
        i0 = self.n_ghost
        i1 = self.n_ghost + self.grid.n_cells
        flux_left = flux[i0 - 1 : i1 - 1].copy()
        flux_right = flux[i0:i1].copy()

        for interface in self.internal_interfaces:
            interface.apply(
                flux_left=flux_left,
                flux_right=flux_right,
                U=self.U,
                eos=self.eos,
                t=self.t,
                flux_function=self.flux_function,
            )

        if self.boundary_budget is not None:
            self.boundary_budget.record_external_fluxes(
                left_flux=flux_left[0],
                right_flux=flux_right[-1],
                dt=dt,
            )
        if self.interface_budget is not None:
            self.interface_budget.record_step(
                left_boundary=self.left_boundary,
                right_boundary=self.right_boundary,
                left_flux=flux_left[0],
                right_flux=flux_right[-1],
                internal_interfaces=self.internal_interfaces,
                U=self.U,
                eos=self.eos,
                area_m2=self.grid.geometry.area_m2,
                dt=dt,
                t=self.t,
            )

        U_new = self.U - (dt / self.grid.dx) * (flux_right - flux_left)
        check_physical_state(U_new, names=["after FVM update"])

        # 2. Operator-split source terms.
        U_before_source = U_new.copy()
        source_energy_terms = None
        if hasattr(self.source_term, "energy_budget_terms"):
            source_energy_terms = self.source_term.energy_budget_terms(  # type: ignore[attr-defined]
                U_before_source, self.grid, self.eos, dt, self.t
            )
        U_new = self.source_term.apply(U_new, self.grid, self.eos, dt, self.t)
        if self.energy_budget is not None:
            self.energy_budget.record_source_step(
                U_before=U_before_source,
                U_after=U_new,
                dx=self.grid.dx,
                area_m2=self.grid.geometry.area_m2,
                dt=dt,
                source_terms=source_energy_terms,
            )
        check_physical_state(U_new, names=["after source update"])

        # 3. Operator-split phase change.
        U_before_phase = U_new.copy()
        U_new = self.phase_change.apply(U_new, self.eos, dt, self.t)
        phase_vapor_source_kg = 0.0
        if self.phase_budget is not None:
            self.phase_budget.record_phase_change(
                U_before=U_before_phase,
                U_after=U_new,
                dx=self.grid.dx,
                area_m2=self.grid.geometry.area_m2,
                dt=dt,
            )
            phase_vapor_source_kg = self.phase_budget.last_source_kg
        if self.energy_budget is not None:
            self.energy_budget.record_phase_change(
                U_before=U_before_phase,
                U_after=U_new,
                dx=self.grid.dx,
                area_m2=self.grid.geometry.area_m2,
                dt=dt,
                vapor_mass_source_kg=phase_vapor_source_kg,
            )
        check_physical_state(U_new, names=["after phase-change update"])

        self.U = U_new
        self.t += dt
        self.step_count += 1
        return dt

    def run(self, t_end: float, max_steps: int = 100_000, *, sample_every: int = 1) -> list[dict[str, float]]:
        """Run until t_end and return diagnostic history."""

        if t_end <= self.t:
            raise ValueError("t_end must be greater than current solver time")
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if sample_every <= 0:
            raise ValueError("sample_every must be positive")

        history: list[dict[str, float]] = [self.diagnostics(dt=0.0)]
        for _ in range(max_steps):
            if self.t >= t_end:
                break
            dt = self.compute_dt(t_end)
            if dt <= 0.0:
                break
            self.step(dt)
            if self.step_count % sample_every == 0 or self.t >= t_end:
                history.append(self.diagnostics(dt=dt))
        else:
            raise RuntimeError("max_steps reached before t_end")
        return history

    def diagnostics(self, dt: float) -> dict[str, float]:
        """Return scalar diagnostics for the current state."""

        prim = self.primitive()
        inv = inventory(self.U, self.grid.dx, self.grid.geometry.area_m2)
        cfl_max = float(np.max((np.abs(prim.u) + prim.c) * dt / self.grid.dx)) if dt > 0 else 0.0
        data = {
            "time_s": float(self.t),
            "step": float(self.step_count),
            "dt_s": float(dt),
            "cfl_max": cfl_max,
            **inv,
            "p_min_pa": float(np.min(prim.p)),
            "p_max_pa": float(np.max(prim.p)),
            "rho_min_kg_m3": float(np.min(prim.rho)),
            "rho_max_kg_m3": float(np.max(prim.rho)),
            "xv_min": float(np.min(prim.xv)),
            "xv_max": float(np.max(prim.xv)),
            "alpha_min": float(np.min(prim.alpha)),
            "alpha_max": float(np.max(prim.alpha)),
            "c_min_m_s": float(np.min(prim.c)),
            "c_max_m_s": float(np.max(prim.c)),
            "u_min_m_s": float(np.min(prim.u)),
            "u_max_m_s": float(np.max(prim.u)),
        }
        if self.boundary_budget is not None:
            data.update(self.boundary_budget.diagnostics(inv))
        if self.phase_budget is not None:
            data.update(self.phase_budget.diagnostics(inv, boundary_budget=self.boundary_budget))
        if self.energy_budget is not None:
            data.update(self.energy_budget.diagnostics(inv, boundary_budget=self.boundary_budget))
        if self.interface_budget is not None:
            data.update(self.interface_budget.diagnostics())
        return data
