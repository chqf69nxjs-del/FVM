"""Lightweight CoolProp single-phase Gaussian-wave regression evaluation.

The limits in this module are intentionally broad software/numerical regression
bands for the CI-light path. They are not design-accuracy thresholds, physical
Validation criteria, CoolProp backend approval criteria, or design mesh
acceptance criteria.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
from typing import Any


@dataclass(frozen=True)
class WaveRegressionLimits:
    """Broad CI-light bands for detecting severe software regressions only.

    These values are not accuracy acceptance criteria and must not be used to
    approve design use, physical Validation, CoolProp backend acceptance, or a
    design mesh. Threshold-crossing speed is diagnostic only because waveform
    diffusion can bias the crossing time.
    """

    profile_name: str = "coolprop_wave_ci_light_v1"
    max_abs_mass_relative_residual: float = 1.0e-12
    max_abs_energy_relative_residual: float = 1.0e-12
    max_abs_vapor_mass_relative_residual: float = 1.0e-12
    max_peak_speed_relative_error: float = 5.0e-4
    max_centroid_speed_relative_error: float = 5.0e-2
    max_cross_correlation_speed_relative_error: float = 8.0e-2
    min_cross_correlation_coefficient: float = 0.50
    min_amplitude_ratio_L2: float = 0.35
    max_amplitude_ratio_L2: float = 1.05
    min_fwhm_broadening_ratio_L2: float = 1.0
    max_fwhm_broadening_ratio_L2: float = 3.0
    max_alpha: float = 1.0e-12
    max_vapor_mass_fraction: float = 1.0e-12


def _single_run_metrics(sweep_metrics: dict[str, Any]) -> dict[str, Any]:
    runs = sweep_metrics.get("runs")
    if isinstance(runs, list) and runs:
        return runs[0]
    return sweep_metrics


def _observed_metrics(sweep_metrics: dict[str, Any]) -> dict[str, Any]:
    run = _single_run_metrics(sweep_metrics)
    rows = sweep_metrics.get("summary_rows")
    row = rows[0] if isinstance(rows, list) and rows else {}
    keys = [
        "runtime_seconds", "step_count", "missing_budget_fields",
        "budget_mass_relative_residual", "energy_budget_balance_relative_residual",
        "phase_vapor_mass_balance_relative_residual", "interprobe_threshold_speed_relative_error",
        "interprobe_peak_speed_relative_error", "interprobe_centroid_speed_relative_error",
        "interprobe_cross_correlation_speed_relative_error", "cross_correlation_coefficient",
        "primary_probe_amplitude_ratio_L2", "primary_probe_fwhm_broadening_ratio_L2",
        "waveform_l1_difference_vs_finest", "waveform_l2_difference_vs_finest",
        "max_alpha", "max_vapor_mass_fraction",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        if key in run:
            out[key] = run[key]
        if key in row:
            out[key] = row[key]
    return out


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and value == value and value not in (float("inf"), float("-inf"))


def evaluate_coolprop_wave_regression(sweep_metrics: dict[str, Any], limits: WaveRegressionLimits | None = None) -> dict[str, Any]:
    """Evaluate precomputed wave sweep metrics without running the solver.

    Missing inputs are not inferred: the associated check is marked failed and
    recorded in ``failed_checks`` instead of raising ``KeyError``.
    """

    lim = limits or WaveRegressionLimits()
    run = _single_run_metrics(sweep_metrics)
    observed = _observed_metrics(sweep_metrics)
    checks: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    failed: list[str] = []

    def add(name: str, ok: bool, value: Any = None, expected: Any = None, missing: bool = False) -> None:
        checks[name] = {"pass": bool(ok), "value": value, "expected": expected, "missing": bool(missing)}
        if not ok:
            failed.append(name)

    def require_bool(name: str, source: dict[str, Any], key: str | None = None) -> None:
        k = key or name
        if k not in source:
            add(name, False, missing=True)
        else:
            add(name, bool(source[k]) is True, source[k], True)

    def require_eq(name: str, source: dict[str, Any], key: str, expected: Any) -> None:
        if key not in source:
            add(name, False, missing=True)
        else:
            add(name, source[key] == expected, source[key], expected)

    def require_abs_le(name: str, source: dict[str, Any], key: str, limit: float) -> None:
        if key not in source:
            add(name, False, missing=True)
            return
        v = source[key]
        add(name, _finite_number(v) and abs(float(v)) <= limit, v, f"abs <= {limit}")

    def require_between(name: str, source: dict[str, Any], key: str, lo: float, hi: float) -> None:
        if key not in source:
            add(name, False, missing=True)
            return
        v = source[key]
        add(name, _finite_number(v) and lo <= float(v) <= hi, v, f"{lo} <= value <= {hi}")

    require_bool("overall_sweep_execution_pass", sweep_metrics)
    require_bool("overall_observation_run_pass", run)
    require_bool("completed_without_exception", run)
    require_bool("reached_target_time", run)
    require_bool("within_max_steps", run)
    require_eq("property_backend_design_status_not_approved_for_design_use", run if "property_backend_design_status" in run else sweep_metrics, "property_backend_design_status", "not_approved_for_design_use")

    for key in ["all_history_finite", "positive_pressure", "positive_temperature", "positive_density", "positive_sound_speed", "remained_single_phase"]:
        require_bool(key, run)
    require_abs_le("max_alpha", run, "max_alpha", lim.max_alpha)
    require_abs_le("max_vapor_mass_fraction", run, "max_vapor_mass_fraction", lim.max_vapor_mass_fraction)

    if "missing_budget_fields" not in run:
        add("missing_budget_fields_empty", False, missing=True)
    else:
        add("missing_budget_fields_empty", run["missing_budget_fields"] == [], run["missing_budget_fields"], [])
    require_abs_le("mass_relative_residual", run, "budget_mass_relative_residual", lim.max_abs_mass_relative_residual)
    require_abs_le("energy_balance_relative_residual", run, "energy_budget_balance_relative_residual", lim.max_abs_energy_relative_residual)
    require_abs_le("vapor_mass_balance_relative_residual", run, "phase_vapor_mass_balance_relative_residual", lim.max_abs_vapor_mass_relative_residual)

    src = observed
    require_abs_le("interprobe_peak_speed_relative_error", src, "interprobe_peak_speed_relative_error", lim.max_peak_speed_relative_error)
    require_abs_le("interprobe_centroid_speed_relative_error", src, "interprobe_centroid_speed_relative_error", lim.max_centroid_speed_relative_error)
    require_abs_le("interprobe_cross_correlation_speed_relative_error", src, "interprobe_cross_correlation_speed_relative_error", lim.max_cross_correlation_speed_relative_error)
    require_between("cross_correlation_coefficient", src, "cross_correlation_coefficient", lim.min_cross_correlation_coefficient, 1.0)
    require_between("L2_amplitude_ratio_broad_regression_band", src, "primary_probe_amplitude_ratio_L2", lim.min_amplitude_ratio_L2, lim.max_amplitude_ratio_L2)
    require_between("L2_fwhm_broadening_ratio_broad_regression_band", src, "primary_probe_fwhm_broadening_ratio_L2", lim.min_fwhm_broadening_ratio_L2, lim.max_fwhm_broadening_ratio_L2)

    diagnostic = {
        "threshold_speed_relative_error": src.get("interprobe_threshold_speed_relative_error"),
        "runtime_seconds": src.get("runtime_seconds", run.get("runtime_seconds")),
        "step_count": src.get("step_count", run.get("step_count")),
        "waveform_l1_difference_vs_finest": src.get("waveform_l1_difference_vs_finest"),
        "waveform_l2_difference_vs_finest": src.get("waveform_l2_difference_vs_finest"),
    }
    if diagnostic["threshold_speed_relative_error"] is not None:
        warnings.append("threshold_speed_relative_error is diagnostic only for CI light because waveform diffusion can bias threshold crossing.")

    return {
        "profile_name": lim.profile_name,
        "regression_evaluation": True,
        "software_path_verification": True,
        "numerical_verification": True,
        "design_evaluation": False,
        "acceptance_gate": False,
        "validation": False,
        "property_backend_design_status": (run.get("property_backend_design_status") or sweep_metrics.get("property_backend_design_status")),
        "limits": asdict(lim),
        "observed_metrics": observed,
        "diagnostic_only": diagnostic,
        "checks": checks,
        "warnings": warnings,
        "failed_checks": failed,
        "overall_regression_pass": not failed,
        "regression_band_note": "Broad CI-light software/numerical regression band; not design accuracy acceptance criteria.",
    }


def run_coolprop_wave_regression(output_path: str | Path | None = None, limits: WaveRegressionLimits | None = None) -> dict[str, Any]:
    """Run the n=50/CFL=0.5 CI-light profile and optionally save JSON results."""

    from liquid_gas_transient.cases.coolprop_small_amplitude_wave_sweep import CoolPropSmallAmplitudeWaveSweepConfig, run_coolprop_small_amplitude_wave_sweep

    out_dir = Path(tempfile.mkdtemp(prefix="coolprop_wave_ci_light_"))
    cfg = CoolPropSmallAmplitudeWaveSweepConfig(mesh_cells=(50,), cfl_values=(0.5,), mesh_comparison_cfl=0.5, cfl_comparison_n_cells=50, generate_case_plots=False, generate_comparison_plots=False)
    sweep = run_coolprop_small_amplitude_wave_sweep(out_dir, cfg)
    result = evaluate_coolprop_wave_regression(sweep, limits)
    result["provenance"] = {"runner": "run_coolprop_wave_regression", "artifact_directory": str(out_dir), "does_not_replace_formal_verification_report": True}
    if output_path is not None:
        Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
