"""Exact 128-cell / CFL=0.10 replay for the Stage 7 CFL gate.

This increment executes only the three authoritative PR #82 baseline rows. It
does not execute or accept the CFL 0.05 or 0.025 comparison rows.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics, _case_metrics
from .hem_pipeline_cfl_sensitivity import (
    ANALYSIS_MODEL,
    CFL_ANALYSIS_ID,
    CFL_CELL_COUNT,
    EXPECTED_128_CELL_CFL_0P10,
    HEMPipelineCflSensitivityConfig,
    PROPERTY_BACKEND_NAME,
    _assert_128_cell_cfl_0p10_baseline,
    collect_cfl_runtime_provenance,
    normalize_cfl_provenance,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineDepressurizationCaseSpec,
    run_pipeline_depressurization_case,
)


BASELINE_CFL = 0.10
BASELINE_ANALYSIS_ID = "stage7_pipeline_cfl_0p10_baseline_replay"


class HEMPipelineCflBaselineError(RuntimeError):
    """Raised when the exact CFL=0.10 replay cannot be retained safely."""


CflBaselineRunner = Callable[
    [PipelineDepressurizationCaseSpec, HEMPipelineDepressurizationConfig],
    PipelineCaseResult,
]


def _baseline_provenance(
    provenance: Mapping[str, object] | None,
    *,
    case_runner: CflBaselineRunner,
) -> dict[str, object]:
    if provenance is None:
        if case_runner is not run_pipeline_depressurization_case:
            raise HEMPipelineCflBaselineError(
                "an injected baseline case_runner requires explicit backend provenance"
            )
        raw = collect_cfl_runtime_provenance()
    else:
        raw = normalize_cfl_provenance(provenance)
    result = dict(raw)
    result["parent_analysis_id"] = result.get("analysis_id", CFL_ANALYSIS_ID)
    result["analysis_id"] = BASELINE_ANALYSIS_ID
    result["analysis_model"] = ANALYSIS_MODEL
    result["property_backend_name"] = PROPERTY_BACKEND_NAME
    result["verification_only"] = True
    result["design_use_acceptance"] = False
    result["production_hem_activation_approved"] = False
    return normalize_cfl_provenance(result)


@dataclass(frozen=True)
class HEMPipelineCflBaselineResult:
    """Exact replay of the three 128-cell / CFL=0.10 PR #82 rows."""

    cases: tuple[MeshCaseMetrics, ...]
    provenance: dict[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": "stage7_lco2_hem_pipeline_cfl_0p10_baseline_v1",
            "scope": "verification_only",
            "analysis_identity": {
                "analysis_id": str(self.provenance["analysis_id"]),
                "model": str(self.provenance["analysis_model"]),
                "backend": str(self.provenance["property_backend_name"]),
                "version": str(self.provenance["property_backend_version"]),
            },
            "provenance": dict(self.provenance),
            "case_count": len(self.cases),
            "n_cells": CFL_CELL_COUNT,
            "dx_m": 1.0 / CFL_CELL_COUNT,
            "cfl": BASELINE_CFL,
            "maximum_steps": 8000,
            "case_ids": [case.case_id for case in self.cases],
            "all_pr82_rows_reproduced_exactly": len(self.cases) == 3,
            "low_cfl_matrix_executed": False,
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
    provenance: Mapping[str, object] | None = None,
) -> HEMPipelineCflBaselineResult:
    """Run and require exact identity for all three PR #82 baseline rows."""

    resolved_provenance = _baseline_provenance(
        provenance,
        case_runner=case_runner,
    )
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
        provenance=resolved_provenance,
    )


def baseline_case_csv_rows(
    result: HEMPipelineCflBaselineResult,
) -> list[dict[str, object]]:
    """Return standalone CSV rows with backend and approval provenance embedded."""

    provenance = result.provenance
    prefix = {
        "analysis_id": provenance["analysis_id"],
        "analysis_model": provenance["analysis_model"],
        "property_backend_name": provenance["property_backend_name"],
        "property_backend_version": provenance["property_backend_version"],
        "source_git_sha": provenance["source_git_sha"],
        "verification_only": True,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
        "CFL_independent_crossing_verified": False,
        "Gate_P2_passed": False,
    }
    return [{**prefix, **asdict(case)} for case in result.cases]


def write_cfl_0p10_baseline_artifacts(
    output_dir: str | Path,
) -> tuple[HEMPipelineCflBaselineResult, dict[str, Path]]:
    """Run the exact replay and write traceable JSON, CSV, and Markdown evidence."""

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

    rows = baseline_case_csv_rows(result)
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
        f"analysis ID:       {provenance['analysis_id']}",
        f"model:             {provenance['analysis_model']}",
        f"backend:           {provenance['property_backend_name']}",
        f"backend version:   {provenance['property_backend_version']}",
        f"source Git SHA:    {provenance['source_git_sha']}",
        "design use:       false",
        "production HEM:   false",
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
