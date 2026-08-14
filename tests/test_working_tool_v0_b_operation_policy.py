from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from liquid_gas_transient.working_tool.operation_policy import (
    WorkingToolDestinationMode,
    WorkingToolOperationPolicy,
    WorkingToolStateStorageMode,
    storage_mode_for_sample_interval,
)
from liquid_gas_transient.working_tool.output_size import (
    RAW_STATE_PAYLOAD_ESTIMATE_BASIS,
    RAW_STATE_PAYLOAD_ESTIMATE_LABEL,
    RAW_STATE_PAYLOAD_SCOPE,
    estimate_maximum_raw_state_payload,
    maximum_state_sample_count,
    raw_state_payload_bytes_per_sample,
)


def test_storage_mode_is_derived_only_from_interval() -> None:
    assert (
        storage_mode_for_sample_interval(1)
        is WorkingToolStateStorageMode.FULL_STATE
    )
    assert (
        storage_mode_for_sample_interval(2)
        is WorkingToolStateStorageMode.SAMPLED_STATE
    )
    assert (
        storage_mode_for_sample_interval(10)
        is WorkingToolStateStorageMode.SAMPLED_STATE
    )


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None])
def test_storage_interval_rejects_non_builtin_int(value: object) -> None:
    with pytest.raises(TypeError):
        storage_mode_for_sample_interval(value)


@pytest.mark.parametrize("value", [0, -1, -100])
def test_storage_interval_rejects_nonpositive_int(value: int) -> None:
    with pytest.raises(ValueError):
        storage_mode_for_sample_interval(value)


def test_explicit_policy_is_strict_immutable_and_derived() -> None:
    output_dir = Path("results/run001")
    policy = WorkingToolOperationPolicy.explicit(output_dir)

    assert policy.destination_mode is WorkingToolDestinationMode.EXPLICIT
    assert policy.output_dir == output_dir
    assert policy.output_root is None
    assert policy.destination_path == output_dir
    assert policy.state_sample_interval_accepted_steps == 1
    assert policy.storage_mode is WorkingToolStateStorageMode.FULL_STATE

    with pytest.raises(FrozenInstanceError):
        policy.output_dir = Path("results/other")  # type: ignore[misc]


def test_auto_policy_is_strict_immutable_and_sampled() -> None:
    output_root = Path("results")
    policy = WorkingToolOperationPolicy.auto_run_directory(
        output_root,
        state_sample_interval_accepted_steps=10,
    )

    assert (
        policy.destination_mode
        is WorkingToolDestinationMode.AUTO_RUN_DIRECTORY
    )
    assert policy.output_dir is None
    assert policy.output_root == output_root
    assert policy.destination_path == output_root
    assert policy.storage_mode is WorkingToolStateStorageMode.SAMPLED_STATE


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "state_sample_interval_accepted_steps": 1,
            "destination_mode": "EXPLICIT",
            "output_dir": Path("run"),
        },
        {
            "state_sample_interval_accepted_steps": 1,
            "destination_mode": WorkingToolDestinationMode.EXPLICIT,
        },
        {
            "state_sample_interval_accepted_steps": 1,
            "destination_mode": WorkingToolDestinationMode.EXPLICIT,
            "output_dir": Path("run"),
            "output_root": Path("root"),
        },
        {
            "state_sample_interval_accepted_steps": 1,
            "destination_mode": WorkingToolDestinationMode.AUTO_RUN_DIRECTORY,
        },
        {
            "state_sample_interval_accepted_steps": 1,
            "destination_mode": WorkingToolDestinationMode.AUTO_RUN_DIRECTORY,
            "output_dir": Path("run"),
            "output_root": Path("root"),
        },
        {
            "state_sample_interval_accepted_steps": 1,
            "destination_mode": WorkingToolDestinationMode.EXPLICIT,
            "output_dir": "run",
        },
        {
            "state_sample_interval_accepted_steps": 1,
            "destination_mode": WorkingToolDestinationMode.AUTO_RUN_DIRECTORY,
            "output_root": "root",
        },
    ],
)
def test_policy_fails_closed_for_unknown_or_contradictory_destination(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        WorkingToolOperationPolicy(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, 0, -1])
def test_policy_rejects_invalid_interval(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        WorkingToolOperationPolicy(
            state_sample_interval_accepted_steps=value,  # type: ignore[arg-type]
            destination_mode=WorkingToolDestinationMode.EXPLICIT,
            output_dir=Path("run"),
        )


def test_maximum_sample_count_uses_initial_periodic_and_final_rule() -> None:
    assert maximum_state_sample_count(32000, 1) == 32001
    assert maximum_state_sample_count(32000, 10) == 3201
    assert maximum_state_sample_count(32000, 64) == 501
    assert maximum_state_sample_count(32000, 100) == 321
    assert maximum_state_sample_count(32000, 32000) == 2
    assert maximum_state_sample_count(32000, 32001) == 2


def test_canonical_raw_payload_estimates_are_exact_and_truthful() -> None:
    full = estimate_maximum_raw_state_payload(
        n_cells=32,
        max_steps=32000,
        state_sample_interval_accepted_steps=1,
    )
    sampled = estimate_maximum_raw_state_payload(
        n_cells=32,
        max_steps=32000,
        state_sample_interval_accepted_steps=10,
    )

    assert raw_state_payload_bytes_per_sample(32) == 2568

    assert full.label == RAW_STATE_PAYLOAD_ESTIMATE_LABEL
    assert full.estimate_basis == RAW_STATE_PAYLOAD_ESTIMATE_BASIS
    assert full.payload_scope == RAW_STATE_PAYLOAD_SCOPE
    assert full.storage_mode is WorkingToolStateStorageMode.FULL_STATE
    assert full.maximum_state_samples == 32001
    assert full.bytes_per_sample == 2568
    assert full.estimated_raw_payload_bytes == 82178568
    assert full.estimated_raw_payload_mib == pytest.approx(78.37158966064453)

    assert sampled.storage_mode is WorkingToolStateStorageMode.SAMPLED_STATE
    assert sampled.maximum_state_samples == 3201
    assert sampled.estimated_raw_payload_bytes == 8220168
    assert sampled.estimated_raw_payload_mib == pytest.approx(7.839363098144531)

    for estimate in (full, sampled):
        assert estimate.runtime_state_capture_mode == "FULL"
        assert estimate.runtime_memory_optimized is False
        assert estimate.exact_directory_size is False
        assert "STATIC_X_M_ARRAY" in estimate.excluded_payloads
        assert "NPZ_CONTAINER_METADATA_AND_OVERHEAD" in estimate.excluded_payloads
        assert "BACKEND_FULL_HISTORY_MEMORY" in estimate.excluded_payloads
        disclosure = estimate.as_dict()
        assert disclosure["storage_mode"] == estimate.storage_mode.value
        assert disclosure["runtime_state_capture_mode"] == "FULL"
        assert disclosure["runtime_memory_optimized"] is False
        assert disclosure["exact_directory_size"] is False


def test_raw_payload_estimate_is_immutable() -> None:
    estimate = estimate_maximum_raw_state_payload(
        n_cells=32,
        max_steps=32000,
        state_sample_interval_accepted_steps=10,
    )
    with pytest.raises(FrozenInstanceError):
        estimate.maximum_state_samples = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("function_name", "args"),
    [
        ("maximum", (True, 1)),
        ("maximum", (32000, True)),
        ("maximum", (0, 1)),
        ("maximum", (32000, 0)),
        ("bytes", (True,)),
        ("bytes", (0,)),
    ],
)
def test_estimator_helpers_reject_invalid_integer_inputs(
    function_name: str,
    args: tuple[object, ...],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        if function_name == "maximum":
            maximum_state_sample_count(*args)
        else:
            raw_state_payload_bytes_per_sample(*args)


def test_a1_modules_have_no_solver_backend_or_physics_imports() -> None:
    import liquid_gas_transient.working_tool.operation_policy as operation_policy
    import liquid_gas_transient.working_tool.output_size as output_size

    for module in (operation_policy, output_size):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in (
            ".backend",
            "CoolProp",
            "FvmSolver",
            "PhysicsBoundaryModelManager",
            "Hugoniot",
            "execute_case",
        ):
            assert forbidden not in source
