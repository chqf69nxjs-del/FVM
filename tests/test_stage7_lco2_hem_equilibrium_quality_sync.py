from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.hem_equilibrium_quality_sync import (
    HEMEquilibriumQualityProjection,
    HEMEquilibriumQualitySyncConfig,
    HEMEquilibriumQualitySyncError,
    HEMQualityEvaluation,
)
from liquid_gas_transient.hem_uniform_state_preservation import (
    HEMUniformStatePreservationError,
    VerificationHEMEquilibriumEOS,
)
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import (
    IDX_RHO_XV,
    PrimitiveState,
    inventory,
    make_conserved,
)


def _fixed_evaluator(
    quality,
    *,
    phase_class: str = "liquid_vapor_two_phase",
    scope_status: str = "supported_candidate",
    quality_defined: bool = True,
):
    def evaluate(rho: np.ndarray, e: np.ndarray) -> HEMQualityEvaluation:
        del e
        quality_array = np.broadcast_to(
            np.asarray(quality, dtype=float),
            rho.shape,
        ).copy()
        return HEMQualityEvaluation(
            quality=quality_array,
            quality_defined=np.full(rho.shape, quality_defined, dtype=bool),
            raw_phase=np.full(rho.shape, "twophase"),
            phase_class=np.full(rho.shape, phase_class),
            scope_status=np.full(rho.shape, scope_status),
        )

    return evaluate


def _analytic_equilibrium_quality(rho: np.ndarray, e: np.ndarray) -> np.ndarray:
    return 0.30 + 1.0e-3 * np.asarray(e) + 0.02 * (np.asarray(rho) - 1.0)


def _analytic_evaluator(rho: np.ndarray, e: np.ndarray) -> HEMQualityEvaluation:
    quality = _analytic_equilibrium_quality(rho, e)
    return HEMQualityEvaluation(
        quality=np.asarray(quality, dtype=float),
        quality_defined=np.ones(rho.shape, dtype=bool),
        raw_phase=np.full(rho.shape, "twophase"),
        phase_class=np.full(rho.shape, "liquid_vapor_two_phase"),
        scope_status=np.full(rho.shape, "supported_candidate"),
    )


class _StrictAnalyticHEMEOS:
    quality_tolerance = 1.0e-12

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        array = np.asarray(U, dtype=float)
        rho = array[..., 0]
        u = array[..., 1] / rho
        E = array[..., 2] / rho
        e = E - 0.5 * u**2
        transported_quality = array[..., 3] / rho
        equilibrium_quality = _analytic_equilibrium_quality(rho, e)
        mismatch = np.abs(transported_quality - equilibrium_quality)
        if np.any(mismatch > self.quality_tolerance):
            raise ValueError("transported quality mismatch")
        p = 1.0e5 + 2.0e4 * (rho - 1.0) + 100.0 * (e - 100.0)
        c = np.full_like(rho, 50.0, dtype=float)
        T = 300.0 + 0.1 * (e - 100.0)
        return PrimitiveState(
            rho=np.array(rho, copy=True),
            u=np.array(u, copy=True),
            p=np.asarray(p, dtype=float),
            e=np.array(e, copy=True),
            E=np.array(E, copy=True),
            T=np.asarray(T, dtype=float),
            xv=np.asarray(equilibrium_quality, dtype=float),
            alpha=np.asarray(equilibrium_quality, dtype=float),
            c=c,
        )

    def density_from_pressure(self, p):
        raise NotImplementedError("transmissive-boundary verification only")


@pytest.mark.parametrize(
    "value",
    [-1.0, np.nan, np.inf],
)
def test_sync_config_rejects_invalid_activation_tolerance(value):
    with pytest.raises(ValueError):
        HEMEquilibriumQualitySyncConfig(activation_tolerance=value)


def test_equilibrated_state_is_bitwise_noop():
    rho = np.asarray([10.0, 20.0])
    quality = np.asarray([0.20, 0.80])
    U = make_conserved(rho, 0.0, 100.0, quality)
    projection = HEMEquilibriumQualityProjection(
        evaluator=_fixed_evaluator(quality)
    )

    result = projection.project(U)

    assert np.array_equal(result.U_before, U)
    assert np.array_equal(result.U_after, U)
    assert not np.any(result.projection_applied)
    assert result.summary()["projection_cell_count"] == 0
    assert result.summary()["quality_synchronized_within_tolerance"] is True


def test_mismatch_projects_only_rho_quality_and_is_idempotent():
    rho = np.asarray([10.0, 20.0])
    U = make_conserved(rho, 0.0, 100.0, np.asarray([0.10, 0.90]))
    projection = HEMEquilibriumQualityProjection(
        evaluator=_fixed_evaluator(np.asarray([0.20, 0.80]))
    )

    result = projection.project(U)

    assert np.array_equal(result.U_before[..., :IDX_RHO_XV], result.U_after[..., :IDX_RHO_XV])
    np.testing.assert_allclose(result.q_after, [0.20, 0.80], rtol=0.0, atol=1.0e-15)
    np.testing.assert_allclose(result.delta_q, [0.10, -0.10], rtol=0.0, atol=1.0e-15)
    assert result.summary()["projection_cell_count"] == 2
    assert result.summary()["evaporation_cell_count"] == 1
    assert result.summary()["condensation_cell_count"] == 1
    assert result.summary()["mass_bitwise_unchanged"] is True
    assert result.summary()["momentum_bitwise_unchanged"] is True
    assert result.summary()["energy_bitwise_unchanged"] is True

    repeated = projection.project(result.U_after)
    assert np.array_equal(repeated.U_after, result.U_after)
    assert repeated.summary()["projection_cell_count"] == 0


def test_projection_does_not_mutate_input_array():
    U = make_conserved(10.0, 0.0, 100.0, 0.10)
    reference = np.array(U, copy=True)
    projection = HEMEquilibriumQualityProjection(
        evaluator=_fixed_evaluator(0.20)
    )

    projection.project(U)

    assert np.array_equal(U, reference)


@pytest.mark.parametrize(
    ("scope_status", "phase_class", "quality_defined", "match"),
    [
        ("guarded_out", "critical_region", True, "outside supported HEM scope"),
        ("unknown", "unknown", True, "outside supported HEM scope"),
        ("supported_candidate", "liquid_vapor_two_phase", False, "undefined"),
        ("supported_candidate", "supercritical", True, "unsupported phase class"),
    ],
)
def test_guarded_or_undefined_state_fails_atomically(
    scope_status,
    phase_class,
    quality_defined,
    match,
):
    U = make_conserved(10.0, 0.0, 100.0, 0.20)
    reference = np.array(U, copy=True)
    projection = HEMEquilibriumQualityProjection(
        evaluator=_fixed_evaluator(
            0.20,
            phase_class=phase_class,
            scope_status=scope_status,
            quality_defined=quality_defined,
        )
    )

    with pytest.raises(HEMEquilibriumQualitySyncError, match=match):
        projection.project(U)

    assert projection.last_result is None
    assert np.array_equal(U, reference)


@pytest.mark.parametrize("quality", [-0.01, 1.01])
def test_out_of_bounds_transported_quality_is_rejected_without_clipping(quality):
    U = make_conserved(10.0, 0.0, 100.0, quality)
    projection = HEMEquilibriumQualityProjection(
        evaluator=_fixed_evaluator(0.50)
    )

    with pytest.raises(HEMEquilibriumQualitySyncError, match="outside"):
        projection.project(U)


@pytest.mark.parametrize(
    ("dt", "time"),
    [(-1.0, 0.0), (np.nan, 0.0), (0.0, np.nan)],
)
def test_phase_change_apply_rejects_invalid_time_inputs(dt, time):
    U = make_conserved(10.0, 0.0, 100.0, 0.20)
    projection = HEMEquilibriumQualityProjection(
        evaluator=_fixed_evaluator(0.20)
    )

    with pytest.raises(HEMEquilibriumQualitySyncError):
        projection.apply(U, eos=object(), dt=dt, t=time)


def test_projection_runs_in_existing_fvm_phase_change_slot_and_closes_budgets():
    rho = np.asarray([1.0, 1.0, 1.1, 1.1])
    e = np.asarray([100.0, 100.0, 110.0, 110.0])
    quality = _analytic_equilibrium_quality(rho, e)
    U_initial = make_conserved(rho, 0.0, e, quality)
    grid = UniformGrid(
        PipeGeometry(length_m=4.0, diameter_m=0.10),
        n_cells=4,
    )
    projection = HEMEquilibriumQualityProjection(
        evaluator=_analytic_evaluator
    )
    solver = FvmSolver(
        grid=grid,
        eos=_StrictAnalyticHEMEOS(),
        U=U_initial,
        cfl=0.10,
        phase_change=projection,
    )

    dt = solver.step()
    result = projection.last_result

    assert dt > 0.0
    assert result is not None
    assert result.summary()["projection_cell_count"] >= 1
    assert np.array_equal(
        result.U_before[..., :IDX_RHO_XV],
        result.U_after[..., :IDX_RHO_XV],
    )
    solver.primitive()

    expected_vapor_source = float(
        np.sum(result.delta_rho_q) * grid.dx * grid.geometry.area_m2
    )
    assert solver.phase_budget is not None
    assert solver.phase_budget.last_source_kg == pytest.approx(
        expected_vapor_source,
        rel=0.0,
        abs=1.0e-15,
    )
    assert solver.energy_budget is not None
    assert solver.energy_budget.last_phase_energy_delta_j == 0.0

    current_inventory = inventory(
        solver.U,
        grid.dx,
        grid.geometry.area_m2,
    )
    phase_diagnostics = solver.phase_budget.diagnostics(
        current_inventory,
        boundary_budget=solver.boundary_budget,
    )
    assert phase_diagnostics["phase_vapor_mass_balance_residual_kg"] == pytest.approx(
        0.0,
        abs=1.0e-15,
    )

    repeated = projection.project(solver.U)
    assert repeated.summary()["projection_cell_count"] == 0


@pytest.mark.coolprop_installed
def test_coolprop_projection_covers_liquid_two_phase_and_vapor_candidates():
    coolprop = pytest.importorskip("CoolProp")
    props_si = coolprop.CoolProp.PropsSI
    specifications = [
        ("PT", 8.0e6, 280.0, 0.20),
        ("PQ", 2.0e6, 0.50, 0.40),
        ("PT", 1.0e6, 280.0, 0.80),
    ]
    rho = []
    e = []
    transported_quality = []
    for pair, value_1, value_2, q_before in specifications:
        second_name = "T" if pair == "PT" else "Q"
        rho.append(
            float(props_si("Dmass", "P", value_1, second_name, value_2, "CO2"))
        )
        e.append(
            float(props_si("Umass", "P", value_1, second_name, value_2, "CO2"))
        )
        transported_quality.append(q_before)

    U = make_conserved(
        np.asarray(rho),
        0.0,
        np.asarray(e),
        np.asarray(transported_quality),
    )
    result = HEMEquilibriumQualityProjection().project(U)

    np.testing.assert_allclose(
        result.q_equilibrium,
        [0.0, 0.50, 1.0],
        rtol=0.0,
        atol=1.0e-10,
    )
    assert list(result.phase_class) == [
        "compressed_or_subcooled_liquid",
        "liquid_vapor_two_phase",
        "single_phase_vapor",
    ]
    assert result.summary()["projection_cell_count"] == 3


@pytest.mark.coolprop_installed
def test_coolprop_projection_repairs_state_before_strict_hem_eos_handoff():
    coolprop = pytest.importorskip("CoolProp")
    props_si = coolprop.CoolProp.PropsSI
    pressure = 2.0e6
    equilibrium_quality = 0.50
    rho = float(
        props_si("Dmass", "P", pressure, "Q", equilibrium_quality, "CO2")
    )
    e = float(
        props_si("Umass", "P", pressure, "Q", equilibrium_quality, "CO2")
    )
    U = make_conserved(rho, 0.0, e, 0.40)
    eos = VerificationHEMEquilibriumEOS()

    with pytest.raises(HEMUniformStatePreservationError, match="does not match"):
        eos.primitive_from_conserved(U)

    result = HEMEquilibriumQualityProjection().project(U)
    primitive = eos.primitive_from_conserved(result.U_after)

    assert float(primitive.xv) == pytest.approx(equilibrium_quality, abs=1.0e-10)
    assert result.summary()["projection_cell_count"] == 1
    assert result.summary()["energy_bitwise_unchanged"] is True
