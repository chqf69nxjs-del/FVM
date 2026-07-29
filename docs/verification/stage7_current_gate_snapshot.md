# Stage 7 Current Gate Snapshot

## Status — 2026-07-29

```text
Stage 1–6:                         COMPLETE
Stage 7:                           IN_PROGRESS
recorded substantive main:         39937efaebe673ba16f156427957baef8e29ec32
pipeline Increment 2:              MERGED in PR #77
fixed 4 MPa forensic diagnostic:   MERGED in PR #79
mesh sensitivity at CFL 0.10:      MERGED in PR #82
CFL contract / 0.10 replay:        MERGED in PR #84
Gate 3 cross-runtime checkpoint:   NUMERICALLY_EQUIVALENT; MERGED in PR #91
Issue #85:                         COMPLETE; CLOSED
Gate 4 low-CFL execution:          CFL_SENSITIVITY_OBSERVED; MERGED in PR #90
Issue #86:                         COMPLETE; CLOSED AFTER CENTRAL SYNC
Gate 5 acoustic review execution:  COMPLETE; MERGED in PR #96
Gate 5 acoustic approval:          NOT APPROVED
Issue #95:                         CLOSE AFTER THIS CENTRAL SYNC
Gate P2:                           FALSE
active next controlled gate:       post-crossing propagation specification / review
physical Validation:               NOT ESTABLISHED
design-use acceptance:             NOT ESTABLISHED
production HEM activation:         NOT APPROVED
two-phase acoustic accuracy band:  NOT APPROVED
post-crossing propagation:         NOT APPROVED
```

This snapshot supersedes the earlier Gate 4 continuation state. Detailed historic entries
remain in [`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md) and
[`stage7_execution_log.md`](stage7_execution_log.md). The reviewed Gate 5 closeout is
recorded separately in [`stage7_gate5_closeout.md`](stage7_gate5_closeout.md).

## PR #77 — merged fixed pipeline matrix

| case | formal result | step | crossing time [s] | cell | outlet distance [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa observation is a reproducible subthreshold raw crossing. It is neither an
accepted crossing nor an all-liquid control. The fixed `1e-6` evidence threshold and the
physical/numerical contract were not tuned.

## PR #79 — merged fixed-case diagnosis

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
perturbation classification = WEAKLY_RESOLVED
```

The raw point is independently on the equilibrium two-phase side in internal-energy and
specific-volume coordinates. Last-step evidence did not support direct attribution to
Rusanov dissipation or one-sided boundary closure. The equilibrium sound-speed candidate
changed from about `461.26 m/s` before crossing to about `43.22 m/s` after the micro-quality
crossing; acoustic continuity and physical accuracy remained unapproved pending Gate 5.

## PR #82 — merged mesh sensitivity

The 4 MPa raw crossing persisted at CFL 0.10:

| cells | maximum q_eq | normalized crossing time | outlet distance [m] |
|---:|---:|---:|---:|
| 32 | `9.672588429198319e-9` | `0.9318710632753395` | `0.203125` |
| 64 | `5.977506779042054e-7` | `0.8590001798084317` | `0.1484375` |
| 128 | `3.8580990283897163e-7` | `0.8060444782479008` | `0.11328125` |

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

The crossing exists on all three reviewed meshes, but crossing depth is non-monotone.
Formal convergence order and mesh-independent physical accuracy are not established.

## PR #84 — merged CFL contract and exact replay

```text
fixed cells:                    128
fixed final pressures:          2 / 3 / 4 MPa
reviewed CFL values:            0.10 / 0.05 / 0.025
reviewed step caps:             8000 / 16000 / 32000
CFL 0.10 baseline rows:         exact PR #82 replay
CFL 0.05 / 0.025:               executed / formal evidence accepted in PR #90
```

Authoritative evidence:

```text
validated head:                 8564b97493686e06902e5fed0aeb2e117cbd662c
contract workflow / artifact:   30191706675 / 8628766608
contract artifact SHA256:       dc62c44b9844fd07ac15b564140ae1ba2cedeb1684ccaa5539d9eab77cdca8a5
baseline workflow / artifact:   30191706654 / 8629224828
baseline artifact SHA256:       00260475d3b7630b3e77cdd3778db970e026bcfc8aab91104d283a6936d53318
contract + baseline tests:      45 passed
related Stage 7 regressions:    119 passed
full repository:                796 passed
skips / failures / errors:      0 / 0 / 0
pre-execution checkout state:   clean
```

## PR #91 — merged Gate 3 cross-runtime closure

```text
Gate 3 disposition:                  NUMERICALLY_EQUIVALENT
Ubuntu exact baseline retained:      true
Windows hashes replace Ubuntu:       false
all reviewed discrete events exact:  true
maximum normalized array difference: 5.519112370006797e-12
comparison guard:                    1.0e-10
Windows full suite:                  796 tests
passed / failed / errors / skips:    785 / 4 / 7 / 0
unexpected Windows problems:         0
```

The Windows least-significant-bit differences begin in the CoolProp-backed initial state
before the first FVM update. They do not change outcomes, step counts, crossing locations,
or fixed-threshold decisions. Issue #85 is complete. This conclusion is limited to
cross-runtime software reproduction and does not approve physical or design interpretation.

## PR #90 — merged Gate 4 low-CFL execution

```text
merge:                            6399c5fddf6bfbe802da23fdb4f3992ad496e51f
source head:                      ce54f388dc6db75151b7690ca83f8c355c05188f
workflow / artifact:             30313389184 / 8675117973
artifact SHA256:                  cee333aeba52510f9f99f89b6fbb36a1a01548bb1a21dd65bab967d203dfaa83
CFL 0.10 exact replay:            PASS
Gate 4 / related / full JUnit:    50 / 126 / 809
skips / failures / errors:       0 / 0 / 0
```

```text
FINITE_CROSSING_PERSISTS_ACROSS_CFL
CROSSING_TIME_POSITION_TREND_STABLE
CFL_SEQUENCE_NON_MONOTONE
```

The low-CFL observations are formally accepted. Crossing time and position are stable, but
crossing depth is non-monotone. The accepted/guard classification changes with CFL at
2 MPa, so CFL-independent crossing is not verified.

```text
Gate_4_execution = COMPLETE
Gate_4_software_verification = PASSED
Gate_4_numerical_disposition = CFL_SENSITIVITY_OBSERVED
low_cfl_result_accepted = true
CFL_independent_crossing_verified = false
```

## PR #96 — merged Gate 5 near-saturation acoustic review

The FVM-independent 0-D diagnostic executed the fixed 2/3/4 MPa liquid-side, saturated
liquid endpoint, open-two-phase quality, and rho/e perturbation grids using pure CO2 and
CoolProp 8.0.0. The production FVM, acoustic formula, Rusanov flux, boundaries, crossing
threshold, and quality projection were unchanged.

```text
merge:                            39937efaebe673ba16f156427957baef8e29ec32
source head:                      9cb9d64fb7a6ae7b30417083894f0b68cbe3747b
workflow / artifact:             30451125151 / 8723959176
artifact upload SHA256:           018fa92a8395524bcb7bf28e5258d76cda88b539f037bc66f528d50358793949
internal evidence-set SHA256:     a91b3d6f544c1cf9fae986e0c1d466c747d54a383a0be2764985926d45fca411
state / perturbation records:     33 / 588
successful / failed-or-refused:   24 / 9
Gate 5 / related / full JUnit:    2 / 58 / 811
skips / failures / errors:        0 / 0 / 0
```

Reviewed disposition:

```text
FINITE_JUMP_MODEL_CONSISTENT
PHASE_CLASSIFIER_SENSITIVE
NEAR_SATURATION_PROPERTY_SENSITIVE
ACOUSTIC_REVIEW_INCONCLUSIVE
```

The nearest sampled liquid branch and smallest acoustically evaluable open-two-phase branch
have a large finite sound-speed difference. Same-phase perturbations remain comparatively
stable, while large changes coincide with phase reclassification. The unchanged central
stencil cannot acoustically evaluate q=0, q=1e-12, or q=1e-10; therefore the strict q→0+
limit remains unresolved. This does not block execution closeout and does not approve
physical acoustic accuracy.

```text
Gate_5_execution_complete = true
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
```

## Active next gate

Gate 5 execution is complete. Its evidence is accepted as a formal verification record,
including the negative finding that the strict q→0+ acoustic limit is not observable with
the unchanged phase-preserving central stencil. This is not an acoustic-accuracy or
physical-validation approval.

The next controlled gate is a specification-first post-crossing propagation review. It must
retain the current production and approval boundaries until separately established.

```text
low-CFL result accepted = true
mesh-independent crossing verified = false
CFL-independent crossing verified = false
Gate 5 execution complete = true
near-saturation acoustic continuity approved = false
two-phase acoustic accuracy band approved = false
post-crossing propagation approved = false
Gate P2 passed = false
physical Validation = false
design-use acceptance = false
production HEM activation = false
```
