# Stage 7 U3 B2 A1 Increment 9K provisional zero-transfer closure closeout

## Status

`PROVISIONAL ENGINEERING WORKING SLICE / EXECUTED / NOT VERIFIED / NOT ACCEPTED`

Increment 9K implements the project decision to stop treating the unresolved near-zero-flow transition as a blocker for the first working tool. The unresolved transition remains a technical issue; a conservative one-way zero-transfer closure is supplied as an explicit engineering physics model.

This closeout does not modify the locked B2 contract, B1, the production B2 adapter, or the FVM solver core.

## Source and authoritative parent

```text
Increment 9K source Git SHA:
0ec2938c02de812535269a3f28b51b065f943303

workflow run:
31680200411

job:
94383678744

parent Increment 9I run:
31670285271

parent job:
94353300958

parent artifact:
9169437776

parent source SHA:
c89a992d69c2985fc081fe3750c5b27136d3941e

parent artifact SHA256:
ed48b82be9f6cc8d6e081a416ab2b61bd97401782279506d83c8afd4d173f5d3

parent step-637 state SHA256:
7d2633e58adcc36e7ea7a1204af95455f5e8942e2c4e9a6dbf76cf437efd2a25
```

The workflow re-read and verified the authoritative Increment 9I artifact before executing any new FVM step.

## Increment 9J boundary evidence retained

The prior fixed diagnostic remains authoritative for the old outward-flow branch:

```text
classification:
ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE

technical issue:
TECHNICAL_ISSUE_A1_NEAR_ZERO_FLOW_BRANCH_TRANSITION
```

Increment 9K does not reinterpret this result as a proven zero-flow compatibility root. It intentionally supplies a separate engineering closure model.

## Engineering physics model used

The provisional branch is:

```text
ZERO_TRANSFER_CLOSED
```

The right-face conservative flux is evaluated from the current adjacent interior static pressure `p_i`:

```text
F_rho     = 0
F_rho_u   = p_i
F_rho_E   = 0
F_rho_xv  = 0
```

Interpretation: a one-way/non-return discharge path closes when the retained outward branch is exhausted. After closure, no reverse mass transfer is constructed. External pressure is carried mechanically by the closure device while the modeled fluid sees the wall pressure traction.

Re-entry, reverse transfer, transition hysteresis, and physical validation remain future technical work.

## Actual FvmSolver execution

The authoritative step-637 state was loaded exactly and the unchanged `FvmSolver` executed three additional accepted steps:

```text
start step: 637
start time: 0.004269583083221582 s

accepted step 638: ZERO_TRANSFER_CLOSED
accepted step 639: ZERO_TRANSFER_CLOSED
accepted step 640: ZERO_TRANSFER_CLOSED

final step: 640
final time: 0.004285834855172021 s
nominal 2L/c0 target: 0.004285834855172021 s
horizon time error: 0.0 s
final step target-clipped: true
maximum deterministic halvings: 0
```

This is an actual solver continuation, not time extrapolation.

## Boundary identities

For all three accepted closure steps:

```text
right mass transfer exact zero: PASS
right energy transfer exact zero: PASS
right vapor transfer exact zero: PASS
right momentum flux = interior static pressure: PASS EXACT
reverse mass transfer constructed: false
B1 called after closure: false
Hugoniot root called after closure: false
```

No reverse outlet velocity occurred during this short continuation.

## Conservation and state gates

Maximum absolute residuals over the three-step engineering continuation were:

```text
step mass residual:
1.3877787807814457e-17 kg

step momentum residual:
1.3552527156068805e-20 kg m/s

step energy residual:
3.637978807091713e-12 J

segment cumulative mass residual:
1.3877787807814457e-17 kg

segment cumulative momentum residual:
1.3552527156068805e-20 kg m/s

segment cumulative energy residual:
3.637978807091713e-12 J
```

Final state checks:

```text
all conserved values finite: PASS
minimum density: 874.2084603532102 kg/m3
minimum internal energy: 216871.95943393288 J/kg
all cells normalized liquid: PASS
rho*xv exact zero: PASS
```

Final outlet state:

```text
pressure: 4947313.078743964 Pa
velocity: 0.004733450937742386 m/s
Mach: 1.0162598397134617e-05
phase: liquid
```

Final state SHA256:

```text
a5931cb69e90f481ea59cf026c2fdbe19426f7c2794be4fdc68f29f79d4e0338
```

## Immutable evidence artifact

```text
artifact ID:
9173152297

artifact name:
u3-b2-a1-increment-9k-zero-transfer-31680200411

artifact SHA256:
bf1c85e4928820ff71fe7cd3ce16d4ee1c5f4693f65eb72ace2f3e6d62accd39

files:
authority_verification.json
branch_sequence.csv
report.md
summary.json
technical_issue.json
zero_transfer_full_horizon_states.npz
zero_transfer_steps.csv
artifact_sha256.txt
```

The internal manifest records SHA256 for every evidence file.

## Project interpretation

Increment 9K establishes:

```text
engineering physics model defined: YES
verification-side implementation: IMPLEMENTED
actual FvmSolver execution: PASS
provisional engineering 2L/c0 horizon reached: YES
working vertical slice: YES
```

It does **not** establish that the new branch transition is physically unique or validated. Therefore the result shall be described as:

```text
PROVISIONAL ENGINEERING WORKING SLICE
```

and not as `VERIFIED`, `ACCEPTED`, `VALIDATED`, or `APPROVED`.

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

The separate field `provisional_engineering_two_l_over_c0_reached = true` records only that the working engineering model actually executed to the nominal horizon.

## Next development priority

The next tool-focused increment should generalize the successful hard transition into a small explicit boundary state machine while preserving fail-safe behavior:

```text
OUTWARD_FLOW
    -> ZERO_TRANSFER_CLOSED
```

The first generalization should cover only transition detection and closed-state hold. Re-opening and reverse flow should remain separate future increments so that the working tool is not destabilized by unnecessary model breadth.
