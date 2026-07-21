"""Verification-only uniform pure-CO2 HEM state preservation path.

This module connects the reviewed phase-classification and equilibrium sound-speed
scaffolds to the existing first-order ``FvmSolver`` for one deliberately narrow
case: an initially uniform, stationary, open liquid-vapor two-phase state with
transmissive boundaries, no source term, no phase-change operator, and no internal
interfaces.

The production solver, numerical flux, CFL implementation, EOS defaults, boundaries,
and phase-change models are not modified.  The adapter below is intentionally local
to this verification increment and is not an approved production HEM EOS.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from .config import PipeGeometry
from .grid import UniformGrid
from .hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedConfig,
    estimate_coolprop_equilibrium_sound_speed,
)
from .hem_phase_classification import evaluate_coolprop_hem_phase_state
from .solver import FvmSolver
from .state import (
    IDX_MOM,
    IDX_RHO,
    IDX_RHOE,
    IDX_RHO_XV,
    N_VARS,
    PrimitiveState,
    inventory,
    make_conserved,
)


class HEMUniformStatePreservationError(RuntimeError):
    """Raised when the narrow verification-only HEM path is inconsistent."""


@dataclass
class VerificationHEMEquilibriumEOS:
    """Verification-only EOS adapter for open liquid-vapor two-phase states.

    The fourth conserved component remains ``rho * q``.  For this first connection,
    transported quality must already match the equilibrium quality returned by
    CoolProp.  A mismatch is rejected rather than silently projected.
    """

    quality_tolerance: float = 1.0e-8
    sound_speed_config: HEMEquilibriumSoundSpeedConfig = field(
        default_factory=HEMEquilibriumSoundSpeedConfig
    )
    _cache: dict[tuple[float, float], tuple[float, float, float, float, float]] = field(
        init=False, default_factory=dict, repr=False
    )
    phase_evaluation_count: int = field(init=False, default=0)
    sound_speed_evaluation_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if not np.isfinite(self.quality_tolerance) or self.quality_tolerance < 0.0:
            raise ValueError("quality_tolerance must be finite and non-negative")

    @property
    def backend_name(self) -> str:
        return "coolprop_pure_co2_hem_uniform_verification"

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def _evaluate_scalar(self, rho: float, e: float) -> tuple[float, float, float, float, float]:
        key = (float(rho), float(e))
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        state = evaluate_coolprop_hem_phase_state(
            np.asarray([rho], dtype=float),
            np.asarray([e], dtype=float),
        )
        self.phase_evaluation_count += 1
        phase_class = str(state.phase_class[0])
        scope_status = str(state.scope_status[0])
        if scope_status != "supported_candidate":
            raise HEMUniformStatePreservationError(
                f"state is outside the supported HEM candidate scope: {scope_status}"
            )
        if phase_class != "liquid_vapor_two_phase":
            raise HEMUniformStatePreservationError(
                "uniform-state verification currently accepts only open liquid-vapor "
                f"two-phase states; received {phase_class}"
            )
        if not bool(state.quality_defined[0]) or not bool(state.alpha_defined[0]):
            raise HEMUniformStatePreservationError(
                "two-phase quality and void fraction must be explicitly defined"
            )

        acoustic = estimate_coolprop_equilibrium_sound_speed(
            rho,
            e,
            config=self.sound_speed_config,
        )
        self.sound_speed_evaluation_count += 1
        values = (
            float(state.p[0]),
            float(state.T[0]),
            float(state.quality[0]),
            float(state.alpha[0]),
            float(acoustic.sound_speed_m_s),
        )
        if not all(np.isfinite(value) for value in values):
            raise HEMUniformStatePreservationError(
                "HEM primitive state contains a non-finite value"
            )
        if values[0] <= 0.0 or values[1] <= 0.0 or values[4] <= 0.0:
            raise HEMUniformStatePreservationError(
                "pressure, temperature and equilibrium sound speed must be positive"
            )
        self._cache[key] = values
        return values

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        array = np.asarray(U, dtype=float)
        if array.shape[-1] != N_VARS:
            raise ValueError("U must have N_VARS entries in its last dimension")
        if not np.all(np.isfinite(array)):
            raise HEMUniformStatePreservationError("conserved state contains NaN or infinity")

        rho = np.asarray(array[..., IDX_RHO], dtype=float)
        if np.any(rho <= 0.0):
            raise HEMUniformStatePreservationError("density must be positive")
        u = np.asarray(array[..., IDX_MOM] / rho, dtype=float)
        E = np.asarray(array[..., IDX_RHOE] / rho, dtype=float)
        e = np.asarray(E - 0.5 * u**2, dtype=float)
        transported_quality = np.asarray(array[..., IDX_RHO_XV] / rho, dtype=float)
        if not np.all(np.isfinite(e)):
            raise HEMUniformStatePreservationError("internal energy must be finite")
        if np.any(transported_quality < -self.quality_tolerance) or np.any(
            transported_quality > 1.0 + self.quality_tolerance
        ):
            raise HEMUniformStatePreservationError(
                "transported quality lies outside [0, 1]"
            )

        p = np.empty_like(rho, dtype=float)
        T = np.empty_like(rho, dtype=float)
        quality = np.empty_like(rho, dtype=float)
        alpha = np.empty_like(rho, dtype=float)
        c = np.empty_like(rho, dtype=float)

        for index in np.ndindex(rho.shape):
            p_i, T_i, q_i, alpha_i, c_i = self._evaluate_scalar(
                float(rho[index]), float(e[index])
            )
            p[index] = p_i
            T[index] = T_i
            quality[index] = q_i
            alpha[index] = alpha_i
            c[index] = c_i

        mismatch = np.abs(transported_quality - quality)
        if np.any(mismatch > self.quality_tolerance):
            raise HEMUniformStatePreservationError(
                "transported quality does not match equilibrium CoolProp quality; "
                f"maximum mismatch={float(np.max(mismatch))}"
            )

        return PrimitiveState(
            rho=np.array(rho, copy=True),
            u=np.array(u, copy=True),
            p=p,
            e=np.array(e, copy=True),
            E=np.array(E, copy=True),
            T=T,
            xv=quality,
            alpha=alpha,
            c=c,
        )

    def density_from_pressure(self, p: np.ndarray | float) -> np.ndarray:
        raise NotImplementedError(
            "uniform HEM verification uses transmissive boundaries only"
        )


@dataclass(frozen=True)
class HEMUniformStatePreservationConfig:
    """Fixed-case settings for the first uniform-state FVM connection."""

    pressure_pa: float = 2.0e6
    quality: float = 0.50
    velocity_m_s: float = 0.0
    length_m: float = 10.0
    diameter_m: float = 0.10
    n_cells: int = 8
    cfl: float = 0.25
    n_steps: int = 8
    absolute_drift_tolerance: float = 1.0e-10
    relative_drift_tolerance: float = 1.0e-12

    def __post_init__(self) -> None:
        numeric = (
            self.pressure_pa,
            self.quality,
            self.velocity_m_s,
            self.length_m,
            self.diameter_m,
            self.cfl,
            self.absolute_drift_tolerance,
            self.relative_drift_tolerance,
        )
        if not all(np.isfinite(value) for value in numeric):
            raise ValueError("uniform-state configuration values must be finite")
        if self.pressure_pa <= 0.0:
            raise ValueError("pressure_pa must be positive")
        if not 0.0 < self.quality < 1.0:
            raise ValueError("quality must lie in the open interval (0, 1)")
        if self.length_m <= 0.0 or self.diameter_m <= 0.0:
            raise ValueError("pipe dimensions must be positive")
        if self.n_cells < 2:
            raise ValueError("n_cells must be at least 2")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must lie in (0, 1]")
        if self.n_steps <= 0:
            raise ValueError("n_steps must be positive")
        if self.absolute_drift_tolerance < 0.0:
            raise ValueError("absolute_drift_tolerance must be non-negative")
        if self.relative_drift_tolerance < 0.0:
            raise ValueError("relative_drift_tolerance must be non-negative")


@dataclass(frozen=True)
class HEMUniformStatePreservationResult:
    """Numerical evidence from one uniform-state FVM run."""

    config: HEMUniformStatePreservationConfig
    summary: dict[str, object]
    history: list[dict[str, float]]
    initial_U: np.ndarray
    final_U: np.ndarray


def _coolprop_props_si():
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover - installed-only path
        raise ImportError("CoolProp is required for uniform HEM verification") from exc
    return PropsSI


def _max_abs_drift(current: np.ndarray, reference: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(current) - np.asarray(reference))))


def _max_relative_drift(current: np.ndarray, reference: np.ndarray) -> float:
    current_arr = np.asarray(current, dtype=float)
    reference_arr = np.asarray(reference, dtype=float)
    scale = np.maximum(np.abs(reference_arr), 1.0)
    return float(np.max(np.abs(current_arr - reference_arr) / scale))


def run_uniform_hem_state_preservation(
    config: HEMUniformStatePreservationConfig | None = None,
) -> HEMUniformStatePreservationResult:
    """Run the fixed first-order uniform two-phase preservation test."""

    cfg = config or HEMUniformStatePreservationConfig()
    props_si = _coolprop_props_si()
    rho = float(props_si("Dmass", "P", cfg.pressure_pa, "Q", cfg.quality, "CO2"))
    e = float(props_si("Umass", "P", cfg.pressure_pa, "Q", cfg.quality, "CO2"))
    T = float(props_si("T", "P", cfg.pressure_pa, "Q", cfg.quality, "CO2"))
    if not all(np.isfinite(value) for value in (rho, e, T)) or rho <= 0.0:
        raise HEMUniformStatePreservationError("CoolProp returned an invalid initial state")

    U_cell = make_conserved(rho, cfg.velocity_m_s, e, cfg.quality)
    U_initial = np.repeat(U_cell[np.newaxis, :], cfg.n_cells, axis=0)
    grid = UniformGrid(
        PipeGeometry(length_m=cfg.length_m, diameter_m=cfg.diameter_m),
        n_cells=cfg.n_cells,
    )
    eos = VerificationHEMEquilibriumEOS()
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U_initial,
        cfl=cfg.cfl,
        enable_boundary_budget=False,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )

    initial_prim = solver.primitive()
    initial_inventory = inventory(U_initial, grid.dx, grid.geometry.area_m2)
    history: list[dict[str, float]] = []

    def record(step_dt: float) -> None:
        prim = solver.primitive()
        inv = inventory(solver.U, grid.dx, grid.geometry.area_m2)
        history.append(
            {
                "step": float(solver.step_count),
                "time_s": float(solver.t),
                "dt_s": float(step_dt),
                "cfl_max": float(
                    np.max((np.abs(prim.u) + prim.c) * step_dt / grid.dx)
                )
                if step_dt > 0.0
                else 0.0,
                "rho_max_abs_drift": _max_abs_drift(prim.rho, initial_prim.rho),
                "u_max_abs_drift": _max_abs_drift(prim.u, initial_prim.u),
                "p_max_abs_drift_pa": _max_abs_drift(prim.p, initial_prim.p),
                "T_max_abs_drift_K": _max_abs_drift(prim.T, initial_prim.T),
                "quality_max_abs_drift": _max_abs_drift(prim.xv, initial_prim.xv),
                "alpha_max_abs_drift": _max_abs_drift(prim.alpha, initial_prim.alpha),
                "sound_speed_max_abs_drift_m_s": _max_abs_drift(prim.c, initial_prim.c),
                "mass_inventory_drift": float(inv["mass_total"] - initial_inventory["mass_total"]),
                "momentum_inventory_drift": float(
                    inv["momentum_total"] - initial_inventory["momentum_total"]
                ),
                "energy_inventory_drift": float(
                    inv["energy_total"] - initial_inventory["energy_total"]
                ),
                "vapor_mass_inventory_drift": float(
                    inv["vapor_mass_total"] - initial_inventory["vapor_mass_total"]
                ),
            }
        )

    record(0.0)
    for _ in range(cfg.n_steps):
        dt = solver.compute_dt()
        solver.step(dt)
        record(dt)

    final_prim = solver.primitive()
    final_inventory = inventory(solver.U, grid.dx, grid.geometry.area_m2)
    U_abs_drift = _max_abs_drift(solver.U, U_initial)
    U_rel_drift = _max_relative_drift(solver.U, U_initial)
    primitive_abs_drifts = {
        "rho": _max_abs_drift(final_prim.rho, initial_prim.rho),
        "u": _max_abs_drift(final_prim.u, initial_prim.u),
        "p": _max_abs_drift(final_prim.p, initial_prim.p),
        "T": _max_abs_drift(final_prim.T, initial_prim.T),
        "quality": _max_abs_drift(final_prim.xv, initial_prim.xv),
        "alpha": _max_abs_drift(final_prim.alpha, initial_prim.alpha),
        "sound_speed": _max_abs_drift(final_prim.c, initial_prim.c),
    }
    inventory_drifts = {
        key: float(final_inventory[key] - initial_inventory[key])
        for key in initial_inventory
    }
    preserved = (
        U_abs_drift <= cfg.absolute_drift_tolerance
        or U_rel_drift <= cfg.relative_drift_tolerance
    ) and all(
        abs(value) <= cfg.absolute_drift_tolerance for value in primitive_abs_drifts.values()
    )
    if not preserved:
        raise HEMUniformStatePreservationError(
            "uniform HEM state drift exceeded the configured verification tolerances"
        )

    summary: dict[str, object] = {
        "scope": "verification_only",
        "case_id": "uniform_p2mpa_q050_u0",
        "fvm_solver_exercised": True,
        "rusanov_flux_exercised": True,
        "cfl_exercised": True,
        "transmissive_boundaries": True,
        "source_term_enabled": False,
        "phase_change_operator_enabled": False,
        "internal_interfaces_enabled": False,
        "verification_only_hem_eos_adapter": True,
        "production_default_changed": False,
        "production_hem_activation_approved": False,
        "equilibrium_sound_speed_used_in_verification_flux_and_cfl": True,
        "physical_validation": False,
        "design_use_acceptance": False,
        "numeric_accuracy_band_approved": False,
        "uniform_state_preserved": True,
        "pressure_pa": cfg.pressure_pa,
        "temperature_K": T,
        "quality": cfg.quality,
        "rho_kg_m3": rho,
        "e_j_kg": e,
        "alpha": float(initial_prim.alpha[0]),
        "equilibrium_sound_speed_m_s": float(initial_prim.c[0]),
        "n_cells": cfg.n_cells,
        "n_steps": cfg.n_steps,
        "final_time_s": float(solver.t),
        "dt_min_s": float(min(row["dt_s"] for row in history[1:])),
        "dt_max_s": float(max(row["dt_s"] for row in history[1:])),
        "cfl_max": float(max(row["cfl_max"] for row in history)),
        "conserved_max_abs_drift": U_abs_drift,
        "conserved_max_relative_drift": U_rel_drift,
        "primitive_max_abs_drifts": primitive_abs_drifts,
        "inventory_drifts": inventory_drifts,
        "eos_cache_size": eos.cache_size,
        "phase_evaluation_count": eos.phase_evaluation_count,
        "sound_speed_evaluation_count": eos.sound_speed_evaluation_count,
    }
    return HEMUniformStatePreservationResult(
        config=cfg,
        summary=summary,
        history=history,
        initial_U=np.array(U_initial, copy=True),
        final_U=np.array(solver.U, copy=True),
    )


def write_uniform_state_artifacts(
    output_dir: str | Path,
    result: HEMUniformStatePreservationResult,
) -> dict[str, Path]:
    """Write JSON, CSV, Markdown and NPZ evidence."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_uniform_state_preservation"
    json_path = destination / f"{stem}.json"
    csv_path = destination / f"{stem}.csv"
    markdown_path = destination / f"{stem}.md"
    npz_path = destination / f"{stem}.npz"

    payload = {
        "schema_version": "stage7_lco2_hem_uniform_state_preservation_v1",
        **result.summary,
        "history": result.history,
    }
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result.history[0]))
        writer.writeheader()
        writer.writerows(result.history)

    lines = [
        "# Stage 7 Pure-CO2 HEM Uniform-State Preservation",
        "",
        "`VERIFICATION ONLY; NOT PRODUCTION HEM ACTIVATION`",
        "",
        f"- case: `{result.summary['case_id']}`",
        f"- pressure: `{result.summary['pressure_pa']}` Pa",
        f"- quality: `{result.summary['quality']}`",
        f"- equilibrium sound speed: `{result.summary['equilibrium_sound_speed_m_s']}` m/s",
        f"- cells / steps: `{result.summary['n_cells']}` / `{result.summary['n_steps']}`",
        f"- final time: `{result.summary['final_time_s']}` s",
        f"- maximum conserved absolute drift: `{result.summary['conserved_max_abs_drift']}`",
        f"- maximum conserved relative drift: `{result.summary['conserved_max_relative_drift']}`",
        f"- uniform state preserved: `{result.summary['uniform_state_preserved']}`",
        "- production default changed: `False`",
        "- physical Validation: `False`",
        "- design-use acceptance: `False`",
        "",
        "| step | time [s] | dt [s] | CFL | max p drift [Pa] | max q drift | max alpha drift |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result.history:
        lines.append(
            "| {step:.0f} | {time_s:.8g} | {dt_s:.8g} | {cfl_max:.8g} | "
            "{p_max_abs_drift_pa:.8g} | {quality_max_abs_drift:.8g} | "
            "{alpha_max_abs_drift:.8g} |".format(**row)
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    np.savez_compressed(
        npz_path,
        initial_U=result.initial_U,
        final_U=result.final_U,
        step=np.asarray([row["step"] for row in result.history]),
        time_s=np.asarray([row["time_s"] for row in result.history]),
        p_max_abs_drift_pa=np.asarray(
            [row["p_max_abs_drift_pa"] for row in result.history]
        ),
        quality_max_abs_drift=np.asarray(
            [row["quality_max_abs_drift"] for row in result.history]
        ),
        alpha_max_abs_drift=np.asarray(
            [row["alpha_max_abs_drift"] for row in result.history]
        ),
    )
    return {
        "json": json_path,
        "csv": csv_path,
        "markdown": markdown_path,
        "npz": npz_path,
    }


def run_uniform_state_verification(
    output_dir: str | Path,
    *,
    config: HEMUniformStatePreservationConfig | None = None,
) -> dict[str, Path]:
    result = run_uniform_hem_state_preservation(config)
    return write_uniform_state_artifacts(output_dir, result)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Stage 7 uniform pure-CO2 HEM preservation test."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cells", type=int, default=8)
    parser.add_argument("--steps", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    config = HEMUniformStatePreservationConfig(
        n_cells=args.cells,
        n_steps=args.steps,
    )
    paths = run_uniform_state_verification(args.output_dir, config=config)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
