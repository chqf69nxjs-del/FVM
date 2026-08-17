from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.eos import LCO2PropertyEOSAdapter, ToyHEMEOS
from liquid_gas_transient.hne_shadow_pipeline import (
    EXPECTED_BACKEND_NAME,
    FORMAL_STATUS,
    OUTPUT_FILES,
    SCHEMA_VERSION,
    HNEShadowPipelineError,
    HNEThermodynamicShadowObserver,
    ShadowPipelineConfig,
    _build_solver,
    analyze_shadow_pipeline,
    execute,
)
from liquid_gas_transient.properties import SurrogateLCO2PropertyBackend


def test_a2_3_contract_and_maturity_boundary() -> None:
    assert SCHEMA_VERSION == "stage7_p2_hne_shadow_pipeline_a2_3_v1"
    assert EXPECTED_BACKEND_NAME == "surrogate_lco2"
    assert len(OUTPUT_FILES) == 6
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["finite_pipeline_shadow_integration"] is True
    assert FORMAL_STATUS["diagnostic_evidence_ready"] is True
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
        assert FORMAL_STATUS[key] is False


def test_shadow_observer_rejects_backend_or_authority_mismatch() -> None:
    observer = HNEThermodynamicShadowObserver()
    with pytest.raises(HNEShadowPipelineError):
        observer.assert_compatible(ToyHEMEOS())

    transported = LCO2PropertyEOSAdapter(
        backend=SurrogateLCO2PropertyBackend(),
        quality_source="transported",
    )
    with pytest.raises(HNEShadowPipelineError):
        observer.assert_compatible(transported)

    mismatched = LCO2PropertyEOSAdapter(
        backend=SurrogateLCO2PropertyBackend(p_sat_ref_pa=2.0e6),
        quality_source="backend",
    )
    with pytest.raises(HNEShadowPipelineError):
        observer.assert_compatible(mismatched)


def test_shadow_observation_is_read_only() -> None:
    config = ShadowPipelineConfig(n_steps=2)
    solver, closure = _build_solver(config, 1.0e-4)
    observer = HNEThermodynamicShadowObserver(closure=closure)
    before = solver.U.copy()
    observation = observer.observe(
        case_id="READ_ONLY_TEST",
        tau_s=1.0e-4,
        U=solver.U,
        eos=solver.eos,
        grid=solver.grid,
        step=0,
        time_s=0.0,
        dt_s=0.0,
    )
    assert np.array_equal(solver.U, before)
    assert observation.step_row["shadow_state_read_only"] is True
    assert observation.step_row["closure_failure_count"] == 0
    assert observation.step_row["closure_success_count"] == config.n_cells
    assert len(observation.cell_rows) == config.n_cells


def test_finite_pipeline_shadow_matrix_passes_without_coupling() -> None:
    analysis = analyze_shadow_pipeline()
    summary = analysis.summary
    assert summary["a2_3_shadow_ready"] is True
    assert summary["execution_status"] == (
        "A2_3_FINITE_PIPELINE_SHADOW_READY_WITH_COUPLING_GATE_CLOSED"
    )
    assert all(summary["gate_results"].values())
    assert summary["physical_hne_claim_allowed"] is False
    assert summary["hydrodynamic_coupling_allowed"] is False
    assert summary["coupling_contract"]["c_hne_to_flux_or_cfl"] is False

    by_id = {row["case_id"]: row for row in summary["case_summary"]}
    near = by_id["TAU_NEAR_ZERO"]
    finite = by_id["TAU_FINITE"]
    frozen = by_id["TAU_FROZEN"]
    assert near["maximum_absolute_q_lag_final"] <= 1.0e-15
    assert near["maximum_absolute_pressure_delta_pa_final"] <= 1.0e-8
    assert finite["maximum_absolute_q_lag_final"] > 1.0e-8
    assert finite["maximum_absolute_pressure_delta_pa_final"] > 1.0
    assert finite["maximum_absolute_temperature_delta_K_final"] > 1.0e-6
    assert frozen["frozen_source_matches_no_phase_change"] is True
    for row in by_id.values():
        assert row["baseline_shadow_full_trajectory_bitwise_equal"] is True
        assert row["hydrodynamic_state_unchanged_from_initial"] is True
        assert row["mass_momentum_energy_conserved"] is True


def test_execute_writes_exact_reproducible_evidence_set(tmp_path: Path) -> None:
    result = execute(tmp_path)
    assert result["a2_3_shadow_ready"] is True
    assert {path.name for path in tmp_path.iterdir() if path.is_file()} == set(
        OUTPUT_FILES
    )
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["declared_file_count"] == len(OUTPUT_FILES)
    assert manifest["declared_file_names"] == list(OUTPUT_FILES)
    assert manifest["analysis_sha256"] == summary["analysis_sha256"]
    assert manifest["a2_3_shadow_ready"] is True
    assert manifest["hydrodynamic_coupling_allowed"] is False
    assert set(manifest["payload_files"]) == set(OUTPUT_FILES) - {
        "manifest.json"
    }
    for item in manifest["payload_files"].values():
        assert item["size_bytes"] > 0
        assert len(item["sha256"]) == 64
