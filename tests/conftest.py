"""PR #48 artifact-traceability assertions for the installed-CoolProp run."""
from __future__ import annotations

from importlib.metadata import version as distribution_version
import json

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item):
    outcome = yield
    if outcome.excinfo is not None:
        return
    if item.name != "test_v013a_installed_cross_verification_run_and_artifacts":
        return

    output_dir = item.funcargs["tmp_path"]
    expected = distribution_version("CoolProp")
    aggregate = json.loads(
        (output_dir / "v013a_metrics.json").read_text(encoding="utf-8")
    )
    reference = json.loads(
        (output_dir / "v013a_reference_constants.json").read_text(encoding="utf-8")
    )
    case_id = aggregate["run_plan"][0]["case_id"]
    fvm_metrics = json.loads(
        (output_dir / case_id / "fvm_metrics.json").read_text(encoding="utf-8")
    )
    assert aggregate["coolprop_version"] == expected
    assert reference["coolprop_version"] == expected
    assert fvm_metrics["coolprop_version"] == expected
