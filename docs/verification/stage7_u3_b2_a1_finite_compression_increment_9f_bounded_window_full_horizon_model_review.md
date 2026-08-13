# Stage 7 U3 B2 A1 finite-compression Increment 9F bounded-window full-horizon review

## Status

`MODEL_REVIEW_ONLY / FULL_NOMINAL_2L_OVER_C0_ATTEMPT / BOUNDED_ADMISSIBLE_SUCCESS_WINDOW / FIXED_BEFORE_EXECUTION_RESULT`

Increment 9F continues the corrected general-EOS Hugoniot finite-compression path from the authoritative accepted step-605 state retained in the failed Increment 9D artifact. It applies the Increment 9E diagnostic classification correction and attempts the remaining nominal horizon to `2L/c0`.

It does not change B1, local candidate admissibility, the locked B2 Contract, the production Adapter, `FvmSolver`, EOS, Hugoniot relation, Lax gate, entropy gate, root tolerance, fixed `chi` nodes, finite-compression `chi` cap, conservation gates, or formal project states.

## Primary state authority

```text
source Git SHA:
bc4b8102400f1d0741ea85156b71c64a7258c658

workflow run:
31667618448

job:
94345455162

artifact:
9168542012

artifact SHA256:
3d9fe84b8e9dfcdab73971c39651093bc565230db8ac461e77a26a9a53a16da7

accepted state:
solver step 605
solver time 0.004054899620692231 s

horizon fraction:
0.9461166278488066
```

The primary artifact records 71 accepted `FINITE_COMPRESSION_HUGONIOT` steps from 535 through 605 before a fail-closed topology-classification stop. The accepted steps retain zero branch transitions, no clear chatter, liquid and outward subsonic outlet state, positive density and internal energy, exact-zero `rho*xv`, root residual within `1.0e-8 kg/s`, `chi` within `1.0e-4`, and mass, momentum and energy closure.

## Diagnostic authority

```text
source Git SHA:
4b96bee28a6abeb1080256d965be408ebd565d37

workflow run:
31668258876

job:
94347432910

artifact:
9168751076

artifact SHA256:
9a5e3c500ba379370827276ce5b098ca51e81e49685b1fab5e4dabbcbf16baaa

outcome:
BOUNDED_B1_SUCCESS_WINDOW_WITH_UNIQUE_ROOT_SUPPORTED
```

The diagnostic loaded the exact step-605 state without mutation and did not attempt step 606. It found:

```text
fixed nodes:
12

leading B1-unavailable nodes:
9

one contiguous B1-success and locally admissible fixed block:
chi = 2.0e-5 and 5.0e-5

trailing B1-unavailable fixed nodes:
1

lower first-success boundary:
approximately chi = 1.22959719108277e-5

upper locally admissible / excluded boundary:
approximately chi = 9.95815508793391e-5

root topology:
3 nodes, monotone nonincreasing residual, one sign-change bracket

selected step-606 candidate root:
chi = 1.2319749072333934e-5
pressure = 4,950,003.7885851655 Pa
residual = 2.823674341220772e-9 kg/s
outward, subsonic, liquid, B1 success, all fixed gates passed
```

The upper excluded side contained both exact B1-unavailable states and B1-success/local-inadmissible states. Neither category is an admissible root state.

## Fixed evolving-state classification

Before every requested actual solver update, evaluate the unchanged fixed `chi` nodes and assign each candidate to exactly one category:

```text
ADMISSIBLE_SUCCESS:
  B1 evaluation succeeds
  local_candidate_admissible = true

EXCLUDED_B1_UNAVAILABLE:
  B1 evaluation fails with exactly:
  - REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
  - NONPOSITIVE_KINETIC_ENERGY_HEAD

EXCLUDED_LOCAL_INADMISSIBLE:
  B1 evaluation succeeds
  local_candidate_admissible = false
```

Excluded states remain unusable as root-topology members, root endpoints and applied flux states.

Require the admissible-success fixed nodes to form exactly one contiguous window. Multiple admissible windows are fail-closed.

### Root construction

```text
if the fixed admissible-success window contains exactly one root bracket:
  solve it directly

if no fixed bracket exists and a leading excluded domain exists:
  refine the last-excluded / first-admissible boundary for exactly 48 iterations
  use the final refined admissible state plus higher fixed admissible states
  require one monotone root topology and exactly one root bracket

if the refined first-admissible residual is negative beyond tolerance:
  stop ROOT_LIES_INSIDE_EXCLUDED_DOMAIN

if the final admissible residual remains positive through the window/cap:
  stop FINITE_COMPRESSION_DIAGNOSTIC_CAP_REQUIRED
```

A trailing excluded suffix is retained as evidence but is never inserted into root topology. No upper-boundary bisection is required for an actual step because the root is constructed entirely from the earlier admissible-success states.

Every selected root must retain all unchanged Hugoniot, identity-accounted, B1, Lax, entropy, direction, phase, stagnation-pressure, energy and reaction-ledger gates.

## Fixed target

```text
starting solver step:
605

starting solver time:
0.004054899620692231 s

nominal target:
0.004285834855172021 s

remaining nominal time:
0.00023093523447979044 s

starting horizon fraction:
0.9461166278488066

maximum operational solver step:
700
```

The final requested update uses:

```text
requested_dt = min(CFL candidate dt, target time - current time)
```

and must be clipped to the target within `8 * spacing(target time)`.

## Per-step pass gate

Every accepted step must satisfy:

```text
branch = FINITE_COMPRESSION_HUGONIOT
one contiguous admissible-success window
one monotone compatibility-root topology
one compatibility sign-change bracket
selected root passes all unchanged gates
1.0e-6 < chi <= 1.0e-4
absolute root residual <= 1.0e-8 kg/s
accepted dt > 0
finite conserved state
positive density and internal energy
outward subsonic liquid outlet
rho*xv exact zero
step and cumulative mass, momentum and energy closure
no excluded state used as root endpoint or applied flux
```

The accepted branch sequence must have zero transitions and no fixed chatter pattern.

## Full-horizon pass gate

A pass requires:

```text
both authorities verified
at least one accepted actual step
all per-step gates pass
no stop classification or reason
final step clipped to target
final time reaches target within roundoff allowance
horizon fraction >= 1.0
final state remains outward, subsonic, liquid and positive
rho*xv remains exact zero
```

## Pass outcome

```text
FINITE_COMPRESSION_INCREMENT_9F_BOUNDED_WINDOW_FULL_HORIZON_WORKING_SLICE_PASS
```

A pass establishes only a corrected MODEL_REVIEW working vertical slice to nominal `2L/c0`.

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
