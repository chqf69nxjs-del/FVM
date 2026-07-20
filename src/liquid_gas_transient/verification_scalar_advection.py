"""Verification-only scalar linear-advection comparison harness.

This module isolates spatial reconstruction and time-integration effects from the
production FVM, EOS, boundaries, source terms, and phase-change paths. It
advects a periodic Gaussian pulse with a constant velocity and reports
conservation, diffusion, phase, extrema, and runtime metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal, Sequence

import numpy as np

from .reconstruction import (
    LIMITER_NAMES,
    RECONSTRUCTION_METHODS,
    LimiterName,
    ReconstructionMethod,
    reconstruct_interfaces,
)

TimeIntegrator = Literal["forward_euler", "ssprk2"]
TIME_INTEGRATORS: tuple[TimeIntegrator, ...] = ("forward_euler", "ssprk2")


@dataclass(frozen=True)
class ComparisonVariant:
    """One scalar-advection comparison path."""

    name: str
    reconstruction_method: ReconstructionMethod
    limiter: LimiterName
    time_integrator: TimeIntegrator


DEFAULT_COMPARISON_VARIANTS: tuple[ComparisonVariant, ...] = (
    ComparisonVariant("first_order_euler", "first_order", "minmod", "forward_euler"),
    ComparisonVariant("first_order_ssprk2", "first_order", "minmod", "ssprk2"),
    ComparisonVariant("muscl_minmod_ssprk2", "muscl", "minmod", "ssprk2"),
    ComparisonVariant("muscl_mc_ssprk2", "muscl", "mc", "ssprk2"),
    ComparisonVariant("muscl_van_leer_ssprk2", "muscl", "van_leer", "ssprk2"),
)


@dataclass(frozen=True)
class ScalarAdvectionConfig:
    """Configuration for one periodic Gaussian scalar-advection run."""

    n_cells: int = 200
    domain_length: float = 1.0
    velocity: float = 1.0
    cfl: float = 0.5
    t_end: float = 1.0
    gaussian_center: float = 0.25
    gaussian_sigma: float = 0.05
    gaussian_amplitude: float = 1.0
    background: float = 0.0
    reconstruction_method: ReconstructionMethod = "first_order"
    limiter: LimiterName = "minmod"
    time_integrator: TimeIntegrator = "forward_euler"
    n_ghost: int = 2

    def __post_init__(self) -> None:
        numeric_values = {
            "domain_length": self.domain_length,
            "velocity": self.velocity,
            "cfl": self.cfl,
            "t_end": self.t_end,
            "gaussian_center": self.gaussian_center,
            "gaussian_sigma": self.gaussian_sigma,
            "gaussian_amplitude": self.gaussian_amplitude,
            "background": self.background,
        }
        if not all(np.isfinite(value) for value in numeric_values.values()):
            raise ValueError("scalar-advection configuration values must be finite")
        if self.n_cells < 8:
            raise ValueError("n_cells must be at least 8")
        if self.domain_length <= 0.0:
            raise ValueError("domain_length must be positive")
        if self.velocity == 0.0:
            raise ValueError("velocity must be nonzero")
        if not 0.0 < self.cfl <= 1.0:
            raise ValueError("cfl must be in (0, 1]")
        if self.t_end <= 0.0:
            raise ValueError("t_end must be positive")
        if not 0.0 <= self.gaussian_center < self.domain_length:
            raise ValueError("gaussian_center must lie in [0, domain_length)")
        if not 0.0 < self.gaussian_sigma <= 0.25 * self.domain_length:
            raise ValueError("gaussian_sigma must lie in (0, 0.25 * domain_length]")
        if self.gaussian_amplitude <= 0.0:
            raise ValueError("gaussian_amplitude must be positive")
        if self.reconstruction_method not in RECONSTRUCTION_METHODS:
            raise ValueError(
                f"unknown reconstruction method {self.reconstruction_method!r}; "
                f"expected one of {RECONSTRUCTION_METHODS}"
            )
        if self.limiter not in LIMITER_NAMES:
            raise ValueError(
                f"unknown limiter {self.limiter!r}; expected one of {LIMITER_NAMES}"
            )
        if self.time_integrator not in TIME_INTEGRATORS:
            raise ValueError(
                f"unknown time integrator {self.time_integrator!r}; "
                f"expected one of {TIME_INTEGRATORS}"
            )
        if self.n_ghost < 2:
            raise ValueError("n_ghost must be at least 2 for periodic MUSCL reconstruction")

    @property
    def dx(self) -> float:
        return self.domain_length / self.n_cells


@dataclass(frozen=True)
class ScalarAdvectionMetrics:
    """Scalar metrics for one completed advection run."""

    pulse_mass_initial: float
    pulse_mass_final: float
    pulse_mass_relative_error: float
    peak_initial: float
    peak_final: float
    peak_retention: float
    width_initial: float
    width_final: float
    width_growth_ratio: float
    phase_error: float
    phase_error_cells: float
    l1_error: float
    l2_error: float
    linf_error: float
    total_variation_initial: float
    total_variation_final: float
    total_variation_ratio: float
    overshoot: float
    undershoot: float
    runtime_seconds: float
    n_steps: int
    dt_min: float
    dt_max: float
    cfl_actual_max: float


@dataclass(frozen=True)
class ScalarAdvectionResult:
    """Arrays and summary metrics for one scalar-advection run."""

    variant_name: str
    config: ScalarAdvectionConfig
    x: np.ndarray
    initial: np.ndarray
    final: np.ndarray
    exact: np.ndarray
    metrics: ScalarAdvectionMetrics

    def summary_record(self) -> dict[str, object]:
        record: dict[str, object] = {"variant_name": self.variant_name}
        record.update(asdict(self.config))
        record.update(asdict(self.metrics))
        return record


def periodic_signed_distance(
    value: np.ndarray | float,
    reference: float,
    domain_length: float,
) -> np.ndarray:
    """Return signed shortest periodic distance from ``reference`` to ``value``."""

    values = np.asarray(value, dtype=float)
    return (values - reference + 0.5 * domain_length) % domain_length - 0.5 * domain_length


def gaussian_profile(
    x: np.ndarray,
    *,
    center: float,
    sigma: float,
    amplitude: float,
    background: float,
    domain_length: float,
) -> np.ndarray:
    """Return a wrapped cell-centre Gaussian profile."""

    points = np.asarray(x, dtype=float)
    if not np.all(np.isfinite(points)):
        raise ValueError("x must contain only finite values")
    distance = periodic_signed_distance(points, center, domain_length)
    return background + amplitude * np.exp(-0.5 * (distance / sigma) ** 2)


def _periodic_extension(values: np.ndarray, n_ghost: int) -> np.ndarray:
    return np.concatenate((values[-n_ghost:], values, values[:n_ghost]))


def _advection_rhs(values: np.ndarray, config: ScalarAdvectionConfig) -> np.ndarray:
    if values.shape != (config.n_cells,):
        raise ValueError(f"values must have shape ({config.n_cells},)")
    if not np.all(np.isfinite(values)):
        raise ValueError("scalar state must contain only finite values")

    extended = _periodic_extension(values, config.n_ghost)
    left, right = reconstruct_interfaces(
        extended,
        method=config.reconstruction_method,
        limiter=config.limiter,
    )
    interface_flux = config.velocity * (left if config.velocity > 0.0 else right)

    i0 = config.n_ghost
    i1 = config.n_ghost + config.n_cells
    flux_left = interface_flux[i0 - 1 : i1 - 1]
    flux_right = interface_flux[i0:i1]
    return -(flux_right - flux_left) / config.dx


def _advance(values: np.ndarray, dt: float, config: ScalarAdvectionConfig) -> np.ndarray:
    if config.time_integrator == "forward_euler":
        updated = values + dt * _advection_rhs(values, config)
    elif config.time_integrator == "ssprk2":
        stage_one = values + dt * _advection_rhs(values, config)
        if not np.all(np.isfinite(stage_one)):
            raise ValueError("SSP-RK2 stage one produced a non-finite scalar state")
        updated = 0.5 * values + 0.5 * (
            stage_one + dt * _advection_rhs(stage_one, config)
        )
    else:  # pragma: no cover - validated in ScalarAdvectionConfig
        raise ValueError(f"unsupported time integrator {config.time_integrator!r}")

    if not np.all(np.isfinite(updated)):
        raise ValueError("time integration produced a non-finite scalar state")
    return updated


def _pulse_center_and_width(
    x: np.ndarray,
    values: np.ndarray,
    *,
    background: float,
    domain_length: float,
) -> tuple[float, float]:
    weights = np.maximum(values - background, 0.0)
    weight_sum = float(np.sum(weights))
    if weight_sum <= 0.0 or not np.isfinite(weight_sum):
        raise ValueError("pulse weights must have a positive finite sum")

    angle = 2.0 * np.pi * x / domain_length
    resultant = np.sum(weights * np.exp(1j * angle))
    if abs(resultant) <= np.finfo(float).eps:
        raise ValueError("pulse centre is undefined for a zero circular resultant")
    center = float(
        (np.angle(resultant) % (2.0 * np.pi))
        * domain_length
        / (2.0 * np.pi)
    )
    distance = periodic_signed_distance(x, center, domain_length)
    width = float(np.sqrt(np.sum(weights * distance**2) / weight_sum))
    return center, width


def _total_variation(values: np.ndarray) -> float:
    return float(np.sum(np.abs(np.roll(values, -1) - values)))


def _build_metrics(
    config: ScalarAdvectionConfig,
    x: np.ndarray,
    initial: np.ndarray,
    final: np.ndarray,
    exact: np.ndarray,
    *,
    runtime_seconds: float,
    n_steps: int,
    dt_min: float,
    dt_max: float,
) -> ScalarAdvectionMetrics:
    pulse_initial = initial - config.background
    pulse_final = final - config.background
    pulse_mass_initial = float(np.sum(pulse_initial) * config.dx)
    pulse_mass_final = float(np.sum(pulse_final) * config.dx)
    pulse_mass_relative_error = (
        pulse_mass_final - pulse_mass_initial
    ) / pulse_mass_initial

    peak_initial = float(np.max(pulse_initial))
    peak_final = float(np.max(pulse_final))
    _, width_initial = _pulse_center_and_width(
        x,
        initial,
        background=config.background,
        domain_length=config.domain_length,
    )
    center_final, width_final = _pulse_center_and_width(
        x,
        final,
        background=config.background,
        domain_length=config.domain_length,
    )
    expected_center = (
        config.gaussian_center + config.velocity * config.t_end
    ) % config.domain_length
    phase_error = float(
        periodic_signed_distance(center_final, expected_center, config.domain_length)
    )

    difference = final - exact
    tv_initial = _total_variation(initial)
    tv_final = _total_variation(final)

    return ScalarAdvectionMetrics(
        pulse_mass_initial=pulse_mass_initial,
        pulse_mass_final=pulse_mass_final,
        pulse_mass_relative_error=float(pulse_mass_relative_error),
        peak_initial=peak_initial,
        peak_final=peak_final,
        peak_retention=peak_final / peak_initial,
        width_initial=width_initial,
        width_final=width_final,
        width_growth_ratio=width_final / width_initial,
        phase_error=phase_error,
        phase_error_cells=phase_error / config.dx,
        l1_error=float(np.mean(np.abs(difference))),
        l2_error=float(np.sqrt(np.mean(difference**2))),
        linf_error=float(np.max(np.abs(difference))),
        total_variation_initial=tv_initial,
        total_variation_final=tv_final,
        total_variation_ratio=tv_final / tv_initial,
        overshoot=max(float(np.max(final) - np.max(initial)), 0.0),
        undershoot=max(float(np.min(initial) - np.min(final)), 0.0),
        runtime_seconds=float(runtime_seconds),
        n_steps=n_steps,
        dt_min=dt_min,
        dt_max=dt_max,
        cfl_actual_max=abs(config.velocity) * dt_max / config.dx,
    )


def run_scalar_advection(
    config: ScalarAdvectionConfig,
    *,
    variant_name: str = "custom",
) -> ScalarAdvectionResult:
    """Run one periodic scalar-advection case and return arrays plus metrics."""

    x = (np.arange(config.n_cells, dtype=float) + 0.5) * config.dx
    initial = gaussian_profile(
        x,
        center=config.gaussian_center,
        sigma=config.gaussian_sigma,
        amplitude=config.gaussian_amplitude,
        background=config.background,
        domain_length=config.domain_length,
    )
    values = initial.copy()
    nominal_dt = config.cfl * config.dx / abs(config.velocity)
    step_ratio = config.t_end / nominal_dt
    nearest_integer = round(step_ratio)
    if math.isclose(
        step_ratio,
        nearest_integer,
        rel_tol=0.0,
        abs_tol=1.0e-12 * max(1.0, abs(step_ratio)),
    ):
        n_steps = max(1, int(nearest_integer))
    else:
        n_steps = max(1, int(math.ceil(step_ratio)))
    dt = config.t_end / n_steps

    started = perf_counter()
    for _ in range(n_steps):
        values = _advance(values, dt, config)
    runtime_seconds = perf_counter() - started

    exact_center = (
        config.gaussian_center + config.velocity * config.t_end
    ) % config.domain_length
    exact = gaussian_profile(
        x,
        center=exact_center,
        sigma=config.gaussian_sigma,
        amplitude=config.gaussian_amplitude,
        background=config.background,
        domain_length=config.domain_length,
    )
    metrics = _build_metrics(
        config,
        x,
        initial,
        values,
        exact,
        runtime_seconds=runtime_seconds,
        n_steps=n_steps,
        dt_min=dt,
        dt_max=dt,
    )
    return ScalarAdvectionResult(
        variant_name=variant_name,
        config=config,
        x=x,
        initial=initial,
        final=values,
        exact=exact,
        metrics=metrics,
    )


def run_default_gaussian_comparison(
    *,
    mesh_cells: Sequence[int] = (100, 200, 400),
    domain_length: float = 1.0,
    velocity: float = 1.0,
    cfl: float = 0.5,
    t_end: float | None = None,
    gaussian_center: float = 0.25,
    gaussian_sigma: float = 0.05,
    gaussian_amplitude: float = 1.0,
    background: float = 0.0,
) -> list[ScalarAdvectionResult]:
    """Run the fixed first-order/time-control/MUSCL comparison matrix."""

    final_time = domain_length / abs(velocity) if t_end is None else t_end
    results: list[ScalarAdvectionResult] = []
    for n_cells in mesh_cells:
        for variant in DEFAULT_COMPARISON_VARIANTS:
            config = ScalarAdvectionConfig(
                n_cells=int(n_cells),
                domain_length=domain_length,
                velocity=velocity,
                cfl=cfl,
                t_end=final_time,
                gaussian_center=gaussian_center,
                gaussian_sigma=gaussian_sigma,
                gaussian_amplitude=gaussian_amplitude,
                background=background,
                reconstruction_method=variant.reconstruction_method,
                limiter=variant.limiter,
                time_integrator=variant.time_integrator,
            )
            results.append(run_scalar_advection(config, variant_name=variant.name))
    return results


def _comparison_payload(
    results: Sequence[ScalarAdvectionResult],
) -> dict[str, object]:
    return {
        "schema_version": "stage7_scalar_advection_comparison_v1",
        "scope": "verification_only",
        "production_solver_connected": False,
        "production_solver_behavior_changed": False,
        "production_time_integrator_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "numeric_accuracy_band_approved": False,
        "results": [result.summary_record() for result in results],
    }


def write_comparison_artifacts(
    output_dir: str | Path,
    results: Sequence[ScalarAdvectionResult],
) -> dict[str, Path]:
    """Write JSON, CSV, Markdown, and NPZ evidence for a comparison matrix."""

    if not results:
        raise ValueError("results must not be empty")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    json_path = destination / "stage7_scalar_advection_comparison.json"
    csv_path = destination / "stage7_scalar_advection_comparison.csv"
    markdown_path = destination / "stage7_scalar_advection_summary.md"
    npz_path = destination / "stage7_scalar_advection_profiles.npz"

    payload = _comparison_payload(results)
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    records = [result.summary_record() for result in results]
    fieldnames = list(records[0])
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    table_lines = [
        "# Stage 7 Scalar-Advection Comparison",
        "",
        "`VERIFICATION ONLY; NOT PRODUCTION ACTIVATION`",
        "",
        "| n | variant | peak retention | width growth | phase error [cells] | L2 error | TV ratio | runtime [s] |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        metrics = result.metrics
        table_lines.append(
            f"| {result.config.n_cells} | {result.variant_name} | "
            f"{metrics.peak_retention:.8f} | {metrics.width_growth_ratio:.8f} | "
            f"{metrics.phase_error_cells:.8f} | {metrics.l2_error:.8e} | "
            f"{metrics.total_variation_ratio:.8f} | "
            f"{metrics.runtime_seconds:.6f} |"
        )
    table_lines.extend(
        [
            "",
            "The SSP-RK2 rows are verification candidates only. They do not select the production",
            "time integrator, limiter, reconstruction variables, EOS fallback policy, or an",
            "accuracy-acceptance band.",
            "",
        ]
    )
    markdown_path.write_text("\n".join(table_lines), encoding="utf-8")

    arrays: dict[str, np.ndarray] = {}
    for result in results:
        prefix = f"n{result.config.n_cells}_{result.variant_name}"
        arrays[f"{prefix}_x"] = result.x
        arrays[f"{prefix}_initial"] = result.initial
        arrays[f"{prefix}_final"] = result.final
        arrays[f"{prefix}_exact"] = result.exact
    np.savez_compressed(npz_path, **arrays)

    return {
        "json": json_path,
        "csv": csv_path,
        "markdown": markdown_path,
        "npz": npz_path,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--meshes", nargs="+", type=int, default=[100, 200, 400])
    parser.add_argument("--velocity", type=float, default=1.0)
    parser.add_argument("--cfl", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    results = run_default_gaussian_comparison(
        mesh_cells=tuple(args.meshes),
        velocity=args.velocity,
        cfl=args.cfl,
    )
    paths = write_comparison_artifacts(args.output_dir, results)
    print(
        json.dumps(
            {
                "runs": len(results),
                "artifacts": {
                    name: str(path) for name, path in paths.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
