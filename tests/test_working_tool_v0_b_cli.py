from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from liquid_gas_transient.working_tool.output_v0_b import V0_B_RUN_FILENAMES
from liquid_gas_transient.working_tool.results import BackendRunData


EXAMPLE = Path("examples/working_tool/canonical_a2_case_v0.json")
CLI_PATH = Path("tools/working_tool/run_working_tool_v0_b.py")


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("working_tool_v0_b_cli", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBackend:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def run_case(self, case):
        self.calls += 1
        if self.fail:
            raise RuntimeError("deliberate v0-B fake backend failure")
        n_cells = case.numerics.n_cells
        accepted_steps = 3
        samples = accepted_steps + 1
        time_s = np.asarray([0.0, 5.0e-5, 9.0e-5, 1.25e-4])
        x_m = np.linspace(0.0, case.geometry.length_m, n_cells)
        shape = (samples, n_cells)
        rho = np.full(shape, 900.0)
        velocity = np.zeros(shape)
        pressure = np.full(shape, case.initial.pressure_pa)
        temperature = np.full(shape, case.initial.temperature_k)
        internal_energy = np.full(shape, 2.0e5)
        vapor = np.zeros(shape)
        conserved = np.stack(
            (rho, rho * velocity, rho * internal_energy, vapor), axis=2
        )
        return BackendRunData(
            summary={
                "accepted_steps": accepted_steps,
                "final_solver_time_s": float(time_s[-1]),
                "target_horizon_reached": True,
                "a2_behavioral_regression_tested": False,
            },
            history=tuple(
                {"step": step, "time_s": float(time_s[step])}
                for step in range(1, samples)
            ),
            state_history={
                "time_s": time_s,
                "x_m": x_m,
                "conserved": conserved,
                "rho_kg_m3": rho,
                "velocity_m_s": velocity,
                "pressure_pa": pressure,
                "temperature_k": temperature,
                "internal_energy_j_kg": internal_energy,
                "vapor_mass_fraction": vapor,
            },
        )


def test_cli_explicit_sampled_run_discloses_truthfully(
    tmp_path: Path,
    capsys,
) -> None:
    cli = _load_cli_module()
    backend = FakeBackend()
    output = tmp_path / "explicit-run"

    code = cli.main(
        [
            "--case",
            str(EXAMPLE),
            "--output-dir",
            str(output),
            "--state-sample-every",
            "2",
        ],
        backend_factory=lambda: backend,
    )
    captured = capsys.readouterr()

    assert code == 0
    assert backend.calls == 1
    assert sorted(path.name for path in output.iterdir()) == sorted(
        V0_B_RUN_FILENAMES
    )
    completion = json.loads(captured.out)
    assert completion["event"] == "WORKING_TOOL_V0_B_COMPLETED"
    assert completion["output_dir"] == str(output.resolve())
    assert completion["storage_mode"] == "SAMPLED_STATE"
    assert completion["state_sample_interval_accepted_steps"] == 2
    assert completion["runtime_state_capture_mode"] == "FULL"
    assert completion["runtime_memory_optimized"] is False
    assert completion["accepted_steps"] == 3
    assert completion["full_state_samples"] == 4
    assert completion["stored_state_samples"] == 3
    assert completion["actual_core_total_bytes"] > 0
    assert completion["formal_status"]["verified"] is False
    assert completion["formal_status"]["accepted"] is False
    assert "WORKING_TOOL_V0_B_PRE_RUN_STORAGE_DISCLOSURE" in captured.err
    assert "raw sample-dependent state-array payload estimate" in captured.err
    assert '"maximum_state_samples": 16001' in captured.err
    assert '"runtime_state_capture_mode": "FULL"' in captured.err
    assert '"runtime_memory_optimized": false' in captured.err
    assert captured.err.count("PROVISIONAL ENGINEERING MODEL") == 2


def test_cli_auto_run_reports_generated_output(tmp_path: Path, capsys) -> None:
    cli = _load_cli_module()
    backend = FakeBackend()
    root = tmp_path / "results"

    code = cli.main(
        ["--case", str(EXAMPLE), "--output-root", str(root)],
        backend_factory=lambda: backend,
    )
    captured = capsys.readouterr()
    completion = json.loads(captured.out)
    output = Path(completion["output_dir"])

    assert code == 0
    assert backend.calls == 1
    assert output.parent == root.resolve()
    assert output.name.startswith(
        "working-tool-v0-b-working-tool-v0-a-canonical-a2__"
    )
    assert sorted(path.name for path in output.iterdir()) == sorted(
        V0_B_RUN_FILENAMES
    )
    assert completion["storage_mode"] == "FULL_STATE"
    assert completion["stored_state_samples"] == 4
    assert '"destination_mode": "AUTO_RUN_DIRECTORY"' in captured.err


def test_cli_validates_case_before_backend_construction(tmp_path: Path, capsys) -> None:
    cli = _load_cli_module()
    bad_case = tmp_path / "bad.json"
    bad_case.write_text("{}", encoding="utf-8")
    factory_called = False

    def factory():
        nonlocal factory_called
        factory_called = True
        return FakeBackend()

    code = cli.main(
        ["--case", str(bad_case), "--output-dir", str(tmp_path / "run")],
        backend_factory=factory,
    )
    captured = capsys.readouterr()

    assert code == 2
    assert factory_called is False
    assert "WORKING_TOOL_V0_B_INPUT_ERROR" in captured.err
    assert not (tmp_path / "run").exists()


def test_cli_runtime_failure_returns_one_and_leaves_no_package(
    tmp_path: Path,
    capsys,
) -> None:
    cli = _load_cli_module()
    backend = FakeBackend(fail=True)
    output = tmp_path / "run"

    code = cli.main(
        ["--case", str(EXAMPLE), "--output-dir", str(output)],
        backend_factory=lambda: backend,
    )
    captured = capsys.readouterr()

    assert code == 1
    assert backend.calls == 1
    assert "WORKING_TOOL_V0_B_RUNTIME_ERROR" in captured.err
    assert not output.exists()
    assert not list(tmp_path.glob(".run.tmp-*"))


@pytest.mark.parametrize(
    "argv",
    [
        ["--case", str(EXAMPLE)],
        [
            "--case",
            str(EXAMPLE),
            "--output-dir",
            "a",
            "--output-root",
            "b",
        ],
        ["--case", str(EXAMPLE), "--output-dir", "a", "--state-sample-every", "0"],
        ["--case", str(EXAMPLE), "--output-dir", "a", "--state-sample-every", "1.0"],
    ],
)
def test_cli_parser_fails_closed_for_invalid_operation_flags(argv: list[str]) -> None:
    cli = _load_cli_module()
    with pytest.raises(SystemExit) as exc_info:
        cli._parser().parse_args(argv)
    assert exc_info.value.code == 2


def test_cli_help_needs_no_manual_pythonpath() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, str(CLI_PATH), "--help"],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "--state-sample-every" in completed.stdout
    assert "--output-root" in completed.stdout
