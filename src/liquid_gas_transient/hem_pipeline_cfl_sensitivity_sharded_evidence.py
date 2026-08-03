"""Sharded execution and aggregation for the fixed Stage 7 CFL matrix.

The numerical contract is unchanged.  The nine reviewed runs are split into
three independent CFL columns so that GitHub Actions does not exceed one job's
wall-clock limit.  A final aggregation job validates the three shards and
reconstructs the same traceable Gate 4 evidence bundle without rerunning the
solver.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

from .hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics, _case_metrics
from .hem_pipeline_cfl_sensitivity import (
    CFL_ANALYSIS_ID,
    CFL_CELL_COUNT,
    CFL_STEP_CAPS,
    CFL_VALUES,
    FOUR_MPA_CASE_ID,
    HEMPipelineCflSensitivityConfig,
    HEMPipelineCflSensitivityError,
    HEMPipelineCflSensitivityResult,
    _assert_128_cell_cfl_0p10_baseline,
    _cfl_token,
    classify_four_mpa_cfl_sequence,
    collect_cfl_runtime_provenance,
    normalize_cfl_provenance,
)
from .hem_pipeline_cfl_sensitivity_evidence import (
    PLOT_KEYS,
    _assert_same_runtime_provenance,
    _flatten_csv,
    _generate_plots,
    _identity_prefix,
    _write_rows,
    standalone_case_rows,
)
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineCellRecord,
    PipelineDepressurizationCaseSpec,
    PipelineStepRecord,
    run_pipeline_depressurization_case,
)

SHARD_SCHEMA_VERSION = "stage7_lco2_hem_pipeline_cfl_sensitivity_shard_v1"
COMBINED_EXECUTION_MODE = "three_parallel_cfl_columns_then_aggregate"
SHARD_SUMMARY_NAME = "pipeline_cfl_sensitivity_shard.json"
CASES_CSV_NAME = "pipeline_cfl_sensitivity_cases.csv"
STEPS_CSV_NAME = "pipeline_cfl_sensitivity_steps.csv"
CELLS_CSV_NAME = "pipeline_cfl_sensitivity_cells.csv"


class HEMPipelineCflShardedEvidenceError(RuntimeError):
    """Raised when a CFL shard or the combined evidence is incomplete."""


@dataclass(frozen=True)
class HEMPipelineCflColumnResult:
    cfl: float
    cases: tuple[MeshCaseMetrics, ...]
    provenance: dict[str, object]

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": SHARD_SCHEMA_VERSION,
            "scope": "verification_only",
            "execution_mode": "one_fixed_cfl_column",
            "analysis_id": str(self.provenance["analysis_id"]),
            "analysis_model": str(self.provenance["analysis_model"]),
            "property_backend_name": str(
                self.provenance["property_backend_name"]
            ),
            "property_backend_version": str(
                self.provenance["property_backend_version"]
            ),
            "source_git_sha": str(self.provenance["source_git_sha"]),
            "checkout_git_sha": self.provenance.get("checkout_git_sha"),
            "git_status_porcelain": self.provenance.get(
                "git_status_porcelain", ""
            ),
            "cfl": self.cfl,
            "cfl_token": _cfl_token(self.cfl),
            "maximum_steps": CFL_STEP_CAPS[self.cfl],
            "case_count": len(self.cases),
            "case_ids": [case.case_id for case in self.cases],
            "cases": [asdict(case) for case in self.cases],
            "verification_only": True,
            "local_pc_checkpoint_completed": True,
            "low_cfl_result_accepted": False,
            "central_record_promotion_allowed": False,
            "CFL_independent_crossing_verified": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
            "provenance": dict(self.provenance),
        }


CflCaseRunner = Callable[
    [PipelineDepressurizationCaseSpec, HEMPipelineDepressurizationConfig],
    PipelineCaseResult,
]
CflCaseCallback = Callable[[PipelineCaseResult, MeshCaseMetrics], None]


def _resolved_cfl(value: float | str) -> float:
    if isinstance(value, bool):
        raise HEMPipelineCflShardedEvidenceError(
            f"CFL must be one of {CFL_VALUES}"
        )
    candidate = float(value)
    if candidate not in CFL_STEP_CAPS:
        raise HEMPipelineCflShardedEvidenceError(
            f"CFL must be one of {CFL_VALUES}"
        )
    return candidate


def run_fixed_pipeline_cfl_column(
    cfl: float | str,
    *,
    case_runner: CflCaseRunner = run_pipeline_depressurization_case,
    on_case_result: CflCaseCallback | None = None,
    provenance: Mapping[str, object] | None = None,
) -> HEMPipelineCflColumnResult:
    """Run exactly three reviewed pressure cases for one fixed CFL value."""

    value = _resolved_cfl(cfl)
    if case_runner is run_pipeline_depressurization_case:
        if provenance is not None:
            raise HEMPipelineCflShardedEvidenceError(
                "default-runner provenance must come from the actual runtime"
            )
        resolved_provenance = collect_cfl_runtime_provenance()
    else:
        if provenance is None:
            raise HEMPipelineCflShardedEvidenceError(
                "an injected case runner requires explicit provenance"
            )
        resolved_provenance = normalize_cfl_provenance(provenance)

    config = HEMPipelineCflSensitivityConfig.for_cfl(value)
    metrics: list[MeshCaseMetrics] = []
    for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
        raw = case_runner(case, config)
        metric = replace(
            _case_metrics(raw),
            run_id=(
                f"{case.case_id}__n{CFL_CELL_COUNT}"
                f"__cfl{_cfl_token(value)}"
            ),
        )
        if value == 0.10:
            _assert_128_cell_cfl_0p10_baseline(metric)
        if on_case_result is not None:
            on_case_result(raw, metric)
        metrics.append(metric)

    return HEMPipelineCflColumnResult(
        cfl=value,
        cases=tuple(metrics),
        provenance=dict(resolved_provenance),
    )


def write_pipeline_cfl_sensitivity_shard(
    output_dir: str | Path,
    cfl: float | str,
) -> tuple[HEMPipelineCflColumnResult, dict[str, Path]]:
    """Execute one CFL column and stream a self-contained shard artifact."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_json": target / SHARD_SUMMARY_NAME,
        "cases_csv": target / CASES_CSV_NAME,
        "steps_csv": target / STEPS_CSV_NAME,
        "cells_csv": target / CELLS_CSV_NAME,
    }

    pre_provenance = collect_cfl_runtime_provenance()
    prefix = _identity_prefix(pre_provenance)
    step_fields = list(prefix) + [
        "n_cells",
        "dx_m",
        "cfl",
        "maximum_steps",
    ] + [item.name for item in fields(PipelineStepRecord)]
    cell_fields = list(prefix) + [
        "n_cells",
        "dx_m",
        "cfl",
        "maximum_steps",
    ] + [item.name for item in fields(PipelineCellRecord)]

    step_handle = paths["steps_csv"].open(
        "w", newline="", encoding="utf-8"
    )
    cell_handle = paths["cells_csv"].open(
        "w", newline="", encoding="utf-8"
    )
    step_writer = csv.DictWriter(step_handle, fieldnames=step_fields)
    cell_writer = csv.DictWriter(cell_handle, fieldnames=cell_fields)
    step_writer.writeheader()
    cell_writer.writeheader()

    def retain(raw: PipelineCaseResult, metric: MeshCaseMetrics) -> None:
        run_prefix = {
            **prefix,
            "n_cells": metric.n_cells,
            "dx_m": metric.dx_m,
            "cfl": metric.cfl,
            "maximum_steps": metric.maximum_steps,
        }
        for step in raw.steps:
            row = {**run_prefix, **asdict(step)}
            step_writer.writerow(
                {key: _flatten_csv(value) for key, value in row.items()}
            )
        for cell in raw.cells:
            row = {**run_prefix, **asdict(cell)}
            cell_writer.writerow(
                {key: _flatten_csv(value) for key, value in row.items()}
            )
        step_handle.flush()
        cell_handle.flush()

    def execute_reviewed_case(case, config):
        return run_pipeline_depressurization_case(case, config)

    try:
        result = run_fixed_pipeline_cfl_column(
            cfl,
            case_runner=execute_reviewed_case,
            on_case_result=retain,
            provenance=pre_provenance,
        )
    finally:
        step_handle.close()
        cell_handle.close()

    _assert_same_runtime_provenance(
        pre_provenance, result.provenance
    )
    pseudo_full = HEMPipelineCflSensitivityResult(
        cases=result.cases,
        four_mpa_classifications=("CFL_SENSITIVITY_INCONCLUSIVE",),
        four_mpa_classification_rationale={
            "CFL_SENSITIVITY_INCONCLUSIVE": (
                "A single-CFL shard is not a cross-CFL classification."
            )
        },
        provenance=result.provenance,
    )
    _write_rows(paths["cases_csv"], standalone_case_rows(pseudo_full))
    paths["summary_json"].write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result, paths


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or ()), list(reader)


def _write_combined_csv(
    destination: Path,
    shard_paths: Sequence[Path],
) -> None:
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for path in shard_paths:
        current_header, current_rows = _read_csv(path)
        if header is None:
            header = current_header
        elif current_header != header:
            raise HEMPipelineCflShardedEvidenceError(
                f"CSV header mismatch while combining {path.name}"
            )
        rows.extend(current_rows)
    if not header:
        raise HEMPipelineCflShardedEvidenceError(
            f"no CSV header available for {destination.name}"
        )
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _load_shard(path: Path) -> HEMPipelineCflColumnResult:
    payload = json.loads(
        (path / SHARD_SUMMARY_NAME).read_text(encoding="utf-8")
    )
    if payload.get("schema_version") != SHARD_SCHEMA_VERSION:
        raise HEMPipelineCflShardedEvidenceError(
            f"invalid shard schema in {path}"
        )
    cfl = _resolved_cfl(payload["cfl"])
    cases = tuple(MeshCaseMetrics(**row) for row in payload["cases"])
    expected_case_ids = [
        case.case_id for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
    ]
    if [case.case_id for case in cases] != expected_case_ids:
        raise HEMPipelineCflShardedEvidenceError(
            f"unexpected case order in CFL {cfl} shard"
        )
    if len(cases) != 3 or any(float(case.cfl) != cfl for case in cases):
        raise HEMPipelineCflShardedEvidenceError(
            f"incomplete CFL {cfl} shard"
        )
    provenance = normalize_cfl_provenance(payload["provenance"])
    if cfl == 0.10:
        for metric in cases:
            _assert_128_cell_cfl_0p10_baseline(metric)
    return HEMPipelineCflColumnResult(cfl, cases, provenance)


def _assert_shard_provenance_equal(
    shards: Sequence[HEMPipelineCflColumnResult],
) -> None:
    keys = (
        "analysis_id",
        "analysis_model",
        "property_backend_name",
        "property_backend_version",
        "source_git_sha",
        "checkout_git_sha",
        "git_status_porcelain",
        "python_version",
        "numpy_version",
    )
    baseline = shards[0].provenance
    mismatch: dict[str, list[object]] = {}
    for key in keys:
        values = [shard.provenance.get(key) for shard in shards]
        if any(value != values[0] for value in values[1:]):
            mismatch[key] = values
    if mismatch:
        raise HEMPipelineCflShardedEvidenceError(
            "CFL shard provenance mismatch: "
            + json.dumps(mismatch, sort_keys=True)
        )


def _write_final_bundle(
    target: Path,
    result: HEMPipelineCflSensitivityResult,
    shard_dirs: Sequence[Path],
) -> dict[str, Path]:
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_json": target / "pipeline_cfl_sensitivity_summary.json",
        "cases_csv": target / CASES_CSV_NAME,
        "steps_csv": target / STEPS_CSV_NAME,
        "cells_csv": target / CELLS_CSV_NAME,
        "crossing_metrics_csv": (
            target / "pipeline_cfl_sensitivity_4mpa_metrics.csv"
        ),
        "markdown": target / "pipeline_cfl_sensitivity.md",
        "npz": target / "pipeline_cfl_sensitivity.npz",
    }

    _write_combined_csv(
        paths["steps_csv"],
        [path / STEPS_CSV_NAME for path in shard_dirs],
    )
    _write_combined_csv(
        paths["cells_csv"],
        [path / CELLS_CSV_NAME for path in shard_dirs],
    )
    case_rows = standalone_case_rows(result)
    _write_rows(paths["cases_csv"], case_rows)
    _write_rows(
        paths["crossing_metrics_csv"],
        [row for row in case_rows if row["case_id"] == FOUR_MPA_CASE_ID],
    )

    fixed = HEMPipelineDepressurizationConfig()
    payload = {
        **result.summary(),
        "immutable_pr77_base_config": asdict(fixed),
        "cfl_only_overrides": [
            {
                "n_cells": CFL_CELL_COUNT,
                "dx_m": fixed.length_m / CFL_CELL_COUNT,
                "cfl": cfl,
                "maximum_steps": CFL_STEP_CAPS[cfl],
            }
            for cfl in CFL_VALUES
        ],
        "execution_mode": COMBINED_EXECUTION_MODE,
        "cfl_shard_count": len(shard_dirs),
        "local_pc_checkpoint_completed": True,
        "low_cfl_result_accepted": False,
        "central_record_promotion_allowed": False,
        "gate4_execution_completed_in_ci": True,
    }
    paths["summary_json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    np.savez_compressed(
        paths["npz"],
        cfl=np.asarray([case.cfl for case in result.cases], dtype=float),
        final_boundary_pressure_pa=np.asarray(
            [case.final_boundary_pressure_pa for case in result.cases],
            dtype=float,
        ),
        crossing_time_s=np.asarray(
            [
                np.nan if case.crossing_time_s is None else case.crossing_time_s
                for case in result.cases
            ],
            dtype=float,
        ),
        crossing_distance_from_outlet_m=np.asarray(
            [
                np.nan
                if case.crossing_distance_from_outlet_m is None
                else case.crossing_distance_from_outlet_m
                for case in result.cases
            ],
            dtype=float,
        ),
        maximum_crossing_quality=np.asarray(
            [case.maximum_crossing_quality for case in result.cases],
            dtype=float,
        ),
        crossing_delta_u_sat_j_kg=np.asarray(
            [
                np.nan
                if case.crossing_delta_u_sat_j_kg is None
                else case.crossing_delta_u_sat_j_kg
                for case in result.cases
            ],
            dtype=float,
        ),
        crossing_delta_v_sat_m3_kg=np.asarray(
            [
                np.nan
                if case.crossing_delta_v_sat_m3_kg is None
                else case.crossing_delta_v_sat_m3_kg
                for case in result.cases
            ],
            dtype=float,
        ),
        sound_speed_ratio_raw_to_pre=np.asarray(
            [
                np.nan
                if case.sound_speed_ratio_raw_to_pre is None
                else case.sound_speed_ratio_raw_to_pre
                for case in result.cases
            ],
            dtype=float,
        ),
    )
    paths.update(_generate_plots(target, result))

    lines = [
        "# Stage 7 Pipeline CFL Sensitivity",
        "",
        (
            "`VERIFICATION ONLY; 128 CELLS; FIRST-ORDER RUSANOV; "
            "GATE 3 COMPLETE; RESULT NOT ACCEPTED`"
        ),
        "",
        "```text",
        f"analysis ID:       {result.provenance['analysis_id']}",
        f"model:             {result.provenance['analysis_model']}",
        f"backend:           {result.provenance['property_backend_name']}",
        (
            "backend version:   "
            f"{result.provenance['property_backend_version']}"
        ),
        f"source Git SHA:    {result.provenance['source_git_sha']}",
        f"execution mode:    {COMBINED_EXECUTION_MODE}",
        "low-CFL accepted:  false",
        "```",
        "",
        (
            "| pressure [MPa] | CFL | outcome | step | crossing t/t_a | "
            "outlet distance/L | max q_eq |"
        ),
        "|---:|---:|---|---:|---:|---:|---:|",
    ]
    for case in result.cases:
        lines.append(
            f"| {case.final_boundary_pressure_pa / 1.0e6:.0f} | "
            f"{case.cfl:.3f} | `{case.outcome}` | {case.step_count} | "
            f"{'' if case.normalized_crossing_time is None else format(case.normalized_crossing_time, '.17g')} | "
            f"{'' if case.normalized_crossing_distance_from_outlet is None else format(case.normalized_crossing_distance_from_outlet, '.17g')} | "
            f"{case.maximum_crossing_quality:.17g} |"
        )
    lines.extend(
        [
            "",
            "## 4 MPa diagnostic classifications",
            "",
            "```text",
            *result.four_mpa_classifications,
            "```",
            "",
            (
                "These labels are Gate 4 execution observations only. "
                "They remain unaccepted until dedicated review and a "
                "separate central-record promotion."
            ),
            "",
            "## Approval boundary",
            "",
            "```text",
            "Gate_P2_passed = false",
            "mesh_independent_crossing_verified = false",
            "CFL_independent_crossing_verified = false",
            "local_pc_checkpoint_completed = true",
            "low_cfl_result_accepted = false",
            "central_record_promotion_allowed = false",
            "near_saturation_acoustic_continuity_approved = false",
            "post_crossing_propagation_approved = false",
            "physical_validation = false",
            "design_use_acceptance = false",
            "production_hem_activation_approved = false",
            "```",
        ]
    )
    paths["markdown"].write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return paths


def combine_pipeline_cfl_sensitivity_shards(
    shard_dirs: Sequence[str | Path],
    output_dir: str | Path,
) -> tuple[HEMPipelineCflSensitivityResult, dict[str, Path]]:
    """Validate three CFL shards and build the authoritative full bundle."""

    directories = [Path(path) for path in shard_dirs]
    if len(directories) != len(CFL_VALUES):
        raise HEMPipelineCflShardedEvidenceError(
            f"expected {len(CFL_VALUES)} shard directories"
        )
    loaded = [(path, _load_shard(path)) for path in directories]
    by_cfl = {shard.cfl: (path, shard) for path, shard in loaded}
    if set(by_cfl) != set(CFL_VALUES) or len(by_cfl) != len(loaded):
        raise HEMPipelineCflShardedEvidenceError(
            f"expected exactly one shard for each CFL {CFL_VALUES}"
        )
    ordered_dirs = [by_cfl[cfl][0] for cfl in CFL_VALUES]
    ordered_shards = [by_cfl[cfl][1] for cfl in CFL_VALUES]
    _assert_shard_provenance_equal(ordered_shards)

    cases = tuple(
        case for shard in ordered_shards for case in shard.cases
    )
    classifications, rationale = classify_four_mpa_cfl_sequence(cases)
    result = HEMPipelineCflSensitivityResult(
        cases=cases,
        four_mpa_classifications=classifications,
        four_mpa_classification_rationale=rationale,
        provenance=dict(ordered_shards[0].provenance),
    )
    paths = _write_final_bundle(
        Path(output_dir), result, ordered_dirs
    )
    return result, paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    shard = subparsers.add_parser("shard")
    shard.add_argument("--cfl", required=True)
    shard.add_argument("--output-dir", type=Path, required=True)

    combine = subparsers.add_parser("combine")
    combine.add_argument(
        "--shard-dir",
        action="append",
        type=Path,
        required=True,
        dest="shard_dirs",
    )
    combine.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "shard":
        result, paths = write_pipeline_cfl_sensitivity_shard(
            args.output_dir, args.cfl
        )
        print(json.dumps(result.summary(), indent=2, sort_keys=True))
    else:
        result, paths = combine_pipeline_cfl_sensitivity_shards(
            args.shard_dirs, args.output_dir
        )
        print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
