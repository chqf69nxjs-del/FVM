# Stage 7 U3 B2 A1 Increment 9L Guard-front root-topology correction

## Status

`MODEL_REVIEW_ONLY / IMPLEMENTATION_ROOT_TOPOLOGY_CORRECTION / NO PHYSICS OR TOLERANCE CHANGE`

## Failed precursor

The connected-rarefaction handoff correction was executed from the locked initial state with:

```text
source Git SHA:
af16ae68d8ce3581416486a3ce55f84441af5623

workflow run:
31686545744

job:
94403827129

artifact:
9175846671

artifact SHA256:
cda10e7ff8663daba089b3ca7a4207f69ed4f38ca7a781786b66a82e2dd0eef1
```

The run accepted 451 actual FvmSolver steps and stopped before accepting requested step 452 with:

```text
classification:
SUCCESS_DOMAIN_NONMONOTONE

message:
three-branch outward model failed:
successful-domain compatibility residual is not monotone
```

The accepted trajectory through step 451 retained:

```text
finite conserved state
positive density
positive internal energy
single-phase liquid
rho*xv exact zero
step and cumulative mass / momentum / energy gates PASS
```

Accepted outward branches were:

```text
CONNECTED_RAREFACTION: 336 steps
NEUTRAL_ENDPOINT: 1 step
WEAK_COMPRESSION: 114 steps
```

No public boundary transition or finite-compression transition had yet occurred.

## Classification

This is an implementation/root-topology classification defect, not a physical-state failure.

The Guard-front categorical bisection intentionally evaluates both B1-unavailable and B1-success candidates. Successful intermediate bisection points are valuable evidence for locating the categorical boundary, but they are not all members of the ordered compatibility-root topology. Mixing every successful intermediate point into the topology can make the residual sequence appear nonmonotone even though the retained final first-success endpoint and the higher fixed B1-success nodes form the authoritative ordered domain.

The same defect was previously isolated and corrected in the authoritative verification-side source:

```text
tools/verification/
u3_b2_a1_weak_compression_bridge_full_horizon_guard_front_root_topology.py
```

That correction records its original failed authority as:

```text
source SHA:
618f49c0a75620751cb517d669a4da868e82f41e

workflow run:
31619671593

job:
94191039227

artifact:
9150769457

artifact SHA256:
2d00f5fc739a218657de9cc82d0fb1193649decfa3d4813d15ef0782d8dc6927

stop:
SUCCESS_DOMAIN_NONMONOTONE
```

Increment 9L shall reuse that existing correction rather than invent a new topology rule.

## Correction

All Guard-front scan and bisection rows remain immutable diagnostic evidence.

Compatibility-root topology shall use only:

```text
1. the final refined first B1-success endpoint
2. higher fixed B1-success nodes
```

The following remain evidence-only and are not compatibility-root topology members:

```text
B1-unavailable candidates
intermediate categorical-bisection success candidates
```

The ordered retained topology shall then be checked for:

```text
strictly increasing requested pressure offset
monotone nonincreasing compatibility residual
zero or one sign-change bracket
local admissibility of any selected bracket
```

If no sign-change bracket remains and the retained weak-compression scope-limit residual is still positive above the locked root tolerance, the existing classification shall be:

```text
FINITE_COMPRESSION_MODEL_REQUIRED
```

This classification hands the same requested step to the already implemented general-EOS finite-compression path while the public boundary state remains `OUTWARD_FLOW`.

## Invariants

The correction shall not change:

```text
mass, momentum, or energy equations
B1 equations, search, or guards
production B2 adapter
FvmSolver core
locked B2 contract
root tolerance
velocity tolerance
chi cap
fixed scan node counts
Guard-front bisection count
Hugoniot equations
zero-transfer closure flux
public state-machine transitions
```

No failed B1 state or intermediate evidence row may become:

```text
a root endpoint
a selected root
a flux state
an accepted solver-step authority
```

## Increment 9L integration

The public state machine remains:

```text
OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED
```

The internal progression remains step-independent:

```text
CONNECTED_RAREFACTION
    -> GENERAL_THREE_BRANCH_CLASSIFICATION
    -> GENERAL_EOS_FINITE_COMPRESSION
    -> expected NO_ADMISSIBLE_ISLAND
    -> ZERO_TRANSFER_CLOSED
```

This correction acts only inside `GENERAL_THREE_BRANCH_CLASSIFICATION`.

## Evidence requirement

The corrected Increment 9L artifact shall record:

```text
failed precursor run/job/artifact/SHA/digest
existing authoritative topology-correction source identity
first corrected requested step
corrected step count
Guard-front evidence-row count
topology node count
topology monotonicity
topology sign-change count
failed B1 state used as root endpoint = false
failed B1 state used to construct flux = false
intermediate evidence used as topology = false
absolute step-number transition trigger used = false
```

A successful correction gate is bookkeeping/topology evidence only. Increment 9L must still satisfy the original end-to-end state-machine, conservation, positivity, phase, and horizon gates.

## Formal-state boundary

All formal verification, acceptance, validation, approval, design-use, and production-activation fields remain false.
