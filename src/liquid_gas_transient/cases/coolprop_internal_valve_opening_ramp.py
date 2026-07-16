"""Stage 6 V-012C controlled opening-ramp observation.

This runner exercises the existing single-phase ``InternalValveInterface`` and
``LinearRampOpening`` paths. It does not change the Kv law, Mach cap, governing
equations, or conserved-energy treatment. The result is software / numerical
verification only, not physical Validation or design-use acceptance.
"""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..boundary import ConstantPressure, PressureTankBoundary
from ..boundary_history import (
    record_solver_boundary_telemetry,
    write_boundary_history_csv,
)
from ..boundary_telemetry import BoundaryTelemetryRecorder
from ..config import PipeGeometry
from ..eos import LCO2PropertyEOSAdapter
from ..grid import UniformGrid
from ..interfaces import InternalValveInterface
from ..phase_change import NoPhaseChange
from ..properties import CoolPropCO2Backend, coolprop_available
from ..solver import FvmSolver
from ..source_terms import NoSource
from ..state import make_conserved
from ..valve import KvLiquidValve, LinearRampOpening
from .coolprop_internal_valve_driven import (
    _final_profile,
    _max_abs,
    _probe_specs,
    _relative_difference,
    _sample_probes,
    _state_from_pT,
)
from .coolprop_internal_valve_uniform import (
    _coolprop_version,
    _roundoff_tolerance,
    _sample_valve,
    _write_csv,
)
from .internal_valve_opening_ramp_config import (
    CoolPropInternalValveOpeningRampConfig,
    opening_roundoff_tolerance,
)


def build_coolprop_internal_valve_opening_ramp_solver(
    config: CoolPropInternalValveOpeningRampConfig | None = None,
) -> tuple[FvmSolver, dict[str, Any]]:
    """Build the primary V-012C 0 -> 1 opening-ramp problem."""

    cfg = config or CoolPropInternalValveOpeningRampConfig()
    backend = CoolPropCO2Backend()
    eos = LCO2PropertyEOSAdapter(
        backend=backend,
        boundary_temperature_K=cfg.initial_temperature_K,
        quality_source="transported",
    )
    left_state = _state_from_pT(
        backend,
        eos,
        cfg.left_pressure_pa,
        cfg.initial_temperature_K,
    )
    right_state = _state_from_pT(
        backend,
        eos,
        cfg.right_pressure_pa,
        cfg.initial_temperature_K,
    )

    grid = UniformGrid(
        PipeGeometry(cfg.pipe_length_m, cfg.diameter_m),
        cfg.n_cells,
    )
    area_m2 = float(grid.geometry.area_m2)
    calibration_q_m3_s = (
        area_m2 * cfg.target_full_open_face_velocity_m_s
    )
    kv_m3_per_h = KvLiquidValve.kv_for_target_flow(
        q_m3_s=calibration_q_m3_s,
        delta_p_pa=cfg.calibration_delta_p_pa,
        rho_kg_m3=float(left_state["rho_kg_m3"]),
        opening=1.0,
    )
    opening_schedule = LinearRampOpening(
        t_start_s=cfg.ramp_start_s,
        duration_s=cfg.ramp_duration_s,
        open_initial=cfg.open_initial,
        open_final=cfg.open_final,
    )
    left_cell = cfg.n_cells // 2 - 1
    interface = InternalValveInterface(
        left_cell=left_cell,
        area_m2=area_m2,
        valve=KvLiquidValve(
            kv_m3_per_h=kv_m3_per_h,
            allow_reverse_flow=False,
        ),
        opening_schedule=opening_schedule,
        max_mach=cfg.max_mach,
    )

    rho = np.empty(cfg.n_cells)
    e = np.empty(cfg.n_cells)
    rho[: left_cell + 1] = float(left_state["rho_kg_m3"])
    rho[left_cell + 1 :] = float(right_state["rho_kg_m3"])
    e[: left_cell + 1] = float(left_state["e_j_kg"])
    e[left_cell + 1 :] = float(right_state["e_j_kg"])

    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=make_conserved(
            rho=rho,
            u=np.zeros(cfg.n_cells),
            e=e,
            xv=np.zeros(cfg.n_cells),
        ),
        cfl=cfg.cfl,
        left_boundary=PressureTankBoundary(
            pressure_schedule=ConstantPressure(cfg.left_pressure_pa),
            flow_direction="bidirectional",
            velocity_policy="copy",
        ),
        right_boundary=PressureTankBoundary(
            pressure_schedule=ConstantPressure(cfg.right_pressure_pa),
            flow_direction="bidirectional",
            velocity_policy="copy",
        ),
        source_term=NoSource(),
        phase_change=NoPhaseChange(),
        internal_interfaces=(interface,),
        latent_heat_placeholder_j_kg=0.0,
    )
    valve_x_m = float((left_cell + 1) * grid.dx)
    reference_pressure_profile_pa = np.where(
        grid.cell_centers < valve_x_m,
        float(left_state["pressure_pa"]),
        float(right_state["pressure_pa"]),
    )
    return solver, {
        "left_state": left_state,
        "right_state": right_state,
        "interface": interface,
        "opening_schedule": opening_schedule,
        "kv_m3_per_h": kv_m3_per_h,
        "calibration_q_m3_s": calibration_q_m3_s,
        "valve_x_m": valve_x_m,
        "reference_pressure_profile_pa": reference_pressure_profile_pa,
    }


def opening_ramp_timing(
    config: CoolPropInternalValveOpeningRampConfig,
    context: dict[str, Any],
    probes: list[dict[str, Any]],
) -> dict[str, float]:
    """Return a probe-complete, pre-boundary-arrival observation window."""

    valve_x_m = float(context["valve_x_m"])
    c_left = float(context["left_state"]["c_m_s"])
    c_right = float(context["right_state"]["c_m_s"])
    c_min = min(c_left, c_right)
    farthest_probe_distance_m = max(
        abs(float(row["probe_cell_center_x_m"]) - valve_x_m)
        for row in probes
    )
    full_ramp_probe_observation_time_s = (
        config.ramp_end_s
        + farthest_probe_distance_m / c_min
        + config.post_probe_margin_fraction * config.pipe_length_m / c_min
    )
    boundary_travel_time_s = min(
        valve_x_m / c_left,
        (config.pipe_length_m - valve_x_m) / c_right,
    )
    first_boundary_arrival_time_s = (
        config.ramp_start_s + boundary_travel_time_s
    )
    safe_window_end_s = (
        config.ramp_start_s
        + config.boundary_arrival_safety_fraction * boundary_travel_time_s
    )
    target_time_s = (
        float(config.t_end_s)
        if config.t_end_s is not None
        else min(full_ramp_probe_observation_time_s, safe_window_end_s)
    )
    if target_time_s <= config.ramp_end_s:
        raise ValueError("target time must extend beyond the opening ramp")
    if target_time_s >= first_boundary_arrival_time_s:
        raise ValueError(
            "target time must precede the first valve-generated boundary arrival"
        )
    return {
        "target_time_s": float(target_time_s),
        "ramp_start_s": float(config.ramp_start_s),
        "ramp_end_s": float(config.ramp_end_s),
        "farthest_probe_distance_m": float(farthest_probe_distance_m),
        "full_ramp_probe_observation_time_s": float(
            full_ramp_probe_observation_time_s
        ),
        "first_boundary_arrival_time_s": float(
            first_boundary_arrival_time_s
        ),
        "safe_window_end_s": float(safe_window_end_s),
    }


def _sample_field(
    solver: FvmSolver,
    context: dict[str, Any],
) -> dict[str, Any]:
    primitive = solver.primitive()
    reference_pressure = np.asarray(
        context["reference_pressure_profile_pa"], dtype=float
    )
    return {
        "time_s": float(solver.t),
        "pressure_pa": np.asarray(primitive.p, dtype=float).copy(),
        "delta_pressure_pa": (
            np.asarray(primitive.p, dtype=float) - reference_pressure
        ),
        "velocity_m_s": np.asarray(primitive.u, dtype=float).copy(),
        "temperature_K": np.asarray(primitive.T, dtype=float).copy(),
        "density_kg_m3": np.asarray(primitive.rho, dtype=float).copy(),
        "sound_speed_m_s": np.asarray(primitive.c, dtype=float).copy(),
    }


def _field_history_finite(field_history: list[dict[str, Any]]) -> bool:
    return bool(
        field_history
        and all(
            np.all(np.isfinite(np.asarray(value, dtype=float)))
            for row in field_history
            for value in row.values()
        )
    )


def _max_series_relative_difference(
    rows: list[dict[str, Any]],
    left_key: str,
    right_key: str,
    floor: float,
) -> float:
    return max(
        (
            abs(float(row[left_key]) - float(row[right_key]))
            / max(
                abs(float(row[left_key])),
                abs(float(row[right_key])),
                floor,
            )
            for row in rows
        ),
        default=np.nan,
    )


def _characteristic_summary(
    probe_history: list[dict[str, Any]],
    probes: list[dict[str, Any]],
    config: CoolPropInternalValveOpeningRampConfig,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in probe_history:
        grouped.setdefault(str(row["probe_name"]), []).append(row)

    valve_x_m = float(context["valve_x_m"])
    summaries: list[dict[str, Any]] = []
    for probe in probes:
        name = str(probe["probe_name"])
        side = str(probe["probe_side"])
        distance_m = abs(
            float(probe["probe_cell_center_x_m"]) - valve_x_m
        )
        c0 = float(context[f"{side}_state"]["c_m_s"])
        arrival_start_s = config.ramp_start_s + distance_m / c0
        arrival_end_s = config.ramp_end_s + distance_m / c0
        rows = [
            row
            for row in grouped[name]
            if float(row["time_s"]) >= arrival_start_s
        ]
        if not rows:
            rows = grouped[name][-1:]

        desired_key = "A_minus_pa" if side == "left" else "A_plus_pa"
        undesired_key = "A_plus_pa" if side == "left" else "A_minus_pa"
        desired_peak_row = max(
            rows,
            key=lambda row: abs(float(row[desired_key])),
        )
        desired_peak = float(desired_peak_row[desired_key])
        desired_abs = abs(desired_peak)
        undesired_abs = max(
            abs(float(row[undesired_key])) for row in rows
        )
        leakage_ratio = float(
            undesired_abs / max(desired_abs, np.finfo(float).tiny)
        )
        expected_sign = -1.0 if side == "left" else 1.0
        pressure_extreme = (
            min(float(row["delta_pressure_pa"]) for row in rows)
            if side == "left"
            else max(float(row["delta_pressure_pa"]) for row in rows)
        )
        pressure_sign_match = bool(expected_sign * pressure_extreme > 0.0)
        desired_sign_match = bool(expected_sign * desired_peak > 0.0)
        direction_dominant = bool(desired_abs >= undesired_abs)
        summaries.append(
            {
                **probe,
                "expected_dominant_characteristic": (
                    "A_minus" if side == "left" else "A_plus"
                ),
                "expected_pressure_sign": (
                    "negative" if side == "left" else "positive"
                ),
                "arrival_start_s": float(arrival_start_s),
                "arrival_end_s": float(arrival_end_s),
                "desired_peak_pa": desired_peak,
                "desired_peak_abs_pa": desired_abs,
                "undesired_peak_abs_pa": undesired_abs,
                "opposite_direction_leakage_ratio": leakage_ratio,
                "pressure_extreme_pa": float(pressure_extreme),
                "desired_sign_match": desired_sign_match,
                "pressure_sign_match": pressure_sign_match,
                "direction_dominant": direction_dominant,
                "direction_observation_pass": bool(
                    desired_abs > 0.0
                    and desired_sign_match
                    and pressure_sign_match
                    and direction_dominant
                ),
            }
        )
    return summaries


def _primary_characteristic_rows(
    summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    left = [row for row in summaries if row["probe_side"] == "left"]
    right = [row for row in summaries if row["probe_side"] == "right"]
    if not left or not right:
        return []
    return [
        max(left, key=lambda row: float(row["probe_cell_center_x_m"])),
        min(right, key=lambda row: float(row["probe_cell_center_x_m"])),
    ]


def _write_report(path: Path, metrics: dict[str, Any]) -> None:
    lines = [
        "# V-012C Controlled Opening-Ramp Observation",
        "",
        "Software/numerical verification only; not physical Validation or",
        "design-use acceptance.",
        "",
        "## Result",
        "",
        f"- overall observation execution pass: `{metrics['overall_observation_execution_pass']}`",
        f"- opening ramp: `{metrics['open_initial']}` -> `{metrics['open_final']}`",
        f"- ramp interval: `{metrics['ramp_start_s']:.9e}` to `{metrics['ramp_end_s']:.9e} s`",
        f"- maximum applied Q: `{metrics['max_applied_q_m3_s']:.9e} m3/s`",
        f"- final applied Q: `{metrics['final_applied_q_m3_s']:.9e} m3/s`",
        f"- flow-sign consistency: `{metrics['flow_sign_consistency_fraction']:.6f}`",
        f"- primary characteristic direction pass: `{metrics['primary_characteristic_direction_pass']}`",
        f"- Mach-cap activation count: `{metrics['mach_cap_activation_count']}`",
        "",
        "The opening schedule is prescribed rather than an actuator-dynamics model.",
        "Fixed-pressure boundaries are zero-impedance numerical idealizations,",
        "and the accepted observation window ends before the first valve-generated",
        "wave reaches an external boundary.",
        "",
        "The hydraulic-loss proxy remains diagnostic and is not removed from",
        "conserved `rhoE`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _save_field_history(
    path: Path,
    solver: FvmSolver,
    context: dict[str, Any],
    field_history: list[dict[str, Any]],
) -> None:
    np.savez_compressed(
        path,
        time_s=np.asarray([row["time_s"] for row in field_history]),
        x_m=np.asarray(solver.grid.cell_centers, dtype=float),
        valve_x_m=np.asarray([float(context["valve_x_m"])]),
        reference_pressure_pa=np.asarray(
            context["reference_pressure_profile_pa"], dtype=float
        ),
        pressure_pa=np.stack([row["pressure_pa"] for row in field_history]),
        delta_pressure_pa=np.stack(
            [row["delta_pressure_pa"] for row in field_history]
        ),
        velocity_m_s=np.stack([row["velocity_m_s"] for row in field_history]),
        temperature_K=np.stack([row["temperature_K"] for row in field_history]),
        density_kg_m3=np.stack([row["density_kg_m3"] for row in field_history]),
        sound_speed_m_s=np.stack(
            [row["sound_speed_m_s"] for row in field_history]
        ),
    )


def run_coolprop_internal_valve_opening_ramp(
    output_dir: Path | str | None = None,
    config: CoolPropInternalValveOpeningRampConfig | None = None,
) -> dict[str, Any]:
    """Run V-012C and optionally save numerical artifacts."""

    cfg = config or CoolPropInternalValveOpeningRampConfig()
    solver, context = build_coolprop_internal_valve_opening_ramp_solver(cfg)
    interface: InternalValveInterface = context["interface"]
    opening_schedule: LinearRampOpening = context["opening_schedule"]
    probes = _probe_specs(cfg, solver, float(context["valve_x_m"]))
    timing = opening_ramp_timing(cfg, context, probes)
    target_time_s = float(timing["target_time_s"])

    recorder = BoundaryTelemetryRecorder(area_m2=solver.grid.geometry.area_m2)
    probe_history = _sample_probes(solver, probes, context, 0.0)
    field_history = [_sample_field(solver, context)]
    schedule_history: list[dict[str, Any]] = []
    valve_history: list[dict[str, Any]] = []
    flux_history: list[dict[str, Any]] = []
    dts: list[float] = []

    for _ in range(cfg.max_steps):
        if solver.t >= target_time_s:
            break
        dt_s = solver.compute_dt(target_time_s)
        requested_opening = opening_schedule.opening(solver.t)
        schedule_row, valve_row, flux_row = _sample_valve(
            solver,
            interface,
            requested_opening=requested_opening,
            valve_x_m=float(context["valve_x_m"]),
            dt_s=dt_s,
        )
        schedule_history.append(schedule_row)
        valve_history.append(valve_row)
        flux_history.append(flux_row)
        record_solver_boundary_telemetry(solver, recorder, dt_s)
        solver.step(dt_s)
        dts.append(float(dt_s))

        if solver.step_count % cfg.sample_every == 0 or solver.t >= target_time_s:
            probe_history.extend(_sample_probes(solver, probes, context, dt_s))
        if (
            solver.step_count % cfg.field_sample_every == 0
            or solver.t >= target_time_s
        ):
            field_history.append(_sample_field(solver, context))

    boundary_history = recorder.rows()
    final_profile = _final_profile(solver, context)
    primitive = solver.primitive()
    diagnostics = solver.diagnostics(dt=0.0)
    characteristic_summary = _characteristic_summary(
        probe_history,
        probes,
        cfg,
        context,
    )
    primary_characteristics = _primary_characteristic_rows(
        characteristic_summary
    )

    required_budgets = (
        "budget_mass_residual",
        "energy_budget_balance_residual_j",
        "phase_vapor_mass_balance_residual_kg",
    )
    missing_budget_fields = [
        key for key in required_budgets if key not in diagnostics
    ]
    histories_finite = all(
        np.isfinite(float(value))
        for history in (
            schedule_history,
            valve_history,
            flux_history,
            probe_history,
            boundary_history,
            final_profile,
            characteristic_summary,
        )
        for row in history
        for value in row.values()
        if isinstance(value, (int, float, np.integer, np.floating))
        and not isinstance(value, (bool, np.bool_))
    ) and _field_history_finite(field_history)

    opening_tolerance = opening_roundoff_tolerance(cfg)
    q_tolerance = _roundoff_tolerance(
        *[float(row["applied_q_m3_s"]) for row in valve_history]
    )
    tolerances = {
        "opening_roundoff_tolerance": opening_tolerance,
        "mass_flux_roundoff_tolerance_kg_m2_s": _roundoff_tolerance(
            *[float(row["left_mass_flux_kg_m2_s"]) for row in flux_history]
        ),
        "energy_flux_roundoff_tolerance_w_m2": _roundoff_tolerance(
            *[float(row["left_energy_flux_w_m2"]) for row in flux_history]
        ),
        "vapor_flux_roundoff_tolerance_kg_m2_s": _roundoff_tolerance(
            *[
                float(row["left_vapor_mass_flux_kg_m2_s"])
                for row in flux_history
            ]
        ),
        "momentum_roundoff_tolerance_pa": _roundoff_tolerance(
            *[float(row["left_momentum_flux_pa"]) for row in flux_history]
        ),
        "q_roundoff_tolerance_m3_s": q_tolerance,
    }
    budget_values = {
        "budget_mass_relative_residual": float(
            diagnostics.get("budget_mass_relative_residual", np.nan)
        ),
        "energy_budget_balance_relative_residual": float(
            diagnostics.get(
                "energy_budget_balance_relative_residual",
                np.nan,
            )
        ),
        "phase_vapor_mass_balance_relative_residual": float(
            diagnostics.get(
                "phase_vapor_mass_balance_relative_residual",
                np.nan,
            )
        ),
    }
    budgets_within_tolerance = bool(
        all(
            np.isfinite(value)
            and abs(value) <= cfg.relative_budget_tolerance
            for value in budget_values.values()
        )
    )

    opening_values = np.asarray(
        [float(row["opening_requested"]) for row in schedule_history]
    )
    opening_monotonic = bool(
        opening_values.size > 0
        and np.all(np.diff(opening_values) >= -opening_tolerance)
    )
    pre_hold_rows = [
        row
        for row in valve_history
        if float(row["time_s"]) <= cfg.ramp_start_s + opening_tolerance
    ]
    post_ramp_rows = [
        row
        for row in valve_history
        if float(row["time_s"]) >= cfg.ramp_end_s
    ]
    zero_opening_rows = [
        row
        for row in valve_history
        if float(row["opening_actual"]) <= opening_tolerance
    ]
    finite_opening_rows = [
        row
        for row in valve_history
        if float(row["opening_actual"]) > opening_tolerance
    ]

    raw_applied_difference = _max_series_relative_difference(
        valve_history,
        "raw_target_q_m3_s",
        "applied_q_m3_s",
        q_tolerance,
    )
    applied_flux_difference = _max_series_relative_difference(
        [
            {
                "applied_q_m3_s": valve["applied_q_m3_s"],
                "flux_derived_q_m3_s": flux["flux_derived_q_m3_s"],
            }
            for valve, flux in zip(valve_history, flux_history)
        ],
        "applied_q_m3_s",
        "flux_derived_q_m3_s",
        q_tolerance,
    )
    flow_sign_consistency_count = sum(
        float(row["delta_p_pa"]) * float(row["applied_q_m3_s"])
        >= -q_tolerance
        for row in valve_history
    )

    initial_applied_q = float(
        valve_history[0]["applied_q_m3_s"] if valve_history else np.nan
    )
    final_applied_q = float(
        valve_history[-1]["applied_q_m3_s"] if valve_history else np.nan
    )
    max_applied_q = max(
        (float(row["applied_q_m3_s"]) for row in valve_history),
        default=np.nan,
    )
    primary_characteristic_direction_pass = bool(
        len(primary_characteristics) == 2
        and all(
            bool(row["direction_observation_pass"])
            for row in primary_characteristics
        )
    )

    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "verification_item": "V-012C",
        "expected_dynamic_response": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_name": "coolprop_co2",
        "property_backend_design_status": "not_approved_for_design_use",
        "coolprop_available": coolprop_available(),
        "coolprop_version": _coolprop_version(),
        "n_cells": cfg.n_cells,
        "dx_m": float(solver.grid.dx),
        "cfl_target": cfg.cfl,
        "left_pressure_requested_pa": cfg.left_pressure_pa,
        "right_pressure_requested_pa": cfg.right_pressure_pa,
        "left_pressure_eos_pa": float(context["left_state"]["pressure_pa"]),
        "right_pressure_eos_pa": float(context["right_state"]["pressure_pa"]),
        "initial_delta_p_pa": cfg.initial_delta_p_pa,
        "initial_temperature_K": cfg.initial_temperature_K,
        "left_rho0_kg_m3": float(context["left_state"]["rho_kg_m3"]),
        "right_rho0_kg_m3": float(context["right_state"]["rho_kg_m3"]),
        "left_c0_m_s": float(context["left_state"]["c_m_s"]),
        "right_c0_m_s": float(context["right_state"]["c_m_s"]),
        "open_initial": cfg.open_initial,
        "open_final": cfg.open_final,
        "ramp_duration_s": cfg.ramp_duration_s,
        "kv_m3_per_h": float(context["kv_m3_per_h"]),
        "calibration_delta_p_pa": cfg.calibration_delta_p_pa,
        "calibration_q_m3_s": float(context["calibration_q_m3_s"]),
        "target_full_open_face_velocity_m_s": (
            cfg.target_full_open_face_velocity_m_s
        ),
        "valve_left_cell": int(interface.left_cell),
        "valve_right_cell": int(interface.right_cell),
        "valve_x_m": float(context["valve_x_m"]),
        **timing,
        "final_time_s": float(solver.t),
        "reached_target_time": bool(solver.t >= target_time_s),
        "within_max_steps": bool(solver.step_count <= cfg.max_steps),
        "step_count": int(solver.step_count),
        "min_positive_dt_s": min(dts) if dts else 0.0,
        "max_dt_s": max(dts) if dts else 0.0,
        "all_history_finite": bool(histories_finite),
        "positive_pressure": bool(np.min(primitive.p) > 0.0),
        "positive_temperature": bool(np.min(primitive.T) > 0.0),
        "positive_density": bool(np.min(primitive.rho) > 0.0),
        "positive_sound_speed": bool(np.min(primitive.c) > 0.0),
        "remained_single_phase": bool(
            np.max(primitive.xv) <= 1.0e-12
            and np.max(primitive.alpha) <= 1.0e-12
        ),
        "max_vapor_mass_fraction": float(np.max(primitive.xv)),
        "max_alpha": float(np.max(primitive.alpha)),
        "missing_budget_fields": missing_budget_fields,
        **budget_values,
        "relative_budget_tolerance": cfg.relative_budget_tolerance,
        "budgets_within_tolerance": budgets_within_tolerance,
        "schedule_sample_count": len(schedule_history),
        "valve_history_row_count": len(valve_history),
        "interface_flux_history_row_count": len(flux_history),
        "probe_sample_count": len(probe_history),
        "boundary_history_row_count": len(boundary_history),
        "final_profile_row_count": len(final_profile),
        "field_history_sample_count": len(field_history),
        "characteristic_summary_row_count": len(characteristic_summary),
        "opening_monotonic_non_decreasing": opening_monotonic,
        "max_abs_opening_error": _max_abs(
            schedule_history,
            "opening_error",
        ),
        "pre_hold_sample_count": len(pre_hold_rows),
        "post_ramp_sample_count": len(post_ramp_rows),
        "max_pre_hold_opening": max(
            (float(row["opening_actual"]) for row in pre_hold_rows),
            default=np.nan,
        ),
        "min_post_ramp_opening": min(
            (float(row["opening_actual"]) for row in post_ramp_rows),
            default=np.nan,
        ),
        "zero_opening_hydraulic_separation_fraction": float(
            sum(
                bool(row["hydraulic_separation_active"])
                for row in zero_opening_rows
            )
            / len(zero_opening_rows)
            if zero_opening_rows
            else 0.0
        ),
        "finite_opening_hydraulic_separation_count": int(
            sum(
                bool(row["hydraulic_separation_active"])
                for row in finite_opening_rows
            )
        ),
        "initial_applied_q_m3_s": initial_applied_q,
        "final_applied_q_m3_s": final_applied_q,
        "max_applied_q_m3_s": float(max_applied_q),
        "max_raw_applied_relative_difference": float(
            raw_applied_difference
        ),
        "max_applied_flux_relative_difference": float(
            applied_flux_difference
        ),
        "flow_relative_tolerance": cfg.flow_relative_tolerance,
        "flow_sign_consistency_count": int(flow_sign_consistency_count),
        "flow_sign_consistency_fraction": float(
            flow_sign_consistency_count / len(valve_history)
            if valve_history
            else 0.0
        ),
        "mach_cap_activation_count": int(
            sum(bool(row["mach_cap_active"]) for row in valve_history)
        ),
        "max_applied_face_mach": max(
            abs(float(row["applied_face_mach"]))
            for row in valve_history
        ),
        "max_abs_mass_flux_mismatch_kg_m2_s": _max_abs(
            flux_history,
            "mass_flux_mismatch_kg_m2_s",
        ),
        "max_abs_energy_flux_mismatch_w_m2": _max_abs(
            flux_history,
            "energy_flux_mismatch_w_m2",
        ),
        "max_abs_vapor_mass_flux_mismatch_kg_m2_s": _max_abs(
            flux_history,
            "vapor_mass_flux_mismatch_kg_m2_s",
        ),
        "max_abs_momentum_difference_residual_pa": _max_abs(
            flux_history,
            "momentum_difference_residual_pa",
        ),
        "max_abs_flux_q_minus_applied_q_m3_s": _max_abs(
            flux_history,
            "flux_q_minus_applied_q_m3_s",
        ),
        **tolerances,
        "primary_characteristic_direction_pass": (
            primary_characteristic_direction_pass
        ),
        "primary_characteristic_max_leakage_ratio": max(
            (
                float(row["opposite_direction_leakage_ratio"])
                for row in primary_characteristics
            ),
            default=np.nan,
        ),
        "upstream_decompression_observed": bool(
            primary_characteristics
            and float(primary_characteristics[0]["pressure_extreme_pa"]) < 0.0
        ),
        "downstream_compression_observed": bool(
            len(primary_characteristics) == 2
            and float(primary_characteristics[1]["pressure_extreme_pa"]) > 0.0
        ),
        "max_abs_pressure_disturbance_pa": _max_abs(
            probe_history + final_profile,
            "delta_pressure_pa",
        ),
        "max_abs_velocity_m_s": _max_abs(
            probe_history + final_profile,
            "velocity_m_s",
        ),
        "hydraulic_loss_proxy_is_diagnostic_only": True,
        "hydraulic_loss_removed_from_rhoE": False,
        "fixed_pressure_boundaries_are_zero_impedance_idealizations": True,
    }

    checks = [
        metrics["reached_target_time"],
        metrics["within_max_steps"],
        metrics["all_history_finite"],
        metrics["positive_pressure"],
        metrics["positive_temperature"],
        metrics["positive_density"],
        metrics["positive_sound_speed"],
        metrics["remained_single_phase"],
        not metrics["missing_budget_fields"],
        metrics["budgets_within_tolerance"],
        metrics["target_time_s"] < metrics["first_boundary_arrival_time_s"],
        metrics["opening_monotonic_non_decreasing"],
        metrics["max_abs_opening_error"]
        <= metrics["opening_roundoff_tolerance"],
        metrics["pre_hold_sample_count"] > 0,
        metrics["post_ramp_sample_count"] > 0,
        metrics["max_pre_hold_opening"]
        <= cfg.open_initial + metrics["opening_roundoff_tolerance"],
        metrics["min_post_ramp_opening"]
        >= cfg.open_final - metrics["opening_roundoff_tolerance"],
        metrics["zero_opening_hydraulic_separation_fraction"] == 1.0,
        metrics["finite_opening_hydraulic_separation_count"] == 0,
        abs(metrics["initial_applied_q_m3_s"])
        <= metrics["q_roundoff_tolerance_m3_s"],
        metrics["max_applied_q_m3_s"]
        > metrics["q_roundoff_tolerance_m3_s"],
        metrics["final_applied_q_m3_s"]
        > metrics["q_roundoff_tolerance_m3_s"],
        metrics["max_raw_applied_relative_difference"]
        <= metrics["flow_relative_tolerance"],
        metrics["max_applied_flux_relative_difference"]
        <= metrics["flow_relative_tolerance"],
        metrics["flow_sign_consistency_count"]
        == metrics["valve_history_row_count"],
        metrics["mach_cap_activation_count"] == 0,
        metrics["max_abs_mass_flux_mismatch_kg_m2_s"]
        <= metrics["mass_flux_roundoff_tolerance_kg_m2_s"],
        metrics["max_abs_energy_flux_mismatch_w_m2"]
        <= metrics["energy_flux_roundoff_tolerance_w_m2"],
        metrics["max_abs_vapor_mass_flux_mismatch_kg_m2_s"]
        <= metrics["vapor_flux_roundoff_tolerance_kg_m2_s"],
        metrics["max_abs_momentum_difference_residual_pa"]
        <= metrics["momentum_roundoff_tolerance_pa"],
        metrics["max_abs_flux_q_minus_applied_q_m3_s"]
        <= metrics["q_roundoff_tolerance_m3_s"],
        metrics["primary_characteristic_direction_pass"],
        metrics["upstream_decompression_observed"],
        metrics["downstream_compression_observed"],
    ]
    metrics["overall_observation_execution_pass"] = bool(all(checks))

    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stem = cfg.case_name
        (directory / f"{stem}_config.json").write_text(
            json.dumps(asdict(cfg), indent=2) + "\n",
            encoding="utf-8",
        )
        (directory / f"{stem}_metrics.json").write_text(
            json.dumps(metrics, indent=2) + "\n",
            encoding="utf-8",
        )
        _write_csv(directory / f"{stem}_valve_schedule.csv", schedule_history)
        _write_csv(directory / f"{stem}_valve_history.csv", valve_history)
        _write_csv(
            directory / f"{stem}_interface_flux_history.csv",
            flux_history,
        )
        _write_csv(directory / f"{stem}_probe_history.csv", probe_history)
        _write_csv(
            directory / f"{stem}_probe_characteristic_summary.csv",
            characteristic_summary,
        )
        write_boundary_history_csv(
            directory / f"{stem}_boundary_history.csv",
            boundary_history,
        )
        _write_csv(directory / f"{stem}_final_profile.csv", final_profile)
        _save_field_history(
            directory / f"{stem}_field_history.npz",
            solver,
            context,
            field_history,
        )
        _write_report(
            directory / f"{stem}_observation_report.md",
            metrics,
        )

    return metrics
