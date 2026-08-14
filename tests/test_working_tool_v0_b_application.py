from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pytest

from liquid_gas_transient.config import NumericsConfig, PipeGeometry, TimeConfig
from liquid_gas_transient.working_tool.application_v0_b import (
    AUTO_RUN_DIRECTORY_ATTEMPTS,
    V0BApplicationError,
    build_auto_run_directory_name,
    run_loaded_case_v0_b,
    sanitize_case_slug,
)
from liquid_gas_transient.working_tool.case_schema import (
    InitialCondition,
    OutletCondition,
    WorkingToolCase,
)
from liquid_gas_transient.working_tool.operation_policy import (
    WorkingToolOperationPolicy,
)
from liquid_gas_transient.working_tool.output_v0_b import V0_B_RUN_FILENAMES
from liquid_gas_transient.working_tool.results import BackendRunData


START = datetime(2026, 8, 14, 6, 15, 30, tzinfo=timezone.utc)
END = START + timedelta(seconds=1)
LOCAL_ID = "0123456789abcdef0123456789abcdef"


def _case(case_id: str = "Canonical A2") -> WorkingToolCase:
    return WorkingToolCase(
        case_id=case_id,
        geometry=PipeGeometry(10.0, 0.1, 1.0e-5),
        numerics=NumericsConfig(n_cells=3, n_ghost=2, cfl=0.5),
        time=TimeConfig(t_end_s=4.0e-4, max_steps=32000),
        initial=InitialCondition(6.0e6, 285.0, 0.0),
        outlet=OutletCondition(5.0e6, 1.0, 0.8),
    )


def _backend_data(accepted_steps: int = 4) -> BackendRunData:
    n_cells = 3
    samples = accepted_steps + 1
    time_s = np.arange(samples, dtype=np.float64) * 1.0e-4
    x_m = np.linspace(0.0, 10.0, n_cells, dtype=np.float64)
    sample_axis = np.arange(samples, dtype=np.float64)[:, None]
    cell_axis = np.arange(n_cells, dtype=np.float64)[None, :]
    rho = 900.0 + sample_axis + 0.01 * cell_axis
    velocity = 0.1 * sample_axis - 0.001 * cell_axis
    pressure = 6.0e6 - sample_axis - cell_axis
    temperature = 285.0 - 0.001 * sample_axis + 0.01 * cell_axis
    internal_energy = 2.0e5 + 2.0 * sample_axis + cell_axis
    vapor = np.zeros((samples, n_cells), dtype=np.float64)
    conserved = np.stack(
        (rho, rho * velocity, rho * internal_energy, vapor), axis=2
    )
    return BackendRunData(
        summary={
            "accepted_steps": accepted_steps,
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


class RecordingBackend:
    def __init__(
        self,
        *,
        failure: Exception | None = None,
        during_run: Callable[[], None] | None = None,
    ) -> None:
        self.failure = failure
        self.during_run = during_run
        self.calls: list[WorkingToolCase] = []

    def run_case(self, case: WorkingToolCase) -> BackendRunData:
        self.calls.append(case)
        if self.during_run is not None:
            self.during_run()
        if self.failure is not None:
            raise self.failure
        return _backend_data()


class SequenceClock:
    def __init__(self, *values: datetime) -> None:
        self.values = list(values)

    def __call__(self) -> datetime:
        return self.values.pop(0)


class TokenSequence:
    def __init__(self, *values: tuple[int, str]) -> None:
        self.values = list(values)
        self.calls: list[int] = []

    def __call__(self, nbytes: int) -> str:
        self.calls.append(nbytes)
        expected_nbytes, value = self.values.pop(0)
        assert nbytes == expected_nbytes
        return value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Canonical A2", "canonical-a2"),
        ("../A\\B/..", "a-b"),
        ("ＣＯ₂ case", "co2-case"),
        ("日本語のみ", "case"),
        ("---", "case"),
    ],
)
def test_case_slug_is_path_safe(raw: str, expected: str) -> None:
    assert sanitize_case_slug(raw) == expected


def test_case_slug_is_bounded() -> None:
    assert sanitize_case_slug("A" * 200) == "a" * 64


def test_auto_name_contract_is_exact() -> None:
    assert build_auto_run_directory_name(
        case_id="Canonical A2",
        started_at_utc=START,
        random_suffix="8f42a9c731bd",
    ) == "working-tool-v0-b-canonical-a2__20260814T061530Z__8f42a9c731bd"


def test_explicit_run_publishes_exact_requested_directory(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "my-run"
    backend = RecordingBackend()
    receipt = run_loaded_case_v0_b(
        _case(),
        WorkingToolOperationPolicy.explicit(
            output,
            state_sample_interval_accepted_steps=3,
        ),
        backend,
        clock=SequenceClock(START, END),
        token_hex=TokenSequence((16, LOCAL_ID)),
    )

    assert receipt.output_dir == output
    assert receipt.package.output_dir == output
    assert output.is_dir()
    assert sorted(path.name for path in output.iterdir()) == sorted(
        V0_B_RUN_FILENAMES
    )
    assert backend.calls == [receipt.case]
    assert receipt.projection.full_state_samples == 5
    assert receipt.projection.stored_state_samples == 3
    assert receipt.package.manifest["destination"] == {
        "mode": "EXPLICIT",
        "published_directory_name": "my-run",
    }
    assert not any(path.name.startswith(".my-run.tmp-") for path in output.parent.iterdir())


def test_explicit_existing_path_fails_before_backend(tmp_path: Path) -> None:
    for existing_kind in ("directory", "file", "symlink"):
        parent = tmp_path / existing_kind
        parent.mkdir()
        output = parent / "run"
        if existing_kind == "directory":
            output.mkdir()
        elif existing_kind == "file":
            output.write_text("existing", encoding="utf-8")
        else:
            target = parent / "target"
            target.mkdir()
            output.symlink_to(target, target_is_directory=True)
        backend = RecordingBackend()
        with pytest.raises(V0BApplicationError) as exc_info:
            run_loaded_case_v0_b(
                _case(),
                WorkingToolOperationPolicy.explicit(output),
                backend,
                clock=SequenceClock(START),
                token_hex=TokenSequence(),
            )
        assert exc_info.value.classification == (
            "WORKING_TOOL_V0_B_OUTPUT_ALREADY_EXISTS"
        )
        assert backend.calls == []


def test_auto_run_retries_collision_without_rerunning_solver(tmp_path: Path) -> None:
    root = tmp_path / "results"
    first_name = build_auto_run_directory_name(
        case_id="Canonical A2",
        started_at_utc=START,
        random_suffix="000000000001",
    )
    root.mkdir()
    (root / first_name).mkdir()
    tokens = TokenSequence(
        (6, "000000000001"),
        (6, "000000000002"),
        (16, LOCAL_ID),
    )
    backend = RecordingBackend()

    receipt = run_loaded_case_v0_b(
        _case(),
        WorkingToolOperationPolicy.auto_run_directory(root),
        backend,
        clock=SequenceClock(START, END),
        token_hex=tokens,
    )

    assert receipt.output_dir.name.endswith("__000000000002")
    assert receipt.output_dir.parent == root
    assert len(backend.calls) == 1
    assert tokens.calls == [6, 6, 16]
    assert receipt.package.manifest["destination"]["mode"] == (
        "AUTO_RUN_DIRECTORY"
    )


def test_auto_collision_limit_fails_before_backend(tmp_path: Path) -> None:
    root = tmp_path / "results"
    root.mkdir()
    repeated = "000000000001"
    name = build_auto_run_directory_name(
        case_id="Canonical A2",
        started_at_utc=START,
        random_suffix=repeated,
    )
    (root / name).mkdir()
    tokens = TokenSequence(
        *((6, repeated) for _ in range(AUTO_RUN_DIRECTORY_ATTEMPTS))
    )
    backend = RecordingBackend()

    with pytest.raises(V0BApplicationError) as exc_info:
        run_loaded_case_v0_b(
            _case(),
            WorkingToolOperationPolicy.auto_run_directory(root),
            backend,
            clock=SequenceClock(START),
            token_hex=tokens,
        )
    assert exc_info.value.classification == (
        "WORKING_TOOL_V0_B_AUTO_NAME_COLLISION_LIMIT"
    )
    assert backend.calls == []


def test_failure_cleans_hidden_temporary_directory(tmp_path: Path) -> None:
    output = tmp_path / "run"
    backend = RecordingBackend(failure=RuntimeError("backend failed"))
    with pytest.raises(RuntimeError, match="backend failed"):
        run_loaded_case_v0_b(
            _case(),
            WorkingToolOperationPolicy.explicit(output),
            backend,
            clock=SequenceClock(START),
            token_hex=TokenSequence(),
        )
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_detected_publication_race_fails_closed_and_cleans_temp(
    tmp_path: Path,
) -> None:
    output = tmp_path / "run"

    def create_racing_destination() -> None:
        output.mkdir()

    backend = RecordingBackend(during_run=create_racing_destination)
    with pytest.raises(V0BApplicationError) as exc_info:
        run_loaded_case_v0_b(
            _case(),
            WorkingToolOperationPolicy.explicit(output),
            backend,
            clock=SequenceClock(START, END),
            token_hex=TokenSequence((16, LOCAL_ID)),
        )
    assert exc_info.value.classification == (
        "WORKING_TOOL_V0_B_OUTPUT_RACE_DETECTED"
    )
    assert output.is_dir()
    assert list(output.iterdir()) == []
    assert not any(path.name.startswith(".run.tmp-") for path in tmp_path.iterdir())


def test_auto_root_must_be_regular_directory(tmp_path: Path) -> None:
    root = tmp_path / "not-a-directory"
    root.write_text("file", encoding="utf-8")
    backend = RecordingBackend()
    with pytest.raises(V0BApplicationError) as exc_info:
        run_loaded_case_v0_b(
            _case(),
            WorkingToolOperationPolicy.auto_run_directory(root),
            backend,
            clock=SequenceClock(START),
            token_hex=TokenSequence(),
        )
    assert exc_info.value.classification == "WORKING_TOOL_V0_B_OUTPUT_ROOT_ERROR"
    assert backend.calls == []


def test_invalid_random_material_fails_closed_and_cleans(tmp_path: Path) -> None:
    output = tmp_path / "run"
    backend = RecordingBackend()
    with pytest.raises(V0BApplicationError) as exc_info:
        run_loaded_case_v0_b(
            _case(),
            WorkingToolOperationPolicy.explicit(output),
            backend,
            clock=SequenceClock(START, END),
            token_hex=TokenSequence((16, "INVALID")),
        )
    assert exc_info.value.classification == "WORKING_TOOL_V0_B_RANDOM_ID_ERROR"
    assert len(backend.calls) == 1
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []
