from __future__ import annotations

import csv
import json
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.eos import LinearLiquidEOS
from liquid_gas_transient.flux import observe_rusanov_flux, rusanov_flux
from liquid_gas_transient.hem_pipeline_crossing_depth_diagnosis import solver_identity
from liquid_gas_transient.hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
)
from liquid_gas_transient.hem_rusanov_diagnostic_decomposition import (
    D2_CAPTURE_STATUS,
    PROPERTY_BACKEND_DESIGN_STATUS,
    PROPERTY_BACKEND_NAME,
    RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE,
    build_gate9_interface_flux_records,
    decompose_rusanov_interface,
    run_gate9_d2_identity_pair,
    write_gate9_d2_artifacts,
)
from liquid_gas_transient.state import N_VARS, make_conserved


def _observed_flux(U_left: np.ndarray, U_right: np.ndarray):
    captured = []
    with observe_rusanov_flux(captured.append):
        production = rusanov_flux(U_left, U_right, LinearLiquidEOS())
    assert len(captured) == 1
    return production, captured[0]


def test_production_rusanov_observer_is_read_only_and_exact() -> None:
    U_left = make_conserved(
        rho=np.asarray([1000.0, 1000.01]),
        u=np.asarray([1.0, -0.25]),
        e=np.asarray([1.0e5, 1.01e5]),
        xv=np.asarray([0.0, 2.0e-6]),
    )
    U_right = make_conserved(
        rho=np.asarray([999.99, 1000.02]),
        u=np.asarray([0.5, 0.1]),
        e=np.asarray([1.02e5, 0.99e5]),
        xv=np.asarray([1.0e-6, 3.0e-6]),
    )

    production, evaluation = _observed_flux(U_left, U_right)

    assert np.array_equal(evaluation.production_flux, production)
    for values in (
        evaluation.left_conserved_state,
        evaluation.right_conserved_state,
        evaluation.left_physical_flux,
        evaluation.right_physical_flux,
        evaluation.maximum_wave_speed,
        evaluation.production_flux,
    ):
        assert values.flags.writeable is False
    with pytest.raises(ValueError):
        evaluation.production_flux[0, 0] = 0.0

    for index in range(production.shape[0]):
        *_, residual = decompose_rusanov_interface(evaluation, index)
        assert residual <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE


def test_zero_jump_has_zero_dissipative_component() -> None:
    state = make_conserved(1000.0, 0.75, 1.0e5, 2.0e-6)[np.newaxis, :]
    production, evaluation = _observed_flux(state, state.copy())
    (
        _,
        _,
        left_flux,
        right_flux,
        _,
        central,
        dissipative,
        reconstructed,
        observed_production,
        residual,
    ) = decompose_rusanov_interface(evaluation, 0)

    assert np.array_equal(left_flux, right_flux)
    assert np.array_equal(dissipative, np.zeros(N_VARS))
    assert np.array_equal(central, reconstructed)
    assert np.array_equal(observed_production, production[0])
    assert residual <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE


def test_focused_interface_mapping_and_cell_increment_signs() -> None:
    n_cells = 32
    n_ghost = 2
    n_extended = n_cells + 2 * n_ghost
    rho = 1000.0 + np.linspace(0.0, 0.02, n_extended)
    velocity = np.linspace(-0.2, 0.4, n_extended)
    energy = np.full(n_extended, 1.0e5)
    quality = np.linspace(0.0, 3.0e-6, n_extended)
    extended = make_conserved(rho, velocity, energy, quality)
    _, evaluation = _observed_flux(extended[:-1], extended[1:])

    result = SimpleNamespace(
        case=SimpleNamespace(case_id="pipeline_crossing_candidate_p5m5_to_p2m5"),
        config=SimpleNamespace(
            cfl=0.10,
            n_cells=n_cells,
            n_ghost=n_ghost,
            dx_m=1.0 / n_cells,
        ),
        steps=(
            SimpleNamespace(
                step_index=1,
                time_before_s=0.0,
                dt_s=1.0e-6,
            ),
        ),
    )
    records = build_gate9_interface_flux_records(result, (evaluation,))

    assert [record.interface_id for record in records] == [
        "27|28",
        "28|29",
        "29|30",
        "30|31",
        "RIGHT_BOUNDARY",
    ]
    assert len(records) == 5
    for record in records:
        assert record.capture_status == D2_CAPTURE_STATUS
        assert (
            record.normalized_reconstruction_residual
            <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE
        )
        assert record.left_cell_increment_over_dt_dx is not None
        if record.right_cell is None:
            assert record.right_cell_increment_over_dt_dx is None
        else:
            assert np.allclose(
                np.asarray(record.left_cell_increment_over_dt_dx)
                + np.asarray(record.right_cell_increment_over_dt_dx),
                0.0,
                rtol=0.0,
                atol=0.0,
            )


@pytest.fixture(scope="module")
def installed_d2_identity_pair():
    pytest.importorskip("CoolProp")
    case = FIXED_PIPELINE_DEPRESSURIZATION_CASES[0]
    config = HEMPipelineDepressurizationConfig()
    return run_gate9_d2_identity_pair(case, config)


@pytest.mark.coolprop_installed
def test_installed_d2_observer_preserves_gate8_cfl_0p10_identity(
    installed_d2_identity_pair,
) -> None:
    diagnostic_off, diagnostic_on, result = installed_d2_identity_pair

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
    assert result.diagnostic_off_on_identity is True
    assert result.production_evaluation_count == 125
    assert len(result.interface_flux_records) == 125 * 5
    assert (
        result.maximum_normalized_reconstruction_residual
        <= RUSANOV_NORMALIZED_RESIDUAL_TOLERANCE
    )
    assert diagnostic_on.outcome == "ACCEPTED_FIRST_CROSSING"
    assert diagnostic_on.step_count == 125
    assert diagnostic_on.crossing_step == 125
    assert diagnostic_on.crossing_time_s == 7.999325695335248e-4
    assert diagnostic_on.crossing_cell_indices == (29,)
    assert diagnostic_on.maximum_crossing_quality == 3.773646403587342e-6


@pytest.mark.coolprop_installed
def test_d2_writer_emits_locked_interface_artifact(
    installed_d2_identity_pair,
    tmp_path,
) -> None:
    _, _, result = installed_d2_identity_pair
    paths = write_gate9_d2_artifacts(tmp_path, result)

    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    assert summary["property_backend_name"] == PROPERTY_BACKEND_NAME
    assert (
        summary["property_backend_design_status"]
        == PROPERTY_BACKEND_DESIGN_STATUS
    )
    assert summary["production_evaluation_count"] == 125
    assert summary["interface_flux_record_count"] == 625
    assert summary["rusanov_reconstruction_guard_passed"] is True
    assert summary["diagnostic_off_on_identity"] is True
    assert summary["Gate_9_execution_complete"] is False

    with paths["interfaces"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 625
    assert {row["interface_id"] for row in rows} == {
        "27|28",
        "28|29",
        "29|30",
        "30|31",
        "RIGHT_BOUNDARY",
    }
    assert paths["digest"].read_text(encoding="utf-8").count("\n") == 5
