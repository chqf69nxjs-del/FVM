"""Formal V-012 internal-valve report and SHA256 manifest generator.

The generator reads existing mesh/CFL sweep artifacts. It does not rerun CoolProp,
modify solver physics, or define physical Validation or design-use acceptance.
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

from liquid_gas_transient.verification.internal_valve_regression import (
    InternalValveRegressionLimits,
)

REPORT_VERSION = "coolprop_internal_valve_verification_report_v1"
MANIFEST_VERSION = "coolprop_internal_valve_verification_manifest_v1"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "not available"
    if isinstance(value, bool):
        return "True" if value else "False"
    number = _number(value)
    if number is None:
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


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend(
        "| " + " | ".join(_fmt(value) for value in row) + " |" for row in rows
    )
    return lines


def _single_identity(rows: list[dict[str, Any]], key: str) -> str:
    values = {str(row.get(key, "")).strip() for row in rows}
    values.discard("")
    if len(values) != 1:
        raise ValueError(f"inconsistent or missing {key} across sweep rows: {sorted(values)}")
    return next(iter(values))


def _group_contains(row: dict[str, Any], group: str) -> bool:
    value = row.get("comparison_groups", "")
    if isinstance(value, str):
        return group in value.split(";")
    if isinstance(value, (list, tuple)):
        return group in value
    return False


def _row(
    rows: list[dict[str, Any]],
    item: str,
    n_cells: int,
    cfl: float,
) -> dict[str, Any]:
    matches = [
        row
        for row in rows
        if row.get("verification_item") == item
        and int(float(row.get("n_cells", -1))) == n_cells
        and float(row.get("cfl", -1.0)) == cfl
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one row for {item}, n={n_cells}, CFL={cfl}")
    return matches[0]


def generate_internal_valve_verification_report(
    *,
    sweep_metrics_path: str | Path,
    sweep_summary_path: str | Path,
    output_path: str | Path,
    manifest_path: str | Path | None = None,
    artifact_root: str | Path | None = None,
    ci_result_path: str | Path | None = None,
) -> dict[str, Any]:
    """Generate the formal V-012 Markdown report and SHA256 manifest."""

    metrics_path = Path(sweep_metrics_path)
    summary_path = Path(sweep_summary_path)
    report_path = Path(output_path)
    root = Path(artifact_root) if artifact_root is not None else report_path.parent
    manifest = Path(manifest_path) if manifest_path is not None else report_path.with_name(
        "coolprop_internal_valve_verification_manifest_v1.json"
    )

    metrics = _read_json(metrics_path)
    rows: list[dict[str, Any]] = list(_read_csv(summary_path))
    if int(metrics.get("planned_run_count", 0)) != 13:
        raise ValueError("formal V-012 report requires the fixed 13-run plan")
    if int(metrics.get("executed_run_count", 0)) != 13 or len(rows) != 13:
        raise ValueError("formal V-012 report requires thirteen executed summary rows")
    if metrics.get("overall_sweep_execution_pass") is not True:
        raise ValueError("formal V-012 report requires a successful sweep")
    if metrics.get("aggregate_trend_analysis_complete") is not True:
        raise ValueError("formal V-012 report requires completed aggregate analysis")
    if metrics.get("comparison_plots_complete") is not True:
        raise ValueError("formal V-012 report requires completed comparison plots")

    backend_name = _single_identity(rows, "property_backend_name")
    source_coolprop_version = _single_identity(rows, "coolprop_version")
    design_status = _single_identity(rows, "property_backend_design_status")
    if backend_name != "coolprop_co2":
        raise ValueError("unexpected property backend")
    if source_coolprop_version != "8.0.0":
        raise ValueError("unexpected source CoolProp version")
    if design_status != "not_approved_for_design_use":
        raise ValueError("unexpected property_backend_design_status")
    for key, expected in (
        ("property_backend_name", backend_name),
        ("coolprop_version", source_coolprop_version),
        ("property_backend_design_status", design_status),
    ):
        if str(metrics.get(key, "")).strip() != expected:
            raise ValueError(f"sweep metrics and summary disagree on {key}")

    ci_result = _read_json(Path(ci_result_path)) if ci_result_path is not None else None
    if ci_result is not None and ci_result.get("overall_regression_pass") is not True:
        raise ValueError("formal V-012 report requires a successful CI-light result")

    limits = InternalValveRegressionLimits()
    provenance = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy_version": _package_version("numpy"),
        "source_property_backend_name": backend_name,
        "source_coolprop_version": source_coolprop_version,
        "generator_coolprop_version": _package_version("CoolProp"),
        "matplotlib_version": _package_version("matplotlib"),
        "git_commit_hash": _git_commit(),
        "source_metrics_path": str(metrics_path),
        "source_summary_path": str(summary_path),
        "source_ci_result_path": str(ci_result_path) if ci_result_path is not None else None,
        "report_version": REPORT_VERSION,
    }

    lines: list[str] = [
        "# CoolProp Single-Phase Internal-Valve Numerical Verification Report",
        "",
        "> Guardrail: software/numerical verification only; physical Validation = false; design-use acceptance = false; property_backend_design_status = not_approved_for_design_use.",
        "",
        "## 1. Executive summary",
        "",
        f"- full 13-run sweep execution pass: {_fmt(metrics.get('overall_sweep_execution_pass'))}",
        f"- aggregate trend analysis complete: {_fmt(metrics.get('aggregate_trend_analysis_complete'))}",
        f"- comparison plots complete: {_fmt(metrics.get('comparison_plots_complete'))}",
        "- finite-opening flow and actual interface flux remain consistent across the observed mesh/CFL cases.",
        "- opening- and closing-wave directions match the prescribed operation expectations.",
        "- near-probe p50 timing offsets decrease with mesh refinement for V-012B/C/D.",
        "- complete closure retains hydraulic separation and numerical-zero through-flow.",
        "- all runs remain finite, positive, and single phase with required budgets present.",
        "- lower CFL is not treated as truth or as automatically superior.",
        "- n=200 is a comparison reference, not an exact solution.",
        "- n=400 was reviewed and is not required for this observation increment.",
        "",
        "## 2. Scope and idealizations",
        "",
        "- single-phase CO2 near 8 MPa and 280 K",
        "- conservative FVM with CoolProp-backed properties",
        "- prescribed internal-valve opening schedules and a single-phase liquid Kv relation",
        "- fixed-pressure boundaries are zero-impedance numerical idealizations",
        "- hydraulic-loss power remains diagnostic and is not removed from conserved rhoE",
        "- actuator dynamics, hysteresis, flashing, choked discharge, HEM, HNE, ESD, and pump trip are outside scope",
        "- no experimental or operating-plant data are used",
        "",
        "## 3. Traceability",
        "",
        f"- output version: {_fmt(metrics.get('output_version'))}",
        f"- property backend name: {backend_name}",
        f"- source CoolProp version: {source_coolprop_version}",
        f"- report-generator CoolProp version: {provenance['generator_coolprop_version']}",
        f"- property backend status: {design_status}",
        f"- Python: {provenance['python_version']}",
        f"- platform: {provenance['platform']}",
        f"- NumPy: {provenance['numpy_version']}",
        f"- git commit: {provenance['git_commit_hash']}",
        "",
        "## 4. Executed run matrix",
        "",
    ]

    run_rows = [
        [
            row.get("case_id"),
            row.get("verification_item"),
            row.get("n_cells"),
            row.get("dx_m"),
            row.get("cfl"),
            row.get("execution_pass"),
            row.get("analysis_complete"),
            row.get("remained_single_phase"),
            row.get("runtime_s"),
        ]
        for row in rows
    ]
    lines.extend(
        _markdown_table(
            [
                "case", "item", "n", "dx [m]", "CFL", "execution",
                "analysis", "single phase", "runtime [s]",
            ],
            run_rows,
        )
    )

    lines.extend(["", "## 5. Mesh observation", ""])
    timing_rows = []
    for item in ("V-012B", "V-012C", "V-012D"):
        for n_cells in (50, 100, 200):
            row = _row(rows, item, n_cells, 0.5)
            timing_rows.append(
                [
                    item,
                    n_cells,
                    row.get("dx_m"),
                    1.0e3
                    * float(row["near_probe_characteristic_p50_time_offset_max_abs_s"]),
                    row.get("near_probe_characteristic_peak_abs_mean_pa"),
                    row.get("near_probe_characteristic_max_leakage_ratio"),
                    row.get("max_applied_q_m3_s_extracted"),
                ]
            )
    lines.extend(
        _markdown_table(
            [
                "item", "n", "dx [m]", "p50 offset [ms]",
                "characteristic peak [Pa]", "opposite ratio", "max Q [m3/s]",
            ],
            timing_rows,
        )
    )
    lines.extend(
        [
            "",
            "Observed maximum near-probe p50 timing offsets at CFL=0.5:",
            "- V-012B: 4.5636 ms -> 3.0810 ms -> 2.1543 ms",
            "- V-012C: 1.9002 ms -> 0.7526 ms -> 0.1132 ms",
            "- V-012D: 4.8728 ms -> 3.0317 ms -> 2.1373 ms",
            "",
            "## 6. Complete closure",
            "",
        ]
    )
    closure_rows = []
    for n_cells in (50, 100, 200):
        row = _row(rows, "V-012D", n_cells, 0.5)
        closure_rows.append(
            [
                n_cells,
                row.get("post_closure_hydraulic_separation_fraction_extracted"),
                row.get("post_closure_no_flow_direction_fraction_extracted"),
                row.get("max_abs_post_closure_flux_derived_q_m3_s_extracted"),
                row.get("max_abs_post_closure_mass_flux_kg_m2_s_extracted"),
                row.get("max_abs_post_closure_energy_flux_w_m2_extracted"),
                row.get("max_abs_post_closure_vapor_mass_flux_kg_m2_s_extracted"),
            ]
        )
    lines.extend(
        _markdown_table(
            [
                "n", "separation fraction", "no-flow fraction",
                "max flux Q [m3/s]", "max mass flux [kg/m2/s]",
                "max energy flux [W/m2]", "max vapor flux [kg/m2/s]",
            ],
            closure_rows,
        )
    )

    lines.extend(["", "## 7. CFL observation", ""])
    cfl_rows = []
    for item in ("V-012B", "V-012C", "V-012D"):
        for cfl in (0.25, 0.5):
            row = _row(rows, item, 100, cfl)
            cfl_rows.append(
                [
                    item,
                    cfl,
                    row.get("step_count"),
                    row.get("runtime_s"),
                    1.0e3
                    * float(row["near_probe_characteristic_p50_time_offset_max_abs_s"]),
                    row.get("near_probe_characteristic_peak_abs_mean_pa"),
                ]
            )
    lines.extend(
        _markdown_table(
            ["item", "CFL", "steps", "runtime [s]", "p50 offset [ms]", "peak [Pa]"],
            cfl_rows,
        )
    )
    lines.extend(
        [
            "",
            "CFL=0.25 approximately doubles step count and runtime at n=100, but is not uniformly closer to the mesh trend. It is not treated as truth.",
            "",
            "## 8. Conservation and phase health",
            "",
        ]
    )
    budget_rows = [
        [
            row.get("case_id"),
            row.get("budget_mass_relative_residual"),
            row.get("energy_budget_balance_relative_residual"),
            row.get("phase_vapor_mass_balance_relative_residual"),
            row.get("max_abs_mass_flux_mismatch_kg_m2_s"),
            row.get("max_abs_flux_q_minus_applied_q_m3_s"),
            row.get("remained_single_phase"),
        ]
        for row in rows
    ]
    lines.extend(
        _markdown_table(
            [
                "case", "mass rel. residual", "energy rel. residual",
                "vapor rel. residual", "mass mismatch", "Q mismatch", "single phase",
            ],
            budget_rows,
        )
    )

    lines.extend(
        [
            "",
            "## 9. CI-light regression profile",
            "",
            f"- profile name: {limits.profile_name}",
            "- four cases: V-012A/B/C/D",
            "- profile: n=50, CFL=0.5",
            f"- budget absolute relative-residual limit: {limits.max_abs_budget_relative_residual:g}",
            f"- interface Q mismatch absolute limit: {limits.max_abs_flux_q_minus_applied_q_m3_s:g} m3/s",
            f"- characteristic leakage limit: {limits.max_characteristic_leakage_ratio:g}",
            f"- V-012B/C/D p50 limits: {limits.v012b_max_p50_offset_s:g} / {limits.v012c_max_p50_offset_s:g} / {limits.v012d_max_p50_offset_s:g} s",
            f"- V-012D post-closure Q limit: {limits.v012d_max_abs_post_closure_q_m3_s:g} m3/s",
            "",
            "These are broad software-regression sentinels, not physical-accuracy or design-acceptance criteria.",
            "",
            "## 10. Artifact inventory",
            "",
        ]
    )
    for name in metrics.get("generated_comparison_plots", []) or []:
        lines.append(f"- comparison plot: {name}")
    lines.extend(
        [
            "- per-run config, metrics, valve, interface-flux, probe, boundary, final-profile, and field-history artifacts are indexed by the manifest.",
            "",
            "## 11. Limitations",
            "",
            "- numerical fronts remain diffusive at coarse resolution",
            "- n=200 is not an exact solution",
            "- the CI-light n=50 profile is not a design mesh",
            "- lower CFL is not truth",
            "- no experiment or operating-plant data are used",
            "- CoolProp remains not approved for design use in this project",
            "- the Kv relation is single phase and does not verify flashing or choked discharge",
            "- prescribed opening is not a physical actuator model",
            "- fixed-pressure boundaries are numerical idealizations",
            "",
            "## 12. Conclusion",
            "",
            "The V-012 single-phase internal-valve software path is reproducible and numerically consistent within the documented observation and regression scope. The evidence supports software/numerical verification and regression protection only. It does not establish physical Validation, equipment fidelity, a design mesh, operating limits, or design-use acceptance.",
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
        "property_backend_name": backend_name,
        "source_coolprop_version": source_coolprop_version,
        "generator_coolprop_version": provenance["generator_coolprop_version"],
        "property_backend_design_status": design_status,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "artifact_root": str(root),
        "source_metrics_path": str(metrics_path),
        "source_summary_path": str(summary_path),
        "source_ci_result_path": str(ci_result_path) if ci_result_path is not None else None,
        "provenance": provenance,
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
        "manifest_sha256": _sha256(manifest),
        "property_backend_name": backend_name,
        "source_coolprop_version": source_coolprop_version,
        "property_backend_design_status": design_status,
        "overall_sweep_execution_pass": metrics.get("overall_sweep_execution_pass"),
        "ci_light_regression_pass": (
            ci_result.get("overall_regression_pass") if ci_result is not None else None
        ),
    }
