# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4E Guard-front formal-outcome correction

## Status

`MODEL_REVIEW_ONLY / IMPLEMENTATION_CORRECTION / FIXED_BEFORE_RERUN_RESULT`

This note fixes one diagnostic classification defect observed in the first Increment 4E run. It does not change B1, disable a B1 Guard, convert a failed B1 state into a successful state, relax a tolerance, add a pressure tolerance, enlarge the Weak Compression `chi` scope, change a root law, revise the locked B2 v1 Contract, modify the production B2 Adapter, modify `FvmSolver`, or promote any formal project state.

## Parent failed diagnostic

```text
source Git SHA:
88e8d7f1e343bc7f6e45a7c35df585d2d73e661f

workflow run:
31617525217

job:
94183955040

artifact:
none; the diagnostic stopped before creating its output directory

failed operation:
Guard-front categorical bisection iteration 23

formal outcome:
NONPOSITIVE_KINETIC_ENERGY_HEAD

formal message:
Nonpositive kinetic energy head -9.167706593871117e-09 J/kg.
```

Checkout, dependency installation, fixed-scope comparison, and authoritative Increment 4D artifact download all passed before the diagnostic stop.

## Reviewed B1 behavior

The accepted B1 implementation defines the candidate kinetic-energy head as:

```text
h0 - h_candidate
```

and returns:

```text
NONPOSITIVE_KINETIC_ENERGY_HEAD
```

whenever that value is nonfinite or not strictly positive. The locked B1 Contract requires a positive kinetic-energy head except for its separately defined exact zero-pressure-drop identity.

Therefore the midpoint that produced the parent failure is not a B1-success state and may not be used as a compatibility-root state or root-bracket endpoint.

## Defect classification

Increment 4E fixed a categorical bracket around the transition from states unavailable to the unchanged B1 component to states accepted by it:

```text
lower endpoint:
B1 unavailable

upper endpoint:
B1 success and locally admissible
```

The initial implementation recognized only:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
```

as a valid lower-side unavailable classification.

At iteration 23, the midpoint had moved beyond the exact reverse-pressure classification but still did not have a strictly positive B1 kinetic-energy head. B1 correctly returned `NONPOSITIVE_KINETIC_ENERGY_HEAD`. The diagnostic incorrectly treated this second formal B1 refusal as an unexpected internal failure rather than retaining it on the unavailable side of the categorical Guard front.

This is a diagnostic classification defect. It is not evidence that B1 accepted the midpoint, and it is not evidence that the later successful B1 domain or compatibility root disappeared.

## Fixed correction

For Guard-front categorical bisection only, define the lower unavailable side as either exact formal outcome:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
NONPOSITIVE_KINETIC_ENERGY_HEAD
```

Both outcomes remain failed B1 evaluations with zero applied transfer. Neither may:

```text
construct a flux
serve as a compatibility-root state
serve as a successful root-bracket endpoint
be counted as B1 success
```

The upper side remains unchanged:

```text
B1 evaluation succeeds
candidate is locally admissible
```

No magnitude threshold is introduced for the kinetic-energy head. The formal B1 outcome itself determines the unavailable classification. Any other formal outcome remains fail-closed.

The Guard-front bisection still runs exactly 32 iterations, retains a failed lower endpoint and a successful upper endpoint, and uses only successful B1 states for the compatibility-root bracket and root bisection.

## Rerun scope

Rerun the unchanged Increment 4E step-451 diagnostic through a narrow wrapper that replaces only the Guard-front lower-side formal-outcome classification described above.

The rerun must preserve:

```text
accepted state loaded = step 451
FvmSolver step 452 attempted = false
root mass tolerance = 1.0e-8 kg/s
Weak Compression chi scope = 0 < chi <= 1.0e-6
Guard-front iterations = 32
root bisection maximum = 32
B1 component and Guard behavior = unchanged
formal project states = false
```

The evidence must separately count and retain:

```text
reverse-pressure unavailable midpoints
nonpositive-kinetic-head unavailable midpoints
successful midpoints
```

If the refined first-success residual is already negative beyond the unchanged root tolerance, classify `ROOT_LIES_INSIDE_B1_GUARD_DOMAIN` and stop. If the successful residual remains positive through the fixed `chi` cap, classify `FINITE_COMPRESSION_MODEL_REQUIRED` and stop. Only an independently successful B1-domain root may support later continuation.

A passing rerun remains `MODEL_REVIEW / DIAGNOSTIC_ONLY` evidence and does not authorize an actual solver step.
