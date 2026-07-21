"""Explicit pure-CO2 phase classification for HEM development.

The phase/property path is intentionally separate from acoustic closure. It
returns p, T, explicit phase, quality and void fraction where meaningful, but
never requests a speed of sound and is not connected to ``FvmSolver``.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Sequence

import numpy as np

PhaseClass = Literal[
    "compressed_or_subcooled_liquid",
    "liquid_vapor_two_phase",
    "single_phase_vapor",
    "supercritical",
    "critical_region",
    "solid_or_below_triple_guard",
    "unknown",
]
ScopeStatus = Literal["supported_candidate", "guarded_out", "unknown"]


class HEMPhaseClassificationError(RuntimeError):
    """Raised when explicit phase evaluation is unusable."""


@dataclass(frozen=True)
class HEMPhaseClassificationConfig:
    critical_temperature_margin_K: float = 0.5
    critical_pressure_margin_Pa: float = 5.0e4
    endpoint_tolerance: float = 1.0e-10

    def __post_init__(self) -> None:
        values = (
            self.critical_temperature_margin_K,
            self.critical_pressure_margin_Pa,
            self.endpoint_tolerance,
        )
        if not all(np.isfinite(value) for value in values):
            raise ValueError("phase-classification settings must be finite")
        if min(values) < 0.0:
            raise ValueError("phase-classification settings must be non-negative")


@dataclass(frozen=True)
class HEMPhaseState:
    backend_name: str
    rho: np.ndarray
    e: np.ndarray
    p: np.ndarray
    T: np.ndarray
    quality: np.ndarray
    quality_defined: np.ndarray
    alpha: np.ndarray
    alpha_defined: np.ndarray
    raw_phase: np.ndarray
    phase_class: np.ndarray
    scope_status: np.ndarray
    sound_speed_evaluated: bool = False

    def __post_init__(self) -> None:
        expected = self.rho.shape
        for name in (
            "e", "p", "T", "quality", "quality_defined", "alpha",
            "alpha_defined", "raw_phase", "phase_class", "scope_status",
        ):
            value = getattr(self, name)
            if value.shape != expected:
                raise ValueError(f"{name} must have shape {expected}; received {value.shape}")
        if self.sound_speed_evaluated:
            raise ValueError("phase-state path must not evaluate sound speed")


@dataclass(frozen=True)
class PhaseMapRecord:
    case_id: str
    source_pair: str
    source_value_1: float
    source_value_2: float
    rho_kg_m3: float
    e_j_kg: float
    p_pa: float
    T_K: float
    quality: float | None
    alpha: float | None
    raw_phase: str
    phase_class: str
    scope_status: str
    sound_speed_evaluated: bool


def normalize_coolprop_phase(raw_phase: str) -> str:
    return raw_phase.strip().lower().replace("phase_", "")


def classify_explicit_phase(
    raw_phase: str,
    *,
    p_pa: float,
    T_K: float,
    critical_pressure_pa: float,
    critical_temperature_K: float,
    triple_temperature_K: float,
    config: HEMPhaseClassificationConfig | None = None,
) -> tuple[PhaseClass, ScopeStatus]:
    """Map CoolProp phase labels to the first liquid-vapor HEM scope.

    CoolProp may label a dense state above critical pressure but below critical
    temperature as ``supercritical_liquid``. Away from the critical guard box,
    that label is retained as a dense-liquid candidate, consistent with the
    existing project property adapter. High-temperature ``supercritical`` and
    ``supercritical_gas`` states remain outside the first liquid-vapor scope.
    """

    cfg = config or HEMPhaseClassificationConfig()
    values = (p_pa, T_K, critical_pressure_pa, critical_temperature_K, triple_temperature_K)
    if not all(np.isfinite(value) for value in values):
        raise HEMPhaseClassificationError("phase-classification inputs must be finite")
    if p_pa <= 0.0 or T_K <= 0.0:
        raise HEMPhaseClassificationError("pressure and temperature must be positive")

    phase = normalize_coolprop_phase(raw_phase)
    if phase == "solid" or T_K <= triple_temperature_K:
        return "solid_or_below_triple_guard", "guarded_out"

    in_critical_box = (
        abs(T_K - critical_temperature_K) <= cfg.critical_temperature_margin_K
        and abs(p_pa - critical_pressure_pa) <= cfg.critical_pressure_margin_Pa
    )
    if phase in {"critical_point", "critical"} or in_critical_box:
        return "critical_region", "guarded_out"

    if phase in {"liquid", "subcooled_liquid", "supercritical_liquid"}:
        return "compressed_or_subcooled_liquid", "supported_candidate"
    if phase in {"twophase", "two_phase"}:
        return "liquid_vapor_two_phase", "supported_candidate"
    if phase in {"gas", "vapor", "superheated_gas"}:
        return "single_phase_vapor", "supported_candidate"
    if phase in {"supercritical", "supercritical_gas"}:
        return "supercritical", "guarded_out"
    return "unknown", "unknown"


def _coolprop_api():
    try:
        from CoolProp.CoolProp import PhaseSI, PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError("CoolProp is required for explicit HEM phase classification") from exc
    return PropsSI, PhaseSI


def _alpha_from_quality_pressure(quality: float, pressure_pa: float, *, fluid: str, props_si) -> float:
    rho_l = float(props_si("Dmass", "P", pressure_pa, "Q", 0.0, fluid))
    rho_v = float(props_si("Dmass", "P", pressure_pa, "Q", 1.0, fluid))
    v_v = quality / rho_v
    v_l = (1.0 - quality) / rho_l
    denominator = v_v + v_l
    if not np.isfinite(denominator) or denominator <= 0.0:
        raise HEMPhaseClassificationError("void-fraction denominator is invalid")
    return float(np.clip(v_v / denominator, 0.0, 1.0))


def evaluate_coolprop_hem_phase_state(
    rho: np.ndarray | float,
    e: np.ndarray | float,
    *,
    fluid: str = "CO2",
    config: HEMPhaseClassificationConfig | None = None,
) -> HEMPhaseState:
    """Evaluate explicit CoolProp phase information without sound speed."""

    cfg = config or HEMPhaseClassificationConfig()
    props_si, phase_si = _coolprop_api()
    rho_arr, e_arr = np.broadcast_arrays(np.asarray(rho, float), np.asarray(e, float))
    rho_arr = np.array(rho_arr, copy=True)
    e_arr = np.array(e_arr, copy=True)
    if not np.all(np.isfinite(rho_arr)) or np.any(rho_arr <= 0.0):
        raise HEMPhaseClassificationError("rho must be finite and strictly positive")
    if not np.all(np.isfinite(e_arr)):
        raise HEMPhaseClassificationError("e must contain only finite values")

    try:
        critical_T = float(props_si("Tcrit", fluid))
        critical_p = float(props_si("Pcrit", fluid))
        triple_T = float(props_si("Ttriple", fluid))
    except Exception as exc:  # pragma: no cover
        raise HEMPhaseClassificationError("CoolProp failed to provide CO2 limits") from exc

    shape = rho_arr.shape
    p = np.empty(shape)
    T = np.empty(shape)
    quality = np.full(shape, np.nan)
    quality_defined = np.zeros(shape, dtype=bool)
    alpha = np.full(shape, np.nan)
    alpha_defined = np.zeros(shape, dtype=bool)
    raw_phase = np.empty(shape, dtype="<U40")
    phase_class = np.empty(shape, dtype="<U40")
    scope_status = np.empty(shape, dtype="<U24")

    for index in np.ndindex(shape):  # pragma: no cover
        rho_i = float(rho_arr[index])
        e_i = float(e_arr[index])
        try:
            p_i = float(props_si("P", "Dmass", rho_i, "Umass", e_i, fluid))
            T_i = float(props_si("T", "Dmass", rho_i, "Umass", e_i, fluid))
            raw_i = str(phase_si("Dmass", rho_i, "Umass", e_i, fluid))
        except Exception as exc:
            raise HEMPhaseClassificationError(
                f"CoolProp phase evaluation failed at rho={rho_i}, e={e_i}"
            ) from exc
        if not np.isfinite(p_i) or p_i <= 0.0 or not np.isfinite(T_i) or T_i <= 0.0:
            raise HEMPhaseClassificationError("CoolProp returned invalid p/T")

        class_i, scope_i = classify_explicit_phase(
            raw_i,
            p_pa=p_i,
            T_K=T_i,
            critical_pressure_pa=critical_p,
            critical_temperature_K=critical_T,
            triple_temperature_K=triple_T,
            config=cfg,
        )
        q_i: float | None = None
        alpha_i: float | None = None
        if class_i == "compressed_or_subcooled_liquid":
            q_i, alpha_i = 0.0, 0.0
        elif class_i == "single_phase_vapor":
            q_i, alpha_i = 1.0, 1.0
        elif class_i == "liquid_vapor_two_phase":
            try:
                q_i = float(props_si("Q", "Dmass", rho_i, "Umass", e_i, fluid))
            except Exception as exc:
                raise HEMPhaseClassificationError(
                    "CoolProp failed to return quality for an explicit two-phase state"
                ) from exc
            if not np.isfinite(q_i) or q_i < -cfg.endpoint_tolerance or q_i > 1.0 + cfg.endpoint_tolerance:
                raise HEMPhaseClassificationError("two-phase quality is outside [0, 1]")
            q_i = float(np.clip(q_i, 0.0, 1.0))
            alpha_i = _alpha_from_quality_pressure(q_i, p_i, fluid=fluid, props_si=props_si)

        p[index] = p_i
        T[index] = T_i
        raw_phase[index] = normalize_coolprop_phase(raw_i)
        phase_class[index] = class_i
        scope_status[index] = scope_i
        if q_i is not None:
            quality[index] = q_i
            quality_defined[index] = True
        if alpha_i is not None:
            alpha[index] = alpha_i
            alpha_defined[index] = True

    return HEMPhaseState(
        backend_name="coolprop_co2",
        rho=rho_arr,
        e=e_arr,
        p=p,
        T=T,
        quality=quality,
        quality_defined=quality_defined,
        alpha=alpha,
        alpha_defined=alpha_defined,
        raw_phase=raw_phase,
        phase_class=phase_class,
        scope_status=scope_status,
        sound_speed_evaluated=False,
    )


def build_representative_coolprop_phase_map() -> list[PhaseMapRecord]:
    props_si, _ = _coolprop_api()
    specifications = [
        ("compressed_liquid_8mpa_280k", "PT", 8.0e6, 280.0),
        ("liquid_5mpa_280k", "PT", 5.0e6, 280.0),
        ("sat_liquid_2mpa", "PQ", 2.0e6, 0.0),
        ("two_phase_q10_2mpa", "PQ", 2.0e6, 0.10),
        ("two_phase_q50_2mpa", "PQ", 2.0e6, 0.50),
        ("two_phase_q90_2mpa", "PQ", 2.0e6, 0.90),
        ("sat_vapor_2mpa", "PQ", 2.0e6, 1.0),
        ("superheated_vapor_1mpa_280k", "PT", 1.0e6, 280.0),
        ("supercritical_8mpa_310k", "PT", 8.0e6, 310.0),
    ]
    records: list[PhaseMapRecord] = []
    for case_id, pair, value_1, value_2 in specifications:  # pragma: no cover
        second_name = "T" if pair == "PT" else "Q"
        rho = float(props_si("Dmass", "P", value_1, second_name, value_2, "CO2"))
        e = float(props_si("Umass", "P", value_1, second_name, value_2, "CO2"))
        state = evaluate_coolprop_hem_phase_state(rho, e)
        records.append(
            PhaseMapRecord(
                case_id=case_id,
                source_pair=pair,
                source_value_1=value_1,
                source_value_2=value_2,
                rho_kg_m3=rho,
                e_j_kg=e,
                p_pa=float(state.p),
                T_K=float(state.T),
                quality=float(state.quality) if bool(state.quality_defined) else None,
                alpha=float(state.alpha) if bool(state.alpha_defined) else None,
                raw_phase=str(state.raw_phase),
                phase_class=str(state.phase_class),
                scope_status=str(state.scope_status),
                sound_speed_evaluated=False,
            )
        )
    return records


def write_phase_map_artifacts(output_dir: str | Path, records: Sequence[PhaseMapRecord]) -> dict[str, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_coolprop_phase_map"
    rows = [asdict(record) for record in records]
    payload = {
        "schema_version": "stage7_lco2_hem_coolprop_phase_map_v1",
        "scope": "verification_only",
        "backend_name": "coolprop_co2",
        "production_solver_connected": False,
        "production_solver_behavior_changed": False,
        "explicit_phase_classification_added": True,
        "sound_speed_evaluated": False,
        "equilibrium_two_phase_sound_speed_closure_approved": False,
        "critical_region_guarded_out": True,
        "solid_region_guarded_out": True,
        "supercritical_in_current_liquid_vapor_scope": False,
        "supercritical_liquid_dense_state_supported_candidate": True,
        "physical_validation": False,
        "design_use_acceptance": False,
        "results": rows,
    }
    json_path = destination / f"{stem}.json"
    csv_path = destination / f"{stem}.csv"
    markdown_path = destination / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Stage 7 LCO2 HEM CoolProp Phase Map",
        "",
        "`VERIFICATION ONLY; SOUND SPEED NOT EVALUATED`",
        "",
        "| case | raw phase | phase class | scope | p [Pa] | T [K] | q | alpha |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        q = "undefined" if row["quality"] is None else f'{row["quality"]:.6g}'
        a = "undefined" if row["alpha"] is None else f'{row["alpha"]:.6g}'
        lines.append(
            f'| {row["case_id"]} | {row["raw_phase"]} | {row["phase_class"]} | '
            f'{row["scope_status"]} | {row["p_pa"]:.8g} | {row["T_K"]:.8g} | {q} | {a} |'
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "markdown": markdown_path}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate explicit CoolProp HEM phase-map evidence.")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    paths = write_phase_map_artifacts(args.output_dir, build_representative_coolprop_phase_map())
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
