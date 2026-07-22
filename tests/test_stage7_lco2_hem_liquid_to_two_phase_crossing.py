from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.hem_liquid_to_two_phase_crossing import (
    HEMLiquidToTwoPhaseCrossingError,
    classify_transition_events,
    derive_boundary_regions,
    detect_raw_transition_events,
    evaluate_boundary_regions_from_conserved,
)
from liquid_gas_transient.hem_phase_classification import (
    HEMPhaseClassificationConfig,
    HEMPhaseState,
)
from liquid_gas_transient.state import make_conserved


def _phase_state(
    quality,
    phase_class,
    *,
    scope_status: str = "supported_candidate",
    quality_defined: bool = True,
    rho=None,
    e=None,
) -> HEMPhaseState:
    quality_array = np.asarray(quality, dtype=float)
    shape = quality_array.shape
    rho_array = np.ones(shape) if rho is None else np.asarray(rho, dtype=float)
    e_array = np.full(shape, 100.0) if e is None else np.asarray(e, dtype=float)
    phase_array = np.broadcast_to(
        np.asarray(phase_class, dtype="<U40"), shape
    ).copy()
    raw_phase = np.where(
        phase_array == "liquid_vapor_two_phase",
        "twophase",
        np.where(phase_array == "single_phase_vapor", "gas", "liquid"),
    )
    return HEMPhaseState(
        backend_name="fake",
        rho=np.array(rho_array, copy=True),
        e=np.array(e_array, copy=True),
        p=np.full(shape, 1.0e6),
        T=np.full(shape, 280.0),
        quality=np.array(quality_array, copy=True),
        quality_defined=np.full(shape, quality_defined, dtype=bool),
        alpha=np.array(quality_array, copy=True),
        alpha_defined=np.full(shape, quality_defined, dtype=bool),
        raw_phase=np.asarray(raw_phase),
        phase_class=phase_array,
        scope_status=np.full(shape, scope_status, dtype="<U24"),
        sound_speed_evaluated=False,
    )


def test_mapping_distinguishes_liquid_and_saturated_liquid_at_quality_zero():
    state = _phase_state(
        [0.0, 0.0],
        ["compressed_or_subcooled_liquid", "liquid_vapor_two_phase"],
    )
    assert derive_boundary_regions(state).tolist() == [
        "LIQUID_CANDIDATE",
        "SATURATED_LIQUID_ENDPOINT",
    ]


def test_mapping_uses_configured_endpoint_intervals_without_clipping():
    config = HEMPhaseClassificationConfig(endpoint_tolerance=1.0e-3)
    state = _phase_state(
        [0.0, 1.0e-3, 1.0001e-3, 0.5, 0.9989999, 0.999, 1.0],
        ["liquid_vapor_two_phase"] * 7,
    )
    assert derive_boundary_regions(state, config=config).tolist() == [
        "SATURATED_LIQUID_ENDPOINT",
        "SATURATED_LIQUID_ENDPOINT",
        "OPEN_TWO_PHASE",
        "OPEN_TWO_PHASE",
        "OPEN_TWO_PHASE",
        "SATURATED_VAPOR_ENDPOINT",
        "SATURATED_VAPOR_ENDPOINT",
    ]


@pytest.mark.parametrize("quality", [np.nan, np.inf, -1.0e-8, 1.0000001])
def test_nonfinite_or_out_of_range_equilibrium_quality_fails(quality):
    with pytest.raises(HEMLiquidToTwoPhaseCrossingError):
        derive_boundary_regions(
            _phase_state([quality], ["liquid_vapor_two_phase"])
        )


@pytest.mark.parametrize(
    ("scope_status", "quality_defined", "match"),
    [
        ("guarded_out", True, "guarded"),
        ("unknown", True, "unknown"),
        ("supported_candidate", False, "undefined"),
    ],
)
def test_guarded_unknown_or_undefined_state_fails(
    scope_status, quality_defined, match
):
    state = _phase_state(
        [0.0],
        ["liquid_vapor_two_phase"],
        scope_status=scope_status,
        quality_defined=quality_defined,
    )
    with pytest.raises(HEMLiquidToTwoPhaseCrossingError, match=match):
        derive_boundary_regions(state)


@pytest.mark.parametrize(
    ("quality", "phase_class"),
    [
        (0.1, "compressed_or_subcooled_liquid"),
        (0.9, "single_phase_vapor"),
    ],
)
def test_inconsistent_single_phase_quality_fails(quality, phase_class):
    with pytest.raises(HEMLiquidToTwoPhaseCrossingError, match="inconsistent"):
        derive_boundary_regions(_phase_state([quality], [phase_class]))


@pytest.mark.parametrize("endpoint_tolerance", [0.5, 1.0])
def test_crossing_mapper_rejects_endpoint_tolerance_without_open_interval(
    endpoint_tolerance,
):
    config = HEMPhaseClassificationConfig(
        endpoint_tolerance=endpoint_tolerance
    )
    with pytest.raises(HEMLiquidToTwoPhaseCrossingError):
        derive_boundary_regions(
            _phase_state([0.0], ["compressed_or_subcooled_liquid"]),
            config=config,
        )


@pytest.mark.parametrize(
    ("previous", "raw", "expected"),
    [
        ("LIQUID_CANDIDATE", "LIQUID_CANDIDATE", "NO_TRANSITION"),
        (
            "LIQUID_CANDIDATE",
            "SATURATED_LIQUID_ENDPOINT",
            "BOUNDARY_TOUCH",
        ),
        (
            "LIQUID_CANDIDATE",
            "OPEN_TWO_PHASE",
            "LIQUID_TO_TWO_PHASE_CROSSING",
        ),
        (
            "SATURATED_LIQUID_ENDPOINT",
            "OPEN_TWO_PHASE",
            "LIQUID_TO_TWO_PHASE_CROSSING",
        ),
        (
            "SATURATED_LIQUID_ENDPOINT",
            "LIQUID_CANDIDATE",
            "REVERSE_TRANSITION",
        ),
        ("OPEN_TWO_PHASE", "LIQUID_CANDIDATE", "REVERSE_TRANSITION"),
        (
            "OPEN_TWO_PHASE",
            "SATURATED_LIQUID_ENDPOINT",
            "REVERSE_TRANSITION",
        ),
        ("OPEN_TWO_PHASE", "OPEN_TWO_PHASE", "NO_TRANSITION"),
        (
            "LIQUID_CANDIDATE",
            "SATURATED_VAPOR_ENDPOINT",
            "FORBIDDEN_TRANSITION",
        ),
        (
            "LIQUID_CANDIDATE",
            "VAPOR_CANDIDATE",
            "FORBIDDEN_TRANSITION",
        ),
    ],
)
def test_transition_table(previous, raw, expected):
    result = classify_transition_events(
        np.asarray([previous]), np.asarray([raw])
    )
    assert result.event.tolist() == [expected]


def test_transition_summary_counts_each_event_class():
    result = classify_transition_events(
        np.asarray(
            [
                "LIQUID_CANDIDATE",
                "LIQUID_CANDIDATE",
                "SATURATED_LIQUID_ENDPOINT",
                "OPEN_TWO_PHASE",
                "OPEN_TWO_PHASE",
                "LIQUID_CANDIDATE",
            ]
        ),
        np.asarray(
            [
                "LIQUID_CANDIDATE",
                "SATURATED_LIQUID_ENDPOINT",
                "OPEN_TWO_PHASE",
                "LIQUID_CANDIDATE",
                "OPEN_TWO_PHASE",
                "VAPOR_CANDIDATE",
            ]
        ),
    )
    assert result.summary() == {
        "cell_count": 6,
        "no_transition_count": 2,
        "boundary_touch_count": 1,
        "liquid_to_two_phase_crossing_count": 1,
        "reverse_transition_count": 1,
        "forbidden_transition_count": 1,
    }


def test_transition_classifier_rejects_unknown_regions_and_shape_mismatch():
    with pytest.raises(HEMLiquidToTwoPhaseCrossingError, match="unknown"):
        classify_transition_events(
            np.asarray(["LIQUID_CANDIDATE"]), np.asarray(["BOGUS"])
        )
    with pytest.raises(
        HEMLiquidToTwoPhaseCrossingError, match="matching shapes"
    ):
        classify_transition_events(
            np.asarray(["LIQUID_CANDIDATE"]),
            np.asarray(["LIQUID_CANDIDATE", "OPEN_TWO_PHASE"]),
        )


class _AnalyticDirectPhaseEvaluator:
    def __init__(self):
        self.calls = []

    def __call__(self, rho, e, *, config=None):
        rho_array = np.asarray(rho, dtype=float)
        e_array = np.asarray(e, dtype=float)
        self.calls.append((rho_array.copy(), e_array.copy(), config))
        phase_class = np.where(
            e_array < 105.0,
            "compressed_or_subcooled_liquid",
            "liquid_vapor_two_phase",
        )
        quality = np.where(e_array < 105.0, 0.0, 0.2)
        return _phase_state(
            quality, phase_class, rho=rho_array, e=e_array
        )


def test_raw_detection_uses_rho_e_and_is_independent_of_transported_quality():
    evaluator = _AnalyticDirectPhaseEvaluator()
    previous = make_conserved(
        [10.0, 10.0], 0.0, [100.0, 100.0], [0.0, 0.0]
    )
    raw_zero_quality = make_conserved(
        [10.0, 10.0], 0.0, [110.0, 100.0], [0.0, 0.0]
    )
    raw_different_quality = make_conserved(
        [10.0, 10.0], 0.0, [110.0, 100.0], [0.9, 0.4]
    )

    zero_result = detect_raw_transition_events(
        previous, raw_zero_quality, evaluator=evaluator
    )
    different_result = detect_raw_transition_events(
        previous, raw_different_quality, evaluator=evaluator
    )

    assert zero_result.transitions.event.tolist() == [
        "LIQUID_TO_TWO_PHASE_CROSSING",
        "NO_TRANSITION",
    ]
    assert np.array_equal(
        zero_result.raw.region, different_result.raw.region
    )
    assert np.array_equal(
        zero_result.transitions.event, different_result.transitions.event
    )
    assert len(evaluator.calls) == 4


def test_instantiated_phase_config_is_forwarded_to_direct_evaluator():
    config = HEMPhaseClassificationConfig(endpoint_tolerance=1.0e-7)
    evaluator = _AnalyticDirectPhaseEvaluator()
    result = evaluate_boundary_regions_from_conserved(
        make_conserved(10.0, 0.0, 100.0, 0.0),
        evaluator=evaluator,
        phase_config=config,
    )
    assert evaluator.calls[0][2] is config
    assert result.endpoint_tolerance == config.endpoint_tolerance


def test_direct_evaluator_receives_copies_and_must_preserve_rho_e_contract():
    U = make_conserved([10.0], 0.0, [100.0], [0.3])
    reference = U.copy()

    class _MutatingEvaluator:
        def __call__(self, rho, e, *, config=None):
            del config
            rho[:] = 1.0
            e[:] = 100.0
            return _phase_state(
                [0.0],
                ["compressed_or_subcooled_liquid"],
                rho=rho,
                e=e,
            )

    with pytest.raises(HEMLiquidToTwoPhaseCrossingError, match="preserve"):
        evaluate_boundary_regions_from_conserved(
            U, evaluator=_MutatingEvaluator()
        )
    assert np.array_equal(U, reference)


def test_direct_backend_failure_is_wrapped_atomically():
    class _BrokenEvaluator:
        def __call__(self, rho, e, *, config=None):
            del rho, e, config
            raise ValueError("backend failed")

    with pytest.raises(
        HEMLiquidToTwoPhaseCrossingError, match="direct rho/e"
    ):
        evaluate_boundary_regions_from_conserved(
            make_conserved(10.0, 0.0, 100.0, 0.0),
            evaluator=_BrokenEvaluator(),
        )


def test_direct_detection_retains_current_nonnegative_internal_energy_guard():
    with pytest.raises(
        HEMLiquidToTwoPhaseCrossingError, match="non-negative"
    ):
        evaluate_boundary_regions_from_conserved(
            make_conserved(10.0, 0.0, -1.0, 0.0),
            evaluator=_AnalyticDirectPhaseEvaluator(),
        )


def test_previous_and_raw_conservative_cell_shapes_must_match():
    previous = make_conserved([10.0], 0.0, [100.0], [0.0])
    raw = make_conserved(
        [10.0, 10.0], 0.0, [100.0, 110.0], [0.0, 0.0]
    )
    with pytest.raises(
        HEMLiquidToTwoPhaseCrossingError, match="matching cell shapes"
    ):
        detect_raw_transition_events(
            previous, raw, evaluator=_AnalyticDirectPhaseEvaluator()
        )


@pytest.mark.coolprop_installed
def test_installed_coolprop_endpoints_map_from_canonical_rho_e():
    coolprop = pytest.importorskip("CoolProp")
    props_si = coolprop.CoolProp.PropsSI
    pressure_pa = 2.0e6
    rho, e, transported_quality = [], [], []
    for quality in (0.0, 1.0):
        rho.append(
            float(
                props_si(
                    "Dmass", "P", pressure_pa, "Q", quality, "CO2"
                )
            )
        )
        e.append(
            float(
                props_si(
                    "Umass", "P", pressure_pa, "Q", quality, "CO2"
                )
            )
        )
        transported_quality.append(quality)

    result = evaluate_boundary_regions_from_conserved(
        make_conserved(
            np.asarray(rho),
            0.0,
            np.asarray(e),
            np.asarray(transported_quality),
        )
    )
    assert result.region.tolist() == [
        "SATURATED_LIQUID_ENDPOINT",
        "SATURATED_VAPOR_ENDPOINT",
    ]
    assert result.phase_state.phase_class.tolist() == [
        "liquid_vapor_two_phase",
        "liquid_vapor_two_phase",
    ]
