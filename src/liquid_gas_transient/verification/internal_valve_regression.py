"""V-012 single-phase internal-valve CI-light regression checks.

These checks are broad software/numerical regression sentinels only. They are not
physical Validation, design-use acceptance, equipment-model approval, operating
limits, or a claim that the CI-light mesh is a design mesh.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import tempfile
from typing import Any, Iterable, Mapping

from liquid_gas_transient.cases.coolprop_internal_valve_mesh_cfl_sweep import (
    CoolPropInternalValveMeshCflSweepConfig,
    case_id_for,
    run_coolprop_internal_valve_mesh_cfl_sweep,
)


EXPECTED_ITEMS = ("V-012A", "V-012B", "V-012C", "V-012D")


@dataclass(frozen=True)
class InternalValveRegressionLimits:
    """Broad CI-light limits derived from the PR #40 coarse observations."""

    profile_name: str = "coolprop_internal_valve_ci_light_v1"
    n_cells: int = 50
    cfl: float = 0.5
    required_backend_name: str = "coolprop_co2"
    required_coolprop_version: str = "8.0.0"
    required_design_status: str = "not_approved_for_design_use"

    max_abs_budget_relative_residual: float = 1.0e-12
    max_abs_opening_error: float = 1.0e-12
    max_abs_mass_flux_mismatch_kg_m2_s: float = 1.0e-12
    max_abs_energy_flux_mismatch_w_m2: float = 1.0e-8
    max_abs_vapor_mass_flux_mismatch_kg_m2_s: float = 1.0e-12
    max_abs_flux_q_minus_applied_q_m3_s: float = 1.0e-15
    max_flow_relative_difference: float = 1.0e-10
    max_characteristic_leakage_ratio: float = 1.0e-3

    v012a_max_abs_q_m3_s: float = 1.0e-15
    v012a_max_pressure_disturbance_pa: float = 1.0e-6
    v012a_max_velocity_m_s: float = 1.0e-12

    v012b_min_initial_q_m3_s: float = 3.0e-5
    v012b_max_initial_q_m3_s: float = 4.0e-5
    v012b_min_final_q_m3_s: float = 2.0e-5
    v012b_max_final_q_m3_s: float = 3.5e-5
    v012b_max_p50_offset_s: float = 8.0e-3
    v012b_min_characteristic_peak_pa: float = 50.0
    v012b_max_characteristic_peak_pa: float = 200.0

    v012c_max_abs_initial_q_m3_s: float = 1.0e-15
    v012c_min_max_q_m3_s: float = 3.0e-5
    v012c_max_max_q_m3_s: float = 6.0e-5
    v012c_min_final_q_m3_s: float = 3.0e-5
    v012c_max_final_q_m3_s: float = 6.0e-5
    v012c_max_p50_offset_s: float = 5.0e-3
    v012c_min_characteristic_peak_pa: float = 150.0
    v012c_max_characteristic_peak_pa: float = 400.0

    v012d_min_initial_q_m3_s: float = 6.0e-5
    v012d_max_initial_q_m3_s: float = 8.0e-5
    v012d_max_abs_final_q_m3_s: float = 1.0e-15
    v012d_max_p50_offset_s: float = 8.0e-3
    v012d_min_characteristic_peak_pa: float = 100.0
    v012d_max_characteristic_peak_pa: float = 300.0
    v012d_max_abs_post_closure_q_m3_s: float = 1.0e-15
    v012d_max_abs_post_closure_mass_flux_kg_m2_s: float = 1.0e-12
    v012d_max_abs_post_closure_energy_flux_w_m2: float = 1.0e-8
    v012d_max_abs_post_closure_vapor_flux_kg_m2_s: float = 1.0e-12
    v012d_max_abs_finite_opening_momentum_residual_pa: float = 1.0e-8


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _true(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _empty(value: Any) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def evaluate_internal_valve_regression(
    summary_rows: Iterable[Mapping[str, Any]],
    limits: InternalValveRegressionLimits | None = None,
) -> dict[str, Any]:
    """Evaluate four precomputed CI-light summary rows without running the solver."""

    lim = limits or InternalValveRegressionLimits()
    rows = [dict(row) for row in summary_rows]
    checks: dict[str, dict[str, Any]] = {}
    failed: list[str] = []

    def add(
        name: str,
        ok: bool,
        value: Any = None,
        expected: Any = None,
        *,
        missing: bool = False,
    ) -> None:
        checks[name] = {
            "pass": bool(ok),
            "value": value,
            "expected": expected,
            "missing": bool(missing),
        }
        if not ok:
            failed.append(name)

    def require_true(name: str, row: Mapping[str, Any], key: str | None = None) -> None:
        source_key = key or name
        if source_key not in row:
            add(name, False, missing=True)
        else:
            add(name, _true(row[source_key]), row[source_key], True)

    def require_equal(name: str, value: Any, expected: Any) -> None:
        add(name, value == expected, value, expected, missing=value is None)

    def require_abs_le(name: str, value: Any, limit: float) -> None:
        number = _number(value)
        add(
            name,
            number is not None and abs(number) <= limit,
            value,
            f"abs <= {limit}",
            missing=number is None,
        )

    def require_le(name: str, value: Any, limit: float) -> None:
        number = _number(value)
        add(
            name,
            number is not None and number <= limit,
            value,
            f"<= {limit}",
            missing=number is None,
        )

    def require_ge(name: str, value: Any, limit: float) -> None:
        number = _number(value)
        add(
            name,
            number is not None and number >= limit,
            value,
            f">= {limit}",
            missing=number is None,
        )

    def require_range(name: str, value: Any, low: float, high: float) -> None:
        number = _number(value)
        add(
            name,
            number is not None and low <= number <= high,
            value,
            f"{low} <= value <= {high}",
            missing=number is None,
        )

    add("row_count", len(rows) == 4, len(rows), 4)
    items = [str(row.get("verification_item", "")) for row in rows]
    add(
        "expected_items_present_once",
        sorted(items) == sorted(EXPECTED_ITEMS),
        items,
        list(EXPECTED_ITEMS),
    )
    by_item = {str(row.get("verification_item", "")): row for row in rows}

    for item in EXPECTED_ITEMS:
        row = by_item.get(item)
        if row is None:
            add(f"{item}.row_present", False, missing=True)
            continue

        prefix = item.lower().replace("-", "")
        require_equal(f"{prefix}.n_cells", _number(row.get("n_cells")), float(lim.n_cells))
        require_equal(f"{prefix}.cfl", _number(row.get("cfl")), float(lim.cfl))
        for key in (
            "execution_pass",
            "analysis_complete",
            "summary_extraction_complete",
            "all_history_finite",
            "positive_pressure",
            "positive_temperature",
            "positive_density",
            "positive_sound_speed",
            "remained_single_phase",
        ):
            require_true(f"{prefix}.{key}", row, key)

        add(
            f"{prefix}.missing_budget_fields_empty",
            _empty(row.get("missing_budget_fields")),
            row.get("missing_budget_fields"),
            "empty",
            missing="missing_budget_fields" not in row,
        )
        require_equal(
            f"{prefix}.property_backend_name",
            row.get("property_backend_name"),
            lim.required_backend_name,
        )
        require_equal(
            f"{prefix}.coolprop_version",
            row.get("coolprop_version"),
            lim.required_coolprop_version,
        )
        require_equal(
            f"{prefix}.property_backend_design_status",
            row.get("property_backend_design_status"),
            lim.required_design_status,
        )
        require_equal(
            f"{prefix}.mach_cap_activation_count",
            _number(row.get("mach_cap_activation_count")),
            0.0,
        )
        require_abs_le(
            f"{prefix}.mass_relative_residual",
            row.get("budget_mass_relative_residual"),
            lim.max_abs_budget_relative_residual,
        )
        require_abs_le(
            f"{prefix}.energy_relative_residual",
            row.get("energy_budget_balance_relative_residual"),
            lim.max_abs_budget_relative_residual,
        )
        require_abs_le(
            f"{prefix}.vapor_mass_relative_residual",
            row.get("phase_vapor_mass_balance_relative_residual"),
            lim.max_abs_budget_relative_residual,
        )
        require_abs_le(
            f"{prefix}.opening_error",
            row.get("max_abs_opening_error"),
            lim.max_abs_opening_error,
        )
        require_abs_le(
            f"{prefix}.mass_flux_mismatch",
            row.get("max_abs_mass_flux_mismatch_kg_m2_s"),
            lim.max_abs_mass_flux_mismatch_kg_m2_s,
        )
        require_abs_le(
            f"{prefix}.energy_flux_mismatch",
            row.get("max_abs_energy_flux_mismatch_w_m2"),
            lim.max_abs_energy_flux_mismatch_w_m2,
        )
        require_abs_le(
            f"{prefix}.vapor_flux_mismatch",
            row.get("max_abs_vapor_mass_flux_mismatch_kg_m2_s"),
            lim.max_abs_vapor_mass_flux_mismatch_kg_m2_s,
        )
        require_abs_le(
            f"{prefix}.flux_q_minus_applied_q",
            row.get("max_abs_flux_q_minus_applied_q_m3_s"),
            lim.max_abs_flux_q_minus_applied_q_m3_s,
        )

        for field in (
            "max_raw_applied_relative_difference_extracted",
            "max_applied_flux_relative_difference_extracted",
        ):
            if field in row and row.get(field) not in (None, ""):
                require_le(
                    f"{prefix}.{field}",
                    row.get(field),
                    lim.max_flow_relative_difference,
                )

        if item != "V-012A":
            require_true(
                f"{prefix}.near_probe_characteristic_direction_pass",
                row,
                "near_probe_characteristic_direction_pass",
            )
            require_le(
                f"{prefix}.characteristic_leakage_ratio",
                row.get("near_probe_characteristic_max_leakage_ratio"),
                lim.max_characteristic_leakage_ratio,
            )
            require_equal(
                f"{prefix}.flow_sign_consistency_fraction",
                _number(row.get("flow_sign_consistency_fraction")),
                1.0,
            )

    a = by_item.get("V-012A", {})
    require_abs_le(
        "v012a.max_raw_q",
        a.get("max_abs_raw_target_q_m3_s_extracted"),
        lim.v012a_max_abs_q_m3_s,
    )
    require_abs_le(
        "v012a.max_applied_q",
        a.get("max_abs_applied_q_m3_s_extracted"),
        lim.v012a_max_abs_q_m3_s,
    )
    require_abs_le(
        "v012a.max_flux_derived_q",
        a.get("max_abs_flux_derived_q_m3_s_extracted"),
        lim.v012a_max_abs_q_m3_s,
    )
    require_abs_le(
        "v012a.pressure_disturbance",
        a.get("max_abs_pressure_disturbance_pa"),
        lim.v012a_max_pressure_disturbance_pa,
    )
    require_abs_le(
        "v012a.velocity",
        a.get("max_abs_velocity_m_s"),
        lim.v012a_max_velocity_m_s,
    )
    require_equal(
        "v012a.hydraulic_separation_fraction",
        _number(a.get("hydraulic_separation_fraction_extracted")),
        1.0,
    )
    require_equal(
        "v012a.no_flow_direction_fraction",
        _number(a.get("no_flow_direction_fraction_extracted")),
        1.0,
    )

    b = by_item.get("V-012B", {})
    require_range(
        "v012b.initial_applied_q",
        b.get("initial_applied_q_m3_s_extracted"),
        lim.v012b_min_initial_q_m3_s,
        lim.v012b_max_initial_q_m3_s,
    )
    require_range(
        "v012b.final_applied_q",
        b.get("final_applied_q_m3_s_extracted"),
        lim.v012b_min_final_q_m3_s,
        lim.v012b_max_final_q_m3_s,
    )
    require_le(
        "v012b.p50_timing_offset",
        b.get("near_probe_characteristic_p50_time_offset_max_abs_s"),
        lim.v012b_max_p50_offset_s,
    )
    require_range(
        "v012b.characteristic_peak",
        b.get("near_probe_characteristic_peak_abs_mean_pa"),
        lim.v012b_min_characteristic_peak_pa,
        lim.v012b_max_characteristic_peak_pa,
    )
    require_equal(
        "v012b.hydraulic_separation_fraction",
        _number(b.get("hydraulic_separation_fraction_extracted")),
        0.0,
    )

    c = by_item.get("V-012C", {})
    require_abs_le(
        "v012c.initial_applied_q",
        c.get("initial_applied_q_m3_s_extracted"),
        lim.v012c_max_abs_initial_q_m3_s,
    )
    require_range(
        "v012c.max_applied_q",
        c.get("max_applied_q_m3_s_extracted"),
        lim.v012c_min_max_q_m3_s,
        lim.v012c_max_max_q_m3_s,
    )
    require_range(
        "v012c.final_applied_q",
        c.get("final_applied_q_m3_s_extracted"),
        lim.v012c_min_final_q_m3_s,
        lim.v012c_max_final_q_m3_s,
    )
    require_le(
        "v012c.p50_timing_offset",
        c.get("near_probe_characteristic_p50_time_offset_max_abs_s"),
        lim.v012c_max_p50_offset_s,
    )
    require_range(
        "v012c.characteristic_peak",
        c.get("near_probe_characteristic_peak_abs_mean_pa"),
        lim.v012c_min_characteristic_peak_pa,
        lim.v012c_max_characteristic_peak_pa,
    )
    for key in (
        "opening_monotonic_non_decreasing",
        "upstream_decompression_observed",
        "downstream_compression_observed",
    ):
        require_true(f"v012c.{key}", c, key)

    d = by_item.get("V-012D", {})
    require_range(
        "v012d.initial_applied_q",
        d.get("initial_applied_q_m3_s_extracted"),
        lim.v012d_min_initial_q_m3_s,
        lim.v012d_max_initial_q_m3_s,
    )
    require_abs_le(
        "v012d.final_applied_q",
        d.get("final_applied_q_m3_s_extracted"),
        lim.v012d_max_abs_final_q_m3_s,
    )
    require_le(
        "v012d.p50_timing_offset",
        d.get("near_probe_characteristic_p50_time_offset_max_abs_s"),
        lim.v012d_max_p50_offset_s,
    )
    require_range(
        "v012d.characteristic_peak",
        d.get("near_probe_characteristic_peak_abs_mean_pa"),
        lim.v012d_min_characteristic_peak_pa,
        lim.v012d_max_characteristic_peak_pa,
    )
    for key in (
        "opening_monotonic_non_increasing",
        "upstream_compression_observed",
        "downstream_decompression_observed",
    ):
        require_true(f"v012d.{key}", d, key)
    require_equal(
        "v012d.post_closure_hydraulic_separation_fraction",
        _number(d.get("post_closure_hydraulic_separation_fraction_extracted")),
        1.0,
    )
    require_equal(
        "v012d.post_closure_no_flow_direction_fraction",
        _number(d.get("post_closure_no_flow_direction_fraction_extracted")),
        1.0,
    )
    require_abs_le(
        "v012d.post_closure_raw_q",
        d.get("max_abs_post_closure_raw_target_q_m3_s_extracted"),
        lim.v012d_max_abs_post_closure_q_m3_s,
    )
    require_abs_le(
        "v012d.post_closure_applied_q",
        d.get("max_abs_post_closure_applied_q_m3_s_extracted"),
        lim.v012d_max_abs_post_closure_q_m3_s,
    )
    require_abs_le(
        "v012d.post_closure_flux_derived_q",
        d.get("max_abs_post_closure_flux_derived_q_m3_s_extracted"),
        lim.v012d_max_abs_post_closure_q_m3_s,
    )
    require_abs_le(
        "v012d.post_closure_mass_flux",
        d.get("max_abs_post_closure_mass_flux_kg_m2_s_extracted"),
        lim.v012d_max_abs_post_closure_mass_flux_kg_m2_s,
    )
    require_abs_le(
        "v012d.post_closure_energy_flux",
        d.get("max_abs_post_closure_energy_flux_w_m2_extracted"),
        lim.v012d_max_abs_post_closure_energy_flux_w_m2,
    )
    require_abs_le(
        "v012d.post_closure_vapor_flux",
        d.get("max_abs_post_closure_vapor_mass_flux_kg_m2_s_extracted"),
        lim.v012d_max_abs_post_closure_vapor_flux_kg_m2_s,
    )
    require_abs_le(
        "v012d.finite_opening_momentum_residual",
        d.get("max_abs_finite_opening_momentum_residual_pa_extracted"),
        lim.v012d_max_abs_finite_opening_momentum_residual_pa,
    )
    add(
        "v012d.finite_opening_relation_not_applied_to_closed_rows",
        d.get("finite_opening_momentum_relation_applied_to_closed_rows_extracted")
        is False,
        d.get("finite_opening_momentum_relation_applied_to_closed_rows_extracted"),
        False,
        missing=(
            "finite_opening_momentum_relation_applied_to_closed_rows_extracted"
            not in d
        ),
    )

    return {
        "profile_name": lim.profile_name,
        "regression_evaluation": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_design_status": lim.required_design_status,
        "limits": asdict(lim),
        "checks": checks,
        "failed_checks": failed,
        "overall_regression_pass": not failed,
        "regression_band_note": (
            "Broad CI-light software/numerical regression band; not physical "
            "accuracy or design-use acceptance criteria."
        ),
    }


def run_internal_valve_regression(
    output_path: str | Path | None = None,
    *,
    artifact_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the four-case n=50, CFL=0.5 internal-valve CI-light profile."""

    root = (
        Path(artifact_dir)
        if artifact_dir is not None
        else Path(tempfile.mkdtemp(prefix="internal_valve_ci_light_"))
    )
    root.mkdir(parents=True, exist_ok=True)
    config = CoolPropInternalValveMeshCflSweepConfig()
    selected = tuple(case_id_for(item, 50, 0.5) for item in EXPECTED_ITEMS)
    sweep = run_coolprop_internal_valve_mesh_cfl_sweep(
        root,
        config,
        selected_case_ids=selected,
    )
    evaluation = evaluate_internal_valve_regression(sweep["summary_rows"])
    result = {
        "profile_name": InternalValveRegressionLimits().profile_name,
        "regression_evaluation": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_design_status": "not_approved_for_design_use",
        "ci_profile": {
            "n_cells": 50,
            "cfl": 0.5,
            "verification_items": list(EXPECTED_ITEMS),
        },
        "case_result": evaluation,
        "overall_regression_pass": evaluation["overall_regression_pass"],
        "artifact_directory": str(root),
        "sweep_execution_pass": sweep["overall_selected_execution_pass"],
        "executed_run_count": sweep["executed_run_count"],
    }
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result
