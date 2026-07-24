from __future__ import annotations

import numpy as np
import pytest

from liquid_gas_transient.reconstruction import (
    LIMITER_NAMES,
    limited_slopes,
    minmod,
    monotonized_central,
    reconstruct_interfaces,
    van_leer,
)


def test_first_order_reconstruction_matches_adjacent_cell_averages() -> None:
    values = np.array(
        [
            [1.0, 10.0],
            [2.0, 8.0],
            [4.0, 5.0],
            [7.0, 1.0],
        ]
    )
    original = values.copy()

    left, right = reconstruct_interfaces(values, method="first_order")

    np.testing.assert_array_equal(left, values[:-1])
    np.testing.assert_array_equal(right, values[1:])
    np.testing.assert_array_equal(values, original)
    assert not np.shares_memory(left, values)
    assert not np.shares_memory(right, values)


@pytest.mark.parametrize("limiter", LIMITER_NAMES)
def test_muscl_preserves_constant_and_linear_profiles(limiter: str) -> None:
    constant = np.full((6, 2), [3.0, -4.0])
    left_constant, right_constant = reconstruct_interfaces(
        constant,
        method="muscl",
        limiter=limiter,  # type: ignore[arg-type]
    )
    np.testing.assert_allclose(left_constant, constant[:-1])
    np.testing.assert_allclose(right_constant, constant[1:])

    x = np.arange(7.0)
    linear = np.column_stack((2.0 * x + 1.0, -3.0 * x + 5.0))
    left, right = reconstruct_interfaces(
        linear,
        method="muscl",
        limiter=limiter,  # type: ignore[arg-type]
    )
    exact_midpoint = 0.5 * (linear[:-1] + linear[1:])

    # End cells deliberately use zero slope. Interfaces whose two adjacent
    # cells both have neighbours recover the exact linear midpoint.
    np.testing.assert_allclose(left[1:-1], exact_midpoint[1:-1])
    np.testing.assert_allclose(right[1:-1], exact_midpoint[1:-1])


@pytest.mark.parametrize("limiter", LIMITER_NAMES)
def test_tvd_reconstruction_does_not_create_new_interface_extrema(limiter: str) -> None:
    values = np.array([0.0, 1.0, 3.0, 2.0, 2.5, 1.5, 0.0])

    left, right = reconstruct_interfaces(
        values,
        method="muscl",
        limiter=limiter,  # type: ignore[arg-type]
    )
    local_min = np.minimum(values[:-1], values[1:])
    local_max = np.maximum(values[:-1], values[1:])

    assert np.all(left >= local_min)
    assert np.all(left <= local_max)
    assert np.all(right >= local_min)
    assert np.all(right <= local_max)

    slopes = limited_slopes(values, limiter=limiter)  # type: ignore[arg-type]
    assert slopes[3] == pytest.approx(0.0)  # local minimum
    assert slopes[4] == pytest.approx(0.0)  # local maximum


def test_limiters_are_componentwise_and_return_expected_scalar_values() -> None:
    delta_minus = np.array([2.0, 2.0, -2.0, -2.0, 0.0])
    delta_plus = np.array([1.0, -1.0, -1.0, -4.0, 3.0])

    np.testing.assert_allclose(
        minmod(delta_minus, delta_plus),
        [1.0, 0.0, -1.0, -2.0, 0.0],
    )
    np.testing.assert_allclose(
        monotonized_central(delta_minus, delta_plus),
        [1.5, 0.0, -1.5, -3.0, 0.0],
    )
    np.testing.assert_allclose(
        van_leer(delta_minus, delta_plus),
        [4.0 / 3.0, 0.0, -4.0 / 3.0, -8.0 / 3.0, 0.0],
    )


def test_reconstruction_rejects_invalid_configuration_and_nonfinite_input() -> None:
    values = np.array([1.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="unknown reconstruction method"):
        reconstruct_interfaces(values, method="weno")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unknown limiter"):
        reconstruct_interfaces(
            values,
            method="muscl",
            limiter="superbee",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="at least three cells"):
        limited_slopes(np.array([1.0, 2.0]))
    with pytest.raises(ValueError, match="finite"):
        reconstruct_interfaces(np.array([1.0, np.nan, 3.0]), method="muscl")
