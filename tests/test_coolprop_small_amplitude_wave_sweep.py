import math

import numpy as np
import pytest

from liquid_gas_transient.properties import coolprop_available
from liquid_gas_transient.cases.coolprop_small_amplitude_wave_sweep import (
    CoolPropSmallAmplitudeWaveSweepConfig,
    apparent_order,
    case_id_for,
    common_time_grid,
    cross_correlation_lag,
    gaussian_fwhm_m,
    run_coolprop_small_amplitude_wave_sweep,
    temporal_centroid,
    temporal_fwhm,
)


def test_gaussian_fwhm_theory():
    sigma = 3.0
    assert gaussian_fwhm_m(sigma) == pytest.approx(2.0 * math.sqrt(2.0 * math.log(2.0)) * sigma)


def test_temporal_fwhm_and_centroid_synthetic_gaussian():
    sigma = 0.01
    center = 0.04
    t = np.linspace(0.0, 0.08, 1001)
    y = np.exp(-0.5 * ((t - center) / sigma) ** 2)
    f = temporal_fwhm(t, y)
    c = temporal_centroid(t, y)
    assert f["fwhm_detected"]
    assert f["temporal_fwhm_s"] == pytest.approx(gaussian_fwhm_m(sigma), rel=2e-3)
    assert c["centroid_detected"]
    assert c["temporal_centroid_time_s"] == pytest.approx(center, rel=1e-3)


def test_common_grid_and_cross_correlation_lag():
    lag = 0.013
    t1 = np.linspace(0, 0.1, 501)
    t2 = np.linspace(0, 0.1, 401)
    y1 = np.exp(-0.5 * ((t1 - 0.03) / 0.006) ** 2)
    y2 = np.exp(-0.5 * ((t2 - 0.03 - lag) / 0.006) ** 2)
    tg, a, b = common_time_grid(t1, y1, t2, y2)
    assert len(tg) == min(len(t1), len(t2))
    assert np.isfinite(a).all() and np.isfinite(b).all()
    cc = cross_correlation_lag(t1, y1, t2, y2)
    assert cc["cross_correlation_detected"]
    assert cc["cross_correlation_lag_s"] == pytest.approx(lag, abs=4e-4)
    assert cc["cross_correlation_coefficient"] > 0.95


def test_apparent_order_conditions_and_case_naming():
    assert case_id_for(50, 0.5) == "n0050_cfl050"
    good = apparent_order([2.0, 1.0, 0.5], [0.04, 0.01, 0.003])
    assert good["apparent_order"] == pytest.approx(2.0)
    assert apparent_order([2.0, 1.0, 0.5], [0.01, 0.02, 0.003])["apparent_order"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mesh_cells": (100, 50)},
        {"mesh_cells": (5, 10)},
        {"cfl_values": (0.0,)},
        {"mesh_comparison_cfl": 0.75},
        {"cfl_comparison_n_cells": 999},
        {"primary_probe_fractions": (0.1,)},
    ],
)
def test_sweep_config_validation(kwargs):
    with pytest.raises(ValueError):
        CoolPropSmallAmplitudeWaveSweepConfig(**kwargs)


@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_installed_coolprop_small_sweep(tmp_path):
    cfg = CoolPropSmallAmplitudeWaveSweepConfig(
        mesh_cells=(30, 40),
        cfl_values=(0.5,),
        mesh_comparison_cfl=0.5,
        cfl_comparison_n_cells=30,
        probe_fractions=(0.5, 0.75),
        primary_probe_fractions=(0.5, 0.75),
        sample_every=2,
        max_steps=5000,
        generate_case_plots=False,
        generate_comparison_plots=False,
    )
    metrics = run_coolprop_small_amplitude_wave_sweep(tmp_path, cfg)
    assert metrics["overall_sweep_execution_pass"]
    assert metrics["property_backend_design_status"] == "not_approved_for_design_use"
    assert (tmp_path / "coolprop_small_amplitude_wave_sweep_sweep_summary.csv").exists()
    assert len(metrics["runs"]) == 2
    for run in metrics["runs"]:
        assert run["remained_single_phase"]
        assert run["interprobe_peak_speed_m_s"] > 0
        assert run["interprobe_centroid_speed_m_s"] > 0
        assert run["interprobe_cross_correlation_speed_m_s"] > 0


@pytest.mark.skipif(not coolprop_available(), reason="CoolProp is not installed")
def test_comparison_plotting_headless(tmp_path):
    cfg = CoolPropSmallAmplitudeWaveSweepConfig(
        mesh_cells=(30, 40), cfl_values=(0.5,), mesh_comparison_cfl=0.5, cfl_comparison_n_cells=30,
        probe_fractions=(0.5, 0.75), primary_probe_fractions=(0.5, 0.75), sample_every=3, max_steps=5000,
        generate_case_plots=False, generate_comparison_plots=True,
    )
    metrics = run_coolprop_small_amplitude_wave_sweep(tmp_path, cfg)
    assert metrics["generated_plots"]
    for name in metrics["generated_plots"]:
        assert (tmp_path / name).exists()
