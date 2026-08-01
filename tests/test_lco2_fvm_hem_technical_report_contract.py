from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "docs" / "technical_report"
CONTRACT_PATH = REPORT_DIR / "lco2_fvm_hem_technical_report_contract_v0p1.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_technical_report_contract_has_fixed_scope_and_claim_boundaries() -> None:
    contract = _contract()
    assert contract["schema_version"] == "lco2_fvm_hem_technical_report_contract_v0p1"
    assert contract["status"] == "STRUCTURE_LOCKED_BEFORE_FULL_DRAFTING"
    assert contract["scope"]["start"] == "Stage_1"
    assert contract["scope"]["end"] == "Gate_9_literature_and_execution_contract_preparation"
    assert contract["approval_boundary"]["report_structure_approved_for_drafting"] is True
    assert contract["approval_boundary"]["full_prose_draft_complete"] is False
    assert contract["approval_boundary"]["physical_validation"] is False
    assert contract["approval_boundary"]["design_use_acceptance"] is False
    assert contract["approval_boundary"]["production_hem_activation_approved"] is False
    assert len(contract["authorized_claims"]) >= 10
    assert len(contract["prohibited_claims"]) >= 10


def test_technical_report_contract_locks_fourteen_chapters() -> None:
    chapters = _contract()["chapters"]
    assert [row["number"] for row in chapters] == list(range(1, 15))
    assert chapters[0]["title"] == "緒言"
    assert chapters[9]["title"] == "Gate 8 Post-crossing CFL感度"
    assert chapters[-1]["title"] == "結論"
    assert all(row["target_pages"] for row in chapters)
    assert all(row["primary_question"] for row in chapters)


def test_technical_report_source_of_truth_paths_exist() -> None:
    for relative in _contract()["source_of_truth"]:
        assert (ROOT / relative).is_file(), relative


def test_technical_report_workspace_files_exist_and_are_linked() -> None:
    required = {
        "README.md",
        "lco2_fvm_hem_technical_report_contract_v0p1.json",
        "lco2_fvm_hem_writing_design_v0p1.md",
        "lco2_fvm_hem_evidence_matrix_v0p1.md",
        "lco2_fvm_hem_figure_table_register_v0p1.md",
        "lco2_fvm_hem_technical_report_skeleton_v0p1.md",
    }
    assert required <= {path.name for path in REPORT_DIR.iterdir() if path.is_file()}
    readme = (REPORT_DIR / "README.md").read_text(encoding="utf-8")
    for name in required - {"README.md"}:
        assert name in readme


def test_report_skeleton_contains_all_chapters_and_claim_checklist() -> None:
    skeleton = (REPORT_DIR / "lco2_fvm_hem_technical_report_skeleton_v0p1.md").read_text(
        encoding="utf-8"
    )
    headings = [int(value) for value in re.findall(r"^# (\d+)\.", skeleton, flags=re.MULTILINE)]
    assert headings == list(range(1, 15))
    assert "physical validation remains false" in skeleton
    assert "design-use acceptance remains false" in skeleton
    assert "production activation remains false" in skeleton


def test_evidence_and_figure_registers_retain_gate8_and_planned_ids() -> None:
    evidence = (REPORT_DIR / "lco2_fvm_hem_evidence_matrix_v0p1.md").read_text(
        encoding="utf-8"
    )
    assert "8761925785" in evidence
    assert "FIXED_HORIZON_OUTCOME_DIVERGENCE" in evidence
    assert "CFL_SEQUENCE_NON_MONOTONE" in evidence
    assert "POST_CROSSING_CFL_REVIEW_INCONCLUSIVE" in evidence
    figures = (REPORT_DIR / "lco2_fvm_hem_figure_table_register_v0p1.md").read_text(
        encoding="utf-8"
    )
    for number in range(1, 18):
        assert f"F{number:02d}" in figures
    for number in range(1, 17):
        assert f"T{number:02d}" in figures
