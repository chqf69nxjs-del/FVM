"""V-013B rigid-wall FVM / MOC / analytical observation runner.

This production-connected runner uses the existing CoolProp small-amplitude FVM
initialization and the existing reflective boundary without changing solver physics.
The independent analytical/MOC path receives only recorded scalar reference inputs.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import csv
import importlib.metadata
import json
import math
from pathlib import Path
import tempfile
import time
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..boundary_history import write_boundary_history_csv
from ..boundary_telemetry import BoundaryTelemetryRecorder
from ..verification.linear_acoustic_reference import (
    LinearAcousticReferenceConfig,
    acoustic_energy_proxy,
    characteristics_from_pressure_velocity,
    evaluate_gaussian_reference,
    initialize_moc_characteristics,
    make_gaussian_profile,
    run_moc_reference,
)
from .coolprop_boundary_reflection import (
    CoolPropBoundaryReflectionConfig,
    build_coolprop_boundary_reflection_solver,
)
from .v013_rigid_wall_reflection import (
    V013RigidWallReflectionConfig,
    build_matched_sample_plan,
    build_probe_plan,
    build_run_plan,
)


EXPECTED_PLOT_COUNT = 7


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _installed_coolprop_version() -> str:
    try:
        return importlib.metadata.version("CoolProp")
    except importlib.metadata.PackageNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("CoolProp package metadata is unavailable") from exc


def _trapezoidal_integral(values: ArrayLike, x_m: ArrayLike) -> float:
    integrate = getattr(np, "trapezoid", None)
    if integrate is None:
        integrate = np.trapz
    return float(
        integrate(
            np.asarray(values, dtype=float),
            np.asarray(x_m, dtype=float),
        )
    )


def normalized_error_norms(
    x_m: ArrayLike,
    candidate: ArrayLike,
    reference: ArrayLike,
    *,
    normalization_reference: ArrayLike | None = None,
) -> dict[str, float]:
    """Return normalized L1/L2/Linf and absolute Linf errors on one grid."""

    x = np.asarray(x_m, dtype=float)
    cand = np.asarray(candidate, dtype=float)
    ref = np.asarray(reference, dtype=float)
    scale = ref if normalization_reference is None else np.asarray(
        normalization_reference, dtype=float
    )
    if x.ndim != 1 or x.size < 2:
        raise ValueError("x_m must be a 1-D increasing grid with at least two samples")
    if cand.shape != x.shape or ref.shape != x.shape or scale.shape != x.shape:
        raise ValueError("candidate, reference, and normalization arrays must match x_m")
    if not (
        np.all(np.isfinite(x))
        and np.all(np.diff(x) > 0.0)
        and np.all(np.isfinite(cand))
        and np.all(np.isfinite(ref))
        and np.all(np.isfinite(scale))
    ):
        raise ValueError("error-norm inputs must be finite on an increasing grid")
    diff = cand - ref
    l1_num = _trapezoidal_integral(np.abs(diff), x)
    l2_num = float(np.sqrt(_trapezoidal_integral(diff * diff, x)))
    linf_num = float(np.max(np.abs(diff)))
    l1_den = _trapezoidal_integral(np.abs(scale), x)
    l2_den = float(np.sqrt(_trapezoidal_integral(scale * scale, x)))
    linf_den = float(np.max(np.abs(scale)))
    floor = np.finfo(float).tiny
    return {
        "l1_relative": 0.0 if l1_num == 0.0 else l1_num / max(l1_den, floor),
        "l2_relative": 0.0 if l2_num == 0.0 else l2_num / max(l2_den, floor),
        "linf_relative": 0.0 if linf_num == 0.0 else linf_num / max(linf_den, floor),
        "linf_absolute": linf_num,
    }


def sample_spacetime_history(
    history_time_s: ArrayLike,
    history_x_m: ArrayLike,
    history_values: ArrayLike,
    query_time_s: ArrayLike,
    query_x_m: ArrayLike,
) -> NDArray[np.float64]:
    """Sample one history by fixed linear time and space interpolation."""

    times = np.asarray(history_time_s, dtype=float)
    x = np.asarray(history_x_m, dtype=float)
    values = np.asarray(history_values, dtype=float)
    qt, qx = np.broadcast_arrays(
        np.asarray(query_time_s, dtype=float),
        np.asarray(query_x_m, dtype=float),
    )
    if times.ndim != 1 or x.ndim != 1 or values.shape != (times.size, x.size):
        raise ValueError("history_values must have shape (len(time), len(x))")
    if times.size < 2 or x.size < 2:
        raise ValueError("history axes must contain at least two points")
    if np.any(np.diff(times) <= 0.0) or np.any(np.diff(x) <= 0.0):
        raise ValueError("history axes must be strictly increasing")
    if not (
        np.all(np.isfinite(times))
        and np.all(np.isfinite(x))
        and np.all(np.isfinite(values))
        and np.all(np.isfinite(qt))
        and np.all(np.isfinite(qx))
    ):
        raise ValueError("history and query values must be finite")
    tolerance = 1.0e-12
    if (
        np.any(qt < times[0] - tolerance)
        or np.any(qt > times[-1] + tolerance)
        or np.any(qx < x[0] - tolerance)
        or np.any(qx > x[-1] + tolerance)
    ):
        raise ValueError("spacetime query lies outside the saved history domain")

    flat_t = np.clip(qt.ravel(), times[0], times[-1])
    flat_x = np.clip(qx.ravel(), x[0], x[-1])
    result = np.empty(flat_t.shape, dtype=float)
    for k, (time_value, x_value) in enumerate(zip(flat_t, flat_x)):
        hi = int(np.searchsorted(times, time_value, side="right"))
        if hi == 0:
            lo = hi = 0
        elif hi >= times.size:
            lo = hi = times.size - 1
        else:
            lo = hi - 1
        spatial_lo = float(np.interp(x_value, x, values[lo]))
        if lo == hi:
            result[k] = spatial_lo
        else:
            spatial_hi = float(np.interp(x_value, x, values[hi]))
            weight = (time_value - times[lo]) / (times[hi] - times[lo])
            result[k] = spatial_lo + weight * (spatial_hi - spatial_lo)
    return result.reshape(qt.shape)


def leading_fraction_crossings(
    time_s: ArrayLike,
    signal: ArrayLike,
    fractions: Sequence[float] = (0.1, 0.5, 0.9),
) -> dict[str, Any]:
    """Detect rising-side local-peak fraction crossings by linear interpolation."""

    t = np.asarray(time_s, dtype=float)
    y = np.asarray(signal, dtype=float)
    if t.ndim != 1 or y.shape != t.shape or t.size < 3:
        return {
            "detected": False,
            "peak": None,
            "peak_time_s": None,
            "crossing_times_s": {},
        }
    if np.any(np.diff(t) <= 0.0) or not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)):
        raise ValueError("crossing inputs must be finite with strictly increasing time")
    adjusted = y - y[0]
    peak_index = int(np.argmax(adjusted))
    peak = float(adjusted[peak_index])
    out: dict[str, Any] = {
        "detected": bool(peak_index > 0 and peak > 0.0),
        "peak": peak,
        "peak_time_s": float(t[peak_index]),
        "crossing_times_s": {},
    }
    if not out["detected"]:
        return out
    for fraction in fractions:
        threshold = float(fraction) * peak
        crossing: float | None = None
        for index in range(peak_index):
            y0 = float(adjusted[index])
            y1 = float(adjusted[index + 1])
            if y0 < threshold <= y1:
                weight = 0.0 if y1 == y0 else (threshold - y0) / (y1 - y0)
                crossing = float(t[index] + weight * (t[index + 1] - t[index]))
                break
        out["crossing_times_s"][f"p{int(round(100 * fraction)):02d}"] = crossing
    return out


def _record_boundary_step(
    solver: Any,
    recorder: BoundaryTelemetryRecorder,
    dt_s: float,
) -> None:
    U_ext = solver.extend_with_ghosts(solver.t)
    flux = solver.flux_function(U_ext[:-1], U_ext[1:], solver.eos)
    i0 = solver.n_ghost
    i1 = solver.n_ghost + solver.grid.n_cells
    recorder.record_external_faces(
        step=solver.step_count + 1,
        flux_evaluation_time_s=solver.t,
        dt_s=dt_s,
        left_face_U_left=U_ext[i0 - 1],
        left_face_U_right=U_ext[i0],
        right_face_U_left=U_ext[i1 - 1],
        right_face_U_right=U_ext[i1],
        left_flux=flux[i0 - 1],
        right_flux=flux[i1 - 1],
        eos=solver.eos,
    )


def _sample_fvm_state(
    solver: Any,
    initial_pressure_pa: float,
    rho0: float,
    c0: float,
) -> dict[str, NDArray[np.float64]]:
    prim = solver.primitive()
    pressure = np.asarray(prim.p, dtype=float) - float(initial_pressure_pa)
    velocity = np.asarray(prim.u, dtype=float)
    a_plus, a_minus = characteristics_from_pressure_velocity(
        pressure,
        velocity,
        rho0_kg_m3=rho0,
        c0_m_s=c0,
    )
    return {
        "pressure_perturbation_pa": pressure,
        "velocity_m_s": velocity,
        "a_plus_pa": a_plus,
        "a_minus_pa": a_minus,
        "temperature_K": np.asarray(prim.T, dtype=float),
        "density_kg_m3": np.asarray(prim.rho, dtype=float),
        "sound_speed_m_s": np.asarray(prim.c, dtype=float),
        "vapor_mass_fraction": np.asarray(prim.xv, dtype=float),
        "alpha": np.asarray(prim.alpha, dtype=float),
    }


def _probe_timing(
    probe_x_m: float,
    c0_m_s: float,
    cfg: V013RigidWallReflectionConfig,
) -> dict[str, Any]:
    x = float(probe_x_m)
    c0 = float(c0_m_s)
    x0 = cfg.pulse_center_m
    length = cfg.pipe_length_m
    half_width_s = cfg.window_half_width_sigma * cfg.pulse_sigma_m / c0
    incident_path = x - x0
    wall_path = length - x0
    reflected_path = 2.0 * length - x0 - x
    initial_left_return_path = x0 + x
    wall_left_wall_return_path = 2.0 * length - x0 + x
    earliest_return_path = min(initial_left_return_path, wall_left_wall_return_path)
    incident_time = incident_path / c0
    wall_time = wall_path / c0
    reflected_time = reflected_path / c0
    return_center_time = earliest_return_path / c0
    return_leading_time = return_center_time - half_width_s
    reflected_end_time = reflected_time + half_width_s
    return {
        "theoretical_incident_path_m": float(incident_path),
        "theoretical_wall_path_m": float(wall_path),
        "theoretical_reflected_path_m": float(reflected_path),
        "theoretical_incident_time_s": float(incident_time),
        "theoretical_wall_time_s": float(wall_time),
        "theoretical_reflected_time_s": float(reflected_time),
        "incident_window_start_s": float(max(0.0, incident_time - half_width_s)),
        "incident_window_end_s": float(incident_time + half_width_s),
        "wall_window_start_s": float(wall_time - half_width_s),
        "wall_window_end_s": float(wall_time + half_width_s),
        "reflected_window_start_s": float(reflected_time - half_width_s),
        "reflected_window_end_s": float(reflected_end_time),
        "earliest_secondary_boundary_return_time_s": float(return_center_time),
        "earliest_secondary_boundary_return_window_start_s": float(return_leading_time),
        "evaluation_window_contaminated": bool(
            reflected_end_time >= return_leading_time
        ),
    }


def _probe_specs(
    x_m: NDArray[np.float64],
    c0_m_s: float,
    cfg: V013RigidWallReflectionConfig,
) -> list[dict[str, Any]]:
    planned = build_probe_plan(c0_m_s, cfg)
    specs: list[dict[str, Any]] = []
    for row in planned:
        target = float(row["probe_target_x_m"])
        index = int(np.argmin(np.abs(x_m - target)))
        actual = float(x_m[index])
        specs.append(
            {
                "probe_id": str(row["probe_id"]),
                "probe_fraction": float(row["probe_fraction"]),
                "probe_target_x_m": target,
                "probe_index": index,
                "probe_x_m": actual,
                **_probe_timing(actual, c0_m_s, cfg),
            }
        )
    return specs


def _boundary_metrics(
    cfg: V013RigidWallReflectionConfig,
    boundary_rows: Sequence[Mapping[str, Any]],
    c0_m_s: float,
) -> dict[str, Any]:
    wall_time = cfg.wall_path_travel_m / c0_m_s
    half_width = cfg.window_half_width_sigma * cfg.pulse_sigma_m / c0_m_s
    selected = [
        row
        for row in boundary_rows
        if row.get("side") == "right"
        and wall_time - half_width
        <= float(row["flux_evaluation_time_s"])
        <= wall_time + half_width
    ]
    if not selected:
        return {
            "wall_window_sample_count": 0,
            "wall_window_start_s": float(wall_time - half_width),
            "wall_window_end_s": float(wall_time + half_width),
        }
    pressure = np.asarray(
        [row["boundary_face_pressure_pa"] for row in selected], dtype=float
    )
    velocity = np.asarray(
        [row["boundary_face_velocity_m_s"] for row in selected], dtype=float
    )
    mass_flux = np.asarray(
        [row["numerical_mass_flux_kg_m2_s"] for row in selected], dtype=float
    )
    energy_flux = np.asarray(
        [row["numerical_energy_flux_w_m2"] for row in selected], dtype=float
    )
    return {
        "wall_window_sample_count": len(selected),
        "wall_window_start_s": float(wall_time - half_width),
        "wall_window_end_s": float(wall_time + half_width),
        "max_abs_wall_velocity_m_s": float(np.max(np.abs(velocity))),
        "max_abs_wall_mass_flux_kg_m2_s": float(np.max(np.abs(mass_flux))),
        "max_abs_wall_energy_flux_w_m2": float(np.max(np.abs(energy_flux))),
        "max_wall_pressure_perturbation_pa": float(
            np.max(pressure - cfg.initial_pressure_pa)
        ),
        "wall_pressure_amplification_ratio": float(
            np.max(pressure - cfg.initial_pressure_pa)
            / cfg.pressure_amplitude_pa
        ),
    }


def _run_fvm(
    n_cells: int,
    cfg: V013RigidWallReflectionConfig,
) -> tuple[
    dict[str, Any],
    dict[str, NDArray[np.float64]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    source_cfg = CoolPropBoundaryReflectionConfig(
        boundary_kind="rigid_wall",
        case_name=f"v013b_fvm_rigid_wall_n{n_cells:04d}",
        output_version="v013b_fvm_rigid_wall_v1",
        pipe_length_m=cfg.pipe_length_m,
        diameter_m=cfg.diameter_m,
        n_cells=n_cells,
        cfl=cfg.fvm_cfl,
        initial_pressure_pa=cfg.initial_pressure_pa,
        initial_temperature_K=cfg.initial_temperature_K,
        pressure_amplitude_pa=cfg.pressure_amplitude_pa,
        pulse_center_fraction=cfg.pulse_center_fraction,
        pulse_sigma_fraction=cfg.pulse_sigma_fraction,
        probe_fractions=cfg.probe_fractions,
        sample_every=1,
        max_steps=cfg.max_steps,
        window_half_width_sigma=cfg.window_half_width_sigma,
    )
    solver, initial = build_coolprop_boundary_reflection_solver(source_cfg)
    reference = initial["reference"]
    rho0 = float(reference["rho0"])
    c0 = float(reference["c0"])
    x = np.asarray(solver.grid.cell_centers, dtype=float)
    matched_plan = build_matched_sample_plan(c0, cfg)
    matched_times = np.asarray([row["time_s"] for row in matched_plan], dtype=float)
    probes = _probe_specs(x, c0, cfg)
    recorder = BoundaryTelemetryRecorder(area_m2=solver.grid.geometry.area_m2)

    field_samples: dict[str, list[NDArray[np.float64]]] = {
        "pressure_perturbation_pa": [],
        "velocity_m_s": [],
        "a_plus_pa": [],
        "a_minus_pa": [],
    }
    probe_rows: list[dict[str, Any]] = []
    dt_history: list[float] = []
    extrema = {
        "min_pressure_pa": math.inf,
        "min_temperature_K": math.inf,
        "min_density_kg_m3": math.inf,
        "min_sound_speed_m_s": math.inf,
        "max_vapor_mass_fraction": 0.0,
        "max_alpha": 0.0,
    }

    def capture_step(dt_s: float) -> dict[str, NDArray[np.float64]]:
        state = _sample_fvm_state(
            solver,
            cfg.initial_pressure_pa,
            rho0,
            c0,
        )
        extrema["min_pressure_pa"] = min(
            extrema["min_pressure_pa"],
            float(np.min(state["pressure_perturbation_pa"] + cfg.initial_pressure_pa)),
        )
        extrema["min_temperature_K"] = min(
            extrema["min_temperature_K"], float(np.min(state["temperature_K"]))
        )
        extrema["min_density_kg_m3"] = min(
            extrema["min_density_kg_m3"], float(np.min(state["density_kg_m3"]))
        )
        extrema["min_sound_speed_m_s"] = min(
            extrema["min_sound_speed_m_s"], float(np.min(state["sound_speed_m_s"]))
        )
        extrema["max_vapor_mass_fraction"] = max(
            extrema["max_vapor_mass_fraction"],
            float(np.max(state["vapor_mass_fraction"])),
        )
        extrema["max_alpha"] = max(
            extrema["max_alpha"], float(np.max(state["alpha"]))
        )
        for probe in probes:
            index = int(probe["probe_index"])
            probe_rows.append(
                {
                    "time_s": float(solver.t),
                    "step": int(solver.step_count),
                    "dt_s": float(dt_s),
                    **probe,
                    "pressure_perturbation_pa": float(
                        state["pressure_perturbation_pa"][index]
                    ),
                    "velocity_m_s": float(state["velocity_m_s"][index]),
                    "a_plus_pa": float(state["a_plus_pa"][index]),
                    "a_minus_pa": float(state["a_minus_pa"][index]),
                }
            )
        return state

    state = capture_step(0.0)
    for key in field_samples:
        field_samples[key].append(np.array(state[key], dtype=float, copy=True))

    for target_time in matched_times[1:]:
        while solver.t < float(target_time) - 1.0e-14:
            if solver.step_count >= cfg.max_steps:
                raise RuntimeError("V-013B FVM run exceeded max_steps")
            dt_s = float(solver.compute_dt(float(target_time)))
            if not math.isfinite(dt_s) or dt_s <= 0.0:
                raise RuntimeError("V-013B FVM produced a non-positive timestep")
            _record_boundary_step(solver, recorder, dt_s)
            solver.step(dt_s)
            dt_history.append(dt_s)
            state = capture_step(dt_s)
        if not math.isclose(
            solver.t,
            float(target_time),
            rel_tol=0.0,
            abs_tol=2.0e-13,
        ):
            raise RuntimeError("FVM did not land on a prescribed V-013B sample time")
        for key in field_samples:
            field_samples[key].append(np.array(state[key], dtype=float, copy=True))

    field_history = {
        "time_s": matched_times,
        "x_m": x,
        **{key: np.vstack(values) for key, values in field_samples.items()},
    }
    boundary_rows = recorder.rows()
    diag = solver.diagnostics(dt=0.0)
    required_budget = (
        "budget_mass_residual",
        "energy_budget_balance_residual_j",
        "phase_vapor_mass_balance_residual_kg",
    )
    missing_budget = [name for name in required_budget if name not in diag]
    arrays_finite = all(
        np.all(np.isfinite(np.asarray(value)))
        for value in field_history.values()
    ) and all(
        math.isfinite(float(row[key]))
        for row in probe_rows
        for key in (
            "time_s",
            "pressure_perturbation_pa",
            "velocity_m_s",
            "a_plus_pa",
            "a_minus_pa",
        )
    )
    contamination = any(
        bool(probe["evaluation_window_contaminated"]) for probe in probes
    )
    wall = _boundary_metrics(cfg, boundary_rows, c0)
    health_pass = bool(
        arrays_finite
        and not missing_budget
        and extrema["min_pressure_pa"] > 0.0
        and extrema["min_temperature_K"] > 0.0
        and extrema["min_density_kg_m3"] > 0.0
        and extrema["min_sound_speed_m_s"] > 0.0
        and extrema["max_vapor_mass_fraction"] <= 1.0e-12
        and extrema["max_alpha"] <= 1.0e-12
        and solver.step_count <= cfg.max_steps
        and not contamination
        and wall.get("wall_window_sample_count", 0) > 0
    )
    metrics = {
        "implementation": "fvm",
        "source_case": "coolprop_boundary_reflection",
        "source_builder": "build_coolprop_boundary_reflection_solver",
        "right_boundary": "ReflectiveBoundary",
        "solver_physics_changed": False,
        "n_cells": int(n_cells),
        "dx_m": float(solver.grid.dx),
        "cfl_target": float(cfg.fvm_cfl),
        "final_time_s": float(solver.t),
        "target_time_s": float(matched_times[-1]),
        "reached_target_time": bool(
            math.isclose(
                solver.t,
                matched_times[-1],
                rel_tol=0.0,
                abs_tol=2.0e-13,
            )
        ),
        "step_count": int(solver.step_count),
        "min_positive_dt_s": float(min(dt_history)) if dt_history else 0.0,
        "max_dt_s": float(max(dt_history)) if dt_history else 0.0,
        "probe_sample_count": len(probe_rows),
        "field_sample_count": int(matched_times.size),
        "boundary_history_row_count": len(boundary_rows),
        "all_history_finite": arrays_finite,
        "positive_pressure": extrema["min_pressure_pa"] > 0.0,
        "positive_temperature": extrema["min_temperature_K"] > 0.0,
        "positive_density": extrema["min_density_kg_m3"] > 0.0,
        "positive_sound_speed": extrema["min_sound_speed_m_s"] > 0.0,
        "remained_single_phase": bool(
            extrema["max_vapor_mass_fraction"] <= 1.0e-12
            and extrema["max_alpha"] <= 1.0e-12
        ),
        **extrema,
        "missing_budget_fields": missing_budget,
        "budget_mass_residual": float(diag.get("budget_mass_residual", math.nan)),
        "budget_mass_relative_residual": float(
            diag.get("budget_mass_relative_residual", math.nan)
        ),
        "energy_budget_balance_residual_j": float(
            diag.get("energy_budget_balance_residual_j", math.nan)
        ),
        "energy_budget_balance_relative_residual": float(
            diag.get("energy_budget_balance_relative_residual", math.nan)
        ),
        "phase_vapor_mass_balance_residual_kg": float(
            diag.get("phase_vapor_mass_balance_residual_kg", math.nan)
        ),
        "phase_vapor_mass_balance_relative_residual": float(
            diag.get("phase_vapor_mass_balance_relative_residual", math.nan)
        ),
        "property_backend_name": "coolprop_co2",
        "property_backend_design_status": "not_approved_for_design_use",
        "coolprop_version": _installed_coolprop_version(),
        "rho0_kg_m3": rho0,
        "c0_m_s": c0,
        "rho0_provenance": (
            "CoolPropCO2Backend.density_from_pT at the recorded p0/T0 source state"
        ),
        "c0_provenance": (
            "LCO2PropertyEOSAdapter primitive sound speed at the recorded uniform source state"
        ),
        "evaluation_window_contaminated": contamination,
        "boundary_metrics": wall,
        "overall_fvm_health_pass": health_pass,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
    }
    return metrics, field_history, probe_rows, boundary_rows, {
        "source_config": asdict(source_cfg),
        "reference": reference,
        "probes": probes,
        "matched_sample_plan": matched_plan,
    }


def _run_moc(
    n_cells: int,
    cfg: V013RigidWallReflectionConfig,
    *,
    rho0: float,
    c0: float,
) -> tuple[LinearAcousticReferenceConfig, dict[str, Any], dict[str, Any]]:
    reference_cfg = LinearAcousticReferenceConfig(
        p0_pa=cfg.initial_pressure_pa,
        rho0_kg_m3=rho0,
        c0_m_s=c0,
        length_m=cfg.pipe_length_m,
        n_cells=n_cells,
        left_boundary="transmissive",
        right_boundary="rigid_wall",
    )
    profile = make_gaussian_profile(
        amplitude_pa=cfg.pressure_amplitude_pa,
        center_m=cfg.pulse_center_m,
        sigma_m=cfg.pulse_sigma_m,
    )
    zero = lambda x: np.zeros_like(x, dtype=float)
    initial_plus, initial_minus = initialize_moc_characteristics(
        reference_cfg,
        initial_a_plus=profile,
        initial_a_minus=zero,
    )
    final_steps = int(
        round(cfg.matched_path_travel_m[-1] / reference_cfg.dx_m)
    )
    history = run_moc_reference(
        reference_cfg,
        initial_a_plus_pa=initial_plus,
        initial_a_minus_pa=initial_minus,
        n_steps=final_steps,
    )
    max_native_error = 0.0
    for path_travel_m in cfg.matched_path_travel_m:
        step = int(round(path_travel_m / reference_cfg.dx_m))
        analytical = evaluate_gaussian_reference(
            history["x_m"],
            float(history["time_s"][step]),
            length_m=cfg.pipe_length_m,
            rho0_kg_m3=rho0,
            c0_m_s=c0,
            amplitude_pa=cfg.pressure_amplitude_pa,
            center_m=cfg.pulse_center_m,
            sigma_m=cfg.pulse_sigma_m,
            direction="right_going",
            left_boundary="transmissive",
            right_boundary="rigid_wall",
        )
        max_native_error = max(
            max_native_error,
            float(
                np.max(
                    np.abs(
                        history["pressure_perturbation_pa"][step]
                        - analytical["pressure_perturbation_pa"]
                    )
                )
            ),
            float(
                np.max(
                    np.abs(
                        history["velocity_m_s"][step]
                        - analytical["velocity_m_s"]
                    )
                )
            )
            * rho0
            * c0,
        )
    metrics = {
        "implementation": "moc",
        "n_cells": int(n_cells),
        "n_nodes": int(reference_cfg.n_nodes),
        "dx_m": float(reference_cfg.dx_m),
        "dt_s": float(reference_cfg.dt_s),
        "cfl": float(reference_cfg.cfl),
        "n_steps": int(final_steps),
        "final_time_s": float(history["time_s"][-1]),
        "native_grid_max_pressure_equivalent_error_pa": max_native_error,
        "right_boundary": "rigid_wall",
        "reference_only": True,
        "calls_coolprop": False,
        "production_solver_imported": False,
        "production_boundary_imported": False,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "overall_moc_reference_pass": bool(
            np.all(np.isfinite(history["pressure_perturbation_pa"]))
            and np.all(np.isfinite(history["velocity_m_s"]))
            and max_native_error
            <= max(1.0e-10, cfg.pressure_amplitude_pa * 1.0e-12)
        ),
    }
    return reference_cfg, history, metrics


def _absolute_peak_metrics(
    x_m: NDArray[np.float64],
    candidate: NDArray[np.float64],
    reference: NDArray[np.float64],
) -> dict[str, Any]:
    candidate_index = int(np.argmax(np.abs(candidate)))
    reference_index = int(np.argmax(np.abs(reference)))
    candidate_peak = float(candidate[candidate_index])
    reference_peak = float(reference[reference_index])
    return {
        "candidate_signed_peak": candidate_peak,
        "reference_signed_peak": reference_peak,
        "candidate_absolute_peak": abs(candidate_peak),
        "reference_absolute_peak": abs(reference_peak),
        "absolute_peak_ratio": (
            float(abs(candidate_peak) / abs(reference_peak))
            if reference_peak != 0.0
            else None
        ),
        "signed_peak_error": float(candidate_peak - reference_peak),
        "candidate_peak_x_m": float(x_m[candidate_index]),
        "reference_peak_x_m": float(x_m[reference_index]),
        "peak_location_error_m": float(
            x_m[candidate_index] - x_m[reference_index]
        ),
    }


def _window_mask(
    time_s: NDArray[np.float64],
    start_s: float,
    end_s: float,
) -> NDArray[np.bool_]:
    return (time_s >= float(start_s)) & (time_s <= float(end_s))


def _reflection_metrics_for_signal(
    time_s: NDArray[np.float64],
    a_plus_pa: NDArray[np.float64],
    a_minus_pa: NDArray[np.float64],
    velocity_m_s: NDArray[np.float64],
    timing: Mapping[str, Any],
) -> dict[str, Any]:
    incident_mask = _window_mask(
        time_s,
        float(timing["incident_window_start_s"]),
        float(timing["incident_window_end_s"]),
    )
    reflected_mask = _window_mask(
        time_s,
        float(timing["reflected_window_start_s"]),
        float(timing["reflected_window_end_s"]),
    )
    if np.count_nonzero(incident_mask) < 3 or np.count_nonzero(reflected_mask) < 3:
        return {
            "detected": False,
            "incident_sample_count": int(np.count_nonzero(incident_mask)),
            "reflected_sample_count": int(np.count_nonzero(reflected_mask)),
        }
    incident_plus = a_plus_pa[incident_mask]
    reflected_minus = a_minus_pa[reflected_mask]
    incident_velocity = velocity_m_s[incident_mask]
    reflected_velocity = velocity_m_s[reflected_mask]
    incident_peak = float(np.max(incident_plus))
    reflected_peak = float(np.max(reflected_minus))
    incident_velocity_peak = float(np.max(incident_velocity))
    reflected_velocity_peak = float(np.min(reflected_velocity))
    crossings = leading_fraction_crossings(
        time_s[reflected_mask],
        reflected_minus,
    )
    incident_leakage = float(np.max(np.abs(a_minus_pa[incident_mask])))
    reflected_leakage = float(np.max(np.abs(a_plus_pa[reflected_mask])))
    return {
        "detected": bool(incident_peak > 0.0 and reflected_peak > 0.0),
        "incident_sample_count": int(np.count_nonzero(incident_mask)),
        "reflected_sample_count": int(np.count_nonzero(reflected_mask)),
        "incident_a_plus_peak_pa": incident_peak,
        "reflected_a_minus_peak_pa": reflected_peak,
        "pressure_reflection_coefficient": (
            float(reflected_peak / incident_peak) if incident_peak != 0.0 else None
        ),
        "incident_velocity_peak_m_s": incident_velocity_peak,
        "reflected_velocity_signed_peak_m_s": reflected_velocity_peak,
        "velocity_reflection_coefficient": (
            float(reflected_velocity_peak / incident_velocity_peak)
            if incident_velocity_peak != 0.0
            else None
        ),
        "incident_a_minus_leakage_peak_pa": incident_leakage,
        "reflected_a_plus_leakage_peak_pa": reflected_leakage,
        "incident_characteristic_leakage_ratio": (
            float(incident_leakage / incident_peak)
            if incident_peak != 0.0
            else None
        ),
        "reflected_characteristic_leakage_ratio": (
            float(reflected_leakage / reflected_peak)
            if reflected_peak != 0.0
            else None
        ),
        "reflected_p10_time_s": crossings["crossing_times_s"].get("p10"),
        "reflected_p50_time_s": crossings["crossing_times_s"].get("p50"),
        "reflected_p90_time_s": crossings["crossing_times_s"].get("p90"),
        "expected_pressure_sign_observed": bool(reflected_peak > 0.0),
        "expected_velocity_sign_observed": bool(reflected_velocity_peak < 0.0),
    }


def _compare_run(
    cfg: V013RigidWallReflectionConfig,
    fvm_metrics: dict[str, Any],
    fvm_history: dict[str, NDArray[np.float64]],
    fvm_probe_rows: list[dict[str, Any]],
    moc_history: dict[str, Any],
    matched_plan: Sequence[Mapping[str, Any]],
    probe_specs: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    rho0 = float(fvm_metrics["rho0_kg_m3"])
    c0 = float(fvm_metrics["c0_m_s"])
    x = np.asarray(fvm_history["x_m"], dtype=float)
    matched_times = np.asarray(fvm_history["time_s"], dtype=float)
    field_rows: list[dict[str, Any]] = []
    analytical_rows: list[dict[str, Any]] = []
    field_metrics: list[dict[str, Any]] = []

    for time_index, (time_value, sample) in enumerate(
        zip(matched_times, matched_plan)
    ):
        analytical = evaluate_gaussian_reference(
            x,
            float(time_value),
            length_m=cfg.pipe_length_m,
            rho0_kg_m3=rho0,
            c0_m_s=c0,
            amplitude_pa=cfg.pressure_amplitude_pa,
            center_m=cfg.pulse_center_m,
            sigma_m=cfg.pulse_sigma_m,
            direction="right_going",
            left_boundary="transmissive",
            right_boundary="rigid_wall",
        )
        keys = (
            "pressure_perturbation_pa",
            "velocity_m_s",
            "a_plus_pa",
            "a_minus_pa",
        )
        moc_fields = {
            key: sample_spacetime_history(
                moc_history["time_s"],
                moc_history["x_m"],
                moc_history[key],
                np.full(x.shape, time_value),
                x,
            )
            for key in keys
        }
        fvm_fields = {
            key: np.asarray(fvm_history[key][time_index], dtype=float)
            for key in keys
        }
        analytical_fields = {key: np.asarray(analytical[key], dtype=float) for key in keys}
        metrics_at_time: dict[str, Any] = {
            "sample_id": sample["sample_id"],
            "time_s": float(time_value),
            "path_travel_m": float(sample["path_travel_m"]),
            "phase": sample["phase"],
            "expected_center_x_m": float(sample["expected_center_x_m"]),
            "fvm": {},
            "moc": {},
        }
        characteristic_normalizer = np.asarray(
            analytical_fields["pressure_perturbation_pa"],
            dtype=float,
        )
        for implementation, fields in (("fvm", fvm_fields), ("moc", moc_fields)):
            for key in keys:
                normalizer = (
                    characteristic_normalizer
                    if key in {"a_plus_pa", "a_minus_pa"}
                    else analytical_fields[key]
                )
                metrics_at_time[implementation][key] = normalized_error_norms(
                    x,
                    fields[key],
                    analytical_fields[key],
                    normalization_reference=normalizer,
                )
            metrics_at_time[implementation]["pressure_peak"] = _absolute_peak_metrics(
                x,
                fields["pressure_perturbation_pa"],
                analytical_fields["pressure_perturbation_pa"],
            )
            metrics_at_time[implementation]["velocity_peak"] = _absolute_peak_metrics(
                x,
                fields["velocity_m_s"],
                analytical_fields["velocity_m_s"],
            )
            if sample["phase"] == "incident":
                dominant = float(np.max(np.abs(fields["a_plus_pa"])))
                opposite = float(np.max(np.abs(fields["a_minus_pa"])))
            elif sample["phase"] == "reflected":
                dominant = float(np.max(np.abs(fields["a_minus_pa"])))
                opposite = float(np.max(np.abs(fields["a_plus_pa"])))
            else:
                dominant = float(
                    max(
                        np.max(np.abs(fields["a_plus_pa"])),
                        np.max(np.abs(fields["a_minus_pa"])),
                    )
                )
                opposite = 0.0
            metrics_at_time[implementation]["opposite_direction_leakage_ratio"] = (
                float(opposite / dominant) if dominant > 0.0 else 0.0
            )
            energy = acoustic_energy_proxy(
                x,
                fields["pressure_perturbation_pa"],
                fields["velocity_m_s"],
                rho0_kg_m3=rho0,
                c0_m_s=c0,
            )
            metrics_at_time[implementation]["acoustic_energy_proxy"] = energy
        analytical_energy = acoustic_energy_proxy(
            x,
            analytical_fields["pressure_perturbation_pa"],
            analytical_fields["velocity_m_s"],
            rho0_kg_m3=rho0,
            c0_m_s=c0,
        )
        metrics_at_time["analytical_acoustic_energy_proxy"] = analytical_energy
        for implementation in ("fvm", "moc"):
            energy = metrics_at_time[implementation]["acoustic_energy_proxy"]
            metrics_at_time[implementation][
                "acoustic_energy_relative_difference"
            ] = (
                float((energy - analytical_energy) / analytical_energy)
                if analytical_energy != 0.0
                else None
            )
        field_metrics.append(metrics_at_time)

        for index, x_value in enumerate(x):
            row = {
                "sample_id": sample["sample_id"],
                "phase": sample["phase"],
                "path_travel_m": float(sample["path_travel_m"]),
                "time_s": float(time_value),
                "x_m": float(x_value),
                "fvm_pressure_perturbation_pa": float(
                    fvm_fields["pressure_perturbation_pa"][index]
                ),
                "moc_pressure_perturbation_pa": float(
                    moc_fields["pressure_perturbation_pa"][index]
                ),
                "analytical_pressure_perturbation_pa": float(
                    analytical_fields["pressure_perturbation_pa"][index]
                ),
                "fvm_velocity_m_s": float(fvm_fields["velocity_m_s"][index]),
                "moc_velocity_m_s": float(moc_fields["velocity_m_s"][index]),
                "analytical_velocity_m_s": float(
                    analytical_fields["velocity_m_s"][index]
                ),
                "fvm_a_plus_pa": float(fvm_fields["a_plus_pa"][index]),
                "moc_a_plus_pa": float(moc_fields["a_plus_pa"][index]),
                "analytical_a_plus_pa": float(analytical_fields["a_plus_pa"][index]),
                "fvm_a_minus_pa": float(fvm_fields["a_minus_pa"][index]),
                "moc_a_minus_pa": float(moc_fields["a_minus_pa"][index]),
                "analytical_a_minus_pa": float(
                    analytical_fields["a_minus_pa"][index]
                ),
            }
            field_rows.append(row)
            analytical_rows.append(
                {
                    "sample_id": sample["sample_id"],
                    "phase": sample["phase"],
                    "path_travel_m": float(sample["path_travel_m"]),
                    "time_s": float(time_value),
                    "x_m": float(x_value),
                    "pressure_perturbation_pa": row[
                        "analytical_pressure_perturbation_pa"
                    ],
                    "velocity_m_s": row["analytical_velocity_m_s"],
                    "a_plus_pa": row["analytical_a_plus_pa"],
                    "a_minus_pa": row["analytical_a_minus_pa"],
                }
            )

    probe_comparison_rows: list[dict[str, Any]] = []
    probe_metrics: list[dict[str, Any]] = []
    for probe in probe_specs:
        probe_id = str(probe["probe_id"])
        rows = [row for row in fvm_probe_rows if row["probe_id"] == probe_id]
        times = np.asarray([row["time_s"] for row in rows], dtype=float)
        probe_x = float(probe["probe_x_m"])
        fvm_fields = {
            "pressure_perturbation_pa": np.asarray(
                [row["pressure_perturbation_pa"] for row in rows], dtype=float
            ),
            "velocity_m_s": np.asarray(
                [row["velocity_m_s"] for row in rows], dtype=float
            ),
            "a_plus_pa": np.asarray([row["a_plus_pa"] for row in rows], dtype=float),
            "a_minus_pa": np.asarray([row["a_minus_pa"] for row in rows], dtype=float),
        }
        analytical_samples = [
            evaluate_gaussian_reference(
                np.asarray([probe_x]),
                float(time_value),
                length_m=cfg.pipe_length_m,
                rho0_kg_m3=rho0,
                c0_m_s=c0,
                amplitude_pa=cfg.pressure_amplitude_pa,
                center_m=cfg.pulse_center_m,
                sigma_m=cfg.pulse_sigma_m,
                direction="right_going",
                left_boundary="transmissive",
                right_boundary="rigid_wall",
            )
            for time_value in times
        ]
        analytical_fields = {
            key: np.asarray([sample[key][0] for sample in analytical_samples], dtype=float)
            for key in (
                "pressure_perturbation_pa",
                "velocity_m_s",
                "a_plus_pa",
                "a_minus_pa",
            )
        }
        moc_fields = {
            key: sample_spacetime_history(
                moc_history["time_s"],
                moc_history["x_m"],
                moc_history[key],
                times,
                np.full(times.shape, probe_x),
            )
            for key in (
                "pressure_perturbation_pa",
                "velocity_m_s",
                "a_plus_pa",
                "a_minus_pa",
            )
        }
        implementations = {
            "fvm": fvm_fields,
            "moc": moc_fields,
            "analytical": analytical_fields,
        }
        metrics_by_implementation = {
            name: _reflection_metrics_for_signal(
                times,
                fields["a_plus_pa"],
                fields["a_minus_pa"],
                fields["velocity_m_s"],
                probe,
            )
            for name, fields in implementations.items()
        }
        analytical_p50 = metrics_by_implementation["analytical"].get(
            "reflected_p50_time_s"
        )
        for name in ("fvm", "moc"):
            value = metrics_by_implementation[name].get("reflected_p50_time_s")
            metrics_by_implementation[name]["reflected_p50_offset_s"] = (
                float(value - analytical_p50)
                if value is not None and analytical_p50 is not None
                else None
            )
        probe_metrics.append(
            {
                "probe_id": probe_id,
                "probe_target_x_m": float(probe["probe_target_x_m"]),
                "probe_x_m": probe_x,
                "timing": {
                    key: value
                    for key, value in probe.items()
                    if "time_s" in key
                    or "window" in key
                    or key.startswith("theoretical_")
                    or key == "evaluation_window_contaminated"
                },
                "implementations": metrics_by_implementation,
            }
        )
        for index, time_value in enumerate(times):
            probe_comparison_rows.append(
                {
                    "probe_id": probe_id,
                    "probe_x_m": probe_x,
                    "time_s": float(time_value),
                    "fvm_pressure_perturbation_pa": float(
                        fvm_fields["pressure_perturbation_pa"][index]
                    ),
                    "moc_pressure_perturbation_pa": float(
                        moc_fields["pressure_perturbation_pa"][index]
                    ),
                    "analytical_pressure_perturbation_pa": float(
                        analytical_fields["pressure_perturbation_pa"][index]
                    ),
                    "fvm_velocity_m_s": float(fvm_fields["velocity_m_s"][index]),
                    "moc_velocity_m_s": float(moc_fields["velocity_m_s"][index]),
                    "analytical_velocity_m_s": float(
                        analytical_fields["velocity_m_s"][index]
                    ),
                    "fvm_a_plus_pa": float(fvm_fields["a_plus_pa"][index]),
                    "moc_a_plus_pa": float(moc_fields["a_plus_pa"][index]),
                    "analytical_a_plus_pa": float(
                        analytical_fields["a_plus_pa"][index]
                    ),
                    "fvm_a_minus_pa": float(fvm_fields["a_minus_pa"][index]),
                    "moc_a_minus_pa": float(moc_fields["a_minus_pa"][index]),
                    "analytical_a_minus_pa": float(
                        analytical_fields["a_minus_pa"][index]
                    ),
                }
            )

    fvm_sign_pass = all(
        item["implementations"]["fvm"].get("expected_pressure_sign_observed") is True
        and item["implementations"]["fvm"].get("expected_velocity_sign_observed") is True
        for item in probe_metrics
    )
    comparison = {
        "verification_item": "V-013B",
        "case_role": "rigid_wall_reflection",
        "field_metrics": field_metrics,
        "probe_reflection_metrics": probe_metrics,
        "boundary_metrics": fvm_metrics["boundary_metrics"],
        "formal_fvm_regression_band_applied": False,
        "time_shift_applied": False,
        "parameter_tuning_applied": False,
        "moc_is_truth": False,
        "finest_mesh_is_exact_solution": False,
        "expected_pressure_reflection_coefficient": 1.0,
        "expected_velocity_reflection_coefficient": -1.0,
        "fvm_expected_reflection_signs_observed": fvm_sign_pass,
        "comparison_analysis_complete": bool(
            len(field_metrics) == len(matched_plan)
            and len(probe_metrics) == len(probe_specs)
        ),
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
    }
    return comparison, field_rows, analytical_rows, probe_comparison_rows


def _summary_row(
    case_id: str,
    n_cells: int,
    fvm_metrics: Mapping[str, Any],
    moc_metrics: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    probes = comparison["probe_reflection_metrics"]
    fvm_coefficients = [
        item["implementations"]["fvm"].get("pressure_reflection_coefficient")
        for item in probes
    ]
    fvm_velocity_coefficients = [
        item["implementations"]["fvm"].get("velocity_reflection_coefficient")
        for item in probes
    ]
    valid_pressure = [float(value) for value in fvm_coefficients if value is not None]
    valid_velocity = [float(value) for value in fvm_velocity_coefficients if value is not None]
    field_metrics = comparison["field_metrics"]
    max_pressure_l2 = max(
        float(item["fvm"]["pressure_perturbation_pa"]["l2_relative"])
        for item in field_metrics
    )
    max_velocity_l2 = max(
        float(item["fvm"]["velocity_m_s"]["l2_relative"])
        for item in field_metrics
    )
    return {
        "case_id": case_id,
        "verification_item": "V-013B",
        "n_cells": int(n_cells),
        "dx_m": float(fvm_metrics["dx_m"]),
        "fvm_cfl": float(fvm_metrics["cfl_target"]),
        "moc_cfl": float(moc_metrics["cfl"]),
        "execution_pass": bool(
            fvm_metrics["overall_fvm_health_pass"]
            and moc_metrics["overall_moc_reference_pass"]
            and comparison["comparison_analysis_complete"]
            and comparison["fvm_expected_reflection_signs_observed"]
        ),
        "fvm_health_pass": bool(fvm_metrics["overall_fvm_health_pass"]),
        "moc_reference_pass": bool(moc_metrics["overall_moc_reference_pass"]),
        "fvm_expected_reflection_signs_observed": bool(
            comparison["fvm_expected_reflection_signs_observed"]
        ),
        "mean_fvm_pressure_reflection_coefficient": (
            float(np.mean(valid_pressure)) if valid_pressure else None
        ),
        "mean_fvm_velocity_reflection_coefficient": (
            float(np.mean(valid_velocity)) if valid_velocity else None
        ),
        "max_fvm_pressure_l2_relative": max_pressure_l2,
        "max_fvm_velocity_l2_relative": max_velocity_l2,
        "max_abs_wall_velocity_m_s": fvm_metrics["boundary_metrics"].get(
            "max_abs_wall_velocity_m_s"
        ),
        "wall_pressure_amplification_ratio": fvm_metrics["boundary_metrics"].get(
            "wall_pressure_amplification_ratio"
        ),
        "coolprop_version": fvm_metrics["coolprop_version"],
        "property_backend_design_status": fvm_metrics[
            "property_backend_design_status"
        ],
    }


def _write_report(
    path: Path,
    cfg: V013RigidWallReflectionConfig,
    metrics: Mapping[str, Any],
) -> None:
    lines = [
        "# V-013B Rigid-Wall Reflection Observation",
        "",
        "This is a software / numerical verification observation only.",
        "",
        f"- status: {metrics['status']}",
        f"- planned / executed runs: {metrics['planned_run_count']} / {metrics['executed_run_count']}",
        f"- overall execution pass: {metrics['overall_execution_pass']}",
        f"- pulse: {cfg.pressure_amplitude_pa:g} Pa Gaussian at x0={cfg.pulse_center_m:g} m, sigma={cfg.pulse_sigma_m:g} m",
        "- right boundary: rigid wall",
        "- expected pressure / velocity reflection coefficients: +1 / -1",
        "- physical Validation: false",
        "- design-use acceptance: false",
        "- property backend design status: not_approved_for_design_use",
        "- formal FVM regression band applied: false",
        "- production solver behaviour changed: false",
        "",
        "The finest mesh is not an exact solution. Numerical differences are recorded as observations.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_v013_rigid_wall_observation(
    output_dir: str | Path | None = None,
    config: V013RigidWallReflectionConfig | None = None,
) -> dict[str, Any]:
    """Execute the fixed V-013B rigid-wall observation matrix."""

    cfg = config or V013RigidWallReflectionConfig()
    base = (
        Path(output_dir)
        if output_dir is not None
        else Path(tempfile.mkdtemp(prefix="v013b_rigid_wall_"))
    )
    base.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    plan = build_run_plan(cfg)
    _write_json(base / "v013b_config.json", asdict(cfg))
    _write_json(base / "v013b_run_plan.json", plan)

    run_records: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    reference_constants: dict[str, Any] | None = None
    top_matched_plan: list[dict[str, Any]] | None = None
    top_probe_plan: list[dict[str, Any]] | None = None

    for item in plan:
        case_id = str(item["case_id"])
        n_cells = int(item["n_cells"])
        run_dir = base / case_id
        run_dir.mkdir(parents=True, exist_ok=True)

        (
            fvm_metrics,
            fvm_history,
            fvm_probe_rows,
            fvm_boundary_rows,
            source,
        ) = _run_fvm(n_cells, cfg)
        rho0 = float(fvm_metrics["rho0_kg_m3"])
        c0 = float(fvm_metrics["c0_m_s"])
        matched_plan = list(source["matched_sample_plan"])
        probe_specs = list(source["probes"])

        if reference_constants is None:
            reference_constants = {
                "p0_pa": cfg.initial_pressure_pa,
                "T0_K": cfg.initial_temperature_K,
                "rho0_kg_m3": rho0,
                "c0_m_s": c0,
                "rho0_provenance": fvm_metrics["rho0_provenance"],
                "c0_provenance": fvm_metrics["c0_provenance"],
                "property_backend_name_fvm": "coolprop_co2",
                "coolprop_version": fvm_metrics["coolprop_version"],
                "property_backend_design_status": (
                    "not_approved_for_design_use"
                ),
                "moc_calls_coolprop": False,
            }
            top_matched_plan = matched_plan
            top_probe_plan = probe_specs
        else:
            if not math.isclose(
                rho0,
                float(reference_constants["rho0_kg_m3"]),
                rel_tol=0.0,
                abs_tol=1.0e-10,
            ) or not math.isclose(
                c0,
                float(reference_constants["c0_m_s"]),
                rel_tol=0.0,
                abs_tol=1.0e-10,
            ):
                raise RuntimeError("rho0/c0 changed across the V-013B mesh matrix")

        reference_cfg, moc_history, moc_metrics = _run_moc(
            n_cells,
            cfg,
            rho0=rho0,
            c0=c0,
        )
        (
            comparison,
            matched_rows,
            analytical_rows,
            probe_comparison_rows,
        ) = _compare_run(
            cfg,
            fvm_metrics,
            fvm_history,
            fvm_probe_rows,
            moc_history,
            matched_plan,
            probe_specs,
        )

        _write_json(run_dir / "fvm_config.json", source["source_config"])
        _write_json(run_dir / "fvm_metrics.json", fvm_metrics)
        _write_csv(run_dir / "fvm_probe_history.csv", fvm_probe_rows)
        write_boundary_history_csv(
            run_dir / "fvm_boundary_history.csv",
            fvm_boundary_rows,
        )
        np.savez_compressed(run_dir / "fvm_field_history.npz", **fvm_history)
        _write_json(run_dir / "moc_config.json", asdict(reference_cfg))
        _write_json(run_dir / "moc_metrics.json", moc_metrics)
        np.savez_compressed(
            run_dir / "moc_history.npz",
            x_m=moc_history["x_m"],
            time_s=moc_history["time_s"],
            a_plus_pa=moc_history["a_plus_pa"],
            a_minus_pa=moc_history["a_minus_pa"],
            pressure_perturbation_pa=moc_history["pressure_perturbation_pa"],
            velocity_m_s=moc_history["velocity_m_s"],
        )
        _write_csv(run_dir / "analytical_samples.csv", analytical_rows)
        _write_csv(run_dir / "matched_samples.csv", matched_rows)
        _write_csv(run_dir / "probe_comparison.csv", probe_comparison_rows)
        _write_json(run_dir / "comparison_metrics.json", comparison)

        summary = _summary_row(
            case_id,
            n_cells,
            fvm_metrics,
            moc_metrics,
            comparison,
        )
        summary_rows.append(summary)
        run_records.append(
            {
                **item,
                "fvm_metrics_path": f"{case_id}/fvm_metrics.json",
                "moc_metrics_path": f"{case_id}/moc_metrics.json",
                "comparison_metrics_path": f"{case_id}/comparison_metrics.json",
                "summary": summary,
            }
        )

    if reference_constants is None or top_matched_plan is None or top_probe_plan is None:
        raise RuntimeError("V-013B run plan was empty")

    _write_json(base / "v013b_reference_constants.json", reference_constants)
    _write_json(base / "v013b_matched_sample_plan.json", top_matched_plan)
    _write_json(base / "v013b_probe_plan.json", top_probe_plan)
    _write_csv(base / "v013b_summary.csv", summary_rows)

    overall_pass = bool(
        len(run_records) == len(plan)
        and all(bool(row["execution_pass"]) for row in summary_rows)
    )
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "verification_item": "V-013B",
        "status": "EXECUTED; OBSERVATION REVIEW PENDING",
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "formal_fvm_regression_band_applied": False,
        "property_backend_name": "coolprop_co2",
        "property_backend_design_status": "not_approved_for_design_use",
        "coolprop_version": reference_constants["coolprop_version"],
        "reference_calls_coolprop": False,
        "production_solver_behavior_changed": False,
        "planned_run_count": len(plan),
        "executed_run_count": len(run_records),
        "run_plan": plan,
        "runs": run_records,
        "summary_rows": summary_rows,
        "overall_execution_pass": overall_pass,
        "aggregate_analysis_complete": bool(len(summary_rows) == len(plan)),
        "comparison_plots_complete": False,
        "generated_plots": [],
        "plotting_errors": {},
        "runtime_s": float(time.perf_counter() - start),
        "moc_is_truth": False,
        "finest_mesh_is_exact_solution": False,
        "limitations": [
            "analytical path solves the specified linearized constant-coefficient PDE",
            "MOC is an independent numerical reference, not physical truth",
            "finest FVM or MOC mesh is not an exact solution",
            "no V-013B FVM CI-light band is applied before observation review",
            "plots are a later saved-artifact increment",
            "not physical Validation or design-use acceptance",
        ],
    }
    _write_json(base / "v013b_metrics.json", metrics)
    _write_report(base / "v013b_observation_report.md", cfg, metrics)
    _write_json(
        base / "v013b_plot_metrics.json",
        {
            "verification_item": "V-013B",
            "plot_count": 0,
            "expected_plot_count": EXPECTED_PLOT_COUNT,
            "plotting_status": "PENDING_SAVED_ARTIFACT_PLOTTER_INCREMENT",
            "solver_rerun": False,
            "numerical_results_changed": False,
        },
    )
    return metrics


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--mesh-cells",
        nargs="+",
        type=int,
        default=None,
        help="Override the default 100/200/400 observation matrix.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = V013RigidWallReflectionConfig(
        fvm_mesh_cells=(
            tuple(args.mesh_cells)
            if args.mesh_cells is not None
            else V013RigidWallReflectionConfig().fvm_mesh_cells
        )
    )
    result = run_v013_rigid_wall_observation(args.output_dir, cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall_execution_pass"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "EXPECTED_PLOT_COUNT",
    "leading_fraction_crossings",
    "normalized_error_norms",
    "run_v013_rigid_wall_observation",
    "sample_spacetime_history",
]
