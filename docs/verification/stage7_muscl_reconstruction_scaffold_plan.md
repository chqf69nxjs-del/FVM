# Stage 7 Numerical-Diffusion Improvement — MUSCL/TVD Scaffold

## 1. Status

`PURE RECONSTRUCTION SCAFFOLD VALIDATED; REVIEW REQUIRED`

The V-013 first-order baseline was formalized and merged in PR #51 at merge commit
`62390bd526ae99b6702f4ed76e3594e1bf01259b`. This increment begins the separate
numerical-diffusion improvement phase on branch
`agent/stage7-muscl-reconstruction-scaffold` in Draft PR #52.

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

The reconstruction file expands to `9` pytest cases through the supported-limiter matrix.
Together with the `4` V-013 baseline-definition tests, the focused inventory is `13`.

## 6. Branch validation evidence

Validation head:

```text
commit:                     c00cd2ccd5ced099bf4ea0e31a3f8a1070681a92
workflow run:               29721475855
focused inventory:          13 tests
full repository inventory:  398 tests
clean checkout:             success
focused test step:          success
full repository step:       success
committed diff check:       success
tracked files unchanged:    success
```

The four permanent workflows also completed successfully on this validation head:

```text
CoolProp Wave Regression:                 29721475864
CoolProp Controlled Pressure Ramp:        29721475869
CoolProp Boundary Reflection Regression:  29721475940
CoolProp Internal Valve Regression:       29721475854
```

Generated untracked cache/build artifacts are reported after the tests but are not confused
with source-tree mutation. The workflow separately requires a clean checkout before setup
and verifies that no tracked or staged file changes after execution.

The temporary scaffold-validation workflow is removed after this evidence is recorded.
Later closeout commits are documentation/workflow-only and do not change the reconstruction
module, its tests, or any production numerical path.

## 7. Integration sequence

The recommended sequence after this scaffold is:

1. add a scalar linear-advection harness comparing first-order and MUSCL transport;
2. measure Gaussian peak retention, width growth, phase error, total variation, and cost;
3. review conservative/primitive/characteristic reconstruction choices;
4. define EOS-validity and local first-order fallback rules;
5. connect reconstruction as an explicit optional `FvmSolver` path;
6. add second-order-compatible time integration;
7. rerun V-013A before any boundary-reflection claim;
8. rerun V-013B/C only after boundary reconstruction policy is explicit;
9. compare all results against `v013_baseline_v1` while retaining first order unchanged.

## 8. Completion boundary

This scaffold is complete for review when:

- focused reconstruction and baseline-integrity tests pass;
- the full repository suite remains green;
- `git diff --check origin/main...HEAD` is clean;
- permanent GitHub Actions remain green;
- the temporary validation workflow is removed;
- no production solver, flux, EOS inversion, time integration, source, phase-change,
  internal-interface, or boundary behavior is changed.

The next increment should be the scalar-advection comparison harness, not immediate
production activation.
