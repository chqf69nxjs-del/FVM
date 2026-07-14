"""Backfill and validate V-011 aggregate property-backend traceability.

This utility reads existing per-run baseline metrics and updates the aggregate
sweep JSON, CSV, and observation report without rerunning the solver. It is
software/numerical traceability work only and does not change numerical results,
physical Validation status, or design-use status.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _group_contains(row: dict[str, Any], name: str) -> bool:
    groups = str(row.get("comparison_groups", "")).split(";")
    return name in groups


def _run_identity(root: Path, case_id: str) -> dict[str, str]:
    run_dir = root / case_id
    if not run_dir.is_dir():
        raise FileNotFoundError(run_dir)
    candidates = sorted(run_dir.glob("*_metrics.json"))
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one baseline *_metrics.json in {run_dir}, "
            f"found {len(candidates)}"
        )
    metrics = _read_json(candidates[0])
    identity = {
        "property_backend_name": str(metrics.get("property_backend_name", "")),
        "coolprop_version": str(metrics.get("coolprop_version", "")),
        "property_backend_design_status": str(
            metrics.get("property_backend_design_status", "")
        ),
    }
    missing = [key for key, value in identity.items() if not value]
    if missing:
        raise ValueError(
            f"missing backend identity fields in {candidates[0]}: {missing}"
        )
    return identity


def _single_identity(rows: list[dict[str, Any]], key: str) -> str:
    values = {str(row.get(key, "")) for row in rows}
    values.discard("")
    if len(values) != 1:
        raise ValueError(f"inconsistent {key} across sweep runs: {sorted(values)}")
    return next(iter(values))


def _update_report(path: Path, identity: dict[str, str]) -> None:
    if not path.is_file():
        return
    lines = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if not line.startswith("- property_backend_name:")
        and not line.startswith("- coolprop_version:")
    ]
    insertion = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if line.startswith("- formal_accuracy_threshold_applied:")
        ),
        None,
    )
    trace_lines = [
        f"- property_backend_name: {identity['property_backend_name']}",
        f"- coolprop_version: {identity['coolprop_version']}",
    ]
    if insertion is None:
        lines.extend(["", "## Property backend traceability", "", *trace_lines])
    else:
        lines[insertion:insertion] = trace_lines
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def backfill_controlled_pressure_ramp_sweep_traceability(
    *,
    sweep_metrics_path: str | Path,
    sweep_summary_path: str | Path,
    artifact_root: str | Path | None = None,
    sweep_report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Backfill exact backend name/version into existing V-011 aggregates."""

    metrics_path = Path(sweep_metrics_path)
    summary_path = Path(sweep_summary_path)
    root = Path(artifact_root) if artifact_root is not None else metrics_path.parent
    report_path = (
        Path(sweep_report_path)
        if sweep_report_path is not None
        else metrics_path.with_name(
            metrics_path.name.replace("_sweep_metrics.json", "_sweep_report.md")
        )
    )

    metrics = _read_json(metrics_path)
    rows: list[dict[str, Any]] = list(_read_csv(summary_path))
    if int(metrics.get("unique_run_count", 0)) != len(rows):
        raise ValueError("unique_run_count does not match sweep summary rows")

    for row in rows:
        case_id = str(row.get("case_id", ""))
        if not case_id:
            raise ValueError("sweep summary row is missing case_id")
        row.update(_run_identity(root, case_id))

    identity = {
        "property_backend_name": _single_identity(rows, "property_backend_name"),
        "coolprop_version": _single_identity(rows, "coolprop_version"),
        "property_backend_design_status": _single_identity(
            rows, "property_backend_design_status"
        ),
    }
    if identity["property_backend_design_status"] != "not_approved_for_design_use":
        raise ValueError("unexpected property_backend_design_status")

    metrics.update(identity)
    metrics["summary_rows"] = rows
    if isinstance(metrics.get("cfl_observation"), dict):
        metrics["cfl_observation"]["rows"] = [
            row for row in rows if _group_contains(row, "cfl_comparison")
        ]

    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_csv(summary_path, rows)
    _update_report(report_path, identity)

    return {
        **identity,
        "updated_row_count": len(rows),
        "sweep_metrics_path": str(metrics_path),
        "sweep_summary_path": str(summary_path),
        "sweep_report_path": str(report_path),
        "solver_rerun": False,
        "numerical_results_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument(
        "--stem",
        default="coolprop_controlled_pressure_ramp_sweep",
    )
    args = parser.parse_args(argv)
    root = args.artifact_root
    result = backfill_controlled_pressure_ramp_sweep_traceability(
        sweep_metrics_path=root / f"{args.stem}_sweep_metrics.json",
        sweep_summary_path=root / f"{args.stem}_sweep_summary.csv",
        sweep_report_path=root / f"{args.stem}_sweep_report.md",
        artifact_root=root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
