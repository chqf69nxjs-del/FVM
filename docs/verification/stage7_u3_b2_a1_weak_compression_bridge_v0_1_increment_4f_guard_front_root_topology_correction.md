# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4F Guard-front root-topology correction

## Status

`MODEL_REVIEW_ONLY / IMPLEMENTATION_CORRECTION / FIXED_BEFORE_RERUN_RESULT`

This note corrects one diagnostic/root-topology construction defect observed in the first Increment 4F run. It does not change B1, disable a B1 Guard, convert a failed B1 state into a successful state, relax a tolerance, add a residual monotonicity tolerance, enlarge the Weak Compression `chi` scope, change the characteristic relation, revise the locked B2 v1 Contract, modify the production B2 Adapter, modify `FvmSolver`, or promote any formal project state.

## Parent failed Increment 4F run

```text
source Git SHA:
618f49c0a75620751cb517d669a4da868e82f41e

workflow run:
31619671593

job:
94191039227

artifact:
9150769457

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4f-31619671593

artifact SHA256:
2d00f5fc739a218657de9cc82d0fb1193649decfa3d4813d15ef0782d8dc6927

accepted continuation before stop:
solver step 369 -> 451

stop before requested step:
452

stop classification:
GUARD_FRONT_SCAN_FAILURE

stop reason:
successful-domain compatibility residual is not monotone
```

The first 82 accepted continuation rows through step 451 reproduced the authoritative failed Increment 4D evidence. The stop occurred while constructing the step-452 Guard-front scan before any new root or solver step was accepted.

## Reproduced step-451 Guard-front evidence

The authoritative corrected Increment 4E evidence contains 15 successful categorical-bisection midpoints. When all intermediate successful midpoints are sorted by requested pressure offset, the first values include:

```text
Delta-p = 10.85551441181451 Pa
R = +0.010661053123812912 kg/s

Delta-p = 10.855514453724027 Pa
R = +0.01066127150667873 kg/s
```

The second residual is approximately `2.18e-7 kg/s` larger than the first, producing the Increment 4F nonmonotonic classification.

The same evidence then decreases through:

```text
Delta-p = 55 Pa
R = -0.00046023298601683034 kg/s

Delta-p = 100 Pa
R = -0.005148895980200964 kg/s

Delta-p = fixed chi cap
R = -0.011746583719090032 kg/s
```

The two near-front successful states differ by approximately `4.19e-8 Pa` in requested pressure offset while their absolute pressures are near `4.95 MPa`. They are intermediate categorical-bisection evidence, not independently selected root-topology nodes.

## Defect classification

The fixed Increment 4F method states:

```text
1. categorically bisect the B1-unavailable / B1-success front for exactly 32 iterations
2. retain the final successful upper endpoint as the refined first-success probe
3. combine that final probe with higher fixed B1-success states
4. form the compatibility-root bracket only from successful B1 states
```

The first implementation instead combined every intermediate successful midpoint from all 32 categorical iterations into the residual-topology sequence and required that enlarged evidence sequence to be globally monotone.

That requirement is not part of the fixed physical or root method. Intermediate bisection points exist to locate the categorical B1 front. They remain evidence, but only the final successful upper endpoint represents the refined first-success topology node.

The stop is therefore an implementation defect caused by mixing:

```text
Guard-front refinement evidence rows
```

with:

```text
compatibility-root topology rows
```

It is not evidence that the selected Weak Compression root, B1-success domain, fixed `chi` scope, direction, phase, positivity, or conservation failed.

## Fixed correction

Retain every fixed scan row and every categorical-bisection midpoint in the evidence tables without modification.

For compatibility-root topology and residual monotonicity only, use:

```text
node 1:
the final successful upper endpoint after exactly 32 Guard-front iterations

nodes 2...N:
fixed B1-success scan nodes with requested pressure offset strictly greater
than the final successful upper endpoint
```

Do not include earlier successful categorical-bisection midpoints in the root-topology sequence.

The root-topology sequence must still satisfy:

```text
all nodes are B1 success
all nodes are locally admissible
requested pressure offsets strictly increase
successful residuals are monotone nonincreasing
exactly one admissible sign-change bracket exists
```

Use the unchanged maximum 32 compatibility-root bisection iterations.

All intermediate successful and unavailable categorical midpoints remain recorded with their exact formal outcomes, requested coordinates, realized coordinates, and residuals where available. No evidence is discarded; only the role of each row is separated.

## Rerun scope

Rerun the unchanged Increment 4F full-horizon continuation through a narrow wrapper replacing only the Guard-front compatibility-root topology construction described above.

The rerun must preserve:

```text
first 82 accepted continuation rows through step 451 reproduced exactly
first Guard-front refinement activation = requested step 452
Guard-front categorical iterations = 32
root mass tolerance = 1.0e-8 kg/s
Weak Compression scope = 0 < chi <= 1.0e-6
root bisection maximum = 32
B1 behavior and formal outcomes = unchanged
failed B1 states never serve as root endpoints
failed B1 states never construct a flux
formal project states = false
```

The rerun evidence must separately report:

```text
Guard-front evidence-row count
Guard-front successful-intermediate-row count
root-topology node count
root-topology requested pressure offsets
root-topology residual sequence
root-topology monotonicity
root-topology sign-change count
```

A passing full-horizon result remains `MODEL_REVIEW / WORKING_VERTICAL_SLICE` evidence only.
