# Stage 7 U3 B2 A1 finite-compression Increment 8D dynamic 32-step checkpoint

## Status

`MODEL_REVIEW_ONLY / THIRTY_TWO_ACTUAL_FVM_STEPS / DYNAMIC_ROOT_TOPOLOGY / FIXED_BEFORE_EXECUTION_RESULT`

Increment 8D continues the corrected general-EOS Hugoniot finite-compression path from the authoritative Increment 8C accepted state at solver step 502. It requests exactly 32 additional accepted actual `FvmSolver` updates through solver step 534.

This increment does not change the B1 component, locked B2 Contract, production Adapter, `FvmSolver`, EOS, Hugoniot relation, Lax gate, entropy gate, root tolerance, fixed `chi` nodes, finite-compression `chi` cap, conservation gates, or formal project states.

## Authoritative parent

```text
source Git SHA:
c3368b99c7429490feba0b86d1605138f80e29d5

workflow run:
31663509236

job:
94333135976

artifact:
9167066290

artifact name:
u3-b2-a1-finite-compression-increment-8c-dynamic-31663509236

artifact SHA256:
faa90e1c4968e9cbed1b615726d6080c90ec100b9bf6f6ebb78069e32ba43611

outcome:
FINITE_COMPRESSION_INCREMENT_8C_GUARD_FRONT_8_STEP_PASS

accepted state:
solver step 502
solver time 0.0033640121156822815 s
```

The parent evidence records eight accepted `FINITE_COMPRESSION_HUGONIOT` steps from 494 through 502, zero branch transitions, no stop classification, liquid and outward subsonic outlet state, positive density and internal energy, exact-zero `rho*xv`, root residual within `1.0e-8 kg/s`, and retained mass, momentum and energy closure.

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

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

starting solver step:
502

starting solver time:
0.0033640121156822815 s

requested accepted steps:
32

required final solver step:
534

Weak Compression upper boundary:
1.0e-6

finite-compression diagnostic chi cap:
1.0e-4

compatibility-root absolute tolerance:
1.0e-8 kg/s
```

No target-time clipping is applied in this checkpoint. A later full-horizon increment remains separately gated.

## Per-step pass gate

Each accepted step from 503 through 534 must satisfy:

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

## Checkpoint comparison record

Because this run crosses solver step 524, the accepted step-524 state and root are copied into a dedicated `step524_checkpoint.json` record. This record supports a later comparison with the earlier pre-correction step-524 route.

The old/new step-524 numerical comparison is diagnostic and is not used to relax or replace any Increment 8D pass gate. A separate review will judge the size and continuity of the difference.

## Pass outcome

```text
FINITE_COMPRESSION_INCREMENT_8D_DYNAMIC_32_STEP_PASS
```

A pass establishes only that the corrected dynamic root-topology implementation advanced the actual `FvmSolver` from step 502 through step 534 under the fixed minimum gates.

It does not authorize step 535, approve the finite-compression branch, complete B2 finite-pipe Verification, accept a benchmark, perform Physical Validation, approve design use, or activate production behavior.

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
