from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
import u3_b2_characteristic_port_root_robustness_v4 as robustness_v4
import u3_b2_characteristic_port_two_l_over_c0 as horizon
from liquid_gas_transient.boundary import ReflectiveBoundary, TransmissiveBoundary
from liquid_gas_transient.config import PipeGeometry
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.solver import FvmSolver
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    CoolPropB2StateProvider,
    CoolPropSinglePhaseEOS,
    build_uniform_initial_state,
    load_b1_contract,
    load_contract,
    normalize_phase,
)
from u3_b2_a1_neutral_endpoint_resume import _solve_neutral_endpoint
from u3_b2_a1_post_endpoint_branch_classification import (
    _classification_diagnostics,
)
from u3_b2_a1_weak_compression_bridge_diagnostic import (
    CHI_MAX,
    MAX_BISECTION_ITERATIONS,
    _positive_scan_offsets,
    _solve_first_bracket,
)
from u3_b2_a1_weak_compression_bridge_one_step import (
    OUTCOME as INCREMENT_2_OUTCOME,
    _build_weak_compression_context,
    _full_wave_row,
    _run_increment_2,
)
from u3_b2_a1_wave_curve_model import CASE_ID, _brackets
from u3_b2_characteristic_port_dynamic_short_metrics import (
    build_step_row,
    inventory,
)
from u3_b2_characteristic_port_dynamic_short_model import DynamicDiagnosticStop


PARENT_SOURCE_SHA = "a9b43a0bc8e2a307f21ac02129a3d62ba3495165"
PARENT_WORKFLOW_RUN = 31602684937
PARENT_JOB = 94133772628
PARENT_ARTIFACT = 9143921347
PARENT_ARTIFACT_SHA256 = (
    "e8ab1e24f9612f1cbad23a128b29835e54ca8eb74525641ff966d64d8e75088d"
)
STARTING_ACCEPTED_SOLVER_STEP = 337
REQUESTED_ACCEPTED_STEPS = 32
FINAL_ACCEPTED_SOLVER_STEP = 369
OUTCOME = "WEAK_COMPRESSION_INCREMENT_3_32_STEP_PASS"
ALLOWED_BRANCHES = {
    "RAREFACTION",
    "NEUTRAL_ENDPOINT",
    "WEAK_COMPRESSION",
}
robustness = robustness_v4.robustness


class WeakCompressionShortRunStop(DynamicDiagnosticStop):
    def __init__(
        self,
        classification: str,
        message: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.classification = classification
        self.diagnostics = diagnostics or {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _inventory_array(values: dict[str, float]) -> np.ndarray:
    return np.asarray(
        [
            values["mass_kg"],
            values["momentum_kg_m_s"],
            values["energy_J"],
            values["vapor_mass_kg"],
        ],
        dtype=float,
    )


def _minimum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return min(values) if values else None


def _maximum(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _max_abs(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [abs(float(row[key])) for row in rows if row.get(key) is not None]
    return max(values) if values else None


def _clear_branch_chatter(history: list[str], candidate: str) -> bool:
    sequence = [*history[-4:], candidate]
    return bool(
        len(sequence) == 5
        and sequence[0] == sequence[2] == sequence[4]
        and sequence[1] == sequence[3]
        and sequence[0] != sequence[1]
        and set(sequence).issubset(ALLOWED_BRANCHES)
    )


def _annotate_positive_row(
    row: dict[str, Any],
    *,
    interior_density_kg_m3: float,
    interior_sound_speed_m_s: float,
    selected_bracket_member: bool = False,
) -> dict[str, Any]:
    item = dict(row)
    offset = float(item["pressure_offset_pa"])
    denominator = float(
        interior_density_kg_m3 * interior_sound_speed_m_s**2
    )
    chi = float(offset / denominator)
    item.update(
        {
            "chi": chi,
            "chi_max": CHI_MAX,
            "within_weak_compression_scope": bool(
                offset == 0.0 or 0.0 < chi <= CHI_MAX
            ),
            "selected_sign_change_bracket_member": bool(
                selected_bracket_member
            ),
        }
    )
    return item


def _positive_pressure_scan(
    *,
    hook: Any,
    U: np.ndarray,
) -> dict[str, Any]:
    reconstruction = hook.provider.reconstruct_from_conserved(U[-1])
    static = reconstruction.static
    allowed_phases = {
        normalize_phase(value)
        for value in diagnostic._family(hook.contract, hook.state_id)[
            "allowed_normalized_phases"
        ]
    }
    velocity_tolerance = float(
        hook.contract["acceptance_tolerances"][
            "velocity_zero_tolerance_m_s"
        ]
    )
    diagnostic.QUADRATURE_ORDER = horizon.ROOT_QUADRATURE_ORDER
    isentrope = diagnostic.Isentrope(float(static.entropy_J_kg_K))
    density = float(static.density_kg_m3)
    sound_speed = float(static.sound_speed_m_s)
    delta_p_max = float(CHI_MAX * density * sound_speed**2)
    offsets = _positive_scan_offsets(delta_p_max)
    cache: dict[float, dict[str, Any]] = {}

    def evaluate_offset(offset_pa: float) -> dict[str, Any]:
        key = float(offset_pa)
        if key not in cache:
            raw = _full_wave_row(
                pressure_pa=float(static.pressure_pa + key),
                static=static,
                isentrope=isentrope,
                hook=hook,
                area_m2=hook.area_m2,
                allowed_phases=allowed_phases,
                velocity_tolerance=velocity_tolerance,
                state_id=hook.state_id,
            )
            cache[key] = _annotate_positive_row(
                raw,
                interior_density_kg_m3=density,
                interior_sound_speed_m_s=sound_speed,
            )
        return dict(cache[key])

    scan_rows = [evaluate_offset(offset) for offset in offsets]
    for index, row in enumerate(scan_rows):
        if not bool(row.get("evaluation_succeeded")):
            raise WeakCompressionShortRunStop(
                "POSITIVE_SCAN_EVALUATION_FAILURE",
                "positive-pressure scan evaluation failed at "
                f"node {index}: {row.get('formal_outcome')} "
                f"{row.get('formal_message')}",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                },
            )
        if not bool(row.get("local_candidate_admissible")):
            raise WeakCompressionShortRunStop(
                "POSITIVE_SCAN_INADMISSIBLE",
                f"positive-pressure scan node {index} is inadmissible",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                },
            )
        residual = row.get("compatibility_residual_kg_s")
        if residual is None or not np.isfinite(float(residual)):
            raise WeakCompressionShortRunStop(
                "POSITIVE_SCAN_NONFINITE_RESIDUAL",
                f"positive-pressure scan node {index} has no finite residual",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                },
            )
        if not bool(row["within_weak_compression_scope"]):
            raise WeakCompressionShortRunStop(
                "POSITIVE_SCAN_SCOPE_FAILURE",
                f"positive-pressure scan node {index} exceeds fixed chi scope",
                {
                    "positive_scan_rows": scan_rows,
                    "delta_p_max_pa": delta_p_max,
                },
            )

    evaluable = _brackets(scan_rows, admissible_only=False)
    admissible = _brackets(scan_rows, admissible_only=True)
    if len(evaluable) != len(admissible):
        raise WeakCompressionShortRunStop(
            "LOCAL_ROOT_INADMISSIBLE",
            "a positive-pressure sign change is evaluable but inadmissible",
            {
                "positive_scan_rows": scan_rows,
                "positive_evaluable_brackets": evaluable,
                "positive_admissible_brackets": admissible,
                "delta_p_max_pa": delta_p_max,
            },
        )
    if len(admissible) > 1:
        raise WeakCompressionShortRunStop(
            "MULTIPLE_LOCAL_ROOTS",
            "multiple positive-pressure sign-change brackets were observed",
            {
                "positive_scan_rows": scan_rows,
                "positive_admissible_brackets": admissible,
                "delta_p_max_pa": delta_p_max,
            },
        )

    selected_offsets: set[float] = set()
    if admissible:
        selected_offsets = {
            float(admissible[0]["lower_offset_pa"]),
            float(admissible[0]["upper_offset_pa"]),
        }
    annotated = [
        {
            **row,
            "selected_sign_change_bracket_member": bool(
                float(row["pressure_offset_pa"]) in selected_offsets
            ),
        }
        for row in scan_rows
    ]
    residuals = [
        float(row["compatibility_residual_kg_s"])
        for row in annotated
    ]
    monotone_nonincreasing = bool(
        len(residuals) >= 2
        and all(
            residuals[index + 1] <= residuals[index]
            for index in range(len(residuals) - 1)
        )
    )
    return {
        "static": static,
        "rows": annotated,
        "evaluate_offset": evaluate_offset,
        "evaluable_brackets": evaluable,
        "admissible_brackets": admissible,
        "sign_change_count": len(admissible),
        "residual_monotone_nonincreasing": monotone_nonincreasing,
        "delta_p_max_pa": delta_p_max,
        "endpoint_residual_kg_s": residuals[0],
        "scope_limit_residual_kg_s": residuals[-1],
    }


def _solve_weak_compression(
    *,
    hook: Any,
    U: np.ndarray,
    solver_time_s: float,
    positive: dict[str, Any],
) -> dict[str, Any]:
    brackets = list(positive["admissible_brackets"])
    if len(brackets) != 1:
        raise WeakCompressionShortRunStop(
            "NO_UNIQUE_WEAK_COMPRESSION_ROOT",
            "Weak Compression requires exactly one positive-pressure bracket",
            positive,
        )
    try:
        root, iterations, final_bracket = _solve_first_bracket(
            bracket=brackets[0],
            evaluate_offset=positive["evaluate_offset"],
            root_tolerance_kg_s=float(
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
        )
    except Exception as exc:
        raise WeakCompressionShortRunStop(
            "ROOT_OR_LEDGER_FAILURE",
            "Weak Compression bisection failed: "
            f"{type(exc).__name__}: {exc}",
            positive,
        ) from exc

    root = dict(root)
    root.update(
        {
            "bisection_iterations": int(iterations),
            "selected_initial_bracket_lower_offset_pa": float(
                brackets[0]["lower_offset_pa"]
            ),
            "selected_initial_bracket_upper_offset_pa": float(
                brackets[0]["upper_offset_pa"]
            ),
            **final_bracket,
        }
    )
    try:
        context = _build_weak_compression_context(
            contract=hook.contract,
            state_id=hook.state_id,
            provider=hook.provider,
            hook=hook,
            outlet_conserved=np.asarray(U[-1], dtype=float),
            solver_time_s=solver_time_s,
            increment_1_root=root,
            increment_1_scan_rows=list(positive["rows"]),
        )
    except Exception as exc:
        raise WeakCompressionShortRunStop(
            "ROOT_OR_LEDGER_FAILURE",
            "Weak Compression root completion failed: "
            f"{type(exc).__name__}: {exc}",
            {
                **positive,
                "weak_compression_root": root,
            },
        ) from exc

    completed_root = context["root"]
    completed_root.update(
        {
            "bisection_iterations": int(iterations),
            "selected_initial_bracket_lower_offset_pa": float(
                brackets[0]["lower_offset_pa"]
            ),
            "selected_initial_bracket_upper_offset_pa": float(
                brackets[0]["upper_offset_pa"]
            ),
            **final_bracket,
        }
    )
    context.update(
        {
            "branch_classification": "WEAK_COMPRESSION",
            "positive_scan_rows": list(positive["rows"]),
            "positive_scan_sign_change_count": 1,
            "positive_scan_residual_monotone_nonincreasing": bool(
                positive["residual_monotone_nonincreasing"]
            ),
            "positive_scan_delta_p_max_pa": float(
                positive["delta_p_max_pa"]
            ),
            "weak_compression_bisection_iterations": int(iterations),
            "positive_pressure_continuation_flux_applied": True,
            "finite_compression_branch_approved": False,
        }
    )
    return context


def _solve_three_branch_boundary(
    *,
    hook: Any,
    U: np.ndarray,
    solver_time_s: float,
) -> dict[str, Any]:
    details = _classification_diagnostics(
        hook=hook,
        U=U,
        solver_time_s=solver_time_s,
    )
    endpoint = dict(details["endpoint"])
    if not bool(endpoint.get("evaluation_succeeded")):
        raise WeakCompressionShortRunStop(
            "ENDPOINT_EVALUATION_FAILURE",
            "neutral endpoint evaluation did not succeed",
            details,
        )
    if not bool(endpoint.get("local_candidate_admissible")):
        raise WeakCompressionShortRunStop(
            "LOCAL_ROOT_INADMISSIBLE",
            "neutral endpoint is outside the retained admissible branch",
            details,
        )

    endpoint_residual = float(endpoint["compatibility_residual_kg_s"])
    endpoint_within = bool(endpoint["root_closure_passed"])
    connected = details["connected_rarefaction"]
    branch: str
    positive: dict[str, Any] | None = None

    if endpoint_within:
        branch = "NEUTRAL_ENDPOINT"
        try:
            context = _solve_neutral_endpoint(
                contract=hook.contract,
                case_id=hook.case_id,
                state_id=hook.state_id,
                provider=hook.provider,
                adapter=hook.adapter,
                area_m2=hook.area_m2,
                outlet_conserved=np.asarray(U[-1], dtype=float),
                solver_time_s=solver_time_s,
            )
        except Exception as exc:
            raise WeakCompressionShortRunStop(
                "ROOT_OR_LEDGER_FAILURE",
                "neutral endpoint completion failed: "
                f"{type(exc).__name__}: {exc}",
                details,
            ) from exc
    else:
        if int(connected["admissible_subsonic_nodes"]) < 2:
            raise WeakCompressionShortRunStop(
                "LOCAL_ROOT_INADMISSIBLE",
                "connected rarefaction scan has fewer than two admissible "
                "subsonic nodes",
                details,
            )
        if not bool(connected["residual_monotone"]):
            raise WeakCompressionShortRunStop(
                "CONNECTED_RAREFACTION_NON_MONOTONE",
                "connected rarefaction residual is not monotone",
                details,
            )
        rarefaction_count = int(connected["sign_change_count"])
        negative_local_count = int(
            details["rarefaction_side_local_sign_change_count"]
        )
        if rarefaction_count > 1 or negative_local_count > 1:
            raise WeakCompressionShortRunStop(
                "MULTIPLE_LOCAL_ROOTS",
                "multiple rarefaction-side roots were observed",
                details,
            )

        positive = _positive_pressure_scan(hook=hook, U=U)
        positive_count = int(positive["sign_change_count"])
        if rarefaction_count == 1 and positive_count == 1:
            raise WeakCompressionShortRunStop(
                "MULTIPLE_LOCAL_ROOTS",
                "admissible root brackets exist on both sides of the endpoint",
                {
                    **details,
                    "positive_scan": positive,
                },
            )
        if rarefaction_count == 1 and positive_count == 0:
            branch = "RAREFACTION"
            try:
                context = horizon._solve_two_l_over_c0_root(
                    contract=hook.contract,
                    case_id=hook.case_id,
                    state_id=hook.state_id,
                    provider=hook.provider,
                    adapter=hook.adapter,
                    area_m2=hook.area_m2,
                    outlet_conserved=np.asarray(U[-1], dtype=float),
                    solver_time_s=solver_time_s,
                    previous_root_pressure_pa=hook._previous_root_pressure_pa,
                )
            except Exception as exc:
                raise WeakCompressionShortRunStop(
                    "ROOT_OR_LEDGER_FAILURE",
                    "rarefaction root completion failed: "
                    f"{type(exc).__name__}: {exc}",
                    {
                        **details,
                        "positive_scan": positive,
                    },
                ) from exc
            if not float(context["root"]["pressure_pa"]) < float(
                context["interior_pressure_pa"]
            ):
                raise WeakCompressionShortRunStop(
                    "BRANCH_JUMP",
                    "selected rarefaction root is not below the endpoint",
                    {
                        **details,
                        "positive_scan": positive,
                    },
                )
        elif rarefaction_count == 0 and negative_local_count == 0 and (
            positive_count == 1
        ):
            branch = "WEAK_COMPRESSION"
            context = _solve_weak_compression(
                hook=hook,
                U=U,
                solver_time_s=solver_time_s,
                positive=positive,
            )
        elif rarefaction_count == 0 and negative_local_count == 1:
            raise WeakCompressionShortRunStop(
                "BRANCH_JUMP",
                "a local rarefaction bracket was observed but the connected "
                "approved scan did not retain it",
                {
                    **details,
                    "positive_scan": positive,
                },
            )
        elif rarefaction_count == 0 and positive_count == 0:
            endpoint_significant_positive = bool(
                endpoint_residual
                > float(robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S)
            )
            scope_residual_positive = bool(
                float(positive["scope_limit_residual_kg_s"]) > 0.0
            )
            if endpoint_significant_positive and scope_residual_positive:
                raise WeakCompressionShortRunStop(
                    "FINITE_COMPRESSION_MODEL_REQUIRED",
                    "the positive-pressure residual remained positive through "
                    "the fixed Weak Compression chi scope",
                    {
                        **details,
                        "positive_scan": positive,
                    },
                )
            raise WeakCompressionShortRunStop(
                "NO_LOCAL_COMPATIBLE_ROOT",
                "neither an approved rarefaction root nor an in-scope Weak "
                "Compression root was found",
                {
                    **details,
                    "positive_scan": positive,
                },
            )
        else:
            raise WeakCompressionShortRunStop(
                "NO_LOCAL_COMPATIBLE_ROOT",
                "the branch classifier reached an unhandled root topology",
                {
                    **details,
                    "positive_scan": positive,
                },
            )

    if branch not in ALLOWED_BRANCHES:
        raise WeakCompressionShortRunStop(
            "UNAPPROVED_BRANCH",
            f"branch {branch!r} is outside the fixed three-branch set",
            details,
        )
    if _clear_branch_chatter(hook.accepted_branch_history, branch):
        raise WeakCompressionShortRunStop(
            "CLEAR_BRANCH_CHATTER",
            "candidate branch forms the fixed five-point A-B-A-B-A pattern",
            {
                **details,
                "accepted_branch_history": list(
                    hook.accepted_branch_history
                ),
                "candidate_branch": branch,
                "candidate_five_point_sequence": [
                    *hook.accepted_branch_history[-4:],
                    branch,
                ],
            },
        )

    root = context["root"]
    root_offset = float(
        root["pressure_pa"] - context["interior_pressure_pa"]
    )
    denominator = float(
        context["interior_density_kg_m3"]
        * context["interior_sound_speed_m_s"] ** 2
    )
    root_chi = float(root_offset / denominator)
    if branch == "WEAK_COMPRESSION" and not 0.0 < root_chi <= CHI_MAX:
        raise WeakCompressionShortRunStop(
            "FINITE_COMPRESSION_MODEL_REQUIRED",
            f"Weak Compression root chi is outside scope: {root_chi}",
            details,
        )
    if branch == "NEUTRAL_ENDPOINT" and root_offset != 0.0:
        raise WeakCompressionShortRunStop(
            "BRANCH_JUMP",
            "neutral endpoint root does not equal the interior pressure",
            details,
        )
    if branch == "RAREFACTION" and not root_offset < 0.0:
        raise WeakCompressionShortRunStop(
            "BRANCH_JUMP",
            "rarefaction root is not below the interior pressure",
            details,
        )

    context.update(
        {
            "branch_classification": branch,
            "endpoint_residual_kg_s": endpoint_residual,
            "endpoint_within_locked_root_mass_tolerance": bool(
                endpoint["within_locked_root_mass_tolerance"]
            ),
            "endpoint_admissible": bool(
                endpoint["local_candidate_admissible"]
            ),
            "endpoint_root_closure_passed": bool(
                endpoint["root_closure_passed"]
            ),
            "retained_root_mass_tolerance_kg_s": float(
                robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
            ),
            "rarefaction_side_local_sign_change_count": int(
                details["rarefaction_side_local_sign_change_count"]
            ),
            "connected_rarefaction_sign_change_count": int(
                connected["sign_change_count"]
            ),
            "connected_rarefaction_residual_monotone": bool(
                connected["residual_monotone"]
            ),
            "connected_rarefaction_stop_reason": connected["stop_reason"],
            "positive_scan_sign_change_count": (
                0 if positive is None else int(positive["sign_change_count"])
            ),
            "positive_scan_rows": (
                [] if positive is None else list(positive["rows"])
            ),
            "positive_scan_residual_monotone_nonincreasing": (
                None
                if positive is None
                else bool(positive["residual_monotone_nonincreasing"])
            ),
            "positive_scan_delta_p_max_pa": (
                None
                if positive is None
                else float(positive["delta_p_max_pa"])
            ),
            "local_scan_rows": list(details["local_scan_rows"]),
            "p_P_minus_p_i_pa": root_offset,
            "root_chi": root_chi,
            "accepted_branch_history_before": list(
                hook.accepted_branch_history
            ),
            "clear_branch_chatter_detected": False,
            "positive_pressure_continuation_flux_applied": bool(
                branch == "WEAK_COMPRESSION"
            ),
            "finite_compression_branch_approved": False,
        }
    )
    return context


class A1WeakCompressionBridgeShortRunHook(horizon.A1TwoLOverC0Hook):
    """Three-branch MODEL_REVIEW hook after the accepted step 337."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.accepted_branch_history: list[str] = ["NEUTRAL_ENDPOINT"]
        self.pending_branch_classification: str | None = None

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        context = _solve_three_branch_boundary(
            hook=self,
            U=U,
            solver_time_s=t,
        )
        self.root_context = context
        self.flux = np.asarray(context["flux"], dtype=float).copy()
        self.pending_branch_classification = str(
            context["branch_classification"]
        )
        self._cache_t = float(t)
        self._cache_outlet = np.asarray(U[-1], dtype=float).copy()
        self.trial_dts_s = []

    def accept_current_root(self) -> None:
        if self.pending_branch_classification is None:
            raise AssertionError("no pending short-run branch classification")
        super().accept_current_root()
        self.accepted_branch_history.append(
            self.pending_branch_classification
        )
        self.pending_branch_classification = None


def _flatten_scan(
    *,
    rows: list[dict[str, Any]],
    requested_solver_step: int,
    solver_time_s: float,
    branch: str,
    scan_kind: str,
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for row in rows:
        flattened.append(
            {
                "requested_solver_step": int(requested_solver_step),
                "solver_time_s": float(solver_time_s),
                "selected_branch": branch,
                "scan_kind": scan_kind,
                **row,
            }
        )
    return flattened


def _root_evidence_row(
    *,
    context: dict[str, Any],
    requested_solver_step: int,
) -> dict[str, Any]:
    root = context["root"]
    return {
        "requested_solver_step": int(requested_solver_step),
        "solver_time_s": float(context["solver_time_s"]),
        "branch_classification": context["branch_classification"],
        "interior_pressure_pa": float(context["interior_pressure_pa"]),
        "interior_density_kg_m3": float(context["interior_density_kg_m3"]),
        "interior_velocity_m_s": float(context["interior_velocity_m_s"]),
        "interior_sound_speed_m_s": float(
            context["interior_sound_speed_m_s"]
        ),
        "interior_mach": float(context["interior_mach"]),
        "interior_phase": context["interior_phase"],
        "endpoint_residual_kg_s": float(
            context["endpoint_residual_kg_s"]
        ),
        "endpoint_within_locked_root_mass_tolerance": bool(
            context["endpoint_within_locked_root_mass_tolerance"]
        ),
        "connected_rarefaction_sign_change_count": int(
            context["connected_rarefaction_sign_change_count"]
        ),
        "connected_rarefaction_residual_monotone": bool(
            context["connected_rarefaction_residual_monotone"]
        ),
        "positive_scan_sign_change_count": int(
            context["positive_scan_sign_change_count"]
        ),
        "positive_scan_residual_monotone_nonincreasing": context[
            "positive_scan_residual_monotone_nonincreasing"
        ],
        "positive_scan_delta_p_max_pa": context[
            "positive_scan_delta_p_max_pa"
        ],
        "root_pressure_pa": float(root["pressure_pa"]),
        "p_P_minus_p_i_pa": float(context["p_P_minus_p_i_pa"]),
        "root_chi": float(context["root_chi"]),
        "chi_max": CHI_MAX,
        "root_density_kg_m3": float(root["density_kg_m3"]),
        "root_velocity_m_s": float(root["velocity_m_s"]),
        "root_sound_speed_m_s": float(root["sound_speed_m_s"]),
        "root_mach": float(root["mach"]),
        "root_phase": root["phase"],
        "root_mass_residual_kg_s": float(
            root["root_mass_residual_kg_s"]
        ),
        "root_local_slope_kg_s_Pa": float(
            root["local_residual_slope_kg_s_Pa"]
        ),
        "root_b1_formal_outcome": root["formal_outcome"],
        "root_pipe_mass_rate_kg_s": float(root["pipe_mass_rate_kg_s"]),
        "root_b1_mass_rate_kg_s": float(root["b1_mass_rate_kg_s"]),
        "root_pipe_momentum_port_N": float(root["pipe_momentum_port_N"]),
        "root_downstream_stream_pressure_port_N": float(
            root["downstream_stream_pressure_port_N"]
        ),
        "root_restriction_reaction_on_fluid_N": float(
            root["restriction_reaction_on_fluid_N"]
        ),
        "root_restriction_reaction_ledger_residual_N": float(
            root["momentum_ledger_residual_N"]
        ),
        "root_pipe_energy_rate_W": float(root["pipe_energy_rate_W"]),
        "root_b1_energy_rate_W": float(root["b1_energy_rate_W"]),
        "root_energy_port_residual_W": float(
            root["energy_port_residual_W"]
        ),
        "stagnation_enthalpy_round_trip_passed": bool(
            root["stagnation_enthalpy_round_trip_passed"]
        ),
        "energy_mass_consistency_passed": bool(
            root["energy_mass_consistency_passed"]
        ),
        "energy_port_closure_passed": bool(
            root["energy_port_closure_passed"]
        ),
        "weak_compression_bisection_iterations": int(
            context.get("weak_compression_bisection_iterations", 0)
        ),
        "positive_pressure_continuation_flux_applied": bool(
            context["positive_pressure_continuation_flux_applied"]
        ),
        "finite_compression_branch_approved": False,
    }


def _run_increment_3(
    contract: dict[str, Any],
    b1_contract: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    np.ndarray,
    np.ndarray,
]:
    (
        parent_step_row,
        _,
        _,
        parent_summary,
        U_step337,
        U_step338,
    ) = _run_increment_2(contract, b1_contract)
    if not bool(parent_summary["increment_2_one_step_gate_passed"]):
        raise WeakCompressionShortRunStop(
            "PARENT_REPRODUCTION_FAILURE",
            "Increment 2 one-step parent did not reproduce as passed",
            {"parent_summary": parent_summary},
        )
    if parent_summary["outcome"] != INCREMENT_2_OUTCOME:
        raise WeakCompressionShortRunStop(
            "PARENT_REPRODUCTION_FAILURE",
            "Increment 2 parent returned an unexpected outcome",
            {"parent_summary": parent_summary},
        )

    case = diagnostic._case(contract, CASE_ID)
    state_id = str(case["state_id"])
    geometry = contract["geometry"]
    pipe = PipeGeometry(
        length_m=float(geometry["pipe_length_m"]),
        diameter_m=float(geometry["pipe_diameter_m"]),
        roughness_m=float(geometry["roughness_m"]),
    )
    grid = UniformGrid(pipe, int(geometry["baseline_cells"]))
    provider = CoolPropB2StateProvider()
    U_initial, initial_static = build_uniform_initial_state(
        contract,
        provider,
        state_id,
        grid.n_cells,
    )
    starting_time_s = float(parent_summary["solver_time_before_s"])
    hook = A1WeakCompressionBridgeShortRunHook(
        contract=contract,
        b1_contract=b1_contract,
        case_id=CASE_ID,
        provider=provider,
    )
    hook._previous_root_pressure_pa = float(
        parent_summary["root_pressure_pa"]
    )
    solver = FvmSolver(
        grid=grid,
        eos=CoolPropSinglePhaseEOS(
            provider,
            boundary_temperature_K=initial_static.temperature_K,
        ),
        U=np.asarray(U_step337, dtype=float),
        cfl=float(geometry["baseline_cfl"]),
        n_ghost=int(geometry["ghost_cells_each_side"]),
        left_boundary=ReflectiveBoundary(),
        right_boundary=TransmissiveBoundary(),
        right_external_face_flux_override=hook,
        enable_boundary_budget=True,
        enable_phase_budget=False,
        enable_energy_budget=False,
        enable_interface_budget=False,
        t=starting_time_s,
        step_count=STARTING_ACCEPTED_SOLVER_STEP,
    )

    initial = inventory(
        U_initial,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    starting = inventory(
        solver.U,
        dx=grid.dx,
        area_m2=grid.geometry.area_m2,
    )
    current_minus_initial = _inventory_array(starting) - _inventory_array(
        initial
    )
    cumulative_residual_before = np.asarray(
        [
            float(parent_step_row["cumulative_mass_residual_kg"])
            - float(parent_step_row["step_mass_residual_kg"]),
            float(parent_step_row["cumulative_momentum_residual_kg_m_s"])
            - float(parent_step_row["step_momentum_residual_kg_m_s"]),
            float(parent_step_row["cumulative_energy_residual_J"])
            - float(parent_step_row["step_energy_residual_J"]),
            0.0,
        ],
        dtype=float,
    )
    cumulative_expected_delta = (
        current_minus_initial - cumulative_residual_before
    )

    step_rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    local_scan_rows: list[dict[str, Any]] = []
    positive_scan_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    stop_reason: str | None = None
    stop_classification: str | None = None
    stop_diagnostics: dict[str, Any] = {}
    U_start = np.asarray(solver.U, dtype=float).copy()

    for offset in range(1, REQUESTED_ACCEPTED_STEPS + 1):
        requested_solver_step = STARTING_ACCEPTED_SOLVER_STEP + offset
        try:
            before = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            candidate_dt = float(solver.compute_dt())
            dt_limits = dict(hook.last_dt_limits)
            if hook.root_context is None:
                raise WeakCompressionShortRunStop(
                    "ROOT_OR_LEDGER_FAILURE",
                    "branch-aware root was not prepared by compute_dt",
                )
            context = hook.root_context
            branch = str(context["branch_classification"])
            history_before = list(hook.accepted_branch_history)
            flux_left, _ = solver._base_fluxes()
            left_flux = np.asarray(flux_left[0], dtype=float)
            right_flux = np.asarray(hook.flux, dtype=float)
            accepted_dt = float(solver.step(candidate_dt))
            hook.accept_current_root()

            after = inventory(
                solver.U,
                dx=grid.dx,
                area_m2=grid.geometry.area_m2,
            )
            expected_step_delta = (
                accepted_dt
                * grid.geometry.area_m2
                * (left_flux - right_flux)
            )
            cumulative_expected_delta += expected_step_delta
            primitive_after = solver.primitive()
            post_reconstruction = provider.reconstruct_from_conserved(
                solver.U[-1]
            )
            row = build_step_row(
                case_id=CASE_ID,
                state_id=state_id,
                requested_step=requested_solver_step,
                solver=solver,
                hook=hook,
                root_context=context,
                dt_limits=dt_limits,
                candidate_dt=candidate_dt,
                accepted_dt=accepted_dt,
                before=before,
                after=after,
                initial=initial,
                expected_step_delta=expected_step_delta,
                cumulative_expected_delta=cumulative_expected_delta,
                left_flux=left_flux,
                right_flux=right_flux,
                post_reconstruction=post_reconstruction,
                primitive_after=primitive_after,
                tolerances=contract["acceptance_tolerances"],
            )
            rho_after = np.asarray(solver.U[:, 0], dtype=float)
            velocity_after = np.asarray(
                solver.U[:, 1] / rho_after,
                dtype=float,
            )
            internal_after = np.asarray(
                solver.U[:, 2] / rho_after - 0.5 * velocity_after**2,
                dtype=float,
            )
            root = context["root"]
            row.update(
                {
                    "branch_classification": branch,
                    "endpoint_residual_kg_s": float(
                        context["endpoint_residual_kg_s"]
                    ),
                    "endpoint_within_locked_root_mass_tolerance": bool(
                        context[
                            "endpoint_within_locked_root_mass_tolerance"
                        ]
                    ),
                    "connected_rarefaction_sign_change_count": int(
                        context[
                            "connected_rarefaction_sign_change_count"
                        ]
                    ),
                    "connected_rarefaction_residual_monotone": bool(
                        context[
                            "connected_rarefaction_residual_monotone"
                        ]
                    ),
                    "positive_scan_sign_change_count": int(
                        context["positive_scan_sign_change_count"]
                    ),
                    "positive_scan_residual_monotone_nonincreasing": context[
                        "positive_scan_residual_monotone_nonincreasing"
                    ],
                    "p_P_minus_p_i_pa": float(
                        context["p_P_minus_p_i_pa"]
                    ),
                    "root_chi": float(context["root_chi"]),
                    "chi_max": CHI_MAX,
                    "weak_compression_bisection_iterations": int(
                        context.get(
                            "weak_compression_bisection_iterations",
                            0,
                        )
                    ),
                    "branch_history_before": history_before,
                    "branch_history_after": list(
                        hook.accepted_branch_history
                    ),
                    "clear_branch_chatter_detected": False,
                    "minimum_density_after_step_kg_m3": float(
                        np.min(rho_after)
                    ),
                    "minimum_internal_energy_after_step_J_kg": float(
                        np.min(internal_after)
                    ),
                    "all_conserved_finite_after_step": bool(
                        np.all(np.isfinite(solver.U))
                    ),
                    "positive_pressure_continuation_flux_applied": bool(
                        branch == "WEAK_COMPRESSION"
                    ),
                    "finite_compression_branch_approved": False,
                }
            )

            branch_specific = bool(
                (
                    branch == "WEAK_COMPRESSION"
                    and int(row["positive_scan_sign_change_count"]) == 1
                    and 0.0 < float(row["root_chi"]) <= CHI_MAX
                    and float(row["p_P_minus_p_i_pa"]) > 0.0
                )
                or (
                    branch == "RAREFACTION"
                    and int(
                        row["connected_rarefaction_sign_change_count"]
                    )
                    == 1
                    and float(row["p_P_minus_p_i_pa"]) < 0.0
                )
                or (
                    branch == "NEUTRAL_ENDPOINT"
                    and bool(
                        row[
                            "endpoint_within_locked_root_mass_tolerance"
                        ]
                    )
                    and float(row["p_P_minus_p_i_pa"]) == 0.0
                )
            )
            per_step_gate = bool(
                branch in ALLOWED_BRANCHES
                and branch_specific
                and bool(row["accepted_step"])
                and int(row["solver_step_count"]) == requested_solver_step
                and accepted_dt > 0.0
                and abs(float(row["root_mass_residual_kg_s"]))
                <= robustness.ROOT_MASS_RESIDUAL_ABSOLUTE_KG_S
                and float(row["root_velocity_m_s"]) >= 0.0
                and 0.0 <= float(row["root_mach"]) < 1.0
                and bool(row["stagnation_enthalpy_round_trip_passed"])
                and bool(row["energy_mass_consistency_passed"])
                and bool(row["energy_port_closure_passed"])
                and abs(
                    float(
                        row[
                            "restriction_reaction_ledger_residual_N"
                        ]
                    )
                )
                <= robustness.MOMENTUM_LEDGER_RESIDUAL_ABSOLUTE_N
                and bool(row["all_conserved_finite_after_step"])
                and float(row["minimum_density_after_step_kg_m3"]) > 0.0
                and float(
                    row["minimum_internal_energy_after_step_J_kg"]
                )
                > 0.0
                and not bool(row["reverse_flow_guard_triggered"])
                and not bool(row["reverse_velocity_detected"])
                and bool(row["outlet_phase_passed"])
                and bool(row["rho_xv_exact_zero"])
                and bool(row["step_mass_passed"])
                and bool(row["step_momentum_passed"])
                and bool(row["step_energy_passed"])
                and bool(row["cumulative_mass_passed"])
                and bool(row["cumulative_momentum_passed"])
                and bool(row["cumulative_energy_passed"])
                and bool(row["step_passed"])
            )
            row["increment_3_per_step_gate_passed"] = per_step_gate
            if not per_step_gate:
                raise WeakCompressionShortRunStop(
                    "PER_STEP_GATE_FAILURE",
                    f"accepted step {requested_solver_step} failed the fixed "
                    "Increment 3 gate",
                    {"step_row": row},
                )

            if requested_solver_step == 338:
                if not np.array_equal(
                    np.asarray(solver.U, dtype=float),
                    np.asarray(U_step338, dtype=float),
                ):
                    raise WeakCompressionShortRunStop(
                        "PARENT_REPRODUCTION_FAILURE",
                        "independent first short-run step does not exactly "
                        "reproduce the accepted Increment 2 state",
                        {"step_row": row},
                    )
                row["increment_2_state_exactly_reproduced"] = True
            else:
                row["increment_2_state_exactly_reproduced"] = None

            step_rows.append(row)
            root_rows.append(
                _root_evidence_row(
                    context=context,
                    requested_solver_step=requested_solver_step,
                )
            )
            local_scan_rows.extend(
                _flatten_scan(
                    rows=list(context["local_scan_rows"]),
                    requested_solver_step=requested_solver_step,
                    solver_time_s=float(context["solver_time_s"]),
                    branch=branch,
                    scan_kind="LOCAL_FIXED_OFFSETS",
                )
            )
            if context["positive_scan_rows"]:
                positive_scan_rows.extend(
                    _flatten_scan(
                        rows=list(context["positive_scan_rows"]),
                        requested_solver_step=requested_solver_step,
                        solver_time_s=float(context["solver_time_s"]),
                        branch=branch,
                        scan_kind="POSITIVE_CHI_SCOPED",
                    )
                )
            previous_branch = history_before[-1]
            transition_rows.append(
                {
                    "from_solver_step": requested_solver_step - 1,
                    "to_solver_step": requested_solver_step,
                    "from_branch": previous_branch,
                    "to_branch": branch,
                    "branch_changed": bool(previous_branch != branch),
                    "clear_branch_chatter_detected": False,
                    "five_point_history_after": list(
                        hook.accepted_branch_history[-5:]
                    ),
                }
            )
        except WeakCompressionShortRunStop as exc:
            stop_classification = exc.classification
            stop_reason = f"{exc.classification}: {exc}"
            stop_diagnostics = dict(exc.diagnostics)
            break
        except Exception as exc:
            stop_classification = type(exc).__name__
            stop_reason = f"{type(exc).__name__}: {exc}"
            stop_diagnostics = {}
            break

    U_final = np.asarray(solver.U, dtype=float).copy()
    branch_sequence = [
        str(row["branch_classification"]) for row in step_rows
    ]
    counts = Counter(branch_sequence)
    transitions = sum(
        bool(row["branch_changed"]) for row in transition_rows
    )
    complete = bool(
        stop_reason is None
        and len(step_rows) == REQUESTED_ACCEPTED_STEPS
        and int(solver.step_count) == FINAL_ACCEPTED_SOLVER_STEP
        and all(
            bool(row["increment_3_per_step_gate_passed"])
            for row in step_rows
        )
        and all(
            str(row["branch_classification"]) in ALLOWED_BRANCHES
            for row in step_rows
        )
        and not any(
            bool(row["clear_branch_chatter_detected"])
            for row in step_rows
        )
    )
    final_reconstruction = provider.reconstruct_from_conserved(solver.U[-1])
    summary = {
        "schema_version": (
            "stage7_u3_b2_a1_weak_compression_bridge_v0_1_increment_3"
        ),
        "scope": "model_review_working_vertical_slice_32_accepted_steps",
        "parent_source_sha": PARENT_SOURCE_SHA,
        "parent_workflow_run": PARENT_WORKFLOW_RUN,
        "parent_job": PARENT_JOB,
        "parent_artifact": PARENT_ARTIFACT,
        "parent_artifact_sha256": PARENT_ARTIFACT_SHA256,
        "parent_increment_2_reproduced": bool(
            parent_summary["increment_2_one_step_gate_passed"]
        ),
        "parent_increment_2_outcome": parent_summary["outcome"],
        "case_id": CASE_ID,
        "cells": int(grid.n_cells),
        "cfl": float(geometry["baseline_cfl"]),
        "solver_step_before": STARTING_ACCEPTED_SOLVER_STEP,
        "solver_step_after": int(solver.step_count),
        "solver_time_before_s": starting_time_s,
        "solver_time_after_s": float(solver.t),
        "requested_accepted_steps": REQUESTED_ACCEPTED_STEPS,
        "accepted_steps_completed": len(step_rows),
        "expected_final_solver_step": FINAL_ACCEPTED_SOLVER_STEP,
        "branch_sequence": branch_sequence,
        "branch_counts": {
            branch: int(counts.get(branch, 0))
            for branch in sorted(ALLOWED_BRANCHES)
        },
        "branch_transition_count": int(transitions),
        "clear_branch_chatter_detected": False,
        "clear_branch_chatter_rule": "five accepted classifications A-B-A-B-A",
        "maximum_weak_compression_chi": _maximum(
            [
                row
                for row in step_rows
                if row["branch_classification"] == "WEAK_COMPRESSION"
            ],
            "root_chi",
        ),
        "minimum_root_pressure_offset_pa": _minimum(
            step_rows,
            "p_P_minus_p_i_pa",
        ),
        "maximum_root_pressure_offset_pa": _maximum(
            step_rows,
            "p_P_minus_p_i_pa",
        ),
        "maximum_absolute_root_mass_residual_kg_s": _max_abs(
            step_rows,
            "root_mass_residual_kg_s",
        ),
        "maximum_root_mach": _maximum(step_rows, "root_mach"),
        "minimum_root_velocity_m_s": _minimum(
            step_rows,
            "root_velocity_m_s",
        ),
        "maximum_halving_count": _maximum(step_rows, "halving_count"),
        "maximum_absolute_step_mass_residual_kg": _max_abs(
            step_rows,
            "step_mass_residual_kg",
        ),
        "maximum_absolute_step_momentum_residual_kg_m_s": _max_abs(
            step_rows,
            "step_momentum_residual_kg_m_s",
        ),
        "maximum_absolute_step_energy_residual_J": _max_abs(
            step_rows,
            "step_energy_residual_J",
        ),
        "maximum_absolute_cumulative_mass_residual_kg": _max_abs(
            step_rows,
            "cumulative_mass_residual_kg",
        ),
        "maximum_absolute_cumulative_momentum_residual_kg_m_s": _max_abs(
            step_rows,
            "cumulative_momentum_residual_kg_m_s",
        ),
        "maximum_absolute_cumulative_energy_residual_J": _max_abs(
            step_rows,
            "cumulative_energy_residual_J",
        ),
        "final_outlet_pressure_pa": float(
            final_reconstruction.static.pressure_pa
        ),
        "final_outlet_velocity_m_s": float(
            final_reconstruction.static.velocity_m_s
        ),
        "final_outlet_mach": float(
            final_reconstruction.static.velocity_m_s
            / final_reconstruction.static.sound_speed_m_s
        ),
        "final_outlet_phase": final_reconstruction.static.phase,
        "final_minimum_density_kg_m3": float(
            np.min(U_final[:, 0])
        ),
        "final_rho_xv_exact_zero": bool(
            np.all(U_final[:, 3] == 0.0)
        ),
        "stop_classification": stop_classification,
        "stop_reason": stop_reason,
        "stop_diagnostics_keys": sorted(stop_diagnostics),
        "outcome": OUTCOME if complete else "INCREMENT_3_STOPPED",
        "increment_3_32_step_gate_passed": complete,
        "finite_compression_branch_approved": False,
        "full_two_l_over_c0_passed": False,
        "formal_state_promoted": False,
        "u3_b2_finite_pipe_execution_complete": False,
        "single_phase_finite_pipe_coupling_verified": False,
        "u3_b2_verification_benchmark_accepted": False,
        "physical_validation": False,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }
    return (
        step_rows,
        root_rows,
        local_scan_rows,
        positive_scan_rows,
        transition_rows,
        summary,
        U_start,
        U_final,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--b1-contract", type=Path, required=True)
    parser.add_argument("--model-review-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-git-sha", required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    b1_contract = load_b1_contract(args.b1_contract)
    if not args.model_review_spec.is_file():
        raise FileNotFoundError(args.model_review_spec)

    (
        step_rows,
        root_rows,
        local_scan_rows,
        positive_scan_rows,
        transition_rows,
        summary,
        U_start,
        U_final,
    ) = _run_increment_3(contract, b1_contract)
    summary["source_git_sha"] = args.source_git_sha

    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "short_run_steps.csv", step_rows)
    _write_csv(output / "short_run_roots.csv", root_rows)
    _write_csv(output / "local_wave_scans.csv", local_scan_rows)
    _write_csv(output / "positive_pressure_scans.csv", positive_scan_rows)
    _write_csv(output / "branch_transitions.csv", transition_rows)
    np.savez_compressed(
        output / "short_run_states.npz",
        U_start=np.asarray(U_start, dtype=float),
        U_final=np.asarray(U_final, dtype=float),
        solver_step_before=np.asarray(
            [STARTING_ACCEPTED_SOLVER_STEP],
            dtype=np.int64,
        ),
        solver_step_after=np.asarray(
            [summary["solver_step_after"]],
            dtype=np.int64,
        ),
        solver_time_before_s=np.asarray(
            [summary["solver_time_before_s"]]
        ),
        solver_time_after_s=np.asarray(
            [summary["solver_time_after_s"]]
        ),
    )
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# U3 B2 A1 Weak Compression Bridge v0.1 Increment 3\n\n"
        "MODEL_REVIEW / WORKING_VERTICAL_SLICE evidence only. The accepted "
        "step-337 state was reproduced and the three-branch A1 boundary was "
        "attempted for 32 accepted FvmSolver steps. This does not approve a "
        "general finite-compression model, full-horizon passage, finite-pipe "
        "verification, benchmark acceptance, Physical Validation, design use, "
        "or production activation.\n\n"
        f"source Git SHA: `{args.source_git_sha}`\n\n"
        "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    names = (
        "short_run_steps.csv",
        "short_run_roots.csv",
        "local_wave_scans.csv",
        "positive_pressure_scans.csv",
        "branch_transitions.csv",
        "short_run_states.npz",
        "summary.json",
        "report.md",
    )
    (output / "artifact_sha256.txt").write_text(
        "".join(f"{_sha256(output / name)}  {name}\n" for name in names),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary["increment_3_32_step_gate_passed"]:
        raise SystemExit(
            "Weak Compression Bridge Increment 3 did not pass: "
            f"{summary['stop_reason']}"
        )


if __name__ == "__main__":
    main()
