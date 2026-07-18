"""Verification helpers for liquid-gas transient software-path checks.

Boundary-reflection, controlled-pressure-ramp, and internal-valve regression exports
are loaded lazily because those modules import case runners that may import
verification submodules. Eager package-level imports would create
import-order-dependent cycles.
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
    "ControlledPressureRampRegressionLimits",
    "evaluate_controlled_pressure_ramp_regression",
    "run_controlled_pressure_ramp_regression",
    "InternalValveRegressionLimits",
    "evaluate_internal_valve_regression",
    "run_internal_valve_regression",
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
    if name in {
        "ControlledPressureRampRegressionLimits",
        "evaluate_controlled_pressure_ramp_regression",
        "run_controlled_pressure_ramp_regression",
    }:
        from . import controlled_pressure_ramp_regression as module

        return getattr(module, name)
    if name in {
        "InternalValveRegressionLimits",
        "evaluate_internal_valve_regression",
        "run_internal_valve_regression",
    }:
        from . import internal_valve_regression as module

        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
