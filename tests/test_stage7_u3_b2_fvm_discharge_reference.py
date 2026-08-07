from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

from liquid_gas_transient import u3_b1_critical_state_reference as b1_ref
from liquid_gas_transient import u3_b2_fvm_discharge_reference as reference
from liquid_gas_transient import (
    u3_b2_fvm_discharge_reference_authoritative as authoritative,
)


PARENT = Path(
    "docs/verification/stage7_u3_b2_fvm_discharge_coupling_contract_v1.json"
)
EXTENSION = Path(
    "docs/verification/"
    "stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1.json"
)
B1_CONTRACT = Path(
    "docs/verification/stage7_u3_b1_critical_state_contract_v1.json"
)


@lru_cache(maxsize=1)
def _package() -> reference.ReferencePackage:
    authoritative.install_authoritative_interpretation()
    return reference.evaluate_reference(
        reference.load_contract(PARENT),
        reference.load_extension(EXTENSION),
        b1_ref.load_contract(B1_CONTRACT),
    )


def test_reference_contract_identity_and_approval_boundary() -> None:
    contract = reference.load_contract(PARENT)
    extension = reference.load_extension(EXTENSION)
    assert contract["schema_version"] == reference.CONTRACT_SCHEMA_VERSION
    assert extension["schema_version"] == reference.EXTENSION_SCHEMA_VERSION
    assert contract["status"] == "LOCKED_BEFORE_RESULTS"
    assert contract["issue"] == 135
    assert contract["independent_paths"]["reference_first"] is True
    assert contract["independent_paths"]["shared_b2_face_mapping_helper"] is False
    assert contract["independent_paths"]["shared_b2_one_step_balance_helper"] is False
    assert contract["independent_paths"]["shared_b2_inventory_ledger_helper"] is False
    assert contract["independent_paths"]["shared_b2_acoustic_reference_helper"] is False
    assert contract["approval_boundary"]["u3_b2_contract_locked"] is True
    assert contract["approval_boundary"]["u3_b2_reference_implemented"] is False


def test_static_to_stagnation_reconstruction_round_trip() -> None:
    contract = reference.load_contract(PARENT)
    provider = reference.CoolPropReferenceProperties()
    tolerances = contract["acceptance_tolerances"]
    for state_id in (
        "LIQUID_SMALL_DROP",
        "GAS_UNCHOKED",
        "GAS_CHOKED",
    ):
        result = reference.reconstruct_family(contract, provider, state_id)
        assert result.static.density_kg_m3 > 0.0
        assert result.static.sound_speed_m_s > 0.0
        assert result.conserved.vapor_mass_kg_m3 == 0.0
        assert abs(result.enthalpy_round_trip_residual_J_kg) <= float(
            tolerances["stagnation_enthalpy_round_trip_absolute_J_kg"]
        )
        assert abs(result.entropy_round_trip_residual_J_kg_K) <= float(
            tolerances["stagnation_entropy_round_trip_absolute_J_kg_K"]
        )
        assert math.isclose(
            result.stagnation_pressure_pa,
            result.static.pressure_pa,
            rel_tol=0.0,
            abs_tol=1.0e-5,
        )


def test_face_mapping_outcomes_and_exact_wall_identities() -> None:
    package = _package()
    assert len(package.face_rows) == 13
    by_id = {row.case_id: row for row in package.face_rows}
    assert all(row.outcome_matches_contract for row in package.face_rows)
    one_step_face = by_id["B2-09_ONE_STEP_UNCHOKED_CONSERVATIVE_UPDATE"]
    assert one_step_face.formal_outcome == reference.SUCCESS_UNCHOKED_FACE_MAPPING
    assert one_step_face.expected_outcome == reference.SUCCESS_UNCHOKED_FACE_MAPPING

    identity_ids = {
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
        "B2-03_CLOSED_GAS_WALL_IDENTITY",
    }
    for case_id in sorted(identity_ids):
        row = by_id[case_id]
        assert row.F_rho_kg_m2_s == 0.0
        assert row.F_rho_u_pa == row.upstream_static_pressure_pa
        assert row.F_rho_E_W_m2 == 0.0
        assert row.F_rho_xv_kg_m2_s == 0.0

    zero_drop = by_id["B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY"]
    assert zero_drop.formal_outcome == reference.SUCCESS_ZERO_DROP_WALL_IDENTITY
    assert zero_drop.expected_outcome == reference.SUCCESS_ZERO_DROP_WALL_IDENTITY
    assert zero_drop.b1_formal_outcome
    assert zero_drop.b1_formal_outcome in zero_drop.formal_message
    assert "raw B1 outcome" in zero_drop.formal_message
    assert "No B1 law, contract value, or tolerance was changed" in (
        zero_drop.formal_message
    )

    assert {
        row.case_id
        for row in package.face_rows
        if row.mass_transfer_outward_kg_s == 0.0
        and row.energy_transfer_outward_W == 0.0
    } == identity_ids
    for row in package.face_rows:
        if row.case_id == "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY":
            continue
        assert reference.map_b1_outcome(row.b1_formal_outcome) == row.formal_outcome

    assert max(
        abs(row.pressure_decomposition_residual_pa)
        for row in package.face_rows
    ) <= 1.0e-8


def test_locked_b0_plateau_area_and_cd_checks_pass() -> None:
    package = _package()
    checks = {row["check"]: row for row in package.locked_checks}
    for name in (
        "B0_limit_mass",
        "B0_limit_velocity",
        "B0_limit_momentum",
        "B0_limit_energy",
        "below_critical_face_flux_plateau",
        "area_scaling",
        "Cd_scaling_and_critical_pressure",
    ):
        assert checks[name]["passed"] is True
    assert package.summary["all_locked_reference_checks_passed"] is True


def test_one_step_reference_closes_conservative_balances() -> None:
    result = _package().one_step
    tolerances = reference.load_contract(PARENT)["acceptance_tolerances"]
    assert result.formal_outcome == reference.SUCCESS_ONE_STEP
    assert result.accepted_dt_s > 0.0
    assert result.accepted_dt_s <= result.cfl_dt_s
    assert result.accepted_dt_s <= result.mass_removal_dt_s
    assert result.accepted_dt_s <= result.energy_removal_dt_s
    assert result.U_after_rho > 0.0
    assert result.U_after_rho_E > 0.0
    assert result.U_after_rho_xv == 0.0
    assert result.normalized_balance_residual <= float(
        tolerances["one_step_normalized_state_absolute"]
    )
    assert abs(result.mass_inventory_residual_kg) <= float(
        tolerances["mass_inventory_absolute_kg"]
    )
    assert abs(result.energy_inventory_residual_J) <= float(
        tolerances["energy_inventory_absolute_J"]
    )
    assert result.vapor_inventory_residual_kg == 0.0


def test_independent_inventory_ledgers_close() -> None:
    package = _package()
    tolerances = reference.load_contract(PARENT)["acceptance_tolerances"]
    assert len(package.ledger_rows) == 12
    assert {row.ledger_id for row in package.ledger_rows} == {
        "LIQUID_LEDGER_REFERENCE",
        "GAS_UNCHOKED_LEDGER_REFERENCE",
        "GAS_CHOKED_LEDGER_REFERENCE",
    }
    assert max(abs(row.mass_residual_kg) for row in package.ledger_rows) <= float(
        tolerances["mass_inventory_absolute_kg"]
    )
    assert max(abs(row.energy_residual_J) for row in package.ledger_rows) <= float(
        tolerances["energy_inventory_absolute_J"]
    )
    assert max(
        abs(row.momentum_residual_kg_m_s) for row in package.ledger_rows
    ) <= float(tolerances["momentum_inventory_absolute_kg_m_s"])
    assert all(row.vapor_residual_kg == 0.0 for row in package.ledger_rows)


def test_acoustic_reference_uses_requested_probe_coordinates() -> None:
    rows = _package().acoustic_rows
    assert len(rows) == 9
    assert {row.cells for row in rows} == {16, 32, 64}
    for cells in (16, 32, 64):
        mesh_rows = [row for row in rows if row.cells == cells]
        assert [row.probe_normalized_position for row in mesh_rows] == [
            0.25,
            0.50,
            0.75,
        ]
        assert [row.direct_order_rank for row in mesh_rows] == [3, 2, 1]
        assert [row.reflected_order_rank for row in mesh_rows] == [1, 2, 3]
        for row in mesh_rows:
            assert row.interpolation_weight == 0.5
            assert row.left_center_xi < row.probe_normalized_position
            assert row.probe_normalized_position < row.right_center_xi
            expected_direct = (
                1.0 - row.probe_normalized_position
            ) / row.initial_sound_speed_m_s
            expected_reflected = (
                1.0 + row.probe_normalized_position
            ) / row.initial_sound_speed_m_s
            assert math.isclose(
                row.direct_reference_time_s,
                expected_direct,
                rel_tol=0.0,
                abs_tol=0.0,
            )
            assert math.isclose(
                row.reflected_reference_time_s,
                expected_reflected,
                rel_tol=0.0,
                abs_tol=0.0,
            )
            assert row.arrival_reference_coordinate == "requested_xi_probe"


def test_all_seven_guard_outcomes_are_atomic_and_match() -> None:
    rows = _package().guard_rows
    assert len(rows) == 7
    assert all(row.outcome_matches_contract for row in rows)
    assert all(row.guard_triggered_before_flux for row in rows)
    assert all(row.guard_triggered_before_budget for row in rows)
    assert all(row.guard_triggered_before_state_mutation for row in rows)


def test_reference_case_matrix_preserves_unimplemented_boundaries() -> None:
    package = _package()
    assert len(package.case_matrix) == 26
    assert package.summary["u3_b2_reference_implemented"] is True
    for key in (
        "u3_b2_fvm_adapter_implemented",
        "u3_b2_finite_pipe_execution_complete",
        "u3_b2_verification_benchmark_accepted",
        "single_phase_fvm_discharge_mapping_verified",
        "single_phase_finite_pipe_coupling_verified",
        "physical_discharge_boundary_approved",
        "two_phase_critical_discharge_accuracy_approved",
        "integrated_blowdown_model_approved",
        "physical_validation",
        "design_use_acceptance",
        "production_hem_activation_approved",
    ):
        assert package.summary[key] is False
    assert package.summary["reference_imports_future_B2_adapter"] is False


def test_reference_artifact_is_complete_and_digest_verified(tmp_path: Path) -> None:
    package = _package()
    output = tmp_path / "reference"
    reference.write_artifact(
        output_dir=output,
        package=package,
        contract_path=PARENT,
        extension_path=EXTENSION,
        b1_contract_path=B1_CONTRACT,
        source_git_sha="1" * 40,
    )
    expected = {
        "summary.json",
        "runtime_and_git_provenance.json",
        "benchmark_contract.json",
        "event_provenance_contract.json",
        "b1_component_contract.json",
        "reference_case_matrix.csv",
        "face_state_and_choking_adoption.csv",
        "face_flux_decomposition.csv",
        "one_step_conservative_update_reference.csv",
        "cumulative_discharge_and_inventory_reference.csv",
        "momentum_impulse_reference.csv",
        "acoustic_arrival_reference.csv",
        "guard_outcomes.csv",
        "locked_checks.csv",
        "face_flux_reference.png",
        "acoustic_arrival_reference.png",
        "report.md",
        "artifact_sha256.txt",
    }
    assert {path.name for path in output.iterdir()} == expected
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == reference.SCHEMA_VERSION
    assert summary["all_locked_reference_checks_passed"] is True
    assert summary["provenance"]["source_git_sha"] == "1" * 40
    manifest = {}
    for line in (output / "artifact_sha256.txt").read_text(
        encoding="utf-8"
    ).splitlines():
        digest, name = line.split("  ", 1)
        manifest[name] = digest
    assert set(manifest) == expected - {"artifact_sha256.txt"}
    for name, expected_digest in manifest.items():
        actual = hashlib.sha256((output / name).read_bytes()).hexdigest()
        assert actual == expected_digest
