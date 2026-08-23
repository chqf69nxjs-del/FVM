"""P2-A2.4-2R equilibrium acoustic verification closure.

The implementation is split into types, analytic model, and evidence modules.
This facade keeps the public API and CLI stable. All acoustic quantities remain
read-only diagnostics with no FVM, CFL, flux, Rusanov, or boundary authority.
"""

from __future__ import annotations

from .hne_equilibrium_acoustic_types import (
    ACOUSTIC_AUTHORITY,
    DEFAULT_CONFIG,
    DERIVATIVE_METHOD,
    EquilibriumAcousticClosureError,
    EquilibriumAcousticConfig,
    EquilibriumAcousticDiagnostic,
    EquilibriumManifoldState,
    FORMAL_OUTCOME,
    FORMAL_STATUS,
    MODEL_FORM,
    NEXT_ACTION,
    PHASE_BRANCH,
    SCHEMA_VERSION,
    SOLVER_AUTHORITY,
    SOURCE_A2_4_1_SHA,
    VerificationCase,
)
from .hne_equilibrium_acoustic_model_compat import (
    evaluate_equilibrium_acoustic,
    recover_equilibrium_state,
    representative_cases,
    state_from_pressure_quality,
)
from .hne_equilibrium_acoustic_evidence import (
    evaluate_focused_gates,
    main,
    write_evidence,
)

__all__ = [
    "ACOUSTIC_AUTHORITY",
    "DEFAULT_CONFIG",
    "DERIVATIVE_METHOD",
    "EquilibriumAcousticClosureError",
    "EquilibriumAcousticConfig",
    "EquilibriumAcousticDiagnostic",
    "EquilibriumManifoldState",
    "FORMAL_OUTCOME",
    "FORMAL_STATUS",
    "MODEL_FORM",
    "NEXT_ACTION",
    "PHASE_BRANCH",
    "SCHEMA_VERSION",
    "SOLVER_AUTHORITY",
    "SOURCE_A2_4_1_SHA",
    "VerificationCase",
    "evaluate_equilibrium_acoustic",
    "evaluate_focused_gates",
    "recover_equilibrium_state",
    "representative_cases",
    "state_from_pressure_quality",
    "write_evidence",
]

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
