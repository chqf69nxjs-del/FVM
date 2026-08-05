from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import liquid_gas_transient.u3_b1_critical_state_authoritative as authoritative
from liquid_gas_transient.u3_b1_critical_state_authoritative import critical_search
from liquid_gas_transient.u3_b1_critical_state_reference import (
    CandidateState,
    UpstreamState,
    load_contract,
)

CONTRACT = Path("docs/verification/stage7_u3_b1_critical_state_contract_v1.json")


class RatioOffsetProvider:
    """Analytic path whose peak distinguishes the two offset interpretations."""

    version = "analytic-ratio-offset"

    def saturation_temperature(self, pressure_pa: float) -> float:
        return 300.0

    def upstream_snapshot(
        self, pressure_pa: float, temperature_K: float
    ) -> UpstreamState:
        return UpstreamState(
            pressure_pa=pressure_pa,
            temperature_K=temperature_K,
            density_kg_m3=1.0,
            enthalpy_J_kg=1.0,
            entropy_J_kg_K=1.0,
            phase="gas",
        )

    def isentropic_candidate(
        self, pressure_pa: float, entropy_J_kg_K: float
    ) -> CandidateState:
        ratio = pressure_pa / 1.0e6
        peak_ratio = 2.0 / 3.0
        density = 1.0 - 1.2 * (ratio - peak_ratio) ** 2
        return CandidateState(
            pressure_pa=pressure_pa,
            temperature_K=300.0,
            density_kg_m3=density,
            enthalpy_J_kg=0.5,
            entropy_J_kg_K=entropy_J_kg_K,
            phase="gas",
        )


def test_peak_neighbor_offset_is_measured_in_upstream_pressure_ratio() -> None:
    contract = load_contract(CONTRACT)
    provider = RatioOffsetProvider()
    upstream = provider.upstream_snapshot(1.0e6, 320.0)

    critical, records, outcome, message = critical_search(
        contract,
        provider,
        upstream,
        {"gas"},
        0.8,
    )

    assert outcome is None, message
    assert critical is not None
    assert critical.pressure_ratio == pytest.approx(2.0 / 3.0, abs=5e-5)
    assert critical.peak_prominence_relative >= 1e-8
    assert len(records) == 4097


import pytest


def test_locked_check_fail_safe_retains_b0_and_check_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_locked_checks(*args: object, **kwargs: object) -> object:
        raise ZeroDivisionError("synthetic zero denominator")

    monkeypatch.setattr(
        authoritative,
        "_ORIGINAL_LOCKED_CHECKS",
        fail_locked_checks,
    )
    contract = {
        "benchmark_cases": [
            {"case_id": "unit", "expected_outcome": "SUCCESS_UNIT"}
        ]
    }
    results = [SimpleNamespace(case_id="unit", formal_outcome="SUCCESS_UNIT")]

    rows, summary = authoritative.locked_checks_fail_safe(contract, results)

    assert any(row.get("measure") for row in rows)
    assert any(row.get("check") for row in rows)
    assert all(row["passed"] is False for row in rows)
    assert summary["all_expected_outcomes_match"] is True
    assert summary["all_locked_checks_passed"] is False
