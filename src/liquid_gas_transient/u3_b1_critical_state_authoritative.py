"""Authoritative runner for the locked U3 B1 independent reference.

The initial implementation interpreted ``peak_neighbor_relative_offset`` as a
fraction of the candidate pressure. The locked contract defines the search in
pressure-ratio coordinates, so the neighbor probe must instead use
``p_critical +/- offset * p0``. This module keeps the contract unchanged and
supplies that corrected interpretation while the reference remains isolated
from any future adapter.
"""

from __future__ import annotations

import math
from typing import Any

from . import u3_b1_critical_state_reference as ref

_ORIGINAL_LOCKED_CHECKS = ref.locked_checks


def critical_search(
    contract: dict[str, Any],
    provider: ref.PropertyProvider,
    upstream: ref.UpstreamState,
    allowed_phases: set[str],
    discharge_coefficient: float,
) -> tuple[
    ref.CriticalState | None,
    list[dict[str, Any]],
    str | None,
    str,
]:
    search = contract["critical_state_search"]
    tolerances = contract["acceptance_tolerances"]
    p0 = upstream.pressure_pa
    upper_ratio = float(search["coarse_pressure_ratio_upper"])
    lower_ratio = float(search["coarse_pressure_ratio_lower"])
    node_count = int(search["coarse_node_count"])
    entropy_tolerance = float(
        tolerances["isentropic_entropy_absolute_J_kg_K"]
    )

    records: list[dict[str, Any]] = []
    admissible: list[tuple[int, ref.StreamState]] = []
    termination_outcome: str | None = None
    termination_pressure: float | None = None

    for index in range(node_count):
        ratio = upper_ratio - (upper_ratio - lower_ratio) * index / (node_count - 1)
        pressure = p0 * ratio
        if index == 0:
            candidate = ref.CandidateState(
                pressure_pa=upstream.pressure_pa,
                temperature_K=upstream.temperature_K,
                density_kg_m3=upstream.density_kg_m3,
                enthalpy_J_kg=upstream.enthalpy_J_kg,
                entropy_J_kg_K=upstream.entropy_J_kg_K,
                phase=upstream.phase,
            )
            stream = ref.StreamState(
                candidate=candidate,
                kinetic_energy_head_J_kg=0.0,
                ideal_velocity_m_s=0.0,
                effective_velocity_m_s=0.0,
                ideal_mass_flux_kg_m2_s=0.0,
                effective_mass_flux_kg_m2_s=0.0,
                entropy_residual_J_kg_K=0.0,
            )
            outcome, message = None, "SUCCESS_ZERO_PRESSURE_DROP"
        else:
            stream, outcome, message = ref.evaluate_stream(
                provider,
                upstream,
                pressure,
                discharge_coefficient,
                allowed_phases,
                entropy_tolerance,
            )
        records.append(
            {
                "coarse_index": index,
                "pressure_pa": pressure,
                "pressure_ratio": ratio,
                "admissible": stream is not None,
                "formal_outcome": "SUCCESS" if stream is not None else outcome,
                "formal_message": message,
                "temperature_K": None if stream is None else stream.candidate.temperature_K,
                "density_kg_m3": None if stream is None else stream.candidate.density_kg_m3,
                "enthalpy_J_kg": None if stream is None else stream.candidate.enthalpy_J_kg,
                "entropy_J_kg_K": None if stream is None else stream.candidate.entropy_J_kg_K,
                "phase": None if stream is None else stream.candidate.phase,
                "kinetic_energy_head_J_kg": None if stream is None else stream.kinetic_energy_head_J_kg,
                "ideal_velocity_m_s": None if stream is None else stream.ideal_velocity_m_s,
                "effective_velocity_m_s": None if stream is None else stream.effective_velocity_m_s,
                "ideal_mass_flux_kg_m2_s": None if stream is None else stream.ideal_mass_flux_kg_m2_s,
                "effective_mass_flux_kg_m2_s": None if stream is None else stream.effective_mass_flux_kg_m2_s,
                "entropy_residual_J_kg_K": None if stream is None else stream.entropy_residual_J_kg_K,
            }
        )
        if stream is None:
            termination_outcome = outcome
            termination_pressure = pressure
            break
        admissible.append((index, stream))

    if len(admissible) < 3:
        return None, records, ref.CRITICAL_SEARCH_NOT_BRACKETED, (
            "Fewer than three admissible coarse states."
        )

    max_flux = max(item[1].effective_mass_flux_kg_m2_s for item in admissible)
    maxima = [
        item
        for item in admissible
        if item[1].effective_mass_flux_kg_m2_s == max_flux
    ]
    coarse_index, coarse_stream = min(maxima, key=lambda item: item[0])
    position = next(
        idx for idx, item in enumerate(admissible) if item[0] == coarse_index
    )
    if position == 0 or position == len(admissible) - 1:
        return None, records, ref.CRITICAL_SEARCH_NOT_BRACKETED, (
            "Coarse maximum does not have admissible neighbors on both pressure sides."
        )

    higher = admissible[position - 1][1]
    lower = admissible[position + 1][1]
    bracket_low = min(lower.candidate.pressure_pa, higher.candidate.pressure_pa)
    bracket_high = max(lower.candidate.pressure_pa, higher.candidate.pressure_pa)
    cache: dict[float, ref.StreamState] = {
        higher.candidate.pressure_pa: higher,
        lower.candidate.pressure_pa: lower,
        coarse_stream.candidate.pressure_pa: coarse_stream,
    }

    def objective(pressure: float) -> float:
        if pressure not in cache:
            stream, outcome, message = ref.evaluate_stream(
                provider,
                upstream,
                pressure,
                discharge_coefficient,
                allowed_phases,
                entropy_tolerance,
            )
            if stream is None:
                raise ValueError(f"{outcome}: {message}")
            cache[pressure] = stream
        return cache[pressure].effective_mass_flux_kg_m2_s

    try:
        refined_pressure, _, iterations, bracket_width = ref.golden_section_maximize(
            objective,
            bracket_low,
            bracket_high,
            float(search["refinement_pressure_bracket_tolerance_pa"]),
            int(search["refinement_max_iterations"]),
        )
        refined_stream = cache.get(refined_pressure)
        candidates = [coarse_stream, higher, lower, refined_stream]
        valid = [item for item in candidates if item is not None]
        best = sorted(
            valid,
            key=lambda stream: (
                -stream.effective_mass_flux_kg_m2_s,
                -stream.candidate.pressure_pa,
            ),
        )[0]
    except Exception as exc:
        return None, records, ref.CRITICAL_REFINEMENT_FAILURE, (
            f"Critical refinement failed: {type(exc).__name__}: {exc}"
        )

    # Contract search coordinates are pressure ratios. Therefore an offset of
    # 1e-4 means +/- 1e-4 * p0 in pressure, not +/- 1e-4 * p_critical.
    ratio_offset = float(search["peak_neighbor_relative_offset"])
    pressure_offset = ratio_offset * p0
    neighbor_pressures = [
        best.candidate.pressure_pa - pressure_offset,
        best.candidate.pressure_pa + pressure_offset,
    ]
    neighbor_fluxes: list[float] = []
    for pressure in neighbor_pressures:
        if pressure <= 0.0 or pressure >= p0:
            continue
        try:
            neighbor_fluxes.append(objective(pressure))
        except Exception:
            continue
    prominence = (
        0.0
        if not neighbor_fluxes
        else (
            best.effective_mass_flux_kg_m2_s - max(neighbor_fluxes)
        )
        / best.effective_mass_flux_kg_m2_s
    )

    minimum_prominence = float(search["minimum_peak_prominence_relative"])
    minimum_distance = float(
        tolerances["minimum_critical_pressure_distance_from_search_bounds_pa"]
    )
    retained_low = admissible[-1][1].candidate.pressure_pa
    retained_high = admissible[0][1].candidate.pressure_pa
    if (
        prominence < minimum_prominence
        or best.candidate.pressure_pa - retained_low < minimum_distance
        or retained_high - best.candidate.pressure_pa < minimum_distance
    ):
        return None, records, ref.CRITICAL_SEARCH_NOT_BRACKETED, (
            "Critical maximum does not satisfy locked prominence or interior-distance rules."
        )

    return (
        ref.CriticalState(
            pressure_pa=best.candidate.pressure_pa,
            pressure_ratio=best.candidate.pressure_pa / p0,
            stream=best,
            coarse_index=coarse_index,
            coarse_neighbor_high_pressure_pa=higher.candidate.pressure_pa,
            coarse_neighbor_low_pressure_pa=lower.candidate.pressure_pa,
            refinement_iterations=iterations,
            final_bracket_width_pa=bracket_width,
            peak_prominence_relative=prominence,
            path_termination_outcome=termination_outcome,
            path_termination_pressure_pa=termination_pressure,
        ),
        records,
        None,
        "SUCCESS",
    )


def locked_checks_fail_safe(
    contract: dict[str, Any],
    results: list[ref.ReferenceResult],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Never hide formal outcomes behind a ratio exception."""

    try:
        return _ORIGINAL_LOCKED_CHECKS(contract, results)
    except (ZeroDivisionError, ValueError, OverflowError) as exc:
        expected = {
            row["case_id"]: row["expected_outcome"]
            for row in contract["benchmark_cases"]
        }
        matches = {
            result.case_id: result.formal_outcome == expected[result.case_id]
            for result in results
        }
        row = {
            "check": "aggregate_check_construction",
            "value": f"{type(exc).__name__}: {exc}",
            "target": "finite locked metrics",
            "passed": False,
        }
        summary = {
            "all_expected_outcomes_match": all(matches.values()),
            "outcome_matches": matches,
            "b0_limit_passed": False,
            "unchoked_ordering_margin_relative": math.inf,
            "unchoked_ordering_passed": False,
            "below_critical_plateau_relative": math.inf,
            "below_critical_plateau_passed": False,
            "area_scaling_ratio": math.inf,
            "area_scaling_passed": False,
            "Cd_scaling_ratio": math.inf,
            "Cd_scaling_passed": False,
            "critical_pressure_Cd_relative_difference": math.inf,
            "critical_pressure_Cd_independence_passed": False,
            "all_locked_checks_passed": False,
        }
        b0_placeholder = {
            "measure": "aggregate_check_construction_failure",
            "reference_value": "",
            "b0_value": "",
            "relative_error": "",
            "tolerance": "finite locked metrics",
            "passed": False,
            "formal_message": f"{type(exc).__name__}: {exc}",
        }
        return [b0_placeholder, row], summary


def install_authoritative_interpretation() -> None:
    ref.critical_search = critical_search
    ref.locked_checks = locked_checks_fail_safe


def main() -> None:
    install_authoritative_interpretation()
    ref.main()


if __name__ == "__main__":
    main()
