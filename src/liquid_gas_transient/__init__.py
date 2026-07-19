"""Liquid gas transient analysis package.

Phase 2 / Ver.0.2 focuses on a conservative finite-volume foundation. Public
exports are resolved lazily so independent verification submodules can be imported
without implicitly loading the production solver, boundary stack, or property
backends.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "NumericsConfig": (".config", "NumericsConfig"),
    "TimeConfig": (".config", "TimeConfig"),
    "PipeGeometry": (".config", "PipeGeometry"),
    "UniformGrid": (".grid", "UniformGrid"),
    "PrimitiveState": (".state", "PrimitiveState"),
    "make_conserved": (".state", "make_conserved"),
    "LCO2PropertyEOSAdapter": (".eos", "LCO2PropertyEOSAdapter"),
    "LinearLiquidEOS": (".eos", "LinearLiquidEOS"),
    "StiffenedGasEOS": (".eos", "StiffenedGasEOS"),
    "ToyHEMEOS": (".eos", "ToyHEMEOS"),
    "FvmSolver": (".solver", "FvmSolver"),
    "BoundaryBudgetTracker": (".budget", "BoundaryBudgetTracker"),
    "ConstantPumpHead": (".pump", "ConstantPumpHead"),
    "LinearPumpTrip": (".pump", "LinearPumpTrip"),
    "PumpInletBoundary": (".pump", "PumpInletBoundary"),
    "CoolPropCO2Backend": (".properties", "CoolPropCO2Backend"),
    "SurrogateLCO2PropertyBackend": (
        ".properties",
        "SurrogateLCO2PropertyBackend",
    ),
    "generate_coolprop_small_amplitude_wave_verification_report": (
        ".reporting_wave_verification",
        "generate_coolprop_small_amplitude_wave_verification_report",
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


__version__ = "0.5.1"
