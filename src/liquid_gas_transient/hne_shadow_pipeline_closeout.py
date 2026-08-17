"""Formal closeout authority for Stage 7 P2-A2.3.

P2-A2.3 demonstrated that the A2 nonequilibrium thermodynamic closure can be
executed as a read-only shadow on accepted finite-pipeline FVM states.  This
module freezes that result without changing the solver, EOS, flux, CFL,
boundaries, phase source, or the A2/A2.3 implementations.

The closeout deliberately keeps the hydrodynamic-coupling gate closed.  It
records an authority boundary and authorizes only the next design investigation:
P2-A2.4-1, the nonequilibrium acoustic-closure contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Mapping


SCHEMA_VERSION = "stage7_p2_hne_shadow_pipeline_a2_3_closeout_v1"
SCOPE = "p2_a2_3_finite_pipeline_shadow_formal_closeout"
SOURCE_A2_3_SHA = "799edb09faa1502e25837c97fa5d168ad79e492e"
SOURCE_A2_3_WORKFLOW_RUN_ID = 31999652196
SOURCE_A2_3_ARTIFACT_ID = 9277959046
SOURCE_A2_3_ARTIFACT_SHA256 = (
    "9af5b48eb941e55c027ca4ad6ca7aab74f8d7f7ab6fc7b8426f32066f9db547c"
)
SOURCE_A2_3_ANALYSIS_SHA256 = (
    "4d20bf56f020eeed33d49f70722a00a9f2fc1445f80181fe52ab84de68e749f5"
)
SOURCE_A2_SHA = "b45156f349ddc9754d481c285a8e1efde5d74d22"
CLOSEOUT_OUTCOME = (
    "A2_3_FORMALLY_CLOSED_WITH_HYDRODYNAMIC_COUPLING_GATE_CLOSED"
)
NEXT_AUTHORIZED_ACTION = (
    "PROCEED_TO_A2_4_1_NONEQUILIBRIUM_ACOUSTIC_CLOSURE_CONTRACT"
)
OUTPUT_FILES = (
    "summary.json",
    "operator_report.md",
    "manifest.json",
)

FORMAL_STATUS = {
    "implemented": True,
    "finite_pipeline_shadow_integration": True,
    "diagnostic_evidence_ready": True,
    "a2_3_formally_closed": True,
    "hydrodynamic_coupling_allowed": False,
    "physical_hne_vertical_slice": False,
    "working_vertical_slice": False,
    "verified": False,
    "accepted": False,
    "physically_validated": False,
    "design_use_accepted": False,
    "production_approved": False,
}

COUPLING_AUTHORITY = {
    "shadow_reads_accepted_U": True,
    "shadow_may_mutate_U": False,
    "p_hne_to_flux": False,
    "T_hne_to_flux": False,
    "alpha_hne_to_flux": False,
    "c_hne_to_flux_or_cfl": False,
    "hne_boundary_characteristics_allowed": False,
    "hydrodynamic_coupling_allowed": False,
}

RETAINED_LIMITATIONS = (
    "SURROGATE_CONSTITUENT_EOS_ONLY",
    "NO_VALIDATED_NONEQUILIBRIUM_ACOUSTIC_DERIVATIVE",
    "NO_HNE_PRESSURE_FEEDBACK_TO_FLUX",
    "NO_NUCLEATION_METASTABILITY_OR_BUBBLE_GROWTH_MODEL",
    "NO_SLIP_MODEL",
    "TAU_NOT_PHYSICALLY_VALIDATED",
    "NO_REAL_FLUID_BACKEND_COMPATIBILITY",
    "NO_PHYSICAL_DISCHARGE_FEEDBACK_LOOP",
    "P1_MESH_CFL_LIMITATIONS_RETAINED",
)

CLOSEOUT_CLAIMS = {
    "finite_pipeline_shadow_execution": (
        "SUPPORTED_BY_FOCUSED_A2_3_EVIDENCE"
    ),
    "read_only_shadow_observer": "SUPPORTED_BITWISE",
    "authoritative_hem_flux_and_cfl_retained": "SUPPORTED_BITWISE",
    "tau_to_zero_hem_limit": "SUPPORTED_IN_SURROGATE_FOCUSED_CASE",
    "finite_tau_thermodynamic_difference_visible": (
        "SUPPORTED_IN_SURROGATE_FOCUSED_CASE"
    ),
    "tau_infinity_no_phase_change_limit": "SUPPORTED_BITWISE",
    "deterministic_reproducibility": "SUPPORTED",
    "physical_co2_prediction": "NOT_CLAIMED",
    "nonequilibrium_acoustic_closure": "NOT_ESTABLISHED",
    "hydrodynamic_hne_coupling": "NOT_AUTHORIZED",
}


class HNEShadowPipelineCloseoutError(RuntimeError):
    """Raised when closeout evidence cannot satisfy its frozen authority."""


def _run_command(*args: str) -> str:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return ""


def runtime_provenance() -> dict[str, str]:
    """Return checkout provenance before closeout artifacts are written."""

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


def frozen_authority_record() -> dict[str, object]:
    """Return the static A2.3 closeout record used for authority hashing."""

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": SCOPE,
        "source": {
            "a2_sha": SOURCE_A2_SHA,
            "a2_3_sha": SOURCE_A2_3_SHA,
            "workflow_run_id": SOURCE_A2_3_WORKFLOW_RUN_ID,
            "artifact_id": SOURCE_A2_3_ARTIFACT_ID,
            "artifact_sha256": SOURCE_A2_3_ARTIFACT_SHA256,
            "analysis_sha256": SOURCE_A2_3_ANALYSIS_SHA256,
            "workflow_conclusion": "success",
            "focused_test_result": {
                "tests": 5,
                "skipped": 0,
                "failures": 0,
                "errors": 0,
            },
        },
        "closeout_outcome": CLOSEOUT_OUTCOME,
        "next_authorized_action": NEXT_AUTHORIZED_ACTION,
        "formal_status": dict(FORMAL_STATUS),
        "coupling_authority": dict(COUPLING_AUTHORITY),
        "claims": dict(CLOSEOUT_CLAIMS),
        "retained_limitations": list(RETAINED_LIMITATIONS),
    }


def _gate_results(
    authority: Mapping[str, object],
    provenance: Mapping[str, str],
) -> dict[str, bool]:
    status = authority["formal_status"]
    coupling = authority["coupling_authority"]
    claims = authority["claims"]
    source = authority["source"]
    assert isinstance(status, dict)
    assert isinstance(coupling, dict)
    assert isinstance(claims, dict)
    assert isinstance(source, dict)

    no_maturity_promotion = all(
        status[key] is False
        for key in (
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
    provenance_clean = (
        provenance.get("analysis_source_git_sha", "")
        == provenance.get("checkout_git_sha", "")
        and provenance.get("analysis_source_git_sha", "") != ""
        and provenance.get("git_status_porcelain", "") == ""
    )
    return {
        "SOURCE_A2_3_SHA_FROZEN": source["a2_3_sha"] == SOURCE_A2_3_SHA,
        "SOURCE_WORKFLOW_SUCCESS_FROZEN": (
            source["workflow_run_id"] == SOURCE_A2_3_WORKFLOW_RUN_ID
            and source["workflow_conclusion"] == "success"
        ),
        "SOURCE_ARTIFACT_DIGEST_FROZEN": (
            source["artifact_id"] == SOURCE_A2_3_ARTIFACT_ID
            and source["artifact_sha256"] == SOURCE_A2_3_ARTIFACT_SHA256
        ),
        "SOURCE_ANALYSIS_DIGEST_FROZEN": (
            source["analysis_sha256"] == SOURCE_A2_3_ANALYSIS_SHA256
        ),
        "FINITE_PIPELINE_SHADOW_CLAIM_RETAINED": (
            status["finite_pipeline_shadow_integration"] is True
            and status["diagnostic_evidence_ready"] is True
        ),
        "HYDRODYNAMIC_COUPLING_GATE_CLOSED": (
            coupling["hydrodynamic_coupling_allowed"] is False
            and coupling["p_hne_to_flux"] is False
            and coupling["c_hne_to_flux_or_cfl"] is False
        ),
        "PHYSICAL_HNE_CLAIM_CLOSED": (
            claims["physical_co2_prediction"] == "NOT_CLAIMED"
            and claims["hydrodynamic_hne_coupling"] == "NOT_AUTHORIZED"
        ),
        "MATURITY_NOT_PROMOTED": no_maturity_promotion,
        "A2_4_1_IS_ONLY_AUTHORIZED_NEXT_STEP": (
            authority["next_authorized_action"] == NEXT_AUTHORIZED_ACTION
        ),
        "LIMITATIONS_RETAINED": (
            list(authority["retained_limitations"]) == list(RETAINED_LIMITATIONS)
        ),
        "CLEAN_RUNTIME_PROVENANCE": provenance_clean,
    }


def build_summary(
    *,
    provenance: Mapping[str, str] | None = None,
    require_clean_provenance: bool = True,
) -> dict[str, object]:
    """Build and validate the complete closeout summary."""

    authority = frozen_authority_record()
    runtime = dict(provenance) if provenance is not None else runtime_provenance()
    gates = _gate_results(authority, runtime)
    if not require_clean_provenance:
        gates["CLEAN_RUNTIME_PROVENANCE"] = True
    failed = [name for name, passed in gates.items() if not passed]
    summary = {
        **authority,
        "authority_sha256": _canonical_sha256(authority),
        "runtime_provenance": runtime,
        "gate_results": gates,
        "failed_gates": failed,
        "closeout_ready": not failed,
    }
    if failed:
        raise HNEShadowPipelineCloseoutError(
            "A2.3 closeout gates failed: " + ", ".join(failed)
        )
    return summary


def _operator_report(summary: Mapping[str, object]) -> str:
    source = summary["source"]
    status = summary["formal_status"]
    assert isinstance(source, dict)
    assert isinstance(status, dict)
    limitations = summary["retained_limitations"]
    assert isinstance(limitations, list)
    lines = [
        "# Stage 7 P2-A2.3 Formal Closeout",
        "",
        f"- Outcome: `{summary['closeout_outcome']}`",
        f"- Frozen A2.3 SHA: `{source['a2_3_sha']}`",
        f"- Source workflow run: `{source['workflow_run_id']}` (`success`)",
        f"- Source artifact ID: `{source['artifact_id']}`",
        f"- Source artifact SHA-256: `{source['artifact_sha256']}`",
        f"- Source analysis SHA-256: `{source['analysis_sha256']}`",
        f"- Closeout authority SHA-256: `{summary['authority_sha256']}`",
        "",
        "## Authority decision",
        "",
        "Finite-pipeline read-only HNE shadow execution is formally recorded.",
        "No HNE pressure, temperature, void fraction, or acoustic diagnostic is",
        "authorized to enter flux, CFL, boundary characteristics, or solver control.",
        "",
        "## Maturity",
        "",
    ]
    for key, value in status.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(["", "## Retained limitations", ""])
    lines.extend(f"- `{item}`" for item in limitations)
    lines.extend(
        [
            "",
            "## Next authorized action",
            "",
            f"`{summary['next_authorized_action']}`",
            "",
            "This authorizes a contract/design investigation only. It does not",
            "authorize hydrodynamic coupling or any physical CO2 prediction.",
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
    """Write the exact deterministic P2-A2.3 closeout evidence set."""

    summary = build_summary(
        provenance=provenance,
        require_clean_provenance=require_clean_provenance,
    )
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    summary_path = target / "summary.json"
    report_path = target / "operator_report.md"
    manifest_path = target / "manifest.json"

    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_operator_report(summary), encoding="utf-8")

    payload_files = (summary_path, report_path)
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
            for path in payload_files
        },
        "authority_sha256": summary["authority_sha256"],
        "source_a2_3_sha": SOURCE_A2_3_SHA,
        "closeout_ready": summary["closeout_ready"],
        "hydrodynamic_coupling_allowed": False,
        "next_authorized_action": NEXT_AUTHORIZED_ACTION,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    actual = {path.name for path in target.iterdir() if path.is_file()}
    if actual != set(OUTPUT_FILES):
        raise HNEShadowPipelineCloseoutError(
            f"unexpected closeout evidence set: {sorted(actual)}"
        )
    return {
        "closeout_ready": True,
        "closeout_outcome": CLOSEOUT_OUTCOME,
        "authority_sha256": summary["authority_sha256"],
        "output_dir": str(target),
        "artifact_paths": {
            "summary": str(summary_path),
            "report": str(report_path),
            "manifest": str(manifest_path),
        },
        "next_authorized_action": NEXT_AUTHORIZED_ACTION,
        "hydrodynamic_coupling_allowed": False,
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
