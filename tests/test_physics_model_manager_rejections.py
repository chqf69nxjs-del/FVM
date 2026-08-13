from __future__ import annotations

import math

import pytest

from liquid_gas_transient.physics_model_manager import (
    FINITE_COMPRESSION_MODEL_REQUIRED,
    ModelTransitionRejected,
    NO_ADMISSIBLE_ISLAND,
    PhysicsBoundaryModelManager,
)


def _snapshot(manager: PhysicsBoundaryModelManager) -> tuple[object, int, int]:
    return (
        manager.selection,
        len(manager.transition_history),
        len(manager.selection_history),
    )


def test_wrong_trigger_does_not_mutate_state() -> None:
    manager = PhysicsBoundaryModelManager()
    before = _snapshot(manager)

    with pytest.raises(ModelTransitionRejected) as caught:
        manager.activate_finite_compression(trigger_classification="WRONG")

    assert caught.value.classification == "TRANSITION_TRIGGER_MISMATCH"
    assert _snapshot(manager) == before


def test_closure_requires_finite_compression() -> None:
    manager = PhysicsBoundaryModelManager()
    before = _snapshot(manager)

    with pytest.raises(ModelTransitionRejected) as caught:
        manager.close_zero_transfer(trigger_classification=NO_ADMISSIBLE_ISLAND)

    assert caught.value.classification == "TRANSITION_PRECONDITION_NOT_MET"
    assert _snapshot(manager) == before


def test_repeated_and_reverse_transitions_are_rejected() -> None:
    manager = PhysicsBoundaryModelManager()
    manager.activate_finite_compression(
        trigger_classification=FINITE_COMPRESSION_MODEL_REQUIRED
    )

    with pytest.raises(ModelTransitionRejected) as repeated_model:
        manager.activate_finite_compression(
            trigger_classification=FINITE_COMPRESSION_MODEL_REQUIRED
        )
    assert repeated_model.value.classification == "REPEATED_TRANSITION_NOT_SUPPORTED"

    manager.close_zero_transfer(trigger_classification=NO_ADMISSIBLE_ISLAND)
    after_close = _snapshot(manager)

    with pytest.raises(ModelTransitionRejected) as repeated_boundary:
        manager.close_zero_transfer(trigger_classification=NO_ADMISSIBLE_ISLAND)
    assert repeated_boundary.value.classification == "REPEATED_TRANSITION_NOT_SUPPORTED"

    with pytest.raises(ModelTransitionRejected) as reverse:
        manager.request_reverse_boundary_transition()
    assert reverse.value.classification == "REVERSE_TRANSITION_NOT_SUPPORTED"
    assert _snapshot(manager) == after_close


@pytest.mark.parametrize("bad_time", [-1.0, math.inf, -math.inf, math.nan, True])
def test_invalid_time_is_atomic(bad_time: object) -> None:
    manager = PhysicsBoundaryModelManager()
    before = _snapshot(manager)

    with pytest.raises(ModelTransitionRejected) as caught:
        manager.activate_finite_compression(
            trigger_classification=FINITE_COMPRESSION_MODEL_REQUIRED,
            solver_time_s=bad_time,  # type: ignore[arg-type]
        )

    assert caught.value.classification == "INVALID_TRANSITION_OBSERVATION"
    assert _snapshot(manager) == before


@pytest.mark.parametrize("bad_step", [-1, 1.5, True, "4"])
def test_invalid_step_is_atomic(bad_step: object) -> None:
    manager = PhysicsBoundaryModelManager()
    before = _snapshot(manager)

    with pytest.raises(ModelTransitionRejected) as caught:
        manager.activate_finite_compression(
            trigger_classification=FINITE_COMPRESSION_MODEL_REQUIRED,
            observed_solver_step=bad_step,  # type: ignore[arg-type]
        )

    assert caught.value.classification == "INVALID_TRANSITION_OBSERVATION"
    assert _snapshot(manager) == before
