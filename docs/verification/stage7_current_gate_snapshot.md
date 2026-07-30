# Stage 7 Current Gate Snapshot

## Status — 2026-07-30

```text
Stage 1–6:                         COMPLETE
Stage 7:                           IN_PROGRESS
recorded substantive main:         d98adbd6ae5d407814b0a92724f92f33bdbc0da1
pipeline Increment 2:              MERGED in PR #77
fixed 4 MPa forensic diagnostic:   MERGED in PR #79
mesh sensitivity at CFL 0.10:      MERGED in PR #82
CFL contract / 0.10 replay:        MERGED in PR #84
Gate 3 cross-runtime checkpoint:   NUMERICALLY_EQUIVALENT; MERGED in PR #91
Gate 4 low-CFL execution:          CFL_SENSITIVITY_OBSERVED; MERGED in PR #90
Gate 5 acoustic execution:         COMPLETE; MERGED in PR #96
Gate 5 acoustic approval:          NOT APPROVED
Gate 6 propagation execution:      COMPLETE; MERGED in PR #99
Gate 6 propagation approval:       NOT APPROVED
Gate 7 chatter diagnosis:          COMPLETE; MERGED in PR #102
Gate 7 root-cause approval:        NOT APPROVED
Issue #100:                        CLOSE AFTER THIS CENTRAL SYNC
Gate P2:                           FALSE
active next controlled gate:       specification pending for chatter causal discrimination
physical Validation:               NOT ESTABLISHED
design-use acceptance:             NOT ESTABLISHED
production HEM activation:         NOT APPROVED
two-phase acoustic accuracy band:  NOT APPROVED
```

This snapshot is intentionally concise. Detailed historical entries remain in
[`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md) and
[`stage7_execution_log.md`](stage7_execution_log.md). Gate-specific reviewed records are:

- [`stage7_gate5_closeout.md`](stage7_gate5_closeout.md)
- [`stage7_gate6_closeout.md`](stage7_gate6_closeout.md)
- [`stage7_gate7_closeout.md`](stage7_gate7_closeout.md)

## Project-level current conclusion

The first-order verification path now supports:

- direct liquid-to-open-two-phase crossing from an all-liquid initial state;
- equilibrium-quality projection and accepted mixed liquid/open-two-phase recovery;
- exact second-projection no-op behavior;
- repeatable boundary-driven first-crossing cases;
- fixed mesh and CFL sensitivity evidence for first crossing;
- an independent near-saturation acoustic map;
- continuation for 64 accepted steps after the first 5→2 MPa crossing;
- an open-two-phase region that persists and moves upstream;
- conservative and vapor-budget closure throughout the fixed continuation;
- focused event-aligned diagnosis of the boundary-adjacent cell-30 chatter.

The current evidence also retains important limitations:

- crossing depth is non-monotone across reviewed mesh and CFL sequences;
- accepted/guard classification is CFL-dependent at 2 MPa;
- strict `q -> 0+` acoustic continuity is unresolved;
- liquid and open-two-phase acoustic branches differ substantially;
- cell 30 repeatedly crosses the selected saturation boundary and switches acoustic branches;
- the first-order flux, boundary-adjacent coupling, acoustic branch switch, and equilibrium model remain causally entangled;
- propagation speed, chatter root cause, mitigation, physical accuracy, and design use are unapproved.

## Gate 3 — cross-runtime software reproduction

```text
PR:                                  #91
formal disposition:                  NUMERICALLY_EQUIVALENT
all reviewed discrete events exact:  true
maximum normalized array difference: 5.519112370006797e-12
comparison guard:                    1.0e-10
```

Ubuntu remains authoritative for exact scalar and SHA256 references. The Windows result preserves reviewed outcomes and decisions without replacing Ubuntu hashes.

## Gate 4 — low-CFL execution

```text
PR:                                 #90
merge SHA:                          6399c5fddf6bfbe802da23fdb4f3992ad496e51f
workflow / artifact:               30313389184 / 8675117973
artifact SHA256:                    cee333aeba52510f9f99f89b6fbb36a1a01548bb1a21dd65bab967d203dfaa83
formal disposition:                 CFL_SENSITIVITY_OBSERVED
low_cfl_result_accepted:            true
CFL_independent_crossing_verified:  false
```

Crossing time and position show a stable trend, but crossing depth is non-monotone and the fixed accepted/guard decision changes with CFL at 2 MPa.

## Gate 5 — near-saturation acoustic review

```text
PR:                               #96
merge SHA:                        39937efaebe673ba16f156427957baef8e29ec32
workflow / artifact:             30451125151 / 8723959176
artifact upload SHA256:           018fa92a8395524bcb7bf28e5258d76cda88b539f037bc66f528d50358793949
state / perturbation records:     33 / 588
successful / failed-or-refused:   24 / 9
```

Reviewed evidence labels:

```text
FINITE_JUMP_MODEL_CONSISTENT
PHASE_CLASSIFIER_SENSITIVE
NEAR_SATURATION_PROPERTY_SENSITIVE
ACOUSTIC_REVIEW_INCONCLUSIVE
```

The nearest sampled liquid branch and smallest acoustically evaluable open-two-phase branch have a large finite sound-speed difference. The unchanged central stencil cannot evaluate `q=0`, `q=1e-12`, or `q=1e-10`, so the strict limit remains unresolved.

```text
Gate_5_execution_complete = true
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
```

## Gate 6 — post-crossing propagation review

```text
implementation PR:                #99
PR #99 merge SHA:                 163208a2d027f74217e63375a87ad07d4b845123
source head:                      08167ccf9ebbaf750f5f9c4886b8aceeed7fe547
workflow / artifact:             30466063542 / 8730632937
artifact upload SHA256:           8849d43ba99c1982eace86835567f4d1fb5a3d4b4951a39ac73e153337299bdf
internal evidence-set SHA256:     b1bca3eabf1e5d61dccef2434e256e981ba5e3e2182eef3d90b8592cd55be1a5
Gate 6 / related / full JUnit:    9 / 54 / 820
skips / failures / errors:        0 / 0 / 0
```

The fixed continuation reached every predeclared checkpoint:

| offset | open-two-phase cells | indices | furthest upstream distance [m] | maximum q_eq | maximum alpha |
|---:|---:|---|---:|---:|---:|
| +1 | 1 | `[29]` | 0.078125 | `9.9651e-6` | `7.3594e-5` |
| +4 | 2 | `[28, 29]` | 0.109375 | `2.7667e-5` | `2.0583e-4` |
| +16 | 4 | `[27, 28, 29, 30]` | 0.140625 | `1.3211e-4` | `9.3335e-4` |
| +64 | 7 | `[24, 25, 26, 27, 28, 29, 30]` | 0.234375 | `1.2605e-3` | `9.0086e-3` |

Reviewed evidence labels:

```text
POST_CROSSING_REGION_PERSISTS
POST_CROSSING_REGION_PROPAGATES
PHASE_CLASSIFIER_CHATTER_OBSERVED
PROJECTION_RECOVERY_STABLE
CONSERVATION_BUDGET_STABLE
```

The stable upstream front and localized cell-30 chatter are separate findings.

```text
Gate_6_execution_complete = true
post_crossing_propagation_approved = false
```

## Gate 7 — boundary-adjacent phase-chatter diagnosis

```text
implementation PR:                #102
PR #102 merge SHA:                d98adbd6ae5d407814b0a92724f92f33bdbc0da1
source head:                      71c2ac8bd12116a394baf76b52daa7d2dd0784ff
workflow / artifact:             30501363884 / 8744210262
artifact upload SHA256:           36b65d74f202c191e18f3c94b2bf865254bf9d13da1f796871b18a8a962a2d3f
internal evidence-set SHA256:     1b39115cdbe47c11f52491a442d91784d29366ed3e863c8457de330248253c5b
Gate 7 / related / full JUnit:    10 / 52 / 830
skips / failures / errors:        0 / 0 / 0
```

The Gate 6 final accepted-state SHA and all 49 cell-30 region changes reproduced exactly. The fixed focused evidence contained 576 cell records, 192 interface-flux records, and 49 event-aligned comparisons.

```text
cell 29: 0 toggles; stable OPEN_TWO_PHASE
cell 30: 49 toggles; localized chatter
cell 31: 0 toggles; stable LIQUID_CANDIDATE
```

Reviewed evidence labels:

```text
STABLE_FRONT_SEPARATED_FROM_CHATTER
PHASE_MARGIN_OSCILLATION_CORRELATED
ACOUSTIC_BRANCH_SWITCH_CORRELATED
PROJECTION_ACTIVITY_CORRELATED
MULTI_FACTOR_CHATTER
CHATTER_REVIEW_INCONCLUSIVE
```

Every cell-30 region change crossed both fixed saturated-liquid margin coordinates and switched between non-overlapping acoustic branches:

```text
delta_e sign changes:          49 / 49
delta_v sign changes:          49 / 49
acoustic branch switches:      49 / 49
projection active at events:   49 / 49
liquid sound speed:            492.148 to 533.022 m/s
two-phase sound speed:          35.665 to 39.612 m/s
```

Projection changes only transported `rho*q`; it does not alter the `rho/e` state that determines the phase crossing. The boundary pressure remains monotonic. The predeclared interface-flux sign-change screen was not met (`41/49` for net mass flux, `0/49` for energy and vapor).

From `+35` through `+64`, cell 30 changed region on every accepted step while cells 29 and 31 remained stable. This supports a multi-factor localized oscillation but not a unique root cause.

```text
Gate_7_execution_complete = true
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
```

## Next controlled decision

The next work should be specification-first and should discriminate among the remaining coupled mechanisms without suppressing the observed behavior. Candidate controlled comparisons are:

- post-crossing CFL sensitivity;
- post-crossing mesh sensitivity;
- fixed-state local flux/acoustic contribution analysis.

No next numerical gate, mitigation, hysteresis, or production change is authorized by this snapshot.

## Approval boundary

```text
Gate_6_execution_complete = true
Gate_7_execution_complete = true
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```