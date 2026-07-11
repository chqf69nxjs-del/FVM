from __future__ import annotations

import json
import math

import numpy as np
import pytest

from liquid_gas_transient.cases.coolprop_small_amplitude_wave import (
    CoolPropSmallAmplitudeWaveConfig,
    build_initial_gaussian_pulse,
    run_coolprop_small_amplitude_wave,
)
from liquid_gas_transient.state import vapor_mass_fraction


def test_config_validation_accepts_default():
    cfg = CoolPropSmallAmplitudeWaveConfig()
    assert cfg.pipe_length_m == 100.0
    assert cfg.probe_fractions == (0.25, 0.5, 0.75)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pipe_length_m": 0.0},
        {"diameter_m": 0.0},
        {"n_cells": 5},
        {"cfl": 0.0},
        {"cfl": 1.5},
        {"pressure_amplitude_pa": 0.0},
        {"pressure_amplitude_pa": 2.0e4},
        {"pulse_center_fraction": 0.0},
        {"pulse_center_fraction": 1.0},
        {"pulse_sigma_fraction": 0.0},
        {"probe_fractions": (0.1,)},
        {"probe_fractions": (1.0,)},
        {"max_steps": 0},
        {"sample_every": 0},
        {"arrival_threshold_fraction": 0.0},
        {"arrival_threshold_fraction": 1.0},
    ],
)
def test_config_validation_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        CoolPropSmallAmplitudeWaveConfig(**kwargs)


def test_initial_pulse_structure_with_coolprop():
    pytest.importorskip("CoolProp")
    cfg = CoolPropSmallAmplitudeWaveConfig(n_cells=50, probe_fractions=(0.5,), max_steps=5000)
    init = build_initial_gaussian_pulse(cfg)
    assert np.all(np.isfinite(init["U"]))
    assert np.all(init["dp"] > 0.0)
    assert np.all(init["u"] > 0.0)
    assert np.allclose(vapor_mass_fraction(init["U"]), 0.0)
    center_idx = int(np.argmin(np.abs(init["x"] - cfg.pulse_center_fraction * cfg.pipe_length_m)))
    assert center_idx == int(np.argmax(init["dp"]))
    expected = init["dp"] / (init["reference"]["rho0"] * init["reference"]["c0"])
    assert np.allclose(init["u"], expected)


def test_coolprop_small_amplitude_wave_integration_and_artifacts(tmp_path):
    pytest.importorskip("CoolProp")
    cfg = CoolPropSmallAmplitudeWaveConfig(n_cells=50, probe_fractions=(0.5,), max_steps=5000)
    metrics = run_coolprop_small_amplitude_wave(output_dir=tmp_path, config=cfg)
    assert metrics["completed_without_exception"]
    assert metrics["step_count"] > 1
    assert metrics["overall_observation_run_pass"]
    assert metrics["property_backend_name"] == "coolprop_co2"
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert metrics["design_evaluation"] is False
    assert metrics["validation"] is False
    assert metrics["remained_single_phase"]
    assert metrics["max_vapor_mass_fraction"] <= 1.0e-12
    assert metrics["max_alpha"] <= 1.0e-12
    assert not metrics["missing_budget_fields"]
    probe = metrics["probes"][0]
    assert probe["arrival_detected"]
    assert math.isfinite(probe["numerical_arrival_time_s"])
    assert math.isfinite(probe["inferred_wave_speed_m_s"])
    assert probe["inferred_wave_speed_m_s"] > 0.0
    for suffix in ["config.json", "metrics.json", "probe_history.csv", "final_profile.csv", "report.md"]:
        assert (tmp_path / f"{cfg.case_name}_{suffix}").exists()
    saved = json.loads((tmp_path / f"{cfg.case_name}_metrics.json").read_text())
    assert saved["overall_observation_run_pass"] is True
