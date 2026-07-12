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


def _sample_mesh_rows():
    return [
        {"case_id":"n0050_cfl050","dx_m":2.0,"cfl":0.5,"interprobe_threshold_speed_relative_error":0.08612,"interprobe_peak_speed_relative_error":8.43e-6,"interprobe_centroid_speed_relative_error":0.02937,"interprobe_cross_correlation_speed_relative_error":0.04550,"primary_probe_amplitude_ratio_L2":0.45538,"primary_probe_fwhm_broadening_ratio_L2":2.19006,"waveform_l2_difference_vs_finest":0.35697},
        {"case_id":"n0100_cfl050","dx_m":1.0,"cfl":0.5,"interprobe_threshold_speed_relative_error":0.05485,"interprobe_peak_speed_relative_error":1.11e-5,"interprobe_centroid_speed_relative_error":0.01223,"interprobe_cross_correlation_speed_relative_error":0.02292,"primary_probe_amplitude_ratio_L2":0.58462,"primary_probe_fwhm_broadening_ratio_L2":1.70842,"waveform_l2_difference_vs_finest":0.16886},
        {"case_id":"n0200_cfl050","dx_m":0.5,"cfl":0.5,"interprobe_threshold_speed_relative_error":0.03347,"interprobe_peak_speed_relative_error":1.38e-5,"interprobe_centroid_speed_relative_error":0.00375,"interprobe_cross_correlation_speed_relative_error":0.00917,"primary_probe_amplitude_ratio_L2":0.71301,"primary_probe_fwhm_broadening_ratio_L2":1.40170,"waveform_l2_difference_vs_finest":0.0},
    ]


def test_local_order_and_convergence_by_metric_peak_floor():
    from liquid_gas_transient.cases.coolprop_small_amplitude_wave_sweep import convergence_by_metric, local_order_estimates
    loc = local_order_estimates([2.0, 1.0, 0.5], [0.08, 0.04, 0.01])
    assert loc["local_order_estimates"] == pytest.approx([1.0, 2.0])
    conv = convergence_by_metric(_sample_mesh_rows())
    assert conv["threshold_speed"]["classification"] == "monotonic_improvement"
    assert conv["peak_speed"]["classification"] == "at_error_floor_or_non_monotonic"
    assert conv["peak_speed"]["apparent_order"] is None
    assert conv["waveform_difference"]["classification"] == "monotonic_improvement_against_finest_reference"
    assert conv["overall_classification"] == "monotonic_shape_improvement_with_phase_speed_at_error_floor"


def test_optional_400_cell_config_and_finest_reference_plan():
    cfg = CoolPropSmallAmplitudeWaveSweepConfig(mesh_cells=(50, 100, 200, 400), cfl_values=(0.25, 0.5), mesh_comparison_cfl=0.5, cfl_comparison_n_cells=100)
    from liquid_gas_transient.cases.coolprop_small_amplitude_wave_sweep import _run_plan
    plan = _run_plan(cfg)
    assert any(p["n_cells"] == 400 and p["cfl"] == 0.5 and "mesh_comparison" in p["comparison_groups"] for p in plan)
    assert case_id_for(max(cfg.mesh_cells), cfg.mesh_comparison_cfl) == "n0400_cfl050"


def test_mesh_plot_rows_exclude_cfl_comparison_duplicate_dx():
    from liquid_gas_transient.cases.coolprop_small_amplitude_wave_sweep import _mesh_summary_rows
    cfg = CoolPropSmallAmplitudeWaveSweepConfig(mesh_cells=(50, 100, 200), cfl_values=(0.25, 0.5), mesh_comparison_cfl=0.5, cfl_comparison_n_cells=100)
    runs = []
    for row in _sample_mesh_rows():
        runs.append({"case_id": row["case_id"], "comparison_groups": ["mesh_comparison"] + (["cfl_comparison"] if row["case_id"] == "n0100_cfl050" else []), "metrics": {"cfl_target": row["cfl"]}, "summary_row": row})
    runs.append({"case_id":"n0100_cfl025", "comparison_groups":["cfl_comparison"], "metrics":{"cfl_target":0.25}, "summary_row": {**_sample_mesh_rows()[1], "case_id":"n0100_cfl025", "cfl":0.25}})
    rows = _mesh_summary_rows(runs, cfg)
    assert [r["case_id"] for r in rows] == ["n0050_cfl050", "n0100_cfl050", "n0200_cfl050"]
    assert [r["dx_m"] for r in rows].count(1.0) == 1
