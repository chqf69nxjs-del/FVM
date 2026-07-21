"""Verification-only nonuniform pure-CO2 HEM quality-sync case.

This module exercises the merged equilibrium-quality projection in a deliberately
weak real-fluid two-phase problem.  The initial left and right states have a small
pressure offset and remain well inside the open liquid-vapor region.  The purpose
is to demonstrate that conservative transport creates a measurable quality
mismatch, the projection repairs it, and existing budgets remain closed.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from .config import PipeGeometry
from .grid import UniformGrid
from .hem_equilibrium_quality_sync import HEMEquilibriumQualityProjection
from .hem_uniform_state_preservation import VerificationHEMEquilibriumEOS
from .solver import FvmSolver
from .state import IDX_RHO_XV, inventory, make_conserved


class HEMNonuniformQualitySyncError(RuntimeError):
    """Raised when the fixed nonuniform HEM verification case is inconsistent."""


@dataclass(frozen=True)
class HEMNonuniformQualitySyncConfig:
    """Fixed settings for the weak pressure-offset open-two-phase case."""

    left_pressure_pa: float = 2.01e6
    left_quality: float = 0.45
    right_pressure_pa: float = 1.99e6
    right_quality: float = 0.55
    velocity_m_s: float = 0.0
    length_m: float = 10.0
    diameter_m: float = 0.10
    n_cells: int = 32
    cfl: float = 0.10
    n_steps: int = 4
    quality_sync_tolerance: float = 1.0e-10
    budget_relative_tolerance: float = 1.0e-11

    def __post_init__(self) -> None:
        numeric = (
            self.left_pressure_pa,
            self.left_quality,
            self.right_pressure_pa,
            self.right_quality,
            self.velocity_m_s,
            self.length_m,
            self.diameter_m,
            self.cfl,
            self.quality_sync_tolerance,
            self.budget_relative_tolerance,
        )
        if not all(np.isfinite(value) for value in numeric):
            raise ValueError("nonuniform-case settings must be finite")
        if self.left_pressure_pa <= 0.0 or self.right_pressure_pa <= 0.0:
            raise ValueError("pressures must be positive")
        if not 0.0 < self.left_quality < 1.0:
            raise ValueError("left_quality must lie in (0, 1)")
        if not 0.0 < self.right_quality < 1.0:
            raise ValueError("right_quality must lie in (0, 1)")
        if self.length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.n_cells < 4 or self.n_cells % 2 != 0:
            raise ValueError("n_cells must be an even integer of at least 4")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must lie in (0, 1]")
        if self.n_steps <= 0:
            raise ValueError("n_steps must be positive")
        if self.quality_sync_tolerance < 0.0:
            raise ValueError("quality_sync_tolerance must be non-negative")
        if self.budget_relative_tolerance < 0.0:
            raise ValueError("budget_relative_tolerance must be non-negative")


@dataclass(frozen=True)
class HEMNonuniformQualitySyncResult:
    """Numerical and diagnostic evidence from the fixed nonuniform run."""

    config: HEMNonuniformQualitySyncConfig
    summary: dict[str, object]
    history: list[dict[str, float]]
    x_m: np.ndarray
    initial_U: np.ndarray
    final_U: np.ndarray
    initial_profiles: dict[str, np.ndarray]
    final_profiles: dict[str, np.ndarray]
    final_projection: dict[str, np.ndarray]


def _coolprop_props_si():
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover - installed-only path
        raise ImportError("CoolProp is required for the nonuniform HEM case") from exc
    return PropsSI


def _profile_dict(primitive) -> dict[str, np.ndarray]:
    return {
        "rho_kg_m3": np.array(primitive.rho, dtype=float, copy=True),
        "velocity_m_s": np.array(primitive.u, dtype=float, copy=True),
        "pressure_pa": np.array(primitive.p, dtype=float, copy=True),
        "internal_energy_j_kg": np.array(primitive.e, dtype=float, copy=True),
        "temperature_K": np.array(primitive.T, dtype=float, copy=True),
        "quality": np.array(primitive.xv, dtype=float, copy=True),
        "void_fraction": np.array(primitive.alpha, dtype=float, copy=True),
        "sound_speed_m_s": np.array(primitive.c, dtype=float, copy=True),
    }


def _maximum_abs(values: Sequence[float]) -> float:
    return float(max((abs(float(value)) for value in values), default=0.0))


def run_nonuniform_hem_quality_sync(
    config: HEMNonuniformQualitySyncConfig | None = None,
) -> HEMNonuniformQualitySyncResult:
    """Run the fixed weak pressure-offset first-order HEM synchronization case."""

    cfg = config or HEMNonuniformQualitySyncConfig()
    props_si = _coolprop_props_si()

    specifications = (
        (cfg.left_pressure_pa, cfg.left_quality),
        (cfg.right_pressure_pa, cfg.right_quality),
    )
    states: list[tuple[float, float, float]] = []
    for pressure, quality in specifications:
        try:
            rho = float(props_si("Dmass", "P", pressure, "Q", quality, "CO2"))
            e = float(props_si("Umass", "P", pressure, "Q", quality, "CO2"))
            T = float(props_si("T", "P", pressure, "Q", quality, "CO2"))
        except Exception as exc:
            raise HEMNonuniformQualitySyncError(
                "CoolProp failed to construct an initial open-two-phase state"
            ) from exc
        if not all(np.isfinite(value) for value in (rho, e, T)) or rho <= 0.0:
            raise HEMNonuniformQualitySyncError(
                "CoolProp returned an invalid initial state"
            )
        states.append((rho, e, T))

    grid = UniformGrid(
        PipeGeometry(length_m=cfg.length_m, diameter_m=cfg.diameter_m),
        n_cells=cfg.n_cells,
    )
    x_m = grid.cell_centers
    left_mask = x_m < 0.5 * cfg.length_m

    rho = np.where(left_mask, states[0][0], states[1][0])
    e = np.where(left_mask, states[0][1], states[1][1])
    quality = np.where(left_mask, cfg.left_quality, cfg.right_quality)
    U_initial = make_conserved(rho, cfg.velocity_m_s, e, quality)

    eos = VerificationHEMEquilibriumEOS(
        quality_tolerance=cfg.quality_sync_tolerance
    )
    projection = HEMEquilibriumQualityProjection()
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U_initial,
        cfl=cfg.cfl,
        phase_change=projection,
    )

    initial_primitive = solver.primitive()
    initial_profiles = _profile_dict(initial_primitive)
    initial_inventory = inventory(
        U_initial,
        grid.dx,
        grid.geometry.area_m2,
    )

    history: list[dict[str, float]] = []
    projection_records = []
    all_projection_invariants = True
    all_open_two_phase = True
    maximum_quality_mismatch_after = 0.0

    for _ in range(cfg.n_steps):
        dt = solver.step()
        projection_result = projection.last_result
        if projection_result is None:
            raise HEMNonuniformQualitySyncError(
                "quality projection did not record a result"
            )
        projection_records.append(projection_result)

        projection_summary = projection_result.summary()
        all_projection_invariants = all_projection_invariants and all(
            bool(projection_summary[key])
            for key in (
                "mass_bitwise_unchanged",
                "momentum_bitwise_unchanged",
                "energy_bitwise_unchanged",
                "quality_synchronized_within_tolerance",
            )
        )
        all_open_two_phase = all_open_two_phase and bool(
            np.all(projection_result.phase_class == "liquid_vapor_two_phase")
        )
        maximum_quality_mismatch_after = max(
            maximum_quality_mismatch_after,
            float(
                np.max(
                    np.abs(
                        projection_result.q_after
                        - projection_result.q_equilibrium
                    )
                )
            ),
        )

        primitive = solver.primitive()
        current_inventory = inventory(
            solver.U,
            grid.dx,
            grid.geometry.area_m2,
        )
        if solver.boundary_budget is None:
            raise HEMNonuniformQualitySyncError("boundary budget is unavailable")
        if solver.phase_budget is None:
            raise HEMNonuniformQualitySyncError("phase budget is unavailable")
        if solver.energy_budget is None:
            raise HEMNonuniformQualitySyncError("energy budget is unavailable")

        boundary = solver.boundary_budget.diagnostics(current_inventory)
        phase = solver.phase_budget.diagnostics(
            current_inventory,
            boundary_budget=solver.boundary_budget,
        )
        energy = solver.energy_budget.diagnostics(
            current_inventory,
            boundary_budget=solver.boundary_budget,
        )
        cfl_max = float(
            np.max((np.abs(primitive.u) + primitive.c) * dt / grid.dx)
        )
        history.append(
            {
                "step": float(solver.step_count),
                "time_s": float(solver.t),
                "dt_s": float(dt),
                "cfl_max": cfl_max,
                "projection_cell_count": float(
                    projection_summary["projection_cell_count"]
                ),
                "evaporation_cell_count": float(
                    projection_summary["evaporation_cell_count"]
                ),
                "condensation_cell_count": float(
                    projection_summary["condensation_cell_count"]
                ),
                "max_abs_delta_q": float(
                    projection_summary["max_abs_delta_q"]
                ),
                "sum_delta_rho_q": float(
                    projection_summary["sum_delta_rho_q"]
                ),
                "pressure_min_pa": float(np.min(primitive.p)),
                "pressure_max_pa": float(np.max(primitive.p)),
                "velocity_min_m_s": float(np.min(primitive.u)),
                "velocity_max_m_s": float(np.max(primitive.u)),
                "rho_min_kg_m3": float(np.min(primitive.rho)),
                "rho_max_kg_m3": float(np.max(primitive.rho)),
                "quality_min": float(np.min(primitive.xv)),
                "quality_max": float(np.max(primitive.xv)),
                "alpha_min": float(np.min(primitive.alpha)),
                "alpha_max": float(np.max(primitive.alpha)),
                "sound_speed_min_m_s": float(np.min(primitive.c)),
                "sound_speed_max_m_s": float(np.max(primitive.c)),
                "budget_mass_relative_residual": float(
                    boundary["budget_mass_relative_residual"]
                ),
                "budget_momentum_relative_residual": float(
                    boundary["budget_momentum_relative_residual"]
                ),
                "energy_budget_balance_relative_residual": float(
                    energy["energy_budget_balance_relative_residual"]
                ),
                "phase_vapor_mass_balance_relative_residual": float(
                    phase["phase_vapor_mass_balance_relative_residual"]
                ),
                "phase_vapor_mass_source_cumulative_kg": float(
                    phase["phase_vapor_mass_source_cumulative_kg"]
                ),
                "phase_energy_delta_cumulative_j": float(
                    energy["energy_budget_phase_delta_cumulative_j"]
                ),
            }
        )

    final_primitive = solver.primitive()
    final_profiles = _profile_dict(final_primitive)
    final_projection_result = projection_records[-1]
    final_projection = {
        "q_before": np.array(final_projection_result.q_before, copy=True),
        "q_equilibrium": np.array(
            final_projection_result.q_equilibrium,
            copy=True,
        ),
        "q_after": np.array(final_projection_result.q_after, copy=True),
        "delta_q": np.array(final_projection_result.delta_q, copy=True),
        "delta_rho_q": np.array(
            final_projection_result.delta_rho_q,
            copy=True,
        ),
        "projection_applied": np.array(
            final_projection_result.projection_applied,
            dtype=bool,
            copy=True,
        ),
        "phase_class": np.array(
            final_projection_result.phase_class,
            copy=True,
        ),
    }

    projection_total_cell_updates = int(
        sum(int(record.summary()["projection_cell_count"]) for record in projection_records)
    )
    max_abs_delta_q = max(
        float(record.summary()["max_abs_delta_q"])
        for record in projection_records
    )
    cfl_max = max(row["cfl_max"] for row in history)
    mass_budget_max = _maximum_abs(
        row["budget_mass_relative_residual"] for row in history
    )
    momentum_budget_max = _maximum_abs(
        row["budget_momentum_relative_residual"] for row in history
    )
    energy_budget_max = _maximum_abs(
        row["energy_budget_balance_relative_residual"] for row in history
    )
    vapor_budget_max = _maximum_abs(
        row["phase_vapor_mass_balance_relative_residual"] for row in history
    )
    phase_energy_delta_max = _maximum_abs(
        row["phase_energy_delta_cumulative_j"] for row in history
    )

    summary: dict[str, object] = {
        "schema_version": "stage7_lco2_hem_nonuniform_quality_sync_v1",
        "scope": "verification_only",
        "completed_steps": int(solver.step_count),
        "final_time_s": float(solver.t),
        "cfl_max": float(cfl_max),
        "projection_total_cell_updates": projection_total_cell_updates,
        "projection_ever_applied": projection_total_cell_updates > 0,
        "max_abs_delta_q": float(max_abs_delta_q),
        "maximum_post_projection_quality_mismatch": float(
            maximum_quality_mismatch_after
        ),
        "all_projection_invariants_satisfied": bool(all_projection_invariants),
        "all_projection_states_open_two_phase": bool(all_open_two_phase),
        "all_sound_speeds_finite_positive": bool(
            np.all(np.isfinite(final_primitive.c))
            and np.all(final_primitive.c > 0.0)
        ),
        "mass_budget_max_relative_residual": float(mass_budget_max),
        "momentum_budget_max_relative_residual": float(momentum_budget_max),
        "energy_budget_max_relative_residual": float(energy_budget_max),
        "phase_vapor_budget_max_relative_residual": float(vapor_budget_max),
        "phase_energy_delta_max_abs_j": float(phase_energy_delta_max),
        "initial_mass_kg": float(initial_inventory["mass_total"]),
        "initial_momentum_kg_m_s": float(initial_inventory["momentum_total"]),
        "initial_energy_j": float(initial_inventory["energy_total"]),
        "initial_vapor_mass_kg": float(initial_inventory["vapor_mass_total"]),
        "final_mass_kg": float(
            inventory(solver.U, grid.dx, grid.geometry.area_m2)["mass_total"]
        ),
        "final_momentum_kg_m_s": float(
            inventory(solver.U, grid.dx, grid.geometry.area_m2)["momentum_total"]
        ),
        "final_energy_j": float(
            inventory(solver.U, grid.dx, grid.geometry.area_m2)["energy_total"]
        ),
        "final_vapor_mass_kg": float(
            inventory(solver.U, grid.dx, grid.geometry.area_m2)["vapor_mass_total"]
        ),
        "budget_tolerance_satisfied": bool(
            max(
                mass_budget_max,
                momentum_budget_max,
                energy_budget_max,
                vapor_budget_max,
            )
            <= cfg.budget_relative_tolerance
        ),
        "quality_sync_tolerance_satisfied": bool(
            maximum_quality_mismatch_after <= cfg.quality_sync_tolerance
        ),
        "fvm_solver_exercised": True,
        "rusanov_flux_exercised": True,
        "cfl_exercised": True,
        "equilibrium_quality_projection_exercised": True,
        "production_default_changed": False,
        "production_hem_activation_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "numeric_accuracy_band_approved": False,
    }

    required_true = (
        summary["projection_ever_applied"],
        summary["all_projection_invariants_satisfied"],
        summary["all_projection_states_open_two_phase"],
        summary["all_sound_speeds_finite_positive"],
        summary["budget_tolerance_satisfied"],
        summary["quality_sync_tolerance_satisfied"],
    )
    if not all(bool(value) for value in required_true):
        raise HEMNonuniformQualitySyncError(
            f"nonuniform HEM quality-sync acceptance failed: {summary}"
        )
    if phase_energy_delta_max != 0.0:
        raise HEMNonuniformQualitySyncError(
            "quality projection changed conservative total energy"
        )

    return HEMNonuniformQualitySyncResult(
        config=cfg,
        summary=summary,
        history=history,
        x_m=np.array(x_m, copy=True),
        initial_U=np.array(U_initial, copy=True),
        final_U=np.array(solver.U, copy=True),
        initial_profiles=initial_profiles,
        final_profiles=final_profiles,
        final_projection=final_projection,
    )


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def write_nonuniform_quality_sync_artifacts(
    output_dir: str | Path,
    result: HEMNonuniformQualitySyncResult,
) -> dict[str, Path]:
    """Write traceable JSON/CSV/Markdown/NPZ evidence."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_nonuniform_quality_sync"
    paths = {
        "json": out / f"{stem}.json",
        "history_csv": out / f"{stem}_history.csv",
        "profile_csv": out / f"{stem}_final_profile.csv",
        "markdown": out / f"{stem}.md",
        "npz": out / f"{stem}.npz",
    }

    payload = {
        **result.summary,
        "config": asdict(result.config),
        "history": result.history,
        "x_m": result.x_m,
        "initial_profiles": result.initial_profiles,
        "final_profiles": result.final_profiles,
        "final_projection": result.final_projection,
    }
    paths["json"].write_text(
        json.dumps(_jsonable(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    history_fields = list(result.history[0])
    with paths["history_csv"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=history_fields)
        writer.writeheader()
        writer.writerows(result.history)

    profile_fields = [
        "x_m",
        *result.final_profiles.keys(),
        "q_before_projection",
        "q_equilibrium",
        "q_after_projection",
        "delta_q",
        "delta_rho_q",
        "projection_applied",
        "phase_class",
    ]
    with paths["profile_csv"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=profile_fields)
        writer.writeheader()
        for index, x_value in enumerate(result.x_m):
            row = {"x_m": float(x_value)}
            for name, values in result.final_profiles.items():
                row[name] = float(values[index])
            row.update(
                {
                    "q_before_projection": float(
                        result.final_projection["q_before"][index]
                    ),
                    "q_equilibrium": float(
                        result.final_projection["q_equilibrium"][index]
                    ),
                    "q_after_projection": float(
                        result.final_projection["q_after"][index]
                    ),
                    "delta_q": float(result.final_projection["delta_q"][index]),
                    "delta_rho_q": float(
                        result.final_projection["delta_rho_q"][index]
                    ),
                    "projection_applied": bool(
                        result.final_projection["projection_applied"][index]
                    ),
                    "phase_class": str(
                        result.final_projection["phase_class"][index]
                    ),
                }
            )
            writer.writerow(row)

    markdown_lines = [
        "# Stage 7 LCO2 HEM Nonuniform Quality Synchronization",
        "",
        "`VERIFICATION ONLY; NOT PRODUCTION HEM ACTIVATION`",
        "",
        "## Fixed case",
        "",
        "```text",
        f"left pressure / quality:  {result.config.left_pressure_pa} Pa / {result.config.left_quality}",
        f"right pressure / quality: {result.config.right_pressure_pa} Pa / {result.config.right_quality}",
        f"cells / CFL / steps:       {result.config.n_cells} / {result.config.cfl} / {result.config.n_steps}",
        "```",
        "",
        "## Result",
        "",
        "```text",
    ]
    for key in (
        "projection_total_cell_updates",
        "projection_ever_applied",
        "max_abs_delta_q",
        "maximum_post_projection_quality_mismatch",
        "all_projection_states_open_two_phase",
        "mass_budget_max_relative_residual",
        "momentum_budget_max_relative_residual",
        "energy_budget_max_relative_residual",
        "phase_vapor_budget_max_relative_residual",
        "phase_energy_delta_max_abs_j",
    ):
        markdown_lines.append(f"{key}: {result.summary[key]}")
    markdown_lines.extend(
        [
            "```",
            "",
            "The run is software/numerical verification only. It does not establish",
            "physical Validation, design use, a production HEM activation decision, or",
            "a numeric accuracy band.",
            "",
        ]
    )
    paths["markdown"].write_text("\n".join(markdown_lines), encoding="utf-8")

    np.savez_compressed(
        paths["npz"],
        x_m=result.x_m,
        initial_U=result.initial_U,
        final_U=result.final_U,
        **{f"initial_{key}": value for key, value in result.initial_profiles.items()},
        **{f"final_{key}": value for key, value in result.final_profiles.items()},
        **{f"projection_{key}": value for key, value in result.final_projection.items()},
    )
    return paths


def write_nonuniform_quality_sync_plots(
    output_dir: str | Path,
    result: HEMNonuniformQualitySyncResult,
) -> dict[str, Path]:
    """Create human-review figures from an existing result without rerunning."""

    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - optional plotting dependency
        raise ImportError("matplotlib is required for quality-sync plots") from exc

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "quality_snapshot_png": out / "quality_sync_snapshot.png",
        "state_profiles_png": out / "hem_state_profiles.png",
        "history_png": out / "conservation_and_projection_history.png",
    }

    x = result.x_m
    projection = result.final_projection
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(x, projection["q_before"], label="q before projection", linestyle="--")
    axes[0].plot(x, projection["q_equilibrium"], label="q equilibrium")
    axes[0].plot(x, projection["q_after"], label="q after projection", marker=".")
    axes[0].set_ylabel("quality [-]")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(x, projection["delta_q"], marker=".")
    axes[1].axhline(0.0, linewidth=1.0)
    axes[1].set_xlabel("x [m]")
    axes[1].set_ylabel("delta q [-]")
    axes[1].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(paths["quality_snapshot_png"], dpi=160)
    plt.close(fig)

    profiles = result.final_profiles
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), sharex=True)
    items = (
        ("pressure_pa", "pressure [Pa]"),
        ("velocity_m_s", "velocity [m/s]"),
        ("rho_kg_m3", "density [kg/m3]"),
        ("void_fraction", "void fraction [-]"),
        ("sound_speed_m_s", "equilibrium sound speed [m/s]"),
        ("quality", "equilibrium quality [-]"),
    )
    for axis, (key, label) in zip(axes.ravel(), items):
        axis.plot(x, profiles[key])
        axis.set_ylabel(label)
        axis.grid(True, alpha=0.3)
    axes[-1, 0].set_xlabel("x [m]")
    axes[-1, 1].set_xlabel("x [m]")
    fig.tight_layout()
    fig.savefig(paths["state_profiles_png"], dpi=160)
    plt.close(fig)

    steps = np.asarray([row["step"] for row in result.history])
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(
        steps,
        [row["max_abs_delta_q"] for row in result.history],
        marker="o",
        label="max |delta q|",
    )
    axes[0].plot(
        steps,
        [row["projection_cell_count"] for row in result.history],
        marker="s",
        label="projected cells",
    )
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(
        steps,
        [row["budget_mass_relative_residual"] for row in result.history],
        label="mass",
    )
    axes[1].plot(
        steps,
        [row["budget_momentum_relative_residual"] for row in result.history],
        label="momentum",
    )
    axes[1].plot(
        steps,
        [row["energy_budget_balance_relative_residual"] for row in result.history],
        label="energy",
    )
    axes[1].set_ylabel("relative residual")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[2].plot(
        steps,
        [row["phase_vapor_mass_source_cumulative_kg"] for row in result.history],
        marker="o",
        label="cumulative vapor source",
    )
    axes[2].plot(
        steps,
        [row["phase_vapor_mass_balance_relative_residual"] for row in result.history],
        marker="s",
        label="vapor budget residual",
    )
    axes[2].set_xlabel("step")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(paths["history_png"], dpi=160)
    plt.close(fig)
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Stage 7 nonuniform HEM quality-sync verification case."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    result = run_nonuniform_hem_quality_sync()
    paths = write_nonuniform_quality_sync_artifacts(args.output_dir, result)
    paths.update(write_nonuniform_quality_sync_plots(args.output_dir, result))
    print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
