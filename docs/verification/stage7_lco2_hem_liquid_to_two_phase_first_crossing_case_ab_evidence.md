# Stage 7 — First-Crossing Case A/B Freeze Evidence

## Status

`VALIDATED; CASE A AND CASE B FROZEN; FIRST-ORDER SOFTWARE CROSSING VERIFIED; PHYSICAL VALIDATION NOT ESTABLISHED`

This record follows merged PR #71. It repeats the fixed strong crossing case and
the matched liquid control three times each, stops Case A at its first accepted
crossing, and advances Case B to the exact same physical time.

## Validation environment

```text
validated head:            825ebba11b7ea273c81db717c097d8f1122ae092
workflow run:              30105917479
artifact ID:               8601660179
artifact SHA256:           02b13cb63704ea63d826f1e1feab209c4bd5b83b4a5fec7e3936af114e0cbc7b
CoolProp:                  8.0.0
compileall:                success
git diff --check:          success
focused tests:             14 passed, 0 skipped
related Stage 7 HEM:      200 passed, 0 skipped
full repository:          642 passed, 0 skipped
failures / errors:          0 / 0
```

The temporary validation workflow executed the installed-CoolProp repeatability
test without a skip.

## Frozen numerical and thermodynamic conditions

```text
cells:                 8
pipe length:           1.0 m
pipe diameter:         0.10 m
interface:             between cells 3 and 4
initial velocity:      0 m/s
initial transported q: 0 exactly
CFL limit:             0.20
flux:                  existing first-order Rusanov
boundaries:            transmissive
physical source:       none
repeat count:          3
Case A step limit:     8
```

```text
Case A:
5 MPa / 5 K subcooling -> 2 MPa / 5 K subcooling

Case B:
5 MPa / 5 K subcooling -> 4 MPa / 5 K subcooling
```

No case condition, algorithm, tolerance, or threshold was changed after PR #71.

## Freeze result

```text
case_a_repeatable = true
case_b_repeatable = true
case_b_matched_physical_time = true
case_a_frozen = true
case_b_frozen = true
actual_first_order_fvm_crossing_verified = true
```

`actual_first_order_fvm_crossing_verified` is a software verification flag for the
current first-order FVM and reviewed HEM chain. It is not physical Validation or
design-use acceptance.

## Case A — repeated first accepted crossing

Every repeat produced the same result:

```text
outcome:                       ACCEPTED_CROSSING
crossing step:                 1
crossing time:                 3.356317173211922e-5 s
crossing cells:                3, 4
projection cells:              3, 4
maximum crossing q_eq:         5.911503500507591e-4
projection vapor source:       7.054022964126832e-4 kg
second projection cells:       none
post q mismatch:               0
```

Repeatability evidence:

```text
final conservative-state SHA256:
78897b5c8ca57221186ccf3e0aa69e1492a942cc2e8dee0abb440a3e2e08e039

Case A repeatability signature:
914ed2249c9546a1d32f6d6dbcd8b30236e1c1f2b37ecf9306100ad30622b612
```

The same state hash and repeatability signature were obtained in all three runs.

### Case A budgets

```text
mass residual:                0
momentum residual:            0
energy residual:              2.3283064365386963e-10
energy relative residual:     1.742733258599977e-16
phase-vapor residual:         0 kg
```

The boundary-only vapor residual equals the internal projection source, as
expected. The combined boundary-plus-phase vapor budget closes exactly.

## Case B — exact matched physical-time liquid control

The Case B final step was shortened through the existing
`compute_dt(t_end=...)` path so that every repeat ended at exactly:

```text
3.356317173211922e-5 s
```

Every repeat produced:

```text
outcome:                       MATCHED_ALL_LIQUID
step count:                    1
crossing cells:                none
projection cells:              none
maximum q_eq:                  0
projection vapor source:       0 kg
all final regions:             LIQUID_CANDIDATE
```

Repeatability evidence:

```text
final conservative-state SHA256:
8c09735ee9185cfb34b2186be30b32d78ec73350e211762d92c372e0b9f23a59

Case B repeatability signature:
3bd7edc37842a00a0c27964a17029f5c66ef973b59bd7670f513c82fc7e85669
```

The same state hash and repeatability signature were obtained in all three runs.

### Case B budgets

```text
mass residual:                0
momentum residual:            0
energy residual:              0
vapor residual:               0
phase-vapor residual:         0 kg
```

## Common accepted-path checks

All repeated runs satisfied the applicable checks:

```text
initial states accepted as liquid
actual FvmSolver.step() exercised
raw regions classified directly from rho/e
crossing cells = first projection cells
post q = q_eq
post mixed accepted-state EOS succeeds
post pressure, temperature, and sound speed finite and positive
second projection is a no-op
projection source counted once
mass/momentum/energy budgets close
phase-vapor budget closes
```

## Technical conclusion

The first liquid-to-open-two-phase software verification pair is now frozen:

```text
Case A:
strong pressure-span case with a repeatable accepted crossing

Case B:
nearest pressure-span liquid control at the exact matched physical time
```

The evidence is deterministic in the validated CoolProp 8.0.0 environment across
three fresh executions of each case.

## Approval boundary

```text
verification_only = true
case_a_frozen = true
case_b_frozen = true
actual_first_order_fvm_crossing_verified = true
software_verification_only = true
algorithms_or_tolerances_tuned = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Next increment

After review and merge:

1. synchronize PRs #70–#72 into `MASTER_VERIFICATION_INDEX.md` and
   `stage7_execution_log.md`;
2. retain the frozen Case A/B pair as the first-order regression control;
3. define a separate, narrow pipeline-depressurization prototype gate;
4. keep production activation, physical Validation, design use, and acoustic
   accuracy approval false until separately established.
