# Stage 7 U3 B2 A1 finite-compression Increment 6 Hugoniot one-step MODEL_REVIEW

## Status

`MODEL_REVIEW_ONLY / ONE_ACTUAL_FVM_STEP / FIXED_BEFORE_EXECUTION_RESULT`

This increment applies the authoritative Increment 5 general-EOS Hugoniot boundary root to exactly one actual `FvmSolver` update from accepted solver step 483 to requested solver step 484.

It does not approve a general finite-compression branch, authorize a multi-step continuation, enlarge the diagnostic `chi` cap, relax any tolerance, change B1, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, promote any formal state, accept the B2 benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative accepted-state parent

```text
source Git SHA:
2c1e1e26138b7d3bd3cf0e7f1d2f7a2c11b443c1

workflow run:
31650819553

job:
94294552017

artifact:
9162559698

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4f-root-topology-31650819553

GitHub artifact SHA256:
6f611e1935d2680a04046d1fc7fbb595f19bc99d12ccc274700fd92c086ddb93

accepted solver step:
483

accepted solver time:
0.0032365792102672024 s
```

The accepted state is finite, positive, outward, subsonic, liquid, conservative, and exact-zero in `rho*xv`.

## Authoritative Increment 5 model-selection evidence

```text
source Git SHA:
c4a0f92e4b418c2cc91c53639bff50b8d3af69b5

workflow run:
31652171734

job:
94298712101

artifact:
9162985187

artifact name:
u3-b2-a1-finite-compression-increment-5-rerun-2-31652171734

GitHub artifact SHA256:
80051eedde6b5a9ea92938d9700ad5fa03eaa5ff3cd54dae3964bb12c1fb1781

outcome:
FINITE_COMPRESSION_HUGONIOT_ROOT_SUPPORTED_FOR_ONE_STEP_REVIEW
```

The authoritative Hugoniot root is:

```text
requested chi:
1.03690185546875e-6

realized chi:
1.0369018554666658e-6

pressure:
4950032.723676263 Pa

pressure offset above outlet cell:
196.73964847624302 Pa

density:
874.438640904945 kg/m3

temperature:
282.37972251022893 K

velocity:
0.11939939121585115 m/s

Mach:
0.0002563222780068828

compatibility residual:
2.8688997531778337e-9 kg/s

local residual slope:
-1.341750718583531e-4 kg/(s Pa)

B1 outcome:
SUCCESS_UNCHOKED_FACE_MAPPING

shock speed:
-465.6960943636747 m/s

lambda_1,P:
-465.69805566684596 m/s

lambda_1,i:
-465.69426511322695 m/s

entropy delta:
6.821210263296962e-13 J/(kg K)

Hugoniot internal-energy residual:
1.5837863746176462e-10 J/kg

root stagnation-pressure margin above back pressure:
38.95682551525533 Pa
```

The fixed Lax ordering, entropy bound, B1 checks, energy checks, and restriction-reaction ledger passed. Diagnostic-only isentropic extrapolation and Hugoniot roots showed no material disagreement under the pre-fixed comparison thresholds.

## Objective

Reproduce the exact accepted step-483 state and authoritative Hugoniot root, construct the pipe-side Euler flux from that root, and apply exactly one actual `FvmSolver` step.

The increment must answer:

```text
1. Is the step-483 parent state reproduced exactly?
2. Is the Increment 5 artifact verified independently?
3. Is the Hugoniot root independently recomputed from the exact step-483 state?
4. Does the recomputed root agree with the authoritative Increment 5 root?
5. Does the root remain outside the approved Weak Compression scope but inside
   the fixed Increment 5 diagnostic cap?
6. Does one actual FvmSolver update reach accepted step 484 while retaining
   positivity, direction, phase, conservation, and root/ledger checks?
```

## Fixed root reproduction tolerances

The recomputed root must agree with the authoritative Increment 5 root within:

```text
absolute requested-chi difference:
1.0e-12

absolute pressure difference:
1.0e-6 Pa

absolute pressure-offset difference:
1.0e-6 Pa

absolute density difference:
1.0e-9 kg/m3

absolute velocity difference:
1.0e-9 m/s

absolute compatibility-residual difference:
1.0e-8 kg/s
```

These tolerances compare two executions of the same fixed diagnostic. They do not change the physical root tolerance.

The retained compatibility-root tolerance remains:

```text
absolute mass residual:
1.0e-8 kg/s
```

## Fixed pipe-side flux

From the independently recomputed Hugoniot root, define:

```text
h0,P = h_P + 0.5 u_P^2

F_mass = mdot_P / A

F_momentum = (mdot_P u_P + p_P A) / A

F_energy = mdot_P h0,P / A

F_rho_xv = 0
```

The selected root must be reevaluated through the unchanged B1 Adapter before the flux is constructed.

Failed B1 states may not construct a flux. No fallback to the isentropic extrapolation root is permitted.

## Fixed solver execution

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

solver step before:
483

requested solver step after:
484

solver time before:
0.0032365792102672024 s

accepted steps requested:
1
```

Use the existing verification-only one-step boundary hook, CFL calculation, boundary mass/energy removal limits, deterministic trial validation, reflective left boundary, transmissive right boundary, and boundary budget.

The candidate time step is the solver-computed and boundary-limited time step. No target-time clipping is applied.

## Required pre-step root gates

Before the solver step, require:

```text
Increment 5 outcome supports one-step review
requested chi > 1.0e-6
requested chi <= 1.0e-4
absolute compatibility residual <= 1.0e-8 kg/s
negative local compatibility-residual slope
p_P > p_i
rho_P > rho_i
outward velocity
0 <= Mach < 1
liquid phase
positive density and internal energy
B1 success
stagnation pressure > back pressure
Hugoniot energy closures pass
identity-accounted Hugoniot equivalence passes
Lax 1-shock ordering passes
entropy delta >= -1.0e-7 J/(kg K)
stagnation-enthalpy round trip passes
energy/mass consistency passes
energy-port closure passes
restriction-reaction ledger closes
```

## Required post-step gates

After the actual step, require:

```text
accepted dt > 0
solver step count = 484
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

The increment records, but does not require, zero deterministic halvings. Any accepted halving must remain inside the existing locked maximum and all final gates must pass.

## Pass outcome

The sole pass token is:

```text
FINITE_COMPRESSION_INCREMENT_6_HUGONIOT_ONE_STEP_PASS
```

A pass establishes only that the fixed Hugoniot root can construct one accepted verification-only finite-compression boundary update from step 483 to step 484.

It does not authorize step 485 or a finite-compression continuation.

## Immediate stop conditions

```text
parent or Increment 5 authority mismatch
state reproduction mismatch
root reproduction outside the fixed comparison tolerances
root inside the approved Weak Compression scope
root outside the fixed Increment 5 diagnostic cap
Hugoniot closure, identity, Lax, entropy, B1, direction, phase,
root, energy, or reaction-ledger failure
nonfinite trial state
nonpositive density or internal energy
reverse outlet velocity
phase departure
rho*xv identity failure
inventory closure failure
solver step count not equal to 484
```

## Formal-state boundary

Regardless of result, retain:

```text
finite_compression_branch_approved = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
