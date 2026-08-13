from __future__ import annotations

import json

import pytest

from liquid_gas_transient.physics_model_manager import (
    BoundaryRegime,
    FINITE_COMPRESSION_MODEL_REQUIRED,
    NO_ADMISSIBLE_ISLAND,
    OutwardFlowModel,
    PhysicsBoundaryModelManager,
)
from u3_b2_a1_increment_9m_a1_delegate_composition import (
    DELEGATE_SOURCE,
    DelegateCompositionFailed,
    Increment9LHookDelegateAdapter,
    ModelManagedIncrement9LDelegateComposer,
)


class FakeDelegateStop(RuntimeError):
    def __init__(self, classification: str) -> None:
        super().__init__(classification)
        self.classification = classification


class FakeIncrement9LHook:
    def __init__(
        self,
        *,
        three: str = "success",
        finite: str = "success",
        closed: str = "success",
    ) -> None:
        self.plan = {"three": three, "finite": finite, "closed": closed}
        self.root_context = None
        self.boundary_state = "OUTWARD_FLOW"
        self.outward_model = "THREE_BRANCH_WAVE_MODEL"
        self.requested_solver_step = None
        self.closure_trigger_classification = None
        self.closure_trigger_message = None
        self.calls: list[tuple[str, int, float, int | None]] = []
        self.installed_contexts: list[dict[str, object]] = []

    def _invalidate_cache(self) -> None:
        self.root_context = None

    def _install(self, public: str, outward: str | None, branch: str) -> None:
        context = {
            "public_boundary_state": public,
            "outward_internal_model": outward,
            "branch_classification": branch,
            "flux": (branch,),
        }
        self.root_context = context
        self.installed_contexts.append(context)

    def _record(self, name: str, state: object, t: float) -> None:
        self.calls.append((name, id(state), float(t), self.requested_solver_step))

    def _prepare_three_branch(self, state: object, t: float) -> None:
        self._record("three", state, t)
        action = self.plan["three"]
        if action == "finite":
            self._switch_outward_model(
                t=t,
                classification=FINITE_COMPRESSION_MODEL_REQUIRED,
                message="finite model required",
            )
        if action == "wrong_trigger":
            self._switch_outward_model(
                t=t,
                classification="WRONG_TRIGGER",
                message="wrong trigger",
            )
        if action == "fail":
            raise FakeDelegateStop("MULTIPLE_ROOTS")
        if action == "mismatch":
            self._install("OUTWARD_FLOW", "GENERAL_EOS_FINITE_COMPRESSION", "BAD")
            return
        self._install("OUTWARD_FLOW", "THREE_BRANCH_WAVE_MODEL", "WEAK")

    def _prepare_finite(self, state: object, t: float) -> None:
        self._record("finite", state, t)
        action = self.plan["finite"]
        if action == "closed":
            self._transition_to_closed(
                t=t,
                classification=NO_ADMISSIBLE_ISLAND,
                message="no admissible island",
            )
        if action == "fail":
            raise FakeDelegateStop("FINITE_TARGET_FAILURE")
        if action == "mismatch":
            self._install("OUTWARD_FLOW", "THREE_BRANCH_WAVE_MODEL", "BAD")
            return
        self._install(
            "OUTWARD_FLOW",
            "GENERAL_EOS_FINITE_COMPRESSION",
            "FINITE",
        )

    def _prepare_closed(self, state: object, t: float) -> None:
        self._record("closed", state, t)
        if self.plan["closed"] == "fail":
            raise FakeDelegateStop("CLOSED_TARGET_FAILURE")
        self._install("ZERO_TRANSFER_CLOSED", None, "CLOSED")


def _build(**plan: str):
    manager = PhysicsBoundaryModelManager()
    hook = FakeIncrement9LHook(**plan)
    composer = ModelManagedIncrement9LDelegateComposer(
        manager=manager,
        adapter=Increment9LHookDelegateAdapter(hook),
    )
    return manager, hook, composer


def test_initial_selection_routes_to_three_branch() -> None:
    manager, hook, composer = _build()
    result = composer.evaluate(
        conserved_state=object(),
        solver_time_s=0.1,
        observed_solver_step=7,
    )
    assert [row[0] for row in hook.calls] == ["three"]
    assert result.selection == manager.selection
    assert result.transition_events == ()
    assert result.context["delegate_source"] == DELEGATE_SOURCE


def test_preselected_finite_and_closed_states_route_directly() -> None:
    manager, hook, composer = _build()
    manager.activate_finite_compression(
        trigger_classification=FINITE_COMPRESSION_MODEL_REQUIRED
    )
    composer.evaluate(conserved_state=object(), solver_time_s=0.2)
    assert [row[0] for row in hook.calls] == ["finite"]

    manager.close_zero_transfer(trigger_classification=NO_ADMISSIBLE_ISLAND)
    hook.calls.clear()
    composer.evaluate(conserved_state=object(), solver_time_s=0.3)
    assert [row[0] for row in hook.calls] == ["closed"]


def test_finite_transition_retries_same_request() -> None:
    manager, hook, composer = _build(three="finite")
    state = object()
    result = composer.evaluate(
        conserved_state=state,
        solver_time_s=0.4,
        observed_solver_step=484,
    )
    assert [row[0] for row in hook.calls] == ["three", "finite"]
    assert all(row[1:] == (id(state), 0.4, 484) for row in hook.calls)
    assert manager.selection.outward_flow_model is (
        OutwardFlowModel.GENERAL_EOS_FINITE_COMPRESSION
    )
    assert [event.sequence for event in result.transition_events] == [1]


def test_finite_then_closed_chain_commits_in_order() -> None:
    manager, hook, composer = _build(three="finite", finite="closed")
    result = composer.evaluate(
        conserved_state=object(),
        solver_time_s=0.5,
        observed_solver_step=638,
    )
    assert [row[0] for row in hook.calls] == ["three", "finite", "closed"]
    assert manager.selection.boundary_regime is BoundaryRegime.ZERO_TRANSFER_CLOSED
    assert [event.sequence for event in result.transition_events] == [1, 2]
    assert [event.trigger_classification for event in result.transition_events] == [
        FINITE_COMPRESSION_MODEL_REQUIRED,
        NO_ADMISSIBLE_ISLAND,
    ]
    assert result.context["model_manager_transition_count_for_request"] == 2
    assert result.context["physics_flux_modified_by_manager"] is False


@pytest.mark.parametrize("observed_step", [1, 484, 638, 999_999])
def test_observed_step_is_evidence_only(observed_step: int) -> None:
    manager, _, composer = _build(three="finite")
    result = composer.evaluate(
        conserved_state=object(),
        solver_time_s=0.6,
        observed_solver_step=observed_step,
    )
    assert manager.selection.outward_flow_model is (
        OutwardFlowModel.GENERAL_EOS_FINITE_COMPRESSION
    )
    assert result.transition_events[0].observed_solver_step == observed_step
    assert result.transition_events[0].absolute_step_number_trigger_used is False


@pytest.mark.parametrize(
    (plan, expected),
    [
        ({"three": "fail"}, "MULTIPLE_ROOTS"),
        ({"three": "wrong_trigger"}, "TRANSITION_TRIGGER_MISMATCH"),
        ({"three": "finite", "finite": "fail"}, "FINITE_TARGET_FAILURE"),
        ({"three": "mismatch"}, "DELEGATE_CONTEXT_SELECTION_MISMATCH"),
    ],
)
def test_failed_staged_evaluation_leaves_manager_unchanged(
    plan: dict[str, str],
    expected: str,
) -> None:
    manager, _, composer = _build(**plan)
    selection_before = manager.selection
    history_before = manager.transition_history
    with pytest.raises(DelegateCompositionFailed) as caught:
        composer.evaluate(conserved_state=object(), solver_time_s=0.7)
    assert caught.value.classification == expected
    assert manager.selection == selection_before
    assert manager.transition_history == history_before


def test_invalid_observation_leaves_manager_unchanged() -> None:
    manager, _, composer = _build(three="finite")
    with pytest.raises(DelegateCompositionFailed) as caught:
        composer.evaluate(conserved_state=object(), solver_time_s=float("nan"))
    assert caught.value.classification == "INVALID_EVALUATION_OBSERVATION"
    assert manager.transition_history == ()


def test_result_metadata_is_serializable_and_source_context_is_not_modified() -> None:
    _, hook, composer = _build(three="finite")
    result = composer.evaluate(conserved_state=object(), solver_time_s=0.8)
    json.dumps(result.context)
    installed = hook.installed_contexts[-1]
    assert "model_manager_profile" not in installed
    assert result.context["absolute_step_number_trigger_used"] is False


def test_adapter_rejects_missing_legacy_methods() -> None:
    class Incomplete:
        root_context = None

    with pytest.raises(TypeError):
        Increment9LHookDelegateAdapter(Incomplete())
