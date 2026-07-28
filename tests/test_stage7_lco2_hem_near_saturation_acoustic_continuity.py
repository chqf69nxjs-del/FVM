from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from liquid_gas_transient.hem_near_saturation_acoustic_continuity import (
    APPROVAL_BOUNDARY,
    PERTURBATIONS,
    PRESSURES_PA,
    QUALITIES,
    SUBCOOLING_K,
    PR79_REFERENCE,
    execute,
)


def test_gate5_contract_is_locked() -> None:
    assert PRESSURES_PA == (2.0e6, 3.0e6, 4.0e6)
    assert SUBCOOLING_K == (5.0, 1.0, 0.1, 0.01)
    assert QUALITIES == (0.0, 1.0e-12, 1.0e-10, 1.0e-8, 1.0e-6, 1.0e-4, 1.0e-2)
    assert PERTURBATIONS == (0.0, -1.0e-10, 1.0e-10, -1.0e-8, 1.0e-8, -1.0e-6, 1.0e-6)
    assert all(value is False for value in APPROVAL_BOUNDARY.values())
    assert PR79_REFERENCE["raw_q_eq"] == 9.672588429198319e-9


@pytest.mark.installed
@pytest.mark.requires_coolprop

def test_gate5_execute_fixed_grid_and_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "gate5"
    summary = execute(output)

    assert summary["scope"] == "verification_only_0d"
    assert summary["immutable_contract"]["fvm_used"] is False
    assert summary["immutable_contract"]["boundary_used"] is False
    assert summary["immutable_contract"]["rusanov_used"] is False
    assert summary["immutable_contract"]["cfl_used"] is False
    assert summary["immutable_contract"]["sound_speed_formula_changed"] is False
    assert summary["state_record_count"] == 33
    assert summary["perturbation_record_count"] == 588
    assert summary["pr79_forensic_comparison"]["baseline_reclassified"] is False
    assert all(summary[key] is False for key in APPROVAL_BOUNDARY)

    expected = {
        "summary.json",
        "state_points.csv",
        "perturbations.csv",
        "report.md",
        "sound_speed_vs_quality.png",
        "sound_speed_vs_saturation_approach.png",
        "perturbation_sensitivity.png",
        "artifact_sha256.txt",
    }
    assert expected <= {path.name for path in output.iterdir()}

    loaded = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert loaded["state_record_count"] == 33
    assert loaded["initial_evidence_labels"]

    with (output / "state_points.csv").open(newline="", encoding="utf-8") as handle:
        states = list(csv.DictReader(handle))
    assert len(states) == 33
    endpoints = [row for row in states if row["source_state_definition"] == "PQ" and float(row["source_coordinate"]) == 0.0]
    assert len(endpoints) == 3
    assert all(row["acoustic_status"] in {"REFUSED", "FAILURE"} for row in endpoints)

    successful = [row for row in states if row["acoustic_status"] == "SUCCESS"]
    assert successful
    assert all(float(row["c_eq_m_s"]) > 0.0 for row in successful)
    assert all(float(row["c_eq_squared_m2_s2"]) > 0.0 for row in successful)

    with (output / "perturbations.csv").open(newline="", encoding="utf-8") as handle:
        perturbations = list(csv.DictReader(handle))
    assert len(perturbations) == 588
    assert {float(row["delta_rho_relative"]) for row in perturbations} == set(PERTURBATIONS)
    assert {float(row["delta_e_relative"]) for row in perturbations} == set(PERTURBATIONS)
