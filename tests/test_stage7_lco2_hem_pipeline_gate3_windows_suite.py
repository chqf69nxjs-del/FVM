from __future__ import annotations

import xml.etree.ElementTree as ET

from liquid_gas_transient.hem_pipeline_gate3_windows_suite import (
    KNOWN_WINDOWS_EXACT_MISMATCHES,
    inspect_windows_full_suite,
)


def _write_junit(path, cases, *, skipped=0):
    suite = ET.Element(
        "testsuite",
        tests=str(len(cases) + skipped),
        failures=str(sum(kind == "failure" for _, kind, _ in cases)),
        errors=str(sum(kind == "error" for _, kind, _ in cases)),
        skipped=str(skipped),
    )
    for test_id, kind, text in cases:
        classname, name = test_id.split("::", 1)
        case = ET.SubElement(
            suite,
            "testcase",
            classname=classname,
            name=name,
        )
        problem = ET.SubElement(case, kind)
        problem.text = text
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def test_reviewed_windows_exact_mismatch_set_is_accepted(tmp_path):
    path = tmp_path / "full.xml"
    cases = [
        (
            test_id,
            "failure" if index < 4 else "error",
            expected_text,
        )
        for index, (test_id, expected_text) in enumerate(
            KNOWN_WINDOWS_EXACT_MISMATCHES.items()
        )
    ]
    _write_junit(path, cases)
    result = inspect_windows_full_suite(path)
    assert result.accepted_as_known_exact_mismatches_only is True
    assert result.unexpected_problem_tests == ()
    assert result.missing_expected_problem_tests == ()
    assert result.message_contract_failures == ()


def test_unexpected_failure_is_rejected(tmp_path):
    path = tmp_path / "full.xml"
    _write_junit(
        path,
        [("tests.test_unrelated::test_new_failure", "failure", "unexpected")],
    )
    result = inspect_windows_full_suite(path)
    assert result.accepted_as_known_exact_mismatches_only is False
    assert result.unexpected_problem_tests == (
        "tests.test_unrelated::test_new_failure",
    )


def test_missing_expected_mismatch_is_rejected(tmp_path):
    path = tmp_path / "full.xml"
    first_id, first_text = next(iter(KNOWN_WINDOWS_EXACT_MISMATCHES.items()))
    _write_junit(path, [(first_id, "failure", first_text)])
    result = inspect_windows_full_suite(path)
    assert result.accepted_as_known_exact_mismatches_only is False
    assert result.missing_expected_problem_tests


def test_wrong_failure_message_is_rejected(tmp_path):
    path = tmp_path / "full.xml"
    cases = [
        (test_id, "error", "wrong failure mechanism")
        for test_id in KNOWN_WINDOWS_EXACT_MISMATCHES
    ]
    _write_junit(path, cases)
    result = inspect_windows_full_suite(path)
    assert result.accepted_as_known_exact_mismatches_only is False
    assert set(result.message_contract_failures) == set(
        KNOWN_WINDOWS_EXACT_MISMATCHES
    )


def test_skipped_test_is_rejected(tmp_path):
    path = tmp_path / "full.xml"
    cases = [
        (test_id, "error", expected_text)
        for test_id, expected_text in KNOWN_WINDOWS_EXACT_MISMATCHES.items()
    ]
    _write_junit(path, cases, skipped=1)
    result = inspect_windows_full_suite(path)
    assert result.accepted_as_known_exact_mismatches_only is False
    assert result.skipped == 1
