from __future__ import annotations

import csv
from types import SimpleNamespace

import numpy as np
import pytest

from liquid_gas_transient.boundary_history import (
    record_solver_boundary_telemetry,
    write_boundary_history_csv,
)
from liquid_gas_transient.boundary_telemetry import (
    BOUNDARY_FACE_DEFINITION,
    BOUNDARY_HISTORY_COLUMNS,
    BoundaryTelemetryRecorder,
    diagnostic_boundary_face_primitive,
)
from liquid_gas_transient.eos import LinearLiquidEOS
from liquid_gas_transient.flux import rusanov_flux
from liquid_gas_transient.state import make_conserved
from liquid_gas_transient.verification.boundary_reflection import (
    acoustic_impedance,
    characteristic_amplitudes,
    evaluation_windows,
    expected_reflection_coefficients,
    theoretical_reflection_timing,
)


def test_characteristic_amplitudes_separate_right_running_wave() -> None:
    rho0, c0, dp = 900.0, 500.0, 1200.0
    a_plus, a_minus = characteristic_amplitudes(dp, dp / acoustic_impedance(rho0, c0), rho0, c0)
    assert a_plus == pytest.approx(dp)
    assert a_minus == pytest.approx(0.0, abs=1e-12)


def test_characteristic_amplitudes_separate_left_running_wave() -> None:
    rho0, c0, dp = 900.0, 500.0, -1200.0
    a_plus, a_minus = characteristic_amplitudes(dp, -dp / acoustic_impedance(rho0, c0), rho0, c0)
    assert a_plus == pytest.approx(0.0, abs=1e-12)
    assert a_minus == pytest.approx(dp)


def test_expected_ideal_reflection_coefficients() -> None:
    assert expected_reflection_coefficients("rigid_wall") == {
        "pressure_reflection_coefficient": 1.0,
        "velocity_reflection_coefficient": -1.0,
    }
    assert expected_reflection_coefficients("fixed_pressure") == {
        "pressure_reflection_coefficient": -1.0,
        "velocity_reflection_coefficient": 1.0,
    }


def test_theoretical_timing_satisfies_roundtrip_identity() -> None:
    timing = theoretical_reflection_timing(
        pipe_length_m=100.0,
        pulse_center_x_m=50.0,
        probe_x_m=90.0,
        c0_m_s=500.0,
        pulse_sigma_m=3.0,
    )
    assert timing["theoretical_reflected_time_s"] - timing["theoretical_incident_time_s"] == pytest.approx(
        timing["theoretical_roundtrip_delay_s"]
    )


def test_evaluation_windows_clip_overlap_at_midpoint() -> None:
    timing = theoretical_reflection_timing(
        pipe_length_m=100.0,
        pulse_center_x_m=50.0,
        probe_x_m=90.0,
        c0_m_s=500.0,
        pulse_sigma_m=15.0,
    )
    windows = evaluation_windows(timing)
    assert windows["window_clip_applied"] is True
    assert windows["incident_window_end_s"] == pytest.approx(windows["boundary_window_start_s"])
    assert windows["boundary_window_end_s"] == pytest.approx(windows["reflected_window_start_s"])
    assert windows["window_clip_reasons"]


def test_diagnostic_face_primitive_is_midpoint_of_flux_input_states() -> None:
    eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
    left = make_conserved(rho=1000.0, u=-2.0, e=1.0e5, xv=0.0)
    right = make_conserved(rho=1000.2, u=4.0, e=1.02e5, xv=0.0)
    face = diagnostic_boundary_face_primitive(left, right, eos)
    prim_l = eos.primitive_from_conserved(left[np.newaxis, :])
    prim_r = eos.primitive_from_conserved(right[np.newaxis, :])
    assert face["boundary_face_velocity_m_s"] == pytest.approx(0.5 * (prim_l.u[0] + prim_r.u[0]))
    assert face["boundary_face_pressure_pa"] == pytest.approx(0.5 * (prim_l.p[0] + prim_r.p[0]))
    assert face["boundary_face_velocity_m_s"] not in (prim_l.u[0], prim_r.u[0])


class _SyntheticSolver:
    def __init__(self) -> None:
        self.n_ghost = 1
        self.step_count = 3
        self.t = 0.2
        self.eos = LinearLiquidEOS(rho_ref=1000.0, p_ref=1.0e5, c_ref=1000.0)
        self.grid = SimpleNamespace(n_cells=2)
        self._internal = make_conserved(
            rho=np.array([1000.0, 1000.1]),
            u=np.array([1.0, 2.0]),
            e=np.array([1.0e5, 1.0e5]),
            xv=np.zeros(2),
        )

    def extend_with_ghosts(self, t: float) -> np.ndarray:
        assert t == self.t
        out = np.empty((4, 4))
        out[1:3] = self._internal
        out[0] = self._internal[0]
        out[3] = self._internal[1].copy()
        out[3, 1] *= -1.0
        return out

    def flux_function(self, U_left: np.ndarray, U_right: np.ndarray, eos: LinearLiquidEOS) -> np.ndarray:
        return rusanov_flux(U_left, U_right, eos)


def test_pre_step_solver_sampler_records_exact_external_fluxes() -> None:
    solver = _SyntheticSolver()
    recorder = BoundaryTelemetryRecorder(area_m2=2.0)
    record_solver_boundary_telemetry(solver, recorder, dt_s=0.01)
    rows = recorder.rows()
    assert len(rows) == 2
    assert rows[0]["step"] == 4
    assert rows[1]["side"] == "right"
    assert rows[1]["boundary_face_definition"] == BOUNDARY_FACE_DEFINITION
    assert rows[1]["boundary_face_velocity_m_s"] == pytest.approx(0.0)
    assert rows[1]["numerical_mass_flux_kg_m2_s"] == pytest.approx(0.0, abs=1e-12)
    assert rows[1]["domain_momentum_rate_n"] == pytest.approx(-rows[1]["numerical_momentum_flow_rate_n"])


def test_boundary_history_csv_uses_declared_schema(tmp_path) -> None:
    solver = _SyntheticSolver()
    recorder = BoundaryTelemetryRecorder(area_m2=1.0)
    record_solver_boundary_telemetry(solver, recorder, dt_s=0.01)
    output = write_boundary_history_csv(tmp_path / "synthetic_boundary_history.csv", recorder.rows())
    with output.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames or ()) == BOUNDARY_HISTORY_COLUMNS
        assert len(list(reader)) == 2


def test_boundary_history_csv_rejects_empty_history(tmp_path) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        write_boundary_history_csv(tmp_path / "empty_boundary_history.csv", [])
