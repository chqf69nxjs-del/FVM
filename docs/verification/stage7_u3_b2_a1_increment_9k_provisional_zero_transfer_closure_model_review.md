# Stage 7 U3 B2 A1 Increment 9K provisional zero-transfer closure

## Status

`MODEL_REVIEW_ONLY / ENGINEERING_PHYSICS_CLOSURE / WORKING_TOOL_PRIORITY / NOT_VERIFICATION`

Increment 9K intentionally changes the project objective after Increment 9J established that the present finite-compression outward-flow compatibility model reaches an unresolved near-zero-flow transition at accepted solver step 637.

The objective is no longer to refine the root search until the final nominal fraction of `2L/c0` can be proven under the existing outward-flow branch. The objective is to retain the evidence for that unresolved transition, declare it a technical issue, and provide a conservative engineering boundary model that allows the transient tool to continue running.

This record does not modify the locked B2 contract, B1 equations, B1 search, production adapter, or FVM core.

## Authoritative starting state

The provisional continuation shall start only from the authoritative Increment 9I state:

```text
parent run: 31670285271
parent job: 94353300958
parent artifact: 9169437776
parent source SHA: c89a992d69c2985fc081fe3750c5b27136d3941e
parent artifact SHA256: ed48b82be9f6cc8d6e081a416ab2b61bd97401782279506d83c8afd4d173f5d3
solver step: 637
solver time: 0.004269583083221582 s
state SHA256: 7d2633e58adcc36e7ea7a1204af95455f5e8942e2c4e9a6dbf76cf437efd2a25
nominal 2L/c0 target: 0.004285834855172021 s
```

Increment 9J subsequently classified the unresolved transition as:

```text
ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE
```

That result remains authoritative evidence that the previous outward-flow model is not approved beyond step 637. Increment 9K does not reinterpret it as a successful zero-flow root.

## Technical issue

The unresolved item is declared as:

```text
TECHNICAL_ISSUE_A1_NEAR_ZERO_FLOW_BRANCH_TRANSITION
```

The present outward-flow Hugoniot/B1 compatibility construction does not supply an approved state-transition rule when the admissible outward root disappears near zero transfer. The project will not spend additional effort increasing the fixed 4097/513 diagnostic search resolution for the purpose of recovering the last nominal horizon fraction.

The following remain unresolved physics/modeling topics:

```text
outward-flow -> zero-transfer transition criterion
open-orifice versus non-return-device interpretation
zero-transfer hold duration
zero-transfer -> outward-flow re-entry
reverse-flow model
transition hysteresis/chatter control
pressure-wave reflection introduced by closure
physical validation of the closure event
```

They are retained as technical debt rather than blockers for the working tool.

## Provisional physical model

Increment 9K adopts a **one-way discharge / non-return closure** interpretation for the unresolved transition.

At the authoritative step-637 state, the existing outward-flow branch is considered exhausted for this trajectory. The boundary transitions once to:

```text
ZERO_TRANSFER_CLOSED
```

and remains in that branch through the short remaining nominal `2L/c0` segment. Re-opening and reverse flow are explicitly outside Increment 9K.

The right external-face flux is defined from the adjacent interior static pressure `p_i` as:

```text
F_rho     = 0
F_rho_u   = p_i
F_rho_E   = 0
F_rho_xv  = 0
```

This is the same conservative wall/zero-transfer flux form already present in the locked B2 closed and zero-drop identities, but Increment 9K applies it under a new engineering transition model. Therefore its use here is not a claim that the locked B2 benchmark has passed.

### Physical interpretation

The model represents a discharge path that permits outward transfer while the outward branch is supported, but closes when that branch is no longer available. Once closed:

- no mass crosses the outlet,
- no advected energy crosses the outlet,
- no vapor scalar crosses the outlet,
- the fluid receives only the normal pressure traction represented by the interior wall identity,
- external reservoir pressure is carried mechanically by the closure device rather than imposed as an inflow state on the modeled fluid.

This intentionally avoids inventing an unverified reverse-flow solution.

## Numerical rules

The provisional closure shall:

```text
use the unchanged FvmSolver
use the unchanged CoolProp single-phase EOS path
use baseline 32 cells and CFL = 0.1
use ordinary CFL time-step selection
clip the final step exactly to the nominal 2L/c0 target
retain the solver's atomic trial/halving mechanism
construct no B1 state after the closure transition
construct no Hugoniot root after the closure transition
```

Because mass and energy transfer are zero, B2 mass-removal and energy-removal limits are not active in the closure branch.

## Per-step engineering gates

Every accepted closure step shall require:

```text
accepted dt > 0
finite conserved state
rho > 0 everywhere
internal energy > 0 everywhere
rho*xv exact zero everywhere
adjacent outlet state remains normalized liquid
right-face mass flux exact zero
right-face energy flux exact zero
right-face vapor flux exact zero
right-face momentum flux equals reconstructed interior static pressure
step mass conservation residual within retained B2 tolerance
step energy conservation residual within retained B2 tolerance
```

Reverse outlet velocity after closure is diagnostic information, not an automatic failure, because a rigid/non-return closure can reflect the incident acoustic disturbance. It shall not be used to create reverse mass transfer.

## Working-tool success criterion

Increment 9K is successful as an engineering working slice only if:

```text
step-637 authoritative state is reproduced exactly
closure branch is selected explicitly
at least one actual FvmSolver step is executed
nominal 2L/c0 target is reached without extrapolation
the final step is target-clipped
all closure per-step engineering gates pass
state remains finite, positive, single-phase liquid, and rho*xv exact zero
no mass/energy/vapor transfer occurs after closure
```

A successful result may be described only as:

```text
PROVISIONAL ENGINEERING WORKING SLICE
```

It may not be described as `VERIFIED`, `ACCEPTED`, `VALIDATED`, or `APPROVED`.

## Formal-state boundary

Regardless of whether Increment 9K reaches the target, retain:

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

A separate future model/contract is required before any of those states may change.
