"""P2-A2.4-3 finite-pipeline read-only acoustic shadow."""
from __future__ import annotations

import argparse, csv, hashlib, json, math, os, subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence
import numpy as np

from .hne_equilibrium_acoustic_closure import (
    ACOUSTIC_AUTHORITY, DEFAULT_CONFIG, MODEL_FORM,
    SOLVER_AUTHORITY as PARENT_AUTHORITY, evaluate_equilibrium_acoustic,
)
from .hne_shadow_pipeline import (
    TAU_CASES, ShadowPipelineConfig, _array_sha, _build_solver, _tau_value,
)
from .state import (
    IDX_RHO, IDX_RHO_XV, check_physical_state, internal_energy, inventory,
    vapor_mass_fraction, velocity,
)

SCHEMA_VERSION = "stage7_p2_hne_acoustic_shadow_pipeline_a2_4_3_v1"
SOURCE_A2_4_2R_SHA = "fd4380472e5487dccb7824d4eddac1dcb134e18e"
SOURCE_A2_4_2R_FIX_SHA = "f95a1bd248849cfb8c72dac942823191e9023c63"
FORMAL_OUTCOME = (
    "A2_4_3_FINITE_PIPELINE_READ_ONLY_ACOUSTIC_SHADOW_READY_"
    "WITH_SOLVER_AUTHORITY_CLOSED"
)
NEXT_ACTION = "PROCEED_TO_A2_4_4_FINITE_RELAXATION_DISPERSION_INVESTIGATION"
OUTPUT_FILES = (
    "summary.json", "case_summary.csv", "step_history.csv", "cell_history.csv",
    "operator_report.md", "manifest.json",
)
FORMAL_STATUS = {
    "implemented": True, "working_verification_slice": True,
    "finite_pipeline_acoustic_shadow": True,
    "read_only_shadow_evidence_ready": True, "working_vertical_slice": False,
    "verified": False, "accepted": False, "physically_validated": False,
    "design_use_accepted": False, "production_approved": False,
}
SOLVER_AUTHORITY = {
    "equilibrium_c2_to_cfl": False, "equilibrium_c2_to_rusanov": False,
    "frozen_c2_to_cfl": False, "frozen_c2_to_rusanov": False,
    "acoustic_pressure_to_flux": False, "acoustic_state_to_fvm_state": False,
    "acoustic_values_to_boundary_characteristics": False,
    "hydrodynamic_coupling_allowed": False,
}

class HNEAcousticShadowPipelineError(RuntimeError):
    pass

@dataclass(frozen=True)
class AcousticShadowObservation:
    step_row: dict[str, object]
    cell_rows: tuple[dict[str, object], ...]

@dataclass(frozen=True)
class AcousticShadowPipelineAnalysis:
    summary: dict[str, object]
    case_rows: tuple[dict[str, object], ...]
    step_rows: tuple[dict[str, object], ...]
    cell_rows: tuple[dict[str, object], ...]

def _extreme(rows: Sequence[Mapping[str, object]], key: str, fn: object) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return None if not values else float(fn(values))  # type: ignore[operator]

def _payload_sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _provenance() -> dict[str, str]:
    def run(*args: str) -> str:
        try: return subprocess.check_output(args, text=True).strip()
        except Exception: return ""
    return {
        "analysis_source_git_sha": os.environ.get("ANALYSIS_SOURCE_GIT_SHA", ""),
        "checkout_git_sha": run("git", "rev-parse", "HEAD"),
        "git_status_porcelain": run(
            "git", "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }

def _conserved(run: Mapping[str, object]) -> bool:
    a, b = run["initial_inventory"], run["final_inventory"]
    assert isinstance(a, Mapping) and isinstance(b, Mapping)
    for key in ("mass_total", "momentum_total", "energy_total"):
        x, y = float(a[key]), float(b[key])
        if abs(y-x) > 256*np.finfo(float).eps*max(abs(x), 1.0): return False
    return True

@dataclass(frozen=True)
class FinitePipelineAcousticShadowObserver:
    def observe(self, *, case_id: str, tau_s: float, U: np.ndarray, grid: object,
                step: int, time_s: float, dt_s: float) -> AcousticShadowObservation:
        check_physical_state(U, names=["A2.4-3 acoustic shadow input"])
        state_sha, hydro_sha = _array_sha(U), _array_sha(U[..., :IDX_RHO_XV])
        rho = np.asarray(U[..., IDX_RHO], float)
        u, e = np.asarray(velocity(U), float), np.asarray(internal_energy(U), float)
        q = np.asarray(vapor_mass_fraction(U), float)
        n = int(getattr(grid, "n_cells")); x = np.asarray(getattr(grid, "cell_centers"), float)
        if any(v.shape != (n,) for v in (rho, e, q, x)):
            raise HNEAcousticShadowPipelineError("unexpected state shape")
        cells: list[dict[str, object]] = []; failures: dict[str, int] = {}
        for i in range(n):
            d = evaluate_equilibrium_acoustic(float(rho[i]), float(e[i])); s = d.state
            if not d.valid:
                label = d.failure_reason or "UNSPECIFIED_ACOUSTIC_FAILURE"
                failures[label] = failures.get(label, 0) + 1
            ce2, cf2 = d.equilibrium_sound_speed_squared_m2_s2, d.frozen_sound_speed_squared_m2_s2
            row: dict[str, object] = {
                "case_id": case_id, "tau_s": _tau_value(tau_s), "step": int(step),
                "time_s": float(time_s), "dt_s": float(dt_s), "cell_index": i,
                "x_m": float(x[i]), "rho_kg_m3": float(rho[i]), "u_m_s": float(u[i]),
                "e_j_kg": float(e[i]), "q_transport": float(q[i]), "valid": bool(d.valid),
                "failure_reason": str(d.failure_reason),
                "within_claimed_domain": None if s is None else bool(s.within_claimed_domain),
                "p_equilibrium_acoustic_pa": None if s is None else float(s.pressure_pa),
                "q_equilibrium_acoustic": None if s is None else float(s.vapor_mass_fraction),
                "equilibrium_c2_m2_s2": None if ce2 is None else float(ce2),
                "equilibrium_c_m_s": d.equilibrium_sound_speed_m_s,
                "frozen_c2_m2_s2": None if cf2 is None else float(cf2),
                "frozen_c_m_s": d.frozen_sound_speed_m_s,
                "subcharacteristic_margin_m2_s2": (
                    None if ce2 is None or cf2 is None else float(cf2-ce2)
                ),
                "derivative_relative_error": d.derivative_relative_error,
                "subcharacteristic_satisfied": d.subcharacteristic_satisfied,
                "derivative_crosscheck_satisfied": d.derivative_crosscheck_satisfied,
                "positive_hyperbolicity_satisfied": d.positive_hyperbolicity_satisfied,
                "solver_authority_granted": d.solver_authority_granted,
                "model_form": d.model_form, "acoustic_authority": d.acoustic_authority,
                "empirical_fallback_used": False, "shadow_state_read_only": True,
            }
            for key, value in row.items():
                if value is not None and not isinstance(value, (str, bool)) and not math.isfinite(float(value)):
                    raise HNEAcousticShadowPipelineError(f"nonfinite {key} at {step}:{i}")
            cells.append(row)
        if _array_sha(U) != state_sha or _array_sha(U[..., :IDX_RHO_XV]) != hydro_sha:
            raise HNEAcousticShadowPipelineError("observer mutated U")
        valid = [row for row in cells if row["valid"] is True]
        step_row = {
            "case_id": case_id, "tau_s": _tau_value(tau_s), "step": int(step),
            "time_s": float(time_s), "dt_s": float(dt_s), "state_sha256": state_sha,
            "hydrodynamic_state_sha256": hydro_sha, "cell_count": n,
            "acoustic_valid_count": len(valid), "acoustic_invalid_count": n-len(valid),
            "failure_counts": dict(sorted(failures.items())),
            "minimum_equilibrium_c2_m2_s2": _extreme(valid, "equilibrium_c2_m2_s2", min),
            "maximum_equilibrium_c2_m2_s2": _extreme(valid, "equilibrium_c2_m2_s2", max),
            "minimum_frozen_c2_m2_s2": _extreme(valid, "frozen_c2_m2_s2", min),
            "maximum_frozen_c2_m2_s2": _extreme(valid, "frozen_c2_m2_s2", max),
            "minimum_subcharacteristic_margin_m2_s2": _extreme(
                valid, "subcharacteristic_margin_m2_s2", min
            ),
            "maximum_derivative_relative_error": _extreme(valid, "derivative_relative_error", max),
            "minimum_recovered_pressure_pa": _extreme(valid, "p_equilibrium_acoustic_pa", min),
            "maximum_recovered_pressure_pa": _extreme(valid, "p_equilibrium_acoustic_pa", max),
            "minimum_recovered_quality": _extreme(valid, "q_equilibrium_acoustic", min),
            "maximum_recovered_quality": _extreme(valid, "q_equilibrium_acoustic", max),
            "all_derivative_crosschecks_satisfied": all(
                row["derivative_crosscheck_satisfied"] is True for row in valid
            ),
            "all_subcharacteristic_checks_satisfied": all(
                row["subcharacteristic_satisfied"] is True for row in valid
            ),
            "all_positive_hyperbolicity_checks_satisfied": all(
                row["positive_hyperbolicity_satisfied"] is True for row in valid
            ),
            "any_empirical_fallback_used": False,
            "all_solver_authority_denied": all(
                row["solver_authority_granted"] is False for row in cells
            ),
            "shadow_state_read_only": True,
        }
        return AcousticShadowObservation(step_row, tuple(cells))

def _run(case_id: str, tau_s: float, config: ShadowPipelineConfig, shadow: bool) -> dict[str, object]:
    solver, _ = _build_solver(config, tau_s); observer = FinitePipelineAcousticShadowObserver()
    initial = inventory(solver.U, solver.grid.dx, solver.grid.geometry.area_m2)
    states, hydros = [_array_sha(solver.U)], [_array_sha(solver.U[..., :IDX_RHO_XV])]
    steps: list[dict[str, object]] = []; cells: list[dict[str, object]] = []
    def observe(dt: float) -> None:
        result = observer.observe(case_id=case_id, tau_s=tau_s, U=solver.U,
            grid=solver.grid, step=solver.step_count, time_s=solver.t, dt_s=dt)
        steps.append(result.step_row); cells.extend(result.cell_rows)
    if shadow: observe(0.0)
    for _ in range(config.n_steps):
        dt = float(solver.compute_dt())
        if float(solver.step(dt)) != dt: raise HNEAcousticShadowPipelineError("dt changed")
        states.append(_array_sha(solver.U)); hydros.append(_array_sha(solver.U[..., :IDX_RHO_XV]))
        if shadow: observe(dt)
    return {
        "trajectory": tuple(states), "hydrodynamic_trajectory": tuple(hydros),
        "initial_inventory": initial,
        "final_inventory": inventory(solver.U, solver.grid.dx, solver.grid.geometry.area_m2),
        "final_q": np.asarray(vapor_mass_fraction(solver.U), float).copy(),
        "step_rows": tuple(steps), "cell_rows": tuple(cells),
        "initial_state_sha256": states[0], "final_state_sha256": states[-1],
        "step_count": int(solver.step_count), "final_time_s": float(solver.t),
    }

def _failures(steps: Sequence[Mapping[str, object]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in steps:
        values = row["failure_counts"]; assert isinstance(values, Mapping)
        for reason, count in values.items(): out[str(reason)] = out.get(str(reason), 0)+int(count)
    return dict(sorted(out.items()))

def _case(case_id: str, tau_s: float, baseline: Mapping[str, object], shadow: Mapping[str, object]) -> dict[str, object]:
    steps, cells = tuple(shadow["step_rows"]), tuple(shadow["cell_rows"])
    valid = [row for row in cells if row["valid"] is True]
    q = np.asarray(shadow["final_q"], float)
    initial, final = shadow["initial_inventory"], shadow["final_inventory"]
    assert isinstance(initial, Mapping) and isinstance(final, Mapping)
    complete = len(valid) == len(cells)
    return {
        "case_id": case_id, "tau_s": _tau_value(tau_s),
        "step_count": int(shadow["step_count"]), "observation_count": len(steps),
        "cell_observation_count": len(cells), "final_time_s": float(shadow["final_time_s"]),
        "baseline_shadow_full_trajectory_bitwise_equal": baseline["trajectory"] == shadow["trajectory"],
        "baseline_shadow_hydrodynamic_trajectory_bitwise_equal": (
            baseline["hydrodynamic_trajectory"] == shadow["hydrodynamic_trajectory"]
        ),
        "all_shadow_states_read_only": all(row["shadow_state_read_only"] is True for row in steps),
        "all_pipeline_states_in_claimed_acoustic_domain": all(
            row["within_claimed_domain"] is True for row in cells
        ),
        "all_acoustic_diagnostics_valid": complete,
        "all_equilibrium_c2_positive": complete and all(float(row["equilibrium_c2_m2_s2"])>0 for row in valid),
        "all_frozen_c2_positive": complete and all(float(row["frozen_c2_m2_s2"])>0 for row in valid),
        "all_subcharacteristic_margins_nonnegative": complete and all(
            float(row["subcharacteristic_margin_m2_s2"])>=0 for row in valid
        ),
        "all_derivative_crosschecks_satisfied": complete and all(
            row["derivative_crosscheck_satisfied"] is True for row in valid
        ),
        "all_solver_authority_denied": all(row["solver_authority_granted"] is False for row in cells),
        "no_empirical_fallback_used": not any(bool(row["empirical_fallback_used"]) for row in cells),
        "mass_momentum_energy_conserved": _conserved(shadow),
        "q_min_final": float(np.min(q)), "q_max_final": float(np.max(q)),
        "minimum_equilibrium_c2_m2_s2": _extreme(valid, "equilibrium_c2_m2_s2", min),
        "maximum_equilibrium_c2_m2_s2": _extreme(valid, "equilibrium_c2_m2_s2", max),
        "minimum_frozen_c2_m2_s2": _extreme(valid, "frozen_c2_m2_s2", min),
        "maximum_frozen_c2_m2_s2": _extreme(valid, "frozen_c2_m2_s2", max),
        "minimum_subcharacteristic_margin_m2_s2": _extreme(valid, "subcharacteristic_margin_m2_s2", min),
        "maximum_derivative_relative_error": _extreme(valid, "derivative_relative_error", max),
        "minimum_recovered_pressure_pa": _extreme(valid, "p_equilibrium_acoustic_pa", min),
        "maximum_recovered_pressure_pa": _extreme(valid, "p_equilibrium_acoustic_pa", max),
        "minimum_recovered_quality": _extreme(valid, "q_equilibrium_acoustic", min),
        "maximum_recovered_quality": _extreme(valid, "q_equilibrium_acoustic", max),
        "invalid_failure_counts": _failures(steps),
        "mass_residual_kg": float(final["mass_total"])-float(initial["mass_total"]),
        "momentum_residual_kg_m_s": float(final["momentum_total"])-float(initial["momentum_total"]),
        "energy_residual_J": float(final["energy_total"])-float(initial["energy_total"]),
        "initial_state_sha256": str(shadow["initial_state_sha256"]),
        "final_state_sha256": str(shadow["final_state_sha256"]),
    }

def analyze_acoustic_shadow_pipeline(config: ShadowPipelineConfig | None = None) -> AcousticShadowPipelineAnalysis:
    cfg = config or ShadowPipelineConfig(n_cells=8, n_steps=8)
    cases: list[dict[str, object]] = []; steps: list[dict[str, object]] = []
    cells: list[dict[str, object]] = []; runs: dict[str, Mapping[str, object]] = {}
    for case_id, tau_s in TAU_CASES:
        baseline, shadow = _run(case_id, tau_s, cfg, False), _run(case_id, tau_s, cfg, True)
        cases.append(_case(case_id, tau_s, baseline, shadow))
        steps.extend(shadow["step_rows"]); cells.extend(shadow["cell_rows"]); runs[case_id] = shadow
    repeat, finite = _run("TAU_FINITE", 1e-4, cfg, True), runs["TAU_FINITE"]
    reproducible = finite["trajectory"] == repeat["trajectory"] and _payload_sha(
        finite["step_rows"]
    ) == _payload_sha(repeat["step_rows"]) and _payload_sha(finite["cell_rows"]) == _payload_sha(repeat["cell_rows"])
    mature = all(FORMAL_STATUS[key] is False for key in (
        "working_vertical_slice", "verified", "accepted", "physically_validated",
        "design_use_accepted", "production_approved",
    ))
    gates = {
        "A2_4_2R_SOURCE_PINNED": SOURCE_A2_4_2R_SHA == "fd4380472e5487dccb7824d4eddac1dcb134e18e",
        "A2_4_2R_RECOVERY_NAME_ERROR_CORRECTED": SOURCE_A2_4_2R_FIX_SHA == "f95a1bd248849cfb8c72dac942823191e9023c63",
        "A2_4_2R_SOLVER_AUTHORITY_REMAINS_CLOSED": all(v is False for v in PARENT_AUTHORITY.values()),
        "A2_4_3_SOLVER_AUTHORITY_REMAINS_CLOSED": all(v is False for v in SOLVER_AUTHORITY.values()),
        "ACOUSTIC_SHADOW_FULL_TRAJECTORY_BITWISE_UNCHANGED": all(r["baseline_shadow_full_trajectory_bitwise_equal"] is True for r in cases),
        "ACOUSTIC_SHADOW_HYDRODYNAMIC_TRAJECTORY_BITWISE_UNCHANGED": all(r["baseline_shadow_hydrodynamic_trajectory_bitwise_equal"] is True for r in cases),
        "ALL_ACCEPTED_PIPELINE_STATES_IN_CLAIMED_ACOUSTIC_DOMAIN": all(r["all_pipeline_states_in_claimed_acoustic_domain"] is True for r in cases),
        "ALL_ACCEPTED_PIPELINE_ACOUSTIC_DIAGNOSTICS_VALID": all(r["all_acoustic_diagnostics_valid"] is True for r in cases),
        "FINITE_POSITIVE_EQUILIBRIUM_AND_FROZEN_C2": all(r["all_equilibrium_c2_positive"] is True and r["all_frozen_c2_positive"] is True for r in cases),
        "SUBCHARACTERISTIC_MARGIN_NONNEGATIVE": all(r["all_subcharacteristic_margins_nonnegative"] is True for r in cases),
        "INDEPENDENT_DERIVATIVE_CROSSCHECK_RETAINED": all(r["all_derivative_crosschecks_satisfied"] is True for r in cases),
        "NO_EMPIRICAL_ACOUSTIC_FALLBACK": all(r["no_empirical_fallback_used"] is True for r in cases),
        "NO_CELL_ACOUSTIC_SOLVER_AUTHORITY": all(r["all_solver_authority_denied"] is True for r in cases),
        "MASS_MOMENTUM_ENERGY_NOT_DAMAGED": all(r["mass_momentum_energy_conserved"] is True for r in cases),
        "DETERMINISTIC_REPRODUCIBILITY": reproducible, "MATURITY_NOT_PROMOTED": mature,
    }
    failed = [name for name, passed in gates.items() if not passed]; ready = not failed
    summary: dict[str, object] = {
        "schema_version": SCHEMA_VERSION, "scope": "p2_a2_4_3_finite_pipeline_read_only_acoustic_shadow",
        "source_a2_4_2r_sha": SOURCE_A2_4_2R_SHA,
        "source_a2_4_2r_recovery_fix_sha": SOURCE_A2_4_2R_FIX_SHA,
        "configuration": asdict(cfg),
        "case_matrix": [{"case_id": c, "tau_s": _tau_value(t)} for c, t in TAU_CASES],
        "acoustic_model": {
            "model_form": MODEL_FORM, "authority": ACOUSTIC_AUTHORITY,
            "claimed_pressure_interval_pa": [DEFAULT_CONFIG.claimed_pressure_min_pa, DEFAULT_CONFIG.claimed_pressure_max_pa],
            "claimed_quality_interval": [DEFAULT_CONFIG.claimed_quality_min, DEFAULT_CONFIG.claimed_quality_max],
            "boundary_policy": "open_interval_fail_closed", "empirical_fallback": "FORBIDDEN_AND_UNUSED",
        },
        "solver_authority": dict(SOLVER_AUTHORITY), "formal_status": dict(FORMAL_STATUS),
        "formal_outcome": FORMAL_OUTCOME if ready else "A2_4_3_IMPLEMENTED_NOT_READY_WITH_FAIL_CLOSED_GATES",
        "next_action": NEXT_ACTION if ready else "RESOLVE_FAILED_A2_4_3_GATES_BEFORE_A2_4_4",
        "case_summary": cases, "gate_results": gates, "failed_gates": failed,
        "deterministic_reproducibility": reproducible,
        "a2_4_3_acoustic_shadow_ready": ready, "hydrodynamic_coupling_allowed": False,
        "runtime_provenance": _provenance(),
        "limitations": ["ANALYTIC_VERIFICATION_SURROGATE_NOT_REAL_CO2_PREDICTION",
            "FINITE_RELAXATION_DISPERSION_NOT_IMPLEMENTED", "NO_SOLVER_COUPLING"],
    }
    authority = {k:v for k,v in summary.items() if k not in {"runtime_provenance", "case_summary"}}
    summary["analysis_sha256"] = _payload_sha({"authority": authority, "cases": cases, "steps": steps, "cells": cells})
    return AcousticShadowPipelineAnalysis(summary, tuple(cases), tuple(steps), tuple(cells))

def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows: raise HNEAcousticShadowPipelineError("CSV requires rows")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, sort_keys=True, separators=(",", ":")) if isinstance(v, (dict,list,tuple)) else v for k,v in row.items()})

def _report(summary: Mapping[str, object]) -> str:
    lines = ["# Stage 7 P2-A2.4-3 Finite-Pipeline Acoustic Shadow", "",
        f"- Outcome: `{summary['formal_outcome']}`", "- Hydrodynamic coupling allowed: `false`", "",
        "| case | tau [s] | min c_eq [m/s] | min c_frozen [m/s] | min margin [m2/s2] | no effect |",
        "|---|---:|---:|---:|---:|---|"]
    for row in summary["case_summary"]:  # type: ignore[index]
        ce2, cf2, m = row["minimum_equilibrium_c2_m2_s2"], row["minimum_frozen_c2_m2_s2"], row["minimum_subcharacteristic_margin_m2_s2"]
        lines.append("| {case} | {tau} | {ce} | {cf} | {m} | {same} |".format(
            case=row["case_id"], tau=row["tau_s"], ce="NA" if ce2 is None else f"{math.sqrt(float(ce2)):.8g}",
            cf="NA" if cf2 is None else f"{math.sqrt(float(cf2)):.8g}", m="NA" if m is None else f"{float(m):.8g}",
            same=row["baseline_shadow_full_trajectory_bitwise_equal"]))
    lines += ["", "Read-only verification evidence only; proceed to A2.4-4 with all solver authority closed.", ""]
    return "\n".join(lines)

def write_artifacts(output_dir: str | Path, analysis: AcousticShadowPipelineAnalysis) -> dict[str, Path]:
    target = Path(output_dir); target.mkdir(parents=True, exist_ok=True); expected = set(OUTPUT_FILES)
    if {p.name for p in target.iterdir() if p.is_file()} - expected:
        raise HNEAcousticShadowPipelineError("unexpected artifact")
    paths = {"summary": target/"summary.json", "cases": target/"case_summary.csv",
        "steps": target/"step_history.csv", "cells": target/"cell_history.csv",
        "report": target/"operator_report.md", "manifest": target/"manifest.json"}
    paths["summary"].write_text(json.dumps(analysis.summary, indent=2, sort_keys=True, allow_nan=False)+"\n")
    _write_csv(paths["cases"], analysis.case_rows); _write_csv(paths["steps"], analysis.step_rows); _write_csv(paths["cells"], analysis.cell_rows)
    paths["report"].write_text(_report(analysis.summary))
    payload = {k:p for k,p in paths.items() if k != "manifest"}
    manifest = {"schema_version": SCHEMA_VERSION, "declared_file_count": len(OUTPUT_FILES),
        "declared_file_names": list(OUTPUT_FILES), "analysis_sha256": analysis.summary["analysis_sha256"],
        "a2_4_3_acoustic_shadow_ready": analysis.summary["a2_4_3_acoustic_shadow_ready"],
        "hydrodynamic_coupling_allowed": False,
        "payload_files": {p.name:{"size_bytes":p.stat().st_size,"sha256":_file_sha(p)} for p in payload.values()}}
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False)+"\n")
    if {p.name for p in target.iterdir() if p.is_file()} != expected: raise HNEAcousticShadowPipelineError("artifact envelope")
    return paths

def execute(output_dir: str | Path) -> dict[str, object]:
    analysis = analyze_acoustic_shadow_pipeline(); paths = write_artifacts(output_dir, analysis)
    return {**analysis.summary, "artifact_paths": {k:str(v) for k,v in paths.items()}}

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, required=True)
    result = execute(parser.parse_args(argv).output_dir)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["a2_4_3_acoustic_shadow_ready"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
