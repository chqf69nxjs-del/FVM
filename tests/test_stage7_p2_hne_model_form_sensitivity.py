from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.hne_pipeline_model_form_sensitivity import (
    MODEL_SPECS,
    P2_A1_FORMAL_STATUS,
    P2_A1_KINETIC_QUALITY_FLOOR,
    P2_A1_OUTPUT_FILES,
    P2_A1_SCHEMA_VERSION,
    P2_A1_TAU_CASES,
    VerificationHNEQualityRelaxationEOS,
    _budget_within,
    _canonical_json_sha256,
    _front_distance,
)
from liquid_gas_transient.phase_change import HEMPhaseChange, HNERelaxationPhaseChange
from liquid_gas_transient.state import make_conserved


def test_p2_a1_contract_and_maturity_boundary() -> None:
    assert P2_A1_SCHEMA_VERSION == "stage7_p2_hne_model_form_sensitivity_a1_v1"
    assert P2_A1_KINETIC_QUALITY_FLOOR == pytest.approx(1.0e-6)
    assert P2_A1_TAU_CASES == (
        ("HNE_TAU_NEAR_ZERO", 1.0e-9),
        ("HNE_TAU_MEDIUM", 1.0e-5),
        ("HNE_TAU_SLOW", 1.0e-4),
    )
    assert [spec.model_id for spec in MODEL_SPECS] == [
        "HEM_EQUILIBRIUM",
        "HNE_TAU_NEAR_ZERO",
        "HNE_TAU_MEDIUM",
        "HNE_TAU_SLOW",
    ]
    assert len(P2_A1_OUTPUT_FILES) == 9
    assert P2_A1_FORMAL_STATUS["implemented"] is True
    assert P2_A1_FORMAL_STATUS["p2_model_form_vertical_slice"] is True
    for key in (
        "working_vertical_slice",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert P2_A1_FORMAL_STATUS[key] is False


@pytest.mark.coolprop_installed
def test_hne_eos_accepts_transport_equilibrium_quality_mismatch() -> None:
    pytest.importorskip("CoolProp")
    from CoolProp.CoolProp import PropsSI

    p = 2.0e6
    q_eq = 0.10
    rho = float(PropsSI("Dmass", "P", p, "Q", q_eq, "CO2"))
    e = float(PropsSI("Umass", "P", p, "Q", q_eq, "CO2"))
    U = make_conserved(rho, 0.0, e, xv=0.0)[np.newaxis, :]
    eos = VerificationHNEQualityRelaxationEOS()
    primitive = eos.primitive_from_conserved(U)

    assert primitive.xv[0] == pytest.approx(0.0, abs=0.0)
    assert eos.last_equilibrium_quality is not None
    assert eos.last_equilibrium_quality[0] == pytest.approx(q_eq, rel=1.0e-8)
    assert eos.last_regions is not None
    assert eos.last_regions[0] == "OPEN_TWO_PHASE"
    assert primitive.alpha[0] == pytest.approx(0.0, abs=0.0)
    assert primitive.p[0] == pytest.approx(p, rel=1.0e-9)


@pytest.mark.coolprop_installed
def test_near_zero_relaxation_matches_instantaneous_hem_for_one_cell() -> None:
    pytest.importorskip("CoolProp")
    from CoolProp.CoolProp import PropsSI

    p = 2.0e6
    q_eq = 0.20
    rho = float(PropsSI("Dmass", "P", p, "Q", q_eq, "CO2"))
    e = float(PropsSI("Umass", "P", p, "Q", q_eq, "CO2"))
    U = make_conserved(rho, 0.0, e, xv=0.0)[np.newaxis, :]
    eos = VerificationHNEQualityRelaxationEOS()

    hem = HEMPhaseChange().apply(np.array(U, copy=True), eos, 1.0e-5, 0.0)
    hne = HNERelaxationPhaseChange(tau_s=1.0e-9).apply(
        np.array(U, copy=True), eos, 1.0e-5, 0.0
    )
    assert np.array_equal(hem, hne)


def test_front_and_budget_helpers_are_fail_closed() -> None:
    distances = np.asarray([0.1, 0.2, 0.3])
    assert _front_distance(np.asarray([False, True, False]), distances) == pytest.approx(0.2)
    assert _front_distance(np.asarray([False, False, False]), distances) is None
    diagnostics = {
        "budget_mass_residual": 1.0e-13,
        "budget_mass_relative_residual": 1.0e-5,
    }
    assert _budget_within(
        diagnostics,
        "mass",
        absolute_tolerance=1.0e-12,
        relative_tolerance=1.0e-10,
    )
    diagnostics["budget_mass_residual"] = 1.0e-6
    assert not _budget_within(
        diagnostics,
        "mass",
        absolute_tolerance=1.0e-12,
        relative_tolerance=1.0e-10,
    )


def test_canonical_digest_is_order_independent() -> None:
    first = _canonical_json_sha256({"a": 1, "b": [2, 3]})
    second = _canonical_json_sha256({"b": [2, 3], "a": 1})
    assert first == second
    assert len(first) == 64


def test_generated_p2_a1_artifact_contract_when_available() -> None:
    target = Path("artifacts/stage7-p2-hne-model-form-sensitivity")
    if not target.exists():
        pytest.skip("generated P2-A1 evidence is supplied by the focused workflow")
    assert {path.name for path in target.iterdir() if path.is_file()} == set(
        P2_A1_OUTPUT_FILES
    )
    summary = json.loads((target / "model_form_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((target / "model_form_manifest.json").read_text(encoding="utf-8"))
    assert summary["model_form_slice_ready"] is True
    assert summary["execution_status"] == (
        "WORKING_MODEL_FORM_SLICE_WITH_EXPLICIT_LIMITATIONS"
    )
    assert all(summary["gate_results"].values())
    assert summary["interpretation"]["tau_to_zero_limit"] == (
        "BITWISE_HEM_LIMIT_REPRODUCED"
    )
    assert summary["interpretation"]["hydrodynamic_feedback_in_this_scaffold"] == (
        "ABSENT_BY_CONSTRUCTION"
    )
    assert summary["formal_status"]["verified"] is False
    assert summary["formal_status"]["accepted"] is False
    assert manifest["declared_file_count"] == 9
    assert manifest["model_form_sha256"] == summary["model_form_sha256"]
    assert set(manifest["payload_files"]) == set(P2_A1_OUTPUT_FILES) - {
        "model_form_manifest.json"
    }
    by_id = {row["model_id"]: row for row in summary["case_comparison"]}
    assert by_id["HNE_TAU_NEAR_ZERO"]["final_full_state_sha256"] == by_id[
        "HEM_EQUILIBRIUM"
    ]["final_full_state_sha256"]
    assert by_id["HNE_TAU_MEDIUM"]["maximum_quality_lag"] > 0.0
    assert by_id["HNE_TAU_SLOW"]["maximum_quality_lag"] >= by_id[
        "HNE_TAU_MEDIUM"
    ]["maximum_quality_lag"]
    for row in summary["tau_limit_comparison"]:
        assert row["hydrodynamic_state_matches_hem"] is True
        assert row["first_thermodynamic_crossing_time_s"] is not None
        assert math.isfinite(float(row["first_thermodynamic_crossing_time_s"]))
