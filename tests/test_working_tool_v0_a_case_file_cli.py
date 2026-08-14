from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from liquid_gas_transient.working_tool import (
    BackendRunData,
    CaseFileError,
    OutputDirectoryError,
    PROVISIONAL_WARNING_CODE,
    RESULT_FILENAMES,
    load_case_file,
    run_case_file,
)


EXAMPLE = Path("examples/working_tool/canonical_a2_case_v0.json")
CLI_PATH = Path("tools/working_tool/run_working_tool_v0_a.py")


def _canonical_mapping() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write_mapping(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("working_tool_v0_a_cli", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBackend:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def run_case(self, case):
        self.calls += 1
        if self.fail:
            raise RuntimeError("deliberate fake backend failure")
        return BackendRunData(
            summary={
                "accepted_steps": 3,
                "final_solver_time_s": 1.25e-4,
                "target_horizon_reached": True,
                "backend_name": "FAKE_V0_A_BACKEND",
            },
            history=(
                {"step": 1, "time_s": 5.0e-5},
                {"step": 2, "time_s": 9.0e-5},
                {"step": 3, "time_s": 1.25e-4},
            ),
            state_history={
                "time_s": np.asarray([0.0, 5.0e-5, 9.0e-5, 1.25e-4]),
                "conserved": np.zeros((4, 1, 4), dtype=np.float64),
            },
        )


def test_canonical_example_is_deterministic_and_loads_exactly() -> None:
    case = load_case_file(EXAMPLE)
    expected_text = json.dumps(
        case.as_dict(), indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    assert EXAMPLE.read_text(encoding="utf-8") == expected_text
    assert case.case_id == "WORKING-TOOL-V0-A-CANONICAL-A2"
    assert case.geometry.length_m == 1.0
    assert case.geometry.diameter_m == 0.011283791670955126
    assert case.numerics.n_cells == 32
    assert case.numerics.n_ghost == 2
    assert case.numerics.cfl == 0.1
    assert case.time.max_steps == 32000
    assert case.time.t_end_s == 0.004285834855172021
    assert case.initial.pressure_pa == 5000000.0
    assert case.initial.temperature_k == 282.43392381063524
    assert case.outlet.back_pressure_pa == 4950000.0
    assert case.outlet.opening_fraction == 0.5
    assert case.outlet.discharge_coefficient == 0.8


@pytest.mark.parametrize(
    ("text", "classification"),
    [
        (
            '{"case_id":"first","case_id":"second"}',
            "WORKING_TOOL_CASE_FILE_DUPLICATE_KEY",
        ),
        ("{not-json}", "WORKING_TOOL_CASE_FILE_INVALID_JSON"),
        ("[]", "WORKING_TOOL_CASE_FILE_TYPE_ERROR"),
        ("{\"value\": NaN}", "WORKING_TOOL_CASE_FILE_NONFINITE_JSON"),
        ("{\"value\": Infinity}", "WORKING_TOOL_CASE_FILE_NONFINITE_JSON"),
    ],
)
def test_case_loader_rejects_invalid_json_forms(
    tmp_path: Path,
    text: str,
    classification: str,
) -> None:
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CaseFileError) as exc_info:
        load_case_file(path)
    assert exc_info.value.classification == classification


def test_case_loader_rejects_invalid_utf8_and_nonregular_path(tmp_path: Path) -> None:
    invalid_utf8 = tmp_path / "invalid-utf8.json"
    invalid_utf8.write_bytes(b"\xff\xfe")
    with pytest.raises(CaseFileError) as exc_info:
        load_case_file(invalid_utf8)
    assert exc_info.value.classification == "WORKING_TOOL_CASE_FILE_INVALID_UTF8"

    directory = tmp_path / "directory.json"
    directory.mkdir()
    with pytest.raises(CaseFileError) as exc_info:
        load_case_file(directory)
    assert exc_info.value.classification == "WORKING_TOOL_CASE_FILE_NOT_REGULAR"


@pytest.mark.parametrize(
    ("mutation", "classification"),
    [
        (
            lambda data: data.update({"unknown_root": 1}),
            "WORKING_TOOL_CASE_FILE_SCHEMA_ERROR",
        ),
        (
            lambda data: data.pop("outlet"),
            "WORKING_TOOL_CASE_FILE_SCHEMA_ERROR",
        ),
        (
            lambda data: data["geometry"].update({"unknown_geometry": 1}),
            "WORKING_TOOL_CASE_FILE_SCHEMA_ERROR",
        ),
        (
            lambda data: data["numerics"].update({"n_cells": True}),
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
        ),
        (
            lambda data: data["numerics"].update({"n_cells": 32.0}),
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
        ),
        (
            lambda data: data["initial"].update({"pressure_pa": "5000000"}),
            "WORKING_TOOL_CASE_FILE_TYPE_ERROR",
        ),
        (
            lambda data: data.update({"schema_version": "future-schema"}),
            "WORKING_TOOL_CASE_FILE_UNSUPPORTED_SCHEMA",
        ),
        (
            lambda data: data.update({"model_profile": "FUTURE_PROFILE"}),
            "WORKING_TOOL_CASE_FILE_UNSUPPORTED_MODEL_PROFILE",
        ),
        (
            lambda data: data.update({"fluid": "N2"}),
            "WORKING_TOOL_CASE_FILE_VALUE_ERROR",
        ),
    ],
)
def test_case_loader_fails_closed_for_schema_and_scope_errors(
    tmp_path: Path,
    mutation,
    classification: str,
) -> None:
    data = _canonical_mapping()
    mutation(data)
    path = _write_mapping(tmp_path / "case.json", data)
    with pytest.raises(CaseFileError) as exc_info:
        load_case_file(path)
    assert exc_info.value.classification == classification


def test_case_file_application_writes_exact_public_package_atomically(
    tmp_path: Path,
) -> None:
    backend = FakeBackend()
    output = tmp_path / "result"
    receipt = run_case_file(EXAMPLE, output, backend)

    assert backend.calls == 1
    assert receipt.output_dir == output
    assert receipt.case.case_id == "WORKING-TOOL-V0-A-CANONICAL-A2"
    assert sorted(path.name for path in output.iterdir()) == sorted(RESULT_FILENAMES)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["accepted_steps"] == 3
    assert summary["verified"] is False
    assert summary["accepted"] is False
    assert summary["validated"] is False
    assert summary["design_use_approved"] is False
    assert summary["warning_codes"] == [PROVISIONAL_WARNING_CODE]
    assert not list(tmp_path.glob(".result.tmp-*"))


def test_case_file_application_rejects_existing_output_before_backend_call(
    tmp_path: Path,
) -> None:
    backend = FakeBackend()
    output = tmp_path / "result"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("unchanged", encoding="utf-8")

    with pytest.raises(OutputDirectoryError) as exc_info:
        run_case_file(EXAMPLE, output, backend)
    assert exc_info.value.classification == "WORKING_TOOL_OUTPUT_ALREADY_EXISTS"
    assert backend.calls == 0
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_case_file_application_cleans_partial_output_after_runtime_failure(
    tmp_path: Path,
) -> None:
    backend = FakeBackend(fail=True)
    output = tmp_path / "result"
    with pytest.raises(RuntimeError, match="deliberate fake backend failure"):
        run_case_file(EXAMPLE, output, backend)
    assert backend.calls == 1
    assert not output.exists()
    assert not list(tmp_path.glob(".result.tmp-*"))


def test_cli_validates_before_backend_construction(tmp_path: Path, capsys) -> None:
    cli = _load_cli_module()
    data = _canonical_mapping()
    data.pop("outlet")
    bad_case = _write_mapping(tmp_path / "bad.json", data)
    output = tmp_path / "result"
    factory_called = False

    def factory():
        nonlocal factory_called
        factory_called = True
        return FakeBackend()

    return_code = cli.main(
        ["--case", str(bad_case), "--output-dir", str(output)],
        backend_factory=factory,
    )
    captured = capsys.readouterr()
    assert return_code == 2
    assert factory_called is False
    assert "WORKING_TOOL_V0_A_INPUT_ERROR" in captured.err
    assert "PROVISIONAL ENGINEERING MODEL" in captured.err
    assert not output.exists()


def test_cli_runs_public_case_file_path_with_visible_disclosure(
    tmp_path: Path,
    capsys,
) -> None:
    cli = _load_cli_module()
    backend = FakeBackend()
    output = tmp_path / "result"
    return_code = cli.main(
        ["--case", str(EXAMPLE), "--output-dir", str(output)],
        backend_factory=lambda: backend,
    )
    captured = capsys.readouterr()

    assert return_code == 0
    assert backend.calls == 1
    assert sorted(path.name for path in output.iterdir()) == sorted(RESULT_FILENAMES)
    completion = json.loads(captured.out)
    assert completion["case_id"] == "WORKING-TOOL-V0-A-CANONICAL-A2"
    assert completion["accepted_steps"] == 3
    assert completion["target_horizon_reached"] is True
    assert completion["warning_codes"] == [PROVISIONAL_WARNING_CODE]
    assert captured.err.count("PROVISIONAL ENGINEERING MODEL") == 2
    assert "not VERIFIED" in captured.err
    assert "DESIGN-USE APPROVED" in captured.err


def test_public_v0_a_application_sources_have_no_verification_dependency() -> None:
    import liquid_gas_transient.working_tool.application as application
    import liquid_gas_transient.working_tool.case_io as case_io

    for module in (application, case_io):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "tools.verification",
            "u3_b2_a1_increment_9",
            "u3_b2_a1_working_tool_w1",
            "u3_b2_a1_working_tool_w2",
            "workflow_run",
            "artifact_id",
            "parent_authority",
        ):
            assert forbidden not in source
