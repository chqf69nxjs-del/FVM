"""Ver.0.3.0 HEM flash demonstration case.

A closed one-dimensional pipe is initialized with a local density depression.
The toy HEM EOS converts that low-density region into equilibrium vapor mass
fraction and void fraction. This case is not intended to represent a full LCO2
system; it verifies the software path for HEM flashing.
"""

from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path

import numpy as np

from ..boundary import ReflectiveBoundary
from ..config import PipeGeometry
from ..eos import ToyHEMEOS
from ..grid import UniformGrid
from ..phase_change import HEMPhaseChange
from ..solver import FvmSolver
from ..state import make_conserved


@dataclass(frozen=True)
class HEMFlashCaseParameters:
    """Parameters for the HEM flash verification/demo case."""

    length_m: float = 100.0
    diameter_m: float = 0.25
    n_cells: int = 200
    t_end_s: float = 0.02
    cfl: float = 0.25
    rho_l_sat_kg_m3: float = 930.0
    rho_v_sat_kg_m3: float = 40.0
    p_sat_pa: float = 1.9e6
    initial_internal_energy_j_kg: float = 1.0e5
    flash_region_xv_equivalent: float = 0.08
    flash_region_fraction: float = 0.15


def density_for_equilibrium_xv(rho_l: float, rho_v: float, xv: float) -> float:
    """Return mixture density satisfying the saturated specific-volume law."""

    x = float(np.clip(xv, 0.0, 1.0))
    return 1.0 / ((1.0 - x) / rho_l + x / rho_v)


def build_hem_flash_solver(params: HEMFlashCaseParameters = HEMFlashCaseParameters()) -> FvmSolver:
    """Build a closed-pipe HEM flash verification solver."""

    geometry = PipeGeometry(length_m=params.length_m, diameter_m=params.diameter_m)
    grid = UniformGrid(geometry=geometry, n_cells=params.n_cells)
    eos = ToyHEMEOS(
        rho_l_sat=params.rho_l_sat_kg_m3,
        rho_v_sat=params.rho_v_sat_kg_m3,
        p_sat=params.p_sat_pa,
    )
    rho = np.full(grid.n_cells, params.rho_l_sat_kg_m3, dtype=float)
    low_density = density_for_equilibrium_xv(
        params.rho_l_sat_kg_m3,
        params.rho_v_sat_kg_m3,
        params.flash_region_xv_equivalent,
    )
    x_center = grid.cell_centers
    half_width = 0.5 * params.flash_region_fraction * params.length_m
    mask = np.abs(x_center - 0.5 * params.length_m) <= half_width
    rho[mask] = low_density

    U = make_conserved(
        rho=rho,
        u=np.zeros(grid.n_cells),
        e=np.full(grid.n_cells, params.initial_internal_energy_j_kg),
        xv=np.zeros(grid.n_cells),
    )
    return FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=params.cfl,
        left_boundary=ReflectiveBoundary(),
        right_boundary=ReflectiveBoundary(),
        phase_change=HEMPhaseChange(),
    )


def write_profile_csv(solver: FvmSolver, path: str | Path) -> None:
    """Write current HEM flash profile for inspection."""

    prim = solver.primitive()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x_m", "rho_kg_m3", "p_pa", "u_m_s", "xv", "alpha", "c_m_s"])
        for row in zip(
            solver.grid.cell_centers,
            prim.rho,
            prim.p,
            prim.u,
            prim.xv,
            prim.alpha,
            prim.c,
        ):
            writer.writerow([float(v) for v in row])


if __name__ == "__main__":
    params = HEMFlashCaseParameters()
    solver = build_hem_flash_solver(params)
    history = solver.run(params.t_end_s, sample_every=10)
    print(history[-1])
