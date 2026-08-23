"""Compatibility bridge for the A2.4-2R pressure-recovery name error.

The published A2.4-2R model contains a one-token variable-name typo inside
``_quality_from_pressure_energy``.  This module replaces only that helper in the
original module namespace and re-exports the existing public model functions.
No model equation, coefficient, claimed domain, or solver authority is changed.
"""

from __future__ import annotations

from . import hne_equilibrium_acoustic_model as _model
from .hne_equilibrium_acoustic_types import EquilibriumAcousticConfig


def _quality_from_pressure_energy(
    pressure_pa: float,
    e_j_kg: float,
    config: EquilibriumAcousticConfig,
) -> float:
    _, _, _, e_l, _, _, _ = _model._constituent_state(pressure_pa, config)
    return (e_j_kg - e_l) / config.latent_heat_j_kg


# The functions defined in the original module resolve this helper from their
# own module globals at call time.  Replacing that one global therefore repairs
# the typo without duplicating or altering the acoustic model implementation.
_model._quality_from_pressure_energy = _quality_from_pressure_energy

evaluate_equilibrium_acoustic = _model.evaluate_equilibrium_acoustic
recover_equilibrium_state = _model.recover_equilibrium_state
representative_cases = _model.representative_cases
state_from_pressure_quality = _model.state_from_pressure_quality

__all__ = [
    "evaluate_equilibrium_acoustic",
    "recover_equilibrium_state",
    "representative_cases",
    "state_from_pressure_quality",
]
