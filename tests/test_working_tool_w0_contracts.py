import csv
import json
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.config import NumericsConfig, PipeGeometry, TimeConfig
from liquid_gas_transient.working_tool import (
    BackendRunData,
    InitialCondition,
    ModelProfile,
    OutletCondition,
    PROVISIONAL_MODEL_WARNING,
    PROVISIONAL_WARNING_CODE,
    RESULT_FILENAMES,
    TransitionRecord,
    WorkingToolBackend,
    WorkingToolCase,
    WorkingToolResult,
    write_result_package,
)


def _case() -> WorkingToolCase:
    return WorkingToolCase(
        case_id="W0-LIQUID-SMALL-DROP",
        geometry=PipeGeometry(
            length_m=1.0,
            diameter_m=0.011283791670955126,
            roughness_m=0.0,
        ),
        numerics=NumericsConfig(n_cells=32, n_ghost=2, cfl=0.1),
        time=TimeConfig(t_end_s=0.004285834855172021, max_steps=10_000),
        initial=InitialCondition(
            pressure_pa=5_000_000.0,
            temperature_k=280.0,
            velocity_m_s=0.0,
        ),
        outlet=OutletCondition(
            back_pressure_pa=4_950_000.0,
            opening_fraction=0.5,
            discharge_coefficient=0.8,
        ),
    )


def test_w0_case_reuses_existing_core_config_types() -> None:
    case = _case()
    assert isinstance(case.geometry, PipeGeometry)
    assert isinstance(case.numerics, NumericsConfig)
    assert isinstance(case.time, TimeConfig)
    assert case.fluid == "CO2"
    assert case.model_profile is ModelProfile.STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0
    payload = case.as_dict()
    assert payload["geometry"]["length_m"] == 1.0
    assert payload["numerics"]["n_cells"] == 32


def test_w0_case_rejects_unsupported_scope_fail_closed() -> None:
    base = _case()
    with pytest.raises(ValueError, match="fluid='CO2' only"):
        WorkingToolCase(
            case_id="BAD-FLUID",
            geometry=base.geometry,
            numerics=base.numerics,
            time=base.time,
            initial=base.initial,
            outlet=base.outlet,
            fluid="N2",
        )
    with pytest.raises(ValueError, match="unsupported model_profile"):
        WorkingToolCase(
            case_id="BAD-PROFILE",
            geometry=base.geometry,
            numerics=base.numerics,
            time=base.time,
            initial=base.initial,
            outlet=base.outlet,
            model_profile="TWO_PHASE",  # type: ignore[arg-type]
        )


def test_w0_transition_step_is_evidence_not_trigger() -> None:
    event = TransitionRecord(
        axis="outward_flow_model",
        from_state="THREE_BRANCH_WAVE_MODEL",
        to_state="GENERAL_EOS_FINITE_COMPRESSION",
        trigger_classification="FINITE_COMPRESSION_MODEL_REQUIRED",
        solver_time_s=0.0032365792102672024,
        observed_solver_step=484,
    )
    assert event.as_dict()["absolute_step_number_trigger_used"] is False
    with pytest.raises(ValueError, match="transition criteria are forbidden"):
        TransitionRecord(
            axis="boundary_regime",
            from_state="OUTWARD_FLOW",
            to_state="ZERO_TRANSFER_CLOSED",
            trigger_classification="NO_ADMISSIBLE_ISLAND",
            solver_time_s=0.004269583083221582,
            observed_solver_step=638,
            absolute_step_number_trigger_used=True,
        )


def test_w0_result_requires_provisional_warning_and_false_authority() -> None:
    case = _case()
    with pytest.raises(ValueError, match="mandatory provisional engineering warning"):
        WorkingToolResult(
            case_id=case.case_id,
            model_profile=case.model_profile,
            summary={},
            history=(),
            transitions=(),
            state_history={},
            warnings=(),
        )
    with pytest.raises(ValueError, match="formal authority flags must remain false"):
        WorkingToolResult(
            case_id=case.case_id,
            model_profile=case.model_profile,
            summary={},
            history=(),
            transitions=(),
            state_history={},
            warnings=(PROVISIONAL_MODEL_WARNING,),
            verified=True,
        )


def test_w0_backend_payload_is_separate_from_public_authority() -> None:
    data = BackendRunData(summary={"accepted_steps": 8})
    assert data.summary == {"accepted_steps": 8}
    assert not hasattr(data, "workflow_run")
    assert not hasattr(data, "artifact_id")


class _FakeBackend:
    def __init__(self) -> None:
        self.seen_case: WorkingToolCase | None = None

    def run_case(self, case: WorkingToolCase) -> BackendRunData:
        self.seen_case = case
        return BackendRunData(summary={"backend": "fake", "accepted_steps": 0})


def test_w0_backend_run_case_contract_is_reusable() -> None:
    case = _case()
    backend: WorkingToolBackend = _FakeBackend()
    data = backend.run_case(case)
    assert data.summary == {"backend": "fake", "accepted_steps": 0}
    assert backend.seen_case is case  # type: ignore[attr-defined]


def test_w0_writes_only_normal_user_result_package(tmp_path: Path) -> None:
    case = _case()
    result = WorkingToolResult(
        case_id=case.case_id,
        model_profile=case.model_profile,
        summary={"accepted_steps": 8, "final_time_s": 1.0e-4},
        history=(
            {"step": 0, "time_s": 0.0, "p_min_pa": 5_000_000.0},
            {"step": 8, "time_s": 1.0e-4, "p_min_pa": 4_999_000.0},
        ),
        transitions=(
            TransitionRecord(
                axis="outward_flow_model",
                from_state="THREE_BRANCH_WAVE_MODEL",
                to_state="GENERAL_EOS_FINITE_COMPRESSION",
                trigger_classification="FINITE_COMPRESSION_MODEL_REQUIRED",
                solver_time_s=8.0e-5,
                observed_solver_step=7,
            ),
        ),
        state_history={
            "time_s": np.array([0.0, 1.0e-4]),
            "pressure_pa": np.array([[5_000_000.0], [4_999_000.0]]),
        },
        warnings=(PROVISIONAL_MODEL_WARNING,),
    )
    output = write_result_package(result, tmp_path)
    assert {path.name for path in output.iterdir()} == set(RESULT_FILENAMES)

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["verified"] is False
    assert summary["accepted"] is False
    assert summary["validated"] is False
    assert summary["design_use_approved"] is False
    assert PROVISIONAL_WARNING_CODE in summary["warning_codes"]
    assert "workflow_run" not in summary
    assert "artifact_id" not in summary

    with (output / "transitions.csv").open(newline="", encoding="utf-8") as handle:
        transition_rows = list(csv.DictReader(handle))
    assert transition_rows[0]["trigger_classification"] == "FINITE_COMPRESSION_MODEL_REQUIRED"
    assert transition_rows[0]["absolute_step_number_trigger_used"] == "False"

    with np.load(output / "state_history.npz") as arrays:
        assert np.array_equal(arrays["time_s"], np.array([0.0, 1.0e-4]))
        assert arrays["pressure_pa"].shape == (2, 1)


@pytest.mark.parametrize(
    "reserved_key",
    [
        "verified",
        "accepted",
        "validated",
        "design_use_approved",
        "workflow_run",
        "workflow_job",
        "artifact_id",
        "artifact_sha256",
        "parent_artifact_id",
        "exact_increment_9l_behavioral_equivalence_passed",
    ],
)
def test_w0_output_rejects_reserved_authority_keys(
    tmp_path: Path,
    reserved_key: str,
) -> None:
    case = _case()
    result = WorkingToolResult(
        case_id=case.case_id,
        model_profile=case.model_profile,
        summary={reserved_key: True},
        history=(),
        transitions=(),
        state_history={},
        warnings=(PROVISIONAL_MODEL_WARNING,),
    )
    with pytest.raises(ValueError, match="reserved public keys"):
        write_result_package(result, tmp_path)


def test_w0_public_sources_do_not_import_verification_runner() -> None:
    import liquid_gas_transient.working_tool.backend as backend
    import liquid_gas_transient.working_tool.case_schema as case_schema
    import liquid_gas_transient.working_tool.output as output
    import liquid_gas_transient.working_tool.results as results

    for module in (backend, case_schema, output, results):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "tools.verification" not in source
        assert "u3_b2_a1_increment_9m_a2_live_fvm_composition" not in source
