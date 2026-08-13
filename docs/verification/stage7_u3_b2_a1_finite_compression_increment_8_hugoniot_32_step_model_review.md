# Stage 7 U3 B2 A1 finite-compression Increment 8 Hugoniot 32-step MODEL_REVIEW

## Status

`MODEL_REVIEW_ONLY / THIRTY_TWO_ACTUAL_FVM_STEPS / FIXED_BEFORE_EXECUTION_RESULT`

This increment extends the successful general-EOS Hugoniot finite-compression working slice for exactly 32 additional accepted actual `FvmSolver` steps.

It starts from the authoritative Increment 7 accepted step-492 state and requests steps 493 through 524. A new general-EOS Hugoniot and unchanged B1-compatible root are solved from the evolving outlet state at every step.

This increment does not approve the finite-compression branch, authorize more than 32 accepted steps, enlarge the fixed `chi=1.0e-4` diagnostic cap, relax any tolerance, change B1, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, promote any formal state, accept the B2 benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative Increment 7 parent

```text
source Git SHA:
559f34e9e578b8335295dc2ee16f975b9fdad586

workflow run:
31653551138

job:
94302870493

artifact:
9163478011

artifact name:
u3-b2-a1-finite-compression-increment-7-31653551138

GitHub artifact SHA256:
f208ac3a5125c7cd5265af6e0b19ef7705eee85614d282a639a3263223734de1

outcome:
FINITE_COMPRESSION_INCREMENT_7_HUGONIOT_8_STEP_PASS
```

Increment 7 accepted steps 485 through 492 with no halving, no branch transition, no clear chatter, liquid outward subsonic flow, exact-zero `rho*xv`, and all root, Hugoniot, B1, Lax, entropy, energy, reaction and inventory gates passing.

The final accepted state was:

```text
solver step:
492

solver time:
0.003296941966003099 s

outlet pressure:
4949761.868058326 Pa

outlet velocity:
+0.11869397089115863 m/s

outlet Mach:
0.00025481039814647023

outlet phase:
liquid
```

The final selected root had:

```text
requested chi:
1.3760337829589844e-6

pressure offset:
261.08453609235585 Pa
```

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

starting accepted solver step:
492

requested accepted steps:
32

final accepted solver step on pass:
524

starting solver time:
0.003296941966003099 s

finite-compression model:
general-EOS liquid compression Hugoniot

approved Weak Compression limit:
chi = 1.0e-6

finite-compression diagnostic cap:
chi = 1.0e-4

compatibility-root absolute tolerance:
1.0e-8 kg/s

Hugoniot density bisection iterations:
64

compatibility-root bisection maximum:
48
```

No target-horizon clipping is used. Every accepted time step is obtained from the existing CFL, boundary removal-limit and deterministic trial-validation path.

## Per-step model and gates

At every requested step, retain exactly the Increment 7 construction:

```text
fixed requested-chi scan nodes from 1.0e-6 through 1.0e-4
general-EOS liquid compression Hugoniot density solve
both Hugoniot energy forms within 1.0e-6 J/kg
identity-accounted equivalence within 1.0e-10 J/kg
unchanged B1 evaluation at every candidate
successful-domain residual monotone nonincreasing
exactly one successful locally admissible sign-change bracket
requested-chi compatibility bisection
```

The selected root must retain:

```text
1.0e-6 < requested chi <= 1.0e-4
p_P > p_i
rho_P > rho_i
absolute compatibility residual <= 1.0e-8 kg/s
negative local residual slope
outward velocity
0 <= Mach < 1
liquid phase
B1 success
stagnation pressure > back pressure
Hugoniot closure and identity-accounted equivalence
Lax 1-shock ordering
entropy delta >= -1.0e-7 J/(kg K)
stagnation-enthalpy round trip
energy/mass consistency
energy-port closure
restriction-reaction ledger closure
```

After every actual update retain:

```text
accepted dt > 0
finite conserved state
positive density and internal energy
outward subsonic liquid outlet
rho*xv exact zero
no reverse-flow Guard
step mass, momentum and energy closure
cumulative mass, momentum and energy closure
```

## Sequence gates

Across all 32 accepted steps require:

```text
branch = FINITE_COMPRESSION_HUGONIOT for every accepted step
branch transition count = 0
no clear five-point branch chatter
all 32 root and post-step gates pass
final solver step = 524
```

Root `chi`, pressure offset, shock speed, entropy, stagnation-pressure margin and accepted `dt` trends are retained as observations. No monotonic trend is required except the per-step fixed-scan residual topology.

## Required evidence

At minimum write:

```text
Increment 7 GitHub metadata and digest verification
Increment 7 internal SHA256 verification
exact step-492 state and solver identity
32 accepted-step rows
32 selected-root rows
all fixed Hugoniot scan rows
all Hugoniot density-search rows
branch sequence
root chi, pressure-offset, shock-speed, entropy and margin sequences
accepted-dt and halving sequences
outlet state sequence
step and cumulative inventory residuals
starting and final conserved states
confirmation that only steps 493 through 524 were requested
```

## Pass outcome

The sole pass token is:

```text
FINITE_COMPRESSION_INCREMENT_8_HUGONIOT_32_STEP_PASS
```

A pass establishes only that 32 additional verification-only finite-compression Hugoniot updates can be accepted after Increment 7.

It does not authorize solver step 525 or a longer continuation.

## Immediate stop conditions

The fail-closed conditions remain those of Increment 7, including:

```text
parent or state mismatch
Hugoniot density root absent or multiple
phase departure
fixed scan nonmonotonicity
no unique B1-compatible root
root chi outside (1.0e-6, 1.0e-4]
Hugoniot, identity, Lax or entropy failure
B1, direction, phase, root, energy or reaction-ledger failure
nonfinite or nonpositive trial state
reverse outlet velocity
rho*xv failure
inventory closure failure
clear branch chatter
accepted-step count other than 32
final solver step other than 524
```

No tolerance or cap may be changed to obtain passage.

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
