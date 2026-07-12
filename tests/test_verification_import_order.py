from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _run_import(code: str) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_case_module_can_be_imported_before_verification_exports() -> None:
    _run_import(
        "from liquid_gas_transient.cases.coolprop_boundary_reflection import "
        "CoolPropBoundaryReflectionConfig; "
        "from liquid_gas_transient.verification import "
        "BoundaryReflectionRegressionLimits; "
        "assert CoolPropBoundaryReflectionConfig and BoundaryReflectionRegressionLimits"
    )


def test_verification_exports_can_be_imported_before_case_module() -> None:
    _run_import(
        "from liquid_gas_transient.verification import "
        "BoundaryReflectionRegressionLimits; "
        "from liquid_gas_transient.cases.coolprop_boundary_reflection import "
        "CoolPropBoundaryReflectionConfig; "
        "assert BoundaryReflectionRegressionLimits and CoolPropBoundaryReflectionConfig"
    )
