# Stage 7 U3 B2 A1 finite-compression Increment 7 Hugoniot 8-step MODEL_REVIEW

## Status

`MODEL_REVIEW_ONLY / EIGHT_ACTUAL_FVM_STEPS / FIXED_BEFORE_EXECUTION_RESULT`

This increment continues the general-EOS Hugoniot boundary model for exactly eight accepted actual `FvmSolver` steps after the successful Increment 6 one-step review.

The execution starts from authoritative accepted solver step 484 and requests accepted steps 485 through 492. At every candidate step the outlet-cell state is reconstructed, a new general-EOS Hugoniot locus is solved, the B1-compatible root is recomputed, all physical and numerical gates are reevaluated, and only the accepted root may construct the pipe-side Euler flux.

This increment does not approve a general finite-compression branch, authorize more than eight accepted steps, enlarge the fixed diagnostic `chi` cap, relax any tolerance, change B1, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, promote any formal state, accept the B2 benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative Increment 6 parent

```text
source Git SHA:
821bac91c6c9b9bdd991ab54a845ec3a311c4b48

workflow run:
31652814648

job:
94300642258

artifact:
9163222601

artifact name:
u3-b2-a1-finite-compression-increment-6-rerun-31652814648

GitHub artifact SHA256:
db671e3b9c7f8f7b52b88d3f0d44a279496546cd2777a683538451f2efe71fe7

outcome:
FINITE_COMPRESSION_INCREMENT_6_HUGONIOT_ONE_STEP_PASS
```

Increment 6 accepted:

```text
solver step:
483 -> 484

accepted dt:
6.706958065882384e-6 s

solver time after:
0.0032432861683330846 s

halving count:
0
```

Its selected Hugoniot root independently reproduced the Increment 5 authority and retained B1 success, general-EOS Hugoniot closure, identity-accounted equivalence, Lax 1-shock ordering, entropy bound, direction, phase, energy and reaction ledgers. The actual step retained positivity, conservation, liquid phase, outward subsonic flow, and exact-zero `rho*xv`.

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

starting accepted solver step:
484

requested accepted steps:
8

final accepted solver step on pass:
492

starting solver time:
0.0032432861683330846 s

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

No horizon-time clipping is used. Each accepted time step is the solver-computed CFL step after the existing boundary mass- and energy-removal limits and deterministic trial validation.

## Per-step Hugoniot construction

For each evolving outlet state, define:

```text
chi = (p_P - p_i) / (rho_i c_i^2)
```

Evaluate the fixed diagnostic nodes:

```text
1.0e-6
1.05e-6
1.10e-6
1.25e-6
1.50e-6
2.0e-6
3.0e-6
5.0e-6
1.0e-5
2.0e-5
5.0e-5
1.0e-4
```

At each pressure, solve the same general-EOS liquid compression Hugoniot density state used by authoritative Increment 5:

```text
e_P - e_i + 0.5 (p_P + p_i) (v_P - v_i) = 0
```

with the authoritative enthalpy-identity treatment:

```text
abs(H_e) <= 1.0e-6 J/kg
abs(H_h) <= 1.0e-6 J/kg
identity-accounted difference <= 1.0e-10 J/kg
```

The raw `H_e-H_h` difference is recorded but is not a standalone stricter gate.

For each successful compression state:

```text
j = sqrt((p_P - p_i)/(v_i - v_P))
u_P = u_i - j(v_i - v_P)
S = u_i - j v_i
```

The fixed Lax ordering remains:

```text
u_P - c_P < S < u_i - c_i
```

Each candidate is passed through the unchanged B1 Adapter. Failed states remain failed and may not form a root bracket or construct a flux.

## Per-step root topology

For every requested step require:

```text
fixed Hugoniot scan residuals monotone nonincreasing
exactly one successful locally admissible sign-change bracket
```

Use requested `chi` as the bisection coordinate. Every bisection midpoint must independently reconstruct a Hugoniot state and pass B1/local admissibility.

The selected root must satisfy:

```text
requested chi > 1.0e-6
requested chi <= 1.0e-4
p_P > p_i
rho_P > rho_i
absolute compatibility residual <= 1.0e-8 kg/s
negative local compatibility-residual slope
outward velocity
0 <= Mach < 1
liquid phase
B1 success
stagnation pressure > retained back pressure
both Hugoniot energy forms close
identity-accounted equivalence passes
Lax 1-shock ordering passes
entropy delta >= -1.0e-7 J/(kg K)
stagnation-enthalpy round trip passes
energy/mass consistency passes
energy-port closure passes
restriction-reaction ledger closes
```

The pipe-side Euler flux is unchanged from Increment 6:

```text
F_mass = mdot_P/A
F_momentum = (mdot_P u_P + p_P A)/A
F_energy = mdot_P h0,P/A
F_rho_xv = 0
```

## Per-step post-update gates

After every accepted step require:

```text
accepted dt > 0
solver step count increases by one
solver time increases by accepted dt
all conserved values finite
minimum density > 0
minimum internal energy > 0
outlet velocity remains outward
outlet Mach remains subsonic
outlet phase remains liquid
rho*xv remains exact zero
no reverse-flow Guard
step mass closure passes
step momentum closure passes
step energy closure passes
cumulative mass closure passes
cumulative momentum closure passes
cumulative energy closure passes
```

The existing deterministic-halving maximum remains unchanged. Any accepted halving must be recorded; all final gates must still pass.

## Sequence gates

Across the eight accepted steps require:

```text
branch classification = FINITE_COMPRESSION_HUGONIOT for all steps
no branch transition
no clear five-point branch chatter
root requested chi remains inside (1.0e-6, 1.0e-4]
root pressure, density and velocity remain finite
all selected roots are unique and admissible
all eight step rows pass
```

The root `chi`, pressure offset, shock speed, entropy delta and accepted dt trends are observation-only. No monotonic trend is required beyond the per-step scan residual topology.

## Required evidence

At minimum write:

```text
Increment 6 parent GitHub metadata and digest verification
Increment 6 internal SHA256 verification
exact step-484 state and solver identity
one row per accepted solver step
one selected-root row per accepted solver step
all fixed Hugoniot scan rows per requested step
all Hugoniot density-search rows per requested step
branch sequence
root-chi and pressure-offset sequence
shock-speed and Lax-eigenvalue sequence
entropy sequence
accepted-dt and halving sequence
outlet pressure, velocity, Mach and phase sequence
step and cumulative inventory residuals
starting and final conserved states
confirmation that only steps 485 through 492 were requested
```

## Pass outcome

The sole pass token is:

```text
FINITE_COMPRESSION_INCREMENT_7_HUGONIOT_8_STEP_PASS
```

A pass establishes only that eight verification-only finite-compression Hugoniot updates can be accepted after the authoritative one-step result.

It does not authorize solver step 493 or a longer continuation.

## Immediate stop conditions

```text
Increment 6 parent mismatch
starting-state or solver-identity mismatch
nonfinite or nonpositive interior state
Hugoniot density root absent or multiple
phase-scope departure
fixed scan nonmonotonicity
no unique B1-compatible root
multiple compatibility roots
root chi <= 1.0e-6
root chi > 1.0e-4
Hugoniot closure or identity failure
Lax ordering failure
entropy decrease below fixed bound
B1, direction, phase, root, energy or reaction-ledger failure
nonfinite trial state
nonpositive density or internal energy
reverse outlet velocity
rho*xv identity failure
inventory closure failure
clear branch chatter
accepted-step count other than eight
final solver step other than 492
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
