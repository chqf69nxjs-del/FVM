"""Human-review plots for V-012B driven internal-valve artifacts."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from .plot_internal_valve_results import (
    _plot_interface_flux_consistency,
    _plot_probe_pressure_velocity,
    _plot_ratio_bars,
    _plot_valve_command_and_flow,
    _pyplot,
    _read_csv,
    _read_json,
    _resolve_case_name,
    _save,
    _ratio,
)


PLOT_SUFFIXES = (
    "valve_command_and_flow",
    "probe_pressure_velocity",
    "interface_flux_consistency",
    "budget_and_health",
)


def _plot_driven_budget_and_health(
    *, directory: Path, stem: str, metrics: dict[str, Any]
) -> Path:
    budget_pairs = (
        ("mass", "budget_mass_relative_residual", "relative_budget_tolerance"),
        ("energy", "energy_budget_balance_relative_residual", "relative_budget_tolerance"),
        ("vapor mass", "phase_vapor_mass_balance_relative_residual", "relative_budget_tolerance"),
    )
    health_pairs = (
        ("opening", "max_abs_opening_error", "opening_roundoff_tolerance"),
        ("raw-applied", "initial_raw_applied_relative_difference", "flow_relative_tolerance"),
        ("applied-flux", "initial_applied_flux_relative_difference", "flow_relative_tolerance"),
        ("mass flux", "max_abs_mass_flux_mismatch_kg_m2_s", "mass_flux_roundoff_tolerance_kg_m2_s"),
        ("energy flux", "max_abs_energy_flux_mismatch_w_m2", "energy_flux_roundoff_tolerance_w_m2"),
        ("vapor flux", "max_abs_vapor_mass_flux_mismatch_kg_m2_s", "vapor_flux_roundoff_tolerance_kg_m2_s"),
        ("momentum", "max_abs_momentum_difference_residual_pa", "momentum_roundoff_tolerance_pa"),
        ("Q consistency", "max_abs_flux_q_minus_applied_q_m3_s", "q_roundoff_tolerance_m3_s"),
    )
    required = {
        key
        for _, value_key, tolerance_key in budget_pairs + health_pairs
        for key in (value_key, tolerance_key)
    }
    missing = sorted(required.difference(metrics))
    if missing:
        raise ValueError(
            "missing required V-012B plot metrics: " + ", ".join(missing)
        )
    budget_ratios = [
        _ratio(metrics[value_key], metrics[tolerance_key])
        for _, value_key, tolerance_key in budget_pairs
    ]
    health_ratios = [
        _ratio(metrics[value_key], metrics[tolerance_key])
        for _, value_key, tolerance_key in health_pairs
    ]
    plt = _pyplot()
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    _plot_ratio_bars(
        axes[0],
        [label for label, _, _ in budget_pairs],
        budget_ratios,
        "absolute residual / observation tolerance",
    )
    _plot_ratio_bars(
        axes[1],
        [label for label, _, _ in health_pairs],
        health_ratios,
        "consistency magnitude / numerical tolerance",
    )
    axes[1].tick_params(axis="x", rotation=25)
    status = bool(metrics.get("overall_observation_execution_pass", False))
    sign_fraction = float(metrics.get("flow_sign_consistency_fraction", 0.0))
    fig.suptitle(
        "V-012B budget and consistency summary "
        f"(software observation pass={status}, sign consistency={sign_fraction:.3f})\n"
        "Exact zeros are labelled explicitly and drawn at the visualization floor."
    )
    fig.tight_layout()
    output = directory / f"{stem}_budget_and_health.png"
    _save(fig, output)
    plt.close(fig)
    return output


def plot_internal_valve_driven_results(
    output_dir: Path | str,
    case_name: str | None = None,
) -> dict[str, Any]:
    directory = Path(output_dir)
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    stem = _resolve_case_name(directory, case_name)
    metrics = _read_json(directory / f"{stem}_metrics.json")
    if metrics.get("verification_item") != "V-012B":
        raise ValueError("driven plotter requires verification_item V-012B")
    valve_rows = _read_csv(directory / f"{stem}_valve_history.csv")
    flux_rows = _read_csv(directory / f"{stem}_interface_flux_history.csv")
    probe_rows = _read_csv(directory / f"{stem}_probe_history.csv")
    outputs = [
        _plot_valve_command_and_flow(
            directory=directory, stem=stem, valve_rows=valve_rows, flux_rows=flux_rows
        ),
        _plot_probe_pressure_velocity(
            directory=directory, stem=stem, probe_rows=probe_rows
        ),
        _plot_interface_flux_consistency(
            directory=directory, stem=stem, flux_rows=flux_rows
        ),
        _plot_driven_budget_and_health(directory=directory, stem=stem, metrics=metrics),
    ]
    return {
        "case_name": stem,
        "verification_item": "V-012B",
        "plot_count": len(outputs),
        "plot_files": [path.name for path in outputs],
        "matplotlib_version": importlib.metadata.version("matplotlib"),
        "solver_rerun": False,
        "numerical_results_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate V-012B review plots")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name", default=None)
    args = parser.parse_args(argv)
    print(json.dumps(plot_internal_valve_driven_results(args.output_dir, args.case_name), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
