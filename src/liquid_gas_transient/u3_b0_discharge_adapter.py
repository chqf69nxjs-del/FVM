"""Verification-only U3 B0 discharge component adapter.

This module is intentionally independent from ``u3_b0_discharge_reference``.
It consumes the locked U3 B0 contract, constructs outward stream transfers, and
compares its outputs with an immutable authoritative reference artifact.

The adapter remains disconnected from the production FVM boundary. Static
pressure-force mapping, choking, two-phase critical flow, and reverse flow are
outside this increment.
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
from typing import Any, Iterable, Protocol

SCHEMA_VERSION = "stage7_u3_b0_discharge_adapter_comparison_v1"
CONTRACT_SCHEMA_VERSION = "stage7_u3_b0_discharge_boundary_contract_v1"
REFERENCE_SCHEMA_VERSION = "stage7_u3_b0_independent_reference_v1"

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
CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE = (
    "CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE"
)


@dataclass(frozen=True)
class PropertySnapshot:
    density_kg_m3: float
    enthalpy_J_kg: float
    entropy_J_kg_K: float
    phase: str
    upstream_saturation_temperature_K: float
    downstream_saturation_temperature_K: float


class PropertyProvider(Protocol):
    version: str

    def saturation_temperature(self, pressure_pa: float) -> float: ...

    def snapshot(
        self,
        upstream_pressure_pa: float,
        upstream_temperature_K: float,
        back_pressure_pa: float,
    ) -> PropertySnapshot: ...


class CoolPropPropertyProvider:
    def __init__(self) -> None:
        from CoolProp import __version__ as coolprop_version
        from CoolProp.CoolProp import PhaseSI, PropsSI

        self._props = PropsSI
        self._phase = PhaseSI
        self.version = str(coolprop_version)

    def saturation_temperature(self, pressure_pa: float) -> float:
        return float(self._props("T", "P", pressure_pa, "Q", 0.0, "CO2"))

    def snapshot(
        self,
        upstream_pressure_pa: float,
        upstream_temperature_K: float,
        back_pressure_pa: float,
    ) -> PropertySnapshot:
        return PropertySnapshot(
            density_kg_m3=float(
                self._props(
                    "DMASS",
                    "P",
                    upstream_pressure_pa,
                    "T",
                    upstream_temperature_K,
                    "CO2",
                )
            ),
            enthalpy_J_kg=float(
                self._props(
                    "HMASS",
                    "P",
                    upstream_pressure_pa,
                    "T",
                    upstream_temperature_K,
                    "CO2",
                )
            ),
            entropy_J_kg_K=float(
                self._props(
                    "SMASS",
                    "P",
                    upstream_pressure_pa,
                    "T",
                    upstream_temperature_K,
                    "CO2",
                )
            ),
            phase=str(
                self._phase(
                    "P",
                    upstream_pressure_pa,
                    "T",
                    upstream_temperature_K,
                    "CO2",
                )
            ),
            upstream_saturation_temperature_K=self.saturation_temperature(
                upstream_pressure_pa
            ),
            downstream_saturation_temperature_K=self.saturation_temperature(
                back_pressure_pa
            ),
        )


@dataclass(frozen=True)
class AdapterInput:
    case_id: str
    upstream_pressure_pa: float
    upstream_temperature_K: float
    back_pressure_pa: float
    reference_area_m2: float
    opening_fraction: float
    discharge_coefficient: float
    minimum_downstream_subcooling_margin_K: float


@dataclass(frozen=True)
class AdapterResult:
    case_id: str
    formal_outcome: str
    formal_message: str
    upstream_pressure_pa: float
    upstream_temperature_K: float
    back_pressure_pa: float
    pressure_drop_pa: float
    reference_area_m2: float
    opening_fraction: float
    effective_area_m2: float
    discharge_coefficient: float
    density_kg_m3: float | None
    enthalpy_J_kg: float | None
    entropy_J_kg_K: float | None
    phase: str | None
    upstream_saturation_temperature_K: float | None
    upstream_subcooling_margin_K: float | None
    downstream_saturation_temperature_K: float | None
    downstream_subcooling_margin_K: float | None
    mass_transfer_outward_kg_s: float
    momentum_stream_transfer_outward_N: float
    energy_transfer_outward_W: float
    exit_velocity_m_s: float
    static_pressure_force_included: bool
    production_fvm_connected: bool

    @property
    def succeeded(self) -> bool:
        return self.formal_outcome.startswith("SUCCESS_")


def _finite(*values: float) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _empty_result(
    inputs: AdapterInput,
    outcome: str,
    message: str,
    *,
    pressure_drop_pa: float,
    effective_area_m2: float,
    snapshot: PropertySnapshot | None = None,
) -> AdapterResult:
    upstream_tsat = (
        None if snapshot is None else snapshot.upstream_saturation_temperature_K
    )
    downstream_tsat = (
        None if snapshot is None else snapshot.downstream_saturation_temperature_K
    )
    return AdapterResult(
        case_id=inputs.case_id,
        formal_outcome=outcome,
        formal_message=message,
        upstream_pressure_pa=inputs.upstream_pressure_pa,
        upstream_temperature_K=inputs.upstream_temperature_K,
        back_pressure_pa=inputs.back_pressure_pa,
        pressure_drop_pa=pressure_drop_pa,
        reference_area_m2=inputs.reference_area_m2,
        opening_fraction=inputs.opening_fraction,
        effective_area_m2=effective_area_m2,
        discharge_coefficient=inputs.discharge_coefficient,
        density_kg_m3=None if snapshot is None else snapshot.density_kg_m3,
        enthalpy_J_kg=None if snapshot is None else snapshot.enthalpy_J_kg,
        entropy_J_kg_K=None if snapshot is None else snapshot.entropy_J_kg_K,
        phase=None if snapshot is None else snapshot.phase,
        upstream_saturation_temperature_K=upstream_tsat,
        upstream_subcooling_margin_K=(
            None if upstream_tsat is None else upstream_tsat - inputs.upstream_temperature_K
        ),
        downstream_saturation_temperature_K=downstream_tsat,
        downstream_subcooling_margin_K=(
            None
            if downstream_tsat is None
            else downstream_tsat - inputs.upstream_temperature_K
        ),
        mass_transfer_outward_kg_s=0.0,
        momentum_stream_transfer_outward_N=0.0,
        energy_transfer_outward_W=0.0,
        exit_velocity_m_s=0.0,
        static_pressure_force_included=False,
        production_fvm_connected=False,
    )


def evaluate_adapter(
    inputs: AdapterInput,
    provider: PropertyProvider | None = None,
) -> AdapterResult:
    """Construct one verification-only component transfer row."""

    numeric = (
        inputs.upstream_pressure_pa,
        inputs.upstream_temperature_K,
        inputs.back_pressure_pa,
        inputs.reference_area_m2,
        inputs.opening_fraction,
        inputs.discharge_coefficient,
        inputs.minimum_downstream_subcooling_margin_K,
    )
    if not _finite(*numeric):
        return _empty_result(
            inputs,
            NONFINITE_INPUT,
            "One or more component inputs are nonfinite.",
            pressure_drop_pa=math.nan,
            effective_area_m2=math.nan,
        )
    pressure_drop = inputs.upstream_pressure_pa - inputs.back_pressure_pa
    effective_area = inputs.reference_area_m2 * inputs.opening_fraction
    if inputs.reference_area_m2 <= 0.0:
        return _empty_result(
            inputs,
            NONPOSITIVE_REFERENCE_AREA,
            "Reference area must be positive.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
        )
    if inputs.opening_fraction < 0.0 or inputs.opening_fraction > 1.0:
        return _empty_result(
            inputs,
            OPENING_OUTSIDE_UNIT_INTERVAL,
            "Opening fraction must be in [0, 1].",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
        )
    if inputs.discharge_coefficient <= 0.0:
        return _empty_result(
            inputs,
            NONPOSITIVE_DISCHARGE_COEFFICIENT,
            "Discharge coefficient must be positive.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
        )
    if pressure_drop < 0.0:
        return _empty_result(
            inputs,
            REVERSE_PRESSURE_NOT_SUPPORTED,
            "Reverse pressure is outside the B0 component scope.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
        )

    try:
        property_provider = provider or CoolPropPropertyProvider()
        snapshot = property_provider.snapshot(
            inputs.upstream_pressure_pa,
            inputs.upstream_temperature_K,
            inputs.back_pressure_pa,
        )
    except Exception as exc:
        return _empty_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            f"Property provider failed: {type(exc).__name__}: {exc}",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
        )

    required = (
        snapshot.density_kg_m3,
        snapshot.enthalpy_J_kg,
        snapshot.entropy_J_kg_K,
        snapshot.upstream_saturation_temperature_K,
        snapshot.downstream_saturation_temperature_K,
    )
    if not _finite(*required) or snapshot.density_kg_m3 <= 0.0:
        return _empty_result(
            inputs,
            PROPERTY_BACKEND_FAILURE,
            "Property provider returned an invalid required value.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
            snapshot=snapshot,
        )

    phase = snapshot.phase.lower().replace("_", "")
    upstream_subcooling = (
        snapshot.upstream_saturation_temperature_K - inputs.upstream_temperature_K
    )
    downstream_subcooling = (
        snapshot.downstream_saturation_temperature_K - inputs.upstream_temperature_K
    )
    if "liquid" not in phase or upstream_subcooling <= 0.0:
        return _empty_result(
            inputs,
            UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE,
            "Upstream state is not a positively subcooled liquid.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
            snapshot=snapshot,
        )
    if downstream_subcooling < inputs.minimum_downstream_subcooling_margin_K:
        return _empty_result(
            inputs,
            DOWNSTREAM_LIQUID_SCOPE_FAILURE,
            "Back pressure does not retain the locked liquid-scope margin.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
            snapshot=snapshot,
        )
    if effective_area == 0.0:
        return _empty_result(
            inputs,
            SUCCESS_CLOSED,
            "Closed component identity retained exactly.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
            snapshot=snapshot,
        )
    if pressure_drop == 0.0:
        return _empty_result(
            inputs,
            SUCCESS_ZERO_PRESSURE_DROP,
            "Zero-pressure-drop component identity retained exactly.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
            snapshot=snapshot,
        )

    try:
        speed_scale = math.sqrt(2.0 * pressure_drop / snapshot.density_kg_m3)
        exit_velocity = inputs.discharge_coefficient * speed_scale
        mass_transfer = snapshot.density_kg_m3 * effective_area * exit_velocity
        momentum_transfer = mass_transfer * exit_velocity
        energy_transfer = mass_transfer * snapshot.enthalpy_J_kg
    except Exception as exc:
        return _empty_result(
            inputs,
            CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE,
            f"Transfer construction failed: {type(exc).__name__}: {exc}",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
            snapshot=snapshot,
        )
    if not _finite(
        speed_scale,
        exit_velocity,
        mass_transfer,
        momentum_transfer,
        energy_transfer,
    ):
        return _empty_result(
            inputs,
            CONSERVATIVE_TRANSFER_CONSTRUCTION_FAILURE,
            "Transfer construction produced a nonfinite value.",
            pressure_drop_pa=pressure_drop,
            effective_area_m2=effective_area,
            snapshot=snapshot,
        )

    return AdapterResult(
        case_id=inputs.case_id,
        formal_outcome=SUCCESS_FORWARD_LIQUID_DISCHARGE,
        formal_message="Verification-only component transfers constructed.",
        upstream_pressure_pa=inputs.upstream_pressure_pa,
        upstream_temperature_K=inputs.upstream_temperature_K,
        back_pressure_pa=inputs.back_pressure_pa,
        pressure_drop_pa=pressure_drop,
        reference_area_m2=inputs.reference_area_m2,
        opening_fraction=inputs.opening_fraction,
        effective_area_m2=effective_area,
        discharge_coefficient=inputs.discharge_coefficient,
        density_kg_m3=snapshot.density_kg_m3,
        enthalpy_J_kg=snapshot.enthalpy_J_kg,
        entropy_J_kg_K=snapshot.entropy_J_kg_K,
        phase=snapshot.phase,
        upstream_saturation_temperature_K=(
            snapshot.upstream_saturation_temperature_K
        ),
        upstream_subcooling_margin_K=upstream_subcooling,
        downstream_saturation_temperature_K=(
            snapshot.downstream_saturation_temperature_K
        ),
        downstream_subcooling_margin_K=downstream_subcooling,
        mass_transfer_outward_kg_s=mass_transfer,
        momentum_stream_transfer_outward_N=momentum_transfer,
        energy_transfer_outward_W=energy_transfer,
        exit_velocity_m_s=exit_velocity,
        static_pressure_force_included=False,
        production_fvm_connected=False,
    )


def load_contract(path: Path) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise ValueError("Unexpected U3 B0 contract schema")
    if contract.get("status") != "LOCKED_BEFORE_RESULTS":
        raise ValueError("U3 B0 contract is not locked")
    if contract.get("approval_boundary", {}).get("u3_b0_contract_locked") is not True:
        raise ValueError("u3_b0_contract_locked must be true")
    return contract


def build_case_inputs(
    contract: dict[str, Any],
    provider: PropertyProvider | None = None,
) -> list[AdapterInput]:
    property_provider = provider or CoolPropPropertyProvider()
    state = contract["upstream_state_definition"]
    geometry = contract["geometry_and_coefficients"]
    tolerances = contract["acceptance_tolerances"]
    p0 = float(state["pressure_pa"])
    upstream_tsat = property_provider.saturation_temperature(p0)
    base_subcooling = float(state["subcooling_K"])
    return [
        AdapterInput(
            case_id=str(row["case_id"]),
            upstream_pressure_pa=p0,
            upstream_temperature_K=upstream_tsat
            - float(row.get("upstream_subcooling_override_K", base_subcooling)),
            back_pressure_pa=float(row["back_pressure_pa"]),
            reference_area_m2=float(geometry["reference_area_m2"]),
            opening_fraction=float(row["opening_fraction"]),
            discharge_coefficient=float(row["discharge_coefficient"]),
            minimum_downstream_subcooling_margin_K=float(
                tolerances["minimum_downstream_subcooling_margin_K"]
            ),
        )
        for row in contract["benchmark_cases"]
    ]


def evaluate_contract(
    contract: dict[str, Any],
    provider: PropertyProvider | None = None,
) -> list[AdapterResult]:
    property_provider = provider or CoolPropPropertyProvider()
    return [
        evaluate_adapter(row, property_provider)
        for row in build_case_inputs(contract, property_provider)
    ]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def verify_reference_artifact(
    reference_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    summary_path = reference_dir / "summary.json"
    manifest_path = reference_dir / "artifact_sha256.txt"
    contract_path = reference_dir / "benchmark_contract.json"
    cases_path = reference_dir / "benchmark_cases.csv"
    for required in (summary_path, manifest_path, contract_path, cases_path):
        if not required.is_file():
            raise ValueError(f"Missing reference artifact file: {required.name}")
    manifest: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    for name, expected in manifest.items():
        path = reference_dir / name
        if not path.is_file():
            raise ValueError(f"Missing manifest entry: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Reference internal digest mismatch: {name}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise ValueError("Unexpected reference artifact schema")
    if summary.get("u3_b0_reference_implemented") is not True:
        raise ValueError("Reference artifact is not completion-qualified")
    if summary.get("u3_b0_adapter_implemented") is not False:
        raise ValueError("Reference artifact approval boundary changed")
    return summary, _read_csv(cases_path)


def _allowed_error(expected: float, absolute: float, relative: float) -> float:
    return absolute + relative * abs(expected)


def compare_to_reference(
    contract: dict[str, Any],
    adapter_results: list[AdapterResult],
    reference_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    tolerances = contract["acceptance_tolerances"]
    reference_by_case = {row["case_id"]: row for row in reference_rows}
    if set(reference_by_case) != {row.case_id for row in adapter_results}:
        raise ValueError("Reference and adapter case sets differ")

    comparisons: list[dict[str, Any]] = []
    fields = (
        (
            "mass_transfer_outward_kg_s",
            "mass_transfer_rate_outward_kg_s",
            float(tolerances["mass_flow_absolute_kg_s"]),
            float(tolerances["mass_flow_relative"]),
        ),
        (
            "momentum_stream_transfer_outward_N",
            "momentum_stream_transfer_outward_N",
            float(tolerances["momentum_transfer_absolute_N"]),
            float(tolerances["momentum_transfer_relative"]),
        ),
        (
            "energy_transfer_outward_W",
            "energy_transfer_outward_W",
            float(tolerances["energy_transfer_absolute_W"]),
            float(tolerances["energy_transfer_relative"]),
        ),
    )
    for adapter in adapter_results:
        reference = reference_by_case[adapter.case_id]
        outcome_match = adapter.formal_outcome == reference["formal_outcome"]
        for adapter_field, reference_field, absolute, relative in fields:
            actual = float(getattr(adapter, adapter_field))
            expected = float(reference[reference_field])
            error = abs(actual - expected)
            allowed = _allowed_error(expected, absolute, relative)
            comparisons.append(
                {
                    "case_id": adapter.case_id,
                    "formal_outcome_match": outcome_match,
                    "adapter_outcome": adapter.formal_outcome,
                    "reference_outcome": reference["formal_outcome"],
                    "measure": adapter_field,
                    "adapter_value": actual,
                    "reference_value": expected,
                    "absolute_error": error,
                    "allowed_error": allowed,
                    "comparison_passed": outcome_match and error <= allowed,
                }
            )
    return comparisons


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    payload = list(rows)
    if not payload:
        raise ValueError(f"No rows supplied for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(payload[0]))
        writer.writeheader()
        writer.writerows(payload)


def _write_plots(
    output_dir: Path,
    adapter_results: list[AdapterResult],
    reference_rows: list[dict[str, str]],
    comparisons: list[dict[str, Any]],
) -> None:
    import matplotlib.pyplot as plt

    reference_by_case = {row["case_id"]: row for row in reference_rows}
    successes = [
        row
        for row in adapter_results
        if row.formal_outcome == SUCCESS_FORWARD_LIQUID_DISCHARGE
    ]
    fig = plt.figure()
    ax = fig.add_subplot(111)
    x = [
        float(reference_by_case[row.case_id]["mass_flow_rate_kg_s"])
        for row in successes
    ]
    y = [row.mass_transfer_outward_kg_s for row in successes]
    ax.scatter(x, y)
    if x:
        lower = min(x + y)
        upper = max(x + y)
        ax.plot([lower, upper], [lower, upper])
    ax.set_xlabel("Reference mass transfer [kg/s]")
    ax.set_ylabel("Adapter mass transfer [kg/s]")
    ax.set_title("U3 B0 reference versus verification adapter")
    fig.tight_layout()
    fig.savefig(output_dir / "mass_flow_reference_vs_adapter.png", dpi=160)
    plt.close(fig)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.scatter(
        range(len(comparisons)),
        [float(row["absolute_error"]) for row in comparisons],
    )
    ax.set_xlabel("Comparison row")
    ax.set_ylabel("Absolute transfer error")
    ax.set_title("U3 B0 adapter transfer residuals")
    fig.tight_layout()
    fig.savefig(output_dir / "transfer_residuals.png", dpi=160)
    plt.close(fig)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_artifact(
    contract_path: Path,
    reference_dir: Path,
    output_dir: Path,
    *,
    source_git_sha: str,
    reference_artifact_id: int,
    reference_artifact_zip_sha256: str,
    provider: PropertyProvider | None = None,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    reference_summary, reference_rows = verify_reference_artifact(reference_dir)
    reference_contract = json.loads(
        (reference_dir / "benchmark_contract.json").read_text(encoding="utf-8")
    )
    if reference_contract != contract:
        raise ValueError("Local and authoritative reference contracts differ")

    property_provider = provider or CoolPropPropertyProvider()
    adapter_results = evaluate_contract(contract, property_provider)
    expected_outcomes = {
        str(row["case_id"]): str(row["expected_outcome"])
        for row in contract["benchmark_cases"]
    }
    for result in adapter_results:
        if result.formal_outcome != expected_outcomes[result.case_id]:
            raise RuntimeError(
                f"{result.case_id}: {result.formal_outcome} != "
                f"{expected_outcomes[result.case_id]}"
            )
    comparisons = compare_to_reference(contract, adapter_results, reference_rows)
    all_comparisons_passed = all(
        bool(row["comparison_passed"]) for row in comparisons
    )
    if not all_comparisons_passed:
        raise RuntimeError("One or more reference/adapter comparisons failed")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "benchmark_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_csv(
        output_dir / "adapter_cases.csv", [asdict(row) for row in adapter_results]
    )
    _write_csv(output_dir / "reference_adapter_comparison.csv", comparisons)
    _write_csv(
        output_dir / "guard_outcomes.csv",
        [
            {
                "case_id": row.case_id,
                "formal_outcome": row.formal_outcome,
                "formal_message": row.formal_message,
            }
            for row in adapter_results
            if not row.succeeded
        ],
    )
    _write_csv(output_dir / "conservative_transfer_comparison.csv", comparisons)
    _write_plots(output_dir, adapter_results, reference_rows, comparisons)

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": "verification_only_component_adapter_comparison",
        "issue": 109,
        "contract_schema_version": contract["schema_version"],
        "reference_schema_version": reference_summary["schema_version"],
        "reference_artifact_id": int(reference_artifact_id),
        "reference_artifact_zip_sha256": reference_artifact_zip_sha256,
        "reference_source_git_sha": reference_summary["provenance"][
            "source_git_sha"
        ],
        "case_count": len(adapter_results),
        "success_count": sum(row.succeeded for row in adapter_results),
        "guard_count": sum(not row.succeeded for row in adapter_results),
        "comparison_count": len(comparisons),
        "comparison_pass_count": sum(
            bool(row["comparison_passed"]) for row in comparisons
        ),
        "all_formal_outcomes_match": all(
            bool(row["formal_outcome_match"]) for row in comparisons
        ),
        "all_transfer_comparisons_passed": all_comparisons_passed,
        "exact_zero_identities_retained": all(
            row.mass_transfer_outward_kg_s == 0.0
            and row.momentum_stream_transfer_outward_N == 0.0
            and row.energy_transfer_outward_W == 0.0
            for row in adapter_results
            if row.formal_outcome in {SUCCESS_CLOSED, SUCCESS_ZERO_PRESSURE_DROP}
        ),
        "static_pressure_force_included": False,
        "production_fvm_connected": False,
        "u3_b0_contract_locked": True,
        "u3_b0_reference_implemented": True,
        "u3_b0_adapter_implemented": True,
        "u3_b0_component_benchmark_execution_complete": True,
        "u3_component_benchmark_accepted": True,
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
            "property_backend": "CoolProp",
            "property_backend_version": property_provider.version,
            "tracked_git_status": "",
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = [
        "# U3 B0 Verification Adapter Comparison",
        "",
        "The verification-only adapter was compared against the immutable "
        "independent reference artifact.",
        "No reference helper is imported by the adapter implementation.",
        "",
        "## Result",
        "",
        f"- cases: {len(adapter_results)}",
        f"- transfer comparisons: {len(comparisons)}",
        f"- passed: {sum(bool(row['comparison_passed']) for row in comparisons)}",
        "- formal outcomes: all matched",
        "- exact-zero identities: retained",
        "",
        "## Boundary",
        "",
        "```text",
        "u3_b0_reference_implemented = true",
        "u3_b0_adapter_implemented = true",
        "u3_b0_component_benchmark_execution_complete = true",
        "u3_component_benchmark_accepted = true",
        "physical_discharge_boundary_approved = false",
        "two_phase_critical_discharge_accuracy_approved = false",
        "integrated_blowdown_model_approved = false",
        "physical_validation = false",
        "design_use_acceptance = false",
        "production_hem_activation_approved = false",
        "```",
        "",
    ]
    (output_dir / "report.md").write_text("\n".join(report), encoding="utf-8")
    names = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.name != "artifact_sha256.txt"
    )
    (output_dir / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output_dir / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--reference-artifact-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-artifact-id", type=int, required=True)
    parser.add_argument("--reference-artifact-zip-sha256", required=True)
    parser.add_argument(
        "--source-git-sha",
        default=os.environ.get("ANALYSIS_SOURCE_GIT_SHA", "UNKNOWN"),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    write_artifact(
        args.contract,
        args.reference_artifact_dir,
        args.output_dir,
        source_git_sha=str(args.source_git_sha),
        reference_artifact_id=int(args.reference_artifact_id),
        reference_artifact_zip_sha256=str(
            args.reference_artifact_zip_sha256
        ),
    )


if __name__ == "__main__":
    main()
