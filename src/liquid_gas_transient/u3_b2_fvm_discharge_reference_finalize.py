"""Finalize authoritative U3 B2 Reference artifact provenance.

The numerical/reference generator deliberately remains independent of GitHub
Actions.  This small post-processor adds run-specific authority fields after the
Reference files exist, annotates retained PNG figures visibly, and regenerates
the internal SHA256 manifest.  It changes no contract, tolerance, equation, or
Reference value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _annotate_png(path: Path, footer: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    with Image.open(path) as source:
        image = source.convert("RGB")
    font = ImageFont.load_default()
    draw_probe = ImageDraw.Draw(image)
    bbox = draw_probe.multiline_textbbox((0, 0), footer, font=font, spacing=2)
    footer_height = max(34, bbox[3] - bbox[1] + 14)
    canvas = Image.new("RGB", (image.width, image.height + footer_height), "white")
    canvas.paste(image, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.line((0, image.height, image.width, image.height), fill="black", width=1)
    draw.multiline_text(
        (7, image.height + 6),
        footer,
        fill="black",
        font=font,
        spacing=2,
    )
    canvas.save(path, format="PNG")


def finalize(
    *,
    output_dir: Path,
    source_git_sha: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
) -> None:
    if len(source_git_sha) != 40 or any(
        character not in "0123456789abcdef" for character in source_git_sha
    ):
        raise ValueError("source_git_sha must be a lowercase forty-character SHA")
    if workflow_run_id <= 0 or workflow_run_attempt <= 0:
        raise ValueError("workflow identifiers must be positive")

    summary_path = output_dir / "summary.json"
    provenance_path = output_dir / "runtime_and_git_provenance.json"
    report_path = output_dir / "report.md"
    if not summary_path.is_file() or not provenance_path.is_file():
        raise FileNotFoundError("Reference artifact is incomplete before finalization")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance["source_git_sha"] != source_git_sha:
        raise ValueError("Reference source SHA changed before finalization")

    authority = {
        "analysis_id": "stage7_u3_b2_independent_reference",
        "analysis_model": "single_phase_fvm_discharge_coupling_reference",
        "case_or_matrix_identifier": "U3_B2_REFERENCE_26_CASE_CONTRACT",
        "workflow_run_id": int(workflow_run_id),
        "workflow_run_attempt": int(workflow_run_attempt),
    }
    provenance.update(authority)
    summary["provenance"] = provenance
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = report_path.read_text(encoding="utf-8")
    report += (
        "\n## Authoritative workflow provenance\n\n"
        "```text\n"
        f"case / matrix: {authority['case_or_matrix_identifier']}\n"
        f"model: {authority['analysis_model']}\n"
        f"property backend: CoolProp {provenance['property_backend_version']}\n"
        f"analysis source SHA: {source_git_sha}\n"
        f"workflow run ID: {workflow_run_id}\n"
        f"workflow run attempt: {workflow_run_attempt}\n"
        "```\n"
    )
    report_path.write_text(report, encoding="utf-8")

    footer = (
        f"U3_B2_REFERENCE_26_CASE_CONTRACT | independent Reference | "
        f"CoolProp {provenance['property_backend_version']}\n"
        f"source {source_git_sha} | workflow {workflow_run_id} "
        f"attempt {workflow_run_attempt}"
    )
    for name in (
        "face_flux_reference.png",
        "acoustic_arrival_reference.png",
    ):
        _annotate_png(output_dir / name, footer)

    manifest_lines: list[str] = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.name == "artifact_sha256.txt":
            continue
        if not path.is_file():
            raise ValueError(f"Unexpected artifact directory: {path}")
        manifest_lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
        )
    (output_dir / "artifact_sha256.txt").write_text(
        "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    finalize(
        output_dir=args.output_dir,
        source_git_sha=args.source_git_sha,
        workflow_run_id=args.workflow_run_id,
        workflow_run_attempt=args.workflow_run_attempt,
    )


if __name__ == "__main__":
    main()
