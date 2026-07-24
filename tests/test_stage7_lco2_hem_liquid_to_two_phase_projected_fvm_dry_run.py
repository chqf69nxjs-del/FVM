from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.hem_equilibrium_quality_sync import (
    HEMEquilibriumQualityProjection,
    HEMEquilibriumQualitySyncConfig,
    HEMQualityEvaluation,
)
from liquid_gas_transient.hem_liquid_to_two_phase_minimal_fvm_dry_run import (
    DryRunEndpointState,
    HEMMinimalRawFvmDryRunConfig,
    HEMMinimalRawFvmDryRunResult,
    MinimalFvmDryRunCaseSpec,
    MinimalRawFvmCellRecord,
    MinimalRawFvmCaseResult,
)
from liquid_gas_transient.hem_liquid_to_two_phase_projected_fvm_dry_run import (
    HEMProjectedFvmDryRunConfig,
    run_one_projected_fvm_case,
    run_projected_fvm_dry_run_matrix,
    write_projected_fvm_dry_run_artifacts,
)
from liquid_gas_transient.state import PrimitiveState, make_conserved


def _quality_evaluator(rho, e):
    rho_arr = np.asarray(rho, dtype=float)
    e_arr = np.asarray(e, dtype=float)
    open_two_phase = e_arr >= 200.0
    return HEMQualityEvaluation(
        quality=np.where(open_two_phase, 0.25, 0.0),
        quality_defined=np.ones(rho_arr.shape, dtype=bool),
        raw_phase=np.where(open_two_phase, "twophase", "liquid"),
        phase_class=np.where(
            open_two_phase,
            "liquid_vapor_two_phase",
            "compressed_or_subcooled_liquid",
        ),
        scope_status=np.full(
            rho_arr.shape, "supported_candidate", dtype="<U24"
        ),
    )


def _projection_factory(config):
    return HEMEquilibriumQualityProjection(
        evaluator=_quality_evaluator,
        config=config,
    )


class _FakeAcceptedEOS:
    def __init__(self, *, wrong_regions=False):
        self._last_regions = None
        self.wrong_regions = wrong_regions

    @property
    def last_regions(self):
        return (
            None
            if self._last_regions is None
            else self._last_regions.copy()
        )

    def primitive_from_conserved(self, U):
        array = np.asarray(U, dtype=float)
        rho = array[:, 0]
        u = array[:, 1] / rho
        E = array[:, 2] / rho
        e = E - 0.5 * u**2
        q = array[:, 3] / rho
        open_two_phase = e >= 200.0
        regions = np.where(
            open_two_phase, "OPEN_TWO_PHASE", "LIQUID_CANDIDATE"
        )
        if self.wrong_regions:
            regions = np.full(
                regions.shape, "LIQUID_CANDIDATE", dtype="<U40"
            )
        self._last_regions = regions.astype("<U40")
        return PrimitiveState(
            rho=rho.copy(),
            u=u.copy(),
            p=np.where(open_two_phase, 2.0e6, 5.0e6),
            e=e.copy(),
            E=E.copy(),
            T=np.where(open_two_phase, 255.0, 280.0),
            xv=q.copy(),
            alpha=np.where(open_two_phase, 0.8, 0.0),
            c=np.where(open_two_phase, 120.0, 700.0),
        )


def _accepted_eos_factory(
    phase_config,
    quality_sync_config,
    quality_tolerance,
):
    del phase_config, quality_sync_config, quality_tolerance
    return _FakeAcceptedEOS()


def _wrong_eos_factory(
    phase_config,
    quality_sync_config,
    quality_tolerance,
):
    del phase_config, quality_sync_config, quality_tolerance
    return _FakeAcceptedEOS(wrong_regions=True)


def _raw_case(*, crossing: bool) -> MinimalRawFvmCaseResult:
    spec = MinimalFvmDryRunCaseSpec(
        case_id="synthetic_crossing" if crossing else "synthetic_control",
        role="test",
        left_candidate_id="left",
        right_candidate_id="right",
    )
    left = DryRunEndpointState("left", 5.0e6, 5.0, 800.0, 100.0)
    right = DryRunEndpointState(
        "right",
        2.0e6,
        5.0,
        100.0,
        300.0 if crossing else 100.0,
    )
    e = [100.0, 300.0] if crossing else [100.0, 100.0]
    rho = [800.0, 100.0]
    initial_U = make_conserved(rho, 0.0, e, 0.0)
    raw_U = np.array(initial_U, copy=True)
    raw_region = [
        "LIQUID_CANDIDATE",
        "OPEN_TWO_PHASE" if crossing else "LIQUID_CANDIDATE",
    ]
    event = [
        "NO_TRANSITION",
        "LIQUID_TO_TWO_PHASE_CROSSING" if crossing else "NO_TRANSITION",
    ]
    q_eq = [0.0, 0.25 if crossing else 0.0]
    cells = tuple(
        MinimalRawFvmCellRecord(
            case_id=spec.case_id,
            cell_index=index,
            cell_center_m=0.25 + 0.5 * index,
            initial_region="LIQUID_CANDIDATE",
            raw_region=raw_region[index],
            transition_event=event[index],
            rho_initial_kg_m3=rho[index],
            rho_raw_kg_m3=rho[index],
            velocity_initial_m_s=0.0,
            velocity_raw_m_s=0.0,
            e_initial_j_kg=e[index],
            e_raw_j_kg=e[index],
            pressure_initial_pa=5.0e6 if index == 0 else 2.0e6,
            pressure_raw_pa=5.0e6 if index == 0 else 2.0e6,
            temperature_initial_K=280.0 if index == 0 else 255.0,
            temperature_raw_K=280.0 if index == 0 else 255.0,
            q_transport_initial=0.0,
            q_transport_raw=0.0,
            q_equilibrium_initial=0.0,
            q_equilibrium_raw=q_eq[index],
            alpha_initial=0.0,
            alpha_raw=0.8 if crossing and index == 1 else 0.0,
        )
        for index in range(2)
    )
    return MinimalRawFvmCaseResult(
        spec=spec,
        left_state=left,
        right_state=right,
        dt_s=1.0e-4,
        dx_m=0.5,
        target_cfl=0.2,
        measured_initial_cfl=0.2,
        interface_cell=1,
        outcome="OPEN_TWO_PHASE" if crossing else "ALL_LIQUID",
        failure_reason="",
        initial_U=initial_U,
        raw_U=raw_U,
        cells=cells,
        budget_diagnostics={"budget_vapor_mass_net_boundary": 0.0},
        fvm_step_exercised=True,
    )


@pytest.mark.parametrize("value", [-1.0, np.nan])
def test_config_rejects_invalid_accepted_state_tolerance(value):
    with pytest.raises(ValueError, match="accepted_state_quality_tolerance"):
        HEMProjectedFvmDryRunConfig(
            accepted_state_quality_tolerance=value
        )


def test_config_rejects_tolerance_tighter_than_projection_activation():
    with pytest.raises(ValueError, match="projection activation"):
        HEMProjectedFvmDryRunConfig(
            accepted_state_quality_tolerance=1.0e-13,
            projection_config=HEMEquilibriumQualitySyncConfig(
                activation_tolerance=1.0e-12
            ),
        )


@pytest.mark.parametrize("value", [-1.0, np.nan])
def test_config_rejects_invalid_budget_tolerance(value):
    with pytest.raises(ValueError, match="vapor_budget"):
        HEMProjectedFvmDryRunConfig(
            vapor_budget_absolute_tolerance_kg=value
        )


def test_crossing_case_projects_accepts_and_second_projection_is_noop():
    case = run_one_projected_fvm_case(
        _raw_case(crossing=True),
        HEMProjectedFvmDryRunConfig(),
        projection_factory=_projection_factory,
        accepted_eos_factory=_accepted_eos_factory,
    )

    summary = case.summary()
    assert case.outcome == "ACCEPTED_CROSSING"
    assert summary["crossing_cell_indices"] == [1]
    assert summary["first_projection_cell_indices"] == [1]
    assert summary["second_projection_cell_indices"] == []
    assert summary["crossing_and_first_projection_cells_match"] is True
    assert case.first_projection is not None
    assert case.first_projection.summary()["mass_bitwise_unchanged"] is True
    assert (
        case.first_projection.summary()["momentum_bitwise_unchanged"]
        is True
    )
    assert case.first_projection.summary()["energy_bitwise_unchanged"] is True
    np.testing.assert_allclose(
        case.post_U[:, 3] / case.post_U[:, 0],
        [0.0, 0.25],
    )
    assert (
        case.budget_diagnostics[
            "combined_post_vapor_balance_residual_kg"
        ]
        == 0.0
    )
    assert (
        case.budget_diagnostics[
            "projection_source_consistency_residual_kg"
        ]
        == 0.0
    )


def test_all_liquid_control_is_first_and_second_projection_noop():
    case = run_one_projected_fvm_case(
        _raw_case(crossing=False),
        HEMProjectedFvmDryRunConfig(),
        projection_factory=_projection_factory,
        accepted_eos_factory=_accepted_eos_factory,
    )

    summary = case.summary()
    assert case.outcome == "ACCEPTED_ALL_LIQUID_NOOP"
    assert summary["crossing_cell_indices"] == []
    assert summary["first_projection_cell_indices"] == []
    assert summary["second_projection_cell_indices"] == []
    assert np.array_equal(case.post_U, case.raw_case.raw_U)
    assert case.budget_diagnostics["projection_vapor_source_kg"] == 0.0


def test_projection_cell_mismatch_fails_atomically():
    def bad_evaluator(rho, e):
        base = _quality_evaluator(rho, e)
        return HEMQualityEvaluation(
            quality=np.asarray([0.1, 0.25]),
            quality_defined=base.quality_defined,
            raw_phase=base.raw_phase,
            phase_class=base.phase_class,
            scope_status=base.scope_status,
        )

    def bad_projection_factory(config):
        return HEMEquilibriumQualityProjection(
            evaluator=bad_evaluator,
            config=config,
        )

    case = run_one_projected_fvm_case(
        _raw_case(crossing=True),
        HEMProjectedFvmDryRunConfig(),
        projection_factory=bad_projection_factory,
        accepted_eos_factory=_accepted_eos_factory,
    )
    assert case.outcome == "GUARD_FAILURE"
    assert "do not match" in case.failure_reason
    assert case.cells == ()


def test_post_accepted_region_mismatch_fails():
    case = run_one_projected_fvm_case(
        _raw_case(crossing=True),
        HEMProjectedFvmDryRunConfig(),
        projection_factory=_projection_factory,
        accepted_eos_factory=_wrong_eos_factory,
    )
    assert case.outcome == "GUARD_FAILURE"
    assert "regions do not match" in case.failure_reason


def test_raw_unsupported_outcome_is_recorded_without_projection():
    raw = _raw_case(crossing=False)
    raw = MinimalRawFvmCaseResult(
        **{**raw.__dict__, "outcome": "ENDPOINT_LANDING"}
    )
    case = run_one_projected_fvm_case(
        raw,
        HEMProjectedFvmDryRunConfig(),
        projection_factory=_projection_factory,
        accepted_eos_factory=_accepted_eos_factory,
    )
    assert case.outcome == "RAW_STATE_REJECTED"
    assert case.first_projection is None


def test_matrix_summary_and_artifacts(tmp_path):
    raw = HEMMinimalRawFvmDryRunResult(
        config=HEMMinimalRawFvmDryRunConfig(
            n_cells=4,
            interface_cell=2,
            case_specs=(
                MinimalFvmDryRunCaseSpec(
                    "a", "test", "p5_m5", "p2_m5"
                ),
                MinimalFvmDryRunCaseSpec(
                    "b", "test", "p5_m5", "p4_m5"
                ),
            ),
        ),
        survey_summary={"scope": "test"},
        cases=(_raw_case(crossing=True), _raw_case(crossing=False)),
    )
    result = run_projected_fvm_dry_run_matrix(
        HEMProjectedFvmDryRunConfig(raw_config=raw.config),
        raw_result=raw,
        projection_factory=_projection_factory,
        accepted_eos_factory=_accepted_eos_factory,
    )
    summary = result.summary()
    assert summary["all_fixed_cases_completed"] is True
    assert summary["complete_one_step_crossing_path_observed"] is True
    assert summary["actual_first_order_fvm_crossing_verified"] is False

    paths = write_projected_fvm_dry_run_artifacts(tmp_path, result)
    assert set(paths) == {
        "json",
        "cases_csv",
        "cells_csv",
        "markdown",
        "npz",
    }
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["scope"] == "verification_only"
    assert payload["case_a_frozen"] is False
    assert payload["production_hem_activation_approved"] is False
    assert len(payload["cells"]) == 4


@pytest.mark.coolprop_installed
def test_installed_coolprop_fixed_matrix_completes_projection_chain():
    pytest.importorskip("CoolProp")
    result = run_projected_fvm_dry_run_matrix()
    by_id = {case.raw_case.spec.case_id: case for case in result.cases}

    strong = by_id["strong_p5m5_to_p2m5"]
    moderate = by_id["moderate_p5m5_to_p3m5"]
    control = by_id["control_p5m5_to_p4m5"]

    assert strong.outcome == "ACCEPTED_CROSSING"
    assert moderate.outcome == "ACCEPTED_CROSSING"
    assert control.outcome == "ACCEPTED_ALL_LIQUID_NOOP"
    assert strong.summary()["crossing_cell_indices"] == [3, 4]
    assert strong.summary()["first_projection_cell_indices"] == [3, 4]
    assert moderate.summary()["crossing_cell_indices"] == [4]
    assert moderate.summary()["first_projection_cell_indices"] == [4]
    assert control.summary()["first_projection_cell_indices"] == []

    for case in result.cases:
        summary = case.summary()
        assert summary["second_projection_cell_indices"] == []
        assert summary["max_post_quality_mismatch"] <= 1.0e-12
        assert case.post_accepted_state_eos_exercised is True
        assert (
            abs(
                case.budget_diagnostics[
                    "combined_post_vapor_balance_residual_kg"
                ]
            )
            <= 1.0e-12
        )
        assert (
            abs(
                case.budget_diagnostics[
                    "phase_vapor_mass_balance_residual_kg"
                ]
            )
            <= 1.0e-12
        )
        assert np.array_equal(case.second_U, case.post_U)

    assert result.summary()["complete_one_step_crossing_path_observed"] is True
    assert result.summary()["actual_first_order_fvm_crossing_verified"] is False
