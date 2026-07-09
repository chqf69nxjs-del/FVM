"""Valve laws and opening schedules for boundary valve models.

Ver.0.2.1 keeps valve physics deliberately simple and verification-oriented:

- incompressible liquid Kv law for open-valve flow,
- a deterministic opening schedule,
- no choked two-phase discharge yet,
- no cavitation/flashing at the valve yet.

The purpose is to make ESD valve closure act as a true hydraulic boundary
instead of an artificial large local-loss coefficient inside one cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import numpy as np


class OpeningSchedule(Protocol):
    """Opening schedule interface returning a valve opening fraction in [0, 1]."""

    def opening(self, t: float) -> float:
        """Return valve opening fraction at time t."""


@dataclass(frozen=True)
class ConstantOpening:
    """Constant valve opening fraction."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("opening value must be in [0, 1]")

    def opening(self, t: float) -> float:
        return float(self.value)


@dataclass(frozen=True)
class LinearRampOpening:
    """Linear opening ramp from open_initial to open_final.

    For ESD closure, use open_initial=1 and open_final=0.
    """

    t_start_s: float
    duration_s: float
    open_initial: float = 1.0
    open_final: float = 0.0

    def __post_init__(self) -> None:
        if self.duration_s < 0.0:
            raise ValueError("duration_s must be non-negative")
        if not 0.0 <= self.open_initial <= 1.0:
            raise ValueError("open_initial must be in [0, 1]")
        if not 0.0 <= self.open_final <= 1.0:
            raise ValueError("open_final must be in [0, 1]")

    def opening(self, t: float) -> float:
        if self.duration_s == 0.0:
            return float(self.open_final if t >= self.t_start_s else self.open_initial)
        r = np.clip((t - self.t_start_s) / self.duration_s, 0.0, 1.0)
        return float(self.open_initial + (self.open_final - self.open_initial) * r)


@dataclass(frozen=True)
class KvLiquidValve:
    """Liquid valve law using industrial Kv units.

    Kv convention used here:

        Q[m3/h] = Kv * sqrt(DeltaP[bar] / SG)

    where SG = rho / 1000 for liquid. The SI flow rate returned by this class is
    Q[m3/s]. This is a single-phase liquid relation and should not be used as a
    two-phase relief/vent model.
    """

    kv_m3_per_h: float
    allow_reverse_flow: bool = False
    min_pressure_drop_pa: float = 0.0

    def __post_init__(self) -> None:
        if self.kv_m3_per_h < 0.0:
            raise ValueError("kv_m3_per_h must be non-negative")
        if self.min_pressure_drop_pa < 0.0:
            raise ValueError("min_pressure_drop_pa must be non-negative")

    @classmethod
    def from_cv_us(cls, cv_us_gpm: float, *, allow_reverse_flow: bool = False) -> "KvLiquidValve":
        """Build from US Cv using the common approximation Kv ~= 0.865 Cv."""

        if cv_us_gpm < 0.0:
            raise ValueError("cv_us_gpm must be non-negative")
        return cls(kv_m3_per_h=0.865 * cv_us_gpm, allow_reverse_flow=allow_reverse_flow)

    def flow_rate_m3_s(
        self,
        *,
        p_up_pa: float,
        p_down_pa: float,
        rho_kg_m3: float,
        opening: float,
    ) -> float:
        """Return valve volumetric flow rate [m3/s].

        Positive flow is from upstream to downstream. If reverse flow is not
        allowed, negative pressure drop gives zero flow.
        """

        if rho_kg_m3 <= 0.0:
            raise ValueError("rho_kg_m3 must be positive")
        if not 0.0 <= opening <= 1.0:
            raise ValueError("opening must be in [0, 1]")
        if self.kv_m3_per_h == 0.0 or opening == 0.0:
            return 0.0

        dp = float(p_up_pa - p_down_pa)
        if abs(dp) < self.min_pressure_drop_pa:
            return 0.0
        if dp <= 0.0 and not self.allow_reverse_flow:
            return 0.0

        sign = 1.0 if dp >= 0.0 else -1.0
        dp_bar = abs(dp) / 1.0e5
        specific_gravity = rho_kg_m3 / 1000.0
        q_m3_h = opening * self.kv_m3_per_h * np.sqrt(dp_bar / specific_gravity)
        return float(sign * q_m3_h / 3600.0)

    @staticmethod
    def kv_for_target_flow(
        *,
        q_m3_s: float,
        delta_p_pa: float,
        rho_kg_m3: float,
        opening: float = 1.0,
    ) -> float:
        """Return Kv [m3/h] that gives a target liquid flow at given dp and rho."""

        if q_m3_s < 0.0:
            raise ValueError("q_m3_s must be non-negative")
        if delta_p_pa <= 0.0:
            raise ValueError("delta_p_pa must be positive")
        if rho_kg_m3 <= 0.0:
            raise ValueError("rho_kg_m3 must be positive")
        if not 0.0 < opening <= 1.0:
            raise ValueError("opening must be in (0, 1]")
        dp_bar = delta_p_pa / 1.0e5
        specific_gravity = rho_kg_m3 / 1000.0
        return float((q_m3_s * 3600.0 / opening) / np.sqrt(dp_bar / specific_gravity))
