"""Stage 6 V-011 controlled-pressure-ramp CI-light regression checks.

These checks are broad software/numerical regression sentinels only. They are
not physical Validation, design-use acceptance, equipment-model approval, or a
claim that the CI-light mesh is a design mesh.
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import tempfile
from typing import Any

from liquid_gas_transient.analyze_controlled_pressure_ramp_front_fit import (
    fit_p50_propagation,
)
from liquid_gas_transient.analyze_controlled_pressure_ramp_results import (
    build_probe_observation_metrics,
)
from liquid_gas_transient.cases.coolprop_controlled_pressure_ramp import (
    CoolPropControlledPressureRampConfig,
    run_coolprop_controlled_pressure_ramp,
)


@dataclass(frozen=True)
class ControlledPressureRampRegressionLimits:
    """Broad CI-light limits derived from PR #31 observations.

    The limits intentionally leave margin around the observed n=50, CFL=0.5
    result. They protect the software path from major regression and are not
    formal physical-accuracy or design-acceptance criteria.
    """

    profile_name: str = "coolprop_controlled_pressure_ramp_ci_light_v1"
    max_abs_mass_relative_residual: float = 1.0e-12
    max_abs_energy_relative_residual: float = 1.0e-12
    max_abs_vapor_mass_relative_residual: float = 1.0e-12
    max_wave_speed_relative_error: float = 5.0e-3
    max_abs_common_launch_delay_s: float = 8.0e-3
    max_mean_p10_arrival_relative_error: float = 0.15
    max_mean_p50_arrival_relative_error: float = 0.08
    max_mean_p90_arrival_relative_error: float = 0.35
    max_max_p50_arrival_relative_error: float = 0.12
    max_primary_peak_amplitude_error: float = 5.0e-3
    max_primary_opposite_direction_leakage_ratio: float = 1.0e-3
    max_primary_linear_velocity_relative_error: float = 1.0e-2
    max_fit_residual_rms_s: float = 1.0e-4
    min_fit_r_squared: float = 0.999


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _primary_probe(
    observations: list[dict[str, Any]],
    name: str = "x_over_L_0.75",
) -> dict[str, Any]:
    for item in observations:
        if item.get("probe_name") == name:
            return item
    return {}


def _arrival_values(
    observations: list[dict[str, Any]],
    label: str,
) -> list[float]:
    key = f"{label}_arrival_relative_error"
    values = [item.get(key) for item in observations]
    return [float(value) for value in values if _finite(value)]


def evaluate_controlled_pressure_ramp_regression(
    case_metrics: dict[str, Any],
    probe_observations: list[dict[str, Any]],
    p50_fit: dict[str, Any],
    limits: ControlledPressureRampRegressionLimits | None = None,
) -> dict[str, Any]:
    """Evaluate one CI-light pressure-ramp result without running the solver."""

    lim = limits or ControlledPressureRampRegressionLimits()
    checks: dict[str, dict[str, Any]] = {}
    failed: list[str] = []

    def add(
        name: str,
        ok: bool,
        value: Any = None,
        expected: Any = None,
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

    def require_true(name: str, source: dict[str, Any], key: str | None = None) -> None:
        source_key = key or name
        if source_key not in source:
            add(name, False, missing=True)
        else:
            add(name, source[source_key] is True, source[source_key], True)

    def require_abs_le(name: str, value: Any, limit: float) -> None:
        add(
            name,
            _finite(value) and abs(float(value)) <= limit,
            value,
            f"abs <= {limit}",
            not _finite(value),
        )

    def require_le(name: str, value: Any, limit: float) -> None:
        add(
            name,
            _finite(value) and float(value) <= limit,
            value,
            f"<= {limit}",
            not _finite(value),
        )

    def require_ge(name: str, value: Any, limit: float) -> None:
        add(
            name,
            _finite(value) and float(value) >= limit,
            value,
            f">= {limit}",
            not _finite(value),
        )

    for key in (
        "overall_observation_execution_pass",
        "reached_target_time",
        "within_max_steps",
        "all_history_finite",
        "positive_pressure",
        "positive_temperature",
        "positive_density",
        "positive_sound_speed",
        "remained_single_phase",
    ):
        require_true(key, case_metrics)

    add(
        "missing_budget_fields_empty",
        case_metrics.get("missing_budget_fields") == [],
        case_metrics.get("missing_budget_fields"),
        [],
        "missing_budget_fields" not in case_metrics,
    )
    add(
        "property_backend_design_status_not_approved_for_design_use",
        case_metrics.get("property_backend_design_status")
        == "not_approved_for_design_use",
        case_metrics.get("property_backend_design_status"),
        "not_approved_for_design_use",
    )
    schedule_error = case_metrics.get("max_abs_schedule_pressure_error_pa")
    schedule_tolerance = case_metrics.get("schedule_pressure_tolerance_pa")
    add(
        "schedule_roundoff_within_ulp_tolerance",
        _finite(schedule_error)
        and _finite(schedule_tolerance)
        and abs(float(schedule_error)) <= float(schedule_tolerance),
        schedule_error,
        f"abs <= {schedule_tolerance}",
        not (_finite(schedule_error) and _finite(schedule_tolerance)),
    )

    require_abs_le(
        "mass_relative_residual",
        case_metrics.get("budget_mass_relative_residual"),
        lim.max_abs_mass_relative_residual,
    )
    require_abs_le(
        "energy_balance_relative_residual",
        case_metrics.get("energy_budget_balance_relative_residual"),
        lim.max_abs_energy_relative_residual,
    )
    require_abs_le(
        "vapor_mass_balance_relative_residual",
        case_metrics.get("phase_vapor_mass_balance_relative_residual"),
        lim.max_abs_vapor_mass_relative_residual,
    )

    add(
        "probe_observation_count",
        len(probe_observations) >= 3,
        len(probe_observations),
        ">= 3",
    )
    primary = _primary_probe(probe_observations)
    add(
        "primary_probe_present",
        bool(primary),
        primary.get("probe_name") if primary else None,
        "x_over_L_0.75",
        not bool(primary),
    )
    if primary:
        add(
            "left_going_characteristic_dominant",
            primary.get("observed_propagation_direction") == "left_going",
            primary.get("observed_propagation_direction"),
            "left_going",
        )
        amplitude_ratio = primary.get("peak_amplitude_ratio")
        amplitude_error = (
            abs(abs(float(amplitude_ratio)) - 1.0)
            if _finite(amplitude_ratio)
            else None
        )
        require_le(
            "primary_peak_amplitude_error",
            amplitude_error,
            lim.max_primary_peak_amplitude_error,
        )
        require_le(
            "primary_opposite_direction_leakage_ratio",
            primary.get("opposite_direction_leakage_ratio"),
            lim.max_primary_opposite_direction_leakage_ratio,
        )
        require_le(
            "primary_linear_velocity_relative_error",
            primary.get("linear_velocity_relative_error"),
            lim.max_primary_linear_velocity_relative_error,
        )

    for label, mean_limit in (
        ("p10", lim.max_mean_p10_arrival_relative_error),
        ("p50", lim.max_mean_p50_arrival_relative_error),
        ("p90", lim.max_mean_p90_arrival_relative_error),
    ):
        values = _arrival_values(probe_observations, label)
        mean_value = sum(values) / len(values) if values else None
        require_le(f"mean_{label}_arrival_relative_error", mean_value, mean_limit)
        if label == "p50":
            max_value = max(values) if values else None
            require_le(
                "max_p50_arrival_relative_error",
                max_value,
                lim.max_max_p50_arrival_relative_error,
            )

    require_le(
        "wave_speed_relative_error",
        p50_fit.get("wave_speed_relative_error"),
        lim.max_wave_speed_relative_error,
    )
    require_abs_le(
        "common_boundary_launch_delay_s",
        p50_fit.get("common_boundary_launch_delay_s"),
        lim.max_abs_common_launch_delay_s,
    )
    require_le(
        "fit_residual_rms_s",
        p50_fit.get("fit_residual_rms_s"),
        lim.max_fit_residual_rms_s,
    )
    require_ge(
        "fit_r_squared",
        p50_fit.get("fit_r_squared"),
        lim.min_fit_r_squared,
    )

    return {
        "profile_name": lim.profile_name,
        "regression_evaluation": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_design_status": case_metrics.get(
            "property_backend_design_status"
        ),
        "limits": asdict(lim),
        "checks": checks,
        "failed_checks": failed,
        "overall_regression_pass": not failed,
        "diagnostic_only": {
            "runtime_s": case_metrics.get("runtime_s"),
            "step_count": case_metrics.get("step_count"),
            "n_cells": case_metrics.get("n_cells"),
            "cfl": case_metrics.get("cfl_target"),
        },
        "regression_band_note": (
            "Broad CI-light software/numerical regression band; not physical "
            "accuracy or design-use acceptance criteria."
        ),
    }


def run_controlled_pressure_ramp_regression(
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the n=50, CFL=0.5 CI-light pressure-ramp profile."""

    root = Path(tempfile.mkdtemp(prefix="controlled_pressure_ramp_ci_light_"))
    case_name = "coolprop_controlled_pressure_ramp_ci_light"
    config = CoolPropControlledPressureRampConfig(
        case_name=case_name,
        n_cells=50,
        cfl=0.5,
    )
    case_metrics = run_coolprop_controlled_pressure_ramp(root, config)
    probe_rows = _read_csv(root / f"{case_name}_probe_history.csv")
    observations = build_probe_observation_metrics(
        probe_rows,
        config=config,
        base_metrics=case_metrics,
    )
    p50_fit = fit_p50_propagation(
        observations,
        reference_sound_speed_m_s=float(case_metrics["c0"]),
        expected_boundary_p50_time_s=(
            config.ramp_start_s + 0.5 * config.ramp_duration_s
        ),
    )
    evaluation = evaluate_controlled_pressure_ramp_regression(
        case_metrics,
        observations,
        p50_fit,
    )
    result = {
        "profile_name": ControlledPressureRampRegressionLimits().profile_name,
        "regression_evaluation": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "validation": False,
        "design_evaluation": False,
        "acceptance_gate": False,
        "property_backend_design_status": "not_approved_for_design_use",
        "ci_profile": {"n_cells": 50, "cfl": 0.5},
        "case_result": evaluation,
        "overall_regression_pass": evaluation["overall_regression_pass"],
        "artifact_directory": str(root),
    }
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result
