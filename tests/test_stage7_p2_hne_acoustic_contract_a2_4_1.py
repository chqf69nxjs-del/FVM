from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from liquid_gas_transient.hne_acoustic_contract import (
    CONTRACT_OUTCOME,
    FAIL_CLOSED_CONDITIONS,
    FORMAL_STATUS,
    HNEAcousticContractError,
    NEXT_AUTHORIZED_ACTION,
    OUTPUT_FILES,
    REGIME_ORDER,
    REQUIRED_EVIDENCE,
    SOLVER_AUTHORITY,
    SOURCE_A2_3_CLOSEOUT_ARTIFACT_ID,
    SOURCE_A2_3_CLOSEOUT_ARTIFACT_SHA256,
    SOURCE_A2_3_CLOSEOUT_RUN_ID,
    SOURCE_A2_3_CLOSEOUT_SHA,
    acoustic_contract_record,
    build_summary,
    execute,
)


CLEAN_PROVENANCE = {
    "analysis_source_git_sha": "acoustic-contract-head",
    "checkout_git_sha": "acoustic-contract-head",
    "git_status_porcelain": "",
}


def test_source_closeout_and_all_solver_authority_are_frozen() -> None:
    summary = build_summary(provenance=CLEAN_PROVENANCE)
    source = summary["source_closeout"]
    assert source["a2_3_closeout_sha"] == SOURCE_A2_3_CLOSEOUT_SHA
    assert source["a2_3_closeout_workflow_run_id"] == SOURCE_A2_3_CLOSEOUT_RUN_ID
    assert source["a2_3_closeout_artifact_id"] == SOURCE_A2_3_CLOSEOUT_ARTIFACT_ID
    assert source["a2_3_closeout_artifact_sha256"] == (
        SOURCE_A2_3_CLOSEOUT_ARTIFACT_SHA256
    )
    assert source["closeout_conclusion"] == "success"
    assert summary["solver_authority"] == SOLVER_AUTHORITY
    assert all(value is False for value in summary["solver_authority"].values())
    assert summary["contract_outcome"] == CONTRACT_OUTCOME
    assert summary["hydrodynamic_coupling_allowed"] is False if (
        "hydrodynamic_coupling_allowed" in summary
    ) else summary["solver_authority"]["hydrodynamic_coupling_allowed"] is False


def test_exact_frozen_equilibrium_and_finite_relaxation_regimes_are_declared() -> None:
    summary = build_summary(provenance=CLEAN_PROVENANCE)
    regimes = summary["regime_contracts"]
    assert summary["regime_order"] == list(REGIME_ORDER)
    assert set(regimes) == set(REGIME_ORDER)

    frozen = regimes["FROZEN_QUALITY"]
    assert frozen["frequency_ordering"] == "OMEGA_TAU_MUCH_GREATER_THAN_ONE"
    assert frozen["quality_response"] == "DELTA_Q_EQUALS_ZERO_DURING_PERTURBATION"
    assert "Q_FIXED" in frozen["thermodynamic_path"]
    assert frozen["single_real_scalar_c_authorized"] is False

    equilibrium = regimes["EQUILIBRIUM_MANIFOLD"]
    assert equilibrium["frequency_ordering"] == "OMEGA_TAU_MUCH_LESS_THAN_ONE"
    assert equilibrium["quality_response"] == (
        "Q_FOLLOWS_DECLARED_EQUILIBRIUM_MANIFOLD"
    )
    assert equilibrium["required_limit"] == (
        "TAU_TO_ZERO_OR_LOW_FREQUENCY_HEM_LIMIT"
    )
    assert equilibrium["single_real_scalar_c_authorized"] is False


def test_finite_relaxation_cannot_be_collapsed_to_an_unjustified_real_scalar() -> None:
    summary = build_summary(provenance=CLEAN_PROVENANCE)
    finite = summary["regime_contracts"]["FINITE_RELAXATION_DISPERSIVE"]
    assert finite["frequency_ordering"] == "OMEGA_TAU_ORDER_ONE"
    assert finite["single_real_scalar_c_authorized"] is False
    assert finite["derivative_contract"] == (
        "A_SINGLE_STATIC_PRESSURE_DENSITY_DERIVATIVE_IS_NOT_SUFFICIENT"
    )
    for required in (
        "ANGULAR_FREQUENCY_OR_DISTURBANCE_TIME_SCALE",
        "COMPLEX_WAVENUMBER_OR_EQUIVALENT_TRANSFER_RESPONSE",
        "PHASE_SPEED",
        "ATTENUATION_RATE",
        "FROZEN_LIMIT_RESIDUAL",
        "EQUILIBRIUM_LIMIT_RESIDUAL",
    ):
        assert required in finite["required_outputs"]
    assert (
        "COMPLEX_FINITE_RELAXATION_RESPONSE_COLLAPSED_TO_UNJUSTIFIED_REAL_SCALAR"
        in summary["fail_closed_conditions"]
    )


def test_contract_mutations_fail_closed() -> None:
    bad_path = acoustic_contract_record()
    bad_path["regime_contracts"]["FROZEN_QUALITY"]["thermodynamic_path"] = (
        "UNSPECIFIED"
    )
    with pytest.raises(HNEAcousticContractError, match="FROZEN_QUALITY_PATH_DECLARED"):
        build_summary(contract=bad_path, provenance=CLEAN_PROVENANCE)

    bad_authority = acoustic_contract_record()
    bad_authority["solver_authority"]["frozen_candidate_to_cfl"] = True
    with pytest.raises(HNEAcousticContractError, match="ALL_SOLVER_AUTHORITY_CLOSED"):
        build_summary(contract=bad_authority, provenance=CLEAN_PROVENANCE)


def test_evidence_and_maturity_boundaries_are_complete() -> None:
    summary = build_summary(provenance=CLEAN_PROVENANCE)
    assert summary["required_evidence"] == list(REQUIRED_EVIDENCE)
    assert summary["fail_closed_conditions"] == list(FAIL_CLOSED_CONDITIONS)
    assert summary["formal_status"] == FORMAL_STATUS
    assert summary["formal_status"]["implemented"] is True
    assert summary["formal_status"]["acoustic_contract_ready"] is True
    for key in (
        "frozen_acoustic_formula_implemented",
        "equilibrium_acoustic_formula_implemented",
        "finite_relaxation_dispersion_implemented",
        "finite_pipeline_acoustic_shadow_ready",
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
    assert summary["next_authorized_action"] == NEXT_AUTHORIZED_ACTION
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())


def test_execute_writes_exact_reproducible_contract_evidence(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    result_one = execute(first, provenance=CLEAN_PROVENANCE)
    result_two = execute(second, provenance=CLEAN_PROVENANCE)

    assert result_one["contract_ready"] is True
    assert result_two["contract_ready"] is True
    assert result_one["contract_authority_sha256"] == (
        result_two["contract_authority_sha256"]
    )
    assert {path.name for path in first.iterdir()} == set(OUTPUT_FILES)
    assert {path.name for path in second.iterdir()} == set(OUTPUT_FILES)
    for name in OUTPUT_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    summary = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    with (first / "regime_contracts.csv").open(encoding="utf-8", newline="") as stream:
        regime_rows = list(csv.DictReader(stream))

    assert summary["contract_ready"] is True
    assert len(summary["contract_authority_sha256"]) == 64
    assert [row["regime_id"] for row in regime_rows] == list(REGIME_ORDER)
    assert manifest["declared_file_count"] == 4
    assert manifest["declared_file_names"] == list(OUTPUT_FILES)
    assert set(manifest["payload_files"]) == {
        "summary.json",
        "regime_contracts.csv",
        "operator_report.md",
    }
    assert manifest["contract_authority_sha256"] == (
        summary["contract_authority_sha256"]
    )
    assert manifest["source_a2_3_closeout_sha"] == SOURCE_A2_3_CLOSEOUT_SHA
    assert manifest["contract_ready"] is True
    assert manifest["hydrodynamic_coupling_allowed"] is False
