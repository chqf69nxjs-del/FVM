# Stage 7 — Projected Liquid-to-Two-Phase FVM Dry Run

## Status

`IMPLEMENTED DRAFT; PROJECTION/POST-STATE VERIFICATION ONLY; REVIEW REQUIRED`

This increment follows merged PR #70. PR #70 established one actual first-order
Rusanov/CFL step from three all-liquid state pairs and observed raw liquid-to-open-two-phase
transitions in the strong and moderate cases while the nearest pressure-span control
remained liquid.

Base:

```text
main: 38e841af97ac0adbebf42dbe36a17c1edc6c5246
PR #70: raw one-step first-order FVM crossing observation
```

## Objective

Complete the next narrow verification chain without changing numerical or thermodynamic
algorithms:

```text
raw post-FVM rho/e state
        |
        v
HEMEquilibriumQualityProjection
        |
        v
synchronized liquid/open-two-phase accepted state
        |
        v
VerificationHEMLiquidOpenTwoPhaseEOS
        |
        v
second projection must be a no-op
        |
        v
projection vapor-mass budget closure
```

The increment must answer four questions:

1. Do first-projection cells match the raw liquid-to-two-phase crossing cells?
2. Can the projected state be recovered by the strict mixed accepted-state EOS?
3. Is a second projection an exact no-op under the existing activation tolerance?
4. Is the projected vapor inventory counted exactly once as a phase-change source?

## Fixed numerical matrix

The raw states are regenerated through the merged PR #70 runner. No case condition is
changed.

```text
cells:              8
pipe length:        1.0 m
pipe diameter:      0.10 m
interface:          between cells 3 and 4
initial velocity:   0 m/s
initial q:          0 exactly
CFL:                0.20
boundaries:         transmissive
physical source:    none
raw FVM steps:      exactly 1
```

Cases:

```text
strong:   5 MPa / 5 K subcooling -> 2 MPa / 5 K subcooling
moderate: 5 MPa / 5 K subcooling -> 3 MPa / 5 K subcooling
control:  5 MPa / 5 K subcooling -> 4 MPa / 5 K subcooling
```

## Existing algorithms reused unchanged

```text
FvmSolver.step
first-order Rusanov flux
existing CFL calculation
transmissive ghost-cell boundaries
CoolProp rho/e phase evaluation
HEMLiquidToTwoPhase transition classifier
HEMEquilibriumQualityProjection
VerificationHEMLiquidOpenTwoPhaseEOS
PhaseChangeBudgetTracker
```

No new runtime phase switch, clipping, endpoint fallback, acoustic formula, or solver
threshold is introduced.

## Tolerances

Existing values are retained:

```text
projection activation:
    HEMEquilibriumQualitySyncConfig.activation_tolerance = 1e-12

accepted-state quality tolerance:
    1e-10, matching the merged mixed-EOS contract
```

The projection-vapor budget uses a verification-only absolute residual check of `1e-12 kg`.
This value does not affect the solver, EOS, projection, phase classifier, or acoustic path.

## Per-case processing

For each PR #70 raw case:

1. retain the initial and raw conservative arrays;
2. retain the raw transition and region evidence;
3. apply `HEMEquilibriumQualityProjection` to the raw state;
4. require mass, momentum, and total energy to remain bitwise unchanged;
5. require first-projection cell indices to equal raw crossing cell indices;
6. require the all-liquid control to remain a first-projection no-op;
7. recover primitives through `VerificationHEMLiquidOpenTwoPhaseEOS`;
8. require post-projection regions to equal the raw thermodynamic regions;
9. require finite positive post pressure, temperature, and sound speed;
10. apply a fresh second projection;
11. require zero second-projection cells and bitwise-identical conservative state;
12. record the projection vapor source and close the projection-only and combined budgets.

## Accepted outcomes

### Crossing cases

```text
raw outcome:                  OPEN_TWO_PHASE
first projection cells:      exactly raw crossing cells
post EOS:                    accepted liquid/open-two-phase array
second projection:           no-op
projected vapor source:      positive
budget residual:             within verification tolerance
result:                      ACCEPTED_CROSSING
```

### Negative control

```text
raw outcome:                  ALL_LIQUID
first projection cells:      none
post EOS:                    all liquid accepted array
second projection:           no-op
projected vapor source:      zero
budget residual:             within verification tolerance
result:                      ACCEPTED_ALL_LIQUID_NOOP
```

## Vapor accounting

The raw FVM step and projection are kept distinct.

```text
initial vapor inventory
+ raw external-boundary vapor contribution
= raw vapor inventory

raw vapor inventory
+ projection vapor source
= post-projection vapor inventory
```

The projection source is checked in two independent forms:

```text
PhaseChangeBudgetTracker last source
sum(delta rho*q) * dx * area
```

The two values must agree within `1e-12 kg`. The projection source is not also recorded as a
boundary contribution, physical source, or energy source.

## Failure policy

The complete case fails if any of the following occurs:

```text
raw endpoint, forbidden, guard, or backend outcome
projection cells differ from crossing cells
control projection activates
projection changes rho, rho*u, or rho*E
post EOS rejects the synchronized state
post region differs from raw thermodynamic region
post pressure, temperature, or sound speed is non-finite/non-positive
second projection activates or changes state
projection source is counted inconsistently
vapor budget does not close
```

No result-dependent tolerance adjustment is allowed.

## Source and test files

```text
src/liquid_gas_transient/
  hem_liquid_to_two_phase_projected_fvm_dry_run.py

tests/
  test_stage7_lco2_hem_liquid_to_two_phase_projected_fvm_dry_run.py
```

The runner writes:

```text
stage7_lco2_hem_projected_fvm_dry_run.json
stage7_lco2_hem_projected_fvm_dry_run_cases.csv
stage7_lco2_hem_projected_fvm_dry_run_cells.csv
stage7_lco2_hem_projected_fvm_dry_run.md
stage7_lco2_hem_projected_fvm_dry_run.npz
```

## Test coverage

Dependency-free tests cover:

- invalid accepted-state and budget tolerances;
- one synthetic crossing with matching projection cell;
- one all-liquid first/second-projection no-op;
- crossing/projection cell-set mismatch;
- post accepted-region mismatch;
- unsupported raw outcome recording;
- result summary and artifact flags.

The installed-CoolProp test runs the complete fixed strong/moderate/control matrix and must
execute with zero skips.

## Completion criteria

The increment is review-ready when:

```text
source compiles
git diff --check is clean
focused tests pass with installed CoolProp and zero skips
fixed projected matrix completes
strong and moderate = ACCEPTED_CROSSING
control = ACCEPTED_ALL_LIQUID_NOOP
first projection cells equal crossing cells
second projection cells = 0 for all cases
post accepted-state EOS succeeds for all cases
projection and combined vapor budgets close
related Stage 7 HEM tests pass
full repository tests pass
artifacts are uploaded
permanent workflows pass on the final head
temporary validation workflow is removed
```

## Deliberate boundary

This increment does not:

```text
change FvmSolver or production phase-change activation
advance a second FVM time step
freeze formal Case A or matched Case B
approve endpoint acoustics
approve a two-phase acoustic accuracy band
perform pipeline depressurization
perform physical Validation
approve design use
```

A successful result establishes a complete **one-step projected crossing chain** for the
fixed matrix. Formal Case A/B freeze and longer repeatability remain separate gates.

## Approval boundary

```text
verification_only = true
raw_first_order_fvm_crossing_observed = true
complete_one_step_crossing_path_observed = pending
actual_first_order_fvm_crossing_verified = false
case_a_frozen = false
case_b_frozen = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```
