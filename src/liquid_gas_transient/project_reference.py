"""Project-approved LCO2 reference-table ingestion for Ver.0.5.3.

Ver.0.5.2 added an external CSV comparator.  Ver.0.5.3 adds the step that a
project actually needs before using that comparator for qualification:

* a manifest that records provenance and approval status,
* schema/unit normalization into canonical SI columns,
* validation of required inputs for each thermodynamic mode,
* immutable canonical output CSVs that can be archived,
* comparison against the selected property backend.

The default generated table is a surrogate-backed pipeline demonstration.  It
verifies ingestion and comparison mechanics, not real LCO2 property truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence
import csv
import json
import math

import numpy as np

from .external_reference import (
    ExternalReferenceComparisonConfig,
    REFERENCE_COLUMNS,
    RESULT_COLUMNS,
    build_surrogate_self_reference_rows,
    compare_backend_to_reference_rows,
    summarize_reference_comparison,
)
from .properties import (
    RealFluidPropertyBackend,
    SurrogateLCO2PropertyBackend,
    make_property_backend,
    property_backend_availability,
)


CANONICAL_REFERENCE_COLUMNS: tuple[str, ...] = (
    "project_reference_id",
    "approval_status",
    "approved_for_design_use",
    "point_id",
    "mode",
    "source",
    "p_pa",
    "T_K",
    "rho_kg_m3",
    "e_j_kg",
    "ref_T_sat_K",
    "ref_rho_l_kg_m3",
    "ref_rho_v_kg_m3",
    "ref_e_l_j_kg",
    "ref_e_v_j_kg",
    "ref_h_lv_j_kg",
    "ref_rho_kg_m3",
    "ref_p_pa",
    "ref_T_K",
    "ref_quality",
    "ref_alpha",
    "ref_c_m_s",
    "notes",
)

RAW_TEMPLATE_COLUMNS: tuple[str, ...] = (
    "point_id",
    "mode",
    "source",
    "p_pa",
    "p_MPa",
    "p_bar",
    "T_K",
    "T_C",
    "rho_kg_m3",
    "e_j_kg",
    "e_kJ_kg",
    "ref_T_sat_K",
    "ref_T_sat_C",
    "ref_rho_l_kg_m3",
    "ref_rho_v_kg_m3",
    "ref_e_l_j_kg",
    "ref_e_l_kJ_kg",
    "ref_e_v_j_kg",
    "ref_e_v_kJ_kg",
    "ref_h_lv_j_kg",
    "ref_h_lv_kJ_kg",
    "ref_rho_kg_m3",
    "ref_p_pa",
    "ref_p_MPa",
    "ref_T_K",
    "ref_T_C",
    "ref_quality",
    "ref_alpha",
    "ref_c_m_s",
    "notes",
)

MODE_REQUIRED_INPUTS: dict[str, tuple[str, ...]] = {
    "saturation": ("p_pa",),
    "density_pt": ("p_pa", "T_K"),
    "mixture_rhoe": ("rho_kg_m3", "e_j_kg"),
}


@dataclass(frozen=True)
class ProjectReferenceManifest:
    """Provenance and approval metadata for one reference table."""

    project_reference_id: str = "LCO2_REFERENCE_DEMO_SURROGATE_V0_5_3"
    fluid: str = "CO2"
    source_name: str = "surrogate_lco2_pipeline_demo"
    source_version: str = "v0.5.3-demo"
    generated_by: str = "liquid_gas_transient verification generator"
    approval_status: str = "pipeline_demo_not_design_data"
    approved_for_design_use: bool = False
    approved_by: str = "not_applicable"
    approval_date: str = "not_applicable"
    units_basis: str = "canonical SI after ingestion: Pa, K, kg/m3, J/kg"
    notes: str = (
        "This manifest demonstrates the ingestion gate. Replace it with a project-"
        "approved CoolProp/REFPROP/NIST/vendor reference manifest before design use."
    )


@dataclass(frozen=True)
class ProjectReferenceIngestionConfig:
    """Configuration for Ver.0.5.3 ingestion and comparison."""

    version: str = "0.5.3"
    require_design_approved_reference: bool = False
    allowed_fluids: tuple[str, ...] = ("CO2", "LCO2", "R744")
    fail_on_validation_warning: bool = True
    fail_on_empty_comparison: bool = True
    comparison_config: ExternalReferenceComparisonConfig | None = None


def _to_float(value: object, default: float = math.nan) -> float:
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    try:
        out = float(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _as_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


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


def _value_from_aliases(row: Mapping[str, object], aliases: Sequence[tuple[str, float, float]]) -> float:
    """Return first finite value after scale and offset conversion.

    aliases entries are (column_name, scale, offset).  Converted value is
    raw * scale + offset.
    """

    for key, scale, offset in aliases:
        raw = _to_float(row.get(key))
        if math.isfinite(raw):
            return raw * scale + offset
    return math.nan


def _canonicalize_one_row(row: Mapping[str, object], manifest: ProjectReferenceManifest) -> dict[str, object]:
    p = _value_from_aliases(row, (("p_pa", 1.0, 0.0), ("p_MPa", 1.0e6, 0.0), ("p_bar", 1.0e5, 0.0)))
    T = _value_from_aliases(row, (("T_K", 1.0, 0.0), ("T_C", 1.0, 273.15)))
    rho = _value_from_aliases(row, (("rho_kg_m3", 1.0, 0.0),))
    e = _value_from_aliases(row, (("e_j_kg", 1.0, 0.0), ("e_kJ_kg", 1.0e3, 0.0)))

    ref_T_sat = _value_from_aliases(row, (("ref_T_sat_K", 1.0, 0.0), ("ref_T_sat_C", 1.0, 273.15)))
    ref_e_l = _value_from_aliases(row, (("ref_e_l_j_kg", 1.0, 0.0), ("ref_e_l_kJ_kg", 1.0e3, 0.0)))
    ref_e_v = _value_from_aliases(row, (("ref_e_v_j_kg", 1.0, 0.0), ("ref_e_v_kJ_kg", 1.0e3, 0.0)))
    ref_h_lv = _value_from_aliases(row, (("ref_h_lv_j_kg", 1.0, 0.0), ("ref_h_lv_kJ_kg", 1.0e3, 0.0)))
    ref_p = _value_from_aliases(row, (("ref_p_pa", 1.0, 0.0), ("ref_p_MPa", 1.0e6, 0.0)))
    ref_T = _value_from_aliases(row, (("ref_T_K", 1.0, 0.0), ("ref_T_C", 1.0, 273.15)))

    out = {
        "project_reference_id": manifest.project_reference_id,
        "approval_status": manifest.approval_status,
        "approved_for_design_use": bool(manifest.approved_for_design_use),
        "point_id": _as_text(row.get("point_id")),
        "mode": _as_text(row.get("mode")).lower(),
        "source": _as_text(row.get("source"), manifest.source_name),
        "p_pa": p,
        "T_K": T,
        "rho_kg_m3": rho,
        "e_j_kg": e,
        "ref_T_sat_K": ref_T_sat,
        "ref_rho_l_kg_m3": _value_from_aliases(row, (("ref_rho_l_kg_m3", 1.0, 0.0),)),
        "ref_rho_v_kg_m3": _value_from_aliases(row, (("ref_rho_v_kg_m3", 1.0, 0.0),)),
        "ref_e_l_j_kg": ref_e_l,
        "ref_e_v_j_kg": ref_e_v,
        "ref_h_lv_j_kg": ref_h_lv,
        "ref_rho_kg_m3": _value_from_aliases(row, (("ref_rho_kg_m3", 1.0, 0.0),)),
        "ref_p_pa": ref_p,
        "ref_T_K": ref_T,
        "ref_quality": _value_from_aliases(row, (("ref_quality", 1.0, 0.0),)),
        "ref_alpha": _value_from_aliases(row, (("ref_alpha", 1.0, 0.0),)),
        "ref_c_m_s": _value_from_aliases(row, (("ref_c_m_s", 1.0, 0.0),)),
        "notes": _as_text(row.get("notes"), manifest.notes),
    }
    # Empty strings are cleaner than NaN in archived canonical CSVs while still
    # being accepted by the existing comparator.
    for k, v in list(out.items()):
        if isinstance(v, float) and not math.isfinite(v):
            out[k] = ""
    return out


def validate_project_reference_rows(
    canonical_rows: Sequence[Mapping[str, object]],
    manifest: ProjectReferenceManifest,
    *,
    config: ProjectReferenceIngestionConfig | None = None,
) -> list[dict[str, object]]:
    """Validate canonicalized project-reference rows."""

    cfg = config or ProjectReferenceIngestionConfig()
    issues: list[dict[str, object]] = []
    if manifest.fluid.upper() not in {f.upper() for f in cfg.allowed_fluids}:
        issues.append({"level": "error", "point_id": "__manifest__", "issue": f"unsupported fluid: {manifest.fluid}"})
    if cfg.require_design_approved_reference and not manifest.approved_for_design_use:
        issues.append({"level": "error", "point_id": "__manifest__", "issue": "reference table is not approved for design use"})

    seen: set[str] = set()
    for i, row in enumerate(canonical_rows):
        point_id = _as_text(row.get("point_id"), f"row_{i:04d}")
        mode = _as_text(row.get("mode")).lower()
        if point_id in seen:
            issues.append({"level": "error", "point_id": point_id, "issue": "duplicate point_id"})
        seen.add(point_id)
        if mode not in MODE_REQUIRED_INPUTS:
            issues.append({"level": "error", "point_id": point_id, "issue": f"unsupported mode: {mode}"})
            continue
        for req in MODE_REQUIRED_INPUTS[mode]:
            if not math.isfinite(_to_float(row.get(req))):
                issues.append({"level": "error", "point_id": point_id, "issue": f"missing required input: {req}"})
        comparable_ref_fields = [
            k
            for k in (
                "ref_T_sat_K",
                "ref_rho_l_kg_m3",
                "ref_rho_v_kg_m3",
                "ref_e_l_j_kg",
                "ref_e_v_j_kg",
                "ref_h_lv_j_kg",
                "ref_rho_kg_m3",
                "ref_p_pa",
                "ref_T_K",
                "ref_quality",
                "ref_alpha",
                "ref_c_m_s",
            )
            if math.isfinite(_to_float(row.get(k)))
        ]
        if len(comparable_ref_fields) == 0:
            issues.append({"level": "error", "point_id": point_id, "issue": "no comparable reference value supplied"})
        if mode == "saturation":
            rho_l = _to_float(row.get("ref_rho_l_kg_m3"))
            rho_v = _to_float(row.get("ref_rho_v_kg_m3"))
            if math.isfinite(rho_l) and math.isfinite(rho_v) and not rho_l > rho_v:
                issues.append({"level": "error", "point_id": point_id, "issue": "saturation density ordering failed: rho_l <= rho_v"})
            h_lv = _to_float(row.get("ref_h_lv_j_kg"))
            if math.isfinite(h_lv) and not h_lv > 0.0:
                issues.append({"level": "error", "point_id": point_id, "issue": "latent heat must be positive"})
        if mode == "mixture_rhoe":
            q = _to_float(row.get("ref_quality"))
            a = _to_float(row.get("ref_alpha"))
            if math.isfinite(q) and not (-1.0e-12 <= q <= 1.0 + 1.0e-12):
                issues.append({"level": "error", "point_id": point_id, "issue": "quality outside [0, 1]"})
            if math.isfinite(a) and not (-1.0e-12 <= a <= 1.0 + 1.0e-12):
                issues.append({"level": "error", "point_id": point_id, "issue": "alpha outside [0, 1]"})
    return issues


def project_reference_template_rows() -> list[dict[str, object]]:
    """Rows documenting the accepted raw CSV schema, including alternate units."""

    return [
        {
            "point_id": "sat_1900kpa",
            "mode": "saturation",
            "source": "CoolProp_or_REFPROP_or_NIST_or_vendor_table",
            "p_MPa": 1.9,
            "ref_T_sat_K": "",
            "ref_rho_l_kg_m3": "",
            "ref_rho_v_kg_m3": "",
            "ref_e_l_kJ_kg": "",
            "ref_e_v_kJ_kg": "",
            "ref_h_lv_kJ_kg": "",
            "notes": "Use either SI canonical columns or supported alternate-unit columns.",
        },
        {
            "point_id": "rho_pT_1900kpa_253K",
            "mode": "density_pT",
            "source": "CoolProp_or_REFPROP_or_NIST_or_vendor_table",
            "p_MPa": 1.9,
            "T_K": 253.15,
            "ref_rho_kg_m3": "",
            "notes": "Compares backend density_from_pT(p,T).",
        },
        {
            "point_id": "mix_1900kpa_q010",
            "mode": "mixture_rhoe",
            "source": "CoolProp_or_REFPROP_or_NIST_or_vendor_table",
            "rho_kg_m3": "",
            "e_kJ_kg": "",
            "ref_p_MPa": 1.9,
            "ref_T_K": "",
            "ref_quality": 0.1,
            "ref_alpha": "",
            "ref_c_m_s": "",
            "notes": "rho/e should describe the mixture state being reconstructed.",
        },
    ]


def manifest_template() -> ProjectReferenceManifest:
    return ProjectReferenceManifest(
        project_reference_id="LCO2_REFERENCE_APPROVED_YYYYMMDD",
        source_name="CoolProp_OR_REFPROP_OR_NIST_OR_VENDOR",
        source_version="replace_with_version_or_export_id",
        generated_by="replace_with_person_or_tool",
        approval_status="replace_with_project_approval_status",
        approved_for_design_use=False,
        approved_by="replace_with_approver",
        approval_date="YYYY-MM-DD",
        notes="Archive the raw CSV, canonical CSV, manifest, comparison CSV, and report together.",
    )


def build_surrogate_project_reference_demo_rows(
    backend: RealFluidPropertyBackend | None = None,
) -> tuple[ProjectReferenceManifest, list[dict[str, object]]]:
    """Build a raw CSV demo using alternate units to exercise ingestion.

    This is intentionally not design data.  It is a deterministic pipeline test
    built from the surrogate backend.
    """

    b = backend or SurrogateLCO2PropertyBackend()
    base = build_surrogate_self_reference_rows(
        b,
        pressures_pa=(1.2e6, 1.5e6, 1.9e6, 2.3e6, 2.8e6),
        density_pT_offsets_K=(-6.0, 0.0, 6.0),
        mixture_pressure_pa=1.9e6,
        qualities=(0.0, 0.01, 0.1, 0.5, 0.9, 0.99, 1.0),
    )
    manifest = ProjectReferenceManifest()
    raw: list[dict[str, object]] = []
    for row in base:
        mode = str(row.get("mode"))
        out: dict[str, object] = {
            "point_id": row.get("point_id"),
            "mode": mode,
            "source": "surrogate_project_reference_demo",
            "notes": "pipeline demo reference; not design data",
        }
        if mode == "saturation":
            out["p_MPa"] = _to_float(row.get("p_pa")) / 1.0e6
            out["ref_T_sat_C"] = _to_float(row.get("ref_T_sat_K")) - 273.15
            out["ref_rho_l_kg_m3"] = row.get("ref_rho_l_kg_m3")
            out["ref_rho_v_kg_m3"] = row.get("ref_rho_v_kg_m3")
            out["ref_e_l_kJ_kg"] = _to_float(row.get("ref_e_l_j_kg")) / 1.0e3
            out["ref_e_v_kJ_kg"] = _to_float(row.get("ref_e_v_j_kg")) / 1.0e3
            out["ref_h_lv_kJ_kg"] = _to_float(row.get("ref_h_lv_j_kg")) / 1.0e3
        elif mode == "density_pT":
            out["p_bar"] = _to_float(row.get("p_pa")) / 1.0e5
            out["T_C"] = _to_float(row.get("T_K")) - 273.15
            out["ref_rho_kg_m3"] = row.get("ref_rho_kg_m3")
        elif mode == "mixture_rhoe":
            out["rho_kg_m3"] = row.get("rho_kg_m3")
            out["e_kJ_kg"] = _to_float(row.get("e_j_kg")) / 1.0e3
            out["ref_p_MPa"] = _to_float(row.get("ref_p_pa")) / 1.0e6
            out["ref_T_C"] = _to_float(row.get("ref_T_K")) - 273.15
            out["ref_quality"] = row.get("ref_quality")
            out["ref_alpha"] = row.get("ref_alpha")
            out["ref_c_m_s"] = row.get("ref_c_m_s")
        raw.append(out)
    return manifest, raw


def ingest_project_reference_rows(
    raw_rows: Sequence[Mapping[str, object]],
    manifest: ProjectReferenceManifest,
    *,
    config: ProjectReferenceIngestionConfig | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Normalize raw reference rows and return canonical rows plus issues."""

    cfg = config or ProjectReferenceIngestionConfig()
    canonical_rows = [_canonicalize_one_row(row, manifest) for row in raw_rows]
    issues = validate_project_reference_rows(canonical_rows, manifest, config=cfg)
    return canonical_rows, issues


def _read_manifest(path: Path) -> ProjectReferenceManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = {f.name for f in ProjectReferenceManifest.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return ProjectReferenceManifest(**{k: v for k, v in data.items() if k in allowed})


def generate_project_reference_ingestion_artifacts(
    output_dir: str | Path,
    *,
    backend_name: str = "surrogate_lco2",
    raw_reference_csv: str | Path | None = None,
    manifest_json: str | Path | None = None,
    config: ProjectReferenceIngestionConfig | None = None,
) -> dict[str, object]:
    """Generate Ver.0.5.3 reference-ingestion artifacts."""

    cfg = config or ProjectReferenceIngestionConfig()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    template_csv = out_dir / "project_reference_raw_template_v0_5_3.csv"
    manifest_template_path = out_dir / "project_reference_manifest_template_v0_5_3.json"
    _write_csv(template_csv, project_reference_template_rows(), RAW_TEMPLATE_COLUMNS)
    _write_json(manifest_template_path, asdict(manifest_template()))

    if raw_reference_csv is None:
        manifest, raw_rows = build_surrogate_project_reference_demo_rows()
        raw_reference_path = out_dir / "surrogate_project_reference_raw_demo_v0_5_3.csv"
        manifest_path = out_dir / "surrogate_project_reference_manifest_demo_v0_5_3.json"
        _write_csv(raw_reference_path, raw_rows, RAW_TEMPLATE_COLUMNS)
        _write_json(manifest_path, asdict(manifest))
        reference_mode = "surrogate_project_reference_demo"
    else:
        raw_reference_path = Path(raw_reference_csv)
        raw_rows = _read_csv(raw_reference_path)
        if manifest_json is None:
            raise ValueError("manifest_json is required when raw_reference_csv is supplied")
        manifest_path = Path(manifest_json)
        manifest = _read_manifest(manifest_path)
        reference_mode = "project_supplied_reference"

    canonical_rows, validation_issues = ingest_project_reference_rows(raw_rows, manifest, config=cfg)
    canonical_csv = out_dir / "project_reference_canonical_si_v0_5_3.csv"
    validation_csv = out_dir / "project_reference_validation_issues_v0_5_3.csv"
    _write_csv(canonical_csv, canonical_rows, CANONICAL_REFERENCE_COLUMNS)
    _write_csv(validation_csv, validation_issues, ("level", "point_id", "issue"))

    backend = make_property_backend(backend_name)
    comparison_cfg = cfg.comparison_config or ExternalReferenceComparisonConfig(version=cfg.version)
    comparison_rows = compare_backend_to_reference_rows(backend, canonical_rows, config=comparison_cfg)
    comparison_csv = out_dir / "project_reference_comparison_v0_5_3.csv"
    _write_csv(comparison_csv, comparison_rows, RESULT_COLUMNS + ("error",))
    comparison_summary = summarize_reference_comparison(comparison_rows)

    has_errors = any(str(issue.get("level")) == "error" for issue in validation_issues)
    comparison_ok = bool(comparison_summary.get("overall_pass"))
    ingestion_ok = not has_errors
    design_reference_available = bool(manifest.approved_for_design_use)
    overall_pass = ingestion_ok and comparison_ok and (
        design_reference_available or not cfg.require_design_approved_reference
    )

    optional_backend_status = property_backend_availability()
    metrics: dict[str, object] = {
        "version": cfg.version,
        "backend_name": backend.name,
        "reference_mode": reference_mode,
        "reference_manifest": asdict(manifest),
        "design_reference_available": design_reference_available,
        "require_design_approved_reference": cfg.require_design_approved_reference,
        "ingestion_validation_issue_count": len(validation_issues),
        "ingestion_validation_error_count": sum(1 for i in validation_issues if str(i.get("level")) == "error"),
        "canonical_row_count": len(canonical_rows),
        "comparison_summary": comparison_summary,
        "optional_backend_status": optional_backend_status,
        "overall_pass": overall_pass,
        "interpretation": (
            "Pipeline ingestion/comparison pass only; not design-qualified LCO2 property data"
            if not design_reference_available
            else "Project-approved reference table ingested and compared"
        ),
        "paths": {
            "raw_template_csv": str(template_csv),
            "manifest_template_json": str(manifest_template_path),
            "raw_reference_csv": str(raw_reference_path),
            "manifest_json": str(manifest_path),
            "canonical_csv": str(canonical_csv),
            "validation_issues_csv": str(validation_csv),
            "comparison_csv": str(comparison_csv),
            "metrics_json": str(out_dir / "project_reference_ingestion_metrics_v0_5_3.json"),
            "report_md": str(out_dir / "project_reference_ingestion_report_v0_5_3.md"),
        },
    }
    _write_json(Path(metrics["paths"]["metrics_json"]), metrics)  # type: ignore[index]

    lines = [
        "# Project-approved LCO2 reference ingestion report Ver.0.5.3",
        "",
        f"overall_pass: `{str(overall_pass).lower()}`",
        "",
        "## Scope",
        "",
        "Ver.0.5.3 adds the project-reference ingestion gate before real-fluid qualification.",
        "It normalizes a raw reference CSV into canonical SI units, validates required columns, archives the manifest, and compares the selected backend against the canonical table.",
        "",
        "## Reference manifest",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| project_reference_id | `{manifest.project_reference_id}` |",
        f"| fluid | `{manifest.fluid}` |",
        f"| source_name | `{manifest.source_name}` |",
        f"| source_version | `{manifest.source_version}` |",
        f"| approval_status | `{manifest.approval_status}` |",
        f"| approved_for_design_use | `{str(manifest.approved_for_design_use).lower()}` |",
        f"| approved_by | `{manifest.approved_by}` |",
        f"| approval_date | `{manifest.approval_date}` |",
        "",
        "## Ingestion validation",
        "",
        f"- Canonical row count: `{len(canonical_rows)}`",
        f"- Validation issue count: `{len(validation_issues)}`",
        f"- Validation error count: `{metrics['ingestion_validation_error_count']}`",
        "",
        "## Backend comparison",
        "",
        f"- Backend evaluated: `{backend.name}`",
        f"- Comparable quantities: `{comparison_summary['comparison_count']}`",
        f"- Failed comparisons: `{comparison_summary['failed_count']}`",
        "",
        "| Quantity | Count | Max abs error | Max rel error |",
        "|---|---:|---:|---:|",
    ]
    for quantity, bucket in dict(comparison_summary["by_quantity"]).items():
        lines.append(
            f"| {quantity} | {int(bucket['count'])} | {float(bucket['max_abs_error']):.6e} | {float(bucket['max_rel_error']):.6e} |"
        )
    lines.extend(
        [
            "",
            "## Generated files",
            "",
            f"- Raw template CSV: `{template_csv.name}`",
            f"- Manifest template JSON: `{manifest_template_path.name}`",
            f"- Raw reference CSV used: `{raw_reference_path.name}`",
            f"- Manifest used: `{manifest_path.name}`",
            f"- Canonical SI CSV: `{canonical_csv.name}`",
            f"- Validation issues CSV: `{validation_csv.name}`",
            f"- Comparison CSV: `{comparison_csv.name}`",
            f"- Metrics JSON: `{Path(metrics['paths']['metrics_json']).name}`",  # type: ignore[index]
            "",
            "## Gate interpretation",
            "",
        ]
    )
    if design_reference_available:
        lines.append("This run used a manifest marked as approved for design use. Keep the raw CSV, canonical CSV, comparison CSV, manifest, and report archived together.")
    else:
        lines.append("This run used the surrogate pipeline-demonstration reference. PASS means the ingestion and comparison machinery works; it does not certify real LCO2 thermodynamic properties.")
    lines.append("")
    Path(metrics["paths"]["report_md"]).write_text("\n".join(lines), encoding="utf-8")  # type: ignore[index]
    return metrics
