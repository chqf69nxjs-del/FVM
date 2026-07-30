# Stage 7 Gate 8 — CFL 0.10 Replay and CFL 0.05 Implementation Increment

## Status

```text
Issue:                              #105
scope:                              verification-only implementation increment
mesh:                               32 cells
locked full CFL sequence:           0.10 / 0.05 / 0.025
implemented in this increment:      0.10 / 0.05
pending locked column:              0.025
cross-CFL interpretation:           prohibited in this increment
Gate 8 execution complete:          false
```

This increment is deliberately narrower than the eventual Gate 8 execution bundle. It establishes the exact Gate 6 replay gate and the first refined column without changing or shortening the locked full sequence. CFL 0.025 and all sensitivity classifications remain pending.

## 1. Execution order

```text
1. Execute the authoritative Gate 6 CFL 0.10 runner.
2. Require the complete Gate 6 identity:
   - first crossing step / time / cell / q_eq;
   - T1–T4 at post steps +1 / +4 / +16 / +64;
   - final absolute time;
   - final accepted-state SHA256;
   - cell-30 region-change count.
3. Stop immediately on any identity mismatch.
4. Only after step 2 passes, execute CFL 0.05 from the fixed all-liquid initial state.
5. Retain the CFL 0.05 formal first-crossing outcome without tuning.
6. Continue an accepted CFL 0.05 crossing with ordinary CFL-computed steps to T1–T4, or retain an explicit categorized stop.
```

## 2. Fixed physical targets

| checkpoint | elapsed time after each column's own accepted crossing [s] |
|---|---:|
| T1 | `6.016940923599307e-6` |
| T2 | `2.402911232474538e-5` |
| T3 | `9.544429181626145e-5` |
| T4 | `3.696527559334590e-4` |

At each target, the first accepted state at or after the target is retained. No interpolation, state reconstruction, target adjustment, or result-dependent time-step truncation is permitted. The recorded overshoot must not exceed one accepted local time step.

## 3. Immutable numerical path

```text
case:                               pipeline_crossing_candidate_p5m5_to_p2m5
geometry:                           1.0 m x 0.10 m
mesh:                               32 cells
fluid / backend:                    pure CO2 / CoolProp 8.0.0
initial state:                      5 MPa / 5 K subcooling / u=0 / q=0
left boundary:                      reflective
right boundary:                     existing prescribed 2 MPa / 5 K subcooled path
spatial method:                     existing first-order FVM
flux:                               existing Rusanov
phase classifier:                   unchanged
sound-speed formula:                unchanged
quality projection:                 unchanged
crossing threshold:                 unchanged at 1e-6
friction / heat / gravity:          disabled
```

Only the explicit CFL and predeclared verification step caps differ between columns. No production default is changed.

## 4. Retained evidence

The increment writes:

```text
summary.json
cfl_cases.csv
physical_checkpoints.csv
cell_29_30_31_history.csv
transition_events.csv
inventory_budget.csv
report.md
artifact_sha256.txt
JUnit / runtime / Git provenance through CI
```

The focused history is fixed to cells 29, 30, and 31. Step evidence retains phase-front position, quality, void fraction, pressure, sound-speed ranges, conservative inventories, projection activity, vapor source, and residuals.

## 5. Interpretation boundary

The two implemented columns may be inspected for software correctness, but this increment does not assign any Gate 8 cross-CFL evidence label. In particular, it does not claim:

```text
convergence order
CFL-independent propagation
stable or unstable phase-front trend
chatter amplification or reduction
phase-chatter root cause
physical phase-front speed
physical blowdown accuracy
design use
production HEM activation
```

Those decisions require the locked CFL 0.025 column and the complete Gate 8 execution contract.

## 6. Completion boundary for this increment

```text
CFL 0.10 complete Gate 6 identity reproduced
CFL 0.05 column executed to its formal outcome
all reached targets satisfy the overshoot rule
all successful accepted steps retain projection and budget evidence
CFL 0.025 remains visibly pending
no cross-CFL classification is emitted
no production or numerical-model change occurs
dedicated, related, and full-repository tests are clean
```

## 7. Approval boundary

```text
Gate_8_execution_complete = false
post_crossing_CFL_sensitivity_characterized = false
CFL_independent_post_crossing_verified = false
mesh_independent_post_crossing_verified = false
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
