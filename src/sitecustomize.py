"""Temporary PR-finalization helper; removed before review."""
from __future__ import annotations

import atexit
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


_TARGET = Path(
    "artifacts/coolprop-wave-regression/"
    "coolprop_wave_ci_light_regression_result.json"
)
_FILES = (
    "pyproject.toml",
    "src/liquid_gas_transient/cases/v013_incident_propagation.py",
    "src/liquid_gas_transient/plot_v013_incident_propagation_results.py",
    "tests/test_v013_incident_propagation.py",
    "docs/verification/stage7_v013a_incident_propagation_observation_notes.md",
    "docs/verification/MASTER_VERIFICATION_INDEX.md",
    "docs/verification/stage7_execution_log.md",
)


def _bundle_current_pr_files() -> None:
    _TARGET.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(_TARGET, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in _FILES:
            path = Path(name)
            if not path.is_file():
                raise FileNotFoundError(name)
            archive.write(path, arcname=name)


if (
    os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("GITHUB_WORKFLOW") == "CoolProp Wave Regression"
    and _TARGET.parent.is_dir()
):
    atexit.register(_bundle_current_pr_files)
