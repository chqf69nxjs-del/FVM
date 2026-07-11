"""Case C CoolProp software-path mini-run.

This module is intentionally separate from the normal Case C builder.  It
constructs a short, event-free, single-phase, uniform-state run that verifies
that the CoolProp-backed property path can provide p-T initialized ``rho`` and
``e`` to the conservative FVM solver.  It is not a design evaluation,
acceptance gate, validation artifact, or HEM/HNE/DVCM assessment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np

from ..boundary import ConstantPressure, PressureTankBoundary
from ..config import NumericsConfig
from ..eos import LCO2PropertyEOSAdapter
from ..interfaces import InternalValveInterface
from ..phase_change import NoPhaseChange
from ..properties import CoolPropCO2Backend
from ..pump import ConstantPumpHead, PumpInletBoundary
from ..solver import FvmSolver
from ..source_terms import CellwisePipeSourceTerms
from ..state import make_conserved
from ..valve import ConstantOpening, KvLiquidValve
from .case_c import CaseCParameters, build_discretized_case_c_network


@dataclass(frozen=True)
class CaseCCoolPropMiniRunConfig:
    """Configuration for the Case C CoolProp software-path mini-run."""

    initial_pressure_pa: float = 8.0e6
    initial_temperature_K: float = 280.0
    n_cells: int = 20
    t_end_s: float = 1.0e-4
    cfl: float = 0.5
    max_steps: int = 10000
    sample_every: int = 1
    output_version: str = "case_c_coolprop_mini_run_v1"
    case_name: str = "case_c_coolprop_mini_run"

    def __post_init__(self) -> None:
        if self.initial_pressure_pa <= 0.0:
            raise ValueError("initial_pressure_pa must be positive")
        if self.initial_temperature_K <= 0.0:
            raise ValueError("initial_temperature_K must be positive")
        if self.n_cells <= 0:
            raise ValueError("n_cells must be positive")
        if self.t_end_s <= 0.0:
            raise ValueError("t_end_s must be positive")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.sample_every <= 0:
            raise ValueError("sample_every must be positive")


def build_case_c_coolprop_mini_run_parameters(
    config: CaseCCoolPropMiniRunConfig | None = None,
) -> CaseCParameters:
    """Return Case C parameters specialized for the zero-event mini-run."""

    cfg = config or CaseCCoolPropMiniRunConfig()
    return CaseCParameters(
        n_cells=cfg.n_cells,
        t_end_s=cfg.t_end_s,
        cfl=cfg.cfl,
        upstream_initial_pressure_pa=cfg.initial_pressure_pa,
        downstream_initial_pressure_pa=cfg.initial_pressure_pa,
        initial_velocity_m_s=0.0,
        lco2_boundary_temperature_K=cfg.initial_temperature_K,
        lco2_quality_source="transported",
        eos_model="coolprop_lco2",
        phase_change_model="none",
        enable_hem=False,
        pump_delta_p_nominal_pa=0.0,
        pump_trip_start_s=None,
        pump_trip_duration_s=0.0,
        pump_delta_p_final_pa=0.0,
        valve_close_start_s=10.0 * cfg.t_end_s + 1.0,
        valve_close_time_s=max(cfg.t_end_s, 1.0e-6),
        # Positive finite verification Kv only; this is not a design value.  With
        # zero initial pressure drop and zero velocity the valve flow remains zero.
        valve_kv_m3_h=100.0,
        darcy_friction_factor=0.0,
        onshore_elevation_start_m=0.0,
        onshore_elevation_end_m=0.0,
        jetty_elevation_start_m=0.0,
        jetty_elevation_end_m=0.0,
        loading_arm_elevation_start_m=0.0,
        loading_arm_elevation_end_m=0.0,
        latent_heat_placeholder_j_kg=0.0,
        downstream_tank_flow_direction="bidirectional",
        downstream_tank_velocity_policy="zero",
    )


def _require_finite_positive(name: str, values: np.ndarray) -> None:
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{name} must be finite")
    if np.any(values <= 0.0):
        raise ValueError(f"{name} must be positive")


def build_uniform_initial_state_from_pT(
    discretized,
    eos: LCO2PropertyEOSAdapter,
    backend: CoolPropCO2Backend,
    pressure_pa: float,
    temperature_K: float,
) -> np.ndarray:
    """Build uniform conservative state from explicit p-T property calls."""

    n_cells = discretized.grid.n_cells
    p0 = np.full(n_cells, float(pressure_pa), dtype=float)
    T0 = np.full(n_cells, float(temperature_K), dtype=float)
    rho0 = np.asarray(backend.density_from_pT(p0, T0), dtype=float)
    e0 = np.asarray(backend.internal_energy_from_pT(p0, T0), dtype=float)
    _require_finite_positive("rho0", rho0)
    if not np.all(np.isfinite(e0)):
        raise ValueError("e0 must be finite")
    U0 = make_conserved(rho=rho0, u=np.zeros(n_cells), e=e0, xv=np.zeros(n_cells))

    prim = eos.primitive_from_conserved(U0)
    for name, values in (("primitive pressure", prim.p), ("primitive temperature", prim.T), ("sound speed", prim.c)):
        _require_finite_positive(name, np.asarray(values, dtype=float))
    if not np.allclose(prim.xv, 0.0):
        raise ValueError("initial quality must be zero")
    if not np.allclose(prim.alpha, 0.0):
        raise ValueError("initial alpha must be zero")
    return U0


def build_case_c_coolprop_mini_run_solver(
    config: CaseCCoolPropMiniRunConfig | None = None,
) -> FvmSolver:
    """Build the Case C CoolProp mini-run solver without calibrated valve logic."""

    cfg = config or CaseCCoolPropMiniRunConfig()
    params = build_case_c_coolprop_mini_run_parameters(cfg)
    numerics = NumericsConfig(n_cells=params.n_cells, cfl=params.cfl)
    discretized = build_discretized_case_c_network(params)
    backend = CoolPropCO2Backend()
    eos = LCO2PropertyEOSAdapter(
        backend=backend,
        boundary_temperature_K=cfg.initial_temperature_K,
        quality_source="transported",
    )
    U0 = build_uniform_initial_state_from_pT(
        discretized, eos, backend, cfg.initial_pressure_pa, cfg.initial_temperature_K
    )
    valve_face = discretized.device_face("land_side_esd_valve")
    internal_valve = InternalValveInterface(
        left_cell=valve_face - 1,
        area_m2=discretized.geometry.area_m2,
        valve=KvLiquidValve(kv_m3_per_h=float(params.valve_kv_m3_h), allow_reverse_flow=False),
        opening_schedule=ConstantOpening(1.0),
    )
    source = CellwisePipeSourceTerms.from_discretized_network(
        discretized,
        local_loss_k=0.0,
        include_gravity_energy_source=False,
    )
    return FvmSolver(
        grid=discretized.grid,
        eos=eos,
        U=U0,
        cfl=numerics.cfl,
        n_ghost=numerics.n_ghost,
        left_boundary=PumpInletBoundary(
            suction_pressure_pa=params.upstream_initial_pressure_pa,
            head_schedule=ConstantPumpHead(delta_p_pa=0.0),
        ),
        right_boundary=PressureTankBoundary(
            pressure_schedule=ConstantPressure(params.downstream_initial_pressure_pa),
            flow_direction="bidirectional",
            velocity_policy="zero",
        ),
        source_term=source,
        phase_change=NoPhaseChange(),
        internal_interfaces=(internal_valve,),
        latent_heat_placeholder_j_kg=0.0,
    )


def _sample_with_temperature(solver: FvmSolver, dt: float) -> dict[str, float]:
    prim = solver.primitive()
    sample = solver.diagnostics(dt=dt)
    sample["T_min_K"] = float(np.min(prim.T))
    sample["T_max_K"] = float(np.max(prim.T))
    return sample


def _run_with_temperature_history(solver: FvmSolver, cfg: CaseCCoolPropMiniRunConfig) -> list[dict[str, float]]:
    history = [_sample_with_temperature(solver, 0.0)]
    for _ in range(cfg.max_steps):
        if solver.t >= cfg.t_end_s:
            break
        dt = solver.compute_dt(cfg.t_end_s)
        if not np.isfinite(dt) or dt <= 0.0:
            raise ValueError("computed dt must be finite and positive")
        solver.step(dt)
        if solver.step_count % cfg.sample_every == 0 or solver.t >= cfg.t_end_s:
            history.append(_sample_with_temperature(solver, dt))
    else:
        raise RuntimeError("max_steps reached before t_end")
    return history


def _safe_relative_change(delta: float, reference: float, eps: float = 1.0e-30) -> float:
    denom = max(abs(float(reference)), eps)
    return float(abs(delta) / denom)


def _range_metrics(prefix: str, initial: np.ndarray, final: np.ndarray) -> dict[str, float]:
    all_values = np.concatenate([np.ravel(initial), np.ravel(final)])
    max_abs = float(np.max(np.abs(final - initial)))
    denom = float(np.max(np.abs(initial)))
    return {
        f"initial_{prefix}": float(np.mean(initial)),
        f"final_{prefix}": float(np.mean(final)),
        f"min_{prefix}": float(np.min(all_values)),
        f"max_{prefix}": float(np.max(all_values)),
        f"max_abs_change_{prefix}": max_abs,
        f"max_relative_change_{prefix}": _safe_relative_change(max_abs, denom),
    }


def _coolprop_version() -> str:
    try:
        return importlib.metadata.version("CoolProp")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover - optional dependency mismatch
        return "unknown"


def _metrics(cfg: CaseCCoolPropMiniRunConfig, solver: FvmSolver, history: list[dict[str, float]], initial_prim, final_prim) -> dict[str, Any]:
    diag = solver.diagnostics(dt=0.0)
    budget_keys = sorted(k for k in diag if "budget" in k or "residual" in k or "inventory" in k)
    expected_budget = [
        "budget_mass_residual",
        "energy_budget_balance_residual_j",
        "phase_vapor_mass_balance_residual_kg",
    ]
    missing_budget = [k for k in expected_budget if k not in diag]
    hist_numbers = np.array([[float(v) for v in row.values()] for row in history], dtype=float)
    advanced_step_dt = [float(row["dt_s"]) for row in history if row["step"] > 0]
    positive_dt = [dt > 0.0 for dt in advanced_step_dt]
    min_positive_dt_s = min(advanced_step_dt) if advanced_step_dt else 0.0
    backend_status = getattr(solver.eos.backend, "design_status", "not_approved_for_design_use")
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "mini_run": True,
        "result_type": "simulation_result",
        "design_evaluation": False,
        "acceptance_gate": False,
        "validation": False,
        "software_path_verification": True,
        "output_version": cfg.output_version,
        "eos_model": "coolprop_lco2",
        "property_backend_name": getattr(solver.eos.backend, "name", "coolprop_co2"),
        "property_backend_design_status": backend_status,
        "quality_source": solver.eos.quality_source,
        "coolprop_available": True,
        "coolprop_version": _coolprop_version(),
        "saturation_temperature_margin_status": "not_applicable_above_critical_pressure",
        "target_time_s": cfg.t_end_s,
        "final_time_s": float(solver.t),
        "step_count": int(solver.step_count),
        "sample_count": len(history),
        "max_steps": cfg.max_steps,
        "sample_every": cfg.sample_every,
        "reached_target_time": bool(np.isclose(solver.t, cfg.t_end_s, rtol=1.0e-12, atol=1.0e-15)),
        "completed_without_exception": True,
        "initial_pressure_pa": cfg.initial_pressure_pa,
        "initial_temperature_K": cfg.initial_temperature_K,
        "initial_density_kg_m3": float(np.mean(initial_prim.rho)),
        "initial_internal_energy_j_kg": float(np.mean(initial_prim.e)),
        "initial_sound_speed_m_s": float(np.mean(initial_prim.c)),
        "initial_quality": float(np.max(initial_prim.xv)),
        "initial_alpha": float(np.max(initial_prim.alpha)),
        "initial_dt_s": float(history[0]["dt_s"]),
        "final_dt_s": float(history[-1]["dt_s"]),
        "min_dt_s": float(min(row["dt_s"] for row in history)),
        "min_positive_dt_s": float(min_positive_dt_s),
        "max_dt_s": float(max(row["dt_s"] for row in history)),
        "initial_cfl": float(history[0]["cfl_max"]),
        "final_cfl": float(history[-1]["cfl_max"]),
        "min_cfl": float(min(row["cfl_max"] for row in history)),
        "max_cfl": float(max(row["cfl_max"] for row in history)),
        "budget": {k: float(diag[k]) for k in budget_keys},
        "missing_budget_fields": missing_budget,
    }
    metrics.update(_range_metrics("pressure_pa", initial_prim.p, final_prim.p))
    metrics.update(_range_metrics("temperature_K", initial_prim.T, final_prim.T))
    metrics.update(_range_metrics("density_kg_m3", initial_prim.rho, final_prim.rho))
    metrics.update(_range_metrics("velocity_m_s", initial_prim.u, final_prim.u))
    metrics.update(_range_metrics("vapor_mass_fraction", initial_prim.xv, final_prim.xv))
    metrics.update(_range_metrics("alpha", initial_prim.alpha, final_prim.alpha))
    metrics.update(_range_metrics("sound_speed_m_s", initial_prim.c, final_prim.c))

    checks = {
        "all_history_finite": bool(np.all(np.isfinite(hist_numbers))),
        "positive_density": bool(metrics["min_density_kg_m3"] > 0.0),
        "positive_pressure": bool(metrics["min_pressure_pa"] > 0.0),
        "positive_temperature": bool(metrics["min_temperature_K"] > 0.0),
        "positive_sound_speed": bool(metrics["min_sound_speed_m_s"] > 0.0),
        "positive_dt_for_advanced_steps": bool(all(positive_dt)),
        "reached_target_time": bool(metrics["reached_target_time"]),
        "within_max_steps": bool(solver.step_count <= cfg.max_steps),
        "zero_or_finite_quality": bool(np.all(np.isfinite(final_prim.xv)) and np.all(final_prim.xv >= 0.0)),
        "zero_or_finite_alpha": bool(np.all(np.isfinite(final_prim.alpha)) and np.all(final_prim.alpha >= 0.0)),
        "backend_metadata_complete": bool(
            metrics["property_backend_name"] == "coolprop_co2"
            and metrics["property_backend_design_status"] == "not_approved_for_design_use"
            and metrics["coolprop_version"]
        ),
    }
    checks["overall_software_path_pass"] = bool(
        metrics["completed_without_exception"]
        and checks["reached_target_time"]
        and checks["all_history_finite"]
        and checks["positive_density"]
        and checks["positive_pressure"]
        and checks["positive_temperature"]
        and checks["positive_sound_speed"]
        and checks["within_max_steps"]
        and checks["backend_metadata_complete"]
    )
    metrics.update(checks)
    return metrics


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _final_profile(solver: FvmSolver) -> list[dict[str, float]]:
    prim = solver.primitive()
    return [
        {
            "cell_index": i,
            "x_m": float(solver.grid.cell_centers[i]),
            "p_pa": float(prim.p[i]),
            "T_K": float(prim.T[i]),
            "rho_kg_m3": float(prim.rho[i]),
            "u_m_s": float(prim.u[i]),
            "e_j_kg": float(prim.e[i]),
            "xv": float(prim.xv[i]),
            "alpha": float(prim.alpha[i]),
            "c_m_s": float(prim.c[i]),
        }
        for i in range(solver.grid.n_cells)
    ]


def _write_artifacts(output_dir: Path, cfg: CaseCCoolPropMiniRunConfig, metrics: dict[str, Any], history: list[dict[str, float]], profile: list[dict[str, float]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = cfg.case_name
    (output_dir / f"{stem}_config.json").write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{stem}_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(output_dir / f"{stem}_history.csv", history)
    _write_csv(output_dir / f"{stem}_final_profile.csv", profile)
    report = f"""# Case C CoolProp mini-run report

このレポートは software-path verification 用です。design-use ではありません。acceptance gate ではありません。Validation ではありません。

- CoolProp backend design status: not_approved_for_design_use
- 初期状態: 8 MPa, 280 K は dense single-phase / supercritical-liquid 側候補
- saturation temperature margin: not_applicable_above_critical_pressure
- case: {cfg.case_name}
- output_version: {cfg.output_version}
- final_time_s: {metrics['final_time_s']}
- step_count: {metrics['step_count']}
- overall_software_path_pass: {metrics['overall_software_path_pass']}

## 注意

この結果は実設計 Case C 評価、CoolProp backend の design-use 承認、acceptance gate 通過、Validation 完了、HEM/HNE/DVCM 評価を意味しません。
"""
    (output_dir / f"{stem}_report.md").write_text(report, encoding="utf-8")


def run_case_c_coolprop_mini_run(
    output_dir: Path | str | None = None,
    config: CaseCCoolPropMiniRunConfig | None = None,
) -> dict[str, Any]:
    """Run the Case C CoolProp software-path mini-run and return metrics."""

    cfg = config or CaseCCoolPropMiniRunConfig()
    solver = build_case_c_coolprop_mini_run_solver(cfg)
    initial_prim = solver.primitive()
    history = _run_with_temperature_history(solver, cfg)
    final_prim = solver.primitive()
    metrics = _metrics(cfg, solver, history, initial_prim, final_prim)
    profile = _final_profile(solver)
    if output_dir is not None:
        _write_artifacts(Path(output_dir), cfg, metrics, history, profile)
    return metrics


__all__ = [
    "CaseCCoolPropMiniRunConfig",
    "build_case_c_coolprop_mini_run_parameters",
    "build_uniform_initial_state_from_pT",
    "build_case_c_coolprop_mini_run_solver",
    "run_case_c_coolprop_mini_run",
]
