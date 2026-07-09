"""HEM diagnostic utilities for Case C integration.

Ver.0.3.0 introduced a toy HEM flash operator. Ver.0.3.1 keeps the
thermodynamic model deliberately simple and adds case-level diagnostics that
are useful for abnormal-scenario screening:

* maximum vapor mass fraction x_v,
* maximum void fraction alpha,
* minimum mixture sound speed,
* vapor mass inventory,
* high-elevation two-phase flag.

These diagnostics are not a replacement for real-fluid LCO2 validation. They
are a verified software pathway for carrying two-phase indicators through the
Case C network.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .network import DiscretizedNetwork
from .solver import FvmSolver
from .state import IDX_RHO, IDX_RHO_XV, inventory


@dataclass(frozen=True)
class HEMDiagnosticsConfig:
    """Thresholds and spatial filters for HEM case diagnostics."""

    alpha_threshold: float = 1.0e-6
    xv_threshold: float = 1.0e-8
    high_elevation_min_m: float = 10.0

    def __post_init__(self) -> None:
        if self.alpha_threshold < 0.0:
            raise ValueError("alpha_threshold must be non-negative")
        if self.xv_threshold < 0.0:
            raise ValueError("xv_threshold must be non-negative")
        if not np.isfinite(self.high_elevation_min_m):
            raise ValueError("high_elevation_min_m must be finite")


def vapor_mass_inventory_kg(U: np.ndarray, dx: float, area_m2: float) -> float:
    """Return domain-integrated vapor mass inventory [kg]."""

    return float(np.sum(U[..., IDX_RHO_XV]) * dx * area_m2)


def two_phase_mask_from_primitive(prim, config: HEMDiagnosticsConfig) -> np.ndarray:
    """Return cells considered two-phase for diagnostics."""

    return (prim.alpha > config.alpha_threshold) | (prim.xv > config.xv_threshold)


def summarize_hem_state(
    solver: FvmSolver,
    discretized: DiscretizedNetwork,
    config: HEMDiagnosticsConfig | None = None,
    *,
    prefix: str = "hem_",
) -> dict[str, float]:
    """Return scalar HEM diagnostics for a solver/discretized Case C state.

    The returned values are intentionally scalar and CSV-friendly so they can be
    merged directly into time-history diagnostics.
    """

    cfg = config or HEMDiagnosticsConfig()
    prim = solver.primitive()
    inv = inventory(solver.U, solver.grid.dx, solver.grid.geometry.area_m2)
    vapor_mass = vapor_mass_inventory_kg(solver.U, solver.grid.dx, solver.grid.geometry.area_m2)
    total_mass = max(inv["mass_total"], 1.0e-300)

    two_phase = two_phase_mask_from_primitive(prim, cfg)
    high = discretized.cell_elevation_m >= cfg.high_elevation_min_m
    high_two_phase = two_phase & high
    dx = solver.grid.dx

    def safe_max(values: np.ndarray, mask: np.ndarray, default: float = 0.0) -> float:
        if not np.any(mask):
            return float(default)
        return float(np.max(values[mask]))

    def safe_min(values: np.ndarray, mask: np.ndarray, default: float = 0.0) -> float:
        if not np.any(mask):
            return float(default)
        return float(np.min(values[mask]))

    high_cell_count = int(np.count_nonzero(high))
    two_phase_count = int(np.count_nonzero(two_phase))
    high_two_phase_count = int(np.count_nonzero(high_two_phase))

    out = {
        "xv_max": float(np.max(prim.xv)),
        "alpha_max": float(np.max(prim.alpha)),
        "c_min_m_s": float(np.min(prim.c)),
        "vapor_mass_inventory_kg": vapor_mass,
        "vapor_mass_fraction_inventory": float(vapor_mass / total_mass),
        "two_phase_cell_count": float(two_phase_count),
        "two_phase_length_m": float(two_phase_count * dx),
        "two_phase_present": float(two_phase_count > 0),
        "high_elevation_min_m": float(cfg.high_elevation_min_m),
        "high_elevation_cell_count": float(high_cell_count),
        "high_elevation_xv_max": safe_max(prim.xv, high),
        "high_elevation_alpha_max": safe_max(prim.alpha, high),
        "high_elevation_c_min_m_s": safe_min(prim.c, high, default=float(np.min(prim.c))),
        "high_elevation_two_phase_cell_count": float(high_two_phase_count),
        "high_elevation_two_phase_length_m": float(high_two_phase_count * dx),
        "high_elevation_two_phase_flag": float(high_two_phase_count > 0),
    }
    return {prefix + key: value for key, value in out.items()}


def hem_profile_table(solver: FvmSolver, discretized: DiscretizedNetwork) -> dict[str, np.ndarray]:
    """Return cell-wise HEM profile arrays for plotting or CSV output."""

    prim = solver.primitive()
    return {
        "x_m": solver.grid.cell_centers.copy(),
        "elevation_m": discretized.cell_elevation_m.copy(),
        "rho_kg_m3": prim.rho.copy(),
        "p_pa": prim.p.copy(),
        "u_m_s": prim.u.copy(),
        "xv": prim.xv.copy(),
        "alpha": prim.alpha.copy(),
        "c_m_s": prim.c.copy(),
        "segment": np.array(discretized.cell_segment_names, dtype=object),
    }
