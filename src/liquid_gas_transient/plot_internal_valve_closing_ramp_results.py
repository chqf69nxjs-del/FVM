"""Human-review plots for V-012D controlled internal-valve closing."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any

import numpy as np

from .plot_internal_valve_results import (
    _bool_value,
    _float_values,
    _plot_probe_pressure_velocity,
    _plot_ratio_bars,
    _plot_valve_command_and_flow,
    _pyplot,
    _ratio,
    _read_csv,
    _read_json,
    _require_columns,
    _resolve_case_name,
    _save,
)


PLOT_SUFFIXES = (
    "valve_command_and_flow",
    "probe_pressure_velocity",
    "probe_characteristics",
    "pressure_xt_map",
    "velocity_xt_map",
    "interface_flux_consistency",
    "budget_and_health",
    "profile_snapshots",
    "valve_dp_q_path",
)


def _event_lines(axis: Any, metrics: dict[str, Any]) -> None:
    axis.axvline(
        float(metrics["ramp_start_s"]),
        linewidth=0.9,
        linestyle="--",
        label="ramp start",
    )
    axis.axvline(
        float(metrics["ramp_end_s"]),
        linewidth=0.9,
        linestyle=":",
        label="complete closure",
    )


def _plot_characteristics(
    *,
    directory: Path,
    stem: str,
    probe_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
    metrics: dict[str, Any],
) -> Path:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in probe_rows:
        grouped.setdefault(row["probe_name"], []).append(row)
    summary_by_name = {row["probe_name"]: row for row in summary_rows}
    missing = sorted(set(grouped).difference(summary_by_name))
    if missing:
        raise ValueError(
            "missing V-012D characteristic summaries: " + ", ".join(missing)
        )

    plt = _pyplot()
    names = sorted(
        grouped,
        key=lambda name: float(grouped[name][0]["probe_cell_center_x_m"]),
    )
    fig, axes = plt.subplots(
        len(names),
        1,
        figsize=(11, max(3.0 * len(names), 5.0)),
        sharex=True,
    )
    axes_array = np.atleast_1d(axes)
    for axis, name in zip(axes_array, names):
        rows = grouped[name]
        summary = summary_by_name[name]
        time_s = _float_values(rows, "time_s")
        a_plus = _float_values(rows, "A_plus_pa") - float(summary["baseline_A_plus_pa"])
        a_minus = _float_values(rows, "A_minus_pa") - float(
            summary["baseline_A_minus_pa"]
        )
        axis.plot(time_s, a_plus, label="delta A+ right-going")
        axis.plot(time_s, a_minus, label="delta A- left-going")
        axis.axhline(0.0, linewidth=0.8)
        axis.axvline(
            float(summary["arrival_start_s"]),
            linewidth=0.8,
            linestyle="--",
            label="closure-front arrival",
        )
        axis.axvline(
            float(summary["arrival_end_s"]),
            linewidth=0.8,
            linestyle=":",
            label="ramp-end-front arrival",
        )
        axis.set_ylabel("increment [Pa]")
        axis.set_title(name)
        axis.grid(True)
        axis.legend(ncol=4)
    axes_array[-1].set_xlabel("time [s]")
    fig.suptitle("V-012D internal valve: pre-arrival-rebased characteristic increments")
    fig.tight_layout()
    output = directory / f"{stem}_probe_characteristics.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _load_field_history(path: Path) -> dict[str, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path) as payload:
        required = (
            "time_s",
            "x_m",
            "delta_pressure_pa",
            "velocity_m_s",
            "temperature_K",
            "density_kg_m3",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(
                "missing required V-012D field arrays: " + ", ".join(missing)
            )
        result = {key: np.asarray(payload[key]).copy() for key in payload.files}
    if not all(np.all(np.isfinite(value)) for value in result.values()):
        raise ValueError("non-finite V-012D field history")
    return result


def _plot_fronts(axis: Any, metrics: dict[str, Any]) -> None:
    valve_x = float(metrics["valve_x_m"])
    length = float(metrics["dx_m"]) * int(metrics["n_cells"])
    target = float(metrics["target_time_s"])
    fronts = (
        (0.0, "initial full-open front", "-."),
        (float(metrics["ramp_start_s"]), "ramp-start front", "--"),
        (float(metrics["ramp_end_s"]), "closure front", ":"),
    )
    for launch_time, label, linestyle in fronts:
        t = np.linspace(launch_time, target, 200)
        left_x = valve_x - float(metrics["left_c0_m_s"]) * (t - launch_time)
        right_x = valve_x + float(metrics["right_c0_m_s"]) * (t - launch_time)
        left_mask = (left_x >= 0.0) & (left_x <= length)
        right_mask = (right_x >= 0.0) & (right_x <= length)
        axis.plot(t[left_mask], left_x[left_mask], linestyle=linestyle, label=label)
        axis.plot(t[right_mask], right_x[right_mask], linestyle=linestyle)


def _plot_xt_map(
    *,
    directory: Path,
    stem: str,
    field: dict[str, np.ndarray],
    metrics: dict[str, Any],
    key: str,
    suffix: str,
    title: str,
    colorbar_label: str,
) -> Path:
    time_s = np.asarray(field["time_s"], dtype=float)
    x_m = np.asarray(field["x_m"], dtype=float)
    values = np.asarray(field[key], dtype=float)
    if values.shape != (time_s.size, x_m.size):
        raise ValueError(f"unexpected shape for {key}: {values.shape}")
    limit = float(np.max(np.abs(values)))
    if limit == 0.0:
        limit = 1.0

    plt = _pyplot()
    fig, axis = plt.subplots(figsize=(11, 7))
    image = axis.pcolormesh(
        time_s,
        x_m,
        values.T,
        shading="auto",
        cmap="coolwarm",
        vmin=-limit,
        vmax=limit,
    )
    _plot_fronts(axis, metrics)
    axis.axhline(float(metrics["valve_x_m"]), linewidth=0.8, alpha=0.5)
    axis.set_xlabel("time [s]")
    axis.set_ylabel("x [m]")
    axis.set_title(title)
    axis.legend(loc="best")
    fig.colorbar(image, ax=axis, label=colorbar_label)
    fig.tight_layout()
    output = directory / f"{stem}_{suffix}.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _snapshot_indices(
    time_s: np.ndarray,
    metrics: dict[str, Any],
) -> list[int]:
    requested = (
        0.0,
        float(metrics["ramp_start_s"]),
        0.5 * (float(metrics["ramp_start_s"]) + float(metrics["ramp_end_s"])),
        float(metrics["ramp_end_s"]),
        float(metrics["minimum_post_closure_end_s"]),
        float(metrics["target_time_s"]),
    )
    indices: list[int] = []
    for target in requested:
        index = int(np.argmin(np.abs(time_s - target)))
        if index not in indices:
            indices.append(index)
    return indices


def _plot_profile_snapshots(
    *,
    directory: Path,
    stem: str,
    field: dict[str, np.ndarray],
    metrics: dict[str, Any],
) -> Path:
    time_s = np.asarray(field["time_s"], dtype=float)
    x_m = np.asarray(field["x_m"], dtype=float)
    indices = _snapshot_indices(time_s, metrics)
    delta_pressure = np.asarray(field["delta_pressure_pa"], dtype=float)
    velocity = np.asarray(field["velocity_m_s"], dtype=float)
    density = np.asarray(field["density_kg_m3"], dtype=float)
    temperature = np.asarray(field["temperature_K"], dtype=float)
    density_reference = density[0]
    temperature_reference = temperature[0]

    plt = _pyplot()
    fig, axes = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
    for index in indices:
        label = f"t={time_s[index]:.5f} s"
        axes[0].plot(x_m, delta_pressure[index], label=label)
        axes[1].plot(x_m, velocity[index], label=label)
        axes[2].plot(x_m, density[index] - density_reference, label=label)
        axes[3].plot(x_m, temperature[index] - temperature_reference, label=label)
    axes[0].set_ylabel("delta p [Pa]")
    axes[1].set_ylabel("velocity [m/s]")
    axes[2].set_ylabel("delta rho [kg/m3]")
    axes[3].set_ylabel("delta T [K]")
    axes[3].set_xlabel("x [m]")
    for axis in axes:
        axis.axvline(float(metrics["valve_x_m"]), linewidth=0.8, linestyle="--")
        axis.axhline(0.0, linewidth=0.7)
        axis.grid(True)
    axes[0].legend(ncol=3)
    fig.suptitle("V-012D internal valve: representative field profiles")
    fig.tight_layout()
    output = directory / f"{stem}_profile_snapshots.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_dp_q_path(
    *,
    directory: Path,
    stem: str,
    valve_rows: list[dict[str, str]],
    metrics: dict[str, Any],
) -> Path:
    time_s = _float_values(valve_rows, "time_s")
    delta_p = _float_values(valve_rows, "delta_p_pa")
    applied_q = _float_values(valve_rows, "applied_q_m3_s")
    opening = _float_values(valve_rows, "opening_actual")

    plt = _pyplot()
    fig, axis = plt.subplots(figsize=(9, 7))
    axis.plot(delta_p, applied_q, linewidth=1.0, alpha=0.7)
    points = axis.scatter(delta_p, applied_q, c=time_s, s=24)
    for event_time, label in (
        (float(metrics["ramp_start_s"]), "ramp start"),
        (float(metrics["ramp_end_s"]), "complete closure"),
    ):
        index = int(np.argmin(np.abs(time_s - event_time)))
        axis.scatter(
            [delta_p[index]],
            [applied_q[index]],
            marker="x",
            s=90,
            label=f"{label}; opening={opening[index]:.3f}",
        )
    axis.set_xlabel("valve pressure difference [Pa]")
    axis.set_ylabel("applied Q [m3/s]")
    axis.set_title("V-012D internal valve: pressure-difference / flow path")
    axis.grid(True)
    axis.legend()
    fig.colorbar(points, ax=axis, label="time [s]")
    fig.tight_layout()
    output = directory / f"{stem}_valve_dp_q_path.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_interface_flux_consistency(
    *,
    directory: Path,
    stem: str,
    flux_rows: list[dict[str, str]],
    metrics: dict[str, Any],
) -> Path:
    path = directory / f"{stem}_interface_flux_history.csv"
    _require_columns(
        flux_rows,
        path,
        (
            "time_s",
            "opening_actual",
            "hydraulic_separation_active",
            "mass_flux_mismatch_kg_m2_s",
            "energy_flux_mismatch_w_m2",
            "vapor_mass_flux_mismatch_kg_m2_s",
            "left_momentum_flux_pa",
            "right_momentum_flux_pa",
            "momentum_difference_residual_pa",
            "flux_q_minus_applied_q_m3_s",
        ),
    )
    t = _float_values(flux_rows, "time_s")
    closed = np.asarray(
        [_bool_value(row["hydraulic_separation_active"]) for row in flux_rows]
    )
    momentum_residual = _float_values(flux_rows, "momentum_difference_residual_pa")
    finite_residual = np.where(closed, np.nan, momentum_residual)

    plt = _pyplot()
    fig, axes = plt.subplots(6, 1, figsize=(11, 15), sharex=True)
    axes[0].plot(t, _float_values(flux_rows, "mass_flux_mismatch_kg_m2_s"))
    axes[0].set_ylabel("mass mismatch\n[kg/m2/s]")
    axes[1].plot(t, _float_values(flux_rows, "energy_flux_mismatch_w_m2"))
    axes[1].set_ylabel("energy mismatch\n[W/m2]")
    axes[2].plot(t, _float_values(flux_rows, "vapor_mass_flux_mismatch_kg_m2_s"))
    axes[2].set_ylabel("vapor mismatch\n[kg/m2/s]")
    axes[3].plot(t, finite_residual, label="finite-opening residual")
    axes[3].set_ylabel("momentum residual\n[Pa]")
    axes[3].legend()
    axes[4].plot(
        t,
        _float_values(flux_rows, "left_momentum_flux_pa"),
        label="left wall/face momentum flux",
    )
    axes[4].plot(
        t,
        _float_values(flux_rows, "right_momentum_flux_pa"),
        label="right wall/face momentum flux",
        linestyle="--",
    )
    axes[4].set_ylabel("momentum flux\n[Pa]")
    axes[4].legend()
    axes[5].plot(t, _float_values(flux_rows, "flux_q_minus_applied_q_m3_s"))
    axes[5].set_ylabel("flux Q - applied Q\n[m3/s]")
    axes[5].set_xlabel("time [s]")
    for axis in axes:
        axis.axhline(0.0, linewidth=0.8)
        _event_lines(axis, metrics)
        axis.grid(True)
    fig.suptitle(
        "V-012D interface consistency: finite-opening relation and closed-wall reactions"
    )
    fig.tight_layout()
    output = directory / f"{stem}_interface_flux_consistency.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_budget_and_health(
    *,
    directory: Path,
    stem: str,
    metrics: dict[str, Any],
) -> Path:
    budget_pairs = (
        ("mass", "budget_mass_relative_residual", "relative_budget_tolerance"),
        (
            "energy",
            "energy_budget_balance_relative_residual",
            "relative_budget_tolerance",
        ),
        (
            "vapor mass",
            "phase_vapor_mass_balance_relative_residual",
            "relative_budget_tolerance",
        ),
    )
    finite_pairs = (
        ("opening", "max_abs_opening_error", "opening_roundoff_tolerance"),
        (
            "finite raw-applied",
            "max_raw_applied_relative_difference",
            "flow_relative_tolerance",
        ),
        (
            "finite applied-flux",
            "max_applied_flux_relative_difference",
            "flow_relative_tolerance",
        ),
        (
            "mass mismatch",
            "max_abs_mass_flux_mismatch_kg_m2_s",
            "mass_flux_roundoff_tolerance_kg_m2_s",
        ),
        (
            "energy mismatch",
            "max_abs_energy_flux_mismatch_w_m2",
            "energy_flux_roundoff_tolerance_w_m2",
        ),
        (
            "vapor mismatch",
            "max_abs_vapor_mass_flux_mismatch_kg_m2_s",
            "vapor_flux_roundoff_tolerance_kg_m2_s",
        ),
        (
            "finite momentum",
            "max_abs_finite_opening_momentum_difference_residual_pa",
            "finite_opening_momentum_roundoff_tolerance_pa",
        ),
        (
            "Q consistency",
            "max_abs_flux_q_minus_applied_q_m3_s",
            "q_roundoff_tolerance_m3_s",
        ),
    )
    closure_pairs = (
        (
            "raw Q",
            "max_abs_post_closure_raw_target_q_m3_s",
            "q_roundoff_tolerance_m3_s",
        ),
        (
            "applied Q",
            "max_abs_post_closure_applied_q_m3_s",
            "q_roundoff_tolerance_m3_s",
        ),
        (
            "flux Q",
            "max_abs_post_closure_flux_derived_q_m3_s",
            "q_roundoff_tolerance_m3_s",
        ),
        (
            "mass through-flux",
            "max_abs_post_closure_mass_flux_kg_m2_s",
            "mass_flux_roundoff_tolerance_kg_m2_s",
        ),
        (
            "energy through-flux",
            "max_abs_post_closure_energy_flux_w_m2",
            "energy_flux_roundoff_tolerance_w_m2",
        ),
        (
            "vapor through-flux",
            "max_abs_post_closure_vapor_mass_flux_kg_m2_s",
            "vapor_flux_roundoff_tolerance_kg_m2_s",
        ),
    )
    required = {
        key
        for _, value_key, tolerance_key in budget_pairs + finite_pairs + closure_pairs
        for key in (value_key, tolerance_key)
    }
    missing = sorted(required.difference(metrics))
    if missing:
        raise ValueError("missing required V-012D plot metrics: " + ", ".join(missing))

    plt = _pyplot()
    fig, axes = plt.subplots(3, 1, figsize=(13, 12))
    for axis, pairs, ylabel in (
        (axes[0], budget_pairs, "absolute residual / observation tolerance"),
        (axes[1], finite_pairs, "finite/interface magnitude / tolerance"),
        (axes[2], closure_pairs, "post-closure through quantity / tolerance"),
    ):
        _plot_ratio_bars(
            axis,
            [label for label, _, _ in pairs],
            [
                _ratio(metrics[value], metrics[tolerance])
                for _, value, tolerance in pairs
            ],
            ylabel,
        )
        axis.tick_params(axis="x", rotation=25)
    axes[2].text(
        0.01,
        0.97,
        (
            "closure separation fraction="
            f"{float(metrics['post_closure_hydraulic_separation_fraction']):.3f}; "
            "primary direction pass="
            f"{bool(metrics['primary_characteristic_direction_pass'])}"
        ),
        transform=axes[2].transAxes,
        va="top",
    )
    status = bool(metrics.get("overall_observation_execution_pass", False))
    fig.suptitle(
        "V-012D budget, finite-opening consistency, and complete-closure summary "
        f"(software observation pass={status})\n"
        "Exact zeros are labelled explicitly and drawn at the visualization floor."
    )
    fig.tight_layout()
    output = directory / f"{stem}_budget_and_health.png"
    _save(fig, output)
    plt.close(fig)
    return output


def plot_internal_valve_closing_ramp_results(
    output_dir: Path | str,
    case_name: str | None = None,
) -> dict[str, Any]:
    """Generate the V-012D human-review plot set from saved artifacts."""

    directory = Path(output_dir)
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    stem = _resolve_case_name(directory, case_name)
    metrics = _read_json(directory / f"{stem}_metrics.json")
    if metrics.get("verification_item") != "V-012D":
        raise ValueError("closing-ramp plotter requires verification_item V-012D")
    valve_rows = _read_csv(directory / f"{stem}_valve_history.csv")
    flux_rows = _read_csv(directory / f"{stem}_interface_flux_history.csv")
    probe_rows = _read_csv(directory / f"{stem}_probe_history.csv")
    summary_rows = _read_csv(directory / f"{stem}_probe_characteristic_summary.csv")
    field = _load_field_history(directory / f"{stem}_field_history.npz")

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
        _plot_characteristics(
            directory=directory,
            stem=stem,
            probe_rows=probe_rows,
            summary_rows=summary_rows,
            metrics=metrics,
        ),
        _plot_xt_map(
            directory=directory,
            stem=stem,
            field=field,
            metrics=metrics,
            key="delta_pressure_pa",
            suffix="pressure_xt_map",
            title="V-012D internal valve: x-t pressure perturbation",
            colorbar_label="delta pressure [Pa]",
        ),
        _plot_xt_map(
            directory=directory,
            stem=stem,
            field=field,
            metrics=metrics,
            key="velocity_m_s",
            suffix="velocity_xt_map",
            title="V-012D internal valve: x-t velocity",
            colorbar_label="velocity [m/s]",
        ),
        _plot_interface_flux_consistency(
            directory=directory,
            stem=stem,
            flux_rows=flux_rows,
            metrics=metrics,
        ),
        _plot_budget_and_health(
            directory=directory,
            stem=stem,
            metrics=metrics,
        ),
        _plot_profile_snapshots(
            directory=directory,
            stem=stem,
            field=field,
            metrics=metrics,
        ),
        _plot_dp_q_path(
            directory=directory,
            stem=stem,
            valve_rows=valve_rows,
            metrics=metrics,
        ),
    ]
    return {
        "case_name": stem,
        "verification_item": "V-012D",
        "plot_count": len(outputs),
        "plot_files": [path.name for path in outputs],
        "matplotlib_version": importlib.metadata.version("matplotlib"),
        "solver_rerun": False,
        "numerical_results_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate V-012D review plots")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--case-name", default=None)
    args = parser.parse_args(argv)
    result = plot_internal_valve_closing_ramp_results(
        args.output_dir,
        args.case_name,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
