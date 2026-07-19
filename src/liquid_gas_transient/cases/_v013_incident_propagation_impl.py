"""V-013A incident-wave FVM / MOC / analytical cross verification.

This module connects the existing CoolProp small-amplitude FVM source case to the
independent linear-acoustic reference core.  It is software / numerical verification
only.  It is not physical Validation, design-use acceptance, or a production MOC
solver.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import csv
import json
import math
from pathlib import Path
import tempfile
import time
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .coolprop_small_amplitude_wave import (
    CoolPropSmallAmplitudeWaveConfig,
    build_coolprop_small_amplitude_wave_solver,
    build_initial_gaussian_pulse,
)
from ..verification.linear_acoustic_reference import (
    LinearAcousticReferenceConfig,
    acoustic_energy_proxy,
    characteristics_from_pressure_velocity,
    evaluate_gaussian_reference,
    initialize_moc_characteristics,
    make_gaussian_profile,
    run_moc_reference,
)


@dataclass(frozen=True)
class V013IncidentPropagationConfig:
    """Fixed observation configuration for Stage 7 / V-013A."""

    case_name: str = "v013a_incident_propagation"
    output_version: str = "v013a_incident_propagation_v1"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_amplitude_pa: float = 100.0
    pulse_center_fraction: float = 0.20
    pulse_sigma_fraction: float = 0.02
    probe_fractions: tuple[float, ...] = (0.35, 0.50, 0.65, 0.80)
    fvm_mesh_cells: tuple[int, ...] = (100, 200, 400)
    fvm_cfl: float = 0.5
    moc_cfl: float = 1.0
    matched_center_travel_m: tuple[float, ...] = (0.0, 20.0, 40.0, 60.0, 65.0)
    max_steps: int = 30000
    generate_plots: bool = True
    validation: bool = False
    design_evaluation: bool = False
    acceptance_gate: bool = False

    def __post_init__(self) -> None:
        if not self.case_name:
            raise ValueError("case_name must not be empty")
        if self.pipe_length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe geometry must be positive")
        if self.initial_pressure_pa <= 0.0 or self.initial_temperature_K <= 0.0:
            raise ValueError("initial state must be positive")
        if self.pressure_amplitude_pa <= 0.0:
            raise ValueError("pressure_amplitude_pa must be positive")
        if self.pressure_amplitude_pa / self.initial_pressure_pa > 1.0e-4:
            raise ValueError("V-013A pressure perturbation must remain in the linear guardrail")
        if not 0.0 < self.pulse_center_fraction < 1.0:
            raise ValueError("pulse_center_fraction must be in (0, 1)")
        if self.pulse_sigma_fraction <= 0.0:
            raise ValueError("pulse_sigma_fraction must be positive")
        if tuple(sorted(set(self.fvm_mesh_cells))) != self.fvm_mesh_cells:
            raise ValueError("fvm_mesh_cells must be unique and ascending")
        if any(n < 20 for n in self.fvm_mesh_cells):
            raise ValueError("each FVM mesh must contain at least 20 cells")
        if not 0.0 < self.fvm_cfl <= 1.0:
            raise ValueError("fvm_cfl must be in (0, 1]")
        if self.moc_cfl != 1.0:
            raise ValueError("the independent nodal MOC translator is fixed at CFL=1")
        if not self.probe_fractions or any(
            p <= self.pulse_center_fraction or p >= 1.0 for p in self.probe_fractions
        ):
            raise ValueError("probe fractions must lie right of the pulse center and inside the pipe")
        if tuple(sorted(set(self.matched_center_travel_m))) != self.matched_center_travel_m:
            raise ValueError("matched_center_travel_m must be unique and ascending")
        if not self.matched_center_travel_m or self.matched_center_travel_m[0] != 0.0:
            raise ValueError("matched_center_travel_m must start at zero")
        x0 = self.pulse_center_fraction * self.pipe_length_m
        sigma = self.pulse_sigma_fraction * self.pipe_length_m
        final_center = x0 + self.matched_center_travel_m[-1]
        if final_center + 5.0 * sigma >= self.pipe_length_m:
            raise ValueError("final matched sample is too close to the right boundary")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.validation or self.design_evaluation or self.acceptance_gate:
            raise ValueError("V-013A validation/design/acceptance flags must remain false")
        for n in self.fvm_mesh_cells:
            dx = self.pipe_length_m / n
            for distance in self.matched_center_travel_m:
                if not math.isclose(distance / dx, round(distance / dx), abs_tol=1.0e-10):
                    raise ValueError(
                        "matched center travel distances must align with every MOC grid"
                    )


def _float_token(value: float) -> str:
    text = format(float(value), ".12g")
    return text.replace("-", "m").replace(".", "p").replace("+", "")


def case_id_for(n_cells: int, fvm_cfl: float = 0.5, moc_cfl: float = 1.0) -> str:
    if isinstance(n_cells, bool) or int(n_cells) < 1:
        raise ValueError("n_cells must be a positive integer")
    return (
        f"v013a_n{int(n_cells):04d}_"
        f"fvmcfl{_float_token(fvm_cfl)}_moccfl{_float_token(moc_cfl)}"
    )


def build_run_plan(
    config: V013IncidentPropagationConfig | None = None,
) -> list[dict[str, Any]]:
    cfg = config or V013IncidentPropagationConfig()
    return [
        {
            "case_id": case_id_for(n, cfg.fvm_cfl, cfg.moc_cfl),
            "verification_item": "V-013A",
            "case_role": "incident_propagation",
            "n_cells": int(n),
            "fvm_cfl": float(cfg.fvm_cfl),
            "moc_cfl": float(cfg.moc_cfl),
            "comparison_groups": ["mesh_comparison", "fvm_moc_analytical"],
        }
        for n in cfg.fvm_mesh_cells
    ]


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
        json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
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


def normalized_error_norms(
    x_m: ArrayLike,
    candidate: ArrayLike,
    reference: ArrayLike,
    *,
    normalization_reference: ArrayLike | None = None,
) -> dict[str, float]:
    """Return normalized L1/L2/Linf and absolute Linf errors on a fixed grid."""

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
    l1_num = float(np.trapezoid(np.abs(diff), x))
    l2_num = float(math.sqrt(np.trapezoid(diff * diff, x)))
    linf_num = float(np.max(np.abs(diff)))
    l1_den = float(np.trapezoid(np.abs(scale), x))
    l2_den = float(math.sqrt(np.trapezoid(scale * scale, x)))
    linf_den = float(np.max(np.abs(scale)))
    floor = np.finfo(float).tiny
    return {
        "l1_relative": 0.0 if l1_num == 0.0 else l1_num / max(l1_den, floor),
        "l2_relative": 0.0 if l2_num == 0.0 else l2_num / max(l2_den, floor),
        "linf_relative": 0.0 if linf_num == 0.0 else linf_num / max(linf_den, floor),
        "linf_absolute": linf_num,
    }


def leading_fraction_crossings(
    time_s: ArrayLike,
    signal: ArrayLike,
    fractions: Iterable[float] = (0.1, 0.5, 0.9),
) -> dict[str, Any]:
    """Detect rising-side local-peak fraction crossings with linear interpolation."""

    t = np.asarray(time_s, dtype=float)
    y = np.asarray(signal, dtype=float)
    requested = tuple(float(f) for f in fractions)
    if t.ndim != 1 or y.shape != t.shape or t.size < 3:
        raise ValueError("time and signal must be matching 1-D arrays with at least 3 samples")
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(y)) or np.any(np.diff(t) <= 0):
        raise ValueError("time and signal must be finite and time strictly increasing")
    if any(not 0.0 < f < 1.0 for f in requested):
        raise ValueError("crossing fractions must be in (0, 1)")
    adjusted = y - y[0]
    peak_index = int(np.argmax(adjusted))
    peak = float(adjusted[peak_index])
    out: dict[str, Any] = {
        "detected": bool(peak_index > 0 and peak > 0.0),
        "baseline": float(y[0]),
        "peak": peak,
        "peak_time_s": float(t[peak_index]),
        "crossing_times_s": {},
    }
    if not out["detected"]:
        return out
    for fraction in requested:
        threshold = fraction * peak
        crossing: float | None = None
        for i in range(peak_index):
            y0 = adjusted[i]
            y1 = adjusted[i + 1]
            if y0 < threshold <= y1 and t[i + 1] > t[i]:
                weight = 0.0 if y1 == y0 else (threshold - y0) / (y1 - y0)
                crossing = float(t[i] + weight * (t[i + 1] - t[i]))
                break
        out["crossing_times_s"][f"p{int(round(100 * fraction)):02d}"] = crossing
    return out


def sample_spacetime_history(
    history_time_s: ArrayLike,
    history_x_m: ArrayLike,
    history_values: ArrayLike,
    query_time_s: ArrayLike,
    query_x_m: ArrayLike,
) -> NDArray[np.float64]:
    """Sample a time-space history by fixed linear time and space interpolation."""

    times = np.asarray(history_time_s, dtype=float)
    x = np.asarray(history_x_m, dtype=float)
    values = np.asarray(history_values, dtype=float)
    qt, qx = np.broadcast_arrays(
        np.asarray(query_time_s, dtype=float), np.asarray(query_x_m, dtype=float)
    )
    if times.ndim != 1 or x.ndim != 1 or values.shape != (times.size, x.size):
        raise ValueError("history_values must have shape (len(time), len(x))")
    if times.size < 2 or x.size < 2 or np.any(np.diff(times) <= 0) or np.any(np.diff(x) <= 0):
        raise ValueError("history axes must be strictly increasing")
    if not (
        np.all(np.isfinite(times))
        and np.all(np.isfinite(x))
        and np.all(np.isfinite(values))
        and np.all(np.isfinite(qt))
        and np.all(np.isfinite(qx))
    ):
        raise ValueError("history and query samples must be finite")
    if np.any(qt < times[0]) or np.any(qt > times[-1]):
        raise ValueError("query times lie outside the history")
    if np.any(qx < x[0]) or np.any(qx > x[-1]):
        raise ValueError("query positions lie outside the history")
    flat_t = qt.ravel()
    flat_x = qx.ravel()
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


def _fitted_speed(probe_rows: Sequence[Mapping[str, Any]], key: str, c0: float) -> dict[str, Any]:
    usable = [
        (float(row["probe_x_m"]), float(row[key]))
        for row in probe_rows
        if row.get(key) is not None and math.isfinite(float(row[key]))
    ]
    if len(usable) < 2:
        return {
            "detected": False,
            "speed_m_s": None,
            "relative_error": None,
            "sample_count": len(usable),
        }
    x = np.asarray([item[0] for item in usable], dtype=float)
    t = np.asarray([item[1] for item in usable], dtype=float)
    slope, intercept = np.polyfit(t, x, 1)
    return {
        "detected": bool(slope > 0.0),
        "speed_m_s": float(slope),
        "relative_error": float(abs(slope - c0) / c0),
        "intercept_m": float(intercept),
        "sample_count": int(len(usable)),
    }


def _sample_fvm_state(
    solver: Any,
    cfg: CoolPropSmallAmplitudeWaveConfig,
    rho0: float,
    c0: float,
) -> dict[str, NDArray[np.float64]]:
    prim = solver.primitive()
    pressure = np.asarray(prim.p, dtype=float) - cfg.initial_pressure_pa
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


def _probe_specs(
    x_m: NDArray[np.float64], cfg: V013IncidentPropagationConfig
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for fraction in cfg.probe_fractions:
        target = fraction * cfg.pipe_length_m
        index = int(np.argmin(np.abs(x_m - target)))
        specs.append(
            {
                "probe_id": f"x_over_L_{fraction:g}",
                "probe_fraction": float(fraction),
                "probe_target_x_m": float(target),
                "probe_index": index,
                "probe_x_m": float(x_m[index]),
            }
        )
    return specs


def _run_fvm(
    n_cells: int,
    cfg: V013IncidentPropagationConfig,
) -> tuple[dict[str, Any], dict[str, NDArray[np.float64]], list[dict[str, Any]], dict[str, Any]]:
    source_cfg = CoolPropSmallAmplitudeWaveConfig(
        case_name="v013a_fvm_incident",
        output_version="v013a_fvm_incident_v1",
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
    )
    initial = build_initial_gaussian_pulse(source_cfg)
    solver = build_coolprop_small_amplitude_wave_solver(source_cfg)
    reference = initial["reference"]
    rho0 = float(reference["rho0"])
    c0 = float(reference["c0"])
    x = np.asarray(solver.grid.cell_centers, dtype=float)
    matched_times = np.asarray(cfg.matched_center_travel_m, dtype=float) / c0
    probes = _probe_specs(x, cfg)
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
        state = _sample_fvm_state(solver, source_cfg, rho0, c0)
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
        extrema["max_alpha"] = max(extrema["max_alpha"], float(np.max(state["alpha"])))
        for probe in probes:
            i = int(probe["probe_index"])
            probe_rows.append(
                {
                    "time_s": float(solver.t),
                    "step": int(solver.step_count),
                    "dt_s": float(dt_s),
                    **probe,
                    "pressure_perturbation_pa": float(
                        state["pressure_perturbation_pa"][i]
                    ),
                    "velocity_m_s": float(state["velocity_m_s"][i]),
                    "a_plus_pa": float(state["a_plus_pa"][i]),
                    "a_minus_pa": float(state["a_minus_pa"][i]),
                }
            )
        return state

    state = capture_step(0.0)
    for key in field_samples:
        field_samples[key].append(np.array(state[key], dtype=float, copy=True))

    for target_time in matched_times[1:]:
        while solver.t < float(target_time) - 1.0e-14:
            if solver.step_count >= cfg.max_steps:
                raise RuntimeError("V-013A FVM run exceeded max_steps")
            dt = float(solver.compute_dt(float(target_time)))
            if not math.isfinite(dt) or dt <= 0.0:
                raise RuntimeError("V-013A FVM produced a non-positive timestep")
            solver.step(dt)
            dt_history.append(dt)
            state = capture_step(dt)
        if not math.isclose(solver.t, float(target_time), rel_tol=0.0, abs_tol=2.0e-13):
            raise RuntimeError("FVM did not land on a prescribed matched-sample time")
        for key in field_samples:
            field_samples[key].append(np.array(state[key], dtype=float, copy=True))

    field_history = {
        "time_s": matched_times,
        "x_m": x,
        **{key: np.vstack(values) for key, values in field_samples.items()},
    }
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
    )
    metrics = {
        "implementation": "fvm",
        "source_case": "coolprop_small_amplitude_wave",
        "source_builder": (
            "build_initial_gaussian_pulse + build_coolprop_small_amplitude_wave_solver"
        ),
        "solver_physics_changed": False,
        "n_cells": int(n_cells),
        "dx_m": float(solver.grid.dx),
        "cfl_target": float(cfg.fvm_cfl),
        "final_time_s": float(solver.t),
        "target_time_s": float(matched_times[-1]),
        "reached_target_time": bool(
            math.isclose(solver.t, matched_times[-1], rel_tol=0.0, abs_tol=2.0e-13)
        ),
        "step_count": int(solver.step_count),
        "min_positive_dt_s": float(min(dt_history)) if dt_history else 0.0,
        "max_dt_s": float(max(dt_history)) if dt_history else 0.0,
        "probe_sample_count": len(probe_rows),
        "field_sample_count": int(matched_times.size),
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
        "rho0_kg_m3": rho0,
        "c0_m_s": c0,
        "rho0_provenance": (
            "CoolPropCO2Backend.density_from_pT at the recorded p0/T0 source state"
        ),
        "c0_provenance": (
            "LCO2PropertyEOSAdapter primitive sound speed at the recorded uniform source state"
        ),
        "overall_fvm_health_pass": health_pass,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
    }
    source_config = asdict(source_cfg)
    return metrics, field_history, probe_rows, {
        "source_config": source_config,
        "reference": reference,
        "probes": probes,
    }


def _run_moc(
    n_cells: int,
    cfg: V013IncidentPropagationConfig,
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
        right_boundary="transmissive",
    )
    profile = make_gaussian_profile(
        amplitude_pa=cfg.pressure_amplitude_pa,
        center_m=cfg.pulse_center_fraction * cfg.pipe_length_m,
        sigma_m=cfg.pulse_sigma_fraction * cfg.pipe_length_m,
    )
    zero = lambda x: np.zeros_like(x, dtype=float)
    initial_plus, initial_minus = initialize_moc_characteristics(
        reference_cfg,
        initial_a_plus=profile,
        initial_a_minus=zero,
    )
    final_steps = int(round(cfg.matched_center_travel_m[-1] / reference_cfg.dx_m))
    history = run_moc_reference(
        reference_cfg,
        initial_a_plus_pa=initial_plus,
        initial_a_minus_pa=initial_minus,
        n_steps=final_steps,
    )
    max_native_error = 0.0
    for travel_m in cfg.matched_center_travel_m:
        step = int(round(travel_m / reference_cfg.dx_m))
        analytical = evaluate_gaussian_reference(
            history["x_m"],
            float(history["time_s"][step]),
            length_m=cfg.pipe_length_m,
            rho0_kg_m3=rho0,
            c0_m_s=c0,
            amplitude_pa=cfg.pressure_amplitude_pa,
            center_m=cfg.pulse_center_fraction * cfg.pipe_length_m,
            sigma_m=cfg.pulse_sigma_fraction * cfg.pipe_length_m,
            direction="right_going",
            left_boundary="transmissive",
            right_boundary="transmissive",
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
                    np.abs(history["velocity_m_s"][step] - analytical["velocity_m_s"])
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
        "reference_only": True,
        "calls_coolprop": False,
        "production_solver_imported": False,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "overall_moc_reference_pass": bool(
            np.all(np.isfinite(history["pressure_perturbation_pa"]))
            and np.all(np.isfinite(history["velocity_m_s"]))
            and max_native_error <= max(1.0e-10, cfg.pressure_amplitude_pa * 1.0e-12)
        ),
    }
    return reference_cfg, history, metrics


def _peak_metrics(
    x: NDArray[np.float64],
    candidate: NDArray[np.float64],
    reference: NDArray[np.float64],
) -> dict[str, Any]:
    i_candidate = int(np.argmax(candidate))
    i_reference = int(np.argmax(reference))
    peak_candidate = float(candidate[i_candidate])
    peak_reference = float(reference[i_reference])
    return {
        "candidate_peak": peak_candidate,
        "reference_peak": peak_reference,
        "peak_ratio": (
            float(peak_candidate / peak_reference) if peak_reference != 0.0 else None
        ),
        "peak_error": float(peak_candidate - peak_reference),
        "candidate_peak_x_m": float(x[i_candidate]),
        "reference_peak_x_m": float(x[i_reference]),
        "peak_location_error_m": float(x[i_candidate] - x[i_reference]),
    }


def _compare_run(
    cfg: V013IncidentPropagationConfig,
    fvm_metrics: dict[str, Any],
    fvm_history: dict[str, NDArray[np.float64]],
    fvm_probe_rows: list[dict[str, Any]],
    moc_history: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rho0 = float(fvm_metrics["rho0_kg_m3"])
    c0 = float(fvm_metrics["c0_m_s"])
    x = np.asarray(fvm_history["x_m"], dtype=float)
    matched_times = np.asarray(fvm_history["time_s"], dtype=float)
    field_rows: list[dict[str, Any]] = []
    analytical_rows: list[dict[str, Any]] = []
    field_metrics: list[dict[str, Any]] = []
    energy_rows: list[dict[str, Any]] = []

    for time_index, time_value in enumerate(matched_times):
        analytical = evaluate_gaussian_reference(
            x,
            float(time_value),
            length_m=cfg.pipe_length_m,
            rho0_kg_m3=rho0,
            c0_m_s=c0,
            amplitude_pa=cfg.pressure_amplitude_pa,
            center_m=cfg.pulse_center_fraction * cfg.pipe_length_m,
            sigma_m=cfg.pulse_sigma_fraction * cfg.pipe_length_m,
            direction="right_going",
            left_boundary="transmissive",
            right_boundary="transmissive",
        )
        moc_fields = {
            key: sample_spacetime_history(
                moc_history["time_s"],
                moc_history["x_m"],
                moc_history[key],
                np.full(x.shape, time_value),
                x,
            )
            for key in (
                "pressure_perturbation_pa",
                "velocity_m_s",
                "a_plus_pa",
                "a_minus_pa",
            )
        }
        fvm_fields = {
            key: np.asarray(fvm_history[key][time_index], dtype=float)
            for key in (
                "pressure_perturbation_pa",
                "velocity_m_s",
                "a_plus_pa",
                "a_minus_pa",
            )
        }
        analytical_fields = {
            "pressure_perturbation_pa": analytical["pressure_perturbation_pa"],
            "velocity_m_s": analytical["velocity_m_s"],
            "a_plus_pa": analytical["a_plus_pa"],
            "a_minus_pa": analytical["a_minus_pa"],
        }
        metrics_at_time: dict[str, Any] = {
            "time_s": float(time_value),
            "center_travel_m": float(time_value * c0),
            "fvm": {},
            "moc": {},
        }
        for implementation, fields in (("fvm", fvm_fields), ("moc", moc_fields)):
            for key in (
                "pressure_perturbation_pa",
                "velocity_m_s",
                "a_plus_pa",
                "a_minus_pa",
            ):
                normalizer = (
                    analytical_fields["a_plus_pa"]
                    if key == "a_minus_pa"
                    else analytical_fields[key]
                )
                metrics_at_time[implementation][key] = normalized_error_norms(
                    x,
                    fields[key],
                    analytical_fields[key],
                    normalization_reference=normalizer,
                )
            metrics_at_time[implementation]["pressure_peak"] = _peak_metrics(
                x,
                fields["pressure_perturbation_pa"],
                analytical_fields["pressure_perturbation_pa"],
            )
            metrics_at_time[implementation]["velocity_peak"] = _peak_metrics(
                x,
                fields["velocity_m_s"],
                analytical_fields["velocity_m_s"],
            )
            plus_scale = float(np.max(np.abs(fields["a_plus_pa"])))
            metrics_at_time[implementation]["opposite_direction_leakage_ratio"] = (
                float(np.max(np.abs(fields["a_minus_pa"])) / plus_scale)
                if plus_scale > 0.0
                else 0.0
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
            metrics_at_time[implementation]["acoustic_energy_relative_difference"] = (
                float((energy - analytical_energy) / analytical_energy)
                if analytical_energy != 0.0
                else None
            )
        field_metrics.append(metrics_at_time)
        energy_rows.append(
            {
                "time_s": float(time_value),
                "analytical": analytical_energy,
                "fvm": metrics_at_time["fvm"]["acoustic_energy_proxy"],
                "moc": metrics_at_time["moc"]["acoustic_energy_proxy"],
            }
        )
        for i, x_value in enumerate(x):
            row = {
                "time_s": float(time_value),
                "x_m": float(x_value),
                "fvm_pressure_perturbation_pa": float(
                    fvm_fields["pressure_perturbation_pa"][i]
                ),
                "moc_pressure_perturbation_pa": float(
                    moc_fields["pressure_perturbation_pa"][i]
                ),
                "analytical_pressure_perturbation_pa": float(
                    analytical_fields["pressure_perturbation_pa"][i]
                ),
                "fvm_velocity_m_s": float(fvm_fields["velocity_m_s"][i]),
                "moc_velocity_m_s": float(moc_fields["velocity_m_s"][i]),
                "analytical_velocity_m_s": float(
                    analytical_fields["velocity_m_s"][i]
                ),
                "fvm_a_plus_pa": float(fvm_fields["a_plus_pa"][i]),
                "moc_a_plus_pa": float(moc_fields["a_plus_pa"][i]),
                "analytical_a_plus_pa": float(analytical_fields["a_plus_pa"][i]),
                "fvm_a_minus_pa": float(fvm_fields["a_minus_pa"][i]),
                "moc_a_minus_pa": float(moc_fields["a_minus_pa"][i]),
                "analytical_a_minus_pa": float(analytical_fields["a_minus_pa"][i]),
            }
            field_rows.append(row)
            analytical_rows.append(
                {
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
    arrival_rows: list[dict[str, Any]] = []
    for probe_id in sorted({str(row["probe_id"]) for row in fvm_probe_rows}):
        rows = [row for row in fvm_probe_rows if row["probe_id"] == probe_id]
        times = np.asarray([row["time_s"] for row in rows], dtype=float)
        probe_x = float(rows[0]["probe_x_m"])
        fvm_pressure = np.asarray(
            [row["pressure_perturbation_pa"] for row in rows], dtype=float
        )
        fvm_velocity = np.asarray([row["velocity_m_s"] for row in rows], dtype=float)
        # The analytical helper accepts one scalar time, so evaluate each recorded time.
        analytical_pressure = np.asarray(
            [
                evaluate_gaussian_reference(
                    np.asarray([probe_x]),
                    float(t),
                    length_m=cfg.pipe_length_m,
                    rho0_kg_m3=rho0,
                    c0_m_s=c0,
                    amplitude_pa=cfg.pressure_amplitude_pa,
                    center_m=cfg.pulse_center_fraction * cfg.pipe_length_m,
                    sigma_m=cfg.pulse_sigma_fraction * cfg.pipe_length_m,
                )["pressure_perturbation_pa"][0]
                for t in times
            ],
            dtype=float,
        )
        analytical_velocity = analytical_pressure / (rho0 * c0)
        moc_pressure = sample_spacetime_history(
            moc_history["time_s"],
            moc_history["x_m"],
            moc_history["pressure_perturbation_pa"],
            times,
            np.full(times.shape, probe_x),
        )
        moc_velocity = sample_spacetime_history(
            moc_history["time_s"],
            moc_history["x_m"],
            moc_history["velocity_m_s"],
            times,
            np.full(times.shape, probe_x),
        )
        crossings: dict[str, dict[str, Any]] = {}
        for implementation, pressure in (
            ("fvm", fvm_pressure),
            ("moc", moc_pressure),
            ("analytical", analytical_pressure),
        ):
            crossings[implementation] = leading_fraction_crossings(times, pressure)
        arrival_row: dict[str, Any] = {
            "probe_id": probe_id,
            "probe_x_m": probe_x,
        }
        for implementation in ("fvm", "moc", "analytical"):
            for key, value in crossings[implementation]["crossing_times_s"].items():
                arrival_row[f"{implementation}_{key}_time_s"] = value
        for implementation in ("fvm", "moc"):
            for key in ("p10", "p50", "p90"):
                value = arrival_row.get(f"{implementation}_{key}_time_s")
                reference_value = arrival_row.get(f"analytical_{key}_time_s")
                arrival_row[f"{implementation}_{key}_offset_s"] = (
                    float(value - reference_value)
                    if value is not None and reference_value is not None
                    else None
                )
        arrival_rows.append(arrival_row)
        for i, time_value in enumerate(times):
            probe_comparison_rows.append(
                {
                    "probe_id": probe_id,
                    "probe_x_m": probe_x,
                    "time_s": float(time_value),
                    "fvm_pressure_perturbation_pa": float(fvm_pressure[i]),
                    "moc_pressure_perturbation_pa": float(moc_pressure[i]),
                    "analytical_pressure_perturbation_pa": float(
                        analytical_pressure[i]
                    ),
                    "fvm_velocity_m_s": float(fvm_velocity[i]),
                    "moc_velocity_m_s": float(moc_velocity[i]),
                    "analytical_velocity_m_s": float(analytical_velocity[i]),
                }
            )

    speed_metrics = {
        implementation: {
            key: _fitted_speed(
                arrival_rows, f"{implementation}_{key}_time_s", c0
            )
            for key in ("p10", "p50", "p90")
        }
        for implementation in ("fvm", "moc", "analytical")
    }
    def maxima(implementation: str, field: str, norm: str) -> float:
        return float(
            max(
                sample[implementation][field][norm]
                for sample in field_metrics
            )
        )

    aggregate = {
        "matched_time_count": len(field_metrics),
        "matched_spatial_sample_count": len(field_rows),
        "interpolation_method": (
            "fixed bilinear interpolation of MOC native history to FVM cell-center "
            "positions and FVM probe times; no phase shift or optimization"
        ),
        "field_metrics_by_time": field_metrics,
        "probe_arrival_metrics": arrival_rows,
        "fitted_speed_metrics": speed_metrics,
        "max_fvm_pressure_l1_relative": maxima(
            "fvm", "pressure_perturbation_pa", "l1_relative"
        ),
        "max_fvm_pressure_l2_relative": maxima(
            "fvm", "pressure_perturbation_pa", "l2_relative"
        ),
        "max_fvm_pressure_linf_relative": maxima(
            "fvm", "pressure_perturbation_pa", "linf_relative"
        ),
        "max_moc_pressure_l2_relative": maxima(
            "moc", "pressure_perturbation_pa", "l2_relative"
        ),
        "max_fvm_velocity_l2_relative": maxima(
            "fvm", "velocity_m_s", "l2_relative"
        ),
        "max_moc_velocity_l2_relative": maxima(
            "moc", "velocity_m_s", "l2_relative"
        ),
        "max_fvm_a_plus_l2_relative": maxima(
            "fvm", "a_plus_pa", "l2_relative"
        ),
        "max_moc_a_plus_l2_relative": maxima(
            "moc", "a_plus_pa", "l2_relative"
        ),
        "max_fvm_a_minus_leakage_l2_relative": maxima(
            "fvm", "a_minus_pa", "l2_relative"
        ),
        "max_moc_a_minus_leakage_l2_relative": maxima(
            "moc", "a_minus_pa", "l2_relative"
        ),
        "max_abs_fvm_energy_relative_difference": float(
            max(
                abs(sample["fvm"]["acoustic_energy_relative_difference"])
                for sample in field_metrics
                if sample["fvm"]["acoustic_energy_relative_difference"] is not None
            )
        ),
        "max_abs_moc_energy_relative_difference": float(
            max(
                abs(sample["moc"]["acoustic_energy_relative_difference"])
                for sample in field_metrics
                if sample["moc"]["acoustic_energy_relative_difference"] is not None
            )
        ),
        "max_abs_fvm_p50_offset_s": float(
            max(
                abs(row["fvm_p50_offset_s"])
                for row in arrival_rows
                if row.get("fvm_p50_offset_s") is not None
            )
        ),
        "max_abs_moc_p50_offset_s": float(
            max(
                abs(row["moc_p50_offset_s"])
                for row in arrival_rows
                if row.get("moc_p50_offset_s") is not None
            )
        ),
        "energy_rows": energy_rows,
        "formal_fvm_regression_band_applied": False,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
    }
    return aggregate, field_rows, analytical_rows, probe_comparison_rows


def _summary_row(
    case_id: str,
    n_cells: int,
    fvm_metrics: Mapping[str, Any],
    moc_metrics: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "verification_item": "V-013A",
        "n_cells": int(n_cells),
        "dx_m": float(fvm_metrics["dx_m"]),
        "fvm_cfl": float(fvm_metrics["cfl_target"]),
        "moc_cfl": float(moc_metrics["cfl"]),
        "fvm_step_count": int(fvm_metrics["step_count"]),
        "moc_step_count": int(moc_metrics["n_steps"]),
        "fvm_health_pass": bool(fvm_metrics["overall_fvm_health_pass"]),
        "moc_reference_pass": bool(moc_metrics["overall_moc_reference_pass"]),
        "max_fvm_pressure_l1_relative": comparison[
            "max_fvm_pressure_l1_relative"
        ],
        "max_fvm_pressure_l2_relative": comparison[
            "max_fvm_pressure_l2_relative"
        ],
        "max_fvm_pressure_linf_relative": comparison[
            "max_fvm_pressure_linf_relative"
        ],
        "max_moc_pressure_l2_relative": comparison[
            "max_moc_pressure_l2_relative"
        ],
        "max_fvm_velocity_l2_relative": comparison[
            "max_fvm_velocity_l2_relative"
        ],
        "max_moc_velocity_l2_relative": comparison[
            "max_moc_velocity_l2_relative"
        ],
        "max_fvm_a_minus_leakage_l2_relative": comparison[
            "max_fvm_a_minus_leakage_l2_relative"
        ],
        "max_moc_a_minus_leakage_l2_relative": comparison[
            "max_moc_a_minus_leakage_l2_relative"
        ],
        "max_abs_fvm_p50_offset_s": comparison["max_abs_fvm_p50_offset_s"],
        "max_abs_moc_p50_offset_s": comparison["max_abs_moc_p50_offset_s"],
        "fvm_p50_speed_relative_error": comparison["fitted_speed_metrics"]["fvm"][
            "p50"
        ]["relative_error"],
        "moc_p50_speed_relative_error": comparison["fitted_speed_metrics"]["moc"][
            "p50"
        ]["relative_error"],
        "max_abs_fvm_energy_relative_difference": comparison[
            "max_abs_fvm_energy_relative_difference"
        ],
        "max_abs_moc_energy_relative_difference": comparison[
            "max_abs_moc_energy_relative_difference"
        ],
        "property_backend_design_status": fvm_metrics[
            "property_backend_design_status"
        ],
        "execution_pass": bool(
            fvm_metrics["overall_fvm_health_pass"]
            and moc_metrics["overall_moc_reference_pass"]
        ),
        "formal_fvm_regression_band_applied": False,
    }


def _write_report(
    path: Path,
    cfg: V013IncidentPropagationConfig,
    metrics: Mapping[str, Any],
) -> None:
    lines = [
        "# V-013A incident-propagation cross-verification observation",
        "",
        "This report records software / numerical verification only. It is not physical "
        "Validation, design-use acceptance, or approval of the CoolProp backend.",
        "",
        "## Compared paths",
        "",
        "- production FVM source path: existing CoolProp small-amplitude-wave builders;",
        "- independent nodal MOC: CFL=1, explicit rho0/c0, no CoolProp calls;",
        "- analytical constant-coefficient right-going Gaussian characteristic solution.",
        "",
        "## Fixed observation matrix",
        "",
    ]
    for row in metrics["summary_rows"]:
        lines.append(
            f"- {row['case_id']}: n={row['n_cells']}, dx={row['dx_m']}, "
            f"FVM CFL={row['fvm_cfl']}, MOC CFL={row['moc_cfl']}, "
            f"execution_pass={row['execution_pass']}"
        )
    lines += [
        "",
        "## Comparison policy",
        "",
        "- common field samples are FVM cell centers at prescribed center-travel times;",
        "- MOC is sampled with fixed linear time/space interpolation;",
        "- no signal shifting or parameter tuning is used;",
        "- FVM errors are observations; no CI-light band is applied in this increment;",
        "- the finest FVM or MOC mesh is not an exact solution.",
        "",
        "## Status",
        "",
        f"- planned / executed runs: {metrics['planned_run_count']} / "
        f"{metrics['executed_run_count']}",
        f"- overall execution pass: {metrics['overall_execution_pass']}",
        f"- aggregate analysis complete: {metrics['aggregate_analysis_complete']}",
        f"- plots complete: {metrics['comparison_plots_complete']}",
        f"- generated plots: {metrics['generated_plots']}",
        "",
        "V-013 remains IN_PROGRESS. V-013B/C reflection observations, CI-light bands, "
        "formal report, and SHA256 manifest remain.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_v013_incident_propagation(
    output_dir: str | Path | None = None,
    config: V013IncidentPropagationConfig | None = None,
) -> dict[str, Any]:
    """Execute the V-013A FVM/MOC/analytical incident-wave observation."""

    cfg = config or V013IncidentPropagationConfig()
    base = (
        Path(output_dir)
        if output_dir is not None
        else Path(tempfile.mkdtemp(prefix="v013a_incident_"))
    )
    base.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    plan = build_run_plan(cfg)
    _write_json(base / "v013a_config.json", asdict(cfg))
    _write_json(base / "v013a_run_plan.json", plan)
    run_records: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    reference_constants: dict[str, Any] | None = None

    for item in plan:
        case_id = str(item["case_id"])
        run_dir = base / case_id
        run_dir.mkdir(parents=True, exist_ok=True)
        n_cells = int(item["n_cells"])
        fvm_metrics, fvm_history, fvm_probe_rows, source = _run_fvm(n_cells, cfg)
        rho0 = float(fvm_metrics["rho0_kg_m3"])
        c0 = float(fvm_metrics["c0_m_s"])
        if reference_constants is None:
            reference_constants = {
                "p0_pa": cfg.initial_pressure_pa,
                "T0_K": cfg.initial_temperature_K,
                "rho0_kg_m3": rho0,
                "c0_m_s": c0,
                "rho0_provenance": fvm_metrics["rho0_provenance"],
                "c0_provenance": fvm_metrics["c0_provenance"],
                "moc_calls_coolprop": False,
                "property_backend_name_fvm": "coolprop_co2",
                "property_backend_design_status": (
                    "not_approved_for_design_use"
                ),
            }
        else:
            if not math.isclose(
                rho0, float(reference_constants["rho0_kg_m3"]), rel_tol=0.0, abs_tol=1.0e-10
            ) or not math.isclose(
                c0, float(reference_constants["c0_m_s"]), rel_tol=0.0, abs_tol=1.0e-10
            ):
                raise RuntimeError("rho0/c0 changed across the V-013A mesh matrix")
        reference_cfg, moc_history, moc_metrics = _run_moc(
            n_cells, cfg, rho0=rho0, c0=c0
        )
        comparison, matched_rows, analytical_rows, probe_rows = _compare_run(
            cfg,
            fvm_metrics,
            fvm_history,
            fvm_probe_rows,
            moc_history,
        )
        _write_json(run_dir / "fvm_config.json", source["source_config"])
        _write_json(run_dir / "fvm_metrics.json", fvm_metrics)
        _write_csv(run_dir / "fvm_probe_history.csv", fvm_probe_rows)
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
        _write_csv(run_dir / "probe_comparison.csv", probe_rows)
        _write_json(run_dir / "comparison_metrics.json", comparison)
        summary = _summary_row(
            case_id, n_cells, fvm_metrics, moc_metrics, comparison
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

    if reference_constants is None:
        raise RuntimeError("V-013A run plan was empty")
    _write_json(base / "v013a_reference_constants.json", reference_constants)
    _write_csv(base / "v013a_summary.csv", summary_rows)
    overall_pass = bool(
        len(run_records) == len(plan)
        and all(row["execution_pass"] for row in summary_rows)
    )
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "verification_item": "V-013A",
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "formal_fvm_regression_band_applied": False,
        "property_backend_name": "coolprop_co2",
        "property_backend_design_status": "not_approved_for_design_use",
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
        "lower_cfl_is_truth": False,
        "limitations": [
            "analytical path solves the specified linearized constant-coefficient PDE",
            "MOC is an independent numerical reference, not physical truth",
            "finest FVM or MOC mesh is not an exact solution",
            "no FVM CI-light band is applied before observation review",
            "not physical Validation or design-use acceptance",
        ],
    }
    _write_json(base / "v013a_metrics.json", metrics)
    _write_report(base / "v013a_observation_report.md", cfg, metrics)

    if cfg.generate_plots:
        try:
            from liquid_gas_transient.plot_v013_incident_propagation_results import (
                plot_v013_incident_propagation_results,
            )
            plot_result = plot_v013_incident_propagation_results(base)
            metrics["generated_plots"] = plot_result["plot_files"]
            metrics["plotting_errors"] = plot_result["plotting_errors"]
            metrics["comparison_plots_complete"] = bool(
                plot_result["plot_count"] == plot_result["expected_plot_count"]
                and not plot_result["plotting_errors"]
            )
        except Exception as exc:  # pragma: no cover - plotting must not erase numerics
            metrics["plotting_errors"] = {"plotter": str(exc)}
            metrics["comparison_plots_complete"] = False
        _write_json(base / "v013a_metrics.json", metrics)
        _write_report(base / "v013a_observation_report.md", cfg, metrics)
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
    parser.add_argument("--no-plots", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = V013IncidentPropagationConfig(
        fvm_mesh_cells=(
            tuple(args.mesh_cells)
            if args.mesh_cells is not None
            else V013IncidentPropagationConfig().fvm_mesh_cells
        ),
        generate_plots=not args.no_plots,
    )
    result = run_v013_incident_propagation(args.output_dir, cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall_execution_pass"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "V013IncidentPropagationConfig",
    "build_run_plan",
    "case_id_for",
    "leading_fraction_crossings",
    "normalized_error_norms",
    "run_v013_incident_propagation",
    "sample_spacetime_history",
]
