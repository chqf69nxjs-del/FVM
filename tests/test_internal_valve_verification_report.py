from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from liquid_gas_transient.reporting_internal_valve_verification import (
    MANIFEST_VERSION,
    REPORT_VERSION,
    generate_internal_valve_verification_report,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(item: str, n: int, cfl: float) -> dict:
    role = {
        "V-012A": "preservation_sentinel",
        "V-012B": "finite_opening",
        "V-012C": "opening_ramp",
        "V-012D": "closing_ramp_complete_closure",
    }[item]
    groups = "preservation_sentinel" if item == "V-012A" else (
        "mesh_comparison;cfl_comparison"
        if n == 100 and cfl == 0.5
        else "cfl_comparison"
        if n == 100 and cfl == 0.25
        else "mesh_comparison"
    )
    p50 = {
        "V-012B": {50: 4.56e-3, 100: 3.08e-3, 200: 2.15e-3},
        "V-012C": {50: 1.90e-3, 100: 7.53e-4, 200: 1.13e-4},
        "V-012D": {50: 4.87e-3, 100: 3.03e-3, 200: 2.14e-3},
    }
    peak = {"V-012B": 108.0, "V-012C": 276.0, "V-012D": 194.0}
    row = {
        "case_id": f"{item.lower().replace('-', '')}_n{n:04d}_cfl{str(cfl).replace('.', 'p')}",
        "verification_item": item,
        "case_role": role,
        "n_cells": n,
        "dx_m": 100.0 / n,
        "cfl": cfl,
        "comparison_groups": groups,
        "execution_pass": True,
        "analysis_complete": True,
        "remained_single_phase": True,
        "runtime_s": float(n) / 10.0 / cfl,
        "step_count": int(n / cfl),
        "property_backend_name": "coolprop_co2",
        "coolprop_version": "8.0.0",
        "property_backend_design_status": "not_approved_for_design_use",
        "budget_mass_relative_residual": 0.0,
        "energy_budget_balance_relative_residual": 2.0e-16,
        "phase_vapor_mass_balance_relative_residual": 0.0,
        "max_abs_mass_flux_mismatch_kg_m2_s": 0.0,
        "max_abs_flux_q_minus_applied_q_m3_s": 1.0e-20,
        "max_applied_q_m3_s_extracted": 0.0,
    }
    if item != "V-012A":
        observed_n = n if cfl == 0.5 else 100
        row.update(
            {
                "near_probe_characteristic_p50_time_offset_max_abs_s": p50[item][observed_n],
                "near_probe_characteristic_peak_abs_mean_pa": peak[item],
                "near_probe_characteristic_max_leakage_ratio": 1.5e-6,
                "max_applied_q_m3_s_extracted": {
                    "V-012B": 3.53e-5,
                    "V-012C": 4.31e-5,
                    "V-012D": 7.07e-5,
                }[item],
            }
        )
    if item == "V-012D":
        row.update(
            {
                "post_closure_hydraulic_separation_fraction_extracted": 1.0,
                "post_closure_no_flow_direction_fraction_extracted": 1.0,
                "max_abs_post_closure_flux_derived_q_m3_s_extracted": 3.0e-25,
                "max_abs_post_closure_mass_flux_kg_m2_s_extracted": 4.0e-21,
                "max_abs_post_closure_energy_flux_w_m2_extracted": 0.0,
                "max_abs_post_closure_vapor_mass_flux_kg_m2_s_extracted": 0.0,
            }
        )
    return row


def _rows() -> list[dict]:
    rows = [_row("V-012A", 50, 0.5)]
    for item in ("V-012B", "V-012C", "V-012D"):
        rows.extend(
            [
                _row(item, 50, 0.5),
                _row(item, 100, 0.25),
                _row(item, 100, 0.5),
                _row(item, 200, 0.5),
            ]
        )
    return rows


def _write_inputs(root: Path) -> tuple[Path, Path, Path]:
    rows = _rows()
    metrics_path = root / "v012_internal_valve_mesh_cfl_sweep_metrics.json"
    summary_path = root / "v012_internal_valve_mesh_cfl_sweep_summary.csv"
    ci_path = root / "coolprop_internal_valve_ci_light_result.json"
    metrics = {
        "case_name": "v012_internal_valve_mesh_cfl_sweep",
        "output_version": "v012_internal_valve_mesh_cfl_sweep_v1",
        "planned_run_count": 13,
        "executed_run_count": 13,
        "overall_sweep_execution_pass": True,
        "aggregate_trend_analysis_complete": True,
        "comparison_plots_complete": True,
        "property_backend_name": "coolprop_co2",
        "coolprop_version": "8.0.0",
        "property_backend_design_status": "not_approved_for_design_use",
        "generated_comparison_plots": ["timing.png", "closure.png"],
    }
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    ci_path.write_text(
        json.dumps({"overall_regression_pass": True}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "timing.png").write_bytes(b"fake png")
    (root / "closure.png").write_bytes(b"fake png")
    return metrics_path, summary_path, ci_path


def test_generate_internal_valve_report_and_manifest(tmp_path: Path) -> None:
    metrics_path, summary_path, ci_path = _write_inputs(tmp_path)
    report = tmp_path / "coolprop_internal_valve_verification_report_v1.md"
    manifest = tmp_path / "coolprop_internal_valve_verification_manifest_v1.json"
    result = generate_internal_valve_verification_report(
        sweep_metrics_path=metrics_path,
        sweep_summary_path=summary_path,
        output_path=report,
        manifest_path=manifest,
        artifact_root=tmp_path,
        ci_result_path=ci_path,
    )
    assert report.is_file()
    assert manifest.is_file()
    assert result["overall_sweep_execution_pass"] is True
    assert result["ci_light_regression_pass"] is True
    assert result["report_sha256"] == _sha256(report)
    assert result["manifest_sha256"] == _sha256(manifest)
    text = report.read_text(encoding="utf-8")
    assert "Software/numerical verification" in text
    assert "physical Validation = false" in text
    assert "V-012B: 4.5636 ms" in text
    assert "CI-light regression profile" in text
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["manifest_version"] == MANIFEST_VERSION
    assert data["report_version"] == REPORT_VERSION
    assert data["validation"] is False
    assert data["design_evaluation"] is False
    assert data["acceptance_gate"] is False
    paths = {entry["relative_path"] for entry in data["entries"]}
    assert report.name in paths
    assert metrics_path.name in paths
    assert summary_path.name in paths
    assert manifest.name not in paths


def test_report_rejects_incomplete_sweep(tmp_path: Path) -> None:
    metrics_path, summary_path, ci_path = _write_inputs(tmp_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["executed_run_count"] = 12
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")
    with pytest.raises(ValueError, match="thirteen executed"):
        generate_internal_valve_verification_report(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            output_path=tmp_path / "report.md",
            artifact_root=tmp_path,
            ci_result_path=ci_path,
        )


def test_report_rejects_failed_ci_light(tmp_path: Path) -> None:
    metrics_path, summary_path, ci_path = _write_inputs(tmp_path)
    ci_path.write_text(json.dumps({"overall_regression_pass": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="successful CI-light"):
        generate_internal_valve_verification_report(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            output_path=tmp_path / "report.md",
            artifact_root=tmp_path,
            ci_result_path=ci_path,
        )


def test_report_rejects_inconsistent_backend(tmp_path: Path) -> None:
    metrics_path, summary_path, ci_path = _write_inputs(tmp_path)
    rows = list(csv.DictReader(summary_path.open(encoding="utf-8")))
    rows[-1]["property_backend_name"] = "other_backend"
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="inconsistent or missing"):
        generate_internal_valve_verification_report(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            output_path=tmp_path / "report.md",
            artifact_root=tmp_path,
            ci_result_path=ci_path,
        )
