from __future__ import annotations

import copy
import json
from pathlib import Path

from liquid_gas_transient.hem_p1_numerical_sensitivity_closeout import (
    P1_CLOSEOUT_AUTHORITY,
    P1_CLOSEOUT_FIXED_EVIDENCE_FLOOR,
    P1_CLOSEOUT_FORMAL_STATUS,
    P1_CLOSEOUT_OUTPUT_FILES,
    P1_CLOSEOUT_SCHEMA_VERSION,
    synthesize_closeout,
    write_closeout_artifacts,
)


def _formal() -> dict[str, bool]:
    return {
        "implemented": True,
        "working_vertical_slice": False,
        "verified": False,
        "accepted": False,
        "physically_validated": False,
        "design_use_accepted": False,
        "production_approved": False,
    }


def _sources():
    thresholds = []
    for multiplier in (0.5, 1.0, 2.0):
        thresholds.append({
            "threshold_multiplier": multiplier,
            "pressure_drop_threshold_relative": multiplier * 1.0e-6,
            "phase_bearing_snapshot_count": 65,
            "pressure_strictly_ahead_snapshot_count": 65,
            "pressure_strictly_ahead_all_phase_bearing_snapshots": True,
            "final_pressure_front_distance_from_outlet_m": 0.984375,
            "final_phase_front_distance_from_outlet_m": 0.234375,
            "final_pressure_phase_separation_m": 0.75,
        })
    a2 = {
        "sensitivity_execution_status": "SENSITIVITY_READY",
        "sensitivity_verdict": "ROBUST",
        "sensitivity_ready": True,
        "threshold_comparisons": thresholds,
        "physics_or_numerics_changed": False,
        "formal_status": _formal(),
    }
    a3 = {
        "sensitivity_execution_status": "FAIL_CLOSED",
        "ordering_verdict": "INCONCLUSIVE",
        "numerical_verdict": "INCONCLUSIVE",
        "physics_or_production_numerics_changed": False,
        "locked_gate6_contract_changed": False,
        "warnings": ["MESH_INDEPENDENCE_NOT_VERIFIED", "CFL_INDEPENDENCE_NOT_VERIFIED"],
        "formal_status": {
            **_formal(),
            "mesh_independent_crossing_verified": False,
            "cfl_independent_crossing_verified": False,
        },
    }
    a3f = {
        "forensic_execution_status": "FORENSICS_READY",
        "forensics_ready": True,
        "direct_failure_mechanism": "CONFIRMED",
        "unrelated_failure_case_ids": [],
        "subthreshold_case_ids": ["mesh_64_cfl_0p10", "cfl_32_0p05"],
        "fixed_crossing_evidence_floor": 1.0e-6,
        "threshold_or_tolerance_changed": False,
        "solver_or_physics_changed": False,
        "formal_status": {**_formal(), "diagnostic_evidence_ready": False},
    }
    rows = [
        ("mesh_16_cfl_0p10", 16, 0.10, "ACCEPTED_FIRST_CROSSING", 0.0009120425918744504, 2.635685786879886e-6, 0.0009120425918744504, 2.635685786879886e-6, 0.0, 0, False),
        ("baseline_32_cfl_0p10", 32, 0.10, "ACCEPTED_FIRST_CROSSING", 0.0007999325695335248, 3.7736464035873424e-6, 0.0007999325695335248, 3.7736464035873424e-6, 0.0, 0, False),
        ("mesh_64_cfl_0p10", 64, 0.10, "GUARD_FAILURE", 0.000705780654880499, 4.859613684053916e-7, 0.0007087877639382655, 3.932317391962726e-6, 3.007109057766473e-6, 1, True),
        ("cfl_32_0p05", 32, 0.05, "GUARD_FAILURE", 0.0007967173062790038, 1.1006096906989802e-7, 0.0007997273361982498, 3.220257773230569e-6, 3.0100299192459138e-6, 1, True),
        ("cfl_32_0p20", 32, 0.20, "ACCEPTED_FIRST_CROSSING", 0.0008063635641112909, 1.1110586461917749e-5, 0.0008063635641112909, 1.1110586461917749e-5, 0.0, 0, False),
    ]
    case_alignment = []
    for case_id, cells, cfl, outcome, ta, qa, tb, qb, dt, ds, shadow in rows:
        case_alignment.append({
            "case_id": case_id,
            "n_cells": cells,
            "cfl": cfl,
            "authoritative_outcome": outcome,
            "event_a_time_s": ta,
            "event_a_quality": qa,
            "event_b_time_s": tb,
            "event_b_quality": qb,
            "delta_t_a_to_b_s": dt,
            "delta_step_a_to_b": ds,
            "delta_x_front_a_to_b_m": 0.0,
            "shadow_continuation_used": shadow,
        })
    a3g = {
        "alignment_execution_status": "ALIGNMENT_READY",
        "alignment_ready": True,
        "event_definition_interpretation": "STRONGLY_SUPPORTS_DISCRETE_EVENT_ALIASING",
        "event_b_unreached_case_ids": [],
        "subthreshold_case_ids": ["mesh_64_cfl_0p10", "cfl_32_0p05"],
        "fixed_crossing_evidence_floor": 1.0e-6,
        "threshold_or_tolerance_changed": False,
        "solver_or_physics_changed": False,
        "authoritative_a3_verdict": {
            "sensitivity_execution_status": "FAIL_CLOSED",
            "ordering_verdict": "INCONCLUSIVE",
            "numerical_verdict": "INCONCLUSIVE",
        },
        "case_alignment": case_alignment,
        "formal_status": {**_formal(), "diagnostic_evidence_ready": True},
    }
    return a2, a3, a3f, a3g


def test_closeout_contract_freezes_authority_and_maturity() -> None:
    assert P1_CLOSEOUT_SCHEMA_VERSION == "stage7_p1_numerical_sensitivity_closeout_v1"
    assert P1_CLOSEOUT_FIXED_EVIDENCE_FLOOR == 1.0e-6
    assert P1_CLOSEOUT_AUTHORITY["p1_a3g"]["sha"] == "5d58291e0debe103092c4b7ebd6ad751eb5ea9bd"
    assert len(P1_CLOSEOUT_OUTPUT_FILES) == 8
    assert P1_CLOSEOUT_FORMAL_STATUS["implemented"] is True
    for key, value in P1_CLOSEOUT_FORMAL_STATUS.items():
        if key != "implemented":
            assert value is False


def test_closeout_ready_requires_robust_and_unresolved_findings_together() -> None:
    summary = synthesize_closeout(*_sources(), source_digests={"test": "a" * 64})
    assert summary["closeout_ready"] is True
    assert summary["closeout_execution_status"] == "CLOSEOUT_READY_WITH_LIMITATIONS"
    assert all(summary["gate_results"].values())
    assert summary["engineering_interpretation"]["mesh_independence"] == "NOT_VERIFIED"
    assert summary["engineering_interpretation"]["cfl_independence"] == "NOT_VERIFIED"
    assert summary["next_phase_decision"].startswith("PROCEED_TO_P2_HNE")
    metrics = summary["sensitivity_metrics"]
    assert metrics["mesh_event_a_time_span_relative_to_baseline"] > 0.20
    assert metrics["cfl_event_a_time_span_relative_to_baseline"] < 0.02


def test_closeout_fails_if_a3_is_silently_promoted() -> None:
    sources = list(_sources())
    a3 = copy.deepcopy(sources[1])
    a3["sensitivity_execution_status"] = "SENSITIVITY_READY"
    a3["ordering_verdict"] = "ROBUST"
    a3["numerical_verdict"] = "ROBUST_ORDERING_WITH_BOUNDED_NUMERICAL_SENSITIVITY"
    sources[1] = a3
    summary = synthesize_closeout(*sources)
    assert summary["closeout_ready"] is False
    assert summary["gate_results"]["A3_FAIL_CLOSED_AUTHORITY_PRESERVED"] is False


def test_closeout_fails_on_maturity_promotion() -> None:
    sources = list(_sources())
    a3g = copy.deepcopy(sources[3])
    a3g["formal_status"]["verified"] = True
    sources[3] = a3g
    summary = synthesize_closeout(*sources)
    assert summary["closeout_ready"] is False
    assert summary["gate_results"]["SOURCE_MATURITY_NOT_PROMOTED"] is False


def test_closeout_writer_retains_exact_eight_file_contract(tmp_path: Path) -> None:
    summary = synthesize_closeout(*_sources(), source_digests={"test": "b" * 64})
    paths = write_closeout_artifacts(tmp_path, summary)
    assert {path.name for path in tmp_path.iterdir()} == set(P1_CLOSEOUT_OUTPUT_FILES)
    assert paths["plot"].stat().st_size > 0
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert manifest["declared_file_count"] == 8
    assert manifest["closeout_ready"] is True
    assert manifest["closeout_sha256"] == summary["closeout_sha256"]
    assert set(manifest["payload_files"]) == set(P1_CLOSEOUT_OUTPUT_FILES) - {"closeout_manifest.json"}
