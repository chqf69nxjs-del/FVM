from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

import pytest

from liquid_gas_transient.u3_b0_discharge_adapter import (
    DOWNSTREAM_LIQUID_SCOPE_FAILURE,
    NONFINITE_INPUT,
    NONPOSITIVE_DISCHARGE_COEFFICIENT,
    NONPOSITIVE_REFERENCE_AREA,
    OPENING_OUTSIDE_UNIT_INTERVAL,
    REVERSE_PRESSURE_NOT_SUPPORTED,
    SUCCESS_CLOSED,
    SUCCESS_FORWARD_LIQUID_DISCHARGE,
    SUCCESS_ZERO_PRESSURE_DROP,
    UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE,
    AdapterInput,
    PropertySnapshot,
    compare_to_reference,
    evaluate_adapter,
    evaluate_contract,
    load_contract,
    verify_reference_artifact,
    write_artifact,
)

CONTRACT = Path("docs/verification/stage7_u3_b0_discharge_boundary_contract_v1.json")


class FakeProvider:
    version = "fake"

    def __init__(
        self,
        *,
        phase: str = "liquid",
        upstream_tsat: float = 300.0,
        downstream_tsat: float = 299.0,
    ) -> None:
        self.phase = phase
        self.upstream_tsat = upstream_tsat
        self.downstream_tsat = downstream_tsat

    def saturation_temperature(self, pressure_pa: float) -> float:
        return self.upstream_tsat

    def snapshot(
        self,
        upstream_pressure_pa: float,
        upstream_temperature_K: float,
        back_pressure_pa: float,
    ) -> PropertySnapshot:
        return PropertySnapshot(
            density_kg_m3=800.0,
            enthalpy_J_kg=200000.0,
            entropy_J_kg_K=1000.0,
            phase=self.phase,
            upstream_saturation_temperature_K=self.upstream_tsat,
            downstream_saturation_temperature_K=self.downstream_tsat,
        )


def _base(**overrides: float | str) -> AdapterInput:
    values: dict[str, float | str] = {
        "case_id": "unit",
        "upstream_pressure_pa": 5.0e6,
        "upstream_temperature_K": 295.0,
        "back_pressure_pa": 4.95e6,
        "reference_area_m2": 1.0e-4,
        "opening_fraction": 0.5,
        "discharge_coefficient": 0.8,
        "minimum_downstream_subcooling_margin_K": 0.5,
    }
    values.update(overrides)
    return AdapterInput(**values)  # type: ignore[arg-type]


def test_adapter_formula_is_independent_and_outward_positive() -> None:
    result = evaluate_adapter(_base(), FakeProvider())
    expected_velocity = 0.8 * math.sqrt(2.0 * 50000.0 / 800.0)
    expected_mass = 800.0 * 5.0e-5 * expected_velocity
    assert result.formal_outcome == SUCCESS_FORWARD_LIQUID_DISCHARGE
    assert result.exit_velocity_m_s == pytest.approx(expected_velocity)
    assert result.mass_transfer_outward_kg_s == pytest.approx(expected_mass)
    assert result.momentum_stream_transfer_outward_N == pytest.approx(
        expected_mass * expected_velocity
    )
    assert result.energy_transfer_outward_W == pytest.approx(
        expected_mass * 200000.0
    )
    assert result.static_pressure_force_included is False
    assert result.production_fvm_connected is False


def test_exact_zero_identities() -> None:
    closed = evaluate_adapter(_base(opening_fraction=0.0), FakeProvider())
    zero_dp = evaluate_adapter(_base(back_pressure_pa=5.0e6), FakeProvider())
    assert closed.formal_outcome == SUCCESS_CLOSED
    assert zero_dp.formal_outcome == SUCCESS_ZERO_PRESSURE_DROP
    for row in (closed, zero_dp):
        assert row.mass_transfer_outward_kg_s == 0.0
        assert row.momentum_stream_transfer_outward_N == 0.0
        assert row.energy_transfer_outward_W == 0.0


def test_input_guards_precede_property_access() -> None:
    assert (
        evaluate_adapter(
            _base(upstream_pressure_pa=math.nan), FakeProvider()
        ).formal_outcome
        == NONFINITE_INPUT
    )
    assert (
        evaluate_adapter(
            _base(reference_area_m2=0.0), FakeProvider()
        ).formal_outcome
        == NONPOSITIVE_REFERENCE_AREA
    )
    assert (
        evaluate_adapter(
            _base(opening_fraction=1.1), FakeProvider()
        ).formal_outcome
        == OPENING_OUTSIDE_UNIT_INTERVAL
    )
    assert (
        evaluate_adapter(
            _base(discharge_coefficient=0.0), FakeProvider()
        ).formal_outcome
        == NONPOSITIVE_DISCHARGE_COEFFICIENT
    )
    assert (
        evaluate_adapter(
            _base(back_pressure_pa=5.1e6), FakeProvider()
        ).formal_outcome
        == REVERSE_PRESSURE_NOT_SUPPORTED
    )


def test_scope_guards_are_explicit() -> None:
    gas = evaluate_adapter(_base(), FakeProvider(phase="gas"))
    downstream = evaluate_adapter(_base(), FakeProvider(downstream_tsat=295.2))
    assert gas.formal_outcome == UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE
    assert downstream.formal_outcome == DOWNSTREAM_LIQUID_SCOPE_FAILURE


def test_comparison_tolerance_and_formal_outcome_contract() -> None:
    contract = load_contract(CONTRACT)
    result = evaluate_adapter(_base(case_id="B0-03"), FakeProvider())
    reference = [
        {
            "case_id": "B0-03",
            "formal_outcome": result.formal_outcome,
            "mass_transfer_rate_outward_kg_s": str(
                result.mass_transfer_outward_kg_s
            ),
            "momentum_stream_transfer_outward_N": str(
                result.momentum_stream_transfer_outward_N
            ),
            "energy_transfer_outward_W": str(
                result.energy_transfer_outward_W
            ),
        }
    ]
    rows = compare_to_reference(contract, [result], reference)
    assert len(rows) == 3
    assert all(row["comparison_passed"] for row in rows)


@pytest.mark.u3_b0_reference_artifact
@pytest.mark.coolprop_installed
def test_locked_matrix_matches_authoritative_reference() -> None:
    reference_dir_text = os.environ.get("U3_B0_REFERENCE_ARTIFACT_DIR")
    if not reference_dir_text:
        pytest.skip("authoritative reference artifact is not configured")
    reference_dir = Path(reference_dir_text)
    contract = load_contract(CONTRACT)
    adapter = evaluate_contract(contract)
    _, reference_rows = verify_reference_artifact(reference_dir)
    comparisons = compare_to_reference(contract, adapter, reference_rows)
    assert len(adapter) == 10
    assert len(comparisons) == 30
    assert all(row["comparison_passed"] for row in comparisons)


@pytest.mark.u3_b0_reference_artifact
@pytest.mark.coolprop_installed
def test_comparison_artifact_contract(tmp_path: Path) -> None:
    reference_dir_text = os.environ.get("U3_B0_REFERENCE_ARTIFACT_DIR")
    if not reference_dir_text:
        pytest.skip("authoritative reference artifact is not configured")
    output = tmp_path / "artifact"
    summary = write_artifact(
        CONTRACT,
        Path(reference_dir_text),
        output,
        source_git_sha="test-sha",
        reference_artifact_id=8890056064,
        reference_artifact_zip_sha256=(
            "7005055beb8b0722dd035f37c0fa6d10f46ddd121d6ead5906a8d941fb6c23a6"
        ),
    )
    expected_files = {
        "summary.json",
        "benchmark_contract.json",
        "adapter_cases.csv",
        "reference_adapter_comparison.csv",
        "guard_outcomes.csv",
        "conservative_transfer_comparison.csv",
        "report.md",
        "mass_flow_reference_vs_adapter.png",
        "transfer_residuals.png",
        "artifact_sha256.txt",
    }
    assert {path.name for path in output.iterdir()} == expected_files
    assert summary["case_count"] == 10
    assert summary["comparison_count"] == 30
    assert summary["comparison_pass_count"] == 30
    assert summary["all_formal_outcomes_match"] is True
    assert summary["all_transfer_comparisons_passed"] is True
    assert summary["exact_zero_identities_retained"] is True
    assert summary["u3_b0_reference_implemented"] is True
    assert summary["u3_b0_adapter_implemented"] is True
    assert summary["u3_b0_component_benchmark_execution_complete"] is True
    assert summary["u3_component_benchmark_accepted"] is True
    assert summary["physical_discharge_boundary_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False
    assert summary["production_hem_activation_approved"] is False

    with (output / "reference_adapter_comparison.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    assert all(row["comparison_passed"] == "True" for row in rows)

    saved = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert saved == summary
