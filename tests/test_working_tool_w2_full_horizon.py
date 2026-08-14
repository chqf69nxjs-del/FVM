from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.eos import LinearLiquidEOS
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import make_conserved
from u3_b2_a1_working_tool_w1_a2_live_backend import build_canonical_w1_case
from u3_b2_a1_working_tool_w2_full_horizon_backend import (
    A2FullHorizonWorkingToolBackend,
    RecordingFvmSolver,
    W2CaseScopeError,
    W2_FULL_HORIZON_WARNING,
    W2_FULL_HORIZON_WARNING_CODE,
)
from u3_b2_a1_working_tool_w2_regression import _compare_npz


CONTRACT = Path(
    "docs/verification/stage7_u3_b2_fvm_discharge_coupling_contract_v1.json"
)
B1_CONTRACT = Path(
    "docs/verification/stage7_u3_b1_critical_state_contract_v1.json"
)


def test_w2_noncanonical_case_fails_before_solver_construction() -> None:
    case = build_canonical_w1_case(CONTRACT, case_id="W2-NONCANONICAL")
    bad_case = replace(
        case,
        numerics=replace(case.numerics, cfl=case.numerics.cfl * 0.5),
    )
    backend = A2FullHorizonWorkingToolBackend(
        contract_path=CONTRACT,
        b1_contract_path=B1_CONTRACT,
    )
    with pytest.raises(W2CaseScopeError, match="W2_NONCANONICAL_CASE"):
        backend.run_case(bad_case)
    assert backend.solver_instances_created == 0
    assert backend.runtime_evidence is None


def test_recording_solver_preserves_core_step_exactly() -> None:
    pipe = PipeGeometry(length_m=1.0, diameter_m=0.1, roughness_m=0.0)
    grid = UniformGrid(pipe, 4)
    eos = LinearLiquidEOS()
    U = make_conserved(
        np.full(4, 1000.0),
        np.zeros(4),
        np.full(4, 1.0e5),
        np.zeros(4),
    )
    core = FvmSolver(grid=grid, eos=eos, U=U, cfl=0.1, n_ghost=2)
    RecordingFvmSolver.instance_count = 0
    RecordingFvmSolver.last_instance = None
    recording = RecordingFvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.1,
        n_ghost=2,
    )
    dt = min(core.compute_dt(), recording.compute_dt())
    core_accepted = core.step(dt)
    recording_accepted = recording.step(dt)

    assert core_accepted == recording_accepted
    assert core.t == recording.t
    assert core.step_count == recording.step_count == 1
    assert np.array_equal(core.U, recording.U)
    assert RecordingFvmSolver.instance_count == 1
    assert len(recording.accepted_state_snapshots) == 2
    assert recording.accepted_time_snapshots_s == [0.0, recording.t]
    assert np.array_equal(recording.accepted_state_snapshots[-1], recording.U)


def test_w2_npz_comparison_checks_dtype_shape_and_values(tmp_path: Path) -> None:
    parent = tmp_path / "parent.npz"
    exact = tmp_path / "exact.npz"
    mismatch = tmp_path / "mismatch.npz"
    np.savez(parent, values=np.asarray([1.0, 2.0], dtype=np.float64))
    np.savez(exact, values=np.asarray([1.0, 2.0], dtype=np.float64))
    np.savez(mismatch, values=np.asarray([1.0, 2.0], dtype=np.float32))

    exact_result = _compare_npz(exact, parent)
    mismatch_result = _compare_npz(mismatch, parent)
    assert exact_result["values"]["exact_match"] is True
    assert mismatch_result["values"]["exact_match"] is False


def test_w2_reuses_a2_path_and_declares_canonical_warning() -> None:
    import u3_b2_a1_working_tool_w2_full_horizon_backend as backend_module

    source = Path(backend_module.__file__).read_text(encoding="utf-8")
    assert "base._run(" in source
    assert "a2.ModelManagedLiveFvmHook" in source
    assert "topology_v3._install_correction()" in source
    for forbidden in (
        "_dynamic_seeded_root_run(",
        "_bounded_dynamic_root_run(",
        "_guard_front_solve_three_branch_boundary(",
        "def evaluate_pressure(",
        "def bisect_root(",
    ):
        assert forbidden not in source
    assert W2_FULL_HORIZON_WARNING.code == W2_FULL_HORIZON_WARNING_CODE
    assert "not VERIFIED" in W2_FULL_HORIZON_WARNING.message
    assert "DESIGN-USE APPROVED" in W2_FULL_HORIZON_WARNING.message
