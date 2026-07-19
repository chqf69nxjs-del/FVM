# Stage 7 V-013 Baseline and Limitation Statement

## 1. Status

`FORMALIZATION DRAFT; REVIEW REQUIRED`

V-013A incident propagation, V-013B rigid-wall reflection, and V-013C fixed-pressure
reflection are all `OBSERVED; MERGED`. This document formalizes their joint meaning and
freezes the current first-order production FVM path as a software/numerical observation
baseline.

The machine-readable companion is
[`v013_baseline_definition_v1.json`](v013_baseline_definition_v1.json).

Stage 7 / V-013 remains `IN_PROGRESS` until this baseline statement and the associated
CI-light proposal are reviewed. This document does not approve physical Validation,
design use, or an accuracy band.

## 2. Purpose

The baseline has four purposes:

1. state what the current production FVM has demonstrated;
2. state what it has not demonstrated;
3. provide a stable comparison point for future optional higher-order methods;
4. prevent current numerical observations from being misrepresented as design accuracy.

The baseline is intentionally conservative. It records reproducible software and
numerical behavior without changing the production solver, numerical flux, EOS inversion,
or boundary implementations.

## 3. Source evidence

| item | purpose | PR / merge commit | primary evidence |
|---|---|---|---|
| V-013A | incident-wave propagation | PR #48 / `613b21622b22402fbf7b8d77b1d881db7ff5f28e` | run `29647234616`; focused/full `39/315`; 3 runs; 7 figures |
| V-013B | right rigid-wall reflection | PR #49 / `bc874193de6a4c019073b6cf629e99ec5dfa6602` | run `29684930259`; focused/full `57/350`; artifact `8441899419` |
| V-013C | right fixed-pressure reflection | PR #50 / `f403103c46a1d618ce2f2345c986e29b921b664a` | run `29692477941`; focused/full `58/385`; artifact `8444138380` |

The post-PR #50 main baseline was independently rechecked on Windows with `385 passed`
and a clean working tree before branch
`agent/stage7-v013-baseline-formalization` was created.

## 4. Common fixed problem

The A/B/C comparison matrix shares the following numerical contract except where the
boundary type is the intended independent variable:

```text
pipe length:                 100 m
base pressure / temperature: 8 MPa / 280 K
pulse:                       100 Pa right-going Gaussian A+
pulse centre / sigma:        65 m / 2 m
FVM meshes:                  n=100 / 200 / 400
FVM CFL:                     0.5
independent MOC CFL:         1.0
property backend:            coolprop_co2
CoolProp version:            8.0.0
time shift:                  none
parameter tuning:            none
```

The independent analytical/MOC path is a verification reference. It is not physical
truth, a production solver, or a substitute for experimental Validation.

## 5. Case results

### 5.1 V-013A — incident propagation

| n | Δx [m] | final FVM pressure peak ratio |
|---:|---:|---:|
| 100 | 1.00 | 0.33987050 |
| 200 | 0.50 | 0.44696360 |
| 400 | 0.25 | 0.57499430 |

Observed baseline behavior:

- the pulse propagates in the expected positive-x direction;
- approximate propagation speed is consistent with the recorded reference sound speed;
- peak retention improves monotonically with refinement;
- strong numerical broadening and peak loss remain at `n=400`.

### 5.2 V-013B — rigid-wall reflection

Ideal identities:

```text
A-_reflected = A+_incident
pressure reflection coefficient = +1
velocity reflection coefficient = -1
wall velocity = 0
wall mass flux = 0
wall energy flux = 0
wall pressure amplification ratio = 2
```

| n | pressure reflection | velocity reflection | wall pressure ratio | final peak ratio | maximum pressure L2 difference |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 | 0.66558518 |
| 200 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 | 0.54412398 |
| 400 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 | 0.40713104 |

Observed baseline behavior:

- pressure reflection has the expected positive sign;
- velocity reflection has the expected negative sign;
- the return is a left-going `A-` characteristic;
- wall-face velocity, mass flux, and energy flux are exactly zero;
- principal amplitude and field-error metrics improve monotonically with refinement;
- the ideal amplitude and wall-pressure rise are not reached at `n=400`.

### 5.3 V-013C — fixed-pressure reflection

Ideal identities:

```text
A-_reflected = -A+_incident
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

| n | pressure reflection | velocity reflection | fixed-pressure residual | boundary velocity ratio | final peak ratio | maximum pressure L2 difference |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | -0.63395297 | 0.63399661 | 0.05654903 | 0.82447607 | 0.33190828 | 0.68067093 |
| 200 | -0.69829946 | 0.69829998 | 0.04880759 | 1.09704849 | 0.44185022 | 0.55451247 |
| 400 | -0.77022729 | 0.77022778 | 0.03712903 | 1.37073388 | 0.57212615 | 0.41332543 |

Observed baseline behavior:

- pressure reflection has the expected negative sign;
- velocity reflection has the expected positive sign;
- the return is a left-going negative `A-` characteristic;
- fixed-pressure residual decreases monotonically with refinement;
- boundary velocity amplification moves toward the ideal value `2`;
- nonzero mass and energy transfer are expected for this pressure boundary and are
  retained as observations, not treated as zero-flux failures;
- strong numerical broadening and peak loss remain at `n=400`.

## 6. Joint finding

The three cases consistently demonstrate that the production FVM reproduces:

- propagation direction;
- approximate wave timing and speed;
- rigid-wall and fixed-pressure reflection signs;
- the expected returning characteristic direction;
- essential rigid-wall no-flow behavior;
- essential fixed-pressure boundary behavior;
- finite, positive, single-phase numerical execution;
- monotonic improvement of the principal recorded differences under mesh refinement.

The common limiting issue is first-order numerical diffusion. At `n=400`, the final
pressure-peak ratio is approximately:

```text
V-013A: 0.57499430
V-013B: 0.57499450
V-013C: 0.57212615
```

The close agreement across three boundary configurations indicates that the principal
peak loss is a common transport-discretization limitation rather than a boundary-specific
sign failure.

## 7. Approved baseline uses

The current first-order implementation may be used as:

- a stable software-regression reference;
- a numerical-behavior reference for direction, timing, reflection signs, and boundary
  invariants;
- the control implementation when optional higher-order reconstruction is introduced;
- a reference for comparing peak retention, field differences, stability, positivity,
  and runtime cost of future methods;
- a traceable source for engineering-development decisions about where numerical-method
  improvement is needed.

## 8. Prohibited interpretations

This baseline must not be described as:

- physical Validation;
- design-use acceptance;
- an experimentally confirmed pressure-wave model;
- a design-accurate peak-pressure predictor;
- an exact or converged solution at `n=400`;
- approval of `coolprop_co2` for design use;
- an approved FVM regression band, CI-light band, or design-accuracy band.

The approximately `57%` peak retention is a recorded limitation, not a target accuracy
or an acceptable design margin.

## 9. Baseline freeze rules

Future numerical-method work shall follow these rules:

1. retain the current first-order path as a selectable reference implementation;
2. add higher-order behavior through an explicit option rather than silently replacing
   the reference path;
3. rerun V-013A/B/C whenever reconstruction, limiting, flux, time integration, EOS
   coupling, or boundary interaction changes;
4. report improvement and degradation against `v013_baseline_v1`;
5. preserve positivity, finite-state, phase, budget, and traceability checks;
6. do not tune the independent reference to the production result;
7. do not use time shifting or post-result parameter fitting;
8. keep physical Validation and design-use acceptance as separate future gates.

A change to the baseline JSON requires an intentional review explaining whether the
change is a corrected defect, an expected solver change, or a new baseline version.

## 10. Completion boundary

This formalization increment is complete for review when:

- this joint statement is consistent with the three merged observation records;
- `v013_baseline_definition_v1.json` passes its integrity tests;
- the CI-light proposal clearly separates gross-regression monitoring from accuracy
  acceptance;
- the full repository suite remains green;
- production solver behavior is unchanged.

After merge, the recommended next phase is a separate numerical-diffusion improvement
branch, beginning with an optional MUSCL/TVD reconstruction while retaining the current
first-order implementation as the control baseline.
