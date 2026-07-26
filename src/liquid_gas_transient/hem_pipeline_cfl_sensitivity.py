"""Verification-only CFL sensitivity contract for the Stage 7 pipeline matrix.

The PR #77 pipeline model and the PR #82 128-cell mesh are immutable. This
module permits exactly three CFL values and their predeclared inverse-CFL step
caps. It does not modify the production solver, Rusanov flux, boundary model,
HEM phase/projection algorithms, or any tolerance.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
from dataclasses import asdict, dataclass, fields, replace
from typing import Callable, Literal, Mapping, Sequence

import numpy as np

from .hem_pipeline_4mpa_mesh_sensitivity import MeshCaseMetrics, _case_metrics
from .hem_pipeline_depressurization_first_crossing import (
    FIXED_PIPELINE_DEPRESSURIZATION_CASES,
    HEMPipelineDepressurizationConfig,
    PipelineCaseResult,
    PipelineDepressurizationCaseSpec,
    run_pipeline_depressurization_case,
)


CFL_CELL_COUNT = 128
CFL_VALUES: tuple[float, ...] = (0.10, 0.05, 0.025)
CFL_STEP_CAPS: dict[float, int] = {0.10: 8000, 0.05: 16000, 0.025: 32000}
FOUR_MPA_CASE_ID = "pipeline_liquid_control_p5m5_to_p4m5"
CFL_ANALYSIS_ID = "stage7_pipeline_cfl_sensitivity_matrix"
ANALYSIS_MODEL = "HEM"
PROPERTY_BACKEND_NAME = "coolprop_co2"

CflClassification = Literal[
    "CROSSING_VANISHES_WITH_SMALLER_CFL",
    "CROSSING_DEPTH_DECAYS_WITH_SMALLER_CFL",
    "FINITE_CROSSING_PERSISTS_ACROSS_CFL",
    "CROSSING_TIME_POSITION_TREND_STABLE",
    "CROSSING_TIME_POSITION_NOT_STABLE",
    "CFL_SEQUENCE_NON_MONOTONE",
    "CFL_SENSITIVITY_INCONCLUSIVE",
]


EXPECTED_128_CELL_CFL_0P10: dict[str, dict[str, object]] = {
    "pipeline_crossing_candidate_p5m5_to_p2m5": {
        "case_id": "pipeline_crossing_candidate_p5m5_to_p2m5",
        "n_cells": 128,
        "cfl": 0.10,
        "maximum_steps": 8000,
        "outcome": "ACCEPTED_FIRST_CROSSING",
        "failure_reason": "",
        "step_count": 403,
        "final_time_s": 0.0006422816041107276,
        "crossing_step": 403,
        "crossing_time_s": 0.0006422816041107276,
        "crossing_cell_index": 120,
        "crossing_distance_from_outlet_m": 0.05859375,
        "maximum_crossing_quality": 1.1990738237934995e-06,
        "maximum_projected_quality": 1.1990738237934995e-06,
        "maximum_void_fraction": 8.317377912099828e-06,
        "crossing_delta_u_sat_j_kg": 0.21067950761062093,
        "crossing_delta_v_sat_m3_kg": 8.127203220305301e-09,
        "crossing_q_from_internal_energy": 1.199073831887237e-06,
        "crossing_q_from_specific_volume": 1.1990738246568563e-06,
        "pre_crossing_liquid_sound_speed_m_s": 460.8082162127932,
        "raw_crossing_sound_speed_m_s": 43.27199311642356,
        "projection_vapor_source_kg": 6.4440925992278e-08,
        "boundary_vapor_transport_kg": 0.0,
        "mass_residual_kg": -8.881784197001252e-16,
        "momentum_residual_kg_m_s": 1.3322676295501878e-15,
        "energy_residual_J": -2.3283064365386963e-10,
        "combined_vapor_residual_kg": 0.0,
        "final_state_sha256": "40edf828e6c3c9545cf654b7232f2fbff6623ba954383d2716364277a006a186",
        "run_signature_sha256": "2efa68ca4b6b60da2de324fe884fa46c39d411f400fb7c3df40836d5b1faed24",
    },
    "pipeline_moderate_diagnostic_p5m5_to_p3m5": {
        "case_id": "pipeline_moderate_diagnostic_p5m5_to_p3m5",
        "n_cells": 128,
        "cfl": 0.10,
        "maximum_steps": 8000,
        "outcome": "GUARD_FAILURE",
        "failure_reason": (
            "HEMPipelineDepressurizationError: "
            "crossing quality evidence is below the fixed minimum"
        ),
        "step_count": 578,
        "final_time_s": 0.0009203833940858876,
        "crossing_step": 578,
        "crossing_time_s": 0.0009203833940858876,
        "crossing_cell_index": 118,
        "crossing_distance_from_outlet_m": 0.07421875,
        "maximum_crossing_quality": 5.977506786571329e-07,
        "maximum_projected_quality": 5.977506786571329e-07,
        "maximum_void_fraction": 4.12752024824155e-06,
        "crossing_delta_u_sat_j_kg": 0.10481627815170214,
        "crossing_delta_v_sat_m3_kg": 4.0336276736253895e-09,
        "crossing_q_from_internal_energy": 5.977506842773405e-07,
        "crossing_q_from_specific_volume": 5.977506790514761e-07,
        "pre_crossing_liquid_sound_speed_m_s": 459.75338884922354,
        "raw_crossing_sound_speed_m_s": 43.39395406717686,
        "projection_vapor_source_kg": 3.209599149450161e-08,
        "boundary_vapor_transport_kg": 0.0,
        "mass_residual_kg": -8.881784197001252e-16,
        "momentum_residual_kg_m_s": -7.549516567451064e-15,
        "energy_residual_J": -6.984919309616089e-10,
        "combined_vapor_residual_kg": 0.0,
        "final_state_sha256": "d01d13e9a0ad6a119d869d5a75e170b4be532a349d1874b7cf3b1b7f19aa853d",
        "run_signature_sha256": "6f92a6418776bc0c08f17d7efe42b7ea181fd621b87e305bb21b5e3388233b34",
    },
    "pipeline_liquid_control_p5m5_to_p4m5": {
        "case_id": "pipeline_liquid_control_p5m5_to_p4m5",
        "n_cells": 128,
        "cfl": 0.10,
        "maximum_steps": 8000,
        "outcome": "GUARD_FAILURE",
        "failure_reason": (
            "HEMPipelineDepressurizationError: "
            "crossing quality evidence is below the fixed minimum"
        ),
        "step_count": 1086,
        "final_time_s": 0.0017272870719037706,
        "crossing_step": 1086,
        "crossing_time_s": 0.0017272870719037706,
        "crossing_cell_index": 113,
        "crossing_distance_from_outlet_m": 0.11328125,
        "maximum_crossing_quality": 3.8580990283897163e-07,
        "maximum_projected_quality": 3.8580990283897163e-07,
        "maximum_void_fraction": 2.64573452797628e-06,
        "crossing_delta_u_sat_j_kg": 0.06744639214593917,
        "crossing_delta_v_sat_m3_kg": 2.586019042351631e-09,
        "crossing_q_from_internal_energy": 3.85809899633048e-07,
        "crossing_q_from_specific_volume": 3.8580990249425214e-07,
        "pre_crossing_liquid_sound_speed_m_s": 458.13610847272406,
        "raw_crossing_sound_speed_m_s": 43.579722162603666,
        "projection_vapor_source_kg": 3.497439408405266e-08,
        "boundary_vapor_transport_kg": 0.0,
        "mass_residual_kg": -1.7763568394002505e-15,
        "momentum_residual_kg_m_s": 1.9539925233402755e-14,
        "energy_residual_J": -2.3283064365386963e-10,
        "combined_vapor_residual_kg": 0.0,
        "final_state_sha256": "a48fb2c74d9a72f6f8641c0277fc5941b808b7cc3e599fba9c81746114142bd5",
        "run_signature_sha256": "c706e5d02ed3e40cedf4176a356fe4d4d3bfaaf4599b46265d10cbfd52670a67",
    },
}


class HEMPipelineCflSensitivityError(RuntimeError):
    """Raised when the reviewed CFL-only contract cannot be applied safely."""


def _git_output(*args: str) -> str | None:
    try:
        value = subprocess.check_output(
            ["git", *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return value or None


def collect_cfl_runtime_provenance() -> dict[str, object]:
    """Collect explicit model/backend/version and Git/runtime identity."""

    try:
        import CoolProp  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("CoolProp is required for an executed CFL matrix") from exc
    version = str(getattr(CoolProp, "__version__", "")).strip()
    if not version:
        raise HEMPipelineCflSensitivityError("CoolProp version is unavailable")

    checkout_sha = _git_output("rev-parse", "HEAD")
    source_sha = (
        os.environ.get("ANALYSIS_SOURCE_GIT_SHA", "").strip()
        or os.environ.get("GITHUB_HEAD_SHA", "").strip()
        or os.environ.get("GITHUB_SHA", "").strip()
        or checkout_sha
    )
    if not source_sha:
        raise HEMPipelineCflSensitivityError(
            "source Git SHA is unavailable; set ANALYSIS_SOURCE_GIT_SHA"
        )
    return {
        "analysis_id": CFL_ANALYSIS_ID,
        "analysis_model": ANALYSIS_MODEL,
        "property_backend_name": PROPERTY_BACKEND_NAME,
        "property_backend_version": version,
        "source_git_sha": source_sha,
        "checkout_git_sha": checkout_sha,
        "git_branch": _git_output("rev-parse", "--abbrev-ref", "HEAD"),
        "git_status_porcelain": _git_output("status", "--porcelain") or "",
        "github_repository": os.environ.get("GITHUB_REPOSITORY"),
        "github_ref": os.environ.get("GITHUB_REF"),
        "github_head_ref": os.environ.get("GITHUB_HEAD_REF"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "verification_only": True,
        "design_use_acceptance": False,
        "production_hem_activation_approved": False,
    }


def normalize_cfl_provenance(provenance: Mapping[str, object]) -> dict[str, object]:
    """Validate mandatory provenance fields and return a plain dictionary."""

    required = (
        "analysis_id",
        "analysis_model",
        "property_backend_name",
        "property_backend_version",
        "source_git_sha",
        "verification_only",
        "design_use_acceptance",
        "production_hem_activation_approved",
    )
    result = dict(provenance)
    missing = [key for key in required if key not in result]
    if missing:
        raise HEMPipelineCflSensitivityError(
            f"CFL provenance is missing required fields: {missing}"
        )
    for key in required[:5]:
        if not str(result[key]).strip():
            raise HEMPipelineCflSensitivityError(
                f"CFL provenance field {key} must not be empty"
            )
    if result["verification_only"] is not True:
        raise HEMPipelineCflSensitivityError("CFL execution must remain verification-only")
    if result["design_use_acceptance"] is not False:
        raise HEMPipelineCflSensitivityError("design use must remain unapproved")
    if result["production_hem_activation_approved"] is not False:
        raise HEMPipelineCflSensitivityError(
            "production HEM activation must remain unapproved"
        )
    return result


@dataclass(frozen=True)
class CflSensitivityRunSpec:
    """One entry in the fixed 128-cell, three-CFL, three-pressure matrix."""

    run_id: str
    case_id: str
    final_boundary_pressure_pa: float
    cfl: float
    maximum_steps: int


@dataclass(frozen=True)
class HEMPipelineCflSensitivityConfig(HEMPipelineDepressurizationConfig):
    """PR #77 configuration with only CFL and its fixed step cap variable."""

    n_cells: int = CFL_CELL_COUNT
    cfl: float = 0.10
    max_steps: int = 8000

    def __post_init__(self) -> None:
        if isinstance(self.n_cells, bool) or self.n_cells != CFL_CELL_COUNT:
            raise ValueError(f"CFL sensitivity n_cells is fixed at {CFL_CELL_COUNT}")
        if isinstance(self.cfl, bool) or self.cfl not in CFL_STEP_CAPS:
            raise ValueError(f"CFL sensitivity cfl must be one of {CFL_VALUES}")
        expected_steps = CFL_STEP_CAPS[float(self.cfl)]
        if self.max_steps != expected_steps:
            raise ValueError(
                f"CFL sensitivity max_steps is fixed at {expected_steps} "
                f"for cfl={self.cfl}"
            )

        fixed = HEMPipelineDepressurizationConfig()
        for item in fields(HEMPipelineDepressurizationConfig):
            if item.name in {"n_cells", "cfl", "max_steps"}:
                continue
            actual = getattr(self, item.name)
            expected = getattr(fixed, item.name)
            if actual != expected:
                raise ValueError(
                    f"CFL sensitivity may not change {item.name}: "
                    f"expected {expected!r}, received {actual!r}"
                )

    @classmethod
    def for_cfl(cls, cfl: float) -> "HEMPipelineCflSensitivityConfig":
        if isinstance(cfl, bool):
            raise ValueError(f"cfl must be one of {CFL_VALUES}")
        value = float(cfl)
        if value not in CFL_STEP_CAPS:
            raise ValueError(f"cfl must be one of {CFL_VALUES}")
        return cls(cfl=value, max_steps=CFL_STEP_CAPS[value])

    @property
    def cfl_override(self) -> dict[str, object]:
        return {
            "n_cells": self.n_cells,
            "dx_m": self.dx_m,
            "cfl": self.cfl,
            "maximum_steps": self.max_steps,
        }


def _cfl_token(cfl: float) -> str:
    return f"{float(cfl):.3f}".replace(".", "p")


def fixed_cfl_sensitivity_run_specs() -> tuple[CflSensitivityRunSpec, ...]:
    """Return the reviewed nine-run order without executing the solver."""

    return tuple(
        CflSensitivityRunSpec(
            run_id=f"{case.case_id}__n{CFL_CELL_COUNT}__cfl{_cfl_token(cfl)}",
            case_id=case.case_id,
            final_boundary_pressure_pa=case.final_boundary_pressure_pa,
            cfl=cfl,
            maximum_steps=CFL_STEP_CAPS[cfl],
        )
        for cfl in CFL_VALUES
        for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
    )


FIXED_CFL_SENSITIVITY_RUN_SPECS = fixed_cfl_sensitivity_run_specs()


_BASELINE_FIELDS: tuple[str, ...] = (
    "case_id",
    "n_cells",
    "cfl",
    "maximum_steps",
    "outcome",
    "failure_reason",
    "step_count",
    "final_time_s",
    "crossing_step",
    "crossing_time_s",
    "crossing_cell_index",
    "crossing_distance_from_outlet_m",
    "maximum_crossing_quality",
    "maximum_projected_quality",
    "maximum_void_fraction",
    "crossing_delta_u_sat_j_kg",
    "crossing_delta_v_sat_m3_kg",
    "crossing_q_from_internal_energy",
    "crossing_q_from_specific_volume",
    "pre_crossing_liquid_sound_speed_m_s",
    "raw_crossing_sound_speed_m_s",
    "projection_vapor_source_kg",
    "boundary_vapor_transport_kg",
    "mass_residual_kg",
    "momentum_residual_kg_m_s",
    "energy_residual_J",
    "combined_vapor_residual_kg",
    "final_state_sha256",
    "run_signature_sha256",
)


def _assert_128_cell_cfl_0p10_baseline(metric: MeshCaseMetrics) -> None:
    """Require one PR #82 128-cell/CFL=0.10 row to match exactly."""

    expected = EXPECTED_128_CELL_CFL_0P10.get(metric.case_id)
    if expected is None:
        raise HEMPipelineCflSensitivityError(
            f"unexpected CFL=0.10 baseline case: {metric.case_id}"
        )
    actual = {name: getattr(metric, name) for name in _BASELINE_FIELDS}
    if actual != expected:
        raise HEMPipelineCflSensitivityError(
            "128-cell CFL=0.10 PR #82 baseline mismatch; lower-CFL comparison "
            "is not allowed: "
            + json.dumps({"actual": actual, "expected": expected}, sort_keys=True)
        )


def _strictly_decreasing(values: Sequence[float | None]) -> bool:
    return bool(
        len(values) == len(CFL_VALUES)
        and all(value is not None and np.isfinite(value) for value in values)
        and all(float(left) > float(right) for left, right in zip(values, values[1:]))
    )


def _nonmonotone(values: Sequence[float | None]) -> bool:
    if len(values) != len(CFL_VALUES) or any(
        value is None or not np.isfinite(value) for value in values
    ):
        return False
    differences = [float(right) - float(left) for left, right in zip(values, values[1:])]
    return any(
        first * second < 0.0 for first, second in zip(differences, differences[1:])
    )


def classify_four_mpa_cfl_sequence(
    cases: Sequence[MeshCaseMetrics],
) -> tuple[tuple[CflClassification, ...], dict[str, str]]:
    """Classify the fixed 4 MPa CFL sequence without claiming an accuracy band."""

    control = sorted(
        [case for case in cases if case.case_id == FOUR_MPA_CASE_ID],
        key=lambda item: (
            CFL_VALUES.index(float(item.cfl))
            if float(item.cfl) in CFL_VALUES
            else len(CFL_VALUES)
        ),
    )
    if [float(case.cfl) for case in control] != list(CFL_VALUES):
        return (
            ("CFL_SENSITIVITY_INCONCLUSIVE",),
            {
                "CFL_SENSITIVITY_INCONCLUSIVE": (
                    "The fixed 0.10/0.05/0.025 4 MPa sequence is incomplete."
                )
            },
        )

    severe = {
        "ENDPOINT_LANDING",
        "FORBIDDEN_TRANSITION",
        "REVERSE_FLOW_GUARD",
        "BACKEND_FAILURE",
    }
    if any(case.outcome in severe for case in control):
        return (
            ("CFL_SENSITIVITY_INCONCLUSIVE",),
            {
                "CFL_SENSITIVITY_INCONCLUSIVE": (
                    "At least one 4 MPa CFL row ended in an endpoint, forbidden, "
                    "reverse-flow, or backend outcome; no trend classification is valid."
                )
            },
        )

    categories: list[CflClassification] = []
    rationale: dict[str, str] = {}
    crossed = [case.raw_crossing_observed for case in control]
    if crossed[0] and not crossed[-1]:
        categories.append("CROSSING_VANISHES_WITH_SMALLER_CFL")
        rationale["CROSSING_VANISHES_WITH_SMALLER_CFL"] = (
            "The CFL 0.10 row crosses while CFL 0.025 remains liquid through "
            "the fixed physical horizon."
        )

    q_values = [
        case.maximum_crossing_quality if crossed[index] else None
        for index, case in enumerate(control)
    ]
    du_values = [
        case.crossing_delta_u_sat_j_kg if crossed[index] else None
        for index, case in enumerate(control)
    ]
    dv_values = [
        case.crossing_delta_v_sat_m3_kg if crossed[index] else None
        for index, case in enumerate(control)
    ]
    depth_decays = (
        _strictly_decreasing(q_values)
        and _strictly_decreasing(du_values)
        and _strictly_decreasing(dv_values)
    )
    if depth_decays:
        categories.append("CROSSING_DEPTH_DECAYS_WITH_SMALLER_CFL")
        rationale["CROSSING_DEPTH_DECAYS_WITH_SMALLER_CFL"] = (
            "q_eq, Delta_u_sat, and Delta_v_sat decrease strictly as CFL is reduced."
        )
    if all(crossed) and not depth_decays:
        categories.append("FINITE_CROSSING_PERSISTS_ACROSS_CFL")
        rationale["FINITE_CROSSING_PERSISTS_ACROSS_CFL"] = (
            "All three CFL rows cross and the reviewed depth coordinates do not "
            "all decrease strictly."
        )

    if all(crossed):
        times = [case.normalized_crossing_time for case in control]
        positions = [case.normalized_crossing_distance_from_outlet for case in control]
        if all(value is not None and np.isfinite(value) for value in times + positions):
            time_stable = abs(float(times[2]) - float(times[1])) <= abs(
                float(times[1]) - float(times[0])
            )
            position_stable = abs(float(positions[2]) - float(positions[1])) <= abs(
                float(positions[1]) - float(positions[0])
            )
            if time_stable and position_stable:
                categories.append("CROSSING_TIME_POSITION_TREND_STABLE")
                rationale["CROSSING_TIME_POSITION_TREND_STABLE"] = (
                    "The CFL 0.05-to-0.025 changes in normalized time and position "
                    "do not exceed the CFL 0.10-to-0.05 changes."
                )
            else:
                categories.append("CROSSING_TIME_POSITION_NOT_STABLE")
                rationale["CROSSING_TIME_POSITION_NOT_STABLE"] = (
                    "Normalized crossing time or position does not show a smaller "
                    "0.05-to-0.025 change."
                )

    if any(_nonmonotone(values) for values in (q_values, du_values, dv_values)):
        categories.append("CFL_SEQUENCE_NON_MONOTONE")
        rationale["CFL_SEQUENCE_NON_MONOTONE"] = (
            "At least one principal crossing-depth coordinate reverses trend across "
            "the three CFL values."
        )

    if not categories:
        categories.append("CFL_SENSITIVITY_INCONCLUSIVE")
        rationale["CFL_SENSITIVITY_INCONCLUSIVE"] = (
            "The reviewed classification rules do not resolve the observed sequence."
        )
    return tuple(categories), rationale


@dataclass(frozen=True)
class HEMPipelineCflSensitivityResult:
    """Fixed 128-cell, 2/3/4 MPa, three-CFL software-sensitivity matrix."""

    cases: tuple[MeshCaseMetrics, ...]
    four_mpa_classifications: tuple[CflClassification, ...]
    four_mpa_classification_rationale: dict[str, str]
    provenance: dict[str, object]

    def summary(self) -> dict[str, object]:
        identity = {
            "analysis_id": str(self.provenance["analysis_id"]),
            "model": str(self.provenance["analysis_model"]),
            "backend": str(self.provenance["property_backend_name"]),
            "version": str(self.provenance["property_backend_version"]),
        }
        return {
            "schema_version": "stage7_lco2_hem_pipeline_cfl_sensitivity_v1",
            "scope": "verification_only",
            "analysis_identity": identity,
            "provenance": dict(self.provenance),
            "case_count": len(self.cases),
            "n_cells": CFL_CELL_COUNT,
            "dx_m": 1.0 / CFL_CELL_COUNT,
            "cfl_values": list(CFL_VALUES),
            "cfl_step_caps": {
                format(key, ".3f"): value for key, value in CFL_STEP_CAPS.items()
            },
            "final_boundary_pressures_pa": [
                case.final_boundary_pressure_pa
                for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES
            ],
            "four_mpa_classifications": list(self.four_mpa_classifications),
            "four_mpa_classification_rationale": dict(
                self.four_mpa_classification_rationale
            ),
            "cfl_0p10_baseline_reproduced_exactly": True,
            "only_cfl_and_step_cap_varied": True,
            "Gate_P2_passed": False,
            "mesh_independent_crossing_verified": False,
            "CFL_independent_crossing_verified": False,
            "near_saturation_acoustic_continuity_approved": False,
            "two_phase_acoustic_accuracy_band_approved": False,
            "post_crossing_propagation_approved": False,
            "physical_validation": False,
            "design_use_acceptance": False,
            "production_hem_activation_approved": False,
            "cases": [asdict(case) for case in self.cases],
        }


CflCaseRunner = Callable[
    [PipelineDepressurizationCaseSpec, HEMPipelineDepressurizationConfig],
    PipelineCaseResult,
]
CflCaseCallback = Callable[[PipelineCaseResult, MeshCaseMetrics], None]


def run_fixed_pipeline_cfl_sensitivity_matrix(
    *,
    case_runner: CflCaseRunner = run_pipeline_depressurization_case,
    on_case_result: CflCaseCallback | None = None,
    provenance: Mapping[str, object] | None = None,
) -> HEMPipelineCflSensitivityResult:
    """Run the fixed nine-run CFL matrix with no result-dependent tuning."""

    if provenance is None:
        if case_runner is not run_pipeline_depressurization_case:
            raise HEMPipelineCflSensitivityError(
                "an injected case_runner requires explicit backend provenance"
            )
        resolved_provenance = collect_cfl_runtime_provenance()
    else:
        resolved_provenance = normalize_cfl_provenance(provenance)

    metrics: list[MeshCaseMetrics] = []
    for cfl in CFL_VALUES:
        config = HEMPipelineCflSensitivityConfig.for_cfl(cfl)
        for case in FIXED_PIPELINE_DEPRESSURIZATION_CASES:
            raw = case_runner(case, config)
            metric = replace(
                _case_metrics(raw),
                run_id=f"{case.case_id}__n{CFL_CELL_COUNT}__cfl{_cfl_token(cfl)}",
            )
            if cfl == 0.10:
                _assert_128_cell_cfl_0p10_baseline(metric)
            if on_case_result is not None:
                on_case_result(raw, metric)
            metrics.append(metric)

    classifications, rationale = classify_four_mpa_cfl_sequence(metrics)
    return HEMPipelineCflSensitivityResult(
        cases=tuple(metrics),
        four_mpa_classifications=classifications,
        four_mpa_classification_rationale=rationale,
        provenance=resolved_provenance,
    )
