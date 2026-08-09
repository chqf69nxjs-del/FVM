from __future__ import annotations

import ast
import importlib.util
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient import u3_b1_critical_state_adapter as b1_adapter
from liquid_gas_transient import u3_b1_critical_state_reference as b1_reference
from liquid_gas_transient import u3_b2_fvm_discharge_reference as reference
from liquid_gas_transient import (
    u3_b2_fvm_discharge_reference_authoritative as reference_authoritative,
)
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.eos import LinearLiquidEOS
from liquid_gas_transient.flux import rusanov_flux
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import IDX_RHO_XV, make_conserved
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
    BOUNDARY_UPDATE_POSITIVITY_FAILURE,
    INVENTORY_ORIENTATION_CONTRACT_MISMATCH,
    NONFINITE_INPUT,
    REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
    STAGNATION_RECONSTRUCTION_FAILURE,
    SUCCESS_CLOSED_WALL_MAPPING,
    SUCCESS_ONE_STEP,
    SUCCESS_UNCHOKED_FACE_MAPPING,
    SUCCESS_ZERO_DROP_WALL_IDENTITY,
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    U3B2FvmDischargeAdapter,
    adapter_for_case,
    build_uniform_initial_state,
    evaluate_face_case,
    evaluate_face_matrix,
    evaluate_inventory_orientation_guard,
    load_b1_contract,
    load_contract,
    run_one_step_case,
)

B2_CONTRACT = Path(
    "docs/verification/stage7_u3_b2_fvm_discharge_coupling_contract_v1.json"
)
B2_EXTENSION = Path(
    "docs/verification/"
    "stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1.json"
)
B1_CONTRACT = Path(
    "docs/verification/stage7_u3_b1_critical_state_contract_v1.json"
)
ADAPTER_SOURCE = Path(
    "src/liquid_gas_transient/u3_b2_fvm_discharge_adapter.py"
)
COOLPROP_AVAILABLE = importlib.util.find_spec("CoolProp") is not None
requires_coolprop = pytest.mark.skipif(
    not COOLPROP_AVAILABLE,
    reason="CoolProp is not installed in this environment",
)


@lru_cache(maxsize=1)
def _contracts():
    return load_contract(B2_CONTRACT), load_b1_contract(B1_CONTRACT)


@lru_cache(maxsize=1)
def _reference_package() -> reference.ReferencePackage:
    reference_authoritative.install_authoritative_interpretation()
    return reference.evaluate_reference(
        reference.load_contract(B2_CONTRACT),
        reference.load_extension(B2_EXTENSION),
        b1_reference.load_contract(B1_CONTRACT),
    )


@lru_cache(maxsize=1)
def _adapter_faces():
    contract, b1_contract = _contracts()
    return evaluate_face_matrix(contract, b1_contract)


def _within(actual: float, expected: float, abs_tol: float, rel_tol: float) -> bool:
    return abs(actual - expected) <= max(abs_tol, rel_tol * abs(expected))


def test_adapter_does_not_import_b2_reference() -> None:
    tree = ast.parse(ADAPTER_SOURCE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any("u3_b2_fvm_discharge_reference" in name for name in imported)


def test_solver_without_hook_retains_historical_uniform_noop() -> None:
    grid = UniformGrid(PipeGeometry(length_m=1.0, diameter_m=0.1), 8)
    eos = LinearLiquidEOS()
    U = make_conserved(
        np.full(grid.n_cells, eos.rho_ref),
        np.zeros(grid.n_cells),
        np.full(grid.n_cells, eos.e_ref),
        np.zeros(grid.n_cells),
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    before = np.array(solver.U, copy=True)
    dt = solver.step()
    assert dt > 0.0
    assert np.array_equal(solver.U, before)
    assert solver.step_count == 1


class _RejectFirstTrialHook:
    maximum_halvings = 1
    failure_outcome = BOUNDARY_UPDATE_POSITIVITY_FAILURE

    def __init__(self) -> None:
        self.validation_calls = 0

    def limit_dt(self, *, candidate_dt: float, **kwargs) -> float:
        return candidate_dt

    def evaluate_flux(self, *, U, eos, **kwargs):
        return np.asarray(rusanov_flux(U[-1:], U[-1:], eos)[0], dtype=float)

    def validate_trial(self, **kwargs) -> None:
        self.validation_calls += 1
        if self.validation_calls == 1:
            raise ValueError("synthetic first-trial rejection")


def test_run_history_records_accepted_halved_dt() -> None:
    grid = UniformGrid(PipeGeometry(length_m=1.0, diameter_m=0.1), 8)
    eos = LinearLiquidEOS()
    U = make_conserved(
        np.full(grid.n_cells, eos.rho_ref),
        np.zeros(grid.n_cells),
        np.full(grid.n_cells, eos.e_ref),
        np.zeros(grid.n_cells),
    )
    hook = _RejectFirstTrialHook()
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=0.2,
        left_boundary=TransmissiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    candidate_dt = solver.compute_dt()
    accepted_dt = 0.5 * candidate_dt
    history = solver.run(t_end=candidate_dt, max_steps=3, sample_every=1)
    assert hook.validation_calls == 3
    assert len(history) == 3
    first = history[1]
    assert first["dt_s"] == pytest.approx(accepted_dt)
    assert first["time_s"] == pytest.approx(accepted_dt)
    prim = solver.eos.primitive_from_conserved(solver.U)
    expected_cfl = float(
        np.max((np.abs(prim.u) + prim.c) * accepted_dt / grid.dx)
    )
    assert first["cfl_max"] == pytest.approx(expected_cfl)
    assert history[2]["dt_s"] == pytest.approx(accepted_dt)
    assert history[2]["time_s"] == pytest.approx(candidate_dt)


@requires_coolprop
def test_face_matrix_matches_independent_reference() -> None:
    contract, _ = _contracts()
    tolerances = contract["acceptance_tolerances"]
    actual_rows = _adapter_faces()
    expected_rows = _reference_package().face_rows
    assert len(actual_rows) == len(expected_rows) == 13
    actual = {row.case_id: row for row in actual_rows}
    expected = {row.case_id: row for row in expected_rows}
    assert set(actual) == set(expected)

    comparison_count = 0
    for case_id, expected_row in expected.items():
        actual_eval = actual[case_id]
        assert actual_eval.succeeded
        assert actual_eval.formal_outcome == expected_row.formal_outcome
        assert actual_eval.face is not None
        actual_row = actual_eval.face
        for field, abs_key, rel_key in (
            (
                "F_rho_kg_m2_s",
                "reference_adapter_mass_flux_absolute_kg_m2_s",
                "reference_adapter_mass_flux_relative",
            ),
            (
                "F_rho_u_pa",
                "reference_adapter_momentum_flux_absolute_pa",
                "reference_adapter_momentum_flux_relative",
            ),
            (
                "F_rho_E_W_m2",
                "reference_adapter_energy_flux_absolute_W_m2",
                "reference_adapter_energy_flux_relative",
            ),
        ):
            assert _within(
                float(getattr(actual_row, field)),
                float(getattr(expected_row, field)),
                float(tolerances[abs_key]),
                float(tolerances[rel_key]),
            ), (case_id, field, getattr(actual_row, field), getattr(expected_row, field))
            comparison_count += 1
        assert actual_row.F_rho_xv_kg_m2_s == expected_row.F_rho_xv_kg_m2_s == 0.0
        comparison_count += 1
    assert comparison_count == 52


@requires_coolprop
def test_exact_closed_and_zero_drop_identities() -> None:
    rows = {row.case_id: row for row in _adapter_faces()}
    for case_id in (
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
        "B2-03_CLOSED_GAS_WALL_IDENTITY",
    ):
        evaluation = rows[case_id]
        assert evaluation.face is not None
        face = evaluation.face
        assert face.F_rho_kg_m2_s == 0.0
        assert face.F_rho_u_pa == face.upstream_static_pressure_pa
        assert face.F_rho_E_W_m2 == 0.0
        assert face.F_rho_xv_kg_m2_s == 0.0
    zero = rows["B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY"]
    assert zero.formal_outcome == SUCCESS_ZERO_DROP_WALL_IDENTITY
    assert zero.face is not None and zero.face.zero_drop_canonicalized is True
    assert zero.face.raw_b1_formal_outcome in {
        b1_adapter.SUCCESS_ZERO_PRESSURE_DROP,
        b1_adapter.SUCCESS_UNCHOKED,
    }
    assert "No B1 law" not in zero.formal_message or "no B1 law" in zero.formal_message.lower()


@requires_coolprop
def test_one_step_actual_solver_matches_independent_reference() -> None:
    contract, b1_contract = _contracts()
    actual = run_one_step_case(contract, b1_contract)
    expected = _reference_package().one_step
    tolerances = contract["acceptance_tolerances"]
    assert actual.formal_outcome == expected.formal_outcome == SUCCESS_ONE_STEP
    assert actual.cells == expected.cells == 32
    assert actual.accepted_dt_s > 0.0
    assert actual.accepted_dt_s <= actual.cfl_dt_s
    assert actual.accepted_dt_s <= actual.mass_removal_dt_s
    assert actual.accepted_dt_s <= actual.energy_removal_dt_s
    scale = max(
        abs(expected.U_after_rho),
        abs(expected.U_after_rho_u),
        abs(expected.U_after_rho_E),
        1.0,
    )
    state_error = max(
        abs(actual.U_after_rho - expected.U_after_rho),
        abs(actual.U_after_rho_u - expected.U_after_rho_u),
        abs(actual.U_after_rho_E - expected.U_after_rho_E),
        abs(actual.U_after_rho_xv - expected.U_after_rho_xv),
    ) / scale
    assert state_error <= float(tolerances["one_step_normalized_state_absolute"])
    assert actual.normalized_balance_residual <= float(
        tolerances["one_step_normalized_state_absolute"]
    )
    assert abs(actual.mass_inventory_residual_kg) <= float(
        tolerances["mass_inventory_absolute_kg"]
    )
    assert abs(actual.energy_inventory_residual_J) <= float(
        tolerances["energy_inventory_absolute_J"]
    )
    assert abs(actual.momentum_inventory_residual_kg_m_s) <= float(
        tolerances["momentum_inventory_absolute_kg_m_s"]
    )
    assert actual.vapor_inventory_residual_kg == 0.0
    assert actual.U_after_rho_xv == 0.0


@requires_coolprop
def test_declared_face_guards_are_atomic_outcomes() -> None:
    contract, b1_contract = _contracts()
    cases = {row["case_id"]: row for row in contract["benchmark_cases"]}
    expected = {
        "G-01_REVERSE_PRESSURE": REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
        "G-02_REVERSE_ADJACENT_VELOCITY": REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED,
        "G-03_NONFINITE_ADJACENT_STATE": NONFINITE_INPUT,
        "G-04_SINGLE_PHASE_SCOPE_FAILURE": ADJACENT_STATE_OUTSIDE_SINGLE_PHASE_SCOPE,
    }
    for case_id, outcome in expected.items():
        result = evaluate_face_case(contract, b1_contract, cases[case_id])
        assert result.formal_outcome == outcome
        assert result.face is None
        assert result.guard_triggered_before_flux
        assert result.guard_triggered_before_budget
        assert result.guard_triggered_before_state_mutation


class _FailingStagnationProvider:
    def __init__(self) -> None:
        self._base = CoolPropB2StateProvider()
        self.version = self._base.version
        self.backend_name = self._base.backend_name

    def saturation_temperature(self, pressure_pa: float) -> float:
        return self._base.saturation_temperature(pressure_pa)

    def static_state_from_pT(self, pressure_pa, temperature_K, velocity_m_s):
        return self._base.static_state_from_pT(
            pressure_pa, temperature_K, velocity_m_s
        )

    def reconstruct_from_conserved(self, conserved):
        raise RuntimeError("synthetic HmassSmass inversion failure")


@requires_coolprop
def test_stagnation_reconstruction_guard_is_atomic() -> None:
    contract, b1_contract = _contracts()
    case = next(
        row
        for row in contract["benchmark_cases"]
        if row["case_id"] == "G-05_STAGNATION_RECONSTRUCTION_FAILURE"
    )
    result = evaluate_face_case(
        contract,
        b1_contract,
        case,
        provider=_FailingStagnationProvider(),
    )
    assert result.formal_outcome == STAGNATION_RECONSTRUCTION_FAILURE
    assert result.face is None
    assert result.guard_triggered_before_flux
    assert result.guard_triggered_before_budget
    assert result.guard_triggered_before_state_mutation


class _AlwaysRejectTrialAdapter(U3B2FvmDischargeAdapter):
    def validate_trial(self, **kwargs) -> None:
        raise ValueError("synthetic nonpositive internal energy")


@requires_coolprop
def test_twelve_halving_exhaustion_is_atomic() -> None:
    contract, b1_contract = _contracts()
    case = next(
        row
        for row in contract["benchmark_cases"]
        if row["case_id"] == "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"
    )
    provider = CoolPropB2StateProvider()
    cells = int(case["cells"])
    geometry = contract["geometry"]
    grid = UniformGrid(
        PipeGeometry(
            length_m=float(geometry["pipe_length_m"]),
            diameter_m=float(geometry["pipe_diameter_m"]),
        ),
        cells,
    )
    U, static = build_uniform_initial_state(
        contract, provider, str(case["state_id"]), cells
    )
    eos = CoolPropSinglePhaseEOS(
        provider, boundary_temperature_K=static.temperature_K
    )
    base = adapter_for_case(
        contract,
        b1_contract,
        case,
        provider=provider,
    )
    adapter = _AlwaysRejectTrialAdapter(
        contract=contract,
        b1_contract=b1_contract,
        state_id=base.state_id,
        back_pressure_pa=base.back_pressure_pa,
        opening_fraction=base.opening_fraction,
        discharge_coefficient=base.discharge_coefficient,
        case_id="G-06_BOUNDARY_UPDATE_POSITIVITY_FAILURE",
        provider=provider,
    )
    solver = FvmSolver(
        grid=grid,
        eos=eos,
        U=U,
        cfl=float(case["cfl"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=adapter,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )
    U_before = np.array(solver.U, copy=True)
    assert solver.boundary_budget is not None
    left_before = np.array(solver.boundary_budget.cumulative_left, copy=True)
    right_before = np.array(solver.boundary_budget.cumulative_right, copy=True)
    with pytest.raises(RuntimeError, match=BOUNDARY_UPDATE_POSITIVITY_FAILURE):
        solver.step()
    assert np.array_equal(solver.U, U_before)
    assert solver.t == 0.0
    assert solver.step_count == 0
    assert np.array_equal(solver.boundary_budget.cumulative_left, left_before)
    assert np.array_equal(solver.boundary_budget.cumulative_right, right_before)
    assert solver.boundary_budget.last_dt_s == 0.0


def test_inventory_orientation_guard_is_explicit() -> None:
    result = evaluate_inventory_orientation_guard(right_outward_sign=-1)
    assert result.formal_outcome == INVENTORY_ORIENTATION_CONTRACT_MISMATCH
    assert result.face is None
    assert result.guard_triggered_before_flux
    assert result.guard_triggered_before_budget
    assert result.guard_triggered_before_state_mutation


@requires_coolprop
def test_face_application_order_keeps_vapor_flux_exact_zero() -> None:
    rows = _adapter_faces()
    assert all(
        row.face is not None and row.face.F_rho_xv_kg_m2_s == 0.0
        for row in rows
    )
