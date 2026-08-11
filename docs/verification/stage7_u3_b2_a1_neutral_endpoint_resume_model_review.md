# Stage 7 U3 B2 A1 neutral-endpoint resume model review

## Status

`MODEL_REVIEW_ONLY / FIXED_BEFORE_RESUME_RESULT`

This increment follows the successful checkpoint and local wave-curve evidence run. It tests one accepted FVM step only. It does not approve a finite compression branch, revise the locked B2 v1 Contract, change the accepted B1 component, modify the production B2 Adapter or `FvmSolver`, introduce a new physics tolerance, or promote any formal project state.

## Authoritative parent evidence

```text
parent evidence source:
5fa69e2b1dff91095ea852057bbe19222b8c68ce

workflow run:
31522368454

job:
93882291625

checkpoint:
336 accepted steps
solver time 0.0022506672049592393 s
outlet pressure 4950034.465962833 Pa
outlet velocity 0.12253662591328077 m/s

classification:
NEUTRAL_ENDPOINT_WITHIN_LOCKED_TOLERANCE

endpoint compatibility residual:
9.284082582577957e-10 kg/s

retained root-mass tolerance:
1.0e-8 kg/s

local positive-side sign-change estimate:
p_P - p_i = 6.280430948341739e-06 Pa
```

The endpoint is outward, subsonic, single-phase liquid, above the B1 back-pressure in stagnation pressure, and closes the retained energy and restriction-reaction ledgers. The exact local continuation root lies a few micro-pascals on the positive-pressure side, but finite compression-wave physics remains unapproved.

## Fixed neutral-endpoint rule

At the reproduced step-336 checkpoint, evaluate the A1 compatibility residual at

```text
p_P = p_i
u_P = u_i
rho_P = rho_i
s_P = s_i
h0_P = h_i + 0.5*u_i^2
```

The endpoint is accepted for this diagnostic only when all of the following hold:

```text
abs(rho_P*u_P*A_pipe - m_dot_B1) <= 1.0e-8 kg/s
u_P >= -1.0e-12 m/s
0 <= Mach_P < 1
phase remains in the locked LIQUID_SMALL_DROP scope
stagnation pressure exceeds B1 back pressure
stagnation h0 round trip passes the locked 1.0e-5 J/kg tolerance
energy/mass decomposition closes under the retained tolerances
restriction-reaction ledger residual <= 1.0e-12 N
```

No sign change is required when the endpoint itself already passes the retained root-mass tolerance. This changes the order in which the existing tolerance is applied; it does not change the tolerance value.

## Local slope check

The retained 1 Pa local residual slope check remains active. Because the endpoint is the upper edge of the currently approved rarefaction domain, the backward 1 Pa stencil is used:

```text
[R(p_i) - R(p_i - 1 Pa)] / 1 Pa < 0
```

No positive-pressure continuation is used to construct the applied FVM flux in this increment.

## One-step execution

The exact B2-10A state after 336 accepted steps is reproduced from the parent numerical source. A new diagnostic-only hook then:

```text
1. accepts the neutral endpoint under the fixed rule above
2. constructs the pipe-side Euler flux
3. applies the existing CFL/mass/energy dt limits
4. advances the existing FvmSolver for exactly one accepted step
5. records the state as solver step 337
```

The pipe-side flux remains:

```text
F_rho   = rho_P*u_P
F_rho_u = rho_P*u_P^2 + p_P
F_rho_E = rho_P*u_P*h0_P
F_rho_xv = 0
```

The B1 downstream stream/pressure port and restriction reaction remain separate diagnostic ledgers.

## Gate conditions

The one-step gate passes only when:

```text
checkpoint reproduction = true
endpoint branch = NEUTRAL_ENDPOINT
endpoint root uses the unchanged retained root tolerance
one accepted step is completed
solver step count becomes 337
step and cumulative mass/momentum/energy residuals pass
rho*xv remains exact zero
outlet velocity remains nonnegative
outlet phase remains liquid
no reverse-flow Guard fires
no dt-halving or at most the already locked maximum occurs
root, h0, energy and reaction ledgers pass
```

## Claim boundary

A pass means only:

```text
The previous step-337 stop was bypassed for one accepted step by applying the already-retained root tolerance at the neutral endpoint before demanding a sign-change bracket.
```

A pass does not mean:

```text
finite compression branch approved
post-endpoint multi-step continuation passed
full 2L/c0 passed
finite-pipe coupling verified
B2 benchmark accepted
Physical Validation complete
design use accepted
production activation approved
```

## Mandatory formal flags

```text
finite_compression_branch_approved = false
post_endpoint_multi_step_passed = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## Stop policy

Any checkpoint mismatch, endpoint residual above the retained limit, nonnegative local slope, B1 failure, reverse direction, supersonic state, phase departure, positivity failure, or conservation/reaction-ledger failure stops the increment. No tolerance or production behavior may be changed to obtain a pass.
