from __future__ import annotations

import json
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
