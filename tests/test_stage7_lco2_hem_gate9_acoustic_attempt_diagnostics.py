from __future__ import annotations

import csv
import json

import numpy as np
import pytest

from liquid_gas_transient import hem_equilibrium_sound_speed as acoustic_module
from liquid_gas_transient.hem_acoustic_attempt_diagnostics import (
    D3_ALIGNMENT_STATUS,
    D3_MAX_EXISTING_HALVINGS,
    PROPERTY_BACKEND_DESIGN_STATUS,
    PROPERTY_BACKEND_NAME,
    Gate9AcousticAttemptCollector,
    HEMGate9AcousticDiagnosticError,
    observe_equilibrium_acoustic_attempts,
    run_gate9_d3_identity_pair,
    write_gate9_d3_artifacts,
)
from liquid_gas_transient.hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedConfig,
    HEMEquilibriumSoundSpeedError,
    PressurePhaseSample,
)
from liquid_gas_transient.hem_pipeline_crossing_depth_diagnosis import solver_identity
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
)


def _sample(pressure: float, phase: str = "target") -> PressurePhaseSample:
    return PressurePhaseSample(
        pressure_pa=pressure,
        phase_class=phase,
        scope_status="supported_candidate",
    )


def _analytic_evaluator(rho: float, e: float) -> PressurePhaseSample:
    return _sample(1.0e6 + 1.0e4 * rho + 2.0 * e)


def test_d3_observer_records_first_try_density_and_energy_stencils() -> None:
    collector = Gate9AcousticAttemptCollector()
    with observe_equilibrium_acoustic_attempts(collector):
        estimate = acoustic_module.estimate_equilibrium_sound_speed(
            10.0,
            1.0e5,
            _analytic_evaluator,
        )

    attempts = [event for event in collector.events if event.event_kind == "STENCIL_ATTEMPT"]
    final = [event for event in collector.events if event.event_kind == "EVALUATION_RESULT"]
    assert [(event.axis, event.halving_index) for event in attempts] == [
        ("rho", 0),
        ("e", 0),
    ]
    assert all(event.accepted_or_refused == "ACCEPTED" for event in attempts)
    assert len(final) == 1
    assert final[0].accepted_or_refused == "ACCEPTED"
    assert final[0].computed_sound_speed_squared == estimate.sound_speed_squared_m2_s2


def test_d3_observer_retains_exact_halving_sequence_until_phase_match() -> None:
    center_rho = 10.0

    def evaluator(rho: float, e: float) -> PressurePhaseSample:
        phase = "target" if abs(rho - center_rho) <= 0.5 else "other"
        return _sample(1.0e6 + 1.0e4 * rho + 2.0 * e, phase)

    collector = Gate9AcousticAttemptCollector()
    config = HEMEquilibriumSoundSpeedConfig(
        relative_density_step=0.2,
        relative_energy_step=1.0e-4,
        max_step_halvings=6,
    )
    with observe_equilibrium_acoustic_attempts(collector):
        acoustic_module.estimate_equilibrium_sound_speed(
            center_rho,
            1.0e5,
            evaluator,
            config=config,
        )

    density = [
        event
        for event in collector.events
        if event.event_kind == "STENCIL_ATTEMPT" and event.axis == "rho"
    ]
    assert [event.halving_index for event in density] == [0, 1, 2]
    assert [event.trial_step for event in density] == [2.0, 1.0, 0.5]
    assert [event.accepted_or_refused for event in density] == [
        "REFUSED",
        "REFUSED",
        "ACCEPTED",
    ]
    assert density[0].refusal_category == "PHASE_CLASS_MISMATCH"
    assert density[1].refusal_category == "PHASE_CLASS_MISMATCH"


def test_d3_observer_records_all_zero_to_twelve_attempts_on_refusal() -> None:
    def evaluator(rho: float, e: float) -> PressurePhaseSample:
        phase = "target" if rho == 10.0 else "other"
        return _sample(1.0e6 + 1.0e4 * rho + 2.0 * e, phase)

    collector = Gate9AcousticAttemptCollector()
    with pytest.raises(HEMEquilibriumSoundSpeedError, match="after 12 halvings"):
        with observe_equilibrium_acoustic_attempts(collector):
            acoustic_module.estimate_equilibrium_sound_speed(
                10.0,
                1.0e5,
                evaluator,
            )

    density = [
        event
        for event in collector.events
        if event.event_kind == "STENCIL_ATTEMPT" and event.axis == "rho"
    ]
    assert [event.halving_index for event in density] == list(range(13))
    assert all(event.accepted_or_refused == "REFUSED" for event in density)
    final = [event for event in collector.events if event.event_kind == "EVALUATION_RESULT"]
    assert len(final) == 1
    assert final[0].accepted_or_refused == "REFUSED"
    assert (
        final[0].refusal_category
        == "NO_VALID_CENTRAL_RHO_STENCIL_AFTER_MAX_HALVINGS"
    )


def test_d3_observer_does_not_change_scalar_estimate() -> None:
    off = acoustic_module.estimate_equilibrium_sound_speed(
        10.0,
        1.0e5,
        _analytic_evaluator,
    )
    collector = Gate9AcousticAttemptCollector()
    with observe_equilibrium_acoustic_attempts(collector):
        on = acoustic_module.estimate_equilibrium_sound_speed(
            10.0,
            1.0e5,
            _analytic_evaluator,
        )
    assert off == on
    assert collector.events


def test_nested_d3_observer_context_is_rejected() -> None:
    first = Gate9AcousticAttemptCollector()
    second = Gate9AcousticAttemptCollector()
    with observe_equilibrium_acoustic_attempts(first):
        with pytest.raises(HEMGate9AcousticDiagnosticError, match="nested"):
            with observe_equilibrium_acoustic_attempts(second):
                pass


@pytest.fixture(scope="module")
def installed_d3_identity_pair():
    pytest.importorskip("CoolProp")
    return run_gate9_d3_identity_pair(
        FIXED_PIPELINE_DEPRESSURIZATION_CASES[0],
        HEMPipelineDepressurizationConfig(),
    )


@pytest.mark.coolprop_installed
def test_installed_d3_observer_preserves_gate8_cfl_0p10_identity(
    installed_d3_identity_pair,
) -> None:
    off, on, result = installed_d3_identity_pair
    assert solver_identity(off) == solver_identity(on)
    assert np.array_equal(off.time_history_s, on.time_history_s)
    assert np.array_equal(off.pressure_history_pa, on.pressure_history_pa)
    assert np.array_equal(off.accepted_state_history, on.accepted_state_history)

    summary = result.summary()
    assert summary["property_backend_name"] == PROPERTY_BACKEND_NAME
    assert summary["property_backend_design_status"] == PROPERTY_BACKEND_DESIGN_STATUS
    assert summary["production_acoustic_evaluation_count"] > 0
    assert summary["density_attempt_record_count"] > 0
    assert summary["energy_attempt_record_count"] > 0
    assert summary["maximum_observed_halving_index"] <= D3_MAX_EXISTING_HALVINGS
    assert summary["halving_limit_preserved"] is True
    assert summary["all_evaluations_have_final_record"] is True
    assert summary["diagnostic_off_on_identity"] is True
    assert summary["event_alignment_status"] == D3_ALIGNMENT_STATUS
    assert summary["candidate_summary"]["candidate_step"] == 125
    assert summary["candidate_summary"]["candidate_time_s"] == 7.999325695335248e-4
    assert summary["candidate_summary"]["candidate_cells"] == [29]
    assert (
        summary["candidate_summary"]["maximum_candidate_q_equilibrium"]
        == 3.773646403587342e-6
    )
    assert summary["Gate_9_execution_complete"] is False


@pytest.mark.coolprop_installed
def test_d3_writer_emits_raw_unaligned_attempt_artifact(
    installed_d3_identity_pair,
    tmp_path,
) -> None:
    _, _, result = installed_d3_identity_pair
    paths = write_gate9_d3_artifacts(tmp_path, result)
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["event_alignment_status"] == D3_ALIGNMENT_STATUS
    assert summary["acoustic_event_record_count"] == len(result.events)
    assert summary["Gate_9_execution_complete"] is False

    with paths["acoustic"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(result.events)
    assert {row["event_kind"] for row in rows} >= {
        "STENCIL_ATTEMPT",
        "EVALUATION_RESULT",
    }
    assert all(
        row["halving_index"] == ""
        or 0 <= int(row["halving_index"]) <= D3_MAX_EXISTING_HALVINGS
        for row in rows
    )
    assert paths["digest"].read_text(encoding="utf-8").count("\n") == 3
