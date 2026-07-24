# Stage 7 — Repeated First-Crossing Case A/B Freeze

## Status

`IMPLEMENTED DRAFT; REPEATED SHORT-RUN SOFTWARE VERIFICATION; REVIEW REQUIRED`

This increment follows merged PR #71. PR #71 established the complete projected
crossing chain for one fixed first-order step. This increment adds the repeatability
and matched-control gate required before the first liquid-to-two-phase Case A and
Case B may be frozen.

Base:

```text
main: ceaba980e5e7f7305424df8bd1e9e6b4f1acfe40
PR #70: raw one-step liquid-to-open-two-phase crossing observation
PR #71: projected one-step accepted crossing path
```

## Objective

Run the fixed strong crossing candidate repeatedly until the first accepted
crossing, stop at that point, and run the fixed liquid control to the same physical
time. Freeze Case A and Case B only if repeated executions produce identical
software evidence.

```text
Case A:
5 MPa / 5 K subcooling -> 2 MPa / 5 K subcooling

Case B:
5 MPa / 5 K subcooling -> 4 MPa / 5 K subcooling
```

The moderate `5 MPa -> 3 MPa` case remains supporting evidence and is not part of
the first formal Case A/B pair.

## Fixed numerical settings

The numerical and thermodynamic settings remain unchanged from PRs #70–#71:

```text
cells:                 8
pipe length:           1.0 m
pipe diameter:         0.10 m
initial interface:     between cells 3 and 4
initial velocity:      0 m/s
initial transported q: 0 exactly
CFL limit:             0.20
Rusanov flux:          existing implementation
boundaries:            transmissive
physical source:       none
phase projection:      existing HEMEquilibriumQualityProjection
accepted-state EOS:    existing VerificationHEMLiquidOpenTwoPhaseEOS
```

No case parameter, algorithm, tolerance, or acceptance threshold may be adjusted
after observing the result.

## Execution contract

### Case A

For every step:

```text
accepted state at step start
        |
        v
existing CFL calculation
        |
        v
existing FvmSolver.step() with NoPhaseChange
        |
        v
raw rho/e transition classification
        |
        v
existing equilibrium-quality projection
        |
        v
mixed liquid/open-two-phase accepted-state EOS
        |
        v
fresh second projection required to be a no-op
```

The Case A run stops immediately after the first accepted
`LIQUID_TO_TWO_PHASE_CROSSING`.

The current safety limit is:

```text
maximum Case A steps: 8
```

Reaching the limit without an accepted crossing is a failed freeze attempt, not a
reason to tune the case.

### Case B

Case B uses the same geometry, mesh, flux, CFL limit, boundaries, source policy,
projection, EOS, and tolerances. It is advanced to the exact physical time at
which Case A first crossed.

The final control step may be shortened by the existing
`compute_dt(t_end=...)` path. This preserves the same CFL upper bound while
matching the physical-time horizon exactly.

Case B must remain:

```text
LIQUID_CANDIDATE in every cell
no raw crossing event
first projection no-op
second projection no-op
zero projection vapor source
```

## Repeatability

Each case is reconstructed from the same canonical liquid candidates and executed
three times in fresh solver/EOS instances.

```text
repeat_count = 3
```

A canonical SHA-256 repeatability signature includes:

```text
outcome
step count
final physical time
crossing step and time
crossing cells
projection cells
maximum crossing q_eq
cumulative projection vapor source
final conservative-state hash
mass, momentum, energy, and phase-vapor residuals
```

The repeat index is deliberately excluded from the signature.

Repeatability requires all three signatures for a case to be identical.

## Case A freeze criteria

Case A is frozen only when every repeat satisfies:

```text
all initial cells are LIQUID_CANDIDATE
first accepted crossing is reached within the fixed step limit
no saturated-liquid endpoint landing
no forbidden transition
crossing q_eq >= 1e-6 test-evidence threshold
crossing cells = first projection cells
post q = q_eq
post mixed accepted-state EOS succeeds
post pressure, temperature, and sound speed are finite and positive
second projection is a no-op
mass, momentum, and energy boundary budgets close
phase-vapor budget closes
repeatability signatures are identical
```

The `1e-6` crossing threshold remains test evidence only. It is not a solver,
EOS, phase-classifier, or projection switch.

## Case B freeze criteria

Case B is frozen only when every repeat satisfies:

```text
final time matches the Case A crossing time
all cells remain LIQUID_CANDIDATE
no crossing event
first and second projections are no-ops
projection vapor source = 0
accepted-state EOS succeeds
mass, momentum, energy, and phase-vapor budgets close
repeatability signatures are identical
```

## Verification meaning

If both cases freeze, the increment may set:

```text
case_a_frozen = true
case_b_frozen = true
actual_first_order_fvm_crossing_verified = true
```

This flag means a deterministic software verification case has been established
for the existing first-order FVM and reviewed HEM path.

It does not mean:

```text
physical Validation
experimental agreement
design-use acceptance
approved two-phase acoustic accuracy
production HEM activation
long-duration pipeline depressurization approval
```

## Budget policy

The existing boundary budget tracks external flux contributions. A separate
`PhaseChangeBudgetTracker` tracks every projection-induced vapor source.

At the final accepted state:

```text
mass/momentum/energy inventory
=
initial inventory + boundary contribution + residual

vapor inventory
=
initial vapor
+ boundary vapor contribution
+ cumulative projection source
+ residual
```

No projection source is counted twice.

Fixed absolute tolerances:

```text
mass/momentum/energy residual: 1e-9
phase-vapor residual:          1e-12 kg
physical-time match:           1e-15 s
```

## Implementation

```text
src/liquid_gas_transient/
  hem_liquid_to_two_phase_first_crossing_case_ab.py
```

The runner reuses:

```text
run_liquid_state_pair_survey
build_piecewise_liquid_initial_state
FvmSolver
detect_raw_transition_events
run_one_projected_fvm_case
HEMEquilibriumQualityProjection
VerificationHEMLiquidOpenTwoPhaseEOS
PhaseChangeBudgetTracker
```

Existing implementation files are not modified.

## Test plan

Dependency-free tests cover:

- invalid Case A/B and repeatability configurations;
- deterministic state hashing;
- successful freeze decision from repeated fake records;
- Case A signature mismatch;
- unmatched Case B physical time;
- control crossing rejection;
- artifact and approval flags.

The installed-CoolProp test must execute without a skip and verify:

```text
Case A repeats: 3 accepted crossings
Case A crossing step: 1
Case A crossing cells: 3, 4
Case A signatures: identical
Case B repeats: 3 matched all-liquid runs
Case B final time: exact Case A crossing time
Case B projection source: zero
Case B signatures: identical
Case A/B frozen: true
software first-order crossing verified: true
```

## Artifacts

The runner writes:

```text
stage7_lco2_hem_first_crossing_case_ab.json
stage7_lco2_hem_first_crossing_case_ab_runs.csv
stage7_lco2_hem_first_crossing_case_ab_steps.csv
stage7_lco2_hem_first_crossing_case_ab_cells.csv
stage7_lco2_hem_first_crossing_case_ab.md
stage7_lco2_hem_first_crossing_case_ab.npz
```

## Completion criteria

The increment is review-ready when:

```text
source compiles
git diff --check is clean
focused tests pass with zero skips
installed-CoolProp repeatability test executes
related Stage 7 HEM tests pass
full repository tests pass
fixed Case A/B runner completes
all evidence flags are internally consistent
Case A/B freeze criteria pass
temporary validation workflow is removed
all permanent workflows pass on the final head
final diff contains only the runner, tests, and verification documents
```

## Approval boundary

```text
verification_only = true
case_a_frozen = result-dependent
case_b_frozen = result-dependent
actual_first_order_fvm_crossing_verified = result-dependent
algorithms_or_tolerances_tuned = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Next increment after successful merge

After Case A/B freeze:

1. synchronize PRs #70–#72 into the central verification index and execution log;
2. define the next pipeline-depressurization prototype gate separately;
3. retain the frozen first-order Case A/B pair as the regression control;
4. do not expand to production use until physical Validation and acoustic accuracy
   are separately established.
