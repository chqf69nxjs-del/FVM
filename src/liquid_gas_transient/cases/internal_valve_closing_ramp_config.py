"""Configuration helpers for V-012D controlled internal-valve closing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CoolPropInternalValveClosingRampConfig:
    """Numerical-observation inputs for the primary 1 -> 0 closing ramp."""

    case_name: str = "coolprop_internal_valve_closing_ramp"
    output_version: str = "coolprop_internal_valve_closing_ramp_v1"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    n_cells: int = 100
    cfl: float = 0.5
    left_pressure_pa: float = 8_000_500.0
    right_pressure_pa: float = 7_999_500.0
    initial_temperature_K: float = 280.0
    open_initial: float = 1.0
    open_final: float = 0.0
    ramp_start_s: float = 0.005
    ramp_duration_s: float = 0.010
    post_closure_hold_s: float = 0.005
    calibration_delta_p_pa: float = 1.0e3
    target_full_open_face_velocity_m_s: float = 1.0e-3
    max_mach: float = 0.8
    probe_fractions: tuple[float, ...] = (0.25, 0.375, 0.625, 0.75)
    post_probe_margin_fraction: float = 0.05
    boundary_arrival_safety_fraction: float = 0.85
    t_end_s: float | None = None
    sample_every: int = 1
    field_sample_every: int = 1
    max_steps: int = 20_000
    relative_budget_tolerance: float = 1.0e-10
    flow_relative_tolerance: float = 1.0e-12

    def __post_init__(self) -> None:
        if self.pipe_length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.n_cells < 10 or self.n_cells % 2:
            raise ValueError("n_cells must be an even integer of at least 10")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.left_pressure_pa <= self.right_pressure_pa:
            raise ValueError("left_pressure_pa must exceed right_pressure_pa")
        if self.right_pressure_pa <= 0.0 or self.initial_temperature_K <= 0.0:
            raise ValueError("pressures and temperature must be positive")
        if not 0.0 <= self.open_final < self.open_initial <= 1.0:
            raise ValueError("closing ramp must satisfy 0 <= final < initial <= 1")
        if self.ramp_start_s < 0.0:
            raise ValueError("ramp_start_s must be non-negative")
        if self.ramp_duration_s <= 0.0:
            raise ValueError("ramp_duration_s must be positive")
        if self.post_closure_hold_s <= 0.0:
            raise ValueError("post_closure_hold_s must be positive")
        if self.calibration_delta_p_pa <= 0.0:
            raise ValueError("calibration_delta_p_pa must be positive")
        if self.target_full_open_face_velocity_m_s <= 0.0:
            raise ValueError("target_full_open_face_velocity_m_s must be positive")
        if not 0.0 < self.max_mach <= 1.0:
            raise ValueError("max_mach must be in (0, 1]")
        if not self.probe_fractions or any(
            not 0.0 < value < 1.0 for value in self.probe_fractions
        ):
            raise ValueError("probe_fractions must lie in (0, 1)")
        if tuple(sorted(set(self.probe_fractions))) != self.probe_fractions:
            raise ValueError("probe_fractions must be unique and ascending")
        if not any(value < 0.5 for value in self.probe_fractions):
            raise ValueError("at least one upstream probe is required")
        if not any(value > 0.5 for value in self.probe_fractions):
            raise ValueError("at least one downstream probe is required")
        if self.post_probe_margin_fraction <= 0.0:
            raise ValueError("post_probe_margin_fraction must be positive")
        if not 0.0 < self.boundary_arrival_safety_fraction < 1.0:
            raise ValueError("boundary_arrival_safety_fraction must lie in (0, 1)")
        if self.t_end_s is not None and self.t_end_s < self.minimum_post_closure_end_s:
            raise ValueError("t_end_s must include the configured post-closure hold")
        if self.sample_every <= 0 or self.field_sample_every <= 0:
            raise ValueError("sample intervals must be positive")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.relative_budget_tolerance <= 0.0:
            raise ValueError("relative_budget_tolerance must be positive")
        if self.flow_relative_tolerance <= 0.0:
            raise ValueError("flow_relative_tolerance must be positive")

    @property
    def initial_delta_p_pa(self) -> float:
        return float(self.left_pressure_pa - self.right_pressure_pa)

    @property
    def ramp_end_s(self) -> float:
        return float(self.ramp_start_s + self.ramp_duration_s)

    @property
    def minimum_post_closure_end_s(self) -> float:
        return float(self.ramp_end_s + self.post_closure_hold_s)


def opening_roundoff_tolerance(
    config: CoolPropInternalValveClosingRampConfig,
) -> float:
    """Return an 8-ULP schedule-tracking tolerance."""

    scale = max(abs(config.open_initial), abs(config.open_final), 1.0)
    return float(8.0 * np.spacing(scale))
