"""Plot saved V-013A incident-propagation comparison artifacts.

The plotter reads saved CSV/JSON/NPZ artifacts and does not rerun the FVM, MOC, or
analytical paths.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPECTED_PLOT_COUNT = 7


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    converted: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for key, value in row.items():
            if value in ("", None):
                item[key] = None
            elif value == "True":
                item[key] = True
            elif value == "False":
                item[key] = False
            else:
                try:
                    item[key] = float(value)
                except (TypeError, ValueError):
                    item[key] = value
        converted.append(item)
    return converted


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(fig: Any, base: Path, name: str) -> str:
    fig.text(
        0.01,
        0.01,
        "V-013A software/numerical verification only; not physical Validation or design-use acceptance",
        fontsize=7,
    )
    fig.tight_layout(rect=(0.0, 0.035, 1.0, 1.0))
    fig.savefig(base / name, dpi=160, bbox_inches="tight")
    return name


def _case_id_for_finest(summary_rows: Sequence[Mapping[str, Any]]) -> str:
    if not summary_rows:
        raise ValueError("V-013A summary is empty")
    return str(max(summary_rows, key=lambda row: int(float(row["n_cells"])))["case_id"])


def plot_v013_incident_propagation_results(
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate V-013A comparison figures from saved artifacts only."""

    base = Path(output_dir)
    metrics = _load_json(base / "v013a_metrics.json")
    summary = _read_csv(base / "v013a_summary.csv")
    finest_case_id = _case_id_for_finest(summary)
    run_dir = base / finest_case_id
    matched = _read_csv(run_dir / "matched_samples.csv")
    probe = _read_csv(run_dir / "probe_comparison.csv")
    comparison = _load_json(run_dir / "comparison_metrics.json")

    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception as exc:  # pragma: no cover
        return {
            "plot_count": 0,
            "expected_plot_count": EXPECTED_PLOT_COUNT,
            "plot_files": [],
            "plotting_errors": {"matplotlib_import": str(exc)},
            "solver_rerun": False,
            "numerical_results_changed": False,
        }

    generated: list[str] = []
    errors: dict[str, str] = {}

    def figure() -> Any:
        fig = Figure(figsize=(9.0, 5.5))
        FigureCanvasAgg(fig)
        return fig

    unique_times = sorted({float(row["time_s"]) for row in matched})
    selected_times = unique_times[1:] if len(unique_times) > 1 else unique_times

    try:
        fig = figure()
        ax = fig.subplots()
        for time_value in selected_times:
            rows = [row for row in matched if float(row["time_s"]) == time_value]
            x = [row["x_m"] for row in rows]
            ax.plot(
                x,
                [row["fvm_pressure_perturbation_pa"] for row in rows],
                label=f"FVM t={time_value:.5g}s",
            )
            ax.plot(
                x,
                [row["analytical_pressure_perturbation_pa"] for row in rows],
                linestyle="--",
                label=f"analytical t={time_value:.5g}s",
            )
        ax.set_title(f"V-013A pressure profiles — finest mesh {finest_case_id}")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("pressure perturbation [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
        generated.append(_save(fig, base, "v013a_incident_pressure_profiles.png"))
    except Exception as exc:
        errors["pressure_profiles"] = str(exc)

    try:
        time_value = unique_times[-1]
        rows = [row for row in matched if float(row["time_s"]) == time_value]
        fig = figure()
        ax = fig.subplots()
        ax.plot(
            [row["x_m"] for row in rows],
            [row["fvm_velocity_m_s"] for row in rows],
            label="FVM",
        )
        ax.plot(
            [row["x_m"] for row in rows],
            [row["moc_velocity_m_s"] for row in rows],
            label="MOC",
        )
        ax.plot(
            [row["x_m"] for row in rows],
            [row["analytical_velocity_m_s"] for row in rows],
            linestyle="--",
            label="analytical",
        )
        ax.set_title(f"V-013A velocity profile at t={time_value:.6g} s")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("velocity [m/s]")
        ax.grid(True, alpha=0.3)
        ax.legend()
        generated.append(_save(fig, base, "v013a_incident_velocity_profile.png"))
    except Exception as exc:
        errors["velocity_profile"] = str(exc)

    try:
        time_value = unique_times[-1]
        rows = [row for row in matched if float(row["time_s"]) == time_value]
        fig = figure()
        ax = fig.subplots()
        ax.plot(
            [row["x_m"] for row in rows],
            [row["fvm_a_plus_pa"] for row in rows],
            label="FVM A+",
        )
        ax.plot(
            [row["x_m"] for row in rows],
            [row["analytical_a_plus_pa"] for row in rows],
            linestyle="--",
            label="analytical A+",
        )
        ax.plot(
            [row["x_m"] for row in rows],
            [row["fvm_a_minus_pa"] for row in rows],
            label="FVM A-",
        )
        ax.plot(
            [row["x_m"] for row in rows],
            [row["moc_a_minus_pa"] for row in rows],
            label="MOC A-",
        )
        ax.set_title(f"V-013A characteristic components at t={time_value:.6g} s")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("pressure-dimension characteristic [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend()
        generated.append(
            _save(fig, base, "v013a_incident_characteristic_profiles.png")
        )
    except Exception as exc:
        errors["characteristic_profiles"] = str(exc)

    try:
        probe_ids = sorted({str(row["probe_id"]) for row in probe})
        selected_probe = probe_ids[-1]
        rows = [row for row in probe if row["probe_id"] == selected_probe]
        fig = figure()
        ax = fig.subplots()
        ax.plot(
            [row["time_s"] for row in rows],
            [row["fvm_pressure_perturbation_pa"] for row in rows],
            label="FVM",
        )
        ax.plot(
            [row["time_s"] for row in rows],
            [row["moc_pressure_perturbation_pa"] for row in rows],
            label="MOC",
        )
        ax.plot(
            [row["time_s"] for row in rows],
            [row["analytical_pressure_perturbation_pa"] for row in rows],
            linestyle="--",
            label="analytical",
        )
        arrival = next(
            row
            for row in comparison["probe_arrival_metrics"]
            if row["probe_id"] == selected_probe
        )
        for implementation, linestyle in (
            ("fvm", ":"),
            ("moc", "-."),
            ("analytical", "--"),
        ):
            value = arrival.get(f"{implementation}_p50_time_s")
            if value is not None:
                ax.axvline(
                    value,
                    linestyle=linestyle,
                    linewidth=0.9,
                    alpha=0.65,
                    label=f"{implementation} p50",
                )
        ax.set_title(f"V-013A probe history — {selected_probe}")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("pressure perturbation [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        generated.append(_save(fig, base, "v013a_incident_probe_history.png"))
    except Exception as exc:
        errors["probe_history"] = str(exc)

    try:
        rows = sorted(summary, key=lambda row: float(row["dx_m"]), reverse=True)
        fig = figure()
        ax = fig.subplots()
        for label, key in (
            ("FVM pressure L2", "max_fvm_pressure_l2_relative"),
            ("MOC pressure L2", "max_moc_pressure_l2_relative"),
            ("FVM velocity L2", "max_fvm_velocity_l2_relative"),
            ("MOC velocity L2", "max_moc_velocity_l2_relative"),
        ):
            ax.plot(
                [row["dx_m"] for row in rows],
                [row[key] for row in rows],
                marker="o",
                label=label,
            )
        ax.set_yscale("log")
        ax.set_title("V-013A field error versus mesh spacing")
        ax.set_xlabel("dx [m] (coarse to fine)")
        ax.set_ylabel("maximum normalized L2 error [-]")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend(fontsize=8)
        generated.append(_save(fig, base, "v013a_field_error_vs_dx.png"))
    except Exception as exc:
        errors["field_error_vs_dx"] = str(exc)

    try:
        rows = sorted(summary, key=lambda row: float(row["dx_m"]), reverse=True)
        fig = figure()
        ax = fig.subplots()
        ax.plot(
            [row["dx_m"] for row in rows],
            [abs(row["max_abs_fvm_p50_offset_s"]) for row in rows],
            marker="o",
            label="FVM max |p50 offset|",
        )
        ax.plot(
            [row["dx_m"] for row in rows],
            [abs(row["max_abs_moc_p50_offset_s"]) for row in rows],
            marker="o",
            label="MOC max |p50 offset|",
        )
        ax.plot(
            [row["dx_m"] for row in rows],
            [row["fvm_p50_speed_relative_error"] for row in rows],
            marker="s",
            label="FVM p50 speed relative error",
        )
        ax.plot(
            [row["dx_m"] for row in rows],
            [row["moc_p50_speed_relative_error"] for row in rows],
            marker="s",
            label="MOC p50 speed relative error",
        )
        ax.set_yscale("log")
        ax.set_title("V-013A arrival and propagation-speed observations")
        ax.set_xlabel("dx [m] (coarse to fine)")
        ax.set_ylabel("offset [s] or relative error [-]")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend(fontsize=8)
        generated.append(_save(fig, base, "v013a_arrival_speed_vs_dx.png"))
    except Exception as exc:
        errors["arrival_speed_vs_dx"] = str(exc)

    try:
        rows = sorted(summary, key=lambda row: float(row["dx_m"]), reverse=True)
        fig = figure()
        ax = fig.subplots()
        ax.plot(
            [row["dx_m"] for row in rows],
            [abs(row["max_abs_fvm_energy_relative_difference"]) for row in rows],
            marker="o",
            label="FVM",
        )
        ax.plot(
            [row["dx_m"] for row in rows],
            [abs(row["max_abs_moc_energy_relative_difference"]) for row in rows],
            marker="o",
            label="MOC",
        )
        ax.set_yscale("log")
        ax.set_title("V-013A acoustic-energy-proxy difference")
        ax.set_xlabel("dx [m] (coarse to fine)")
        ax.set_ylabel("maximum absolute relative difference [-]")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend()
        generated.append(_save(fig, base, "v013a_energy_proxy_vs_dx.png"))
    except Exception as exc:
        errors["energy_proxy_vs_dx"] = str(exc)

    result = {
        "case_name": metrics["case_name"],
        "verification_item": "V-013A",
        "plot_count": len(generated),
        "expected_plot_count": EXPECTED_PLOT_COUNT,
        "plot_files": generated,
        "plotting_errors": errors,
        "solver_rerun": False,
        "numerical_results_changed": False,
    }
    (base / "v013a_plot_metrics.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


__all__ = ["EXPECTED_PLOT_COUNT", "plot_v013_incident_propagation_results"]
