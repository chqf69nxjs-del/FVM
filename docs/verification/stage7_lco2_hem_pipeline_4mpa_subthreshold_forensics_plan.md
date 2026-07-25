# Stage 7 — Fixed 4 MPa Subthreshold-Crossing Diagnostics

## Status

`IMPLEMENTED; SOFTWARE-DIAGNOSED; FINAL VALIDATION COMPLETE; GATE P2 REMAINS FALSE`

This increment implements Issue #78 after merged PR #77. It diagnoses the reproducible
4 MPa subthreshold raw crossing without changing the solver, fixed case, mesh, CFL,
boundary schedule, phase/projection settings, or evidence threshold.

## Immutable baseline

```text
outcome:                 GUARD_FAILURE
crossing step/time:      313 / 1.996923102525957e-3 s
crossing cell/distance:  25 / 0.203125 m
maximum q_eq:            9.672588429198319e-9
final-state SHA256:      7e8b6a6bc715755e0419d8a469140c02a79ec5e8bb419eb4868553c3228242e1
run-signature SHA256:    fdd25cbf669428790d1f3d877ab3b86ec329726d7b10e3a8461443ba6340b202
```

The diagnostic stops before analysis if this baseline is not reproduced exactly.

## Fixed observation window

```text
steps 300–313
cells 23–27
```

## Diagnostic phases

1. Retain accepted-before, raw-FVM, and post-projection states.
2. Evaluate saturated-liquid/vapor properties at each raw recovered pressure and calculate
   signed internal-energy and specific-volume margins plus independent quality estimates.
3. Calculate an isentropic saturated-liquid pressure reference from the initial entropy.
4. Reconstruct every selected Rusanov face flux as central plus dissipative components and
   require their total update to reproduce the stored raw state.
5. Apply the independent rho/e perturbation grid `0, ±1e-12, ±1e-10, ±1e-8, ±1e-6` at
   the fixed crossing raw state and record phase, quality, margins, round trip, and EOS result.

## Allowed conclusion categories

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NUMERICAL_DIFFUSION_CONSISTENT
BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
INCONCLUSIVE
```

Multiple categories may be retained. No diagnostic result changes the PR #77 observation.

## Observed diagnostic result

The authoritative execution retained:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

The crossing point is independently on the two-phase side in both internal-energy and
specific-volume coordinates. Its 9×9 rho/e perturbation map is `WEAKLY_RESOLVED`: no phase
change occurs through relative perturbations of `1e-8`, while some `1e-6` perturbations
return to the liquid side.

The local one-step central-only update is also open two phase and has a larger quality than
the full Rusanov update. Therefore the narrow `NUMERICAL_DIFFUSION_CONSISTENT` criterion is
not triggered. The crossing cell is not boundary-adjacent and the narrow direct outlet-face
criterion is also not triggered. Neither result rules out accumulated numerical diffusion
or indirect boundary influence in later sensitivity studies.

The equilibrium sound-speed candidate changes sharply at the micro-quality transition. Its
near-saturation continuity and physical accuracy remain unapproved.

## Final validation identity

```text
validated implementation head:   719301dd64c9ee2571cf3296605466a2ee9de27f
workflow run:                     30162194409
artifact ID:                      8620823392
artifact SHA256:                  1b2c14790c3c66be47386f60ddb9c8b21ee5d253dcc0ab1d78e9deaa7b5184d7
CoolProp:                         8.0.0
```

```text
dependency-free forensic tests:   8 passed, 0 skipped
installed-CoolProp forensics:     9 passed, 0 skipped
related Stage 7 regressions:     69 passed, 0 skipped
full repository:                723 passed, 0 skipped
failures / errors:                0 / 0
```

## Required outputs

The runner writes:

```text
4mpa_forensic_summary.json
4mpa_local_cell_history.csv
4mpa_saturation_margin.csv
4mpa_isentropic_reference.json
4mpa_flux_decomposition.csv
4mpa_property_perturbation.csv
4mpa_property_perturbation.npz
4mpa_forensic_evidence.md
rho_e_saturation_zoom.png
saturation_margin_vs_time.png
central_vs_dissipative_update.png
perturbation_classification_map.png
```

Permanent review records:

- [`stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_evidence.md`](stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_evidence.md)
- [`stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_contract_v1.json`](stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_contract_v1.json)
- [`stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_validation_commands.md`](stage7_lco2_hem_pipeline_4mpa_subthreshold_forensics_validation_commands.md)

## Exclusions

No mesh/CFL variation, higher-order reconstruction, boundary replacement, fixed-schedule or
threshold change, added physical source terms, physical Validation, design use, or
production activation is included.

Passing this diagnostic execution does not pass Gate P2 or freeze a boundary-driven liquid
control.
