from __future__ import annotations

import json
import math
from pathlib import Path


EXTENSION = Path(
    "docs/verification/"
    "stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1.json"
)


def _load() -> dict[str, object]:
    return json.loads(EXTENSION.read_text(encoding="utf-8"))


def test_extension_inherits_locked_b1_tolerances_without_relaxation() -> None:
    extension = _load()
    inherited = extension["inherited_B1_acceptance_tolerances"]
    assert inherited["source_contract"] == (
        "docs/verification/stage7_u3_b1_critical_state_contract_v1.json"
    )
    assert inherited["inheritance_rule"].startswith("exact B1 values")
    assert inherited["B0_limit_mass_flow_relative"] == 0.01
    assert inherited["B0_limit_effective_velocity_relative"] == 0.01
    assert inherited["B0_limit_momentum_transfer_relative"] == 0.02
    assert inherited["B0_limit_energy_transfer_relative"] == 0.01
    assert inherited["critical_pressure_Cd_independence_relative"] == 5.0e-6
    assert inherited["minimum_unchoked_mass_flow_ordering_margin_relative"] == 0.001


def test_extension_locks_direct_and_reflected_acoustic_event_order() -> None:
    detection = _load()["acoustic_event_detection"]
    assert detection["history_sampling"] == "every accepted time step"
    assert detection["expected_window_half_width_L_over_c0"] == 0.20
    assert detection["direct_arrival_order"] == (
        "probe 0.75, then 0.50, then 0.25"
    )
    assert detection["reflected_arrival_order"] == (
        "probe 0.25, then 0.50, then 0.75"
    )
    assert detection["unresolved_outcome"] == "ACOUSTIC_EVENT_NOT_RESOLVED"
    assert detection["no_post_result_window_or_threshold_change"] is True

    sampling = detection["spatial_probe_sampling"]
    assert sampling["requested_normalized_positions"] == [0.25, 0.50, 0.75]
    assert sampling["sampled_primitive_quantities"] == [
        "pressure_pa",
        "axial_velocity_m_s",
    ]
    assert "nearest-cell sampling" in sampling["bracketing_rule"]
    assert "requested xi_probe" in sampling["arrival_reference_coordinate"]
    assert sampling["no_post_result_spatial_rule_change"] is True

    expected_indices = {
        16: [(3, 4), (7, 8), (11, 12)],
        32: [(7, 8), (15, 16), (23, 24)],
        64: [(15, 16), (31, 32), (47, 48)],
    }
    probe_map = {
        int(row["cells"]): row["entries"]
        for row in sampling["fixed_mesh_probe_map"]
    }
    assert set(probe_map) == {16, 32, 64}

    for cells, expected_pairs in expected_indices.items():
        entries = probe_map[cells]
        assert len(entries) == 3
        for entry, expected_pair in zip(entries, expected_pairs, strict=True):
            xi_probe = float(entry["xi_probe"])
            left_index = int(entry["left_internal_index"])
            right_index = int(entry["right_internal_index"])
            left_center = float(entry["left_center_xi"])
            right_center = float(entry["right_center_xi"])
            interpolation_weight = float(entry["lambda"])

            assert (left_index, right_index) == expected_pair
            assert math.isclose(
                left_center,
                (left_index + 0.5) / cells,
                rel_tol=0.0,
                abs_tol=0.0,
            )
            assert math.isclose(
                right_center,
                (right_index + 0.5) / cells,
                rel_tol=0.0,
                abs_tol=0.0,
            )
            assert left_center < xi_probe < right_center
            expected_weight = (
                (xi_probe - left_center) / (right_center - left_center)
            )
            assert math.isclose(
                interpolation_weight,
                expected_weight,
                rel_tol=0.0,
                abs_tol=0.0,
            )
            assert interpolation_weight == 0.5

            # Linear interpolation must reproduce any affine primitive field
            # exactly at the requested physical probe coordinate.
            pressure_left = 2.0e6 + 3.0e5 * left_center
            pressure_right = 2.0e6 + 3.0e5 * right_center
            velocity_left = -4.0 + 5.0 * left_center
            velocity_right = -4.0 + 5.0 * right_center
            pressure_probe = (
                (1.0 - interpolation_weight) * pressure_left
                + interpolation_weight * pressure_right
            )
            velocity_probe = (
                (1.0 - interpolation_weight) * velocity_left
                + interpolation_weight * velocity_right
            )
            assert math.isclose(
                pressure_probe,
                2.0e6 + 3.0e5 * xi_probe,
                rel_tol=0.0,
                abs_tol=1.0e-9,
            )
            assert math.isclose(
                velocity_probe,
                -4.0 + 5.0 * xi_probe,
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )


def test_extension_requires_self_and_runtime_provenance_in_artifact() -> None:
    extension = _load()
    assert extension["required_artifact_additions"] == [
        "event_provenance_contract.json",
        "runtime_and_git_provenance.json",
    ]
    provenance = extension["runtime_and_provenance"]
    assert provenance["parent_and_extension_contract_sha256_required"] is True
    assert provenance["reference_and_adapter_source_shas_separate"] is True
    assert provenance["artifact_manifest_rule"].startswith(
        "artifact_sha256.txt covers"
    )
    approval = extension["approval_boundary"]
    assert approval["u3_b2_contract_locked"] is True
    assert all(
        value is False
        for key, value in approval.items()
        if key != "u3_b2_contract_locked"
    )
