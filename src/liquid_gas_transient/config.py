"""Configuration dataclasses for the Ver.0.2 FVM solver."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PipeGeometry:
    """Equivalent 1-D pipe geometry.

    Parameters
    ----------
    length_m:
        Pipe length [m].
    diameter_m:
        Inner diameter [m].
    roughness_m:
        Absolute roughness [m]. Ver.0.2 does not yet compute friction
        factor from roughness, but the field is kept for future models.
    """

    length_m: float
    diameter_m: float
    roughness_m: float = 0.0

    def __post_init__(self) -> None:
        if self.length_m <= 0.0:
            raise ValueError("length_m must be positive")
        if self.diameter_m <= 0.0:
            raise ValueError("diameter_m must be positive")
        if self.roughness_m < 0.0:
            raise ValueError("roughness_m must be non-negative")

    @property
    def area_m2(self) -> float:
        return math.pi * self.diameter_m**2 / 4.0


@dataclass(frozen=True)
class NumericsConfig:
    """Numerical settings for Ver.0.2."""

    n_cells: int = 200
    n_ghost: int = 2
    cfl: float = 0.5

    def __post_init__(self) -> None:
        if self.n_cells <= 0:
            raise ValueError("n_cells must be positive")
        if self.n_ghost <= 0:
            raise ValueError("n_ghost must be positive")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")


@dataclass(frozen=True)
class TimeConfig:
    """Time integration limits."""

    t_end_s: float
    max_steps: int = 100_000

    def __post_init__(self) -> None:
        if self.t_end_s <= 0.0:
            raise ValueError("t_end_s must be positive")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
