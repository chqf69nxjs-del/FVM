from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from liquid_gas_transient.reporting_boundary_reflection_verification import (
    generate_boundary_reflection_verification_report,
)


def _write_fixture(root: Path, *, design_status: str = "not_approved_for_design_use") -> tuple[Path, Path]:
    rows = []
    for boundary, expected in (("rigid_wall", 1.0), ("fixed_pressure", -1.0)):
        for n, error, arrival, residual, leakage, waveform in (
            (50, 0.20, 0.01 if boundary == "fixed_pressure" else 1.0e-5, 0.06 if boundary == "fixed_pressure" else 0.0, 0.12, 0.35),
            (100, 0.15, 0.008 if boundary == "fixed_pressure" else 1.5e-5, 0.055 if boundary == "fixed_pressure" else 0.0, 0.03, 0.17),
            (200, 0.11, 0.0082 if boundary == "fixed_pressure" else 1.8e-5, 0.049 if boundary == "fixed_pressure" else 0.0, 0.005, 0.0),
        ):
            groups = "mesh_comparison"
            if n == 100:
                groups += ";cfl_comparison"
            rows.append(
                {
                    "case_id": f"{boundary}_n{n:04d}_cfl050",
                    "boundary_kind": boundary,
                    "comparison_groups": groups,
                    "n_cells": n,
                    "dx_m": 100.0 / n,
                    "cfl": 0.5,
                    "pressure_reflection_coefficient": expected * (1.0 - error),
                    "pressure_reflection_magnitude_error": error,
                    "reflected_arrival_time_relative_error": arrival,
                    "boundary_residual": residual,
                    "reflected_characteristic_leakage_ratio": leakage,
                    "waveform_l2_difference_vs_finest": waveform,
                    "budget_mass_relative_residual": 0.0,
                    "energy_budget_balance_relative_residual": -3.0e-16,
                    "phase_vapor_mass_balance_relative_residual": 0.0,
                    "remained_single_phase": True,
                }
            )
        rows.append(
            {
                **rows[-2],
                "case_id": f"{boundary}_n0100_cfl025",
                "comparison_groups": "cfl_comparison",
                "cfl": 0.25,
            }
        )

    metrics = {
        "case_name": "coolprop_boundary_reflection_sweep",
        "output_version": "coolprop_boundary_reflection_sweep_v1",
        "overall_sweep_execution_pass": True,
        "unique_run_count": 8,
        "property_backend_design_status": design_status,
        "generated_comparison_plots": ["reflection_error.png"],
        "mesh_observations": {
            "rigid_wall": {"overall_classification": "mixed_behavior"},
            "fixed_pressure": {"overall_classification": "mixed_behavior"},
        },
    }
    metrics_path = root / "coolprop_boundary_reflection_sweep_sweep_metrics.json"
    summary_path = root / "coolprop_boundary_reflection_sweep_sweep_summary.csv"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (root / "reflection_error.png").write_bytes(b"synthetic-png")
    case_dir = root / "rigid_wall_n0050_cfl050"
    case_dir.mkdir()
    (case_dir / "case_metrics.json").write_text("{}\n", encoding="utf-8")
    return metrics_path, summary_path


def test_report_and_manifest_are_generated_from_existing_artifacts(tmp_path: Path) -> None:
    metrics_path, summary_path = _write_fixture(tmp_path)
    report_path = tmp_path / "coolprop_boundary_reflection_verification_report_v1.md"
    manifest_path = tmp_path / "coolprop_boundary_reflection_verification_manifest_v1.json"

    result = generate_boundary_reflection_verification_report(
        sweep_metrics_path=metrics_path,
        sweep_summary_path=summary_path,
        output_path=report_path,
        manifest_path=manifest_path,
        artifact_root=tmp_path,
    )

    assert report_path.is_file() and report_path.stat().st_size > 0
    assert manifest_path.is_file() and manifest_path.stat().st_size > 0
    report = report_path.read_text(encoding="utf-8")
    assert "Numerical Verification Report" in report
    assert "physical Validation = false" in report
    assert "not_approved_for_design_use" in report
    assert "mixed_behavior" in report
    assert "n=200 is a comparison reference, not an exact solution" in report
    assert "coolprop_boundary_reflection_ci_light_v1" in report
    assert result["overall_sweep_execution_pass"] is True

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["validation"] is False
    assert manifest["design_evaluation"] is False
    assert manifest["property_backend_design_status"] == "not_approved_for_design_use"
    paths = {entry["relative_path"] for entry in manifest["entries"]}
    assert report_path.name in paths
    assert metrics_path.name in paths
    assert summary_path.name in paths
    assert manifest_path.name not in paths

    report_entry = next(entry for entry in manifest["entries"] if entry["relative_path"] == report_path.name)
    expected_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    assert report_entry["sha256"] == expected_hash
    assert result["report_sha256"] == expected_hash


def test_report_rejects_unexpected_design_status(tmp_path: Path) -> None:
    metrics_path, summary_path = _write_fixture(tmp_path, design_status="approved_for_design_use")
    with pytest.raises(ValueError, match="property_backend_design_status"):
        generate_boundary_reflection_verification_report(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            output_path=tmp_path / "report.md",
            artifact_root=tmp_path,
        )


def test_report_requires_both_boundary_kinds(tmp_path: Path) -> None:
    metrics_path, summary_path = _write_fixture(tmp_path)
    with summary_path.open(encoding="utf-8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["boundary_kind"] == "rigid_wall"]
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="both boundary kinds"):
        generate_boundary_reflection_verification_report(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            output_path=tmp_path / "report.md",
            artifact_root=tmp_path,
        )
