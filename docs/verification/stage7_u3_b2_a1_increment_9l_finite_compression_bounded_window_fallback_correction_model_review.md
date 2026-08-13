# Stage 7 U3 B2 A1 Increment 9L finite-compression bounded-window fallback correction

## Status

`MODEL_REVIEW_ONLY / ROOT-TOPOLOGY INTEGRATION CORRECTION / NO PHYSICS OR TOLERANCE CHANGE`

## Failed precursor

The authority-corrected Increment 9L end-to-end attempt used:

```text
source Git SHA:
bdf8e22c20b250b93af4e9284d488c62e5c8ebfd

workflow run:
31688222498

job:
94409230331

artifact:
9176846382

artifact SHA256:
bbbf977e35661287f012ae15a0febd3dd6fc81630e968e93aa4546cbe5132ad5
```

It accepted 605 actual `FvmSolver` steps from the locked initial state before stopping while preparing requested step 606.

Accepted branch history was:

```text
CONNECTED_RAREFACTION: 336 steps
NEUTRAL_ENDPOINT: 1 step
WEAK_COMPRESSION: 146 steps
FINITE_COMPRESSION_HUGONIOT: 122 steps
```

The internal model transition was step-independent:

```text
requested step: 484
THREE_BRANCH_WAVE_MODEL
    -> GENERAL_EOS_FINITE_COMPRESSION
trigger: FINITE_COMPRESSION_MODEL_REQUIRED
```

The accepted trajectory through step 605 retained finite conserved values, positive density and internal energy, single-phase liquid, exact `rho*xv = 0`, and all step/cumulative conservation gates.

The stop before step 606 was:

```text
seeded classification:
SEEDED_INTERVAL_EDGE_CONTACT

fixed fallback classification:
UNEXPECTED_B1_FAILURE

message:
B1-unavailable fixed node follows a successful node
```

No public boundary transition occurred, and no failed candidate was used as a root or flux.

## Classification

This is a finite-compression root-topology integration defect, not a physical-state, B1, conservation, positivity, or phase failure.

At the accepted step-605 state the general-EOS Hugoniot curve has one bounded locally admissible B1-success window. The fixed scan can therefore contain:

```text
leading excluded candidates
one admissible B1-success block
trailing excluded candidates
```

Trailing excluded candidates may be either:

```text
B1-unavailable
B1-success but locally inadmissible
```

The old fallback assumed that B1 success must continue monotonically to the scan cap and incorrectly rejected a valid bounded success window.

## Existing authoritative correction

The bounded-window topology was already diagnosed and implemented in:

```text
tools/verification/
u3_b2_a1_finite_compression_bounded_window_full_horizon.py
```

The independent retained diagnostic authority is:

```text
source Git SHA:
4b96bee28a6abeb1080256d965be408ebd565d37

workflow run:
31668258876

job:
94347432910

artifact:
9168751076

artifact name:
u3-b2-a1-finite-compression-increment-9e-admissibility-31668258876

artifact SHA256:
9a5e3c500ba379370827276ce5b098ca51e81e49685b1fab5e4dabbcbf16baaa

outcome:
BOUNDED_B1_SUCCESS_WINDOW_WITH_UNIQUE_ROOT_SUPPORTED
```

GitHub live metadata confirms that this artifact is non-expired and bound to the stated run and source SHA.

## Correction

When the dynamic seeded finite-compression diagnostic returns the existing limited fallback classification:

```text
SEEDED_INTERVAL_EDGE_CONTACT
```

Increment 9L shall invoke the existing bounded-window root function:

```text
u3_b2_a1_finite_compression_bounded_window_full_horizon
._bounded_dynamic_root_run
```

The fallback shall:

1. evaluate the unchanged fixed Hugoniot nodes;
2. classify candidates as admissible success, B1-unavailable, or local-inadmissible success;
3. require exactly one admissible-success block;
4. exclude all leading and trailing nonadmissible candidates from root topology;
5. refine the lower excluded/admissible boundary when required;
6. retain exactly zero or one compatibility sign-change bracket;
7. construct flux only from a selected locally admissible B1-success root passing all existing gates.

The fallback is not authorized for arbitrary seeded failures. `NO_ADMISSIBLE_ISLAND` remains the expected near-zero public closure trigger. Multiple windows, multiple roots, nonmonotone retained topology, phase departure, nonfinite state, positivity loss, and unknown outcomes remain fail-closed.

## Public state-machine invariants

The public state machine remains:

```text
OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED
```

The bounded-window fallback occurs inside `OUTWARD_FLOW / GENERAL_EOS_FINITE_COMPRESSION` and is not a public transition.

No absolute solver step, checkpoint state, or hard-coded transition time may select this fallback. The trigger is the seeded diagnostic classification only.

## No-change boundary

This correction shall not change:

```text
mass, momentum, or energy equations
Hugoniot equations
B1 equations, search, or guards
production B2 adapter
FvmSolver core
locked B2 contract
root tolerance
velocity tolerance
chi cap
fixed scan nodes
seeded scan nodes
boundary-refinement iterations
zero-transfer closure flux
re-entry or reverse-flow policy
```

No excluded candidate may become:

```text
a root endpoint
a selected root
a flux state
an accepted solver-step authority
```

## Required evidence

The corrected Increment 9L artifact shall record:

```text
failed precursor run/job/source/artifact/digest
bounded-window diagnostic run/job/source/artifact/name/digest
fallback event count
first and last fallback requested steps
seeded trigger classification
bounded success-window count
leading excluded count
trailing excluded count
trailing local-inadmissible count
root-topology node count
root-topology monotonicity
root-topology sign-change count
selected-root gate
excluded state used as root or flux = false
absolute step-number trigger = false
```

Increment 9L must still satisfy the original end-to-end horizon, public-state transition, conservation, positivity, liquid-phase, and evidence gates.

## Formal-state boundary

All formal verification, acceptance, validation, approval, design-use, and production-activation fields remain false.
