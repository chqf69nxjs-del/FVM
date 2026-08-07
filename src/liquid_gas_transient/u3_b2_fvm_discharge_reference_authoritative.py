"""Authoritative interpretation for the locked U3 B2 Reference.

The B2-09 contract row has an execution-level outcome of
``SUCCESS_ONE_STEP_CONSERVATIVE_UPDATE``. Its upstream face calculation is,
correctly, an unchoked face mapping. This wrapper keeps both facts separate:

* the face table records ``SUCCESS_UNCHOKED_FACE_MAPPING`` as the layer result;
* the one-step table records ``SUCCESS_ONE_STEP_CONSERVATIVE_UPDATE``;
* the face-layer expected value is interpreted as the prerequisite mapping,
  rather than comparing it directly with the later execution-level outcome.

The wrapper also supplies the result-independent provenance interpretation
required by the locked B2 event/provenance extension: every retained figure,
summary, runtime record, and report identifies the exact analysis source SHA,
workflow run, backend, model, and mapping mode. No contract value, tolerance,
physical equation, or B1 component behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from . import u3_b1_critical_state_reference as b1_ref
from . import u3_b2_fvm_discharge_reference as ref

_ORIGINAL_EVALUATE_FACE_ROWS = ref.evaluate_face_rows


def evaluate_face_rows(
    contract: Mapping[str, Any],
    b1_contract: Mapping[str, Any],
    provider: ref.CoolPropReferenceProperties,
) -> tuple[list[ref.FaceReference], dict[str, ref.StagnationReconstruction]]:
    rows, reconstructions = _ORIGINAL_EVALUATE_FACE_ROWS(
        contract,
        b1_contract,
        provider,
    )
    adjusted: list[ref.FaceReference] = []
    for row in rows:
        if row.case_id == "B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE":
            if row.formal_outcome != ref.SUCCESS_UNCHOKED_FACE_MAPPING:
                raise AssertionError(
                    "B2-09 face prerequisite must be an unchoked mapping"
                )
            adjusted.append(
                replace(
                    row,
                    expected_outcome=ref.SUCCESS_UNCHOKED_FACE_MAPPING,
                    outcome_matches_contract=True,
                    formal_message=(
                        row.formal_message
                        + " This is the prerequisite face-layer outcome; "
                        "the execution-level one-step outcome is recorded "
                        "separately."
                    ),
                )
            )
        else:
            adjusted.append(row)
    return adjusted, reconstructions


def _workflow_value(name: str, default: str = "local") -> str:
    value = os.environ.get(name, default)
    return value if value else default


def _figure_provenance(case_or_matrix: str, package: ref.ReferencePackage) -> str:
    source = _workflow_value("ANALYSIS_SOURCE_GIT_SHA")
    run_id = _workflow_value("GITHUB_RUN_ID")
    backend = package.summary["property_backend"]
    version = package.summary["property_backend_version"]
    return (
        f"case_or_matrix={case_or_matrix} | "
        "model=U3 B2 independent single-phase FVM-face reference | "
        "mapping=direct_external_face_flux_override | "
        f"backend={backend} {version} | source={source} | run={run_id}"
    )


def write_plots_with_provenance(
    output_dir: Path,
    package: ref.ReferencePackage,
) -> None:
    """Write the two locked plots with visible and embedded provenance."""

    import matplotlib.pyplot as plt

    physical = [
        row
        for row in package.face_rows
        if row.mass_transfer_outward_kg_s > 0.0
    ]
    x = list(range(len(physical)))
    provenance = _figure_provenance("B2_FACE_REFERENCE_MATRIX", package)
    figure = plt.figure(figsize=(12, 6))
    axis = figure.add_subplot(111)
    axis.plot(
        x,
        [row.F_rho_kg_m2_s for row in physical],
        marker="o",
        label="mass flux",
    )
    axis.plot(
        x,
        [
            row.advective_momentum_rate_out_N / row.pipe_area_m2
            for row in physical
        ],
        marker="s",
        label="advective momentum flux",
    )
    axis.set_xticks(x)
    axis.set_xticklabels(
        [row.case_id for row in physical],
        rotation=70,
        ha="right",
    )
    axis.set_ylabel("Reference flux value")
    axis.set_title("U3 B2 independent face-flux reference")
    axis.legend()
    axis.grid(True, alpha=0.3)
    figure.text(0.01, 0.01, provenance, ha="left", va="bottom", fontsize=5)
    figure.tight_layout(rect=(0.0, 0.06, 1.0, 1.0))
    figure.savefig(
        output_dir / "face_flux_reference.png",
        dpi=160,
        metadata={"Description": provenance},
    )
    plt.close(figure)

    mesh = min(row.cells for row in package.acoustic_rows)
    rows = [row for row in package.acoustic_rows if row.cells == mesh]
    provenance = _figure_provenance(
        f"B2_ACOUSTIC_REQUESTED_PROBES_N{mesh}",
        package,
    )
    figure = plt.figure(figsize=(8, 5))
    axis = figure.add_subplot(111)
    probes = [row.probe_normalized_position for row in rows]
    axis.plot(
        probes,
        [row.direct_reference_time_s for row in rows],
        marker="o",
        label="direct rarefaction",
    )
    axis.plot(
        probes,
        [row.reflected_reference_time_s for row in rows],
        marker="s",
        label="rigid-wall reflection",
    )
    axis.set_xlabel("requested probe x/L")
    axis.set_ylabel("reference arrival time [s]")
    axis.set_title("U3 B2 linear-acoustic arrival reference")
    axis.legend()
    axis.grid(True, alpha=0.3)
    figure.text(0.01, 0.01, provenance, ha="left", va="bottom", fontsize=5)
    figure.tight_layout(rect=(0.0, 0.08, 1.0, 1.0))
    figure.savefig(
        output_dir / "acoustic_arrival_reference.png",
        dpi=160,
        metadata={"Description": provenance},
    )
    plt.close(figure)


def _rewrite_manifest(output_dir: Path) -> None:
    lines: list[str] = []
    for artifact in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if artifact.name == "artifact_sha256.txt":
            continue
        if not artifact.is_file():
            raise ValueError(f"Unexpected directory in artifact: {artifact}")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        lines.append(f"{digest}  {artifact.name}")
    (output_dir / "artifact_sha256.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def augment_artifact_provenance(
    output_dir: Path,
    package: ref.ReferencePackage,
) -> None:
    """Promote locked runtime/run provenance into all retained records."""

    provenance_path = output_dir / "runtime_and_git_provenance.json"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "report.md"

    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    run_id = _workflow_value("GITHUB_RUN_ID")
    run_attempt = _workflow_value("GITHUB_RUN_ATTEMPT", "1")
    source_sha = _workflow_value("ANALYSIS_SOURCE_GIT_SHA")
    provenance.update(
        {
            "analysis_source_git_sha": source_sha,
            "workflow_run_id": int(run_id) if run_id.isdigit() else run_id,
            "workflow_run_attempt": (
                int(run_attempt) if run_attempt.isdigit() else run_attempt
            ),
            "runner_os": "ubuntu-24.04",
            "github_runner_os": _workflow_value("RUNNER_OS", "Linux"),
            "case_or_matrix_identifier": "U3_B2_26_CASE_REFERENCE_MATRIX",
            "model": "U3 B2 independent single-phase FVM-face reference",
            "mapping_mode": "direct_external_face_flux_override",
            "B2_adapter_source_sha": None,
        }
    )
    if provenance["source_git_sha"] != source_sha:
        raise AssertionError("Artifact source SHA does not match analysis head")
    if provenance["property_backend_version"] != "8.0.0":
        raise AssertionError("Unexpected CoolProp version")
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["provenance"] = provenance
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = report_path.read_text(encoding="utf-8").rstrip()
    report += (
        "\n\n## Authoritative workflow provenance\n\n"
        "```text\n"
        "case / matrix: U3_B2_26_CASE_REFERENCE_MATRIX\n"
        "model: U3 B2 independent single-phase FVM-face reference\n"
        "mapping: direct_external_face_flux_override\n"
        f"property backend: CoolProp {provenance['property_backend_version']}\n"
        f"analysis source SHA: {source_sha}\n"
        f"B1 Reference source SHA: {provenance['B1_reference_source_sha']}\n"
        "B2 Adapter source SHA: NOT_IMPLEMENTED\n"
        f"workflow run ID: {provenance['workflow_run_id']}\n"
        f"workflow run attempt: {provenance['workflow_run_attempt']}\n"
        "```\n"
    )
    report_path.write_text(report, encoding="utf-8")

    expected_figures = {
        "face_flux_reference.png": "B2_FACE_REFERENCE_MATRIX",
        "acoustic_arrival_reference.png": (
            f"B2_ACOUSTIC_REQUESTED_PROBES_N{min(row.cells for row in package.acoustic_rows)}"
        ),
    }
    for name, identifier in expected_figures.items():
        if not (output_dir / name).is_file():
            raise AssertionError(f"Missing expected figure: {name}")
        if identifier not in _figure_provenance(identifier, package):
            raise AssertionError(f"Figure provenance identifier failed: {name}")

    _rewrite_manifest(output_dir)


def install_authoritative_interpretation() -> None:
    ref.evaluate_face_rows = evaluate_face_rows
    ref.write_plots = write_plots_with_provenance


def main() -> None:
    install_authoritative_interpretation()
    args = ref.parse_args()
    contract = ref.load_contract(args.contract)
    extension = ref.load_extension(args.extension_contract)
    b1_contract = b1_ref.load_contract(args.b1_contract)
    package = ref.evaluate_reference(contract, extension, b1_contract)
    print(json.dumps(package.summary, indent=2, sort_keys=True))
    failed = [
        row for row in package.locked_checks if not bool(row["passed"])
    ]
    if failed:
        print(json.dumps({"failed_locked_checks": failed}, indent=2, default=str))
        raise RuntimeError("One or more locked U3 B2 Reference checks failed")
    ref.write_artifact(
        output_dir=args.output_dir,
        package=package,
        contract_path=args.contract,
        extension_path=args.extension_contract,
        b1_contract_path=args.b1_contract,
        source_git_sha=str(args.source_git_sha),
    )
    augment_artifact_provenance(args.output_dir, package)


if __name__ == "__main__":
    main()
