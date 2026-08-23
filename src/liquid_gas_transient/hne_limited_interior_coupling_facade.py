"""Corrected public facade for the P2-A3.1 limited interior coupling slice.

Two integration details are normalized here without changing the candidate EOS
or solver equations:

* the Acoustic Authority Gate exposes its effective grant as ``authority_grant``;
* the near-zero relaxation limit is compared with the recovered equilibrium map
  used by the source itself, rather than the nominal constructor input.
"""
from __future__ import annotations

import numpy as np

from . import hne_limited_interior_coupling as _impl
from .hne_equilibrium_acoustic_closure import recover_equilibrium_state
from .state import IDX_RHO, IDX_RHO_XV, internal_energy, vapor_mass_fraction


_original_authority_analysis = _impl.analyze_acoustic_authority_gate


def _authority_analysis_with_compatibility_alias():
    summary, cases, eigenvalues = _original_authority_analysis()
    record = dict(summary)
    record["effective_authority_grant"] = record["authority_grant"]
    return record, cases, eigenvalues


def _run_equilibrium_limit_case(config: _impl.InteriorCouplingConfig):
    actual_q = config.equilibrium_quality + config.off_equilibrium_quality_offset
    solver = _impl.build_candidate_solver(
        config,
        actual_quality=actual_q,
        tau_s=1.0e-18,
    )
    initial_hydrodynamic_sha = _impl._array_sha(solver.U[..., :IDX_RHO_XV])
    rho0 = float(solver.U[0, IDX_RHO])
    e0 = float(internal_energy(solver.U)[0])
    equilibrium_target = recover_equilibrium_state(rho0, e0)
    dt = float(solver.compute_dt())
    solver.step(dt)
    final_q = np.asarray(vapor_mass_fraction(solver.U), dtype=float)
    equilibrium_q_error = float(
        np.max(np.abs(final_q - equilibrium_target.vapor_mass_fraction))
    )
    final_hydrodynamic_sha = _impl._array_sha(solver.U[..., :IDX_RHO_XV])
    primitive = solver.primitive()
    equilibrium_final = recover_equilibrium_state(
        float(solver.U[0, IDX_RHO]),
        float(internal_energy(solver.U)[0]),
    )
    return {
        "case_id": "TAU_NEAR_ZERO_EQUILIBRIUM_LIMIT",
        "property_backend_name": _impl.PROPERTY_BACKEND_NAME,
        "initial_actual_quality": actual_q,
        "final_quality": float(final_q[0]),
        "equilibrium_quality": equilibrium_target.vapor_mass_fraction,
        "nominal_constructor_quality": config.equilibrium_quality,
        "maximum_equilibrium_quality_error": equilibrium_q_error,
        "hydrodynamic_state_unchanged_by_uniform_step_and_relaxation": (
            initial_hydrodynamic_sha == final_hydrodynamic_sha
        ),
        "candidate_pressure_recovers_equilibrium_pressure": abs(
            float(primitive.p[0]) - equilibrium_final.pressure_pa
        ) <= 5.0e-4,
        "candidate_temperature_recovers_equilibrium_temperature": abs(
            float(primitive.T[0]) - equilibrium_final.temperature_K
        ) <= 2.0e-9,
        "solver_step_count": solver.step_count,
    }


_impl.analyze_acoustic_authority_gate = _authority_analysis_with_compatibility_alias
_impl._run_equilibrium_limit_case = _run_equilibrium_limit_case

AcousticCompatibleHNEVerificationEOS = _impl.AcousticCompatibleHNEVerificationEOS
CandidateQualityExactRelaxation = _impl.CandidateQualityExactRelaxation
CouplingAnalysis = _impl.CouplingAnalysis
FORMAL_OUTCOME = _impl.FORMAL_OUTCOME
FORMAL_STATUS = _impl.FORMAL_STATUS
HNELimitedInteriorCouplingError = _impl.HNELimitedInteriorCouplingError
IMPLEMENTATION_AUTHORITY = _impl.IMPLEMENTATION_AUTHORITY
InteriorCouplingConfig = _impl.InteriorCouplingConfig
NEXT_ACTION = _impl.NEXT_ACTION
OUTPUT_FILES = _impl.OUTPUT_FILES
PROPERTY_BACKEND_NAME = _impl.PROPERTY_BACKEND_NAME
SCHEMA_VERSION = _impl.SCHEMA_VERSION
SOURCE_AUTHORITY_GATE_RUN_ID = _impl.SOURCE_AUTHORITY_GATE_RUN_ID
SOURCE_AUTHORITY_GATE_SHA = _impl.SOURCE_AUTHORITY_GATE_SHA
analyze_limited_interior_coupling = _impl.analyze_limited_interior_coupling
build_candidate_solver = _impl.build_candidate_solver
execute = _impl.execute
main = _impl.main
write_artifacts = _impl.write_artifacts

__all__ = [
    "AcousticCompatibleHNEVerificationEOS",
    "CandidateQualityExactRelaxation",
    "CouplingAnalysis",
    "FORMAL_OUTCOME",
    "FORMAL_STATUS",
    "HNELimitedInteriorCouplingError",
    "IMPLEMENTATION_AUTHORITY",
    "InteriorCouplingConfig",
    "NEXT_ACTION",
    "OUTPUT_FILES",
    "PROPERTY_BACKEND_NAME",
    "SCHEMA_VERSION",
    "SOURCE_AUTHORITY_GATE_RUN_ID",
    "SOURCE_AUTHORITY_GATE_SHA",
    "analyze_limited_interior_coupling",
    "build_candidate_solver",
    "execute",
    "main",
    "write_artifacts",
]

if __name__ == "__main__":
    raise SystemExit(main())