"""P2 HNE acoustic authority gate public API and CLI."""
from __future__ import annotations

from .hne_acoustic_authority_types import (
    CURRENT_SOLVER_EFFECT, FORMAL_OUTCOME, FORMAL_STATUS, NEXT_ACTION,
    OUTPUT_FILES, PROPOSED_AUTHORITY_GRANT, SCHEMA_VERSION,
    SOURCE_A2_4_4_ANALYSIS_SHA256, SOURCE_A2_4_4_ARTIFACT_ID,
    SOURCE_A2_4_4_ARTIFACT_SHA256, SOURCE_A2_4_4_RUN_ID,
    SOURCE_A2_4_4_SHA, AcousticCompatibleHNEVerificationEOS,
    AcousticCompatibleState, HNEAcousticAuthorityGateError,
)
from .hne_acoustic_authority_jacobian import (
    AuthorityCase, analytic_flux_jacobian, authority_cases,
    candidate_conserved, independent_physical_flux, numerical_flux_jacobian,
)
from .hne_acoustic_authority_analysis import analyze_acoustic_authority_gate
from .hne_acoustic_authority_artifacts import execute, main, write_artifacts

__all__ = [
    "CURRENT_SOLVER_EFFECT", "FORMAL_OUTCOME", "FORMAL_STATUS", "NEXT_ACTION",
    "OUTPUT_FILES", "PROPOSED_AUTHORITY_GRANT", "SCHEMA_VERSION",
    "SOURCE_A2_4_4_ANALYSIS_SHA256", "SOURCE_A2_4_4_ARTIFACT_ID",
    "SOURCE_A2_4_4_ARTIFACT_SHA256", "SOURCE_A2_4_4_RUN_ID",
    "SOURCE_A2_4_4_SHA", "AcousticCompatibleHNEVerificationEOS",
    "AcousticCompatibleState", "HNEAcousticAuthorityGateError",
    "AuthorityCase", "analytic_flux_jacobian", "authority_cases",
    "candidate_conserved", "independent_physical_flux",
    "numerical_flux_jacobian", "analyze_acoustic_authority_gate",
    "execute", "write_artifacts",
]

if __name__ == "__main__":
    raise SystemExit(main())
