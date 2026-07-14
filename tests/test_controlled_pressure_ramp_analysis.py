from __future__ import annotations

from pathlib import Path

import pytest

from liquid_gas_transient.analyze_controlled_pressure_ramp_results import (
    build_probe_observation_metrics,
    detect_fraction_crossing_time,
)
from liquid_gas_transient.cases.coolprop_controlled_pressure_ramp import (
    CoolPropControlledPressureRampConfig,
)


def _rows() -> list[dict[str, object]]:
    return [
        {
            "time_s": 0.0,
            "probe_name": "x_over_L_0.75",
            "probe_cell_center_x_m": 75.5,
            "delta_pressure_pa": 0.0,
            "velocity_m_s": 0.0,
            "A_plus_pa": 0.0,
            "A_minus_pa": 0.0,
        },
        {
            "time_s": 0.05,
            "probe_name": "x_over_L_0.75",
            "probe_cell_center_x_m": 75.5,
            "delta_pressure_pa": 250.0,
            "velocity_m_s": -0.0005,
            "A_plus_pa": 1.0,
            "A_minus_pa": 249.0,
        },
        {
            "time_s": 0.10,
            "probe_name": "x_over_L_0.75",
            "probe_cell_center_x_m": 75.5,
            "delta_pressure_pa": 750.0,
            "velocity_m_s": -0.0015,
            "A_plus_pa": 1.0,
            "A_minus_pa": 749.0,
        },
        {
            "time_s": 0.15,
            "probe_name": "x_over_L_0.75",
            "probe_cell_center_x_m": 75.5,
            "delta_pressure_pa": 1000.0,
            "velocity_m_s": -0.0020,
            "A_plus_pa": 1.0,
            "A_minus_pa": 999.0,
        },
    ]


def test_detect_fraction_crossing_time_interpolates() -> None:
    rows = _rows()

    assert detect_fraction_crossing_time(
        rows,
        fraction=0.5,
        pressure_change_pa=1000.0,
    ) == pytest.approx(0.075)


def test_detect_fraction_crossing_time_returns_none_when_unreached() -> None:
    rows = _rows()[:2]

    assert detect_fraction_crossing_time(
        rows,
        fraction=0.9,
        pressure_change_pa=1000.0,
    ) is None


def test_build_probe_observation_metrics_reports_left_going_direction() -> None:
    cfg = CoolPropControlledPressureRampConfig(
        pipe_length_m=100.0,
        pressure_change_pa=1000.0,
        ramp_start_s=0.005,
        ramp_duration_s=0.010,
        probe_fractions=(0.75,),
    )
    metrics = build_probe_observation_metrics(
        _rows(),
        config=cfg,
        base_metrics={"rho0": 1000.0, "c0": 500.0},
    )

    assert len(metrics) == 1
    item = metrics[0]
    assert item["observed_propagation_direction"] == "left_going"
    assert item["opposite_direction_leakage_ratio"] < 0.01
    assert item["final_amplitude_ratio"] == pytest.approx(1.0)
    assert item["numerical_p50_arrival_time_s"] == pytest.approx(0.075)
    assert item["theoretical_p50_arrival_time_s"] > 0.0
