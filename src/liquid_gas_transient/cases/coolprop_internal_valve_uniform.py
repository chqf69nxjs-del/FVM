"""Stage 6 V-012A uniform-state internal-valve verification runner.

This module verifies the existing single-phase ``InternalValveInterface`` path
without changing solver physics, the Kv law, or conserved-energy treatment. It
is software / numerical verification only, not physical Validation or
design-use acceptance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..boundary import TransmissiveBoundary
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
from ..state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    make_conserved,
)
from ..valve import ConstantOpening, KvLiquidValve
from ..verification.boundary_reflection import characteristic_amplitudes


@dataclass(frozen=True)
class CoolPropInternalValveUniformConfig:
    """Configuration for the first V-012 internal-valve baseline."""

    case_name: str = "coolprop_internal_valve_uniform"
    output_version: str = "coolprop_internal_valve_uniform_v1"
    pipe_length_m: float = 100.0
    diameter_m: float = 0.30
    n_cells: int = 100
    cfl: float = 0.5
    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    constant_opening: float = 0.5
    calibration_delta_p_pa: float = 1.0e3
    target_full_open_face_velocity_m_s: float = 1.0e-3
    max_mach: float = 0.8
    probe_fractions: tuple[float, ...] = (0.25, 0.375, 0.625, 0.75)
    acoustic_duration_fraction: float = 0.25
    t_end_s: float | None = None
    sample_every: int = 1
    max_steps: int = 20000
    relative_budget_roundoff_tolerance: float = 1.0e-12

    def __post_init__(self) -> None:
        if self.pipe_length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.n_cells < 10 or self.n_cells % 2 != 0:
            raise ValueError("n_cells must be an even integer of at least 10")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.initial_pressure_pa <= 0.0 or self.initial_temperature_K <= 0.0:
            raise ValueError("initial pressure and temperature must be positive")
        if not 0.0 < self.constant_opening <= 1.0:
            raise ValueError("constant_opening must be in (0, 1]")
        if self.calibration_delta_p_pa <= 0.0:
            raise ValueError("calibration_delta_p_pa must be positive")
        if self.target_full_open_face_velocity_m_s <= 0.0:
            raise ValueError(
                "target_full_open_face_velocity_m_s must be positive"
            )
        if not 0.0 < self.max_mach <= 1.0:
            raise ValueError("max_mach must be in (0, 1]")
        if not self.probe_fractions:
            raise ValueError("at least one probe is required")
        if any(not 0.0 < value < 1.0 for value in self.probe_fractions):
            raise ValueError("probe fractions must lie in (0, 1)")
        if tuple(sorted(set(self.probe_fractions))) != self.probe_fractions:
            raise ValueError("probe_fractions must be unique and ascending")
        if self.acoustic_duration_fraction <= 0.0:
            raise ValueError("acoustic_duration_fraction must be positive")
        if self.t_end_s is not None and self.t_end_s <= 0.0:
            raise ValueError("t_end_s must be positive")
        if self.sample_every <= 0 or self.max_steps <= 0:
            raise ValueError("sample_every and max_steps must be positive")
        if self.relative_budget_roundoff_tolerance <= 0.0:
            raise ValueError(
                "relative_budget_roundoff_tolerance must be positive"
            )


def _coolprop_version() -> str:
    try:
        return importlib.metadata.version("CoolProp")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def opening_roundoff_tolerance(
    config: CoolPropInternalValveUniformConfig,
) -> float:
    """Return an 8-ULP opening-schedule tolerance."""

    return float(8.0 * np.spacing(max(abs(config.constant_opening), 1.0)))


def _roundoff_tolerance(*values: float, multiplier: float = 128.0) -> float:
    scale = max((abs(float(value)) for value in values), default=1.0)
    return float(multiplier * np.finfo(float).eps * max(scale, 1.0))


def build_coolprop_internal_valve_uniform_solver(
    config: CoolPropInternalValveUniformConfig | None = None,
) -> tuple[FvmSolver, dict[str, Any]]:
    """Build a uniform stationary pipe containing a midpoint internal valve."""

    cfg = config or CoolPropInternalValveUniformConfig()
    backend = CoolPropCO2Backend()
    eos = LCO2PropertyEOSAdapter(
        backend=backend,
        boundary_temperature_K=cfg.initial_temperature_K,
        quality_source="transported",
    )

    rho0 = float(
        np.asarray(
            backend.density_from_pT(
                cfg.initial_pressure_pa,
                cfg.initial_temperature_K,
            )
        )
    )
    e0 = float(
        np.asarray(
            backend.internal_energy_from_pT(
                cfg.initial_pressure_pa,
                cfg.initial_temperature_K,
            )
        )
    )
    reference_state = make_conserved(rho=rho0, u=0.0, e=e0, xv=0.0)
    reference_primitive = eos.primitive_from_conserved(
        reference_state[np.newaxis, :]
    )
    p0 = float(reference_primitive.p[0])
    T0 = float(reference_primitive.T[0])
    c0 = float(reference_primitive.c[0])
    quality0 = float(reference_primitive.xv[0])
    alpha0 = float(reference_primitive.alpha[0])

    if not all(
        np.isfinite(value) and value > 0.0
        for value in (rho0, e0, p0, T0, c0)
    ):
        raise ValueError("CoolProp reference state must be finite and positive")
    if abs(quality0) > 1.0e-12 or abs(alpha0) > 1.0e-12:
        raise ValueError("reference state must remain single phase")

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
        rho_kg_m3=rho0,
        opening=1.0,
    )
    valve = KvLiquidValve(
        kv_m3_per_h=kv_m3_per_h,
        allow_reverse_flow=False,
    )
    opening_schedule = ConstantOpening(cfg.constant_opening)
    left_cell = cfg.n_cells // 2 - 1
    interface = InternalValveInterface(
        left_cell=left_cell,
        area_m2=area_m2,
        valve=valve,
        opening_schedule=opening_schedule,
        max_mach=cfg.max_mach,
    )

    U = make_conserved(
        rho=np.full(cfg.n_cells, rho0),
        u=np.zeros(cfg.n_cells),
        e=np.full(cfg.n_cells, e0),
        xv=np.zeros(cfg.n_cells),
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

    return solver, {
        "reference": {
            "rho0": rho0,
            "e0": e0,
            "p0": p0,
            "T0": T0,
            "c0": c0,
        },
        "interface": interface,
        "kv_m3_per_h": kv_m3_per_h,
        "calibration_q_m3_s": calibration_q_m3_s,
        "valve_x_m": float((left_cell + 1) * grid.dx),
    }


def _probe_specs(
    cfg: CoolPropInternalValveUniformConfig,
    solver: FvmSolver,
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for fraction in cfg.probe_fractions:
        target = fraction * cfg.pipe_length_m
        index = int(
            np.argmin(np.abs(solver.grid.cell_centers - target))
        )
        specs.append(
            {
                "probe_name": f"x_over_L_{fraction:g}",
                "probe_target_x_m": float(target),
                "probe_cell_index": index,
                "probe_cell_center_x_m": float(
                    solver.grid.cell_centers[index]
                ),
            }
        )
    return specs


def _target_time(
    cfg: CoolPropInternalValveUniformConfig,
    c0: float,
) -> float:
    if cfg.t_end_s is not None:
        return float(cfg.t_end_s)
    return float(
        cfg.acoustic_duration_fraction * cfg.pipe_length_m / c0
    )


def _sample_probes(
    solver: FvmSolver,
    probes: list[dict[str, Any]],
    *,
    p0: float,
    rho0: float,
    c0: float,
    dt_s: float,
) -> list[dict[str, Any]]:
    prim = solver.primitive()
    rows: list[dict[str, Any]] = []
    for probe in probes:
        index = int(probe["probe_cell_index"])
        dp = float(prim.p[index] - p0)
        velocity = float(prim.u[index])
        a_plus, a_minus = characteristic_amplitudes(
            dp,
            velocity,
            rho0,
            c0,
        )
        rows.append(
            {
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
            }
        )
    return rows


def _sample_valve(
    solver: FvmSolver,
    interface: InternalValveInterface,
    *,
    requested_opening: float,
    valve_x_m: float,
    dt_s: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    F_l, F_r, flow = interface.evaluate_fluxes(
        U=solver.U,
        eos=solver.eos,
        t=solver.t,
        flux_function=solver.flux_function,
    )
    area_m2 = float(solver.grid.geometry.area_m2)
    rho_upwind = float(flow["rho_upwind_kg_m3"])
    mass_flow_kg_s = float(area_m2 * F_l[IDX_RHO])
    flux_q_m3_s = float(
        mass_flow_kg_s / rho_upwind if rho_upwind > 0.0 else np.nan
    )
    applied_q = float(flow["applied_q_m3_s"])

    schedule_row = {
        "time_s": float(solver.t),
        "step": int(solver.step_count + 1),
        "dt_s": float(dt_s),
        "opening_requested": float(requested_opening),
        "opening_actual": float(flow["opening"]),
        "opening_error": float(flow["opening"]) - float(requested_opening),
        "effective_kv_m3_per_h": float(flow["effective_kv_m3_per_h"]),
    }
    valve_row = {
        **schedule_row,
        "valve_left_cell": int(interface.left_cell),
        "valve_right_cell": int(interface.right_cell),
        "valve_x_m": float(valve_x_m),
        "p_left_pa": float(flow["p_left_pa"]),
        "p_right_pa": float(flow["p_right_pa"]),
        "delta_p_pa": float(flow["delta_p_pa"]),
        "rho_left_kg_m3": float(flow["rho_left_kg_m3"]),
        "rho_right_kg_m3": float(flow["rho_right_kg_m3"]),
        "temperature_left_K": float(flow["temperature_left_K"]),
        "temperature_right_K": float(flow["temperature_right_K"]),
        "velocity_left_m_s": float(flow["velocity_left_m_s"]),
        "velocity_right_m_s": float(flow["velocity_right_m_s"]),
        "sound_speed_left_m_s": float(flow["sound_speed_left_m_s"]),
        "sound_speed_right_m_s": float(flow["sound_speed_right_m_s"]),
        "upwind_side": str(flow["upwind_side"]),
        "rho_upwind_kg_m3": rho_upwind,
        "raw_target_q_m3_s": float(flow["raw_target_q_m3_s"]),
        "q_limit_m3_s": float(flow["q_limit_m3_s"]),
        "applied_q_m3_s": applied_q,
        "applied_face_velocity_m_s": float(
            flow["applied_face_velocity_m_s"]
        ),
        "applied_face_mach": float(flow["applied_face_mach"]),
        "mach_cap_active": bool(flow["mach_cap_active"]),
        "hydraulic_separation_active": bool(
            flow["hydraulic_separation_active"]
        ),
        "flow_direction": str(flow["flow_direction"]),
        "valve_loss_power_proxy_w": float(
            flow["applied_valve_loss_power_proxy_w"]
        ),
    }
    flux_row = {
        "time_s": float(solver.t),
        "step": int(solver.step_count + 1),
        "dt_s": float(dt_s),
        "valve_left_cell": int(interface.left_cell),
        "valve_right_cell": int(interface.right_cell),
        "valve_x_m": float(valve_x_m),
        "left_mass_flux_kg_m2_s": float(F_l[IDX_RHO]),
        "right_mass_flux_kg_m2_s": float(F_r[IDX_RHO]),
        "mass_flux_mismatch_kg_m2_s": float(
            F_l[IDX_RHO] - F_r[IDX_RHO]
        ),
        "left_momentum_flux_pa": float(F_l[IDX_MOM]),
        "right_momentum_flux_pa": float(F_r[IDX_MOM]),
        "momentum_flux_difference_pa": float(
            F_l[IDX_MOM] - F_r[IDX_MOM]
        ),
        "expected_momentum_flux_difference_pa": float(flow["delta_p_pa"]),
        "momentum_difference_residual_pa": float(
            (F_l[IDX_MOM] - F_r[IDX_MOM]) - float(flow["delta_p_pa"])
        ),
        "left_energy_flux_w_m2": float(F_l[IDX_RHOE]),
        "right_energy_flux_w_m2": float(F_r[IDX_RHOE]),
        "energy_flux_mismatch_w_m2": float(
            F_l[IDX_RHOE] - F_r[IDX_RHOE]
        ),
        "left_vapor_mass_flux_kg_m2_s": float(F_l[IDX_RHO_XV]),
        "right_vapor_mass_flux_kg_m2_s": float(F_r[IDX_RHO_XV]),
        "vapor_mass_flux_mismatch_kg_m2_s": float(
            F_l[IDX_RHO_XV] - F_r[IDX_RHO_XV]
        ),
        "mass_flow_kg_s": mass_flow_kg_s,
        "energy_flow_w": float(area_m2 * F_l[IDX_RHOE]),
        "vapor_mass_flow_kg_s": float(area_m2 * F_l[IDX_RHO_XV]),
        "flux_derived_q_m3_s": flux_q_m3_s,
        "applied_q_m3_s": applied_q,
        "flux_q_minus_applied_q_m3_s": float(
            flux_q_m3_s - applied_q
        ),
    }
    return schedule_row, valve_row, flux_row


def _final_profile(
    solver: FvmSolver,
    *,
    p0: float,
) -> list[dict[str, Any]]:
    prim = solver.primitive()
    rows: list[dict[str, Any]] = []
    for index, x_m in enumerate(solver.grid.cell_centers):
        rows.append(
            {
                "cell_index": int(index),
                "x_m": float(x_m),
                "pressure_pa": float(prim.p[index]),
                "delta_pressure_pa": float(prim.p[index] - p0),
                "velocity_m_s": float(prim.u[index]),
                "temperature_K": float(prim.T[index]),
                "density_kg_m3": float(prim.rho[index]),
                "sound_speed_m_s": float(prim.c[index]),
                "vapor_mass_fraction": float(prim.xv[index]),
                "alpha": float(prim.alpha[index]),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_observation_report(
    path: Path,
    metrics: dict[str, Any],
) -> None:
    lines = [
        "# V-012A Uniform-State Internal-Valve Observation",
        "",
        "This is software / numerical verification only. It is not physical",
        "Validation, design-use acceptance, or approval of a real valve model.",
        "",
        "## Result",
        "",
        f"- overall observation execution pass: `{metrics['overall_observation_execution_pass']}`",
        f"- property backend: `{metrics['property_backend_name']}`",
        f"- CoolProp version: `{metrics['coolprop_version']}`",
        f"- design-use status: `{metrics['property_backend_design_status']}`",
        f"- constant opening: `{metrics['constant_opening']}`",
        f"- raw target flow maximum: `{metrics['max_abs_raw_target_q_m3_s']:.9e} m3/s`",
        f"- applied flow maximum: `{metrics['max_abs_applied_q_m3_s']:.9e} m3/s`",
        f"- pressure disturbance maximum: `{metrics['max_abs_pressure_disturbance_pa']:.9e} Pa`",
        f"- velocity maximum: `{metrics['max_abs_velocity_m_s']:.9e} m/s`",
        "",
        "## Interpretation",
        "",
        "The nonzero-opening valve is placed in a uniform stationary state with",
        "zero driving pressure difference. The existing implementation therefore",
        "produces zero target flow and uses its explicit hydraulic-separation path.",
        "No material pressure wave or through-flow should be created.",
        "",
        "The hydraulic-loss proxy remains diagnostic and is not removed from",
        "the conserved `rhoE` equation.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_coolprop_internal_valve_uniform(
    output_dir: Path | str | None = None,
    config: CoolPropInternalValveUniformConfig | None = None,
) -> dict[str, Any]:
    """Run the V-012A uniform-state constant-opening observation."""

    cfg = config or CoolPropInternalValveUniformConfig()
    solver, context = build_coolprop_internal_valve_uniform_solver(cfg)
    reference = context["reference"]
    interface: InternalValveInterface = context["interface"]
    probes = _probe_specs(cfg, solver)
    target_time = _target_time(cfg, float(reference["c0"]))

    recorder = BoundaryTelemetryRecorder(
        area_m2=solver.grid.geometry.area_m2
    )
    probe_history = _sample_probes(
        solver,
        probes,
        p0=float(reference["p0"]),
        rho0=float(reference["rho0"]),
        c0=float(reference["c0"]),
        dt_s=0.0,
    )
    schedule_history: list[dict[str, Any]] = []
    valve_history: list[dict[str, Any]] = []
    interface_flux_history: list[dict[str, Any]] = []
    dts: list[float] = []

    for _ in range(cfg.max_steps):
        if solver.t >= target_time:
            break
        dt_s = solver.compute_dt(target_time)
        schedule_row, valve_row, flux_row = _sample_valve(
            solver,
            interface,
            requested_opening=cfg.constant_opening,
            valve_x_m=float(context["valve_x_m"]),
            dt_s=dt_s,
        )
        schedule_history.append(schedule_row)
        valve_history.append(valve_row)
        interface_flux_history.append(flux_row)
        record_solver_boundary_telemetry(solver, recorder, dt_s)
        solver.step(dt_s)
        dts.append(float(dt_s))

        if solver.step_count % cfg.sample_every == 0 or solver.t >= target_time:
            probe_history.extend(
                _sample_probes(
                    solver,
                    probes,
                    p0=float(reference["p0"]),
                    rho0=float(reference["rho0"]),
                    c0=float(reference["c0"]),
                    dt_s=dt_s,
                )
            )

    boundary_history = recorder.rows()
    final_profile = _final_profile(
        solver,
        p0=float(reference["p0"]),
    )
    final_primitive = solver.primitive()
    diagnostics = solver.diagnostics(dt=0.0)

    required_budget_fields = (
        "budget_mass_residual",
        "energy_budget_balance_residual_j",
        "phase_vapor_mass_balance_residual_kg",
    )
    missing_budget_fields = [
        key for key in required_budget_fields if key not in diagnostics
    ]

    histories_finite = all(
        np.isfinite(float(value))
        for history in (
            schedule_history,
            valve_history,
            interface_flux_history,
            probe_history,
            boundary_history,
            final_profile,
        )
        for row in history
        for value in row.values()
        if isinstance(value, (int, float, np.integer, np.floating))
        and not isinstance(value, (bool, np.bool_))
    )

    opening_tolerance = opening_roundoff_tolerance(cfg)
    max_opening_error = max(
        (
            abs(float(row["opening_error"]))
            for row in schedule_history
        ),
        default=0.0,
    )
    max_pressure_disturbance = max(
        (
            abs(float(row["delta_pressure_pa"]))
            for row in probe_history + final_profile
        ),
        default=0.0,
    )
    max_velocity = max(
        (
            abs(float(row["velocity_m_s"]))
            for row in probe_history + final_profile
        ),
        default=0.0,
    )
    max_mass_mismatch = max(
        (
            abs(float(row["mass_flux_mismatch_kg_m2_s"]))
            for row in interface_flux_history
        ),
        default=0.0,
    )
    max_energy_mismatch = max(
        (
            abs(float(row["energy_flux_mismatch_w_m2"]))
            for row in interface_flux_history
        ),
        default=0.0,
    )
    max_vapor_mismatch = max(
        (
            abs(float(row["vapor_mass_flux_mismatch_kg_m2_s"]))
            for row in interface_flux_history
        ),
        default=0.0,
    )
    max_momentum_residual = max(
        (
            abs(float(row["momentum_difference_residual_pa"]))
            for row in interface_flux_history
        ),
        default=0.0,
    )
    max_q_difference = max(
        (
            abs(float(row["flux_q_minus_applied_q_m3_s"]))
            for row in interface_flux_history
        ),
        default=0.0,
    )
    max_raw_q = max(
        (
            abs(float(row["raw_target_q_m3_s"]))
            for row in valve_history
        ),
        default=0.0,
    )
    max_applied_q = max(
        (
            abs(float(row["applied_q_m3_s"]))
            for row in valve_history
        ),
        default=0.0,
    )

    pressure_tolerance = _roundoff_tolerance(
        float(reference["p0"]),
        multiplier=256.0,
    )
    velocity_tolerance = _roundoff_tolerance(
        float(reference["c0"]),
        multiplier=256.0,
    )
    mass_flux_tolerance = _roundoff_tolerance(
        *[
            float(row["left_mass_flux_kg_m2_s"])
            for row in interface_flux_history
        ],
    )
    energy_flux_tolerance = _roundoff_tolerance(
        *[
            float(row["left_energy_flux_w_m2"])
            for row in interface_flux_history
        ],
    )
    vapor_flux_tolerance = _roundoff_tolerance(
        *[
            float(row["left_vapor_mass_flux_kg_m2_s"])
            for row in interface_flux_history
        ],
    )
    momentum_tolerance = _roundoff_tolerance(
        *[
            float(row["left_momentum_flux_pa"])
            for row in interface_flux_history
        ],
    )
    q_tolerance = _roundoff_tolerance(
        *[
            float(row["applied_q_m3_s"])
            for row in valve_history
        ],
    )

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
    budgets_within_roundoff = bool(
        all(
            np.isfinite(value)
            and abs(value) <= cfg.relative_budget_roundoff_tolerance
            for value in budget_values.values()
        )
    )

    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "verification_item": "V-012A",
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
        "initial_pressure_requested_pa": cfg.initial_pressure_pa,
        "initial_pressure_eos_pa": float(reference["p0"]),
        "initial_temperature_requested_K": cfg.initial_temperature_K,
        "initial_temperature_eos_K": float(reference["T0"]),
        "rho0": float(reference["rho0"]),
        "e0": float(reference["e0"]),
        "c0": float(reference["c0"]),
        "constant_opening": cfg.constant_opening,
        "kv_m3_per_h": float(context["kv_m3_per_h"]),
        "calibration_delta_p_pa": cfg.calibration_delta_p_pa,
        "calibration_q_m3_s": float(context["calibration_q_m3_s"]),
        "target_full_open_face_velocity_m_s": (
            cfg.target_full_open_face_velocity_m_s
        ),
        "valve_left_cell": int(interface.left_cell),
        "valve_right_cell": int(interface.right_cell),
        "valve_x_m": float(context["valve_x_m"]),
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
        **budget_values,
        "relative_budget_roundoff_tolerance": (
            cfg.relative_budget_roundoff_tolerance
        ),
        "budgets_within_roundoff": budgets_within_roundoff,
        "schedule_sample_count": len(schedule_history),
        "valve_history_row_count": len(valve_history),
        "interface_flux_history_row_count": len(
            interface_flux_history
        ),
        "probe_sample_count": len(probe_history),
        "boundary_history_row_count": len(boundary_history),
        "final_profile_row_count": len(final_profile),
        "max_abs_opening_error": float(max_opening_error),
        "opening_roundoff_tolerance": float(opening_tolerance),
        "max_abs_raw_target_q_m3_s": float(max_raw_q),
        "max_abs_applied_q_m3_s": float(max_applied_q),
        "mach_cap_activation_count": int(
            sum(bool(row["mach_cap_active"]) for row in valve_history)
        ),
        "hydraulic_separation_count": int(
            sum(
                bool(row["hydraulic_separation_active"])
                for row in valve_history
            )
        ),
        "max_abs_pressure_disturbance_pa": float(
            max_pressure_disturbance
        ),
        "pressure_roundoff_tolerance_pa": float(pressure_tolerance),
        "max_abs_velocity_m_s": float(max_velocity),
        "velocity_roundoff_tolerance_m_s": float(velocity_tolerance),
        "max_abs_mass_flux_mismatch_kg_m2_s": float(
            max_mass_mismatch
        ),
        "mass_flux_roundoff_tolerance_kg_m2_s": float(
            mass_flux_tolerance
        ),
        "max_abs_energy_flux_mismatch_w_m2": float(
            max_energy_mismatch
        ),
        "energy_flux_roundoff_tolerance_w_m2": float(
            energy_flux_tolerance
        ),
        "max_abs_vapor_mass_flux_mismatch_kg_m2_s": float(
            max_vapor_mismatch
        ),
        "vapor_flux_roundoff_tolerance_kg_m2_s": float(
            vapor_flux_tolerance
        ),
        "max_abs_momentum_difference_residual_pa": float(
            max_momentum_residual
        ),
        "momentum_roundoff_tolerance_pa": float(
            momentum_tolerance
        ),
        "max_abs_flux_q_minus_applied_q_m3_s": float(
            max_q_difference
        ),
        "q_roundoff_tolerance_m3_s": float(q_tolerance),
        "hydraulic_loss_proxy_is_diagnostic_only": True,
        "hydraulic_loss_removed_from_rhoE": False,
    }

    metrics["overall_observation_execution_pass"] = bool(
        all(
            [
                metrics["reached_target_time"],
                metrics["within_max_steps"],
                metrics["all_history_finite"],
                metrics["positive_pressure"],
                metrics["positive_temperature"],
                metrics["positive_density"],
                metrics["positive_sound_speed"],
                metrics["remained_single_phase"],
                not metrics["missing_budget_fields"],
                metrics["budgets_within_roundoff"],
                metrics["max_abs_opening_error"]
                <= metrics["opening_roundoff_tolerance"],
                metrics["max_abs_raw_target_q_m3_s"]
                <= metrics["q_roundoff_tolerance_m3_s"],
                metrics["max_abs_applied_q_m3_s"]
                <= metrics["q_roundoff_tolerance_m3_s"],
                metrics["mach_cap_activation_count"] == 0,
                metrics["hydraulic_separation_count"]
                == metrics["valve_history_row_count"],
                metrics["max_abs_pressure_disturbance_pa"]
                <= metrics["pressure_roundoff_tolerance_pa"],
                metrics["max_abs_velocity_m_s"]
                <= metrics["velocity_roundoff_tolerance_m_s"],
                metrics["max_abs_mass_flux_mismatch_kg_m2_s"]
                <= metrics["mass_flux_roundoff_tolerance_kg_m2_s"],
                metrics["max_abs_energy_flux_mismatch_w_m2"]
                <= metrics["energy_flux_roundoff_tolerance_w_m2"],
                metrics[
                    "max_abs_vapor_mass_flux_mismatch_kg_m2_s"
                ]
                <= metrics[
                    "vapor_flux_roundoff_tolerance_kg_m2_s"
                ],
                metrics[
                    "max_abs_momentum_difference_residual_pa"
                ]
                <= metrics["momentum_roundoff_tolerance_pa"],
                metrics["max_abs_flux_q_minus_applied_q_m3_s"]
                <= metrics["q_roundoff_tolerance_m3_s"],
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
        _write_csv(
            directory / f"{stem}_valve_schedule.csv",
            schedule_history,
        )
        _write_csv(
            directory / f"{stem}_valve_history.csv",
            valve_history,
        )
        _write_csv(
            directory / f"{stem}_interface_flux_history.csv",
            interface_flux_history,
        )
        _write_csv(
            directory / f"{stem}_probe_history.csv",
            probe_history,
        )
        write_boundary_history_csv(
            directory / f"{stem}_boundary_history.csv",
            boundary_history,
        )
        _write_csv(
            directory / f"{stem}_final_profile.csv",
            final_profile,
        )
        _write_observation_report(
            directory / f"{stem}_observation_report.md",
            metrics,
        )

    return metrics
