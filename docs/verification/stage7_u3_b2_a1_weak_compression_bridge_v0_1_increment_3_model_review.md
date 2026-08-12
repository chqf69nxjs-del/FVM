# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 3 model review

## Status

`MODEL_REVIEW_ONLY / WORKING_VERTICAL_SLICE / FIXED_BEFORE_EXECUTION_RESULT`

This increment extends the accepted Weak Compression Bridge v0.1 one-step result to a maximum 32-accepted-step branch-aware short run.

It does not change the Weak Compression approximation, root tolerance, `chi` scope, B1 component, locked B2 v1 Contract, production B2 Adapter, or `FvmSolver`. It does not approve a general finite-compression branch, complete the full `2L/c0` horizon, verify finite-pipe coupling, accept a benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative parent evidence

```text
parent source:
a9b43a0bc8e2a307f21ac02129a3d62ba3495165

Increment 2 workflow run:
31602684937

Increment 2 job:
94133772628

Increment 2 artifact:
9143921347

Increment 2 artifact SHA256:
e8ab1e24f9612f1cbad23a128b29835e54ca8eb74525641ff966d64d8e75088d

Increment 2 outcome:
WEAK_COMPRESSION_INCREMENT_2_ONE_STEP_PASS

accepted solver step:
337 -> 338

root pressure offset:
+1.2812502682209015e-3 Pa

root chi:
6.7526315817248263e-12

root mass residual:
-1.0287136420483733e-10 kg/s

accepted dt:
6.7068718415872047e-6 s

post-step outlet pressure:
4,950,034.4632814685 Pa

post-step outlet velocity:
+0.12253661869990586 m/s
```

## Objective

Reproduce the accepted step-337 state and Increment 2 one-step result, then independently run the branch-aware Weak Compression Bridge from step 337 for exactly 32 accepted steps:

```text
first accepted step:
338

final accepted step:
369

accepted steps requested:
32
```

The run is intended to observe whether the compatibility root remains unique, whether Weak Compression grows, returns through Neutral to Rarefaction, or produces clear branch chatter, while retaining the existing solver safeguards and conservation checks.

## Fixed branch set

Only these accepted branches are permitted:

```text
RAREFACTION
NEUTRAL_ENDPOINT
WEAK_COMPRESSION
```

The fail-closed classification remains:

```text
FINITE_COMPRESSION_MODEL_REQUIRED
```

No other compression model is introduced.

## Fixed classification order at every accepted step

For the current outlet-cell state, perform the following in order:

```text
1. reconstruct the interior state
2. evaluate the neutral endpoint R(p_i)
3. if abs(R(p_i)) <= 1.0e-8 kg/s and all state/ledger checks pass,
   select NEUTRAL_ENDPOINT
4. otherwise scan the approved connected rarefaction branch
5. independently reject multiple admissible roots
6. if exactly one approved rarefaction root exists and no positive-side root exists,
   select RAREFACTION
7. if no approved rarefaction root exists, scan the positive-pressure side under
   the fixed Weak Compression chi scope
8. if exactly one admissible positive-pressure root exists within scope,
   select WEAK_COMPRESSION
9. if the required positive-pressure root lies beyond the fixed scope,
   stop as FINITE_COMPRESSION_MODEL_REQUIRED
10. otherwise stop fail closed
```

The endpoint check always precedes sign-change requirements. The root mass tolerance remains unchanged:

```text
abs(R) <= 1.0e-8 kg/s
```

## Rarefaction branch

Use the existing A1 connected subsonic rarefaction model and safeguards:

```text
u_P = u_i - integral[p_i -> p_P] dp / (rho c)

p_P < p_i

one connected admissible root
residual monotone on the approved connected scan
0 <= Mach < 1
outward velocity
allowed single-phase liquid
B1 success
energy ledger closure
restriction-reaction ledger closure
```

No rarefaction tolerance or scan rule is changed.

## Neutral branch

Use the current interior state when:

```text
p_P = p_i
abs(R(p_i)) <= 1.0e-8 kg/s
```

The same phase, direction, subsonic, B1, energy, and reaction-ledger checks remain mandatory.

## Weak Compression branch

Use the unchanged local weak-acoustic relation:

```text
u_P = u_i - integral[p_i -> p_P] dp / (rho(p,s_i)c(p,s_i))

p_P > p_i
s_P = s_i
```

The fixed scope remains:

```text
chi = (p_P - p_i) / (rho_i c_i^2)

0 < chi <= 1.0e-6
```

The positive-pressure scan remains decade-based, uses the first sign-change bracket, evaluates the complete in-scope scan to detect multiple roots, and uses at most 32 bisection iterations. The root tolerance is not relaxed.

## Pipe-side flux and restriction reaction

For all three branches, apply only the pipe-side Euler flux:

```text
F_rho    = rho_P u_P
F_rho_u  = rho_P u_P^2 + p_P
F_rho_E  = rho_P u_P h0_P
F_rho_xv = 0
```

Keep the B1 downstream stream-plus-pressure port separate and retain:

```text
R_w = Pi_E - Pi_P
```

`Pi_E` must not replace the pipe-side momentum flux.

## Fixed branch-chatter rule

A single branch transition is not a failure. Natural transitions such as

```text
WEAK_COMPRESSION -> NEUTRAL_ENDPOINT -> RAREFACTION
```

are allowed when every root is individually admissible.

For this short-run increment, `CLEAR_BRANCH_CHATTER` is fixed structurally as five consecutive accepted branch classifications alternating between exactly two distinct branches:

```text
A -> B -> A -> B -> A

A != B
```

The fifth candidate is rejected before solver advancement. This rule introduces no pressure or residual tolerance and must not be relaxed after observing the result.

All shorter transition patterns are recorded for review but do not by themselves stop the working vertical slice.

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

starting accepted solver step:
337

requested additional accepted steps:
32

expected final accepted solver step:
369

maximum deterministic halvings per step:
locked Contract value
```

The run stops immediately on any fail-closed condition. Partial rows and the stopping classification must still be preserved in the artifact.

## Per-step acceptance gate

Every accepted row must satisfy:

```text
branch in {RAREFACTION, NEUTRAL_ENDPOINT, WEAK_COMPRESSION}
exactly one selected admissible root, or an accepted neutral endpoint
abs(root mass residual) <= 1.0e-8 kg/s
root velocity >= 0
0 <= root Mach < 1
allowed single-phase liquid
B1 success
stagnation-enthalpy round trip passed
energy/mass decomposition passed
energy-port closure passed
restriction-reaction ledger closure passed
accepted dt > 0
post-step conserved state finite
post-step density positive
post-step internal energy positive
no reverse-flow Guard
no reverse outlet velocity
post-step phase allowed
rho*xv exact zero
step mass closure passed
step momentum closure passed
step energy closure passed
cumulative mass closure passed
cumulative momentum closure passed
cumulative energy closure passed
```

For `WEAK_COMPRESSION`, also require:

```text
0 < chi <= 1.0e-6
exactly one positive-pressure sign-change bracket
```

For `RAREFACTION`, require:

```text
p_P < p_i
exactly one connected rarefaction root
```

For `NEUTRAL_ENDPOINT`, require:

```text
p_P = p_i
endpoint within retained root tolerance
```

## Increment 3 acceptance gate

The Increment 3 gate passes only when:

```text
Increment 2 parent result is reproduced
32 accepted rows are completed
solver step count changes exactly 337 -> 369
all 32 rows pass their per-step gates
no fail-closed stop occurs
no CLEAR_BRANCH_CHATTER occurs
all root branches remain inside the approved three-branch set
all conservation and ledger checks remain passed
formal flags remain false
```

The successful outcome is:

```text
WEAK_COMPRESSION_INCREMENT_3_32_STEP_PASS
```

## Required evidence

Retain at minimum:

```text
source and parent Git SHAs
parent workflow/job/artifact/digest
parent one-step reproduction result
one row per requested/accepted step
branch sequence and branch counts
branch transitions and chatter-rule evaluation
endpoint residual per step
rarefaction scan count and monotonicity per step
positive-pressure scan and bracket count when evaluated
root pressure offset and chi per step
root mass residual, Mach, velocity, phase, and B1 outcome
pipe-side flux, downstream port, reaction, and energy ledgers
candidate dt, removal limits, accepted dt, halvings, and trial dts
post-step outlet pressure, velocity, phase, density, and internal energy
step and cumulative mass/momentum/energy residuals
initial and final conserved arrays
stop reason or explicit null stop reason
formal flags
```

## Immediate stop conditions

```text
parent reproduction failure
endpoint evaluation or admissibility failure
non-monotone connected rarefaction scan
no root
multiple roots
positive root beyond chi scope
FINITE_COMPRESSION_MODEL_REQUIRED
CLEAR_BRANCH_CHATTER
root residual outside retained tolerance
reverse root velocity
root subsonic departure
phase-scope departure
EOS or B1 failure
energy or reaction-ledger failure
nonfinite state
positivity failure after all existing halvings
reverse outlet velocity
rho*xv identity failure
mass, momentum, or energy closure failure
unexpected source or branch movement
```

## Formal state

A passing Increment 3 result authorizes only the next MODEL_REVIEW increment: an attempted full `2L/c0` working vertical slice under the same fixed branch model and safeguards.

The following remain false:

```text
finite_compression_branch_approved = false
full_two_l_over_c0_passed = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
formal_state_promoted = false
```
