"""Inspect the Stage 7 Windows full-suite result without weakening exact baselines.

The authoritative Ubuntu regressions remain bitwise exact. A Windows runtime is
accepted here only as a Gate 3 diagnostic when the complete repository suite has
no failures outside the reviewed set of exact cross-platform mismatches.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


EXPECTED_PR91_FULL_SUITE_TEST_COUNT = 804

KNOWN_WINDOWS_EXACT_MISMATCHES: dict[str, str] = {
    (
        "tests.test_stage7_lco2_hem_pipeline_depressurization_increment2::"
        "test_installed_pipeline_result_matches_observation_contract_exactly"
    ): "assert actual.final_time_s == expected",
    (
        "tests.test_stage7_lco2_hem_pipeline_depressurization_increment2::"
        "test_frozen_case_ab_regression_signatures_remain_exact"
    ): "Extra items in the left set",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_fixed_forensic_result_reproduces_pr77_and_retains_complete_window"
    ): "PR #77 baseline mismatch",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_crossing_state_has_independent_thermodynamic_evidence"
    ): "PR #77 baseline mismatch",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_isentropic_reference_is_explicitly_recorded"
    ): "PR #77 baseline mismatch",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_rusanov_decomposition_reconstructs_every_selected_raw_state"
    ): "PR #77 baseline mismatch",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_perturbation_map_is_complete_and_keeps_the_baseline_state"
    ): "PR #77 baseline mismatch",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_fixed_forensic_diagnostic_repeats_exactly"
    ): "PR #77 baseline mismatch",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_forensic_artifact_bundle_is_complete"
    ): "PR #77 baseline mismatch",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics::"
        "test_frozen_case_ab_regression_remains_exact"
    ): "Extra items in the left set",
    (
        "tests.test_stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_contract::"
        "test_installed_forensic_result_matches_machine_readable_contract_exactly"
    ): "PR #77 baseline mismatch",
}


class HEMGate3WindowsSuiteError(RuntimeError):
    """Raised when the Windows full-suite evidence exceeds the reviewed boundary."""


@dataclass(frozen=True)
class Gate3WindowsSuiteResult:
    tests: int
    expected_tests: int
    test_count_exact: bool
    failures: int
    errors: int
    skipped: int
    observed_problem_tests: tuple[str, ...]
    expected_problem_tests: tuple[str, ...]
    unexpected_problem_tests: tuple[str, ...]
    missing_expected_problem_tests: tuple[str, ...]
    message_contract_failures: tuple[str, ...]
    disposition: str

    @property
    def accepted_as_known_exact_mismatches_only(self) -> bool:
        return self.disposition == "KNOWN_EXACT_WINDOWS_MISMATCHES_ONLY"

    def summary(self) -> dict[str, object]:
        result = asdict(self)
        result["accepted_as_known_exact_mismatches_only"] = (
            self.accepted_as_known_exact_mismatches_only
        )
        result["authoritative_ubuntu_exact_baselines_changed"] = False
        result["automatic_gate3_acceptance"] = False
        result["Gate_P2_passed"] = False
        result["CFL_independent_crossing_verified"] = False
        result["physical_validation"] = False
        result["design_use_acceptance"] = False
        result["production_hem_activation_approved"] = False
        return result


def _suite_totals(root: ET.Element) -> dict[str, int]:
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }


def inspect_windows_full_suite(
    junit_xml: str | Path,
    *,
    expected_test_count: int = EXPECTED_PR91_FULL_SUITE_TEST_COUNT,
) -> Gate3WindowsSuiteResult:
    """Require the full suite to contain only the reviewed Windows exact mismatches."""

    if expected_test_count <= 0:
        raise ValueError("expected_test_count must be positive")
    path = Path(junit_xml)
    if not path.is_file():
        raise HEMGate3WindowsSuiteError(f"JUnit XML does not exist: {path}")
    root = ET.parse(path).getroot()
    totals = _suite_totals(root)

    observed: dict[str, str] = {}
    for case in root.iter("testcase"):
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            continue
        classname = str(case.attrib.get("classname", "")).strip()
        name = str(case.attrib.get("name", "")).strip()
        if not classname or not name:
            raise HEMGate3WindowsSuiteError(
                "failing JUnit testcase is missing classname or name"
            )
        observed[f"{classname}::{name}"] = str(problem.text or "")

    expected_ids = set(KNOWN_WINDOWS_EXACT_MISMATCHES)
    observed_ids = set(observed)
    unexpected = tuple(sorted(observed_ids - expected_ids))
    missing = tuple(sorted(expected_ids - observed_ids))
    message_failures = tuple(
        sorted(
            test_id
            for test_id in observed_ids & expected_ids
            if KNOWN_WINDOWS_EXACT_MISMATCHES[test_id] not in observed[test_id]
        )
    )
    test_count_exact = totals["tests"] == expected_test_count

    accepted = bool(
        test_count_exact
        and totals["skipped"] == 0
        and not unexpected
        and not missing
        and not message_failures
        and totals["failures"] + totals["errors"] == len(expected_ids)
    )
    disposition = (
        "KNOWN_EXACT_WINDOWS_MISMATCHES_ONLY"
        if accepted
        else "UNEXPECTED_WINDOWS_FULL_SUITE_RESULT"
    )
    return Gate3WindowsSuiteResult(
        tests=totals["tests"],
        expected_tests=expected_test_count,
        test_count_exact=test_count_exact,
        failures=totals["failures"],
        errors=totals["errors"],
        skipped=totals["skipped"],
        observed_problem_tests=tuple(sorted(observed_ids)),
        expected_problem_tests=tuple(sorted(expected_ids)),
        unexpected_problem_tests=unexpected,
        missing_expected_problem_tests=missing,
        message_contract_failures=message_failures,
        disposition=disposition,
    )


def write_windows_full_suite_report(
    junit_xml: str | Path,
    output_json: str | Path,
    *,
    expected_test_count: int = EXPECTED_PR91_FULL_SUITE_TEST_COUNT,
) -> Gate3WindowsSuiteResult:
    result = inspect_windows_full_suite(
        junit_xml,
        expected_test_count=expected_test_count,
    )
    Path(output_json).write_text(
        json.dumps(result.summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect the complete Windows suite against the Gate 3 allowlist."
    )
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--expected-tests",
        type=int,
        default=EXPECTED_PR91_FULL_SUITE_TEST_COUNT,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = write_windows_full_suite_report(
        args.junit,
        args.output,
        expected_test_count=args.expected_tests,
    )
    print(json.dumps(result.summary(), indent=2, sort_keys=True))
    return 0 if result.accepted_as_known_exact_mismatches_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
