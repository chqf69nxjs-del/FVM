from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liquid_gas_transient.reporting_controlled_pressure_ramp_verification import (
    MANIFEST_VERSION,
    REPORT_VERSION,
    generate_controlled_pressure_ramp_verification_report,
)


def _write_sweep_artifacts(root: Path) -> tuple[Path, Path]:
    metrics = {
        "case_name": "coolprop_controlled_pressure_ramp_sweep",
        "output_version": "coolprop_controlled_pressure_ramp_sweep_v1",
        "property_backend_design_status": "not_approved_for_design_use",
        "unique_run_count": 4,
        "overall_sweep_execution_pass": True,
        "mesh_observation": {"overall_classification": "mixed_behavior"},
        "generated_comparison_plots": ["comparison.png"],
    }
    metrics_path = root / "sweep_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    rows = []
    for case_id, n_cells, cfl, groups, scale in (
        ("n0050_cfl050", 50, 0.5, "mesh_comparison", 3.0),
        ("n0100_cfl025", 100, 0.25, "cfl_comparison", 2.0),
        ("n0100_cfl050", 100, 0.5, "mesh_comparison;cfl_comparison", 2.0),
        ("n0200_cfl050", 200, 0.5, "mesh_comparison", 1.0),
    ):
        rows.append(
            {
                "case_id": case_id,
                "comparison_groups": groups,
                "n_cells": n_cells,
                "dx_m": 100.0 / n_cells,
                "cfl": cfl,
                "wave_speed_relative_error": 1.0e-3 * scale,
                "abs_common_boundary_launch_delay_s": 1.0e-3 * scale,
                "p10_arrival_relative_error_mean": 0.02 * scale,
                "p50_arrival_relative_error_mean": 0.01 * scale,
                "p90_arrival_relative_error_mean": 0.04 * scale,
                "primary_peak_amplitude_error": 1.0e-7 * scale,
                "primary_opposite_direction_leakage_ratio": 5.0e-6,
                "budget_mass_relative_residual": 0.0,
                "energy_budget_balance_relative_residual": 1.0e-16,
                "phase_vapor_mass_balance_relative_residual": 0.0,
                "remained_single_phase": True,
                "execution_pass": True,
                "analysis_complete": True,
                "total_case_runtime_s": 10.0 * scale,
            }
        )
    summary_path = root / "sweep_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    (root / "comparison.png").write_bytes(b"synthetic png bytes")
    per_run = root / "n0050_cfl050"
    per_run.mkdir()
    (per_run / "metrics.json").write_text("{}\n", encoding="utf-8")
    return metrics_path, summary_path


def test_generate_controlled_pressure_ramp_verification_report(tmp_path: Path) -> None:
    metrics_path, summary_path = _write_sweep_artifacts(tmp_path)
    report_path = tmp_path / "report.md"
    manifest_path = tmp_path / "manifest.json"

    result = generate_controlled_pressure_ramp_verification_report(
        sweep_metrics_path=metrics_path,
        sweep_summary_path=summary_path,
        output_path=report_path,
        manifest_path=manifest_path,
        artifact_root=tmp_path,
    )

    assert report_path.is_file() and report_path.stat().st_size > 0
    assert manifest_path.is_file() and manifest_path.stat().st_size > 0
    assert result["overall_sweep_execution_pass"] is True
    assert result["property_backend_design_status"] == "not_approved_for_design_use"
    assert result["artifact_count"] >= 5
    assert len(result["report_sha256"]) == 64

    report = report_path.read_text(encoding="utf-8")
    assert "Controlled Pressure Ramp Numerical Verification Report" in report
    assert "CI-light regression profile" in report
    assert "physical Validation = false" in report

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == MANIFEST_VERSION
    assert manifest["report_version"] == REPORT_VERSION
    assert manifest["validation"] is False
    assert manifest["design_evaluation"] is False
    assert manifest["acceptance_gate"] is False
    assert manifest["property_backend_design_status"] == "not_approved_for_design_use"
    paths = {entry["relative_path"] for entry in manifest["entries"]}
    assert "report.md" in paths
    assert "manifest.json" not in paths


def test_report_rejects_unapproved_status_change(tmp_path: Path) -> None:
    metrics_path, summary_path = _write_sweep_artifacts(tmp_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["property_backend_design_status"] = "approved_for_design_use"
    metrics_path.write_text(json.dumps(metrics) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="property_backend_design_status"):
        generate_controlled_pressure_ramp_verification_report(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            output_path=tmp_path / "report.md",
            artifact_root=tmp_path,
        )


def test_report_requires_four_successful_rows(tmp_path: Path) -> None:
    metrics_path, summary_path = _write_sweep_artifacts(tmp_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["overall_sweep_execution_pass"] = False
    metrics_path.write_text(json.dumps(metrics) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="successful sweep"):
        generate_controlled_pressure_ramp_verification_report(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            output_path=tmp_path / "report.md",
            artifact_root=tmp_path,
        )
