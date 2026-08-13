# Stage 7 U3 B2 A1 finite-compression Increment 9 full-horizon MODEL_REVIEW

## Status

`MODEL_REVIEW_ONLY / FULL_NOMINAL_2L_OVER_C0_ATTEMPT / FIXED_BEFORE_EXECUTION_RESULT`

This increment continues the authoritative general-EOS Hugoniot finite-compression working slice from accepted solver step 524 to the fixed nominal B2-10A acoustic horizon:

```text
2L/c0 = 0.004285834855172021 s
```

A new general-EOS Hugoniot and unchanged B1-compatible root are recomputed from the evolving outlet state before every requested step. The last accepted step is clipped exactly to the remaining horizon time.

This increment does not approve the finite-compression branch, enlarge the fixed `chi=1.0e-4` diagnostic cap, relax a tolerance, change B1, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, promote a formal state, accept the B2 benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative Increment 8 parent

```text
source Git SHA:
55d414ac82b63ae93ce2866148af363dc76fa2cb

workflow run:
31654235903

job:
94304991819

artifact:
9163799106

artifact name:
u3-b2-a1-finite-compression-increment-8-31654235903

GitHub artifact SHA256:
45d726b422090c8ce00becb7d66a7a44b309678c0a7cb61b4f842dd08086be8b

outcome:
FINITE_COMPRESSION_INCREMENT_8_HUGONIOT_32_STEP_PASS
```

The parent accepted:

```text
solver step:
492 -> 524

solver time after step 524:
0.003511644475195471 s

branch:
FINITE_COMPRESSION_HUGONIOT for all 32 steps

final selected chi:
2.7214050292968744e-6

final root pressure offset:
516.2656671926379 Pa

final root stagnation-pressure margin above back:
34.81309639289975 Pa
```

The parent retained no halving, no branch transition, no clear chatter, liquid outward subsonic flow, exact-zero `rho*xv`, and all root, Hugoniot, B1, Lax, entropy, energy, reaction and inventory gates.

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

starting accepted solver step:
524

starting solver time:
0.003511644475195471 s

fixed nominal target time:
0.004285834855172021 s

remaining horizon at start:
0.0007741903799765502 s

maximum operational solver step:
1000

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

horizon roundoff tolerance:
6.938893903907228e-18 s
```

## Per-step construction and gates

Every nonfinal step uses the solver-computed CFL and boundary-limited time step. For the final step only:

```text
accepted dt = min(candidate dt, target time - current solver time)
```

The existing deterministic trial validation is applied to the clipped value.

At every requested step retain exactly the authoritative Increment 8 construction:

```text
fixed requested-chi scan from 1.0e-6 through 1.0e-4
general-EOS liquid compression Hugoniot density solve
both Hugoniot energy closures
identity-accounted Hugoniot equivalence
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

## Full-horizon pass gate

A pass requires:

```text
no fail-closed stop before the target
solver time reaches or exceeds the target
absolute target-time error <= 6.938893903907228e-18 s
final accepted step is clipped to the target
all accepted branches are FINITE_COMPRESSION_HUGONIOT
branch transition count = 0
no clear five-point branch chatter
all selected roots remain inside the fixed diagnostic cap
all accepted-step gates pass
operational solver-step cap is not exceeded
```

The final solver step and the number of additional accepted steps are results, not pre-assumed values.

## Required evidence

At minimum write:

```text
Increment 8 GitHub metadata and digest verification
Increment 8 internal SHA256 verification
exact step-524 state and solver identity
one accepted-step row for every additional step
one selected-root row for every additional step
all fixed Hugoniot scan rows
all Hugoniot density-search rows
branch sequence
root chi, pressure offset, shock speed, entropy and pressure-margin sequences
accepted-dt and halving sequences
outlet-state sequence
step and cumulative inventory residuals
starting and final conserved states
target time, final time, time error and roundoff tolerance
confirmation of final target-time clipping
```

## Pass outcome

The sole pass token is:

```text
FINITE_COMPRESSION_INCREMENT_9_FULL_HORIZON_WORKING_SLICE_PASS
```

A pass means only that the B2-10A MODEL_REVIEW working slice reached the fixed nominal `2L/c0` horizon under the general-EOS Hugoniot finite-compression boundary treatment and all retained minimum gates.

It does not mean the branch is formally Verified, Accepted, Validated, or approved for design or production.

## Immediate stop conditions

The fail-closed conditions remain those of Increment 8, including:

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
operational solver-step cap exceeded
```

No tolerance or cap may be changed to obtain passage.

## Formal-state boundary

Even if the nominal horizon is reached, retain:

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

A separate field may record:

```text
working_vertical_slice_two_l_over_c0_reached = true
```

without promoting any formal state.
