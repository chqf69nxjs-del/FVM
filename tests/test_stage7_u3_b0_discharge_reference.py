from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import pytest

from liquid_gas_transient.u3_b0_discharge_reference import (
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
    ReferenceInput,
    build_case_inputs,
    evaluate_contract,
    evaluate_reference,
    load_contract,
    write_artifact,
)

CONTRACT = Path("docs/verification/stage7_u3_b0_discharge_boundary_contract_v1.json")


def _base_input(**overrides: float | str) -> ReferenceInput:
    values: dict[str, float | str] = {
        "case_id": "unit",
        "upstream_pressure_pa": 5.0e6,
        "upstream_temperature_K": 282.0,
        "back_pressure_pa": 4.95e6,
        "reference_area_m2": 1.0e-4,
        "opening_fraction": 0.5,
        "discharge_coefficient": 0.8,
        "minimum_downstream_subcooling_margin_K": 0.5,
    }
    values.update(overrides)
    return ReferenceInput(**values)  # type: ignore[arg-type]


@pytest.mark.coolprop_installed
def test_locked_contract_builds_expected_case_matrix() -> None:
    contract = load_contract(CONTRACT)
    inputs = build_case_inputs(contract)
    assert len(inputs) == 10
    assert [row.case_id for row in inputs] == [
        "B0-01_CLOSED_ELEMENT",
        "B0-02_ZERO_PRESSURE_DROP",
        "B0-03_SUBCOOLED_LIQUID_LIMIT",
        "B0-04A_AREA_SCALING_LOW",
        "B0-04B_AREA_SCALING_HIGH",
        "B0-05A_CD_SCALING_LOW",
        "B0-05B_CD_SCALING_HIGH",
        "G-01_REVERSE_PRESSURE",
        "G-02_OPENING_OUTSIDE_RANGE",
        "G-03_SINGLE_PHASE_SCOPE_FAILURE",
    ]


@pytest.mark.coolprop_installed
def test_locked_matrix_outcomes_and_exact_zero_identities() -> None:
    contract = load_contract(CONTRACT)
    results = {row.case_id: row for row in evaluate_contract(contract)}
    expected = {
        str(row["case_id"]): str(row["expected_outcome"])
        for row in contract["benchmark_cases"]
    }
    assert {case: row.formal_outcome for case, row in results.items()} == expected

    for case_id in ("B0-01_CLOSED_ELEMENT", "B0-02_ZERO_PRESSURE_DROP"):
        row = results[case_id]
        assert row.mass_flow_rate_kg_s == 0.0
        assert row.exit_velocity_m_s == 0.0
        assert row.mass_transfer_rate_outward_kg_s == 0.0
        assert row.momentum_stream_transfer_outward_N == 0.0
        assert row.energy_transfer_outward_W == 0.0


@pytest.mark.coolprop_installed
def test_reference_formula_area_and_cd_scaling() -> None:
    results = {
        row.case_id: row for row in evaluate_contract(load_contract(CONTRACT))
    }
    base = results["B0-03_SUBCOOLED_LIQUID_LIMIT"]
    assert base.formal_outcome == SUCCESS_FORWARD_LIQUID_DISCHARGE
    assert base.upstream_density_kg_m3 is not None
    expected = (
        base.discharge_coefficient
        * base.effective_area_m2
        * math.sqrt(
            2.0 * base.upstream_density_kg_m3 * base.delta_p_pa
        )
    )
    assert base.mass_flow_rate_kg_s == pytest.approx(expected, rel=1e-15, abs=0.0)
    assert base.energy_transfer_outward_W == pytest.approx(
        base.mass_flow_rate_kg_s * base.upstream_enthalpy_J_kg, rel=1e-15
    )
    assert base.momentum_stream_transfer_outward_N == pytest.approx(
        base.mass_flow_rate_kg_s * base.exit_velocity_m_s, rel=1e-15
    )

    area_ratio = (
        results["B0-04B_AREA_SCALING_HIGH"].mass_flow_rate_kg_s
        / results["B0-04A_AREA_SCALING_LOW"].mass_flow_rate_kg_s
    )
    cd_ratio = (
        results["B0-05B_CD_SCALING_HIGH"].mass_flow_rate_kg_s
        / results["B0-05A_CD_SCALING_LOW"].mass_flow_rate_kg_s
    )
    assert area_ratio == pytest.approx(2.0, abs=1e-12)
    assert cd_ratio == pytest.approx(2.0, abs=1e-12)


def test_input_guards_are_explicit_before_property_evaluation() -> None:
    assert evaluate_reference(
        _base_input(upstream_pressure_pa=math.nan)
    ).formal_outcome == NONFINITE_INPUT
    assert evaluate_reference(
        _base_input(reference_area_m2=0.0)
    ).formal_outcome == NONPOSITIVE_REFERENCE_AREA
    assert evaluate_reference(
        _base_input(opening_fraction=1.1)
    ).formal_outcome == OPENING_OUTSIDE_UNIT_INTERVAL
    assert evaluate_reference(
        _base_input(discharge_coefficient=0.0)
    ).formal_outcome == NONPOSITIVE_DISCHARGE_COEFFICIENT
    assert evaluate_reference(
        _base_input(back_pressure_pa=5.1e6)
    ).formal_outcome == REVERSE_PRESSURE_NOT_SUPPORTED


@pytest.mark.coolprop_installed
def test_phase_scope_guards_are_explicit() -> None:
    contract = load_contract(CONTRACT)
    inputs = build_case_inputs(contract)
    scope_failure = next(
        row for row in inputs if row.case_id == "G-03_SINGLE_PHASE_SCOPE_FAILURE"
    )
    assert (
        evaluate_reference(scope_failure).formal_outcome
        == UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE
    )

    base = next(
        row for row in inputs if row.case_id == "B0-03_SUBCOOLED_LIQUID_LIMIT"
    )
    downstream_failure = ReferenceInput(
        **{
            **base.__dict__,
            "case_id": "downstream-scope",
            "minimum_downstream_subcooling_margin_K": 100.0,
        }
    )
    assert (
        evaluate_reference(downstream_failure).formal_outcome
        == DOWNSTREAM_LIQUID_SCOPE_FAILURE
    )


@pytest.mark.coolprop_installed
def test_artifact_contract_and_internal_digest(tmp_path: Path) -> None:
    output = tmp_path / "artifact"
    summary = write_artifact(CONTRACT, output, source_git_sha="test-sha")
    expected_files = {
        "summary.json",
        "benchmark_contract.json",
        "benchmark_cases.csv",
        "property_scope_history.csv",
        "conservative_flux_budget.csv",
        "guard_outcomes.csv",
        "report.md",
        "mass_flow_vs_pressure_drop.png",
        "area_and_Cd_scaling.png",
        "energy_transfer_residual.png",
        "artifact_sha256.txt",
    }
    assert {path.name for path in output.iterdir()} == expected_files
    assert summary["case_count"] == 10
    assert summary["success_count"] == 7
    assert summary["guard_count"] == 3
    assert summary["exact_zero_identities_retained"] is True
    assert summary["u3_b0_contract_locked"] is True
    assert summary["u3_b0_reference_implemented"] is True
    assert summary["u3_b0_adapter_implemented"] is False
    assert summary["u3_b0_component_benchmark_execution_complete"] is False
    assert summary["physical_discharge_boundary_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False
    assert summary["production_hem_activation_approved"] is False
    assert summary["provenance"]["source_git_sha"] == "test-sha"

    with (output / "benchmark_cases.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 10

    manifest = {}
    for line in (output / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    assert set(manifest) == expected_files - {"artifact_sha256.txt"}
    for name, expected_digest in manifest.items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected_digest

    saved_summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert saved_summary == summary
