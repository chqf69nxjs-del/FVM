from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.config import NumericsConfig, PipeGeometry, TimeConfig
from liquid_gas_transient.working_tool.case_schema import (
    InitialCondition,
    OutletCondition,
    WorkingToolCase,
)
from liquid_gas_transient.working_tool.operation_policy import (
    WorkingToolOperationPolicy,
)
from liquid_gas_transient.working_tool.output import (
    RESULT_FILENAMES,
    write_result_package,
)
from liquid_gas_transient.working_tool.output_v0_b import (
    V0_B_RUN_FILENAMES,
    V0BOutputError,
    validate_v0_b_package,
    write_v0_b_result_package,
)
from liquid_gas_transient.working_tool.results import (
    PROVISIONAL_MODEL_WARNING,
    WorkingToolResult,
)
from liquid_gas_transient.working_tool.run_manifest import (
    RUN_MANIFEST_FILENAME,
    RUN_MANIFEST_SCHEMA,
    V0_B_OUTPUT_CONTRACT,
    RunManifestError,
    build_run_manifest,
    canonical_working_tool_case_bytes,
    measure_core_files,
    resolved_case_sha256,
)
from liquid_gas_transient.working_tool.storage_projection import (
    project_state_storage,
)


STARTED_AT = datetime(2026, 8, 14, 6, 15, 30, 123456, tzinfo=timezone.utc)
COMPLETED_AT = STARTED_AT + timedelta(seconds=2)
LOCAL_RUN_ID = "0123456789abcdef0123456789abcdef"


def _case() -> WorkingToolCase:
    return WorkingToolCase(
        case_id="V0-B-MANIFEST-TEST",
        geometry=PipeGeometry(
            length_m=10.0,
            diameter_m=0.1,
            roughness_m=1.0e-5,
        ),
        numerics=NumericsConfig(n_cells=3, n_ghost=2, cfl=0.5),
        time=TimeConfig(t_end_s=6.4e-4, max_steps=32000),
        initial=InitialCondition(
            pressure_pa=6.0e6,
            temperature_k=285.0,
            velocity_m_s=0.0,
        ),
        outlet=OutletCondition(
            back_pressure_pa=5.0e6,
            opening_fraction=1.0,
            discharge_coefficient=0.8,
        ),
    )


def _full_result(*, accepted_steps: int = 4) -> WorkingToolResult:
    case = _case()
    n_cells = case.numerics.n_cells
    samples = accepted_steps + 1
    time_s = np.arange(samples, dtype=np.float64) * 1.0e-4
    x_m = np.linspace(0.0, case.geometry.length_m, n_cells, dtype=np.float64)
    sample_axis = np.arange(samples, dtype=np.float64)[:, None]
    cell_axis = np.arange(n_cells, dtype=np.float64)[None, :]
    rho = 900.0 + sample_axis + 0.01 * cell_axis
    velocity = 0.1 * sample_axis - 0.001 * cell_axis
    pressure = 6.0e6 - 10.0 * sample_axis - cell_axis
    temperature = 285.0 - 0.001 * sample_axis + 0.01 * cell_axis
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

    return WorkingToolResult(
        case_id=case.case_id,
        model_profile=case.model_profile,
        summary={
            "accepted_steps": accepted_steps,
            "final_solver_time_s": float(time_s[-1]),
            "target_horizon_reached": True,
            "a2_behavioral_regression_tested": False,
        },
        history=tuple(
            {
                "step": step,
                "time_s": float(time_s[step]),
                "accepted_log_value": step * 2,
            }
            for step in range(1, samples)
        ),
        transitions=(),
        state_history={
            "time_s": time_s,
            "x_m": x_m,
            "conserved": conserved,
            "rho_kg_m3": rho.astype(np.float64, copy=False),
            "velocity_m_s": velocity.astype(np.float64, copy=False),
            "pressure_pa": pressure.astype(np.float64, copy=False),
            "temperature_k": temperature.astype(np.float64, copy=False),
            "internal_energy_j_kg": internal_energy.astype(
                np.float64,
                copy=False,
            ),
            "vapor_mass_fraction": vapor_mass_fraction,
        },
        warnings=(PROVISIONAL_MODEL_WARNING,),
    )


def _write_package(
    output_dir: Path,
    *,
    interval: int,
):
    case = _case()
    policy = WorkingToolOperationPolicy.explicit(
        output_dir,
        state_sample_interval_accepted_steps=interval,
    )
    projection = project_state_storage(_full_result(), interval)
    output_dir.mkdir()
    return write_v0_b_result_package(
        case=case,
        policy=policy,
        projection=projection,
        output_dir=output_dir,
        published_directory_name=output_dir.name,
        started_at_utc=STARTED_AT,
        completed_at_utc=COMPLETED_AT,
        local_run_id=LOCAL_RUN_ID,
    )


def _all_mapping_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(key)
            keys.update(_all_mapping_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(_all_mapping_keys(nested))
    return keys


def test_resolved_case_sha_uses_exact_canonical_serialization() -> None:
    expected = (
        b'{"case_id":"V0-B-MANIFEST-TEST","fluid":"CO2",'
        b'"geometry":{"diameter_m":0.1,"length_m":10.0,'
        b'"roughness_m":1e-05},"initial":{"pressure_pa":6000000.0,'
        b'"temperature_k":285.0,"velocity_m_s":0.0},'
        b'"model_profile":"STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0",'
        b'"numerics":{"cfl":0.5,"n_cells":3,"n_ghost":2},'
        b'"outlet":{"back_pressure_pa":5000000.0,'
        b'"discharge_coefficient":0.8,"opening_fraction":1.0},'
        b'"schema_version":"stage7_u3_b2_a1_working_tool_case_v0",'
        b'"time":{"max_steps":32000,"t_end_s":0.00064}}'
    )
    assert canonical_working_tool_case_bytes(_case()) == expected
    assert resolved_case_sha256(_case()) == (
        "aeaa700bf72cfbf7b3d601d9ab8e3d8e5eaed2881038b959b04c7d69ff563a7c"
    )


def test_full_mode_core_files_are_v0_a_semantic_exact(tmp_path: Path) -> None:
    v0_a_dir = tmp_path / "v0-a"
    v0_b_dir = tmp_path / "v0-b"
    source = _full_result()
    write_result_package(source, v0_a_dir)
    receipt = _write_package(v0_b_dir, interval=1)

    assert tuple(path.name for path in validate_v0_b_package(v0_b_dir)) == (
        V0_B_RUN_FILENAMES
    )
    assert sorted(path.name for path in v0_a_dir.iterdir()) == sorted(
        RESULT_FILENAMES
    )
    assert sorted(path.name for path in v0_b_dir.iterdir()) == sorted(
        V0_B_RUN_FILENAMES
    )

    assert json.loads((v0_a_dir / "summary.json").read_text()) == json.loads(
        (v0_b_dir / "summary.json").read_text()
    )
    for filename in ("history.csv", "transitions.csv", "warnings.csv"):
        assert (v0_a_dir / filename).read_bytes() == (
            v0_b_dir / filename
        ).read_bytes()

    with np.load(v0_a_dir / "state_history.npz") as expected_npz:
        with np.load(v0_b_dir / "state_history.npz") as actual_npz:
            assert expected_npz.files == actual_npz.files
            for name in expected_npz.files:
                assert expected_npz[name].dtype == actual_npz[name].dtype
                assert expected_npz[name].shape == actual_npz[name].shape
                assert np.array_equal(expected_npz[name], actual_npz[name])

    assert receipt.manifest["storage"]["mode"] == "FULL_STATE"
    assert receipt.manifest["storage"]["full_state_samples"] == 5
    assert receipt.manifest["storage"]["stored_state_samples"] == 5
    assert (
        receipt.manifest["storage"]["raw_state_payload_reduction_ratio"]
        == 0.0
    )


def test_sampled_mode_changes_only_state_npz_storage(tmp_path: Path) -> None:
    full_dir = tmp_path / "full"
    sampled_dir = tmp_path / "sampled"
    full_receipt = _write_package(full_dir, interval=1)
    sampled_receipt = _write_package(sampled_dir, interval=3)

    for filename in ("summary.json", "history.csv", "transitions.csv", "warnings.csv"):
        assert (full_dir / filename).read_bytes() == (
            sampled_dir / filename
        ).read_bytes()

    with np.load(sampled_dir / "state_history.npz") as sampled_npz:
        np.testing.assert_allclose(
            sampled_npz["time_s"],
            np.asarray([0.0, 0.0003, 0.0004], dtype=np.float64),
            rtol=0.0,
            atol=0.0,
        )
        assert sampled_npz["conserved"].shape[0] == 3
        assert sampled_npz["x_m"].shape == (3,)
    assert sampled_receipt.manifest["storage"]["mode"] == "SAMPLED_STATE"
    assert sampled_receipt.manifest["storage"]["full_state_samples"] == 5
    assert sampled_receipt.manifest["storage"]["stored_state_samples"] == 3
    assert sampled_receipt.core_total_bytes < full_receipt.core_total_bytes


def test_manifest_records_actual_core_file_integrity_only(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    receipt = _write_package(output_dir, interval=3)
    manifest = json.loads((output_dir / RUN_MANIFEST_FILENAME).read_text())

    assert manifest == receipt.manifest
    assert manifest["schema"] == RUN_MANIFEST_SCHEMA
    assert manifest["schema_version"] == 1
    assert manifest["output_contract"] == V0_B_OUTPUT_CONTRACT
    assert manifest["local_run_id"] == LOCAL_RUN_ID
    assert manifest["started_at_utc"] == "2026-08-14T06:15:30.123456Z"
    assert manifest["completed_at_utc"] == "2026-08-14T06:15:32.123456Z"
    assert manifest["destination"] == {
        "mode": "EXPLICIT",
        "published_directory_name": "run",
    }
    assert manifest["case"] == {
        "case_id": "V0-B-MANIFEST-TEST",
        "resolved_case_sha256": (
            "aeaa700bf72cfbf7b3d601d9ab8e3d8e5eaed2881038b959b04c7d69ff563a7c"
        ),
        "model_profile": "STAGE7_U3_B2_SINGLE_PHASE_PROVISIONAL_V0",
        "fluid": "CO2",
    }
    assert manifest["result"] == {
        "accepted_steps": 4,
        "final_time_s": 0.0004,
        "target_reached": True,
    }
    assert set(manifest["core_files"]) == set(RESULT_FILENAMES)
    assert RUN_MANIFEST_FILENAME not in manifest["core_files"]

    expected_total = 0
    for filename in RESULT_FILENAMES:
        payload = (output_dir / filename).read_bytes()
        expected_total += len(payload)
        assert manifest["core_files"][filename] == {
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    assert manifest["core_total_bytes"] == expected_total
    assert receipt.core_total_bytes == expected_total


def test_public_manifest_contains_no_verification_authority(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    receipt = _write_package(output_dir, interval=1)
    keys = _all_mapping_keys(receipt.manifest)

    for forbidden in (
        "workflow_id",
        "workflow_run_id",
        "job_id",
        "artifact_id",
        "artifact_digest",
        "a2_authority",
        "parent_authority",
        "exact_regression_pass",
        "mismatch_count",
        "context_restoration_evidence",
        "pytest_result",
        "ci_success",
        "verification_approval",
    ):
        assert forbidden not in keys

    assert receipt.manifest["formal_status"] == {
        "provisional_engineering_end_to_end_working_slice": True,
        "verified": False,
        "accepted": False,
        "physically_validated": False,
        "design_use_accepted": False,
        "production_approved": False,
    }
    summary = json.loads((output_dir / "summary.json").read_text())
    assert summary["a2_behavioral_regression_tested"] is False
    assert summary["verified"] is False
    assert summary["accepted"] is False
    assert summary["validated"] is False
    assert summary["design_use_approved"] is False


def test_writer_requires_existing_empty_directory(tmp_path: Path) -> None:
    case = _case()
    projection = project_state_storage(_full_result(), 1)
    missing = tmp_path / "missing"
    policy = WorkingToolOperationPolicy.explicit(missing)

    with pytest.raises(V0BOutputError) as exc_info:
        write_v0_b_result_package(
            case=case,
            policy=policy,
            projection=projection,
            output_dir=missing,
            published_directory_name="missing",
            started_at_utc=STARTED_AT,
            completed_at_utc=COMPLETED_AT,
            local_run_id=LOCAL_RUN_ID,
        )
    assert exc_info.value.classification == (
        "WORKING_TOOL_V0_B_OUTPUT_DIRECTORY_ERROR"
    )

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "unexpected").write_text("x", encoding="utf-8")
    policy = WorkingToolOperationPolicy.explicit(nonempty)
    with pytest.raises(V0BOutputError) as exc_info:
        write_v0_b_result_package(
            case=case,
            policy=policy,
            projection=projection,
            output_dir=nonempty,
            published_directory_name="nonempty",
            started_at_utc=STARTED_AT,
            completed_at_utc=COMPLETED_AT,
            local_run_id=LOCAL_RUN_ID,
        )
    assert exc_info.value.classification == "WORKING_TOOL_V0_B_OUTPUT_NOT_EMPTY"


def test_manifest_fails_closed_on_policy_or_status_mismatch(tmp_path: Path) -> None:
    output_dir = tmp_path / "core"
    output_dir.mkdir()
    source = _full_result()
    write_result_package(source, output_dir)
    core_files = measure_core_files(output_dir)
    projection = project_state_storage(source, 1)
    sampled_policy = WorkingToolOperationPolicy.explicit(
        tmp_path / "published",
        state_sample_interval_accepted_steps=2,
    )

    with pytest.raises(RunManifestError) as exc_info:
        build_run_manifest(
            case=_case(),
            policy=sampled_policy,
            projection=projection,
            published_directory_name="published",
            started_at_utc=STARTED_AT,
            completed_at_utc=COMPLETED_AT,
            local_run_id=LOCAL_RUN_ID,
            core_files=core_files,
        )
    assert exc_info.value.classification == (
        "WORKING_TOOL_V0_B_POLICY_PROJECTION_MISMATCH"
    )

    invalid_result = replace(projection.result)
    object.__setattr__(invalid_result, "verified", True)
    verified_projection = replace(
        projection,
        result=invalid_result,
    )
    full_policy = WorkingToolOperationPolicy.explicit(tmp_path / "published")
    with pytest.raises(RunManifestError) as exc_info:
        build_run_manifest(
            case=_case(),
            policy=full_policy,
            projection=verified_projection,
            published_directory_name="published",
            started_at_utc=STARTED_AT,
            completed_at_utc=COMPLETED_AT,
            local_run_id=LOCAL_RUN_ID,
            core_files=core_files,
        )
    assert exc_info.value.classification == "WORKING_TOOL_V0_B_FORMAL_STATUS_ERROR"


def test_manifest_rejects_ambiguous_target_field_and_invalid_metadata(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "core"
    output_dir.mkdir()
    source = _full_result()
    write_result_package(source, output_dir)
    core_files = measure_core_files(output_dir)
    policy = WorkingToolOperationPolicy.explicit(tmp_path / "published")
    ambiguous = replace(
        source,
        summary={**source.summary, "target_reached": True},
    )
    projection = project_state_storage(ambiguous, 1)

    with pytest.raises(RunManifestError, match="exactly one"):
        build_run_manifest(
            case=_case(),
            policy=policy,
            projection=projection,
            published_directory_name="published",
            started_at_utc=STARTED_AT,
            completed_at_utc=COMPLETED_AT,
            local_run_id=LOCAL_RUN_ID,
            core_files=core_files,
        )

    valid_projection = project_state_storage(source, 1)
    for invalid_run_id in ("", "ABC", "g" * 32, "0" * 31):
        with pytest.raises(ValueError):
            build_run_manifest(
                case=_case(),
                policy=policy,
                projection=valid_projection,
                published_directory_name="published",
                started_at_utc=STARTED_AT,
                completed_at_utc=COMPLETED_AT,
                local_run_id=invalid_run_id,
                core_files=core_files,
            )

    with pytest.raises(ValueError, match="must not precede"):
        build_run_manifest(
            case=_case(),
            policy=policy,
            projection=valid_projection,
            published_directory_name="published",
            started_at_utc=COMPLETED_AT,
            completed_at_utc=STARTED_AT,
            local_run_id=LOCAL_RUN_ID,
            core_files=core_files,
        )
    with pytest.raises(ValueError, match="one path component"):
        build_run_manifest(
            case=_case(),
            policy=policy,
            projection=valid_projection,
            published_directory_name="../published",
            started_at_utc=STARTED_AT,
            completed_at_utc=COMPLETED_AT,
            local_run_id=LOCAL_RUN_ID,
            core_files=core_files,
        )


def test_package_validator_rejects_extra_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    _write_package(output_dir, interval=1)
    (output_dir / "extra.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(V0BOutputError) as exc_info:
        validate_v0_b_package(output_dir)
    assert exc_info.value.classification == (
        "WORKING_TOOL_V0_B_OUTPUT_CONTRACT_ERROR"
    )
