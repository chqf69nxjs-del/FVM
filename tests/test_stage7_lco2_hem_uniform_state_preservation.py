from __future__ import annotations

import json

import numpy as np
import pytest

from liquid_gas_transient.hem_uniform_state_preservation import (
    HEMUniformStatePreservationConfig,
    HEMUniformStatePreservationError,
    VerificationHEMEquilibriumEOS,
    run_uniform_hem_state_preservation,
    write_uniform_state_artifacts,
)
from liquid_gas_transient.state import make_conserved


pytestmark = pytest.mark.coolprop_installed


def _props_si():
    coolprop = pytest.importorskip("CoolProp")
    return coolprop.CoolProp.PropsSI


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pressure_pa", 0.0),
        ("quality", 0.0),
        ("quality", 1.0),
        ("length_m", -1.0),
        ("n_cells", 1),
        ("cfl", 0.0),
        ("n_steps", 0),
        ("absolute_drift_tolerance", -1.0),
        ("relative_drift_tolerance", np.nan),
    ],
)
def test_config_rejects_invalid_values(field, value):
    with pytest.raises(ValueError):
        HEMUniformStatePreservationConfig(**{field: value})


def test_verification_eos_recovers_open_two_phase_primitive_state():
    props_si = _props_si()
    pressure = 2.0e6
    quality = 0.50
    rho = float(props_si("Dmass", "P", pressure, "Q", quality, "CO2"))
    e = float(props_si("Umass", "P", pressure, "Q", quality, "CO2"))
    U = make_conserved(
        np.full(3, rho),
        np.zeros(3),
        np.full(3, e),
        np.full(3, quality),
    )

    eos = VerificationHEMEquilibriumEOS()
    prim = eos.primitive_from_conserved(U)

    assert np.all(prim.p == pytest.approx(pressure, rel=1.0e-10))
    assert np.all(prim.xv == pytest.approx(quality, abs=1.0e-8))
    assert np.all(prim.alpha > quality)
    assert np.all(prim.c > 0.0)
    assert np.all(prim.u == 0.0)
    assert eos.cache_size == 1
    assert eos.phase_evaluation_count == 1
    assert eos.sound_speed_evaluation_count == 1


def test_verification_eos_rejects_transported_quality_mismatch():
    props_si = _props_si()
    pressure = 2.0e6
    equilibrium_quality = 0.50
    rho = float(
        props_si("Dmass", "P", pressure, "Q", equilibrium_quality, "CO2")
    )
    e = float(props_si("Umass", "P", pressure, "Q", equilibrium_quality, "CO2"))
    U = make_conserved(rho, 0.0, e, 0.40)

    with pytest.raises(HEMUniformStatePreservationError, match="does not match"):
        VerificationHEMEquilibriumEOS().primitive_from_conserved(U)


def test_uniform_two_phase_state_is_preserved_by_first_order_fvm():
    result = run_uniform_hem_state_preservation(
        HEMUniformStatePreservationConfig(n_cells=4, n_steps=4, cfl=0.25)
    )
    summary = result.summary

    assert summary["uniform_state_preserved"] is True
    assert summary["fvm_solver_exercised"] is True
    assert summary["rusanov_flux_exercised"] is True
    assert summary["cfl_exercised"] is True
    assert summary["verification_only_hem_eos_adapter"] is True
    assert summary["production_default_changed"] is False
    assert summary["production_hem_activation_approved"] is False
    assert summary["physical_validation"] is False
    assert summary["design_use_acceptance"] is False
    assert summary["conserved_max_abs_drift"] <= 1.0e-10
    assert summary["conserved_max_relative_drift"] <= 1.0e-12
    assert summary["cfl_max"] == pytest.approx(0.25)
    assert np.array_equal(result.initial_U, result.final_U)
    assert len(result.history) == 5
    assert all(row["p_max_abs_drift_pa"] == 0.0 for row in result.history)
    assert all(row["quality_max_abs_drift"] == 0.0 for row in result.history)
    assert all(row["alpha_max_abs_drift"] == 0.0 for row in result.history)


def test_uniform_state_artifacts_are_traceable(tmp_path):
    result = run_uniform_hem_state_preservation(
        HEMUniformStatePreservationConfig(n_cells=3, n_steps=2)
    )
    files = write_uniform_state_artifacts(tmp_path, result)

    assert set(files) == {"json", "csv", "markdown", "npz"}
    assert all(path.is_file() for path in files.values())

    payload = json.loads(files["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "stage7_lco2_hem_uniform_state_preservation_v1"
    assert payload["scope"] == "verification_only"
    assert payload["uniform_state_preserved"] is True
    assert payload["equilibrium_sound_speed_used_in_verification_flux_and_cfl"] is True
    assert payload["production_default_changed"] is False
    assert payload["production_hem_activation_approved"] is False
    assert payload["physical_validation"] is False
    assert payload["design_use_acceptance"] is False
    assert payload["numeric_accuracy_band_approved"] is False
    assert len(payload["history"]) == 3

    markdown = files["markdown"].read_text(encoding="utf-8")
    assert "VERIFICATION ONLY; NOT PRODUCTION HEM ACTIVATION" in markdown
    assert "uniform state preserved: `True`" in markdown
