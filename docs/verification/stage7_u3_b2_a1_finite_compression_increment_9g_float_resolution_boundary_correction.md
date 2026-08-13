# Stage 7 U3 B2 A1 finite-compression Increment 9G floating-point boundary correction

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_IMPLEMENTATION_CORRECTION / FIXED_BEFORE_RERUN_RESULT`

This note corrects one floating-point bookkeeping failure observed in the first Increment 9G run. It does not change B1, local admissibility, the Hugoniot model, any root gate, the root tolerance, the diagnostic interval, the 129 scan nodes, the finite-compression `chi` cap, the production Adapter, `FvmSolver`, or any formal project state.

## Parent failed diagnostic

```text
source Git SHA:
c7dddb08c6bbeff911d25408f607431cc220c2c0

workflow run:
31668979089

job:
94349560941

failed operation:
lower admissible-island boundary refinement

failure:
lower boundary midpoint collapsed
```

Source/scope checks, parent artifact verification, state reproduction, the unchanged 12-node fixed scan, and the pre-fixed 129-node seeded interval scan completed before this stop.

The diagnostic reached the lower-boundary refinement only after finding one admissible island with excluded diagnostic nodes on both sides. Therefore the failure was not `NO_ADMISSIBLE_ISLAND`.

## Cause

The seeded diagnostic interval is:

```text
1.0e-5 <= chi <= 2.0e-5
```

with 129 equally spaced nodes. Two adjacent diagnostic coordinates differ by:

```text
7.8125e-8
```

Refining such an adjacent interval for 48 binary iterations requests a final mathematical width below the spacing of IEEE-754 binary64 values near `chi ~ 1e-5`. Eventually:

```text
midpoint == lower endpoint
or
midpoint == upper endpoint
```

although the excluded/admissible categorical endpoints remain distinct adjacent representable values.

This is a coordinate-resolution limit, not a pressure, residual, B1, admissibility, or physical tolerance failure.

## Fixed logical-iteration rule

Retain exactly 48 logical boundary-iteration records.

While a strictly interior binary64 midpoint exists:

```text
evaluate the unchanged candidate state
update the excluded or admissible endpoint according to the unchanged category
record boundary_action = CANDIDATE_EVALUATED
```

When no strictly interior binary64 midpoint exists, require:

```text
lower endpoint < upper endpoint
np.nextafter(lower endpoint, upper endpoint) == upper endpoint
```

Then retain both endpoints unchanged for every remaining logical iteration and record:

```text
boundary_action = FLOAT_RESOLUTION_HOLD
candidate_evaluated = false
```

A resolution hold:

```text
does not classify a new candidate
does not change either endpoint
does not create a root-topology node
does not create a root endpoint
does not create an applied flux
does not add a tolerance
```

If the endpoints are not adjacent representable values when midpoint collapse occurs, fail closed.

The final excluded/admissible endpoint invariants remain mandatory. Root topology still uses only admissible candidate states and must retain strict coordinate ordering, monotone residuals, one sign-change bracket and all unchanged root gates.

## Rerun evidence

Record separately for each boundary:

```text
candidate-evaluated iteration count
float-resolution-hold iteration count
first hold iteration
final excluded chi
final admissible chi
final representable bracket width
adjacent-representable assertion
```

A passing result remains diagnostic-only and does not authorize step 636.

## Formal-state boundary

All approval, Verification, Validation, design-use and production flags remain false regardless of result.
