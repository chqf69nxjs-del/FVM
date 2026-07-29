# Stage 7 Gate 6 Post-Crossing Propagation Closeout

## Status — 2026-07-30

```text
Gate_6_execution_complete = true
post_crossing_propagation_approved = false
```

Gate 6 executed the fixed Issue #98 verification contract. It established that the existing verification-only first-order HEM path can continue for the fixed 64-step horizon after the first accepted liquid-to-open-two-phase crossing. It did not establish mesh/CFL independence, physical propagation accuracy, design use, or production activation.

## Scope

```text
fluid / backend:             pure CO2 / CoolProp 8.0.0
case:                        pipeline_crossing_candidate_p5m5_to_p2m5
pipe length / diameter:      1.0 m / 0.10 m
cells / CFL:                 32 / 0.10
initial state:               5 MPa / 5 K subcooling / u=0 / q=0
right boundary:              prescribed 2 MPa / 5 K subcooling
spatial method / flux:       existing first-order FVM / Rusanov
post-crossing checkpoints:   +1 / +4 / +16 / +64
```

The production solver, Rusanov flux, phase classifier, sound-speed formula, boundary model, quality projection, crossing threshold, property model, and tolerances were unchanged.

## Authoritative implementation and execution

```text
implementation PR:                #99
PR #99 merge SHA:                 163208a2d027f74217e63375a87ad07d4b845123
source head:                      08167ccf9ebbaf750f5f9c4886b8aceeed7fe547
workflow run:                     30466063542
artifact ID:                      8730632937
artifact upload SHA256:           8849d43ba99c1982eace86835567f4d1fb5a3d4b4951a39ac73e153337299bdf
internal evidence-set SHA256:     b1bca3eabf1e5d61dccef2434e256e981ba5e3e2182eef3d90b8592cd55be1a5
pre-execution checkout:           clean
Gate 6 dedicated JUnit:           9 / 0 skipped / 0 failures / 0 errors
related Stage 7 JUnit:            54 / 0 skipped / 0 failures / 0 errors
full repository JUnit:            820 / 0 skipped / 0 failures / 0 errors
```

The downloaded artifact's internal evidence-set digest was independently recomputed and matched `artifact_sha256.txt` exactly.

## Exact first-crossing prerequisite

The merged PR #77 5→2 MPa baseline reproduced exactly before continuation evidence was retained.

```text
outcome:                    ACCEPTED_FIRST_CROSSING
crossing step:              125
crossing time:              7.999325695335248e-4 s
crossing cell:              29
outlet distance:            0.078125 m
maximum q_eq:               3.773646403587342e-6
final-state SHA256:         170ce66c02a320d50389d0cf26fed78f21042f83dec6f64a0978e451cd91e361
run-signature SHA256:       28a5f8b1fd43f6208807bd15d96eaf09a568349007a1994273717aa264505fea
```

## Fixed continuation result

```text
outcome:                         COMPLETED_FIXED_CHECKPOINTS
successful post-crossing steps:  64
reached offsets:                 +1 / +4 / +16 / +64
accepted cell records:           2048
acoustic successes / refusals:   2048 / 0
final accepted-state SHA256:      62bbaf5d7014af258180fe29622324a2228a0c5eec507ef10eb6b9f3e411d440
```

| offset | open-two-phase cells | indices | furthest upstream distance [m] | maximum q_eq | maximum alpha | vapor mass [kg] |
|---:|---:|---|---:|---:|---:|---:|
| +1 | 1 | `[29]` | 0.078125 | `9.9651e-6` | `7.3594e-5` | `2.1682e-6` |
| +4 | 2 | `[28, 29]` | 0.109375 | `2.7667e-5` | `2.0583e-4` | `9.4368e-6` |
| +16 | 4 | `[27, 28, 29, 30]` | 0.140625 | `1.3211e-4` | `9.3335e-4` | `6.1276e-5` |
| +64 | 7 | `[24, 25, 26, 27, 28, 29, 30]` | 0.234375 | `1.2605e-3` | `9.0086e-3` | `6.3461e-4` |

## Stable upstream front

The ordered upstream front entered open two phase at the following fixed post-crossing steps:

```text
cell 28: +2
cell 27: +9
cell 26: +19
cell 25: +34
cell 24: +52
```

Those cells did not return to liquid during the fixed horizon. This supports separate persistence and propagation observations.

## Boundary-adjacent chatter

Cell 30 exhibited a separate local transition history:

```text
first liquid -> open-two-phase transition: +6
liquid -> open-two-phase transitions:      25
open-two-phase -> liquid transitions:      24
total region changes:                      49
final region at +64:                       OPEN_TWO_PHASE
```

Its accepted sound speed was approximately `492–533 m/s` when liquid and `35.7–39.6 m/s` when open two phase. The observed two-phase `q_eq` range was approximately `1.93e-7` to `5.96e-6`.

The label `PHASE_CLASSIFIER_CHATTER_OBSERVED` records the transition history only. Gate 6 did not assign root cause to the classifier, boundary, Rusanov diffusion, acoustic branch switching, quality projection, or physical flashing behavior.

## Projection and budget evidence

```text
first-projection cells per step:     3 to 9
second-projection activations:       0 / 64
maximum |mass residual|:             1.7764e-15 kg
maximum |momentum residual|:         6.2172e-15 kg m/s
maximum |energy residual|:           4.6566e-10 J
maximum |phase-vapor residual|:      2.1684e-19 kg
```

Every successful step synchronized transported quality and retained an exact second-projection no-op. All fixed conservative and vapor-budget guards passed.

## Reviewed evidence classifications

```text
POST_CROSSING_REGION_PERSISTS
POST_CROSSING_REGION_PROPAGATES
PHASE_CLASSIFIER_CHATTER_OBSERVED
PROJECTION_RECOVERY_STABLE
CONSERVATION_BUDGET_STABLE
```

The stable upstream front and localized cell-30 chatter are distinct findings.

## Closeout decision

The Issue #98 execution contract is satisfied because:

- the authoritative first-crossing prerequisite reproduced exactly;
- all predeclared continuation checkpoints were reached;
- retained states were finite, accepted, and acoustically evaluable;
- transition history distinguishes persistence, propagation, and localized chatter;
- projection and budget evidence satisfy the fixed guards;
- authoritative JUnit is clean;
- provenance and artifact identity are complete.

The result is accepted as a formal software/numerical verification record. It is not a post-crossing physical-accuracy approval.

## Approval boundary

```text
Gate_6_execution_complete = true
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
CFL_independent_crossing_verified = false
mesh_independent_crossing_verified = false
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## Next controlled gate

Issue #100 is the specification-first boundary-adjacent phase-chatter diagnosis. It fixes cells 29, 30, and 31; interfaces `29|30` and `30|31`; the right boundary; saturation-margin, acoustic, projection, and flux records; and event-step-versus-previous-step comparisons.

The next gate may identify correlations and temporal ordering. It may not alter production behavior or claim root cause from correlation alone.