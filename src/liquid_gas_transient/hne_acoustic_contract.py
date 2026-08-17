"""P2-A2.4-1 contract for nonequilibrium acoustic closure.

This increment defines the questions that must be answered before an HNE
acoustic quantity may influence the finite-volume solver.  It intentionally
implements no sound-speed formula and changes no FVM, EOS, flux, CFL, boundary,
or phase-source code.

Three regimes are separated:

* frozen quality: the acoustic disturbance is fast relative to phase relaxation;
* equilibrium manifold: phase relaxation is fast relative to the disturbance;
* finite relaxation: disturbance and relaxation time scales are comparable.

At finite relaxation, a single real scalar sound speed is not assumed.  A
frequency-dependent phase response and attenuation may be required.  Every
quantity in this increment therefore remains contract-only and non-authoritative.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Mapping, Sequence


SCHEMA_VERSION = "stage7_p2_hne_acoustic_contract_a2_4_1_v1"
SCOPE = "p2_a2_4_1_nonequilibrium_acoustic_closure_contract"
SOURCE_A2_3_CLOSEOUT_SHA = "4479d0ed4ee76975564e58cdfd152c2a9e554069"
SOURCE_A2_3_CLOSEOUT_RUN_ID = 32006617206
SOURCE_A2_3_CLOSEOUT_ARTIFACT_ID = 9280233147
SOURCE_A2_3_CLOSEOUT_ARTIFACT_SHA256 = (
    "85beec5faaef8715bdf5b7b2dee7687db8856a033aa0e1803ab23f2abb9debe6"
)
SOURCE_A2_3_SHA = "799edb09faa1502e25837c97fa5d168ad79e492e"
CONTRACT_OUTCOME = (
    "A2_4_1_ACOUSTIC_CONTRACT_READY_WITH_ALL_SOLVER_AUTHORITY_CLOSED"
)
NEXT_AUTHORIZED_ACTION = (
    "PROCEED_TO_A2_4_2_FROZEN_AND_EQUILIBRIUM_ACOUSTIC_DIAGNOSTIC_PROTOTYPES"
)
OUTPUT_FILES = (
    "summary.json",
    "regime_contracts.csv",
    "operator_report.md",
    "manifest.json",
)
REGIME_ORDER = (
    "FROZEN_QUALITY",
    "EQUILIBRIUM_MANIFOLD",
    "FINITE_RELAXATION_DISPERSIVE",
)

FORMAL_STATUS = {
    "implemented": True,
    "acoustic_contract_ready": True,
    "frozen_acoustic_formula_implemented": False,
    "equilibrium_acoustic_formula_implemented": False,
    "finite_relaxation_dispersion_implemented": False,
    "finite_pipeline_acoustic_shadow_ready": False,
    "hydrodynamic_coupling_allowed": False,
    "physical_hne_vertical_slice": False,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

SOLVER_AUTHORITY = {
    "frozen_candidate_to_flux": False,
    "frozen_candidate_to_cfl": False,
    "equilibrium_candidate_to_flux": False,
    "equilibrium_candidate_to_cfl": False,
    "finite_relaxation_candidate_to_flux": False,
    "finite_relaxation_candidate_to_cfl": False,
    "hne_boundary_characteristics_allowed": False,
    "hne_riemann_structure_allowed": False,
    "hydrodynamic_coupling_allowed": False,
}

REGIME_CONTRACTS = {
    "FROZEN_QUALITY": {
        "regime_id": "FROZEN_QUALITY",
        "disturbance_relaxation_ordering": (
            "DISTURBANCE_TIME_MUCH_SHORTER_THAN_PHASE_RELAXATION_TIME"
        ),
        "frequency_ordering": "OMEGA_TAU_MUCH_GREATER_THAN_ONE",
        "quality_response": "DELTA_Q_EQUALS_ZERO_DURING_PERTURBATION",
        "thermodynamic_path": (
            "MUST_DECLARE_ENERGY_OR_ENTROPY_CONSTRAINT_WITH_Q_FIXED"
        ),
        "derivative_contract": (
            "C_FROZEN_SQUARED_REQUIRES_A_DECLARED_CONSTRAINED_PRESSURE_DENSITY_DERIVATIVE"
        ),
        "required_outputs": [
            "C_FROZEN_SQUARED_CANDIDATE",
            "DERIVATIVE_PATH_LABEL",
            "POSITIVITY_RESULT",
            "HYPERBOLICITY_RESULT",
        ],
        "required_limit": "TAU_TO_INFINITY_OR_HIGH_FREQUENCY_LIMIT",
        "single_real_scalar_c_authorized": False,
        "solver_authority": "NONE_CONTRACT_ONLY",
    },
    "EQUILIBRIUM_MANIFOLD": {
        "regime_id": "EQUILIBRIUM_MANIFOLD",
        "disturbance_relaxation_ordering": (
            "PHASE_RELAXATION_TIME_MUCH_SHORTER_THAN_DISTURBANCE_TIME"
        ),
        "frequency_ordering": "OMEGA_TAU_MUCH_LESS_THAN_ONE",
        "quality_response": "Q_FOLLOWS_DECLARED_EQUILIBRIUM_MANIFOLD",
        "thermodynamic_path": (
            "MUST_DECLARE_THE_EQUILIBRIUM_MANIFOLD_AND_ENERGY_OR_ENTROPY_CONSTRAINT"
        ),
        "derivative_contract": (
            "C_EQUILIBRIUM_SQUARED_REQUIRES_A_DERIVATIVE_TANGENT_TO_THE_DECLARED_EQUILIBRIUM_MANIFOLD"
        ),
        "required_outputs": [
            "C_EQUILIBRIUM_SQUARED_CANDIDATE",
            "EQUILIBRIUM_MANIFOLD_LABEL",
            "HEM_LIMIT_RESIDUAL",
            "POSITIVITY_RESULT",
            "HYPERBOLICITY_RESULT",
        ],
        "required_limit": "TAU_TO_ZERO_OR_LOW_FREQUENCY_HEM_LIMIT",
        "single_real_scalar_c_authorized": False,
        "solver_authority": "NONE_CONTRACT_ONLY",
    },
    "FINITE_RELAXATION_DISPERSIVE": {
        "regime_id": "FINITE_RELAXATION_DISPERSIVE",
        "disturbance_relaxation_ordering": (
            "DISTURBANCE_AND_PHASE_RELAXATION_TIME_SCALES_COMPARABLE"
        ),
        "frequency_ordering": "OMEGA_TAU_ORDER_ONE",
        "quality_response": (
            "DELTA_Q_IS_DYNAMIC_AND_MAY_LAG_THE_THERMODYNAMIC_PERTURBATION"
        ),
        "thermodynamic_path": (
            "MUST_LINEARIZE_THE_COUPLED_CONSERVATION_AND_RELAXATION_SYSTEM"
        ),
        "derivative_contract": (
            "A_SINGLE_STATIC_PRESSURE_DENSITY_DERIVATIVE_IS_NOT_SUFFICIENT"
        ),
        "required_outputs": [
            "ANGULAR_FREQUENCY_OR_DISTURBANCE_TIME_SCALE",
            "COMPLEX_WAVENUMBER_OR_EQUIVALENT_TRANSFER_RESPONSE",
            "PHASE_SPEED",
            "ATTENUATION_RATE",
            "FROZEN_LIMIT_RESIDUAL",
            "EQUILIBRIUM_LIMIT_RESIDUAL",
            "STABILITY_RESULT",
        ],
        "required_limit": "CONNECT_FROZEN_AND_EQUILIBRIUM_LIMITS",
        "single_real_scalar_c_authorized": False,
        "solver_authority": "NONE_CONTRACT_ONLY",
    },
}

REQUIRED_EVIDENCE = (
    "STATE_AND_BACKEND_SCOPE_DECLARED",
    "PERTURBATION_PATH_DECLARED",
    "ENERGY_OR_ENTROPY_CONSTRAINT_DECLARED",
    "INDEPENDENT_DERIVATIVE_CROSS_CHECK",
    "FINITE_AND_POSITIVE_C_SQUARED_WHERE_A_REAL_CANDIDATE_IS_CLAIMED",
    "HYPERBOLICITY_OR_DISPERSION_STABILITY_CHECK",
    "TAU_TO_ZERO_HEM_LIMIT",
    "TAU_TO_INFINITY_FROZEN_LIMIT",
    "SUBCHARACTERISTIC_CONDITION_CHECK_WHERE_APPLICABLE",
    "FINITE_RELAXATION_PHASE_SPEED_AND_ATTENUATION",
    "BACKEND_PARAMETER_COHERENCE",
    "NO_BRANCH_CHATTER_OR_DERIVATIVE_PATH_SWITCHING",
    "DETERMINISTIC_REPRODUCIBILITY",
    "FINITE_PIPELINE_READ_ONLY_ACOUSTIC_SHADOW_BEFORE_COUPLING",
)

FAIL_CLOSED_CONDITIONS = (
    "THERMODYNAMIC_PERTURBATION_PATH_UNSPECIFIED",
    "ENERGY_OR_ENTROPY_CONSTRAINT_UNSPECIFIED",
    "FINITE_RELAXATION_FREQUENCY_OR_TIME_SCALE_UNSPECIFIED",
    "BACKEND_OR_PARAMETER_SET_MISMATCH",
    "STATE_NONFINITE_OR_OUTSIDE_DECLARED_SCOPE",
    "QUALITY_OUTSIDE_ZERO_TO_ONE",
    "DERIVATIVE_NONFINITE",
    "C_SQUARED_NONPOSITIVE_WHERE_REAL_HYPERBOLIC_C_IS_REQUIRED",
    "LOSS_OF_HYPERBOLICITY_OR_UNRESOLVED_UNSTABLE_MODE",
    "HEM_LIMIT_NOT_RECOVERED",
    "FROZEN_LIMIT_NOT_RECOVERED",
    "UNEXPLAINED_SUBCHARACTERISTIC_CONDITION_VIOLATION",
    "MULTIPLE_DERIVATIVE_BRANCHES_OR_BRANCH_CHATTER",
    "COMPLEX_FINITE_RELAXATION_RESPONSE_COLLAPSED_TO_UNJUSTIFIED_REAL_SCALAR",
    "ATTEMPTED_FLUX_CFL_OR_BOUNDARY_PROMOTION_WITHOUT_NEW_AUTHORITY_GATE",
)

LITERATURE_BASIS = (
    {
        "reference_id": "LINGA_2018_RELAXATION_HIERARCHY",
        "citation": (
            "G. Linga, A Hierarchy of Non-Equilibrium Two-Phase Flow Models, "
            "arXiv:1804.05241 (2018)"
        ),
        "contract_use": (
            "RELAXATION_HIERARCHY_AND_SUBCHARACTERISTIC_CONDITION_CONTEXT"
        ),
    },
    {
        "reference_id": "ARDRON_DUFFEY_1978_LIQUID_VAPOUR_ACOUSTICS",
        "citation": (
            "K. H. Ardron and R. B. Duffey, Acoustic wave propagation in a "
            "flowing liquid-vapour mixture, Int. J. Multiphase Flow 4 (1978) "
            "303-322, DOI 10.1016/0301-9322(78)90004-6"
        ),
        "contract_use": (
            "FREQUENCY_DEPENDENT_DISPERSION_AND_ATTENUATION_CONTEXT"
        ),
    },
    {
        "reference_id": "LUND_2012_RELAXATION_MODELS",
        "citation": (
            "H. Lund, A Hierarchy of Relaxation Models for Two-Phase Flow, "
            "SIAM J. Appl. Math. 72 (2012) 1713-1741, DOI 10.1137/12086368X"
        ),
        "contract_use": (
            "HYPERBOLIC_RELAXATION_AND_SUBCHARACTERISTIC_CONDITION_CONTEXT"
        ),
    },
)


class HNEAcousticContractError(RuntimeError):
    """Raised when the acoustic contract loses a required authority boundary."""


def _run_command(*args: str) -> str:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return ""


def runtime_provenance() -> dict[str, str]:
    return {
        "analysis_source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": _run_command("git", "rev-parse", "HEAD"),
        "git_status_porcelain": _run_command(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }


def _canonical_sha256(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def acoustic_contract_record() -> dict[str, object]:
    """Return a mutable copy of the static P2-A2.4-1 contract."""

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "source_closeout": {
            "a2_3_closeout_sha": SOURCE_A2_3_CLOSEOUT_SHA,
            "a2_3_closeout_workflow_run_id": SOURCE_A2_3_CLOSEOUT_RUN_ID,
            "a2_3_closeout_artifact_id": SOURCE_A2_3_CLOSEOUT_ARTIFACT_ID,
            "a2_3_closeout_artifact_sha256": (
                SOURCE_A2_3_CLOSEOUT_ARTIFACT_SHA256
            ),
            "a2_3_sha": SOURCE_A2_3_SHA,
            "closeout_conclusion": "success",
            "hydrodynamic_coupling_allowed": False,
        },
        "contract_outcome": CONTRACT_OUTCOME,
        "regime_order": list(REGIME_ORDER),
        "regime_contracts": deepcopy(REGIME_CONTRACTS),
        "required_evidence": list(REQUIRED_EVIDENCE),
        "fail_closed_conditions": list(FAIL_CLOSED_CONDITIONS),
        "solver_authority": dict(SOLVER_AUTHORITY),
        "formal_status": dict(FORMAL_STATUS),
        "literature_basis": deepcopy(LITERATURE_BASIS),
        "next_authorized_action": NEXT_AUTHORIZED_ACTION,
        "interpretation": {
            "a2_diagnostic_acoustic_value": (
                "REMAINS_SURROGATE_DIAGNOSTIC_ONLY_NOT_HYDRODYNAMIC_CLOSURE"
            ),
            "frozen_and_equilibrium_candidates": (
                "MAY_BE_IMPLEMENTED_NEXT_AS_READ_ONLY_DIAGNOSTICS"
            ),
            "finite_relaxation_response": (
                "MUST_RETAIN_FREQUENCY_AND_ATTENUATION_INFORMATION"
            ),
            "solver_effect": "NONE",
        },
    }


def _maturity_is_closed(status: Mapping[str, object]) -> bool:
    return all(
        status[key] is False
        for key in (
            "frozen_acoustic_formula_implemented",
            "equilibrium_acoustic_formula_implemented",
            "finite_relaxation_dispersion_implemented",
            "finite_pipeline_acoustic_shadow_ready",
            "hydrodynamic_coupling_allowed",
            "physical_hne_vertical_slice",
            "working_vertical_slice",
            "verified",
            "accepted",
            "physically_validated",
            "design_use_accepted",
            "production_approved",
        )
    )


def validate_contract(
    contract: Mapping[str, object],
    *,
    provenance: Mapping[str, str],
    require_clean_provenance: bool = True,
) -> dict[str, bool]:
    """Validate structural, physical-authority, and provenance gates."""

    source = contract.get("source_closeout")
    regimes = contract.get("regime_contracts")
    authority = contract.get("solver_authority")
    status = contract.get("formal_status")
    if not isinstance(source, Mapping):
        raise HNEAcousticContractError("source_closeout must be a mapping")
    if not isinstance(regimes, Mapping):
        raise HNEAcousticContractError("regime_contracts must be a mapping")
    if not isinstance(authority, Mapping):
        raise HNEAcousticContractError("solver_authority must be a mapping")
    if not isinstance(status, Mapping):
        raise HNEAcousticContractError("formal_status must be a mapping")

    exact_regimes = (
        list(contract.get("regime_order", [])) == list(REGIME_ORDER)
        and set(regimes) == set(REGIME_ORDER)
    )
    frozen = regimes.get("FROZEN_QUALITY", {})
    equilibrium = regimes.get("EQUILIBRIUM_MANIFOLD", {})
    finite = regimes.get("FINITE_RELAXATION_DISPERSIVE", {})
    if not all(isinstance(item, Mapping) for item in (frozen, equilibrium, finite)):
        raise HNEAcousticContractError("each acoustic regime must be a mapping")

    provenance_clean = (
        provenance.get("analysis_source_git_sha", "")
        == provenance.get("checkout_git_sha", "")
        and provenance.get("analysis_source_git_sha", "") != ""
        and provenance.get("git_status_porcelain", "") == ""
    )
    if not require_clean_provenance:
        provenance_clean = True

    gates = {
        "SOURCE_A2_3_CLOSEOUT_FROZEN": (
            source.get("a2_3_closeout_sha") == SOURCE_A2_3_CLOSEOUT_SHA
            and source.get("a2_3_closeout_workflow_run_id")
            == SOURCE_A2_3_CLOSEOUT_RUN_ID
            and source.get("a2_3_closeout_artifact_id")
            == SOURCE_A2_3_CLOSEOUT_ARTIFACT_ID
            and source.get("a2_3_closeout_artifact_sha256")
            == SOURCE_A2_3_CLOSEOUT_ARTIFACT_SHA256
            and source.get("closeout_conclusion") == "success"
            and source.get("hydrodynamic_coupling_allowed") is False
        ),
        "EXACT_THREE_ACOUSTIC_REGIMES_DECLARED": exact_regimes,
        "FROZEN_QUALITY_PATH_DECLARED": (
            frozen.get("quality_response")
            == "DELTA_Q_EQUALS_ZERO_DURING_PERTURBATION"
            and "Q_FIXED" in str(frozen.get("thermodynamic_path", ""))
            and frozen.get("single_real_scalar_c_authorized") is False
        ),
        "EQUILIBRIUM_MANIFOLD_PATH_DECLARED": (
            equilibrium.get("quality_response")
            == "Q_FOLLOWS_DECLARED_EQUILIBRIUM_MANIFOLD"
            and equilibrium.get("required_limit")
            == "TAU_TO_ZERO_OR_LOW_FREQUENCY_HEM_LIMIT"
            and equilibrium.get("single_real_scalar_c_authorized") is False
        ),
        "FINITE_RELAXATION_RETAINS_DISPERSION_AND_ATTENUATION": (
            finite.get("frequency_ordering") == "OMEGA_TAU_ORDER_ONE"
            and finite.get("single_real_scalar_c_authorized") is False
            and "PHASE_SPEED" in finite.get("required_outputs", [])
            and "ATTENUATION_RATE" in finite.get("required_outputs", [])
            and "COMPLEX_WAVENUMBER_OR_EQUIVALENT_TRANSFER_RESPONSE"
            in finite.get("required_outputs", [])
        ),
        "SUBCHARACTERISTIC_CHECK_REQUIRED": (
            "SUBCHARACTERISTIC_CONDITION_CHECK_WHERE_APPLICABLE"
            in contract.get("required_evidence", [])
            and "UNEXPLAINED_SUBCHARACTERISTIC_CONDITION_VIOLATION"
            in contract.get("fail_closed_conditions", [])
        ),
        "ALL_SOLVER_AUTHORITY_CLOSED": (
            set(authority) == set(SOLVER_AUTHORITY)
            and all(value is False for value in authority.values())
        ),
        "FAIL_CLOSED_CONDITIONS_COMPLETE": (
            list(contract.get("fail_closed_conditions", []))
            == list(FAIL_CLOSED_CONDITIONS)
        ),
        "REQUIRED_EVIDENCE_COMPLETE": (
            list(contract.get("required_evidence", []))
            == list(REQUIRED_EVIDENCE)
        ),
        "NO_ACOUSTIC_IMPLEMENTATION_OR_MATURITY_PROMOTION": (
            status.get("implemented") is True
            and status.get("acoustic_contract_ready") is True
            and _maturity_is_closed(status)
        ),
        "ONLY_A2_4_2_DIAGNOSTIC_PROTOTYPES_AUTHORIZED_NEXT": (
            contract.get("next_authorized_action") == NEXT_AUTHORIZED_ACTION
        ),
        "CLEAN_RUNTIME_PROVENANCE": provenance_clean,
    }
    failed = [name for name, passed in gates.items() if not passed]
    if failed:
        raise HNEAcousticContractError(
            "P2-A2.4-1 acoustic contract gates failed: " + ", ".join(failed)
        )
    return gates


def build_summary(
    *,
    provenance: Mapping[str, str] | None = None,
    require_clean_provenance: bool = True,
    contract: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build the validated contract summary and static authority digest."""

    record = deepcopy(contract) if contract is not None else acoustic_contract_record()
    runtime = dict(provenance) if provenance is not None else runtime_provenance()
    gates = validate_contract(
        record,
        provenance=runtime,
        require_clean_provenance=require_clean_provenance,
    )
    return {
        **record,
        "contract_authority_sha256": _canonical_sha256(record),
        "runtime_provenance": runtime,
        "gate_results": gates,
        "failed_gates": [],
        "contract_ready": True,
    }


def _regime_rows(summary: Mapping[str, object]) -> list[dict[str, object]]:
    regimes = summary["regime_contracts"]
    assert isinstance(regimes, Mapping)
    rows: list[dict[str, object]] = []
    for regime_id in REGIME_ORDER:
        regime = regimes[regime_id]
        assert isinstance(regime, Mapping)
        rows.append(
            {
                "regime_id": regime_id,
                "frequency_ordering": regime["frequency_ordering"],
                "disturbance_relaxation_ordering": regime[
                    "disturbance_relaxation_ordering"
                ],
                "quality_response": regime["quality_response"],
                "thermodynamic_path": regime["thermodynamic_path"],
                "derivative_contract": regime["derivative_contract"],
                "required_limit": regime["required_limit"],
                "required_outputs": "|".join(regime["required_outputs"]),
                "single_real_scalar_c_authorized": regime[
                    "single_real_scalar_c_authorized"
                ],
                "solver_authority": regime["solver_authority"],
            }
        )
    return rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise HNEAcousticContractError("regime contract CSV requires rows")
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _operator_report(summary: Mapping[str, object]) -> str:
    source = summary["source_closeout"]
    assert isinstance(source, Mapping)
    lines = [
        "# Stage 7 P2-A2.4-1 Nonequilibrium Acoustic Contract",
        "",
        f"- Outcome: `{summary['contract_outcome']}`",
        f"- Source A2.3 closeout SHA: `{source['a2_3_closeout_sha']}`",
        f"- Contract authority SHA-256: `{summary['contract_authority_sha256']}`",
        "- Solver effect: `NONE`",
        "- Hydrodynamic coupling allowed: `false`",
        "",
        "## Regimes",
        "",
    ]
    regimes = summary["regime_contracts"]
    assert isinstance(regimes, Mapping)
    for regime_id in REGIME_ORDER:
        regime = regimes[regime_id]
        assert isinstance(regime, Mapping)
        lines.extend(
            [
                f"### {regime_id}",
                "",
                f"- Ordering: `{regime['frequency_ordering']}`",
                f"- Quality response: `{regime['quality_response']}`",
                f"- Path: `{regime['thermodynamic_path']}`",
                f"- Required limit: `{regime['required_limit']}`",
                "- Real scalar sound-speed authority: `false`",
                "",
            ]
        )
    lines.extend(
        [
            "## Authority decision",
            "",
            "No acoustic candidate may enter flux, CFL, Riemann structure, or",
            "boundary characteristics. Frozen and equilibrium candidates may be",
            "implemented next only as read-only diagnostics. Finite relaxation",
            "must retain frequency-dependent phase and attenuation information.",
            "",
            "## Next authorized action",
            "",
            f"`{summary['next_authorized_action']}`",
            "",
        ]
    )
    return "\n".join(lines)


def execute(
    output_dir: str | Path,
    *,
    provenance: Mapping[str, str] | None = None,
    require_clean_provenance: bool = True,
) -> dict[str, object]:
    """Write the exact deterministic A2.4-1 contract evidence set."""

    summary = build_summary(
        provenance=provenance,
        require_clean_provenance=require_clean_provenance,
    )
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    summary_path = target / "summary.json"
    regimes_path = target / "regime_contracts.csv"
    report_path = target / "operator_report.md"
    manifest_path = target / "manifest.json"

    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(regimes_path, _regime_rows(summary))
    report_path.write_text(_operator_report(summary), encoding="utf-8")

    payload_paths = (summary_path, regimes_path, report_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "payload_files": {
            path.name: {
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
            for path in payload_paths
        },
        "contract_authority_sha256": summary["contract_authority_sha256"],
        "source_a2_3_closeout_sha": SOURCE_A2_3_CLOSEOUT_SHA,
        "contract_ready": True,
        "hydrodynamic_coupling_allowed": False,
        "next_authorized_action": NEXT_AUTHORIZED_ACTION,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != set(OUTPUT_FILES):
        raise HNEAcousticContractError(
            f"unexpected A2.4-1 evidence set: {sorted(actual)}"
        )
    return {
        "contract_ready": True,
        "contract_outcome": CONTRACT_OUTCOME,
        "contract_authority_sha256": summary["contract_authority_sha256"],
        "hydrodynamic_coupling_allowed": False,
        "next_authorized_action": NEXT_AUTHORIZED_ACTION,
        "output_dir": str(target),
        "artifact_paths": {
            "summary": str(summary_path),
            "regimes": str(regimes_path),
            "report": str(report_path),
            "manifest": str(manifest_path),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = execute(args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
