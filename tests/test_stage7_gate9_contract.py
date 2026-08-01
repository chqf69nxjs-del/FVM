from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "verification"
CONTRACT_PATH = DOCS / "stage7_gate9_execution_contract_v0p1.json"
REGISTRY_PATH = DOCS / "stage7_gate9_literature_registry_v0p1.json"
REVIEW_PATH = DOCS / "stage7_gate9_literature_review.md"
PLAN_PATH = DOCS / "stage7_gate9_implementation_plan.md"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_gate9_contract_is_locked_before_execution() -> None:
    contract = _load(CONTRACT_PATH)
    assert contract["schema_version"] == "stage7_gate9_execution_contract_v0p1"
    assert contract["contract_status"] == "LOCKED_BEFORE_EXECUTION"
    assert contract["issue"] == 110
    assert contract["scope"] == "verification_only_forensic_diagnosis"

    immutable = contract["immutable_problem"]
    assert immutable["n_cells"] == 32
    assert immutable["cfl_sequence"] == [0.10, 0.05, 0.025]
    assert immutable["accepted_crossing_threshold"] == 1.0e-6
    assert immutable["numerical_flux"] == "existing_Rusanov"
    assert immutable["sound_speed_formula"] == "unchanged"
    assert immutable["quality_projection"] == "unchanged"


def test_gate9_contract_freezes_gate8_formal_outcomes() -> None:
    contract = _load(CONTRACT_PATH)
    rows = {row["cfl"]: row for row in contract["gate8_reference_outcomes"]}
    assert set(rows) == {0.10, 0.05, 0.025}

    assert rows[0.10]["first_crossing_outcome"] == "ACCEPTED_FIRST_CROSSING"
    assert rows[0.10]["candidate_step"] == 125
    assert rows[0.10]["maximum_candidate_q_eq"] == 3.773646403587342e-6

    assert rows[0.05]["first_crossing_outcome"] == "GUARD_FAILURE"
    assert rows[0.05]["candidate_step"] == 249
    assert rows[0.05]["maximum_candidate_q_eq"] == 1.1006096906989802e-7

    assert rows[0.025]["first_crossing_outcome"] == "ACCEPTED_FIRST_CROSSING"
    assert rows[0.025]["candidate_step"] == 499
    assert rows[0.025]["maximum_candidate_q_eq"] == 1.3949366092287805e-6
    assert rows[0.025]["continuation_failure_category"] == "ACOUSTIC_REFUSAL"


def test_gate9_event_and_flux_contract_is_predeclared() -> None:
    contract = _load(CONTRACT_PATH)
    event = contract["event_selection"]
    assert event["pre_event_accepted_steps"] == 8
    assert event["event_step_count"] == 1
    assert event["post_event_accepted_steps"] == 8
    assert "never continue after a guard or refusal" in event["post_event_rule"]

    focus = contract["focus"]
    assert focus["cells"] == [28, 29, 30, 31]
    assert [row["id"] for row in focus["interfaces"]] == [
        "27|28",
        "28|29",
        "29|30",
        "30|31",
        "RIGHT_BOUNDARY",
    ]

    decomposition = contract["rusanov_decomposition"]
    assert decomposition["formula"]["central"] == "0.5 * (F_left + F_right)"
    assert decomposition["formula"]["dissipative"] == (
        "-0.5 * a_max * (U_right - U_left)"
    )
    assert decomposition["normalized_residual_tolerance"] == 5.0e-13


def test_gate9_contract_prohibits_result_driven_model_changes() -> None:
    contract = _load(CONTRACT_PATH)
    prohibited = set(contract["prohibited_changes"])
    required = {
        "accepted crossing threshold or tolerance tuning",
        "quality clipping",
        "one-sided acoustic substitution",
        "hidden sound-speed fallback",
        "forcing subthreshold candidates into continuation",
        "Rusanov flux replacement or modification",
        "phase-classifier modification",
        "quality-projection modification",
        "prescribed-boundary retuning",
        "production-solver modification",
        "result-dependent time-step truncation",
        "HEM-to-HRM or two-fluid replacement inside Gate 9",
    }
    assert required <= prohibited
    assert all(value is False for value in contract["approval_boundary"].values())


def test_gate9_literature_registry_is_traceable_and_prioritized() -> None:
    registry = _load(REGISTRY_PATH)
    assert registry["schema_version"] == "stage7_gate9_literature_registry_v0p1"
    assert registry["issue"] == 110
    papers = registry["papers"]
    assert len(papers) >= 10
    ids = [row["id"] for row in papers]
    assert len(ids) == len(set(ids))
    assert sum(
        row["screening_status"] == "DETAILED_ANNOTATION_COMPLETE"
        for row in papers
    ) >= 3
    assert all(row["doi"] and row["primary_url"].startswith("https://") for row in papers)
    assert {"P0", "P1"} <= {row["priority"] for row in papers}


def test_gate9_document_set_is_cross_linked() -> None:
    review = REVIEW_PATH.read_text(encoding="utf-8")
    plan = PLAN_PATH.read_text(encoding="utf-8")
    assert "LIT-001" in review
    assert "LIT-006" in review
    assert "Rusanov central/dissipative decomposition" in review
    assert "stage7_gate9_execution_contract_v0p1.json" in plan
    assert "diagnostics off/on" in plan
    assert "root cause approved" in plan
