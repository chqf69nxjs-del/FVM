from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.hem_liquid_to_two_phase_first_crossing_case_ab import (
    CaseABRunRecord,
    HEMFirstCrossingCaseABConfig,
    _state_sha256,
    evaluate_case_ab_freeze,
    run_first_crossing_case_ab_freeze,
    write_first_crossing_case_ab_artifacts,
)


def _fake_run(
    *,
    role: str,
    repeat_index: int,
    outcome: str,
    signature: str,
    final_time_s: float = 1.0e-4,
    target_time_s: float | None = None,
    crossing_step: int | None = 1,
    crossing_time_s: float | None = 1.0e-4,
    crossing_cells: tuple[int, ...] = (3, 4),
    projection_cells: tuple[int, ...] = (3, 4),
) -> CaseABRunRecord:
    if role == "Case B":
        crossing_step = None
        crossing_time_s = None
        crossing_cells = ()
        projection_cells = ()
    return CaseABRunRecord(
        case_id="case_a" if role == "Case A" else "case_b",
        role=role,
        repeat_index=repeat_index,
        outcome=outcome,
        failure_reason="",
        step_count=1,
        final_time_s=final_time_s,
        target_time_s=target_time_s,
        crossing_step=crossing_step,
        crossing_time_s=crossing_time_s,
        crossing_cell_indices=crossing_cells,
        projection_cell_indices=projection_cells,
        maximum_crossing_quality=5.0e-4 if role == "Case A" else 0.0,
        cumulative_projection_vapor_source_kg=7.0e-4 if role == "Case A" else 0.0,
        final_state_sha256="a" * 64 if role == "Case A" else "b" * 64,
        repeatability_signature=signature,
        steps=(),
        cells=(),
        boundary_budget_diagnostics={
            "budget_mass_residual": 0.0,
            "budget_momentum_residual": 0.0,
            "budget_energy_residual": 0.0,
        },
        phase_budget_diagnostics={
            "phase_vapor_mass_balance_residual_kg": 0.0,
        },
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"case_a_case_id": "same", "case_b_case_id": "same"},
        {"repeat_count": 1},
        {"case_a_max_steps": 0},
        {"crossing_evidence_min_quality": 0.0},
        {"crossing_evidence_min_quality": 1.0},
        {"time_match_absolute_tolerance_s": -1.0},
        {"conservative_budget_absolute_tolerance": np.nan},
    ],
)
def test_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        HEMFirstCrossingCaseABConfig(**kwargs)


def test_state_sha256_is_deterministic_and_state_sensitive():
    U = np.asarray([[1.0, 2.0, 3.0, 4.0]], dtype=float)
    assert _state_sha256(U) == _state_sha256(np.array(U, copy=True))
    changed = np.array(U, copy=True)
    changed[0, 3] += 1.0e-12
    assert _state_sha256(U) != _state_sha256(changed)


def test_freeze_decision_accepts_repeatable_case_a_and_time_matched_case_b():
    cfg = HEMFirstCrossingCaseABConfig()
    a = tuple(
        _fake_run(
            role="Case A",
            repeat_index=index,
            outcome="ACCEPTED_CROSSING",
            signature="sig-a",
        )
        for index in range(cfg.repeat_count)
    )
    b = tuple(
        _fake_run(
            role="Case B",
            repeat_index=index,
            outcome="MATCHED_ALL_LIQUID",
            signature="sig-b",
            final_time_s=1.0e-4,
            target_time_s=1.0e-4,
        )
        for index in range(cfg.repeat_count)
    )

    summary = evaluate_case_ab_freeze(
        cfg,
        survey_summary={"candidate_count": 11},
        case_a_runs=a,
        case_b_runs=b,
    ).summary()

    assert summary["case_a_repeatable"] is True
    assert summary["case_b_repeatable"] is True
    assert summary["case_b_matched_physical_time"] is True
    assert summary["case_a_frozen"] is True
    assert summary["case_b_frozen"] is True
    assert summary["actual_first_order_fvm_crossing_verified"] is True
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False


def test_freeze_decision_rejects_case_a_signature_mismatch():
    cfg = HEMFirstCrossingCaseABConfig()
    a = tuple(
        _fake_run(
            role="Case A",
            repeat_index=index,
            outcome="ACCEPTED_CROSSING",
            signature=f"sig-a-{index}",
        )
        for index in range(cfg.repeat_count)
    )
    b = tuple(
        _fake_run(
            role="Case B",
            repeat_index=index,
            outcome="MATCHED_ALL_LIQUID",
            signature="sig-b",
            final_time_s=1.0e-4,
            target_time_s=1.0e-4,
        )
        for index in range(cfg.repeat_count)
    )
    summary = evaluate_case_ab_freeze(
        cfg,
        survey_summary={},
        case_a_runs=a,
        case_b_runs=b,
    ).summary()
    assert summary["case_a_frozen"] is False
    assert summary["actual_first_order_fvm_crossing_verified"] is False


def test_freeze_decision_rejects_unmatched_control_time():
    cfg = HEMFirstCrossingCaseABConfig()
    a = tuple(
        _fake_run(
            role="Case A",
            repeat_index=index,
            outcome="ACCEPTED_CROSSING",
            signature="sig-a",
        )
        for index in range(cfg.repeat_count)
    )
    b = tuple(
        _fake_run(
            role="Case B",
            repeat_index=index,
            outcome="MATCHED_ALL_LIQUID",
            signature="sig-b",
            final_time_s=2.0e-4,
            target_time_s=1.0e-4,
        )
        for index in range(cfg.repeat_count)
    )
    summary = evaluate_case_ab_freeze(
        cfg,
        survey_summary={},
        case_a_runs=a,
        case_b_runs=b,
    ).summary()
    assert summary["case_a_frozen"] is True
    assert summary["case_b_matched_physical_time"] is False
    assert summary["case_b_frozen"] is False
    assert summary["actual_first_order_fvm_crossing_verified"] is False


def test_freeze_decision_rejects_control_crossing():
    cfg = HEMFirstCrossingCaseABConfig()
    a = tuple(
        _fake_run(
            role="Case A",
            repeat_index=index,
            outcome="ACCEPTED_CROSSING",
            signature="sig-a",
        )
        for index in range(cfg.repeat_count)
    )
    b = tuple(
        _fake_run(
            role="Case B",
            repeat_index=index,
            outcome="FORBIDDEN_TRANSITION",
            signature="sig-b",
            final_time_s=1.0e-4,
            target_time_s=1.0e-4,
        )
        for index in range(cfg.repeat_count)
    )
    summary = evaluate_case_ab_freeze(
        cfg,
        survey_summary={},
        case_a_runs=a,
        case_b_runs=b,
    ).summary()
    assert summary["case_b_repeatable"] is False
    assert summary["case_b_frozen"] is False


def test_artifact_writer_retains_freeze_and_approval_flags(tmp_path):
    cfg = HEMFirstCrossingCaseABConfig()
    a = tuple(
        _fake_run(
            role="Case A",
            repeat_index=index,
            outcome="ACCEPTED_CROSSING",
            signature="sig-a",
        )
        for index in range(cfg.repeat_count)
    )
    b = tuple(
        _fake_run(
            role="Case B",
            repeat_index=index,
            outcome="MATCHED_ALL_LIQUID",
            signature="sig-b",
            final_time_s=1.0e-4,
            target_time_s=1.0e-4,
        )
        for index in range(cfg.repeat_count)
    )
    result = evaluate_case_ab_freeze(
        cfg,
        survey_summary={"candidate_count": 11},
        case_a_runs=a,
        case_b_runs=b,
    )
    paths = write_first_crossing_case_ab_artifacts(tmp_path, result)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))

    assert set(paths) == {
        "json",
        "runs_csv",
        "steps_csv",
        "cells_csv",
        "markdown",
        "npz",
    }
    assert all(path.exists() for path in paths.values())
    assert payload["case_a_frozen"] is True
    assert payload["case_b_frozen"] is True
    assert payload["actual_first_order_fvm_crossing_verified"] is True
    assert payload["software_verification_only"] is True
    assert payload["production_hem_activation_approved"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False


@pytest.mark.coolprop_installed
def test_installed_coolprop_repeats_and_freezes_case_a_and_case_b():
    coolprop = pytest.importorskip("CoolProp")
    assert coolprop.__version__ == "8.0.0"

    result = run_first_crossing_case_ab_freeze()
    summary = result.summary()

    assert summary["repeat_count"] == 3
    assert summary["case_a_repeatable"] is True
    assert summary["case_b_repeatable"] is True
    assert summary["case_b_matched_physical_time"] is True
    assert summary["case_a_frozen"] is True
    assert summary["case_b_frozen"] is True
    assert summary["actual_first_order_fvm_crossing_verified"] is True
    assert summary["case_a_crossing_step"] == 1
    assert summary["case_a_crossing_cell_indices"] == [3, 4]
    assert summary["case_a_crossing_time_s"] == pytest.approx(
        3.356317173211922e-5,
        rel=1.0e-12,
    )

    assert len({run.repeatability_signature for run in result.case_a_runs}) == 1
    assert len({run.repeatability_signature for run in result.case_b_runs}) == 1

    for run in result.case_a_runs:
        assert run.outcome == "ACCEPTED_CROSSING"
        assert run.step_count == 1
        assert run.crossing_step == 1
        assert run.crossing_cell_indices == (3, 4)
        assert run.projection_cell_indices == (3, 4)
        assert run.maximum_crossing_quality == pytest.approx(
            5.911503500507591e-4,
            rel=1.0e-12,
        )
        assert run.cumulative_projection_vapor_source_kg == pytest.approx(
            7.054022964126832e-4,
            rel=1.0e-12,
        )
        assert abs(
            run.phase_budget_diagnostics[
                "phase_vapor_mass_balance_residual_kg"
            ]
        ) <= 1.0e-12

    target = float(summary["case_a_crossing_time_s"])
    for run in result.case_b_runs:
        assert run.outcome == "MATCHED_ALL_LIQUID"
        assert run.step_count == 1
        assert run.crossing_cell_indices == ()
        assert run.projection_cell_indices == ()
        assert run.cumulative_projection_vapor_source_kg == 0.0
        assert run.final_time_s == pytest.approx(target, abs=1.0e-15)
        assert all(
            cell.post_region == "LIQUID_CANDIDATE" for cell in run.cells
        )
