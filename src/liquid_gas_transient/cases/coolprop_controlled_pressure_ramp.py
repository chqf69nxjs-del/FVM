"""Stage 6 controlled-pressure-ramp numerical verification runner.

This is software/numerical verification only. It is not physical Validation,
design-use acceptance, or an actual tank-operation model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..boundary import LinearPressureRamp, PressureTankBoundary, TransmissiveBoundary
from ..boundary_history import record_solver_boundary_telemetry, write_boundary_history_csv
from ..boundary_telemetry import BoundaryTelemetryRecorder
from ..config import PipeGeometry
from ..eos import LCO2PropertyEOSAdapter
from ..grid import UniformGrid
from ..phase_change import NoPhaseChange
from ..properties import CoolPropCO2Backend, coolprop_available
from ..solver import FvmSolver
from ..source_terms import NoSource
from ..state import make_conserved
from ..verification.boundary_reflection import characteristic_amplitudes


@dataclass(frozen=True)
class CoolPropControlledPressureRampConfig:
    """Configuration for the first Stage 6 pressure-ramp observation."""

    case_name: str = "coolprop_controlled_pressure_ramp"
    output_version: str = "coolprop_controlled_pressure_ramp_v1"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    n_cells: int = 100
    cfl: float = 0.5
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    pressure_change_pa: float = 1.0e3
    ramp_start_s: float = 5.0e-3
    ramp_duration_s: float = 1.0e-2
    probe_fractions: tuple[float, ...] = (0.25, 0.50, 0.75)
    sample_every: int = 1
    max_steps: int = 20000
    t_end_s: float | None = None
    post_arrival_margin_fraction: float = 0.10
    max_perturbation_ratio: float = 1.0e-3

    def __post_init__(self) -> None:
        if self.pipe_length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.n_cells < 10:
            raise ValueError("n_cells must be at least 10")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.initial_pressure_pa <= 0.0 or self.initial_temperature_K <= 0.0:
            raise ValueError("initial pressure and temperature must be positive")
        if self.pressure_change_pa == 0.0:
            raise ValueError("pressure_change_pa must be nonzero")
        if self.final_pressure_pa <= 0.0:
            raise ValueError("final pressure must be positive")
        if abs(self.pressure_change_pa) / self.initial_pressure_pa > self.max_perturbation_ratio:
            raise ValueError("pressure change is too large for the small-amplitude case")
        if self.ramp_start_s < 0.0 or self.ramp_duration_s < 0.0:
            raise ValueError("ramp times must be non-negative")
        if not self.probe_fractions:
            raise ValueError("at least one probe is required")
        if any(not 0.0 < value < 1.0 for value in self.probe_fractions):
            raise ValueError("probe fractions must lie in (0, 1)")
        if tuple(sorted(set(self.probe_fractions))) != self.probe_fractions:
            raise ValueError("probe_fractions must be unique and ascending")
        if self.sample_every <= 0 or self.max_steps <= 0:
            raise ValueError("sample_every and max_steps must be positive")
        if self.t_end_s is not None and self.t_end_s <= self.ramp_start_s:
            raise ValueError("t_end_s must be after ramp_start_s")
        if self.post_arrival_margin_fraction <= 0.0:
            raise ValueError("post_arrival_margin_fraction must be positive")

    @property
    def final_pressure_pa(self) -> float:
        return float(self.initial_pressure_pa + self.pressure_change_pa)

    @property
    def ramp_end_s(self) -> float:
        return float(self.ramp_start_s + self.ramp_duration_s)


def pressure_ramp_fraction(t_s: float, config: CoolPropControlledPressureRampConfig) -> float:
    """Return prescribed ramp completion in the closed interval [0, 1]."""

    if t_s < config.ramp_start_s:
        return 0.0
    if config.ramp_duration_s == 0.0:
        return 1.0
    return float(np.clip((t_s - config.ramp_start_s) / config.ramp_duration_s, 0.0, 1.0))


def requested_boundary_pressure_pa(
    t_s: float,
    config: CoolPropControlledPressureRampConfig,
) -> float:
    return float(
        config.initial_pressure_pa
        + pressure_ramp_fraction(t_s, config) * config.pressure_change_pa
    )


def _coolprop_version() -> str:
    try:
        return importlib.metadata.version("CoolProp")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def build_coolprop_controlled_pressure_ramp_solver(
    config: CoolPropControlledPressureRampConfig | None = None,
) -> tuple[FvmSolver, dict[str, Any]]:
    """Build a uniform, initially stationary pipe with a right pressure ramp."""

    cfg = config or CoolPropControlledPressureRampConfig()
    backend = CoolPropCO2Backend()
    eos = LCO2PropertyEOSAdapter(
        backend=backend,
        boundary_temperature_K=cfg.initial_temperature_K,
        quality_source="transported",
    )
    rho0 = float(np.asarray(backend.density_from_pT(cfg.initial_pressure_pa, cfg.initial_temperature_K)))
    e0 = float(np.asarray(backend.internal_energy_from_pT(cfg.initial_pressure_pa, cfg.initial_temperature_K)))
    reference_state = make_conserved(rho=rho0, u=0.0, e=e0, xv=0.0)
    reference_primitive = eos.primitive_from_conserved(reference_state)
    c0 = float(np.asarray(reference_primitive.c))
    quality0 = float(np.asarray(reference_primitive.xv))
    alpha0 = float(np.asarray(reference_primitive.alpha))
    if not all(np.isfinite(value) and value > 0.0 for value in (rho0, e0, c0)):
        raise ValueError("CoolProp reference state must be finite and positive")
    if abs(quality0) > 1.0e-12 or abs(alpha0) > 1.0e-12:
        raise ValueError("reference state must remain single phase")

    grid = UniformGrid(PipeGeometry(cfg.pipe_length_m, cfg.diameter_m), cfg.n_cells)
    U = make_conserved(
        rho=np.full(cfg.n_cells, rho0),
        u=np.zeros(cfg.n_cells),
        e=np.full(cfg.n_cells, e0),
        xv=np.zeros(cfg.n_cells),
    )
    schedule = LinearPressureRamp(
        p_initial_pa=cfg.initial_pressure_pa,
        p_final_pa=cfg.final_pressure_pa,
        t_start_s=cfg.ramp_start_s,
        duration_s=cfg.ramp_duration_s,
    )
    right_boundary = PressureTankBoundary(
        pressure_schedule=schedule,
        flow_direction="bidirectional",
        velocity_policy="copy",
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=cfg.cfl,
        left_boundary=TransmissiveBoundary(),
        right_boundary=right_boundary,
        source_term=NoSource(),
        phase_change=NoPhaseChange(),
        internal_interfaces=(),
        latent_heat_placeholder_j_kg=0.0,
    )
    return solver, {
        "reference": {"rho0": rho0, "e0": e0, "c0": c0},
        "schedule": schedule,
        "right_boundary": right_boundary,
    }


def _probe_specs(cfg: CoolPropControlledPressureRampConfig, solver: FvmSolver) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for fraction in cfg.probe_fractions:
        target = fraction * cfg.pipe_length_m
        index = int(np.argmin(np.abs(solver.grid.cell_centers - target)))
        specs.append({
            "probe_name": f"x_over_L_{fraction:g}",
            "probe_target_x_m": float(target),
            "probe_cell_index": index,
            "probe_cell_center_x_m": float(solver.grid.cell_centers[index]),
        })
    return specs


def _target_time(
    cfg: CoolPropControlledPressureRampConfig,
    c0: float,
    probes: list[dict[str, Any]],
) -> float:
    if cfg.t_end_s is not None:
        return float(cfg.t_end_s)
    farthest_distance = max(
        cfg.pipe_length_m - float(probe["probe_cell_center_x_m"])
        for probe in probes
    )
    return float(
        cfg.ramp_end_s
        + farthest_distance / c0
        + cfg.post_arrival_margin_fraction * cfg.pipe_length_m / c0
    )


def _sample_probes(
    solver: FvmSolver,
    cfg: CoolPropControlledPressureRampConfig,
    probes: list[dict[str, Any]],
    rho0: float,
    c0: float,
    dt_s: float,
) -> list[dict[str, Any]]:
    prim = solver.primitive()
    rows: list[dict[str, Any]] = []
    for probe in probes:
        index = int(probe["probe_cell_index"])
        dp = float(prim.p[index] - cfg.initial_pressure_pa)
        velocity = float(prim.u[index])
        a_plus, a_minus = characteristic_amplitudes(dp, velocity, rho0, c0)
        rows.append({
            "time_s": float(solver.t),
            "step": int(solver.step_count),
            "dt_s": float(dt_s),
            **probe,
            "pressure_pa": float(prim.p[index]),
            "delta_pressure_pa": dp,
            "velocity_m_s": velocity,
            "A_plus_pa": float(a_plus),
            "A_minus_pa": float(a_minus),
            "temperature_K": float(prim.T[index]),
            "density_kg_m3": float(prim.rho[index]),
            "sound_speed_m_s": float(prim.c[index]),
            "vapor_mass_fraction": float(prim.xv[index]),
            "alpha": float(prim.alpha[index]),
        })
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_coolprop_controlled_pressure_ramp(
    output_dir: Path | str | None = None,
    config: CoolPropControlledPressureRampConfig | None = None,
) -> dict[str, Any]:
    """Run the first controlled-pressure-ramp baseline observation."""

    cfg = config or CoolPropControlledPressureRampConfig()
    solver, context = build_coolprop_controlled_pressure_ramp_solver(cfg)
    reference = context["reference"]
    right_boundary: PressureTankBoundary = context["right_boundary"]
    probes = _probe_specs(cfg, solver)
    target_time = _target_time(cfg, float(reference["c0"]), probes)

    recorder = BoundaryTelemetryRecorder(area_m2=solver.grid.geometry.area_m2)
    probe_history = _sample_probes(
        solver, cfg, probes, float(reference["rho0"]), float(reference["c0"]), 0.0
    )
    schedule_history: list[dict[str, Any]] = []
    dts: list[float] = []

    for _ in range(cfg.max_steps):
        if solver.t >= target_time:
            break
        dt_s = solver.compute_dt(target_time)
        requested = requested_boundary_pressure_pa(solver.t, cfg)
        actual = float(right_boundary.pressure_pa(solver.t))
        schedule_history.append({
            "time_s": float(solver.t),
            "step": int(solver.step_count + 1),
            "dt_s": float(dt_s),
            "ramp_fraction": pressure_ramp_fraction(solver.t, cfg),
            "requested_boundary_pressure_pa": requested,
            "actual_schedule_pressure_pa": actual,
            "schedule_pressure_error_pa": float(actual - requested),
        })
        record_solver_boundary_telemetry(solver, recorder, dt_s)
        solver.step(dt_s)
        dts.append(float(dt_s))
        if solver.step_count % cfg.sample_every == 0 or solver.t >= target_time:
            probe_history.extend(
                _sample_probes(
                    solver,
                    cfg,
                    probes,
                    float(reference["rho0"]),
                    float(reference["c0"]),
                    dt_s,
                )
            )

    boundary_history = recorder.rows()
    final_primitive = solver.primitive()
    diagnostics = solver.diagnostics(dt=0.0)
    missing_budget_fields = [
        key for key in (
            "budget_mass_residual",
            "energy_budget_balance_residual_j",
            "phase_vapor_mass_balance_residual_kg",
        ) if key not in diagnostics
    ]
    histories_finite = all(
        np.isfinite(float(value))
        for history in (schedule_history, probe_history, boundary_history)
        for row in history
        for value in row.values()
        if isinstance(value, (int, float))
    )
    max_schedule_error = max(
        (abs(float(row["schedule_pressure_error_pa"])) for row in schedule_history),
        default=0.0,
    )
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
        "n_cells": cfg.n_cells,
        "dx_m": float(solver.grid.dx),
        "cfl_target": cfg.cfl,
        "initial_pressure_pa": cfg.initial_pressure_pa,
        "final_pressure_pa": cfg.final_pressure_pa,
        "pressure_change_pa": cfg.pressure_change_pa,
        "ramp_start_s": cfg.ramp_start_s,
        "ramp_duration_s": cfg.ramp_duration_s,
        "ramp_end_s": cfg.ramp_end_s,
        "rho0": float(reference["rho0"]),
        "e0": float(reference["e0"]),
        "c0": float(reference["c0"]),
        "target_time_s": target_time,
        "final_time_s": float(solver.t),
        "reached_target_time": bool(solver.t >= target_time),
        "within_max_steps": bool(solver.step_count <= cfg.max_steps),
        "step_count": int(solver.step_count),
        "min_positive_dt_s": min(dts) if dts else 0.0,
        "max_dt_s": max(dts) if dts else 0.0,
        "all_history_finite": bool(histories_finite),
        "positive_pressure": bool(np.min(final_primitive.p) > 0.0),
        "positive_temperature": bool(np.min(final_primitive.T) > 0.0),
        "positive_density": bool(np.min(final_primitive.rho) > 0.0),
        "positive_sound_speed": bool(np.min(final_primitive.c) > 0.0),
        "remained_single_phase": bool(
            np.max(final_primitive.xv) <= 1.0e-12
            and np.max(final_primitive.alpha) <= 1.0e-12
        ),
        "max_vapor_mass_fraction": float(np.max(final_primitive.xv)),
        "max_alpha": float(np.max(final_primitive.alpha)),
        "missing_budget_fields": missing_budget_fields,
        "budget_mass_relative_residual": float(diagnostics.get("budget_mass_relative_residual", np.nan)),
        "energy_budget_balance_relative_residual": float(diagnostics.get("energy_budget_balance_relative_residual", np.nan)),
        "phase_vapor_mass_balance_relative_residual": float(diagnostics.get("phase_vapor_mass_balance_relative_residual", np.nan)),
        "schedule_sample_count": len(schedule_history),
        "probe_sample_count": len(probe_history),
        "boundary_history_row_count": len(boundary_history),
        "max_abs_schedule_pressure_error_pa": float(max_schedule_error),
    }
    metrics["overall_observation_execution_pass"] = bool(all([
        metrics["reached_target_time"],
        metrics["within_max_steps"],
        metrics["all_history_finite"],
        metrics["positive_pressure"],
        metrics["positive_temperature"],
        metrics["positive_density"],
        metrics["positive_sound_speed"],
        metrics["remained_single_phase"],
        not metrics["missing_budget_fields"],
        metrics["max_abs_schedule_pressure_error_pa"] <= 1.0e-12,
    ]))

    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        stem = cfg.case_name
        (directory / f"{stem}_config.json").write_text(
            json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8"
        )
        (directory / f"{stem}_metrics.json").write_text(
            json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv(directory / f"{stem}_pressure_schedule.csv", schedule_history)
        _write_csv(directory / f"{stem}_probe_history.csv", probe_history)
        write_boundary_history_csv(directory / f"{stem}_boundary_history.csv", boundary_history)

    return metrics
