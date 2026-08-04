"""Independent U3 B0 subcooled-liquid discharge reference evaluator.

This module implements only the verification reference defined by
``stage7_u3_b0_discharge_boundary_contract_v1.json``.  It is intentionally
independent from any future FVM boundary adapter and does not alter production
solver behavior.

The retained stream-level convention is positive out of the modeled domain:

    m_dot = Cd * Aeff * sqrt(2 * rho0 * (p0 - pb))
    u_exit = m_dot / (rho0 * Aeff)
    M_dot_stream = m_dot * u_exit
    E_dot_stream = m_dot * h0

Static pressure-force mapping is outside this B0 reference scope.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "stage7_u3_b0_independent_reference_v1"
CONTRACT_SCHEMA_VERSION = "stage7_u3_b0_discharge_boundary_contract_v1"

SUCCESS_CLOSED = "SUCCESS_CLOSED"
SUCCESS_ZERO_PRESSURE_DROP = "SUCCESS_ZERO_PRESSURE_DROP"
SUCCESS_FORWARD_LIQUID_DISCHARGE = "SUCCESS_FORWARD_LIQUID_DISCHARGE"
NONFINITE_INPUT = "NONFINITE_INPUT"
OPENING_OUTSIDE_UNIT_INTERVAL = "OPENING_OUTSIDE_UNIT_INTERVAL"
NONPOSITIVE_REFERENCE_AREA = "NONPOSITIVE_REFERENCE_AREA"
NONPOSITIVE_DISCHARGE_COEFFICIENT = "NONPOSITIVE_DISCHARGE_COEFFICIENT"
REVERSE_PRESSURE_NOT_SUPPORTED = "REVERSE_PRESSURE_NOT_SUPPORTED"
UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE = (
    "UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE"
)
DOWNSTREAM_LIQUID_SCOPE_FAILURE = "DOWNSTREAM_LIQUID_SCOPE_FAILURE"
PROPERTY_BACKEND_FAILURE = "PROPERTY_BACKEND_FAILURE"


@dataclass(frozen=True)
class ReferenceInput:
    case_id: str
    upstream_pressure_pa: float
    upstream_temperature_K: float
    back_pressure_pa: float
    reference_area_m2: float
    opening_fraction: float
    discharge_coefficient: float
    minimum_downstream_subcooling_margin_K: float


@dataclass(frozen=True)
class ReferenceResult:
    case_id: str
    formal_outcome: str
    formal_message: str
    upstream_pressure_pa: float
    upstream_temperature_K: float
    back_pressure_pa: float
    delta_p_pa: float
    reference_area_m2: float
    opening_fraction: float
    effective_area_m2: float
    discharge_coefficient: float
    upstream_density_kg_m3: float | None
    upstream_enthalpy_J_kg: float | None
    upstream_entropy_J_kg_K: float | None
    upstream_phase: str | None
    upstream_saturation_temperature_K: float | None
    upstream_subcooling_margin_K: float | None
    downstream_saturation_temperature_K: float | None
    downstream_subcooling_margin_K: float | None
    mass_flow_rate_kg_s: float
    exit_velocity_m_s: float
    mass_transfer_rate_outward_kg_s: float
    momentum_stream_transfer_outward_N: float
    energy_transfer_outward_W: float

    @property
    def succeeded(self) -> bool:
        return self.formal_outcome.startswith("SUCCESS_")


def _finite(*values: float) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _zero_result(
    inputs: ReferenceInput,
    outcome: str,
    message: str,
    *,
    delta_p_pa: float,
    effective_area_m2: float,
    properties: dict[str, float | str | None] | None = None,
) -> ReferenceResult:
    props = properties or {}
    return ReferenceResult(
        case_id=inputs.case_id,
        formal_outcome=outcome,
        formal_message=message,
        upstream_pressure_pa=inputs.upstream_pressure_pa,
        upstream_temperature_K=inputs.upstream_temperature_K,
        back_pressure_pa=inputs.back_pressure_pa,
        delta_p_pa=delta_p_pa,
        reference_area_m2=inputs.reference_area_m2,
        opening_fraction=inputs.opening_fraction,
        effective_area_m2=effective_area_m2,
        discharge_coefficient=inputs.discharge_coefficient,
        upstream_density_kg_m3=_optional_float(props.get("rho0")),
        upstream_enthalpy_J_kg=_optional_float(props.get("h0")),
        upstream_entropy_J_kg_K=_optional_float(props.get("s0")),
        upstream_phase=_optional_str(props.get("upstream_phase")),
        upstream_saturation_temperature_K=_optional_float(
            props.get("upstream_Tsat")
        ),
        upstream_subcooling_margin_K=_optional_float(
            props.get("upstream_subcooling")
        ),
        downstream_saturation_temperature_K=_optional_float(
            props.get("downstream_Tsat")
        ),
        downstream_subcooling_margin_K=_optional_float(
            props.get("downstream_subcooling")
        ),
        mass_flow_rate_kg_s=0.0,
        exit_velocity_m_s=0.0,
        mass_transfer_rate_outward_kg_s=0.0,
        momentum_stream_transfer_outward_N=0.0,
        energy_transfer_outward_W=0.0,
    )


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _load_coolprop() -> tuple[Any, Any, str]:
    from CoolProp import __version__ as coolprop_version
    from CoolProp.CoolProp import PhaseSI, PropsSI

    return PropsSI, PhaseSI, str(coolprop_version)


def evaluate_reference(inputs: ReferenceInput) -> ReferenceResult:
    """Evaluate one locked B0 reference row without using an adapter helper."""

    numeric_inputs = (
        inputs.upstream_pressure_pa,
        inputs.upstream_temperature_K,
        inputs.back_pressure_pa,
        inputs.reference_area_m2,
        inputs.opening_fraction,
        inputs.discharge_coefficient,
        inputs.minimum_downstream_subcooling_margin_K,
    )
    if not _finite(*numeric_inputs):
        return _zero_result(
            inputs,
            NONFINITE_INPUT,
            "One or more numeric inputs are nonfinite.",
            delta_p_pa=math.nan,
            effective_area_m2=math.nan,
        )
    if inputs.reference_area_m2 <= 0.0:
        return _zero_result(
            inputs,
            NONPOSITIVE_REFERENCE_AREA,
            "Reference area must be positive.",
            delta_p_pa=inputs.upstream_pressure_pa - inputs.back_pressure_pa,
            effective_area_m2=inputs.reference_area_m2 * inputs.opening_fraction,
        )
    if not 0.0 <= inputs.opening_fraction <= 1.0:
        return _zero_result(
            inputs,
            OPENING_OUTSIDE_UNIT_INTERVAL,
            "Opening fraction must be in [0, 1].",
            delta_p_pa=inputs.upstream_pressure_pa - inputs.back_pressure_pa,
            effective_area_m2=inputs.reference_area_m2 * inputs.opening_fraction,
        )
    if inputs.discharge_coefficient <= 0.0:
        return _zero_result(
            inputs,
            NONPOSITIVE_DISCHARGE_COEFFICIENT,
            "Discharge coefficient must be positive.",
            delta_p_pa=inputs.upstream_pressure_pa - inputs.back_pressure_pa,
            effective_area_m2=inputs.reference_area_m2 * inputs.opening_fraction,
        )

    delta_p = inputs.upstream_pressure_pa - inputs.back_pressure_pa
    effective_area = inputs.reference_area_m2 * inputs.opening_fraction
    if delta_p < 0.0:
        return _zero_result(
            inputs,
            REVERSE_PRESSURE_NOT_SUPPORTED,
            "Back pressure exceeds upstream pressure; reverse flow is out of scope.",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
        )

    try:
        PropsSI, PhaseSI, _ = _load_coolprop()
        rho0 = float(
            PropsSI(
                "DMASS",
                "P",
                inputs.upstream_pressure_pa,
                "T",
                inputs.upstream_temperature_K,
                "CO2",
            )
        )
        h0 = float(
            PropsSI(
                "HMASS",
                "P",
                inputs.upstream_pressure_pa,
                "T",
                inputs.upstream_temperature_K,
                "CO2",
            )
        )
        s0 = float(
            PropsSI(
                "SMASS",
                "P",
                inputs.upstream_pressure_pa,
                "T",
                inputs.upstream_temperature_K,
                "CO2",
            )
        )
        upstream_phase = str(
            PhaseSI(
                "P",
                inputs.upstream_pressure_pa,
                "T",
                inputs.upstream_temperature_K,
                "CO2",
            )
        )
        upstream_Tsat = float(
            PropsSI("T", "P", inputs.upstream_pressure_pa, "Q", 0.0, "CO2")
        )
        downstream_Tsat = float(
            PropsSI("T", "P", inputs.back_pressure_pa, "Q", 0.0, "CO2")
        )
    except Exception as exc:  # CoolProp exception is part of the formal evidence.
        return _zero_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            f"CoolProp evaluation failed: {type(exc).__name__}: {exc}",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
        )

    properties: dict[str, float | str] = {
        "rho0": rho0,
        "h0": h0,
        "s0": s0,
        "upstream_phase": upstream_phase,
        "upstream_Tsat": upstream_Tsat,
        "upstream_subcooling": upstream_Tsat - inputs.upstream_temperature_K,
        "downstream_Tsat": downstream_Tsat,
        "downstream_subcooling": downstream_Tsat
        - inputs.upstream_temperature_K,
    }
    if not _finite(rho0, h0, s0, upstream_Tsat, downstream_Tsat) or rho0 <= 0.0:
        return _zero_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            "CoolProp returned a nonfinite or nonpositive required property.",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
            properties=properties,
        )

    normalized_phase = upstream_phase.lower().replace("_", "")
    upstream_subcooling = upstream_Tsat - inputs.upstream_temperature_K
    if "liquid" not in normalized_phase or upstream_subcooling <= 0.0:
        return _zero_result(
            inputs,
            UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE,
            "Upstream state is not a positively subcooled liquid.",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
            properties=properties,
        )

    downstream_subcooling = downstream_Tsat - inputs.upstream_temperature_K
    if downstream_subcooling < inputs.minimum_downstream_subcooling_margin_K:
        return _zero_result(
            inputs,
            DOWNSTREAM_LIQUID_SCOPE_FAILURE,
            "Downstream pressure does not retain the locked liquid-scope margin.",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
            properties=properties,
        )

    if effective_area == 0.0:
        return _zero_result(
            inputs,
            SUCCESS_CLOSED,
            "Closed element identity retained exactly.",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
            properties=properties,
        )
    if delta_p == 0.0:
        return _zero_result(
            inputs,
            SUCCESS_ZERO_PRESSURE_DROP,
            "Zero-pressure-drop identity retained exactly.",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
            properties=properties,
        )

    mass_flow = (
        inputs.discharge_coefficient
        * effective_area
        * math.sqrt(2.0 * rho0 * delta_p)
    )
    exit_velocity = mass_flow / (rho0 * effective_area)
    momentum_transfer = mass_flow * exit_velocity
    energy_transfer = mass_flow * h0
    if not _finite(mass_flow, exit_velocity, momentum_transfer, energy_transfer):
        return _zero_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            "Reference transfer construction produced a nonfinite value.",
            delta_p_pa=delta_p,
            effective_area_m2=effective_area,
            properties=properties,
        )

    return ReferenceResult(
        case_id=inputs.case_id,
        formal_outcome=SUCCESS_FORWARD_LIQUID_DISCHARGE,
        formal_message="Independent subcooled-liquid orifice reference evaluated.",
        upstream_pressure_pa=inputs.upstream_pressure_pa,
        upstream_temperature_K=inputs.upstream_temperature_K,
        back_pressure_pa=inputs.back_pressure_pa,
        delta_p_pa=delta_p,
        reference_area_m2=inputs.reference_area_m2,
        opening_fraction=inputs.opening_fraction,
        effective_area_m2=effective_area,
        discharge_coefficient=inputs.discharge_coefficient,
        upstream_density_kg_m3=rho0,
        upstream_enthalpy_J_kg=h0,
        upstream_entropy_J_kg_K=s0,
        upstream_phase=upstream_phase,
        upstream_saturation_temperature_K=upstream_Tsat,
        upstream_subcooling_margin_K=upstream_subcooling,
        downstream_saturation_temperature_K=downstream_Tsat,
        downstream_subcooling_margin_K=downstream_subcooling,
        mass_flow_rate_kg_s=mass_flow,
        exit_velocity_m_s=exit_velocity,
        mass_transfer_rate_outward_kg_s=mass_flow,
        momentum_stream_transfer_outward_N=momentum_transfer,
        energy_transfer_outward_W=energy_transfer,
    )


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("Unexpected U3 B0 contract schema")
    if contract.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B0 contract must be locked before execution")
    if contract.get("approval_boundary", {}).get("u3_b0_contract_locked") is not True:
        raise ValueError("u3_b0_contract_locked must be true")
    return contract


def build_case_inputs(contract: dict[str, Any]) -> list[ReferenceInput]:
    PropsSI, _, _ = _load_coolprop()
    state = contract["upstream_state_definition"]
    geometry = contract["geometry_and_coefficients"]
    tolerances = contract["acceptance_tolerances"]
    p0 = float(state["pressure_pa"])
    base_subcooling = float(state["subcooling_K"])
    upstream_Tsat = float(PropsSI("T", "P", p0, "Q", 0.0, "CO2"))

    inputs: list[ReferenceInput] = []
    for row in contract["benchmark_cases"]:
        subcooling = float(row.get("upstream_subcooling_override_K", base_subcooling))
        inputs.append(
            ReferenceInput(
                case_id=str(row["case_id"]),
                upstream_pressure_pa=p0,
                upstream_temperature_K=upstream_Tsat - subcooling,
                back_pressure_pa=float(row["back_pressure_pa"]),
                reference_area_m2=float(geometry["reference_area_m2"]),
                opening_fraction=float(row["opening_fraction"]),
                discharge_coefficient=float(row["discharge_coefficient"]),
                minimum_downstream_subcooling_margin_K=float(
                    tolerances["minimum_downstream_subcooling_margin_K"]
                ),
            )
        )
    return inputs


def evaluate_contract(contract: dict[str, Any]) -> list[ReferenceResult]:
    return [evaluate_reference(inputs) for inputs in build_case_inputs(contract)]


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows_list = list(rows)
    if not rows_list:
        raise ValueError(f"No rows for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_list[0]))
        writer.writeheader()
        writer.writerows(rows_list)


def _write_plots(output_dir: Path, results: list[ReferenceResult]) -> None:
    import matplotlib.pyplot as plt

    successes = [
        row for row in results if row.formal_outcome == SUCCESS_FORWARD_LIQUID_DISCHARGE
    ]

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter(
        [row.delta_p_pa for row in successes],
        [row.mass_flow_rate_kg_s for row in successes],
    )
    ax.set_xlabel("Pressure drop [Pa]")
    ax.set_ylabel("Reference mass flow [kg/s]")
    ax.set_title("U3 B0 independent liquid-orifice reference")
    fig.tight_layout()
    fig.savefig(output_dir / "mass_flow_vs_pressure_drop.png", dpi=160)
    plt.close(fig)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter(
        [row.effective_area_m2 for row in successes],
        [row.mass_flow_rate_kg_s for row in successes],
        label="area series",
    )
    ax.set_xlabel("Effective area [m2]")
    ax.set_ylabel("Reference mass flow [kg/s]")
    ax.set_title("Area and discharge-coefficient scaling inputs")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "area_and_Cd_scaling.png", dpi=160)
    plt.close(fig)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter(
        [row.mass_flow_rate_kg_s for row in successes],
        [0.0 for _ in successes],
    )
    ax.set_xlabel("Reference mass flow [kg/s]")
    ax.set_ylabel("Independent-reference residual [W]")
    ax.set_title("Reference self-consistency placeholder: zero by construction")
    fig.tight_layout()
    fig.savefig(output_dir / "energy_transfer_residual.png", dpi=160)
    plt.close(fig)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_artifact(
    contract_path: Path,
    output_dir: Path,
    *,
    source_git_sha: str,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    results = evaluate_contract(contract)
    expected = {
        str(row["case_id"]): str(row["expected_outcome"])
        for row in contract["benchmark_cases"]
    }
    for result in results:
        if result.formal_outcome != expected[result.case_id]:
            raise RuntimeError(
                f"{result.case_id}: {result.formal_outcome} != {expected[result.case_id]}"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rows = [asdict(result) for result in results]
    _write_csv(output_dir / "benchmark_cases.csv", rows)
    _write_csv(
        output_dir / "property_scope_history.csv",
        [
            {
                "case_id": row.case_id,
                "formal_outcome": row.formal_outcome,
                "upstream_phase": row.upstream_phase,
                "upstream_subcooling_margin_K": row.upstream_subcooling_margin_K,
                "downstream_subcooling_margin_K": row.downstream_subcooling_margin_K,
                "upstream_density_kg_m3": row.upstream_density_kg_m3,
                "upstream_enthalpy_J_kg": row.upstream_enthalpy_J_kg,
                "upstream_entropy_J_kg_K": row.upstream_entropy_J_kg_K,
            }
            for row in results
        ],
    )
    _write_csv(
        output_dir / "conservative_flux_budget.csv",
        [
            {
                "case_id": row.case_id,
                "formal_outcome": row.formal_outcome,
                "mass_transfer_rate_outward_kg_s": row.mass_transfer_rate_outward_kg_s,
                "momentum_stream_transfer_outward_N": row.momentum_stream_transfer_outward_N,
                "energy_transfer_outward_W": row.energy_transfer_outward_W,
                "static_pressure_force_included": False,
            }
            for row in results
        ],
    )
    _write_csv(
        output_dir / "guard_outcomes.csv",
        [
            {
                "case_id": row.case_id,
                "formal_outcome": row.formal_outcome,
                "formal_message": row.formal_message,
            }
            for row in results
            if not row.succeeded
        ],
    )
    _write_plots(output_dir, results)

    try:
        _, _, coolprop_version = _load_coolprop()
    except Exception:
        coolprop_version = "unavailable"

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "verification_only_independent_reference",
        "contract_schema_version": contract["schema_version"],
        "contract_status": contract["status"],
        "issue": 109,
        "case_count": len(results),
        "success_count": sum(result.succeeded for result in results),
        "guard_count": sum(not result.succeeded for result in results),
        "formal_outcomes": {
            result.case_id: result.formal_outcome for result in results
        },
        "exact_zero_identities_retained": all(
            result.mass_flow_rate_kg_s == 0.0
            and result.momentum_stream_transfer_outward_N == 0.0
            and result.energy_transfer_outward_W == 0.0
            for result in results
            if result.formal_outcome
            in {SUCCESS_CLOSED, SUCCESS_ZERO_PRESSURE_DROP}
        ),
        "u3_b0_contract_locked": True,
        "u3_b0_reference_implemented": True,
        "u3_b0_adapter_implemented": False,
        "u3_b0_component_benchmark_execution_complete": False,
        "u3_component_benchmark_accepted": False,
        "physical_discharge_boundary_approved": False,
        "two_phase_critical_discharge_accuracy_approved": False,
        "integrated_blowdown_model_approved": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
        "provenance": {
            "source_git_sha": source_git_sha,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "coolprop_version": coolprop_version,
            "property_backend": "CoolProp",
            "tracked_git_status": "",
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_lines = [
        "# U3 B0 Independent Reference Report",
        "",
        "This artifact evaluates the locked subcooled-liquid orifice reference only.",
        "It does not implement or approve an FVM boundary adapter.",
        "",
        "## Formal outcomes",
        "",
    ]
    report_lines.extend(
        f"- `{row.case_id}`: `{row.formal_outcome}`" for row in results
    )
    report_lines.extend(
        [
            "",
            "## Approval boundary",
            "",
            "```text",
            "u3_b0_reference_implemented = true",
            "u3_b0_adapter_implemented = false",
            "u3_b0_component_benchmark_execution_complete = false",
            "physical_discharge_boundary_approved = false",
            "physical_validation = false",
            "design_use_acceptance = false",
            "production_hem_activation_approved = false",
            "```",
            "",
        ]
    )
    (output_dir / "report.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )

    manifest_names = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.name != "artifact_sha256.txt"
    )
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output_dir / name)}  {name}\n" for name in manifest_names),
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--source-git-sha",
        default=os.environ.get("ANALYSIS_SOURCE_GIT_SHA", "UNKNOWN"),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    write_artifact(
        args.contract,
        args.output_dir,
        source_git_sha=str(args.source_git_sha),
    )


if __name__ == "__main__":
    main()
