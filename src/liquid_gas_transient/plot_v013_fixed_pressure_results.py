"""Generate V-013C fixed-pressure comparison figures from saved artifacts only.

The plotter reads the JSON/CSV artifacts written by
``v013_fixed_pressure_observation``. It does not import or rerun the FVM, MOC, or
analytical calculation paths.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


EXPECTED_PLOT_COUNT = 7
MODEL_DESCRIPTION = (
    "production FVM / independent linear-acoustic MOC + analytical"
)
_REQUIRED_TRACEABILITY_KEYS = (
    "case_name",
    "output_version",
    "property_backend_name",
    "coolprop_version",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


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


def build_v013c_plot_traceability(metrics: Mapping[str, Any]) -> str:
    """Return the mandatory case/model/backend/version figure footer."""

    missing = [
        key
        for key in _REQUIRED_TRACEABILITY_KEYS
        if not isinstance(metrics.get(key), str) or not str(metrics[key]).strip()
    ]
    if missing:
        raise ValueError(
            "V-013C plot traceability fields are missing: " + ", ".join(missing)
        )
    return (
        f"case: {metrics['case_name']} | model: {MODEL_DESCRIPTION} | "
        f"backend: {metrics['property_backend_name']} | "
        f"CoolProp: {metrics['coolprop_version']} | "
        f"output: {metrics['output_version']}\n"
        "V-013C software/numerical verification only; "
        "not physical Validation or design-use acceptance"
    )


def _save(fig: Any, base: Path, name: str, traceability: str) -> str:
    fig.text(0.01, 0.01, traceability, fontsize=7, va="bottom")
    fig.tight_layout(rect=(0.0, 0.085, 1.0, 1.0))
    fig.savefig(base / name, dpi=160, bbox_inches="tight")
    return name


def _finest_case_id(summary_rows: Sequence[Mapping[str, Any]]) -> str:
    if not summary_rows:
        raise ValueError("V-013C summary is empty")
    row = max(summary_rows, key=lambda item: int(float(item["n_cells"])))
    return str(row["case_id"])


def _selected_sample_ids(
    matched_rows: Sequence[Mapping[str, Any]],
) -> list[str]:
    metadata: dict[str, dict[str, Any]] = {}
    for row in matched_rows:
        sample_id = str(row["sample_id"])
        metadata.setdefault(
            sample_id,
            {
                "sample_id": sample_id,
                "phase": str(row["phase"]),
                "path_travel_m": float(row["path_travel_m"]),
            },
        )
    incident = sorted(
        (row for row in metadata.values() if row["phase"] == "incident"),
        key=lambda row: float(row["path_travel_m"]),
    )
    contact = sorted(
        (row for row in metadata.values() if row["phase"] == "boundary_contact"),
        key=lambda row: float(row["path_travel_m"]),
    )
    reflected = sorted(
        (row for row in metadata.values() if row["phase"] == "reflected"),
        key=lambda row: float(row["path_travel_m"]),
    )
    if not incident or not contact or not reflected:
        raise ValueError(
            "V-013C samples must include incident, boundary-contact, and reflected phases"
        )
    selected = [incident[-1], contact[0], reflected[0], reflected[-1]]
    return list(dict.fromkeys(str(row["sample_id"]) for row in selected))


def _rows_for_sample(
    matched_rows: Sequence[Mapping[str, Any]],
    sample_id: str,
) -> list[Mapping[str, Any]]:
    rows = [row for row in matched_rows if str(row["sample_id"]) == sample_id]
    return sorted(rows, key=lambda row: float(row["x_m"]))


def _sample_label(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        raise ValueError("V-013C sample rows are empty")
    first = rows[0]
    return f"{first['phase']} {float(first['path_travel_m']):g} m"


def _mean_probe_coefficient(
    comparison: Mapping[str, Any],
    implementation: str,
    key: str,
) -> float:
    values = [
        probe["implementations"][implementation].get(key)
        for probe in comparison["probe_reflection_metrics"]
    ]
    usable = [float(value) for value in values if value is not None]
    if not usable:
        raise ValueError(f"no {implementation} {key} values in V-013C artifacts")
    return float(np.mean(usable))


def _maximum_field_metric(
    comparison: Mapping[str, Any],
    implementation: str,
    field: str,
    metric: str,
) -> float:
    return max(
        float(sample[implementation][field][metric])
        for sample in comparison["field_metrics"]
    )


def _maximum_energy_difference(
    comparison: Mapping[str, Any],
    implementation: str,
) -> float:
    values = [
        sample[implementation].get("acoustic_energy_relative_difference")
        for sample in comparison["field_metrics"]
    ]
    usable = [abs(float(value)) for value in values if value is not None]
    return max(usable) if usable else 0.0


def plot_v013_fixed_pressure_results(
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate seven comparison figures without rerunning numerical solvers."""

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    base = Path(output_dir)
    metrics_path = base / "v013c_metrics.json"
    metrics = _load_json(metrics_path)
    traceability = build_v013c_plot_traceability(metrics)
    summary = sorted(
        _read_csv(base / "v013c_summary.csv"),
        key=lambda row: float(row["dx_m"]),
    )
    finest_case_id = _finest_case_id(summary)
    finest_dir = base / finest_case_id
    matched = _read_csv(finest_dir / "matched_samples.csv")
    probe_rows = _read_csv(finest_dir / "probe_comparison.csv")
    finest_comparison = _load_json(finest_dir / "comparison_metrics.json")
    selected_sample_ids = _selected_sample_ids(matched)

    run_data: list[dict[str, Any]] = []
    for summary_row in summary:
        case_id = str(summary_row["case_id"])
        run_dir = base / case_id
        run_data.append(
            {
                "case_id": case_id,
                "dx_m": float(summary_row["dx_m"]),
                "summary": summary_row,
                "fvm": _load_json(run_dir / "fvm_metrics.json"),
                "comparison": _load_json(run_dir / "comparison_metrics.json"),
            }
        )

    generated: list[str] = []
    errors: dict[str, str] = {}

    try:
        fig, ax = plt.subplots()
        for sample_id in selected_sample_ids:
            rows = _rows_for_sample(matched, sample_id)
            label = _sample_label(rows)
            x = [float(row["x_m"]) for row in rows]
            ax.plot(
                x,
                [float(row["fvm_pressure_perturbation_pa"]) for row in rows],
                label=f"FVM {label}",
            )
            ax.plot(
                x,
                [float(row["moc_pressure_perturbation_pa"]) for row in rows],
                linestyle="--",
                label=f"MOC {label}",
            )
            ax.plot(
                x,
                [float(row["analytical_pressure_perturbation_pa"]) for row in rows],
                linestyle=":",
                label=f"analytical {label}",
            )
        ax.axhline(0.0, linewidth=0.8)
        ax.set_title("V-013C fixed-pressure reflection: pressure profiles")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("pressure perturbation [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013c_fixed_pressure_pressure_profiles.png",
                traceability,
            )
        )
        plt.close(fig)
    except Exception as exc:
        errors["pressure_profiles"] = str(exc)

    try:
        fig, ax = plt.subplots()
        for sample_id in selected_sample_ids:
            rows = _rows_for_sample(matched, sample_id)
            label = _sample_label(rows)
            x = [float(row["x_m"]) for row in rows]
            ax.plot(
                x,
                [float(row["fvm_velocity_m_s"]) for row in rows],
                label=f"FVM {label}",
            )
            ax.plot(
                x,
                [float(row["moc_velocity_m_s"]) for row in rows],
                linestyle="--",
                label=f"MOC {label}",
            )
            ax.plot(
                x,
                [float(row["analytical_velocity_m_s"]) for row in rows],
                linestyle=":",
                label=f"analytical {label}",
            )
        ax.axhline(0.0, linewidth=0.8)
        ax.set_title("V-013C fixed-pressure reflection: velocity profiles")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("velocity perturbation [m/s]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013c_fixed_pressure_velocity_profiles.png",
                traceability,
            )
        )
        plt.close(fig)
    except Exception as exc:
        errors["velocity_profiles"] = str(exc)

    try:
        reflected_id = next(
            sample_id
            for sample_id in selected_sample_ids
            if _rows_for_sample(matched, sample_id)[0]["phase"] == "reflected"
        )
        rows = _rows_for_sample(matched, reflected_id)
        x = [float(row["x_m"]) for row in rows]
        fig, ax = plt.subplots()
        for implementation, linestyle in (
            ("fvm", "-"),
            ("moc", "--"),
            ("analytical", ":"),
        ):
            ax.plot(
                x,
                [float(row[f"{implementation}_a_plus_pa"]) for row in rows],
                linestyle=linestyle,
                label=f"{implementation} A+",
            )
            ax.plot(
                x,
                [float(row[f"{implementation}_a_minus_pa"]) for row in rows],
                linestyle=linestyle,
                label=f"{implementation} A-",
            )
        ax.axhline(0.0, linewidth=0.8)
        ax.set_title(
            "V-013C reflected characteristics "
            f"({_sample_label(rows)})"
        )
        ax.set_xlabel("x [m]")
        ax.set_ylabel("characteristic amplitude [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013c_fixed_pressure_characteristics.png",
                traceability,
            )
        )
        plt.close(fig)
    except Exception as exc:
        errors["characteristics"] = str(exc)

    try:
        probes = finest_comparison["probe_reflection_metrics"]
        target_probe = max(probes, key=lambda item: float(item["probe_x_m"]))
        probe_id = str(target_probe["probe_id"])
        rows = sorted(
            (row for row in probe_rows if str(row["probe_id"]) == probe_id),
            key=lambda row: float(row["time_s"]),
        )
        timing = target_probe["timing"]
        fig, ax = plt.subplots()
        time_values = [float(row["time_s"]) for row in rows]
        ax.plot(
            time_values,
            [float(row["fvm_pressure_perturbation_pa"]) for row in rows],
            label="FVM",
        )
        ax.plot(
            time_values,
            [float(row["moc_pressure_perturbation_pa"]) for row in rows],
            linestyle="--",
            label="MOC",
        )
        ax.plot(
            time_values,
            [float(row["analytical_pressure_perturbation_pa"]) for row in rows],
            linestyle=":",
            label="analytical",
        )
        for key, label in (
            ("theoretical_incident_time_s", "incident"),
            ("theoretical_boundary_time_s", "boundary contact"),
            ("theoretical_reflected_time_s", "reflected"),
        ):
            ax.axvline(float(timing[key]), linestyle="--", label=label)
        ax.axhline(0.0, linewidth=0.8)
        ax.set_title(
            "V-013C near-boundary pressure history "
            f"(x={float(target_probe['probe_x_m']):g} m)"
        )
        ax.set_xlabel("time [s]")
        ax.set_ylabel("pressure perturbation [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013c_fixed_pressure_probe_history.png",
                traceability,
            )
        )
        plt.close(fig)
    except Exception as exc:
        errors["probe_history"] = str(exc)

    try:
        fig, ax = plt.subplots()
        dx = [row["dx_m"] for row in run_data]
        for implementation, marker in (("fvm", "o"), ("moc", "s")):
            pressure = [
                _mean_probe_coefficient(
                    row["comparison"],
                    implementation,
                    "pressure_reflection_coefficient",
                )
                for row in run_data
            ]
            velocity = [
                _mean_probe_coefficient(
                    row["comparison"],
                    implementation,
                    "velocity_reflection_coefficient",
                )
                for row in run_data
            ]
            ax.plot(
                dx,
                pressure,
                marker=marker,
                label=f"{implementation} pressure",
            )
            ax.plot(
                dx,
                velocity,
                marker=marker,
                linestyle="--",
                label=f"{implementation} velocity",
            )
        ax.axhline(-1.0, linestyle=":", label="ideal pressure -1")
        ax.axhline(1.0, linestyle="-.", label="ideal velocity +1")
        ax.set_title("V-013C reflection coefficients")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("reflection coefficient [-]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013c_reflection_coefficients_vs_dx.png",
                traceability,
            )
        )
        plt.close(fig)
    except Exception as exc:
        errors["reflection_coefficients"] = str(exc)

    try:
        fig, ax = plt.subplots()
        dx = [row["dx_m"] for row in run_data]
        floor = np.finfo(float).tiny
        for implementation, marker in (("fvm", "o"), ("moc", "s")):
            for field, label, linestyle in (
                ("pressure_perturbation_pa", "pressure L2", "-"),
                ("velocity_m_s", "velocity L2", "--"),
            ):
                values = [
                    max(
                        _maximum_field_metric(
                            row["comparison"],
                            implementation,
                            field,
                            "l2_relative",
                        ),
                        floor,
                    )
                    for row in run_data
                ]
                ax.plot(
                    dx,
                    values,
                    marker=marker,
                    linestyle=linestyle,
                    label=f"{implementation} {label}",
                )
            energy = [
                max(
                    _maximum_energy_difference(
                        row["comparison"],
                        implementation,
                    ),
                    floor,
                )
                for row in run_data
            ]
            ax.plot(
                dx,
                energy,
                marker=marker,
                linestyle=":",
                label=f"{implementation} energy difference",
            )
        ax.set_yscale("log")
        ax.set_title("V-013C field and acoustic-energy differences")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("maximum normalized difference [-]")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013c_field_energy_error_vs_dx.png",
                traceability,
            )
        )
        plt.close(fig)
    except Exception as exc:
        errors["field_energy_error"] = str(exc)

    try:
        fig, ax = plt.subplots()
        dx = [row["dx_m"] for row in run_data]
        pressure_residual = [
            float(
                row["fvm"]["boundary_metrics"][
                    "normalized_fixed_pressure_residual"
                ]
            )
            for row in run_data
        ]
        velocity_error = [
            float(
                row["fvm"]["boundary_metrics"][
                    "boundary_velocity_amplification_error"
                ]
            )
            for row in run_data
        ]
        ax.plot(
            dx,
            pressure_residual,
            marker="o",
            label="normalized fixed-pressure residual",
        )
        ax.plot(
            dx,
            velocity_error,
            marker="s",
            label="|boundary velocity ratio - 2|",
        )
        ax.axhline(0.0, linewidth=0.8)
        ax.set_ylim(bottom=0.0)
        ax.set_title("V-013C fixed-pressure boundary residuals")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("normalized residual [-]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        generated.append(
            _save(
                fig,
                base,
                "v013c_fixed_pressure_condition_vs_dx.png",
                traceability,
            )
        )
        plt.close(fig)
    except Exception as exc:
        errors["fixed_pressure_condition"] = str(exc)

    result = {
        "case_name": metrics["case_name"],
        "verification_item": "V-013C",
        "model": MODEL_DESCRIPTION,
        "property_backend_name": metrics["property_backend_name"],
        "coolprop_version": metrics["coolprop_version"],
        "output_version": metrics["output_version"],
        "plot_count": len(generated),
        "expected_plot_count": EXPECTED_PLOT_COUNT,
        "plot_files": generated,
        "plotting_errors": errors,
        "solver_rerun": False,
        "numerical_results_changed": False,
    }
    _write_json(base / "v013c_plot_metrics.json", result)
    metrics["comparison_plots_complete"] = bool(
        len(generated) == EXPECTED_PLOT_COUNT and not errors
    )
    metrics["generated_plots"] = generated
    metrics["plotting_errors"] = errors
    _write_json(metrics_path, metrics)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    result = plot_v013_fixed_pressure_results(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["plot_count"] == EXPECTED_PLOT_COUNT and not result[
        "plotting_errors"
    ] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "EXPECTED_PLOT_COUNT",
    "build_v013c_plot_traceability",
    "plot_v013_fixed_pressure_results",
]
