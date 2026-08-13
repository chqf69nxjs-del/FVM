from __future__ import annotations

from typing import Any

import numpy as np

import u3_b2_a1_finite_compression_guard_front_8_step as runner
import u3_b2_a1_finite_compression_hugoniot_8_step as base
import u3_b2_a1_finite_compression_step493_root_topology_diagnostic as inc8a
import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    normalize_phase,
)


_active_b1_contract: dict[str, Any] | None = None


class CorrectedDynamicGuardFrontHugoniotHook(
    runner.DynamicGuardFrontHugoniotHook
):
    def __init__(self, *, b1_contract: dict[str, Any], **kwargs: Any) -> None:
        global _active_b1_contract
        _active_b1_contract = b1_contract
        super().__init__(b1_contract=b1_contract, **kwargs)


def _dynamic_root_run(
    *,
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
    U: np.ndarray,
    parent_root: dict[str, str],
):
    del b1_contract
    if _active_b1_contract is None:
        raise RuntimeError("authoritative B1 contract was not bound")

    provider = CoolPropB2StateProvider()
    hook = base.A1FiniteCompressionHugoniotShortHook(
        contract=contract,
        b1_contract=_active_b1_contract,
        case_id=base.CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(parent_root["root_pressure_pa"])
    state_id = hook.state_id
    reconstruction = provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    denominator = float(static.density_kg_m3 * static.sound_speed_m_s**2)
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(contract, state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        contract["acceptance_tolerances"]["velocity_zero_tolerance_m_s"]
    )
    if (
        float(static.velocity_m_s) < -velocity_tolerance
        or not 0.0 <= float(static.velocity_m_s / static.sound_speed_m_s) < 1.0
        or normalize_phase(str(static.phase)) not in allowed_phases
    ):
        raise inc8a.DiagnosticStop(
            "NONFINITE_OR_NONPOSITIVE_STATE", "outlet scope departure"
        )

    base.inc5_core.HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG = (
        base.inc5_core.HUGONIOT_ENERGY_TOLERANCE_J_KG
    )
    curve = base.inc5_final.IdentityStatusPropagatedHugoniotCurve(
        static=static,
        hook=hook,
        allowed_phases=allowed_phases,
        velocity_tolerance_m_s=velocity_tolerance,
        pressure_denominator_pa=denominator,
    )
    fixed_raw = [
        curve.evaluate(float(chi), "increment_8c_fixed_scan")
        for chi in base.inc5_core.CHI_NODES
    ]
    fixed_rows = inc8a._annotate_fixed(fixed_raw)

    success_seen = False
    for row in fixed_rows:
        if inc8a._is_success(row):
            success_seen = True
        elif inc8a._is_unavailable(row):
            if success_seen:
                raise inc8a.DiagnosticStop(
                    "UNEXPECTED_B1_FAILURE",
                    "B1-unavailable fixed node follows a successful node",
                )
        else:
            raise inc8a.DiagnosticStop(
                "UNEXPECTED_B1_FAILURE",
                f"unexpected fixed-scan outcome: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
            )

    successful_fixed = [row for row in fixed_rows if inc8a._is_success(row)]
    unavailable_fixed = [
        row for row in fixed_rows if inc8a._is_unavailable(row)
    ]
    if not successful_fixed:
        raise inc8a.DiagnosticStop(
            "NO_SUCCESSFUL_DOMAIN", "fixed scan has no B1-success domain"
        )
    if not base.inc5_core._monotone_nonincreasing(fixed_rows):
        raise inc8a.DiagnosticStop(
            "SUCCESS_DOMAIN_NONMONOTONE",
            "fixed successful residuals are nonmonotone",
        )
    fixed_brackets = base.inc5_core._brackets(fixed_rows)
    if len(fixed_brackets) > 1:
        raise inc8a.DiagnosticStop(
            "MULTIPLE_COMPATIBILITY_ROOTS", "multiple fixed root brackets"
        )

    guard_rows: list[dict[str, Any]] = []
    topology_source: list[dict[str, Any]]
    selected_root: dict[str, Any] = {
        "selected_root_present": False,
        "diagnostic_classification": None,
    }
    classification: str

    if len(fixed_brackets) == 1:
        topology_source = successful_fixed
        raw_root = base.inc5_core._bisect_compatibility_root(
            curve="GENERAL_EOS_HUGONIOT",
            bracket=fixed_brackets[0],
            evaluate_chi=curve.evaluate,
        )
        root = inc8a._complete_root(
            raw_root=raw_root,
            curve=curve,
            hook=hook,
            state_id=state_id,
            static=static,
            denominator=denominator,
        )
        classification = inc8a.SUPPORTED
        selected_root = {**root, "selected_root_present": True}
    elif unavailable_fixed:
        _, refined_success, guard_rows = inc8a._refine_guard_front(
            curve=curve,
            lower_row=unavailable_fixed[-1],
            upper_row=successful_fixed[0],
        )
        topology_source = [refined_success] + [
            row
            for row in successful_fixed
            if float(row["requested_chi"])
            > float(refined_success["requested_chi"])
        ]
        topology_source = sorted(
            topology_source, key=lambda row: float(row["requested_chi"])
        )
        refined_residual = float(
            refined_success["compatibility_residual_kg_s"]
        )
        if refined_residual < -inc8a.ROOT_TOLERANCE:
            classification = inc8a.INSIDE_UNAVAILABLE
        else:
            brackets = base.inc5_core._brackets(topology_source)
            if len(brackets) > 1:
                raise inc8a.DiagnosticStop(
                    "MULTIPLE_COMPATIBILITY_ROOTS", "multiple refined roots"
                )
            if len(brackets) == 0:
                last_residual = float(
                    topology_source[-1]["compatibility_residual_kg_s"]
                )
                classification = (
                    inc8a.CAP_REQUIRED
                    if last_residual > inc8a.ROOT_TOLERANCE
                    else inc8a.WEAK_SCOPE
                )
            else:
                raw_root = base.inc5_core._bisect_compatibility_root(
                    curve="GENERAL_EOS_HUGONIOT",
                    bracket=brackets[0],
                    evaluate_chi=curve.evaluate,
                )
                root = inc8a._complete_root(
                    raw_root=raw_root,
                    curve=curve,
                    hook=hook,
                    state_id=state_id,
                    static=static,
                    denominator=denominator,
                )
                classification = inc8a.SUPPORTED
                selected_root = {**root, "selected_root_present": True}
    else:
        topology_source = successful_fixed
        first_residual = float(
            successful_fixed[0]["compatibility_residual_kg_s"]
        )
        last_residual = float(
            successful_fixed[-1]["compatibility_residual_kg_s"]
        )
        if (
            float(successful_fixed[0]["requested_chi"])
            <= base.WEAK_COMPRESSION_CHI_LIMIT
            and first_residual < -inc8a.ROOT_TOLERANCE
        ):
            classification = inc8a.WEAK_SCOPE
        elif last_residual > inc8a.ROOT_TOLERANCE:
            classification = inc8a.CAP_REQUIRED
        else:
            classification = inc8a.WEAK_SCOPE

    topology_rows = [
        {
            **row,
            "row_role": "ROOT_TOPOLOGY",
            "root_topology_member": True,
            "root_topology_order": index,
        }
        for index, row in enumerate(topology_source, start=1)
    ]
    topology_residuals = [
        float(row["compatibility_residual_kg_s"]) for row in topology_rows
    ]
    topology_monotone = bool(
        topology_residuals
        and all(
            right <= left
            for left, right in zip(
                topology_residuals, topology_residuals[1:]
            )
        )
    )
    if not topology_monotone:
        raise inc8a.DiagnosticStop(
            "SUCCESS_DOMAIN_NONMONOTONE", "dynamic root topology is nonmonotone"
        )
    topology_brackets = base.inc5_core._brackets(topology_rows)
    if len(topology_brackets) > 1:
        raise inc8a.DiagnosticStop(
            "MULTIPLE_COMPATIBILITY_ROOTS", "multiple dynamic topology roots"
        )

    summary = {
        "fixed_scan_node_count": len(fixed_rows),
        "fixed_unavailable_node_count": len(unavailable_fixed),
        "fixed_success_node_count": len(successful_fixed),
        "fixed_sign_change_count": len(fixed_brackets),
        "fixed_success_residual_monotone_nonincreasing": True,
        "guard_front_refinement_applied": bool(guard_rows),
        "guard_front_iterations": len(guard_rows),
        "root_topology_node_count": len(topology_rows),
        "root_topology_requested_chi": [
            float(row["requested_chi"]) for row in topology_rows
        ],
        "root_topology_residuals_kg_s": topology_residuals,
        "root_topology_monotone_nonincreasing": topology_monotone,
        "root_topology_sign_change_count": len(topology_brackets),
        "selected_root_present": bool(
            selected_root.get("selected_root_present")
        ),
        "selected_root_chi": selected_root.get("requested_chi"),
        "selected_root_residual_kg_s": selected_root.get(
            "root_mass_residual_kg_s"
        ),
        "selected_root_gate_passed": selected_root.get(
            "root_gate_passed", False
        ),
        "outcome": classification,
        "diagnostic_classification_complete": classification
        in inc8a.CLASSIFIED,
        "actual_continuation_supported": classification == inc8a.SUPPORTED,
    }
    selected_root["diagnostic_classification"] = classification
    return (
        summary,
        fixed_rows,
        guard_rows,
        topology_rows,
        list(curve.density_search_rows),
        selected_root,
    )


runner.DynamicGuardFrontHugoniotHook = (
    CorrectedDynamicGuardFrontHugoniotHook
)
runner.inc8a._run = _dynamic_root_run


if __name__ == "__main__":
    runner.main()
