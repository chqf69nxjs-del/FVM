# Stage 7 U3 B2 A1 finite-compression Increment 9E bounded B1 success-window diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

Increment 9E diagnoses the fail-closed stop immediately before requested solver step 606 in the first corrected dynamic full-horizon attempt. It does not advance `FvmSolver`, change B1, reinterpret a B1 failure as success, relax a tolerance, enlarge the finite-compression `chi` cap, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, or promote any formal project state.

## Authoritative parent evidence

```text
source Git SHA:
bc4b8102400f1d0741ea85156b71c64a7258c658

workflow run:
31667618448

job:
94345455162

artifact:
9168542012

artifact name:
u3-b2-a1-finite-compression-increment-9d-dynamic-full-horizon-31667618448

artifact SHA256:
3d9fe84b8e9dfcdab73971c39651093bc565230db8ac461e77a26a9a53a16da7

accepted continuation:
solver step 534 -> 605
71 additional accepted steps

solver time after step 605:
0.004054899620692231 s

nominal target:
0.004285834855172021 s

horizon fraction reached:
0.9461166278488066

stop before requested solver step:
606

stop classification:
DiagnosticStop

stop reason:
B1-unavailable fixed node follows a successful node
```

The accepted continuation through step 605 retained the `FINITE_COMPRESSION_HUGONIOT` branch, zero branch transitions, no clear chatter, liquid and outward subsonic outlet state, positive density and internal energy, exact-zero `rho*xv`, root residual within `1.0e-8 kg/s`, `chi` within `1.0e-4`, and retained mass, momentum and energy closure.

## Diagnostic question

The evolving-state classifier currently assumes that B1-unavailable fixed scan nodes form only a leading prefix before the B1-success domain.

At the step-605 accepted state, the requested step-606 fixed scan may instead have the topology:

```text
leading B1-unavailable domain
-> one contiguous B1-success window
-> trailing B1-unavailable domain
```

The trailing unavailable domain may arise when the high-pressure candidate state no longer has a positive B1 kinetic-energy head. Such a state remains a failed B1 state and may not construct a root or flux. Its existence does not by itself invalidate a unique compatibility root located inside the earlier B1-success window.

Increment 9E tests whether the step-606 stop is caused only by the classifier's prefix-only topology assumption, while one unique general-EOS Hugoniot/B1 compatibility root remains wholly inside a contiguous B1-success window.

## Fixed diagnostic method

Load and verify the exact accepted step-605 state from the parent artifact. Do not advance the solver.

Evaluate the unchanged fixed `chi` nodes:

```text
1.0e-6
1.05e-6
1.1e-6
1.25e-6
1.5e-6
2.0e-6
3.0e-6
5.0e-6
1.0e-5
2.0e-5
5.0e-5
1.0e-4
```

Each node must be classified as either:

```text
B1_SUCCESS:
  evaluation succeeds and the candidate is locally admissible

B1_UNAVAILABLE:
  evaluation fails with exactly one retained B1 formal outcome:
  - REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
  - NONPOSITIVE_KINETIC_ENERGY_HEAD
```

Any other outcome is fail-closed.

Require the successful fixed nodes to form exactly one contiguous block. Record the leading unavailable prefix and trailing unavailable suffix separately.

If a leading unavailable prefix exists, refine its last-unavailable / first-success boundary for exactly 48 categorical bisection iterations, retaining unavailable and successful states exactly as returned by B1.

If a trailing unavailable suffix exists, refine the last-success / first-unavailable boundary for exactly 48 categorical bisection iterations. The lower endpoint must remain B1 success and locally admissible; the upper endpoint must remain one of the two exact unavailable B1 outcomes.

For compatibility-root topology use only:

```text
the refined lower first-success state
plus
higher fixed B1-success states in the same contiguous success block
```

Do not use trailing unavailable states or any failed state as a root endpoint. Intermediate boundary-refinement rows remain evidence only.

The successful-domain residual sequence must be monotone nonincreasing and contain exactly one admissible sign-change bracket. Use the unchanged compatibility-root bisection and complete the selected root with all existing Hugoniot, B1, Lax, entropy, direction, phase, energy and reaction-ledger gates.

## Fixed scope

```text
accepted state loaded:
solver step 605

next requested solver step:
606

solver time:
0.004054899620692231 s

compatibility-root absolute tolerance:
1.0e-8 kg/s

Weak Compression upper boundary:
1.0e-6

finite-compression diagnostic chi cap:
1.0e-4

lower boundary refinement iterations:
48

upper boundary refinement iterations:
48
```

No tolerance, scan node, formal B1 outcome, root rule, or scope may be changed after observing the result.

## Required evidence

At minimum, record:

```text
parent artifact and internal SHA256 verification
exact step/time/state identity
outlet static and stagnation state
all 12 fixed scan rows and classifications
leading unavailable count and outcomes
contiguous success-block count and node range
trailing unavailable count and outcomes
all lower-boundary refinement rows
all upper-boundary refinement rows
final lower first-success state
final upper last-success state
successful root-topology rows and residuals
root sign-change count
selected root pressure, chi, residual, slope, velocity, Mach, phase,
B1 outcome, Hugoniot closure, Lax ordering, entropy and ledgers
confirmation that step 606 was not attempted
confirmation that the conserved state remained unchanged
```

## Diagnostic classifications

### `BOUNDED_B1_SUCCESS_WINDOW_WITH_UNIQUE_ROOT_SUPPORTED`

This classification requires:

```text
parent and state verification pass
outlet remains finite, positive, outward, subsonic and liquid
fixed nodes contain exactly one contiguous success block
there is at least one leading unavailable node
there is at least one trailing unavailable node
all unavailable outcomes are in the fixed two-outcome set
both 48-iteration categorical boundary refinements retain their invariants
root topology uses only B1-success states
root topology residuals are monotone nonincreasing
exactly one compatibility sign-change bracket exists
selected root remains within 1.0e-6 < chi <= 1.0e-4
absolute root residual <= 1.0e-8 kg/s
negative root slope
outward, subsonic, liquid root
B1 success
Hugoniot, identity-accounted, Lax and entropy gates pass
energy and reaction ledgers close
state remains unchanged
FvmSolver step 606 is not attempted
```

A passing result means only that the stop is consistent with a prefix-only classifier limitation and that one valid root remains inside a bounded B1-success window. It does not authorize an actual continuation step.

### Fail-closed classifications

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
UNEXPECTED_B1_FAILURE
NO_B1_SUCCESS_WINDOW
MULTIPLE_B1_SUCCESS_WINDOWS
MISSING_LEADING_UNAVAILABLE_DOMAIN
MISSING_TRAILING_UNAVAILABLE_DOMAIN
LOWER_BOUNDARY_REFINEMENT_FAILURE
UPPER_BOUNDARY_REFINEMENT_FAILURE
SUCCESS_DOMAIN_NONMONOTONE
MULTIPLE_COMPATIBILITY_ROOTS
NO_UNIQUE_COMPATIBILITY_ROOT
ROOT_OR_LEDGER_FAILURE
STATE_MUTATION_DETECTED
```

## Formal-state boundary

Regardless of result, retain:

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
