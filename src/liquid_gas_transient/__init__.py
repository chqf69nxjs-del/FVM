"""Liquid gas transient analysis package.

Phase 2 / Ver.0.2 focuses on a conservative finite-volume foundation.
"""

from .config import NumericsConfig, TimeConfig, PipeGeometry
from .grid import UniformGrid
from .state import PrimitiveState, make_conserved
from .eos import LCO2PropertyEOSAdapter, LinearLiquidEOS, StiffenedGasEOS, ToyHEMEOS
from .solver import FvmSolver
from .budget import BoundaryBudgetTracker
from .pump import ConstantPumpHead, LinearPumpTrip, PumpInletBoundary
from .properties import CoolPropCO2Backend, SurrogateLCO2PropertyBackend

__all__ = [
    "NumericsConfig",
    "TimeConfig",
    "PipeGeometry",
    "UniformGrid",
    "PrimitiveState",
    "make_conserved",
    "LinearLiquidEOS",
    "LCO2PropertyEOSAdapter",
    "StiffenedGasEOS",
    "ToyHEMEOS",
    "FvmSolver",
    "BoundaryBudgetTracker",
    "ConstantPumpHead",
    "LinearPumpTrip",
    "PumpInletBoundary",
    "CoolPropCO2Backend",
    "SurrogateLCO2PropertyBackend",
]

__version__ = '0.5.1'
