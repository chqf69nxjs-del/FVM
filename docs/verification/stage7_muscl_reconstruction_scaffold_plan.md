# Stage 7 Numerical-Diffusion Improvement — MUSCL/TVD Scaffold

## 1. Status

`IN_PROGRESS; PURE RECONSTRUCTION SCAFFOLD`

The V-013 first-order baseline was formalized and merged in PR #51 at merge commit
`62390bd526ae99b6702f4ed76e3594e1bf01259b`. This increment begins the separate
numerical-diffusion improvement phase on branch
`agent/stage7-muscl-reconstruction-scaffold`.

The present increment does not connect MUSCL reconstruction to `FvmSolver`, does not
change production numerical states, and does not claim second-order production accuracy.

## 2. Objective

Create and verify a small, solver-independent reconstruction layer before choosing how
higher-order states interact with the real-fluid EOS, external boundaries, internal
interfaces, source splitting, or time integration.

The scaffold must preserve the existing first-order path exactly so that
`v013_baseline_v1` remains the selectable control.

## 3. Scope of this increment

Added pure reconstruction support includes:

- exact piecewise-constant `first_order` interface states;
- componentwise MUSCL interface reconstruction;
- `minmod`, monotonized-central (`mc`), and `van_leer` TVD limiters;
- zero end-cell slopes rather than hidden extrapolation;
- finite-input and explicit-configuration checks;
- no mutation or memory aliasing of the caller's state array.

The first array axis is treated as the finite-volume cell axis. The remaining axes are
limited componentwise. The module imports NumPy only and has no dependency on the
production solver, EOS stack, boundaries, property backends, or verification runners.

## 4. Deliberately deferred decisions

The following are not approved by this scaffold:

- reconstruction of conservative versus primitive versus characteristic variables;
- reconstruction at rigid-wall, fixed-pressure, valve, reservoir, or junction interfaces;
- positivity preservation and local first-order fallback policy;
- MUSCL-Hancock versus SSP-RK2 time integration;
- production default limiter;
- CFL changes;
- a peak-retention target or numeric regression band;
- any physical Validation or design-use claim.

These decisions require separate production-connected tests because a mathematically TVD
componentwise reconstruction can still create an EOS-invalid combined thermodynamic state.

## 5. Pure invariants

The focused tests require:

1. `first_order` interface states exactly equal adjacent cell averages;
2. constant fields remain constant;
3. linear fields are reconstructed exactly at fully interior interfaces;
4. supported TVD limiters create no new interface extrema in the scalar test matrix;
5. local extrema receive zero limited slope;
6. limiter operations remain componentwise;
7. input arrays remain unchanged and outputs do not alias them;
8. unknown methods, unknown limiters, undersized slope arrays, and non-finite values fail
   explicitly.

Isolated scaffold validation currently passes `9` tests.

## 6. Integration sequence

The recommended sequence after this scaffold is:

1. validate the pure module in the full repository suite;
2. add a scalar linear-advection harness comparing first-order and MUSCL transport;
3. measure Gaussian peak retention, width growth, phase error, total variation, and cost;
4. review conservative/primitive/characteristic reconstruction choices;
5. define EOS-validity and local first-order fallback rules;
6. connect reconstruction as an explicit optional `FvmSolver` path;
7. add second-order-compatible time integration;
8. rerun V-013A before any boundary-reflection claim;
9. rerun V-013B/C only after boundary reconstruction policy is explicit;
10. compare all results against `v013_baseline_v1` while retaining first order unchanged.

## 7. Completion boundary

This scaffold is complete for review when:

- focused reconstruction tests pass;
- the existing V-013 baseline integrity tests remain green;
- the full repository suite remains green;
- `git diff --check origin/main...HEAD` is clean;
- permanent GitHub Actions remain green;
- no production solver, flux, EOS inversion, time integration, source, phase-change,
  internal-interface, or boundary behavior is changed.

The next increment should be the scalar-advection comparison harness, not immediate
production activation.
