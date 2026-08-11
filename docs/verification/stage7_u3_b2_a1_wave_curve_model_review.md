# Stage 7 U3 B2 A1 wave-curve model review

## Status

`MODEL_REVIEW_ONLY / FIXED_BEFORE_WAVE_CURVE_RESULTS`

This document fixes the next diagnostic increment after the B2-10A evolving-cell A1 run stopped at step 337. It does not revise the locked B2 v1 Contract, the accepted B1 component, the production B2 Adapter, `FvmSolver`, any physics tolerance, or any formal project state.

## Authoritative starting evidence

```text
repository:
chqf69nxjs-del/FVM

parent model-review source:
eee113e40911b11c62644609f9b8c57ac85707b4

dynamic-short success:
run 31458293326

full 2L/c0 attempt after admissible slope fix:
run 31467704260
accepted steps 336
final time 0.0022506672049592393 s
one-way L/c0 0.0021429174275860107 s
target 2L/c0 0.004285834855172021 s
stop: connected rarefaction-side scan retained zero sign changes
```

The 336 accepted steps retained outward velocity, subsonic roots, the liquid phase scope, exact-zero vapor identity, mass/momentum/energy inventory closure, and the restriction-reaction ledger. The next diagnostic therefore targets the boundary wave-curve domain and root classification only.

## Retained A1 architecture

For the right subsonic outflow, the pipe-side trace `P` remains connected to the evolving outlet-cell state `i` through the outgoing 1-wave information. The pipe-side mass rate must remain compatible with the unchanged accepted B1 discharge law.

Rarefaction-side relation:

```text
u_P - u_i = integral[p_P -> p_i] dp / (rho(p,s_i) c(p,s_i))
```

Compatibility residual:

```text
R(p_P) = rho_P u_P A_pipe - m_dot_B1(h0_P, s_P, p_back)
```

Pipe-side Euler transfer:

```text
m_dot_P = rho_P u_P A_pipe
Pi_P    = m_dot_P u_P + p_P A_pipe
E_dot_P = m_dot_P h0_P
```

Restriction reaction remains a separate diagnostic ledger:

```text
R_w = Pi_E - Pi_P
```

No B1 equation or coefficient placement changes in this increment.

## Wave-curve regions under review

### Rarefaction region

```text
p_P < p_i
s_P = s_i
```

The existing isentropic characteristic relation is retained.

### Neutral endpoint

```text
p_P = p_i
```

The endpoint residual is evaluated before any sign-change requirement. If

```text
abs(R(p_i)) <= 1.0e-8 kg/s
```

then the state is classified as an endpoint root under the already-retained root-mass tolerance. This is not a new or relaxed tolerance.

### Local compression continuation

```text
p_P > p_i
```

For this diagnostic only, the same signed isentropic integral is evaluated over small positive pressure offsets to test whether the residual continues smoothly across `p_P = p_i`. This is an observation-only local continuation; it is not approval of a finite-amplitude compression wave model.

For each positive pressure offset, the diagnostic also records the general-EOS Hugoniot energy residual evaluated at the local isentropic candidate:

```text
H = e_P - e_i + 0.5 * (p_P + p_i) * (v_P - v_i)
v = 1 / rho
```

A finite compression branch is not accepted solely because this residual is small. A later increment must independently derive and implement the general-EOS Hugoniot/Lax branch before any finite-compression production use.

## Exact checkpoint method

The diagnostic replays B2-10A from the fixed parent source with:

```text
cells 32
CFL 0.10
left boundary ReflectiveBoundary
right boundary evolving-cell A1 rarefaction-side hook
CoolProp 8.0.0
numpy 2.5.1
```

It advances through every accepted step using the existing retained checks. At the first next-step root failure, it saves:

```text
full conservative U array
solver time
solver step count
previous accepted root pressure
outlet reconstructed static/stagnation state
initial and current inventories
cumulative expected conservative delta
fixed source SHA and dependency versions
```

The expected checkpoint is the state after 336 accepted steps. A different accepted-step count or a different stop classification is not silently normalized; it is reported as a reproduction mismatch.

## Fixed pressure offsets

The checkpoint outlet pressure `p_i` is scanned at the following predeclared offsets in pascals:

```text
-1
-0.1
-0.01
-0.001
-0.0001
-0.00001
-0.000001
0
+0.000001
+0.00001
+0.0001
+0.001
+0.01
+0.1
+1
```

For every point the diagnostic records:

```text
branch label
pressure and pressure offset
rho, u, c, Mach, h, e, s and h0
pipe mass rate
B1 mass rate and formal outcome
compatibility residual
pipe and downstream momentum ports
restriction reaction and ledger residual
pipe and B1 energy rates
Hugoniot energy residual
outward/subsonic/single-phase/stagnation-pressure admissibility
```

## Classification order

The result is classified in this fixed order.

1. `CHECKPOINT_REPRODUCTION_MISMATCH`
   - the expected stopping checkpoint is not reproduced.
2. `NEUTRAL_ENDPOINT_WITHIN_LOCKED_TOLERANCE`
   - `abs(R(p_i)) <= 1.0e-8 kg/s` and endpoint admissibility checks pass.
3. `LOCAL_COMPRESSION_CONTINUATION_ROOT_SUPPORTED`
   - endpoint is outside the retained root tolerance and exactly one sign change exists on the positive-offset local continuation while all retained admissibility checks pass.
4. `RAREFACTION_ROOT_RETAINED`
   - endpoint is outside tolerance and exactly one sign change remains on the negative-offset side.
5. `MULTIPLE_LOCAL_ROOT_BRANCHES`
   - more than one connected sign change exists.
6. `NO_LOCAL_COMPATIBLE_ROOT`
   - no endpoint root or local sign change exists.
7. `LOCAL_ROOT_INADMISSIBLE`
   - a numerical root exists but outward, subsonic, phase, B1, energy, or reaction-ledger requirements fail.

## Gate meaning

This increment passes when:

```text
checkpoint reproduction succeeds
all evidence files are complete and internally hashed
classification is not a reproduction or evidence failure
formal state remains unchanged
```

A diagnostic pass does **not** mean:

```text
full 2L/c0 passed
finite-pipe coupling verified
B2 benchmark accepted
compression branch approved
Physical Validation complete
design use accepted
production activation approved
```

## Mandatory formal flags

The generated summary must retain:

```text
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## Stop policy

No tolerance, Contract field, B1 law, production Adapter, solver behavior, or formal state may be changed to obtain a preferred classification. Unexpected checkpoint motion, multiple branches, nonfinite properties, phase departure, reverse flow, loss of subsonic admissibility, or ledger failure is reported directly and stops promotion to the next increment.
