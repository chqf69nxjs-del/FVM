# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-23

- Stage 1–6: `COMPLETE`
- Stage 7: `IN_PROGRESS`
- recorded development `main`: `640b69c576501ec812cbc2919f35c62526b15974`
- V-013 first-order propagation/reflection baseline: `FORMALIZED; MERGED` in PR #51
- pure-CO2 HEM thermodynamic and phase foundation: `MERGED` in PRs #54–#57
- dynamic equilibrium-quality synchronization: `IMPLEMENTED; MERGED` in PRs #59–#60
- nonuniform open-two-phase activated case: `OBSERVED; MERGED` in PR #61
- equal-pressure contact no-op comparison: `OBSERVED; MERGED` in PR #62
- central quality-sync record synchronization: `MERGED` in PR #63
- first liquid-to-two-phase boundary-crossing specification: `MERGED` in PR #64
- liquid-to-two-phase boundary-region and transition classifier: `IMPLEMENTED; MERGED` in PR #65
- crossing-groundwork central-record synchronization: `MERGED` in PR #66
- mixed liquid/open-two-phase accepted-state verification EOS: `IMPLEMENTED; MERGED` in PR #67
- liquid state-pair property survey: `VALIDATED; MERGED` in PR #68
- MUSCL/TVD reconstruction scaffold: `OPEN; READY FOR REVIEW` in PR #52
- scalar-advection comparison: `VALIDATED STACKED DRAFT` in PR #53
- active physical-model gate: minimal first-order liquid-to-two-phase FVM dry run
- physical Validation: `NOT ESTABLISHED`
- design-use acceptance: `NOT ESTABLISHED`
- production HEM activation: `NOT APPROVED`
- two-phase acoustic accuracy band: `NOT APPROVED`

The main development objective remains a conservative one-dimensional LCO2 pipeline
transient code that can progress from liquid states through flashing and liquid-vapor
two-phase formation. The existing first-order FVM remains the numerical control.

The merged HEM path now supports guarded real-fluid state evaluation, explicit phase
classification, an equilibrium sound-speed candidate, exact preservation of a uniform
open-two-phase state, dynamic equilibrium-quality synchronization inside the open
two-phase region, verification-only classification of liquid-side boundary regions and
transition events, mixed accepted liquid/open-two-phase primitive evaluation, and
reproducible property-level state-pair screening. An actual first-order liquid-to-two-phase
FVM crossing and pipeline depressurization remain unverified.

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

PR #61 produced measurable projection activity while remaining open two-phase:

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

The blend proxy is not an FVM step or physical process path. It nominates candidates for
the next dry run only.

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

## Current technical conclusion

The first-order verification path now demonstrates that:

- a pure-CO2 `rho/e` state can be evaluated through explicit HEM guards;
- open two-phase states can be advanced through Rusanov flux and CFL;
- one uniform stationary open-two-phase state is preserved exactly;
- nonuniform open-two-phase transport can create a measurable transported/equilibrium
  quality mismatch;
- projection repairs that mismatch without changing conservative mass, momentum, or
  total energy;
- an equal-pressure quality contact remains a true projection no-op;
- mass, momentum, energy, and phase-vapor budgets close for the reviewed dynamic cases;
- liquid-side regions, endpoints, and transition events can be classified directly from
  `rho/e` without using transported quality;
- mixed accepted liquid/open-two-phase arrays can be converted to primitive and acoustic
  states cell by cell;
- reproducible liquid state-pair screening can nominate strong, moderate, and liquid-control
  candidates without changing algorithms or tolerances.

The current evidence does **not** demonstrate:

```text
liquid-to-two-phase FVM boundary crossing:      not verified
open-two-phase to vapor crossing:               not verified
Case A / matched Case B:                        not frozen
pipeline depressurization:                      not implemented
two-phase acoustic accuracy band:               not approved
production HEM activation:                      not approved
physical Validation:                            false
design-use acceptance:                          false
```

## Approval boundary

```text
verification_only = true
property_backend_name = coolprop_co2
property_backend_design_status = not_approved_for_design_use
actual_first_order_fvm_crossing_verified = false
screening_is_fvm_solution = false
case_a_frozen = false
case_b_frozen = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

## Next gates

1. perform minimal first-order FVM dry runs on the three ledger-backed candidate pairs;
2. begin with one raw Rusanov update before projection and classify the resulting regions;
3. retain 8–16 cells, transmissive boundaries, no source, low CFL, and fixed algorithms;
4. after the raw path is understood, connect projection and mixed accepted-state evaluation;
5. record every attempt and vary only one permitted case parameter at a time;
6. freeze the first repeatable crossing Case A and matched no-crossing Case B;
7. implement the first-crossing capture runner and close conservation and vapor budgets;
8. only after stable crossing, build the first LCO2 pipeline-depressurization prototype;
9. retain PRs #52/#53 as later numerical-improvement assets until the first-order dynamic
   HEM path is stable.
