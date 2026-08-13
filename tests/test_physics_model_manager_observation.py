from __future__ import annotations

import json

from liquid_gas_transient.physics_model_manager import (
    FINITE_COMPRESSION_MODEL_REQUIRED,
    NO_ADMISSIBLE_ISLAND,
    PhysicsBoundaryModelManager,
)


def _run(first_step: int, second_step: int) -> PhysicsBoundaryModelManager:
    manager = PhysicsBoundaryModelManager()
    manager.activate_finite_compression(
        trigger_classification=FINITE_COMPRESSION_MODEL_REQUIRED,
        observed_solver_step=first_step,
    )
    manager.close_zero_transfer(
        trigger_classification=NO_ADMISSIBLE_ISLAND,
        observed_solver_step=second_step,
    )
    return manager


def test_step_numbers_are_evidence_only() -> None:
    early = _run(1, 2)
    late = _run(999_999, 1_000_000)

    assert early.selection == late.selection
    assert [event.axis for event in early.transition_history] == [
        event.axis for event in late.transition_history
    ]
    assert [event.trigger_classification for event in early.transition_history] == [
        event.trigger_classification for event in late.transition_history
    ]
    assert all(
        event.absolute_step_number_trigger_used is False
        for event in early.transition_history + late.transition_history
    )


def test_history_is_ordered_and_json_serializable() -> None:
    manager = _run(484, 638)
    payload = manager.transition_history_as_dicts()

    assert [row["sequence"] for row in payload] == [1, 2]
    assert json.loads(json.dumps(payload)) == payload
    assert len(manager.selection_history) == 3
