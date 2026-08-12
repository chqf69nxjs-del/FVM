# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4 full-horizon model review

## Status

`MODEL_REVIEW_ONLY / WORKING_VERTICAL_SLICE / FIXED_BEFORE_EXECUTION_RESULT`

This increment continues the accepted branch-aware A1 boundary from the authoritative Increment 3 state to the nominal acoustic horizon `2L/c0`.

The objective is a working vertical slice: demonstrate that B2-10A can run end to end through the full requested horizon without a clear numerical, conservation, direction, phase-scope, root-topology, or model-scope failure.

This increment does not modify the Weak Compression approximation, the retained root tolerance, the fixed `chi` scope, B1, the locked B2 v1 Contract, the production B2 Adapter, or `FvmSolver`. It does not verify finite-pipe coupling, accept a benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative parent evidence

```text
parent source Git SHA:
00a410127c10d5c2fa2f79c7471daa8f896a0e76

Increment 3 corrected rerun workflow:
31605175607

job:
94142164951

artifact:
9144936292

artifact SHA256:
eaaf54b9012ed2748c1e0d425a238915a030c497517a6651f7f916a8b09ecaf6

parent outcome:
WEAK_COMPRESSION_INCREMENT_3_32_STEP_PASS

parent solver step:
337 -> 369

parent solver time:
0.0022573740768004596 -> 0.0024719939763977834 s

parent branch counts:
WEAK_COMPRESSION = 32
NEUTRAL_ENDPOINT = 0
RAREFACTION = 0

parent maximum Weak Compression chi:
1.1714809908599291e-9

parent maximum absolute root residual:
9.649011277479413e-9 kg/s

parent maximum halving count:
0

parent final outlet pressure:
4,950,034.221792596 Pa

parent final outlet velocity:
+0.12253493979845538 m/s
```

The parent artifact contains the exact step-369 conserved state, solver time, step rows, root rows, branch history, cumulative conservation residuals, and an internal SHA256 manifest.

## Fixed start-state rule

Increment 4 starts from the parent artifact, not from a re-derived or manually transcribed state.

Before execution, the workflow and diagnostic must verify:

```text
artifact ID and GitHub artifact digest
parent source Git SHA
parent workflow/job/artifact identifiers
parent outcome and gate status
parent solver step = 369
parent final solver time
32 parent accepted rows
parent final state shape = (32, 4)
finite conserved state
positive density
exact rho*xv = 0
internal artifact manifest
```

The current inventory and the parent cumulative residuals are used to reconstruct the cumulative expected finite-volume inventory change at step 369. Conservation accounting then continues without resetting the ledger.

## Fixed horizon

Use the unchanged B2-10A baseline geometry and initial single-phase state.

```text
cells:
32

CFL:
0.10

horizon definition:
2 * pipe_length_m / initial_sound_speed_m_s

target 2L/c0:
0.004285834855172021 s

starting solver step:
369

starting solver time:
0.0024719939763977834 s

maximum operational solver step:
10000
```

For each step, calculate the normal solver candidate dt and clip only the final-horizon request:

```text
candidate_dt = min(computed_dt, target_time - current_time)
```

Existing deterministic dt halving remains active. If an accepted dt is smaller than the clipped candidate, continue until the target is reached or a fail-closed stop occurs.

## Fixed branch model

Use the same three accepted branches as Increment 3:

```text
RAREFACTION
NEUTRAL_ENDPOINT
WEAK_COMPRESSION
```

Use the same fail-closed classification:

```text
FINITE_COMPRESSION_MODEL_REQUIRED
```

At every candidate step, retain the full Increment 3 classification order and topology review:

```text
neutral endpoint first
approved connected rarefaction scan
corrected positive-pressure chi-scoped scan
complete in-scope sign-change count
first admissible sign-change bracket
bisection
root completion and ledgers
```

The requested positive scan coordinate remains authoritative for the `chi` scope, while the representable absolute pressure remains authoritative for EOS, B1, flux, root, and ledger calculations. Both requested and realized coordinates remain recorded.

No performance shortcut, branch prediction, or reduced topology-audit cadence is introduced in this increment. The short-run branch logic is reused directly because the measured Increment 3 execution cost is acceptable for the remaining horizon.

## Retained numerical limits

```text
root mass residual absolute tolerance:
1.0e-8 kg/s

Weak Compression scope:
0 < chi <= 1.0e-6

positive-pressure bisection maximum:
32 iterations

clear branch chatter:
five consecutive accepted classifications A-B-A-B-A, A != B

finite-compression approval:
false
```

No tolerance is relaxed or added.

## Pipe-side flux and reaction ledger

For every accepted branch, use only the pipe-side Euler flux:

```text
F_rho    = rho_P u_P
F_rho_u  = rho_P u_P^2 + p_P
F_rho_E  = rho_P u_P h0_P
F_rho_xv = 0
```

Keep the B1 downstream stream-plus-pressure port separate:

```text
Pi_E = m_dot_B1 u_eff + p_d A_open
```

Retain the restriction reaction ledger:

```text
Pi_P = m_dot_P u_P + p_P A_pipe
R_w  = Pi_E - Pi_P
```

`Pi_E` must not replace the pipe-side momentum flux.

## Per-step acceptance gate

Every accepted continuation row must satisfy the complete Increment 3 per-step gate:

```text
branch in {RAREFACTION, NEUTRAL_ENDPOINT, WEAK_COMPRESSION}
accepted solver step count increments by one
accepted dt > 0
root topology and branch-specific checks pass
abs(root mass residual) <= 1.0e-8 kg/s
root velocity >= 0
0 <= root Mach < 1
allowed single-phase liquid
B1 success
stagnation-enthalpy round trip passed
energy/mass decomposition passed
energy-port closure passed
restriction-reaction ledger closure passed
conserved state finite
positive density
positive internal energy
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
no CLEAR_BRANCH_CHATTER
```

For `WEAK_COMPRESSION`, additionally require:

```text
exactly one admissible positive-pressure sign-change bracket
0 < chi <= 1.0e-6
p_P > p_i
```

For `RAREFACTION`, additionally require:

```text
exactly one approved connected rarefaction root
p_P < p_i
```

For `NEUTRAL_ENDPOINT`, additionally require:

```text
abs(R(p_i)) <= 1.0e-8 kg/s
p_P = p_i
```

## Full-horizon working-slice gate

The Increment 4 working vertical slice passes only when:

```text
parent Increment 3 artifact is fully verified
solver reaches the exact clipped target 2L/c0
all continuation rows pass
no fail-closed stop occurs
no multiple root occurs
no branch jump occurs
no CLEAR_BRANCH_CHATTER occurs
Weak Compression remains inside fixed chi scope whenever selected
all phase, direction, positivity, conservation, energy, and reaction checks pass
formal state flags remain false
```

The successful outcome is:

```text
WEAK_COMPRESSION_INCREMENT_4_FULL_HORIZON_WORKING_SLICE_PASS
```

This is a MODEL_REVIEW working-slice result. It is deliberately distinct from formal verification or validation.

## Required evidence

Retain at minimum:

```text
source and parent Git SHAs
parent workflow/job/artifact/digest
parent artifact verification report
start and target solver times
one row per continuation step
one root row per continuation step
local wave scans and positive-pressure scans
branch transitions and branch counts
requested and realized positive scan coordinates
root pressure offset, chi, residual, slope, Mach, velocity, phase, and B1 outcome
pipe-side flux, downstream port, reaction, and energy ledgers
computed dt, clipped candidate dt, removal limits, accepted dt, halvings, and trial dts
five pressure/velocity probe series
step and cumulative mass/momentum/energy residuals
start and final conserved arrays
exact horizon result or stop classification
formal flags
```

The acoustic probe series are observation-only. This increment does not claim direct/reflected acoustic timing validation.

## Immediate stop conditions

```text
parent artifact mismatch
parent state or ledger reconstruction failure
endpoint evaluation failure
non-monotone connected rarefaction scan
no root
multiple roots
branch jump
positive root beyond fixed chi scope
FINITE_COMPRESSION_MODEL_REQUIRED
CLEAR_BRANCH_CHATTER
root residual outside retained tolerance
reverse root velocity
root subsonic departure
phase-scope departure
EOS or B1 failure
energy or reaction-ledger failure
nonfinite state
positivity failure after existing halvings
reverse outlet velocity
rho*xv identity failure
step or cumulative mass/momentum/energy closure failure
non-positive horizon dt
operational step cap exceeded
unexpected source or branch movement
```

## Formal state

A passing Increment 4 establishes only:

```text
working_vertical_slice_two_l_over_c0_passed = true
```

It does not promote the formal B2 state. The following remain false:

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

Follow-on verification and model refinement must be prioritized from the completed working-slice evidence rather than assumed in advance.
