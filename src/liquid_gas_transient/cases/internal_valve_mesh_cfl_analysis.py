"""Artifact analysis for the V-012 internal-valve mesh/CFL observation.

The functions in this module read artifacts emitted by the existing V-012A/B/C/D
runners. They do not rerun or modify the solver. Results remain software /
numerical verification only; they are not physical Validation or design-use
acceptance.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


_DYNAMIC_ITEMS = ("V-012B", "V-012C", "V-012D")
_EXPECTED_SIGNS = {
    "V-012B": {"left": -1.0, "right": 1.0},
    "V-012C": {"left": -1.0, "right": 1.0},
    "V-012D": {"left": 1.0, "right": -1.0},
}
_FRACTIONS = (0.1, 0.5, 0.9)


def _read_csv(path: Path, required: Sequence[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"empty CSV artifact: {path.name}")
    available = set(rows[0])
    missing = [name for name in required if name not in available]
    if missing:
        raise ValueError(
            f"missing columns in {path.name}: {', '.join(missing)}"
        )
    return rows


def _number(row: Mapping[str, Any], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric field: {key}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite numeric field: {key}")
    return value


def _bool_value(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no", ""}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _max_abs(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> float:
    return max(
        (abs(_number(row, key)) for row in rows for key in keys),
        default=0.0,
    )


def _relative_difference(left: float, right: float, floor: float) -> float | None:
    scale = max(abs(left), abs(right))
    if scale <= floor:
        return None
    return float(abs(left - right) / scale)


def _max_relative_difference(
    pairs: Sequence[tuple[float, float]],
    floor: float,
) -> float | None:
    values = [
        value
        for left, right in pairs
        if (value := _relative_difference(left, right, floor)) is not None
    ]
    return max(values, default=None)


def _group_probes(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["probe_name"]), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda row: _number(row, "time_s"))
    return grouped


def _near_probe_names(
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    valve_x_m: float,
) -> dict[str, str]:
    first_rows = {name: rows[0] for name, rows in grouped.items() if rows}
    left = [
        (name, _number(row, "probe_cell_center_x_m"))
        for name, row in first_rows.items()
        if str(row["probe_side"]) == "left"
    ]
    right = [
        (name, _number(row, "probe_cell_center_x_m"))
        for name, row in first_rows.items()
        if str(row["probe_side"]) == "right"
    ]
    if not left or not right:
        raise ValueError("dynamic probe history requires both valve sides")
    left_name, left_x = min(left, key=lambda item: abs(item[1] - valve_x_m))
    right_name, right_x = min(right, key=lambda item: abs(item[1] - valve_x_m))
    if not left_x < valve_x_m < right_x:
        raise ValueError("near probes do not bracket the valve")
    return {"left": left_name, "right": right_name}


def _event_times(
    verification_item: str,
    metrics: Mapping[str, Any],
) -> tuple[float, float]:
    if verification_item == "V-012B":
        return 0.0, 0.0
    if verification_item not in {"V-012C", "V-012D"}:
        raise ValueError(f"unsupported dynamic item: {verification_item}")
    start = float(metrics["ramp_start_s"])
    end = float(metrics["ramp_end_s"])
    if not np.isfinite(start) or not np.isfinite(end) or end <= start:
        raise ValueError("invalid ramp timing in source metrics")
    return start, end


def _crossing_time(
    times: Sequence[float],
    projected: Sequence[float],
    threshold: float,
) -> float | None:
    if len(times) != len(projected) or not times:
        return None
    for index, value in enumerate(projected):
        if value < threshold:
            continue
        if index == 0:
            return float(times[0])
        previous_value = float(projected[index - 1])
        previous_time = float(times[index - 1])
        current_time = float(times[index])
        denominator = float(value - previous_value)
        if denominator <= 0.0:
            return current_time
        weight = float((threshold - previous_value) / denominator)
        weight = float(np.clip(weight, 0.0, 1.0))
        return previous_time + weight * (current_time - previous_time)
    return None


def _probe_observation(
    *,
    verification_item: str,
    side: str,
    rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    if side not in {"left", "right"}:
        raise ValueError(f"unsupported probe side: {side}")
    if not rows:
        raise ValueError("empty probe history group")

    valve_x_m = float(metrics["valve_x_m"])
    probe_x_m = _number(rows[0], "probe_cell_center_x_m")
    distance_m = abs(probe_x_m - valve_x_m)
    c0_key = "left_c0_m_s" if side == "left" else "right_c0_m_s"
    c0_m_s = float(metrics[c0_key])
    if not np.isfinite(c0_m_s) or c0_m_s <= 0.0:
        raise ValueError(f"invalid source metric: {c0_key}")

    source_start_s, source_end_s = _event_times(verification_item, metrics)
    travel_time_s = distance_m / c0_m_s
    arrival_start_s = source_start_s + travel_time_s
    theoretical_peak_time_s = source_end_s + travel_time_s

    ordered = sorted(rows, key=lambda row: _number(row, "time_s"))
    pre_rows = [row for row in ordered if _number(row, "time_s") < arrival_start_s]
    baseline = pre_rows[-1] if pre_rows else ordered[0]
    observed = [
        row for row in ordered if _number(row, "time_s") >= arrival_start_s
    ]
    if not observed:
        raise ValueError("no probe samples at or after theoretical arrival")

    desired_key = "A_minus_pa" if side == "left" else "A_plus_pa"
    undesired_key = "A_plus_pa" if side == "left" else "A_minus_pa"
    expected_sign = _EXPECTED_SIGNS[verification_item][side]

    baseline_desired = _number(baseline, desired_key)
    baseline_undesired = _number(baseline, undesired_key)
    baseline_pressure = _number(baseline, "delta_pressure_pa")
    baseline_velocity = _number(baseline, "velocity_m_s")

    times = [_number(row, "time_s") for row in observed]
    desired = [
        _number(row, desired_key) - baseline_desired for row in observed
    ]
    undesired = [
        _number(row, undesired_key) - baseline_undesired for row in observed
    ]
    pressure = [
        _number(row, "delta_pressure_pa") - baseline_pressure
        for row in observed
    ]
    velocity = [
        _number(row, "velocity_m_s") - baseline_velocity
        for row in observed
    ]
    projected = [expected_sign * value for value in desired]
    peak_index = int(np.argmax(np.asarray(projected, dtype=float)))
    projected_peak = float(projected[peak_index])
    if projected_peak <= 0.0:
        raise ValueError("expected-sign characteristic increment was not observed")

    desired_peak = float(desired[peak_index])
    desired_peak_abs = abs(desired_peak)
    undesired_peak_abs = max(abs(value) for value in undesired)
    leakage_ratio = float(
        undesired_peak_abs / max(desired_peak_abs, np.finfo(float).tiny)
    )
    pressure_projected = [expected_sign * value for value in pressure]
    pressure_extreme_projected = max(pressure_projected)
    pressure_extreme = expected_sign * pressure_extreme_projected
    velocity_peak_index = int(
        np.argmax(np.abs(np.asarray(velocity, dtype=float)))
    )

    result: dict[str, Any] = {
        "probe_name": str(rows[0]["probe_name"]),
        "probe_side": side,
        "probe_cell_center_x_m": float(probe_x_m),
        "probe_distance_from_valve_m": float(distance_m),
        "reference_sound_speed_m_s": float(c0_m_s),
        "arrival_start_s": float(arrival_start_s),
        "theoretical_peak_time_s": float(theoretical_peak_time_s),
        "baseline_time_s": _number(baseline, "time_s"),
        "desired_characteristic": (
            "A_minus" if side == "left" else "A_plus"
        ),
        "expected_increment_sign": (
            "positive" if expected_sign > 0.0 else "negative"
        ),
        "desired_increment_peak_pa": desired_peak,
        "desired_increment_peak_abs_pa": desired_peak_abs,
        "desired_increment_peak_time_s": float(times[peak_index]),
        "desired_increment_peak_time_offset_s": float(
            times[peak_index] - theoretical_peak_time_s
        ),
        "undesired_increment_peak_abs_pa": float(undesired_peak_abs),
        "opposite_direction_increment_ratio": leakage_ratio,
        "pressure_increment_extreme_pa": float(pressure_extreme),
        "velocity_increment_extreme_m_s": float(velocity[velocity_peak_index]),
        "desired_sign_match": bool(expected_sign * desired_peak > 0.0),
        "pressure_sign_match": bool(pressure_extreme_projected > 0.0),
        "direction_dominant": bool(desired_peak_abs >= undesired_peak_abs),
    }
    result["direction_observation_pass"] = bool(
        result["desired_sign_match"]
        and result["pressure_sign_match"]
        and result["direction_dominant"]
    )

    duration_s = source_end_s - source_start_s
    for fraction in _FRACTIONS:
        threshold = fraction * projected_peak
        observed_time = _crossing_time(times, projected, threshold)
        source_time = (
            source_start_s + fraction * duration_s
            if duration_s > 0.0
            else source_start_s
        )
        theoretical_time = source_time + travel_time_s
        token = f"p{int(round(100.0 * fraction)):02d}"
        result[f"{token}_time_s"] = observed_time
        result[f"{token}_theoretical_time_s"] = float(theoretical_time)
        result[f"{token}_time_offset_s"] = (
            float(observed_time - theoretical_time)
            if observed_time is not None
            else None
        )
    result["analysis_complete"] = bool(
        result["direction_observation_pass"]
        and all(
            result[f"p{int(100 * fraction):02d}_time_s"] is not None
            for fraction in _FRACTIONS
        )
    )
    return result


def _flatten_probe(prefix: str, values: Mapping[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def _generic_flow_fields(
    valve_rows: Sequence[Mapping[str, Any]],
    flux_rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    if len(valve_rows) != len(flux_rows):
        raise ValueError("valve and interface-flux histories have different lengths")
    q_floor = float(metrics.get("q_roundoff_tolerance_m3_s", 0.0))
    q_floor = max(q_floor, np.finfo(float).tiny)

    applied = [_number(row, "applied_q_m3_s") for row in valve_rows]
    raw = [_number(row, "raw_target_q_m3_s") for row in valve_rows]
    flux_q = [_number(row, "flux_derived_q_m3_s") for row in flux_rows]
    opening = [_number(row, "opening_actual") for row in valve_rows]
    delta_p = [_number(row, "delta_p_pa") for row in valve_rows]
    finite_threshold = float(metrics.get("closed_opening_threshold", 1.0e-12))
    finite_applied = [
        q for q, alpha in zip(applied, opening) if alpha > finite_threshold
    ]

    raw_applied = _max_relative_difference(
        list(zip(raw, applied)),
        q_floor,
    )
    applied_flux = _max_relative_difference(
        list(zip(applied, flux_q)),
        q_floor,
    )
    hydraulic_fraction = sum(
        _bool_value(row["hydraulic_separation_active"])
        for row in valve_rows
    ) / len(valve_rows)
    no_flow_fraction = sum(
        str(row["flow_direction"]).strip().lower() == "none"
        for row in valve_rows
    ) / len(valve_rows)

    return {
        "initial_raw_target_q_m3_s_extracted": float(raw[0]),
        "initial_applied_q_m3_s_extracted": float(applied[0]),
        "initial_flux_derived_q_m3_s_extracted": float(flux_q[0]),
        "max_applied_q_m3_s_extracted": float(max(applied)),
        "min_applied_q_m3_s_extracted": float(min(applied)),
        "final_applied_q_m3_s_extracted": float(applied[-1]),
        "min_finite_opening_applied_q_m3_s_extracted": (
            float(min(finite_applied)) if finite_applied else None
        ),
        "max_abs_raw_target_q_m3_s_extracted": float(
            max(abs(value) for value in raw)
        ),
        "max_abs_applied_q_m3_s_extracted": float(
            max(abs(value) for value in applied)
        ),
        "max_abs_flux_derived_q_m3_s_extracted": float(
            max(abs(value) for value in flux_q)
        ),
        "max_raw_applied_relative_difference_extracted": raw_applied,
        "max_applied_flux_relative_difference_extracted": applied_flux,
        "relative_flow_comparison_evaluated": bool(
            raw_applied is not None or applied_flux is not None
        ),
        "initial_delta_p_pa_extracted": float(delta_p[0]),
        "median_delta_p_pa_extracted": float(np.median(delta_p)),
        "final_delta_p_pa_extracted": float(delta_p[-1]),
        "max_abs_delta_p_pa_extracted": float(
            max(abs(value) for value in delta_p)
        ),
        "hydraulic_separation_fraction_extracted": float(
            hydraulic_fraction
        ),
        "no_flow_direction_fraction_extracted": float(no_flow_fraction),
        "mach_cap_activation_count_extracted": int(
            sum(_bool_value(row["mach_cap_active"]) for row in valve_rows)
        ),
        "max_applied_face_mach_extracted": float(
            max(abs(_number(row, "applied_face_mach")) for row in valve_rows)
        ),
        "max_abs_mass_flux_mismatch_kg_m2_s_extracted": _max_abs(
            flux_rows,
            ("mass_flux_mismatch_kg_m2_s",),
        ),
        "max_abs_energy_flux_mismatch_w_m2_extracted": _max_abs(
            flux_rows,
            ("energy_flux_mismatch_w_m2",),
        ),
        "max_abs_vapor_mass_flux_mismatch_kg_m2_s_extracted": _max_abs(
            flux_rows,
            ("vapor_mass_flux_mismatch_kg_m2_s",),
        ),
        "max_abs_flux_q_minus_applied_q_m3_s_extracted": _max_abs(
            flux_rows,
            ("flux_q_minus_applied_q_m3_s",),
        ),
    }


def _closure_fields(
    valve_rows: Sequence[Mapping[str, Any]],
    flux_rows: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    ramp_end_s = float(metrics["ramp_end_s"])
    post_pairs = [
        (valve, flux)
        for valve, flux in zip(valve_rows, flux_rows)
        if _number(valve, "time_s") >= ramp_end_s
    ]
    if not post_pairs:
        raise ValueError("V-012D has no post-closure artifact rows")
    post_valve = [pair[0] for pair in post_pairs]
    post_flux = [pair[1] for pair in post_pairs]
    finite_flux = [
        row
        for row in flux_rows
        if str(row.get("interface_branch", "")) == "finite_opening"
    ]
    closed_flux = [
        row
        for row in post_flux
        if str(row.get("interface_branch", "closed_wall")) == "closed_wall"
    ]
    if not closed_flux:
        raise ValueError("V-012D has no closed-wall interface rows")

    return {
        "post_closure_sample_count_extracted": len(post_valve),
        "post_closure_hydraulic_separation_fraction_extracted": float(
            sum(
                _bool_value(row["hydraulic_separation_active"])
                for row in post_valve
            )
            / len(post_valve)
        ),
        "post_closure_no_flow_direction_fraction_extracted": float(
            sum(
                str(row["flow_direction"]).strip().lower() == "none"
                for row in post_valve
            )
            / len(post_valve)
        ),
        "max_abs_post_closure_raw_target_q_m3_s_extracted": _max_abs(
            post_valve,
            ("raw_target_q_m3_s",),
        ),
        "max_abs_post_closure_applied_q_m3_s_extracted": _max_abs(
            post_valve,
            ("applied_q_m3_s",),
        ),
        "max_abs_post_closure_flux_derived_q_m3_s_extracted": _max_abs(
            post_flux,
            ("flux_derived_q_m3_s",),
        ),
        "max_abs_post_closure_mass_flux_kg_m2_s_extracted": _max_abs(
            closed_flux,
            ("left_mass_flux_kg_m2_s", "right_mass_flux_kg_m2_s"),
        ),
        "max_abs_post_closure_energy_flux_w_m2_extracted": _max_abs(
            closed_flux,
            ("left_energy_flux_w_m2", "right_energy_flux_w_m2"),
        ),
        "max_abs_post_closure_vapor_mass_flux_kg_m2_s_extracted": _max_abs(
            closed_flux,
            (
                "left_vapor_mass_flux_kg_m2_s",
                "right_vapor_mass_flux_kg_m2_s",
            ),
        ),
        "max_abs_finite_opening_momentum_residual_pa_extracted": _max_abs(
            finite_flux,
            ("momentum_difference_residual_pa",),
        ),
        "max_abs_closed_wall_momentum_residual_pa_diagnostic_extracted": _max_abs(
            closed_flux,
            ("momentum_difference_residual_pa",),
        ),
        "finite_opening_momentum_relation_applied_to_closed_rows_extracted": False,
    }


def extract_case_artifacts(
    run_dir: Path,
    item: Mapping[str, Any],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract traceable per-case summary fields from saved runner artifacts."""

    case_id = str(item["case_id"])
    verification_item = str(item["verification_item"])
    valve_path = run_dir / f"{case_id}_valve_history.csv"
    flux_path = run_dir / f"{case_id}_interface_flux_history.csv"
    valve_rows = _read_csv(
        valve_path,
        (
            "time_s",
            "opening_actual",
            "delta_p_pa",
            "raw_target_q_m3_s",
            "applied_q_m3_s",
            "applied_face_mach",
            "mach_cap_active",
            "hydraulic_separation_active",
            "flow_direction",
        ),
    )
    flux_rows = _read_csv(
        flux_path,
        (
            "time_s",
            "left_mass_flux_kg_m2_s",
            "right_mass_flux_kg_m2_s",
            "mass_flux_mismatch_kg_m2_s",
            "left_energy_flux_w_m2",
            "right_energy_flux_w_m2",
            "energy_flux_mismatch_w_m2",
            "left_vapor_mass_flux_kg_m2_s",
            "right_vapor_mass_flux_kg_m2_s",
            "vapor_mass_flux_mismatch_kg_m2_s",
            "momentum_difference_residual_pa",
            "flux_derived_q_m3_s",
            "flux_q_minus_applied_q_m3_s",
        ),
    )

    result: dict[str, Any] = {
        "source_valve_history_path": valve_path.name,
        "source_interface_flux_history_path": flux_path.name,
        **_generic_flow_fields(valve_rows, flux_rows, metrics),
    }

    if verification_item == "V-012A":
        result.update(
            {
                "analysis_complete": True,
                "dynamic_probe_analysis_complete": False,
                "preservation_sentinel": True,
            }
        )
        return result
    if verification_item not in _DYNAMIC_ITEMS:
        raise ValueError(f"unsupported verification item: {verification_item}")

    probe_path = run_dir / f"{case_id}_probe_history.csv"
    probe_rows = _read_csv(
        probe_path,
        (
            "time_s",
            "probe_name",
            "probe_side",
            "probe_cell_center_x_m",
            "delta_pressure_pa",
            "velocity_m_s",
            "A_plus_pa",
            "A_minus_pa",
        ),
    )
    grouped = _group_probes(probe_rows)
    near = _near_probe_names(grouped, float(metrics["valve_x_m"]))
    left = _probe_observation(
        verification_item=verification_item,
        side="left",
        rows=grouped[near["left"]],
        metrics=metrics,
    )
    right = _probe_observation(
        verification_item=verification_item,
        side="right",
        rows=grouped[near["right"]],
        metrics=metrics,
    )
    probe_results = [left, right]
    result.update(
        {
            "source_probe_history_path": probe_path.name,
            **_flatten_probe("near_left", left),
            **_flatten_probe("near_right", right),
            "near_probe_characteristic_direction_pass": bool(
                all(row["direction_observation_pass"] for row in probe_results)
            ),
            "near_probe_characteristic_max_leakage_ratio": float(
                max(
                    row["opposite_direction_increment_ratio"]
                    for row in probe_results
                )
            ),
            "near_probe_characteristic_peak_abs_mean_pa": float(
                np.mean(
                    [
                        row["desired_increment_peak_abs_pa"]
                        for row in probe_results
                    ]
                )
            ),
            "near_probe_characteristic_peak_time_offset_max_abs_s": float(
                max(
                    abs(row["desired_increment_peak_time_offset_s"])
                    for row in probe_results
                )
            ),
            "near_probe_characteristic_p50_time_offset_max_abs_s": float(
                max(
                    abs(float(row["p50_time_offset_s"]))
                    for row in probe_results
                )
            ),
            "near_probe_pressure_increment_max_abs_pa": float(
                max(
                    abs(row["pressure_increment_extreme_pa"])
                    for row in probe_results
                )
            ),
            "near_probe_velocity_increment_max_abs_m_s": float(
                max(
                    abs(row["velocity_increment_extreme_m_s"])
                    for row in probe_results
                )
            ),
            "dynamic_probe_analysis_complete": bool(
                all(row["analysis_complete"] for row in probe_results)
            ),
        }
    )
    if verification_item == "V-012D":
        result.update(_closure_fields(valve_rows, flux_rows, metrics))
    result["analysis_complete"] = bool(
        result["dynamic_probe_analysis_complete"]
        and result["near_probe_characteristic_direction_pass"]
    )
    return result


def _normalized_difference(left: float, right: float) -> float:
    scale = max(abs(left), abs(right), np.finfo(float).tiny)
    return float(abs(left - right) / scale)


def _mesh_metric_observation(
    rows: Sequence[Mapping[str, Any]],
    key: str,
    *,
    error_like: bool,
    floor: float,
) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["n_cells"]))
    if len(ordered) != 3:
        return {
            "metric": key,
            "classification": "insufficient_data",
            "values": [],
        }
    values = [float(row[key]) for row in ordered]
    if not all(np.isfinite(value) for value in values):
        return {
            "metric": key,
            "classification": "insufficient_data",
            "values": values,
        }
    differences = [
        _normalized_difference(values[0], values[1]),
        _normalized_difference(values[1], values[2]),
    ]
    if error_like:
        magnitudes = [abs(value) for value in values]
        if max(magnitudes) <= floor:
            classification = "near_numerical_floor"
        elif magnitudes[2] <= magnitudes[1] <= magnitudes[0]:
            classification = "monotonic_improvement"
        elif magnitudes[2] < magnitudes[0]:
            classification = "improved_but_non_monotonic"
        else:
            classification = "no_clear_improvement"
    else:
        if max(abs(value) for value in values) <= floor:
            classification = "near_numerical_floor"
        elif differences[1] <= differences[0]:
            classification = "contracting_differences"
        else:
            classification = "no_clear_contraction"
    return {
        "metric": key,
        "classification": classification,
        "n_cells": [int(row["n_cells"]) for row in ordered],
        "dx_m": [float(row["dx_m"]) for row in ordered],
        "values": values,
        "coarse_to_medium_normalized_difference": differences[0],
        "medium_to_fine_normalized_difference": differences[1],
        "error_like": error_like,
        "floor": float(floor),
    }


def _cfl_metric_observation(
    rows: Sequence[Mapping[str, Any]],
    key: str,
) -> dict[str, Any]:
    by_cfl = {float(row["cfl"]): row for row in rows}
    if 0.25 not in by_cfl or 0.5 not in by_cfl:
        return {
            "metric": key,
            "classification": "insufficient_data",
        }
    lower = float(by_cfl[0.25][key])
    baseline = float(by_cfl[0.5][key])
    return {
        "metric": key,
        "cfl_0p25": lower,
        "cfl_0p5": baseline,
        "absolute_difference": float(lower - baseline),
        "normalized_difference": _normalized_difference(lower, baseline),
        "classification": "observation_only_lower_cfl_not_truth",
    }


def build_aggregate_observation(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build mesh/CFL trend summaries from the complete 13-run row set."""

    dynamic = [
        row for row in rows if row["verification_item"] in _DYNAMIC_ITEMS
    ]
    case_metrics = {
        "V-012B": (
            ("max_applied_q_m3_s_extracted", False, 1.0e-16),
            (
                "near_probe_characteristic_p50_time_offset_max_abs_s",
                True,
                1.0e-12,
            ),
            ("near_probe_characteristic_max_leakage_ratio", True, 1.0e-12),
            (
                "max_abs_flux_q_minus_applied_q_m3_s_extracted",
                True,
                1.0e-18,
            ),
        ),
        "V-012C": (
            ("final_applied_q_m3_s_extracted", False, 1.0e-16),
            ("near_probe_characteristic_peak_abs_mean_pa", False, 1.0e-12),
            (
                "near_probe_characteristic_p50_time_offset_max_abs_s",
                True,
                1.0e-12,
            ),
            ("near_probe_characteristic_max_leakage_ratio", True, 1.0e-12),
        ),
        "V-012D": (
            (
                "min_finite_opening_applied_q_m3_s_extracted",
                False,
                1.0e-16,
            ),
            ("near_probe_characteristic_peak_abs_mean_pa", False, 1.0e-12),
            (
                "near_probe_characteristic_p50_time_offset_max_abs_s",
                True,
                1.0e-12,
            ),
            ("near_probe_characteristic_max_leakage_ratio", True, 1.0e-12),
            (
                "max_abs_post_closure_flux_derived_q_m3_s_extracted",
                True,
                1.0e-20,
            ),
            (
                "max_abs_post_closure_mass_flux_kg_m2_s_extracted",
                True,
                1.0e-18,
            ),
        ),
    }
    mesh: dict[str, Any] = {}
    cfl: dict[str, Any] = {}
    unclear: list[str] = []
    for verification_item, specs in case_metrics.items():
        case_rows = [
            row
            for row in dynamic
            if row["verification_item"] == verification_item
        ]
        mesh_rows = [
            row
            for row in case_rows
            if "mesh_comparison" in str(row["comparison_groups"])
        ]
        cfl_rows = [
            row
            for row in case_rows
            if "cfl_comparison" in str(row["comparison_groups"])
        ]
        mesh_metrics = [
            _mesh_metric_observation(
                mesh_rows,
                key,
                error_like=error_like,
                floor=floor,
            )
            for key, error_like, floor in specs
        ]
        cfl_metrics = [
            _cfl_metric_observation(cfl_rows, key) for key, _, _ in specs
        ]
        runtime_mesh = _mesh_metric_observation(
            mesh_rows,
            "runtime_s",
            error_like=False,
            floor=1.0e-12,
        )
        runtime_cfl = _cfl_metric_observation(cfl_rows, "runtime_s")
        step_cfl = _cfl_metric_observation(cfl_rows, "step_count")
        mesh[verification_item] = {
            "metrics": mesh_metrics,
            "runtime": runtime_mesh,
        }
        cfl[verification_item] = {
            "metrics": cfl_metrics,
            "runtime": runtime_cfl,
            "step_count": step_cfl,
        }
        for observation in mesh_metrics:
            if observation["classification"] in {
                "no_clear_improvement",
                "no_clear_contraction",
                "insufficient_data",
            }:
                unclear.append(
                    f"{verification_item}:{observation['metric']}"
                )

    return {
        "mesh_observation": mesh,
        "cfl_observation": cfl,
        "mesh_observation_complete": bool(
            all(
                len(
                    [
                        row
                        for row in dynamic
                        if row["verification_item"] == verification_item
                        and "mesh_comparison"
                        in str(row["comparison_groups"])
                    ]
                )
                == 3
                for verification_item in _DYNAMIC_ITEMS
            )
        ),
        "cfl_observation_complete": bool(
            all(
                len(
                    [
                        row
                        for row in dynamic
                        if row["verification_item"] == verification_item
                        and "cfl_comparison"
                        in str(row["comparison_groups"])
                    ]
                )
                == 2
                for verification_item in _DYNAMIC_ITEMS
            )
        ),
        "unclear_primary_metrics": unclear,
        "cell_400_decision": (
            "consider_only_after_human_review_of_unclear_metrics"
            if unclear
            else "not_required_by_initial_50_100_200_observation"
        ),
        "finest_mesh_is_exact_solution": False,
        "lower_cfl_is_truth": False,
        "formal_regression_band_applied": False,
    }
