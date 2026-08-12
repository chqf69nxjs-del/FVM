from __future__ import annotations

from typing import Any

import numpy as np

import u3_b2_a1_weak_compression_bridge_short_run as short_run


CORRECTION = (
    "requested_scan_coordinate_authoritative_realized_pressure_recorded"
)


def _corrected_positive_pressure_scan(
    *,
    hook: Any,
    U: np.ndarray,
) -> dict[str, Any]:
    reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    allowed_phases = {
        short_run.normalize_phase(value)
        for value in short_run.diagnostic._family(
            hook.contract,
            hook.state_id,
        )["allowed_normalized_phases"]
    }
    velocity_tolerance = float(
        hook.contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    short_run.diagnostic.QUADRATURE_ORDER = (
        short_run.horizon.ROOT_QUADRATURE_ORDER
    )
    isentrope = short_run.diagnostic.Isentrope(
        float(static.entropy_J_kg_K)
    )
    density = float(static.density_kg_m3)
    sound_speed = float(static.sound_speed_m_s)
    denominator = float(density * sound_speed**2)
    delta_p_max = float(denominator * short_run.CHI_MAX)
    offsets = short_run._positive_scan_offsets(delta_p_max)
    cache: dict[float, dict[str, Any]] = {}

    def evaluate_offset(offset_pa: float) -> dict[str, Any]:
        key = float(offset_pa)
        if key not in cache:
            candidate_pressure = float(static.pressure_pa + key)
            raw = short_run._full_wave_row(
                pressure_pa=candidate_pressure,
                static=static,
                isentrope=isentrope,
                hook=hook,
                area_m2=hook.area_m2,
                allowed_phases=allowed_phases,
                velocity_tolerance=velocity_tolerance,
                state_id=hook.state_id,
            )
            realized_offset = float(raw["pressure_offset_pa"])
            realized_chi = float(realized_offset / denominator)
            requested_chi = float(
                short_run.CHI_MAX
                if key == delta_p_max
                else key / denominator
            )
            within_scope = bool(
                key == 0.0 or 0.0 < key <= delta_p_max
            )
            item = dict(raw)
            item.update(
                {
                    "pressure_offset_pa": key,
                    "requested_pressure_offset_pa": key,
                    "realized_pressure_offset_pa": realized_offset,
                    "requested_pressure_pa": candidate_pressure,
                    "realized_pressure_pa": float(raw["pressure_pa"]),
                    "chi": requested_chi,
                    "requested_chi": requested_chi,
                    "realized_chi": realized_chi,
                    "chi_max": short_run.CHI_MAX,
                    "within_weak_compression_scope": within_scope,
                    "scan_coordinate_correction": CORRECTION,
                    "selected_sign_change_bracket_member": False,
                }
            )
            cache[key] = item
        return dict(cache[key])

    scan_rows = [evaluate_offset(offset) for offset in offsets]
    for index, row in enumerate(scan_rows):
        if not bool(row.get("evaluation_succeeded")):
            raise short_run.WeakCompressionShortRunStop(
                "POSITIVE_SCAN_EVALUATION_FAILURE",
                "positive-pressure scan evaluation failed at "
                f"node {index}: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                    "scan_coordinate_correction": CORRECTION,
                },
            )
        if not bool(row.get("local_candidate_admissible")):
            raise short_run.WeakCompressionShortRunStop(
                "POSITIVE_SCAN_INADMISSIBLE",
                f"positive-pressure scan node {index} is inadmissible",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                    "scan_coordinate_correction": CORRECTION,
                },
            )
        residual = row.get("compatibility_residual_kg_s")
        if residual is None or not np.isfinite(float(residual)):
            raise short_run.WeakCompressionShortRunStop(
                "POSITIVE_SCAN_NONFINITE_RESIDUAL",
                f"positive-pressure scan node {index} has no finite residual",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                    "scan_coordinate_correction": CORRECTION,
                },
            )
        if not bool(row["within_weak_compression_scope"]):
            raise short_run.WeakCompressionShortRunStop(
                "POSITIVE_SCAN_SCOPE_FAILURE",
                f"positive-pressure scan node {index} exceeds fixed chi scope",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                    "scan_coordinate_correction": CORRECTION,
                },
            )

    evaluable = short_run._brackets(scan_rows, admissible_only=False)
    admissible = short_run._brackets(scan_rows, admissible_only=True)
    if len(evaluable) != len(admissible):
        raise short_run.WeakCompressionShortRunStop(
            "LOCAL_ROOT_INADMISSIBLE",
            "a positive-pressure sign change is evaluable but inadmissible",
            {
                "positive_scan_rows": scan_rows,
                "positive_evaluable_brackets": evaluable,
                "positive_admissible_brackets": admissible,
                "delta_p_max_pa": delta_p_max,
                "scan_coordinate_correction": CORRECTION,
            },
        )
    if len(admissible) > 1:
        raise short_run.WeakCompressionShortRunStop(
            "MULTIPLE_LOCAL_ROOTS",
            "multiple positive-pressure sign-change brackets were observed",
            {
                "positive_scan_rows": scan_rows,
                "positive_admissible_brackets": admissible,
                "delta_p_max_pa": delta_p_max,
                "scan_coordinate_correction": CORRECTION,
            },
        )

    selected_offsets: set[float] = set()
    if admissible:
        selected_offsets = {
            float(admissible[0]["lower_offset_pa"]),
            float(admissible[0]["upper_offset_pa"]),
        }
    annotated = [
        {
            **row,
            "selected_sign_change_bracket_member": bool(
                float(row["pressure_offset_pa"]) in selected_offsets
            ),
        }
        for row in scan_rows
    ]
    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in annotated
    ]
    monotone_nonincreasing = bool(
        len(residuals) >= 2
        and all(
            residuals[index + 1] <= residuals[index]
            for index in range(len(residuals) - 1)
        )
    )
    return {
        "static": static,
        "rows": annotated,
        "evaluate_offset": evaluate_offset,
        "evaluable_brackets": evaluable,
        "admissible_brackets": admissible,
        "sign_change_count": len(admissible),
        "residual_monotone_nonincreasing": monotone_nonincreasing,
        "delta_p_max_pa": delta_p_max,
        "endpoint_residual_kg_s": residuals[0],
        "scope_limit_residual_kg_s": residuals[-1],
        "scan_coordinate_correction": CORRECTION,
    }


def main() -> None:
    short_run._positive_pressure_scan = _corrected_positive_pressure_scan
    short_run.main()


if __name__ == "__main__":
    main()
