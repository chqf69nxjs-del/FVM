from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.hem_liquid_to_two_phase_crossing import (
    HEMBoundaryRegionEvaluation,
    HEMRawTransitionDetection,
    HEMTransitionClassification,
)
from liquid_gas_transient.hem_liquid_to_two_phase_minimal_fvm_dry_run import (
    DryRunEndpointState,
    HEMMinimalRawFvmDryRunConfig,
    MinimalFvmDryRunCaseSpec,
    build_piecewise_liquid_initial_state,
    run_minimal_raw_fvm_dry_run_matrix,
    run_one_minimal_raw_fvm_case,
    write_minimal_raw_fvm_dry_run_artifacts,
)
from liquid_gas_transient.hem_liquid_to_two_phase_state_pair_survey import (
    CoolPropLimits,
    HEMLiquidStatePairSurveyConfig,
    HEMLiquidStatePairSurveyResult,
    LiquidCandidateRecord,
)
from liquid_gas_transient.hem_phase_classification import HEMPhaseState
from liquid_gas_transient.state import PrimitiveState


def _candidate(candidate_id: str, pressure: float, rho: float, e: float):
    return LiquidCandidateRecord(
        candidate_id=candidate_id,
        pressure_input_pa=pressure,
        subcooling_K=5.0,
        saturation_temperature_K=280.0,
        temperature_input_K=275.0,
        rho_kg_m3=rho,
        e_j_kg=e,
        pressure_recovered_pa=pressure,
        temperature_recovered_K=275.0,
        equilibrium_quality=0.0,
        void_fraction=0.0,
        raw_phase="liquid",
        phase_class="compressed_or_subcooled_liquid",
        scope_status="supported_candidate",
        boundary_region="LIQUID_CANDIDATE",
        sound_speed_m_s=100.0,
        critical_temperature_distance_K=20.0,
        critical_pressure_distance_pa=1.0e6,
        triple_temperature_margin_K=50.0,
        status="ACCEPTED_LIQUID",
        accepted=True,
        reason="",
    )


def _survey_result():
    return HEMLiquidStatePairSurveyResult(
        config=HEMLiquidStatePairSurveyConfig(),
        limits=CoolPropLimits(304.0, 7.38e6, 216.6),
        candidates=(
            _candidate("p5_m5", 5.0e6, 800.0, 100.0),
            _candidate("p2_m5", 2.0e6, 500.0, 80.0),
            _candidate("p3_m5", 3.0e6, 600.0, 85.0),
            _candidate("p4_m5", 4.0e6, 700.0, 90.0),
        ),
        pairs=(),
        blend_points=(),
    )


class _LinearLiquidEOS:
    def primitive_from_conserved(self, U):
        array = np.asarray(U, dtype=float)
        rho = array[..., 0]
        u = array[..., 1] / rho
        E = array[..., 2] / rho
        e = E - 0.5 * u**2
        q = array[..., 3] / rho
        p = 1.0e4 * rho
        return PrimitiveState(
            rho=np.array(rho, copy=True),
            u=np.array(u, copy=True),
            p=np.asarray(p),
            e=np.array(e, copy=True),
            E=np.array(E, copy=True),
            T=np.full_like(rho, 275.0),
            xv=np.array(q, copy=True),
            alpha=np.array(q, copy=True),
            c=np.full_like(rho, 100.0),
        )

    def density_from_pressure(self, p):
        return np.asarray(p, dtype=float) / 1.0e4


def _fake_eos_factory(phase_config):
    del phase_config
    return _LinearLiquidEOS()


def _phase_state(rho, e, *, open_index: int | None = None):
    rho_arr = np.asarray(rho, dtype=float)
    e_arr = np.asarray(e, dtype=float)
    phase_class = np.full(
        rho_arr.shape,
        "compressed_or_subcooled_liquid",
        dtype="<U40",
    )
    quality = np.zeros(rho_arr.shape)
    alpha = np.zeros(rho_arr.shape)
    raw_phase = np.full(rho_arr.shape, "liquid", dtype="<U16")
    p = 1.0e4 * rho_arr
    if open_index is not None:
        phase_class[open_index] = "liquid_vapor_two_phase"
        quality[open_index] = 0.01
        alpha[open_index] = 0.50
        raw_phase[open_index] = "twophase"
        p[open_index] = 2.0e6
    return HEMPhaseState(
        backend_name="fake",
        rho=np.array(rho_arr, copy=True),
        e=np.array(e_arr, copy=True),
        p=np.array(p, copy=True),
        T=np.full(rho_arr.shape, 275.0),
        quality=quality,
        quality_defined=np.ones(rho_arr.shape, dtype=bool),
        alpha=alpha,
        alpha_defined=np.ones(rho_arr.shape, dtype=bool),
        raw_phase=raw_phase,
        phase_class=phase_class,
        scope_status=np.full(
            rho_arr.shape,
            "supported_candidate",
            dtype="<U24",
        ),
        sound_speed_evaluated=False,
    )


def _fake_detection(U_previous, U_raw, *, evaluator=None, phase_config=None):
    del evaluator, phase_config
    rho_previous = np.asarray(U_previous)[..., 0]
    rho_raw = np.asarray(U_raw)[..., 0]
    e_previous = np.asarray(U_previous)[..., 2] / rho_previous
    e_raw = np.asarray(U_raw)[..., 2] / rho_raw - 0.5 * (
        np.asarray(U_raw)[..., 1] / rho_raw
    ) ** 2
    previous_state = _phase_state(rho_previous, e_previous)
    raw_state = _phase_state(rho_raw, e_raw, open_index=3)
    previous_regions = np.full(
        rho_previous.shape,
        "LIQUID_CANDIDATE",
        dtype="<U36",
    )
    raw_regions = np.array(previous_regions, copy=True)
    raw_regions[3] = "OPEN_TWO_PHASE"
    events = np.full(rho_previous.shape, "NO_TRANSITION", dtype="<U40")
    events[3] = "LIQUID_TO_TWO_PHASE_CROSSING"
    return HEMRawTransitionDetection(
        previous=HEMBoundaryRegionEvaluation(
            rho=np.array(rho_previous, copy=True),
            e=np.array(e_previous, copy=True),
            phase_state=previous_state,
            region=previous_regions,
            endpoint_tolerance=1.0e-10,
        ),
        raw=HEMBoundaryRegionEvaluation(
            rho=np.array(rho_raw, copy=True),
            e=np.array(e_raw, copy=True),
            phase_state=raw_state,
            region=raw_regions,
            endpoint_tolerance=1.0e-10,
        ),
        transitions=HEMTransitionClassification(
            previous_region=previous_regions,
            raw_region=raw_regions,
            event=events,
        ),
    )


def _all_liquid_evaluator(rho, e, *, config=None):
    del config
    return _phase_state(rho, e)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("n_cells", 3),
        ("length_m", 0.0),
        ("diameter_m", 0.0),
        ("cfl", 0.0),
        ("cfl", 1.1),
        ("n_ghost", 0),
        ("interface_cell", 0),
        ("interface_cell", 8),
        ("case_specs", ()),
    ],
)
def test_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        HEMMinimalRawFvmDryRunConfig(**{field: value})


def test_config_rejects_unknown_candidate_reference():
    with pytest.raises(ValueError, match="unknown candidates"):
        HEMMinimalRawFvmDryRunConfig(
            case_specs=(
                MinimalFvmDryRunCaseSpec(
                    "bad",
                    "bad",
                    "missing",
                    "p2_m5",
                ),
            )
        )


def test_piecewise_initial_state_is_stationary_and_exact_q_zero():
    left = DryRunEndpointState("left", 5.0e6, 5.0, 800.0, 100.0)
    right = DryRunEndpointState("right", 2.0e6, 5.0, 500.0, 80.0)
    U = build_piecewise_liquid_initial_state(
        left,
        right,
        n_cells=8,
        interface_cell=4,
    )

    assert U.shape == (8, 4)
    assert U[:4, 0].tolist() == [800.0] * 4
    assert U[4:, 0].tolist() == [500.0] * 4
    assert np.all(U[:, 1] == 0.0)
    assert np.all(U[:, 3] == 0.0)


def test_one_step_runner_exercises_real_solver_and_records_crossing():
    config = HEMMinimalRawFvmDryRunConfig(
        case_specs=(
            MinimalFvmDryRunCaseSpec(
                "strong_p5m5_to_p2m5",
                "strong crossing candidate",
                "p5_m5",
                "p2_m5",
            ),
        )
    )
    left = DryRunEndpointState.from_candidate(_survey_result().candidates[0])
    right = DryRunEndpointState.from_candidate(_survey_result().candidates[1])

    result = run_one_minimal_raw_fvm_case(
        config.case_specs[0],
        left,
        right,
        config,
        eos_factory=_fake_eos_factory,
        phase_evaluator=_all_liquid_evaluator,
        transition_detector=_fake_detection,
    )
    summary = result.summary()

    assert result.fvm_step_exercised is True
    assert result.outcome == "OPEN_TWO_PHASE"
    assert summary["event_counts"]["LIQUID_TO_TWO_PHASE_CROSSING"] == 1
    assert summary["raw_region_counts"]["OPEN_TWO_PHASE"] == 1
    assert summary["changed_cell_indices"] == [3, 4]
    assert summary["initial_transport_quality_exactly_zero"] is True
    assert summary["raw_transport_quality_exactly_zero"] is True
    assert summary["max_raw_equilibrium_quality"] == pytest.approx(0.01)
    assert summary["max_raw_quality_mismatch"] == pytest.approx(0.01)
    assert result.measured_initial_cfl == pytest.approx(config.cfl)
    for name in ("mass", "momentum", "energy", "vapor_mass"):
        assert abs(
            result.budget_diagnostics[f"budget_{name}_residual"]
        ) < 1.0e-9


def test_matrix_summary_retains_verification_boundary():
    config = HEMMinimalRawFvmDryRunConfig(
        case_specs=(
            MinimalFvmDryRunCaseSpec("one", "one", "p5_m5", "p2_m5"),
        )
    )
    result = run_minimal_raw_fvm_dry_run_matrix(
        config,
        survey_result=_survey_result(),
        eos_factory=_fake_eos_factory,
        phase_evaluator=_all_liquid_evaluator,
        transition_detector=_fake_detection,
    )
    summary = result.summary()

    assert summary["raw_fvm_crossing_observed"] is True
    assert summary["fvm_solver_step_exercised"] is True
    assert summary["rusanov_flux_exercised"] is True
    assert summary["cfl_path_exercised"] is True
    assert summary["phase_projection_exercised"] is False
    assert summary["accepted_state_eos_after_raw_exercised"] is False
    assert summary["actual_first_order_fvm_crossing_verified"] is False
    assert summary["case_a_frozen"] is False
    assert summary["case_b_frozen"] is False
    assert summary["production_hem_activation_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False


def test_artifacts_are_traceable(tmp_path):
    config = HEMMinimalRawFvmDryRunConfig(
        case_specs=(
            MinimalFvmDryRunCaseSpec("one", "one", "p5_m5", "p2_m5"),
        )
    )
    result = run_minimal_raw_fvm_dry_run_matrix(
        config,
        survey_result=_survey_result(),
        eos_factory=_fake_eos_factory,
        phase_evaluator=_all_liquid_evaluator,
        transition_detector=_fake_detection,
    )
    files = write_minimal_raw_fvm_dry_run_artifacts(tmp_path, result)

    assert set(files) == {
        "json",
        "cases_csv",
        "cells_csv",
        "markdown",
        "npz",
    }
    assert all(path.is_file() for path in files.values())
    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["scope"] == "verification_only"
    assert payload["fvm_solver_step_exercised"] is True
    assert payload["phase_projection_exercised"] is False
    assert payload["actual_first_order_fvm_crossing_verified"] is False
    assert payload["cases"][0]["outcome"] == "OPEN_TWO_PHASE"
    markdown = files["markdown"].read_text(encoding="utf-8")
    assert "ONE RAW FVM STEP" in markdown
    assert "formal crossing" in markdown.lower()


@pytest.mark.coolprop_installed
def test_installed_coolprop_runs_fixed_three_case_one_step_matrix():
    pytest.importorskip("CoolProp")
    result = run_minimal_raw_fvm_dry_run_matrix()
    summary = result.summary()

    assert len(result.cases) == 3
    assert summary["all_cases_exercised_one_fvm_step"] is True
    assert summary["fvm_solver_step_exercised"] is True
    assert summary["phase_projection_exercised"] is False
    assert summary["actual_first_order_fvm_crossing_verified"] is False
    assert all(
        case.outcome not in {"GUARD_FAILURE", "BACKEND_FAILURE"}
        for case in result.cases
    )
    assert all(
        case.summary()["changed_cell_indices"] == [3, 4]
        for case in result.cases
    )
    assert all(
        case.summary()["initial_transport_quality_exactly_zero"] is True
        for case in result.cases
    )
    assert all(
        case.summary()["raw_transport_quality_exactly_zero"] is True
        for case in result.cases
    )
