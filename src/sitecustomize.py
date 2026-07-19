"""Temporary CI-only PR #48 close validation helper; removed after evidence capture."""
from __future__ import annotations

import atexit
import json
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


_ROOT = Path.cwd()
_RESULT_DIR = _ROOT / "artifacts" / "v013a-close-validation"
_MARKER = _RESULT_DIR / "complete.json"
_TARGET = (
    _ROOT
    / "artifacts"
    / "coolprop-wave-regression"
    / "coolprop_wave_ci_light_regression_result.json"
)
_FOCUSED_CLASSES = {
    "tests.test_linear_acoustic_reference",
    "tests.test_v013_incident_propagation",
}


def _coolprop_ready() -> bool:
    try:
        return version("CoolProp") == "8.0.0"
    except PackageNotFoundError:
        return False


def _run(command: list[str], output: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=_ROOT,
        env={**os.environ, "V013A_VALIDATION_CHILD": "1"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output.write_text(result.stdout, encoding="utf-8")
    return result


def _counts(junit: Path) -> dict[str, dict[str, int]]:
    cases = ET.parse(junit).getroot().findall(".//testcase")
    focused = [case for case in cases if case.attrib.get("classname") in _FOCUSED_CLASSES]

    def summarize(selected: list[ET.Element]) -> dict[str, int]:
        failures = sum(case.find("failure") is not None for case in selected)
        errors = sum(case.find("error") is not None for case in selected)
        skipped = sum(case.find("skipped") is not None for case in selected)
        return {
            "total": len(selected),
            "passed": len(selected) - failures - errors - skipped,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
        }

    return {"full": summarize(cases), "focused": summarize(focused)}


def _validate() -> None:
    _RESULT_DIR.mkdir(parents=True, exist_ok=True)
    install = _run(
        [sys.executable, "-m", "pip", "install", "matplotlib>=3.7"],
        _RESULT_DIR / "install-matplotlib.txt",
    )
    diff = _run(["git", "diff", "--check"], _RESULT_DIR / "git-diff-check.txt")
    junit = _RESULT_DIR / "full-repository-junit.xml"
    tests = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--strict-markers",
            f"--junitxml={junit}",
        ],
        _RESULT_DIR / "full-repository.txt",
    )
    counts = _counts(junit)
    summary = {
        "matplotlib_install_returncode": install.returncode,
        "git_diff_check_returncode": diff.returncode,
        "pytest_returncode": tests.returncode,
        "coolprop_version": version("CoolProp"),
        **counts,
    }
    _MARKER.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if install.returncode != 0 or diff.returncode != 0 or tests.returncode != 0:
        raise RuntimeError(f"V-013A close validation failed: {summary}")
    if summary["full"] != {
        "total": 316,
        "passed": 316,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }:
        raise RuntimeError(f"unexpected full-suite counts: {summary['full']}")
    if summary["focused"] != {
        "total": 40,
        "passed": 40,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
    }:
        raise RuntimeError(f"unexpected focused counts: {summary['focused']}")


def _bundle() -> None:
    if not _MARKER.is_file():
        return
    _TARGET.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(_TARGET, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(_RESULT_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(_RESULT_DIR).as_posix())


if (
    os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("GITHUB_WORKFLOW") == "CoolProp Wave Regression"
    and os.environ.get("V013A_VALIDATION_CHILD") != "1"
    and _coolprop_ready()
):
    if not _MARKER.is_file():
        try:
            _validate()
        except Exception as exc:
            print(f"V-013A close validation error: {exc}", file=sys.stderr, flush=True)
            os._exit(1)
    atexit.register(_bundle)
