"""V-012B small driven-flow internal-valve observation.

Software/numerical verification only. Constant-pressure boundaries are
zero-impedance numerical idealizations, not real tanks.
"""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..boundary import ConstantPressure, PressureTankBoundary
from ..boundary_history import record_solver_boundary_telemetry, write_boundary_history_csv
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
from ..valve import ConstantOpening, KvLiquidValve
from ..verification.boundary_reflection import characteristic_amplitudes
from .coolprop_internal_valve_uniform import _coolprop_version, _roundoff_tolerance, _sample_valve, _write_csv
from .internal_valve_driven_config import CoolPropInternalValveDrivenConfig, opening_roundoff_tolerance


def _state_from_pT(backend: CoolPropCO2Backend, eos: LCO2PropertyEOSAdapter, pressure_pa: float, temperature_K: float) -> dict[str, float]:
    rho = float(np.asarray(backend.density_from_pT(pressure_pa, temperature_K)))
    e = float(np.asarray(backend.internal_energy_from_pT(pressure_pa, temperature_K)))
    primitive = eos.primitive_from_conserved(make_conserved(rho=rho, u=0.0, e=e, xv=0.0)[np.newaxis, :])
    state = {
        "pressure_pa": float(primitive.p[0]), "temperature_K": float(primitive.T[0]),
        "rho_kg_m3": float(primitive.rho[0]), "e_j_kg": e, "c_m_s": float(primitive.c[0]),
        "xv": float(primitive.xv[0]), "alpha": float(primitive.alpha[0]),
    }
    primary = ("pressure_pa", "temperature_K", "rho_kg_m3", "e_j_kg", "c_m_s")
    if not all(np.isfinite(state[key]) and state[key] > 0.0 for key in primary):
        raise ValueError("CoolProp initial state must be finite and positive")
    if abs(state["xv"]) > 1.0e-12 or abs(state["alpha"]) > 1.0e-12:
        raise ValueError("initial state must remain single phase")
    return state


def build_coolprop_internal_valve_driven_solver(config: CoolPropInternalValveDrivenConfig | None = None) -> tuple[FvmSolver, dict[str, Any]]:
    cfg = config or CoolPropInternalValveDrivenConfig()
    backend = CoolPropCO2Backend()
    eos = LCO2PropertyEOSAdapter(backend=backend, boundary_temperature_K=cfg.initial_temperature_K, quality_source="transported")
    left_state = _state_from_pT(backend, eos, cfg.left_pressure_pa, cfg.initial_temperature_K)
    right_state = _state_from_pT(backend, eos, cfg.right_pressure_pa, cfg.initial_temperature_K)
    grid = UniformGrid(PipeGeometry(cfg.pipe_length_m, cfg.diameter_m), cfg.n_cells)
    area_m2 = float(grid.geometry.area_m2)
    calibration_q = area_m2 * cfg.target_full_open_face_velocity_m_s
    kv = KvLiquidValve.kv_for_target_flow(q_m3_s=calibration_q, delta_p_pa=cfg.calibration_delta_p_pa, rho_kg_m3=float(left_state["rho_kg_m3"]), opening=1.0)
    left_cell = cfg.n_cells // 2 - 1
    interface = InternalValveInterface(left_cell=left_cell, area_m2=area_m2, valve=KvLiquidValve(kv_m3_per_h=kv, allow_reverse_flow=False), opening_schedule=ConstantOpening(cfg.constant_opening), max_mach=cfg.max_mach)
    rho = np.empty(cfg.n_cells); e = np.empty(cfg.n_cells)
    rho[: left_cell + 1] = left_state["rho_kg_m3"]; rho[left_cell + 1 :] = right_state["rho_kg_m3"]
    e[: left_cell + 1] = left_state["e_j_kg"]; e[left_cell + 1 :] = right_state["e_j_kg"]
    solver = FvmSolver(
        grid=grid, eos=eos,
        U=make_conserved(rho=rho, u=np.zeros(cfg.n_cells), e=e, xv=np.zeros(cfg.n_cells)), cfl=cfg.cfl,
        left_boundary=PressureTankBoundary(ConstantPressure(cfg.left_pressure_pa), flow_direction="bidirectional", velocity_policy="copy"),
        right_boundary=PressureTankBoundary(ConstantPressure(cfg.right_pressure_pa), flow_direction="bidirectional", velocity_policy="copy"),
        source_term=NoSource(), phase_change=NoPhaseChange(), internal_interfaces=(interface,), latent_heat_placeholder_j_kg=0.0,
    )
    return solver, {"left_state": left_state, "right_state": right_state, "interface": interface, "kv_m3_per_h": kv, "calibration_q_m3_s": calibration_q, "valve_x_m": float((left_cell + 1) * grid.dx)}


def _probe_specs(cfg: CoolPropInternalValveDrivenConfig, solver: FvmSolver, valve_x: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fraction in cfg.probe_fractions:
        target = fraction * cfg.pipe_length_m
        index = int(np.argmin(np.abs(solver.grid.cell_centers - target)))
        x_m = float(solver.grid.cell_centers[index])
        rows.append({"probe_name": f"x_over_L_{fraction:g}", "probe_target_x_m": float(target), "probe_cell_index": index, "probe_cell_center_x_m": x_m, "probe_side": "left" if x_m < valve_x else "right"})
    return rows


def _timing(cfg: CoolPropInternalValveDrivenConfig, context: dict[str, Any], probes: list[dict[str, Any]]) -> dict[str, float]:
    valve_x = float(context["valve_x_m"]); c_left = float(context["left_state"]["c_m_s"]); c_right = float(context["right_state"]["c_m_s"]); c_min = min(c_left, c_right)
    probe_distance = max(abs(float(row["probe_cell_center_x_m"]) - valve_x) for row in probes)
    probe_time = probe_distance / c_min + cfg.post_probe_margin_fraction * cfg.pipe_length_m / c_min
    boundary_time = min(valve_x / c_left, (cfg.pipe_length_m - valve_x) / c_right)
    safe_end = cfg.boundary_arrival_safety_fraction * boundary_time
    target = float(cfg.t_end_s) if cfg.t_end_s is not None else min(probe_time, safe_end)
    if not 0.0 < target < boundary_time:
        raise ValueError("target time must precede first valve-generated boundary arrival")
    return {"target_time_s": target, "farthest_probe_distance_m": probe_distance, "probe_observation_time_s": probe_time, "first_boundary_arrival_time_s": boundary_time, "safe_window_end_s": safe_end}


def _sample_probes(solver: FvmSolver, probes: list[dict[str, Any]], context: dict[str, Any], dt: float) -> list[dict[str, Any]]:
    primitive = solver.primitive(); rows: list[dict[str, Any]] = []
    for probe in probes:
        index = int(probe["probe_cell_index"]); reference = context[f"{probe['probe_side']}_state"]
        dp = float(primitive.p[index] - reference["pressure_pa"]); velocity = float(primitive.u[index])
        a_plus, a_minus = characteristic_amplitudes(dp, velocity, float(reference["rho_kg_m3"]), float(reference["c_m_s"]))
        rows.append({"time_s": float(solver.t), "step": int(solver.step_count), "dt_s": float(dt), **probe,
            "reference_pressure_pa": float(reference["pressure_pa"]), "pressure_pa": float(primitive.p[index]), "delta_pressure_pa": dp,
            "velocity_m_s": velocity, "A_plus_pa": float(a_plus), "A_minus_pa": float(a_minus), "temperature_K": float(primitive.T[index]),
            "density_kg_m3": float(primitive.rho[index]), "sound_speed_m_s": float(primitive.c[index]),
            "vapor_mass_fraction": float(primitive.xv[index]), "alpha": float(primitive.alpha[index])})
    return rows


def _final_profile(solver: FvmSolver, context: dict[str, Any]) -> list[dict[str, Any]]:
    primitive = solver.primitive(); valve_x = float(context["valve_x_m"]); rows: list[dict[str, Any]] = []
    for index, x_m in enumerate(solver.grid.cell_centers):
        side = "left" if float(x_m) < valve_x else "right"; p0 = float(context[f"{side}_state"]["pressure_pa"])
        rows.append({"cell_index": index, "x_m": float(x_m), "initial_segment": side, "reference_pressure_pa": p0,
            "pressure_pa": float(primitive.p[index]), "delta_pressure_pa": float(primitive.p[index] - p0), "velocity_m_s": float(primitive.u[index]),
            "temperature_K": float(primitive.T[index]), "density_kg_m3": float(primitive.rho[index]), "sound_speed_m_s": float(primitive.c[index]),
            "vapor_mass_fraction": float(primitive.xv[index]), "alpha": float(primitive.alpha[index])})
    return rows


def _max_abs(rows: list[dict[str, Any]], key: str) -> float:
    return max((abs(float(row[key])) for row in rows), default=0.0)


def _relative_difference(a: float, b: float) -> float:
    return float(abs(a - b) / max(abs(a), abs(b), np.finfo(float).tiny))


def _write_report(path: Path, metrics: dict[str, Any]) -> None:
    path.write_text("\n".join([
        "# V-012B Small Driven-Flow Internal-Valve Observation", "",
        "Software/numerical verification only; not physical Validation or design-use acceptance.", "", "## Result", "",
        f"- overall observation execution pass: `{metrics['overall_observation_execution_pass']}`",
        f"- initial valve dp: `{metrics['initial_delta_p_pa']:.9e} Pa`",
        f"- initial raw/applied/flux Q: `{metrics['initial_raw_target_q_m3_s']:.9e}` / `{metrics['initial_applied_q_m3_s']:.9e}` / `{metrics['initial_flux_derived_q_m3_s']:.9e} m3/s`",
        f"- Mach-cap activation count: `{metrics['mach_cap_activation_count']}`",
        f"- flow-sign consistency fraction: `{metrics['flow_sign_consistency_fraction']:.6f}`", "",
        "Constant-pressure boundaries are zero-impedance numerical idealizations. The observation window ends before a valve-generated wave reaches an external boundary.",
        "The hydraulic-loss proxy remains diagnostic and is not removed from conserved `rhoE`.", "",
    ]), encoding="utf-8")


def run_coolprop_internal_valve_driven(output_dir: Path | str | None = None, config: CoolPropInternalValveDrivenConfig | None = None) -> dict[str, Any]:
    cfg = config or CoolPropInternalValveDrivenConfig(); solver, context = build_coolprop_internal_valve_driven_solver(cfg)
    interface: InternalValveInterface = context["interface"]; probes = _probe_specs(cfg, solver, float(context["valve_x_m"])); timing = _timing(cfg, context, probes); target_time = timing["target_time_s"]
    recorder = BoundaryTelemetryRecorder(area_m2=solver.grid.geometry.area_m2)
    probe_history = _sample_probes(solver, probes, context, 0.0); schedule_history: list[dict[str, Any]] = []; valve_history: list[dict[str, Any]] = []; flux_history: list[dict[str, Any]] = []; dts: list[float] = []
    for _ in range(cfg.max_steps):
        if solver.t >= target_time: break
        dt = solver.compute_dt(target_time)
        schedule, valve, flux = _sample_valve(solver, interface, requested_opening=cfg.constant_opening, valve_x_m=float(context["valve_x_m"]), dt_s=dt)
        schedule_history.append(schedule); valve_history.append(valve); flux_history.append(flux)
        record_solver_boundary_telemetry(solver, recorder, dt); solver.step(dt); dts.append(float(dt))
        if solver.step_count % cfg.sample_every == 0 or solver.t >= target_time: probe_history.extend(_sample_probes(solver, probes, context, dt))
    boundary_history = recorder.rows(); final_profile = _final_profile(solver, context); primitive = solver.primitive(); diagnostics = solver.diagnostics(dt=0.0)
    required_budgets = ("budget_mass_residual", "energy_budget_balance_residual_j", "phase_vapor_mass_balance_residual_kg"); missing_budgets = [key for key in required_budgets if key not in diagnostics]
    histories_finite = all(np.isfinite(float(value)) for history in (schedule_history, valve_history, flux_history, probe_history, boundary_history, final_profile) for row in history for value in row.values() if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, (bool, np.bool_)))
    first_valve = valve_history[0] if valve_history else {}; first_flux = flux_history[0] if flux_history else {}; initial_raw = float(first_valve.get("raw_target_q_m3_s", np.nan)); initial_applied = float(first_valve.get("applied_q_m3_s", np.nan)); initial_flux = float(first_flux.get("flux_derived_q_m3_s", np.nan))
    tolerances = {
        "mass_flux_roundoff_tolerance_kg_m2_s": _roundoff_tolerance(*[float(r["left_mass_flux_kg_m2_s"]) for r in flux_history]),
        "energy_flux_roundoff_tolerance_w_m2": _roundoff_tolerance(*[float(r["left_energy_flux_w_m2"]) for r in flux_history]),
        "vapor_flux_roundoff_tolerance_kg_m2_s": _roundoff_tolerance(*[float(r["left_vapor_mass_flux_kg_m2_s"]) for r in flux_history]),
        "momentum_roundoff_tolerance_pa": _roundoff_tolerance(*[float(r["left_momentum_flux_pa"]) for r in flux_history]),
        "q_roundoff_tolerance_m3_s": _roundoff_tolerance(*[float(r["applied_q_m3_s"]) for r in valve_history]),
        "opening_roundoff_tolerance": opening_roundoff_tolerance(cfg),
    }
    budget_values = {"budget_mass_relative_residual": float(diagnostics.get("budget_mass_relative_residual", np.nan)), "energy_budget_balance_relative_residual": float(diagnostics.get("energy_budget_balance_relative_residual", np.nan)), "phase_vapor_mass_balance_relative_residual": float(diagnostics.get("phase_vapor_mass_balance_relative_residual", np.nan))}
    budget_ok = all(np.isfinite(v) and abs(v) <= cfg.relative_budget_tolerance for v in budget_values.values())
    sign_count = sum(float(r["delta_p_pa"]) * float(r["applied_q_m3_s"]) >= -tolerances["q_roundoff_tolerance_m3_s"] for r in valve_history)
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name, "output_version": cfg.output_version, "verification_item": "V-012B", "expected_dynamic_response": True,
        "software_path_verification": True, "numerical_verification": True, "validation": False, "design_evaluation": False, "acceptance_gate": False,
        "property_backend_name": "coolprop_co2", "property_backend_design_status": "not_approved_for_design_use", "coolprop_available": coolprop_available(), "coolprop_version": _coolprop_version(),
        "n_cells": cfg.n_cells, "dx_m": float(solver.grid.dx), "cfl_target": cfg.cfl, "left_pressure_requested_pa": cfg.left_pressure_pa, "right_pressure_requested_pa": cfg.right_pressure_pa,
        "left_pressure_eos_pa": float(context["left_state"]["pressure_pa"]), "right_pressure_eos_pa": float(context["right_state"]["pressure_pa"]), "initial_delta_p_pa": cfg.initial_delta_p_pa,
        "initial_temperature_K": cfg.initial_temperature_K, "left_rho0_kg_m3": float(context["left_state"]["rho_kg_m3"]), "right_rho0_kg_m3": float(context["right_state"]["rho_kg_m3"]),
        "left_c0_m_s": float(context["left_state"]["c_m_s"]), "right_c0_m_s": float(context["right_state"]["c_m_s"]), "constant_opening": cfg.constant_opening,
        "kv_m3_per_h": float(context["kv_m3_per_h"]), "calibration_delta_p_pa": cfg.calibration_delta_p_pa, "calibration_q_m3_s": float(context["calibration_q_m3_s"]),
        "target_full_open_face_velocity_m_s": cfg.target_full_open_face_velocity_m_s, "valve_left_cell": interface.left_cell, "valve_right_cell": interface.right_cell, "valve_x_m": float(context["valve_x_m"]),
        **timing, "final_time_s": float(solver.t), "reached_target_time": bool(solver.t >= target_time), "within_max_steps": bool(solver.step_count <= cfg.max_steps), "step_count": solver.step_count,
        "min_positive_dt_s": min(dts) if dts else 0.0, "max_dt_s": max(dts) if dts else 0.0, "all_history_finite": bool(histories_finite),
        "positive_pressure": bool(np.min(primitive.p) > 0.0), "positive_temperature": bool(np.min(primitive.T) > 0.0), "positive_density": bool(np.min(primitive.rho) > 0.0), "positive_sound_speed": bool(np.min(primitive.c) > 0.0),
        "remained_single_phase": bool(np.max(primitive.xv) <= 1.0e-12 and np.max(primitive.alpha) <= 1.0e-12), "max_vapor_mass_fraction": float(np.max(primitive.xv)), "max_alpha": float(np.max(primitive.alpha)),
        "missing_budget_fields": missing_budgets, **budget_values, "relative_budget_tolerance": cfg.relative_budget_tolerance, "budgets_within_tolerance": bool(budget_ok),
        "schedule_sample_count": len(schedule_history), "valve_history_row_count": len(valve_history), "interface_flux_history_row_count": len(flux_history), "probe_sample_count": len(probe_history), "boundary_history_row_count": len(boundary_history), "final_profile_row_count": len(final_profile),
        "initial_raw_target_q_m3_s": initial_raw, "initial_applied_q_m3_s": initial_applied, "initial_flux_derived_q_m3_s": initial_flux,
        "initial_raw_applied_relative_difference": _relative_difference(initial_raw, initial_applied), "initial_applied_flux_relative_difference": _relative_difference(initial_applied, initial_flux), "flow_relative_tolerance": cfg.flow_relative_tolerance,
        "min_delta_p_valve_pa": min((float(r["delta_p_pa"]) for r in valve_history), default=np.nan), "min_applied_q_m3_s": min((float(r["applied_q_m3_s"]) for r in valve_history), default=np.nan),
        "max_applied_face_mach": max((abs(float(r["applied_face_mach"])) for r in valve_history), default=np.nan), "flow_sign_consistency_count": int(sign_count), "flow_sign_consistency_fraction": float(sign_count / len(valve_history) if valve_history else 0.0),
        "mach_cap_activation_count": sum(bool(r["mach_cap_active"]) for r in valve_history), "hydraulic_separation_count": sum(bool(r["hydraulic_separation_active"]) for r in valve_history),
        "max_abs_opening_error": _max_abs(schedule_history, "opening_error"), "max_abs_pressure_disturbance_pa": _max_abs(probe_history + final_profile, "delta_pressure_pa"), "max_abs_velocity_m_s": _max_abs(probe_history + final_profile, "velocity_m_s"),
        "max_abs_mass_flux_mismatch_kg_m2_s": _max_abs(flux_history, "mass_flux_mismatch_kg_m2_s"), "max_abs_energy_flux_mismatch_w_m2": _max_abs(flux_history, "energy_flux_mismatch_w_m2"),
        "max_abs_vapor_mass_flux_mismatch_kg_m2_s": _max_abs(flux_history, "vapor_mass_flux_mismatch_kg_m2_s"), "max_abs_momentum_difference_residual_pa": _max_abs(flux_history, "momentum_difference_residual_pa"),
        "max_abs_flux_q_minus_applied_q_m3_s": _max_abs(flux_history, "flux_q_minus_applied_q_m3_s"), **tolerances,
        "hydraulic_loss_proxy_is_diagnostic_only": True, "hydraulic_loss_removed_from_rhoE": False, "fixed_pressure_boundaries_are_zero_impedance_idealizations": True,
    }
    checks = [metrics["reached_target_time"], metrics["within_max_steps"], metrics["all_history_finite"], metrics["positive_pressure"], metrics["positive_temperature"], metrics["positive_density"], metrics["positive_sound_speed"], metrics["remained_single_phase"], not metrics["missing_budget_fields"], metrics["budgets_within_tolerance"], metrics["max_abs_opening_error"] <= metrics["opening_roundoff_tolerance"], metrics["initial_delta_p_pa"] > 0.0, metrics["initial_raw_target_q_m3_s"] > 0.0, metrics["initial_applied_q_m3_s"] > 0.0, metrics["initial_flux_derived_q_m3_s"] > 0.0, metrics["initial_raw_applied_relative_difference"] <= metrics["flow_relative_tolerance"], metrics["initial_applied_flux_relative_difference"] <= metrics["flow_relative_tolerance"], metrics["flow_sign_consistency_count"] == metrics["valve_history_row_count"], metrics["mach_cap_activation_count"] == 0, metrics["max_abs_mass_flux_mismatch_kg_m2_s"] <= metrics["mass_flux_roundoff_tolerance_kg_m2_s"], metrics["max_abs_energy_flux_mismatch_w_m2"] <= metrics["energy_flux_roundoff_tolerance_w_m2"], metrics["max_abs_vapor_mass_flux_mismatch_kg_m2_s"] <= metrics["vapor_flux_roundoff_tolerance_kg_m2_s"], metrics["max_abs_momentum_difference_residual_pa"] <= metrics["momentum_roundoff_tolerance_pa"], metrics["max_abs_flux_q_minus_applied_q_m3_s"] <= metrics["q_roundoff_tolerance_m3_s"]]
    metrics["overall_observation_execution_pass"] = bool(all(checks))
    if output_dir is not None:
        directory = Path(output_dir); directory.mkdir(parents=True, exist_ok=True); stem = cfg.case_name
        (directory / f"{stem}_config.json").write_text(json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8"); (directory / f"{stem}_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        _write_csv(directory / f"{stem}_valve_schedule.csv", schedule_history); _write_csv(directory / f"{stem}_valve_history.csv", valve_history); _write_csv(directory / f"{stem}_interface_flux_history.csv", flux_history); _write_csv(directory / f"{stem}_probe_history.csv", probe_history)
        write_boundary_history_csv(directory / f"{stem}_boundary_history.csv", boundary_history); _write_csv(directory / f"{stem}_final_profile.csv", final_profile); _write_report(directory / f"{stem}_observation_report.md", metrics)
    return metrics
