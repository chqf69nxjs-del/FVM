"""Case builders and runnable verification cases.

Public compatibility exports are loaded lazily so importing a pure case
specification does not also import production FVM case runners.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "CoolPropSmallAmplitudeWaveConfig": (
        ".coolprop_small_amplitude_wave",
        "CoolPropSmallAmplitudeWaveConfig",
    ),
    "build_coolprop_small_amplitude_wave_solver": (
        ".coolprop_small_amplitude_wave",
        "build_coolprop_small_amplitude_wave_solver",
    ),
    "run_coolprop_small_amplitude_wave": (
        ".coolprop_small_amplitude_wave",
        "run_coolprop_small_amplitude_wave",
    ),
    "CoolPropSmallAmplitudeWaveSweepConfig": (
        ".coolprop_small_amplitude_wave_sweep",
        "CoolPropSmallAmplitudeWaveSweepConfig",
    ),
    "run_coolprop_small_amplitude_wave_sweep": (
        ".coolprop_small_amplitude_wave_sweep",
        "run_coolprop_small_amplitude_wave_sweep",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve and cache one compatibility export on first access."""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
