# Stage 7 U3 B2 A1 Increment 9L two-state boundary state machine closeout

## Status

`PROVISIONAL ENGINEERING END-TO-END WORKING SLICE / EXECUTED / EVIDENCE INSPECTED / NOT VERIFIED / NOT ACCEPTED`

Increment 9L generalizes the Increment 9K fixed continuation into a step-independent two-state boundary controller and executes one `FvmSolver` trajectory from the locked initial state to the nominal `2L/c0` horizon.

The result is a working engineering path. It does not modify or approve the locked B2 benchmark, B1, the production B2 adapter, the `FvmSolver` core, accepted tolerances, or the finite-compression `chi` cap.

The remaining branch-transition physics and production-integration work are tracked in GitHub Issue #150.

## Authoritative runner evidence

```text
Increment 9L v5 source Git SHA:
bdbbf88b240ff1b839d8a72fa898437efac1e7b8

workflow run:
31690390529

job:
94416115006

runner step:
SUCCESS

artifact ID:
9177683047

artifact name:
u3-b2-a1-increment-9l-v5-31690390529

artifact SHA256:
0ff366738c855c83d9355c3e18b2cb54f640354a34b96211d85dd205269f6b32
```

The workflow conclusion was red only because its first inspection script contained an incorrect fixed assertion. The FVM runner and its explicit runner-success requirement both passed, and the artifact was uploaded.

## Inspection-correction evidence

The immutable v5 artifact was inspected without rerunning FVM or recomputing any root, flux, or state:

```text
inspection source Git SHA:
81d990ce15d9bbcb576aac2e011f820b1c835816

workflow run:
31692668358

job:
94423259631

workflow conclusion:
SUCCESS

artifact ID:
9178027608

artifact name:
u3-b2-a1-increment-9l-v5-inspection-correction-31692668358

artifact SHA256:
51530de2900fcddd2fd1cef3361e043fce9b9dc65a9a88e3c5ecf3a286d68d49
```

The corrected inspection verified:

```text
source artifact file set: exact
source internal manifest: PASS
all source internal file SHA256 values: PASS
640 per-step engineering gates: PASS
all step and cumulative conservation gates: PASS
state NPZ identity and SHA256: PASS
transition histories: PASS
formal-state boundary: preserved
```

## Why the first inspection failed

The original inspection asserted:

```text
first_fallback_requested_step == 606
```

The immutable evidence shows:

```text
step 484:
first authorized bounded-window fallback
and first GENERAL_EOS_FINITE_COMPRESSION step

step 606:
first fallback scan containing a trailing excluded candidate
```

Thus step 606 is the first bounded **trailing exclusion**, not the first fallback invocation. The corrected inspection preserves the v5 implementation and artifact unchanged.

## End-to-end solver execution

The run used:

```text
initial state:
locked LIQUID_SMALL_DROP state

initial solver step:
0

initial time:
0.0 s

FvmSolver instances:
1

checkpoint artifact:
none

absolute step-number transition condition:
none

cells:
32

CFL:
0.1
```

The solver accepted:

```text
640 actual FvmSolver steps
```

and reached:

```text
final solver step:
640

final time:
0.004285834855172021 s

nominal 2L/c0 target:
0.004285834855172021 s

horizon fraction:
1.0

horizon time error:
0.0 s

final step target-clipped:
true
```

This is not checkpoint replay or time extrapolation.

## Public boundary state machine

The public state machine is exactly:

```text
OUTWARD_FLOW
    |
    | expected near-zero branch exhaustion
    v
ZERO_TRANSFER_CLOSED
```

Accepted public-state history:

```text
OUTWARD_FLOW:
637 steps

ZERO_TRANSFER_CLOSED:
3 steps

public transition count:
1

public-state chatter:
false

re-entry:
disabled

reverse mass transfer:
disabled
```

The public transition occurred while preparing requested step 638:

```text
from:
OUTWARD_FLOW

to:
ZERO_TRANSFER_CLOSED

trigger:
NO_ADMISSIBLE_ISLAND

message:
dynamic seeded interval contains no admissible island

failed candidate used as root:
false

failed candidate used as flux:
false

solver state mutated before transition:
false

absolute step-number trigger used:
false
```

The same requested step 638 was then accepted with the closed-state engineering flux.

## Internal outward-flow progression

The public state remained `OUTWARD_FLOW` while the existing internal models changed by classifications rather than step numbers.

### Connected rarefaction

```text
accepted steps:
1-336

branch:
CONNECTED_RAREFACTION
```

### Rarefaction-to-three-branch handoff

```text
requested step:
337

from algorithm:
CONNECTED_RAREFACTION

to algorithm:
GENERAL_THREE_BRANCH_CLASSIFICATION

trigger:
CONNECTED_ROOT_SIGN_CHANGES_ZERO

failed candidate used as root or flux:
false

state mutation before handoff:
false
```

### Neutral and weak compression

Accepted three-branch history included:

```text
NEUTRAL_ENDPOINT:
1 step

WEAK_COMPRESSION:
146 steps
```

The authoritative Guard-front topology correction was active over 24 requested steps from 452 through 483. Intermediate categorical-bisection rows remained diagnostic evidence only; no failed B1 state or evidence-only row entered root topology or flux construction.

### General-EOS finite compression

```text
internal model transition requested step:
484

from:
THREE_BRANCH_WAVE_MODEL

to:
GENERAL_EOS_FINITE_COMPRESSION

trigger:
FINITE_COMPRESSION_MODEL_REQUIRED

message:
successful residual remains positive through the fixed chi scope

absolute step-number trigger used:
false
```

Accepted finite-compression history:

```text
FINITE_COMPRESSION_HUGONIOT:
154 steps

bounded-window fallback:
steps 484-634
151 events

final dynamic-seeded continuation:
steps 635-637
```

For every bounded-window event:

```text
bounded admissible-success window count:
1

retained root topology monotone:
true

compatibility sign-change count:
1

selected-root gate:
PASS

excluded candidate used as root endpoint:
false

excluded candidate used to construct flux:
false

checkpoint state used:
false

absolute step-number trigger used:
false
```

Topology evolution was recorded as:

```text
first leading excluded candidate:
step 489

first Guard-front refinement:
step 494

first trailing excluded candidate:
step 606
```

## Closed-state execution

Accepted closed steps were:

```text
638
639
640
```

For every closed step:

```text
right mass flux:
exact zero

right energy flux:
exact zero

right vapor flux:
exact zero

right momentum flux:
adjacent interior static pressure exactly

B1 called after closure:
false

Hugoniot root constructed after closure:
false

reverse mass transfer constructed:
false
```

## Conservation and state gates

Maximum absolute residuals over the complete 640-step trajectory were:

```text
step mass residual:
2.5175390835561657e-17 kg

step momentum residual:
3.3186750873423487e-18 kg m/s

step energy residual:
8.049838573498391e-12 J

cumulative mass residual:
2.6461309272224343e-17 kg

cumulative momentum residual:
1.214306433183765e-17 kg m/s

cumulative energy residual:
9.457323812966933e-12 J
```

Final state checks:

```text
all conserved values finite:
PASS

minimum density:
874.2084603532102 kg/m3

minimum internal energy:
216871.95943393288 J/kg

all cells normalized liquid:
PASS

rho*xv exact zero:
PASS

maximum deterministic halvings:
0
```

Final outlet state:

```text
pressure:
4947313.078744332 Pa

velocity:
0.004733450937792009 m/s

Mach:
1.0162598397241116e-05

phase:
liquid
```

State identities:

```text
initial state SHA256:
deaae67e672d92fb1da7c40b1a7a03d904b58f35db12bcec81008b55f9014c21

final state SHA256:
8e73e394f3101840c73c278bbc4521ec4fefeebaee4c7f0db774d87013fd5014
```

## Immutable v5 artifact contents

```text
artifact_sha256.txt
authority_verification.json
boundary_state_history.csv
boundary_transition_events.csv
finite_compression_bounded_window_fallback_correction.json
finite_compression_bounded_window_fallback_events.csv
guard_front_root_topology_correction.json
guard_front_root_topology_correction_events.csv
guard_front_topology_authority_binding_correction.json
initial_and_final_states.npz
initial_rarefaction_handoff_correction.json
outward_model_transition_events.csv
report.md
step_metrics.csv
summary.json
technical_issue.json
three_branch_algorithm_transition_events.csv
```

The internal manifest contains and verifies the SHA256 of every evidence file except the manifest itself.

## Project interpretation

Increment 9L establishes:

```text
step-independent two-state boundary controller:
IMPLEMENTED on verification-side path

initial-state-to-horizon one-solver trajectory:
EXECUTED

internal model handoffs:
EXECUTED by classifications

OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED:
EXECUTED automatically

provisional engineering 2L/c0 horizon:
REACHED

end-to-end working vertical slice:
YES
```

The permitted description is:

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

It is not `VERIFIED`, `ACCEPTED`, `VALIDATED`, or `APPROVED`.

## Remaining technical debt

The following remain open in Issue #150:

```text
ZERO_TRANSFER_CLOSED -> OUTWARD_FLOW re-entry
reverse-flow boundary physics
transition hysteresis and chatter design
open-orifice versus check-valve physical interpretation
closure-reflection characterization
mesh/CFL verification
physical/reference validation
production-path integration
```

The verification-side implementation is currently composed from established model-review modules. The next working-tool increment should consolidate this successful policy into a reusable runner/controller interface with ordinary inputs, event logging, and result export before adding new branch physics.

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

The separate field:

```text
provisional_engineering_two_l_over_c0_reached = true
```

records only the executed engineering working slice.
