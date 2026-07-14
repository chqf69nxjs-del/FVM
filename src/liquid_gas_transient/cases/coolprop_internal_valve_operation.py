"""Stage 6 V-012 single-phase internal-valve operation runner.

This runner exercises the existing ``KvLiquidValve`` and
``InternalValveInterface`` software path without changing valve physics. It is
software/numerical verification only, not physical Validation, equipment
approval, an ESD-event acceptance study, or design-use acceptance.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import importlib.metadata
import json
from pathlib import Path
from typing import Any, Literal

import numpy as np

from ..boundary import TransmissiveBoundary
from ..config import PipeGeometry
from ..eos import LCO2PropertyEOSAdapter
from ..grid import UniformGrid
from ..interfaces import InternalValveInterface
from ..phase_change import NoPhaseChange
from ..properties import CoolPropCO2Backend, coolprop_available
from ..solver import FvmSolver
from ..source_terms import NoSource
from ..state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV, make_conserved
from ..valve import ConstantOpening, KvLiquidValve, LinearRampOpening, OpeningSchedule

ValveOperationKind = Literal["constant", "opening_ramp", "closing_ramp"]


@dataclass(frozen=True)
class CoolPropInternalValveOperationConfig:
    """Configuration for the first V-012 component-operation observation."""

    case_name: str = "coolprop_internal_valve_operation"
    output_version: str = "coolprop_internal_valve_operation_v1"
    operation_kind: ValveOperationKind = "constant"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    n_cells: int = 100
    cfl: float = 0.5
    initial_left_pressure_pa: float = 8.001e6
    initial_right_pressure_pa: float = 8.000e6
    initial_temperature_K: float = 280.0
    valve_fraction: float = 0.50
    kv_m3_per_h: float = 10.0
    allow_reverse_flow: bool = False
    max_mach: float = 0.8
    constant_opening: float = 0.50
    ramp_start_s: float = 5.0e-3
    ramp_duration_s: float = 1.0e-2
    t_end_s: float | None = None
    probe_fractions: tuple[float, ...] = (0.25, 0.495, 0.505, 0.75)
    sample_every: int = 1
    max_steps: int = 20000

    def __post_init__(self) -> None:
        if self.operation_kind not in {"constant", "opening_ramp", "closing_ramp"}:
            raise ValueError("unsupported operation_kind")
        if self.pipe_length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.n_cells < 10:
            raise ValueError("n_cells must be at least 10")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.initial_left_pressure_pa <= 0.0 or self.initial_right_pressure_pa <= 0.0:
            raise ValueError("initial pressures must be positive")
        if self.initial_temperature_K <= 0.0:
            raise ValueError("initial temperature must be positive")
        if not 0.0 < self.valve_fraction < 1.0:
            raise ValueError("valve_fraction must lie in (0, 1)")
        if self.kv_m3_per_h < 0.0:
            raise ValueError("kv_m3_per_h must be non-negative")
        if not 0.0 < self.max_mach <= 1.0:
            raise ValueError("max_mach must lie in (0, 1]")
        if not 0.0 <= self.constant_opening <= 1.0:
            raise ValueError("constant_opening must lie in [0, 1]")
        if self.ramp_start_s < 0.0 or self.ramp_duration_s < 0.0:
            raise ValueError("ramp times must be non-negative")
        if self.t_end_s is not None and self.t_end_s <= 0.0:
            raise ValueError("t_end_s must be positive")
        if not self.probe_fractions:
            raise ValueError("at least one probe is required")
        if any(not 0.0 < value < 1.0 for value in self.probe_fractions):
            raise ValueError("probe fractions must lie in (0, 1)")
        if tuple(sorted(set(self.probe_fractions))) != self.probe_fractions:
            raise ValueError("probe_fractions must be unique and ascending")
        if self.sample_every <= 0 or self.max_steps <= 0:
            raise ValueError("sample_every and max_steps must be positive")


def opening_schedule_for_config(
    config: CoolPropInternalValveOperationConfig,
) -> OpeningSchedule:
    """Build the prescribed opening schedule without changing valve physics."""

    if config.operation_kind == "constant":
        return ConstantOpening(config.constant_opening)
    if config.operation_kind == "opening_ramp":
        return LinearRampOpening(
            t_start_s=config.ramp_start_s,
            duration_s=config.ramp_duration_s,
            open_initial=0.0,
            open_final=1.0,
        )
    return LinearRampOpening(
        t_start_s=config.ramp_start_s,
        duration_s=config.ramp_duration_s,
        open_initial=1.0,
        open_final=0.0,
    )


def opening_history_is_monotonic(
    openings: list[float] | np.ndarray,
    operation_kind: ValveOperationKind,
    *,
    tolerance: float = 1.0e-12,
) -> bool:
    """Return whether sampled openings follow the prescribed monotonic sense."""

    values = np.asarray(openings, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        return False
    differences = np.diff(values)
    if operation_kind == "constant":
        return bool(np.max(values) - np.min(values) <= tolerance)
    if operation_kind == "opening_ramp":
        return bool(np.all(differences >= -tolerance))
    if operation_kind == "closing_ramp":
        return bool(np.all(differences <= tolerance))
    return False


def _coolprop_version() -> str:
    try:
        return importlib.metadata.version("CoolProp")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def _valve_left_cell(config: CoolPropInternalValveOperationConfig) -> int:
    face_index = int(round(config.valve_fraction * config.n_cells))
    if not 1 <= face_index < config.n_cells:
        raise ValueError("valve must lie on an internal grid face")
    return face_index - 1


def build_coolprop_internal_valve_operation_solver(
    config: CoolPropInternalValveOperationConfig | None = None,
) -> tuple[FvmSolver, dict[str, Any]]:
    """Build the piecewise-uniform single-phase CO2 valve problem."""

    cfg = config or CoolPropInternalValveOperationConfig()
    backend = CoolPropCO2Backend()
    eos = LCO2PropertyEOSAdapter(
        backend=backend,
        boundary_temperature_K=cfg.initial_temperature_K,
        quality_source="transported",
    )
    pressures = np.asarray(
        [cfg.initial_left_pressure_pa, cfg.initial_right_pressure_pa],
        dtype=float,
    )
    temperatures = np.full_like(pressures, cfg.initial_temperature_K)
    densities = np.asarray(backend.density_from_pT(pressures, temperatures), dtype=float)
    energies = np.asarray(
        backend.internal_energy_from_pT(pressures, temperatures),
        dtype=float,
    )
    if not np.all(np.isfinite(densities)) or np.any(densities <= 0.0):
        raise ValueError("CoolProp densities must be finite and positive")
    if not np.all(np.isfinite(energies)) or np.any(energies <= 0.0):
        raise ValueError("CoolProp internal energies must be finite and positive")

    grid = UniformGrid(PipeGeometry(cfg.pipe_length_m, cfg.diameter_m), cfg.n_cells)
    left_cell = _valve_left_cell(cfg)
    rho = np.where(np.arange(cfg.n_cells) <= left_cell, densities[0], densities[1])
    e = np.where(np.arange(cfg.n_cells) <= left_cell, energies[0], energies[1])
    U = make_conserved(rho=rho, u=np.zeros(cfg.n_cells), e=e, xv=np.zeros(cfg.n_cells))

    valve = KvLiquidValve(
        kv_m3_per_h=cfg.kv_m3_per_h,
        allow_reverse_flow=cfg.allow_reverse_flow,
    )
    schedule = opening_schedule_for_config(cfg)
    interface = InternalValveInterface(
        left_cell=left_cell,
        area_m2=grid.geometry.area_m2,
        valve=valve,
        opening_schedule=schedule,
        max_mach=cfg.max_mach,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=cfg.cfl,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        source_term=NoSource(),
        phase_change=NoPhaseChange(),
        internal_interfaces=(interface,),
        latent_heat_placeholder_j_kg=0.0,
    )
    prim = solver.primitive()
    return solver, {
        "interface": interface,
        "schedule": schedule,
        "left_cell": left_cell,
        "right_cell": left_cell + 1,
        "c_left_m_s": float(prim.c[left_cell]),
        "c_right_m_s": float(prim.c[left_cell + 1]),
        "rho_left_kg_m3": float(prim.rho[left_cell]),
        "rho_right_kg_m3": float(prim.rho[left_cell + 1]),
    }


def _target_time(
    config: CoolPropInternalValveOperationConfig,
    solver: FvmSolver,
    context: dict[str, Any],
) -> tuple[float, float]:
    valve_x = (int(context["left_cell"]) + 1) * solver.grid.dx
    nearest_boundary_distance = min(valve_x, config.pipe_length_m - valve_x)
    max_sound_speed = max(float(context["c_left_m_s"]), float(context["c_right_m_s"]))
    first_external_arrival = nearest_boundary_distance / max_sound_speed
    if config.t_end_s is not None:
        return float(config.t_end_s), float(first_external_arrival)
    ramp_end = config.ramp_start_s + config.ramp_duration_s
    target = max(ramp_end + 1.0e-2, 0.45 * first_external_arrival)
    return float(target), float(first_external_arrival)


def _probe_specs(
    config: CoolPropInternalValveOperationConfig,
    solver: FvmSolver,
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for fraction in config.probe_fractions:
        target = fraction * config.pipe_length_m
        index = int(np.argmin(np.abs(solver.grid.cell_centers - target)))
        specs.append(
            {
                "probe_name": f"x_over_L_{fraction:g}",
                "probe_fraction": float(fraction),
                "probe_target_x_m": float(target),
                "probe_cell_index": int(index),
                "probe_cell_center_x_m": float(solver.grid.cell_centers[index]),
            }
        )
    return specs


def _sample_probes(
    solver: FvmSolver,
    probes: list[dict[str, Any]],
    dt_s: float,
) -> list[dict[str, Any]]:
    prim = solver.primitive()
    rows: list[dict[str, Any]] = []
    for probe in probes:
        index = int(probe["probe_cell_index"])
        rows.append(
            {
                "time_s": float(solver.t),
                "step": int(solver.step_count),
                "dt_s": float(dt_s),
                **probe,
                "pressure_pa": float(prim.p[index]),
                "velocity_m_s": float(prim.u[index]),
                "temperature_K": float(prim.T[index]),
                "density_kg_m3": float(prim.rho[index]),
                "sound_speed_m_s": float(prim.c[index]),
                "vapor_mass_fraction": float(prim.xv[index]),
                "alpha": float(prim.alpha[index]),
            }
        )
    return rows


def internal_valve_flux_snapshot(
    solver: FvmSolver,
    interface: InternalValveInterface,
    *,
    t_s: float | None = None,
    dt_s: float = 0.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return exact two-sided interface flux and valve diagnostics at one time."""

    time_s = float(solver.t if t_s is None else t_s)
    U_ext = solver.extend_with_ghosts(time_s)
    base_flux = solver.flux_function(U_ext[:-1], U_ext[1:], solver.eos)
    i0 = solver.n_ghost
    i1 = solver.n_ghost + solver.grid.n_cells
    flux_left = base_flux[i0 - 1 : i1 - 1].copy()
    flux_right = base_flux[i0:i1].copy()
    interface.apply(
        flux_left=flux_left,
        flux_right=flux_right,
        U=solver.U,
        eos=solver.eos,
        t=time_s,
        flux_function=solver.flux_function,
    )

    left_cell = interface.left_cell
    right_cell = interface.right_cell
    left_flux = np.asarray(flux_right[left_cell], dtype=float)
    right_flux = np.asarray(flux_left[right_cell], dtype=float)
    prim = solver.primitive()
    p_left = float(prim.p[left_cell])
    p_right = float(prim.p[right_cell])
    rho_left = float(prim.rho[left_cell])
    rho_right = float(prim.rho[right_cell])
    c_limit = min(float(prim.c[left_cell]), float(prim.c[right_cell]))
    opening = float(interface.opening_schedule.opening(time_s))
    q_raw = float(
        interface.flow_rate_m3_s(
            U_l=solver.U[left_cell],
            U_r=solver.U[right_cell],
            eos=solver.eos,
            t=time_s,
        )
    )
    q_limit = float(interface.max_mach * c_limit * interface.area_m2)
    if opening <= interface.closed_opening_tol or abs(q_raw) <= 1.0e-15:
        q_limited = 0.0
    else:
        q_limited = float(np.clip(q_raw, -q_limit, q_limit))
    cap_active = bool(abs(q_raw) > q_limit)
    rho_upstream = rho_left if q_limited >= 0.0 else rho_right
    actual_q_left = float(left_flux[IDX_RHO] * interface.area_m2 / rho_upstream)
    actual_q_right = float(right_flux[IDX_RHO] * interface.area_m2 / rho_upstream)
    loss_terms = interface.interface_energy_terms(U=solver.U, eos=solver.eos, t=time_s)

    valve_row = {
        "time_s": time_s,
        "step": int(solver.step_count),
        "dt_s": float(dt_s),
        "opening": opening,
        "p_left_pa": p_left,
        "p_right_pa": p_right,
        "delta_p_pa": float(p_left - p_right),
        "rho_upstream_kg_m3": rho_upstream,
        "raw_kv_target_q_m3_s": q_raw,
        "mach_q_limit_m3_s": q_limit,
        "limited_target_q_m3_s": q_limited,
        "actual_q_from_left_mass_flux_m3_s": actual_q_left,
        "actual_q_from_right_mass_flux_m3_s": actual_q_right,
        "face_velocity_m_s": float(q_limited / interface.area_m2),
        "face_mach": float(abs(q_limited) / (interface.area_m2 * c_limit)),
        "mach_cap_active": cap_active,
        "raw_valve_loss_power_w": float(loss_terms.get("valve_loss_power_w", 0.0)),
        "limited_valve_loss_power_w": float(max((p_left - p_right) * q_limited, 0.0)),
        "loss_proxy_is_diagnostic_only": True,
        "loss_proxy_removed_from_rhoE": False,
    }
    flux_row = {
        "time_s": time_s,
        "step": int(solver.step_count),
        "dt_s": float(dt_s),
        "opening": opening,
        "left_mass_flux_kg_m2_s": float(left_flux[IDX_RHO]),
        "right_mass_flux_kg_m2_s": float(right_flux[IDX_RHO]),
        "mass_flux_mismatch_kg_m2_s": float(left_flux[IDX_RHO] - right_flux[IDX_RHO]),
        "left_momentum_flux_pa": float(left_flux[IDX_MOM]),
        "right_momentum_flux_pa": float(right_flux[IDX_MOM]),
        "momentum_flux_difference_pa": float(left_flux[IDX_MOM] - right_flux[IDX_MOM]),
        "left_energy_flux_w_m2": float(left_flux[IDX_RHOE]),
        "right_energy_flux_w_m2": float(right_flux[IDX_RHOE]),
        "energy_flux_mismatch_w_m2": float(left_flux[IDX_RHOE] - right_flux[IDX_RHOE]),
        "left_vapor_mass_flux_kg_m2_s": float(left_flux[IDX_RHO_XV]),
        "right_vapor_mass_flux_kg_m2_s": float(right_flux[IDX_RHO_XV]),
        "vapor_mass_flux_mismatch_kg_m2_s": float(left_flux[IDX_RHO_XV] - right_flux[IDX_RHO_XV]),
        "actual_q_from_left_mass_flux_m3_s": actual_q_left,
        "actual_q_from_right_mass_flux_m3_s": actual_q_right,
        "limited_target_q_m3_s": q_limited,
        "mach_cap_active": cap_active,
    }
    return valve_row, flux_row


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _relative_mismatch(rows: list[dict[str, Any]], mismatch_key: str, left_key: str, right_key: str) -> float:
    maximum = 0.0
    for row in rows:
        scale = max(abs(float(row[left_key])), abs(float(row[right_key])), 1.0)
        maximum = max(maximum, abs(float(row[mismatch_key])) / scale)
    return float(maximum)


def _report_lines(metrics: dict[str, Any]) -> list[str]:
    return [
        "# CoolProp internal valve operation observation",
        "",
        "> Guardrail: software/numerical verification only; physical Validation = false; design-use acceptance = false; property_backend_design_status = not_approved_for_design_use.",
        "",
        f"- operation_kind: {metrics['operation_kind']}",
        f"- overall_observation_execution_pass: {metrics['overall_observation_execution_pass']}",
        f"- property_backend_name: {metrics['property_backend_name']}",
        f"- CoolProp version: {metrics['coolprop_version']}",
        f"- opening history monotonic: {metrics['opening_history_monotonic']}",
        f"- max relative mass-flux mismatch: {metrics['max_relative_mass_flux_mismatch']:.6g}",
        f"- max relative energy-flux mismatch: {metrics['max_relative_energy_flux_mismatch']:.6g}",
        f"- max relative vapor-mass-flux mismatch: {metrics['max_relative_vapor_mass_flux_mismatch']:.6g}",
        f"- max relative Q mismatch: {metrics['max_relative_q_mismatch']:.6g}",
        f"- closed samples: {metrics['closed_sample_count']}",
        f"- Mach cap activations: {metrics['mach_cap_activation_count']}",
        "",
        "The valve-loss proxy is diagnostic only and is not removed from rhoE.",
        "Momentum flux may differ across the two valve sides because the valve body exerts force.",
        "No formal regression or design-accuracy band is defined by this baseline observation.",
    ]


def run_coolprop_internal_valve_operation(
    output_dir: Path | str | None = None,
    config: CoolPropInternalValveOperationConfig | None = None,
) -> dict[str, Any]:
    """Run one V-012 baseline operation case and write traceable artifacts."""

    cfg = config or CoolPropInternalValveOperationConfig()
    solver, context = build_coolprop_internal_valve_operation_solver(cfg)
    interface: InternalValveInterface = context["interface"]
    target_time, first_external_arrival = _target_time(cfg, solver, context)
    probes = _probe_specs(cfg, solver)

    probe_history = _sample_probes(solver, probes, 0.0)
    valve_history: list[dict[str, Any]] = []
    flux_history: list[dict[str, Any]] = []
    dts: list[float] = []

    prim0 = solver.primitive()
    p_min = float(np.min(prim0.p))
    T_min = float(np.min(prim0.T))
    rho_min = float(np.min(prim0.rho))
    c_min = float(np.min(prim0.c))
    max_xv = float(np.max(prim0.xv))
    max_alpha = float(np.max(prim0.alpha))

    for _ in range(cfg.max_steps):
        if solver.t >= target_time:
            break
        dt_s = solver.compute_dt(target_time)
        valve_row, flux_row = internal_valve_flux_snapshot(
            solver,
            interface,
            dt_s=dt_s,
        )
        valve_history.append(valve_row)
        flux_history.append(flux_row)
        solver.step(dt_s)
        dts.append(float(dt_s))
        prim = solver.primitive()
        p_min = min(p_min, float(np.min(prim.p)))
        T_min = min(T_min, float(np.min(prim.T)))
        rho_min = min(rho_min, float(np.min(prim.rho)))
        c_min = min(c_min, float(np.min(prim.c)))
        max_xv = max(max_xv, float(np.max(prim.xv)))
        max_alpha = max(max_alpha, float(np.max(prim.alpha)))
        if solver.step_count % cfg.sample_every == 0 or solver.t >= target_time:
            probe_history.extend(_sample_probes(solver, probes, dt_s))

    final_valve_row, final_flux_row = internal_valve_flux_snapshot(solver, interface)
    valve_history.append(final_valve_row)
    flux_history.append(final_flux_row)
    final_primitive = solver.primitive()
    diagnostics = solver.diagnostics(dt=0.0)
    missing_budget_fields = [
        key
        for key in (
            "budget_mass_residual",
            "energy_budget_balance_residual_j",
            "phase_vapor_mass_balance_residual_kg",
        )
        if key not in diagnostics
    ]
    histories_finite = all(
        np.isfinite(float(value))
        for history in (valve_history, flux_history, probe_history)
        for row in history
        for value in row.values()
        if isinstance(value, (int, float))
    )

    max_relative_mass = _relative_mismatch(
        flux_history,
        "mass_flux_mismatch_kg_m2_s",
        "left_mass_flux_kg_m2_s",
        "right_mass_flux_kg_m2_s",
    )
    max_relative_energy = _relative_mismatch(
        flux_history,
        "energy_flux_mismatch_w_m2",
        "left_energy_flux_w_m2",
        "right_energy_flux_w_m2",
    )
    max_relative_vapor = _relative_mismatch(
        flux_history,
        "vapor_mass_flux_mismatch_kg_m2_s",
        "left_vapor_mass_flux_kg_m2_s",
        "right_vapor_mass_flux_kg_m2_s",
    )
    q_errors = []
    for row in valve_history:
        target_q = float(row["limited_target_q_m3_s"])
        actual_q = float(row["actual_q_from_left_mass_flux_m3_s"])
        scale = max(abs(target_q), 1.0e-12)
        q_errors.append(abs(actual_q - target_q) / scale)
    max_relative_q = max(q_errors, default=0.0)
    closed_rows = [row for row in flux_history if float(row["opening"]) <= interface.closed_opening_tol]
    max_closed_mass = max(
        (max(abs(float(row["left_mass_flux_kg_m2_s"])), abs(float(row["right_mass_flux_kg_m2_s"]))) for row in closed_rows),
        default=0.0,
    )
    max_closed_energy = max(
        (max(abs(float(row["left_energy_flux_w_m2"])), abs(float(row["right_energy_flux_w_m2"]))) for row in closed_rows),
        default=0.0,
    )
    max_closed_vapor = max(
        (max(abs(float(row["left_vapor_mass_flux_kg_m2_s"])), abs(float(row["right_vapor_mass_flux_kg_m2_s"]))) for row in closed_rows),
        default=0.0,
    )
    openings = [float(row["opening"]) for row in valve_history]
    opening_monotonic = opening_history_is_monotonic(openings, cfg.operation_kind)
    mach_cap_count = sum(bool(row["mach_cap_active"]) for row in valve_history)

    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_name": "coolprop_co2",
        "property_backend_design_status": "not_approved_for_design_use",
        "coolprop_available": coolprop_available(),
        "coolprop_version": _coolprop_version(),
        "operation_kind": cfg.operation_kind,
        "n_cells": cfg.n_cells,
        "dx_m": float(solver.grid.dx),
        "cfl_target": cfg.cfl,
        "valve_left_cell": int(context["left_cell"]),
        "valve_right_cell": int(context["right_cell"]),
        "kv_m3_per_h": cfg.kv_m3_per_h,
        "allow_reverse_flow": cfg.allow_reverse_flow,
        "max_mach": cfg.max_mach,
        "target_time_s": target_time,
        "first_external_boundary_arrival_s": first_external_arrival,
        "evaluation_window_uncontaminated": bool(target_time < first_external_arrival),
        "final_time_s": float(solver.t),
        "reached_target_time": bool(solver.t >= target_time),
        "within_max_steps": bool(solver.step_count <= cfg.max_steps),
        "step_count": int(solver.step_count),
        "min_positive_dt_s": min(dts) if dts else 0.0,
        "max_dt_s": max(dts) if dts else 0.0,
        "all_history_finite": bool(histories_finite),
        "positive_pressure": bool(p_min > 0.0),
        "positive_temperature": bool(T_min > 0.0),
        "positive_density": bool(rho_min > 0.0),
        "positive_sound_speed": bool(c_min > 0.0),
        "remained_single_phase": bool(max_xv <= 1.0e-12 and max_alpha <= 1.0e-12),
        "max_vapor_mass_fraction": max_xv,
        "max_alpha": max_alpha,
        "missing_budget_fields": missing_budget_fields,
        "budget_mass_relative_residual": float(diagnostics.get("budget_mass_relative_residual", np.nan)),
        "energy_budget_balance_relative_residual": float(diagnostics.get("energy_budget_balance_relative_residual", np.nan)),
        "phase_vapor_mass_balance_relative_residual": float(diagnostics.get("phase_vapor_mass_balance_relative_residual", np.nan)),
        "opening_history_monotonic": opening_monotonic,
        "max_relative_mass_flux_mismatch": max_relative_mass,
        "max_relative_energy_flux_mismatch": max_relative_energy,
        "max_relative_vapor_mass_flux_mismatch": max_relative_vapor,
        "max_relative_q_mismatch": float(max_relative_q),
        "closed_sample_count": len(closed_rows),
        "max_closed_mass_flux_kg_m2_s": float(max_closed_mass),
        "max_closed_energy_flux_w_m2": float(max_closed_energy),
        "max_closed_vapor_mass_flux_kg_m2_s": float(max_closed_vapor),
        "mach_cap_activation_count": int(mach_cap_count),
        "mach_cap_activation_tracked": True,
        "valve_history_row_count": len(valve_history),
        "interface_flux_history_row_count": len(flux_history),
        "probe_history_row_count": len(probe_history),
        "valve_loss_proxy_diagnostic_only": True,
        "valve_loss_proxy_removed_from_rhoE": False,
    }
    invariant_tolerance = 1.0e-12
    metrics["common_flux_invariants_pass"] = bool(
        max_relative_mass <= invariant_tolerance
        and max_relative_energy <= invariant_tolerance
        and max_relative_vapor <= invariant_tolerance
        and max_relative_q <= invariant_tolerance
    )
    metrics["closed_wall_invariants_pass"] = bool(
        not closed_rows
        or (
            max_closed_mass <= invariant_tolerance
            and max_closed_energy <= invariant_tolerance
            and max_closed_vapor <= invariant_tolerance
        )
    )
    metrics["overall_observation_execution_pass"] = bool(
        all(
            [
                metrics["reached_target_time"],
                metrics["within_max_steps"],
                metrics["evaluation_window_uncontaminated"],
                metrics["all_history_finite"],
                metrics["positive_pressure"],
                metrics["positive_temperature"],
                metrics["positive_density"],
                metrics["positive_sound_speed"],
                metrics["remained_single_phase"],
                not metrics["missing_budget_fields"],
                metrics["opening_history_monotonic"],
                metrics["common_flux_invariants_pass"],
                metrics["closed_wall_invariants_pass"],
                metrics["mach_cap_activation_tracked"],
            ]
        )
    )

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
        _write_csv(directory / f"{stem}_valve_history.csv", valve_history)
        _write_csv(directory / f"{stem}_interface_flux_history.csv", flux_history)
        _write_csv(directory / f"{stem}_probe_history.csv", probe_history)
        final_profile = [
            {
                "cell_index": int(index),
                "x_m": float(solver.grid.cell_centers[index]),
                "pressure_pa": float(final_primitive.p[index]),
                "velocity_m_s": float(final_primitive.u[index]),
                "temperature_K": float(final_primitive.T[index]),
                "density_kg_m3": float(final_primitive.rho[index]),
                "sound_speed_m_s": float(final_primitive.c[index]),
                "vapor_mass_fraction": float(final_primitive.xv[index]),
                "alpha": float(final_primitive.alpha[index]),
            }
            for index in range(cfg.n_cells)
        ]
        _write_csv(directory / f"{stem}_final_profile.csv", final_profile)
        (directory / f"{stem}_report.md").write_text(
            "\n".join(_report_lines(metrics)) + "\n",
            encoding="utf-8",
        )
    return metrics
