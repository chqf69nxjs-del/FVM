from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.analyze_controlled_pressure_ramp_front_fit import (
    extract_numerical_fraction_front,
    fit_p50_propagation,
)


def test_fit_p50_propagation_separates_speed_and_common_delay() -> None:
    c0 = 500.0
    expected_launch = 0.010
    common_delay = 0.002
    summaries = [
        {
            "probe_name": name,
            "boundary_to_probe_distance_m": distance,
            "numerical_p50_arrival_time_s": (
                expected_launch + common_delay + distance / c0
            ),
        }
        for name, distance in (
            ("x_over_L_0.75", 25.0),
            ("x_over_L_0.50", 50.0),
            ("x_over_L_0.25", 75.0),
        )
    ]

    fit = fit_p50_propagation(
        summaries,
        reference_sound_speed_m_s=c0,
        expected_boundary_p50_time_s=expected_launch,
    )

    assert fit["inferred_wave_speed_m_s"] == pytest.approx(c0)
    assert fit["fitted_boundary_p50_launch_time_s"] == pytest.approx(
        expected_launch + common_delay
    )
    assert fit["common_boundary_launch_delay_s"] == pytest.approx(common_delay)
    assert fit["fit_residual_rms_s"] == pytest.approx(0.0, abs=1.0e-14)
    assert fit["fit_r_squared"] == pytest.approx(1.0)


def test_fit_p50_propagation_requires_two_arrivals() -> None:
    with pytest.raises(ValueError, match="at least two"):
        fit_p50_propagation(
            [
                {
                    "probe_name": "one",
                    "boundary_to_probe_distance_m": 25.0,
                    "numerical_p50_arrival_time_s": 0.06,
                }
            ],
            reference_sound_speed_m_s=500.0,
            expected_boundary_p50_time_s=0.01,
        )


def test_extract_numerical_fraction_front_interpolates() -> None:
    times = np.asarray([0.0, 0.1, 0.2])
    x = np.asarray([0.0, 1.0, 2.0])
    field = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [0.0, 500.0, 1000.0],
            [500.0, 1000.0, 1000.0],
        ]
    )

    front = extract_numerical_fraction_front(
        times_s=times,
        x_m=x,
        delta_pressure_pa=field,
        pressure_change_pa=1000.0,
        fraction=0.5,
    )

    assert len(front) == 2
    assert front[0]["time_s"] == pytest.approx(0.1)
    assert front[0]["front_x_m"] == pytest.approx(1.0)
    assert front[1]["time_s"] == pytest.approx(0.2)
    assert front[1]["front_x_m"] == pytest.approx(0.0)
