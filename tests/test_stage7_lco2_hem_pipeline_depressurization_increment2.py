from __future__ import annotations

import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.hem_liquid_to_two_phase_first_crossing_case_ab import (
    run_first_crossing_case_ab_freeze,
)
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    _budget_limit,
    _raw_event_stop,
    _raw_outcome,
    run_fixed_pipeline_depressurization_matrix,
    write_pipeline_depressurization_artifacts,
)


def test_increment2_fixed_configuration_matches_reviewed_contract() -> None:
    config = HEMPipelineDepressurizationConfig()

    assert config.length_m == 1.0
    assert config.diameter_m == 0.10
    assert config.n_cells == 32
    assert config.dx_m == 0.03125
    assert config.n_ghost == 2
    assert config.cfl == 0.10
    assert config.initial_pressure_pa == 5.0e6
    assert config.subcooling_K == 5.0
    assert config.ramp_acoustic_time_ratio == 1.0
    assert config.horizon_acoustic_time_ratio == 3.0
    assert config.max_steps == 2000
    assert config.preflight_sample_count == 65
    assert config.projection_config.activation_tolerance == 1.0e-12
    assert config.accepted_state_quality_tolerance == 1.0e-10
    assert config.crossing_evidence_min_quality == 1.0e-6


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("n_cells", 16),
        ("cfl", 0.20),
        ("length_m", 2.0),
        ("subcooling_K", 4.0),
        ("max_steps", 1999),
        ("preflight_sample_count", 33),
    ],
)
def test_increment2_rejects_case_or_numerical_tuning(
    keyword: str,
    value: object,
) -> None:
    with pytest.raises(ValueError):
        HEMPipelineDepressurizationConfig(**{keyword: value})


def test_fixed_pipeline_case_order_and_pressures() -> None:
    assert [
        case.case_id for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
    ] == [
        "pipeline_crossing_candidate_p5m5_to_p2m5",
        "pipeline_moderate_diagnostic_p5m5_to_p3m5",
        "pipeline_liquid_control_p5m5_to_p4m5",
    ]
    assert [
        case.final_boundary_pressure_pa
        for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
    ] == [2.0e6, 3.0e6, 4.0e6]


def test_explicit_stop_priority_places_reverse_flow_before_phase_events() -> None:
    assert (
        _raw_event_stop(
            reverse_flow_delta=1,
            raw_outcome="FORBIDDEN_REGION",
        )
        == "REVERSE_FLOW_GUARD"
    )
    assert (
        _raw_event_stop(
            reverse_flow_delta=0,
            raw_outcome="FORBIDDEN_REGION",
        )
        == "FORBIDDEN_TRANSITION"
    )
    assert (
        _raw_event_stop(
            reverse_flow_delta=0,
            raw_outcome="ENDPOINT_LANDING",
        )
        == "ENDPOINT_LANDING"
    )
    assert (
        _raw_event_stop(
            reverse_flow_delta=0,
            raw_outcome="OPEN_TWO_PHASE",
        )
        is None
    )


def test_raw_outcome_distinguishes_crossing_endpoint_and_forbidden() -> None:
    def detection(regions, events):
        return SimpleNamespace(
            raw=SimpleNamespace(region=np.asarray(regions)),
            transitions=SimpleNamespace(event=np.asarray(events)),
        )

    assert _raw_outcome(
        detection(
            ["LIQUID_CANDIDATE", "OPEN_TWO_PHASE"],
            ["NO_TRANSITION", "LIQUID_TO_TWO_PHASE_CROSSING"],
        )
    ) == "OPEN_TWO_PHASE"
    assert _raw_outcome(
        detection(
            ["LIQUID_CANDIDATE", "SATURATED_LIQUID_ENDPOINT"],
            ["NO_TRANSITION", "BOUNDARY_TOUCH"],
        )
    ) == "ENDPOINT_LANDING"
    assert _raw_outcome(
        detection(
            ["LIQUID_CANDIDATE", "VAPOR_CANDIDATE"],
            ["NO_TRANSITION", "FORBIDDEN_TRANSITION"],
        )
    ) == "FORBIDDEN_REGION"
    assert _raw_outcome(
        detection(
            ["LIQUID_CANDIDATE", "LIQUID_CANDIDATE"],
            ["NO_TRANSITION", "NO_TRANSITION"],
        )
    ) == "ALL_LIQUID"


def test_budget_limit_uses_larger_absolute_or_relative_bound() -> None:
    assert _budget_limit(
        absolute=1.0e-12,
        relative=1.0e-10,
        actual=2.0,
        expected=2.0,
        reference=2.0,
    ) == pytest.approx(2.0e-10)
    assert _budget_limit(
        absolute=1.0e-6,
        relative=1.0e-10,
        actual=1.0,
        expected=1.0,
        reference=1.0,
    ) == pytest.approx(1.0e-6)


def test_increment2_module_is_orchestration_only() -> None:
    import liquid_gas_transient.hem_pipeline_depressurization_first_crossing as module

    source = inspect.getsource(module)
    assert "class FvmSolver" not in source
    assert "def rusanov_flux" not in source
    assert "class VerificationHEMLiquidOpenTwoPhaseEOS" not in source
    assert "class HEMEquilibriumQualityProjection" not in source
    assert "MUSCL" not in source
    assert "friction" not in source.lower()
    assert "wall heat transfer" not in source.lower()


@pytest.fixture(scope="module")
def installed_pipeline_result():
    pytest.importorskip("CoolProp")
    return run_fixed_pipeline_depressurization_matrix()


@pytest.mark.coolprop_installed
def test_installed_coolprop_fixed_pipeline_matrix_completes_honestly(
    installed_pipeline_result,
) -> None:
    result = installed_pipeline_result
    summary = result.summary()

    assert len(result.cases) == 3
    assert summary["pipeline_depressurization_executed"] is True
    assert summary["all_fixed_cases_completed"] is True
    assert summary["algorithms_or_tolerances_tuned"] is False
    assert summary["production_hem_activation_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False

    for case in result.cases:
        assert case.outcome in {
            "ACCEPTED_FIRST_CROSSING",
            "NO_CROSSING_WITHIN_HORIZON",
        }
        assert len(case.preflight.records) == 65
        assert all(record.accepted for record in case.preflight.records)
        assert all(
            record.boundary_region == "LIQUID_CANDIDATE"
            for record in case.preflight.records
        )
        assert case.reverse_flow_fallback_count == 0
        assert case.step_count > 0
        assert case.final_time_s <= case.maximum_horizon_s + 1.0e-15
        assert case.time_history_s.shape[0] == case.step_count + 1
        assert case.pressure_history_pa.shape == (
            case.step_count + 1,
            case.config.n_cells,
        )
        assert case.accepted_state_history.shape == (
            case.step_count + 1,
            case.config.n_cells,
            4,
        )
        assert abs(
            case.boundary_budget_diagnostics["budget_mass_residual"]
        ) <= max(
            case.config.mass_budget_absolute_tolerance_kg,
            case.config.mass_budget_relative_tolerance,
        )
        assert abs(
            case.boundary_budget_diagnostics["budget_energy_residual"]
        ) <= case.config.energy_budget_absolute_tolerance_J
        assert abs(
            case.phase_budget_diagnostics[
                "phase_vapor_mass_balance_residual_kg"
            ]
        ) <= case.config.vapor_budget_absolute_tolerance_kg

        if case.outcome == "ACCEPTED_FIRST_CROSSING":
            assert case.crossing_step == case.step_count
            assert case.crossing_time_s == pytest.approx(case.final_time_s)
            assert case.crossing_cell_indices
            assert (
                case.maximum_crossing_quality
                >= case.config.crossing_evidence_min_quality
            )
            final_step = case.steps[-1]
            assert (
                final_step.crossing_cell_indices
                == final_step.first_projection_cell_indices
            )
            assert final_step.second_projection_cell_indices == ()
            assert (
                final_step.max_post_quality_mismatch
                <= case.config.projection_config.activation_tolerance
            )


@pytest.mark.coolprop_installed
def test_installed_pipeline_artifact_bundle_is_complete(
    installed_pipeline_result,
    tmp_path: Path,
) -> None:
    paths = write_pipeline_depressurization_artifacts(
        tmp_path,
        installed_pipeline_result,
    )

    assert set(paths) == {
        "json",
        "cases_csv",
        "steps_csv",
        "cells_csv",
        "boundary_path_csv",
        "markdown",
        "npz",
    }
    assert all(path.exists() for path in paths.values())
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["case_count"] == 3
    assert payload["pipeline_depressurization_executed"] is True
    assert payload["algorithms_or_tolerances_tuned"] is False
    assert len(payload["boundary_path"]) == 195
    assert len(paths["cases_csv"].read_text(encoding="utf-8").splitlines()) == 4
    assert len(
        paths["boundary_path_csv"].read_text(encoding="utf-8").splitlines()
    ) == 196
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "FIRST-ORDER FVM" in markdown
    assert "physical Validation: false" in markdown
    with np.load(paths["npz"]) as archive:
        assert any(key.endswith("__pressure_history_pa") for key in archive.files)


@pytest.mark.coolprop_installed
def test_frozen_case_ab_regression_signatures_remain_exact() -> None:
    pytest.importorskip("CoolProp")
    result = run_first_crossing_case_ab_freeze()
    summary = result.summary()

    assert summary["case_a_frozen"] is True
    assert summary["case_b_frozen"] is True
    assert summary["actual_first_order_fvm_crossing_verified"] is True
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
