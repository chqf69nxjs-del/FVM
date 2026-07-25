# Stage 7 — Fixed 4 MPa Subthreshold-Crossing Diagnostics

## Status

`IMPLEMENTATION IN PROGRESS; VERIFICATION ONLY; GATE P2 REMAINS FALSE`

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

## Required outputs

The runner writes JSON, CSV, NPZ, Markdown, and four PNG diagnostic figures covering the
local history, saturation margins, isentropic reference, flux decomposition, and rho/e
perturbation map.

## Exclusions

No mesh/CFL variation, higher-order reconstruction, boundary replacement, fixed-schedule or
threshold change, added physical source terms, physical Validation, design use, or
production activation is included.
