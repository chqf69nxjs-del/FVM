# Stage 7 U3 B2 A1 finite-compression Increment 9I dynamic-seeded final-horizon review

## Status

`MODEL_REVIEW_ONLY / FINAL_NOMINAL_2L_OVER_C0_ATTEMPT / DYNAMIC_SEEDED_ADMISSIBLE_ISLAND / FIXED_BEFORE_EXECUTION_RESULT`

Increment 9I continues the corrected general-EOS Hugoniot finite-compression path from the authoritative Increment 9H accepted state at solver step 636 and attempts the remaining nominal horizon to `2L/c0`.

It does not change B1, local candidate admissibility, the Hugoniot relation, the root tolerance, the finite-compression `chi` cap, the locked B2 Contract, the production Adapter, `FvmSolver`, or any formal project state.

## Authoritative parent

```text
source Git SHA:
8e2825d0a6708dd287276181eee55f9459b04ce1

workflow run:
31669680994

job:
94351542532

artifact:
9169230736

artifact name:
u3-b2-a1-finite-compression-increment-9h-rerun-31669680994

artifact SHA256:
a627e2b1720429f79fd80699cb117ddc74c7b931d78c482c27aee98933ece42b

outcome:
FINITE_COMPRESSION_INCREMENT_9H_SEEDED_ISLAND_ONE_STEP_PASS

accepted state:
solver step 636
solver time 0.004262873917468169 s
```

The parent one-step evidence records exact root-authority reproduction, one accepted actual `FvmSolver` update, no halving, liquid and outward subsonic outlet state, positive density and internal energy, exact-zero `rho*xv`, and retained mass, momentum and energy closure.

## Fixed target

```text
nominal target:
2L/c0 = 0.004285834855172021 s

starting time:
0.004262873917468169 s

remaining nominal time:
0.00002296093770385166 s

maximum operational solver step:
650
```

The final update uses:

```text
requested_dt = min(CFL candidate dt, target time - current time)
```

and must be clipped to the target within `8 * spacing(target time)`.

## Dynamic seeded interval

Before every requested update, reconstruct the current accepted outlet state and derive a deterministic seed from the previous accepted root pressure:

```text
seed_chi =
(previous_root_pressure - current_outlet_static_pressure)
/
(current_outlet_density * current_outlet_sound_speed^2)
```

Require:

```text
1.0e-6 < seed_chi < 1.0e-4
```

Then fix the requested diagnostic interval for that step as:

```text
lower_chi = max(1.0e-6, 0.70 * seed_chi)
upper_chi = min(1.0e-4, 1.60 * seed_chi)
```

Evaluate exactly 257 equally spaced requested `chi` values including both endpoints.

This interval rule, factors and point count are fixed before all Increment 9I results.

## Candidate categories

Every candidate belongs to exactly one category:

```text
ADMISSIBLE_SUCCESS:
  B1 evaluation succeeds
  local_candidate_admissible = true

EXCLUDED_B1_UNAVAILABLE:
  B1 evaluation fails with exactly:
  - REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
  - NONPOSITIVE_KINETIC_ENERGY_HEAD

EXCLUDED_LOCAL_INADMISSIBLE:
  B1 evaluation succeeds
  local_candidate_admissible = false
```

Any other outcome is fail-closed.

Excluded states may not be root-topology members, compatibility-root endpoints or applied flux states.

## Island and root construction

Require exactly one contiguous `ADMISSIBLE_SUCCESS` island containing at least two seeded nodes and at least one excluded seeded node on each side.

Refine both categorical boundaries for exactly 48 logical iterations. Evaluate candidates while a strictly interior binary64 midpoint exists. Once the endpoints become adjacent representable values, retain them unchanged for the remaining logical iterations with `FLOAT_RESOLUTION_HOLD` evidence. No tolerance is added.

Construct root topology only from:

```text
final refined lower admissible endpoint
all seeded ADMISSIBLE_SUCCESS nodes inside the island
final refined upper admissible endpoint
```

Sort by requested `chi`, remove duplicate coordinates, and require:

```text
strictly increasing requested chi
monotone nonincreasing compatibility residual
exactly one sign-change bracket
```

Use the unchanged compatibility-root solver and all existing Hugoniot, identity-accounted, B1, Lax, entropy, direction, phase, stagnation-pressure, energy and reaction-ledger gates.

## Per-step pass gate

Every accepted step must satisfy:

```text
branch = FINITE_COMPRESSION_HUGONIOT
seed chi and dynamic interval inside fixed finite-compression scope
exactly one admissible island
both island boundaries retain excluded/admissible invariants
one monotone root topology
one compatibility root bracket
selected root gate passed
1.0e-6 < root chi <= 1.0e-4
absolute root residual <= 1.0e-8 kg/s
negative root slope
accepted dt > 0
finite conserved state
positive density and internal energy
no reverse-flow Guard
no reverse velocity
outward subsonic liquid outlet
rho*xv exact zero
step and cumulative mass, momentum and energy closure
no excluded state used as root endpoint or flux
```

The accepted branch sequence must have zero transitions and no fixed chatter pattern.

## Full-horizon pass gate

A pass requires:

```text
parent authority verified
at least one accepted actual step
all per-step gates pass
no stop classification or reason
final step clipped to target
final time reaches target within roundoff allowance
horizon fraction >= 1.0
final state remains finite, positive, outward, subsonic and liquid
rho*xv remains exact zero
```

## Pass outcome

```text
FINITE_COMPRESSION_INCREMENT_9I_DYNAMIC_SEEDED_FULL_HORIZON_WORKING_SLICE_PASS
```

A pass establishes only a corrected MODEL_REVIEW working vertical slice to nominal `2L/c0`.

## Formal-state boundary

Regardless of result, retain:

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
