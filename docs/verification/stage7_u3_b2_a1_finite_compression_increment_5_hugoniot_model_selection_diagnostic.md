# Stage 7 U3 B2 A1 finite-compression Increment 5 Hugoniot model-selection diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

This increment starts the finite-compression review after Weak Compression Bridge v0.1 exhausted its fixed `chi <= 1.0e-6` scope.

It loads the exact authoritative accepted step-483 state and compares two candidate pressure-state constructions without advancing `FvmSolver`:

```text
A. diagnostic-only continuation of the existing isentropic characteristic curve
B. a general-EOS compression Hugoniot locus satisfying Rankine-Hugoniot energy
```

This increment does not apply a finite-compression flux, advance solver step 484, enlarge the approved Weak Compression scope, relax the root tolerance, change B1, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, promote any formal state, or approve a shock model.

## Authoritative parent evidence

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

accepted final solver step:
483

accepted final solver time:
0.0032365792102672024 s

nominal horizon fraction:
0.7551805703295805

stop before requested step:
484

stop reason:
successful residual remains positive through the fixed chi scope
```

The final accepted state remained finite, positive, outward, subsonic, liquid, conservative, and free of clear branch chatter. The selected step-483 root had:

```text
pressure offset:
189.63561215624213 Pa

chi:
9.994599988803244e-7

root residual:
-4.57096713604721e-9 kg/s
```

No root existed for requested step 484 inside the approved `chi <= 1.0e-6` Weak Compression scope.

## Diagnostic objective

Determine whether a unique B1-compatible finite-compression root exists immediately outside the current Weak Compression scope, and whether a general-EOS Hugoniot construction is materially distinguishable from unapproved isentropic extrapolation at that root.

The diagnostic must answer:

```text
1. Is the exact accepted step-483 state reproduced without mutation?
2. Is the compatibility residual positive at chi = 1.0e-6 for both diagnostic curves?
3. Does diagnostic-only isentropic extrapolation produce exactly one root?
4. Does the general-EOS Hugoniot locus produce exactly one root?
5. Does the Hugoniot root satisfy compression, outward, subsonic, liquid,
   unchanged B1 success, negative residual slope, energy/reaction ledgers,
   and the Lax 1-shock ordering?
6. How far beyond chi = 1.0e-6 is each root?
7. How different are the isentropic and Hugoniot root pressure, velocity,
   mass rate, entropy, and Hugoniot energy residual?
```

## Fixed state and case

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

accepted state loaded:
solver step 483

solver time:
0.0032365792102672024 s

next requested solver step:
484

retained B1 component:
unchanged

root mass residual absolute tolerance:
1.0e-8 kg/s

approved Weak Compression limit:
chi = 1.0e-6
```

## Fixed diagnostic pressure coordinates

Define:

```text
chi = (p_candidate - p_i) / (rho_i c_i^2)
```

Evaluate both candidate curves at the fixed diagnostic nodes:

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

The diagnostic cap `1.0e-4` is an observation boundary only. It is not an approved continuation scope.

Use requested `chi` and requested pressure offset as the authoritative scan coordinates. Record realized floating-point pressure offsets separately.

## Candidate A: isentropic characteristic extrapolation

Use the existing single-phase isentrope and outgoing-characteristic relation already used by the Weak Compression diagnostic:

```text
s_P = s_i

u_P = u_i - integral from p_i to p_P of dp/(rho c)
```

The construction may be evaluated outside `chi = 1.0e-6` only for model comparison. Any root found is labeled:

```text
UNAPPROVED_ISENTROPIC_EXTRAPOLATION_ROOT
```

It may not construct an applied flux or authorize a solver step.

For each state record the existing Hugoniot energy residual:

```text
H = e_P - e_i + 0.5 (p_P + p_i) (v_P - v_i)
```

## Candidate B: general-EOS compression Hugoniot locus

For each fixed candidate pressure `p_P > p_i`, solve a liquid compression state with `rho_P > rho_i` satisfying:

```text
e_P - e_i + 0.5 (p_P + p_i) (v_P - v_i) = 0
```

where:

```text
v = 1/rho
```

Use CoolProp `HEOS::CO2` and fixed-pressure density search. No ideal-gas or constant-gamma approximation is permitted.

The density root search is deterministic:

```text
initial lower density:
rho_i * (1 + 1.0e-12)

initial upper density:
rho_i * (1 + max(1.0e-5, 20 chi))

scan nodes:
65 linearly spaced density nodes

maximum upper-bound expansions:
8

upper-bound expansion factor:
2

Hugoniot density bisection iterations:
64
```

At each expansion, preserve the lower bound and multiply only the fractional density increase above `rho_i` by two. Stop fail-closed if no unique sign-change bracket exists, more than one bracket exists, CoolProp leaves the allowed liquid phase, or a nonfinite state appears.

For a Hugoniot state, define the positive shock-frame mass flux magnitude:

```text
j = sqrt((p_P - p_i) / (v_i - v_P))
```

and the boundary velocity and shock speed:

```text
u_P = u_i - j (v_i - v_P)
S = u_i - j v_i
```

Require:

```text
p_P > p_i
rho_P > rho_i
v_P < v_i
j > 0
```

## Lax and entropy diagnostics

For the compression Hugoniot state, record:

```text
lambda_1,i = u_i - c_i
lambda_1,P = u_P - c_P
```

The fixed Lax 1-shock ordering is:

```text
lambda_1,P < S < lambda_1,i
```

Also record:

```text
entropy_delta_J_kg_K = s_P - s_i
```

Entropy production is observational in Increment 5 because a very weak shock can be near CoolProp and floating-point resolution. A negative value below `-1.0e-7 J/(kg K)` is fail-closed; values at or above that bound are recorded without claiming experimental entropy validation.

## B1 and local admissibility

Each isentropic and Hugoniot candidate is converted to the same conserved-state form and passed through the unchanged B1 Adapter.

A successful root candidate must retain:

```text
B1 success
outward velocity
0 <= Mach < 1
allowed liquid phase
stagnation pressure > retained back pressure
positive density and internal energy
restriction-reaction ledger closure
stagnation-enthalpy round trip
energy/mass consistency
energy-port closure
```

Failed B1 states remain failed and may not form a compatibility-root bracket.

## Root topology

For each candidate curve independently:

```text
use only successful locally admissible states
sort by requested chi
require residuals monotone nonincreasing
require exactly one sign-change bracket
```

Use requested `chi` as the bisection coordinate. Maximum compatibility-root bisection iterations:

```text
48
```

Every bisection midpoint must reconstruct its candidate state from the respective curve and independently pass B1 and local admissibility. No failed state may be used as a root endpoint.

## Required evidence

At minimum, write:

```text
parent GitHub artifact metadata and digest verification
parent internal SHA256 verification
exact step-483 state identity
interior static and stagnation properties
fixed scan rows for both curves
Hugoniot density-search rows and brackets
isentropic root evidence
Hugoniot root evidence
root requested and realized chi
root pressure offset
root residual and local slope
root B1 outcome
root direction, Mach, phase, and stagnation-pressure margin
root entropy delta
root Hugoniot energy residual
Hugoniot mass flux and shock speed
Lax eigenvalues and ordering
energy and reaction ledgers
curve-to-curve root comparison
confirmation that solver step 484 was not attempted
confirmation that the conserved state remained unchanged
```

## Diagnostic classifications

### `FINITE_COMPRESSION_HUGONIOT_ROOT_SUPPORTED_FOR_ONE_STEP_REVIEW`

This classification requires:

```text
parent and exact-state verification pass
residual at chi = 1.0e-6 remains positive
exactly one Hugoniot root exists within the diagnostic cap
root requested chi > 1.0e-6
root requested chi <= 1.0e-4
Hugoniot energy equation closes
compression density and volume ordering pass
outward, subsonic, liquid state
unchanged B1 succeeds
absolute compatibility residual <= 1.0e-8 kg/s
negative local compatibility-residual slope
Lax 1-shock ordering passes
entropy delta >= -1.0e-7 J/(kg K)
energy and reaction ledgers pass
state remains unchanged
FvmSolver step 484 is not attempted
```

A pass supports only a later separately fixed one-step MODEL_REVIEW. It does not approve a finite-compression branch.

### `FINITE_COMPRESSION_ROOT_INSIDE_DIAGNOSTIC_CAP_BUT_MODEL_DISAGREEMENT`

Return this when both roots exist but their pressure offsets or velocities differ materially, or the Hugoniot root fails Lax/entropy while the isentropic extrapolation appears to close.

Material comparison thresholds fixed before results:

```text
relative root pressure-offset difference > 1.0e-3
absolute root velocity difference > 1.0e-5 m/s
relative root mass-rate difference > 1.0e-3
```

### `NO_FINITE_COMPRESSION_ROOT_WITHIN_DIAGNOSTIC_CAP`

Return this when the Hugoniot residual scan remains one-signed through `chi = 1.0e-4` or no unique B1-compatible Hugoniot root exists.

### Other fail-closed classifications

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
HUGONIOT_DENSITY_ROOT_FAILURE
HUGONIOT_MULTIPLE_DENSITY_ROOTS
PHASE_SCOPE_DEPARTURE
B1_ADMISSIBLE_DOMAIN_FAILURE
MULTIPLE_COMPATIBILITY_ROOTS
COMPATIBILITY_ROOT_FAILURE
LAX_ADMISSIBILITY_FAILURE
ENTROPY_DECREASE_FAILURE
ROOT_OR_LEDGER_FAILURE
STATE_MUTATION_DETECTED
```

## Formal-state boundary

Regardless of the diagnostic result, retain:

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
