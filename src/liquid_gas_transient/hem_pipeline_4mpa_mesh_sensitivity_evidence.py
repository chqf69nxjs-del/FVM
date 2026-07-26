"""Traceable artifact wrapper for the Stage 7 pipeline mesh-sensitivity matrix.

The numerical matrix remains implemented by
:mod:`hem_pipeline_4mpa_mesh_sensitivity`.  This module adds the analysis
identity and actual runtime provenance required for authoritative artifacts,
and labels every generated result figure with case, model, backend, and
backend version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .hem_pipeline_4mpa_mesh_sensitivity import (
    FOUR_MPA_CASE_ID,
    HEMPipelineMeshSensitivityResult,
    write_pipeline_mesh_sensitivity_artifacts,
)


ANALYSIS_MODEL = "HEM"
PROPERTY_BACKEND_NAME = "coolprop_co2"
PLOT_KEYS: tuple[str, ...] = (
    "plot_qeq",
    "plot_margin",
    "plot_time_position",
    "plot_sound_speed",
)


class HEMPipelineMeshEvidenceError(RuntimeError):
    """Raised when traceable artifact evidence cannot be produced safely."""


def _coolprop_version() -> str:
    try:
        import CoolProp  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("CoolProp is required for authoritative mesh evidence") from exc
    version = str(getattr(CoolProp, "__version__", "")).strip()
    if not version:
        raise HEMPipelineMeshEvidenceError("CoolProp version is unavailable")
    return version


def _git_output(*args: str) -> str | None:
    try:
        value = subprocess.check_output(
            ["git", *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return value or None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_runtime_provenance() -> dict[str, object]:
    """Return backend, version, and exact Git/runtime identity for this run."""

    checkout_sha = _git_output("rev-parse", "HEAD")
    source_sha = (
        os.environ.get("ANALYSIS_SOURCE_GIT_SHA", "").strip()
        or os.environ.get("GITHUB_HEAD_SHA", "").strip()
        or os.environ.get("GITHUB_SHA", "").strip()
        or checkout_sha
    )
    if not source_sha:
        raise HEMPipelineMeshEvidenceError(
            "source Git SHA is unavailable; set ANALYSIS_SOURCE_GIT_SHA"
        )

    runner_path = Path(__file__).with_name("hem_pipeline_4mpa_mesh_sensitivity.py")
    wrapper_path = Path(__file__)
    if not runner_path.is_file() or not wrapper_path.is_file():
        raise HEMPipelineMeshEvidenceError("mesh evidence source files are unavailable")

    return {
        "analysis_case_id": FOUR_MPA_CASE_ID,
        "analysis_model": ANALYSIS_MODEL,
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "property_backend_version": _coolprop_version(),
        "source_git_sha": source_sha,
        "checkout_git_sha": checkout_sha,
        "git_branch": _git_output("rev-parse", "--abbrev-ref", "HEAD"),
        "git_status_porcelain": _git_output("status", "--porcelain") or "",
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "github_ref": os.environ.get("GITHUB_REF"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "runner_source_sha256": _sha256(runner_path),
        "evidence_wrapper_sha256": _sha256(wrapper_path),
    }


def analysis_identity(provenance: Mapping[str, object]) -> dict[str, str]:
    """Return the mandatory case/model/backend/version figure identity."""

    return {
        "case_id": str(provenance["analysis_case_id"]),
        "model": str(provenance["analysis_model"]),
        "backend": str(provenance["property_backend_name"]),
        "version": str(provenance["property_backend_version"]),
    }


def _identity_text(identity: Mapping[str, str]) -> str:
    return (
        f"case={identity['case_id']} | model={identity['model']} | "
        f"backend={identity['backend']} | version={identity['version']}"
    )


def _annotate_png(
    path: Path,
    *,
    identity: Mapping[str, str],
    provenance: Mapping[str, object],
) -> None:
    try:
        import matplotlib.image as mpimg  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # pragma: no cover - optional plotting path
        raise HEMPipelineMeshEvidenceError(
            "matplotlib is required to label authoritative result figures"
        ) from exc

    image = mpimg.imread(path)
    if image.ndim not in (2, 3):
        raise HEMPipelineMeshEvidenceError(
            f"unexpected PNG shape for {path.name}: {image.shape}"
        )
    height, width = image.shape[:2]
    dpi = 180
    header_px = max(90, int(0.10 * height))
    fig = plt.figure(figsize=(width / dpi, (height + header_px) / dpi), dpi=dpi)
    image_fraction = height / (height + header_px)
    ax = fig.add_axes([0.0, 0.0, 1.0, image_fraction])
    ax.imshow(image)
    ax.axis("off")

    source_sha = str(provenance["source_git_sha"])
    fig.text(
        0.012,
        0.985,
        _identity_text(identity),
        ha="left",
        va="top",
        fontsize=8.5,
    )
    fig.text(
        0.012,
        0.945,
        f"source_git_sha={source_sha}",
        ha="left",
        va="top",
        fontsize=7.0,
    )

    temporary = path.with_name(f".{path.name}.traceable.png")
    metadata = {
        "case": identity["case_id"],
        "model": identity["model"],
        "backend": identity["backend"],
        "version": identity["version"],
        "source_git_sha": source_sha,
    }
    fig.savefig(
        temporary,
        dpi=dpi,
        metadata=metadata,
        facecolor="white",
        bbox_inches=None,
        pad_inches=0.0,
    )
    plt.close(fig)
    temporary.replace(path)


def add_traceability(
    paths: Mapping[str, Path],
    *,
    provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Add mandatory identity and provenance to the complete artifact bundle."""

    resolved_provenance = dict(provenance or collect_runtime_provenance())
    identity = analysis_identity(resolved_provenance)

    summary_path = Path(paths["summary_json"])
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    payload["analysis_identity"] = identity
    payload["provenance"] = resolved_provenance
    payload["generated_plots"] = [Path(paths[key]).name for key in PLOT_KEYS]
    summary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for key in PLOT_KEYS:
        plot_path = Path(paths[key])
        if not plot_path.is_file():
            raise HEMPipelineMeshEvidenceError(
                f"required result figure is missing: {plot_path}"
            )
        _annotate_png(
            plot_path,
            identity=identity,
            provenance=resolved_provenance,
        )

    markdown_path = Path(paths["markdown"])
    original = markdown_path.read_text(encoding="utf-8")
    traceability = (
        "## Analysis identity and runtime provenance\n\n"
        "```text\n"
        f"case:               {identity['case_id']}\n"
        f"model:              {identity['model']}\n"
        f"backend:            {identity['backend']}\n"
        f"backend version:    {identity['version']}\n"
        f"source Git SHA:     {resolved_provenance['source_git_sha']}\n"
        f"checkout Git SHA:   {resolved_provenance.get('checkout_git_sha')}\n"
        "```\n\n"
    )
    marker = "`VERIFICATION ONLY; FIRST-ORDER RUSANOV; CFL 0.10; GATE P2 FALSE`\n\n"
    if marker not in original:
        raise HEMPipelineMeshEvidenceError(
            "mesh Markdown report does not contain the expected scope marker"
        )
    markdown_path.write_text(
        original.replace(marker, marker + traceability, 1),
        encoding="utf-8",
    )
    return {
        "analysis_identity": identity,
        "provenance": resolved_provenance,
    }


def write_traceable_pipeline_mesh_sensitivity_artifacts(
    output_dir: str | Path,
) -> tuple[HEMPipelineMeshSensitivityResult, dict[str, Path], dict[str, object]]:
    """Execute the fixed matrix and emit the traceable authoritative bundle."""

    result, paths = write_pipeline_mesh_sensitivity_artifacts(output_dir)
    traceability = add_traceability(paths)
    return result, paths, traceability


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed Stage 7 mesh matrix and emit traceable authoritative evidence."
        )
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result, paths, traceability = write_traceable_pipeline_mesh_sensitivity_artifacts(
        args.output_dir
    )
    print(json.dumps({**result.summary(), **traceability}, indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
