# Stage 7 V-013C Fixed-Pressure Reflection Observation Notes

Status: `OBSERVED; MERGED` in PR #50. Merge commit:
`f403103c46a1d618ce2f2345c986e29b921b664a`. V-013 overall remains `IN_PROGRESS`.

## Final observation evidence

```text
workflow run:       29692477941
PR head:            2f5c10b3f99f561d457ab8d391d5e91be98b7ff3
Actions merge SHA:  e2eb1a075d229d51d28366aa211a1642fbcc1463
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
runs:               3 / 3
figures:            7 / 7
plotting errors:    0
CoolProp:           8.0.0
artifact ID:        8444138380
artifact entries:   59
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
```

The Windows project recheck independently passed focused `58` and full repository `385`
tests, with `git diff --check origin/main...HEAD` clean and the working tree clean.

Plotting reads saved artifacts only:

```text
solver_rerun = false
numerical_results_changed = false
```

## Fixed reference identities

For the right fixed-pressure boundary:

```text
A-_reflected = -A+_incident
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

The production path uses the existing
`PressureTankBoundary(ConstantPressure(p0), flow_direction="bidirectional",
velocity_policy="copy")`. Production solver, numerical flux, EOS inversion, and
boundary behaviour are unchanged.

## Primary numerical observations

| n | Δx [m] | mean FVM pressure reflection coefficient | mean FVM velocity reflection coefficient | normalized fixed-pressure residual | boundary velocity ratio | final reflected pressure peak ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 1.00 | -0.63395297 | 0.63399661 | 0.05654903 | 0.82447607 | 0.33190828 |
| 200 | 0.50 | -0.69829946 | 0.69829998 | 0.04880759 | 1.09704849 | 0.44185022 |
| 400 | 0.25 | -0.77022729 | 0.77022778 | 0.03712903 | 1.37073388 | 0.57212615 |

The expected signs and direction are observed: the right-going `A+` incident pulse
returns as a left-going negative `A-` pulse, pressure reverses sign, and velocity retains
its positive sign. The fixed-pressure residual decreases monotonically with mesh
refinement, and the boundary velocity ratio moves toward the ideal value `2`.

The final reflected pressure peak retains about `57.2%` of the analytical peak at
`n=400`. This is consistent with the strong FVM numerical broadening and peak loss
already observed in V-013A and V-013B.

## Field differences

| n | maximum pressure L2 relative difference | maximum velocity L2 relative difference |
|---:|---:|---:|
| 100 | 0.68067093 | 0.68067092 |
| 200 | 0.55451247 | 0.55451245 |
| 400 | 0.41332543 | 0.41332538 |

The field differences decrease monotonically, but the finest mesh is not an exact or
design-accurate solution.

## Boundary transfer observations

Unlike the rigid wall, the fixed-pressure boundary is not a zero-flux boundary.
Nonzero mass and energy transfer are expected observations rather than failures.

| n | integrated right-boundary mass [kg] | integrated right-boundary energy [J] |
|---:|---:|---:|
| 100 | 0.0001364845 | 28.98455 |
| 200 | 0.0001668497 | 35.43306 |
| 400 | 0.0001895418 | 40.25207 |

## Completion guardrails

- software / numerical verification only;
- physical Validation and design-use acceptance remain `False`;
- property backend remains `not_approved_for_design_use`;
- MOC is verification-only, not physical truth;
- no time shift or parameter tuning was applied;
- no FVM regression, CI-light, or design-accuracy band is introduced;
- temporary V-013C evidence-capture and review-helper workflows were removed before
  merge;
- final-head permanent workflows passed `4 / 4` and all review threads were resolved.

Next: formalize the combined V-013A/B/C baseline findings, define a cautious CI-light
monitoring proposal, and begin the numerical-diffusion improvement phase on a separate
branch while retaining the current first-order solver as the baseline.
