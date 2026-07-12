"""Verification helpers for liquid-gas transient software-path checks.

Boundary-reflection regression exports are loaded lazily because that module
imports the boundary-reflection case runner, while the case runner imports the
``verification.boundary_reflection`` helper submodule. Eager package-level
imports would therefore create an import-order-dependent cycle.
"""
from __future__ import annotations

from typing import Any

from .wave_regression import (
    WaveRegressionLimits,
    evaluate_coolprop_wave_regression,
    run_coolprop_wave_regression,
)

__all__ = [
    "BoundaryReflectionRegressionLimits",
    "evaluate_boundary_reflection_regression",
    "run_boundary_reflection_regression",
    "WaveRegressionLimits",
    "evaluate_coolprop_wave_regression",
    "run_coolprop_wave_regression",
]


def __getattr__(name: str) -> Any:
    if name in {
        "BoundaryReflectionRegressionLimits",
        "evaluate_boundary_reflection_regression",
        "run_boundary_reflection_regression",
    }:
        from . import boundary_reflection_regression as module

        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
