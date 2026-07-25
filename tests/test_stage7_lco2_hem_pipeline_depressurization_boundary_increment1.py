from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from liquid_gas_transient.boundary import ConstantPressure
from liquid_gas_transient.hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedEstimate,
)
from liquid_gas_transient.hem_phase_classification import HEMPhaseState
from liquid_gas_transient.hem_pipeline_depressurization_boundary import (
    FIXED_PIPELINE_BOUNDARY_PREFLIGHT_CASES,
    HEMBoundaryPathCaseSpec,
    HEMBoundaryPathPreflightError,
    HEMPrescribedBoundaryError,
    HEMPrescribedBoundaryState,
    VerificationHEMPrescribedSubcooledOutletBoundary,
    VerificationHEMPrescribedSubcooledStateProvider,
    run_boundary_path_preflight,
    run_fixed_pipeline_boundary_preflight,
    write_pipeline_boundary_preflight_artifacts,
)
from liquid_gas_transient.state import (
    PrimitiveState,
    internal_energy,
    make_conserved,
    vapor_mass_fraction,
    velocity,
)


@dataclass
class FakePTPropertyBackend:
    backend_name: str = "fake_reversible_pt"
    saturation_calls: int = 0
    density_calls: int = 0
    energy_calls: int = 0
    pressure_bias_pa: float = 0.0
    force_negative_energy: bool = False

    @staticmethod
    def pressure_from_density(rho_kg_m3: np.ndarray | float) -> np.ndarray:
        return np.asarray(rho_kg_m3, dtype=float) * 1.0e4

    @staticmethod
    def temperature_from_energy(e_j_kg: np.ndarray | float) -> np.ndarray:
        return np.asarray(e_j_kg, dtype=float) / 1.0e3

    def saturation_temperature_K(self, pressure_pa: float) -> float:
        self.saturation_calls += 1
        return 250.0 + float(pressure_pa) / 1.0e6

    def density_kg_m3(self, pressure_pa: float, temperature_K: float) -> float:  # noqa: ARG002
        self.density_calls += 1
        return (float(pressure_pa) + self.pressure_bias_pa) / 1.0e4

    def internal_energy_j_kg(self, pressure_pa: float, temperature_K: float) -> float:  # noqa: ARG002
        self.energy_calls += 1
        if self.force_negative_energy:
            return -1.0
        return float(temperature_K) * 1.0e3


class FakeLiquidPhaseEvaluator:
    def __init__(self, *, phase_class: str = "compressed_or_subcooled_liquid", quality: float = 0.0):
        self.phase_class = phase_class
        self.quality = float(quality)
        self.calls = 0

    def __call__(self, rho, e, *, config=None):  # noqa: ANN001, ARG002
        self.calls += 1
        rho_arr, e_arr = np.broadcast_arrays(np.asarray(rho, float), np.asarray(e, float))
        shape = rho_arr.shape
        p = FakePTPropertyBackend.pressure_from_density(rho_arr)
        T = FakePTPropertyBackend.temperature_from_energy(e_arr)
        quality = np.full(shape, self.quality)
        alpha = np.full(shape, self.quality)
        return HEMPhaseState(
            backend_name="fake_phase",
            rho=np.array(rho_arr, copy=True),
            e=np.array(e_arr, copy=True),
            p=np.array(p, copy=True),
            T=np.array(T, copy=True),
            quality=quality,
            quality_defined=np.ones(shape, dtype=bool),
            alpha=alpha,
            alpha_defined=np.ones(shape, dtype=bool),
            raw_phase=np.full(shape, "liquid", dtype="<U16"),
            phase_class=np.full(shape, self.phase_class, dtype="<U40"),
            scope_status=np.full(shape, "supported_candidate", dtype="<U24"),
        )


class FakeSoundSpeedEstimator:
    def __init__(self, *, sound_speed_m_s: float = 600.0):
        self.sound_speed_m_s = float(sound_speed_m_s)
        self.calls = 0

    def __call__(self, rho_kg_m3: float, e_j_kg: float, *, config=None):  # noqa: ARG002
        self.calls += 1
        pressure = float(FakePTPropertyBackend.pressure_from_density(rho_kg_m3))
        c2 = self.sound_speed_m_s**2
        return HEMEquilibriumSoundSpeedEstimate(
            rho_kg_m3=float(rho_kg_m3),
            e_j_kg=float(e_j_kg),
            pressure_pa=pressure,
            phase_class="compressed_or_subcooled_liquid",
            dp_drho_at_e=1.0e4,
            dp_de_at_rho=0.0,
            density_term_m2_s2=c2,
            energy_term_m2_s2=0.0,
            sound_speed_squared_m2_s2=c2,
            sound_speed_m_s=self.sound_speed_m_s,
            density_step_kg_m3=1.0e-2,
            energy_step_j_kg=1.0,
            density_step_halvings=0,
            energy_step_halvings=0,
            stencil_phase_preserved=True,
        )


class FakeAcceptedStateEOS:
    def __init__(self, *, reject: bool = False):
        self.reject = bool(reject)
        self.calls = 0
        self.density_from_pressure_calls = 0

    def density_from_pressure(self, pressure_pa):  # noqa: ANN001
        self.density_from_pressure_calls += 1
        raise AssertionError("pressure-only inversion is forbidden")

    def primitive_from_conserved(self, U: np.ndarray) -> PrimitiveState:
        self.calls += 1
        if self.reject:
            raise ValueError("fake accepted-state rejection")
        array = np.asarray(U, dtype=float)
        rho = np.array(array[..., 0], copy=True)
        u = np.array(velocity(array), copy=True)
        e = np.array(internal_energy(array), copy=True)
        E = e + 0.5 * u**2
        xv = np.array(vapor_mass_fraction(array), copy=True)
        if np.any(np.abs(xv) > 1.0e-12):
            raise ValueError("fake liquid EOS requires zero quality")
        p = FakePTPropertyBackend.pressure_from_density(rho)
        T = FakePTPropertyBackend.temperature_from_energy(e)
        return PrimitiveState(
            rho=rho,
            u=u,
            p=np.asarray(p, dtype=float),
            e=e,
            E=E,
            T=np.asarray(T, dtype=float),
            xv=xv,
            alpha=np.zeros_like(rho),
            c=np.full_like(rho, 600.0),
        )


def _fake_provider(
    schedule,
    subcooling_K: float = 5.0,
    *,
    backend: FakePTPropertyBackend | None = None,
    phase_evaluator: FakeLiquidPhaseEvaluator | None = None,
    sound_estimator: FakeSoundSpeedEstimator | None = None,
    accepted_eos: FakeAcceptedStateEOS | None = None,
) -> VerificationHEMPrescribedSubcooledStateProvider:
    return VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=schedule,
        subcooling_K=subcooling_K,
        property_backend=backend or FakePTPropertyBackend(),
        phase_evaluator=phase_evaluator or FakeLiquidPhaseEvaluator(),
        sound_speed_estimator=sound_estimator or FakeSoundSpeedEstimator(),
        accepted_state_eos=accepted_eos or FakeAcceptedStateEOS(),
    )


def _fake_provider_factory(schedule, subcooling_K: float):  # noqa: ANN001
    return _fake_provider(schedule, subcooling_K)


def _provider_state(*, time_s: float = 0.0) -> HEMPrescribedBoundaryState:
    return _fake_provider(ConstantPressure(3.0e6)).state_at(time_s)


def _extended_state(*, n_internal: int = 4, n_ghost: int = 2, velocity_m_s: float = 3.0, quality: float = 0.8) -> np.ndarray:
    U_ext = np.full((n_internal + 2 * n_ghost, 4), np.nan, dtype=float)
    U_ext[n_ghost:-n_ghost] = make_conserved(
        np.linspace(430.0, 460.0, n_internal),
        velocity_m_s,
        2.45e5,
        quality,
    )
    return U_ext


def test_provider_rejects_nonpositive_subcooling_and_negative_tolerance() -> None:
    with pytest.raises(ValueError, match="subcooling_K"):
        _fake_provider(ConstantPressure(3.0e6), 0.0)
    with pytest.raises(ValueError, match="accepted_quality_tolerance"):
        VerificationHEMPrescribedSubcooledStateProvider(
            pressure_schedule=ConstantPressure(3.0e6),
            subcooling_K=5.0,
            property_backend=FakePTPropertyBackend(),
            phase_evaluator=FakeLiquidPhaseEvaluator(),
            sound_speed_estimator=FakeSoundSpeedEstimator(),
            accepted_state_eos=FakeAcceptedStateEOS(),
            accepted_quality_tolerance=-1.0,
        )


def test_provider_closes_pressure_plus_subcooling_and_accepts_exact_rho_e() -> None:
    backend = FakePTPropertyBackend()
    accepted_eos = FakeAcceptedStateEOS()
    provider = _fake_provider(
        ConstantPressure(3.0e6),
        backend=backend,
        accepted_eos=accepted_eos,
    )

    state = provider.state_at(0.25)

    assert state.time_s == pytest.approx(0.25)
    assert state.pressure_requested_pa == pytest.approx(3.0e6)
    assert state.saturation_temperature_K == pytest.approx(253.0)
    assert state.temperature_requested_K == pytest.approx(248.0)
    assert state.rho_kg_m3 == pytest.approx(300.0)
    assert state.e_j_kg == pytest.approx(248000.0)
    assert state.pressure_recovered_pa == pytest.approx(3.0e6)
    assert state.temperature_recovered_K == pytest.approx(248.0)
    assert state.equilibrium_quality == 0.0
    assert state.void_fraction == 0.0
    assert state.phase_class == "compressed_or_subcooled_liquid"
    assert state.boundary_region == "LIQUID_CANDIDATE"
    assert state.scope_status == "supported_candidate"
    assert state.sound_speed_m_s == pytest.approx(600.0)
    assert state.mixed_eos_accepted is True
    assert accepted_eos.calls == 1
    assert accepted_eos.density_from_pressure_calls == 0
    assert backend.saturation_calls == backend.density_calls == backend.energy_calls == 1


def test_provider_cache_uses_exact_pressure_subcooling_key_without_changing_time() -> None:
    backend = FakePTPropertyBackend()
    provider = _fake_provider(ConstantPressure(3.0e6), backend=backend)

    first = provider.state_at(0.0)
    second = provider.state_at(99.0)

    assert first.time_s == 0.0
    assert second.time_s == 99.0
    assert first.pressure_requested_pa == second.pressure_requested_pa
    assert first.rho_kg_m3 == second.rho_kg_m3
    assert first.e_j_kg == second.e_j_kg
    assert provider.state_provider_evaluation_count == 1
    assert provider.state_provider_cache_hit_count == 1
    assert provider.cache_size == 1
    assert backend.saturation_calls == backend.density_calls == backend.energy_calls == 1


@pytest.mark.parametrize("returned_pressure", [float("nan"), -1.0, 0.0])
def test_provider_classifies_invalid_schedule(returned_pressure: float) -> None:
    class InvalidSchedule:
        def pressure_pa(self, t: float) -> float:  # noqa: ARG002
            return returned_pressure

    provider = _fake_provider(InvalidSchedule())
    with pytest.raises(HEMPrescribedBoundaryError) as captured:
        provider.state_at(0.0)
    assert captured.value.category == "INVALID_SCHEDULE"


def test_provider_classifies_negative_energy_phase_and_round_trip_failures() -> None:
    negative_energy = _fake_provider(
        ConstantPressure(3.0e6),
        backend=FakePTPropertyBackend(force_negative_energy=True),
    )
    with pytest.raises(HEMPrescribedBoundaryError) as captured:
        negative_energy.state_at(0.0)
    assert captured.value.category == "NEGATIVE_INTERNAL_ENERGY"

    unsupported = _fake_provider(
        ConstantPressure(3.0e6),
        phase_evaluator=FakeLiquidPhaseEvaluator(
            phase_class="liquid_vapor_two_phase",
            quality=0.5,
        ),
    )
    with pytest.raises(HEMPrescribedBoundaryError) as captured:
        unsupported.state_at(0.0)
    assert captured.value.category == "UNSUPPORTED_PHASE_REGION"

    round_trip = _fake_provider(
        ConstantPressure(3.0e6),
        backend=FakePTPropertyBackend(pressure_bias_pa=1000.0),
    )
    with pytest.raises(HEMPrescribedBoundaryError) as captured:
        round_trip.state_at(0.0)
    assert captured.value.category == "ROUND_TRIP_MISMATCH"


def test_outlet_adapter_fills_all_right_ghosts_with_equilibrium_quality() -> None:
    provider = _fake_provider(ConstantPressure(3.0e6))
    adapter = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    eos = FakeAcceptedStateEOS()
    U_ext = _extended_state(velocity_m_s=3.0, quality=0.8)
    before_internal = U_ext[2:-2].copy()

    adapter.apply(U_ext, n_ghost=2, side="right", t=0.0, eos=eos)

    assert np.array_equal(U_ext[2:-2], before_internal)
    assert np.array_equal(U_ext[-2], U_ext[-1])
    assert float(U_ext[-1, 0]) == pytest.approx(300.0)
    assert float(velocity(U_ext[-1])) == pytest.approx(3.0)
    assert float(internal_energy(U_ext[-1])) == pytest.approx(248000.0)
    assert float(vapor_mass_fraction(U_ext[-1])) == 0.0
    assert float(vapor_mass_fraction(before_internal[-1])) == pytest.approx(0.8)
    assert eos.calls == 1
    assert eos.density_from_pressure_calls == 0
    assert adapter.boundary_active_count == 1
    assert adapter.reverse_flow_fallback_count == 0
    assert adapter.last_flow_policy == "prescribed_subcooled_outlet"
    assert adapter.last_state is not None


def test_outlet_adapter_reflects_reverse_flow_without_calling_provider() -> None:
    provider = _fake_provider(ConstantPressure(3.0e6))
    adapter = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    U_ext = _extended_state(velocity_m_s=-2.0, quality=0.25)
    before_internal = U_ext[2:-2].copy()

    adapter.apply(U_ext, n_ghost=2, side="right", t=0.0, eos=FakeAcceptedStateEOS())

    assert np.array_equal(U_ext[2:-2], before_internal)
    assert np.array_equal(U_ext[-2], before_internal[-1] * np.array([1.0, -1.0, 1.0, 1.0]))
    assert np.array_equal(U_ext[-1], before_internal[-2] * np.array([1.0, -1.0, 1.0, 1.0]))
    assert provider.state_provider_evaluation_count == 0
    assert adapter.boundary_active_count == 0
    assert adapter.reverse_flow_fallback_count == 1
    assert adapter.last_flow_policy == "reflective_fallback_reverse_flow"
    assert adapter.last_state is None


@pytest.mark.parametrize(
    ("side", "n_ghost", "mutation"),
    [
        ("left", 2, None),
        ("right", 0, None),
        ("right", 2, "nan_adjacent"),
        ("right", 2, "zero_density"),
    ],
)
def test_outlet_adapter_invalid_application_fails_before_mutation(
    side: str,
    n_ghost: int,
    mutation: str | None,
) -> None:
    provider = _fake_provider(ConstantPressure(3.0e6))
    adapter = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    U_ext = _extended_state()
    if mutation == "nan_adjacent":
        U_ext[-3, 2] = np.nan
    elif mutation == "zero_density":
        U_ext[-3, 0] = 0.0
    before = U_ext.copy()

    with pytest.raises(HEMPrescribedBoundaryError) as captured:
        adapter.apply(U_ext, n_ghost=n_ghost, side=side, t=0.0, eos=FakeAcceptedStateEOS())

    assert captured.value.category == "INVALID_BOUNDARY_APPLICATION"
    assert np.array_equal(U_ext, before, equal_nan=True)
    assert provider.state_provider_evaluation_count == 0


def test_outlet_adapter_eos_rejection_is_atomic() -> None:
    provider = _fake_provider(ConstantPressure(3.0e6))
    adapter = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    U_ext = _extended_state()
    before = U_ext.copy()

    with pytest.raises(HEMPrescribedBoundaryError) as captured:
        adapter.apply(
            U_ext,
            n_ghost=2,
            side="right",
            t=0.0,
            eos=FakeAcceptedStateEOS(reject=True),
        )

    assert captured.value.category == "MIXED_EOS_REJECTION"
    assert np.array_equal(U_ext, before, equal_nan=True)
    assert adapter.boundary_active_count == 0


def test_fixed_65_point_preflight_accepts_all_dependency_free_samples() -> None:
    suite = run_fixed_pipeline_boundary_preflight(
        provider_factory=_fake_provider_factory,
    )
    summary = suite.summary()

    assert [case.case.case_id for case in suite.cases] == [
        case.case_id for case in FIXED_PIPELINE_BOUNDARY_PREFLIGHT_CASES
    ]
    assert summary["case_count"] == 3
    assert summary["total_sample_count"] == 195
    assert summary["accepted_sample_count"] == 195
    assert summary["all_cases_accepted"] is True
    assert summary["pipeline_depressurization_executed"] is False
    assert summary["fvm_time_step_exercised"] is False
    assert [case.records[0].pressure_requested_pa for case in suite.cases] == [5.0e6] * 3
    assert [case.records[-1].pressure_requested_pa for case in suite.cases] == [2.0e6, 3.0e6, 4.0e6]
    for case in suite.cases:
        case_summary = case.summary()
        assert case_summary["accepted_sample_count"] == 65
        assert case_summary["liquid_candidate_count"] == 65
        assert case_summary["saturated_liquid_endpoint_count"] == 0
        assert case_summary["open_two_phase_count"] == 0
        assert case_summary["saturated_vapor_endpoint_count"] == 0
        assert case_summary["guard_or_backend_failure_count"] == 0
        assert case.provider_diagnostics["state_provider_evaluation_count"] == 65.0


def test_preflight_fails_at_first_rejected_sample_and_retains_prior_records() -> None:
    class FailingProvider:
        def __init__(self, schedule):  # noqa: ANN001
            self.schedule = schedule
            self.delegate = _fake_provider(schedule)

        def state_at(self, t: float):
            if t >= 0.5:
                raise HEMPrescribedBoundaryError(
                    "PROPERTY_BACKEND_FAILURE",
                    "intentional dependency-free failure",
                )
            return self.delegate.state_at(t)

        def diagnostics(self):
            return self.delegate.diagnostics()

    case = HEMBoundaryPathCaseSpec(
        case_id="fail_fast_probe",
        role="dependency_free_test",
        initial_pressure_pa=5.0e6,
        final_pressure_pa=2.0e6,
    )

    with pytest.raises(HEMBoundaryPathPreflightError) as captured:
        run_boundary_path_preflight(
            case,
            provider_factory=lambda schedule, subcooling: FailingProvider(schedule),
        )

    failure = captured.value
    assert failure.category == "PROPERTY_BACKEND_FAILURE"
    assert failure.case_id == "fail_fast_probe"
    assert failure.sample_index == 32
    assert failure.fraction == 0.5
    assert len(failure.accepted_records) == 32
    assert failure.accepted_records[-1].sample_index == 31


def test_preflight_artifacts_are_complete_and_preserve_approval_boundary(tmp_path: Path) -> None:
    suite = run_fixed_pipeline_boundary_preflight(
        provider_factory=_fake_provider_factory,
    )
    paths = write_pipeline_boundary_preflight_artifacts(tmp_path, suite)

    assert set(paths) == {"json", "csv", "markdown"}
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert len(payload["records"]) == 195
    assert payload["accepted_sample_count"] == 195
    assert payload["pipeline_depressurization_executed"] is False
    assert payload["fvm_time_step_exercised"] is False
    assert payload["production_hem_activation_approved"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False
    assert payload["two_phase_acoustic_accuracy_band_approved"] is False
    assert len(paths["csv"].read_text(encoding="utf-8").splitlines()) == 196
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "NO FVM TIME STEP" in markdown
    assert "physical Validation: false" in markdown


def test_increment_module_does_not_import_or_execute_fvm_solver_step() -> None:
    import liquid_gas_transient.hem_pipeline_depressurization_boundary as module

    source = inspect.getsource(module)
    assert "from .solver import" not in source
    assert "FvmSolver" not in source
    assert ".step(" not in source


def _require_coolprop():
    return pytest.importorskip("CoolProp")


@pytest.mark.coolprop_installed
@pytest.mark.parametrize("pressure_pa", [5.0e6, 4.0e6, 3.0e6, 2.0e6])
def test_installed_coolprop_provider_accepts_fixed_subcooled_states(pressure_pa: float) -> None:
    _require_coolprop()
    provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=ConstantPressure(pressure_pa),
        subcooling_K=5.0,
    )

    state = provider.state_at(0.0)

    assert np.isfinite(state.rho_kg_m3) and state.rho_kg_m3 > 0.0
    assert np.isfinite(state.e_j_kg) and state.e_j_kg >= 0.0
    assert np.isfinite(state.pressure_recovered_pa) and state.pressure_recovered_pa > 0.0
    assert np.isfinite(state.temperature_recovered_K) and state.temperature_recovered_K > 0.0
    assert np.isfinite(state.sound_speed_m_s) and state.sound_speed_m_s > 0.0
    assert state.phase_class == "compressed_or_subcooled_liquid"
    assert state.boundary_region == "LIQUID_CANDIDATE"
    assert state.equilibrium_quality == pytest.approx(0.0, abs=1.0e-10)
    assert state.void_fraction == pytest.approx(0.0, abs=1.0e-10)
    assert state.pressure_recovered_pa == pytest.approx(pressure_pa, rel=1.0e-6, abs=1.0)
    assert state.temperature_recovered_K == pytest.approx(
        state.temperature_requested_K,
        rel=1.0e-8,
        abs=1.0e-6,
    )
    assert state.mixed_eos_accepted is True


@pytest.mark.coolprop_installed
def test_installed_coolprop_adapter_builds_strictly_accepted_ghost_without_fvm_step() -> None:
    _require_coolprop()
    provider = VerificationHEMPrescribedSubcooledStateProvider(
        pressure_schedule=ConstantPressure(3.0e6),
        subcooling_K=5.0,
    )
    adapter = VerificationHEMPrescribedSubcooledOutletBoundary(provider)
    U_ext = np.full((8, 4), np.nan, dtype=float)
    U_ext[2:-2] = make_conserved(900.0, 2.0, 2.0e5, 0.7)
    before_internal = U_ext[2:-2].copy()

    assert provider.accepted_state_eos is not None
    adapter.apply(
        U_ext,
        n_ghost=2,
        side="right",
        t=0.0,
        eos=provider.accepted_state_eos,
    )

    assert np.array_equal(U_ext[2:-2], before_internal)
    assert np.array_equal(U_ext[-2], U_ext[-1])
    assert float(velocity(U_ext[-1])) == pytest.approx(2.0)
    assert float(vapor_mass_fraction(U_ext[-1])) == pytest.approx(0.0, abs=1.0e-10)
    provider.accepted_state_eos.primitive_from_conserved(U_ext[-2:])


@pytest.mark.coolprop_installed
def test_installed_coolprop_fixed_65_point_boundary_preflight() -> None:
    _require_coolprop()
    suite = run_fixed_pipeline_boundary_preflight()
    summary = suite.summary()

    assert summary["total_sample_count"] == 195
    assert summary["accepted_sample_count"] == 195
    assert summary["all_cases_accepted"] is True
    for case in suite.cases:
        case_summary = case.summary()
        assert case_summary["accepted_sample_count"] == 65
        assert case_summary["liquid_candidate_count"] == 65
        assert case_summary["saturated_liquid_endpoint_count"] == 0
        assert case_summary["open_two_phase_count"] == 0
        assert case_summary["saturated_vapor_endpoint_count"] == 0
        assert case_summary["guard_or_backend_failure_count"] == 0
