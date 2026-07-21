"""Verification-first equilibrium sound-speed estimates for pure-CO2 HEM.

The module evaluates the isentropic derivative of an equilibrium pressure closure
``p(rho, e)`` using

    c_eq**2 = (dp/drho)|e + p/rho**2 * (dp/de)|rho.

It is intentionally independent of ``FvmSolver``.  CoolProp is used only to
obtain equilibrium pressure and explicit phase information at finite-difference
stencil states.  CoolProp's speed-of-sound output is never requested for
liquid-vapor two-phase states.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from .hem_phase_classification import (
    HEMPhaseClassificationError,
    evaluate_coolprop_hem_phase_state,
)


class HEMEquilibriumSoundSpeedError(RuntimeError):
    """Raised when a guarded equilibrium acoustic estimate cannot be formed."""


@dataclass(frozen=True)
class PressurePhaseSample:
    """Pressure and phase metadata at one scalar ``rho/e`` state."""

    pressure_pa: float
    phase_class: str
    scope_status: str


PressurePhaseEvaluator = Callable[[float, float], PressurePhaseSample]


@dataclass(frozen=True)
class HEMEquilibriumSoundSpeedConfig:
    """Finite-difference and guard settings for the acoustic scaffold."""

    relative_density_step: float = 1.0e-4
    relative_energy_step: float = 1.0e-4
    minimum_density_step_kg_m3: float = 1.0e-6
    minimum_energy_step_j_kg: float = 1.0e-2
    max_step_halvings: int = 12
    require_same_phase_class: bool = True
    minimum_sound_speed_squared_m2_s2: float = 0.0

    def __post_init__(self) -> None:
        float_values = (
            self.relative_density_step,
            self.relative_energy_step,
            self.minimum_density_step_kg_m3,
            self.minimum_energy_step_j_kg,
            self.minimum_sound_speed_squared_m2_s2,
        )
        if not all(np.isfinite(value) for value in float_values):
            raise ValueError("sound-speed configuration values must be finite")
        if self.relative_density_step <= 0.0:
            raise ValueError("relative_density_step must be positive")
        if self.relative_energy_step <= 0.0:
            raise ValueError("relative_energy_step must be positive")
        if self.minimum_density_step_kg_m3 <= 0.0:
            raise ValueError("minimum_density_step_kg_m3 must be positive")
        if self.minimum_energy_step_j_kg <= 0.0:
            raise ValueError("minimum_energy_step_j_kg must be positive")
        if self.max_step_halvings < 0:
            raise ValueError("max_step_halvings must be non-negative")
        if self.minimum_sound_speed_squared_m2_s2 < 0.0:
            raise ValueError("minimum sound-speed squared must be non-negative")


@dataclass(frozen=True)
class HEMEquilibriumSoundSpeedEstimate:
    """One scalar equilibrium acoustic estimate and its diagnostics."""

    rho_kg_m3: float
    e_j_kg: float
    pressure_pa: float
    phase_class: str
    dp_drho_at_e: float
    dp_de_at_rho: float
    density_term_m2_s2: float
    energy_term_m2_s2: float
    sound_speed_squared_m2_s2: float
    sound_speed_m_s: float
    density_step_kg_m3: float
    energy_step_j_kg: float
    density_step_halvings: int
    energy_step_halvings: int
    stencil_phase_preserved: bool


@dataclass(frozen=True)
class EquilibriumSoundSpeedMapRecord:
    """One representative CoolProp state and acoustic estimate."""

    case_id: str
    source_pair: str
    source_value_1: float
    source_value_2: float
    rho_kg_m3: float
    e_j_kg: float
    p_pa: float
    T_K: float
    phase_class: str
    raw_phase: str
    quality: float | None
    alpha: float | None
    estimated_equilibrium_sound_speed_m_s: float
    sound_speed_squared_m2_s2: float
    dp_drho_at_e: float
    dp_de_at_rho: float
    density_term_m2_s2: float
    energy_term_m2_s2: float
    density_step_kg_m3: float
    energy_step_j_kg: float
    density_step_halvings: int
    energy_step_halvings: int
    single_phase_reference_sound_speed_m_s: float | None
    single_phase_reference_relative_error: float | None
    single_phase_reference_evaluated: bool
    coolprop_two_phase_sound_speed_requested: bool


def _validate_sample(sample: PressurePhaseSample) -> PressurePhaseSample:
    pressure = float(sample.pressure_pa)
    if not np.isfinite(pressure) or pressure <= 0.0:
        raise HEMEquilibriumSoundSpeedError("pressure sample must be finite and positive")
    if sample.scope_status != "supported_candidate":
        raise HEMEquilibriumSoundSpeedError(
            f"phase state is outside the supported candidate scope: {sample.scope_status}"
        )
    if not sample.phase_class:
        raise HEMEquilibriumSoundSpeedError("phase_class must be non-empty")
    return PressurePhaseSample(
        pressure_pa=pressure,
        phase_class=str(sample.phase_class),
        scope_status=str(sample.scope_status),
    )


def _evaluate_guarded(
    evaluator: PressurePhaseEvaluator,
    rho: float,
    e: float,
) -> PressurePhaseSample:
    try:
        return _validate_sample(evaluator(float(rho), float(e)))
    except HEMEquilibriumSoundSpeedError:
        raise
    except Exception as exc:
        raise HEMEquilibriumSoundSpeedError(
            f"pressure/phase evaluation failed at rho={rho}, e={e}"
        ) from exc


def _central_stencil(
    evaluator: PressurePhaseEvaluator,
    *,
    rho: float,
    e: float,
    center_phase_class: str,
    axis: str,
    initial_step: float,
    config: HEMEquilibriumSoundSpeedConfig,
) -> tuple[PressurePhaseSample, PressurePhaseSample, float, int]:
    for halvings in range(config.max_step_halvings + 1):
        step = initial_step / (2.0**halvings)
        if axis == "rho":
            minus_rho, plus_rho = rho - step, rho + step
            minus_e = plus_e = e
            if minus_rho <= 0.0:
                continue
        elif axis == "e":
            minus_rho = plus_rho = rho
            minus_e, plus_e = e - step, e + step
        else:  # pragma: no cover - internal contract
            raise ValueError(f"unsupported axis: {axis}")

        try:
            minus = _evaluate_guarded(evaluator, minus_rho, minus_e)
            plus = _evaluate_guarded(evaluator, plus_rho, plus_e)
        except HEMEquilibriumSoundSpeedError:
            continue

        if config.require_same_phase_class and (
            minus.phase_class != center_phase_class
            or plus.phase_class != center_phase_class
        ):
            continue
        return minus, plus, step, halvings

    raise HEMEquilibriumSoundSpeedError(
        f"no valid central {axis} stencil found after "
        f"{config.max_step_halvings} halvings"
    )


def estimate_equilibrium_sound_speed(
    rho_kg_m3: float,
    e_j_kg: float,
    evaluator: PressurePhaseEvaluator,
    *,
    config: HEMEquilibriumSoundSpeedConfig | None = None,
) -> HEMEquilibriumSoundSpeedEstimate:
    """Estimate equilibrium sound speed from a guarded ``p(rho,e)`` closure."""

    cfg = config or HEMEquilibriumSoundSpeedConfig()
    rho = float(rho_kg_m3)
    e = float(e_j_kg)
    if not np.isfinite(rho) or rho <= 0.0:
        raise HEMEquilibriumSoundSpeedError("rho must be finite and positive")
    if not np.isfinite(e):
        raise HEMEquilibriumSoundSpeedError("e must be finite")

    center = _evaluate_guarded(evaluator, rho, e)
    density_step_0 = max(
        cfg.relative_density_step * abs(rho),
        cfg.minimum_density_step_kg_m3,
    )
    energy_scale = max(abs(e), 1.0)
    energy_step_0 = max(
        cfg.relative_energy_step * energy_scale,
        cfg.minimum_energy_step_j_kg,
    )

    rho_minus, rho_plus, density_step, rho_halvings = _central_stencil(
        evaluator,
        rho=rho,
        e=e,
        center_phase_class=center.phase_class,
        axis="rho",
        initial_step=density_step_0,
        config=cfg,
    )
    e_minus, e_plus, energy_step, e_halvings = _central_stencil(
        evaluator,
        rho=rho,
        e=e,
        center_phase_class=center.phase_class,
        axis="e",
        initial_step=energy_step_0,
        config=cfg,
    )

    dp_drho_at_e = (
        rho_plus.pressure_pa - rho_minus.pressure_pa
    ) / (2.0 * density_step)
    dp_de_at_rho = (
        e_plus.pressure_pa - e_minus.pressure_pa
    ) / (2.0 * energy_step)
    density_term = dp_drho_at_e
    energy_term = center.pressure_pa / (rho * rho) * dp_de_at_rho
    c_squared = density_term + energy_term
    if not np.isfinite(c_squared):
        raise HEMEquilibriumSoundSpeedError("sound-speed squared is not finite")
    if c_squared <= cfg.minimum_sound_speed_squared_m2_s2:
        raise HEMEquilibriumSoundSpeedError(
            "sound-speed squared is non-positive or below the configured minimum"
        )

    return HEMEquilibriumSoundSpeedEstimate(
        rho_kg_m3=rho,
        e_j_kg=e,
        pressure_pa=center.pressure_pa,
        phase_class=center.phase_class,
        dp_drho_at_e=float(dp_drho_at_e),
        dp_de_at_rho=float(dp_de_at_rho),
        density_term_m2_s2=float(density_term),
        energy_term_m2_s2=float(energy_term),
        sound_speed_squared_m2_s2=float(c_squared),
        sound_speed_m_s=float(np.sqrt(c_squared)),
        density_step_kg_m3=float(density_step),
        energy_step_j_kg=float(energy_step),
        density_step_halvings=rho_halvings,
        energy_step_halvings=e_halvings,
        stencil_phase_preserved=True,
    )


def evaluate_coolprop_pressure_phase(rho: float, e: float) -> PressurePhaseSample:
    """Evaluate CoolProp pressure and explicit phase without requesting sound speed."""

    try:
        state = evaluate_coolprop_hem_phase_state(
            np.asarray([rho], dtype=float),
            np.asarray([e], dtype=float),
        )
    except HEMPhaseClassificationError as exc:
        raise HEMEquilibriumSoundSpeedError(
            "CoolProp equilibrium pressure/phase evaluation failed"
        ) from exc
    return PressurePhaseSample(
        pressure_pa=float(state.p[0]),
        phase_class=str(state.phase_class[0]),
        scope_status=str(state.scope_status[0]),
    )


def estimate_coolprop_equilibrium_sound_speed(
    rho_kg_m3: float,
    e_j_kg: float,
    *,
    config: HEMEquilibriumSoundSpeedConfig | None = None,
) -> HEMEquilibriumSoundSpeedEstimate:
    """Estimate pure-CO2 equilibrium sound speed from CoolProp ``p(rho,e)``."""

    return estimate_equilibrium_sound_speed(
        rho_kg_m3,
        e_j_kg,
        evaluate_coolprop_pressure_phase,
        config=config,
    )


def _coolprop_props_si():
    try:
        from CoolProp.CoolProp import PropsSI  # type: ignore
    except Exception as exc:  # pragma: no cover - installed-only path
        raise ImportError("CoolProp is required for the equilibrium sound-speed map") from exc
    return PropsSI


def build_representative_equilibrium_sound_speed_map(
    *,
    config: HEMEquilibriumSoundSpeedConfig | None = None,
) -> list[EquilibriumSoundSpeedMapRecord]:
    """Build liquid, open-two-phase and vapor sound-speed evidence."""

    props_si = _coolprop_props_si()
    specifications = [
        ("dense_liquid_8mpa_280k", "PT", 8.0e6, 280.0),
        ("liquid_5mpa_280k", "PT", 5.0e6, 280.0),
        ("two_phase_q05_2mpa", "PQ", 2.0e6, 0.05),
        ("two_phase_q10_2mpa", "PQ", 2.0e6, 0.10),
        ("two_phase_q25_2mpa", "PQ", 2.0e6, 0.25),
        ("two_phase_q50_2mpa", "PQ", 2.0e6, 0.50),
        ("two_phase_q75_2mpa", "PQ", 2.0e6, 0.75),
        ("two_phase_q90_2mpa", "PQ", 2.0e6, 0.90),
        ("two_phase_q95_2mpa", "PQ", 2.0e6, 0.95),
        ("vapor_1mpa_280k", "PT", 1.0e6, 280.0),
    ]

    records: list[EquilibriumSoundSpeedMapRecord] = []
    for case_id, pair, value_1, value_2 in specifications:  # pragma: no cover
        if pair == "PT":
            rho = float(props_si("Dmass", "P", value_1, "T", value_2, "CO2"))
            e = float(props_si("Umass", "P", value_1, "T", value_2, "CO2"))
        else:
            rho = float(props_si("Dmass", "P", value_1, "Q", value_2, "CO2"))
            e = float(props_si("Umass", "P", value_1, "Q", value_2, "CO2"))

        phase_state = evaluate_coolprop_hem_phase_state(
            np.asarray([rho]), np.asarray([e])
        )
        estimate = estimate_coolprop_equilibrium_sound_speed(
            rho, e, config=config
        )
        phase_class = str(phase_state.phase_class[0])
        is_two_phase = phase_class == "liquid_vapor_two_phase"

        reference: float | None = None
        relative_error: float | None = None
        if not is_two_phase:
            reference = float(
                props_si("A", "Dmass", rho, "Umass", e, "CO2")
            )
            relative_error = abs(estimate.sound_speed_m_s - reference) / reference

        quality = (
            float(phase_state.quality[0])
            if bool(phase_state.quality_defined[0])
            else None
        )
        alpha = (
            float(phase_state.alpha[0])
            if bool(phase_state.alpha_defined[0])
            else None
        )
        records.append(
            EquilibriumSoundSpeedMapRecord(
                case_id=case_id,
                source_pair=pair,
                source_value_1=value_1,
                source_value_2=value_2,
                rho_kg_m3=rho,
                e_j_kg=e,
                p_pa=float(phase_state.p[0]),
                T_K=float(phase_state.T[0]),
                phase_class=phase_class,
                raw_phase=str(phase_state.raw_phase[0]),
                quality=quality,
                alpha=alpha,
                estimated_equilibrium_sound_speed_m_s=estimate.sound_speed_m_s,
                sound_speed_squared_m2_s2=estimate.sound_speed_squared_m2_s2,
                dp_drho_at_e=estimate.dp_drho_at_e,
                dp_de_at_rho=estimate.dp_de_at_rho,
                density_term_m2_s2=estimate.density_term_m2_s2,
                energy_term_m2_s2=estimate.energy_term_m2_s2,
                density_step_kg_m3=estimate.density_step_kg_m3,
                energy_step_j_kg=estimate.energy_step_j_kg,
                density_step_halvings=estimate.density_step_halvings,
                energy_step_halvings=estimate.energy_step_halvings,
                single_phase_reference_sound_speed_m_s=reference,
                single_phase_reference_relative_error=relative_error,
                single_phase_reference_evaluated=not is_two_phase,
                coolprop_two_phase_sound_speed_requested=False,
            )
        )
    return records


def write_equilibrium_sound_speed_artifacts(
    output_dir: str | Path,
    records: list[EquilibriumSoundSpeedMapRecord],
) -> dict[str, Path]:
    """Write JSON, CSV and Markdown verification evidence."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = "stage7_lco2_hem_equilibrium_sound_speed"
    rows = [asdict(record) for record in records]
    payload = {
        "schema_version": "stage7_lco2_hem_equilibrium_sound_speed_v1",
        "scope": "verification_only",
        "closure": "rho_e_finite_difference_isentropic_identity_v1",
        "identity": "c2=dp_drho_at_e+(p/rho2)*dp_de_at_rho",
        "production_solver_connected": False,
        "production_cfl_connected": False,
        "production_flux_connected": False,
        "equilibrium_two_phase_sound_speed_closure_approved": False,
        "coolprop_two_phase_sound_speed_requested": False,
        "single_phase_reference_check_present": True,
        "physical_validation": False,
        "design_use_acceptance": False,
        "numeric_accuracy_band_approved": False,
        "results": rows,
    }

    json_path = destination / f"{stem}.json"
    csv_path = destination / f"{stem}.csv"
    markdown_path = destination / f"{stem}.md"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Stage 7 LCO2 HEM Equilibrium Sound-Speed Scaffold",
        "",
        "`VERIFICATION ONLY; NOT CONNECTED TO FVM`",
        "",
        "- closure approved: `False`",
        "- CoolProp two-phase sound speed requested: `False`",
        "- physical Validation: `False`",
        "- design-use acceptance: `False`",
        "",
        "| case | phase | q | alpha | c_eq [m/s] | single-phase reference [m/s] | rel. error |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        q = "-" if row["quality"] is None else f"{row['quality']:.6g}"
        alpha = "-" if row["alpha"] is None else f"{row['alpha']:.6g}"
        ref = (
            "-"
            if row["single_phase_reference_sound_speed_m_s"] is None
            else f"{row['single_phase_reference_sound_speed_m_s']:.8g}"
        )
        err = (
            "-"
            if row["single_phase_reference_relative_error"] is None
            else f"{row['single_phase_reference_relative_error']:.6g}"
        )
        lines.append(
            f"| {row['case_id']} | {row['phase_class']} | {q} | {alpha} | "
            f"{row['estimated_equilibrium_sound_speed_m_s']:.8g} | {ref} | {err} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "markdown": markdown_path}


def run_equilibrium_sound_speed_verification(
    output_dir: str | Path,
) -> dict[str, Path]:
    records = build_representative_equilibrium_sound_speed_map()
    return write_equilibrium_sound_speed_artifacts(output_dir, records)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Stage 7 HEM equilibrium sound-speed evidence."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    paths = run_equilibrium_sound_speed_verification(args.output_dir)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
