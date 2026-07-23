from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.hem_equilibrium_quality_sync import (
    HEMEquilibriumQualitySyncConfig,
)
from liquid_gas_transient.hem_equilibrium_sound_speed import (
    HEMEquilibriumSoundSpeedEstimate,
)
from liquid_gas_transient.hem_mixed_liquid_open_two_phase_eos import (
    HEMMixedAcceptedStateEOSError,
    VerificationHEMLiquidOpenTwoPhaseEOS,
)
from liquid_gas_transient.hem_phase_classification import (
    HEMPhaseClassificationConfig,
    HEMPhaseState,
)
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.state import make_conserved


def _phase_state(
    rho,
    e,
    *,
    phase_class,
    quality,
    alpha,
    scope_status="supported_candidate",
    quality_defined=True,
    alpha_defined=True,
):
    rho_arr = np.asarray(rho, dtype=float)
    e_arr = np.asarray(e, dtype=float)
    phase_arr = np.broadcast_to(
        np.asarray(phase_class, dtype="<U40"),
        rho_arr.shape,
    ).copy()
    quality_arr = np.broadcast_to(
        np.asarray(quality, dtype=float),
        rho_arr.shape,
    ).copy()
    alpha_arr = np.broadcast_to(
        np.asarray(alpha, dtype=float),
        rho_arr.shape,
    ).copy()
    raw_phase = np.where(
        phase_arr == "liquid_vapor_two_phase",
        "twophase",
        np.where(
            phase_arr == "single_phase_vapor",
            "gas",
            "liquid",
        ),
    )
    p = np.where(
        phase_arr == "compressed_or_subcooled_liquid",
        5.0e6,
        2.0e6,
    )
    T = np.where(
        phase_arr == "compressed_or_subcooled_liquid",
        280.0,
        255.0,
    )
    return HEMPhaseState(
        backend_name="fake",
        rho=np.array(rho_arr, copy=True),
        e=np.array(e_arr, copy=True),
        p=np.asarray(p, dtype=float),
        T=np.asarray(T, dtype=float),
        quality=quality_arr,
        quality_defined=np.full(
            rho_arr.shape,
            quality_defined,
            dtype=bool,
        ),
        alpha=alpha_arr,
        alpha_defined=np.full(
            rho_arr.shape,
            alpha_defined,
            dtype=bool,
        ),
        raw_phase=np.asarray(raw_phase),
        phase_class=phase_arr,
        scope_status=np.full(
            rho_arr.shape,
            scope_status,
            dtype="<U24",
        ),
        sound_speed_evaluated=False,
    )


class _RecordingMixedPhaseEvaluator:
    def __init__(self):
        self.calls = []

    def __call__(self, rho, e, *, config=None):
        rho_arr = np.asarray(rho, dtype=float)
        e_arr = np.asarray(e, dtype=float)
        self.calls.append(
            (
                np.array(rho_arr, copy=True),
                np.array(e_arr, copy=True),
                config,
            )
        )
        liquid = e_arr < 200.0
        phase_class = np.where(
            liquid,
            "compressed_or_subcooled_liquid",
            "liquid_vapor_two_phase",
        )
        quality = np.where(liquid, 0.0, 0.25)
        alpha = np.where(liquid, 0.0, 0.80)
        return _phase_state(
            rho_arr,
            e_arr,
            phase_class=phase_class,
            quality=quality,
            alpha=alpha,
        )


def _sound_estimate(
    rho,
    e,
    *,
    phase_class,
    sound_speed,
):
    c = float(sound_speed)
    return HEMEquilibriumSoundSpeedEstimate(
        rho_kg_m3=float(rho),
        e_j_kg=float(e),
        pressure_pa=5.0e6
        if phase_class == "compressed_or_subcooled_liquid"
        else 2.0e6,
        phase_class=phase_class,
        dp_drho_at_e=c * c,
        dp_de_at_rho=0.0,
        density_term_m2_s2=c * c,
        energy_term_m2_s2=0.0,
        sound_speed_squared_m2_s2=c * c,
        sound_speed_m_s=c,
        density_step_kg_m3=1.0e-3,
        energy_step_j_kg=1.0e-2,
        density_step_halvings=0,
        energy_step_halvings=0,
        stencil_phase_preserved=True,
    )


class _RecordingSoundSpeedEstimator:
    def __init__(self):
        self.calls = []

    def __call__(self, rho, e, *, config=None):
        self.calls.append((float(rho), float(e), config))
        if float(e) < 200.0:
            return _sound_estimate(
                rho,
                e,
                phase_class="compressed_or_subcooled_liquid",
                sound_speed=700.0,
            )
        return _sound_estimate(
            rho,
            e,
            phase_class="liquid_vapor_two_phase",
            sound_speed=120.0,
        )


def _fake_eos():
    phase = _RecordingMixedPhaseEvaluator()
    sound = _RecordingSoundSpeedEstimator()
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=phase,
        sound_speed_estimator=sound,
    )
    return eos, phase, sound


@pytest.mark.parametrize("quality_tolerance", [-1.0, np.nan])
def test_config_rejects_invalid_quality_tolerance(quality_tolerance):
    with pytest.raises(ValueError, match="quality_tolerance"):
        VerificationHEMLiquidOpenTwoPhaseEOS(
            quality_tolerance=quality_tolerance
        )


def test_config_rejects_quality_tolerance_tighter_than_projection():
    with pytest.raises(ValueError, match="projection activation"):
        VerificationHEMLiquidOpenTwoPhaseEOS(
            quality_tolerance=1.0e-13,
            quality_sync_config=HEMEquilibriumQualitySyncConfig(
                activation_tolerance=1.0e-12
            ),
        )


@pytest.mark.parametrize("endpoint_tolerance", [-1.0, np.nan, 0.5, 1.0])
def test_config_rejects_invalid_endpoint_tolerance(endpoint_tolerance):
    with pytest.raises(ValueError):
        VerificationHEMLiquidOpenTwoPhaseEOS(
            phase_config=HEMPhaseClassificationConfig(
                endpoint_tolerance=endpoint_tolerance
            )
        )


def test_mixed_liquid_open_two_phase_array_recovers_primitives():
    eos, phase, sound = _fake_eos()
    U = make_conserved(
        [800.0, 100.0],
        [0.0, 2.0],
        [100.0, 300.0],
        [0.0, 0.25],
    )

    prim = eos.primitive_from_conserved(U)

    np.testing.assert_allclose(prim.p, [5.0e6, 2.0e6])
    np.testing.assert_allclose(prim.T, [280.0, 255.0])
    np.testing.assert_allclose(prim.xv, [0.0, 0.25])
    np.testing.assert_allclose(prim.alpha, [0.0, 0.80])
    np.testing.assert_allclose(prim.c, [700.0, 120.0])
    np.testing.assert_allclose(prim.u, [0.0, 2.0])
    assert eos.last_regions.tolist() == [
        "LIQUID_CANDIDATE",
        "OPEN_TWO_PHASE",
    ]
    assert eos.cache_size == 2
    assert eos.phase_evaluation_count == 2
    assert eos.sound_speed_evaluation_count == 2
    assert eos.liquid_state_evaluation_count == 1
    assert eos.open_two_phase_state_evaluation_count == 1
    assert phase.calls[0][2] is eos.phase_config
    assert sound.calls[0][2] is eos.sound_speed_config


def test_repeated_identical_cells_use_exact_rho_e_cache():
    eos, phase, sound = _fake_eos()
    U = make_conserved(
        [800.0, 800.0, 100.0, 100.0],
        0.0,
        [100.0, 100.0, 300.0, 300.0],
        [0.0, 0.0, 0.25, 0.25],
    )

    eos.primitive_from_conserved(U)
    eos.primitive_from_conserved(U)

    assert eos.cache_size == 2
    assert eos.phase_evaluation_count == 2
    assert eos.sound_speed_evaluation_count == 2
    assert len(phase.calls) == 2
    assert len(sound.calls) == 2


def test_quality_mismatch_within_accepted_tolerance_is_allowed():
    eos, _, _ = _fake_eos()
    U = make_conserved(800.0, 0.0, 100.0, 5.0e-11)

    prim = eos.primitive_from_conserved(U)

    assert float(np.asarray(prim.xv)) == 0.0
    assert str(eos.last_regions) == "LIQUID_CANDIDATE"


@pytest.mark.parametrize(
    ("equilibrium_e", "transported_quality"),
    [
        (100.0, 1.0e-4),
        (300.0, 0.20),
    ],
)
def test_strict_accepted_state_rejects_quality_mismatch(
    equilibrium_e,
    transported_quality,
):
    eos, _, _ = _fake_eos()
    U = make_conserved(
        100.0,
        0.0,
        equilibrium_e,
        transported_quality,
    )

    with pytest.raises(HEMMixedAcceptedStateEOSError, match="does not match"):
        eos.primitive_from_conserved(U)
    assert eos.last_regions is None


@pytest.mark.parametrize("transported_quality", [-1.0e-14, 1.0 + 1.0e-14])
def test_transported_quality_bounds_are_strict(transported_quality):
    eos, _, _ = _fake_eos()
    U = make_conserved(100.0, 0.0, 100.0, transported_quality)

    with pytest.raises(HEMMixedAcceptedStateEOSError, match=r"outside \[0, 1\]"):
        eos.primitive_from_conserved(U)


@pytest.mark.parametrize(
    ("quality", "expected_message"),
    [
        (0.0, "endpoint_acoustic_closure_not_established"),
        (1.0, "saturated-vapor endpoint"),
    ],
)
def test_saturation_endpoints_fail_before_acoustic_evaluation(
    quality,
    expected_message,
):
    class _EndpointEvaluator:
        def __call__(self, rho, e, *, config=None):
            del config
            return _phase_state(
                rho,
                e,
                phase_class="liquid_vapor_two_phase",
                quality=quality,
                alpha=quality,
            )

    sound = _RecordingSoundSpeedEstimator()
    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_EndpointEvaluator(),
        sound_speed_estimator=sound,
    )

    with pytest.raises(HEMMixedAcceptedStateEOSError, match=expected_message):
        eos.primitive_from_conserved(
            make_conserved(100.0, 0.0, 300.0, quality)
        )
    assert sound.calls == []


def test_single_phase_vapor_is_rejected():
    class _VaporEvaluator:
        def __call__(self, rho, e, *, config=None):
            del config
            return _phase_state(
                rho,
                e,
                phase_class="single_phase_vapor",
                quality=1.0,
                alpha=1.0,
            )

    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_VaporEvaluator(),
        sound_speed_estimator=_RecordingSoundSpeedEstimator(),
    )
    with pytest.raises(HEMMixedAcceptedStateEOSError, match="vapor"):
        eos.primitive_from_conserved(
            make_conserved(10.0, 0.0, 300.0, 1.0)
        )


@pytest.mark.parametrize(
    ("scope_status", "quality_defined", "alpha_defined"),
    [
        ("guarded_out", True, True),
        ("unknown", True, True),
        ("supported_candidate", False, True),
        ("supported_candidate", True, False),
    ],
)
def test_guarded_undefined_or_incomplete_state_fails(
    scope_status,
    quality_defined,
    alpha_defined,
):
    class _InvalidEvaluator:
        def __call__(self, rho, e, *, config=None):
            del config
            return _phase_state(
                rho,
                e,
                phase_class="compressed_or_subcooled_liquid",
                quality=0.0,
                alpha=0.0,
                scope_status=scope_status,
                quality_defined=quality_defined,
                alpha_defined=alpha_defined,
            )

    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_InvalidEvaluator(),
        sound_speed_estimator=_RecordingSoundSpeedEstimator(),
    )
    with pytest.raises(HEMMixedAcceptedStateEOSError):
        eos.primitive_from_conserved(
            make_conserved(800.0, 0.0, 100.0, 0.0)
        )


@pytest.mark.parametrize("sound_speed", [0.0, -1.0, np.nan, np.inf])
def test_nonpositive_or_nonfinite_acoustic_result_fails(sound_speed):
    class _BadSoundEstimator:
        def __call__(self, rho, e, *, config=None):
            del config
            return _sound_estimate(
                rho,
                e,
                phase_class="compressed_or_subcooled_liquid",
                sound_speed=sound_speed,
            )

    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_RecordingMixedPhaseEvaluator(),
        sound_speed_estimator=_BadSoundEstimator(),
    )
    with pytest.raises(HEMMixedAcceptedStateEOSError):
        eos.primitive_from_conserved(
            make_conserved(800.0, 0.0, 100.0, 0.0)
        )


def test_phase_backend_failure_is_wrapped():
    class _BrokenPhaseEvaluator:
        def __call__(self, rho, e, *, config=None):
            del rho, e, config
            raise ValueError("phase backend failed")

    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_BrokenPhaseEvaluator(),
        sound_speed_estimator=_RecordingSoundSpeedEstimator(),
    )
    with pytest.raises(
        HEMMixedAcceptedStateEOSError,
        match="phase evaluation failed",
    ):
        eos.primitive_from_conserved(
            make_conserved(800.0, 0.0, 100.0, 0.0)
        )


def test_sound_speed_backend_failure_is_wrapped():
    class _BrokenSoundEstimator:
        def __call__(self, rho, e, *, config=None):
            del rho, e, config
            raise ValueError("acoustic backend failed")

    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_RecordingMixedPhaseEvaluator(),
        sound_speed_estimator=_BrokenSoundEstimator(),
    )
    with pytest.raises(
        HEMMixedAcceptedStateEOSError,
        match="sound-speed evaluation failed",
    ):
        eos.primitive_from_conserved(
            make_conserved(800.0, 0.0, 100.0, 0.0)
        )


def test_phase_and_acoustic_center_phase_must_agree():
    class _WrongPhaseSoundEstimator:
        def __call__(self, rho, e, *, config=None):
            del config
            return _sound_estimate(
                rho,
                e,
                phase_class="liquid_vapor_two_phase",
                sound_speed=120.0,
            )

    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_RecordingMixedPhaseEvaluator(),
        sound_speed_estimator=_WrongPhaseSoundEstimator(),
    )
    with pytest.raises(HEMMixedAcceptedStateEOSError, match="disagree"):
        eos.primitive_from_conserved(
            make_conserved(800.0, 0.0, 100.0, 0.0)
        )


def test_input_is_immutable_and_evaluator_must_preserve_rho_e():
    U = make_conserved([800.0], [0.0], [100.0], [0.0])
    reference = np.array(U, copy=True)

    class _MutatingEvaluator:
        def __call__(self, rho, e, *, config=None):
            del config
            rho[:] = 1.0
            e[:] = 1.0
            return _phase_state(
                rho,
                e,
                phase_class="compressed_or_subcooled_liquid",
                quality=0.0,
                alpha=0.0,
            )

    eos = VerificationHEMLiquidOpenTwoPhaseEOS(
        phase_evaluator=_MutatingEvaluator(),
        sound_speed_estimator=_RecordingSoundSpeedEstimator(),
    )
    with pytest.raises(HEMMixedAcceptedStateEOSError, match="preserve"):
        eos.primitive_from_conserved(U)
    assert np.array_equal(U, reference)


@pytest.mark.parametrize(
    ("U", "match"),
    [
        (np.zeros((2, 3)), "N_VARS"),
        (np.asarray([[np.nan, 0.0, 1.0, 0.0]]), "NaN"),
        (make_conserved(0.0, 0.0, 100.0, 0.0), "density"),
        (make_conserved(10.0, 0.0, -1.0, 0.0), "non-negative"),
    ],
)
def test_invalid_conservative_state_fails(U, match):
    eos, _, _ = _fake_eos()
    with pytest.raises(HEMMixedAcceptedStateEOSError, match=match):
        eos.primitive_from_conserved(U)


def test_density_from_pressure_is_intentionally_unavailable():
    eos, _, _ = _fake_eos()
    with pytest.raises(NotImplementedError, match="transmissive"):
        eos.density_from_pressure(2.0e6)


def test_structural_solver_compatibility_for_mixed_accepted_array():
    eos, _, _ = _fake_eos()
    U = make_conserved(
        [800.0, 100.0],
        0.0,
        [100.0, 300.0],
        [0.0, 0.25],
    )
    solver = FvmSolver(
        grid=UniformGrid(
            PipeGeometry(length_m=2.0, diameter_m=0.10),
            n_cells=2,
        ),
        eos=eos,
        U=U,
        cfl=0.10,
        enable_boundary_budget=False,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
    )

    prim = solver.primitive()
    dt = solver.compute_dt()

    assert prim.c.tolist() == [700.0, 120.0]
    assert np.isfinite(dt) and dt > 0.0
    assert solver.step_count == 0


@pytest.mark.coolprop_installed
def test_installed_coolprop_handles_one_liquid_and_one_open_two_phase_cell():
    coolprop = pytest.importorskip("CoolProp")
    props_si = coolprop.CoolProp.PropsSI

    rho_liquid = float(props_si("Dmass", "P", 5.0e6, "T", 280.0, "CO2"))
    e_liquid = float(props_si("Umass", "P", 5.0e6, "T", 280.0, "CO2"))
    rho_two_phase = float(props_si("Dmass", "P", 2.0e6, "Q", 0.50, "CO2"))
    e_two_phase = float(props_si("Umass", "P", 2.0e6, "Q", 0.50, "CO2"))

    U = make_conserved(
        [rho_liquid, rho_two_phase],
        [0.0, 0.0],
        [e_liquid, e_two_phase],
        [0.0, 0.50],
    )
    eos = VerificationHEMLiquidOpenTwoPhaseEOS()
    prim = eos.primitive_from_conserved(U)

    assert eos.last_regions.tolist() == [
        "LIQUID_CANDIDATE",
        "OPEN_TWO_PHASE",
    ]
    np.testing.assert_allclose(prim.p, [5.0e6, 2.0e6], rtol=1.0e-9)
    np.testing.assert_allclose(prim.xv, [0.0, 0.50], atol=1.0e-10)
    assert np.all(np.isfinite(prim.c))
    assert np.all(prim.c > 0.0)
    assert eos.phase_evaluation_count == 2
    assert eos.sound_speed_evaluation_count == 2
    assert eos.liquid_state_evaluation_count == 1
    assert eos.open_two_phase_state_evaluation_count == 1


@pytest.mark.coolprop_installed
def test_installed_coolprop_saturated_liquid_endpoint_is_rejected():
    coolprop = pytest.importorskip("CoolProp")
    props_si = coolprop.CoolProp.PropsSI

    rho = float(props_si("Dmass", "P", 2.0e6, "Q", 0.0, "CO2"))
    e = float(props_si("Umass", "P", 2.0e6, "Q", 0.0, "CO2"))
    U = make_conserved(rho, 0.0, e, 0.0)

    with pytest.raises(
        HEMMixedAcceptedStateEOSError,
        match="endpoint_acoustic_closure_not_established",
    ):
        VerificationHEMLiquidOpenTwoPhaseEOS().primitive_from_conserved(U)
