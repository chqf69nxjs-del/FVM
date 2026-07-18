"""Aggregate plots for the V-012 internal-valve mesh/CFL observation.

The plotter reads saved aggregate JSON/CSV artifacts and never reruns or changes
the numerical solver result. This remains software / numerical verification only.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np


PLOT_FLOOR = 1.0e-30
PLOT_SUFFIXES = (
    "applied_q_vs_dx",
    "p50_timing_offset_vs_dx",
    "characteristic_peak_amplitude_vs_dx",
    "characteristic_leakage_vs_dx",
    "post_closure_q_vs_dx",
    "post_closure_mass_flux_vs_dx",
    "budget_residual_vs_dx",
    "runtime_vs_cells",
    "cfl_runtime_step_ratio",
)


def matplotlib_available() -> bool:
    return importlib.util.find_spec("matplotlib") is not None


def _pyplot():
    if not matplotlib_available():
        raise RuntimeError(
            "matplotlib is required for V-012 mesh/CFL comparison plots"
        )
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    return plt


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"empty CSV artifact: {path.name}")
    return rows


def _number(row: dict[str, str], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric summary field: {key}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite numeric summary field: {key}")
    return value


def _mesh_rows(
    rows: Sequence[dict[str, str]],
    verification_item: str,
) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if row.get("verification_item") == verification_item
        and "mesh_comparison" in row.get("comparison_groups", "")
    ]
    selected.sort(key=lambda row: _number(row, "dx_m"), reverse=True)
    if len(selected) != 3:
        raise ValueError(
            f"{verification_item} requires three mesh-comparison rows"
        )
    return selected


def _cfl_rows(
    rows: Sequence[dict[str, str]],
    verification_item: str,
) -> dict[float, dict[str, str]]:
    selected = {
        _number(row, "cfl"): row
        for row in rows
        if row.get("verification_item") == verification_item
        and "cfl_comparison" in row.get("comparison_groups", "")
    }
    if set(selected) != {0.25, 0.5}:
        raise ValueError(
            f"{verification_item} requires CFL 0.25 and 0.5 rows"
        )
    return selected


def _save(fig: Any, path: Path) -> Path:
    fig.savefig(path, dpi=160, bbox_inches="tight")
    fig.clf()
    return path


def _line_plot(
    *,
    output: Path,
    rows: Sequence[dict[str, str]],
    keys: dict[str, str],
    ylabel: str,
    title: str,
    transform: Callable[[float], float] = lambda value: value,
    absolute: bool = False,
    log_y: bool = False,
) -> Path:
    plt = _pyplot()
    fig, axis = plt.subplots(figsize=(9, 5.5))
    for verification_item, key in keys.items():
        case_rows = _mesh_rows(rows, verification_item)
        x_values = [_number(row, "dx_m") for row in case_rows]
        raw_values = [_number(row, key) for row in case_rows]
        values = [
            transform(abs(value) if absolute else value)
            for value in raw_values
        ]
        if log_y:
            values = [max(value, PLOT_FLOOR) for value in values]
        axis.plot(x_values, values, marker="o", label=verification_item)
        for x_value, y_value, raw_value in zip(
            x_values,
            values,
            raw_values,
        ):
            if raw_value == 0.0:
                axis.annotate(
                    "0 exact",
                    (x_value, y_value),
                    textcoords="offset points",
                    xytext=(0, 6),
                    ha="center",
                    fontsize=7,
                )
    axis.set_xlabel("dx [m] (coarse to fine)")
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    if log_y:
        axis.set_yscale("log")
    axis.grid(True)
    axis.legend()
    fig.text(
        0.01,
        0.01,
        "software/numerical verification; not approved for design use",
        fontsize=8,
    )
    fig.tight_layout(rect=(0.0, 0.03, 1.0, 1.0))
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_budget_residual(
    directory: Path,
    stem: str,
    rows: Sequence[dict[str, str]],
) -> Path:
    plt = _pyplot()
    fig, axis = plt.subplots(figsize=(9, 5.5))
    keys = (
        "budget_mass_relative_residual",
        "energy_budget_balance_relative_residual",
        "phase_vapor_mass_balance_relative_residual",
    )
    for verification_item in ("V-012B", "V-012C", "V-012D"):
        case_rows = _mesh_rows(rows, verification_item)
        x_values = [_number(row, "dx_m") for row in case_rows]
        raw_values = [
            max(abs(_number(row, key)) for key in keys)
            for row in case_rows
        ]
        values = [max(value, PLOT_FLOOR) for value in raw_values]
        axis.plot(x_values, values, marker="o", label=verification_item)
        for x_value, y_value, raw_value in zip(
            x_values,
            values,
            raw_values,
        ):
            if raw_value == 0.0:
                axis.annotate(
                    "0 exact",
                    (x_value, y_value),
                    textcoords="offset points",
                    xytext=(0, 6),
                    ha="center",
                    fontsize=7,
                )
    axis.set_xlabel("dx [m] (coarse to fine)")
    axis.set_ylabel("maximum absolute relative budget residual")
    axis.set_title("V-012 mesh observation: budget residual envelope")
    axis.set_yscale("log")
    axis.grid(True)
    axis.legend()
    fig.tight_layout()
    output = directory / f"{stem}_budget_residual_vs_dx.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_runtime(
    directory: Path,
    stem: str,
    rows: Sequence[dict[str, str]],
) -> Path:
    plt = _pyplot()
    fig, axis = plt.subplots(figsize=(9, 5.5))
    for verification_item in ("V-012B", "V-012C", "V-012D"):
        case_rows = sorted(
            _mesh_rows(rows, verification_item),
            key=lambda row: int(float(row["n_cells"])),
        )
        axis.plot(
            [int(float(row["n_cells"])) for row in case_rows],
            [_number(row, "runtime_s") for row in case_rows],
            marker="o",
            label=verification_item,
        )
    axis.set_xlabel("cell count")
    axis.set_ylabel("runtime [s]")
    axis.set_title("V-012 mesh observation: execution time")
    axis.grid(True)
    axis.legend()
    fig.tight_layout()
    output = directory / f"{stem}_runtime_vs_cells.png"
    _save(fig, output)
    plt.close(fig)
    return output


def _plot_cfl_ratios(
    directory: Path,
    stem: str,
    rows: Sequence[dict[str, str]],
) -> Path:
    plt = _pyplot()
    fig, axis = plt.subplots(figsize=(9, 5.5))
    names = ["V-012B", "V-012C", "V-012D"]
    runtime_ratios: list[float] = []
    step_ratios: list[float] = []
    for verification_item in names:
        by_cfl = _cfl_rows(rows, verification_item)
        runtime_ratios.append(
            _number(by_cfl[0.25], "runtime_s")
            / _number(by_cfl[0.5], "runtime_s")
        )
        step_ratios.append(
            _number(by_cfl[0.25], "step_count")
            / _number(by_cfl[0.5], "step_count")
        )
    x = np.arange(len(names), dtype=float)
    width = 0.35
    axis.bar(x - width / 2.0, runtime_ratios, width, label="runtime ratio")
    axis.bar(x + width / 2.0, step_ratios, width, label="step-count ratio")
    axis.axhline(1.0, linewidth=0.9, linestyle="--")
    axis.set_xticks(x, names)
    axis.set_ylabel("CFL 0.25 / CFL 0.5 ratio")
    axis.set_title("V-012 CFL observation at n=100")
    axis.grid(True, axis="y")
    axis.legend()
    fig.tight_layout()
    output = directory / f"{stem}_cfl_runtime_step_ratio.png"
    _save(fig, output)
    plt.close(fig)
    return output


def generate_internal_valve_mesh_cfl_plots(
    directory: Path | str,
    case_name: str = "v012_internal_valve_mesh_cfl_sweep",
) -> dict[str, Any]:
    """Generate comparison figures from saved aggregate artifacts only."""

    output_dir = Path(directory)
    metrics_path = output_dir / f"{case_name}_metrics.json"
    summary_path = output_dir / f"{case_name}_summary.csv"
    metrics = _read_json(metrics_path)
    rows = _read_csv(summary_path)
    if bool(metrics.get("partial_execution", True)):
        raise ValueError("comparison plots require the complete 13-run sweep")
    if len(rows) != 13:
        raise ValueError("comparison plots require 13 aggregate summary rows")

    generated = [
        _line_plot(
            output=output_dir / f"{case_name}_applied_q_vs_dx.png",
            rows=rows,
            keys={
                "V-012B": "max_applied_q_m3_s_extracted",
                "V-012C": "final_applied_q_m3_s_extracted",
                "V-012D": "min_finite_opening_applied_q_m3_s_extracted",
            },
            ylabel="representative applied Q [m3/s]",
            title="V-012 mesh observation: valve-flow metrics",
        ),
        _line_plot(
            output=(
                output_dir / f"{case_name}_p50_timing_offset_vs_dx.png"
            ),
            rows=rows,
            keys={
                item: "near_probe_characteristic_p50_time_offset_max_abs_s"
                for item in ("V-012B", "V-012C", "V-012D")
            },
            ylabel="maximum |p50 timing offset| [ms]",
            title="V-012 mesh observation: near-probe p50 timing",
            transform=lambda value: 1.0e3 * value,
            absolute=True,
        ),
        _line_plot(
            output=(
                output_dir
                / f"{case_name}_characteristic_peak_amplitude_vs_dx.png"
            ),
            rows=rows,
            keys={
                item: "near_probe_characteristic_peak_abs_mean_pa"
                for item in ("V-012B", "V-012C", "V-012D")
            },
            ylabel="mean near-probe dominant peak [Pa]",
            title="V-012 mesh observation: characteristic amplitude",
        ),
        _line_plot(
            output=(
                output_dir / f"{case_name}_characteristic_leakage_vs_dx.png"
            ),
            rows=rows,
            keys={
                item: "near_probe_characteristic_max_leakage_ratio"
                for item in ("V-012B", "V-012C", "V-012D")
            },
            ylabel="opposite-direction leakage ratio",
            title="V-012 mesh observation: characteristic leakage",
            absolute=True,
            log_y=True,
        ),
        _line_plot(
            output=output_dir / f"{case_name}_post_closure_q_vs_dx.png",
            rows=rows,
            keys={
                "V-012D": (
                    "max_abs_post_closure_flux_derived_q_m3_s_extracted"
                )
            },
            ylabel="maximum post-closure |Q| [m3/s]",
            title="V-012D mesh observation: post-closure through-flow",
            absolute=True,
            log_y=True,
        ),
        _line_plot(
            output=(
                output_dir / f"{case_name}_post_closure_mass_flux_vs_dx.png"
            ),
            rows=rows,
            keys={
                "V-012D": (
                    "max_abs_post_closure_mass_flux_kg_m2_s_extracted"
                )
            },
            ylabel="maximum post-closure mass flux [kg/m2/s]",
            title="V-012D mesh observation: closed-wall mass through-flux",
            absolute=True,
            log_y=True,
        ),
        _plot_budget_residual(output_dir, case_name, rows),
        _plot_runtime(output_dir, case_name, rows),
        _plot_cfl_ratios(output_dir, case_name, rows),
    ]

    manifest = {
        "case_name": case_name,
        "verification_item": "V-012",
        "plot_count": len(generated),
        "plot_files": [path.name for path in generated],
        "solver_rerun": False,
        "numerical_results_changed": False,
        "exact_zero_visualization_floor": PLOT_FLOOR,
    }
    manifest_path = output_dir / f"{case_name}_plot_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    metrics["comparison_plots_complete"] = bool(
        len(generated) == len(PLOT_SUFFIXES)
        and all(path.stat().st_size > 0 for path in generated)
    )
    metrics["generated_comparison_plots"] = manifest["plot_files"]
    metrics["plot_manifest_path"] = manifest_path.name
    metrics["solver_rerun_for_plotting"] = False
    metrics["numerical_results_changed_by_plotting"] = False
    metrics_path.write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plot saved V-012 mesh/CFL aggregate artifacts",
    )
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--case-name",
        default="v012_internal_valve_mesh_cfl_sweep",
    )
    args = parser.parse_args(argv)
    result = generate_internal_valve_mesh_cfl_plots(
        args.directory,
        args.case_name,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
