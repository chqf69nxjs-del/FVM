from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.hem_liquid_to_two_phase_first_crossing_case_ab import (
    run_first_crossing_case_ab_freeze,
)
from liquid_gas_transient.hem_pipeline_4mpa_subthreshold_forensics import (
    CASE_ID,
    EXPECTED_BASELINE,
    PERTURBATION_LEVELS,
    RECONSTRUCTION_ABSOLUTE_TOLERANCE,
    RECONSTRUCTION_RELATIVE_TOLERANCE,
    SELECTED_CELLS,
    SELECTED_STEPS,
    HEM4MPaForensicError,
    PerturbationRecord,
    _assert_baseline,
    classify_perturbation_sensitivity,
    run_fixed_4mpa_forensic_diagnostic,
    write_fixed_4mpa_forensic_artifacts,
)


def _perturbation(delta_rho: float, delta_e: float, region: str) -> PerturbationRecord:
    return PerturbationRecord(
        delta_rho_relative=delta_rho,
        delta_e_relative=delta_e,
        rho_kg_m3=900.0,
        e_j_kg=200000.0,
        pressure_pa=4.0e6,
        temperature_K=270.0,
        phase_class="liquid_vapor_two_phase",
        boundary_region=region,
        q_equilibrium=1.0e-8 if region == "OPEN_TWO_PHASE" else 0.0,
        void_fraction=1.0e-5 if region == "OPEN_TWO_PHASE" else 0.0,
        delta_u_sat_j_kg=1.0 if region == "OPEN_TWO_PHASE" else -1.0,
        delta_v_sat_m3_kg=1.0e-9 if region == "OPEN_TWO_PHASE" else -1.0e-9,
        pressure_round_trip_residual_pa=0.0,
        temperature_round_trip_residual_K=0.0,
        rho_round_trip_residual_kg_m3=0.0,
        e_round_trip_residual_j_kg=0.0,
        accepted_state_eos=True,
        failure_reason="",
    )


def test_forensic_window_and_perturbation_grid_are_fixed() -> None:
    assert SELECTED_STEPS == tuple(range(300, 314))
    assert SELECTED_CELLS == tuple(range(23, 28))
    assert len(PERTURBATION_LEVELS) == 9
    assert PERTURBATION_LEVELS[4] == 0.0
    assert PERTURBATION_LEVELS[0] == -1.0e-6
    assert PERTURBATION_LEVELS[-1] == 1.0e-6
    assert RECONSTRUCTION_RELATIVE_TOLERANCE == 2.0e-12
    assert RECONSTRUCTION_ABSOLUTE_TOLERANCE == 1.0e-8


def test_baseline_guard_accepts_only_the_exact_pr77_identity() -> None:
    exact = SimpleNamespace(**EXPECTED_BASELINE)
    _assert_baseline(exact)

    changed = dict(EXPECTED_BASELINE)
    changed["crossing_step"] = 312
    with pytest.raises(HEM4MPaForensicError, match="baseline mismatch"):
        _assert_baseline(SimpleNamespace(**changed))


@pytest.mark.parametrize(
    ("change_magnitude", "expected"),
    [
        (1.0e-12, "ROUND_OFF_SENSITIVE"),
        (1.0e-10, "ROUND_OFF_SENSITIVE"),
        (1.0e-8, "HIGHLY_SENSITIVE"),
        (1.0e-6, "WEAKLY_RESOLVED"),
    ],
)
def test_perturbation_sensitivity_categories(
    change_magnitude: float,
    expected: str,
) -> None:
    records = [_perturbation(0.0, 0.0, "OPEN_TWO_PHASE")]
    for delta_rho in PERTURBATION_LEVELS:
        for delta_e in PERTURBATION_LEVELS:
            if delta_rho == 0.0 and delta_e == 0.0:
                continue
            magnitude = max(abs(delta_rho), abs(delta_e))
            region = (
                "LIQUID_CANDIDATE"
                if magnitude == change_magnitude
                else "OPEN_TWO_PHASE"
            )
            records.append(_perturbation(delta_rho, delta_e, region))
    assert classify_perturbation_sensitivity(records) == expected


def test_perturbation_sensitivity_can_be_robust() -> None:
    records = [
        _perturbation(delta_rho, delta_e, "OPEN_TWO_PHASE")
        for delta_rho in PERTURBATION_LEVELS
        for delta_e in PERTURBATION_LEVELS
    ]
    assert (
        classify_perturbation_sensitivity(records)
        == "ROBUST_IN_TESTED_ENVELOPE"
    )


@pytest.fixture(scope="module")
def installed_forensic_result():
    pytest.importorskip("CoolProp")
    return run_fixed_4mpa_forensic_diagnostic(generate_plots=False)


@pytest.mark.coolprop_installed
def test_fixed_forensic_result_reproduces_pr77_and_retains_complete_window(
    installed_forensic_result,
) -> None:
    result = installed_forensic_result
    summary = result.summary()

    assert summary["case_id"] == CASE_ID
    assert summary["baseline_reproduced_exactly"] is True
    assert summary["PR77_observation_reclassified"] is False
    assert summary["Gate_P2_passed"] is False
    assert result.baseline_summary["outcome"] == "GUARD_FAILURE"
    assert result.baseline_summary["crossing_step"] == 313
    assert result.baseline_summary["crossing_cell_indices"] == [25]
    assert result.baseline_summary["maximum_crossing_quality"] == (
        9.672588429198319e-9
    )

    assert len(result.local_states) == len(SELECTED_STEPS) * len(SELECTED_CELLS) * 3
    assert len(result.saturation_margins) == len(SELECTED_STEPS) * len(SELECTED_CELLS)
    assert len(result.flux_decomposition) == len(SELECTED_STEPS) * len(SELECTED_CELLS)
    assert len(result.perturbations) == len(PERTURBATION_LEVELS) ** 2

    assert {
        record.step_index for record in result.local_states
    } == set(SELECTED_STEPS)
    assert {
        record.cell_index for record in result.local_states
    } == set(SELECTED_CELLS)
    assert {
        record.stage for record in result.local_states
    } == {"accepted_before", "raw_fvm", "post_projection"}
    assert all(record.reverse_flow_fallback_count == 0 for record in result.local_states)


@pytest.mark.coolprop_installed
def test_crossing_state_has_independent_thermodynamic_evidence(
    installed_forensic_result,
) -> None:
    crossing = next(
        record
        for record in installed_forensic_result.saturation_margins
        if record.step_index == 313 and record.cell_index == 25
    )
    assert crossing.boundary_region == "OPEN_TWO_PHASE"
    assert crossing.q_equilibrium == 9.672588429198319e-9
    assert crossing.q_from_internal_energy > 0.0
    assert crossing.q_from_specific_volume > 0.0
    assert crossing.delta_u_sat_j_kg > 0.0
    assert crossing.delta_v_sat_m3_kg > 0.0
    assert crossing.coordinate_support == "TWO_PHASE_SIDE_SUPPORT"
    assert np.isfinite(crossing.entropy_offset_from_initial_j_kg_K)

    categories = set(installed_forensic_result.diagnostic_categories)
    assert "THERMODYNAMIC_TWO_PHASE_SUPPORTED" in categories
    assert categories <= {
        "THERMODYNAMIC_TWO_PHASE_SUPPORTED",
        "NUMERICAL_DIFFUSION_CONSISTENT",
        "BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT",
        "NEAR_SATURATION_PROPERTY_SENSITIVE",
        "MULTI_FACTOR_EVIDENCE",
        "INCONCLUSIVE",
    }


@pytest.mark.coolprop_installed
def test_isentropic_reference_is_explicitly_recorded(
    installed_forensic_result,
) -> None:
    reference = installed_forensic_result.isentropic_reference
    assert np.isfinite(reference.initial_entropy_j_kg_K)
    if reference.bracketed:
        assert reference.bracket_low_pa is not None
        assert reference.bracket_high_pa is not None
        assert reference.flash_pressure_pa is not None
        assert reference.residual_j_kg_K is not None
        assert abs(reference.residual_j_kg_K) <= 1.0e-7
    else:
        assert reference.flash_pressure_pa is None
        assert reference.failure_reason


@pytest.mark.coolprop_installed
def test_rusanov_decomposition_reconstructs_every_selected_raw_state(
    installed_forensic_result,
) -> None:
    records = installed_forensic_result.flux_decomposition
    assert records
    assert max(record.reconstructed_raw_max_abs_error for record in records) <= (
        RECONSTRUCTION_ABSOLUTE_TOLERANCE
    )
    assert max(record.reconstructed_raw_max_relative_error for record in records) <= (
        RECONSTRUCTION_RELATIVE_TOLERANCE
    )
    assert installed_forensic_result.reconstruction_max_abs_error <= (
        RECONSTRUCTION_ABSOLUTE_TOLERANCE
    )
    assert installed_forensic_result.reconstruction_max_relative_error <= (
        RECONSTRUCTION_RELATIVE_TOLERANCE
    )
    crossing = next(
        record
        for record in records
        if record.step_index == 313 and record.cell_index == 25
    )
    assert len(crossing.left_total_flux) == 4
    assert len(crossing.right_total_flux) == 4
    assert len(crossing.delta_U_central) == 4
    assert len(crossing.delta_U_dissipative) == 4
    assert len(crossing.delta_U_total) == 4
    assert np.allclose(
        np.asarray(crossing.delta_U_central)
        + np.asarray(crossing.delta_U_dissipative),
        np.asarray(crossing.delta_U_total),
        rtol=0.0,
        atol=1.0e-12,
    )


@pytest.mark.coolprop_installed
def test_perturbation_map_is_complete_and_keeps_the_baseline_state(
    installed_forensic_result,
) -> None:
    records = installed_forensic_result.perturbations
    assert {
        (record.delta_rho_relative, record.delta_e_relative)
        for record in records
    } == {
        (delta_rho, delta_e)
        for delta_rho in PERTURBATION_LEVELS
        for delta_e in PERTURBATION_LEVELS
    }
    baseline = next(
        record
        for record in records
        if record.delta_rho_relative == 0.0
        and record.delta_e_relative == 0.0
    )
    assert baseline.boundary_region == "OPEN_TWO_PHASE"
    assert baseline.q_equilibrium == 9.672588429198319e-9
    assert baseline.accepted_state_eos is True
    assert installed_forensic_result.perturbation_sensitivity in {
        "ROUND_OFF_SENSITIVE",
        "HIGHLY_SENSITIVE",
        "WEAKLY_RESOLVED",
        "ROBUST_IN_TESTED_ENVELOPE",
        "INCONCLUSIVE",
    }


@pytest.mark.coolprop_installed
def test_fixed_forensic_diagnostic_repeats_exactly(
    installed_forensic_result,
) -> None:
    repeated = run_fixed_4mpa_forensic_diagnostic(generate_plots=False)
    assert repeated.summary() == installed_forensic_result.summary()
    assert repeated.isentropic_reference == installed_forensic_result.isentropic_reference
    assert repeated.local_states == installed_forensic_result.local_states
    assert repeated.saturation_margins == installed_forensic_result.saturation_margins
    assert repeated.flux_decomposition == installed_forensic_result.flux_decomposition
    assert repeated.perturbations == installed_forensic_result.perturbations


@pytest.mark.coolprop_installed
def test_forensic_artifact_bundle_is_complete(
    installed_forensic_result,
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    paths = write_fixed_4mpa_forensic_artifacts(
        tmp_path,
        installed_forensic_result,
    )
    required = {
        "summary_json",
        "local_history_csv",
        "saturation_margin_csv",
        "isentropic_json",
        "flux_csv",
        "perturbation_csv",
        "perturbation_npz",
        "markdown",
        "plot_rho_e_saturation_zoom",
        "plot_saturation_margin_vs_time",
        "plot_central_vs_dissipative_update",
        "plot_perturbation_classification_map",
    }
    assert set(paths) == required
    assert all(path.exists() for path in paths.values())

    payload = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    assert payload["baseline_reproduced_exactly"] is True
    assert payload["Gate_P2_passed"] is False
    assert payload["local_state_record_count"] == 210
    assert payload["saturation_margin_record_count"] == 70
    assert payload["flux_decomposition_record_count"] == 70
    assert payload["perturbation_record_count"] == 81
    assert len(
        paths["local_history_csv"].read_text(encoding="utf-8").splitlines()
    ) == 211
    assert len(
        paths["saturation_margin_csv"].read_text(encoding="utf-8").splitlines()
    ) == 71
    assert len(paths["flux_csv"].read_text(encoding="utf-8").splitlines()) == 71
    assert len(
        paths["perturbation_csv"].read_text(encoding="utf-8").splitlines()
    ) == 82
    with np.load(paths["perturbation_npz"]) as archive:
        assert archive["q_equilibrium"].shape == (81,)
        assert archive["boundary_region"].shape == (81,)


@pytest.mark.coolprop_installed
def test_frozen_case_ab_regression_remains_exact() -> None:
    pytest.importorskip("CoolProp")
    result = run_first_crossing_case_ab_freeze()
    summary = result.summary()
    assert summary["case_a_frozen"] is True
    assert summary["case_b_frozen"] is True
    assert {
        run.final_state_sha256 for run in result.case_a_runs
    } == {
        "78897b5c8ca57221186ccf3e0aa69e1492a942cc2e8dee0abb440a3e2e08e039"
    }
    assert {
        run.repeatability_signature for run in result.case_a_runs
    } == {
        "914ed2249c9546a1d32f6d6dbcd8b30236e1c1f2b37ecf9306100ad30622b612"
    }
    assert {
        run.final_state_sha256 for run in result.case_b_runs
    } == {
        "8c09735ee9185cfb34b2186be30b32d78ec73350e211762d92c372e0b9f23a59"
    }
    assert {
        run.repeatability_signature for run in result.case_b_runs
    } == {
        "3bd7edc37842a00a0c27964a17029f5c66ef973b59bd7670f513c82fc7e85669"
    }
