# Stage 7 U3 B2 A1 Increment 9L bounded-window inspection schema correction

## Status

`MODEL_REVIEW_ONLY / EVIDENCE-INSPECTION CORRECTION / NO FVM RERUN / NO PHYSICS CHANGE`

## Successful runner and failed inspection

The Increment 9L bounded-window end-to-end workflow used:

```text
source Git SHA:
bdbbf88b240ff1b839d8a72fa898437efac1e7b8

workflow run:
31690390529

job:
94416115006
```

The actual runner step:

```text
Run bounded-window Increment 9L from initial state
```

completed successfully. The following inspection step failed:

```text
Inspect bounded-window Increment 9L evidence
```

The immutable artifact was nevertheless uploaded successfully:

```text
artifact ID:
9177683047

artifact name:
u3-b2-a1-increment-9l-v5-31690390529

artifact SHA256:
0ff366738c855c83d9355c3e18b2cb54f640354a34b96211d85dd205269f6b32
```

## Incorrect inspection assumption

The failed inspection contained the fixed assertion:

```text
first_fallback_requested_step == 606
```

That assertion conflated two different events:

```text
step 484:
first use of the authorized bounded-window finite-compression fallback

step 606:
first bounded-window scan containing a trailing excluded candidate
```

The v5 model authorizes the bounded-window algorithm whenever the seeded diagnostic returns:

```text
SEEDED_INTERVAL_EDGE_CONTACT
```

This classification already occurs at the first general-EOS finite-compression step, requested step 484. Therefore the fallback correctly begins at step 484 rather than step 606.

Before step 606 the same bounded-window algorithm reduces to a single admissible-success window without a trailing excluded region. At step 606 the topology evolves to the previously diagnosed form:

```text
leading excluded candidates
one admissible B1-success window
trailing excluded candidate(s)
```

No physics or algorithm discrepancy is present.

## Immutable artifact findings

The v5 artifact records:

```text
accepted FvmSolver steps:
640

initial state:
locked LIQUID_SMALL_DROP state at t = 0

final time:
0.004285834855172021 s

nominal 2L/c0 reached:
true

horizon error:
0.0 s
```

Public boundary-state sequence:

```text
OUTWARD_FLOW:
637 accepted steps

ZERO_TRANSFER_CLOSED:
3 accepted steps

public transition:
requested step 638
trigger = NO_ADMISSIBLE_ISLAND
```

Internal model sequence:

```text
CONNECTED_RAREFACTION:
steps 1-336

CONNECTED_RAREFACTION -> GENERAL_THREE_BRANCH_CLASSIFICATION:
requested step 337
trigger = CONNECTED_ROOT_SIGN_CHANGES_ZERO

GENERAL three-branch weak/neutral region:
through requested step 483

THREE_BRANCH_WAVE_MODEL -> GENERAL_EOS_FINITE_COMPRESSION:
requested step 484
trigger = FINITE_COMPRESSION_MODEL_REQUIRED

bounded-window finite-compression fallback:
requested steps 484-634
151 events

seeded finite-compression continuation:
requested steps 635-637

OUTWARD_FLOW -> ZERO_TRANSFER_CLOSED:
requested step 638
trigger = NO_ADMISSIBLE_ISLAND

closed hold:
requested steps 638-640
```

Bounded-window evidence:

```text
first fallback step:
484

last fallback step:
634

fallback event count:
151

first leading excluded candidate:
step 489

first Guard-front refinement:
step 494

first trailing excluded candidate:
step 606

bounded success-window count:
1 for every fallback event

root-topology monotone nonincreasing:
true for every fallback event

root-topology sign-change count:
1 for every fallback event

selected-root gate:
PASS for every fallback event

excluded candidate used as root endpoint:
false

excluded candidate used to construct flux:
false
```

## Corrected inspection rules

The corrected immutable-evidence inspection shall require:

```text
first fallback requested step
= outward finite-compression model-transition requested step
= 484

fallback requested steps
= contiguous integer sequence 484 through 634

first trailing excluded requested step
= 606

first seeded finite-compression step after fallback
= 635

last outward-flow step
= 637

public closure transition step
= 638

final accepted step
= 640
```

The inspection shall also verify:

```text
artifact internal manifest and every file SHA256
source/run/job/artifact/name/digest authority
one FvmSolver instance from initial state
no checkpoint artifact
no absolute-step transition condition
all 640 per-step engineering gates PASS
all step and cumulative conservation gates PASS
finite and positive state
all cells liquid
rho*xv exact zero
closed-state mass / energy / vapor flux exact zero
closed-state wall momentum identity exact
no public re-entry
no public-state chatter
formal project states remain false
```

## Correction method

The existing v5 artifact is immutable and shall not be modified.

A new inspection-only workflow may:

1. verify the failed workflow, job, source SHA, artifact ID, artifact name, and artifact digest;
2. download the exact v5 artifact;
3. verify its internal manifest and contents;
4. apply the corrected inspection semantics above;
5. create a separate immutable inspection-correction artifact.

It may not rerun the FVM trajectory, recompute a root, mutate a state, alter an evidence file, or change any project gate.

## No-change boundary

This correction changes none of the following:

```text
physical equations
state-machine implementation
transition trigger
bounded-window algorithm
Hugoniot equations
B1 behavior
production adapter
FvmSolver core
locked B2 contract
tolerances
chi cap
scan counts
accepted trajectory
```

## Formal-state boundary

A passing inspection-correction workflow confirms only that the already successful provisional engineering runner was recorded and interpreted correctly.

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
