# Stage 7 U3 B2 A1 Increment 9L provisional end-to-end state-machine closeout

## Status

`PROVISIONAL ENGINEERING END-TO-END WORKING SLICE / EXECUTED / NOT VERIFIED / NOT ACCEPTED`

Increment 9L generalizes the Increment 9K step-637 engineering closure into a step-independent two-state boundary state machine and demonstrates one actual `FvmSolver` trajectory from the locked liquid initial state to the nominal `2L/c0` horizon.

This closeout records a working engineering tool path. It is not a formal B2 verification, acceptance, validation, approval, design-use, or production-activation result.

## Authoritative clean execution

```text
source Git SHA:
512723f35addb63fd55f86468c69feb6d24fd457

workflow:
Agent U3 B2 A1 Increment 9L State-Based Inspection Clean Rerun

workflow run:
31700264132

job:
94447447243

workflow conclusion:
SUCCESS

artifact ID:
9181655488

artifact name:
u3-b2-a1-increment-9l-state-based-clean-31700264132

artifact SHA256:
36b8276998871e2939fc7755644d5910689838d78f967e025d2e5ce08f0b89f3

artifact expired at closeout:
false
```

The clean workflow independently passed:

```text
source-scope inspection
precursor authority inspection
actual Increment 9L runner
state- and causal-order inspection
artifact upload
final runner/inspection requirement
```

## Execution identity

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.1

start:
locked initial state, t = 0

checkpoint artifact used:
false

FvmSolver instance count:
1

accepted solver steps:
640

final solver step:
640

nominal target 2L/c0:
0.004285834855172021 s

final solver time:
0.004285834855172021 s

horizon fraction reached:
1.0

horizon time error:
0.0 s

final state SHA256:
8e73e394f3101840c73c278bbc4521ec4fefeebaee4c7f0db774d87013fd5014
```

## Step-independent model progression

The observed step numbers below are evidence only. They are not transition criteria.

### Connected rarefaction handoff

The initial outward path used the retained connected-rarefaction solution.

Observed handoff:

```text
requested solver step:
337

time:
0.0022506672049592393 s

from:
CONNECTED_RAREFACTION

to:
GENERAL_THREE_BRANCH_CLASSIFICATION

trigger:
CONNECTED_ROOT_SIGN_CHANGES_ZERO

absolute step-number trigger used:
false

failed candidate used as root:
false

failed candidate used as flux:
false

solver state mutated before handoff:
false
```

### Weak-to-finite-compression model handoff

Observed outward-model transition:

```text
requested solver step:
484

time:
0.0032365792102672024 s

from:
THREE_BRANCH_WAVE_MODEL

to:
GENERAL_EOS_FINITE_COMPRESSION

trigger:
FINITE_COMPRESSION_MODEL_REQUIRED

trigger message:
successful residual remains positive through the fixed chi scope

absolute step-number trigger used:
false
```

### Finite-compression bounded-window topology

The integrated trajectory required the retained bounded admissible B1-success-window root topology.

```text
bounded-window fallback event count:
151

first observed event step:
484

last observed event step:
634

bounded-window gate passed:
true
```

For every accepted bounded-window event, the state-based clean inspection required:

```text
public state = OUTWARD_FLOW
outward model = GENERAL_EOS_FINITE_COMPRESSION
exactly one bounded admissible-success window
retained root topology monotone nonincreasing
exactly one retained root sign-change bracket
selected-root gate PASS
excluded candidates not used as root endpoints
excluded candidates not used to construct flux
checkpoint state not used to select fallback
absolute step-number trigger not used
```

The historical checkpoint-specific inspection assertion that the first bounded-window fallback must occur at step 606 is superseded for Increment 9L by this state- and causal-ordering inspection. This is an evidence-inspection correction only and does not reinterpret the underlying physics.

### Public boundary transition

Observed public state-machine transition:

```text
requested solver step:
638

time:
0.004269583083221582 s

from:
OUTWARD_FLOW

to:
ZERO_TRANSFER_CLOSED

trigger classification:
NO_ADMISSIBLE_ISLAND

trigger message:
dynamic seeded interval contains no admissible island

absolute step-number trigger used:
false

failed candidate used as root:
false

failed candidate used as flux:
false

solver state mutated before transition:
false

re-entry allowed:
false
```

The public state history contained exactly one transition and no chatter:

```text
OUTWARD_FLOW accepted steps: 637
ZERO_TRANSFER_CLOSED accepted steps: 3
public transition count: 1
public-state chatter detected: false
```

## Closed-state engineering model

After the public transition, the right external-face conservative flux remained the Increment 9K provisional engineering identity:

```text
F_rho     = 0
F_rho_u   = p_i
F_rho_E   = 0
F_rho_xv  = 0
```

The clean run reported:

```text
right mass transfer exact zero for all closed steps:
true

right energy transfer exact zero for all closed steps:
true

right vapor transfer exact zero for all closed steps:
true

wall momentum identity exact for all closed steps:
true

reverse mass-transfer model supported:
false
```

The model remains a one-way/non-return provisional closure. Re-entry and reverse-flow physics are outside Increment 9L scope.

## State and conservation results

The final state remained in the retained single-phase liquid scope:

```text
final normalized phases:
[liquid]

final outlet pressure:
4947313.078744332 Pa

final outlet velocity:
0.004733450937792009 m/s

final outlet Mach:
1.0162598397241116e-05

minimum density:
874.2084603532102 kg/m3

minimum internal energy:
216871.95943393288 J/kg

rho*xv exact zero:
true

maximum solver halving count:
0
```

Conservation residual maxima over the end-to-end trajectory were:

```text
maximum absolute step mass residual:
2.5175390835561657e-17 kg

maximum absolute cumulative mass residual:
2.6461309272224343e-17 kg

maximum absolute step momentum residual:
3.3186750873423487e-18 kg m/s

maximum absolute cumulative momentum residual:
1.214306433183765e-17 kg m/s

maximum absolute step energy residual:
8.049838573498391e-12 J

maximum absolute cumulative energy residual:
9.457323812966933e-12 J
```

All accepted-step Increment 9L engineering gates passed in the clean state-based inspection.

## Working-slice result

The authoritative clean run reported:

```text
outcome:
INCREMENT_9L_PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE_PASS

increment_9l_state_machine_gate_passed:
true

working_vertical_slice:
true

working_vertical_slice_kind:
PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE

provisional_engineering_two_l_over_c0_reached:
true
```

This establishes that the current liquid case can be advanced from its locked initial state through the retained outward-flow models, the expected near-zero-flow branch exhaustion, and the provisional zero-transfer closed model to the nominal horizon without a hard-coded transition step or checkpoint-state continuation.

## Strict predecessor interpretation retained

Increment 9L does not reinterpret the strict Increment 9J result.

The near-zero transition remains the open technical issue:

```text
TECHNICAL_ISSUE_A1_NEAR_ZERO_FLOW_BRANCH_TRANSITION
```

The strict predecessor classification remains evidence that the old outward-flow construction was not formally supported beyond its retained scope. Increment 9L moves forward using an explicit provisional engineering boundary transition rather than claiming that the missing strict root was proven.

## Technical debt retained

Issue #150 remains open. Retained work includes:

```text
general physical transition criterion
open-orifice versus non-return/check-valve distinction
zero-transfer hold interpretation
controlled re-entry, if required
reverse flow as a separate model
hysteresis / chatter policy before re-entry
pressure-wave reflection characterization
physical/reference validation
Increment 9J capture bookkeeping repair as evidence hygiene
```

None of these are required to describe Increment 9L as a provisional engineering working slice, but they remain required before broader physical authority is claimed.

## Architecture implication

Increment 9L provides the first end-to-end working example of the project model-management pattern:

```text
state reconstruction
    -> applicability / admissibility classification
    -> model transition
    -> conservative solver continuation
```

The broader design principles are recorded separately in:

```text
docs/verification/stage7_physics_model_management_principles_v0.md
```

This pattern is intended to support later regime changes, including staged liquid-to-two-phase model transitions, while controlling the growth of model freedom.

## Formal-state boundary

The clean end-to-end execution does **not** set any formal verification or acceptance state.

Retain exactly:

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

## Closeout classification

```text
IMPLEMENTED:
yes

WORKING VERTICAL SLICE:
yes — PROVISIONAL ENGINEERING END-TO-END WORKING SLICE

VERIFIED:
no

ACCEPTED:
no

VALIDATED:
no

APPROVED:
no
```

The recommended next development step is tool integration rather than new physics: consolidate the demonstrated path behind a reusable Physics/Boundary Model Manager interface while retaining the same supported models and formal-state limits.
