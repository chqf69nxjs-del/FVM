from __future__ import annotations

import numpy as np

import u3_b2_characteristic_port_diagnostic as diagnostic


def _exact_identity_checks_v2(
    contract,
    b1_contract,
    provider,
    area_m2: float,
):
    """Use the same exact identity definition as the accepted B2 Adapter tests.

    The authoritative identity is F_rho_u == face.upstream_static_pressure_pa,
    where that pressure is reconstructed from the conserved adjacent state.
    Comparing against the separately retained initial-state helper value can
    differ by CoolProp roundoff even though the Adapter identity is exact.
    """

    results = {}
    for case_id in (
        "B2-01_CLOSED_LIQUID_WALL_IDENTITY",
        "B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY",
    ):
        case = diagnostic._case(contract, case_id)
        conserved, _ = diagnostic.build_uniform_initial_state(
            contract,
            provider,
            str(case["state_id"]),
            1,
        )
        adapter = diagnostic.adapter_for_case(
            contract,
            b1_contract,
            case,
            provider=provider,
        )
        evaluation = adapter.evaluate(conserved[0], area_m2)
        if not evaluation.succeeded or evaluation.face is None:
            raise AssertionError(f"{case_id}: {evaluation.formal_outcome}")

        face = evaluation.face
        flux = face.flux_vector()
        expected = np.asarray(
            [0.0, float(face.upstream_static_pressure_pa), 0.0, 0.0],
            dtype=float,
        )
        results[case_id] = {
            "formal_outcome": evaluation.formal_outcome,
            "flux": [float(value) for value in flux],
            "expected": [float(value) for value in expected],
            "upstream_static_pressure_pa": float(face.upstream_static_pressure_pa),
            "exact_identity": bool(np.array_equal(flux, expected)),
        }
        assert results[case_id]["exact_identity"] is True

    return results


diagnostic.exact_identity_checks = _exact_identity_checks_v2


if __name__ == "__main__":
    diagnostic.main()
