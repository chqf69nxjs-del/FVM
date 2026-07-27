# Stage 7 Current Gate Snapshot

## Status — 2026-07-27

```text
Stage 1–6:                         COMPLETE
Stage 7:                           IN_PROGRESS
recorded substantive main:         1bb1765617de72741086b199efa0d72be16ae651
pipeline Increment 2:              MERGED in PR #77
fixed 4 MPa forensic diagnostic:   MERGED in PR #79
mesh sensitivity at CFL 0.10:      MERGED in PR #82
CFL contract / 0.10 replay:        MERGED in PR #84
Gate 3 cross-runtime checkpoint:   NUMERICALLY_EQUIVALENT; MERGED in PR #91
Issue #85:                         COMPLETE; CLOSED
Gate P2:                           FALSE
active numerical execution gate:   fixed low-CFL matrix — Issue #86
physical Validation:               NOT ESTABLISHED
design-use acceptance:             NOT ESTABLISHED
production HEM activation:         NOT APPROVED
two-phase acoustic accuracy band:  NOT APPROVED
post-crossing propagation:         NOT APPROVED
```

This snapshot supersedes the earlier pre-mesh continuation state. Detailed historic
entries remain in [`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md) and
[`stage7_execution_log.md`](stage7_execution_log.md).

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
crossing; acoustic continuity and physical accuracy remain unapproved.

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
CFL 0.05 / 0.025:               not executed / not accepted
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

## Active next gate

Issue #85 is complete with the Gate 3 disposition `NUMERICALLY_EQUIVALENT`. Issue #86 is
the next numerical execution gate for the fixed nine-run low-CFL matrix. The CFL 0.10 rows
must first reproduce the retained PR #82 baseline exactly; CFL 0.05 and 0.025 results remain
unaccepted until their dedicated execution, review, and central-record promotion.

```text
mesh-independent crossing verified = false
CFL-independent crossing verified = false
near-saturation acoustic continuity approved = false
post-crossing propagation approved = false
Gate P2 passed = false
physical Validation = false
design-use acceptance = false
production HEM activation = false
```
