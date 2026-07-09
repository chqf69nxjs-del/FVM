"""Grid definitions."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .config import PipeGeometry


@dataclass(frozen=True)
class UniformGrid:
    """Uniform finite-volume grid for a 1-D equivalent pipe."""

    geometry: PipeGeometry
    n_cells: int

    def __post_init__(self) -> None:
        if self.n_cells <= 0:
            raise ValueError("n_cells must be positive")

    @property
    def dx(self) -> float:
        return self.geometry.length_m / self.n_cells

    @property
    def cell_centers(self) -> np.ndarray:
        return (np.arange(self.n_cells, dtype=float) + 0.5) * self.dx

    @property
    def face_positions(self) -> np.ndarray:
        return np.arange(self.n_cells + 1, dtype=float) * self.dx
