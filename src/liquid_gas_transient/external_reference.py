"""External property-reference comparison utilities for Ver.0.5.2.

The Ver.0.5.1 verification tables prove that a backend is internally
consistent.  Ver.0.5.2 adds a separate gate: compare backend outputs against an
external reference table, such as CoolProp, REFPROP, NIST tables, vendor data,
or a project-approved CSV exported from another tool.

The comparator is deliberately CSV-based and dependency-free so that the project
can archive exactly which reference points were used for qualification.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Mapping, Sequence
import csv
import json
import math

import numpy as np

from .properties import (
    RealFluidPropertyBackend,
    SurrogateLCO2PropertyBackend,
    make_property_backend,
    property_backend_availability,
)


@dataclass(frozen=True)
class QuantityTolerance:
    """Absolute-plus-relative tolerance for one compared property."""

    abs_tol: float
    rel_tol: float

    def threshold(self, reference_value: float) -> float:
        return self.abs_tol + self.rel_tol * abs(reference_value)


@dataclass(frozen=True)
class ExternalReferenceComparisonConfig:
    """Configuration for external reference table comparison."""

    version: str = "0.5.2"
    # These are engineering-gate defaults for a surrogate/self-reference run.
    # A real LCO2 design gate should tighten/adjust them per property source.
    T_abs_tol_K: float = 1.0e-6
    T_rel_tol: float = 1.0e-10
    rho_abs_tol_kg_m3: float = 1.0e-6
    rho_rel_tol: float = 1.0e-10
    p_abs_tol_pa: float = 1.0e-4
    p_rel_tol: float = 1.0e-10
    e_abs_tol_j_kg: float = 1.0e-4
    e_rel_tol: float = 1.0e-10
    h_abs_tol_j_kg: float = 1.0e-4
    h_rel_tol: float = 1.0e-10
    q_abs_tol: float = 1.0e-10
    q_rel_tol: float = 0.0
    alpha_abs_tol: float = 1.0e-10
    alpha_rel_tol: float = 0.0
    c_abs_tol_m_s: float = 1.0e-6
    c_rel_tol: float = 1.0e-10

    def tolerance_for(self, field_name: str) -> QuantityTolerance:
        if field_name.endswith("T_sat_K") or field_name.endswith("T_K"):
            return QuantityTolerance(self.T_abs_tol_K, self.T_rel_tol)
        if "rho" in field_name:
            return QuantityTolerance(self.rho_abs_tol_kg_m3, self.rho_rel_tol)
        if field_name.endswith("p_pa"):
            return QuantityTolerance(self.p_abs_tol_pa, self.p_rel_tol)
        if field_name.endswith("e_j_kg"):
            return QuantityTolerance(self.e_abs_tol_j_kg, self.e_rel_tol)
        if field_name.endswith("h_lv_j_kg"):
            return QuantityTolerance(self.h_abs_tol_j_kg, self.h_rel_tol)
        if field_name.endswith("quality"):
            return QuantityTolerance(self.q_abs_tol, self.q_rel_tol)
        if field_name.endswith("alpha"):
            return QuantityTolerance(self.alpha_abs_tol, self.alpha_rel_tol)
        if field_name.endswith("c_m_s"):
            return QuantityTolerance(self.c_abs_tol_m_s, self.c_rel_tol)
        return QuantityTolerance(0.0, 0.0)


REFERENCE_COLUMNS: tuple[str, ...] = (
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


RESULT_COLUMNS: tuple[str, ...] = (
    "point_id",
    "mode",
    "source",
    "backend",
    "quantity",
    "reference_value",
    "evaluated_value",
    "abs_error",
    "rel_error",
    "tolerance",
    "pass",
)


def _to_float(value: object, default: float = math.nan) -> float:
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    try:
        x = float(value)  # type: ignore[arg-type]
    except Exception:
        return default
    return x if math.isfinite(x) else default


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    fields.append(key)
    else:
        fields = list(fieldnames)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def reference_table_template_rows() -> list[dict[str, object]]:
    """Return example rows documenting the accepted external-reference schema."""

    return [
        {
            "point_id": "sat_example",
            "mode": "saturation",
            "source": "replace_with_CoolProp_REFPROP_NIST_or_project_table",
            "p_pa": 1.9e6,
            "ref_T_sat_K": "",
            "ref_rho_l_kg_m3": "",
            "ref_rho_v_kg_m3": "",
            "ref_e_l_j_kg": "",
            "ref_e_v_j_kg": "",
            "ref_h_lv_j_kg": "",
            "notes": "Provide any subset of ref_* fields to compare.",
        },
        {
            "point_id": "density_pT_example",
            "mode": "density_pT",
            "source": "replace_with_CoolProp_REFPROP_NIST_or_project_table",
            "p_pa": 1.9e6,
            "T_K": 253.15,
            "ref_rho_kg_m3": "",
            "notes": "Compares backend.density_from_pT(p,T).",
        },
        {
            "point_id": "mixture_rhoe_example",
            "mode": "mixture_rhoe",
            "source": "replace_with_CoolProp_REFPROP_NIST_or_project_table",
            "rho_kg_m3": 250.0,
            "e_j_kg": 180000.0,
            "ref_p_pa": "",
            "ref_T_K": "",
            "ref_quality": "",
            "ref_alpha": "",
            "ref_c_m_s": "",
            "notes": "Compares backend.state_from_rho_e(rho,e).",
        },
    ]


def build_surrogate_self_reference_rows(
    backend: RealFluidPropertyBackend | None = None,
    *,
    pressures_pa: Sequence[float] = (1.2e6, 1.5e6, 1.9e6, 2.3e6, 2.8e6),
    density_pT_offsets_K: Sequence[float] = (-6.0, 0.0, 6.0),
    mixture_pressure_pa: float = 1.9e6,
    qualities: Sequence[float] = (0.0, 0.01, 0.1, 0.5, 0.9, 0.99, 1.0),
) -> list[dict[str, object]]:
    """Generate a deterministic self-reference table for comparator testing.

    This table is not an external truth source.  It verifies that the CSV-based
    comparison engine and field mapping work exactly before a real reference CSV
    is substituted.
    """

    b = backend or SurrogateLCO2PropertyBackend()
    rows: list[dict[str, object]] = []
    sat = b.saturation_state(np.asarray(pressures_pa, dtype=float))
    for i, p in enumerate(pressures_pa):
        rows.append(
            {
                "point_id": f"sat_{i:03d}",
                "mode": "saturation",
                "source": "surrogate_self_reference",
                "p_pa": float(p),
                "ref_T_sat_K": float(np.ravel(sat.T_sat)[i]),
                "ref_rho_l_kg_m3": float(np.ravel(sat.rho_l)[i]),
                "ref_rho_v_kg_m3": float(np.ravel(sat.rho_v)[i]),
                "ref_e_l_j_kg": float(np.ravel(sat.e_l)[i]),
                "ref_e_v_j_kg": float(np.ravel(sat.e_v)[i]),
                "ref_h_lv_j_kg": float(np.ravel(sat.h_lv)[i]),
                "notes": "self-reference comparator check; not design data",
            }
        )
        T_sat = float(np.ravel(sat.T_sat)[i])
        for j, dT in enumerate(density_pT_offsets_K):
            T = T_sat + float(dT)
            rho = float(b.density_from_pT(np.array([float(p)]), np.array([T]))[0])
            rows.append(
                {
                    "point_id": f"pT_{i:03d}_{j:03d}",
                    "mode": "density_pT",
                    "source": "surrogate_self_reference",
                    "p_pa": float(p),
                    "T_K": T,
                    "ref_rho_kg_m3": rho,
                    "notes": "self-reference comparator check; not design data",
                }
            )

    sat_m = b.saturation_state(np.array([float(mixture_pressure_pa)]))
    rho_l = float(np.ravel(sat_m.rho_l)[0])
    rho_v = float(np.ravel(sat_m.rho_v)[0])
    e_l = float(np.ravel(sat_m.e_l)[0])
    e_v = float(np.ravel(sat_m.e_v)[0])
    for k, q in enumerate(qualities):
        qf = float(q)
        rho_mix = 1.0 / ((1.0 - qf) / rho_l + qf / rho_v)
        e_mix = (1.0 - qf) * e_l + qf * e_v
        state = b.state_from_rho_e(np.array([rho_mix]), np.array([e_mix]))
        rows.append(
            {
                "point_id": f"rhoe_{k:03d}",
                "mode": "mixture_rhoe",
                "source": "surrogate_self_reference",
                "rho_kg_m3": rho_mix,
                "e_j_kg": e_mix,
                "ref_p_pa": float(state.p[0]),
                "ref_T_K": float(state.T[0]),
                "ref_quality": float(state.quality[0]),
                "ref_alpha": float(state.alpha[0]),
                "ref_c_m_s": float(state.c[0]),
                "notes": "self-reference comparator check; not design data",
            }
        )
    return rows


def _expected_pairs_for_row(row: Mapping[str, object], evaluated: Mapping[str, float]) -> list[tuple[str, float, float]]:
    pairs: list[tuple[str, float, float]] = []
    for ref_key, eval_key in (
        ("ref_T_sat_K", "T_sat_K"),
        ("ref_rho_l_kg_m3", "rho_l_kg_m3"),
        ("ref_rho_v_kg_m3", "rho_v_kg_m3"),
        ("ref_e_l_j_kg", "e_l_j_kg"),
        ("ref_e_v_j_kg", "e_v_j_kg"),
        ("ref_h_lv_j_kg", "h_lv_j_kg"),
        ("ref_rho_kg_m3", "rho_kg_m3"),
        ("ref_p_pa", "p_pa"),
        ("ref_T_K", "T_K"),
        ("ref_quality", "quality"),
        ("ref_alpha", "alpha"),
        ("ref_c_m_s", "c_m_s"),
    ):
        ref = _to_float(row.get(ref_key))
        if math.isfinite(ref) and eval_key in evaluated:
            pairs.append((eval_key, ref, evaluated[eval_key]))
    return pairs


def evaluate_reference_row(backend: RealFluidPropertyBackend, row: Mapping[str, object]) -> dict[str, float]:
    """Evaluate one reference row with the selected backend."""

    mode = str(row.get("mode", "")).strip().lower()
    if mode == "saturation":
        p = _to_float(row.get("p_pa"))
        sat = backend.saturation_state(np.array([p]))
        return {
            "T_sat_K": float(sat.T_sat[0]),
            "rho_l_kg_m3": float(sat.rho_l[0]),
            "rho_v_kg_m3": float(sat.rho_v[0]),
            "e_l_j_kg": float(sat.e_l[0]),
            "e_v_j_kg": float(sat.e_v[0]),
            "h_lv_j_kg": float(sat.h_lv[0]),
        }
    if mode == "density_pt":
        p = _to_float(row.get("p_pa"))
        T = _to_float(row.get("T_K"))
        rho = backend.density_from_pT(np.array([p]), np.array([T]))
        return {"rho_kg_m3": float(rho[0])}
    if mode == "mixture_rhoe":
        rho = _to_float(row.get("rho_kg_m3"))
        e = _to_float(row.get("e_j_kg"))
        state = backend.state_from_rho_e(np.array([rho]), np.array([e]))
        return {
            "p_pa": float(state.p[0]),
            "T_K": float(state.T[0]),
            "quality": float(state.quality[0]),
            "alpha": float(state.alpha[0]),
            "c_m_s": float(state.c[0]),
        }
    raise ValueError(f"unsupported reference row mode: {mode!r}")


def compare_backend_to_reference_rows(
    backend: RealFluidPropertyBackend,
    rows: Sequence[Mapping[str, object]],
    *,
    config: ExternalReferenceComparisonConfig | None = None,
) -> list[dict[str, object]]:
    """Compare one backend against CSV-like reference rows."""

    cfg = config or ExternalReferenceComparisonConfig()
    results: list[dict[str, object]] = []
    for idx, row in enumerate(rows):
        point_id = str(row.get("point_id") or f"row_{idx:04d}")
        mode = str(row.get("mode", ""))
        source = str(row.get("source", ""))
        try:
            evaluated = evaluate_reference_row(backend, row)
            pairs = _expected_pairs_for_row(row, evaluated)
            if len(pairs) == 0:
                results.append(
                    {
                        "point_id": point_id,
                        "mode": mode,
                        "source": source,
                        "backend": backend.name,
                        "quantity": "__row__",
                        "reference_value": "",
                        "evaluated_value": "",
                        "abs_error": "",
                        "rel_error": "",
                        "tolerance": "",
                        "pass": False,
                        "error": "no comparable ref_* fields were provided",
                    }
                )
                continue
            for quantity, ref, val in pairs:
                tol = cfg.tolerance_for(quantity)
                abs_err = abs(val - ref)
                rel_err = abs_err / max(abs(ref), 1.0e-300)
                threshold = tol.threshold(ref)
                results.append(
                    {
                        "point_id": point_id,
                        "mode": mode,
                        "source": source,
                        "backend": backend.name,
                        "quantity": quantity,
                        "reference_value": ref,
                        "evaluated_value": val,
                        "abs_error": abs_err,
                        "rel_error": rel_err,
                        "tolerance": threshold,
                        "pass": abs_err <= threshold,
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "point_id": point_id,
                    "mode": mode,
                    "source": source,
                    "backend": backend.name,
                    "quantity": "__row__",
                    "reference_value": "",
                    "evaluated_value": "",
                    "abs_error": "",
                    "rel_error": "",
                    "tolerance": "",
                    "pass": False,
                    "error": str(exc),
                }
            )
    return results


def summarize_reference_comparison(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Summarize external-reference comparison results."""

    comparable = [r for r in results if str(r.get("quantity")) != "__row__"]
    failed = [r for r in results if not bool(r.get("pass"))]
    by_quantity: dict[str, dict[str, float | int]] = {}
    for row in comparable:
        q = str(row.get("quantity"))
        bucket = by_quantity.setdefault(q, {"count": 0, "max_abs_error": 0.0, "max_rel_error": 0.0})
        bucket["count"] = int(bucket["count"]) + 1
        bucket["max_abs_error"] = max(float(bucket["max_abs_error"]), _to_float(row.get("abs_error"), 0.0))
        bucket["max_rel_error"] = max(float(bucket["max_rel_error"]), _to_float(row.get("rel_error"), 0.0))
    return {
        "comparison_count": len(comparable),
        "failed_count": len(failed),
        "overall_pass": len(comparable) > 0 and len(failed) == 0,
        "by_quantity": by_quantity,
    }


def generate_external_reference_artifacts(
    output_dir: str | Path,
    *,
    backend_name: str = "surrogate_lco2",
    external_reference_csv: str | Path | None = None,
    config: ExternalReferenceComparisonConfig | None = None,
) -> dict[str, object]:
    """Generate Ver.0.5.2 optional-backend and reference-comparison artifacts."""

    cfg = config or ExternalReferenceComparisonConfig()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    template_path = out_dir / "external_reference_template_v0_5_2.csv"
    _write_csv(template_path, reference_table_template_rows(), REFERENCE_COLUMNS)

    backend = make_property_backend(backend_name)
    self_reference_rows = build_surrogate_self_reference_rows(SurrogateLCO2PropertyBackend())
    self_reference_path = out_dir / "surrogate_self_reference_v0_5_2.csv"
    _write_csv(self_reference_path, self_reference_rows, REFERENCE_COLUMNS)

    if external_reference_csv is None:
        reference_rows: list[dict[str, object]] = self_reference_rows
        reference_source_path = self_reference_path
        reference_mode = "surrogate_self_reference"
    else:
        reference_source_path = Path(external_reference_csv)
        reference_rows = _read_csv(reference_source_path)  # type: ignore[assignment]
        reference_mode = "external_reference_csv"

    comparison_rows = compare_backend_to_reference_rows(backend, reference_rows, config=cfg)
    comparison_path = out_dir / "external_reference_comparison_v0_5_2.csv"
    _write_csv(comparison_path, comparison_rows, RESULT_COLUMNS + ("error",))

    summary = summarize_reference_comparison(comparison_rows)
    availability = property_backend_availability()
    optional_backend_status = {
        "surrogate_lco2": {"available": True, "action": "verified_by_default"},
        "coolprop_co2": {
            "available": bool(availability.get("coolprop_co2")),
            "action": "available_for_direct_reference_comparison" if availability.get("coolprop_co2") else "skipped_optional_dependency_missing",
        },
        "refprop_co2": {
            "available": bool(availability.get("refprop_co2")),
            "action": "available_for_user_configured_adapter" if availability.get("refprop_co2") else "skipped_optional_dependency_missing_or_unconfigured",
        },
    }

    metrics = {
        "version": cfg.version,
        "backend_name": backend.name,
        "reference_mode": reference_mode,
        "reference_source_path": str(reference_source_path),
        "config": asdict(cfg),
        "optional_backend_status": optional_backend_status,
        "comparison_summary": summary,
        "overall_pass": bool(summary.get("overall_pass")),
        "paths": {
            "template_csv": str(template_path),
            "surrogate_self_reference_csv": str(self_reference_path),
            "comparison_csv": str(comparison_path),
            "metrics_json": str(out_dir / "external_reference_comparison_metrics_v0_5_2.json"),
            "report_md": str(out_dir / "external_reference_comparison_report_v0_5_2.md"),
        },
    }
    Path(metrics["paths"]["metrics_json"]).write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")  # type: ignore[index]

    lines = [
        "# External property reference comparison report Ver.0.5.2",
        "",
        f"overall_pass: `{str(metrics['overall_pass']).lower()}`",
        "",
        "## Scope",
        "",
        "Ver.0.5.2 separates two questions:",
        "",
        "1. Is an optional backend available without becoming a hard dependency?",
        "2. Does a selected backend match an archived reference table over the required thermodynamic states?",
        "",
        "The default artifact uses a surrogate self-reference table only to verify the comparison machinery. It is not a certified LCO2 property reference.",
        "",
        "## Optional backend status",
        "",
        "| Backend | Available | Action |",
        "|---|---:|---|",
    ]
    for name, status in optional_backend_status.items():
        lines.append(f"| {name} | {str(status['available']).lower()} | {status['action']} |")
    lines.extend(
        [
            "",
            "## Reference comparison summary",
            "",
            f"- Backend evaluated: `{backend.name}`",
            f"- Reference mode: `{reference_mode}`",
            f"- Comparable quantities: `{summary['comparison_count']}`",
            f"- Failed comparisons: `{summary['failed_count']}`",
            "",
            "| Quantity | Count | Max abs error | Max rel error |",
            "|---|---:|---:|---:|",
        ]
    )
    for quantity, bucket in dict(summary["by_quantity"]).items():
        lines.append(
            f"| {quantity} | {int(bucket['count'])} | {float(bucket['max_abs_error']):.6e} | {float(bucket['max_rel_error']):.6e} |"
        )
    lines.extend(
        [
            "",
            "## Generated files",
            "",
            f"- External reference template: `{template_path.name}`",
            f"- Surrogate self-reference sample: `{self_reference_path.name}`",
            f"- Comparison result: `{comparison_path.name}`",
            f"- Metrics JSON: `{Path(metrics['paths']['metrics_json']).name}`",  # type: ignore[index]
            "",
            "## Gate interpretation",
            "",
            "- PASS with the surrogate self-reference means the comparison engine and backend factory are working.",
            "- It does not certify LCO2 thermodynamic values.",
            "- For design use, replace the self-reference CSV with a project-approved CoolProp/REFPROP/NIST/vendor table and archive the resulting comparison CSV/report.",
            "",
        ]
    )
    Path(metrics["paths"]["report_md"]).write_text("\n".join(lines), encoding="utf-8")  # type: ignore[index]
    return metrics
