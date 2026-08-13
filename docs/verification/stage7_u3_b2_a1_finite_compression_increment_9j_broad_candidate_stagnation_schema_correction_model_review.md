# Stage 7 U3 B2 A1 Increment 9J broad-candidate stagnation schema correction

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_SCHEMA_CORRECTION_ONLY / NO_SOLVER_ADVANCE`

This record corrects a diagnostic schema defect discovered only after the Increment 9J parent-authority binding had been repaired. It does not change the fixed Increment 9J root/endpoint question, the Hugoniot model, B1, the production B2 Adapter, `FvmSolver`, the locked B2 Contract, a tolerance, or a `chi` bound.

The authoritative Increment 9J method remains:

`docs/verification/stage7_u3_b2_a1_finite_compression_increment_9j_zero_flow_endpoint_diagnostic_model_review.md`

The parent-authority correction remains:

`docs/verification/stage7_u3_b2_a1_finite_compression_increment_9j_parent_authority_binding_correction_model_review.md`

## Failed corrected-authority run

```text
workflow run:
31675938522

job:
94370412069

source Git SHA:
6b554899b7b7d1147de3bef99a952f7a9ca23b3b

parent authority verification:
PASS

failure location:
Increment 9J broad endpoint scan

exception:
KeyError: 'stagnation_pressure_pa'

FvmSolver step 638 attempted:
no

authoritative Increment 9J outcome produced:
no
```

The checkout identity, fixed dependency versions, parent workflow run, parent job, parent artifact, parent source SHA, GitHub artifact digest, and internal parent manifest all passed before the diagnostic began. The failure is therefore classified as:

```text
implementation / bookkeeping defect
```

It is not evidence of:

```text
physical branch termination
no admissible compatibility root
multiple roots
phase departure
positivity failure
conservation failure
```

No partial ultrafine or broad result from the failed process is authoritative because the diagnostic did not write a complete evidence set.

## Root cause

The general-EOS Hugoniot candidate evaluation constructs the candidate static thermodynamic state before invoking the B2 Adapter. Therefore an expected excluded candidate can still retain finite values for:

```text
pressure
density
internal energy
enthalpy
entropy
sound speed
phase
velocity
Mach number
```

The B2 Adapter intentionally applies the locked reverse-velocity Guard before adjacent/stagnation reconstruction. Consequently a candidate classified as:

```text
EXCLUDED_B1_UNAVAILABLE
```

can correctly omit the successful-face field:

```text
stagnation_pressure_pa
```

Increment 9J then attempted to calculate the broad scalar margin from that absent field for every broad-scan row. The defect is a mismatch between two legitimate schemas:

```text
successful B1 face row
versus
excluded Hugoniot candidate row
```

The B1 Guard itself is not defective and must remain unchanged.

## Limited diagnostic correction

Only for the two fixed Increment 9J scalar-endpoint activities:

```text
513-node broad endpoint scan
stagnation-pressure / velocity scalar bisection
```

an expected excluded candidate lacking `stagnation_pressure_pa` may receive a diagnostic-only candidate stagnation reconstruction.

The reconstruction shall use the same production-side property path fixed by the locked B2 Contract:

```text
candidate conserved state
  rho
  rho*u
  rho*(e + 0.5*u^2)
  rho*xv = 0

CoolPropB2StateProvider.reconstruct_from_conserved
  Dmass,Umass -> candidate static state
  h0 = h + 0.5*u^2
  s0 = s
  Hmass,Smass -> candidate p0,T0
```

The locked checks remain mandatory:

```text
finite and positive density/internal energy
allowed single-phase liquid classification
stagnation enthalpy round-trip absolute <= locked B2 tolerance
stagnation entropy round-trip absolute <= locked B2 tolerance
```

No new pressure, velocity, mass-rate, or root tolerance is introduced.

## Schema semantics

For a row whose successful B1 face already contains `stagnation_pressure_pa`:

```text
retain the existing field unchanged
source = B1_FACE_RECONSTRUCTION
schema_completed = false
```

For an expected excluded candidate whose static Hugoniot state is available but whose face field is absent:

```text
populate the scalar-diagnostic p0 from the candidate conserved state
source = CANDIDATE_CONSERVED_COOLPROP_RECONSTRUCTION
schema_completed = true
```

The correction must not alter:

```text
evaluation_succeeded
formal_outcome
formal_message
local_candidate_admissible
compatibility_residual_kg_s
candidate velocity
candidate phase
candidate Hugoniot state
```

Any unexpected candidate category, missing candidate thermodynamic field, failed reconstruction, nonfinite result, phase mismatch, or locked round-trip failure remains fail-closed.

## Critical separation from root and flux authority

The diagnostic candidate stagnation reconstruction is permitted only for scalar topology around the zero-transfer locus.

It is not:

```text
a B1 success
a locally admissible compatibility-root state
a compatibility-root bracket endpoint
a selected compatibility root
a boundary flux state
a zero-flow branch implementation
a solver-step authorization
```

The unchanged compatibility-root topology continues to use only:

```text
ADMISSIBLE_SUCCESS
```

rows. A B1-unavailable row must never populate `selected_root`, construct a flux, mutate the conserved state, or advance `FvmSolver`.

An excluded candidate may only show on which side of the independently diagnosed scalar zero-flow locus the unchanged Hugoniot characteristic lies. Even when Increment 9J supports zero-flow branch review, the selected scalar locus is evidence for a later branch-model review, not an approved root or usable boundary state.

## Required correction evidence

The rerun shall record at minimum:

```text
failed run/job and exception classification
original Increment 9J and authority-correction spec identities
number of 513 broad rows
number retaining B1-face p0
number receiving diagnostic candidate p0
candidate classifications receiving completion
completion counts by evaluation stage
stagnation reconstruction source per broad row
locked round-trip residuals for completed rows
confirmation that success/admissibility/residual fields were unchanged
confirmation that compatibility-root topology used only admissible rows
confirmation that no excluded row became selected_root or flux
confirmation that step 638 was not attempted
confirmation that the step-637 conserved state remained unchanged
```

## Rerun decision rule

After this schema-only correction, retain the original three-way project decision:

1. `ULTRAFINE_ADMISSIBLE_ISLAND_WITH_UNIQUE_ROOT_SUPPORTED`  
   supports a separately fixed one-step continuation review.
2. `ZERO_FLOW_ENDPOINT_WITHIN_COMPATIBILITY_TOLERANCE_SUPPORTED_FOR_BRANCH_REVIEW`  
   supports a separately fixed zero-flow branch review, beginning with one step only.
3. Any other result  
   remains fail-closed and supports scope limitation rather than further automatic scan refinement.

No 4097-node or 513-node count may be increased automatically after this correction.

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
