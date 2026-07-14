from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liquid_gas_transient.controlled_pressure_ramp_sweep_traceability import (
    backfill_controlled_pressure_ramp_sweep_traceability,
)


def _write_artifacts(root: Path, versions: tuple[str, ...] = ("8.0.0",) * 4) -> tuple[Path, Path, Path]:
    case_ids = (
        "n0050_cfl050",
        "n0100_cfl025",
        "n0100_cfl050",
        "n0200_cfl050",
    )
    rows = []
    for case_id, version in zip(case_ids, versions):
        run_dir = root / case_id
        run_dir.mkdir(parents=True)
        (run_dir / f"case_{case_id}_metrics.json").write_text(
            json.dumps(
                {
                    "property_backend_name": "coolprop_co2",
                    "coolprop_version": version,
                    "property_backend_design_status": "not_approved_for_design_use",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        rows.append(
            {
                "case_id": case_id,
                "comparison_groups": (
                    "mesh_comparison;cfl_comparison"
                    if case_id == "n0100_cfl050"
                    else "cfl_comparison"
                    if case_id == "n0100_cfl025"
                    else "mesh_comparison"
                ),
                "n_cells": 100,
                "cfl": 0.5,
            }
        )

    metrics_path = root / "coolprop_controlled_pressure_ramp_sweep_sweep_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "unique_run_count": 4,
                "summary_rows": rows,
                "cfl_observation": {"rows": []},
                "property_backend_design_status": "not_approved_for_design_use",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = root / "coolprop_controlled_pressure_ramp_sweep_sweep_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report_path = root / "coolprop_controlled_pressure_ramp_sweep_sweep_report.md"
    report_path.write_text(
        "# report\n\n- formal_accuracy_threshold_applied: false\n",
        encoding="utf-8",
    )
    return metrics_path, summary_path, report_path


def test_backfill_updates_aggregate_identity_without_solver_rerun(tmp_path: Path) -> None:
    metrics_path, summary_path, report_path = _write_artifacts(tmp_path)
    result = backfill_controlled_pressure_ramp_sweep_traceability(
        sweep_metrics_path=metrics_path,
        sweep_summary_path=summary_path,
        sweep_report_path=report_path,
        artifact_root=tmp_path,
    )

    assert result["property_backend_name"] == "coolprop_co2"
    assert result["coolprop_version"] == "8.0.0"
    assert result["solver_rerun"] is False
    assert result["numerical_results_changed"] is False

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["property_backend_name"] == "coolprop_co2"
    assert metrics["coolprop_version"] == "8.0.0"
    assert len(metrics["cfl_observation"]["rows"]) == 2

    with summary_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["property_backend_name"] for row in rows} == {"coolprop_co2"}
    assert {row["coolprop_version"] for row in rows} == {"8.0.0"}

    report = report_path.read_text(encoding="utf-8")
    assert "- property_backend_name: coolprop_co2" in report
    assert "- coolprop_version: 8.0.0" in report


def test_backfill_rejects_inconsistent_backend_versions(tmp_path: Path) -> None:
    metrics_path, summary_path, report_path = _write_artifacts(
        tmp_path,
        versions=("8.0.0", "8.0.0", "8.1.0", "8.0.0"),
    )
    with pytest.raises(ValueError, match="inconsistent coolprop_version"):
        backfill_controlled_pressure_ramp_sweep_traceability(
            sweep_metrics_path=metrics_path,
            sweep_summary_path=summary_path,
            sweep_report_path=report_path,
            artifact_root=tmp_path,
        )
