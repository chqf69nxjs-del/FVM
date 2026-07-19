"""Generate V-013B rigid-wall comparison figures from saved artifacts only.

The plotter reads the JSON/CSV artifacts written by
``v013_rigid_wall_observation``.  It does not import or rerun the FVM, MOC, or
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


def build_v013b_plot_traceability(metrics: Mapping[str, Any]) -> str:
    """Return the mandatory case/model/backend/version figure footer."""

    missing = [
        key
        for key in _REQUIRED_TRACEABILITY_KEYS
        if not isinstance(metrics.get(key), str) or not str(metrics[key]).strip()
    ]
    if missing:
        raise ValueError(
            "V-013B plot traceability fields are missing: " + ", ".join(missing)
        )
    return (
        f"case: {metrics['case_name']} | model: {MODEL_DESCRIPTION} | "
        f"backend: {metrics['property_backend_name']} | "
        f"CoolProp: {metrics['coolprop_version']} | "
        f"output: {metrics['output_version']}\n"
        "V-013B software/numerical verification only; "
        "not physical Validation or design-use acceptance"
    )


def _save(
    fig: Any,
    base: Path,
    name: str,
    traceability: str,
) -> str:
    fig.text(0.01, 0.01, traceability, fontsize=7, va="bottom")
    fig.tight_layout(rect=(0.0, 0.085, 1.0, 1.0))
    fig.savefig(base / name, dpi=160, bbox_inches="tight")
    return name


def _finest_case_id(summary_rows: Sequence[Mapping[str, Any]]) -> str:
    if not summary_rows:
        raise ValueError("V-013B summary is empty")
    return str(max(summary_rows, key=lambda row: int(float(row["n_cells"])))['case_id'])


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
    wall = sorted(
        (row for row in metadata.values() if row["phase"] == "wall_contact"),
        key=lambda row: float(row["path_travel_m"]),
    )
    reflected = sorted(
        (row for row in metadata.values() if row["phase"] == "reflected"),
        key=lambda row: float(row["path_travel_m"]),
    )
    if not incident or not wall or not reflected:
        raise ValueError(
            "V-013B matched samples must include incident, wall, and reflected phases"
        )
    selected = [incident[-1], wall[0], reflected[0], reflected[-1]]
    return list(dict.fromkeys(str(row["sample_id"]) for row in selected))


def _rows_for_sample(
    matched_rows: Sequence[Mapping[str, Any]],
    sample_id: str,
) -> list[Mapping[str, Any]]:
    rows = [row for row in matched_rows if str(row["sample_id"]) == sample_id]
    return sorted(rows, key=lambda row: float(row["x_m"]))


def _sample_label(rows: Sequence[Mapping[str, Any]]) -> str:
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
        raise ValueError(
            f"no {implementation} {key} values in V-013B comparison artifacts"
        )
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


def plot_v013_rigid_wall_results(
    output_dir: str | Path,
) -> dict[str, Any]:
    """Generate seven comparison figures without rerunning numerical solvers."""

    base = Path(output_dir)
    metrics_path = base / "v013b_metrics.json"
    metrics = _load_json(metrics_path)
    traceability = build_v013b_plot_traceability(metrics)
    summary = sorted(
        _read_csv(base / "v013b_summary.csv"),
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
                "comparison": _load_json(run_dir / "comparison_metrics.json"),
                "fvm": _load_json(run_dir / "fvm_metrics.json"),
            }
        )

    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except Exception as exc:  # pragma: no cover
        result = {
            "case_name": metrics["case_name"],
            "verification_item": "V-013B",
            "model": MODEL_DESCRIPTION,
            "property_backend_name": metrics["property_backend_name"],
            "coolprop_version": metrics["coolprop_version"],
            "output_version": metrics["output_version"],
            "plot_count": 0,
            "expected_plot_count": EXPECTED_PLOT_COUNT,
            "plot_files": [],
            "plotting_errors": {"matplotlib_import": str(exc)},
            "solver_rerun": False,
            "numerical_results_changed": False,
        }
        _write_json(base / "v013b_plot_metrics.json", result)
        return result

    generated: list[str] = []
    errors: dict[str, str] = {}

    def figure() -> Any:
        fig = Figure(figsize=(9.5, 5.8))
        FigureCanvasAgg(fig)
        return fig

    try:
        fig = figure()
        ax = fig.subplots()
        for sample_id in selected_sample_ids:
            rows = _rows_for_sample(matched, sample_id)
            label = _sample_label(rows)
            x = [row["x_m"] for row in rows]
            ax.plot(
                x,
                [row["fvm_pressure_perturbation_pa"] for row in rows],
                label=f"FVM {label}",
            )
            ax.plot(
                x,
                [row["moc_pressure_perturbation_pa"] for row in rows],
                linestyle=":",
                label=f"MOC {label}",
            )
            ax.plot(
                x,
                [row["analytical_pressure_perturbation_pa"] for row in rows],
                linestyle="--",
                label=f"analytical {label}",
            )
        ax.set_title(f"V-013B rigid-wall pressure profiles — {finest_case_id}")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("pressure perturbation [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=3)
        generated.append(
            _save(
                fig,
                base,
                "v013b_rigid_wall_pressure_profiles.png",
                traceability,
            )
        )
    except Exception as exc:
        errors["pressure_profiles"] = str(exc)

    try:
        fig = figure()
        ax = fig.subplots()
        for sample_id in selected_sample_ids:
            rows = _rows_for_sample(matched, sample_id)
            label = _sample_label(rows)
            x = [row["x_m"] for row in rows]
            ax.plot(
                x,
                [row["fvm_velocity_m_s"] for row in rows],
                label=f"FVM {label}",
            )
            ax.plot(
                x,
                [row["moc_velocity_m_s"] for row in rows],
                linestyle=":",
                label=f"MOC {label}",
            )
            ax.plot(
                x,
                [row["analytical_velocity_m_s"] for row in rows],
                linestyle="--",
                label=f"analytical {label}",
            )
        ax.axhline(0.0, linewidth=0.8)
        ax.set_title(f"V-013B rigid-wall velocity profiles — {finest_case_id}")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("velocity [m/s]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=3)
        generated.append(
            _save(
                fig,
                base,
                "v013b_rigid_wall_velocity_profiles.png",
                traceability,
            )
        )
    except Exception as exc:
        errors["velocity_profiles"] = str(exc)

    try:
        reflected_ids = [
            sample_id
            for sample_id in selected_sample_ids
            if _rows_for_sample(matched, sample_id)[0]["phase"] == "reflected"
        ]
        if not reflected_ids:
            raise ValueError("no reflected matched sample available")
        sample_id = reflected_ids[0]
        rows = _rows_for_sample(matched, sample_id)
        label = _sample_label(rows)
        x = [row["x_m"] for row in rows]
        fig = figure()
        ax = fig.subplots()
        for implementation, prefix, linestyle in (
            ("FVM", "fvm", "-"),
            ("MOC", "moc", ":"),
            ("analytical", "analytical", "--"),
        ):
            ax.plot(
                x,
                [row[f"{prefix}_a_plus_pa"] for row in rows],
                linestyle=linestyle,
                label=f"{implementation} A+",
            )
            ax.plot(
                x,
                [row[f"{prefix}_a_minus_pa"] for row in rows],
                linestyle=linestyle,
                label=f"{implementation} A-",
            )
        ax.set_title(f"V-013B characteristic profiles — {label}")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("pressure-dimension characteristic [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013b_rigid_wall_characteristics.png",
                traceability,
            )
        )
    except Exception as exc:
        errors["characteristics"] = str(exc)

    try:
        probe_ids = sorted(
            {str(row["probe_id"]) for row in probe_rows},
            key=lambda probe_id: max(
                float(row["probe_x_m"])
                for row in probe_rows
                if str(row["probe_id"]) == probe_id
            ),
        )
        selected_probe = probe_ids[-1]
        rows = sorted(
            (row for row in probe_rows if str(row["probe_id"]) == selected_probe),
            key=lambda row: float(row["time_s"]),
        )
        probe_metric = next(
            row
            for row in finest_comparison["probe_reflection_metrics"]
            if str(row["probe_id"]) == selected_probe
        )
        timing = probe_metric["timing"]
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
            linestyle=":",
            label="MOC",
        )
        ax.plot(
            [row["time_s"] for row in rows],
            [row["analytical_pressure_perturbation_pa"] for row in rows],
            linestyle="--",
            label="analytical",
        )
        for key, label, linestyle in (
            ("theoretical_incident_time_s", "incident centre", ":"),
            ("theoretical_boundary_time_s", "wall contact", "-."),
            ("theoretical_reflected_time_s", "reflected centre", "--"),
        ):
            ax.axvline(
                float(timing[key]),
                linestyle=linestyle,
                linewidth=0.9,
                alpha=0.7,
                label=label,
            )
        ax.set_title(f"V-013B probe pressure history — {selected_probe}")
        ax.set_xlabel("time [s]")
        ax.set_ylabel("pressure perturbation [Pa]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013b_rigid_wall_probe_history.png",
                traceability,
            )
        )
    except Exception as exc:
        errors["probe_history"] = str(exc)

    try:
        fig = figure()
        ax = fig.subplots()
        dx = [row["dx_m"] for row in run_data]
        for implementation, marker in (
            ("fvm", "o"),
            ("moc", "s"),
            ("analytical", "^"),
        ):
            pressure_coefficients = [
                _mean_probe_coefficient(
                    row["comparison"],
                    implementation,
                    "pressure_reflection_coefficient",
                )
                for row in run_data
            ]
            velocity_coefficients = [
                _mean_probe_coefficient(
                    row["comparison"],
                    implementation,
                    "velocity_reflection_coefficient",
                )
                for row in run_data
            ]
            ax.plot(
                dx,
                pressure_coefficients,
                marker=marker,
                label=f"{implementation} pressure",
            )
            ax.plot(
                dx,
                velocity_coefficients,
                marker=marker,
                linestyle="--",
                label=f"{implementation} velocity",
            )
        ax.axhline(1.0, linewidth=0.8, linestyle=":", label="ideal pressure +1")
        ax.axhline(-1.0, linewidth=0.8, linestyle="-.", label="ideal velocity -1")
        ax.set_title("V-013B reflection coefficients versus mesh spacing")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("reflection coefficient [-]")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013b_reflection_coefficients_vs_dx.png",
                traceability,
            )
        )
    except Exception as exc:
        errors["reflection_coefficients"] = str(exc)

    try:
        fig = figure()
        ax = fig.subplots()
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
                    _maximum_energy_difference(row["comparison"], implementation),
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
        ax.set_title("V-013B field and acoustic-energy differences")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("maximum normalized difference [-]")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend(fontsize=8, ncol=2)
        generated.append(
            _save(
                fig,
                base,
                "v013b_field_energy_error_vs_dx.png",
                traceability,
            )
        )
    except Exception as exc:
        errors["field_energy_error"] = str(exc)

    try:
        fig = figure()
        ax = fig.subplots()
        dx = [row["dx_m"] for row in run_data]
        amplitude = float(
            _load_json(base / "v013b_config.json")["pressure_amplitude_pa"]
        )
        floor = np.finfo(float).tiny
        velocity_residuals: list[float] = []
        pressure_errors: list[float] = []
        for row in run_data:
            fvm = row["fvm"]
            wall = fvm["boundary_metrics"]
            velocity_scale = amplitude / (
                float(fvm["rho0_kg_m3"]) * float(fvm["c0_m_s"])
            )
            velocity_residuals.append(
                max(
                    abs(float(wall["max_abs_wall_velocity_m_s"]))
                    / velocity_scale,
                    floor,
                )
            )
            pressure_errors.append(
                max(
                    abs(float(wall["wall_pressure_amplification_ratio"]) - 2.0),
                    floor,
                )
            )
        ax.plot(
            dx,
            velocity_residuals,
            marker="o",
            label="normalized wall velocity residual",
        )
        ax.plot(
            dx,
            pressure_errors,
            marker="s",
            label="|wall pressure ratio - 2|",
        )
        ax.set_yscale("log")
        ax.set_title("V-013B rigid-wall condition residuals")
        ax.set_xlabel("mesh spacing Δx [m]")
        ax.set_ylabel("normalized residual [-]")
        ax.grid(True, alpha=0.3, which="both")
        ax.legend(fontsize=8)
        generated.append(
            _save(
                fig,
                base,
                "v013b_wall_condition_vs_dx.png",
                traceability,
            )
        )
    except Exception as exc:
        errors["wall_condition"] = str(exc)

    result = {
        "case_name": metrics["case_name"],
        "verification_item": "V-013B",
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
    _write_json(base / "v013b_plot_metrics.json", result)

    metrics["generated_plots"] = generated
    metrics["plotting_errors"] = errors
    metrics["comparison_plots_complete"] = bool(
        len(generated) == EXPECTED_PLOT_COUNT and not errors
    )
    _write_json(metrics_path, metrics)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    result = plot_v013_rigid_wall_results(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["plot_count"] == result["expected_plot_count"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "EXPECTED_PLOT_COUNT",
    "MODEL_DESCRIPTION",
    "build_v013b_plot_traceability",
    "plot_v013_rigid_wall_results",
]
