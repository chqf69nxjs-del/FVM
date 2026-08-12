# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 model review

## Status

`MODEL_REVIEW_ONLY / WORKING_VERTICAL_SLICE / FIXED_BEFORE_EXECUTION_RESULT`

This increment defines the minimum diagnostic-only weak-compression continuation needed immediately after the accepted A1 neutral-endpoint step 337. The specification is fixed before any Weak Compression Bridge execution result is produced.

It does not revise the locked B2 v1 Contract, modify the accepted B1 component, change the production B2 Adapter or `FvmSolver`, approve a general finite-compression branch, complete the full `2L/c0` horizon, verify finite-pipe coupling, accept a benchmark, perform Physical Validation, approve design use, or activate production HEM behavior.

## Authoritative parent evidence

```text
parent source:
e3202ce2b886c0ff21893076d66c84dc9b275919

post-endpoint classification workflow run:
31569936520

job:
94029540062

artifact:
9130980459

artifact SHA256:
550f3ffccd1a99a32b8f833a0a2af9e2196dcfd169dbf1aeac1850442cb3c539

classification:
OUTCOME_B_LOCAL_COMPRESSION_REQUIRED

starting accepted solver step:
337

step-338 pre-step endpoint residual:
approximately +1.674677e-7 kg/s

retained root-mass tolerance:
1.0e-8 kg/s

rarefaction-side compatible root:
none

local positive-pressure root evidence:
+0.001 Pa residual positive
+0.01 Pa residual negative

linear positive-pressure root estimate:
approximately +1.28e-3 Pa
```

The parent diagnostic did not apply a positive-pressure continuation flux. It stopped before solver step 338.

## Development objective

The immediate objective is not a complete compression-wave or shock model. It is to determine whether the step-337 outlet state admits one small, admissible, positive-pressure compatibility root under a narrowly scoped weak-acoustic approximation.

The development sequence is:

```text
Increment 1:
diagnostic-only Weak Compression root at the reproduced step-337 state

Increment 2:
one actual FvmSolver step, 337 -> 338, only if Increment 1 passes

Increment 3:
maximum 32 accepted post-endpoint steps, only if Increment 2 passes

Increment 4:
full 2L/c0 working vertical slice, only if Increment 3 is robust
```

This document fixes Increment 1 only.

## Fixed Increment 1 execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

reproduced accepted solver step:
337

FvmSolver advancement after the reproduced step 337:
none

root branch requested:
WEAK_COMPRESSION

bisection iteration limit:
32
```

The exact step-336 checkpoint and accepted neutral-endpoint step 337 must be reproduced first from the existing numerical sources. Increment 1 must leave the reproduced state and solver step unchanged after the diagnostic root solve.

## Weak Compression Bridge v0.1 model

Let the reconstructed step-337 outlet-cell state be

```text
(p_i, rho_i, u_i, e_i, h_i, c_i, s_i)
```

For a candidate pressure `p_P` close to `p_i`, use the same isentropic characteristic continuation on both sides of the neutral endpoint:

```text
u_P = u_i - integral[p_i -> p_P] dp / (rho(p, s_i) c(p, s_i))

s_P = s_i

(rho_P, h_P, e_P, c_P, T_P) = EOS(p_P, s_i)
```

For `p_P < p_i`, the signed integral produces the existing rarefaction continuation. For `p_P > p_i`, it produces the Weak Compression Bridge candidate.

The compatibility residual remains

```text
R(p_P) = rho_P u_P A_pipe - m_dot_B1(p_P, u_P, h0_P)

h0_P = h_P + u_P^2 / 2
```

The pipe-side momentum port remains

```text
Pi_P = m_dot_P u_P + p_P A_pipe
```

The B1 downstream stream-plus-pressure port remains

```text
Pi_E = m_dot_B1 u_eff + p_d A_open
```

The restriction reaction remains a separate ledger:

```text
R_w = Pi_E - Pi_P
```

`Pi_E` must not be copied directly into the pipe-side FVM momentum flux.

## Claim boundary of the approximation

The Weak Compression Bridge v0.1 is a local weak-acoustic approximation around the neutral endpoint. It is not a claim that a finite-amplitude compression shock is isentropic.

The following are explicitly outside Increment 1:

```text
general-EOS Hugoniot solver
entropy-production model
Lax shock condition
shock speed tracking
full Riemann solver
artificial viscosity
high-order reconstruction
two-phase compression model
```

These remain BACKLOG unless the working vertical slice reaches the fixed weak-compression scope limit or exhibits a failure that prevents reliable one-through execution.

## Fixed branch classification order

At the reproduced step-337 outlet state, perform the following operations in this order:

```text
1. evaluate the neutral endpoint R(p_i)
2. accept NEUTRAL_ENDPOINT if the retained root tolerance is met
3. otherwise evaluate the approved connected rarefaction side
4. if one approved rarefaction root exists, classify RAREFACTION
5. if no approved rarefaction root exists, scan the positive-pressure side
6. if exactly one positive-pressure sign-change bracket exists within scope,
   solve its first bracket by bisection
7. classify WEAK_COMPRESSION only if every fixed acceptance check passes
8. otherwise fail closed
```

The endpoint is always evaluated before any sign-change requirement.

## Retained neutral root tolerance

No new root tolerance is introduced.

```text
abs(R(p_i)) <= 1.0e-8 kg/s
```

If this condition is met together with the retained state and ledger checks, the branch is `NEUTRAL_ENDPOINT`, not `WEAK_COMPRESSION`.

The tolerance must not be relaxed to obtain a continuation result.

## Rarefaction precedence

A Weak Compression candidate may be considered only when all of the following hold:

```text
abs(R(p_i)) > 1.0e-8 kg/s
no approved connected rarefaction root exists
no rarefaction-side local root requiring branch review exists
```

The existing A1 rarefaction model and its retained admissibility checks are not modified by this increment.

## Fixed Weak Compression scope

Define

```text
chi = (p_P - p_i) / (rho_i c_i^2)
```

The Weak Compression Bridge v0.1 scope is fixed as

```text
0 < chi <= 1.0e-6
```

This is a model applicability limit, not a root residual tolerance.

The corresponding maximum pressure offset is evaluated from the reproduced outlet state:

```text
Delta_p_max = 1.0e-6 rho_i c_i^2
```

The scope must not be enlarged after observing the result.

## Fixed positive-pressure scan

Start with the neutral endpoint and scan positive pressure offsets in decade order:

```text
Delta_p =
0
1.0e-4
1.0e-3
1.0e-2
1.0e-1
1
10
100
1000 Pa
...
```

Only offsets satisfying

```text
Delta_p <= Delta_p_max
```

are admissible. If the final decade lies below `Delta_p_max`, append `Delta_p_max` as the final scan point.

Evaluate the complete in-scope scan before root acceptance so multiple sign changes can be detected. Use only the first sign-change bracket. More than one admissible sign-change bracket is a fail-closed stop.

## Fixed bisection rule

For the first admissible positive-pressure sign-change bracket:

```text
maximum iterations:
32

root residual acceptance:
abs(R(p_P)) <= 1.0e-8 kg/s
```

Newton iteration, tolerance relaxation, extrapolation beyond the first bracket, and continuation beyond `Delta_p_max` are not permitted in Increment 1.

Every midpoint must remain evaluable and admissible. An EOS failure, B1 failure, phase departure, reverse direction, subsonic departure, or ledger failure stops the diagnostic.

## WEAK_COMPRESSION acceptance gate

Increment 1 passes only when all of the following are true:

```text
step-336 checkpoint reproduction passed
step-337 neutral-endpoint resume reproduction passed
solver step remained 337 after the diagnostic
endpoint residual is outside the retained 1.0e-8 kg/s tolerance
no approved rarefaction root exists
exactly one admissible positive-pressure sign-change bracket exists
branch = WEAK_COMPRESSION
p_P > p_i
0 < chi <= 1.0e-6
abs(R(p_P)) <= 1.0e-8 kg/s
u_P >= 0
0 <= Mach_P < 1
single-phase liquid scope retained
B1 evaluation succeeded
stagnation pressure remains above back pressure
stagnation-enthalpy round trip passed
energy/mass decomposition passed
energy-port closure passed
restriction-reaction ledger closure passed
no FvmSolver step 338 was attempted
```

The diagnostic gate result is:

```text
WEAK_COMPRESSION_INCREMENT_1_DIAGNOSTIC_PASS
```

Any other result is a fail-closed diagnostic stop.

## Required evidence

At minimum, record:

```text
source and parent Git SHAs
checkpoint and step-337 reproduction status
solver step and time before and after the diagnostic
interior p_i, rho_i, u_i, c_i, Mach_i, phase, and entropy
retained root tolerance
endpoint residual and endpoint classification
rarefaction-side sign-change counts
positive-pressure scan offsets, pressures, residuals, admissibility, and chi
positive-pressure sign-change count
selected first bracket
bisection iteration count
root p_P and p_P - p_i
root chi
root rho_P, u_P, c_P, Mach_P, phase, h0_P
pipe and B1 mass rates
root mass residual
B1 formal outcome and message
stagnation pressure and back pressure
pipe-side momentum port
B1 downstream stream-plus-pressure port
restriction reaction
restriction-reaction ledger residual
pipe and B1 energy rates
energy-port residual
stagnation-enthalpy round-trip residual
energy/mass consistency residual
confirmation that no positive-pressure flux was applied
confirmation that solver step remained 337
```

The complete positive-pressure scan and the accepted root row are separate evidence tables.

## Immediate stop conditions

Stop without solver advancement for any of the following:

```text
checkpoint or step-337 reproduction mismatch
endpoint evaluation failure
endpoint already satisfies the retained neutral tolerance
approved rarefaction root exists
no in-scope positive-pressure sign change
multiple positive-pressure sign changes
root not converged within 32 bisection iterations
root pressure is not above p_i
chi <= 0 or chi > 1.0e-6
nonfinite value
EOS failure
B1 failure
reverse velocity
Mach outside [0, 1)
phase-scope departure
stagnation pressure not above back pressure
energy closure failure
restriction-reaction ledger failure
unexpected source or branch movement
```

## Formal state

A passing Increment 1 result remains `MODEL_REVIEW / WORKING_VERTICAL_SLICE` evidence only.

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

A passing diagnostic authorizes only the next MODEL_REVIEW increment: one actual FvmSolver step from 337 to 338 using the same fixed Weak Compression Bridge v0.1 root construction and retained safeguards.
