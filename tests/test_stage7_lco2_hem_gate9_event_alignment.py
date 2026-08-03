from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from liquid_gas_transient.hem_gate9_event_alignment import (
    D4_CAPTURED_STAGES,
    D4_CFL_NO_NEW_TRIALS,
    D4_CFL_TRIALS_OBSERVED,
    D4_POST_STATUS_FORMAL_STOP,
    D4_SCHEMA_VERSION,
    Gate9D4StateSnapshot,
    _exact_cell_records,
    _window_steps,
    run_gate9_d4_identity_pair,
    write_gate9_d4_artifacts,
)
from liquid_gas_transient.hem_pipeline_crossing_depth_diagnosis import (
    GATE9_FOCUS_CELLS,
    solver_identity,
)
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
)
from liquid_gas_transient.state import N_VARS


def test_d4_window_ends_honestly_at_formal_candidate_stop() -> None:
    result = type(
        "Result",
        (),
        {"crossing_step": 125, "step_count": 125},
    )()
    steps, start, post_count, status = _window_steps(result)
    assert steps == tuple(range(117, 126))
    assert start == 117
    assert post_count == 0
    assert status == D4_POST_STATUS_FORMAL_STOP


def test_d4_exact_cell_records_preserve_all_five_stages() -> None:
    snapshots = []
    for stage_index, stage in enumerate(D4_CAPTURED_STAGES):
        state = np.zeros((32, N_VARS), dtype=float)
        state[:, 0] = 800.0 + stage_index
        state[:, 1] = 2.0
        state[:, 2] = state[:, 0] * 2.0e5
        state[:, 3] = 0.0
        state.setflags(write=False)
        snapshots.append(
            Gate9D4StateSnapshot(
                case_id="case",
                cfl=0.10,
                absolute_step=125,
                absolute_time_s=1.0,
                dt_s=1.0e-6,
                stage=stage,
                state=state,
                state_sha256=f"sha-{stage_index}",
            )
        )
    records = _exact_cell_records(
        snapshots,
        candidate_step=125,
        window_steps={125},
    )
    assert len(records) == len(D4_CAPTURED_STAGES) * len(GATE9_FOCUS_CELLS)
    assert {record.stage for record in records} == set(D4_CAPTURED_STAGES)
    assert all(record.candidate_relative_step == 0 for record in records)


@pytest.fixture(scope="module")
def installed_d4_identity_pair():
    pytest.importorskip("CoolProp")
    return run_gate9_d4_identity_pair(
        FIXED_PIPELINE_DEPRESSURIZATION_CASES[0],
        HEMPipelineDepressurizationConfig(),
    )


@pytest.mark.coolprop_installed
def test_installed_d4_aligns_d1_d2_d3_and_cfl_without_changing_solver(
    installed_d4_identity_pair,
) -> None:
    off, on, result = installed_d4_identity_pair
    assert solver_identity(off) == solver_identity(on)
    assert np.array_equal(off.time_history_s, on.time_history_s)
    assert np.array_equal(off.pressure_history_pa, on.pressure_history_pa)
    assert np.array_equal(off.accepted_state_history, on.accepted_state_history)

    summary = result.summary()
    assert summary["schema_version"] == D4_SCHEMA_VERSION
    assert summary["candidate_step"] == 125
    assert summary["candidate_time_s"] == 7.999325695335248e-4
    assert summary["window_steps"] == list(range(117, 126))
    assert summary["available_pre_step_count"] == 8
    assert summary["available_post_step_count"] == 0
    assert summary["post_window_status"] == D4_POST_STATUS_FORMAL_STOP
    assert summary["exact_cell_stage_record_count"] == 9 * 5 * 4
    assert summary["d1_cell_stage_record_count"] == 9 * 3 * 4
    assert summary["interface_flux_record_count"] == 9 * 5
    assert summary["cfl_decision_record_count"] == 9
    assert summary["aligned_acoustic_record_count"] > 0
    assert summary["all_acoustic_records_have_step_cell_stage_dt"] is True
    assert summary["all_cfl_decisions_match_production_dt"] is True
    assert summary["all_timeline_records_have_source_time"] is True
    assert summary["rusanov_reconstruction_guard_passed"] is True
    assert summary["diagnostic_off_on_identity"] is True
    assert summary["cfl_dt_acoustic_trial_capture_status"] in {
        D4_CFL_NO_NEW_TRIALS,
        D4_CFL_TRIALS_OBSERVED,
    }
    assert summary["Gate_9_execution_complete"] is False


@pytest.mark.coolprop_installed
def test_d4_writer_emits_source_timed_event_aligned_artifact(
    installed_d4_identity_pair,
    tmp_path,
) -> None:
    _, _, result = installed_d4_identity_pair
    paths = write_gate9_d4_artifacts(tmp_path, result)
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["schema_version"] == D4_SCHEMA_VERSION
    assert summary["exact_cell_stage_record_count"] == 180
    assert summary["d1_cell_stage_record_count"] == 108
    assert summary["interface_flux_record_count"] == 45
    assert summary["cfl_decision_record_count"] == 9
    assert summary["aligned_acoustic_record_count"] > 0
    assert summary["all_timeline_records_have_source_time"] is True

    def rows(key: str) -> list[dict[str, str]]:
        with paths[key].open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    exact_rows = rows("exact_cells")
    interface_rows = rows("interfaces")
    acoustic_rows = rows("acoustic")
    cfl_rows = rows("cfl")
    timeline_rows = rows("timeline")

    assert len(exact_rows) == 180
    assert len(interface_rows) == 45
    assert len(cfl_rows) == 9
    assert acoustic_rows
    assert timeline_rows
    assert {row["stage"] for row in exact_rows} == set(D4_CAPTURED_STAGES)
    assert all(
        row["absolute_step"]
        and row["cell_index"]
        and row["stage"]
        and float(row["dt_s"]) > 0.0
        for row in acoustic_rows
    )
    assert all(float(row["absolute_time_s"]) > 0.0 for row in timeline_rows)
    assert all(row["formula_identity_passed"] == "True" for row in cfl_rows)

    source_interface_times = {
        (row["absolute_step"], row["interface_id"]): row["absolute_time_s"]
        for row in interface_rows
    }
    timeline_interface_times = {
        (row["absolute_step"], row["entity_id"]): row["absolute_time_s"]
        for row in timeline_rows
        if row["entity_type"] == "INTERFACE"
    }
    assert timeline_interface_times == source_interface_times
    assert paths["digest"].read_text(encoding="utf-8").count("\n") == 8
