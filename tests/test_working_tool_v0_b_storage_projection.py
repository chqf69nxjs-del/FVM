from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from liquid_gas_transient.working_tool.case_schema import ModelProfile
from liquid_gas_transient.working_tool.operation_policy import (
    WorkingToolStateStorageMode,
)
from liquid_gas_transient.working_tool.results import (
    PROVISIONAL_MODEL_WARNING,
    WorkingToolResult,
)
from liquid_gas_transient.working_tool.storage_projection import (
    REQUIRED_STATE_ARRAYS,
    SAMPLE_AXIS_STATE_ARRAYS,
    STATIC_STATE_ARRAYS,
    StateStorageProjectionError,
    project_state_storage,
    retained_state_indices,
    validate_full_state_result,
)


def _full_result(*, accepted_steps: int = 640, n_cells: int = 3) -> WorkingToolResult:
    samples = accepted_steps + 1
    time_s = np.arange(samples, dtype=np.float64) * 1.0e-6
    x_m = np.linspace(0.0, 1.0, n_cells, dtype=np.float64)
    sample_axis = np.arange(samples, dtype=np.float64)[:, None]
    cell_axis = np.arange(n_cells, dtype=np.float64)[None, :]

    rho = 900.0 + sample_axis + 0.01 * cell_axis
    velocity = 0.1 * sample_axis - 0.001 * cell_axis
    pressure = 5.0e6 - 10.0 * sample_axis - cell_axis
    temperature = 282.0 - 0.001 * sample_axis + 0.01 * cell_axis
    internal_energy = 2.0e5 + 2.0 * sample_axis + cell_axis
    vapor_mass_fraction = np.zeros((samples, n_cells), dtype=np.float64)
    conserved = np.stack(
        (
            rho,
            rho * velocity,
            rho * internal_energy,
            vapor_mass_fraction,
        ),
        axis=2,
    ).astype(np.float64, copy=False)

    state_history = {
        "time_s": time_s,
        "x_m": x_m,
        "conserved": conserved,
        "rho_kg_m3": rho.astype(np.float64, copy=False),
        "velocity_m_s": velocity.astype(np.float64, copy=False),
        "pressure_pa": pressure.astype(np.float64, copy=False),
        "temperature_k": temperature.astype(np.float64, copy=False),
        "internal_energy_j_kg": internal_energy.astype(np.float64, copy=False),
        "vapor_mass_fraction": vapor_mass_fraction,
    }
    history = tuple(
        {
            "step": step,
            "time_s": float(time_s[step]),
            "accepted_log_value": step * 2,
        }
        for step in range(1, samples)
    )
    return WorkingToolResult(
        case_id="V0-B-PROJECTION-TEST",
        model_profile=(
            ModelProfile.STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0
        ),
        summary={
            "accepted_steps": accepted_steps,
            "final_solver_time_s": float(time_s[-1]),
            "target_horizon_reached": True,
        },
        history=history,
        transitions=(),
        state_history=state_history,
        warnings=(PROVISIONAL_MODEL_WARNING,),
    )


def _replace_state_array(
    result: WorkingToolResult,
    name: str,
    value: np.ndarray,
) -> WorkingToolResult:
    state_history = dict(result.state_history)
    state_history[name] = value
    return replace(result, state_history=state_history)


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        (1, tuple(range(641))),
        (10, tuple(range(0, 641, 10))),
        (64, tuple(range(0, 641, 64))),
        (100, (0, 100, 200, 300, 400, 500, 600, 640)),
        (641, (0, 640)),
        (1000, (0, 640)),
    ],
)
def test_canonical_retained_indices_are_exact(
    interval: int,
    expected: tuple[int, ...],
) -> None:
    assert retained_state_indices(640, interval) == expected


def test_zero_step_result_retains_the_single_initial_final_state() -> None:
    assert retained_state_indices(0, 1) == (0,)
    assert retained_state_indices(0, 100) == (0,)


@pytest.mark.parametrize(
    ("interval", "expected_samples", "expected_mode"),
    [
        (1, 641, WorkingToolStateStorageMode.FULL_STATE),
        (10, 65, WorkingToolStateStorageMode.SAMPLED_STATE),
        (64, 11, WorkingToolStateStorageMode.SAMPLED_STATE),
        (100, 8, WorkingToolStateStorageMode.SAMPLED_STATE),
        (1000, 2, WorkingToolStateStorageMode.SAMPLED_STATE),
    ],
)
def test_projection_applies_only_to_state_history(
    interval: int,
    expected_samples: int,
    expected_mode: WorkingToolStateStorageMode,
) -> None:
    source = _full_result()
    projection = project_state_storage(source, interval)
    projected = projection.result
    retained = projection.retained_state_indices

    assert projected is not source
    assert projection.full_state_samples == 641
    assert projection.stored_state_samples == expected_samples
    assert projection.storage_mode is expected_mode
    assert projection.state_sample_interval_accepted_steps == interval
    assert len(retained) == expected_samples
    assert retained[0] == 0
    assert retained[-1] == 640
    assert len(set(retained)) == len(retained)
    assert tuple(sorted(retained)) == retained

    assert projected.summary == source.summary
    assert projected.summary is not source.summary
    assert projected.history == source.history
    assert projected.history is not source.history
    assert len(projected.history) == 640
    assert projected.history[0] is not source.history[0]
    assert projected.transitions == source.transitions
    assert projected.warnings == source.warnings
    assert projected.verified is False
    assert projected.accepted is False
    assert projected.validated is False
    assert projected.design_use_approved is False

    for name in SAMPLE_AXIS_STATE_ARRAYS:
        assert np.array_equal(
            projected.state_history[name],
            source.state_history[name][list(retained)],
        )
    for name in STATIC_STATE_ARRAYS:
        assert np.array_equal(
            projected.state_history[name],
            source.state_history[name],
        )


def test_full_mode_is_array_semantic_exact_with_independent_storage() -> None:
    source = _full_result()
    source_snapshots = {
        name: np.array(value, copy=True)
        for name, value in source.state_history.items()
    }
    projection = project_state_storage(source, 1)
    projected = projection.result

    assert tuple(projected.state_history) == tuple(source.state_history)
    assert set(projected.state_history) == set(REQUIRED_STATE_ARRAYS)
    for name in REQUIRED_STATE_ARRAYS:
        source_array = source.state_history[name]
        projected_array = projected.state_history[name]
        assert projected_array.dtype == source_array.dtype
        assert projected_array.shape == source_array.shape
        assert np.array_equal(projected_array, source_array)
        assert not np.shares_memory(projected_array, source_array)
        assert np.array_equal(source_array, source_snapshots[name])


def test_sampled_projection_does_not_mutate_or_share_source_arrays() -> None:
    source = _full_result()
    source_snapshots = {
        name: np.array(value, copy=True)
        for name, value in source.state_history.items()
    }
    projected = project_state_storage(source, 100).result

    for name in REQUIRED_STATE_ARRAYS:
        assert not np.shares_memory(
            projected.state_history[name],
            source.state_history[name],
        )
        assert np.array_equal(source.state_history[name], source_snapshots[name])
        projected.state_history[name].flat[0] += 1.0
        assert np.array_equal(source.state_history[name], source_snapshots[name])


def test_validated_layout_reports_full_dimensions() -> None:
    layout = validate_full_state_result(_full_result())
    assert layout.accepted_steps == 640
    assert layout.full_state_samples == 641
    assert layout.n_cells == 3
    assert layout.layout_version == "WORKING_TOOL_PUBLIC_STATE_LAYOUT_V1"


@pytest.mark.parametrize("value", [True, 1.0, "1", None, -1])
def test_retained_indices_reject_invalid_accepted_steps(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        retained_state_indices(value, 1)


@pytest.mark.parametrize("value", [True, 1.0, "1", None, 0, -1])
def test_projection_rejects_invalid_interval(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        project_state_storage(_full_result(), value)


def test_projection_rejects_summary_history_count_mismatch() -> None:
    result = _full_result()
    bad = replace(result, summary={**result.summary, "accepted_steps": 639})
    with pytest.raises(StateStorageProjectionError) as exc_info:
        project_state_storage(bad, 10)
    assert exc_info.value.classification == (
        "WORKING_TOOL_V0_B_RESULT_CONSISTENCY_ERROR"
    )


def test_projection_rejects_nonexact_history_steps() -> None:
    result = _full_result()
    history = list(result.history)
    history[0] = {**history[0], "step": 2}
    bad = replace(result, history=tuple(history))
    with pytest.raises(StateStorageProjectionError, match="exact sequence"):
        project_state_storage(bad, 10)


def test_projection_rejects_history_state_time_mismatch() -> None:
    result = _full_result()
    history = list(result.history)
    history[0] = {**history[0], "time_s": history[0]["time_s"] + 1.0e-9}
    bad = replace(result, history=tuple(history))
    with pytest.raises(StateStorageProjectionError, match="history times"):
        project_state_storage(bad, 10)


@pytest.mark.parametrize("missing_name", REQUIRED_STATE_ARRAYS)
def test_projection_rejects_every_missing_required_array(
    missing_name: str,
) -> None:
    result = _full_result()
    state_history = dict(result.state_history)
    state_history.pop(missing_name)
    bad = replace(result, state_history=state_history)
    with pytest.raises(StateStorageProjectionError) as exc_info:
        project_state_storage(bad, 10)
    assert exc_info.value.classification == "WORKING_TOOL_V0_B_STATE_LAYOUT_ERROR"


def test_projection_rejects_unknown_array() -> None:
    result = _full_result()
    state_history = dict(result.state_history)
    state_history["future_array"] = np.zeros((641, 3), dtype=np.float64)
    bad = replace(result, state_history=state_history)
    with pytest.raises(StateStorageProjectionError, match="unknown"):
        project_state_storage(bad, 10)


def test_projection_rejects_nonfinite_required_value() -> None:
    result = _full_result()
    pressure = np.array(result.state_history["pressure_pa"], copy=True)
    pressure[10, 1] = np.nan
    bad = _replace_state_array(result, "pressure_pa", pressure)
    with pytest.raises(StateStorageProjectionError) as exc_info:
        project_state_storage(bad, 10)
    assert exc_info.value.classification == "WORKING_TOOL_V0_B_STATE_NONFINITE"


def test_projection_rejects_nonfloating_public_array() -> None:
    result = _full_result()
    bad = _replace_state_array(
        result,
        "vapor_mass_fraction",
        np.zeros((641, 3), dtype=np.int64),
    )
    with pytest.raises(StateStorageProjectionError, match="floating dtype"):
        project_state_storage(bad, 10)


def test_projection_rejects_inconsistent_sample_axis_length() -> None:
    result = _full_result()
    bad = _replace_state_array(
        result,
        "rho_kg_m3",
        np.array(result.state_history["rho_kg_m3"][:-1], copy=True),
    )
    with pytest.raises(StateStorageProjectionError, match="leading dimension"):
        project_state_storage(bad, 10)


@pytest.mark.parametrize(
    ("name", "bad_value", "message"),
    [
        ("time_s", np.zeros((641, 1), dtype=np.float64), "time_s"),
        ("x_m", np.zeros((1, 3), dtype=np.float64), "x_m"),
        ("conserved", np.zeros((641, 3, 3), dtype=np.float64), "conserved"),
        ("pressure_pa", np.zeros((641, 3, 1), dtype=np.float64), "pressure_pa"),
    ],
)
def test_projection_rejects_invalid_explicit_layout_shape(
    name: str,
    bad_value: np.ndarray,
    message: str,
) -> None:
    result = _full_result()
    bad = _replace_state_array(result, name, bad_value)
    with pytest.raises(StateStorageProjectionError, match=message):
        project_state_storage(bad, 10)


def test_projection_reduction_ratio_is_sample_count_basis() -> None:
    projection = project_state_storage(_full_result(), 100)
    assert projection.raw_state_payload_reduction_ratio == pytest.approx(
        1.0 - 8.0 / 641.0
    )
