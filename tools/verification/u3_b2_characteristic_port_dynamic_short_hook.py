from __future__ import annotations

import math
from typing import Any

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic
from liquid_gas_transient.grid import UniformGrid
from liquid_gas_transient.state import IDX_MOM, IDX_RHO, IDX_RHOE, IDX_RHO_XV
from liquid_gas_transient.u3_b2_fvm_discharge_adapter import (
    BOUNDARY_UPDATE_POSITIVITY_FAILURE,
    CoolPropB2StateProvider,
    normalize_phase,
)
from u3_b2_characteristic_port_dynamic_short_model import solve_dynamic_root


class A1DynamicShortHook:
    """Diagnostic-only A1 port recomputed from the evolving outlet cell."""

    failure_outcome = BOUNDARY_UPDATE_POSITIVITY_FAILURE

    def __init__(
        self,
        *,
        contract: dict[str, Any],
        b1_contract: dict[str, Any],
        case_id: str,
        provider: CoolPropB2StateProvider,
    ) -> None:
        self.contract = contract
        self.case_id = case_id
        self.case = diagnostic._case(contract, case_id)
        self.state_id = str(self.case["state_id"])
        self.provider = provider
        self.area_m2 = float(contract["geometry"]["pipe_area_m2"])
        self.adapter = diagnostic.adapter_for_case(
            contract,
            b1_contract,
            self.case,
            provider=provider,
        )
        self.maximum_halvings = int(
            contract["time_step_and_update"]["deterministic_halving"][
                "maximum_halvings"
            ]
        )
        self._cache_t: float | None = None
        self._cache_outlet: np.ndarray | None = None
        self._previous_root_pressure_pa: float | None = None
        self.root_context: dict[str, Any] | None = None
        self.flux = np.zeros(4, dtype=float)
        self.last_dt_limits: dict[str, float] = {}
        self.trial_dts_s: list[float] = []

    def _ensure_root(self, U: np.ndarray, t: float) -> None:
        cached = bool(
            self._cache_t == float(t)
            and self._cache_outlet is not None
            and np.array_equal(self._cache_outlet, U[-1])
            and self.root_context is not None
        )
        if cached:
            return
        context = solve_dynamic_root(
            contract=self.contract,
            case_id=self.case_id,
            state_id=self.state_id,
            provider=self.provider,
            adapter=self.adapter,
            area_m2=self.area_m2,
            outlet_conserved=U[-1],
            solver_time_s=t,
            previous_root_pressure_pa=self._previous_root_pressure_pa,
        )
        self.root_context = context
        self.flux = np.array(context["flux"], copy=True)
        self._cache_t = float(t)
        self._cache_outlet = np.array(U[-1], copy=True)
        self.trial_dts_s = []

    @property
    def velocity_tolerance(self) -> float:
        if self.root_context is None:
            return float(
                self.contract["acceptance_tolerances"][
                    "velocity_zero_tolerance_m_s"
                ]
            )
        return float(self.root_context["velocity_tolerance_m_s"])

    @property
    def allowed_phases(self) -> set[str]:
        if self.root_context is None:
            return {
                normalize_phase(value)
                for value in diagnostic._family(self.contract, self.state_id)[
                    "allowed_normalized_phases"
                ]
            }
        return set(self.root_context["allowed_phases"])

    def limit_dt(
        self,
        *,
        U: np.ndarray,
        eos,
        grid: UniformGrid,
        t: float,
        candidate_dt: float,
    ) -> float:
        del eos
        if not math.isfinite(candidate_dt) or candidate_dt <= 0.0:
            raise ValueError("candidate_dt must be positive and finite")
        self._ensure_root(U, t)
        mass_rate = float(self.flux[IDX_RHO] * self.area_m2)
        energy_rate = float(self.flux[IDX_RHOE] * self.area_m2)
        cell_volume = self.area_m2 * grid.dx
        mass_dt = math.inf
        if mass_rate > 0.0:
            mass_dt = (
                float(
                    self.contract["time_step_and_update"][
                        "boundary_mass_removal_fraction_limit"
                    ]
                )
                * float(U[-1, IDX_RHO])
                * cell_volume
                / mass_rate
            )
        energy_dt = math.inf
        if energy_rate > 0.0:
            energy_dt = (
                float(
                    self.contract["time_step_and_update"][
                        "boundary_energy_removal_fraction_limit"
                    ]
                )
                * float(U[-1, IDX_RHOE])
                * cell_volume
                / energy_rate
            )
        accepted = min(float(candidate_dt), mass_dt, energy_dt)
        self.last_dt_limits = {
            "candidate_dt_s": float(candidate_dt),
            "mass_removal_dt_s": float(mass_dt),
            "energy_removal_dt_s": float(energy_dt),
            "accepted_dt_s": float(accepted),
        }
        return float(accepted)

    def evaluate_flux(
        self,
        *,
        U: np.ndarray,
        eos,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> np.ndarray:
        del eos, grid
        self._ensure_root(U, t)
        self.trial_dts_s.append(float(dt))
        return np.array(self.flux, copy=True)

    def validate_trial(
        self,
        *,
        U_before: np.ndarray,
        U_trial: np.ndarray,
        eos,
        grid: UniformGrid,
        t: float,
        dt: float,
    ) -> None:
        del U_before, eos, grid, t, dt
        if not np.all(np.isfinite(U_trial)):
            raise ValueError("trial conserved state contains a nonfinite value")
        rho = U_trial[:, IDX_RHO]
        if np.any(rho <= 0.0):
            raise ValueError("trial density must be positive")
        velocity = U_trial[:, IDX_MOM] / rho
        internal = U_trial[:, IDX_RHOE] / rho - 0.5 * velocity * velocity
        if np.any(~np.isfinite(internal)) or np.any(internal <= 0.0):
            raise ValueError("trial internal energy must be positive")
        if float(velocity[-1]) < -self.velocity_tolerance:
            raise ValueError("trial outlet velocity is reverse-directed")
        if not np.all(U_trial[:, IDX_RHO_XV] == 0.0):
            raise ValueError("single-phase rho*xv identity must remain exact zero")
        allowed = self.allowed_phases
        for row in U_trial:
            reconstruction = self.provider.reconstruct_from_conserved(row)
            if normalize_phase(reconstruction.static.phase) not in allowed:
                raise ValueError(
                    f"trial phase {reconstruction.static.phase!r} is outside "
                    f"{sorted(allowed)}"
                )

    def accept_current_root(self) -> None:
        if self.root_context is None:
            raise AssertionError("no current root to accept")
        self._previous_root_pressure_pa = float(
            self.root_context["root"]["pressure_pa"]
        )
