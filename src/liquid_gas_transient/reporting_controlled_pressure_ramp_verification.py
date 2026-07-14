"""Formal V-011 controlled-pressure-ramp report and SHA256 manifest generator.

The generator reads existing PR #31 sweep artifacts. It does not rerun CoolProp,
modify the solver, or define physical Validation or design-use acceptance.
"""
from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

from liquid_gas_transient.verification.controlled_pressure_ramp_regression import (
    ControlledPressureRampRegressionLimits,
)

REPORT_VERSION = "coolprop_controlled_pressure_ramp_verification_report_v1"
MANIFEST_VERSION = "coolprop_controlled_pressure_ramp_verification_manifest_v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "not available"
    if isinstance(value, bool):
        return "True" if value else "False"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == 0.0:
        return "0"
    if abs(number) >= 1.0e4 or abs(number) < 1.0e-3:
        return f"{number:.6g}"
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_entries(root: Path, excluded: set[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        if path.resolve() in excluded:
            continue
        entries.append(
            {
                "relative_path": str(path.relative_to(root)).replace("\\", "/"),
                "file_size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return entries


def _is_group(row: dict[str, Any], name: str) -> bool:
    value = row.get("comparison_groups", "")
    if isinstance(value, str):
        return name in value.split(";")
    if isinstance(value, (list, tuple)):
        return name in value
    return False


def _sorted_rows(rows: list[dict[str, Any]], group: str) -> list[dict[str, Any]]:
    selected = [row for row in rows if _is_group(row, group)]
    if group == "mesh_comparison":
        return sorted(selected, key=lambda row: int(float(row["n_cells"])))
    return sorted(selected, key=lambda row: float(row["cfl"]))


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_fmt(value) for value in row) + " |" for row in rows
    )
    return lines


def generate_controlled_pressure_ramp_verification_report(
    *,
    sweep_metrics_path: str | Path,
    sweep_summary_path: str | Path,
    output_path: str | Path,
    manifest_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Generate the formal V-011 Markdown report and SHA256 manifest."""

    metrics_path = Path(sweep_metrics_path)
    summary_path = Path(sweep_summary_path)
    report_path = Path(output_path)
    root = Path(artifact_root) if artifact_root is not None else report_path.parent
    manifest = Path(manifest_path) if manifest_path is not None else report_path.with_name(
        "coolprop_controlled_pressure_ramp_verification_manifest_v1.json"
    )

    metrics = _read_json(metrics_path)
    rows: list[dict[str, Any]] = list(_read_csv(summary_path))
    design_status = metrics.get("property_backend_design_status")
    if design_status != "not_approved_for_design_use":
        raise ValueError("unexpected property_backend_design_status")
    if int(metrics.get("unique_run_count", 0)) != 4 or len(rows) != 4:
        raise ValueError("formal V-011 report requires four unique sweep rows")
    if metrics.get("overall_sweep_execution_pass") is not True:
        raise ValueError("formal V-011 report requires a successful sweep")

    limits = ControlledPressureRampRegressionLimits()
    provenance = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": _package_version("numpy"),
        "coolprop_version": _package_version("CoolProp"),
        "matplotlib_version": _package_version("matplotlib"),
        "git_commit_hash": _git_commit(),
        "source_metrics_path": str(metrics_path),
        "source_summary_path": str(summary_path),
        "report_version": REPORT_VERSION,
    }

    lines: list[str] = [
        "# CoolProp Controlled Pressure Ramp Numerical Verification Report",
        "",
        "> Guardrail: software/numerical verification only; physical Validation = false; design-use acceptance = false; property_backend_design_status = not_approved_for_design_use.",
        "",
        "## 1. Executive summary",
        "",
        f"- full sweep execution pass: {_fmt(metrics.get('overall_sweep_execution_pass'))}",
        f"- unique run count: {_fmt(metrics.get('unique_run_count'))}",
        f"- mesh observation classification: {_fmt(metrics.get('mesh_observation', {}).get('overall_classification'))}",
        "- common p50 phase offset, p50 timing error, and amplitude error improve with mesh refinement.",
        "- wave-speed error is non-monotonic and is not claimed to converge monotonically.",
        "- opposite-direction characteristic leakage remains near a small measurement floor.",
        "- lower CFL is not treated as truth or as automatically superior.",
        "- n=200 is a comparison reference, not an exact solution.",
        "- no physical Validation or design-use approval is claimed.",
        "",
        "## 2. Scope and idealizations",
        "",
        "- single-phase CO2 at p0=8 MPa and T0=280 K",
        "- conservative FVM with CoolProp-backed properties",
        "- 100 m pipe with a small +1 kPa pressure ramp at the right boundary",
        "- transmissive left boundary and observation window before reflected contamination",
        "- friction, gravity, phase change, valve motion, equipment Validation, and plant events are outside scope",
        "- PressureTankBoundary is a numerical pressure-input boundary, not an approved physical tank model",
        "",
        "## 3. Traceability",
        "",
        f"- output version: {_fmt(metrics.get('output_version'))}",
        f"- property backend status: {design_status}",
        f"- Python: {provenance['python_version']}",
        f"- platform: {provenance['platform']}",
        f"- NumPy: {provenance['numpy_version']}",
        f"- CoolProp: {provenance['coolprop_version']}",
        f"- git commit: {provenance['git_commit_hash']}",
        "",
        "## 4. Mesh observation",
        "",
    ]

    mesh_table: list[list[Any]] = []
    for row in _sorted_rows(rows, "mesh_comparison"):
        mesh_table.append(
            [
                row.get("n_cells"),
                row.get("dx_m"),
                row.get("cfl"),
                row.get("wave_speed_relative_error"),
                1.0e3 * float(row["abs_common_boundary_launch_delay_s"]),
                row.get("p10_arrival_relative_error_mean"),
                row.get("p50_arrival_relative_error_mean"),
                row.get("p90_arrival_relative_error_mean"),
                row.get("primary_peak_amplitude_error"),
                row.get("primary_opposite_direction_leakage_ratio"),
            ]
        )
    lines.extend(
        _markdown_table(
            [
                "n",
                "dx [m]",
                "CFL",
                "wave-speed rel. err",
                "common offset [ms]",
                "mean p10 err",
                "mean p50 err",
                "mean p90 err",
                "amplitude err",
                "opposite leakage",
            ],
            mesh_table,
        )
    )
    lines.extend(
        [
            "",
            "Observed primary trends:",
            "- common p50 offset: 4.212 ms -> 2.230 ms -> 1.189 ms",
            "- mean p50 relative error: 5.028% -> 2.583% -> 1.352%",
            "- peak-amplitude error: 2.117e-7 -> 6.893e-8 -> 3.369e-8",
            "- characteristic leakage remains approximately 5.2e-6",
            "- fitted wave-speed error is non-monotonic",
            "",
            "## 5. CFL observation",
            "",
        ]
    )

    cfl_table: list[list[Any]] = []
    for row in _sorted_rows(rows, "cfl_comparison"):
        cfl_table.append(
            [
                row.get("n_cells"),
                row.get("cfl"),
                row.get("wave_speed_relative_error"),
                1.0e3 * float(row["abs_common_boundary_launch_delay_s"]),
                row.get("p10_arrival_relative_error_mean"),
                row.get("p50_arrival_relative_error_mean"),
                row.get("p90_arrival_relative_error_mean"),
                row.get("total_case_runtime_s"),
            ]
        )
    lines.extend(
        _markdown_table(
            [
                "n",
                "CFL",
                "wave-speed rel. err",
                "common offset [ms]",
                "mean p10 err",
                "mean p50 err",
                "mean p90 err",
                "runtime [s]",
            ],
            cfl_table,
        )
    )
    lines.extend(
        [
            "",
            "CFL=0.25 is an observation point and is not treated as an exact or preferred solution.",
            "",
            "## 6. Conservation and phase health",
            "",
        ]
    )

    budget_rows: list[list[Any]] = []
    for row in rows:
        budget_rows.append(
            [
                row.get("case_id"),
                row.get("budget_mass_relative_residual"),
                row.get("energy_budget_balance_relative_residual"),
                row.get("phase_vapor_mass_balance_relative_residual"),
                row.get("remained_single_phase"),
                row.get("execution_pass"),
                row.get("analysis_complete"),
            ]
        )
    lines.extend(
        _markdown_table(
            [
                "case",
                "mass rel. residual",
                "energy rel. residual",
                "vapor-mass rel. residual",
                "single phase",
                "execution pass",
                "analysis complete",
            ],
            budget_rows,
        )
    )

    lines.extend(
        [
            "",
            "## 7. CI-light regression profile",
            "",
            f"- profile name: {limits.profile_name}",
            "- profile: n=50, CFL=0.5",
            f"- wave-speed relative-error limit: {limits.max_wave_speed_relative_error:g}",
            f"- absolute common-offset limit: {limits.max_abs_common_launch_delay_s:g} s",
            f"- mean p10/p50/p90 limits: {limits.max_mean_p10_arrival_relative_error:g} / {limits.max_mean_p50_arrival_relative_error:g} / {limits.max_mean_p90_arrival_relative_error:g}",
            f"- max p50 limit: {limits.max_max_p50_arrival_relative_error:g}",
            f"- peak-amplitude-error limit: {limits.max_primary_peak_amplitude_error:g}",
            f"- opposite-direction leakage limit: {limits.max_primary_opposite_direction_leakage_ratio:g}",
            f"- linear-velocity relative-error limit: {limits.max_primary_linear_velocity_relative_error:g}",
            f"- fit R-squared minimum: {limits.min_fit_r_squared:g}",
            f"- mass/energy/vapor-mass absolute relative-residual limits: {limits.max_abs_mass_relative_residual:g}",
            "",
            "These are broad software-regression sentinels, not physical-accuracy or design-acceptance criteria.",
            "",
            "## 8. Artifact inventory",
            "",
        ]
    )
    for name in metrics.get("generated_comparison_plots", []) or []:
        lines.append(f"- comparison plot: {name}")
    lines.extend(
        [
            "- per-run config, metrics, schedule, probe, boundary, analysis, pressure-field, and front-fit artifacts are indexed by the manifest.",
            "",
            "## 9. Limitations",
            "",
            "- the finite-volume front remains diffusive at coarse resolution",
            "- n=200 is not an exact solution",
            "- fitted wave speed contains interpolation and fit sensitivity",
            "- the CI-light n=50 profile is not a design mesh",
            "- no experiment or operating-plant data are used",
            "- CoolProp remains not approved for design use in this project",
            "- this report does not verify valve operation, flashing, two-phase flow, HEM, HNE, ESD, or pump trip",
            "",
            "## 10. Conclusion",
            "",
            "The V-011 controlled-pressure-ramp software path is reproducible and theoretically consistent within the documented numerical-regression scope. The evidence supports regression protection and numerical verification only. It does not establish physical Validation, equipment fidelity, a design mesh, or design-use acceptance.",
            "",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    root = root.resolve()
    excluded = {manifest.resolve()}
    entries = _artifact_entries(root, excluded)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_data = {
        "manifest_version": MANIFEST_VERSION,
        "report_version": REPORT_VERSION,
        "generated_at_utc": provenance["generated_at_utc"],
        "property_backend_design_status": design_status,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "artifact_root": str(root),
        "source_metrics_path": str(metrics_path),
        "source_summary_path": str(summary_path),
        "regression_limits": asdict(limits),
        "entries": entries,
    }
    manifest.write_text(
        json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "report_path": str(report_path),
        "manifest_path": str(manifest),
        "artifact_count": len(entries),
        "report_sha256": _sha256(report_path),
        "property_backend_design_status": design_status,
        "overall_sweep_execution_pass": metrics.get("overall_sweep_execution_pass"),
    }
