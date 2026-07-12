"""Formal report generator for CoolProp small-amplitude wave verification.

Example (PowerShell compatible)::

    python -c "from liquid_gas_transient.reporting_wave_verification import generate_coolprop_small_amplitude_wave_verification_report; print(generate_coolprop_small_amplitude_wave_verification_report(sweep_metrics_path='verification/coolprop_small_amplitude_wave_sweep_final_v1/coolprop_small_amplitude_wave_sweep_sweep_metrics.json', sweep_summary_path='verification/coolprop_small_amplitude_wave_sweep_final_v1/coolprop_small_amplitude_wave_sweep_sweep_summary.csv', artifact_root='verification/coolprop_small_amplitude_wave_sweep_final_v1', output_path='verification/coolprop_small_amplitude_wave_sweep_final_v1/coolprop_small_amplitude_wave_verification_report_v1.md'))"

This report is a technical interpretation document generated from existing
sweep metrics/summary artifacts.  It does not rerun CoolProp or the FVM solver.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform as _platform
import subprocess
import sys
from typing import Any

OUTPUT_VERSION = "coolprop_small_amplitude_wave_verification_report_v1"
FORBIDDEN_REPORT_PHRASES = (
    "validated model",
    "approved for design use",
    "production-ready thermodynamic model",
    "exact solution",
    "fully converged waveform",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _fmt(v: Any) -> str:
    if v is None or v == "":
        return "not available"
    if isinstance(v, bool):
        return "True" if v else "False"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    if x == 0.0:
        return "0"
    if abs(x) >= 1e4 or abs(x) < 1e-3:
        return f"{x:.6g}"
    return f"{x:.6f}".rstrip("0").rstrip(".")


def _as_runs(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    runs = metrics.get("runs")
    if isinstance(runs, list):
        return [r for r in runs if isinstance(r, dict)]
    rows = metrics.get("summary_rows")
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    return []


def _traceability_value(metrics: dict[str, Any], key: str) -> str:
    value = metrics.get(key)
    if value not in (None, ""):
        return _fmt(value)
    values = []
    seen = set()
    for run in _as_runs(metrics):
        rv = run.get(key)
        if rv in (None, ""):
            continue
        rendered = _fmt(rv)
        if rendered not in seen:
            seen.add(rendered)
            values.append(rendered)
    if not values:
        return "not available"
    if len(values) == 1:
        return values[0]
    return "inconsistent: " + ", ".join(sorted(values))


def _case_ids(metrics: dict[str, Any], summary_rows: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for source in (metrics.get("run_plan", []), metrics.get("runs", []), metrics.get("summary_rows", []), summary_rows):
        if not isinstance(source, list):
            continue
        for row in source:
            if isinstance(row, dict) and row.get("case_id") and row.get("case_id") not in ids:
                ids.append(str(row["case_id"]))
    return ids


def _rel_link(path: Path, output_path: Path) -> str:
    try:
        rel = path.resolve().relative_to(output_path.parent.resolve())
    except ValueError:
        rel = path
    return str(rel).replace("\\", "/")


def _md_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_fmt(c) for c in row) + " |")
    return lines


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _git_commit() -> str:
    try:
        cp = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path.cwd(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return cp.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _provenance(metrics_path: Path, summary_path: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": _platform.platform(),
        "numpy_version": _package_version("numpy"),
        "coolprop_version": _package_version("CoolProp"),
        "matplotlib_version": _package_version("matplotlib"),
        "git_commit_hash": _git_commit(),
        "source_metrics_path": str(metrics_path),
        "source_summary_path": str(summary_path),
        "finest_grid_comparison_reference": metrics.get("finest_grid_comparison_reference", "unknown"),
        "output_version": OUTPUT_VERSION,
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _artifact_manifest(artifact_root: Path | None, metrics_path: Path, summary_path: Path, output_path: Path, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = {metrics_path.resolve(), summary_path.resolve(), output_path.resolve()}
    if artifact_root:
        root = artifact_root.resolve()
        for pat in ("*sweep_report.md", "*sweep_summary.csv", "*mesh_overlay*.png", "*cfl_overlay*.png", "*speed_error*.png", "*amplitude_ratio*.png", "*fwhm_broadening*.png", "*waveform_difference*.png"):
            candidates.update(p.resolve() for p in root.glob(pat) if p.is_file())
        candidates.update(p.resolve() for p in root.rglob("*comparison*.png") if p.is_file())
        for p in metrics.get("generated_plots", []) or []:
            pp = (root / p).resolve()
            if pp.exists():
                candidates.add(pp)
    rows = []
    base = artifact_root.resolve() if artifact_root else output_path.parent.resolve()
    for p in sorted(candidates):
        if not p.exists() or not p.is_file():
            continue
        try:
            rel = p.relative_to(base)
        except ValueError:
            rel = p
        rows.append({"relative_path": str(rel).replace("\\", "/"), "file_size_bytes": p.stat().st_size, "sha256": _sha256(p)})
    return rows


def _select_rows(summary_rows: list[dict[str, Any]], metrics: dict[str, Any], group: str) -> list[dict[str, Any]]:
    ids = {r.get("case_id") for r in metrics.get("mesh_comparison_summary_rows", [])} if group == "mesh" else set()
    if group == "cfl":
        ids = {p["case_id"] for p in metrics.get("run_plan", []) if "cfl_comparison" in p.get("comparison_groups", [])}
    if not ids and group == "mesh":
        cfl = str(metrics.get("run_plan", [{}])[0].get("cfl", "0.5"))
        ids = {r.get("case_id") for r in summary_rows if str(r.get("cfl")) == cfl}
    return sorted([r for r in summary_rows if r.get("case_id") in ids], key=lambda r: (float(r.get("dx_m", 0) or 0), r.get("case_id", "")), reverse=(group == "mesh"))


def _figure_lines(artifact_root: Path | None, output_path: Path, expected: list[tuple[str, str]]) -> list[str]:
    lines = []
    if artifact_root is None:
        return ["- artifact_root が指定されていないため、図リンクは生成していません。"]
    emitted: set[tuple[str, str]] = set()
    for label, pattern in expected:
        found = sorted(p for p in artifact_root.glob(pattern) if p.is_file())
        if not found:
            lines.append(f"- {label}: not found / not included（壊れたMarkdown linkは生成しません）")
            continue
        for p in found:
            rels = _rel_link(p, output_path)
            key = (label, rels)
            if key in emitted:
                continue
            emitted.add(key)
            lines.append(f"- {label}: [{rels}]({rels})")
    return lines


def _probe_artifact_lines(artifact_root: Path | None, output_path: Path, case_ids: list[str]) -> list[str]:
    if artifact_root is None:
        return []
    pngs = sorted(p for p in artifact_root.rglob("*_probe_pressure_history.png") if p.is_file())
    csvs = sorted(p for p in artifact_root.rglob("*_probe_history.csv") if p.is_file())

    def for_case(paths: list[Path], case_id: str) -> list[Path]:
        return [p for p in paths if case_id in p.parts or case_id in p.name or case_id in str(p)]

    lines = ["", "### Probe history artifacts"]
    for case_id in case_ids:
        lines.append(f"- {case_id}:")
        for label, paths in (("probe pressure history", for_case(pngs, case_id)), ("probe history CSV", for_case(csvs, case_id))):
            if not paths:
                lines.append(f"  - {label}: not found / not included（壊れたMarkdown linkは生成しません）")
                continue
            seen: set[str] = set()
            for p in paths:
                rels = _rel_link(p, output_path)
                if rels in seen:
                    continue
                seen.add(rels)
                lines.append(f"  - {label}: [{rels}]({rels})")
    return lines


def generate_coolprop_small_amplitude_wave_verification_report(
    sweep_metrics_path: str | Path,
    sweep_summary_path: str | Path,
    output_path: str | Path,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Generate a Markdown technical verification report from sweep artifacts."""
    metrics_path = Path(sweep_metrics_path)
    summary_path = Path(sweep_summary_path)
    out = Path(output_path)
    root = Path(artifact_root) if artifact_root is not None else None
    metrics = _read_json(metrics_path)
    summary = _read_csv(summary_path)
    prov = _provenance(metrics_path, summary_path, metrics)
    mesh_rows = _select_rows(summary, metrics, "mesh")
    cfl_rows = _select_rows(summary, metrics, "cfl")
    design_status = _traceability_value(metrics, "property_backend_design_status")
    conv = metrics.get("convergence_by_metric", {})

    lines: list[str] = [
        "# CoolProp単相小振幅波 Numerical Verification Report", "",
        "> Guardrail: property_backend_design_status = " + str(design_status) + "; design_evaluation = false; acceptance_gate = false; validation = false。", "",
        "## 1. Executive summary", "",
        "- CoolProp-backed conservative FVM software pathは、入力sweep artifacts上で正常実行として記録されています。",
        "- 静止一様状態保持、単相維持、保存性をhealth checkとして整理します。",
        "- Gaussian pressure pulseのpeak phase speedはCoolProp音速に近い誤差床で評価され、formal convergence orderの対象にはしません。",
        "- centroid / cross-correlation / threshold speed、amplitude retention、FWHM broadening、waveform differenceはmesh refinement観察として整理します。",
        "- 現行schemeには数値拡散が残り、n=400もfinest-grid comparison referenceであって真の解ではありません。",
        "- design-use承認、Validation、二相モデル検証ではありません。", "",
        "## 2. Scope and non-scope", "", "**対象**", "- single-phase CO2 / p0=8 MPa / T0=280 K / small-amplitude Gaussian pulse", "- friction、gravity、local loss、phase changeなし", "- CoolProp backend、conservative FVM", "", "**対象外**", "- design evaluation / backend acceptance / physical Validation", "- HEM/HNE/DVCM、flashing、ESD closure、pump trip、two-phase flow、critical-region verification", "",
        "## 3. Software and property path", "", "CoolProp → property backend → EOS adapter → conservative initialization → FVM solver → probe/full-field diagnostics → budget → artifacts", "",
        "**Traceability**", f"- eos_model: {_traceability_value(metrics, 'eos_model')}", f"- property_backend_name: {_traceability_value(metrics, 'property_backend_name')}", f"- property_backend_design_status: {design_status}", f"- CoolProp version: {_traceability_value(metrics, 'coolprop_version') if _traceability_value(metrics, 'coolprop_version') != 'not available' else _fmt(prov['coolprop_version'])}", f"- output version: {_traceability_value(metrics, 'output_version') if _traceability_value(metrics, 'output_version') != 'not available' else OUTPUT_VERSION}", "",
        "## 4. Governing verification concept", "", "Gaussian pressure pulseに対して u = dp / (rho0*c0) の小振幅音響関係を用い、theoretical sound speed c0、probe positions、reflection-free evaluation windowを基準に到達を比較します。peak、centroid、correlation、thresholdは波形拡散・サンプリング・閾値依存性が異なるため、役割を分けて解釈します。", "",
        "## 5. Test matrix", "", "### Mesh comparison", *_md_table(["case_id","n_cells","dx","CFL","step count","runtime","execution pass","remained single phase","mass relative residual","energy balance relative residual","vapor mass balance relative residual","missing budget fields"], [[r.get('case_id'), r.get('n_cells'), r.get('dx_m'), r.get('cfl'), r.get('step_count'), r.get('runtime_seconds'), r.get('overall_observation_run_pass'), r.get('remained_single_phase'), r.get('budget_mass_relative_residual'), r.get('energy_budget_balance_relative_residual'), r.get('vapor_mass_budget_balance_relative_residual'), r.get('missing_budget_fields')] for r in mesh_rows]), "", "### CFL comparison", *_md_table(["case_id","n_cells","dx","CFL","step count","runtime","execution pass","remained single phase","mass relative residual","energy balance relative residual","vapor mass balance relative residual","missing budget fields"], [[r.get('case_id'), r.get('n_cells'), r.get('dx_m'), r.get('cfl'), r.get('step_count'), r.get('runtime_seconds'), r.get('overall_observation_run_pass'), r.get('remained_single_phase'), r.get('budget_mass_relative_residual'), r.get('energy_budget_balance_relative_residual'), r.get('vapor_mass_budget_balance_relative_residual'), r.get('missing_budget_fields')] for r in cfl_rows]), "",
        "## 6. Conservation and health checks", "", f"- overall_sweep_execution_pass: {_fmt(metrics.get('overall_sweep_execution_pass'))}", "- finite states、positive p/T/rho/c、quality=0、alpha=0、missing budget fieldsは、各run metricsに記録されたhealth checkとして扱います。", "- mass / energy / vapor mass residualは機械精度近傍の保存性確認として整理し、設計保証の表現にはしません。", "",
        "## 7. Phase-speed verification", "", "Primary: interprobe peak speed。Supporting: centroid speed / cross-correlation speed。Diagnostic: threshold crossing speed。", "", *_md_table(["mesh","c0","threshold speed","threshold err","peak speed","peak err","centroid speed","centroid err","corr speed","corr err"], [[r.get('case_id'), r.get('c0'), r.get('interprobe_threshold_speed_m_s'), r.get('interprobe_threshold_speed_relative_error'), r.get('interprobe_peak_speed_m_s'), r.get('interprobe_peak_speed_relative_error'), r.get('interprobe_centroid_speed_m_s'), r.get('interprobe_centroid_speed_relative_error'), r.get('interprobe_cross_correlation_speed_m_s'), r.get('interprobe_cross_correlation_speed_relative_error')] for r in mesh_rows]), "", "peak speedは約1e-5のerror floorまたは非単調挙動として扱い、formal convergence orderの評価対象にしません。", "",
        "## 8. Numerical diffusion / waveform preservation", "", *_md_table(["mesh","amp ratio L/2","amp ratio 3L/4","FWHM L/2","FWHM 3L/4","waveform L1 vs finest","waveform L2 vs finest"], [[r.get('case_id'), r.get('primary_probe_amplitude_ratio_L2'), r.get('primary_probe_amplitude_ratio_3L4'), r.get('primary_probe_fwhm_broadening_ratio_L2'), r.get('primary_probe_fwhm_broadening_ratio_3L4'), r.get('waveform_l1_difference_vs_finest'), r.get('waveform_l2_difference_vs_finest')] for r in mesh_rows]), "", "mesh refinementでamplitude ratio上昇、FWHM broadening低下、waveform difference低下が観察される場合、数値拡散の単調改善を支持します。ただしn=400でも残存波形誤差は否定しません。", "",
        "## 9. Mesh convergence observation", "", f"overall classification: {metrics.get('numerical_convergence_observation', conv.get('overall_classification', 'unknown'))}", "", *_md_table(["metric","classification","local order estimates (diagnostic)"], [[k, v.get('classification') if isinstance(v, dict) else v, ', '.join(_fmt(x) for x in (v.get('optional_local_orders', {}).get('local_order_estimates', []) if isinstance(v, dict) else []))] for k, v in conv.items() if k != 'overall_classification']), "", "local order estimatesは連続mesh間の診断的local estimateであり、formal order verificationではありません。finest-grid comparison referenceは真の解ではなく、参照run自身のwaveform difference = 0は定義による0です。", "",
        "## 10. CFL sensitivity", "", *_md_table(["case_id","n_cells","CFL","runtime","amp ratio L/2","FWHM L/2","peak err","centroid err","corr err"], [[r.get('case_id'), r.get('n_cells'), r.get('cfl'), r.get('runtime_seconds'), r.get('primary_probe_amplitude_ratio_L2'), r.get('primary_probe_fwhm_broadening_ratio_L2'), r.get('interprobe_peak_speed_relative_error'), r.get('interprobe_centroid_speed_relative_error'), r.get('interprobe_cross_correlation_speed_relative_error')] for r in cfl_rows]), "", "CFL=0.5の方が今回のschemeでは振幅保持・FWHM・実行時間で良好な場合があります。CFLを小さくすれば必ず精度が上がるわけではなく、時間積分と空間離散の組合せとして解釈します。CFL=0.5をdesign recommendationとはしません。", "",
        "## 11. Figures and artifact index", "",
    ]
    lines.extend(_figure_lines(root, out, [("mesh overlay", "*mesh_overlay*.png"), ("CFL overlay", "*cfl_overlay*.png"), ("speed error vs dx", "*speed_error*.png"), ("amplitude ratio vs dx", "*amplitude_ratio*.png"), ("FWHM broadening vs dx", "*fwhm_broadening*.png"), ("waveform difference vs finest reference", "*waveform_difference*.png"), ("x-t map", "**/*xt*.png"), ("snapshots", "**/*snapshot*.png")]))
    lines.extend(_probe_artifact_lines(root, out, _case_ids(metrics, summary)))
    lines += ["", "## 12. Verification conclusion", "", "**Verified / supported**", "- software path / execution stability / conservation / single-phase preservation / phase speed / mesh-dependent reduction of numerical diffusion", "", "**Not verified / not approved**", "- complete waveform convergence / design-use mesh requirement / real equipment validation / phase change / two-phase flow / CoolProp design-use acceptance", "", "> Guardrail: property_backend_design_status = " + str(design_status) + "; design_evaluation = false; acceptance_gate = false; validation = false。", "", "## 13. Recommended regression hierarchy", "", "- CI lightweight: n=50または100", "- standard verification: n=200", "- high-cost observation: n=400", "- 今回は正式thresholdを設定しません。", "", "## 14. Next verification action", "", "- 次はboundary reflection verificationを第一候補とします。", "- 候補: linear acoustic / MOC comparison、controlled pressure step、valve operation in single-phase range。", "- 一度に複数へ進まず、小さなverification単位で進めます。", "", "## Provenance", "", *_md_table(["key", "value"], [[k, v] for k, v in prov.items()]), ""]

    text = "\n".join(lines) + "\n"
    lower = text.lower()
    bad = [p for p in FORBIDDEN_REPORT_PHRASES if p in lower]
    if bad:
        raise ValueError(f"forbidden report phrases detected: {bad}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    manifest = _artifact_manifest(root, metrics_path, summary_path, out, metrics)
    manifest_path = out.with_name("coolprop_small_amplitude_wave_verification_manifest_v1.json")
    manifest_path.write_text(json.dumps({"output_version": OUTPUT_VERSION, "artifacts": manifest}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"report_path": str(out), "manifest_path": str(manifest_path), "artifact_count": len(manifest), "provenance": prov, "output_version": OUTPUT_VERSION}


__all__ = ["generate_coolprop_small_amplitude_wave_verification_report", "OUTPUT_VERSION"]
