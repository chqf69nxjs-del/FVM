"""Stage 5 boundary-reflection CI-light software regression checks.

These checks are broad numerical/software regression sentinels only. They are
not physical Validation, design-use acceptance, or equipment-model approval.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from liquid_gas_transient.cases.coolprop_boundary_reflection import (
    CoolPropBoundaryReflectionConfig,
    run_coolprop_boundary_reflection,
)


@dataclass(frozen=True)
class BoundaryReflectionRegressionLimits:
    profile_name: str = "coolprop_boundary_reflection_ci_light_v1"
    max_abs_mass_relative_residual: float = 1.0e-12
    max_abs_energy_relative_residual: float = 1.0e-12
    max_abs_vapor_mass_relative_residual: float = 1.0e-12
    max_rigid_reflection_magnitude_error: float = 0.25
    max_fixed_reflection_magnitude_error: float = 0.30
    max_rigid_arrival_relative_error: float = 0.005
    max_fixed_arrival_relative_error: float = 0.03
    max_reflected_characteristic_leakage_ratio: float = 0.18
    max_normalized_wall_velocity_residual: float = 1.0e-12
    max_normalized_fixed_pressure_residual: float = 0.09


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and value == value and value not in (float("inf"), float("-inf"))


def _primary_probe(metrics: dict[str, Any]) -> dict[str, Any]:
    for probe in metrics.get("probes", []):
        if probe.get("probe_name") == "x_over_L_0.9":
            return probe
    return {}


def _ratio(numerator: Any, denominator: Any) -> float | None:
    if not (_finite(numerator) and _finite(denominator)) or float(denominator) == 0.0:
        return None
    return abs(float(numerator) / float(denominator))


def evaluate_boundary_reflection_regression(
    case_metrics: dict[str, Any],
    limits: BoundaryReflectionRegressionLimits | None = None,
) -> dict[str, Any]:
    lim = limits or BoundaryReflectionRegressionLimits()
    boundary = case_metrics.get("boundary_kind")
    probe = _primary_probe(case_metrics)
    boundary_metrics = case_metrics.get("boundary_metrics", {})
    checks: dict[str, dict[str, Any]] = {}
    failed: list[str] = []

    def add(name: str, ok: bool, value: Any = None, expected: Any = None, missing: bool = False) -> None:
        checks[name] = {"pass": bool(ok), "value": value, "expected": expected, "missing": bool(missing)}
        if not ok:
            failed.append(name)

    def require_true(name: str, source: dict[str, Any], key: str | None = None) -> None:
        k = key or name
        if k not in source:
            add(name, False, missing=True)
        else:
            add(name, source[k] is True, source[k], True)

    def require_abs_le(name: str, value: Any, limit: float) -> None:
        add(name, _finite(value) and abs(float(value)) <= limit, value, f"abs <= {limit}", not _finite(value))

    add("boundary_kind_supported", boundary in {"rigid_wall", "fixed_pressure"}, boundary, "rigid_wall or fixed_pressure")
    for key in (
        "overall_observation_execution_pass", "execution_complete", "reached_target_time",
        "within_max_steps", "all_history_finite", "positive_pressure", "positive_temperature",
        "positive_density", "positive_sound_speed", "remained_single_phase", "reflection_detected",
        "expected_sign_observed",
    ):
        require_true(key, case_metrics)
    add("evaluation_window_not_contaminated", case_metrics.get("evaluation_window_contaminated") is False, case_metrics.get("evaluation_window_contaminated"), False, "evaluation_window_contaminated" not in case_metrics)
    add("missing_budget_fields_empty", case_metrics.get("missing_budget_fields") == [], case_metrics.get("missing_budget_fields"), [])
    add(
        "property_backend_design_status_not_approved_for_design_use",
        case_metrics.get("property_backend_design_status") == "not_approved_for_design_use",
        case_metrics.get("property_backend_design_status"),
        "not_approved_for_design_use",
    )

    require_abs_le("mass_relative_residual", case_metrics.get("budget_mass_relative_residual"), lim.max_abs_mass_relative_residual)
    require_abs_le("energy_balance_relative_residual", case_metrics.get("energy_budget_balance_relative_residual"), lim.max_abs_energy_relative_residual)
    require_abs_le("vapor_mass_balance_relative_residual", case_metrics.get("phase_vapor_mass_balance_relative_residual"), lim.max_abs_vapor_mass_relative_residual)

    coefficient = probe.get("pressure_reflection_coefficient")
    magnitude_error = abs(abs(float(coefficient)) - 1.0) if _finite(coefficient) else None
    arrival_error = probe.get("reflected_arrival_time_relative_error")
    leakage = _ratio(probe.get("reflected_A_plus_leakage_peak_pa"), probe.get("reflected_A_minus_signed_extremum_pa"))

    if boundary == "rigid_wall":
        require_abs_le("reflection_magnitude_error", magnitude_error, lim.max_rigid_reflection_magnitude_error)
        require_abs_le("arrival_relative_error", arrival_error, lim.max_rigid_arrival_relative_error)
        require_abs_le("reflected_characteristic_leakage_ratio", leakage, lim.max_reflected_characteristic_leakage_ratio)
        wall_velocity = boundary_metrics.get("max_abs_wall_velocity_m_s")
        scale = None
        if _finite(case_metrics.get("pressure_amplitude_pa")) and _finite(case_metrics.get("Z0")) and float(case_metrics["Z0"]) > 0.0:
            scale = float(case_metrics["pressure_amplitude_pa"]) / float(case_metrics["Z0"])
        normalized_wall = float(wall_velocity) / scale if _finite(wall_velocity) and scale and scale > 0.0 else None
        require_abs_le("normalized_wall_velocity_residual", normalized_wall, lim.max_normalized_wall_velocity_residual)
    elif boundary == "fixed_pressure":
        require_abs_le("reflection_magnitude_error", magnitude_error, lim.max_fixed_reflection_magnitude_error)
        require_abs_le("arrival_relative_error", arrival_error, lim.max_fixed_arrival_relative_error)
        require_abs_le("reflected_characteristic_leakage_ratio", leakage, lim.max_reflected_characteristic_leakage_ratio)
        require_abs_le("normalized_fixed_pressure_residual", boundary_metrics.get("normalized_fixed_pressure_residual"), lim.max_normalized_fixed_pressure_residual)

    return {
        "profile_name": lim.profile_name,
        "boundary_kind": boundary,
        "regression_evaluation": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "design_evaluation": False,
        "acceptance_gate": False,
        "validation": False,
        "property_backend_design_status": case_metrics.get("property_backend_design_status"),
        "limits": asdict(lim),
        "checks": checks,
        "failed_checks": failed,
        "overall_regression_pass": not failed,
        "diagnostic_only": {
            "runtime_s": case_metrics.get("runtime_s"),
            "step_count": case_metrics.get("step_count"),
        },
        "regression_band_note": "Broad CI-light software/numerical regression band; not design accuracy acceptance criteria.",
    }


def run_boundary_reflection_regression(output_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(tempfile.mkdtemp(prefix="boundary_reflection_ci_light_"))
    results: dict[str, Any] = {}
    for boundary in ("rigid_wall", "fixed_pressure"):
        cfg = CoolPropBoundaryReflectionConfig(
            boundary_kind=boundary,
            case_name=f"coolprop_{boundary}_boundary_reflection_ci_light",
            n_cells=50,
            cfl=0.5,
        )
        metrics = run_coolprop_boundary_reflection(root / boundary, cfg)
        results[boundary] = evaluate_boundary_reflection_regression(metrics)
    failed = [name for name, result in results.items() if not result["overall_regression_pass"]]
    out = {
        "profile_name": BoundaryReflectionRegressionLimits().profile_name,
        "regression_evaluation": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "design_evaluation": False,
        "acceptance_gate": False,
        "validation": False,
        "property_backend_design_status": "not_approved_for_design_use",
        "case_results": results,
        "failed_cases": failed,
        "overall_regression_pass": not failed,
        "artifact_directory": str(root),
    }
    if output_path is not None:
        Path(output_path).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
