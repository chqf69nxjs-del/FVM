from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.hem_liquid_to_two_phase_state_pair_survey import (
    HEMLiquidStatePairSurveyConfig,
    LiquidCandidateSpec,
    LiquidStatePairSpec,
    default_liquid_candidate_specs,
    default_liquid_pair_specs,
    run_liquid_state_pair_survey,
    write_liquid_state_pair_survey_artifacts,
)
from liquid_gas_transient.hem_phase_classification import HEMPhaseState


def _small_config(*, fractions=(0.0, 0.5, 1.0)):
    return HEMLiquidStatePairSurveyConfig(
        candidate_specs=(
            LiquidCandidateSpec("left", 5.0e6, 5.0),
            LiquidCandidateSpec("right", 2.0e6, 5.0),
        ),
        pair_specs=(
            LiquidStatePairSpec(
                "pair",
                "left",
                "right",
                "baseline",
                "dependency-free screening pair",
            ),
        ),
        blend_fractions=fractions,
    )


def _fake_props_si(output, *args):
    if output == "Tcrit":
        return 304.1282
    if output == "Pcrit":
        return 7.3773e6
    if output == "Ttriple":
        return 216.592
    if output == "T":
        pressure = float(args[1])
        return 250.0 + (pressure - 2.0e6) / 3.0e6 * 30.0
    if output == "Dmass":
        pressure = float(args[1])
        return 950.0 if pressure > 4.0e6 else 850.0
    if output == "Umass":
        return 2.0e5
    raise ValueError(f"unsupported fake PropsSI output: {output}")


def _phase_evaluator_for_midpoint(midpoint_mode: str = "open"):
    def evaluate(rho, e, *, config=None):
        rho_arr = np.asarray(rho, dtype=float)
        e_arr = np.asarray(e, dtype=float)
        shape = rho_arr.shape
        p = np.full(shape, 3.0e6)
        T = np.full(shape, 270.0)
        q = np.zeros(shape)
        alpha = np.zeros(shape)
        raw = np.empty(shape, dtype="<U40")
        phase = np.empty(shape, dtype="<U40")
        scope = np.full(shape, "supported_candidate", dtype="<U24")

        for index in np.ndindex(shape):
            is_midpoint = 895.0 <= rho_arr[index] <= 905.0
            if is_midpoint and midpoint_mode == "open":
                raw[index] = "twophase"
                phase[index] = "liquid_vapor_two_phase"
                q[index] = 0.20
                alpha[index] = 0.50
            elif is_midpoint and midpoint_mode == "endpoint":
                raw[index] = "twophase"
                phase[index] = "liquid_vapor_two_phase"
                q[index] = 0.0
                alpha[index] = 0.0
            elif is_midpoint and midpoint_mode == "vapor":
                raw[index] = "gas"
                phase[index] = "single_phase_vapor"
                q[index] = 1.0
                alpha[index] = 1.0
            elif is_midpoint and midpoint_mode == "guarded":
                raw[index] = "supercritical"
                phase[index] = "supercritical"
                q[index] = np.nan
                alpha[index] = np.nan
                scope[index] = "guarded_out"
            else:
                raw[index] = "liquid"
                phase[index] = "compressed_or_subcooled_liquid"

        defined = np.ones(shape, dtype=bool)
        if midpoint_mode == "guarded":
            defined = np.isfinite(q)
        return HEMPhaseState(
            backend_name="fake",
            rho=np.array(rho_arr, copy=True),
            e=np.array(e_arr, copy=True),
            p=p,
            T=T,
            quality=q,
            quality_defined=defined,
            alpha=alpha,
            alpha_defined=defined,
            raw_phase=raw,
            phase_class=phase,
            scope_status=scope,
            sound_speed_evaluated=False,
        )

    return evaluate


def _sound_speed_for_midpoint(midpoint_mode: str = "open"):
    def estimate(rho, e, *, config=None):
        phase_class = "compressed_or_subcooled_liquid"
        if 895.0 <= float(rho) <= 905.0 and midpoint_mode == "open":
            phase_class = "liquid_vapor_two_phase"
        return SimpleNamespace(
            rho_kg_m3=float(rho),
            e_j_kg=float(e),
            phase_class=phase_class,
            sound_speed_m_s=100.0,
        )

    return estimate


_sound_speed = _sound_speed_for_midpoint("open")


@pytest.mark.parametrize(
    "config_factory",
    [
        lambda: HEMLiquidStatePairSurveyConfig(candidate_specs=()),
        lambda: HEMLiquidStatePairSurveyConfig(pair_specs=()),
        lambda: HEMLiquidStatePairSurveyConfig(blend_fractions=(0.0, 1.0)),
        lambda: HEMLiquidStatePairSurveyConfig(
            blend_fractions=(0.0, 0.5, 0.5, 1.0)
        ),
        lambda: HEMLiquidStatePairSurveyConfig(
            blend_fractions=(-0.1, 0.5, 1.0)
        ),
        lambda: HEMLiquidStatePairSurveyConfig(
            crossing_evidence_min_quality=0.0
        ),
        lambda: HEMLiquidStatePairSurveyConfig(
            candidate_specs=(
                LiquidCandidateSpec("duplicate", 5.0e6, 5.0),
                LiquidCandidateSpec("duplicate", 4.0e6, 5.0),
            )
        ),
        lambda: HEMLiquidStatePairSurveyConfig(
            candidate_specs=(LiquidCandidateSpec("only", 5.0e6, 5.0),),
            pair_specs=(
                LiquidStatePairSpec(
                    "bad",
                    "only",
                    "missing",
                    "right pressure",
                    "unknown candidate",
                ),
            ),
        ),
    ],
)
def test_config_rejects_invalid_contract(config_factory):
    with pytest.raises(ValueError):
        config_factory()


def test_default_survey_definitions_are_small_and_reference_known_candidates():
    candidates = default_liquid_candidate_specs()
    pairs = default_liquid_pair_specs()
    ids = {candidate.candidate_id for candidate in candidates}

    assert 5 <= len(candidates) <= 16
    assert 4 <= len(pairs) <= 12
    assert all(pair.left_candidate_id in ids for pair in pairs)
    assert all(pair.right_candidate_id in ids for pair in pairs)


def test_survey_identifies_open_two_phase_blend_proxy():
    result = run_liquid_state_pair_survey(
        _small_config(),
        props_si=_fake_props_si,
        phase_evaluator=_phase_evaluator_for_midpoint("open"),
        sound_speed_estimator=_sound_speed,
    )

    assert result.summary()["accepted_liquid_candidate_count"] == 2
    pair = result.pairs[0]
    assert pair.outcome == "OPEN_TWO_PHASE"
    assert pair.first_open_two_phase_fraction == 0.5
    assert pair.max_equilibrium_quality == pytest.approx(0.20)
    assert pair.promising_for_dry_run is True
    assert [point.point_status for point in result.blend_points] == [
        "LIQUID_POINT",
        "OPEN_TWO_PHASE",
        "LIQUID_POINT",
    ]
    assert result.summary()["fvm_step_exercised"] is False


def test_survey_distinguishes_endpoint_only_proxy():
    result = run_liquid_state_pair_survey(
        _small_config(),
        props_si=_fake_props_si,
        phase_evaluator=_phase_evaluator_for_midpoint("endpoint"),
        sound_speed_estimator=_sound_speed,
    )

    pair = result.pairs[0]
    assert pair.outcome == "ENDPOINT_LANDING"
    assert pair.endpoint_point_count == 1
    assert pair.open_two_phase_point_count == 0
    assert pair.promising_for_dry_run is False
    midpoint = result.blend_points[1]
    assert midpoint.sound_speed_m_s is None
    assert "endpoint_acoustic_closure_not_established" in midpoint.reason


def test_survey_distinguishes_all_liquid_proxy():
    result = run_liquid_state_pair_survey(
        _small_config(),
        props_si=_fake_props_si,
        phase_evaluator=_phase_evaluator_for_midpoint("liquid"),
        sound_speed_estimator=_sound_speed_for_midpoint("liquid"),
    )

    assert result.pairs[0].outcome == "ALL_LIQUID"
    assert result.pairs[0].promising_for_dry_run is False
    assert all(
        point.point_status == "LIQUID_POINT" for point in result.blend_points
    )


def test_survey_rejects_vapor_or_guarded_proxy():
    vapor = run_liquid_state_pair_survey(
        _small_config(),
        props_si=_fake_props_si,
        phase_evaluator=_phase_evaluator_for_midpoint("vapor"),
        sound_speed_estimator=_sound_speed,
    )
    guarded = run_liquid_state_pair_survey(
        _small_config(),
        props_si=_fake_props_si,
        phase_evaluator=_phase_evaluator_for_midpoint("guarded"),
        sound_speed_estimator=_sound_speed,
    )

    assert vapor.pairs[0].outcome == "FORBIDDEN_REGION"
    assert guarded.pairs[0].outcome == "FORBIDDEN_REGION"
    assert vapor.pairs[0].promising_for_dry_run is False
    assert guarded.pairs[0].promising_for_dry_run is False


def test_candidate_guard_failure_prevents_pair_screening():
    def negative_energy_props(output, *args):
        if output == "Umass":
            return -1.0
        return _fake_props_si(output, *args)

    result = run_liquid_state_pair_survey(
        _small_config(),
        props_si=negative_energy_props,
        phase_evaluator=_phase_evaluator_for_midpoint("open"),
        sound_speed_estimator=_sound_speed,
    )

    assert all(candidate.status == "GUARD_FAILURE" for candidate in result.candidates)
    assert result.pairs[0].outcome == "GUARD_FAILURE"
    assert result.blend_points == ()


def test_backend_failure_is_recorded_instead_of_hidden():
    def failed_props(output, *args):
        if output == "Dmass":
            raise RuntimeError("fake density failure")
        return _fake_props_si(output, *args)

    result = run_liquid_state_pair_survey(
        _small_config(),
        props_si=failed_props,
        phase_evaluator=_phase_evaluator_for_midpoint("open"),
        sound_speed_estimator=_sound_speed,
    )

    assert all(candidate.status == "BACKEND_FAILURE" for candidate in result.candidates)
    assert result.pairs[0].outcome == "BACKEND_FAILURE"


def test_acoustic_failure_is_a_guard_failure():
    def failed_sound_speed(rho, e, *, config=None):
        raise RuntimeError("fake acoustic failure")

    result = run_liquid_state_pair_survey(
        _small_config(),
        props_si=_fake_props_si,
        phase_evaluator=_phase_evaluator_for_midpoint("open"),
        sound_speed_estimator=failed_sound_speed,
    )

    assert all(candidate.status == "GUARD_FAILURE" for candidate in result.candidates)
    assert result.pairs[0].outcome == "GUARD_FAILURE"


def test_artifacts_retain_ledger_and_approval_boundary(tmp_path):
    result = run_liquid_state_pair_survey(
        _small_config(),
        props_si=_fake_props_si,
        phase_evaluator=_phase_evaluator_for_midpoint("open"),
        sound_speed_estimator=_sound_speed,
    )
    files = write_liquid_state_pair_survey_artifacts(tmp_path, result)

    assert set(files) == {
        "json",
        "candidates_csv",
        "pairs_csv",
        "blend_points_csv",
        "markdown",
        "npz",
    }
    assert all(path.is_file() for path in files.values())

    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["screening_is_fvm_solution"] is False
    assert payload["promising_pair_ids"] == ["pair"]
    assert payload["production_hem_activation_approved"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False
    assert len(payload["candidates"]) == 2
    assert len(payload["pairs"]) == 1
    assert len(payload["blend_points"]) == 3

    markdown = files["markdown"].read_text(encoding="utf-8")
    assert "NOT AN FVM CROSSING RESULT" in markdown
    assert "pair" in markdown


@pytest.mark.coolprop_installed
def test_small_real_coolprop_survey_runs_without_skip(tmp_path):
    pytest.importorskip("CoolProp")
    config = HEMLiquidStatePairSurveyConfig(
        candidate_specs=(
            LiquidCandidateSpec("p5_m5", 5.0e6, 5.0),
            LiquidCandidateSpec("p4_m5", 4.0e6, 5.0),
            LiquidCandidateSpec("p3_m5", 3.0e6, 5.0),
        ),
        pair_specs=(
            LiquidStatePairSpec(
                "p5_p4",
                "p5_m5",
                "p4_m5",
                "baseline",
                "installed-CoolProp baseline",
            ),
            LiquidStatePairSpec(
                "p5_p3",
                "p5_m5",
                "p3_m5",
                "right pressure",
                "installed-CoolProp wider pressure span",
            ),
        ),
        blend_fractions=(0.0, 0.25, 0.5, 0.75, 1.0),
    )

    result = run_liquid_state_pair_survey(config)
    summary = result.summary()

    assert summary["candidate_count"] == 3
    assert summary["accepted_liquid_candidate_count"] >= 2
    assert summary["pair_count"] == 2
    assert summary["screening_is_fvm_solution"] is False
    assert all(
        pair.outcome
        in {
            "ALL_LIQUID",
            "ENDPOINT_LANDING",
            "OPEN_TWO_PHASE",
            "FORBIDDEN_REGION",
            "GUARD_FAILURE",
            "BACKEND_FAILURE",
        }
        for pair in result.pairs
    )
    files = write_liquid_state_pair_survey_artifacts(tmp_path, result)
    assert all(path.is_file() for path in files.values())
