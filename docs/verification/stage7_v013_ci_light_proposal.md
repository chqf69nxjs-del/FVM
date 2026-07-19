# Stage 7 V-013 CI-Light Monitoring Proposal

## 1. Status

`PROPOSED; NOT APPROVED; NOT IMPLEMENTED`

This document proposes a lightweight regression-monitoring structure for the merged
V-013A/B/C software/numerical baseline. It does not create an accuracy-acceptance band,
design-use criterion, or physical Validation gate.

The source baseline is
[`v013_baseline_definition_v1.json`](v013_baseline_definition_v1.json), described in
[`stage7_v013_baseline_and_limitations.md`](stage7_v013_baseline_and_limitations.md).

## 2. Purpose

CI-light should detect gross unintended changes such as:

- a wave traveling in the wrong direction;
- a rigid-wall or fixed-pressure reflection sign changing;
- loss of a boundary invariant;
- non-finite, negative, or unintended two-phase states;
- contaminated event windows;
- disappearance of expected artifacts or traceability metadata;
- a large software regression that requires human review.

CI-light must not certify peak-pressure accuracy or convert the current approximately
`57%` peak retention into an accepted engineering tolerance.

## 3. Proposed two-tier structure

### Tier 1 — pull-request CI-light

Purpose: fast detection of qualitative and structural regressions on ordinary pull
requests.

Candidate matrix:

```text
V-013A: canonical incident propagation, n=100
V-013B: canonical rigid-wall reflection, n=100
V-013C: canonical fixed-pressure reflection, n=100
FVM CFL: 0.5
MOC CFL: 1.0 where the reference is needed
CoolProp: pinned repository verification version
```

The `n=100` choice is proposed for cost control. It is not an accuracy endorsement.
Before implementation, measured runtime on the target CI runner should confirm that the
three cases fit the intended pull-request budget.

### Tier 2 — scheduled or release verification

Purpose: preserve the full numerical trend and detect slow drift that a one-mesh check
cannot reveal.

Candidate matrix:

```text
V-013A/B/C: n=100 / 200 / 400
saved artifacts: JSON / CSV / NPZ / report / figures
frequency: scheduled, release-candidate, or solver-method change
```

Tier 2 should check monotonic mesh-refinement trends and preserve exact evidence. It is
not intended to run on every minor documentation change.

## 4. Proposed Tier 1 gates

### 4.1 Common execution gates

The following are suitable as exact Boolean gates:

- process exits successfully;
- planned and executed run counts match;
- all required arrays and reported metrics are finite;
- pressure, temperature, density, and sound speed remain positive;
- the case remains within the recorded single-phase guardrail;
- required budget fields are present;
- event windows are not contaminated by secondary returns;
- no time shift is applied;
- no parameter tuning is applied;
- physical Validation, design evaluation, and acceptance flags remain `False`;
- property backend design status remains `not_approved_for_design_use`;
- production solver behavior-change flag remains `False`;
- reference path does not call CoolProp;
- required case, model, backend, version, and disclaimer metadata are present.

### 4.2 V-013A gates

Proposed exact or qualitative gates:

- dominant propagated characteristic remains right-going `A+`;
- recorded propagation direction remains positive-x;
- the expected probe event is detected;
- the numerical state remains healthy;
- final pressure peak is finite and positive.

The proposal intentionally does not impose a peak-retention acceptance threshold in
Tier 1.

### 4.3 V-013B gates

Proposed exact or qualitative gates:

- reflected pressure coefficient has positive sign;
- reflected velocity coefficient has negative sign;
- returning dominant characteristic is `A-`;
- wall-face velocity is exactly zero within the representation used by the boundary
  telemetry;
- wall-face mass flux is zero;
- wall-face energy flux is zero;
- the expected incident and reflected events are detected;
- wall pressure response is finite and positive.

No claim is made that the observed coefficient magnitude is accurate enough for design.

### 4.4 V-013C gates

Proposed exact or qualitative gates:

- reflected pressure coefficient has negative sign;
- reflected velocity coefficient has positive sign;
- returning dominant characteristic is negative `A-`;
- fixed-pressure residual is finite;
- boundary velocity amplification is finite and positive;
- boundary mass and energy transfer fields are present and finite;
- nonzero mass or energy transfer is not treated as a zero-flux failure;
- the expected incident and reflected events are detected.

The fixed-pressure residual and velocity ratio should initially be reported without an
approved numeric pass band.

## 5. Proposed Tier 2 gates

Tier 2 may enforce deterministic identities and monotonic trends across `n=100/200/400`.

### 5.1 Common monotonic trends

Candidate checks:

- final pressure-peak retention increases with refinement;
- maximum pressure L2 difference decreases with refinement where the metric is defined;
- maximum velocity L2 difference decreases with refinement where the metric is defined;
- execution health remains true at all three meshes.

These are trend checks, not design-accuracy checks.

### 5.2 V-013B trends

Candidate checks:

- pressure reflection coefficient moves monotonically toward `+1`;
- velocity reflection coefficient moves monotonically toward `-1` in magnitude;
- wall pressure amplification moves monotonically toward `2`;
- zero wall velocity, mass flux, and energy flux remain exact invariants.

### 5.3 V-013C trends

Candidate checks:

- pressure reflection coefficient moves monotonically toward `-1` in magnitude;
- velocity reflection coefficient moves monotonically toward `+1`;
- normalized fixed-pressure residual decreases monotonically;
- boundary velocity amplification moves monotonically toward `2`;
- nonzero boundary transfer remains recorded and finite.

## 6. Numeric drift bands

No numeric drift band is approved in this proposal.

Before adding tolerances, perform a repeatability study using the same commit on the
supported operating systems and dependency versions. At minimum, record:

- repeated-run variation;
- Linux versus Windows variation;
- supported NumPy-version variation;
- CoolProp-version policy;
- compiler or BLAS variation if it is measurable;
- artifact serialization stability.

Only after that study should a separate review propose tolerances for quantities such as
arrival time, reflection coefficient, residual, or peak ratio.

Any future band should be described as one of:

```text
software regression band
numerical repeatability band
accuracy acceptance band
```

These categories must not be combined. An accuracy-acceptance band requires evidence
beyond the present software/numerical verification package.

## 7. Suggested workflow behavior

A future workflow should:

1. pin the intended Python and CoolProp versions;
2. install the repository normally;
3. run `git diff --check` over the committed base/head range when appropriate;
4. run the dedicated Tier 1 tests or commands;
5. emit a compact JSON evidence record;
6. upload evidence only when useful for diagnosis;
7. fail on exact invariant violations;
8. report unbanded numerical metrics without treating them as accuracy approval;
9. avoid modifying the source branch or PR automatically;
10. keep full three-mesh observations outside ordinary pull-request cost unless the
    changed files affect the solver, flux, EOS, boundaries, or V-013 machinery.

## 8. Change-path policy

Candidate path filters for Tier 1 execution include changes to:

- production solver or numerical flux;
- reconstruction, limiter, or time integration;
- EOS or property-backend coupling;
- external boundary implementations;
- V-013 case runners, reference core, metrics, or plotting;
- shared telemetry, interpolation, or artifact code used by V-013.

Documentation-only changes should normally rely on the standard repository checks unless
they alter the baseline definition or verification status.

## 9. Failure interpretation

A CI-light failure means that a recorded baseline invariant or software expectation has
changed. It does not automatically mean the new method is physically wrong.

For intentional higher-order changes:

- retain the first-order reference path;
- rerun the failing baseline case explicitly;
- explain the expected change;
- compare both methods against the independent reference;
- update the baseline only through a reviewed version change.

## 10. Approval boundary

This proposal is ready for implementation planning when reviewers agree on:

- Tier 1 case and mesh selection;
- runtime budget;
- exact invariant list;
- change-path filters;
- evidence retention policy;
- repeatability-study plan for later numeric bands.

Until then:

```text
CI-light status:             proposed, not approved
numeric regression bands:   none
physical Validation:        false
design-use acceptance:      false
production solver changes:  none
```
