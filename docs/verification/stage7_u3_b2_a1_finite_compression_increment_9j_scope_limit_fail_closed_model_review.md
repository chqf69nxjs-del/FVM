# Stage 7 U3 B2 A1 Increment 9J scope limit and fail-closed decision

## Status

`MODEL_REVIEW_ONLY / SCOPE_DECISION / FAIL_CLOSED / NO_SOLVER_ADVANCE`

This record fixes the project-level decision after Increment 9J reached its predeclared unsupported case. It does not approve a zero-flow branch, reverse flow, a new root-search rule, a tolerance change, a `chi`-range change, or solver continuation.

## Authoritative decision precursor

After correcting the parent-authority binding and the broad-candidate stagnation schema, the fixed Increment 9J diagnostic ran with:

```text
workflow run:
31676910126

job:
94373367790

source Git SHA:
c194068a0c64b46b915b5f31c12a3ec80c7cbbe8

4097-node ultrafine interval:
unchanged

513-node broad endpoint interval:
unchanged

solver step 638 attempted:
no
```

The run reached the retained Increment 9J decision gate and stopped with:

```text
classification:
ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE

message:
zero-flow endpoint did not meet retained compatibility criteria
```

This is no longer an authority-binding defect or a missing-field schema defect. It is the predeclared unsupported result corresponding to Increment 9J case 3.

Because the original diagnostic raises before writing an artifact for an unsupported classification, a final capture runner may catch only this exact expected exception, read the already-computed `_run` frame values, and materialize them as immutable evidence. It may not modify, resume, or repeat an inner root/bisection calculation; increase a scan count; change a gate; or convert the unsupported classification into a supported one.

## Project decision

The project shall take:

```text
scope limit / fail-closed hold
```

rather than:

```text
additional automatic root-scan refinement
zero-flow branch implementation
step 638 continuation
full 2L/c0 completion claim
```

The technical reason is not merely that the trajectory is close to zero flow. The fixed final diagnostic did not support either of the two conditions required to continue:

```text
1. a unique admissible outward-flow compatibility root in the fixed ultrafine interval
2. a zero-flow endpoint satisfying the retained compatibility gate
```

Increasing 4097 or 513 nodes after this result would change the agreed question and would make search resolution, rather than the transient-tool objective, the work product.

## Retained A1 working scope

The finite-compression A1 boundary vertical slice remains usable only while all of the following are true:

```text
single-phase liquid
outward flow
subsonic candidate
positive finite density
positive finite internal energy
rho*xv exact zero
B1 success
local candidate admissibility PASS
one unique compatibility root
1e-6 < chi <= 1e-4
absolute compatibility-root residual <= 1e-8 kg/s
unchanged mass / momentum / energy closure gates PASS
no phase or branch chatter
```

The numeric `chi` interval alone is not sufficient. The unique-root, B1-success, and local-admissibility conditions remain mandatory at every accepted step.

For the present authoritative trajectory, accepted working-vertical-slice authority ends at:

```text
solver step:
637

solver time:
0.004269583083221582 s

nominal 2L/c0 target:
0.004285834855172021 s

remaining nominal time:
1.6251771950439448e-5 s
```

The proximity to the target does not authorize extrapolation across the unsupported branch region.

## Explicit fail-closed conditions

A1 shall stop without constructing a face flux or mutating the FVM state when any retained condition fails, including:

```text
no admissible compatibility-root island
no unique compatibility root
multiple compatibility roots
B1 unavailable
local candidate inadmissible
reverse velocity or reverse pressure/flow
phase departure
two-phase transition
positivity failure
nonfinite state
root residual above the locked tolerance
zero-flow endpoint after outward-root termination
zero-flow to outward-flow re-entry
branch chatter
```

For this trajectory, the specific stop remains:

```text
near-zero-flow transition not approved
```

No B1-unavailable candidate may become a compatibility root, selected root, flux state, or solver-step authority. Diagnostic candidate stagnation reconstruction remains scalar-topology evidence only.

## Claims that remain unavailable

The following claims are not supported:

```text
step 638 passed
full 2L/c0 passed
finite-compression branch approved
zero-flow branch approved
reverse-flow handling approved
single-phase finite-pipe coupling verified
U3 B2 benchmark accepted
physical validation
design use
production activation
```

The result is still useful: it establishes a working single-phase outward-flow vertical slice through step 637 and identifies its present branch boundary without disguising the unresolved transition.

## Deferred work policy

A separate zero-flow branch model should be opened only if the project later requires operation beyond this boundary. That work would need a new, predeclared contract covering at least:

```text
mass flux = 0
energy flux = 0
momentum pressure traction
B2 zero-transfer identity
conservation
pressure discontinuity and acoustic reflection
outward -> zero-flow transition
zero-flow hold
zero-flow -> outward-flow re-entry
reverse-flow separation
transition chatter prevention
```

It is not part of the current Increment 9J closeout and is not automatically justified merely to recover the final approximately 0.38% of the nominal horizon.

## Required final capture evidence

The final capture shall record:

```text
exact unsupported exception classification and message
run/job/source identity of the precursor
parent run/job/artifact/SHA/digest authority
fixed 12 / 4097 / 513 scan counts
ultrafine category and island counts
root-topology count and sign changes
stagnation-pressure and velocity endpoint brackets
both scalar endpoint values and chi separation
each retained zero-flow compatibility sub-gate
which sub-gate or sub-gates failed
broad-candidate schema-correction evidence
step-637 state SHA before and after
state unchanged
step 638 not attempted
scope-limit decision complete
all formal project states false
```

The capture workflow may pass only when it proves the expected fail-closed decision. A passing capture workflow is evidence that the stop was recorded correctly; it is not a passing physical continuation or benchmark.

## Formal-state boundary

Retain:

```text
finite_compression_branch_approved = false
multi_step_finite_compression_continuation_authorized = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
