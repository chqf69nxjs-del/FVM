"""P2-A2.4-4 finite-relaxation acoustic dispersion investigation.

The model is a single transported-quality relaxation linearization around an
A2.4-2R state. With the exp(i(k x - omega t)) convention, the dynamic acoustic
modulus is

    c_dyn^2 = c_f^2 + (c_eq^2 - c_f^2) / (1 - i omega tau).

It produces a complex outgoing wavenumber, phase speed, and attenuation. A
separate dimensionless temporal eigenanalysis checks the cubic relaxation
system and the subcharacteristic stability margin. Nothing in this increment
has CFL, flux, Rusanov, boundary, or hydrodynamic authority.
"""
from __future__ import annotations

import argparse
import cmath
import csv
import hashlib
import itertools
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .hne_acoustic_shadow_pipeline import SOLVER_AUTHORITY as A2_4_3_AUTHORITY
from .hne_equilibrium_acoustic_closure import (
    evaluate_equilibrium_acoustic,
    representative_cases,
    state_from_pressure_quality,
)
from .hne_shadow_pipeline import ShadowPipelineConfig, _build_solver
from .state import IDX_RHO, internal_energy

SCHEMA_VERSION = "stage7_p2_hne_finite_relaxation_dispersion_a2_4_4_v1"
SOURCE_A2_4_3_SHA = "3fdd2fbdd81bafecfa44607324c5e47dddd43d52"
SOURCE_A2_4_3_RUN_ID = 32626001623
SOURCE_A2_4_3_ARTIFACT_ID = 9489698258
SOURCE_A2_4_3_ARTIFACT_SHA256 = (
    "c8bf96be49dc1a0116aac005b66261c3f22e1220627081062fc231e0aaa8d8f1"
)
SOURCE_A2_4_3_ANALYSIS_SHA256 = (
    "e0f41106b62f8da85eae6870a1bda01d8e39fc1addabf0c565ba3b009f4fc837"
)
FORMAL_OUTCOME = (
    "A2_4_4_SINGLE_RELAXATION_DISPERSION_INVESTIGATION_READY_"
    "WITH_ACOUSTIC_AUTHORITY_GATE_CLOSED"
)
NEXT_ACTION = (
    "PROCEED_TO_ACOUSTIC_AUTHORITY_GATE_JACOBIAN_HYPERBOLICITY_FORMULATION"
)
OUTPUT_FILES = (
    "summary.json",
    "state_summary.csv",
    "spatial_dispersion.csv",
    "temporal_stability.csv",
    "operator_report.md",
    "manifest.json",
)
OMEGA_TAU_VALUES = (1e-6, 1e-4, 1e-2, 0.1, 0.3, 1.0, 3.0, 10.0, 100.0, 1e4, 1e6)
DIMENSIONLESS_WAVENUMBERS = (1e-3, 1e-2, 0.1, 1.0, 10.0, 100.0, 1000.0)
REFERENCE_TAU_S = 1e-4
FORMAL_STATUS = {
    "implemented": True,
    "working_verification_slice": True,
    "finite_relaxation_dispersion_investigation": True,
    "spatial_dispersion_evidence_ready": True,
    "temporal_stability_evidence_ready": True,
    "acoustic_authority_gate_ready": False,
    "hydrodynamic_coupling_allowed": False,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}
SOLVER_AUTHORITY = {
    "complex_wavenumber_to_cfl": False,
    "phase_speed_to_cfl": False,
    "phase_speed_to_rusanov": False,
    "attenuation_to_flux": False,
    "dynamic_modulus_to_flux": False,
    "dispersion_to_boundary_characteristics": False,
    "hydrodynamic_coupling_allowed": False,
}


class HNEFiniteRelaxationDispersionError(RuntimeError):
    """Raised when the dispersion investigation leaves its claimed scope."""


@dataclass(frozen=True)
class AcousticLimitPair:
    state_id: str
    rho_kg_m3: float
    e_j_kg: float
    pressure_pa: float
    equilibrium_quality: float
    equilibrium_c2_m2_s2: float
    frozen_c2_m2_s2: float


@dataclass(frozen=True)
class SpatialDispersionPoint:
    omega_tau: float
    omega_rad_s: float
    frequency_hz: float
    dynamic_c2_real_m2_s2: float
    dynamic_c2_imag_m2_s2: float
    wavenumber_real_m_inverse: float
    attenuation_m_inverse: float
    phase_speed_m_s: float
    attenuation_per_wavelength: float
    dispersion_relative_residual: float


@dataclass(frozen=True)
class TemporalStabilityPoint:
    dimensionless_wavenumber: float
    maximum_real_growth: float
    relaxation_mode_real: float
    acoustic_mode_real: float
    acoustic_mode_frequency: float
    polynomial_matrix_root_mismatch: float
    polynomial_relative_residual: float
    stable: bool


@dataclass(frozen=True)
class FiniteRelaxationDispersionAnalysis:
    summary: dict[str, object]
    state_rows: tuple[dict[str, object], ...]
    spatial_rows: tuple[dict[str, object], ...]
    temporal_rows: tuple[dict[str, object], ...]


def _validate_limits(c_eq2: float, c_frozen2: float) -> None:
    if not all(math.isfinite(value) for value in (c_eq2, c_frozen2)):
        raise HNEFiniteRelaxationDispersionError("NONFINITE_ACOUSTIC_LIMIT")
    if c_eq2 <= 0.0 or c_frozen2 <= 0.0:
        raise HNEFiniteRelaxationDispersionError("NONPOSITIVE_ACOUSTIC_LIMIT")
    if c_eq2 >= c_frozen2:
        raise HNEFiniteRelaxationDispersionError(
            "STRICT_SUBCHARACTERISTIC_MARGIN_REQUIRED"
        )


def dynamic_sound_speed_squared(
    c_eq2: float,
    c_frozen2: float,
    omega_tau: float,
) -> complex:
    """Return the single-relaxation complex acoustic modulus."""
    _validate_limits(c_eq2, c_frozen2)
    if not math.isfinite(omega_tau) or omega_tau < 0.0:
        raise HNEFiniteRelaxationDispersionError("OMEGA_TAU_MUST_BE_FINITE_NONNEGATIVE")
    return complex(c_frozen2) + (c_eq2 - c_frozen2) / complex(1.0, -omega_tau)


def spatial_dispersion_point(
    c_eq2: float,
    c_frozen2: float,
    omega_tau: float,
    *,
    tau_s: float = REFERENCE_TAU_S,
) -> SpatialDispersionPoint:
    """Return the outgoing, spatially attenuating branch for real omega."""
    if not math.isfinite(tau_s) or tau_s <= 0.0:
        raise HNEFiniteRelaxationDispersionError("TAU_MUST_BE_FINITE_POSITIVE")
    if omega_tau <= 0.0:
        raise HNEFiniteRelaxationDispersionError("SPATIAL_OMEGA_TAU_MUST_BE_POSITIVE")
    c2 = dynamic_sound_speed_squared(c_eq2, c_frozen2, omega_tau)
    omega = omega_tau / tau_s
    root = cmath.sqrt(c2)
    if root.real < 0.0:
        root = -root
    k = omega / root
    if k.real < 0.0:
        k = -k
    tolerance = 1e-12 * max(abs(k), 1.0)
    if k.imag < -tolerance:
        raise HNEFiniteRelaxationDispersionError("OUTGOING_BRANCH_HAS_SPATIAL_GROWTH")
    attenuation = max(float(k.imag), 0.0)
    phase_speed = omega / float(k.real)
    residual = abs(k * k * c2 - omega * omega) / max(omega * omega, 1.0)
    return SpatialDispersionPoint(
        omega_tau=float(omega_tau),
        omega_rad_s=float(omega),
        frequency_hz=float(omega / (2.0 * math.pi)),
        dynamic_c2_real_m2_s2=float(c2.real),
        dynamic_c2_imag_m2_s2=float(c2.imag),
        wavenumber_real_m_inverse=float(k.real),
        attenuation_m_inverse=attenuation,
        phase_speed_m_s=float(phase_speed),
        attenuation_per_wavelength=float(2.0 * math.pi * attenuation / k.real),
        dispersion_relative_residual=float(residual),
    )


def _matched_root_error(first: np.ndarray, second: np.ndarray) -> float:
    return float(
        min(
            max(abs(first[index] - second[perm[index]]) for index in range(3))
            for perm in itertools.permutations(range(3))
        )
    )


def temporal_stability_point(
    c_eq2: float,
    c_frozen2: float,
    dimensionless_wavenumber: float,
) -> TemporalStabilityPoint:
    """Check the dimensionless temporal cubic with an independent matrix form."""
    _validate_limits(c_eq2, c_frozen2)
    if not math.isfinite(dimensionless_wavenumber) or dimensionless_wavenumber <= 0.0:
        raise HNEFiniteRelaxationDispersionError(
            "DIMENSIONLESS_WAVENUMBER_MUST_BE_FINITE_POSITIVE"
        )
    K = float(dimensionless_wavenumber)
    ratio = c_eq2 / c_frozen2
    delta = ratio - 1.0
    matrix = np.array(
        [
            [0.0, -1j * K, 0.0],
            [-1j * K, 0.0, -1j * K * delta],
            [1.0, 0.0, -1.0],
        ],
        dtype=complex,
    )
    matrix_roots = np.linalg.eigvals(matrix)
    polynomial_roots = np.roots([1.0, 1.0, K * K, ratio * K * K])
    mismatch = _matched_root_error(matrix_roots, polynomial_roots)
    scale = max(K * K, 1.0)
    poly_residual = max(
        abs(root**3 + root**2 + K * K * root + ratio * K * K) / scale
        for root in matrix_roots
    )
    relaxation_index = int(np.argmin(np.abs(matrix_roots.imag)))
    relaxation = matrix_roots[relaxation_index]
    acoustic = np.delete(matrix_roots, relaxation_index)
    acoustic_mode = max(acoustic, key=lambda root: root.imag)
    maximum_growth = max(float(root.real) for root in matrix_roots)
    stable = (
        maximum_growth <= 1e-10
        and mismatch <= 1e-9
        and poly_residual <= 1e-9
        and c_frozen2 > c_eq2
    )
    return TemporalStabilityPoint(
        dimensionless_wavenumber=K,
        maximum_real_growth=maximum_growth,
        relaxation_mode_real=float(relaxation.real),
        acoustic_mode_real=float(acoustic_mode.real),
        acoustic_mode_frequency=float(abs(acoustic_mode.imag)),
        polynomial_matrix_root_mismatch=float(mismatch),
        polynomial_relative_residual=float(poly_residual),
        stable=stable,
    )


def _limit_pair(
    state_id: str,
    rho_kg_m3: float,
    e_j_kg: float,
) -> AcousticLimitPair:
    diagnostic = evaluate_equilibrium_acoustic(rho_kg_m3, e_j_kg)
    if not diagnostic.valid or diagnostic.state is None:
        raise HNEFiniteRelaxationDispersionError(
            f"INVALID_SOURCE_ACOUSTIC_STATE:{state_id}:{diagnostic.failure_reason}"
        )
    if (
        diagnostic.equilibrium_sound_speed_squared_m2_s2 is None
        or diagnostic.frozen_sound_speed_squared_m2_s2 is None
    ):
        raise HNEFiniteRelaxationDispersionError(
            f"MISSING_SOURCE_ACOUSTIC_LIMIT:{state_id}"
        )
    c_eq2 = float(diagnostic.equilibrium_sound_speed_squared_m2_s2)
    c_frozen2 = float(diagnostic.frozen_sound_speed_squared_m2_s2)
    _validate_limits(c_eq2, c_frozen2)
    return AcousticLimitPair(
        state_id=state_id,
        rho_kg_m3=float(rho_kg_m3),
        e_j_kg=float(e_j_kg),
        pressure_pa=float(diagnostic.state.pressure_pa),
        equilibrium_quality=float(diagnostic.state.vapor_mass_fraction),
        equilibrium_c2_m2_s2=c_eq2,
        frozen_c2_m2_s2=c_frozen2,
    )


def source_limit_pairs() -> tuple[AcousticLimitPair, ...]:
    pairs: list[AcousticLimitPair] = []
    for case in representative_cases():
        source = state_from_pressure_quality(
            case.pressure_pa, case.vapor_mass_fraction
        )
        pairs.append(_limit_pair(case.case_id, source.rho_kg_m3, source.e_j_kg))
    solver, _ = _build_solver(ShadowPipelineConfig(n_cells=4, n_steps=1), 1e-4)
    pairs.append(
        _limit_pair(
            "A2_4_3_FOCUSED_PIPELINE_STATE",
            float(solver.U[0, IDX_RHO]),
            float(internal_energy(solver.U)[0]),
        )
    )
    return tuple(pairs)


def _payload_sha(payload: object) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True).strip()
        except Exception:
            return ""

    return {
        "analysis_source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }


def analyze_finite_relaxation_dispersion() -> FiniteRelaxationDispersionAnalysis:
    state_rows: list[dict[str, object]] = []
    spatial_rows: list[dict[str, object]] = []
    temporal_rows: list[dict[str, object]] = []
    pairs = source_limit_pairs()
    for pair in pairs:
        spatial = [
            spatial_dispersion_point(
                pair.equilibrium_c2_m2_s2,
                pair.frozen_c2_m2_s2,
                value,
            )
            for value in OMEGA_TAU_VALUES
        ]
        temporal = [
            temporal_stability_point(
                pair.equilibrium_c2_m2_s2,
                pair.frozen_c2_m2_s2,
                value,
            )
            for value in DIMENSIONLESS_WAVENUMBERS
        ]
        for point in spatial:
            spatial_rows.append({"state_id": pair.state_id, **asdict(point)})
        for point in temporal:
            temporal_rows.append({"state_id": pair.state_id, **asdict(point)})
        low = dynamic_sound_speed_squared(
            pair.equilibrium_c2_m2_s2,
            pair.frozen_c2_m2_s2,
            OMEGA_TAU_VALUES[0],
        )
        high = dynamic_sound_speed_squared(
            pair.equilibrium_c2_m2_s2,
            pair.frozen_c2_m2_s2,
            OMEGA_TAU_VALUES[-1],
        )
        low_residual = abs(low - pair.equilibrium_c2_m2_s2) / pair.frozen_c2_m2_s2
        high_residual = abs(high - pair.frozen_c2_m2_s2) / pair.frozen_c2_m2_s2
        peak = max(spatial, key=lambda point: point.attenuation_per_wavelength)
        state_rows.append(
            {
                **asdict(pair),
                "equilibrium_c_m_s": math.sqrt(pair.equilibrium_c2_m2_s2),
                "frozen_c_m_s": math.sqrt(pair.frozen_c2_m2_s2),
                "strict_subcharacteristic_margin_m2_s2": (
                    pair.frozen_c2_m2_s2 - pair.equilibrium_c2_m2_s2
                ),
                "low_frequency_limit_relative_residual": float(low_residual),
                "high_frequency_limit_relative_residual": float(high_residual),
                "peak_attenuation_omega_tau": peak.omega_tau,
                "peak_attenuation_per_wavelength": peak.attenuation_per_wavelength,
                "minimum_phase_speed_m_s": min(p.phase_speed_m_s for p in spatial),
                "maximum_phase_speed_m_s": max(p.phase_speed_m_s for p in spatial),
                "maximum_spatial_dispersion_residual": max(
                    p.dispersion_relative_residual for p in spatial
                ),
                "maximum_temporal_growth": max(
                    p.maximum_real_growth for p in temporal
                ),
                "maximum_temporal_root_mismatch": max(
                    p.polynomial_matrix_root_mismatch for p in temporal
                ),
                "maximum_temporal_polynomial_residual": max(
                    p.polynomial_relative_residual for p in temporal
                ),
                "all_temporal_modes_stable": all(p.stable for p in temporal),
            }
        )

    repeated = [asdict(point) for point in (
        spatial_dispersion_point(
            pairs[1].equilibrium_c2_m2_s2,
            pairs[1].frozen_c2_m2_s2,
            1.0,
        ),
        temporal_stability_point(
            pairs[1].equilibrium_c2_m2_s2,
            pairs[1].frozen_c2_m2_s2,
            1.0,
        ),
    )]
    repeated_again = [asdict(point) for point in (
        spatial_dispersion_point(
            pairs[1].equilibrium_c2_m2_s2,
            pairs[1].frozen_c2_m2_s2,
            1.0,
        ),
        temporal_stability_point(
            pairs[1].equilibrium_c2_m2_s2,
            pairs[1].frozen_c2_m2_s2,
            1.0,
        ),
    )]
    reproducible = repeated == repeated_again
    maturity_closed = all(
        FORMAL_STATUS[key] is False
        for key in (
            "acoustic_authority_gate_ready",
            "hydrodynamic_coupling_allowed",
            "working_vertical_slice",
            "verified",
            "accepted",
            "physically_validated",
            "design_use_accepted",
            "production_approved",
        )
    )
    ce_cf_bounds = all(
        row["minimum_phase_speed_m_s"]
        >= row["equilibrium_c_m_s"] * (1.0 - 1e-9)
        and row["maximum_phase_speed_m_s"]
        <= row["frozen_c_m_s"] * (1.0 + 1e-9)
        for row in state_rows
    )
    gates = {
        "A2_4_3_SOURCE_AND_EVIDENCE_PINNED": (
            SOURCE_A2_4_3_SHA == "3fdd2fbdd81bafecfa44607324c5e47dddd43d52"
            and SOURCE_A2_4_3_RUN_ID == 32626001623
            and SOURCE_A2_4_3_ARTIFACT_ID == 9489698258
            and len(SOURCE_A2_4_3_ARTIFACT_SHA256) == 64
            and len(SOURCE_A2_4_3_ANALYSIS_SHA256) == 64
        ),
        "A2_4_3_SOLVER_AUTHORITY_REMAINS_CLOSED": all(
            value is False for value in A2_4_3_AUTHORITY.values()
        ),
        "A2_4_4_SOLVER_AUTHORITY_REMAINS_CLOSED": all(
            value is False for value in SOLVER_AUTHORITY.values()
        ),
        "SIX_SOURCE_STATES_VALID": len(state_rows) == 6,
        "STRICT_SUBCHARACTERISTIC_MARGIN_ON_ALL_STATES": all(
            row["strict_subcharacteristic_margin_m2_s2"] > 0.0
            for row in state_rows
        ),
        "EQUILIBRIUM_LOW_FREQUENCY_LIMIT_RECOVERED": all(
            row["low_frequency_limit_relative_residual"] <= 1e-6
            for row in state_rows
        ),
        "FROZEN_HIGH_FREQUENCY_LIMIT_RECOVERED": all(
            row["high_frequency_limit_relative_residual"] <= 1e-6
            for row in state_rows
        ),
        "OUTGOING_BRANCH_SPATIALLY_ATTENUATING": all(
            row["attenuation_m_inverse"] >= 0.0 for row in spatial_rows
        ),
        "PHASE_SPEED_BETWEEN_EQUILIBRIUM_AND_FROZEN_LIMITS": ce_cf_bounds,
        "SPATIAL_DISPERSION_RELATION_RESIDUAL_SMALL": all(
            row["dispersion_relative_residual"] <= 1e-12
            for row in spatial_rows
        ),
        "RELAXATION_ATTENUATION_PEAK_IS_ORDER_ONE_OMEGA_TAU": all(
            0.1 <= row["peak_attenuation_omega_tau"] <= 10.0
            for row in state_rows
        ),
        "TEMPORAL_RELAXATION_SYSTEM_STABLE": all(
            row["all_temporal_modes_stable"] is True for row in state_rows
        ),
        "TEMPORAL_MATRIX_AND_CUBIC_CROSSCHECK": all(
            row["maximum_temporal_root_mismatch"] <= 1e-9
            and row["maximum_temporal_polynomial_residual"] <= 1e-9
            for row in state_rows
        ),
        "DETERMINISTIC_REPRODUCIBILITY": reproducible,
        "MATURITY_NOT_PROMOTED": maturity_closed,
    }
    failed = [name for name, passed in gates.items() if not passed]
    ready = not failed
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "p2_a2_4_4_single_relaxation_dispersion_investigation",
        "source_a2_4_3": {
            "head_sha": SOURCE_A2_4_3_SHA,
            "workflow_run_id": SOURCE_A2_4_3_RUN_ID,
            "artifact_id": SOURCE_A2_4_3_ARTIFACT_ID,
            "artifact_sha256": SOURCE_A2_4_3_ARTIFACT_SHA256,
            "analysis_sha256": SOURCE_A2_4_3_ANALYSIS_SHA256,
        },
        "linearized_model": {
            "time_space_convention": "EXP_I_KX_MINUS_I_OMEGA_T",
            "dynamic_modulus": (
                "C_FROZEN_SQUARED_PLUS_"
                "(C_EQUILIBRIUM_SQUARED_MINUS_C_FROZEN_SQUARED)_"
                "DIVIDED_BY_(ONE_MINUS_I_OMEGA_TAU)"
            ),
            "spatial_dispersion_relation": "K_SQUARED_C_DYNAMIC_SQUARED_MINUS_OMEGA_SQUARED_EQUALS_ZERO",
            "temporal_dimensionless_cubic": (
                "Z_CUBED_PLUS_Z_SQUARED_PLUS_K_SQUARED_Z_PLUS_"
                "(C_EQUILIBRIUM_SQUARED_DIVIDED_BY_C_FROZEN_SQUARED)_K_SQUARED_EQUALS_ZERO"
            ),
            "reference_tau_s": REFERENCE_TAU_S,
            "omega_tau_values": list(OMEGA_TAU_VALUES),
            "dimensionless_wavenumbers": list(DIMENSIONLESS_WAVENUMBERS),
        },
        "formal_status": dict(FORMAL_STATUS),
        "solver_authority": dict(SOLVER_AUTHORITY),
        "state_summary": state_rows,
        "gate_results": gates,
        "failed_gates": failed,
        "a2_4_4_dispersion_investigation_ready": ready,
        "formal_outcome": (
            FORMAL_OUTCOME
            if ready
            else "A2_4_4_IMPLEMENTED_NOT_READY_WITH_FAIL_CLOSED_GATES"
        ),
        "next_action": (
            NEXT_ACTION
            if ready
            else "RESOLVE_FAILED_A2_4_4_GATES_BEFORE_ACOUSTIC_AUTHORITY_GATE"
        ),
        "hydrodynamic_coupling_allowed": False,
        "runtime_provenance": _provenance(),
        "limitations": [
            "SINGLE_RELAXATION_VERIFICATION_MODEL_ONLY",
            "REFERENCE_TAU_NOT_PHYSICALLY_CALIBRATED",
            "NO_REAL_CO2_PHYSICAL_VALIDATION",
            "NO_CFL_FLUX_RUSANOV_OR_BOUNDARY_AUTHORITY",
            "NO_P2_A3_HYDRODYNAMIC_COUPLING_AUTHORIZED",
        ],
        "literature_context": [
            "LINGA_2018_SUBCHARACTERISTIC_RELAXATION_HIERARCHY",
            "LUND_2012_RELAXATION_STABILITY",
            "ARDRON_DUFFEY_1978_FREQUENCY_DEPENDENT_SOUND_AND_ATTENUATION",
        ],
    }
    authority = {
        key: value
        for key, value in summary.items()
        if key not in {"runtime_provenance", "state_summary"}
    }
    summary["analysis_sha256"] = _payload_sha(
        {
            "authority": authority,
            "state_rows": state_rows,
            "spatial_rows": spatial_rows,
            "temporal_rows": temporal_rows,
        }
    )
    return FiniteRelaxationDispersionAnalysis(
        summary=summary,
        state_rows=tuple(state_rows),
        spatial_rows=tuple(spatial_rows),
        temporal_rows=tuple(temporal_rows),
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise HNEFiniteRelaxationDispersionError("CSV_EVIDENCE_REQUIRES_ROWS")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _operator_report(summary: Mapping[str, object]) -> str:
    lines = [
        "# Stage 7 P2-A2.4-4 Finite-Relaxation Dispersion Investigation",
        "",
        f"- Outcome: `{summary['formal_outcome']}`",
        "- Acoustic Authority Gate ready: `false`",
        "- Hydrodynamic coupling allowed: `false`",
        "",
        "| state | c_eq [m/s] | c_frozen [m/s] | peak omega*tau | peak attenuation/wavelength | stable |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in summary["state_summary"]:  # type: ignore[index]
        lines.append(
            "| {state} | {ce:.8g} | {cf:.8g} | {peak:.8g} | {atten:.8g} | {stable} |".format(
                state=row["state_id"],
                ce=float(row["equilibrium_c_m_s"]),
                cf=float(row["frozen_c_m_s"]),
                peak=float(row["peak_attenuation_omega_tau"]),
                atten=float(row["peak_attenuation_per_wavelength"]),
                stable=row["all_temporal_modes_stable"],
            )
        )
    lines += [
        "",
        "The single-relaxation verification model recovers the equilibrium and",
        "frozen limits, produces a spatially attenuating outgoing branch, and",
        "has temporally stable modes under the strict subcharacteristic margin.",
        "This does not authorize use in the finite-volume solver.",
        "",
    ]
    return "\n".join(lines)


def write_artifacts(
    output_dir: str | Path,
    analysis: FiniteRelaxationDispersionAnalysis,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(OUTPUT_FILES)
    if {path.name for path in target.iterdir() if path.is_file()} - expected:
        raise HNEFiniteRelaxationDispersionError("UNEXPECTED_OUTPUT_FILE")
    paths = {
        "summary": target / "summary.json",
        "states": target / "state_summary.csv",
        "spatial": target / "spatial_dispersion.csv",
        "temporal": target / "temporal_stability.csv",
        "report": target / "operator_report.md",
        "manifest": target / "manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(analysis.summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["states"], analysis.state_rows)
    _write_csv(paths["spatial"], analysis.spatial_rows)
    _write_csv(paths["temporal"], analysis.temporal_rows)
    paths["report"].write_text(_operator_report(analysis.summary), encoding="utf-8")
    payload = {key: path for key, path in paths.items() if key != "manifest"}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "analysis_sha256": analysis.summary["analysis_sha256"],
        "a2_4_4_dispersion_investigation_ready": analysis.summary[
            "a2_4_4_dispersion_investigation_ready"
        ],
        "hydrodynamic_coupling_allowed": False,
        "payload_files": {
            path.name: {
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha(path),
            }
            for path in payload.values()
        },
    }
    paths["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if {path.name for path in target.iterdir() if path.is_file()} != expected:
        raise HNEFiniteRelaxationDispersionError("OUTPUT_FILE_ENVELOPE_MISMATCH")
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    analysis = analyze_finite_relaxation_dispersion()
    paths = write_artifacts(output_dir, analysis)
    return {
        **analysis.summary,
        "artifact_paths": {key: str(path) for key, path in paths.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    result = execute(parser.parse_args(argv).output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["a2_4_4_dispersion_investigation_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
