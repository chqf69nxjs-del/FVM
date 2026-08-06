from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

import pytest

from liquid_gas_transient.u3_b1_critical_state_adapter import (
    CRITICAL_SEARCH_NOT_BRACKETED,
    NONFINITE_INPUT,
    NONPOSITIVE_KINETIC_ENERGY_HEAD,
    SUCCESS_CHOKED,
    SUCCESS_CLOSED,
    SUCCESS_UNCHOKED,
    SUCCESS_ZERO_PRESSURE_DROP,
    UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE,
    AdapterInput,
    ThermodynamicState,
    compare_to_reference,
    evaluate_contract,
    evaluate_case,
    golden_section_refine,
    load_contract,
    normalize_phase,
    search_critical_state,
    verify_reference_artifact,
    write_artifact,
)

from liquid_gas_transient.u3_b1_critical_state_adapter import (
    CoolPropStateProvider,
    plot_provenance_text,
)

CONTRACT = Path("docs/verification/stage7_u3_b1_critical_state_contract_v1.json")


class AnalyticProvider:
    version = "analytic"

    def saturation_temperature(self, pressure_pa: float) -> float:
        return 300.0

    def upstream_state(
        self, pressure_pa: float, temperature_K: float
    ) -> ThermodynamicState:
        if pressure_pa == 1.0e6:
            return ThermodynamicState(
                pressure_pa, temperature_K, 1.0, 1.0, 1.0, "gas"
            )
        return ThermodynamicState(
            pressure_pa,
            temperature_K,
            10.0,
            100000.0,
            2.0,
            "liquid" if temperature_K < 300.0 else "gas",
        )

    def isentropic_state(
        self, pressure_pa: float, entropy_J_kg_K: float
    ) -> ThermodynamicState:
        if entropy_J_kg_K == 1.0:
            ratio = pressure_pa / 1.0e6
            return ThermodynamicState(
                pressure_pa,
                250.0 + 70.0 * ratio,
                ratio,
                ratio,
                1.0,
                "gas",
            )
        delta_p = 5.0e6 - pressure_pa
        return ThermodynamicState(
            pressure_pa,
            295.0,
            10.0,
            100000.0 - delta_p / 10.0,
            2.0,
            "liquid",
        )


def test_contract_and_phase_normalization() -> None:
    contract = load_contract(CONTRACT)
    assert contract["approval_boundary"]["u3_b1_contract_locked"] is True
    assert normalize_phase("supercritical_gas") == "supercriticalgas"
    assert normalize_phase("Two Phase") == "twophase"


def test_golden_refinement_is_deterministic() -> None:
    result = golden_section_refine(
        lambda x: -(x - 3.0) ** 2 + 7.0,
        0.0,
        8.0,
        1e-8,
        128,
    )
    assert result.best_pressure_pa == pytest.approx(3.0, abs=1e-6)
    assert result.bracket_high_pa - result.bracket_low_pa <= 1e-8
    assert result.iterations > 0


def test_independent_critical_search_uses_pressure_ratio_offset() -> None:
    contract = load_contract(CONTRACT)
    contract = {
        **contract,
        "critical_state_search": {
            **contract["critical_state_search"],
            "minimum_peak_prominence_relative": 2.0e-8,
        },
    }
    provider = AnalyticProvider()
    upstream = provider.upstream_state(1.0e6, 320.0)
    critical, records, outcome, message = search_critical_state(
        contract, provider, upstream, {"gas"}, 0.8
    )
    assert outcome is None, message
    assert critical is not None
    assert critical.pressure_ratio == pytest.approx(2.0 / 3.0, abs=5e-5)
    assert critical.peak_prominence_relative >= 2.0e-8
    assert 0 < critical.coarse_index < len(records) - 1


def test_exact_zero_and_liquid_limit_transfer() -> None:
    contract = load_contract(CONTRACT)
    provider = AnalyticProvider()
    cases = {row["case_id"]: row for row in contract["benchmark_cases"]}
    cache = {}
    records: list[dict[str, object]] = []
    closed = evaluate_case(
        contract,
        provider,
        cases["B1-01_CLOSED_ELEMENT"],
        critical_cache=cache,
        critical_records=records,
    )
    zero = evaluate_case(
        contract,
        provider,
        cases["B1-02_ZERO_PRESSURE_DROP"],
        critical_cache=cache,
        critical_records=records,
    )
    flow = evaluate_case(
        contract,
        provider,
        cases["B1-03_SMALL_DROP_RECOVERS_B0_LIMIT"],
        critical_cache=cache,
        critical_records=records,
    )
    assert closed.formal_outcome == SUCCESS_CLOSED
    assert zero.formal_outcome == SUCCESS_ZERO_PRESSURE_DROP
    assert flow.formal_outcome == SUCCESS_UNCHOKED
    assert flow.mass_transfer_outward_kg_s > 0.0
    assert flow.momentum_stream_transfer_outward_N > 0.0
    assert flow.energy_transfer_outward_W > 0.0
    for row in (closed, zero):
        assert row.mass_transfer_outward_kg_s == 0.0
        assert row.momentum_stream_transfer_outward_N == 0.0
        assert row.energy_transfer_outward_W == 0.0


def test_critical_classification_and_guards() -> None:
    contract = load_contract(CONTRACT)
    provider = AnalyticProvider()
    cases = {row["case_id"]: row for row in contract["benchmark_cases"]}
    cache = {}
    records: list[dict[str, object]] = []
    choked = evaluate_case(
        contract,
        provider,
        cases["B1-05_CRITICAL_STATE_SEARCH"],
        critical_cache=cache,
        critical_records=records,
    )
    nonfinite = evaluate_case(
        contract,
        provider,
        cases["G-02_NONFINITE_INPUT"],
        critical_cache=cache,
        critical_records=records,
    )
    phase = evaluate_case(
        contract,
        provider,
        cases["G-03_SINGLE_PHASE_SCOPE_FAILURE"],
        critical_cache=cache,
        critical_records=records,
    )
    kinetic = evaluate_case(
        contract,
        provider,
        cases["G-04_NONPOSITIVE_KINETIC_ENERGY_HEAD"],
        critical_cache=cache,
        critical_records=records,
    )
    bracket = evaluate_case(
        contract,
        provider,
        cases["G-05_CRITICAL_SEARCH_NOT_BRACKETED"],
        critical_cache=cache,
        critical_records=records,
    )
    assert choked.formal_outcome == SUCCESS_CHOKED
    assert choked.critical_pressure_pa is not None
    assert nonfinite.formal_outcome == NONFINITE_INPUT
    assert phase.formal_outcome == UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE
    assert kinetic.formal_outcome == NONPOSITIVE_KINETIC_ENERGY_HEAD
    assert bracket.formal_outcome == CRITICAL_SEARCH_NOT_BRACKETED


def test_comparison_contract_accepts_exact_synthetic_rows() -> None:
    contract = load_contract(CONTRACT)
    provider = AnalyticProvider()
    cases = {row["case_id"]: row for row in contract["benchmark_cases"]}
    cache = {}
    records: list[dict[str, object]] = []
    result = evaluate_case(
        contract,
        provider,
        cases["B1-03_SMALL_DROP_RECOVERS_B0_LIMIT"],
        critical_cache=cache,
        critical_records=records,
    )
    reference = [
        {
            "case_id": result.case_id,
            "formal_outcome": result.formal_outcome,
            "effective_mass_flux_kg_m2_s": str(result.effective_mass_flux_kg_m2_s),
            "mass_transfer_outward_kg_s": str(result.mass_transfer_outward_kg_s),
            "momentum_stream_transfer_outward_N": str(
                result.momentum_stream_transfer_outward_N
            ),
            "energy_transfer_outward_W": str(result.energy_transfer_outward_W),
            "critical_pressure_pa": "",
        }
    ]
    comparisons = compare_to_reference(contract, [result], reference)
    assert len(comparisons) == 4
    assert all(row["comparison_passed"] for row in comparisons)


def test_adapter_source_does_not_import_reference_module() -> None:
    module_path = Path(
        "src/liquid_gas_transient/u3_b1_critical_state_adapter.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert "import liquid_gas_transient.u3_b1_critical_state_reference" not in source
    assert "from liquid_gas_transient.u3_b1_critical_state_reference" not in source


@pytest.mark.u3_b1_reference_artifact
@pytest.mark.coolprop_installed
def test_locked_matrix_matches_authoritative_reference() -> None:
    reference_dir_text = os.environ.get("U3_B1_REFERENCE_ARTIFACT_DIR")
    if not reference_dir_text:
        pytest.skip("authoritative U3 B1 reference artifact is not configured")
    contract = load_contract(CONTRACT)
    adapter_results, criticals, _ = evaluate_contract(contract)
    _, reference_rows, reference_critical = verify_reference_artifact(
        Path(reference_dir_text)
    )
    comparisons = compare_to_reference(contract, adapter_results, reference_rows)
    assert len(adapter_results) == 17
    assert len(criticals) == 2
    assert set(reference_critical) == {"GAS_CRITICAL|Cd=0.4", "GAS_CRITICAL|Cd=0.8"}
    assert len(comparisons) == 77
    assert all(row["formal_outcome_match"] for row in comparisons)
    assert all(row["comparison_passed"] for row in comparisons)


@pytest.mark.u3_b1_reference_artifact
@pytest.mark.coolprop_installed
def test_adapter_comparison_artifact_contract(tmp_path: Path) -> None:
    reference_dir_text = os.environ.get("U3_B1_REFERENCE_ARTIFACT_DIR")
    if not reference_dir_text:
        pytest.skip("authoritative U3 B1 reference artifact is not configured")
    output = tmp_path / "artifact"
    artifact_id = int(os.environ.get("REFERENCE_ARTIFACT_ID", "0"))
    artifact_sha = os.environ.get("REFERENCE_ARTIFACT_ZIP_SHA256", "test-sha")
    summary = write_artifact(
        CONTRACT,
        Path(reference_dir_text),
        output,
        source_git_sha="test-sha",
        reference_artifact_id=artifact_id,
        reference_artifact_zip_sha256=artifact_sha,
        reference_resolution_mode="recomputed_from_pinned_source_sha",
        reference_source_git_sha="test-sha",
    )
    expected_files = {
        "summary.json",
        "benchmark_contract.json",
        "adapter_cases.csv",
        "reference_adapter_comparison.csv",
        "locked_checks.csv",
        "guard_outcomes.csv",
        "conservative_transfer_comparison.csv",
        "critical_state_summary.json",
        "report.md",
        "mass_flux_reference_vs_adapter.png",
        "critical_pressure_reference_vs_adapter.png",
        "reference_adapter_residuals.png",
        "artifact_sha256.txt",
    }
    assert {path.name for path in output.iterdir()} == expected_files
    assert summary["case_count"] == 17
    assert summary["success_count"] == 12
    assert summary["guard_count"] == 5
    assert summary["comparison_count"] == 77
    assert summary["comparison_pass_count"] == 77
    assert summary["reference_resolution_mode"] == "recomputed_from_pinned_source_sha"
    assert summary["reference_source_git_sha"] == "test-sha"
    assert summary["reference_artifact_provenance_role"] == "historical_authoritative_evidence"
    assert summary["all_formal_outcomes_match"] is True
    assert summary["all_reference_adapter_comparisons_passed"] is True
    assert summary["all_locked_adapter_checks_passed"] is True
    assert summary["u3_b1_reference_implemented"] is True
    assert summary["u3_b1_adapter_implemented"] is True
    assert summary["u3_b1_component_benchmark_execution_complete"] is True
    assert summary["u3_b1_component_benchmark_accepted"] is True
    assert summary["physical_discharge_boundary_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False
    assert summary["production_hem_activation_approved"] is False

    with (output / "reference_adapter_comparison.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 77
    assert all(row["formal_outcome_match"] == "True" for row in rows)
    assert all(row["comparison_passed"] == "True" for row in rows)

    report = (output / "report.md").read_text(encoding="utf-8")
    assert "property backend: CoolProp analytic" in report
    assert "reference resolution: recomputed_from_pinned_source_sha" in report
    assert "pinned reference source SHA: test-sha" in report

    saved = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert saved == summary


class FakeCandidateAbstractState:
    def __init__(self) -> None:
        self.updates: list[tuple[object, ...]] = []

    def update(self, *args: object) -> None:
        self.updates.append(args)

    def T(self) -> float:
        return 280.0

    def rhomass(self) -> float:
        return 12.0

    def hmass(self) -> float:
        return 190000.0

    def smass(self) -> float:
        return 1000.0


def test_adapter_candidate_phase_uses_pressure_entropy_coordinates() -> None:
    provider = object.__new__(CoolPropStateProvider)
    candidate_state = FakeCandidateAbstractState()
    phase_calls: list[tuple[object, ...]] = []
    provider._candidate = candidate_state
    provider._PSmass_INPUTS = "PSMASS_INPUT"
    provider._phase_si = lambda *args: phase_calls.append(args) or "gas"

    candidate = provider.isentropic_state(8.0e5, 1000.0)

    assert candidate.phase == "gas"
    assert candidate_state.updates == [("PSMASS_INPUT", 8.0e5, 1000.0)]
    assert phase_calls == [("P", 8.0e5, "SMASS", 1000.0, "CO2")]


def test_adapter_plot_provenance_contains_required_fields() -> None:
    text = plot_provenance_text(
        "77-row comparison matrix",
        "8.0.0",
        "0123456789abcdef",
    )
    assert "case=77-row comparison matrix" in text
    assert "model=U3 B1 verification adapter comparison" in text
    assert "backend=CoolProp" in text
    assert "version=8.0.0" in text
    assert "source=0123456789ab" in text
