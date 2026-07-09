"""Project reference acceptance gate for Ver.0.5.4.

Ver.0.5.3 can ingest a project reference table and compare it with a selected
property backend.  Ver.0.5.4 adds the explicit decision gate that engineering
workflows need before a property table is allowed to support design evaluation.

The gate deliberately separates three outcomes:

* ACCEPTED_FOR_DESIGN_USE: all numerical checks pass and the manifest is marked
  as design-approved.
* REHEARSAL_PASS_NOT_DESIGN_REFERENCE: the mechanics pass but the manifest is
  not approved for design use.  This is the expected default for the surrogate
  demonstration table.
* REJECTED: schema, validation, comparison, mode coverage, quantity coverage,
  or approval requirements failed.

This module does not certify a source by itself.  It records the project decision
logic so that real CoolProp/REFPROP/NIST/vendor reference data can be admitted
or rejected in an auditable way.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping, Sequence
import csv
import json
import math

from .project_reference import (
    ProjectReferenceIngestionConfig,
    ProjectReferenceManifest,
    build_surrogate_project_reference_demo_rows,
    generate_project_reference_ingestion_artifacts,
    ingest_project_reference_rows,
)
from .external_reference import ExternalReferenceComparisonConfig


DECISION_COLUMNS: tuple[str, ...] = (
    "check_id",
    "category",
    "required",
    "pass",
    "observed",
    "criterion",
    "message",
)


@dataclass(frozen=True)
class ReferenceAcceptanceGateConfig:
    """Acceptance rules for project-approved LCO2 reference data."""

    version: str = "0.5.4"
    # Default is a safe rehearsal mode: the gate passes its mechanics but does
    # not allow design acceptance unless the manifest explicitly approves it.
    require_design_approved_reference: bool = False
    require_manifest_design_approved_for_design_acceptance: bool = True
    allowed_fluids: tuple[str, ...] = ("CO2", "LCO2", "R744")
    required_modes: tuple[str, ...] = ("saturation", "density_pt", "mixture_rhoe")
    required_quantities: tuple[str, ...] = (
        "T_sat_K",
        "rho_l_kg_m3",
        "rho_v_kg_m3",
        "h_lv_j_kg",
        "rho_kg_m3",
        "p_pa",
        "T_K",
        "quality",
        "alpha",
        "c_m_s",
    )
    min_canonical_rows: int = 12
    min_comparable_quantities: int = 24
    max_validation_errors: int = 0
    max_failed_comparisons: int = 0
    # Optional global sanity limits applied to summarized comparison errors.
    max_temperature_abs_error_K: float = 0.25
    max_density_rel_error: float = 0.01
    max_pressure_rel_error: float = 0.005
    max_energy_rel_error: float = 0.02
    max_quality_abs_error: float = 0.01
    max_alpha_abs_error: float = 0.02
    max_sound_speed_rel_error: float = 0.05
    # For a real design gate this should normally be true.  It is false in the
    # default artifact so the generated surrogate demonstration can complete.
    fail_if_not_design_approved: bool = False

    comparison_config: ExternalReferenceComparisonConfig = field(
        default_factory=lambda: ExternalReferenceComparisonConfig(
            version="0.5.4",
            # Practical default acceptance tolerances for a project reference
            # rehearsal.  Tighten these when approving real REFPROP/NIST data.
            T_abs_tol_K=0.25,
            T_rel_tol=0.0,
            rho_abs_tol_kg_m3=0.5,
            rho_rel_tol=0.01,
            p_abs_tol_pa=1.0e4,
            p_rel_tol=0.005,
            e_abs_tol_j_kg=2.0e3,
            e_rel_tol=0.02,
            h_abs_tol_j_kg=2.0e3,
            h_rel_tol=0.02,
            q_abs_tol=0.01,
            q_rel_tol=0.0,
            alpha_abs_tol=0.02,
            alpha_rel_tol=0.0,
            c_abs_tol_m_s=5.0,
            c_rel_tol=0.05,
        )
    )


@dataclass(frozen=True)
class ReferenceAcceptanceDecision:
    """Human-readable and machine-readable gate result."""

    status: str
    accepted_for_design_use: bool
    rehearsal_pass: bool
    overall_pass: bool
    blocking_issue_count: int
    warning_count: int
    message: str


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _as_float(value: object, default: float = math.nan) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _write_json(path: Path, obj: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _row(check_id: str, category: str, required: bool, passed: bool, observed: object, criterion: str, message: str) -> dict[str, object]:
    return {
        "check_id": check_id,
        "category": category,
        "required": required,
        "pass": passed,
        "observed": observed,
        "criterion": criterion,
        "message": message,
    }


def _comparison_quantity_set(comparison_summary: Mapping[str, object]) -> set[str]:
    by_q = comparison_summary.get("by_quantity", {})
    if isinstance(by_q, Mapping):
        return {str(k) for k in by_q.keys()}
    return set()


def _comparison_max(comparison_summary: Mapping[str, object], quantity: str, key: str) -> float:
    by_q = comparison_summary.get("by_quantity", {})
    if not isinstance(by_q, Mapping):
        return math.nan
    bucket = by_q.get(quantity, {})
    if not isinstance(bucket, Mapping):
        return math.nan
    return _as_float(bucket.get(key))


def evaluate_reference_acceptance(
    ingestion_metrics: Mapping[str, object],
    *,
    config: ReferenceAcceptanceGateConfig | None = None,
) -> tuple[ReferenceAcceptanceDecision, list[dict[str, object]]]:
    """Convert ingestion/comparison metrics into an acceptance decision."""

    cfg = config or ReferenceAcceptanceGateConfig()
    checks: list[dict[str, object]] = []

    manifest = ingestion_metrics.get("reference_manifest", {})
    if not isinstance(manifest, Mapping):
        manifest = {}
    comparison_summary = ingestion_metrics.get("comparison_summary", {})
    if not isinstance(comparison_summary, Mapping):
        comparison_summary = {}

    approved = _as_bool(ingestion_metrics.get("design_reference_available", manifest.get("approved_for_design_use", False)))
    fluid = str(manifest.get("fluid", ""))
    comparison_quantities = _comparison_quantity_set(comparison_summary)

    checks.append(_row(
        "manifest.approved_for_design_use",
        "approval",
        cfg.fail_if_not_design_approved,
        approved or not cfg.fail_if_not_design_approved,
        approved,
        "true when design acceptance is required",
        "Project manifest must explicitly approve the reference for design use.",
    ))
    checks.append(_row(
        "manifest.fluid",
        "schema",
        True,
        fluid.upper() in {f.upper() for f in cfg.allowed_fluids},
        fluid,
        f"one of {cfg.allowed_fluids}",
        "Reference fluid must match the project fluid basis.",
    ))
    checks.append(_row(
        "ingestion.validation_errors",
        "ingestion",
        True,
        _as_int(ingestion_metrics.get("ingestion_validation_error_count")) <= cfg.max_validation_errors,
        ingestion_metrics.get("ingestion_validation_error_count"),
        f"<= {cfg.max_validation_errors}",
        "Raw/canonical reference rows must pass schema and mode validation.",
    ))
    checks.append(_row(
        "ingestion.canonical_rows",
        "coverage",
        True,
        _as_int(ingestion_metrics.get("canonical_row_count")) >= cfg.min_canonical_rows,
        ingestion_metrics.get("canonical_row_count"),
        f">= {cfg.min_canonical_rows}",
        "Reference table must contain enough points to cover the intended thermodynamic envelope.",
    ))
    checks.append(_row(
        "comparison.count",
        "coverage",
        True,
        _as_int(comparison_summary.get("comparison_count")) >= cfg.min_comparable_quantities,
        comparison_summary.get("comparison_count"),
        f">= {cfg.min_comparable_quantities}",
        "Comparable backend/reference quantities must be sufficient for qualification.",
    ))
    checks.append(_row(
        "comparison.failed_count",
        "comparison",
        True,
        _as_int(comparison_summary.get("failed_count")) <= cfg.max_failed_comparisons,
        comparison_summary.get("failed_count"),
        f"<= {cfg.max_failed_comparisons}",
        "Reference comparison must not exceed allowed failed comparisons.",
    ))

    mode_counts = ingestion_metrics.get("mode_counts", {})
    # Ver.0.5.3 metrics did not expose mode_counts; accept if absent and all
    # required quantities are present.  Ver.0.5.4 artifacts add mode_counts.
    if isinstance(mode_counts, Mapping) and mode_counts:
        for mode in cfg.required_modes:
            checks.append(_row(
                f"coverage.mode.{mode}",
                "coverage",
                True,
                _as_int(mode_counts.get(mode)) > 0,
                mode_counts.get(mode, 0),
                "> 0",
                f"Required thermodynamic mode `{mode}` must be represented.",
            ))

    for quantity in cfg.required_quantities:
        checks.append(_row(
            f"coverage.quantity.{quantity}",
            "coverage",
            True,
            quantity in comparison_quantities,
            quantity in comparison_quantities,
            "present in comparison summary",
            f"Required reference quantity `{quantity}` must be compared.",
        ))

    # Aggregate physical tolerance sanity checks.  These complement the exact
    # per-row comparator and are intended to make the gate report readable.
    aggregate_rules = [
        ("max_T_sat_abs_error", "T_sat_K", "max_abs_error", cfg.max_temperature_abs_error_K, "K"),
        ("max_rho_l_rel_error", "rho_l_kg_m3", "max_rel_error", cfg.max_density_rel_error, "fraction"),
        ("max_rho_v_rel_error", "rho_v_kg_m3", "max_rel_error", cfg.max_density_rel_error, "fraction"),
        ("max_rho_pT_rel_error", "rho_kg_m3", "max_rel_error", cfg.max_density_rel_error, "fraction"),
        ("max_pressure_rel_error", "p_pa", "max_rel_error", cfg.max_pressure_rel_error, "fraction"),
        ("max_temperature_rel_error", "T_K", "max_rel_error", 0.002, "fraction"),
        ("max_quality_abs_error", "quality", "max_abs_error", cfg.max_quality_abs_error, "fraction"),
        ("max_alpha_abs_error", "alpha", "max_abs_error", cfg.max_alpha_abs_error, "fraction"),
        ("max_sound_speed_rel_error", "c_m_s", "max_rel_error", cfg.max_sound_speed_rel_error, "fraction"),
        ("max_latent_rel_error", "h_lv_j_kg", "max_rel_error", cfg.max_energy_rel_error, "fraction"),
    ]
    for check_id, quantity, err_key, limit, unit in aggregate_rules:
        if quantity not in comparison_quantities:
            continue
        observed = _comparison_max(comparison_summary, quantity, err_key)
        checks.append(_row(
            f"aggregate_error.{check_id}",
            "comparison",
            True,
            math.isfinite(observed) and observed <= limit,
            observed,
            f"<= {limit:g} {unit}",
            f"Aggregate error for `{quantity}` must stay within project gate tolerance.",
        ))

    blocking = [c for c in checks if _as_bool(c.get("required")) and not _as_bool(c.get("pass"))]
    warnings = [c for c in checks if not _as_bool(c.get("required")) and not _as_bool(c.get("pass"))]
    mechanics_pass = len(blocking) == 0

    if mechanics_pass and approved:
        status = "ACCEPTED_FOR_DESIGN_USE"
        accepted = True
        rehearsal = False
        message = "Project reference table is approved and all acceptance-gate checks passed."
    elif mechanics_pass and not approved:
        status = "REHEARSAL_PASS_NOT_DESIGN_REFERENCE"
        accepted = False
        rehearsal = True
        message = "Acceptance mechanics passed, but manifest is not approved for design use. Do not use for design decisions."
    else:
        status = "REJECTED"
        accepted = False
        rehearsal = False
        message = "Acceptance gate rejected the reference table. Resolve blocking checks before design use."

    if cfg.require_design_approved_reference and not approved:
        status = "REJECTED"
        accepted = False
        rehearsal = False
        message = "Design-approved reference was required but manifest is not approved."

    decision = ReferenceAcceptanceDecision(
        status=status,
        accepted_for_design_use=accepted,
        rehearsal_pass=rehearsal,
        overall_pass=mechanics_pass and (approved or not cfg.require_design_approved_reference),
        blocking_issue_count=len(blocking),
        warning_count=len(warnings),
        message=message,
    )
    return decision, checks


def _mode_counts_from_canonical(canonical_csv: Path) -> dict[str, int]:
    if not canonical_csv.exists():
        return {}
    with canonical_csv.open("r", newline="", encoding="utf-8") as f:
        counts: dict[str, int] = {}
        for row in csv.DictReader(f):
            mode = str(row.get("mode", "")).strip().lower()
            if mode:
                counts[mode] = counts.get(mode, 0) + 1
    return counts


def generate_reference_acceptance_gate_artifacts(
    output_dir: str | Path,
    *,
    backend_name: str = "surrogate_lco2",
    raw_reference_csv: str | Path | None = None,
    manifest_json: str | Path | None = None,
    config: ReferenceAcceptanceGateConfig | None = None,
) -> dict[str, object]:
    """Generate Ver.0.5.4 reference acceptance-gate artifacts."""

    cfg = config or ReferenceAcceptanceGateConfig()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ingestion_cfg = ProjectReferenceIngestionConfig(
        version=cfg.version,
        require_design_approved_reference=cfg.require_design_approved_reference,
        allowed_fluids=cfg.allowed_fluids,
        fail_on_validation_warning=True,
        fail_on_empty_comparison=True,
        comparison_config=cfg.comparison_config,
    )
    ingestion_metrics = generate_project_reference_ingestion_artifacts(
        out_dir,
        backend_name=backend_name,
        raw_reference_csv=raw_reference_csv,
        manifest_json=manifest_json,
        config=ingestion_cfg,
    )
    paths = ingestion_metrics.get("paths", {})
    if isinstance(paths, Mapping) and "canonical_csv" in paths:
        ingestion_metrics = dict(ingestion_metrics)
        ingestion_metrics["mode_counts"] = _mode_counts_from_canonical(Path(str(paths["canonical_csv"])))

    decision, checks = evaluate_reference_acceptance(ingestion_metrics, config=cfg)

    decision_csv = out_dir / "reference_acceptance_decision_v0_5_4.csv"
    thresholds_json = out_dir / "reference_acceptance_thresholds_v0_5_4.json"
    metrics_json = out_dir / "reference_acceptance_metrics_v0_5_4.json"
    report_md = out_dir / "reference_acceptance_gate_report_v0_5_4.md"
    _write_csv(decision_csv, checks, DECISION_COLUMNS)
    _write_json(thresholds_json, asdict(cfg))

    metrics: dict[str, object] = {
        "version": cfg.version,
        "backend_name": backend_name,
        "decision": asdict(decision),
        "acceptance_check_count": len(checks),
        "blocking_checks": [c for c in checks if _as_bool(c.get("required")) and not _as_bool(c.get("pass"))],
        "ingestion_metrics": ingestion_metrics,
        "overall_pass": decision.overall_pass,
        "paths": {
            "decision_csv": str(decision_csv),
            "thresholds_json": str(thresholds_json),
            "metrics_json": str(metrics_json),
            "report_md": str(report_md),
            "ingestion_report_md": str(paths.get("report_md", "")) if isinstance(paths, Mapping) else "",
            "canonical_csv": str(paths.get("canonical_csv", "")) if isinstance(paths, Mapping) else "",
            "comparison_csv": str(paths.get("comparison_csv", "")) if isinstance(paths, Mapping) else "",
        },
    }
    _write_json(metrics_json, metrics)

    lines = [
        "# LCO2 reference acceptance gate report Ver.0.5.4",
        "",
        f"decision: `{decision.status}`",
        f"accepted_for_design_use: `{str(decision.accepted_for_design_use).lower()}`",
        f"overall_pass: `{str(decision.overall_pass).lower()}`",
        "",
        "## Scope",
        "",
        "Ver.0.5.4 converts a project reference-table ingestion/comparison run into an explicit acceptance decision.",
        "The default generated run is a surrogate rehearsal. It verifies the gate mechanics, not real LCO2 property truth.",
        "",
        "## Decision message",
        "",
        decision.message,
        "",
        "## Gate summary",
        "",
        f"- Acceptance checks: `{len(checks)}`",
        f"- Blocking issues: `{decision.blocking_issue_count}`",
        f"- Warnings: `{decision.warning_count}`",
        f"- Backend: `{backend_name}`",
        f"- Mode counts: `{ingestion_metrics.get('mode_counts', {})}`",
        "",
        "## Blocking checks",
        "",
    ]
    blocking_checks = [c for c in checks if _as_bool(c.get("required")) and not _as_bool(c.get("pass"))]
    if not blocking_checks:
        lines.append("No blocking checks.")
    else:
        lines.extend(["| Check | Observed | Criterion | Message |", "|---|---:|---|---|"])
        for c in blocking_checks:
            lines.append(f"| `{c['check_id']}` | `{c['observed']}` | `{c['criterion']}` | {c['message']} |")
    lines.extend([
        "",
        "## All checks",
        "",
        "| Check | Category | Required | Pass | Observed | Criterion |",
        "|---|---|---:|---:|---:|---|",
    ])
    for c in checks:
        lines.append(
            f"| `{c['check_id']}` | {c['category']} | `{str(c['required']).lower()}` | `{str(c['pass']).lower()}` | `{c['observed']}` | {c['criterion']} |"
        )
    lines.extend([
        "",
        "## Generated files",
        "",
        f"- Decision CSV: `{decision_csv.name}`",
        f"- Thresholds JSON: `{thresholds_json.name}`",
        f"- Metrics JSON: `{metrics_json.name}`",
        f"- Canonical SI CSV: `{Path(str(metrics['paths']['canonical_csv'])).name}`",
        f"- Backend comparison CSV: `{Path(str(metrics['paths']['comparison_csv'])).name}`",
        "",
        "## Design-use rule",
        "",
        "Only `ACCEPTED_FOR_DESIGN_USE` should be used for design decisions. `REHEARSAL_PASS_NOT_DESIGN_REFERENCE` is useful for software verification, but it is not a property-data approval.",
        "",
    ])
    report_md.write_text("\n".join(lines), encoding="utf-8")
    return metrics


def build_approved_surrogate_reference_for_gate_demo(output_dir: str | Path) -> tuple[Path, Path]:
    """Create a design-approved surrogate demo file for gate unit testing.

    This helper is intentionally named as a demo.  It proves the gate can reach
    ACCEPTED_FOR_DESIGN_USE when and only when the manifest is marked approved.
    It must not be used as real LCO2 design data.
    """

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest, raw_rows = build_surrogate_project_reference_demo_rows()
    approved_manifest = ProjectReferenceManifest(
        project_reference_id="LCO2_REFERENCE_APPROVED_SURROGATE_GATE_DEMO",
        fluid=manifest.fluid,
        source_name="surrogate_gate_demo_not_physical_design_data",
        source_version="v0.5.4-demo",
        generated_by="reference_acceptance gate unit test",
        approval_status="approved_demo_for_gate_logic_only",
        approved_for_design_use=True,
        approved_by="test_fixture",
        approval_date="2026-06-28",
        units_basis=manifest.units_basis,
        notes="This file is approved only to exercise the gate logic; not a real LCO2 reference.",
    )
    raw_csv = out / "approved_surrogate_reference_raw_demo_v0_5_4.csv"
    manifest_json = out / "approved_surrogate_reference_manifest_demo_v0_5_4.json"
    # Reuse the raw writer through project ingestion is not exported; write here.
    fieldnames = []
    for row in raw_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    _write_csv(raw_csv, raw_rows, fieldnames)
    _write_json(manifest_json, asdict(approved_manifest))
    return raw_csv, manifest_json
