from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.hem_phase_classification import (
    HEMPhaseClassificationConfig,
    HEMPhaseClassificationError,
    build_representative_coolprop_phase_map,
    classify_explicit_phase,
    evaluate_coolprop_hem_phase_state,
    normalize_coolprop_phase,
    write_phase_map_artifacts,
)


def test_normalize_coolprop_phase_is_stable():
    assert normalize_coolprop_phase(" phase_twophase ") == "twophase"
    assert normalize_coolprop_phase("supercritical_liquid") == "supercritical_liquid"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("critical_temperature_margin_K", -1.0),
        ("critical_pressure_margin_Pa", -1.0),
        ("endpoint_tolerance", -1.0),
        ("endpoint_tolerance", np.nan),
    ],
)
def test_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        HEMPhaseClassificationConfig(**{field: value})


@pytest.mark.parametrize(
    ("raw_phase", "p", "T", "expected_class", "expected_scope"),
    [
        ("liquid", 5.0e6, 280.0, "compressed_or_subcooled_liquid", "supported_candidate"),
        ("twophase", 2.0e6, 250.0, "liquid_vapor_two_phase", "supported_candidate"),
        ("gas", 1.0e6, 280.0, "single_phase_vapor", "supported_candidate"),
        ("supercritical", 8.0e6, 310.0, "supercritical", "guarded_out"),
        ("solid", 1.0e5, 200.0, "solid_or_below_triple_guard", "guarded_out"),
        ("unknown", 2.0e6, 260.0, "unknown", "unknown"),
    ],
)
def test_explicit_phase_classification(raw_phase, p, T, expected_class, expected_scope):
    phase_class, scope = classify_explicit_phase(
        raw_phase,
        p_pa=p,
        T_K=T,
        critical_pressure_pa=7.3773e6,
        critical_temperature_K=304.1282,
        triple_temperature_K=216.592,
    )
    assert phase_class == expected_class
    assert scope == expected_scope


def test_critical_guard_box_overrides_generic_phase_label():
    phase_class, scope = classify_explicit_phase(
        "supercritical_liquid",
        p_pa=7.3773e6,
        T_K=304.1282,
        critical_pressure_pa=7.3773e6,
        critical_temperature_K=304.1282,
        triple_temperature_K=216.592,
    )
    assert phase_class == "critical_region"
    assert scope == "guarded_out"


def test_below_triple_temperature_is_guarded_out_even_if_phase_label_is_gas():
    phase_class, scope = classify_explicit_phase(
        "gas",
        p_pa=1.0e5,
        T_K=210.0,
        critical_pressure_pa=7.3773e6,
        critical_temperature_K=304.1282,
        triple_temperature_K=216.592,
    )
    assert phase_class == "solid_or_below_triple_guard"
    assert scope == "guarded_out"


def test_phase_classification_rejects_invalid_numeric_inputs():
    with pytest.raises(HEMPhaseClassificationError):
        classify_explicit_phase(
            "liquid",
            p_pa=0.0,
            T_K=280.0,
            critical_pressure_pa=7.3773e6,
            critical_temperature_K=304.1282,
            triple_temperature_K=216.592,
        )


def _coolprop():
    return pytest.importorskip("CoolProp")


@pytest.mark.coolprop_installed
def test_coolprop_phase_path_does_not_return_sound_speed_and_preserves_inputs():
    coolprop = _coolprop()
    props_si = coolprop.CoolProp.PropsSI
    rho = np.array([
        props_si("Dmass", "P", 8.0e6, "T", 280.0, "CO2"),
        props_si("Dmass", "P", 2.0e6, "Q", 0.5, "CO2"),
    ])
    e = np.array([
        props_si("Umass", "P", 8.0e6, "T", 280.0, "CO2"),
        props_si("Umass", "P", 2.0e6, "Q", 0.5, "CO2"),
    ])
    rho_before = rho.copy()
    e_before = e.copy()

    state = evaluate_coolprop_hem_phase_state(rho, e)

    np.testing.assert_array_equal(rho, rho_before)
    np.testing.assert_array_equal(e, e_before)
    assert state.sound_speed_evaluated is False
    assert not hasattr(state, "sound_speed")
    assert state.phase_class.tolist() == [
        "compressed_or_subcooled_liquid",
        "liquid_vapor_two_phase",
    ]
    assert state.scope_status.tolist() == ["supported_candidate", "supported_candidate"]
    assert state.quality_defined.tolist() == [True, True]
    assert state.alpha_defined.tolist() == [True, True]
    assert state.quality[0] == pytest.approx(0.0)
    assert state.alpha[0] == pytest.approx(0.0)
    assert state.quality[1] == pytest.approx(0.5, rel=1.0e-8)
    assert 0.0 < state.alpha[1] < 1.0


@pytest.mark.coolprop_installed
def test_representative_coolprop_phase_map_covers_supported_and_guarded_states():
    _coolprop()
    records = build_representative_coolprop_phase_map()
    assert len(records) == 9
    classes = {record.phase_class for record in records}
    assert "compressed_or_subcooled_liquid" in classes
    assert "liquid_vapor_two_phase" in classes
    assert "single_phase_vapor" in classes
    assert "supercritical" in classes
    assert all(record.sound_speed_evaluated is False for record in records)
    two_phase = [record for record in records if record.phase_class == "liquid_vapor_two_phase"]
    assert len(two_phase) >= 3
    assert all(record.quality is not None for record in two_phase)
    assert all(record.alpha is not None for record in two_phase)


@pytest.mark.coolprop_installed
def test_phase_map_artifacts_keep_guardrails_false(tmp_path):
    _coolprop()
    files = write_phase_map_artifacts(tmp_path, build_representative_coolprop_phase_map())
    assert set(files) == {"json", "csv", "markdown"}
    assert all(path.is_file() for path in files.values())
    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "stage7_lco2_hem_coolprop_phase_map_v1"
    assert payload["scope"] == "verification_only"
    assert payload["explicit_phase_classification_added"] is True
    assert payload["sound_speed_evaluated"] is False
    assert payload["equilibrium_two_phase_sound_speed_closure_approved"] is False
    assert payload["critical_region_guarded_out"] is True
    assert payload["solid_region_guarded_out"] is True
    assert payload["supercritical_in_current_liquid_vapor_scope"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False
    assert len(payload["results"]) == 9
    markdown = files["markdown"].read_text(encoding="utf-8")
    assert "SOUND SPEED NOT EVALUATED" in markdown
