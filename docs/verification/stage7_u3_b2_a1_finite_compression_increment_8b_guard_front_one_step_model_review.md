# Stage 7 U3 B2 A1 finite-compression Increment 8B Guard-front one-step

## Status

`MODEL_REVIEW_ONLY / ONE_ACTUAL_FVM_STEP / FIXED_BEFORE_EXECUTION_RESULT`

This increment applies the Increment 8A diagnostic result to one actual update from accepted solver step 493 to 494. It does not change B1, relax any tolerance, enlarge the diagnostic `chi` cap, modify production code, approve the finite-compression branch, or promote a formal state.

## Authorities

### Accepted-state parent

```text
run: 31661720453
job: 94327704607
artifact: 9166412782
artifact SHA256: d1d704997ec5e8fd038a0645b31e598939528cd9295de8762c06aaf3b81081d8
accepted state: step 493 at 0.0033036489591120113 s
```

### Root-topology diagnostic

```text
source SHA: d8766a6e2b362d7fc3c577410de59c50c04834f3
run: 31662145018
job: 94328958641
artifact: 9166560133
artifact SHA256: 457e4ad3a2c432d532e483fdc94d8e5f62b9ac600387fb6b3215322858acc6d2
outcome: FINITE_COMPRESSION_GUARD_FRONT_REFINEMENT_SUPPORTED
```

The diagnostic fixed one successful-domain root:

```text
chi: 1.4723673525738786e-6
root residual: -3.1298802768281453e-9 kg/s
root gate: PASS
```

## Fixed method

1. Verify both artifacts and exact step-493 state identity.
2. Recompute the 48-iteration B1-unavailable / B1-success front and selected Hugoniot root.
3. Compare the recomputed root to the diagnostic authority.
4. Construct the existing pipe-side Euler flux from the successful root only.
5. Run exactly one actual `FvmSolver` update to step 494.
6. Require positive density/internal energy, outward subsonic liquid outlet, exact-zero `rho*xv`, root/energy/reaction gates and step/cumulative mass, momentum and energy closure.

Failed B1 states remain unavailable and are not used as root endpoints or fluxes.

## Fixed limits

```text
Weak Compression limit: 1.0e-6
finite-compression diagnostic cap: 1.0e-4
root residual tolerance: 1.0e-8 kg/s
Guard-front iterations: 48
compatibility bisection maximum: 48
requested solver step: 494
```

## Pass token

```text
FINITE_COMPRESSION_INCREMENT_8B_GUARD_FRONT_ONE_STEP_PASS
```

A pass authorizes no step beyond 494. All formal Verification, Validation, design-use and production flags remain false.
