from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.working_tool import (
    BackendRunData,
    PROVISIONAL_MODEL_WARNING,
    PROVISIONAL_WARNING_CODE,
    RESULT_FILENAMES,
    WarningSeverity,
    WorkingToolWarning,
    execute_case,
    write_result_package,
)
from u3_b2_a1_working_tool_w1_a2_live_backend import (
    A2_STARTING_STATE_SHA256,
    A2LiveWorkingToolBackend,
    W1CaseScopeError,
    W1_SMOKE_WARNING_CODE,
    build_canonical_w1_case,
)


CONTRACT = Path(
    "docs/verification/stage7_u3_b2_fvm_discharge_coupling_contract_v1.json"
)
B1_CONTRACT = Path(
    "docs/verification/stage7_u3_b1_critical_state_contract_v1.json"
)


def test_execute_case_is_backend_independent_and_injects_provisional_warning() -> None:
    case = build_canonical_w1_case(CONTRACT, case_id="W1-FACADE")
    source_array = np.array([1.0, 2.0])
    custom_warning = WorkingToolWarning(
        code="CUSTOM_BACKEND_WARNING",
        severity=WarningSeverity.WARNING,
        message="custom warning",
    )

    class FakeBackend:
        def run_case(self, received_case):
            assert received_case is case
            return BackendRunData(
                summary={"backend": "fake"},
                state_history={"time_s": source_array},
                warnings=(PROVISIONAL_MODEL_WARNING, custom_warning),
            )

    result = execute_case(case, FakeBackend())
    source_array[0] = 99.0
    assert np.array_equal(result.state_history["time_s"], np.array([1.0, 2.0]))
    assert [warning.code for warning in result.warnings] == [
        PROVISIONAL_WARNING_CODE,
        "CUSTOM_BACKEND_WARNING",
    ]
    assert result.verified is False
    assert result.accepted is False
    assert result.validated is False
    assert result.design_use_approved is False


def test_w1_noncanonical_case_fails_before_solver_construction() -> None:
    case = build_canonical_w1_case(CONTRACT, case_id="W1-NONCANONICAL")
    bad_case = replace(
        case,
        outlet=replace(
            case.outlet,
            back_pressure_pa=case.outlet.back_pressure_pa + 1.0,
        ),
    )
    backend = A2LiveWorkingToolBackend(
        contract_path=CONTRACT,
        b1_contract_path=B1_CONTRACT,
        smoke_accepted_steps=1,
    )
    with pytest.raises(W1CaseScopeError, match="W1_NONCANONICAL_CASE"):
        backend.run_case(bad_case)
    assert backend.solver_instances_created == 0


def test_w1_two_step_live_backend_uses_a2_path(tmp_path: Path) -> None:
    case = build_canonical_w1_case(CONTRACT, case_id="W1-LIVE-TWO-STEP")
    backend = A2LiveWorkingToolBackend(
        contract_path=CONTRACT,
        b1_contract_path=B1_CONTRACT,
        smoke_accepted_steps=2,
    )
    result = execute_case(case, backend)
    summary = result.summary

    assert summary["a2_live_path_connected"] is True
    assert summary["a2_model_managed_live_hook_used"] is True
    assert summary["starting_state_sha256"] == A2_STARTING_STATE_SHA256
    assert summary["starting_state_matches_a2"] is True
    assert summary["accepted_steps"] == 2
    assert summary["final_solver_step"] == 2
    assert summary["one_fvm_solver_instance"] is True
    assert summary["manager_transition_count"] == 0
    assert summary["manager_selection_history_count"] == 1
    assert summary["successful_context_restoration_count"] == 2
    assert summary["context_restoration_gate_passed"] is True
    assert summary["short_run_physical_gate_passed"] is True
    assert summary["full_two_l_over_c0_regression_tested"] is False
    assert len(result.history) == 2
    assert result.transitions == ()
    assert {warning.code for warning in result.warnings} == {
        PROVISIONAL_WARNING_CODE,
        W1_SMOKE_WARNING_CODE,
    }
    assert result.state_history["conserved"].shape == (3, 32, 4)
    assert result.state_history["pressure_pa"].shape == (3, 32)

    output = write_result_package(result, tmp_path / "public-result")
    assert {path.name for path in output.iterdir()} == set(RESULT_FILENAMES)
    public_summary = json.loads(
        (output / "summary.json").read_text(encoding="utf-8")
    )
    assert public_summary["verified"] is False
    assert public_summary["validated"] is False
    assert "workflow_run" not in public_summary
    assert "artifact_id" not in public_summary


def test_public_runtime_facade_has_no_verification_import() -> None:
    import liquid_gas_transient.working_tool.runtime as runtime

    source = Path(runtime.__file__).read_text(encoding="utf-8")
    assert "tools.verification" not in source
    assert "u3_b2_a1_increment_9m_a2" not in source
