"""Pure V-013B rigid-wall reflection specification and run-plan helpers.

This module fixes the Stage 7 / V-013B observation contract before the production
FVM path is connected. It deliberately imports no production solver, numerical
flux, boundary class, CoolProp package, or existing FVM case runner.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from numbers import Integral
from typing import Any, Literal


ReflectionPhase = Literal["incident", "wall_contact", "reflected"]


@dataclass(frozen=True)
class V013RigidWallReflectionConfig:
    """Fixed observation configuration for Stage 7 / V-013B."""

    case_name: str = "v013b_rigid_wall_reflection"
    output_version: str = "v013b_rigid_wall_reflection_v1"
    matched_sample_schema_version: str = "v013b_matched_samples_v1"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_amplitude_pa: float = 100.0
    pulse_center_fraction: float = 0.65
    pulse_sigma_fraction: float = 0.02
    probe_fractions: tuple[float, ...] = (0.75, 0.85, 0.90)
    fvm_mesh_cells: tuple[int, ...] = (100, 200, 400)
    fvm_cfl: float = 0.5
    moc_cfl: float = 1.0
    matched_path_travel_m: tuple[float, ...] = (
        0.0,
        15.0,
        25.0,
        35.0,
        45.0,
        55.0,
        65.0,
    )
    window_half_width_sigma: float = 2.0
    boundary_guard_sigma: float = 5.0
    max_steps: int = 30000
    validation: bool = False
    design_evaluation: bool = False
    acceptance_gate: bool = False

    def __post_init__(self) -> None:
        if not self.case_name or not self.output_version:
            raise ValueError("case_name and output_version must not be empty")
        if not self.matched_sample_schema_version:
            raise ValueError("matched_sample_schema_version must not be empty")
        for name, value in (
            ("pipe_length_m", self.pipe_length_m),
            ("diameter_m", self.diameter_m),
            ("initial_pressure_pa", self.initial_pressure_pa),
            ("initial_temperature_K", self.initial_temperature_K),
            ("pressure_amplitude_pa", self.pressure_amplitude_pa),
            ("pulse_sigma_fraction", self.pulse_sigma_fraction),
            ("window_half_width_sigma", self.window_half_width_sigma),
            ("boundary_guard_sigma", self.boundary_guard_sigma),
        ):
            _positive_finite(value, name)
        if self.pressure_amplitude_pa / self.initial_pressure_pa > 1.0e-4:
            raise ValueError(
                "V-013B pressure perturbation must remain in the linear guardrail"
            )
        if not 0.0 < self.pulse_center_fraction < 1.0:
            raise ValueError("pulse_center_fraction must be in (0, 1)")
        if tuple(sorted(set(self.probe_fractions))) != self.probe_fractions:
            raise ValueError("probe_fractions must be unique and ascending")
        if not self.probe_fractions or any(
            fraction <= self.pulse_center_fraction or fraction >= 1.0
            for fraction in self.probe_fractions
        ):
            raise ValueError(
                "probe fractions must lie right of the pulse center and inside the pipe"
            )
        if tuple(sorted(set(self.fvm_mesh_cells))) != self.fvm_mesh_cells:
            raise ValueError("fvm_mesh_cells must be unique and ascending")
        if any(
            isinstance(n, bool) or not isinstance(n, Integral) or int(n) < 20
            for n in self.fvm_mesh_cells
        ):
            raise ValueError(
                "each FVM mesh must be an integer with at least 20 cells"
            )
        if not 0.0 < self.fvm_cfl <= 1.0:
            raise ValueError("fvm_cfl must be in (0, 1]")
        if self.moc_cfl != 1.0:
            raise ValueError("the independent nodal MOC translator is fixed at CFL=1")
        if tuple(sorted(set(self.matched_path_travel_m))) != self.matched_path_travel_m:
            raise ValueError("matched_path_travel_m must be unique and ascending")
        if not self.matched_path_travel_m or self.matched_path_travel_m[0] != 0.0:
            raise ValueError("matched_path_travel_m must start at zero")
        if not any(
            math.isclose(distance, self.wall_path_travel_m, abs_tol=1.0e-10)
            for distance in self.matched_path_travel_m
        ):
            raise ValueError(
                "matched_path_travel_m must include the rigid-wall contact distance"
            )
        if self.matched_path_travel_m[-1] <= self.wall_path_travel_m:
            raise ValueError(
                "matched_path_travel_m must include at least one reflected-wave sample"
            )
        if (
            isinstance(self.max_steps, bool)
            or not isinstance(self.max_steps, Integral)
            or int(self.max_steps) <= 0
        ):
            raise ValueError("max_steps must be a positive integer")
        if self.validation or self.design_evaluation or self.acceptance_gate:
            raise ValueError("V-013B validation/design/acceptance flags must remain false")

        guard_m = self.boundary_guard_sigma * self.pulse_sigma_m
        if self.pipe_length_m - self.pulse_center_m <= guard_m:
            raise ValueError("the initial Gaussian is too close to the rigid wall")

        closest_probe_to_wall_m = self.pipe_length_m * max(self.probe_fractions)
        minimum_event_separation_m = self.pipe_length_m - closest_probe_to_wall_m
        required_separation_m = (
            2.0 * self.window_half_width_sigma * self.pulse_sigma_m
        )
        if minimum_event_separation_m <= required_separation_m:
            raise ValueError(
                "probe event windows must have a strictly positive separation"
            )

        for distance in self.matched_path_travel_m:
            state = _path_state_unchecked(distance, self)
            phase = state["phase"]
            center_m = float(state["expected_center_x_m"])
            if (
                phase == "incident"
                and center_m + guard_m > self.pipe_length_m + 1.0e-12
            ):
                raise ValueError(
                    "an incident matched sample enters the primary-wall guard envelope"
                )
            if phase == "reflected":
                if center_m + guard_m > self.pipe_length_m + 1.0e-12:
                    raise ValueError(
                        "a reflected matched sample remains inside the wall-contact envelope"
                    )
                if center_m - guard_m <= 0.0:
                    raise ValueError(
                        "a reflected matched sample is too close to the left boundary"
                    )

        for n_cells in self.fvm_mesh_cells:
            dx_m = self.pipe_length_m / n_cells
            for distance in self.matched_path_travel_m:
                if not math.isclose(
                    distance / dx_m,
                    round(distance / dx_m),
                    abs_tol=1.0e-10,
                ):
                    raise ValueError(
                        "matched path-travel distances must align with every MOC grid"
                    )

    @property
    def pulse_center_m(self) -> float:
        return float(self.pulse_center_fraction * self.pipe_length_m)

    @property
    def pulse_sigma_m(self) -> float:
        return float(self.pulse_sigma_fraction * self.pipe_length_m)

    @property
    def wall_path_travel_m(self) -> float:
        return float(self.pipe_length_m - self.pulse_center_m)

    @property
    def final_reflected_center_m(self) -> float:
        return float(
            2.0 * self.pipe_length_m
            - self.pulse_center_m
            - self.matched_path_travel_m[-1]
        )


def _positive_finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def _float_token(value: float) -> str:
    text = format(float(value), ".12g")
    return text.replace("-", "m").replace(".", "p").replace("+", "")


def case_id_for(
    n_cells: int,
    fvm_cfl: float = 0.5,
    moc_cfl: float = 1.0,
) -> str:
    """Return the stable V-013B case identifier for one mesh."""

    if (
        isinstance(n_cells, bool)
        or not isinstance(n_cells, Integral)
        or int(n_cells) < 1
    ):
        raise ValueError("n_cells must be a positive integer")
    fvm = _positive_finite(fvm_cfl, "fvm_cfl")
    moc = _positive_finite(moc_cfl, "moc_cfl")
    if fvm > 1.0:
        raise ValueError("fvm_cfl must be in (0, 1]")
    if moc != 1.0:
        raise ValueError("moc_cfl must equal 1.0")
    return (
        f"v013b_n{int(n_cells):04d}_"
        f"fvmcfl{_float_token(fvm)}_moccfl{_float_token(moc)}"
    )


def rigid_wall_expected_conditions() -> dict[str, Any]:
    """Return the fixed right-boundary characteristic and reflection identities."""

    return {
        "boundary_kind": "rigid_wall",
        "boundary_side": "right",
        "outgoing_characteristic": "A+",
        "reflected_incoming_characteristic": "A-",
        "characteristic_reflection_coefficient": 1.0,
        "pressure_reflection_coefficient": 1.0,
        "velocity_reflection_coefficient": -1.0,
        "wall_velocity_perturbation_m_s": 0.0,
        "total_wall_pressure_to_incident_pressure_ratio": 2.0,
    }


def _path_state_unchecked(
    path_travel_m: float,
    config: V013RigidWallReflectionConfig,
) -> dict[str, Any]:
    distance = float(path_travel_m)
    wall_distance = config.wall_path_travel_m
    if distance < wall_distance and not math.isclose(
        distance, wall_distance, abs_tol=1.0e-10
    ):
        phase: ReflectionPhase = "incident"
        center_m = config.pulse_center_m + distance
        dominant_characteristic = "A+"
    elif math.isclose(distance, wall_distance, abs_tol=1.0e-10):
        phase = "wall_contact"
        center_m = config.pipe_length_m
        dominant_characteristic = "A+ + A-"
    else:
        phase = "reflected"
        center_m = 2.0 * config.pipe_length_m - config.pulse_center_m - distance
        dominant_characteristic = "A-"
    return {
        "path_travel_m": distance,
        "phase": phase,
        "expected_center_x_m": float(center_m),
        "expected_dominant_characteristic": dominant_characteristic,
    }


def reflection_path_state(
    path_travel_m: float,
    config: V013RigidWallReflectionConfig | None = None,
) -> dict[str, Any]:
    """Map cumulative ray-path travel to the expected pulse phase and centre."""

    cfg = config or V013RigidWallReflectionConfig()
    distance = float(path_travel_m)
    if not math.isfinite(distance) or distance < 0.0:
        raise ValueError("path_travel_m must be finite and non-negative")
    state = _path_state_unchecked(distance, cfg)
    center_m = float(state["expected_center_x_m"])
    if center_m < 0.0 or center_m > cfg.pipe_length_m:
        raise ValueError("path_travel_m places the pulse centre outside the pipe")
    guard_m = cfg.boundary_guard_sigma * cfg.pulse_sigma_m
    phase = state["phase"]
    return {
        **state,
        "right_boundary": "rigid_wall",
        "boundary_guard_sigma": float(cfg.boundary_guard_sigma),
        "primary_wall_guard_overlap_expected": bool(
            phase == "wall_contact"
            or center_m + guard_m > cfg.pipe_length_m + 1.0e-12
        ),
        "secondary_left_boundary_contamination_expected": bool(
            phase == "reflected" and center_m - guard_m <= 0.0
        ),
    }


def build_run_plan(
    config: V013RigidWallReflectionConfig | None = None,
) -> list[dict[str, Any]]:
    """Build the fixed three-run V-013B mesh plan."""

    cfg = config or V013RigidWallReflectionConfig()
    return [
        {
            "case_id": case_id_for(n_cells, cfg.fvm_cfl, cfg.moc_cfl),
            "verification_item": "V-013B",
            "case_role": "rigid_wall_reflection",
            "n_cells": int(n_cells),
            "fvm_cfl": float(cfg.fvm_cfl),
            "moc_cfl": float(cfg.moc_cfl),
            "left_boundary": "transmissive",
            "right_boundary": "rigid_wall",
            "matched_sample_schema_version": cfg.matched_sample_schema_version,
            "comparison_groups": [
                "mesh_comparison",
                "fvm_moc_analytical",
                "rigid_wall_reflection",
            ],
            "production_solver_behavior_changed": False,
        }
        for n_cells in cfg.fvm_mesh_cells
    ]


def build_matched_sample_plan(
    c0_m_s: float,
    config: V013RigidWallReflectionConfig | None = None,
) -> list[dict[str, Any]]:
    """Return fixed field-sample times from cumulative characteristic travel."""

    cfg = config or V013RigidWallReflectionConfig()
    c0 = _positive_finite(c0_m_s, "c0_m_s")
    rows: list[dict[str, Any]] = []
    for index, distance in enumerate(cfg.matched_path_travel_m):
        state = reflection_path_state(distance, cfg)
        rows.append(
            {
                "sample_id": f"v013b_sample_{index:02d}_{_float_token(distance)}m",
                "verification_item": "V-013B",
                "matched_sample_schema_version": cfg.matched_sample_schema_version,
                **state,
                "time_s": float(distance / c0),
                "analytical_sampling": (
                    "direct_at_fvm_cell_centers_and_recorded_times"
                ),
                "moc_sampling": "fixed_linear_time_space_interpolation",
                "time_shift_applied": False,
                "parameter_tuning_applied": False,
            }
        )
    return rows


def build_probe_plan(
    c0_m_s: float,
    config: V013RigidWallReflectionConfig | None = None,
) -> list[dict[str, Any]]:
    """Return fixed probe timing and strictly separated event windows."""

    cfg = config or V013RigidWallReflectionConfig()
    c0 = _positive_finite(c0_m_s, "c0_m_s")
    half_width_s = cfg.window_half_width_sigma * cfg.pulse_sigma_m / c0
    rows: list[dict[str, Any]] = []
    for fraction in cfg.probe_fractions:
        x_m = float(fraction * cfg.pipe_length_m)
        incident_path_m = x_m - cfg.pulse_center_m
        boundary_path_m = cfg.wall_path_travel_m
        reflected_path_m = 2.0 * cfg.pipe_length_m - cfg.pulse_center_m - x_m
        initial_left_return_path_m = cfg.pulse_center_m + x_m
        second_wall_return_path_m = (
            2.0 * cfg.pipe_length_m - cfg.pulse_center_m + x_m
        )
        earliest_secondary_path_m = min(
            initial_left_return_path_m,
            second_wall_return_path_m,
        )
        incident_time_s = incident_path_m / c0
        boundary_time_s = boundary_path_m / c0
        reflected_time_s = reflected_path_m / c0
        incident_end_s = incident_time_s + half_width_s
        boundary_start_s = boundary_time_s - half_width_s
        boundary_end_s = boundary_time_s + half_width_s
        reflected_start_s = reflected_time_s - half_width_s
        reflected_end_s = reflected_time_s + half_width_s
        earliest_secondary_time_s = earliest_secondary_path_m / c0
        earliest_secondary_window_start_s = (
            earliest_secondary_time_s - half_width_s
        )
        if not incident_end_s < boundary_start_s:
            raise RuntimeError("incident and wall-contact windows are not separated")
        if not boundary_end_s < reflected_start_s:
            raise RuntimeError("wall-contact and reflected windows are not separated")
        rows.append(
            {
                "probe_id": f"x_over_L_{_float_token(fraction)}",
                "probe_fraction": float(fraction),
                "probe_target_x_m": x_m,
                "theoretical_incident_path_m": float(incident_path_m),
                "theoretical_boundary_path_m": float(boundary_path_m),
                "theoretical_reflected_path_m": float(reflected_path_m),
                "theoretical_incident_time_s": float(incident_time_s),
                "theoretical_boundary_time_s": float(boundary_time_s),
                "theoretical_reflected_time_s": float(reflected_time_s),
                "window_half_width_sigma": float(cfg.window_half_width_sigma),
                "window_half_width_s": float(half_width_s),
                "incident_window_start_s": float(
                    max(0.0, incident_time_s - half_width_s)
                ),
                "incident_window_end_s": float(incident_end_s),
                "boundary_window_start_s": float(boundary_start_s),
                "boundary_window_end_s": float(boundary_end_s),
                "reflected_window_start_s": float(reflected_start_s),
                "reflected_window_end_s": float(reflected_end_s),
                "initial_left_going_return_time_s": float(
                    initial_left_return_path_m / c0
                ),
                "right_reflection_second_return_time_s": float(
                    second_wall_return_path_m / c0
                ),
                "earliest_secondary_boundary_return_time_s": float(
                    earliest_secondary_time_s
                ),
                "earliest_secondary_boundary_return_window_start_s": float(
                    earliest_secondary_window_start_s
                ),
                "evaluation_window_contaminated": bool(
                    reflected_end_s >= earliest_secondary_window_start_s
                ),
                "event_windows_strictly_separated": True,
                "time_shift_applied": False,
            }
        )
    return rows


def build_specification_snapshot(
    c0_m_s: float,
    config: V013RigidWallReflectionConfig | None = None,
) -> dict[str, Any]:
    """Return a JSON-serializable specification snapshot for review tooling."""

    cfg = config or V013RigidWallReflectionConfig()
    return {
        "verification_item": "V-013B",
        "status": "IN_PROGRESS",
        "config": asdict(cfg),
        "expected_conditions": rigid_wall_expected_conditions(),
        "run_plan": build_run_plan(cfg),
        "matched_sample_plan": build_matched_sample_plan(c0_m_s, cfg),
        "probe_plan": build_probe_plan(c0_m_s, cfg),
        "reference_calls_coolprop": False,
        "production_solver_behavior_changed": False,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "formal_fvm_regression_band_applied": False,
    }


__all__ = [
    "V013RigidWallReflectionConfig",
    "build_matched_sample_plan",
    "build_probe_plan",
    "build_run_plan",
    "build_specification_snapshot",
    "case_id_for",
    "reflection_path_state",
    "rigid_wall_expected_conditions",
]
