from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from liquid_gas_transient.hne_finite_relaxation_dispersion import (
    DIMENSIONLESS_WAVENUMBERS,
    FORMAL_OUTCOME,
    FORMAL_STATUS,
    HNEFiniteRelaxationDispersionError,
    NEXT_ACTION,
    OMEGA_TAU_VALUES,
    OUTPUT_FILES,
    SCHEMA_VERSION,
    SOLVER_AUTHORITY,
    analyze_finite_relaxation_dispersion,
    dynamic_sound_speed_squared,
    execute,
    source_limit_pairs,
    spatial_dispersion_point,
    temporal_stability_point,
)

C_EQ2 = 15429.604745365119
C_FROZEN2 = 20175.699628193724


def test_a2_4_4_contract_and_maturity_boundary() -> None:
    assert SCHEMA_VERSION == "stage7_p2_hne_finite_relaxation_dispersion_a2_4_4_v1"
    assert len(OUTPUT_FILES) == 6
    assert all(value is False for value in SOLVER_AUTHORITY.values())
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["working_verification_slice"] is True
    assert FORMAL_STATUS["finite_relaxation_dispersion_investigation"] is True
    assert FORMAL_STATUS["spatial_dispersion_evidence_ready"] is True
    assert FORMAL_STATUS["temporal_stability_evidence_ready"] is True
    for key in (
        "acoustic_authority_gate_ready",
        "hydrodynamic_coupling_allowed",
        "working_vertical_slice",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False
    assert FORMAL_OUTCOME == (
        "A2_4_4_SINGLE_RELAXATION_DISPERSION_INVESTIGATION_READY_"
        "WITH_ACOUSTIC_AUTHORITY_GATE_CLOSED"
    )
    assert NEXT_ACTION == (
        "PROCEED_TO_ACOUSTIC_AUTHORITY_GATE_JACOBIAN_HYPERBOLICITY_FORMULATION"
    )


def test_dynamic_modulus_recovers_exact_zero_frequency_equilibrium_limit() -> None:
    value = dynamic_sound_speed_squared(C_EQ2, C_FROZEN2, 0.0)
    assert value.real == pytest.approx(C_EQ2, rel=0.0, abs=1e-12)
    assert value.imag == pytest.approx(0.0, abs=1e-12)


def test_dynamic_modulus_recovers_low_and_high_frequency_limits() -> None:
    low = dynamic_sound_speed_squared(C_EQ2, C_FROZEN2, 1e-6)
    high = dynamic_sound_speed_squared(C_EQ2, C_FROZEN2, 1e6)
    assert abs(low - C_EQ2) / C_FROZEN2 <= 1e-6
    assert abs(high - C_FROZEN2) / C_FROZEN2 <= 1e-6
    assert low.imag < 0.0
    assert high.imag < 0.0


def test_spatial_branch_is_attenuating_and_phase_speed_is_between_limits() -> None:
    c_eq = math.sqrt(C_EQ2)
    c_frozen = math.sqrt(C_FROZEN2)
    for omega_tau in OMEGA_TAU_VALUES:
        point = spatial_dispersion_point(C_EQ2, C_FROZEN2, omega_tau)
        assert point.attenuation_m_inverse >= 0.0
        assert point.attenuation_per_wavelength >= 0.0
        assert c_eq * (1.0 - 1e-9) <= point.phase_speed_m_s
        assert point.phase_speed_m_s <= c_frozen * (1.0 + 1e-9)
        assert point.dispersion_relative_residual <= 1e-12


def test_relaxation_attenuation_peaks_at_order_one_omega_tau() -> None:
    points = [
        spatial_dispersion_point(C_EQ2, C_FROZEN2, omega_tau)
        for omega_tau in OMEGA_TAU_VALUES
    ]
    peak = max(points, key=lambda point: point.attenuation_per_wavelength)
    assert 0.1 <= peak.omega_tau <= 10.0
    assert peak.attenuation_per_wavelength > points[0].attenuation_per_wavelength
    assert peak.attenuation_per_wavelength > points[-1].attenuation_per_wavelength


def test_temporal_cubic_matches_matrix_and_all_modes_are_stable() -> None:
    for wavenumber in DIMENSIONLESS_WAVENUMBERS:
        point = temporal_stability_point(C_EQ2, C_FROZEN2, wavenumber)
        assert point.polynomial_matrix_root_mismatch <= 1e-9
        assert point.polynomial_relative_residual <= 1e-9
        assert point.maximum_real_growth <= 1e-10
        assert point.stable is True


def test_invalid_or_non_subcharacteristic_inputs_fail_closed() -> None:
    for c_eq2, c_frozen2 in (
        (C_FROZEN2, C_EQ2),
        (C_EQ2, C_EQ2),
        (-1.0, C_FROZEN2),
        (float("nan"), C_FROZEN2),
    ):
        with pytest.raises(HNEFiniteRelaxationDispersionError):
            dynamic_sound_speed_squared(c_eq2, c_frozen2, 1.0)
    with pytest.raises(HNEFiniteRelaxationDispersionError):
        dynamic_sound_speed_squared(C_EQ2, C_FROZEN2, -1.0)
    with pytest.raises(HNEFiniteRelaxationDispersionError):
        spatial_dispersion_point(C_EQ2, C_FROZEN2, 0.0)
    with pytest.raises(HNEFiniteRelaxationDispersionError):
        spatial_dispersion_point(C_EQ2, C_FROZEN2, 1.0, tau_s=0.0)
    with pytest.raises(HNEFiniteRelaxationDispersionError):
        temporal_stability_point(C_EQ2, C_FROZEN2, 0.0)


def test_source_limit_pairs_cover_representative_and_pipeline_states() -> None:
    pairs = source_limit_pairs()
    assert len(pairs) == 6
    assert pairs[-1].state_id == "A2_4_3_FOCUSED_PIPELINE_STATE"
    assert len({pair.state_id for pair in pairs}) == 6
    for pair in pairs:
        assert pair.equilibrium_c2_m2_s2 > 0.0
        assert pair.frozen_c2_m2_s2 > pair.equilibrium_c2_m2_s2
        assert 1.5e6 < pair.pressure_pa < 5.0e6
        assert 0.02 < pair.equilibrium_quality < 0.45


def test_full_dispersion_analysis_passes_all_focused_gates() -> None:
    analysis = analyze_finite_relaxation_dispersion()
    summary = analysis.summary
    assert summary["a2_4_4_dispersion_investigation_ready"] is True
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert summary["hydrodynamic_coupling_allowed"] is False
    assert all(value is False for value in summary["solver_authority"].values())
    assert len(analysis.state_rows) == 6
    assert len(analysis.spatial_rows) == 6 * len(OMEGA_TAU_VALUES)
    assert len(analysis.temporal_rows) == 6 * len(DIMENSIONLESS_WAVENUMBERS)


def test_analysis_records_frequency_dependent_phase_speed_and_attenuation() -> None:
    analysis = analyze_finite_relaxation_dispersion()
    by_state: dict[str, list[dict[str, object]]] = {}
    for row in analysis.spatial_rows:
        by_state.setdefault(str(row["state_id"]), []).append(row)
    assert len(by_state) == 6
    for rows in by_state.values():
        ordered = sorted(rows, key=lambda row: float(row["omega_tau"]))
        assert float(ordered[0]["phase_speed_m_s"]) < float(
            ordered[-1]["phase_speed_m_s"]
        )
        assert max(float(row["attenuation_per_wavelength"]) for row in rows) > 0.0
        assert all(float(row["attenuation_m_inverse"]) >= 0.0 for row in rows)


def test_repeated_analysis_is_deterministic() -> None:
    first = analyze_finite_relaxation_dispersion()
    second = analyze_finite_relaxation_dispersion()
    assert first.summary["analysis_sha256"] == second.summary["analysis_sha256"]
    assert first.state_rows == second.state_rows
    assert first.spatial_rows == second.spatial_rows
    assert first.temporal_rows == second.temporal_rows


def test_execute_writes_complete_strict_reproducible_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANALYSIS_SOURCE_GIT_SHA", "TEST_SHA")
    first = tmp_path / "first"
    second = tmp_path / "second"
    result_first = execute(first)
    result_second = execute(second)
    assert result_first["a2_4_4_dispersion_investigation_ready"] is True
    assert result_second["a2_4_4_dispersion_investigation_ready"] is True
    assert {path.name for path in first.iterdir()} == set(OUTPUT_FILES)
    assert {path.name for path in second.iterdir()} == set(OUTPUT_FILES)
    for name in OUTPUT_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    summary = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert summary["failed_gates"] == []
    assert all(summary["gate_results"].values())
    assert manifest["declared_file_count"] == len(OUTPUT_FILES)
    assert manifest["declared_file_names"] == list(OUTPUT_FILES)
    assert manifest["analysis_sha256"] == summary["analysis_sha256"]
    assert manifest["a2_4_4_dispersion_investigation_ready"] is True
    assert manifest["hydrodynamic_coupling_allowed"] is False
    assert set(manifest["payload_files"]) == set(OUTPUT_FILES) - {
        "manifest.json"
    }


def test_json_evidence_contains_no_nonstandard_nan_or_infinity(tmp_path: Path) -> None:
    execute(tmp_path)
    raw = (tmp_path / "summary.json").read_text(encoding="utf-8")
    assert "NaN" not in raw
    assert "Infinity" not in raw
    json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
