"""Working Tool W0 public case schema."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from ..config import NumericsConfig, PipeGeometry, TimeConfig


CASE_SCHEMA_VERSION = "stage7_u3_b2_a1_working_tool_case_v0"


class ModelProfile(str, Enum):
    """Explicitly supported Working Tool model profiles."""

    STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0 = (
        "STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0"
    )


@dataclass(frozen=True)
class InitialCondition:
    """Normal-user initial pressure, temperature, and velocity input."""

    pressure_pa: float
    temperature_k: float
    velocity_m_s: float = 0.0

    def __post_init__(self) -> None:
        values = (self.pressure_pa, self.temperature_k, self.velocity_m_s)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("initial-condition values must be finite")
        if self.pressure_pa <= 0.0:
            raise ValueError("pressure_pa must be positive")
        if self.temperature_k <= 0.0:
            raise ValueError("temperature_k must be positive")


@dataclass(frozen=True)
class OutletCondition:
    """Current single-phase B2 outward-discharge user input."""

    back_pressure_pa: float
    opening_fraction: float
    discharge_coefficient: float

    def __post_init__(self) -> None:
        values = (
            self.back_pressure_pa,
            self.opening_fraction,
            self.discharge_coefficient,
        )
        if not all(np.isfinite(value) for value in values):
            raise ValueError("outlet-condition values must be finite")
        if self.back_pressure_pa <= 0.0:
            raise ValueError("back_pressure_pa must be positive")
        if not 0.0 <= self.opening_fraction <= 1.0:
            raise ValueError("opening_fraction must be in [0, 1]")
        if self.discharge_coefficient <= 0.0:
            raise ValueError("discharge_coefficient must be positive")


@dataclass(frozen=True)
class WorkingToolCase:
    """Public W0 case contract for the narrow provisional single-phase path."""

    case_id: str
    geometry: PipeGeometry
    numerics: NumericsConfig
    time: TimeConfig
    initial: InitialCondition
    outlet: OutletCondition
    fluid: str = "CO2"
    model_profile: ModelProfile = (
        ModelProfile.STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0
    )
    schema_version: str = CASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.case_id or not self.case_id.strip():
            raise ValueError("case_id must be non-empty")
        if self.schema_version != CASE_SCHEMA_VERSION:
            raise ValueError(f"unsupported case schema_version: {self.schema_version}")
        if self.fluid != "CO2":
            raise ValueError("W0 supports fluid='CO2' only")
        if self.model_profile is not ModelProfile.STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0:
            raise ValueError(f"unsupported model_profile: {self.model_profile!r}")
        if not isinstance(self.geometry, PipeGeometry):
            raise TypeError("geometry must be PipeGeometry")
        if not isinstance(self.numerics, NumericsConfig):
            raise TypeError("numerics must be NumericsConfig")
        if not isinstance(self.time, TimeConfig):
            raise TypeError("time must be TimeConfig")
        if not isinstance(self.initial, InitialCondition):
            raise TypeError("initial must be InitialCondition")
        if not isinstance(self.outlet, OutletCondition):
            raise TypeError("outlet must be OutletCondition")

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "fluid": self.fluid,
            "model_profile": self.model_profile.value,
            "geometry": {
                "length_m": self.geometry.length_m,
                "diameter_m": self.geometry.diameter_m,
                "roughness_m": self.geometry.roughness_m,
            },
            "numerics": {
                "n_cells": self.numerics.n_cells,
                "n_ghost": self.numerics.n_ghost,
                "cfl": self.numerics.cfl,
            },
            "time": {
                "t_end_s": self.time.t_end_s,
                "max_steps": self.time.max_steps,
            },
            "initial": {
                "pressure_pa": self.initial.pressure_pa,
                "temperature_k": self.initial.temperature_k,
                "velocity_m_s": self.initial.velocity_m_s,
            },
            "outlet": {
                "back_pressure_pa": self.outlet.back_pressure_pa,
                "opening_fraction": self.outlet.opening_fraction,
                "discharge_coefficient": self.outlet.discharge_coefficient,
            },
        }
