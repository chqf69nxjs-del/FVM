"""Traceable artifact bundle for the fixed Stage 7 pipeline CFL matrix.

This module executes the reviewed 128-cell, 2/3/4 MPa, CFL
0.10/0.05/0.025 software-sensitivity matrix.  It reuses the immutable
contract merged in PR #84 and does not alter the production solver, flux,
boundary, HEM phase/projection algorithms, acoustic closure, or tolerances.

The independent local-PC checkpoint is complete with the Gate 3 disposition
NUMERICALLY_EQUIVALENT.  The generated evidence records the active Gate 4
execution while keeping low-CFL acceptance, CFL independence, physical
Validation, design use, and production HEM activation explicitly unapproved.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, fields
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics
from .hem_pipeline_cfl_sensitivity import (
    CFL_CELL_COUNT,
    CFL_STEP_CAPS,
    CFL_VALUES,
    FOUR_MPA_CASE_ID,
    HEMPipelineCflSensitivityError,
    HEMPipelineCflSensitivityResult,
    collect_cfl_runtime_provenance,
    run_fixed_pipeline_cfl_sensitivity_matrix,
)
from .hem_pipeline_depressurization_first_crossing import (
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineCellRecord,
    PipelineStepRecord,
    run_pipeline_depressurization_case,
)


PLOT_KEYS: tuple[str, ...] = (
    "plot_qeq",
    "plot_margin",
    "plot_time_position",
    "plot_sound_speed",
)


class HEMPipelineCflEvidenceError(RuntimeError):
    """Raised when the reviewed Gate 4 artifact cannot be retained safely."""


def _flatten_csv(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    if any(list(row) != fieldnames for row in rows):
        raise HEMPipelineCflEvidenceError(
            f"inconsistent CSV field ordering while writing {path.name}"
        )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten_csv(value) for key, value in row.items()})


def _identity_prefix(provenance: Mapping[str, object]) -> dict[str, object]:
    required = (
        "analysis_id",
        "analysis_model",
        "property_backend_name",
        "property_backend_version",
        "source_git_sha",
        "checkout_git_sha",
        "git_status_porcelain",
    )
    missing = [key for key in required if key not in provenance]
    if missing:
        raise HEMPipelineCflEvidenceError(
            f"CFL evidence provenance is missing fields: {missing}"
        )
    status = str(provenance["git_status_porcelain"])
    return {
        "analysis_id": provenance["analysis_id"],
        "analysis_model": provenance["analysis_model"],
        "property_backend_name": provenance["property_backend_name"],
        "property_backend_version": provenance["property_backend_version"],
        "source_git_sha": provenance["source_git_sha"],
        "checkout_git_sha": provenance["checkout_git_sha"],
        "git_status_porcelain": status,
        "checkout_is_clean": status == "",
        "verification_only": True,
        "local_pc_checkpoint_completed": True,
        "low_cfl_result_accepted": False,
        "central_record_promotion_allowed": False,
        "Gate_P2_passed": False,
        "mesh_independent_crossing_verified": False,
        "CFL_independent_crossing_verified": False,
        "near_saturation_acoustic_continuity_approved": False,
        "post_crossing_propagation_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }


def standalone_case_rows(
    result: HEMPipelineCflSensitivityResult,
) -> list[dict[str, object]]:
    """Return independently traceable one-row-per-run evidence."""

    prefix = _identity_prefix(result.provenance)
    return [{**prefix, **asdict(case)} for case in result.cases]


def _assert_same_runtime_provenance(
    before: Mapping[str, object],
    after: Mapping[str, object],
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
    mismatch = {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in keys
        if before.get(key) != after.get(key)
    }
    if mismatch:
        raise HEMPipelineCflEvidenceError(
            "runtime provenance changed during the fixed matrix: "
            + json.dumps(mismatch, sort_keys=True)
        )


def _plot_identity(result: HEMPipelineCflSensitivityResult) -> tuple[str, dict[str, str]]:
    provenance = result.provenance
    metadata = {
        "analysis_id": str(provenance["analysis_id"]),
        "case": FOUR_MPA_CASE_ID,
        "model": str(provenance["analysis_model"]),
        "backend": str(provenance["property_backend_name"]),
        "version": str(provenance["property_backend_version"]),
        "source_git_sha": str(provenance["source_git_sha"]),
        "verification_only": "true",
        "low_cfl_result_accepted": "false",
    }
    header = (
        f"case={metadata['case']} | model={metadata['model']} | "
        f"backend={metadata['backend']} | version={metadata['version']}\n"
        f"source_git_sha={metadata['source_git_sha']} | verification only"
    )
    return header, metadata


def _generate_plots(
    target: Path,
    result: HEMPipelineCflSensitivityResult,
) -> dict[str, Path]:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # pragma: no cover - optional plotting path
        raise HEMPipelineCflEvidenceError(
            "matplotlib is required for the reviewed CFL-sensitivity artifact bundle"
        ) from exc

    control = sorted(
        [case for case in result.cases if case.case_id == FOUR_MPA_CASE_ID],
        key=lambda item: CFL_VALUES.index(float(item.cfl)),
    )
    if [float(case.cfl) for case in control] != list(CFL_VALUES):
        raise HEMPipelineCflEvidenceError("the fixed 4 MPa CFL sequence is incomplete")

    cfl = np.asarray([case.cfl for case in control], dtype=float)
    q = np.asarray(
        [max(case.maximum_crossing_quality, 1.0e-16) for case in control],
        dtype=float,
    )
    q_u = np.asarray(
        [
            np.nan
            if case.crossing_q_from_internal_energy is None
            else case.crossing_q_from_internal_energy
            for case in control
        ],
        dtype=float,
    )
    q_v = np.asarray(
        [
            np.nan
            if case.crossing_q_from_specific_volume is None
            else case.crossing_q_from_specific_volume
            for case in control
        ],
        dtype=float,
    )
    times = np.asarray(
        [
            np.nan if case.normalized_crossing_time is None else case.normalized_crossing_time
            for case in control
        ],
        dtype=float,
    )
    positions = np.asarray(
        [
            np.nan
            if case.normalized_crossing_distance_from_outlet is None
            else case.normalized_crossing_distance_from_outlet
            for case in control
        ],
        dtype=float,
    )
    ratios = np.asarray(
        [
            np.nan
            if case.sound_speed_ratio_raw_to_pre is None
            else case.sound_speed_ratio_raw_to_pre
            for case in control
        ],
        dtype=float,
    )

    header, metadata = _plot_identity(result)
    paths: dict[str, Path] = {}

    fig, ax = plt.subplots(figsize=(8.2, 5.8))
    ax.plot(cfl, q, marker="o")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("CFL")
    ax.set_ylabel("maximum q_eq (display floor 1e-16)")
    ax.set_title("4 MPa crossing quality versus time-step refinement")
    ax.grid(True, which="both", alpha=0.3)
    fig.suptitle(header, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    paths["plot_qeq"] = target / "cfl_qeq_vs_cfl.png"
    fig.savefig(paths["plot_qeq"], dpi=180, metadata=metadata, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.8))
    ax.plot(cfl, q_u, marker="o", label="q from internal energy")
    ax.plot(cfl, q_v, marker="o", label="q from specific volume")
    ax.axhline(0.0)
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("CFL")
    ax.set_ylabel("quality-like saturation coordinate")
    ax.set_title("4 MPa saturation-side depth versus CFL")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.suptitle(header, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    paths["plot_margin"] = target / "cfl_saturation_margin_vs_cfl.png"
    fig.savefig(paths["plot_margin"], dpi=180, metadata=metadata, bbox_inches="tight")
    plt.close(fig)

    fig, ax_time = plt.subplots(figsize=(8.2, 5.8))
    ax_position = ax_time.twinx()
    time_line = ax_time.plot(cfl, times, marker="o", label="t/t_acoustic,0")
    position_line = ax_position.plot(
        cfl, positions, marker="s", label="outlet distance/L"
    )
    ax_time.set_xscale("log")
    ax_time.invert_xaxis()
    ax_time.set_xlabel("CFL")
    ax_time.set_ylabel("normalized crossing time")
    ax_position.set_ylabel("normalized distance from outlet")
    ax_time.set_title("4 MPa crossing time and position versus CFL")
    lines = time_line + position_line
    ax_time.legend(lines, [line.get_label() for line in lines])
    ax_time.grid(True, alpha=0.3)
    fig.suptitle(header, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    paths["plot_time_position"] = target / "cfl_crossing_time_position.png"
    fig.savefig(
        paths["plot_time_position"], dpi=180, metadata=metadata, bbox_inches="tight"
    )
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.8))
    ax.plot(cfl, ratios, marker="o")
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("CFL")
    ax.set_ylabel("raw crossing sound speed / pre-crossing liquid sound speed")
    ax.set_title("4 MPa near-saturation sound-speed jump versus CFL")
    ax.grid(True, alpha=0.3)
    fig.suptitle(header, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    paths["plot_sound_speed"] = target / "cfl_sound_speed_jump.png"
    fig.savefig(
        paths["plot_sound_speed"], dpi=180, metadata=metadata, bbox_inches="tight"
    )
    plt.close(fig)
    return paths


def write_pipeline_cfl_sensitivity_artifacts(
    output_dir: str | Path,
) -> tuple[HEMPipelineCflSensitivityResult, dict[str, Path]]:
    """Execute once and stream the fixed Gate 4 artifact bundle."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary_json": target / "pipeline_cfl_sensitivity_summary.json",
        "cases_csv": target / "pipeline_cfl_sensitivity_cases.csv",
        "steps_csv": target / "pipeline_cfl_sensitivity_steps.csv",
        "cells_csv": target / "pipeline_cfl_sensitivity_cells.csv",
        "crossing_metrics_csv": target / "pipeline_cfl_sensitivity_4mpa_metrics.csv",
        "markdown": target / "pipeline_cfl_sensitivity.md",
        "npz": target / "pipeline_cfl_sensitivity.npz",
    }

    pre_provenance = collect_cfl_runtime_provenance()
    prefix = _identity_prefix(pre_provenance)
    step_fields = list(prefix) + ["n_cells", "dx_m", "cfl", "maximum_steps"] + [
        item.name for item in fields(PipelineStepRecord)
    ]
    cell_fields = list(prefix) + ["n_cells", "dx_m", "cfl", "maximum_steps"] + [
        item.name for item in fields(PipelineCellRecord)
    ]

    step_handle = paths["steps_csv"].open("w", newline="", encoding="utf-8")
    cell_handle = paths["cells_csv"].open("w", newline="", encoding="utf-8")
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
            step_writer.writerow({key: _flatten_csv(value) for key, value in row.items()})
        for cell in raw.cells:
            row = {**run_prefix, **asdict(cell)}
            cell_writer.writerow({key: _flatten_csv(value) for key, value in row.items()})
        step_handle.flush()
        cell_handle.flush()

    def execute_reviewed_case(case, config):
        # Reuse the real reviewed runner while passing the provenance snapshot captured
        # before any artifact file is created.  This prevents the artifact directory
        # itself from making the second Git-status probe appear dirty.
        return run_pipeline_depressurization_case(case, config)

    try:
        result = run_fixed_pipeline_cfl_sensitivity_matrix(
            case_runner=execute_reviewed_case,
            on_case_result=retain,
            provenance=pre_provenance,
        )
    finally:
        step_handle.close()
        cell_handle.close()

    _assert_same_runtime_provenance(pre_provenance, result.provenance)
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
        "local_pc_checkpoint_completed": True,
        "low_cfl_result_accepted": False,
        "central_record_promotion_allowed": False,
        "gate4_execution_completed_in_ci": True,
    }
    paths["summary_json"].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    np.savez_compressed(
        paths["npz"],
        cfl=np.asarray([case.cfl for case in result.cases], dtype=float),
        final_boundary_pressure_pa=np.asarray(
            [case.final_boundary_pressure_pa for case in result.cases], dtype=float
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
            [case.maximum_crossing_quality for case in result.cases], dtype=float
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
        "`VERIFICATION ONLY; 128 CELLS; FIRST-ORDER RUSANOV; GATE 3 COMPLETE; RESULT NOT ACCEPTED`",
        "",
        "```text",
        f"analysis ID:       {result.provenance['analysis_id']}",
        f"model:             {result.provenance['analysis_model']}",
        f"backend:           {result.provenance['property_backend_name']}",
        f"backend version:   {result.provenance['property_backend_version']}",
        f"source Git SHA:    {result.provenance['source_git_sha']}",
        "low-CFL accepted:  false",
        "```",
        "",
        "| pressure [MPa] | CFL | outcome | step | crossing t/t_a | outlet distance/L | max q_eq |",
        "|---:|---:|---|---:|---:|---:|---:|",
    ]
    for case in result.cases:
        lines.append(
            f"| {case.final_boundary_pressure_pa / 1.0e6:.0f} | {case.cfl:.3f} | "
            f"`{case.outcome}` | {case.step_count} | "
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
            "These labels are Gate 4 execution observations only. They remain unaccepted",
            "until dedicated review and a separate central-record promotion.",
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
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result, paths


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixed Stage 7 128-cell low-CFL software-sensitivity matrix."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result, paths = write_pipeline_cfl_sensitivity_artifacts(args.output_dir)
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
