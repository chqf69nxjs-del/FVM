"""Pure finite-volume reconstruction helpers for optional higher-order paths.

The production solver currently uses piecewise-constant, first-order interface
states. This module provides a solver-independent MUSCL/TVD scaffold that can
be tested before any EOS, boundary, time-integration, or production-state path
is changed.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

LimiterName = Literal["minmod", "mc", "van_leer"]
ReconstructionMethod = Literal["first_order", "muscl"]

LIMITER_NAMES: tuple[LimiterName, ...] = ("minmod", "mc", "van_leer")
RECONSTRUCTION_METHODS: tuple[ReconstructionMethod, ...] = ("first_order", "muscl")


def _broadcast_float_arrays(*values: np.ndarray | float) -> tuple[np.ndarray, ...]:
    arrays = tuple(np.asarray(value, dtype=float) for value in values)
    return tuple(np.broadcast_arrays(*arrays))


def _minmod_many(*values: np.ndarray | float) -> np.ndarray:
    if len(values) < 2:
        raise ValueError("minmod requires at least two values")

    arrays = _broadcast_float_arrays(*values)
    stacked = np.stack(arrays, axis=0)
    all_positive = np.all(stacked > 0.0, axis=0)
    all_negative = np.all(stacked < 0.0, axis=0)
    magnitude = np.min(np.abs(stacked), axis=0)
    return np.where(all_positive, magnitude, np.where(all_negative, -magnitude, 0.0))


def minmod(delta_minus: np.ndarray | float, delta_plus: np.ndarray | float) -> np.ndarray:
    """Return the componentwise two-argument minmod-limited slope."""

    return _minmod_many(delta_minus, delta_plus)


def monotonized_central(
    delta_minus: np.ndarray | float,
    delta_plus: np.ndarray | float,
) -> np.ndarray:
    """Return the componentwise monotonized-central (MC) limited slope."""

    dm, dp = _broadcast_float_arrays(delta_minus, delta_plus)
    centered = 0.5 * (dm + dp)
    return _minmod_many(centered, 2.0 * dm, 2.0 * dp)


def van_leer(delta_minus: np.ndarray | float, delta_plus: np.ndarray | float) -> np.ndarray:
    """Return the componentwise van-Leer harmonic limited slope."""

    dm, dp = _broadcast_float_arrays(delta_minus, delta_plus)
    same_sign = dm * dp > 0.0
    denominator = dm + dp
    slope = np.zeros_like(denominator, dtype=float)
    np.divide(2.0 * dm * dp, denominator, out=slope, where=same_sign)
    return slope


def _apply_limiter(
    delta_minus: np.ndarray,
    delta_plus: np.ndarray,
    limiter: LimiterName,
) -> np.ndarray:
    if limiter == "minmod":
        return minmod(delta_minus, delta_plus)
    if limiter == "mc":
        return monotonized_central(delta_minus, delta_plus)
    if limiter == "van_leer":
        return van_leer(delta_minus, delta_plus)
    raise ValueError(f"unknown limiter {limiter!r}; expected one of {LIMITER_NAMES}")


def limited_slopes(cell_values: np.ndarray, *, limiter: LimiterName = "minmod") -> np.ndarray:
    """Return componentwise TVD slopes for a cell-centred value array.

    The first axis is the finite-volume cell axis. End-cell slopes are set to
    zero so callers can provide an already ghost-extended array without hidden
    extrapolation. Interior slopes use the selected componentwise limiter.
    """

    values = np.asarray(cell_values, dtype=float)
    if values.ndim == 0:
        raise ValueError("cell_values must have at least one dimension")
    if values.shape[0] < 3:
        raise ValueError("MUSCL slope construction requires at least three cells")
    if not np.all(np.isfinite(values)):
        raise ValueError("cell_values must contain only finite values")
    if limiter not in LIMITER_NAMES:
        raise ValueError(f"unknown limiter {limiter!r}; expected one of {LIMITER_NAMES}")

    slopes = np.zeros_like(values, dtype=float)
    delta_minus = values[1:-1] - values[:-2]
    delta_plus = values[2:] - values[1:-1]
    slopes[1:-1] = _apply_limiter(delta_minus, delta_plus, limiter)
    return slopes


def reconstruct_interfaces(
    cell_values: np.ndarray,
    *,
    method: ReconstructionMethod = "first_order",
    limiter: LimiterName = "minmod",
) -> tuple[np.ndarray, np.ndarray]:
    """Return left/right states at every interface between adjacent cells.

    For ``first_order``, the result exactly matches the current piecewise-
    constant contract: ``left = values[:-1]`` and ``right = values[1:]``.
    For ``muscl``, componentwise TVD slopes reconstruct each adjacent cell to
    the shared interface. No EOS conversion or physical-state clipping occurs
    here; those policy decisions remain explicit future integration gates.
    """

    values = np.asarray(cell_values, dtype=float)
    if values.ndim == 0:
        raise ValueError("cell_values must have at least one dimension")
    if values.shape[0] < 2:
        raise ValueError("interface reconstruction requires at least two cells")
    if not np.all(np.isfinite(values)):
        raise ValueError("cell_values must contain only finite values")
    if method not in RECONSTRUCTION_METHODS:
        raise ValueError(
            f"unknown reconstruction method {method!r}; "
            f"expected one of {RECONSTRUCTION_METHODS}"
        )
    if limiter not in LIMITER_NAMES:
        raise ValueError(f"unknown limiter {limiter!r}; expected one of {LIMITER_NAMES}")

    if method == "first_order":
        return values[:-1].copy(), values[1:].copy()

    slopes = limited_slopes(values, limiter=limiter)
    left = values[:-1] + 0.5 * slopes[:-1]
    right = values[1:] - 0.5 * slopes[1:]
    return left, right
