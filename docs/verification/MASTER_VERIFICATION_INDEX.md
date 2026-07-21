# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-21

- Stage 1–6: `COMPLETE`
- Stage 7: `IN_PROGRESS`
- current `main`: `3e116cbcd853bcb1b52fe001819a4b300d5997ff`
- V-013 first-order propagation/reflection baseline: `FORMALIZED; MERGED` in PR #51
- pure-CO2 HEM thermodynamic and phase foundation: `MERGED` in PRs #54–#57
- dynamic equilibrium-quality synchronization: `IMPLEMENTED; MERGED` in PRs #59–#60
- nonuniform open-two-phase activated case: `OBSERVED; MERGED` in PR #61
- equal-pressure contact no-op comparison: `OBSERVED; MERGED` in PR #62
- MUSCL/TVD reconstruction scaffold: `OPEN; READY FOR REVIEW` in PR #52
- scalar-advection comparison: `VALIDATED STACKED DRAFT` in PR #53
- active physical-model gate: first liquid-to-two-phase phase-boundary crossing specification
- physical Validation: `NOT ESTABLISHED`
- design-use acceptance: `NOT ESTABLISHED`
- production HEM activation: `NOT APPROVED`

The main development objective remains a conservative one-dimensional LCO2 pipeline
transient code that can progress from liquid states through flashing and liquid-vapor
two-phase formation. The current first-order FVM remains the numerical control.

The merged HEM path now supports guarded real-fluid state evaluation, explicit phase
classification, an equilibrium sound-speed candidate, exact preservation of a uniform
two-phase state, and dynamic equilibrium-quality synchronization inside the open
two-phase region. Liquid-to-two-phase boundary crossing and pipeline depressurization
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

## First-order V-013 baseline

The current production FVM is fixed as a selectable first-order software/numerical
control. It reproduces wave direction, approximate timing, reflection signs, and
essential boundary-condition behavior across V-013A/B/C.

| case | expected identity | observed conclusion | finest-mesh final peak ratio |
|---|---|---|---:|
| V-013A | right-going `A+` | direction and approximate speed consistent | `0.57499430` |
| V-013B | `A-_reflected = A+_incident` | pressure sign positive; velocity sign negative | `0.57499450` |
| V-013C | `A-_reflected = -A+_incident` | pressure sign negative; velocity sign positive | `0.57212615` |

The common limiting issue is strong first-order numerical diffusion. Approximately
`57%` peak retention at `n=400` is an observed limitation, not an approved accuracy
target, design margin, or CI regression band.

Formalization documents:

- [`stage7_v013_baseline_and_limitations.md`](stage7_v013_baseline_and_limitations.md)
- [`v013_baseline_definition_v1.json`](v013_baseline_definition_v1.json)
- [`stage7_v013_ci_light_proposal.md`](stage7_v013_ci_light_proposal.md)

CI-light remains `PROPOSED; NOT APPROVED; NOT IMPLEMENTED`.

## Numerical-diffusion improvement assets

PR #52 contains a solver-independent reconstruction layer with exact first-order and
componentwise MUSCL reconstruction plus minmod, MC, and van Leer limiters. It does not
connect to `FvmSolver` or change production numerical states.

PR #53 contains a periodic scalar-advection comparison. At `n=200`, peak retention
under SSP-RK2 was approximately:

```text
first order:       0.57795218
MUSCL minmod:      0.88811719
MUSCL MC:          0.96768181
MUSCL van Leer:    0.94953622
```

At `n=400`, MUSCL MC retained `0.98833595` of the peak. These results rank later
numerical candidates; they do not approve a production limiter, reconstruction
variable set, fallback policy, or time integrator.

Higher-order production connection remains deferred until the first-order dynamic HEM
path, including phase-boundary crossing, is established.

## Pure-CO2 HEM foundation — PRs #54–#57

| PR | increment | final reviewed head | focused / full tests | principal evidence |
|---|---|---|---|---|
| #54 | thermodynamic scaffold and deterministic 0-D path | `39a394698383879225216aee403c1221fe454e0e` | `24 / 406` | path states `23 / 23`; artifact formats `4 / 4` |
| #55 | explicit CoolProp phase classification | `97ffe4e57c3a006ae27702749c417f9e3989aba8` | `39 / 423` | phase-map states `9 / 9`; sound-speed calls `0` |
| #56 | equilibrium sound-speed closure candidate | `3c21be4410e808f22888edd9814204a25df40a4c` | `63 / 447` | sound-speed states `10 / 10`; two-phase states `7 / 7` |
| #57 | uniform stationary two-phase FVM preservation | `45cdfe3da409e98825bc3b2ab52265f5f51f2900` | `76 / 460` | cells / steps `8 / 8`; all measured drift exactly `0` |

The foundation demonstrates:

- guarded `rho/e` evaluation through the real-fluid backend contract;
- explicit distinction among liquid, liquid-vapor two-phase, vapor, and guarded-out states;
- equilibrium `p/T/Q/phase/alpha` evaluation separated from acoustic closure;
- an independently defined equilibrium sound-speed candidate;
- verification-only connection to Rusanov flux and CFL;
- exact preservation of one uniform stationary open-two-phase state.

The two-phase sound-speed observations remain closure candidates, not an approved
physical acoustic map.

## Dynamic equilibrium-quality synchronization — PRs #59–#62

### Purpose

The FVM transports the fourth conservative component `rho*q`. The thermodynamic state
`rho/e` independently implies an equilibrium quality `q_eq`. The synchronization
operator enforces:

```text
rho*q <- rho*q_eq
```

while requiring `rho`, `rho*u`, and `rho*E` to remain bitwise unchanged.

The operator is verification-only, fail-fast, and separate from the generic HEM/HNE
phase-change skeletons.

### Milestone summary

| PR | increment | final reviewed head | focused / full tests | primary evidence |
|---|---|---|---|---|
| #59 | specification and acceptance contract | `b7b00432dc6c0ad9197f3f9809c22fb1c247c4ed` | specification only | separate no-op and activated cases; no clipping; fail-fast guards |
| #60 | `HEMEquilibriumQualityProjection` implementation | `1da2ffc9047a71aedc343eb932e7f4115bc004a2` | `72 / 478` | artifact `8483707741`; SHA256 `bdf06b22fbc81ca044ed57dfab9b3a18987c05914bc03b0da3734dc7e7885a6f` |
| #61 | real-CO2 nonuniform pressure-offset case | `a0e1024aa5bf9f54c205dfc8e81e614080354214` | `46 / 493` | artifact `8483939146`; SHA256 `4156346821f0c04b5d5a569fd6bb64edeb07854a4ae905c4b29f5b3e51152447` |
| #62 | equal-pressure no-op and activated contrast | `1b4a754de4e79b0d4bb88acb22b94301d72ca142` | `67 / 514` | artifacts `8488096499`, `8491343302`; backend traceability added after review |

### PR #60 — projection implementation

The operator:

- evaluates equilibrium quality directly from `rho/e`;
- changes only `rho*q`;
- preserves mass, momentum, and total energy bitwise;
- preserves exact no-op behavior inside its activation tolerance;
- rejects unsupported, undefined, non-finite, guarded, or out-of-range states;
- records phase, quality, projection, vapor-source, and energy-budget diagnostics.

This establishes software behavior, not production HEM approval.

### PR #61 — activated nonuniform open-two-phase case

Fixed case:

```text
left:        2.01 MPa / q=0.45 / u=0
right:       1.99 MPa / q=0.55 / u=0
cells:       32
CFL:         0.10
steps:       4
boundaries:  transmissive
source:      none
```

Primary observations:

```text
projection total cell updates:          20
projected cells by step:                 2, 4, 6, 8
maximum |delta q|:                       2.4143668471476865e-5
maximum post-projection q mismatch:      5.551115123125783e-16
maximum velocity:                        0.2547984084365163 m/s
cumulative vapor source:                 3.501570117236952e-5 kg
```

All cells remained in the open liquid-vapor two-phase region. Mass, momentum, energy,
and vapor budgets closed to floating-point tolerance.

### PR #62 — equal-pressure no-op contrast

The equal-pressure case uses:

```text
left:        2.00 MPa / q=0.45 / u=0
right:       2.00 MPa / q=0.55 / u=0
cells:       32
CFL:         0.10
steps:       4
```

Primary observations:

```text
projection total cell updates:          0
projected cells by step:                 0, 0, 0, 0
maximum |delta q|:                       4.440892098500626e-16
transport-changed cells:                 8
mixed-quality cells:                     8
initial maximum quality jump:            0.10000000000000037
final maximum quality jump:              0.06788855198828081
maximum pressure span:                   1.6298145055770874e-9 Pa
projection vapor source:                 0.0 kg
```

The contact spreads through first-order numerical diffusion, but conservative mixing
remains on the same saturation line. The zero projection count is therefore an
exercised no-op, not an unexercised solver path.

The activated/no-op maximum-`|delta q|` ratio is approximately `5.44e10`.

A P2 review required property-backend traceability. The final artifacts now retain:

```text
model_name
fluid_name
property_backend_name = coolprop_co2
property_backend_design_status = not_approved_for_design_use
coolprop_version
numpy_version
output_version
```

The same information is included in the PNG figure footers. Follow-up validation run
`29820825656` and artifact `8491343302` completed successfully. Artifact SHA256:
`ec93eb009d6c9b0d870437d1a9b493ff16823d55d944726bacd5237c184eeec5`.

## Current technical conclusion

The first-order verification path now demonstrates that:

- a pure-CO2 `rho/e` state can be evaluated through explicit HEM guards;
- open two-phase states can be advanced through Rusanov flux and CFL;
- one uniform stationary state is preserved exactly;
- a nonuniform open-two-phase state can create a measurable transported/equilibrium
  quality mismatch;
- the projection repairs that mismatch without changing conservative mass, momentum,
  or total energy;
- an equal-pressure quality contact remains a true projection no-op even while the FVM
  numerically diffuses the contact;
- mass, momentum, energy, and phase-vapor budgets remain closed in both cases.

The current evidence does **not** demonstrate:

```text
liquid-to-two-phase phase-boundary crossing:   not verified
open-two-phase to vapor crossing:              not verified
pipeline depressurization:                     not implemented
two-phase acoustic accuracy band:              not approved
production HEM activation:                     not approved
physical Validation:                           false
design-use acceptance:                         false
```

## Approval boundary

```text
verification_only = true
property_backend_name = coolprop_co2
property_backend_design_status = not_approved_for_design_use
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

## Next gates

1. define the first liquid-to-two-phase boundary-crossing state pair;
2. specify allowed phase-class transitions per step;
3. define the `q=0` endpoint and tolerance policy;
4. define fail-fast behavior for critical, solid, unknown, and backend-invalid states;
5. define required phase, quality, sound-speed, projection, and budget evidence;
6. implement a short first-order transmissive-boundary expansion runner;
7. only after stable boundary crossing, build the first LCO2 pipeline depressurization prototype;
8. retain PRs #52/#53 as later numerical-improvement assets until the first-order dynamic HEM path is stable.
