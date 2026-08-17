from __future__ import annotations

import pytest

from liquid_gas_transient.hne_pipeline_model_form_audit import (
    FORMAL_STATUS,
    OUTPUT_FILES,
    SCHEMA,
    ZERO_TOL,
    behavior_classification,
    front_relation,
)


def test_a1r_contract_and_maturity_boundary() -> None:
    assert SCHEMA == "stage7_p2_hne_model_form_sensitivity_a1r_v1"
    assert ZERO_TOL == pytest.approx(1.0e-18)
    assert len(OUTPUT_FILES) == 9
    assert FORMAL_STATUS["implemented"] is True
    assert FORMAL_STATUS["diagnostic_evidence_ready"] is True
    assert FORMAL_STATUS["p2_model_form_vertical_slice"] is True
    for key in (
        "physical_hne_vertical_slice",
        "working_vertical_slice",
        "verified",
        "accepted",
        "physically_validated",
        "design_use_accepted",
        "production_approved",
    ):
        assert FORMAL_STATUS[key] is False


def test_front_relation_classifies_absent_lag_equal_and_lead() -> None:
    assert front_relation(None, None) == "BOTH_ABSENT"
    assert front_relation(0.1, None) == (
        "KINETIC_ABSENT_WHILE_THERMODYNAMIC_PRESENT"
    )
    assert front_relation(None, 0.1) == (
        "KINETIC_PRESENT_WHILE_THERMODYNAMIC_ABSENT"
    )
    assert front_relation(0.2, 0.1) == "KINETIC_BEHIND"
    assert front_relation(0.2, 0.2) == "COINCIDENT"
    assert front_relation(0.1, 0.2) == "KINETIC_AHEAD"


def test_behavior_classification_retains_mixed_front_behavior() -> None:
    base = {
        "full_state_matches_hem": False,
        "maximum_absolute_signed_quality_lag": 1.0e-4,
        "onset_delay_s": 1.0e-5,
        "kinetic_absent_count": 2,
        "kinetic_behind_count": 2,
        "kinetic_only_count": 0,
        "kinetic_ahead_count": 3,
    }
    assert behavior_classification(base) == (
        "RESOLVED_ONSET_DELAY_WITH_MIXED_FRONT_LAG_AND_LEAD"
    )
    medium = dict(base)
    medium.update(
        onset_delay_s=0.0,
        kinetic_absent_count=0,
        kinetic_behind_count=0,
    )
    assert behavior_classification(medium) == (
        "NO_RESOLVED_ONSET_DELAY_WITH_TRANSIENT_FRONT_LEAD"
    )
