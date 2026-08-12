# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 2 model review

## Status

`MODEL_REVIEW_ONLY / WORKING_VERTICAL_SLICE / FIXED_BEFORE_EXECUTION_RESULT`

This increment applies the already-fixed Weak Compression Bridge v0.1 root construction to exactly one actual `FvmSolver` step after the reproduced accepted step 337.

It does not change the Weak Compression model, root tolerance, `chi` scope, B1 behavior, locked B2 v1 Contract, production B2 Adapter, or `FvmSolver` implementation. It does not approve a general finite-compression branch, complete the full `2L/c0` horizon, verify finite-pipe coupling, accept a benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative parent evidence

```text
parent source:
2807fab09bbacd61971346c43d742944e4428a7f

Increment 1 workflow run:
31601616704

Increment 1 job:
94130182117

Increment 1 artifact:
9143467594

Increment 1 artifact SHA256:
9a68c543740d7a891fe39161619d048bcd4c79b011e4e56dfeb4c55e25187185

Increment 1 outcome:
WEAK_COMPRESSION_INCREMENT_1_DIAGNOSTIC_PASS

Increment 1 solver step before and after diagnostic:
337

Increment 1 FvmSolver step 338 attempted:
false
```

Increment 1 established one admissible positive-pressure root within the fixed Weak Compression Bridge v0.1 scope and independently asserted that the step-337 state was unchanged.

## Objective

Reproduce the authoritative step-337 state and Increment 1 Weak Compression root, construct the pipe-side Euler flux from that root, and advance the existing `FvmSolver` by exactly one accepted step:

```text
337 -> 338
```

No additional post-step continuation is part of Increment 2.

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

target accepted solver step:
338

maximum accepted steps in this increment:
1

Weak Compression chi scope:
0 < chi <= 1.0e-6

root mass residual absolute tolerance:
1.0e-8 kg/s

positive-pressure bisection maximum:
32 iterations
```

The exact step-336 checkpoint and accepted step 337 must first be reproduced. The Increment 1 diagnostic root construction must then pass again before the one-step solver is created.

## Fixed boundary root construction

Use the unchanged Weak Compression Bridge v0.1 relation:

```text
u_P = u_i - integral[p_i -> p_P] dp / (rho(p, s_i) c(p, s_i))

s_P = s_i

(rho_P, h_P, e_P, c_P, T_P) = EOS(p_P, s_i)

R(p_P) = rho_P u_P A_pipe - m_dot_B1
```

The fixed branch order remains:

```text
NEUTRAL_ENDPOINT
then approved RAREFACTION
then WEAK_COMPRESSION
otherwise fail closed
```

For this increment, the reproduced pre-step-338 state must again classify as `WEAK_COMPRESSION` with exactly one admissible positive-pressure sign-change bracket, no approved rarefaction root, and a converged root satisfying the unchanged tolerance and `chi` limit.

## Fixed pipe-side flux

Construct the right external pipe-side Euler flux only from the accepted Weak Compression root:

```text
F_rho    = rho_P u_P
F_rho_u  = rho_P u_P^2 + p_P
F_rho_E  = rho_P u_P h0_P
F_rho_xv = 0

h0_P = h_P + u_P^2 / 2
```

Equivalently, using the pipe area:

```text
F_rho   = m_dot_P / A_pipe
F_rho_u = (m_dot_P u_P + p_P A_pipe) / A_pipe
F_rho_E = m_dot_P h0_P / A_pipe
```

The B1 downstream stream-plus-pressure momentum port remains separate:

```text
Pi_E = m_dot_B1 u_eff + p_d A_open
```

The restriction reaction remains a diagnostic ledger:

```text
R_w = Pi_E - Pi_P

Pi_P = m_dot_P u_P + p_P A_pipe
```

`Pi_E` must not replace the pipe-side momentum flux.

## Existing FvmSolver safeguards

Use the existing solver without source modification:

```text
existing CFL calculation
existing boundary mass-removal limit
existing boundary energy-removal limit
existing deterministic halving limit
existing positivity validation
existing reverse-outlet-velocity validation
existing single-phase validation
exact rho*xv = 0 identity
```

The accepted time step must be positive and finite. Any trial failure is handled only through the existing deterministic halving mechanism; no tolerance or model scope may be relaxed.

## Fixed one-step accounting

Before the step, reconstruct cumulative expected inventory change through the authoritative accepted step 337 from the existing evidence.

For accepted step 338, use the exact external face fluxes applied by the solver:

```text
Delta U_expected = dt A_pipe (F_left - F_right)
```

Record both step and cumulative residuals for:

```text
mass
momentum
energy
```

Use only the locked B2 inventory tolerances.

## Increment 2 acceptance gate

The Increment 2 gate passes only when all of the following are true:

```text
step-336 checkpoint reproduction passed
step-337 neutral-endpoint resume reproduction passed
Increment 1 Weak Compression diagnostic reproduced and passed
pre-step branch = WEAK_COMPRESSION
exactly one positive-pressure root bracket
0 < chi <= 1.0e-6
abs(root mass residual) <= 1.0e-8 kg/s
root velocity >= 0
0 <= root Mach < 1
root phase is allowed single-phase liquid
B1 evaluation succeeded
energy ledger closure passed
restriction-reaction ledger closure passed
solver step count changed exactly 337 -> 338
accepted dt > 0
no reverse-flow Guard
no reverse outlet velocity
post-step phase remains allowed liquid
post-step positivity retained
rho*xv remains exact zero
step mass closure passed
step momentum closure passed
step energy closure passed
cumulative mass closure passed
cumulative momentum closure passed
cumulative energy closure passed
```

The successful diagnostic outcome is:

```text
WEAK_COMPRESSION_INCREMENT_2_ONE_STEP_PASS
```

## Required evidence

At minimum, retain:

```text
source and parent Git SHAs
parent workflow, job, artifact, and artifact digest
checkpoint and step-337 reproduction status
reproduced positive-pressure scan
reproduced Weak Compression root row
root pressure offset and chi
root residual and bisection count
pipe-side applied flux
B1 downstream port and restriction reaction ledger
solver step before and after
solver time before and after
CFL candidate dt
mass-removal dt limit
energy-removal dt limit
accepted dt
halving count and trial dt sequence
state arrays before and after
post-step outlet pressure, velocity, Mach-compatible state, and phase
step and cumulative mass, momentum, and energy residuals
rho*xv exact-zero result
formal flags
```

## Immediate stop conditions

Stop without accepting step 338 for any of the following:

```text
checkpoint or step-337 reproduction mismatch
Increment 1 root reproduction failure
branch is not WEAK_COMPRESSION
no root or multiple roots
root outside fixed chi scope
root residual outside retained tolerance
nonfinite value
EOS or B1 failure
reverse root velocity
root subsonic departure
root phase-scope departure
energy or reaction ledger failure
non-positive candidate or accepted dt
all existing halvings exhausted
post-step positivity failure
post-step reverse velocity
post-step phase-scope departure
rho*xv identity failure
mass, momentum, or energy closure failure
solver step count not exactly 338
unexpected source or branch movement
```

## Formal state

A passing Increment 2 result authorizes only the next MODEL_REVIEW increment: a maximum 32-accepted-step short run using branch-aware `RAREFACTION`, `NEUTRAL_ENDPOINT`, and `WEAK_COMPRESSION` handling under the same fixed safeguards.

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
