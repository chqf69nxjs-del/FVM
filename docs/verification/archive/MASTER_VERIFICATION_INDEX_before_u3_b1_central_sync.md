# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-28

- Stage 1–6: `COMPLETE`
- Stage 7: `IN_PROGRESS`
- recorded substantive development `main`: `6399c5fddf6bfbe802da23fdb4f3992ad496e51f`
- V-013 first-order propagation/reflection baseline: `FORMALIZED; MERGED` in PR #51
- pure-CO2 HEM thermodynamic and phase foundation: `MERGED` in PRs #54–#57
- dynamic equilibrium-quality synchronization: `IMPLEMENTED; MERGED` in PRs #59–#60
- first repeatable liquid-to-open-two-phase crossing Case A and matched liquid Case B:
  `FROZEN; MERGED` in PR #72
- prescribed-subcooled outlet boundary Increment 1: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` in PR #75
- boundary-path preflight: `195 / 195 ACCEPTED LIQUID_CANDIDATE`
- first-order liquid-to-open-two-phase software crossing: `VERIFIED`
- frozen Case A/B retained as the first-order crossing regression control
- fixed boundary-driven 5→2/3/4 MPa pipeline matrix: `OBSERVED; MERGED` in PR #77
- fixed 4 MPa subthreshold forensic diagnosis: `OBSERVED; MERGED` in PR #79
- fixed 32/64/128-cell mesh-sensitivity matrix at CFL 0.10: `OBSERVED; MERGED` in PR #82
- fixed 128-cell CFL-sensitivity contract and exact CFL 0.10 replay: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` in PR #84
- Gate 3 cross-runtime capture and local-PC checkpoint: `NUMERICALLY_EQUIVALENT; MERGED` in PR #91
- Gate 4 fixed 128-cell low-CFL matrix: `CFL_SENSITIVITY_OBSERVED; MERGED` in PR #90
- Ubuntu remains authoritative for bitwise-exact scalars and SHA256 values; Windows hashes do not replace the Ubuntu baselines
- 4 MPa raw crossing: present at 32, 64, and 128 cells; accepted-crossing threshold
  remains unchanged at `1e-6`
- Gate P2: `FALSE`
- mesh-independent crossing accuracy: `NOT ESTABLISHED`
- CFL-independent crossing: `NOT VERIFIED`
- Gate 3 local-PC reproduction checkpoint: `COMPLETE; NUMERICALLY_EQUIVALENT` in PR #91; Issue #85 closed
- Gate 4 low-CFL execution: `COMPLETE; CFL_SENSITIVITY_OBSERVED` in PR #90; Issue #86 closed after synchronization
- next numerical gate: independent near-saturation acoustic-continuity review
- MUSCL/TVD reconstruction scaffold: `OPEN; READY FOR REVIEW` in PR #52
- scalar-advection comparison: `VALIDATED STACKED DRAFT` in PR #53
- physical Validation: `NOT ESTABLISHED`
- design-use acceptance: `NOT ESTABLISHED`
- production HEM activation: `NOT APPROVED`
- two-phase acoustic accuracy band: `NOT APPROVED`

The main development objective remains a conservative one-dimensional LCO2 pipeline
transient code that can progress from liquid states through flashing and liquid-vapor
two-phase formation. The existing first-order FVM remains the numerical control.

The merged HEM verification path now supports guarded real-fluid state evaluation,
explicit phase classification, an equilibrium sound-speed candidate, quality projection,
mixed liquid/open-two-phase accepted-state evaluation, direct raw transition detection,
an actual first-order Rusanov/CFL liquid-to-open-two-phase crossing, synchronized
post-crossing recovery, vapor-budget closure, a repeatable matched Case A/B software
verification pair, a fixed minimal pipeline-depressurization specification, a verified
prescribed-subcooled outlet boundary, a boundary-driven first-crossing pipeline runner,
a fixed 4 MPa forensic diagnosis, a 32/64/128-cell software mesh-sensitivity matrix, and
a fixed 128-cell CFL 0.10/0.05/0.025 execution matrix. Gate 4 accepted the low-CFL
observations as formal verification evidence: crossing time and position are stable, but
crossing depth is non-monotone and the accepted/guard classification is CFL-dependent.
Physical Validation, a two-phase acoustic accuracy band, post-crossing propagation
approval, design use, and production HEM activation remain unestablished.

## Stage 7 milestone index

| item | purpose | status | merge / final reference |
|---|---|---|---|
| V-013A / PR #48 | incident-wave propagation | `OBSERVED; MERGED` | merge `613b21622b22402fbf7b8d77b1d881db7ff5f28e` |
| V-013B / PR #49 | rigid-wall reflection | `OBSERVED; MERGED` | merge `bc874193de6a4c019073b6cf629e99ec5dfa6602` |
| V-013C / PR #50 | fixed-pressure reflection | `OBSERVED; MERGED` | merge `f403103c46a1d618ce2f2345c986e29b921b664a` |
| PR #51 | first-order baseline formalization | `FORMALIZED; MERGED` | merge `62390bd526ae99b6702f4ed76e3594e1bf01259b` |
| PR #52 | solver-independent MUSCL/TVD reconstruction | `OPEN; READY FOR REVIEW` | head `829880e88010ea808b316e09f28f26a0a18c7f03` |
| PR #53 | scalar-advection diffusion comparison | `VALIDATED STACKED DRAFT` | head `ff72bd303a99d832bad6d13536ff9b5682eeb4f9` |
| PR #54 | HEM thermodynamic scaffold and 0-D path | `MERGED` | merge `6e0779346a9adb0f3c74d790f558a6813f009ee7` |
| PR #55 | explicit CoolProp phase classification | `MERGED` | merge `e45362d1aa07bf7144f606dc32595d4ab2f7093d` |
| PR #56 | equilibrium sound-speed closure candidate | `MERGED` | merge `b098f67b71bf53bd20fc14bf80d7f4cea595a707` |
| PR #57 | uniform HEM-state preservation | `OBSERVED; MERGED` | merge `f27ec42d0e191065cd4d3d214a14009b07be800f` |
| PR #58 | HEM verification-record synchronization | `MERGED` | merge `dd5d3d0d10d0f93bb0d7a066e6d861f54c153b25` |
| PR #59 | dynamic quality-sync specification | `MERGED` | merge `70dc41ab7bc3c5ef46d83a49e3ea8de48d84ebad` |
| PR #60 | equilibrium-quality projection implementation | `MERGED` | merge `a4d525a004ae7bf5e284a882706155dce41b3eba` |
| PR #61 | pressure-offset nonuniform dynamic case | `OBSERVED; MERGED` | merge `ceca2b48eb2f34cb8c1d584d80ae2619ff77271a` |
| PR #62 | equal-pressure contact/no-op comparison | `OBSERVED; MERGED` | merge `3e116cbcd853bcb1b52fe001819a4b300d5997ff` |
| PR #63 | quality-sync central-record synchronization | `MERGED` | merge `33349ff6c16373443b2626d13c1a867d54275d0a` |
| PR #64 | first liquid-to-two-phase crossing specification | `MERGED` | merge `f2b8335132741765b6d5e42f65f742cf5e241c66` |
| PR #65 | boundary-region and transition classifier | `IMPLEMENTED; MERGED` | merge `fb078da84fa17d6aa8d840616c494a0bf3efd71c` |
| PR #66 | crossing-groundwork central-record synchronization | `MERGED` | merge `7acaa005c6d32cd48042ca5a333dcc19b5006d23` |
| PR #67 | mixed liquid/open-two-phase accepted-state EOS | `IMPLEMENTED; MERGED` | merge `74b019993823ec4c52f1be38fa8c12580f560686` |
| PR #68 | liquid state-pair property survey | `VALIDATED; MERGED` | merge `640b69c576501ec812cbc2919f35c62526b15974` |
| PR #69 | EOS/state-pair central-record synchronization | `MERGED` | merge `4c0960d32a03269828a8a0d3e2d2c8c9c8322f62` |
| PR #70 | actual one-step raw FVM crossing matrix | `OBSERVED; MERGED` | merge `38e841af97ac0adbebf42dbe36a17c1edc6c5246` |
| PR #71 | projected crossing, post-EOS recovery, and vapor budget | `OBSERVED; MERGED` | merge `ceaba980e5e7f7305424df8bd1e9e6b4f1acfe40` |
| PR #72 | repeated first-crossing Case A/B freeze | `VERIFIED; FROZEN; MERGED` | merge `628800530851b0cb677bc0a6bedcb85a13a303d1` |
| PR #73 | first-crossing central-record synchronization | `MERGED` | merge `3e55b3fae88d813437654c144d0157de5b6d398f` |
| PR #74 | minimal LCO2 pipeline-depressurization prototype specification | `SPECIFIED; MERGED` | merge `49b34bf955a5dd1f0d106f2e81f55aff3bd24add` |
| PR #75 | prescribed-subcooled outlet boundary Increment 1 | `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` | merge `9982c52bc4c26fac991972f0a8156c857e4bf21f` |
| PR #77 | fixed boundary-driven 2/3/4 MPa pipeline matrix | `OBSERVED; MERGED` | merge `5657d26b3f37443ef63971245dce66ddd72c681e` |
| PR #79 | fixed 4 MPa subthreshold forensic diagnosis | `OBSERVED; MERGED` | merge `e40562e03657dec526f84b3911cbf181973462fa` |
| PR #82 | fixed 32/64/128-cell mesh sensitivity at CFL 0.10 | `OBSERVED; MERGED` | merge `08d34069b45083537e1d5c4035993d3fc5c01de5` |
| PR #84 | fixed CFL contract and exact 128-cell/CFL 0.10 replay | `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` | merge `827d99bce97cea2785aa3334b3f5e950389c9aad` |
| PR #91 | Gate 3 cross-runtime numeric-equivalence closure | `NUMERICALLY_EQUIVALENT; MERGED` | merge `1bb1765617de72741086b199efa0d72be16ae651` |
| PR #90 | fixed 128-cell low-CFL execution and evidence | `CFL_SENSITIVITY_OBSERVED; MERGED` | merge `6399c5fddf6bfbe802da23fdb4f3992ad496e51f` |

## Boundary-driven pipeline continuation — PRs #77, #79, #82, #84, and #90

### PR #77 — fixed first-crossing pipeline matrix

The fixed 1.0 m / 0.10 m / 32-cell first-order Rusanov prototype executed the unchanged
5→2, 5→3, and 5→4 MPa schedules at CFL 0.10.

| case | formal result | step | crossing time [s] | cell | outlet distance [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa row is a reproducible subthreshold raw crossing, not an accepted crossing and
not an all-liquid control. Gate P2 remains false; no algorithm, schedule, or threshold was
tuned after observing the result.

### PR #79 — fixed 4 MPa forensic diagnosis

The exact PR #77 baseline was reproduced before diagnosis. Retained categories:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

The crossing point lies on the equilibrium two-phase side in both internal-energy and
specific-volume coordinates. The perturbation result is `WEAKLY_RESOLVED`: the phase
classification is stable through relative `rho/e` perturbations of `1e-8` but changes for
some `1e-6` perturbations. The narrow last-step tests did not support direct assignment to
Rusanov dissipation or one-sided boundary closure. Near-saturation acoustic continuity
remains unapproved.

### PR #82 — fixed mesh sensitivity at CFL 0.10

The 4 MPa raw crossing persisted on all three reviewed meshes:

| cells | formal result | maximum q_eq | normalized crossing time | outlet distance [m] |
|---:|---|---:|---:|---:|
| 32 | `GUARD_FAILURE` | `9.672588429198319e-9` | `0.9318710632753395` | `0.203125` |
| 64 | `GUARD_FAILURE` | `5.977506779042054e-7` | `0.8590001798084317` | `0.1484375` |
| 128 | `GUARD_FAILURE` | `3.8580990283897163e-7` | `0.8060444782479008` | `0.11328125` |

Retained labels:

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

The observations do not establish a formal convergence order, a mesh-independent quality
value, physical nucleation, or design accuracy.

### PR #84 — CFL contract and exact baseline replay

The next comparison is fixed at 128 cells with final pressures 2/3/4 MPa and CFL values
0.10/0.05/0.025. Only CFL and the predeclared 8000/16000/32000 step caps may vary. The
three CFL 0.10 rows reproduced PR #82 exactly before lower-CFL execution is allowed.

```text
validated head:               8564b97493686e06902e5fed0aeb2e117cbd662c
contract workflow:            30191706675
contract artifact:            8628766608
contract artifact SHA256:     dc62c44b9844fd07ac15b564140ae1ba2cedeb1684ccaa5539d9eab77cdca8a5
baseline workflow:            30191706654
baseline artifact:            8629224828
baseline artifact SHA256:     00260475d3b7630b3e77cdd3778db970e026bcfc8aab91104d283a6936d53318
contract + baseline tests:    45 passed
related Stage 7 regressions:  119 passed
full repository:              796 passed
skips / failures / errors:    0 / 0 / 0
```

The independent local-PC reproduction checkpoint completed as `NUMERICALLY_EQUIVALENT`
in PR #91. PR #90 then completed the fixed low-CFL matrix and accepted the observations
as formal verification evidence. The result does not establish CFL-independent crossing.

```text
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
near_saturation_acoustic_continuity_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```


### PR #90 — Gate 4 fixed low-CFL execution and evidence

The clean-head authoritative run completed the fixed 128-cell matrix without tuning. Only
CFL and the predeclared step cap varied.

```text
merge:                            6399c5fddf6bfbe802da23fdb4f3992ad496e51f
source head:                      ce54f388dc6db75151b7690ca83f8c355c05188f
workflow / artifact:             30313389184 / 8675117973
artifact SHA256:                  cee333aeba52510f9f99f89b6fbb36a1a01548bb1a21dd65bab967d203dfaa83
CFL 0.10 exact PR #82 replay:     PASS
Gate 4 / related / full JUnit:    50 / 126 / 809
skips / failures / errors:       0 / 0 / 0
```

| final pressure | CFL | formal result | crossing time [s] | outlet distance [m] | maximum q_eq |
|---:|---:|---|---:|---:|---:|
| 2 MPa | 0.100 | `ACCEPTED_FIRST_CROSSING` | `0.0006422816041107276` | `0.05859375` | `1.1990738237934995e-6` |
| 2 MPa | 0.050 | `GUARD_FAILURE` | `0.0006414831293446631` | `0.05859375` | `8.49256445269167e-8` |
| 2 MPa | 0.025 | `GUARD_FAILURE` | `0.000641835254911946` | `0.05859375` | `4.5860628934931823e-7` |
| 3 MPa | 0.100 | `GUARD_FAILURE` | `0.0009203833940858876` | `0.07421875` | `5.977506786571329e-7` |
| 3 MPa | 0.050 | `GUARD_FAILURE` | `0.0009203372670546511` | `0.07421875` | `4.795347832264699e-7` |
| 3 MPa | 0.025 | `GUARD_FAILURE` | `0.0009199386269654269` | `0.07421875` | `1.0679679596318976e-7` |
| 4 MPa | 0.100 | `GUARD_FAILURE` | `0.0017272870719037706` | `0.11328125` | `3.8580990283897163e-7` |
| 4 MPa | 0.050 | `GUARD_FAILURE` | `0.0017264912557689444` | `0.11328125` | `4.882555423709485e-9` |
| 4 MPa | 0.025 | `GUARD_FAILURE` | `0.0017268445320799829` | `0.11328125` | `1.4058733473620004e-7` |

```text
FINITE_CROSSING_PERSISTS_ACROSS_CFL
CROSSING_TIME_POSITION_TREND_STABLE
CFL_SEQUENCE_NON_MONOTONE
```

The low-CFL observations are accepted as formal verification evidence. Crossing time and
position are stable, but crossing depth does not converge monotonically. At 2 MPa the fixed
`1e-6` accepted-crossing threshold is exceeded at CFL 0.10 but not at CFL 0.05 or 0.025.
Therefore `CFL_independent_crossing_verified` remains false.

```text
Gate_4_execution = COMPLETE
Gate_4_software_verification = PASSED
Gate_4_numerical_disposition = CFL_SENSITIVITY_OBSERVED
low_cfl_result_accepted = true
CFL_independent_crossing_verified = false
```

### PR #91 — Gate 3 cross-runtime numeric-equivalence closure

The authoritative Ubuntu 24.04 reference retained exact PR #82 scalar and SHA256 identity.
An independent Windows 11 replay used Python 3.12.10, NumPy 2.5.1, and CoolProp 8.0.0.
The Windows result was not bitwise identical, but all three reviewed 128-cell / CFL 0.10
cases retained exact formal outcomes, step counts, crossing steps, crossing cells, crossing
positions, and failure categories.

```text
Ubuntu reference artifact:       8632513953
Ubuntu artifact SHA256:          78002ddb524c9f1cac00040a14139d6da512f66f19d39a65afc53dbcac188060
Windows raw-history ZIP SHA256:  508e9b727a2e0d00974e4650c3f927e93af89eed9af96cde5c2b0b3e12368738
maximum normalized difference:   5.519112370006797e-12
predeclared comparison guard:    1.0e-10
```

The first cross-platform difference was already present in the CoolProp-backed uniform
initial state before the first FVM update. It did not change a discrete event or reverse a
crossing-threshold decision. All raw-history shapes matched, all values were finite, and
mass, momentum, energy, and vapor inventory differences remained inside the existing
absolute budget limits.

The independent Windows full-repository packet v2 completed:

```text
source main:                       f1b2c76827482164a12e2924bf7119a0b150e421
full repository:                   796 tests
passed / failed / errors / skips:  785 / 4 / 7 / 0
reviewed exact mismatches:         11
unexpected problems:               0
inspector result:                  KNOWN_EXACT_WINDOWS_MISMATCHES_ONLY
packet SHA256:                     67a0113b63db1b4770baf4bbd4104312c5c24839cf50956e57592f487fd7755f
```

The exact Ubuntu baselines remain unchanged. The formal Gate 3 disposition is
`NUMERICALLY_EQUIVALENT`; this is a cross-runtime software-verification conclusion, not a
physical Validation, acoustic-accuracy, design-use, or production-activation approval.

## First-order V-013 baseline

The current production FVM is fixed as a selectable software/numerical control. It
reproduces wave direction, approximate timing, reflection signs, and essential boundary
behavior across V-013A/B/C.

| case | expected identity | observed conclusion | finest-mesh final peak ratio |
|---|---|---|---:|
| V-013A | right-going `A+` | direction and approximate speed consistent | `0.57499430` |
| V-013B | `A-_reflected = A+_incident` | pressure sign positive; velocity sign negative | `0.57499450` |
| V-013C | `A-_reflected = -A+_incident` | pressure sign negative; velocity sign positive | `0.57212615` |

Approximately `57%` peak retention at `n=400` is an observed first-order numerical-
diffusion limitation, not an approved accuracy target, design margin, or CI band.

Formalization documents:

- [`stage7_v013_baseline_and_limitations.md`](stage7_v013_baseline_and_limitations.md)
- [`v013_baseline_definition_v1.json`](v013_baseline_definition_v1.json)
- [`stage7_v013_ci_light_proposal.md`](stage7_v013_ci_light_proposal.md)

CI-light remains `PROPOSED; NOT APPROVED; NOT IMPLEMENTED`.

## Numerical-diffusion improvement assets

PR #52 contains a solver-independent reconstruction layer with exact first-order and
componentwise MUSCL reconstruction plus minmod, MC, and van Leer limiters. It does not
connect to `FvmSolver` or change production numerical states.

PR #53 contains a periodic scalar-advection comparison. At `n=200`, peak retention under
SSP-RK2 was approximately:

```text
first order:       0.57795218
MUSCL minmod:      0.88811719
MUSCL MC:          0.96768181
MUSCL van Leer:    0.94953622
```

At `n=400`, MUSCL MC retained `0.98833595` of the peak. These results rank later
numerical candidates; they do not approve a production limiter, reconstruction variable
set, fallback policy, or time integrator. Higher-order production connection remains
deferred until the first-order dynamic HEM path is stable.

## Pure-CO2 HEM foundation — PRs #54–#57

| PR | increment | final reviewed head | focused / full tests | principal evidence |
|---|---|---|---|---|
| #54 | thermodynamic scaffold and deterministic 0-D path | `39a394698383879225216aee403c1221fe454e0e` | `24 / 406` | path states `23 / 23`; artifact formats `4 / 4` |
| #55 | explicit CoolProp phase classification | `97ffe4e57c3a006ae27702749c417f9e3989aba8` | `39 / 423` | phase-map states `9 / 9`; sound-speed calls `0` |
| #56 | equilibrium sound-speed closure candidate | `3c21be4410e808f22888edd9814204a25df40a4c` | `63 / 447` | sound-speed states `10 / 10`; two-phase states `7 / 7` |
| #57 | uniform stationary two-phase FVM preservation | `45cdfe3da409e98825bc3b2ab52265f5f51f2900` | `76 / 460` | cells / steps `8 / 8`; all measured drift exactly `0` |

The foundation demonstrates guarded `rho/e` evaluation, explicit liquid/two-phase/vapor
classification, separation of equilibrium state evaluation from acoustic closure, an
independent equilibrium sound-speed candidate, verification-only Rusanov/CFL connection,
and exact preservation of one uniform stationary open-two-phase state. The two-phase
sound-speed values remain closure observations, not an approved physical acoustic map.

## Dynamic equilibrium-quality synchronization — PRs #59–#62

The FVM transports `rho*q`, while `rho/e` independently implies `q_eq`. The reviewed
operator enforces:

```text
rho*q <- rho*q_eq
```

while preserving `rho`, `rho*u`, and `rho*E` bitwise.

| PR | increment | final reviewed head | focused / full tests | primary evidence |
|---|---|---|---|---|
| #59 | specification and acceptance contract | `b7b00432dc6c0ad9197f3f9809c22fb1c247c4ed` | specification only | separate no-op and activated cases; no clipping; fail-fast guards |
| #60 | `HEMEquilibriumQualityProjection` implementation | `1da2ffc9047a71aedc343eb932e7f4115bc004a2` | `72 / 478` | artifact `8483707741`; SHA256 `bdf06b22fbc81ca044ed57dfab9b3a18987c05914bc03b0da3734dc7e7885a6f` |
| #61 | real-CO2 nonuniform pressure-offset case | `a0e1024aa5bf9f54c205dfc8e81e614080354214` | `46 / 493` | artifact `8483939146`; SHA256 `4156346821f0c04b5d5a569fd6bb64edeb07854a4ae905c4b29f5b3e51152447` |
| #62 | equal-pressure no-op and activated contrast | `1b4a754de4e79b0d4bb88acb22b94301d72ca142` | `67 / 514` | artifacts `8488096499`, `8491343302`; backend traceability added after review |

PR #61 produced measurable projection activity while remaining open two phase:

```text
projection total cell updates:          20
projected cells by step:                 2, 4, 6, 8
maximum |delta q|:                       2.4143668471476865e-5
maximum post-projection q mismatch:      5.551115123125783e-16
cumulative vapor source:                 3.501570117236952e-5 kg
```

PR #62 exercised an equal-pressure nonuniform contact as a true no-op:

```text
projection total cell updates:          0
maximum |delta q|:                       4.440892098500626e-16
projection vapor source:                 0.0 kg
```

Mass, momentum, energy, and phase-vapor budgets closed in both cases. The latest
artifacts retain backend, version, and `not_approved_for_design_use` traceability.

## Liquid-to-two-phase boundary groundwork — PRs #64–#68

### PR #64 — specification

PR #64 fixes the first narrow liquid-to-open-two-phase crossing contract. Key decisions
include:

- detect raw thermodynamic transitions directly from updated `rho/e` before projection;
- do not use transported quality as the phase classifier;
- distinguish ordinary liquid `q=0` from saturated-liquid endpoint `q=0` by explicit
  phase classification;
- classify endpoint arrival as `BOUNDARY_TOUCH` and fail the first integration gate until
  endpoint acoustic closure is separately established;
- separate crossing detection from projection activation;
- reuse the reviewed endpoint and projection tolerances from their configuration objects;
- keep `crossing_evidence_min_quality = 1e-6` as test evidence only, never a solver switch;
- retain the current `e >= 0` solver integration constraint;
- compare crossing and no-crossing cases over a matched physical-time horizon;
- permit logged case-condition exploration while keeping algorithms and thresholds fixed.

PR #64 is specification only. It does not prove an FVM crossing.

### PR #65 — transition classifier

PR #65 implements a verification-only boundary-region mapper and transition-event
classifier. It derives:

```text
LIQUID_CANDIDATE
SATURATED_LIQUID_ENDPOINT
OPEN_TWO_PHASE
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
```

and classifies:

```text
NO_TRANSITION
BOUNDARY_TOUCH
LIQUID_TO_TWO_PHASE_CROSSING
REVERSE_TRANSITION
FORBIDDEN_TRANSITION
```

The classifier evaluates phase directly from `rho/e`, is independent of transported
`q`, performs no clipping, retains the current non-negative-internal-energy guard, and
fails atomically for guarded, invalid, undefined, or inconsistent states. It is not
connected to `FvmSolver` and does not modify EOS, flux, CFL, sound speed, or projection.

Authoritative validation:

```text
workflow run:          29927030452
artifact ID:           8532470595
artifact SHA256:       c8968363e4c2cd612fd34a96fcade13bb012dbba1b73ba90568712431d930915
focused tests:         32 passed, 0 skipped
related Stage 7 HEM:   67 passed, 0 skipped
full repository:       546 passed, 0 skipped
failures / errors:     0 / 0
CoolProp:              8.0.0
compileall:            success
git diff --check:      success
```

The installed-CoolProp endpoint test confirmed through the canonical `rho/e` path:

```text
2 MPa / Q=0 -> SATURATED_LIQUID_ENDPOINT
2 MPa / Q=1 -> SATURATED_VAPOR_ENDPOINT
```

All four permanent CoolProp workflows passed after removal of the temporary validation
workflow.

### PR #66 — central record synchronization

PR #66 synchronized the central verification index and execution log through PR #65.
No production source or numerical behavior changed.

### PR #67 — mixed accepted-state EOS

PR #67 added `VerificationHEMLiquidOpenTwoPhaseEOS` for synchronized accepted arrays that
contain both supported liquid and open liquid-vapor two-phase cells. It accepts only
`LIQUID_CANDIDATE` and `OPEN_TWO_PHASE`, rejects endpoints and vapor-side or guarded
states, requires transported quality to match equilibrium quality within `1e-10`, and
uses the same existing equilibrium sound-speed estimator on both accepted regions.

Authoritative validation:

```text
workflow run:          29933435558
artifact ID:           8535107304
artifact SHA256:       55a0362a7e40b681d017f1ae7405f581129c55acecef81e6e95e5bcf324a0c61
focused tests:         37 passed, 0 skipped
related Stage 7 HEM:  141 passed, 0 skipped
full repository:      583 passed, 0 skipped
failures / errors:     0 / 0
CoolProp:              8.0.0
```

The installed-CoolProp mixed array combined `5 MPa / 280 K` liquid with
`2 MPa / Q=0.50` open two phase. The `2 MPa / Q=0` endpoint was rejected with
`endpoint_acoustic_closure_not_established`.

### PR #68 — liquid state-pair property survey

PR #68 constructed 11 fixed liquid candidates over 2–5 MPa and 0.5–10 K subcooling.
Every candidate was re-evaluated through the canonical `rho/e` phase and acoustic paths;
all 11 were accepted as supported liquid states.

Nine controlled ordered pairs were screened through a stationary conservative-blend
proxy:

```text
candidate count:             11
accepted liquid candidates:  11
pair count:                   9
ALL_LIQUID pairs:             1
OPEN_TWO_PHASE pairs:         8
endpoint/guard/backend:       0
```

The blend proxy is not an FVM step or physical process path. It nominated candidates for
the later FVM dry-run gate only.

| role | left state | right state | property-screen observation |
|---|---|---|---|
| strong candidate | 5 MPa / 5 K subcooling | 2 MPa / 5 K subcooling | first sampled open point at `lambda=0.1`; max `q_eq=1.3397273027615007e-3` |
| moderate candidate | 5 MPa / 5 K subcooling | 3 MPa / 5 K subcooling | first sampled open point at `lambda=0.2`; max `q_eq=5.331295761643359e-4` |
| liquid control | 5 MPa / 5 K subcooling | 4 MPa / 5 K subcooling | all sampled points liquid; max `q_eq=0` |

Authoritative validation:

```text
workflow run:          30008209125
artifact ID:           8563976259
artifact SHA256:       688b7e0c79647a9c203f24317e7404f34e5a471c22852095796f72391ca36f02
focused tests:         18 passed, 0 skipped
related Stage 7 HEM:  159 passed, 0 skipped
full repository:      601 passed, 0 skipped
failures / errors:     0 / 0
CoolProp:              8.0.0
```

All four permanent CoolProp workflows passed after removal of the temporary validation
workflow.

## First liquid-to-two-phase FVM crossing verification — PRs #69–#72

### PR #69 — central synchronization through the state-pair survey

PR #69 synchronized the master index and execution log through PR #68. It changed only
the two central verification documents. Merge:
`4c0960d32a03269828a8a0d3e2d2c8c9c8322f62`.

### PR #70 — raw one-step FVM crossing

PR #70 exercised the actual existing `FvmSolver.step()`, first-order Rusanov flux, CFL
path, transmissive boundaries, and an all-liquid `q=0` initial state for the three
ledger-backed pairs.

```text
strong 5 -> 2 MPa:    OPEN_TWO_PHASE; crossing cells 3, 4
moderate 5 -> 3 MPa:  OPEN_TWO_PHASE; crossing cell 4
control 5 -> 4 MPa:   ALL_LIQUID; crossing cells none
```

The strong case produced maximum raw `q_eq=5.911503500507591e-4`; the moderate case
produced `6.844477600333753e-5`; the control remained at `q_eq=0`. Transported raw
quality remained exactly zero, which created the intended pre-projection mismatch.

Authoritative validation:

```text
merge:                    38e841af97ac0adbebf42dbe36a17c1edc6c5246
validated head:           a870d313bd821bc05ba5e3fdd2ab155edadb8de9
workflow run:             30015273238
artifact ID:              8566944015
artifact SHA256:          15569960f65261d16f79d8341ab2706fb61309a5bfd044e1cc0a846bf099f34c
focused tests:            15 passed, 0 skipped
related Stage 7 HEM:     174 passed, 0 skipped
full repository:         616 passed, 0 skipped
```

### PR #71 — projected crossing and accepted-state recovery

PR #71 applied the existing equilibrium-quality projection to the raw crossing state,
required projection cells to equal raw crossing cells, recovered the synchronized state
through the mixed accepted-state EOS, confirmed a second projection was a no-op, and
closed projection vapor accounting.

```text
strong case projection cells:   3, 4
strong projection vapor source: 7.054022964126832e-4 kg
moderate projection cells:      4
moderate vapor source:          6.563798045383618e-5 kg
control projection cells:       none
control vapor source:           0 kg
post q mismatch:                0 for all cases
```

Authoritative validation:

```text
merge:                    ceaba980e5e7f7305424df8bd1e9e6b4f1acfe40
validated head:           7c04a728b1369ed41f083d68b73deb81e92ac374
workflow run:             30018942238
artifact ID:              8568448978
artifact SHA256:          fc577459c65f29a95179dc5a98ef7813a82f14ba8de945a254626555a29c59da
focused tests:            12 passed, 0 skipped
related Stage 7 HEM:     186 passed, 0 skipped
full repository:         628 passed, 0 skipped
```

### PR #72 — frozen repeatable Case A and matched Case B

PR #72 repeated the strong crossing and matched liquid control three times each using
fresh solver/EOS instances. Case A stopped at its first accepted crossing; Case B ran to
the exact same physical time.

Frozen conditions:

```text
cells / length / diameter: 8 / 1.0 m / 0.10 m
CFL / flux:                0.20 / existing first-order Rusanov
boundaries / source:       transmissive / none
Case A:                     5 MPa / 5 K -> 2 MPa / 5 K subcooling
Case B:                     5 MPa / 5 K -> 4 MPa / 5 K subcooling
repeat count:               3 each
```

Every Case A execution produced:

```text
outcome:                    ACCEPTED_CROSSING
crossing step / time:       1 / 3.356317173211922e-5 s
crossing / projection:      cells 3, 4 / cells 3, 4
maximum q_eq:               5.911503500507591e-4
projection vapor source:    7.054022964126832e-4 kg
post q mismatch:            0
second projection:          no-op
final-state SHA256:         78897b5c8ca57221186ccf3e0aa69e1492a942cc2e8dee0abb440a3e2e08e039
```

Every Case B execution ended at the same physical time and produced:

```text
outcome:                    MATCHED_ALL_LIQUID
crossing / projection:      none / none
projection vapor source:    0 kg
all final regions:          LIQUID_CANDIDATE
final-state SHA256:         8c09735ee9185cfb34b2186be30b32d78ec73350e211762d92c372e0b9f23a59
```

Authoritative validation:

```text
merge:                    628800530851b0cb677bc0a6bedcb85a13a303d1
validated head:           825ebba11b7ea273c81db717c097d8f1122ae092
workflow run:             30105917479
artifact ID:              8601660179
artifact SHA256:          02b13cb63704ea63d826f1e1feab209c4bd5b83b4a5fec7e3936af114e0cbc7b
focused tests:            14 passed, 0 skipped
related Stage 7 HEM:     200 passed, 0 skipped
full repository:         642 passed, 0 skipped
```

The Case A/B pair is the first-order software-verification regression control. Its hashes
are environment-specific deterministic evidence, not physical-accuracy or design-use
acceptance criteria.

## Pipeline-depressurization prototype and boundary — PRs #73–#75

### PR #73 — central synchronization through frozen Case A/B

PR #73 synchronized the master index and execution log through PR #72. It changed only the
two central verification documents. Merge:
`3e55b3fae88d813437654c144d0157de5b6d398f`.

### PR #74 — minimal pipeline-depressurization prototype specification

PR #74 fixed the first controlled pipeline-depressurization problem:

```text
pipe length / diameter / cells: 1.0 m / 0.10 m / 32
initial state:                  5 MPa / 5 K subcooling, u=0, q=0
left boundary:                 reflective
right boundary:                prescribed pressure + 5 K subcooling
flux / CFL:                    existing first-order Rusanov / 0.10
friction / heat / gravity:     none / none / none
fixed outlet paths:            5→2, 5→3, and 5→4 MPa
```

The specification requires direct raw `rho/e` transition detection before projection,
first-accepted-crossing stop, explicit endpoint/forbidden/reverse-flow/backend outcomes,
crossing/projection cell agreement, second-projection no-op, and separate boundary and
projection vapor accounting. It forbids tuning schedules, algorithms, or tolerances to
manufacture a crossing.

```text
merge:                       49b34bf955a5dd1f0d106f2e81f55aff3bd24add
validated head:              8640d6f73421ec3d4b7bf64b20e09f7445d32149
workflow run:                30135136669
artifact ID:                 8612546071
artifact SHA256:             5b2e391e32b984eab82c6e5d316add05c54f9e2ecc411580523e1f4323b1b69b
specification tests:         9 passed, 0 skipped
frozen Case A/B tests:      14 passed, 0 skipped
full repository:           651 passed, 0 skipped
```

### PR #75 — prescribed-subcooled outlet boundary Increment 1

PR #75 implemented the boundary-construction layer without executing an FVM time step:

- pressure-plus-positive-subcooling state provider using CoolProp `P,T -> rho,e`;
- strict phase, equilibrium-quality, void-fraction, acoustic, round-trip, and mixed-EOS
  acceptance checks;
- right-side `outlet_only` adapter with copied adjacent interior velocity;
- conservative ghost construction using boundary equilibrium quality, never interior quality;
- explicit reflective fallback diagnostics for reverse flow;
- atomic fail-fast behavior before ghost-cell mutation;
- fixed 65-point preflight for every 5→2/3/4 MPa boundary path.

Real CoolProp 8.0.0 preflight result:

```text
requested / accepted samples:       195 / 195
LIQUID_CANDIDATE samples:           195
q_eq = 0 / alpha = 0 samples:       195 / 195
endpoint / open-two-phase samples:  0 / 0
guard or backend failures:          0
pipeline FVM time step:             not executed
```

Authoritative validation:

```text
merge:                             9982c52bc4c26fac991972f0a8156c857e4bf21f
validated implementation head:    c94458933741866812286ea1e77bd288f7c4e0a2
workflow run:                      30137665050
artifact ID:                       8613415710
artifact SHA256:                   27f43c28566868fd13ec69e207cba3c5ac12e6795627c6045ac9d28b496ef5e0
dependency-free boundary tests:    18 passed, 0 skipped
installed-CoolProp boundary tests:  6 passed, 0 skipped
prototype specification tests:      9 passed, 0 skipped
frozen Case A/B tests:              14 passed, 0 skipped
full repository:                   675 passed, 0 skipped
```

The boundary remains a prescribed numerical boundary. It is not a finite tank, valve,
orifice, release-rate, or external flashing model.

## Historical checkpoint after PR #75 — superseded

At the PR #75 checkpoint, the prescribed-subcooled outlet boundary and its 195-sample
preflight had been software-verified, but that boundary had not yet been connected to a
pipeline FVM time step. The former "Current technical conclusion" and "Next gates" text
below this point described that then-current state.

That checkpoint is retained here only as historical context and is superseded by the
2026-07-26 current-state block and the PR #77/#79/#82/#84 continuation record above.
Subsequent merged work executed the fixed boundary-driven pipeline matrix, diagnosed the
4 MPa subthreshold crossing, completed the 32/64/128-cell mesh matrix, and fixed the
128-cell CFL contract with exact CFL 0.10 replay.

Gate 4 completed in PR #90 with the disposition `CFL_SENSITIVITY_OBSERVED`. The next
controlled numerical gate is the independent near-saturation acoustic-continuity review.
Gate P2, mesh-independent accuracy, CFL-independent crossing, post-crossing propagation,
physical Validation, design use, and production HEM activation remain unapproved.
