"""Human-review plots for Stage 6 V-012 internal-valve artifacts.

The plotter reads saved CSV/JSON artifacts and never modifies solver state or
numerical results. V-012A emits four baseline figures. Dynamic V-012 cases may
extend the same module with characteristic, x-t, profile-snapshot, and dp-Q
plots after their time-resolved artifacts exist.

This remains software / numerical verification only. It is not physical
Validation or design-use acceptance.
"""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import importlib.util
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np


PLOT_SUFFIXES = (
    "valve_command_and_flow",
    "probe_pressure_velocity",
    "interface_flux_consistency",
    "budget_and_health",
)


def matplotlib_available() -> bool:
    """Return whether the optional plotting dependency can be imported."""

    return importlib.util.find_spec("matplotlib") is not None


def _pyplot():
    if not matplotlib_available():
        raise RuntimeError(
            "matplotlib is required for V-012 plots; install the plotting extra"
        )
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    return plt


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"empty CSV artifact: {path.name}")
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return payload


def _require_columns(
    rows: list[dict[str, str]],
    path: Path,
    columns: Iterable[str],
) -> None:
    available = set(rows[0])
    missing = [column for column in columns if column not in available]
    if missing:
        raise ValueError(
            f"missing required columns in {path.name}: {', '.join(missing)}"
        )


def _float_values(rows: list[dict[str, str]], key: str) -> np.ndarray:
    try:
        values = np.asarray([float(row[key]) for row in rows], dtype=float)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric column: {key}") from exc
    if not np.all(np.isfinite(values)):
        raise ValueError(f"non-finite values in column: {key}")
    return values


def _bool_value(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no", ""}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _resolve_case_name(directory: Path, case_name: str | None) -> str:
    if case_name:
        return case_name
    metric_paths = sorted(directory.glob("*_metrics.json"))
    if len(metric_paths) != 1:
        raise ValueError(
            "case_name is required unless the directory contains exactly one "
            "*_metrics.json file"
        )
    suffix = "_metrics.json"
    return metric_paths[0].name[: -len(suffix)]


def _save(fig: Any, path: Path) -> None:
    fig.savefig(path, dpi=160, bbox_inches="tight")
    fig.clf()


def _plot_valve_command_and_flow(
    *,
    directory: Path,
    stem: str,
    valve_rows: list[dict[str, str]],
    flux_rows: list[dict[str, str]],
) -> Path:
    valve_path = directory / f"{stem}_valve_history.csv"
    flux_path = directory / f"{stem}_interface_flux_history.csv"
    _require_columns(
        valve_rows,
        valve_path,
        (
            "time_s",
            "opening_requested",
            "opening_actual",
            "delta_p_pa",
            "raw_target_q_m3_s",
            "applied_q_m3_s",
            "q_limit_m3_s",
            "mach_cap_active",
        ),
    )
    _require_columns(
        flux_rows,
        flux_path,
        ("time_s", "flux_derived_q_m3_s"),
    )

    plt = _pyplot()
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    t = _float_values(valve_rows, "time_s")
    t_flux = _float_values(flux_rows, "time_s")

    axes[0].plot(t, _float_values(valve_rows, "opening_requested"), label="requested")
    axes[0].plot(t, _float_values(valve_rows, "opening_actual"), label="actual", linestyle="--")
    axes[0].set_ylabel("opening [-]")
    axes[0].legend()
    axes[0].grid(True)

    axes[1].plot(t, _float_values(valve_rows, "delta_p_pa"))
    axes[1].axhline(0.0, linewidth=0.8)
    axes[1].set_ylabel("valve dp [Pa]")
    axes[1].grid(True)

    axes[2].plot(t, _float_values(valve_rows, "raw_target_q_m3_s"), label="raw Kv Q")
    axes[2].plot(t, _float_values(valve_rows, "applied_q_m3_s"), label="applied Q", linestyle="--")
    axes[2].plot(t_flux, _float_values(flux_rows, "flux_derived_q_m3_s"), label="flux-derived Q", linestyle=":")
    axes[2].plot(t, _float_values(valve_rows, "q_limit_m3_s"), label="positive Q limit", alpha=0.7)
    cap_times = [
        float(row["time_s"])
        for row in valve_rows
        if _bool_value(row["mach_cap_active"])
    ]
    for cap_time in cap_times:
        axes[2].axvline(cap_time, linewidth=0.7, alpha=0.35)
    axes[2].set_ylabel("Q [m3/s]")
    axes[2].set_xlabel("time [s]")
    axes[2].legend()
    axes[2].grid(True)

    fig.suptitle("V-012 internal valve: command and flow response")
    fig.tight_layout()
    output = directory / f"{stem}_valve_command_and_flow.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_probe_pressure_velocity(
    *,
    directory: Path,
    stem: str,
    probe_rows: list[dict[str, str]],
) -> Path:
    probe_path = directory / f"{stem}_probe_history.csv"
    _require_columns(
        probe_rows,
        probe_path,
        ("time_s", "probe_name", "delta_pressure_pa", "velocity_m_s"),
    )

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in probe_rows:
        grouped.setdefault(row["probe_name"], []).append(row)

    plt = _pyplot()
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    for probe_name in sorted(grouped):
        rows = grouped[probe_name]
        axes[0].plot(
            _float_values(rows, "time_s"),
            _float_values(rows, "delta_pressure_pa"),
            label=probe_name,
        )
        axes[1].plot(
            _float_values(rows, "time_s"),
            _float_values(rows, "velocity_m_s"),
            label=probe_name,
        )

    axes[0].axhline(0.0, linewidth=0.8)
    axes[0].set_ylabel("pressure perturbation [Pa]")
    axes[0].legend(ncol=2)
    axes[0].grid(True)
    axes[1].axhline(0.0, linewidth=0.8)
    axes[1].set_ylabel("velocity [m/s]")
    axes[1].set_xlabel("time [s]")
    axes[1].legend(ncol=2)
    axes[1].grid(True)

    fig.suptitle("V-012 internal valve: probe pressure and velocity")
    fig.tight_layout()
    output = directory / f"{stem}_probe_pressure_velocity.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_interface_flux_consistency(
    *,
    directory: Path,
    stem: str,
    flux_rows: list[dict[str, str]],
) -> Path:
    flux_path = directory / f"{stem}_interface_flux_history.csv"
    columns = (
        "time_s",
        "mass_flux_mismatch_kg_m2_s",
        "energy_flux_mismatch_w_m2",
        "vapor_mass_flux_mismatch_kg_m2_s",
        "momentum_flux_difference_pa",
        "expected_momentum_flux_difference_pa",
        "momentum_difference_residual_pa",
        "flux_q_minus_applied_q_m3_s",
    )
    _require_columns(flux_rows, flux_path, columns)

    plt = _pyplot()
    fig, axes = plt.subplots(5, 1, figsize=(10, 12), sharex=True)
    t = _float_values(flux_rows, "time_s")

    axes[0].plot(t, _float_values(flux_rows, "mass_flux_mismatch_kg_m2_s"))
    axes[0].set_ylabel("mass mismatch\n[kg/m2/s]")
    axes[1].plot(t, _float_values(flux_rows, "energy_flux_mismatch_w_m2"))
    axes[1].set_ylabel("energy mismatch\n[W/m2]")
    axes[2].plot(t, _float_values(flux_rows, "vapor_mass_flux_mismatch_kg_m2_s"))
    axes[2].set_ylabel("vapor mismatch\n[kg/m2/s]")
    axes[3].plot(t, _float_values(flux_rows, "momentum_flux_difference_pa"), label="flux difference")
    axes[3].plot(t, _float_values(flux_rows, "expected_momentum_flux_difference_pa"), label="p_left - p_right", linestyle="--")
    axes[3].plot(t, _float_values(flux_rows, "momentum_difference_residual_pa"), label="residual", linestyle=":")
    axes[3].set_ylabel("momentum / dp [Pa]")
    axes[3].legend()
    axes[4].plot(t, _float_values(flux_rows, "flux_q_minus_applied_q_m3_s"))
    axes[4].set_ylabel("flux Q - applied Q\n[m3/s]")
    axes[4].set_xlabel("time [s]")

    for axis in axes:
        axis.axhline(0.0, linewidth=0.8)
        axis.grid(True)

    fig.suptitle("V-012 internal valve: interface-flux consistency")
    fig.tight_layout()
    output = directory / f"{stem}_interface_flux_consistency.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _safe_ratio(value: Any, tolerance: Any) -> float:
    numerator = abs(float(value))
    denominator = abs(float(tolerance))
    if not np.isfinite(numerator) or not np.isfinite(denominator):
        raise ValueError("non-finite metric or tolerance")
    if denominator <= 0.0:
        raise ValueError("plot tolerance must be positive")
    return max(numerator / denominator, 1.0e-30)


def _plot_budget_and_health(
    *,
    directory: Path,
    stem: str,
    metrics: dict[str, Any],
) -> Path:
    budget_pairs = (
        ("mass", "budget_mass_relative_residual", "relative_budget_roundoff_tolerance"),
        ("energy", "energy_budget_balance_relative_residual", "relative_budget_roundoff_tolerance"),
        ("vapor mass", "phase_vapor_mass_balance_relative_residual", "relative_budget_roundoff_tolerance"),
    )
    health_pairs = (
        ("pressure", "max_abs_pressure_disturbance_pa", "pressure_roundoff_tolerance_pa"),
        ("velocity", "max_abs_velocity_m_s", "velocity_roundoff_tolerance_m_s"),
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
            "missing required metrics for budget/health plot: " + ", ".join(missing)
        )

    budget_values = [
        _safe_ratio(metrics[value_key], metrics[tolerance_key])
        for _, value_key, tolerance_key in budget_pairs
    ]
    health_values = [
        _safe_ratio(metrics[value_key], metrics[tolerance_key])
        for _, value_key, tolerance_key in health_pairs
    ]

    plt = _pyplot()
    fig, axes = plt.subplots(2, 1, figsize=(11, 8))
    axes[0].bar([label for label, _, _ in budget_pairs], budget_values)
    axes[0].axhline(1.0, linewidth=1.0, linestyle="--", label="documented tolerance")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("absolute residual / tolerance")
    axes[0].legend()
    axes[0].grid(True, axis="y")

    axes[1].bar([label for label, _, _ in health_pairs], health_values)
    axes[1].axhline(1.0, linewidth=1.0, linestyle="--", label="documented tolerance")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("observed magnitude / tolerance")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].legend()
    axes[1].grid(True, axis="y")

    status = bool(metrics.get("overall_observation_execution_pass", False))
    fig.suptitle(
        "V-012A budget and health summary "
        f"(software observation pass={status})"
    )
    fig.tight_layout()
    output = directory / f"{stem}_budget_and_health.png"
    _save(fig, output)
    plt.close(fig)
    return output


def plot_internal_valve_results(
    output_dir: Path | str,
    case_name: str | None = None,
) -> dict[str, Any]:
    """Generate the four V-012A human-review PNG artifacts."""

    directory = Path(output_dir)
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    stem = _resolve_case_name(directory, case_name)

    metrics = _read_json(directory / f"{stem}_metrics.json")
    valve_rows = _read_csv(directory / f"{stem}_valve_history.csv")
    flux_rows = _read_csv(directory / f"{stem}_interface_flux_history.csv")
    probe_rows = _read_csv(directory / f"{stem}_probe_history.csv")

    outputs = [
        _plot_valve_command_and_flow(
            directory=directory,
            stem=stem,
            valve_rows=valve_rows,
            flux_rows=flux_rows,
        ),
        _plot_probe_pressure_velocity(
            directory=directory,
            stem=stem,
            probe_rows=probe_rows,
        ),
        _plot_interface_flux_consistency(
            directory=directory,
            stem=stem,
            flux_rows=flux_rows,
        ),
        _plot_budget_and_health(
            directory=directory,
            stem=stem,
            metrics=metrics,
        ),
    ]
    return {
        "case_name": stem,
        "plot_count": len(outputs),
        "plot_files": [path.name for path in outputs],
        "matplotlib_version": importlib.metadata.version("matplotlib"),
        "solver_rerun": False,
        "numerical_results_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate V-012 internal-valve human-review plots"
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name", default=None)
    args = parser.parse_args(argv)
    result = plot_internal_valve_results(args.output_dir, args.case_name)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
