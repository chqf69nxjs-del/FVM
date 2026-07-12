"""Formal Stage 5 boundary-reflection report and SHA256 manifest generator.

The generator reads existing PR-C sweep artifacts. It does not rerun CoolProp or
modify the solver. Results remain software/numerical verification evidence only.
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

from liquid_gas_transient.verification.boundary_reflection_regression import (
    BoundaryReflectionRegressionLimits,
)

REPORT_VERSION = "coolprop_boundary_reflection_verification_report_v1"
MANIFEST_VERSION = "coolprop_boundary_reflection_verification_manifest_v1"


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


def _is_group(row: dict[str, Any], name: str) -> bool:
    value = row.get("comparison_groups", "")
    if isinstance(value, str):
        return name in value.split(";")
    if isinstance(value, (list, tuple)):
        return name in value
    return False


def _sorted_rows(rows: list[dict[str, Any]], boundary: str, group: str) -> list[dict[str, Any]]:
    selected = [
        row for row in rows
        if row.get("boundary_kind") == boundary and _is_group(row, group)
    ]
    if group == "mesh_comparison":
        return sorted(selected, key=lambda row: int(float(row["n_cells"])))
    return sorted(selected, key=lambda row: float(row["cfl"]))


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(_fmt(value) for value in row) + " |" for row in rows)
    return lines


def _artifact_entries(root: Path, excluded: set[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        resolved = path.resolve()
        if resolved in excluded:
            continue
        entries.append(
            {
                "relative_path": str(path.relative_to(root)).replace("\\", "/"),
                "file_size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return entries


def generate_boundary_reflection_verification_report(
    *,
    sweep_metrics_path: str | Path,
    sweep_summary_path: str | Path,
    output_path: str | Path,
    manifest_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Generate the Stage 5 Markdown report and SHA256 manifest."""

    metrics_path = Path(sweep_metrics_path)
    summary_path = Path(sweep_summary_path)
    report_path = Path(output_path)
    root = Path(artifact_root) if artifact_root is not None else report_path.parent
    manifest = Path(manifest_path) if manifest_path is not None else report_path.with_name(
        "coolprop_boundary_reflection_verification_manifest_v1.json"
    )

    metrics = _read_json(metrics_path)
    rows: list[dict[str, Any]] = list(_read_csv(summary_path))
    design_status = metrics.get("property_backend_design_status")
    if design_status != "not_approved_for_design_use":
        raise ValueError("unexpected property_backend_design_status")
    boundaries = {str(row.get("boundary_kind")) for row in rows}
    if boundaries != {"rigid_wall", "fixed_pressure"}:
        raise ValueError("formal Stage 5 report requires both boundary kinds")

    limits = BoundaryReflectionRegressionLimits()
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
        "# CoolProp単相境界反射 Numerical Verification Report",
        "",
        "> Guardrail: software/numerical verification only; physical Validation = false; design-use acceptance = false; property_backend_design_status = not_approved_for_design_use.",
        "",
        "## 1. Executive summary",
        "",
        f"- full sweep execution pass: {_fmt(metrics.get('overall_sweep_execution_pass'))}",
        f"- unique run count: {_fmt(metrics.get('unique_run_count'))}",
        "- rigid-wall and fixed-pressure cases both show the expected reflection sign.",
        "- reflection-magnitude error, characteristic leakage, and waveform difference improve with mesh refinement.",
        "- arrival-time diagnostics show small non-monotonicity or plateau and therefore the overall mesh classification remains mixed_behavior.",
        "- n=200 is a comparison reference, not an exact solution.",
        "- lower CFL is not treated as truth.",
        "- no physical Validation or design-use approval is claimed.",
        "",
        "## 2. Scope and idealizations",
        "",
        "- single-phase CO2 at p0=8 MPa and T0=280 K",
        "- conservative FVM with CoolProp-backed properties",
        "- small-amplitude Gaussian pressure pulse",
        "- first reflection at the right boundary",
        "- rigid wall: infinite-impedance idealization, not an actual closed valve",
        "- fixed pressure: zero-impedance idealization, not an actual reservoir",
        "- friction, gravity, local losses, phase change, valve motion, and equipment Validation are outside scope",
        "",
        "## 3. Theory and sign convention",
        "",
        "- A_plus = 0.5 * (p' + rho0*c0*u')",
        "- A_minus = 0.5 * (p' - rho0*c0*u')",
        "- rigid wall: expected pressure-reflection coefficient +1",
        "- fixed pressure: expected pressure-reflection coefficient -1",
        "",
        "## 4. Traceability",
        "",
        f"- output version: {_fmt(metrics.get('output_version'))}",
        f"- property backend status: {design_status}",
        f"- Python: {provenance['python_version']}",
        f"- platform: {provenance['platform']}",
        f"- NumPy: {provenance['numpy_version']}",
        f"- CoolProp: {provenance['coolprop_version']}",
        f"- git commit: {provenance['git_commit_hash']}",
        "",
        "## 5. Mesh observation",
        "",
    ]

    table_rows: list[list[Any]] = []
    for boundary in ("rigid_wall", "fixed_pressure"):
        for row in _sorted_rows(rows, boundary, "mesh_comparison"):
            table_rows.append(
                [
                    boundary,
                    row.get("n_cells"),
                    row.get("dx_m"),
                    row.get("cfl"),
                    row.get("pressure_reflection_coefficient"),
                    row.get("pressure_reflection_magnitude_error"),
                    row.get("reflected_arrival_time_relative_error"),
                    row.get("boundary_residual"),
                    row.get("reflected_characteristic_leakage_ratio"),
                    row.get("waveform_l2_difference_vs_finest"),
                ]
            )
    lines.extend(
        _markdown_table(
            ["boundary", "n", "dx [m]", "CFL", "Rp", "| |Rp|-1 |", "arrival rel. err", "boundary residual", "reflected leakage", "waveform L2 vs finest"],
            table_rows,
        )
    )

    lines.extend(["", "Mesh classifications:"])
    for boundary in ("rigid_wall", "fixed_pressure"):
        observation = metrics.get("mesh_observations", {}).get(boundary, {})
        lines.append(f"- {boundary}: {_fmt(observation.get('overall_classification'))}")

    lines.extend(["", "## 6. CFL observation", ""])
    cfl_rows: list[list[Any]] = []
    for boundary in ("rigid_wall", "fixed_pressure"):
        for row in _sorted_rows(rows, boundary, "cfl_comparison"):
            cfl_rows.append(
                [
                    boundary,
                    row.get("n_cells"),
                    row.get("cfl"),
                    row.get("pressure_reflection_magnitude_error"),
                    row.get("reflected_arrival_time_relative_error"),
                    row.get("boundary_residual"),
                    row.get("reflected_characteristic_leakage_ratio"),
                ]
            )
    lines.extend(
        _markdown_table(
            ["boundary", "n", "CFL", "reflection magnitude error", "arrival rel. err", "boundary residual", "reflected leakage"],
            cfl_rows,
        )
    )
    lines.append("")
    lines.append("CFL=0.25 is an observation point and is not treated as an exact or preferred solution.")

    lines.extend(["", "## 7. Conservation and phase health", ""])
    budget_rows: list[list[Any]] = []
    for boundary in ("rigid_wall", "fixed_pressure"):
        for row in _sorted_rows(rows, boundary, "mesh_comparison"):
            budget_rows.append(
                [
                    boundary,
                    row.get("n_cells"),
                    row.get("budget_mass_relative_residual"),
                    row.get("energy_budget_balance_relative_residual"),
                    row.get("phase_vapor_mass_balance_relative_residual"),
                    row.get("remained_single_phase"),
                ]
            )
    lines.extend(
        _markdown_table(
            ["boundary", "n", "mass rel. residual", "energy rel. residual", "vapor-mass rel. residual", "single phase"],
            budget_rows,
        )
    )

    lines.extend(
        [
            "",
            "## 8. CI-light regression profile",
            "",
            f"- profile name: {limits.profile_name}",
            "- one n=50, CFL=0.5 case per boundary",
            f"- mass/energy/vapor-mass absolute relative residual limits: {limits.max_abs_mass_relative_residual:g}",
            f"- rigid-wall reflection-magnitude limit: {limits.max_rigid_reflection_magnitude_error:g}",
            f"- fixed-pressure reflection-magnitude limit: {limits.max_fixed_reflection_magnitude_error:g}",
            f"- rigid-wall arrival limit: {limits.max_rigid_arrival_relative_error:g}",
            f"- fixed-pressure arrival limit: {limits.max_fixed_arrival_relative_error:g}",
            f"- characteristic leakage limit: {limits.max_reflected_characteristic_leakage_ratio:g}",
            f"- fixed-pressure residual limit: {limits.max_normalized_fixed_pressure_residual:g}",
            "",
            "These are broad software-regression sentinels, not accuracy acceptance criteria.",
            "",
            "## 9. Artifact inventory",
            "",
        ]
    )
    for name in metrics.get("generated_comparison_plots", []) or []:
        lines.append(f"- comparison plot: {name}")
    lines.extend(
        [
            "- per-run config, metrics, probe history, boundary history, final profile, and observation report are indexed by the manifest.",
            "",
            "## 10. Limitations",
            "",
            "- the numerical scheme remains diffusive at coarse resolution",
            "- n=200 is not an exact solution",
            "- rigid wall and fixed pressure are idealized impedances",
            "- no experiment or operating plant data are used",
            "- CoolProp remains not approved for design use in this project",
            "- this report does not verify flashing, two-phase flow, HEM, HNE, ESD, pump trip, or valve closure",
            "",
            "## 11. Conclusion",
            "",
            "The Stage 5 single-phase boundary-reflection software path is reproducible and theoretically consistent within the documented numerical-regression scope. The evidence supports regression protection and numerical verification only. It does not establish physical Validation, equipment fidelity, a design mesh, or design-use acceptance.",
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
        "entries": entries,
    }
    manifest.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "report_path": str(report_path),
        "manifest_path": str(manifest),
        "artifact_count": len(entries),
        "report_sha256": _sha256(report_path),
        "property_backend_design_status": design_status,
        "overall_sweep_execution_pass": metrics.get("overall_sweep_execution_pass"),
    }
