# Stage 7 U3 B2 A1 post-endpoint branch classification model review

## Status

`MODEL_REVIEW_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

This increment classifies the A1 boundary branch after the accepted step-337 neutral-endpoint resume. It is a short, fail-closed diagnostic only. It does not approve a finite compression branch, revise the locked B2 v1 Contract, change the accepted B1 component, modify the production B2 Adapter or `FvmSolver`, introduce a new physics tolerance, complete the full `2L/c0` horizon, or promote any formal project state.

## Authoritative parent evidence

```text
parent source:
b91832d44e1697fc8d78be2a3bee9c64a9defd72

workflow run:
31523220994

job:
93885176265

artifact:
9113961454

artifact SHA256:
f88496df9623a13b6b9eab2d8335a43d5882804b41722f26d7ec1112446c4ccb

step-336 checkpoint time:
0.0022506672049592393 s

step-337 accepted dt:
6.7068718412e-6 s

step-337 boundary branch:
NEUTRAL_ENDPOINT

step-337 endpoint residual:
9.2841e-10 kg/s

retained root-mass tolerance:
1.0e-8 kg/s

step-337 outlet pressure after the accepted step:
4950034.464684777 Pa

step-337 outlet velocity after the accepted step:
+0.122536622775 m/s

step-337 outlet phase:
liquid
```

The parent evidence accepted `p_P = p_i` before requiring a sign-change bracket because the endpoint itself was already inside the retained root-mass tolerance. No positive-pressure continuation constructed the applied step-337 flux.

## Objective

Determine which of the following occurs immediately after solver step 337:

```text
Outcome A:
The boundary remains on NEUTRAL_ENDPOINT and/or the approved RAREFACTION branch for 32 additional accepted FvmSolver steps.

Outcome B:
The endpoint leaves the retained root tolerance and a compatible root is supported only on the local positive-pressure side, so a finite compression branch is required before another FvmSolver step may be taken.
```

Both outcomes are useful. Outcome A is a candidate basis for a later branch-aware long-horizon diagnostic. Outcome B requires an independent general-EOS Hugoniot, entropy-condition, and Lax 1-shock derivation before implementation.

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

starting accepted solver step:
337

maximum additional accepted steps:
32

nominal attempted solver steps:
338 through 369
```

The exact step-336 checkpoint and the accepted neutral-endpoint step 337 are reproduced first from the parent numerical sources. The short post-endpoint diagnostic starts only after that reproduction passes.

## Fixed per-step order

For every pre-step outlet state, perform the following operations in this order:

```text
1. reconstruct the current outlet cell
2. evaluate the endpoint residual at p_P = p_i
3. evaluate the fixed local pressure-offset scan on both sides of the endpoint
4. evaluate the approved connected rarefaction scan from p_i toward p_back
5. classify the branch
6. construct an FVM flux only for NEUTRAL_ENDPOINT or RAREFACTION
7. advance the existing FvmSolver by one accepted step
8. record conservation, phase, direction, B1, energy, and reaction ledgers
```

The endpoint is always tested before any sign-change requirement.

## Fixed local pressure offsets

The local scan retains the checkpoint-review offsets without modification:

```text
p_P - p_i =
-1
-0.1
-0.01
-0.001
-0.0001
-0.00001
-0.000001
0
+0.000001
+0.00001
+0.0001
+0.001
+0.01
+0.1
+1 Pa
```

Positive offsets are local isentropic-continuation observations only. They may classify the need for compression physics, but they may not construct an applied FVM flux.

## Retained root and ledger tolerances

No new tolerance is introduced. In particular:

```text
root mass residual absolute tolerance:
1.0e-8 kg/s

local slope probe distance:
1 Pa

local root slope requirement:
negative

stagnation enthalpy round-trip tolerance:
retained locked B2 value

mass, momentum, and energy inventory tolerances:
retained locked B2 values

restriction-reaction ledger tolerance:
retained locked value

velocity zero tolerance:
retained locked B2 value
```

## Branch classification

### NEUTRAL_ENDPOINT

Classify the state as `NEUTRAL_ENDPOINT` when the endpoint candidate at `p_P = p_i` satisfies all retained checks:

```text
abs(R(p_i)) <= 1.0e-8 kg/s
outward velocity
0 <= Mach < 1
allowed single-phase liquid scope
B1 admissible
stagnation pressure above back pressure
stagnation-state round trip passed
energy/mass decomposition passed
energy-port closure passed
restriction-reaction ledger closure passed
```

No sign-change bracket is required when the endpoint itself passes the retained root tolerance. The applied flux uses exactly the endpoint state. Positive-pressure local scan values are evidence only.

### RAREFACTION

Classify the state as `RAREFACTION` only when all of the following hold:

```text
endpoint root closure does not pass
approved connected rarefaction scan is admissible and subsonic
connected residual sequence is monotone
exactly one connected rarefaction-side sign-change bracket exists
no admissible positive-side local sign-change bracket exists
retained bisection root passes all root, energy, phase, direction, B1, and reaction checks
```

The connected scan retains the existing node count and includes the previous accepted root pressure when it lies inside the current rarefaction domain. The existing A1 rarefaction characteristic relation and retained bisection implementation are used without modification.

### LOCAL_COMPRESSION_REQUIRED

Classify the state as `LOCAL_COMPRESSION_REQUIRED` when:

```text
endpoint root closure does not pass
no approved connected rarefaction root exists
exactly one admissible positive-pressure local sign-change bracket exists
```

This is Outcome B. Stop before constructing or applying the next FVM boundary flux. The positive-side isentropic continuation is not an approved compression model and must not be used to advance the solver.

### Fail-closed classifications

Stop as inconclusive for any of the following:

```text
CHECKPOINT_REPRODUCTION_MISMATCH
ENDPOINT_EVALUATION_FAILURE
CONNECTED_RAREFACTION_NON_MONOTONE
MULTIPLE_LOCAL_ROOTS
LOCAL_ROOT_INADMISSIBLE
NO_LOCAL_COMPATIBLE_ROOT
BRANCH_JUMP
UNEXPLAINED_BRANCH_CHATTER
ROOT_OR_LEDGER_FAILURE
FVM_STEP_DIAGNOSTIC_FAILURE
```

## Branch continuity and chatter rule

A rarefaction root is considered connected only when it is obtained from the admissible, subsonic, monotone scan beginning at the current endpoint and the scan contains exactly one sign-change bracket. Failure of that connected construction is a branch jump; no pressure-jump tolerance is introduced.

The accepted branch history begins with the parent step-337 `NEUTRAL_ENDPOINT`. Before applying each candidate flux, compare the candidate classification with the two latest accepted classifications. A consecutive `A -> B -> A` pattern between `NEUTRAL_ENDPOINT` and `RAREFACTION` is classified as `UNEXPLAINED_BRANCH_CHATTER` and stops before the candidate step. This is a categorical sequence rule, not a new physics tolerance.

## Actual FvmSolver use

For `NEUTRAL_ENDPOINT` and `RAREFACTION` only, construct the existing pipe-side Euler flux:

```text
F_rho    = rho_P * u_P
F_rho_u  = rho_P * u_P^2 + p_P
F_rho_E  = rho_P * u_P * h0_P
F_rho_xv = 0
```

Use the existing `FvmSolver`, CFL calculation, boundary mass-removal limit, boundary energy-removal limit, deterministic halving limit, positivity checks, reverse-direction check, phase check, and exact `rho*xv = 0` identity. B1 downstream momentum and restriction reaction remain separate diagnostic ledgers.

## Required per-attempt record

At minimum, record:

```text
solver step requested
solver step accepted
solver time before and after
dt and halving count
p_i
u_i
p_P
p_P - p_i
branch classification
endpoint residual
retained root tolerance
endpoint within retained tolerance
rarefaction-side local sign-change count
positive-side local sign-change count
connected rarefaction sign-change count
connected rarefaction monotonicity
root mass residual
local root slope and stencil
Mach
mass flow
B1 formal outcome
p_0,P - p_back
pipe-side momentum port
downstream momentum port
restriction reaction
reaction-ledger residual
step and cumulative mass residuals
step and cumulative momentum residuals
step and cumulative energy residuals
rho*xv exact zero
outlet phase
reverse-flow Guard
reverse outlet velocity
```

The complete fixed local scan is retained as a separate evidence table for every attempted post-endpoint step.

## Diagnostic gate

The classification diagnostic gate passes for either of the following:

```text
OUTCOME_A_NEUTRAL_RAREFACTION_STABLE_32_STEPS
OUTCOME_B_LOCAL_COMPRESSION_REQUIRED
```

Outcome A requires 32 additional accepted steps, no fail-closed classification, all accepted-step checks passed, and every applied branch classified as `NEUTRAL_ENDPOINT` or `RAREFACTION`.

Outcome B requires a fail-closed stop before the candidate FVM step, endpoint residual outside the retained root tolerance, no approved rarefaction root, exactly one admissible positive-side local root bracket, and confirmation that no positive-pressure continuation flux was applied.

Any other result fails the diagnostic gate.

## Mandatory formal flags

The following remain false regardless of Outcome A or Outcome B:

```text
finite_compression_branch_approved = false
post_endpoint_multi_step_passed = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

A successful short diagnostic is not formal finite-pipe verification or benchmark acceptance.

## Immediate stop conditions

Stop before or immediately after the affected operation for any of the following:

```text
checkpoint or step-337 reproduction mismatch
multiple local or connected roots
non-monotone connected rarefaction residual
branch jump
A -> B -> A branch chatter
endpoint residual outside tolerance with positive-side-only root
subsonic departure
reverse velocity
B1 reverse-pressure Guard
phase-scope departure
positivity failure
mass closure failure
momentum closure failure
energy closure failure
restriction-reaction ledger failure
unexpected branch/head movement
unexpected workflow fan-out
```

No tolerance, Contract, B1 behavior, production Adapter, solver behavior, or formal state may be changed to obtain a passing result.

## Claim boundary

A passing Outcome A means only that the already-defined neutral and rarefaction logic continued for 32 additional accepted steps after the reproduced step 337 under the retained checks.

A passing Outcome B means only that the short diagnostic found evidence that an approved finite compression branch is required before further advancement.

Neither outcome means finite compression approval, full-horizon passage, finite-pipe verification, benchmark acceptance, Physical Validation, design-use acceptance, or production activation.
