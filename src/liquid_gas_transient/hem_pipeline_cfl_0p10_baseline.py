"""Exact 128-cell / CFL=0.10 replay for the Stage 7 CFL gate.

This increment executes only the three authoritative PR #82 baseline rows. It
does not execute or accept the CFL 0.05 or 0.025 comparison rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from .hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics, _case_metrics
from .hem_pipeline_cfl_sensitivity import (
    CFL_CELL_COUNT,
    EXPECTED_128_CELL_CFL_0P10,
    HEMPipelineCflSensitivityConfig,
    _assert_128_cell_cfl_0p10_baseline,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineDepressurizationCaseSpec,
    run_pipeline_depressurization_case,
)


BASELINE_CFL = 0.10
ANALYSIS_MODEL = "HEM"
PROPERTY_BACKEND_NAME = "coolprop_co2"


class HEMPipelineCflBaselineError(RuntimeError):
    """Raised when the exact CFL=0.10 replay cannot be retained safely."""


CflBaselineRunner = Callable[
    [PipelineDepressurizationCaseSpec, HEMPipelineDepressurizationConfig],
    PipelineCaseResult,
]


def _coolprop_version() -> str:
    try:
        import CoolProp  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("CoolProp is required for CFL baseline replay") from exc
    version = str(getattr(CoolProp, "__version__", "")).strip()
    if not version:
        raise HEMPipelineCflBaselineError("CoolProp version is unavailable")
    return version


def _git_head() -> str | None:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return value or None


def _runtime_provenance() -> dict[str, object]:
    checkout_sha = _git_head()
    source_sha = (
        os.environ.get("ANALYSIS_SOURCE_GIT_SHA", "").strip()
        or os.environ.get("GITHUB_SHA", "").strip()
        or checkout_sha
    )
    if not source_sha:
        raise HEMPipelineCflBaselineError(
            "source Git SHA is unavailable; set ANALYSIS_SOURCE_GIT_SHA"
        )
    return {
        "analysis_model": ANALYSIS_MODEL,
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "property_backend_version": _coolprop_version(),
        "source_git_sha": source_sha,
        "checkout_git_sha": checkout_sha,
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "github_ref": os.environ.get("GITHUB_REF"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
    }


@dataclass(frozen=True)
class HEMPipelineCflBaselineResult:
    """Exact replay of the three 128-cell / CFL=0.10 PR #82 rows."""

    cases: tuple[MeshCaseMetrics, ...]
    provenance: dict[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "stage7_lco2_hem_pipeline_cfl_0p10_baseline_v1",
            "scope": "verification_only",
            "case_count": len(self.cases),
            "n_cells": CFL_CELL_COUNT,
            "dx_m": 1.0 / CFL_CELL_COUNT,
            "cfl": BASELINE_CFL,
            "maximum_steps": 8000,
            "case_ids": [case.case_id for case in self.cases],
            "all_pr82_rows_reproduced_exactly": len(self.cases) == 3,
            "low_cfl_matrix_executed": False,
            "provenance": dict(self.provenance),
            "cases": [case.summary() for case in self.cases],
            "Gate_P2_passed": False,
            "CFL_independent_crossing_verified": False,
            "near_saturation_acoustic_continuity_approved": False,
            "post_crossing_propagation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
        }


def run_cfl_0p10_baseline(
    *,
    case_runner: CflBaselineRunner = run_pipeline_depressurization_case,
    provenance: dict[str, object] | None = None,
) -> HEMPipelineCflBaselineResult:
    """Run and require exact identity for all three PR #82 baseline rows."""

    config = HEMPipelineCflSensitivityConfig.for_cfl(BASELINE_CFL)
    metrics: list[MeshCaseMetrics] = []
    for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        raw = case_runner(case, config)
        metric = replace(
            _case_metrics(raw),
            run_id=f"{case.case_id}__n{CFL_CELL_COUNT}__cfl0p100_baseline",
        )
        _assert_128_cell_cfl_0p10_baseline(metric)
        metrics.append(metric)

    expected_ids = list(EXPECTED_128_CELL_CFL_0P10)
    observed_ids = [metric.case_id for metric in metrics]
    if observed_ids != expected_ids:
        raise HEMPipelineCflBaselineError(
            f"baseline case order mismatch: {observed_ids!r} != {expected_ids!r}"
        )
    return HEMPipelineCflBaselineResult(
        cases=tuple(metrics),
        provenance=dict(provenance or _runtime_provenance()),
    )


def write_cfl_0p10_baseline_artifacts(
    output_dir: str | Path,
) -> tuple[HEMPipelineCflBaselineResult, dict[str, Path]]:
    """Run the exact replay and write JSON, CSV, and Markdown evidence."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    result = run_cfl_0p10_baseline()
    paths = {
        "summary_json": target / "cfl_0p10_baseline_summary.json",
        "cases_csv": target / "cfl_0p10_baseline_cases.csv",
        "markdown": target / "cfl_0p10_baseline.md",
    }
    summary = result.summary()
    paths["summary_json"].write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rows = [case.summary() for case in result.cases]
    with paths["cases_csv"].open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    provenance = result.provenance
    lines = [
        "# Stage 7 Pipeline CFL 0.10 Baseline Replay",
        "",
        "`EXACT PR #82 REPLAY; LOW-CFL MATRIX NOT EXECUTED; VERIFICATION ONLY`",
        "",
        "```text",
        f"model:             {provenance['analysis_model']}",
        f"backend:           {provenance['property_backend_name']}",
        f"backend version:   {provenance['property_backend_version']}",
        f"source Git SHA:    {provenance['source_git_sha']}",
        "```",
        "",
        "| case | outcome | step | crossing time [s] | cell | max q_eq |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for case in result.cases:
        lines.append(
            f"| {case.case_id} | {case.outcome} | {case.step_count} | "
            f"{case.crossing_time_s:.17g} | {case.crossing_cell_index} | "
            f"{case.maximum_crossing_quality:.17g} |"
        )
    lines.extend(
        [
            "",
            "```text",
            "all_pr82_rows_reproduced_exactly = true",
            "low_cfl_matrix_executed = false",
            "CFL_independent_crossing_verified = false",
            "Gate_P2_passed = false",
            "physical_validation = false",
            "design_use_acceptance = false",
            "production_hem_activation_approved = false",
            "```",
        ]
    )
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result, paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay the exact PR #82 128-cell/CFL=0.10 pipeline baseline."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result, paths = write_cfl_0p10_baseline_artifacts(args.output_dir)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
