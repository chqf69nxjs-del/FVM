"""Artifact writer and CLI for the P2 HNE acoustic authority gate."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from .hne_acoustic_authority_analysis import analyze_acoustic_authority_gate
from .hne_acoustic_authority_types import (
    OUTPUT_FILES, SCHEMA_VERSION, HNEAcousticAuthorityGateError,
)

def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise HNEAcousticAuthorityGateError("CSV_REQUIRES_ROWS")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _operator_report(summary: Mapping[str, object], cases: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# P2 HNE Acoustic Authority Gate",
        "",
        f"- Outcome: `{summary['formal_outcome']}`",
        "- Current production solver effect: `NONE`",
        (
            "- Authorized next implementation: `P2-A3.1 limited interior coupling`"
            if summary["acoustic_authority_gate_passed"]
            else "- Authorized next implementation: `none; gate failed closed`"
        ),
        "- Boundary/discharge/design/production authority: `false`",
        "",
        "| case | q offset | p [Pa] | c_f [m/s] | J rel. err | eig. err | hyperbolic |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in cases:
        lines.append(
            "| {case} | {dq:.4g} | {p:.8g} | {c:.8g} | {j:.3e} | {e:.3e} | {h} |".format(
                case=row["case_id"],
                dq=float(row["quality_offset"]),
                p=float(row["candidate_pressure_pa"]),
                c=float(row["candidate_frozen_c_m_s"]),
                j=float(row["jacobian_relative_error"]),
                e=float(row["numerical_eigenvalue_max_abs_error"]),
                h=row["hyperbolic"],
            )
        )
    lines += [
        "",
        "The gate grants permission only to implement p_candidate + c_frozen as one",
        "interior verification package in P2-A3.1. It does not activate coupling.",
        "",
    ]
    return "\n".join(lines)


def write_artifacts(
    output_dir: str | Path,
    summary: Mapping[str, object],
    case_rows: Sequence[Mapping[str, object]],
    eigen_rows: Sequence[Mapping[str, object]],
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    expected = set(OUTPUT_FILES)
    unexpected = {p.name for p in target.iterdir() if p.is_file()} - expected
    if unexpected:
        raise HNEAcousticAuthorityGateError(
            "UNEXPECTED_OUTPUT_FILES:" + ",".join(sorted(unexpected))
        )
    paths = {
        "summary": target / "summary.json",
        "cases": target / "case_summary.csv",
        "eigenvalues": target / "jacobian_eigenvalues.csv",
        "report": target / "operator_report.md",
        "manifest": target / "manifest.json",
    }
    paths["summary"].write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _write_csv(paths["cases"], case_rows)
    _write_csv(paths["eigenvalues"], eigen_rows)
    paths["report"].write_text(
        _operator_report(summary, case_rows), encoding="utf-8"
    )
    payload = {key: path for key, path in paths.items() if key != "manifest"}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES),
        "analysis_sha256": summary["analysis_sha256"],
        "acoustic_authority_gate_passed": summary["acoustic_authority_gate_passed"],
        "limited_p2_a3_1_implementation_authorized": summary["formal_status"][
            "limited_p2_a3_1_implementation_authorized"
        ],
        "hydrodynamic_coupling_active": False,
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
    if {p.name for p in target.iterdir() if p.is_file()} != expected:
        raise HNEAcousticAuthorityGateError("ARTIFACT_ENVELOPE_MISMATCH")
    return paths


def execute(output_dir: str | Path) -> dict[str, object]:
    summary, cases, eigenvalues = analyze_acoustic_authority_gate()
    paths = write_artifacts(output_dir, summary, cases, eigenvalues)
    return {
        **summary,
        "artifact_paths": {key: str(value) for key, value in paths.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    result = execute(parser.parse_args(argv).output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["acoustic_authority_gate_passed"] else 2
