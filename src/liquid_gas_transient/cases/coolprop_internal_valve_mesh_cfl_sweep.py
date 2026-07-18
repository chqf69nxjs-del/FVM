"""Stage 6 V-012 single-phase internal-valve mesh/CFL observation.

This module coordinates existing V-012A/B/C/D runners and analyzes their saved
artifacts. It does not change solver physics, the Kv law, the Mach cap, boundary
meaning, or conserved-energy treatment. The finest mesh is a comparison
reference rather than an exact solution, and lower CFL is not treated as truth.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping

import numpy as np

from .internal_valve_mesh_cfl_analysis import (
    build_aggregate_observation,
    extract_case_artifacts,
)


RunAdapter = Callable[[Path, dict[str, Any]], dict[str, Any]]
DYNAMIC_ITEMS = ("V-012B", "V-012C", "V-012D")
CASE_ROLES = {
    "V-012A": "preservation_sentinel",
    "V-012B": "finite_opening",
    "V-012C": "opening_ramp",
    "V-012D": "closing_ramp_complete_closure",
}


@dataclass(frozen=True)
class CoolPropInternalValveMeshCflSweepConfig:
    """Inputs for the planned 13-run V-012 mesh/CFL observation."""

    case_name: str = "v012_internal_valve_mesh_cfl_sweep"
    output_version: str = "v012_internal_valve_mesh_cfl_sweep_v2"
    mesh_cells: tuple[int, ...] = (50, 100, 200)
    cfl_values: tuple[float, ...] = (0.25, 0.5)
    mesh_comparison_cfl: float = 0.5
    cfl_comparison_n_cells: int = 100
    uniform_sentinel_n_cells: int = 50
    uniform_sentinel_cfl: float = 0.5

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.mesh_cells))) != self.mesh_cells:
            raise ValueError("mesh_cells must be unique and ascending")
        if not self.mesh_cells or any(
            value < 10 or value % 2 for value in self.mesh_cells
        ):
            raise ValueError(
                "mesh_cells must contain even integers of at least 10"
            )
        if tuple(sorted(set(self.cfl_values))) != self.cfl_values:
            raise ValueError("cfl_values must be unique and ascending")
        if not self.cfl_values or any(
            not np.isfinite(value) or not 0.0 < value <= 1.0
            for value in self.cfl_values
        ):
            raise ValueError("cfl_values must be finite and lie in (0, 1]")
        if self.mesh_comparison_cfl not in self.cfl_values:
            raise ValueError(
                "mesh_comparison_cfl must be listed in cfl_values"
            )
        if self.cfl_comparison_n_cells not in self.mesh_cells:
            raise ValueError(
                "cfl_comparison_n_cells must be listed in mesh_cells"
            )
        if (
            self.uniform_sentinel_n_cells < 10
            or self.uniform_sentinel_n_cells % 2
        ):
            raise ValueError(
                "uniform_sentinel_n_cells must be an even integer of at least 10"
            )
        if (
            not np.isfinite(self.uniform_sentinel_cfl)
            or not 0.0 < self.uniform_sentinel_cfl <= 1.0
        ):
            raise ValueError(
                "uniform_sentinel_cfl must be finite and lie in (0, 1]"
            )


def _cfl_token(cfl: float) -> str:
    """Return a round-trip-safe filesystem token for one finite CFL value."""

    value = float(cfl)
    if not np.isfinite(value):
        raise ValueError("cfl must be finite")
    return (
        repr(value)
        .replace("-", "m")
        .replace("+", "p")
        .replace(".", "p")
    )


def case_id_for(verification_item: str, n_cells: int, cfl: float) -> str:
    """Return a stable identifier for one V-012 numerical execution."""

    if verification_item not in CASE_ROLES:
        raise ValueError(f"unsupported verification item: {verification_item}")
    if n_cells < 10 or n_cells % 2:
        raise ValueError("n_cells must be an even integer of at least 10")
    prefix = verification_item.lower().replace("-", "")
    return f"{prefix}_n{int(n_cells):04d}_cfl{_cfl_token(cfl)}"


def build_run_plan(
    config: CoolPropInternalValveMeshCflSweepConfig,
) -> list[dict[str, Any]]:
    """Return the fixed, de-duplicated V-012 run plan."""

    plan: list[dict[str, Any]] = [
        {
            "case_id": case_id_for(
                "V-012A",
                config.uniform_sentinel_n_cells,
                config.uniform_sentinel_cfl,
            ),
            "verification_item": "V-012A",
            "case_role": CASE_ROLES["V-012A"],
            "n_cells": int(config.uniform_sentinel_n_cells),
            "cfl": float(config.uniform_sentinel_cfl),
            "comparison_groups": ["preservation_sentinel"],
        }
    ]

    pairs = {
        (n_cells, config.mesh_comparison_cfl)
        for n_cells in config.mesh_cells
    }
    pairs.update(
        (config.cfl_comparison_n_cells, cfl)
        for cfl in config.cfl_values
    )
    for verification_item in DYNAMIC_ITEMS:
        for n_cells, cfl in sorted(pairs):
            groups: list[str] = []
            if cfl == config.mesh_comparison_cfl:
                groups.append("mesh_comparison")
            if n_cells == config.cfl_comparison_n_cells:
                groups.append("cfl_comparison")
            plan.append(
                {
                    "case_id": case_id_for(
                        verification_item,
                        n_cells,
                        cfl,
                    ),
                    "verification_item": verification_item,
                    "case_role": CASE_ROLES[verification_item],
                    "n_cells": int(n_cells),
                    "cfl": float(cfl),
                    "comparison_groups": groups,
                }
            )

    case_ids = [str(item["case_id"]) for item in plan]
    if len(case_ids) != len(set(case_ids)):
        raise RuntimeError("generated V-012 sweep case IDs are not unique")
    return plan


def _default_run_adapters() -> dict[str, RunAdapter]:
    def run_uniform(
        output_dir: Path,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        from .coolprop_internal_valve_uniform import (
            CoolPropInternalValveUniformConfig,
            run_coolprop_internal_valve_uniform,
        )

        run_config = CoolPropInternalValveUniformConfig(
            case_name=str(item["case_id"]),
            n_cells=int(item["n_cells"]),
            cfl=float(item["cfl"]),
        )
        return run_coolprop_internal_valve_uniform(output_dir, run_config)

    def run_driven(
        output_dir: Path,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        from .coolprop_internal_valve_driven import (
            run_coolprop_internal_valve_driven,
        )
        from .internal_valve_driven_config import (
            CoolPropInternalValveDrivenConfig,
        )

        run_config = CoolPropInternalValveDrivenConfig(
            case_name=str(item["case_id"]),
            n_cells=int(item["n_cells"]),
            cfl=float(item["cfl"]),
        )
        return run_coolprop_internal_valve_driven(output_dir, run_config)

    def run_opening(
        output_dir: Path,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        from .coolprop_internal_valve_opening_ramp import (
            run_coolprop_internal_valve_opening_ramp,
        )
        from .internal_valve_opening_ramp_config import (
            CoolPropInternalValveOpeningRampConfig,
        )

        run_config = CoolPropInternalValveOpeningRampConfig(
            case_name=str(item["case_id"]),
            n_cells=int(item["n_cells"]),
            cfl=float(item["cfl"]),
        )
        return run_coolprop_internal_valve_opening_ramp(
            output_dir,
            run_config,
        )

    def run_closing(
        output_dir: Path,
        item: dict[str, Any],
    ) -> dict[str, Any]:
        from .coolprop_internal_valve_closing_ramp import (
            run_coolprop_internal_valve_closing_ramp,
        )
        from .internal_valve_closing_ramp_config import (
            CoolPropInternalValveClosingRampConfig,
        )

        run_config = CoolPropInternalValveClosingRampConfig(
            case_name=str(item["case_id"]),
            n_cells=int(item["n_cells"]),
            cfl=float(item["cfl"]),
        )
        return run_coolprop_internal_valve_closing_ramp(
            output_dir,
            run_config,
        )

    return {
        "V-012A": run_uniform,
        "V-012B": run_driven,
        "V-012C": run_opening,
        "V-012D": run_closing,
    }


_REQUIRED_METRIC_FIELDS = (
    "verification_item",
    "n_cells",
    "dx_m",
    "cfl_target",
    "overall_observation_execution_pass",
    "remained_single_phase",
    "missing_budget_fields",
    "budget_mass_relative_residual",
    "energy_budget_balance_relative_residual",
    "phase_vapor_mass_balance_relative_residual",
    "step_count",
    "property_backend_name",
    "coolprop_version",
    "property_backend_design_status",
)

_OPTIONAL_METRIC_FIELDS = (
    "all_history_finite",
    "positive_pressure",
    "positive_temperature",
    "positive_density",
    "positive_sound_speed",
    "mach_cap_activation_count",
    "max_applied_face_mach",
    "flow_sign_consistency_fraction",
    "max_abs_opening_error",
    "max_abs_pressure_disturbance_pa",
    "max_abs_velocity_m_s",
    "max_abs_mass_flux_mismatch_kg_m2_s",
    "max_abs_energy_flux_mismatch_w_m2",
    "max_abs_vapor_mass_flux_mismatch_kg_m2_s",
    "max_abs_momentum_difference_residual_pa",
    "max_abs_finite_opening_momentum_difference_residual_pa",
    "max_abs_flux_q_minus_applied_q_m3_s",
    "opening_monotonic_non_decreasing",
    "opening_monotonic_non_increasing",
    "primary_characteristic_direction_pass",
    "upstream_decompression_observed",
    "downstream_compression_observed",
    "upstream_compression_observed",
    "downstream_decompression_observed",
    "post_closure_sample_count",
    "post_closure_hydraulic_separation_fraction",
    "post_closure_no_flow_direction_fraction",
)


def _summary_row(
    item: dict[str, Any],
    metrics: Mapping[str, Any],
    run_dir: Path,
    runtime_s: float,
) -> dict[str, Any]:
    missing = [
        field for field in _REQUIRED_METRIC_FIELDS if field not in metrics
    ]
    if missing:
        raise ValueError(
            f"{item['case_id']} metrics missing required fields: "
            + ", ".join(missing)
        )
    if str(metrics["verification_item"]) != item["verification_item"]:
        raise ValueError(
            f"{item['case_id']} verification item mismatch: "
            f"{metrics['verification_item']}"
        )
    if int(metrics["n_cells"]) != int(item["n_cells"]):
        raise ValueError(f"{item['case_id']} n_cells mismatch")
    if not np.isclose(
        float(metrics["cfl_target"]),
        float(item["cfl"]),
        rtol=0.0,
        atol=0.0,
    ):
        raise ValueError(f"{item['case_id']} CFL mismatch")
    if (
        str(metrics["property_backend_design_status"])
        != "not_approved_for_design_use"
    ):
        raise ValueError(
            f"{item['case_id']} has unexpected property backend design status"
        )
    if not np.isfinite(float(metrics["dx_m"])):
        raise ValueError(f"{item['case_id']} has non-finite dx_m")
    if not np.isfinite(float(runtime_s)) or runtime_s < 0.0:
        raise ValueError(f"{item['case_id']} has invalid runtime")

    budget_fields = metrics["missing_budget_fields"]
    if not isinstance(budget_fields, (list, tuple)):
        raise ValueError(
            f"{item['case_id']} missing_budget_fields must be a sequence"
        )

    row: dict[str, Any] = {
        **item,
        "comparison_groups": ";".join(item["comparison_groups"]),
        "dx_m": float(metrics["dx_m"]),
        "execution_pass": bool(
            metrics["overall_observation_execution_pass"]
        ),
        "remained_single_phase": bool(metrics["remained_single_phase"]),
        "missing_budget_fields": ";".join(
            str(value) for value in budget_fields
        ),
        "budget_mass_relative_residual": float(
            metrics["budget_mass_relative_residual"]
        ),
        "energy_budget_balance_relative_residual": float(
            metrics["energy_budget_balance_relative_residual"]
        ),
        "phase_vapor_mass_balance_relative_residual": float(
            metrics["phase_vapor_mass_balance_relative_residual"]
        ),
        "step_count": int(metrics["step_count"]),
        "runtime_s": float(runtime_s),
        "property_backend_name": str(metrics["property_backend_name"]),
        "coolprop_version": str(metrics["coolprop_version"]),
        "property_backend_design_status": str(
            metrics["property_backend_design_status"]
        ),
        "source_metrics_path": (
            f"{item['case_id']}/{item['case_id']}_metrics.json"
        ),
    }
    for field in _OPTIONAL_METRIC_FIELDS:
        if field in metrics:
            row[field] = metrics[field]
    row.update(extract_case_artifacts(run_dir, item, metrics))
    row["summary_extraction_complete"] = True
    return row


def _single_identity(rows: list[dict[str, Any]], key: str) -> str:
    values = {str(row.get(key, "")) for row in rows}
    values.discard("")
    if len(values) != 1:
        raise ValueError(
            f"inconsistent or missing {key} across selected runs: "
            f"{sorted(values)}"
        )
    return next(iter(values))


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty V-012 sweep summary")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: _csv_value(row.get(key, "")) for key in fields}
            )


def _report_lines(metrics: dict[str, Any]) -> list[str]:
    lines = [
        "# V-012 internal-valve mesh/CFL sweep",
        "",
        "Software / numerical verification only; not physical Validation or "
        "design-use acceptance.",
        "",
        f"- planned run count: `{metrics['planned_run_count']}`",
        f"- executed run count: `{metrics['executed_run_count']}`",
        f"- partial execution: `{metrics['partial_execution']}`",
        f"- selected execution pass: "
        f"`{metrics['overall_selected_execution_pass']}`",
        f"- full sweep execution pass: "
        f"`{metrics['overall_sweep_execution_pass']}`",
        f"- aggregate trend analysis complete: "
        f"`{metrics['aggregate_trend_analysis_complete']}`",
        "- formal regression band applied: `false`",
        "- finest mesh is an exact solution: `false`",
        "- lower CFL is truth: `false`",
        "",
        "## Executed rows",
        "",
        "| case | item | n | CFL | pass | analysis | single phase | runtime [s] |",
        "|---|---|---:|---:|---|---|---|---:|",
    ]
    for row in metrics["summary_rows"]:
        lines.append(
            "| {case_id} | {verification_item} | {n_cells} | "
            "{cfl:.6g} | {execution_pass} | {analysis_complete} | "
            "{single_phase} | {runtime:.6g} |".format(
                case_id=row["case_id"],
                verification_item=row["verification_item"],
                n_cells=row["n_cells"],
                cfl=float(row["cfl"]),
                execution_pass=row["execution_pass"],
                analysis_complete=row["analysis_complete"],
                single_phase=row["remained_single_phase"],
                runtime=float(row["runtime_s"]),
            )
        )
    if metrics["partial_execution"]:
        lines.extend(
            [
                "",
                "Aggregate trend analysis and comparison plots require the "
                "complete planned run set.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## 400-cell decision",
                "",
                f"- `{metrics['aggregate_observation']['cell_400_decision']}`",
                "",
            ]
        )
    return lines


def run_coolprop_internal_valve_mesh_cfl_sweep(
    output_dir: Path | str,
    config: CoolPropInternalValveMeshCflSweepConfig | None = None,
    *,
    selected_case_ids: tuple[str, ...] | None = None,
    runner_adapters: Mapping[str, RunAdapter] | None = None,
) -> dict[str, Any]:
    """Execute all or a selected subset of the planned V-012 sweep."""

    cfg = config or CoolPropInternalValveMeshCflSweepConfig()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    full_plan = build_run_plan(cfg)
    by_id = {str(item["case_id"]): item for item in full_plan}
    if selected_case_ids is None:
        selected_plan = full_plan
    else:
        if not selected_case_ids:
            raise ValueError("selected_case_ids must not be empty")
        unknown = [
            case_id for case_id in selected_case_ids if case_id not in by_id
        ]
        if unknown:
            raise ValueError(
                "unknown selected V-012 sweep case IDs: "
                + ", ".join(unknown)
            )
        if len(set(selected_case_ids)) != len(selected_case_ids):
            raise ValueError("selected_case_ids must be unique")
        selected_plan = [by_id[case_id] for case_id in selected_case_ids]

    adapters = _default_run_adapters()
    if runner_adapters is not None:
        adapters.update(dict(runner_adapters))

    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for item in selected_plan:
        verification_item = str(item["verification_item"])
        if verification_item not in adapters:
            raise KeyError(f"missing runner adapter for {verification_item}")
        run_dir = directory / str(item["case_id"])
        run_started = time.perf_counter()
        run_metrics = adapters[verification_item](run_dir, item)
        runtime_s = time.perf_counter() - run_started
        rows.append(_summary_row(item, run_metrics, run_dir, runtime_s))

    backend_name = _single_identity(rows, "property_backend_name")
    coolprop_version = _single_identity(rows, "coolprop_version")
    design_status = _single_identity(
        rows,
        "property_backend_design_status",
    )
    selected_pass = all(
        bool(row["execution_pass"])
        and bool(row["remained_single_phase"])
        and not str(row["missing_budget_fields"])
        and bool(row["summary_extraction_complete"])
        and bool(row["analysis_complete"])
        for row in rows
    )
    partial_execution = len(rows) != len(full_plan)
    aggregate = (
        build_aggregate_observation(rows)
        if not partial_execution
        else {
            "mesh_observation_complete": False,
            "cfl_observation_complete": False,
            "cell_400_decision": "deferred_until_complete_sweep",
        }
    )
    aggregate_complete = bool(
        not partial_execution
        and aggregate["mesh_observation_complete"]
        and aggregate["cfl_observation_complete"]
    )
    metrics: dict[str, Any] = {
        "case_name": cfg.case_name,
        "output_version": cfg.output_version,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "formal_regression_band_applied": False,
        "property_backend_name": backend_name,
        "coolprop_version": coolprop_version,
        "property_backend_design_status": design_status,
        "planned_run_count": len(full_plan),
        "executed_run_count": len(rows),
        "partial_execution": partial_execution,
        "run_plan": full_plan,
        "selected_case_ids": [
            str(item["case_id"]) for item in selected_plan
        ],
        "summary_rows": rows,
        "overall_selected_execution_pass": bool(selected_pass),
        "overall_sweep_execution_pass": bool(
            selected_pass and not partial_execution and aggregate_complete
        ),
        "aggregate_trend_analysis_complete": aggregate_complete,
        "aggregate_observation": aggregate,
        "comparison_plots_complete": False,
        "runtime_s": float(time.perf_counter() - started),
        "finest_mesh_is_exact_solution": False,
        "lower_cfl_is_truth": False,
        "limitations": [
            "finest mesh is a comparison reference, not an exact solution",
            "lower CFL is not treated as truth",
            "no formal regression band is applied",
            "comparison plots are added after summary review",
            "not physical Validation or design-use acceptance",
        ],
    }

    stem = cfg.case_name
    config_payload = {
        **asdict(cfg),
        "run_plan": full_plan,
        "selected_case_ids": metrics["selected_case_ids"],
    }
    (directory / f"{stem}_config.json").write_text(
        json.dumps(config_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / f"{stem}_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(directory / f"{stem}_summary.csv", rows)
    (directory / f"{stem}_report.md").write_text(
        "\n".join(_report_lines(metrics)) + "\n",
        encoding="utf-8",
    )
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the V-012 internal-valve mesh/CFL sweep",
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        default=None,
        help="execute only the named planned case; repeat as needed",
    )
    args = parser.parse_args(argv)
    result = run_coolprop_internal_valve_mesh_cfl_sweep(
        args.output_dir,
        selected_case_ids=(
            tuple(args.case_ids) if args.case_ids is not None else None
        ),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
