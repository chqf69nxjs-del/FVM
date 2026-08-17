from __future__ import annotations

import json
from pathlib import Path

import pytest

from liquid_gas_transient.hne_shadow_pipeline_closeout import (
    CLOSEOUT_OUTCOME,
    COUPLING_AUTHORITY,
    FORMAL_STATUS,
    HNEShadowPipelineCloseoutError,
    NEXT_AUTHORIZED_ACTION,
    OUTPUT_FILES,
    RETAINED_LIMITATIONS,
    SOURCE_A2_3_ANALYSIS_SHA256,
    SOURCE_A2_3_ARTIFACT_ID,
    SOURCE_A2_3_ARTIFACT_SHA256,
    SOURCE_A2_3_SHA,
    SOURCE_A2_3_WORKFLOW_RUN_ID,
    build_summary,
    execute,
    frozen_authority_record,
)


CLEAN_PROVENANCE = {
    "analysis_source_git_sha": "closeout-head",
    "checkout_git_sha": "closeout-head",
    "git_status_porcelain": "",
}


def test_frozen_source_authority_is_exact() -> None:
    authority = frozen_authority_record()
    source = authority["source"]
    assert source["a2_3_sha"] == SOURCE_A2_3_SHA
    assert source["workflow_run_id"] == SOURCE_A2_3_WORKFLOW_RUN_ID
    assert source["artifact_id"] == SOURCE_A2_3_ARTIFACT_ID
    assert source["artifact_sha256"] == SOURCE_A2_3_ARTIFACT_SHA256
    assert source["analysis_sha256"] == SOURCE_A2_3_ANALYSIS_SHA256
    assert source["workflow_conclusion"] == "success"
    assert source["focused_test_result"] == {
        "tests": 5,
        "skipped": 0,
        "failures": 0,
        "errors": 0,
    }


def test_closeout_keeps_all_coupling_and_maturity_gates_closed() -> None:
    summary = build_summary(provenance=CLEAN_PROVENANCE)
    assert summary["closeout_ready"] is True
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert summary["closeout_outcome"] == CLOSEOUT_OUTCOME
    assert summary["next_authorized_action"] == NEXT_AUTHORIZED_ACTION
    assert summary["retained_limitations"] == list(RETAINED_LIMITATIONS)
    assert summary["coupling_authority"] == COUPLING_AUTHORITY
    assert summary["formal_status"] == FORMAL_STATUS
    for key in (
        "hydrodynamic_coupling_allowed",
        "physical_hne_vertical_slice",
        "working_vertical_slice",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert summary["formal_status"][key] is False
    for key in (
        "p_hne_to_flux",
        "T_hne_to_flux",
        "alpha_hne_to_flux",
        "c_hne_to_flux_or_cfl",
        "hne_boundary_characteristics_allowed",
        "hydrodynamic_coupling_allowed",
    ):
        assert summary["coupling_authority"][key] is False


def test_dirty_or_mismatched_runtime_provenance_fails_closed() -> None:
    with pytest.raises(HNEShadowPipelineCloseoutError, match="CLEAN_RUNTIME_PROVENANCE"):
        build_summary(
            provenance={
                "analysis_source_git_sha": "one-sha",
                "checkout_git_sha": "another-sha",
                "git_status_porcelain": "?? unexpected.txt",
            }
        )


def test_execute_writes_exact_reproducible_closeout_evidence(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    result_one = execute(first, provenance=CLEAN_PROVENANCE)
    result_two = execute(second, provenance=CLEAN_PROVENANCE)

    assert result_one["closeout_ready"] is True
    assert result_two["closeout_ready"] is True
    assert result_one["authority_sha256"] == result_two["authority_sha256"]
    assert {path.name for path in first.iterdir()} == set(OUTPUT_FILES)
    assert {path.name for path in second.iterdir()} == set(OUTPUT_FILES)
    for name in OUTPUT_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    summary = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert summary["closeout_ready"] is True
    assert manifest["declared_file_count"] == 3
    assert manifest["declared_file_names"] == list(OUTPUT_FILES)
    assert set(manifest["payload_files"]) == {
        "summary.json",
        "operator_report.md",
    }
    assert manifest["authority_sha256"] == summary["authority_sha256"]
    assert manifest["source_a2_3_sha"] == SOURCE_A2_3_SHA
    assert manifest["hydrodynamic_coupling_allowed"] is False


def test_closeout_authorizes_contract_design_only() -> None:
    summary = build_summary(provenance=CLEAN_PROVENANCE)
    claims = summary["claims"]
    assert claims["finite_pipeline_shadow_execution"] == (
        "SUPPORTED_BY_FOCUSED_A2_3_EVIDENCE"
    )
    assert claims["physical_co2_prediction"] == "NOT_CLAIMED"
    assert claims["nonequilibrium_acoustic_closure"] == "NOT_ESTABLISHED"
    assert claims["hydrodynamic_hne_coupling"] == "NOT_AUTHORIZED"
    assert summary["next_authorized_action"] == (
        "PROCEED_TO_A2_4_1_NONEQUILIBRIUM_ACOUSTIC_CLOSURE_CONTRACT"
    )
