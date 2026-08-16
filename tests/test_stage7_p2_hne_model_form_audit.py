from __future__ import annotations

import json
from pathlib import Path

import pytest

from liquid_gas_transient.hne_pipeline_model_form_audit import (
    FORMAL_STATUS,
    OUTPUT_FILES,
    SCHEMA,
    ZERO_TOL,
    behavior_classification,
    front_relation,
)


def test_a1r_contract_and_maturity_boundary() -> None:
    assert SCHEMA == "stage7_p2_hne_model_form_sensitivity_a1r_v1"
    assert ZERO_TOL == pytest.approx(1.0e-18)
    assert len(OUTPUT_FILES) == 9
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["diagnostic_evidence_ready"] is True
    assert FORMAL_STATUS["p2_model_form_vertical_slice"] is True
    for key in (
        "physical_hne_vertical_slice",
        "working_vertical_slice",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False


def test_front_relation_classifies_absent_lag_equal_and_lead() -> None:
    assert front_relation(None, None) == "BOTH_ABSENT"
    assert front_relation(0.1, None) == (
        "KINETIC_ABSENT_WHILE_THERMODYNAMIC_PRESENT"
    )
    assert front_relation(None, 0.1) == (
        "KINETIC_PRESENT_WHILE_THERMODYNAMIC_ABSENT"
    )
    assert front_relation(0.2, 0.1) == "KINETIC_BEHIND"
    assert front_relation(0.2, 0.2) == "COINCIDENT"
    assert front_relation(0.1, 0.2) == "KINETIC_AHEAD"


def test_behavior_classification_retains_mixed_front_behavior() -> None:
    base = {
        "full_state_matches_hem": False,
        "maximum_absolute_signed_quality_lag": 1.0e-4,
        "onset_delay_s": 1.0e-5,
        "kinetic_absent_count": 2,
        "kinetic_behind_count": 2,
        "kinetic_only_count": 0,
        "kinetic_ahead_count": 3,
    }
    assert behavior_classification(base) == (
        "RESOLVED_ONSET_DELAY_WITH_MIXED_FRONT_LAG_AND_LEAD"
    )
    medium = dict(base)
    medium.update(
        onset_delay_s=0.0,
        kinetic_absent_count=0,
        kinetic_behind_count=0,
    )
    assert behavior_classification(medium) == (
        "NO_RESOLVED_ONSET_DELAY_WITH_TRANSIENT_FRONT_LEAD"
    )


def _generated_target() -> Path:
    target = Path("artifacts/stage7-p2-hne-model-form-sensitivity-a1r")
    if not target.exists():
        pytest.skip("focused workflow supplies generated A1R evidence")
    return target


def test_generated_a1r_summary_narrows_the_original_interpretation() -> None:
    target = _generated_target()
    summary = json.loads((target / "audit_summary.json").read_text(encoding="utf-8"))
    assert summary["audit_ready"] is True
    assert summary["execution_status"] == (
        "A1R_AUDIT_READY_WITH_CLOSURE_LIMITATION"
    )
    assert all(summary["gate_results"].values())
    assert summary["physical_hne_claim_allowed"] is False
    assert summary["interpretation"]["tau_to_zero_limit"] == (
        "BITWISE_HEM_LIMIT_RETAINED"
    )
    assert summary["interpretation"]["finite_tau_quality_behavior"] == (
        "MIXED_SIGN_TRANSPORTED_EQUILIBRIUM_DISEQUILIBRIUM"
    )
    assert summary["interpretation"]["kinetic_front_behavior"] == (
        "MIXED_LAG_AND_LEAD_UNDER_INDEPENDENT_QUALITY_TRANSPORT"
    )
    by_id = {row["model_id"]: row for row in summary["case_disequilibrium"]}
    assert by_id["HNE_TAU_MEDIUM"]["onset_delay_s"] == pytest.approx(0.0)
    assert by_id["HNE_TAU_MEDIUM"]["kinetic_ahead_count"] > 0
    assert by_id["HNE_TAU_SLOW"]["onset_delay_s"] > 0.0
    assert by_id["HNE_TAU_SLOW"]["kinetic_ahead_count"] > 0
    assert (
        by_id["HNE_TAU_SLOW"]["kinetic_absent_count"]
        + by_id["HNE_TAU_SLOW"]["kinetic_behind_count"]
        > 0
    )
    for model_id in ("HNE_TAU_MEDIUM", "HNE_TAU_SLOW"):
        assert by_id[model_id]["minimum_signed_quality_lag"] < 0.0
        assert by_id[model_id]["maximum_signed_quality_lag"] > 0.0
        assert by_id[model_id]["hydrodynamic_state_matches_hem"] is True


def test_generated_a1r_exact_nine_file_manifest() -> None:
    target = _generated_target()
    assert {path.name for path in target.iterdir() if path.is_file()} == set(
        OUTPUT_FILES
    )
    summary = json.loads((target / "audit_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((target / "audit_manifest.json").read_text(encoding="utf-8"))
    assert manifest["declared_file_count"] == 9
    assert manifest["declared_file_names"] == list(OUTPUT_FILES)
    assert manifest["audit_ready"] is True
    assert manifest["audit_sha256"] == summary["audit_sha256"]
    assert manifest["physical_hne_claim_allowed"] is False
    assert set(manifest["payload_files"]) == set(OUTPUT_FILES) - {
        "audit_manifest.json"
    }
    for item in manifest["payload_files"].values():
        assert item["size_bytes"] > 0
        assert len(item["sha256"]) == 64
