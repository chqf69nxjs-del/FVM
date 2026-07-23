# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-23

- Stage 1–6: `COMPLETE`
- Stage 7: `IN_PROGRESS`
- current development `main`: `640b69c576501ec812cbc2919f35c62526b15974`
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

The development objective remains a conservative one-dimensional LCO2 pipeline
transient code that can progress from supported liquid states through flashing and
liquid-vapor two-phase formation. The existing first-order FVM remains the numerical
control.

The merged HEM path now supports guarded real-fluid state evaluation, explicit phase
classification, an equilibrium sound-speed candidate, exact preservation of a uniform
open-two-phase state, dynamic equilibrium-quality synchronization, verification-only
liquid-to-two-phase transition classification, mixed accepted liquid/open-two-phase
primitive evaluation, and reproducible property-level state-pair screening.

An actual first-order liquid-to-two-phase FVM crossing, a frozen Case A/Case B pair,
long-duration pipeline depressurization, physical Validation, and design-use acceptance
remain unverified.

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

The current first-order FVM is retained as a selectable software/numerical control. It
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

## Pure-CO2 HEM foundation — PRs #54–#57

The foundation establishes:

- guarded CoolProp evaluation from canonical `rho/e`;
- explicit liquid, open-two-phase, vapor, critical, supercritical, and guarded-state classification;
- separation of equilibrium state evaluation from acoustic closure;
- one equilibrium sound-speed candidate based on guarded pressure derivatives;
- verification-only connection to the existing primitive, Rusanov, and CFL interfaces;
- exact preservation of one uniform stationary open-two-phase state.

The sound-speed observations are closure candidates. They are not a validated acoustic map.

## Dynamic equilibrium-quality synchronization — PRs #59–#62

The conservative state transports `rho*q`, while `rho/e` independently implies an
equilibrium quality `q_eq`. The reviewed operator enforces:

```text
rho*q <- rho*q_eq
```

while preserving `rho`, `rho*u`, and `rho*E` bitwise.

PR #61 demonstrated measurable projection activity in a nonuniform open-two-phase case.
PR #62 demonstrated an equal-pressure nonuniform contact that remained a projection no-op.
Mass, momentum, total energy, and phase-vapor accounting closed to the documented
floating-point tolerances in both cases.

## First liquid-to-two-phase crossing groundwork — PRs #64–#68

### PR #64 — crossing specification

The specification separates:

```text
thermodynamic crossing
projection activation
accepted-state EOS evaluation
test-evidence strength
```

It requires raw transition detection directly from updated `rho/e`, before projection.
It distinguishes ordinary liquid `q=0` from the saturated-liquid endpoint by phase class.
Exact endpoint landing remains fail-fast because endpoint acoustic closure is not yet
established.

### PR #65 — transition classifier

The classifier derives the verification regions:

```text
LIQUID_CANDIDATE
SATURATED_LIQUID_ENDPOINT
OPEN_TWO_PHASE
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
```

and classifies no-transition, boundary-touch, target crossing, reverse transition, and
forbidden transition events without using transported quality as the phase classifier.

### PR #67 — mixed accepted-state EOS

`VerificationHEMLiquidOpenTwoPhaseEOS` processes synchronized arrays containing both:

```text
LIQUID_CANDIDATE
OPEN_TWO_PHASE
```

cell by cell. It rejects endpoints, vapor-side states, guarded states, invalid properties,
and transported/equilibrium quality mismatch. The same existing equilibrium sound-speed
estimator is used on liquid and open-two-phase cells; no runtime CoolProp `A` switch was
introduced.

Authoritative validation:

```text
CoolProp:                   8.0.0
focused mixed-EOS tests:   37 passed, 0 skipped
related Stage 7 HEM:      141 passed, 0 skipped
full repository:          583 passed, 0 skipped
failures / errors:          0 / 0
```

Evidence:

```text
workflow run:   29933435558
artifact ID:    8535107304
artifact SHA256:
55a0362a7e40b681d017f1ae7405f581129c55acecef81e6e95e5bcf324a0c61
```

### PR #68 — liquid state-pair property survey

The survey constructed 11 fixed pressure/subcooling liquid candidates and re-evaluated
every candidate through the canonical `rho/e` phase and acoustic paths. All 11 candidates
were accepted as supported liquids.

Nine controlled ordered pairs were screened with a stationary conservative-blend proxy:

```text
candidate count:              11
accepted liquid candidates:   11
pair count:                     9
ALL_LIQUID pairs:               1
OPEN_TWO_PHASE pairs:           8
endpoint/guard/backend failure: 0
```

The proxy is not an FVM step or a physical process path. It nominates candidates for the
next dry run only.

Current leading candidates:

| role | left state | right state | property-screen observation |
|---|---|---|---|
| strong crossing candidate | 5 MPa / 5 K subcooling | 2 MPa / 5 K subcooling | first sampled open point at `lambda=0.1`; max `q_eq=1.3397273027615007e-3` |
| moderate candidate | 5 MPa / 5 K subcooling | 3 MPa / 5 K subcooling | first sampled open point at `lambda=0.2`; max `q_eq=5.331295761643359e-4` |
| liquid negative-control candidate | 5 MPa / 5 K subcooling | 4 MPa / 5 K subcooling | all sampled points liquid; max `q_eq=0` |

Authoritative validation:

```text
CoolProp:                    8.0.0
focused survey tests:       18 passed, 0 skipped
related Stage 7 HEM:       159 passed, 0 skipped
full repository:           601 passed, 0 skipped
failures / errors:           0 / 0
```

Evidence:

```text
workflow run:   30008209125
artifact ID:    8563976259
artifact SHA256:
688b7e0c79647a9c203f24317e7404f34e5a471c22852095796f72391ca36f02
```

## Current technical conclusion

The software now has the components required to observe a first liquid-to-two-phase raw
FVM transition without changing the production solver:

```text
supported liquid initial states
        |
        v
existing first-order Rusanov/CFL update
        |
        v
direct raw rho/e region and transition classification
        |
        v
equilibrium-quality projection
        |
        v
mixed liquid/open-two-phase accepted-state EOS
```

The property survey provides three ledger-backed trial pairs, but it does not prove that
the actual Rusanov update follows the screened blend path. The next gate must therefore
exercise the real first-order FVM update rather than expand property screening further.

## Active next gate — minimal first-order FVM dry run

The next increment should:

1. use the three ledger-backed candidate pairs without changing property or numerical algorithms;
2. start with a small 8–16-cell, first-order, transmissive-boundary case;
3. use the existing Rusanov flux and CFL calculation;
4. observe one raw FVM step before projection;
5. classify each result as all-liquid, endpoint landing, open-two-phase crossing, forbidden, guard, or backend failure;
6. only after the raw path is understood, connect projection and mixed accepted-state evaluation;
7. retain every trial in a reproducible ledger;
8. freeze Case A and matched Case B only after repeatable behavior is observed.

The immediate gate does not approve long-duration depressurization, higher-order
reconstruction, reverse crossing, production activation, physical Validation, design use,
or an acoustic accuracy band.

## Approval boundary

```text
verification_only = true
actual_first_order_fvm_crossing_verified = false
case_a_frozen = false
case_b_frozen = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```
