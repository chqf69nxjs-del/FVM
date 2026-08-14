from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from liquid_gas_transient.config import NumericsConfig, PipeGeometry, TimeConfig
from liquid_gas_transient.working_tool import (
    InitialCondition,
    ModelProfile,
    OutletCondition,
    PROVISIONAL_MODEL_WARNING,
    PROVISIONAL_WARNING_CODE,
    RESULT_FILENAMES,
    TransitionRecord,
    WorkingToolCase,
    WorkingToolResult,
    write_result_package,
)


OUTCOME = "WORKING_TOOL_W0_CONTRACT_CHECK_PASS"


def _canonical_case() -> WorkingToolCase:
    return WorkingToolCase(
        case_id="W0-CONTRACT-CHECK",
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


def _canonical_result(case: WorkingToolCase) -> WorkingToolResult:
    return WorkingToolResult(
        case_id=case.case_id,
        model_profile=case.model_profile,
        summary={"accepted_steps": 0, "final_time_s": 0.0},
        history=({"step": 0, "time_s": 0.0},),
        transitions=(
            TransitionRecord(
                axis="outward_flow_model",
                from_state="THREE_BRANCH_WAVE_MODEL",
                to_state="GENERAL_EOS_FINITE_COMPRESSION",
                trigger_classification="FINITE_COMPRESSION_MODEL_REQUIRED",
                solver_time_s=0.0,
                observed_solver_step=0,
            ),
        ),
        state_history={"time_s": np.array([0.0])},
        warnings=(PROVISIONAL_MODEL_WARNING,),
    )


def _reserved_key_gate(case: WorkingToolCase) -> bool:
    keys = (
        "verified",
        "accepted",
        "validated",
        "design_use_approved",
        "workflow_run",
        "artifact_id",
        "parent_artifact_id",
        "exact_increment_9l_behavioral_equivalence_passed",
    )
    for key in keys:
        result = WorkingToolResult(
            case_id=case.case_id,
            model_profile=case.model_profile,
            summary={key: True},
            history=(),
            transitions=(),
            state_history={},
            warnings=(PROVISIONAL_MODEL_WARNING,),
        )
        with tempfile.TemporaryDirectory() as tmp:
            try:
                write_result_package(result, Path(tmp))
            except ValueError as exc:
                if "reserved public keys" not in str(exc):
                    return False
            else:
                return False
    return True


def main() -> None:
    case = _canonical_case()
    result = _canonical_result(case)

    with tempfile.TemporaryDirectory() as tmp:
        output = write_result_package(result, Path(tmp))
        files = sorted(path.name for path in output.iterdir())
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))

    gates = {
        "existing_config_types_reused": bool(
            isinstance(case.geometry, PipeGeometry)
            and isinstance(case.numerics, NumericsConfig)
            and isinstance(case.time, TimeConfig)
        ),
        "supported_profile_exact": bool(
            case.model_profile
            is ModelProfile.STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0
        ),
        "public_file_contract_exact": files == sorted(RESULT_FILENAMES),
        "provisional_warning_present": (
            PROVISIONAL_WARNING_CODE in summary["warning_codes"]
        ),
        "formal_authority_false": all(
            summary[name] is False
            for name in (
                "verified",
                "accepted",
                "validated",
                "design_use_approved",
            )
        ),
        "transition_step_is_evidence_only": bool(
            result.transitions[0].absolute_step_number_trigger_used is False
        ),
        "reserved_authority_keys_fail_closed": _reserved_key_gate(case),
    }

    passed = all(gates.values())
    evidence = {
        "schema_version": "stage7_u3_b2_a1_working_tool_w0_contract_check_v1",
        "outcome": OUTCOME if passed else "WORKING_TOOL_W0_CONTRACT_CHECK_FAIL",
        "gates": gates,
        "live_fvm_connected": False,
        "a2_regression_tested": False,
        "verified": False,
        "accepted": False,
        "validated": False,
        "design_use_approved": False,
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
