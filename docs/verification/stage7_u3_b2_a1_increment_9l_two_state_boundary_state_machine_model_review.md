# Stage 7 U3 B2 A1 Increment 9L two-state boundary state machine

## Status

`MODEL_REVIEW_ONLY / PROVISIONAL_ENGINEERING_PHYSICS / END_TO_END_WORKING_TOOL PRIORITY / NOT VERIFICATION`

Increment 9L generalizes the successful Increment 9K hard continuation into a reusable boundary controller that starts from the normal initial state and runs one unchanged `FvmSolver` trajectory to the nominal `2L/c0` horizon.

The objective is a working tool path. This increment does not modify the locked B2 contract, B1 equations or search, the production B2 adapter, the `FvmSolver` core, accepted tolerances, or the finite-compression `chi` cap.

## Precursor evidence

Increment 9K established that the authoritative step-637 state can be continued by an explicit engineering closure:

```text
Increment 9K source SHA:
0ec2938c02de812535269a3f28b51b065f943303

workflow run:
31680200411

job:
94383678744

artifact:
9173152297

artifact SHA256:
bf1c85e4928820ff71fe7cd3ce16d4ee1c5f4693f65eb72ace2f3e6d62accd39

actual continuation:
step 637 -> step 640

final time:
0.004285834855172021 s
```

Increment 9J remains the strict evidence that the old outward-flow model was not approved beyond step 637:

```text
ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE
TECHNICAL_ISSUE_A1_NEAR_ZERO_FLOW_BRANCH_TRANSITION
```

Increment 9L does not reinterpret that result as a proven zero-flow root.

## Public boundary state machine

The reusable controller has exactly two public boundary states:

```text
OUTWARD_FLOW
    |
    | expected near-zero branch exhaustion
    v
ZERO_TRANSFER_CLOSED
```

The transition is one-way in Increment 9L.

```text
re-entry: disabled
reverse mass transfer: disabled
closed -> outward transition: disabled
```

The state machine shall not depend on an absolute solver step number, a preloaded step-637 state, or a hard-coded transition time.

## Internal outward-flow model selection

`OUTWARD_FLOW` is one public state, but it retains two existing internal numerical/physics paths:

```text
THREE_BRANCH_WAVE_MODEL
    rarefaction / neutral endpoint / weak compression

GENERAL_EOS_FINITE_COMPRESSION
    dynamic seeded admissible-island Hugoniot root
```

The internal switch is triggered only by the existing classification:

```text
FINITE_COMPRESSION_MODEL_REQUIRED
```

It is not a public boundary-state transition and does not close the outlet. The previous accepted root pressure remains the deterministic continuation seed.

The finite-compression path may use the existing dynamic fixed/Guard-front topology as a limited fallback when the seeded interval is unsuitable because it touches an interval edge or the seed is at the weak/finite scope boundary. This fallback may not alter scan counts, tolerances, `chi` scope, B1 behavior, or the Hugoniot equations.

## Closure transition trigger

Increment 9L initially authorizes exactly one outward-to-closed trigger:

```text
classification:
NO_ADMISSIBLE_ISLAND

message family:
dynamic seeded interval contains no admissible island
```

This is a step-independent model outcome generated before any face flux or solver-state mutation for the requested step.

When this expected classification occurs:

1. the failed outward candidate is not used as a root or flux state;
2. no solver step has yet been accepted for that request;
3. the controller records the technical issue and transition event;
4. the public state changes once to `ZERO_TRANSFER_CLOSED`;
5. the same requested FVM step is evaluated with the closed-state flux.

No additional root-search refinement is performed after the trigger.

## Fail-closed classifications

The following do **not** authorize an engineering closure and shall stop the run without disguising the cause:

```text
MULTIPLE_LOCAL_ROOTS
MULTIPLE_COMPATIBILITY_ROOTS
SUCCESS_DOMAIN_NONMONOTONE
phase departure
two-phase transition
reverse pressure or reverse mass-flow request
nonfinite state or flux
nonpositive density
nonpositive internal energy
root or conservation gate failure
B1 behavior outside the predeclared expected topology
unknown exception or unclassified failure
```

A fixed-scan fallback that does not return one supported finite-compression root also stops. It may not be converted into closure unless a future model review explicitly adds that exact classification.

## Closed-state engineering model

After transition, the right external-face flux uses the adjacent interior static pressure `p_i`:

```text
F_rho     = 0
F_rho_u   = p_i
F_rho_E   = 0
F_rho_xv  = 0
```

Interpretation:

- mass transfer is exactly zero;
- advected energy transfer is exactly zero;
- vapor-scalar transfer is exactly zero;
- only the interior wall-pressure traction acts on the modeled fluid;
- external reservoir pressure is carried by the assumed one-way closure device;
- no B1 state or Hugoniot root is constructed after closure;
- reverse outlet velocity caused by acoustic reflection is diagnostic information, not reverse mass transfer.

## End-to-end execution requirement

Increment 9L shall build the baseline `LIQUID_SMALL_DROP` initial state and use one `FvmSolver` instance from:

```text
t = 0
solver step = 0
```

to:

```text
t = 2L/c0 = 0.004285834855172021 s
```

The final step shall be clipped to the target. A checkpoint artifact or absolute step-number transition may not be used to complete the trajectory.

## Per-step engineering gates

Every accepted step shall require:

```text
accepted dt > 0
finite conserved values
positive density everywhere
positive internal energy everywhere
all cells remain normalized liquid
rho*xv remains exact zero
step mass conservation gate PASS
step momentum conservation gate PASS
step energy conservation gate PASS
cumulative mass conservation gate PASS
cumulative momentum conservation gate PASS
cumulative energy conservation gate PASS
```

For `OUTWARD_FLOW`, also require:

```text
one supported admissible root
root residual within retained tolerance
root velocity nonreverse
root Mach subsonic
energy and momentum ledgers PASS
```

For `ZERO_TRANSFER_CLOSED`, also require:

```text
right mass flux exact zero
right energy flux exact zero
right vapor flux exact zero
right momentum flux = reconstructed interior static pressure exactly
no B1 or Hugoniot reconstruction
```

## State-machine gates

A successful Increment 9L working slice requires:

```text
initial-state start confirmed
one FvmSolver instance used for the complete trajectory
no absolute step-number transition condition
OUTWARD_FLOW accepted for at least one step
internal finite-compression model used for at least one step
exactly one OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED transition
transition trigger = NO_ADMISSIBLE_ISLAND
ZERO_TRANSFER_CLOSED accepted for at least one step
no public-state re-entry
no public-state chatter
nominal 2L/c0 reached by actual accepted FVM steps
target time error within binary64 roundoff
all per-step engineering gates PASS
```

## Required evidence

The immutable workflow artifact shall contain at least:

```text
summary.json
step_metrics.csv
boundary_state_history.csv
boundary_transition_events.csv
outward_model_transition_events.csv
technical_issue.json
initial_and_final_states.npz
authority_verification.json
report.md
artifact_sha256.txt
```

The boundary history shall make the full sequence auditable from step 1 through the final accepted step.

## Working-state interpretation

A successful result may be described as:

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

It may not be described as `VERIFIED`, `ACCEPTED`, `VALIDATED`, or `APPROVED`.

## Formal-state boundary

Regardless of execution success, retain:

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

A separate contract, verification programme, and validation basis are required before any formal state changes.

## Deferred work

Increment 9L explicitly defers:

```text
ZERO_TRANSFER_CLOSED -> OUTWARD_FLOW re-entry
reverse-flow boundary physics
hysteresis tuning
open-orifice versus check-valve validation
two-phase transition
mesh/CFL verification
physical/reference validation
production integration
```
