"""CoolProp single-phase baseline boundary-reflection observation runner.

This module performs software/numerical verification observations for ideal
rigid-wall and fixed-pressure right boundaries. It is not physical validation,
design-use acceptance, or a model of an actual valve or reservoir.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import importlib.metadata
import json
from pathlib import Path
from typing import Any, Literal

import numpy as np

from ..boundary import ConstantPressure, PressureTankBoundary, ReflectiveBoundary, TransmissiveBoundary
from ..boundary_history import write_boundary_history_csv
from ..boundary_telemetry import BoundaryTelemetryRecorder
from ..phase_change import NoPhaseChange
from ..properties import coolprop_available
from ..solver import FvmSolver
from ..source_terms import NoSource
from ..verification.boundary_reflection import (
    acoustic_impedance,
    characteristic_amplitudes,
    evaluation_windows,
    expected_reflection_coefficients,
    theoretical_reflection_timing,
)
from .coolprop_small_amplitude_wave import CoolPropSmallAmplitudeWaveConfig, build_initial_gaussian_pulse

BoundaryKind = Literal["rigid_wall", "fixed_pressure"]


@dataclass(frozen=True)
class CoolPropBoundaryReflectionConfig:
    """Baseline Stage 5 configuration for one idealized right boundary."""

    boundary_kind: BoundaryKind = "rigid_wall"
    case_name: str | None = None
    output_version: str = "coolprop_boundary_reflection_v1"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    n_cells: int = 100
    cfl: float = 0.5
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_amplitude_pa: float = 1.0e3
    pulse_center_fraction: float = 0.50
    pulse_sigma_fraction: float = 0.03
    probe_fractions: tuple[float, ...] = (0.75, 0.90)
    sample_every: int = 1
    max_steps: int = 20000
    window_half_width_sigma: float = 2.5

    def __post_init__(self) -> None:
        if self.boundary_kind not in {"rigid_wall", "fixed_pressure"}:
            raise ValueError("boundary_kind must be 'rigid_wall' or 'fixed_pressure'")
        if self.case_name is None:
            object.__setattr__(self, "case_name", f"coolprop_{self.boundary_kind}_boundary_reflection")
        if not self.probe_fractions:
            raise ValueError("at least one probe is required")
        if any(not self.pulse_center_fraction < f < 1.0 for f in self.probe_fractions):
            raise ValueError("probe fractions must lie between pulse center and right boundary")
        if self.sample_every <= 0 or self.max_steps <= 0:
            raise ValueError("sample_every and max_steps must be positive")
        if self.window_half_width_sigma <= 0.0:
            raise ValueError("window_half_width_sigma must be positive")


def _wave_config(cfg: CoolPropBoundaryReflectionConfig) -> CoolPropSmallAmplitudeWaveConfig:
    return CoolPropSmallAmplitudeWaveConfig(
        case_name=str(cfg.case_name),
        output_version=cfg.output_version,
        pipe_length_m=cfg.pipe_length_m,
        diameter_m=cfg.diameter_m,
        n_cells=cfg.n_cells,
        cfl=cfg.cfl,
        initial_pressure_pa=cfg.initial_pressure_pa,
        initial_temperature_K=cfg.initial_temperature_K,
        pressure_amplitude_pa=cfg.pressure_amplitude_pa,
        pulse_center_fraction=cfg.pulse_center_fraction,
        pulse_sigma_fraction=cfg.pulse_sigma_fraction,
        probe_fractions=cfg.probe_fractions,
        sample_every=cfg.sample_every,
        max_steps=cfg.max_steps,
    )


def build_coolprop_boundary_reflection_solver(
    config: CoolPropBoundaryReflectionConfig | None = None,
) -> tuple[FvmSolver, dict[str, Any]]:
    """Build the baseline solver and return it with initialization metadata."""

    cfg = config or CoolPropBoundaryReflectionConfig()
    init = build_initial_gaussian_pulse(_wave_config(cfg))
    if cfg.boundary_kind == "rigid_wall":
        right_boundary = ReflectiveBoundary()
    else:
        right_boundary = PressureTankBoundary(
            pressure_schedule=ConstantPressure(cfg.initial_pressure_pa),
            flow_direction="bidirectional",
            velocity_policy="copy",
        )
    solver = FvmSolver(
        grid=init["grid"],
        eos=init["eos"],
        U=init["U"],
        cfl=cfg.cfl,
        left_boundary=TransmissiveBoundary(),
        right_boundary=right_boundary,
        source_term=NoSource(),
        phase_change=NoPhaseChange(),
        internal_interfaces=(),
        latent_heat_placeholder_j_kg=0.0,
    )
    return solver, init


def _probe_specs(cfg: CoolPropBoundaryReflectionConfig, solver: FvmSolver) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for frac in cfg.probe_fractions:
        target = frac * cfg.pipe_length_m
        idx = int(np.argmin(np.abs(solver.grid.cell_centers - target)))
        specs.append(
            {
                "probe_name": f"x_over_L_{frac:g}",
                "probe_target_x_m": float(target),
                "probe_cell_index": idx,
                "probe_cell_center_x_m": float(solver.grid.cell_centers[idx]),
            }
        )
    return specs


def _sample_probes(
    solver: FvmSolver,
    cfg: CoolPropBoundaryReflectionConfig,
    probes: list[dict[str, Any]],
    dt: float,
    rho0: float,
    c0: float,
) -> list[dict[str, Any]]:
    prim = solver.primitive()
    rows: list[dict[str, Any]] = []
    cfl = float(np.max((np.abs(prim.u) + prim.c) * dt / solver.grid.dx)) if dt > 0 else 0.0
    for spec in probes:
        i = spec["probe_cell_index"]
        dp = float(prim.p[i] - cfg.initial_pressure_pa)
        u = float(prim.u[i])
        a_plus, a_minus = characteristic_amplitudes(dp, u, rho0, c0)
        rows.append(
            {
                "time_s": float(solver.t),
                "step": int(solver.step_count),
                "dt_s": float(dt),
                "cfl": cfl,
                **spec,
                "pressure_pa": float(prim.p[i]),
                "delta_pressure_pa": dp,
                "velocity_m_s": u,
                "A_plus_pa": float(a_plus),
                "A_minus_pa": float(a_minus),
                "temperature_K": float(prim.T[i]),
                "density_kg_m3": float(prim.rho[i]),
                "sound_speed_m_s": float(prim.c[i]),
                "vapor_mass_fraction": float(prim.xv[i]),
                "alpha": float(prim.alpha[i]),
            }
        )
    return rows


def _record_boundary_step(solver: FvmSolver, recorder: BoundaryTelemetryRecorder, dt: float) -> None:
    """Record the exact external states and fluxes used at this explicit step."""

    U_ext = solver.extend_with_ghosts(solver.t)
    flux = solver.flux_function(U_ext[:-1], U_ext[1:], solver.eos)
    i0 = solver.n_ghost
    i1 = solver.n_ghost + solver.grid.n_cells
    recorder.record_external_faces(
        step=solver.step_count + 1,
        flux_evaluation_time_s=solver.t,
        dt_s=dt,
        left_face_U_left=U_ext[i0 - 1],
        left_face_U_right=U_ext[i0],
        right_face_U_left=U_ext[i1 - 1],
        right_face_U_right=U_ext[i1],
        left_flux=flux[i0 - 1],
        right_flux=flux[i1 - 1],
        eos=solver.eos,
    )


def _window_rows(rows: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    return [row for row in rows if start <= float(row["time_s"]) <= end]


def _signed_extremum(rows: list[dict[str, Any]], key: str, sign: float) -> tuple[float | None, float | None]:
    if not rows:
        return None, None
    chosen = max(rows, key=lambda row: float(row[key])) if sign > 0 else min(rows, key=lambda row: float(row[key]))
    return float(chosen[key]), float(chosen["time_s"])


def _probe_metrics(
    cfg: CoolPropBoundaryReflectionConfig,
    probes: list[dict[str, Any]],
    history: list[dict[str, Any]],
    rho0: float,
    c0: float,
) -> list[dict[str, Any]]:
    expected = expected_reflection_coefficients(cfg.boundary_kind)
    expected_sign = 1.0 if expected["pressure_reflection_coefficient"] > 0 else -1.0
    out: list[dict[str, Any]] = []
    for spec in probes:
        timing = theoretical_reflection_timing(
            pipe_length_m=cfg.pipe_length_m,
            pulse_center_x_m=cfg.pulse_center_fraction * cfg.pipe_length_m,
            probe_x_m=spec["probe_cell_center_x_m"],
            c0_m_s=c0,
            pulse_sigma_m=cfg.pulse_sigma_fraction * cfg.pipe_length_m,
        )
        windows = evaluation_windows(timing, half_width_sigma=cfg.window_half_width_sigma)
        rows = [row for row in history if row["probe_name"] == spec["probe_name"]]
        incident = _window_rows(rows, windows["incident_window_start_s"], windows["incident_window_end_s"])
        reflected = _window_rows(rows, windows["reflected_window_start_s"], windows["reflected_window_end_s"])
        incident_peak, incident_time = _signed_extremum(incident, "A_plus_pa", 1.0)
        reflected_extremum, reflected_time = _signed_extremum(reflected, "A_minus_pa", expected_sign)
        coefficient = (
            float(reflected_extremum / incident_peak)
            if reflected_extremum is not None and incident_peak not in (None, 0.0)
            else None
        )
        velocity_coefficient = -coefficient if coefficient is not None else None
        reflected_error = (
            float(reflected_time - timing["theoretical_reflected_time_s"])
            if reflected_time is not None
            else None
        )
        observed_sign = 0.0 if reflected_extremum in (None, 0.0) else float(np.sign(reflected_extremum))
        out.append(
            {
                **spec,
                **timing,
                **windows,
                "rho0_kg_m3": float(rho0),
                "c0_m_s": float(c0),
                "Z0_pa_s_m": acoustic_impedance(rho0, c0),
                "incident_A_plus_peak_pa": incident_peak,
                "incident_A_plus_peak_time_s": incident_time,
                "incident_A_minus_leakage_peak_pa": max((abs(float(r["A_minus_pa"])) for r in incident), default=None),
                "reflected_A_minus_signed_extremum_pa": reflected_extremum,
                "reflected_A_minus_extremum_time_s": reflected_time,
                "reflected_A_plus_leakage_peak_pa": max((abs(float(r["A_plus_pa"])) for r in reflected), default=None),
                "pressure_reflection_coefficient": coefficient,
                "velocity_reflection_coefficient": velocity_coefficient,
                "expected_pressure_reflection_coefficient": expected["pressure_reflection_coefficient"],
                "expected_velocity_reflection_coefficient": expected["velocity_reflection_coefficient"],
                "expected_pressure_reflection_sign": expected_sign,
                "observed_pressure_reflection_sign": observed_sign,
                "reflected_arrival_time_error_s": reflected_error,
                "reflected_arrival_time_relative_error": (
                    float(abs(reflected_error) / timing["theoretical_reflected_time_s"])
                    if reflected_error is not None and timing["theoretical_reflected_time_s"] > 0.0
                    else None
                ),
                "expected_sign_observed": bool(observed_sign == expected_sign),
            }
        )
    return out


def _boundary_metrics(
    cfg: CoolPropBoundaryReflectionConfig,
    boundary_rows: list[dict[str, Any]],
    c0: float,
) -> dict[str, Any]:
    timing = theoretical_reflection_timing(
        pipe_length_m=cfg.pipe_length_m,
        pulse_center_x_m=cfg.pulse_center_fraction * cfg.pipe_length_m,
        probe_x_m=max(cfg.probe_fractions) * cfg.pipe_length_m,
        c0_m_s=c0,
        pulse_sigma_m=cfg.pulse_sigma_fraction * cfg.pipe_length_m,
    )
    windows = evaluation_windows(timing, half_width_sigma=cfg.window_half_width_sigma)
    rows = [
        row for row in boundary_rows
        if row["side"] == "right"
        and windows["boundary_window_start_s"] <= float(row["flux_evaluation_time_s"]) <= windows["boundary_window_end_s"]
    ]
    if not rows:
        return {"boundary_window_sample_count": 0}
    pressure = np.asarray([row["boundary_face_pressure_pa"] for row in rows], dtype=float)
    velocity = np.asarray([row["boundary_face_velocity_m_s"] for row in rows], dtype=float)
    mass_flux = np.asarray([row["numerical_mass_flux_kg_m2_s"] for row in rows], dtype=float)
    energy_flux = np.asarray([row["numerical_energy_flux_w_m2"] for row in rows], dtype=float)
    dt = np.asarray([row["dt_s"] for row in rows], dtype=float)
    common: dict[str, Any] = {
        "boundary_window_sample_count": len(rows),
        "max_abs_boundary_velocity_m_s": float(np.max(np.abs(velocity))),
        "max_abs_boundary_mass_flux_kg_m2_s": float(np.max(np.abs(mass_flux))),
        "max_abs_boundary_energy_flux_w_m2": float(np.max(np.abs(energy_flux))),
        "integrated_right_boundary_mass_kg": float(np.sum(np.asarray([r["numerical_mass_flow_rate_kg_s"] for r in rows]) * dt)),
        "integrated_right_boundary_energy_j": float(np.sum(np.asarray([r["numerical_energy_flow_rate_w"] for r in rows]) * dt)),
    }
    if cfg.boundary_kind == "rigid_wall":
        common.update(
            {
                "max_abs_wall_velocity_m_s": common["max_abs_boundary_velocity_m_s"],
                "max_abs_wall_mass_flux_kg_m2_s": common["max_abs_boundary_mass_flux_kg_m2_s"],
                "max_abs_wall_energy_flux_w_m2": common["max_abs_boundary_energy_flux_w_m2"],
                "max_boundary_delta_pressure_pa": float(np.max(pressure - cfg.initial_pressure_pa)),
                "boundary_pressure_amplification_ratio": float(np.max(pressure - cfg.initial_pressure_pa) / cfg.pressure_amplitude_pa),
            }
        )
    else:
        residual = pressure - cfg.initial_pressure_pa
        common.update(
            {
                "max_abs_fixed_pressure_residual_pa": float(np.max(np.abs(residual))),
                "normalized_fixed_pressure_residual": float(np.max(np.abs(residual)) / cfg.pressure_amplitude_pa),
                "max_abs_boundary_velocity_amplification_ratio": float(np.max(np.abs(velocity)) / (cfg.pressure_amplitude_pa / 1.0)),
            }
        )
    return common


def _final_profile(solver: FvmSolver) -> list[dict[str, Any]]:
    prim = solver.primitive()
    return [
        {
            "cell_index": i,
            "x_m": float(solver.grid.cell_centers[i]),
            "pressure_pa": float(prim.p[i]),
            "temperature_K": float(prim.T[i]),
            "density_kg_m3": float(prim.rho[i]),
            "velocity_m_s": float(prim.u[i]),
            "sound_speed_m_s": float(prim.c[i]),
            "vapor_mass_fraction": float(prim.xv[i]),
            "alpha": float(prim.alpha[i]),
        }
        for i in range(solver.grid.n_cells)
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _coolprop_version() -> str:
    try:
        return importlib.metadata.version("CoolProp")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _write_artifacts(
    output_dir: Path,
    cfg: CoolPropBoundaryReflectionConfig,
    metrics: dict[str, Any],
    probe_history: list[dict[str, Any]],
    boundary_history: list[dict[str, Any]],
    profile: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = str(cfg.case_name)
    (output_dir / f"{stem}_config.json").write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{stem}_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_dir / f"{stem}_probe_history.csv", probe_history)
    write_boundary_history_csv(output_dir / f"{stem}_boundary_history.csv", boundary_history)
    _write_csv(output_dir / f"{stem}_final_profile.csv", profile)
    report = f"""# CoolProp single-phase boundary reflection observation

This is a software / numerical verification observation only.

- boundary_kind: {cfg.boundary_kind}
- theoretical idealization: {'infinite impedance rigid wall' if cfg.boundary_kind == 'rigid_wall' else 'zero impedance fixed pressure'}
- physical_validation: false
- design_use_acceptance: false
- actual_reservoir_or_valve_model: false
- property_backend_design_status: not_approved_for_design_use
- execution_complete: {metrics['execution_complete']}
- theoretical_consistency_classification: {metrics['theoretical_consistency_classification']}

No formal reflection-coefficient accuracy band is applied in this baseline PR.
"""
    (output_dir / f"{stem}_report.md").write_text(report, encoding="utf-8")


def run_coolprop_boundary_reflection(
    output_dir: Path | str | None = None,
    config: CoolPropBoundaryReflectionConfig | None = None,
) -> dict[str, Any]:
    """Run one baseline ideal-boundary reflection observation."""

    cfg = config or CoolPropBoundaryReflectionConfig()
    solver, init = build_coolprop_boundary_reflection_solver(cfg)
    ref = init["reference"]
    rho0 = float(ref["rho0"])
    c0 = float(ref["c0"])
    probes = _probe_specs(cfg, solver)
    primary_timings = [
        theoretical_reflection_timing(
            pipe_length_m=cfg.pipe_length_m,
            pulse_center_x_m=cfg.pulse_center_fraction * cfg.pipe_length_m,
            probe_x_m=spec["probe_cell_center_x_m"],
            c0_m_s=c0,
            pulse_sigma_m=cfg.pulse_sigma_fraction * cfg.pipe_length_m,
        )
        for spec in probes
    ]
    target_time = max(
        evaluation_windows(timing, half_width_sigma=cfg.window_half_width_sigma)["recommended_evaluation_end_s"]
        for timing in primary_timings
    )
    recorder = BoundaryTelemetryRecorder(area_m2=solver.grid.geometry.area_m2)
    probe_history = _sample_probes(solver, cfg, probes, 0.0, rho0, c0)
    dts: list[float] = []
    completed = False
    for _ in range(cfg.max_steps):
        if solver.t >= target_time:
            completed = True
            break
        dt = solver.compute_dt(target_time)
        _record_boundary_step(solver, recorder, dt)
        solver.step(dt)
        dts.append(float(dt))
        if solver.step_count % cfg.sample_every == 0 or solver.t >= target_time:
            probe_history.extend(_sample_probes(solver, cfg, probes, dt, rho0, c0))
    completed = completed or solver.t >= target_time
    boundary_history = recorder.rows()
    final_prim = solver.primitive()
    diag = solver.diagnostics(dt=0.0)
    probes_metrics = _probe_metrics(cfg, probes, probe_history, rho0, c0)
    sign_ok = all(bool(item["expected_sign_observed"]) for item in probes_metrics)
    reflection_detected = all(item["pressure_reflection_coefficient"] is not None for item in probes_metrics)
    contamination = any(bool(item["evaluation_window_contaminated"]) for item in probes_metrics)
    if not reflection_detected:
        classification = "reflection_not_detected"
    elif sign_ok and not contamination:
        classification = "expected_sign_and_timing_observed"
    elif sign_ok:
        classification = "expected_sign_observed_but_timing_or_magnitude_mixed"
    else:
        classification = "reflection_detected_but_theory_not_supported"
    missing_budget = [
        key for key in ("budget_mass_residual", "energy_budget_balance_residual_j", "phase_vapor_mass_balance_residual_kg")
        if key not in diag
    ]
    all_history_finite = bool(
        all(np.isfinite(float(value)) for row in probe_history for value in row.values() if isinstance(value, (int, float)))
        and all(np.isfinite(float(value)) for row in boundary_history for value in row.values() if isinstance(value, (int, float)))
    )
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "boundary_kind": cfg.boundary_kind,
        "software_path_verification": True,
        "numerical_verification": True,
        "design_evaluation": False,
        "acceptance_gate": False,
        "validation": False,
        "actual_equipment_model": False,
        "ideal_boundary_impedance": "infinite" if cfg.boundary_kind == "rigid_wall" else "zero",
        "property_backend_name": "coolprop_co2",
        "property_backend_design_status": "not_approved_for_design_use",
        "coolprop_available": coolprop_available(),
        "coolprop_version": _coolprop_version(),
        "rho0": rho0,
        "c0": c0,
        "Z0": acoustic_impedance(rho0, c0),
        "initial_pressure_pa": cfg.initial_pressure_pa,
        "initial_temperature_K": cfg.initial_temperature_K,
        "pressure_amplitude_pa": cfg.pressure_amplitude_pa,
        "pipe_length_m": cfg.pipe_length_m,
        "n_cells": cfg.n_cells,
        "dx_m": solver.grid.dx,
        "cfl_target": cfg.cfl,
        "target_time_s": float(target_time),
        "final_time_s": float(solver.t),
        "step_count": int(solver.step_count),
        "min_positive_dt_s": min(dts) if dts else 0.0,
        "max_dt_s": max(dts) if dts else 0.0,
        "execution_complete": bool(completed),
        "reached_target_time": bool(solver.t >= target_time),
        "within_max_steps": bool(solver.step_count <= cfg.max_steps),
        "all_history_finite": all_history_finite,
        "positive_pressure": bool(np.min(final_prim.p) > 0.0),
        "positive_temperature": bool(np.min(final_prim.T) > 0.0),
        "positive_density": bool(np.min(final_prim.rho) > 0.0),
        "positive_sound_speed": bool(np.min(final_prim.c) > 0.0),
        "remained_single_phase": bool(np.max(final_prim.xv) <= 1e-12 and np.max(final_prim.alpha) <= 1e-12),
        "max_vapor_mass_fraction": float(np.max(final_prim.xv)),
        "max_alpha": float(np.max(final_prim.alpha)),
        "missing_budget_fields": missing_budget,
        "budget_mass_residual": float(diag.get("budget_mass_residual", np.nan)),
        "budget_mass_relative_residual": float(diag.get("budget_mass_relative_residual", np.nan)),
        "energy_budget_balance_residual_j": float(diag.get("energy_budget_balance_residual_j", np.nan)),
        "energy_budget_balance_relative_residual": float(diag.get("energy_budget_balance_relative_residual", np.nan)),
        "phase_vapor_mass_balance_residual_kg": float(diag.get("phase_vapor_mass_balance_residual_kg", np.nan)),
        "phase_vapor_mass_balance_relative_residual": float(diag.get("phase_vapor_mass_balance_relative_residual", np.nan)),
        "probe_sample_count": len(probe_history),
        "boundary_history_row_count": len(boundary_history),
        "probes": probes_metrics,
        "boundary_metrics": _boundary_metrics(cfg, boundary_history, c0),
        "reflection_detected": reflection_detected,
        "expected_sign_observed": sign_ok,
        "evaluation_window_contaminated": contamination,
        "theoretical_consistency_classification": classification,
    }
    health_ok = all(
        [
            metrics["execution_complete"],
            metrics["reached_target_time"],
            metrics["within_max_steps"],
            metrics["all_history_finite"],
            metrics["positive_pressure"],
            metrics["positive_temperature"],
            metrics["positive_density"],
            metrics["positive_sound_speed"],
            metrics["remained_single_phase"],
            not metrics["missing_budget_fields"],
            not metrics["evaluation_window_contaminated"],
            metrics["reflection_detected"],
        ]
    )
    metrics["overall_observation_execution_pass"] = bool(health_ok)
    if output_dir is not None:
        _write_artifacts(Path(output_dir), cfg, metrics, probe_history, boundary_history, _final_profile(solver))
    return metrics
