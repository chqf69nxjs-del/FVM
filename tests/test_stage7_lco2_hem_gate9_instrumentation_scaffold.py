from __future__ import annotations

import csv
import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.hem_pipeline_crossing_depth_diagnosis import (
    GATE9_D1_CAPTURED_STAGES,
    GATE9_FOCUS_CELLS,
    GATE9_FOCUS_INTERFACES,
    GATE9_PENDING_STAGES,
    Gate9CellStageRecord,
    instrument_pipeline_case_result,
    run_gate9_d1_identity_pair,
    solver_identity,
    write_gate9_d1_scaffold_artifacts,
)
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    _state_sha256,
)


def _synthetic_result():
    n_cells = 32
    rho = 900.0
    internal = 2.0e5
    initial = np.zeros((n_cells, 4), dtype=float)
    initial[:, 0] = rho
    initial[:, 2] = rho * internal
    final = np.array(initial, copy=True)
    final[29, 3] = rho * 2.0e-6
    raw = np.array(initial, copy=True)
    raw[29, 0] = rho - 0.25
    raw[29, 1] = 2.0
    raw[29, 2] = (rho - 0.25) * (internal + 1.0)

    cells = []
    for index in range(n_cells):
        raw_rho = float(raw[index, 0])
        raw_u = float(raw[index, 1] / raw_rho)
        raw_e = float(raw[index, 2] / raw_rho - 0.5 * raw_u * raw_u)
        crossing = index == 29
        cells.append(
            SimpleNamespace(
                step_index=1,
                cell_index=index,
                previous_region="LIQUID_CANDIDATE",
                raw_region="OPEN_TWO_PHASE" if crossing else "LIQUID_CANDIDATE",
                post_region="OPEN_TWO_PHASE" if crossing else "LIQUID_CANDIDATE",
                transition_event=(
                    "LIQUID_TO_TWO_PHASE_CROSSING" if crossing else "NO_TRANSITION"
                ),
                rho_raw_kg_m3=raw_rho,
                velocity_raw_m_s=raw_u,
                e_raw_j_kg=raw_e,
                pressure_raw_pa=4.9e6 - index,
                temperature_raw_K=280.0,
                q_transport_raw=0.0,
                q_equilibrium=2.0e-6 if crossing else 0.0,
                q_post=2.0e-6 if crossing else 0.0,
                alpha_post=1.0e-4 if crossing else 0.0,
                sound_speed_post_m_s=500.0 if crossing else 800.0,
                first_projection_applied=crossing,
                second_projection_applied=False,
            )
        )

    step = SimpleNamespace(
        step_index=1,
        time_before_s=0.0,
        dt_s=1.0e-6,
        time_after_s=1.0e-6,
        state_sha256=_state_sha256(final),
    )
    return SimpleNamespace(
        case=SimpleNamespace(case_id="pipeline_crossing_candidate_p5m5_to_p2m5"),
        config=SimpleNamespace(cfl=0.10, n_cells=n_cells),
        outcome="ACCEPTED_FIRST_CROSSING",
        failure_reason="",
        step_count=1,
        final_time_s=1.0e-6,
        crossing_step=1,
        crossing_time_s=1.0e-6,
        crossing_cell_indices=(29,),
        crossing_distances_from_outlet_m=(0.078125,),
        maximum_crossing_quality=2.0e-6,
        final_state_sha256=_state_sha256(final),
        run_signature_sha256="synthetic-signature",
        steps=(step,),
        cells=tuple(cells),
        time_history_s=np.asarray([0.0, 1.0e-6]),
        pressure_history_pa=np.vstack(
            [np.full(n_cells, 5.0e6), np.full(n_cells, 4.9e6)]
        ),
        accepted_state_history=np.stack([initial, final]),
    )


def test_d1_fixed_focus_and_stage_contract() -> None:
    assert GATE9_FOCUS_CELLS == (28, 29, 30, 31)
    assert GATE9_FOCUS_INTERFACES == (
        "27|28",
        "28|29",
        "29|30",
        "30|31",
        "RIGHT_BOUNDARY",
    )
    assert GATE9_D1_CAPTURED_STAGES == (
        "PRE_STEP_ACCEPTED",
        "RAW_POST_FVM",
        "FINAL_ACCEPTED_IF_AVAILABLE",
    )
    assert GATE9_PENDING_STAGES == (
        "POST_FIRST_PROJECTION_IF_AVAILABLE",
        "POST_SECOND_PROJECTION_IF_AVAILABLE",
    )


def test_d1_instrumentation_is_read_only_and_explicit_about_missing_fields() -> None:
    result = _synthetic_result()
    before_time = result.time_history_s.copy()
    before_pressure = result.pressure_history_pa.copy()
    before_state = result.accepted_state_history.copy()

    diagnostics = instrument_pipeline_case_result(result)

    assert np.array_equal(result.time_history_s, before_time)
    assert np.array_equal(result.pressure_history_pa, before_pressure)
    assert np.array_equal(result.accepted_state_history, before_state)
    assert diagnostics.solver_state_preserved is True
    assert diagnostics.diagnostic_status == "D1_CAPTURE_COMPLETE"
    assert diagnostics.diagnostic_failures == ()
    assert len(diagnostics.cell_stage_records) == 12
    assert diagnostics.interface_flux_records == ()
    assert diagnostics.acoustic_attempt_records == ()
    assert diagnostics.interface_capture_status == "PENDING_D2_RUSANOV_DECOMPOSITION"
    assert diagnostics.acoustic_capture_status == "PENDING_D3_ACOUSTIC_ATTEMPT_HOOKS"

    raw_29 = next(
        row
        for row in diagnostics.cell_stage_records
        if row.stage == "RAW_POST_FVM" and row.cell_index == 29
    )
    final_29 = next(
        row
        for row in diagnostics.cell_stage_records
        if row.stage == "FINAL_ACCEPTED_IF_AVAILABLE" and row.cell_index == 29
    )
    assert raw_29.q_internal_energy_coordinate is None
    assert raw_29.q_specific_volume_coordinate is None
    assert raw_29.delta_e_from_saturated_liquid is None
    assert raw_29.delta_v_from_saturated_liquid is None
    assert raw_29.sound_speed_branch == "NOT_CAPTURED_D1_PENDING_D3"
    assert raw_29.void_fraction is None
    assert final_29.first_projection_applied is True
    assert final_29.first_projection_delta_rho_q == pytest.approx(900.0 * 2.0e-6)
    assert final_29.second_projection_exact_noop is None


def test_d1_records_are_frozen() -> None:
    diagnostics = instrument_pipeline_case_result(_synthetic_result())
    row = diagnostics.cell_stage_records[0]
    assert isinstance(row, Gate9CellStageRecord)
    with pytest.raises(FrozenInstanceError):
        row.rho = 1.0  # type: ignore[misc]


def test_d1_writer_emits_headers_for_pending_d2_d3_tables(tmp_path: Path) -> None:
    diagnostics = instrument_pipeline_case_result(_synthetic_result())
    paths = write_gate9_d1_scaffold_artifacts(tmp_path, diagnostics)

    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["solver_state_preserved"] is True
    assert summary["Gate_9_execution_complete"] is False
    assert summary["interface_flux_record_count"] == 0
    assert summary["acoustic_attempt_record_count"] == 0

    with paths["interfaces"].open(newline="", encoding="utf-8") as handle:
        interface_header = next(csv.reader(handle))
    with paths["acoustic"].open(newline="", encoding="utf-8") as handle:
        acoustic_header = next(csv.reader(handle))
    assert "normalized_reconstruction_residual" in interface_header
    assert "halving_index" in acoustic_header
    assert paths["digest"].read_text(encoding="utf-8").count("\n") == 5


@pytest.fixture(scope="module")
def installed_identity_pair():
    pytest.importorskip("CoolProp")
    case = FIXED_PIPELINE_DEPRESSURIZATION_CASES[0]
    config = HEMPipelineDepressurizationConfig()
    return run_gate9_d1_identity_pair(case, config)


@pytest.mark.coolprop_installed
def test_installed_diagnostic_off_on_paths_are_exactly_identical(
    installed_identity_pair,
) -> None:
    diagnostic_off, diagnostic_on, diagnostics = installed_identity_pair

    assert solver_identity(diagnostic_off) == solver_identity(diagnostic_on)
    assert np.array_equal(
        diagnostic_off.time_history_s,
        diagnostic_on.time_history_s,
    )
    assert np.array_equal(
        diagnostic_off.pressure_history_pa,
        diagnostic_on.pressure_history_pa,
    )
    assert np.array_equal(
        diagnostic_off.accepted_state_history,
        diagnostic_on.accepted_state_history,
    )
    assert diagnostics.solver_state_preserved is True
    assert diagnostics.diagnostic_failures == ()
    assert diagnostic_on.outcome == "ACCEPTED_FIRST_CROSSING"
    assert diagnostic_on.step_count == 125
    assert diagnostic_on.crossing_step == 125
    assert diagnostic_on.crossing_time_s == 7.999325695335248e-4
    assert diagnostic_on.crossing_cell_indices == (29,)
    assert diagnostic_on.maximum_crossing_quality == 3.773646403587342e-6
    assert len(diagnostics.cell_stage_records) == 125 * 4 * 3
    assert diagnostics.candidate_summary.formal_outcome == diagnostic_on.outcome
    assert (
        diagnostics.candidate_summary.final_state_sha256
        == diagnostic_on.final_state_sha256
    )
