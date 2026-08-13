# Stage 7 U3 B2 A1 finite-compression Increment 9D dynamic full-horizon review

## Status

`MODEL_REVIEW_ONLY / FULL_NOMINAL_2L_OVER_C0_ATTEMPT / DYNAMIC_ROOT_TOPOLOGY / FIXED_BEFORE_EXECUTION_RESULT`

Increment 9D continues the corrected general-EOS Hugoniot finite-compression path from the authoritative Increment 8D accepted state at solver step 534 and attempts to reach the nominal full acoustic horizon `2L/c0`.

This is the corrected dynamic-topology successor to the earlier pre-correction Increment 9 attempt. It does not reuse the superseded step-524 authority and does not change B1, the locked B2 Contract, the production Adapter, `FvmSolver`, EOS, Hugoniot relation, Lax gate, entropy gate, root tolerance, fixed `chi` nodes, finite-compression `chi` cap, conservation gates, or formal project states.

## Authoritative parent

```text
source Git SHA:
19955eec9802d092de3986a213a0db9fbc62c597

workflow run:
31667111385

job:
94343960303

artifact:
9168340553

artifact name:
u3-b2-a1-finite-compression-increment-8d-dynamic-32-step-31667111385

artifact SHA256:
f7d0821f7b12f14488c42856a8d24bb426bdfa17754be21011ebbd0fc5dbeadf

outcome:
FINITE_COMPRESSION_INCREMENT_8D_DYNAMIC_32_STEP_PASS

accepted state:
solver step 534
solver time 0.0035786412795834176 s
```

The parent evidence records 32 accepted `FINITE_COMPRESSION_HUGONIOT` steps from 503 through 534, zero branch transitions, no stop classification, liquid and outward subsonic outlet state, positive density and internal energy, exact-zero `rho*xv`, root residual within `1.0e-8 kg/s`, and retained mass, momentum and energy closure.

## Fixed target

```text
pipe length:
1.0 m

nominal acoustic target:
2L/c0 = 0.004285834855172021 s

starting time:
0.0035786412795834176 s

remaining nominal time:
0.0007071935755886037 s

starting horizon fraction:
approximately 0.8349928078224519

maximum operational solver step:
700
```

Before the final update, use:

```text
requested_dt = min(CFL candidate dt, target time - current time)
```

The final accepted step must be clipped to the target. The final solver time must reach the target within:

```text
8 * spacing(target time)
```

## Fixed dynamic root classification

Before every requested solver update, evaluate the current accepted outlet state and apply the corrected evolving-state classification:

```text
fixed successful-domain bracket count = 1
  -> solve that bracket directly

fixed bracket count = 0 and a leading B1-unavailable domain exists
  -> refine the B1 unavailable/success front for the fixed 48 iterations
  -> construct the root topology from the final refined success state and
     higher fixed B1-success states
  -> solve exactly one successful-domain bracket

fixed or refined bracket count > 1
  -> fail-closed MULTIPLE_COMPATIBILITY_ROOTS

no successful root through the fixed chi cap
  -> fail-closed scope/cap classification
```

B1-unavailable states remain failed states. They may not serve as compatibility-root endpoints and may not construct an applied flux.

Every selected root must retain:

```text
general-EOS Hugoniot closure
identity-accounted Hugoniot closure
B1 success
Lax 1-shock ordering
entropy bound
negative local compatibility slope
absolute compatibility residual <= 1.0e-8 kg/s
outward velocity
subsonic Mach number
liquid phase
stagnation-pressure margin above back pressure
stagnation-enthalpy round trip
energy/mass consistency
energy-port closure
restriction-reaction ledger closure
```

## Per-step pass gate

Every accepted continuation step must satisfy:

```text
branch = FINITE_COMPRESSION_HUGONIOT
accepted dt > 0
solver step identity exact
selected root gate passed
1.0e-6 < requested chi <= 1.0e-4
one monotone successful-domain root topology
one compatibility sign-change bracket
finite conserved state
positive density and internal energy
no reverse-flow Guard
no reverse velocity
outward outlet velocity
subsonic outlet Mach number
liquid phase
rho*xv exact zero
step and cumulative mass closure
step and cumulative momentum closure
step and cumulative energy closure
failed B1 state not used as a root endpoint
failed B1 state not used to construct flux
```

The accepted branch sequence must contain no transition and no fixed five-point chatter pattern.

## Full-horizon pass gate

A pass requires all of the following:

```text
parent artifact and state verified
at least one additional accepted actual FvmSolver step
all per-step gates pass
no stop classification or stop reason
operational step cap not exceeded
final step clipped to target
final solver time >= target
absolute horizon-time error <= 8 * spacing(target)
horizon fraction >= 1.0
outward subsonic liquid outlet state retained
positive density and internal energy retained
rho*xv exact zero retained
```

## Pass outcome

```text
FINITE_COMPRESSION_INCREMENT_9D_DYNAMIC_FULL_HORIZON_WORKING_SLICE_PASS
```

A pass establishes only that the corrected dynamic root-topology path reached the nominal full `2L/c0` horizon as a MODEL_REVIEW working vertical slice.

It does not approve the finite-compression branch, complete B2 finite-pipe Verification, accept a benchmark, perform Physical Validation, approve design use, or activate production behavior.

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
