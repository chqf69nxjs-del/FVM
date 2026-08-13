# Stage 7 U3 B2 A1 finite-compression Increment 8C Guard-front 8-step continuation

## Status

`MODEL_REVIEW_ONLY / EIGHT_ACTUAL_FVM_STEPS / FIXED_BEFORE_EXECUTION_RESULT`

This increment continues from the authoritative Increment 8B accepted state at solver step 494. Before every requested step, it recomputes the unchanged general-EOS Hugoniot curve, refines the B1-unavailable / B1-success front for exactly 48 categorical iterations when required, solves one successful-domain compatibility root, and applies only that root's Euler flux.

It does not change B1, relax tolerances, enlarge the finite-compression diagnostic cap, modify production code, approve multi-step finite-compression use, or promote any formal state.

## Parent authority

```text
source SHA: 6229760e16e9588e0ef37a818af06158a4f72c06
workflow run: 31662867986
job: 94331160828
artifact: 9166824541
artifact name: u3-b2-a1-finite-compression-increment-8b-import-fix-31662867986
artifact SHA256: e5a126047df4d55da36e53dfc0333ea08cc339f15ca9dac9fd2b6decb0b7405f
outcome: FINITE_COMPRESSION_INCREMENT_8B_GUARD_FRONT_ONE_STEP_PASS
accepted state: step 494 at 0.0033103559567215584 s
```

## Fixed execution

```text
starting step: 494
requested accepted steps: 8
final step on pass: 502
Weak Compression limit: 1.0e-6
finite-compression diagnostic cap: 1.0e-4
root residual tolerance: 1.0e-8 kg/s
Guard-front categorical iterations: 48
compatibility-root bisection maximum: 48
```

For every accepted step require:

```text
one monotone B1-success root topology
one sign-change bracket
chi > 1.0e-6 and chi <= 1.0e-4
root residual <= 1.0e-8 kg/s
negative root slope
Hugoniot and identity-accounted closure
Lax 1-shock ordering
entropy bound
B1 success
outward subsonic liquid root and outlet
positive density and internal energy
exact-zero rho*xv
energy and reaction ledgers closed
step and cumulative mass/momentum/energy closure
no failed B1 state used as a root endpoint or flux
```

Stop immediately on a missing/multiple root, nonmonotone topology, root returning to Weak Compression scope, diagnostic-cap exceedance, phase/direction/positivity departure, ledger failure or conservation failure.

## Pass token

```text
FINITE_COMPRESSION_INCREMENT_8C_GUARD_FRONT_8_STEP_PASS
```

A pass authorizes no step beyond 502. All formal Verification, Validation, design-use and production flags remain false.
