# Stage 7 Execution Log

Earlier entries through the V-013 reference-core checkpoint are preserved in
[`archive/stage7_execution_log_through_v013_reference_core.md`](archive/stage7_execution_log_through_v013_reference_core.md).

## 2026-07-19 to 2026-07-20 — V-013 reference baseline

### PR #48 — incident propagation

Status: `OBSERVED; MERGED`. Merge commit:
`613b21622b22402fbf7b8d77b1d881db7ff5f28e`.

```text
primary run:         29647234616
focused / full:      39 / 315 passed
CoolProp:            8.0.0
n=400 peak ratio:    0.57499430
```

Wave direction and approximate propagation speed were consistent. Strong numerical
broadening remained material at the finest mesh.

### PR #49 — rigid-wall reflection

Status: `OBSERVED; MERGED`. Merge commit:
`bc874193de6a4c019073b6cf629e99ec5dfa6602`.

```text
workflow run:       29684930259
focused tests:      57 passed, 0 skipped
full repository:    350 passed, 0 skipped
artifact ID:        8441899419
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

Pressure reflection was positive, velocity reflection was negative, and wall-face
velocity, mass flux, and energy flux were exactly zero.

### PR #50 — fixed-pressure reflection

Status: `OBSERVED; MERGED`. Merge commit:
`f403103c46a1d618ce2f2345c986e29b921b664a`.

```text
workflow run:       29692477941
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
artifact ID:        8444138380
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
n=400 peak ratio:   0.57212615
```

The reflected pressure sign was negative, reflected velocity sign was positive, and the
returning characteristic was left-going `A-`.

### PR #51 — first-order baseline formalization

Status: `FORMALIZED; MERGED`. Merge commit:
`62390bd526ae99b6702f4ed76e3594e1bf01259b`.

```text
baseline-definition integrity:  4 passed
full repository:               389 passed
permanent workflows:           4 / 4 success
```

The first-order FVM was fixed as a selectable software/numerical control. It is not an
exact solution, physical Validation result, design-use approval, or approved numerical
accuracy band.

## 2026-07-20 — Numerical-diffusion improvement assets

PR #52 is `OPEN; READY FOR REVIEW` and contains a solver-independent MUSCL/TVD
reconstruction scaffold. Final head:
`829880e88010ea808b316e09f28f26a0a18c7f03`.

PR #53 is a `VALIDATED STACKED DRAFT` based on PR #52. Final head:
`ff72bd303a99d832bad6d13536ff9b5682eeb4f9`.

At `n=200`, periodic scalar-advection peak retention under SSP-RK2 was:

```text
first order:       0.57795218
MUSCL minmod:      0.88811719
MUSCL MC:          0.96768181
MUSCL van Leer:    0.94953622
```

The numerical-improvement line remains separate from the HEM physical-model line.
Production activation is deferred.

## 2026-07-20 to 2026-07-21 — Pure-CO2 HEM foundation

### PR #54 — thermodynamic scaffold and 0-D path

Status: `MERGED`. Merge commit:
`6e0779346a9adb0f3c74d790f558a6813f009ee7`.

```text
workflow run:         29739900542
artifact ID:          8459985478
artifact SHA256:      98c3e973d0f81c68bf0cf86396679964d87a3f4f1ecdb542bdbe1dbaeecf8103
focused tests:        24 passed, 0 skipped
full repository:      406 passed, 0 skipped
0-D path states:      23 / 23
```

The increment added a guarded HEM wrapper around real-fluid `rho/e` evaluation and a
deterministic liquid/two-phase/vapor path.

### PR #55 — explicit phase classification

Status: `MERGED`. Merge commit:
`e45362d1aa07bf7144f606dc32595d4ab2f7093d`.

```text
workflow run:         29744597504
artifact ID:          8461927762
artifact SHA256:      d91869f6d7fd3d18ab9e2abf1b3e9b6fecfa87228dabd5546fd8024aa7252c6a
focused tests:        39 passed, 0 skipped
full repository:      423 passed, 0 skipped
phase-map states:     9 / 9
sound-speed calls:    none
```

CoolProp `PhaseSI` was used instead of inferring phase from quality alone. Critical,
solid/below-triple, and unknown states were guarded explicitly.

### PR #56 — equilibrium sound-speed candidate

Status: `MERGED`. Merge commit:
`b098f67b71bf53bd20fc14bf80d7f4cea595a707`.

```text
c_eq^2 = (dp/drho)|e + (p/rho^2) (dp/de)|rho
workflow run:           29748093054
artifact ID:            8463388994
artifact SHA256:        97b6f04a38cd6debafc66fac3dc8b902d1abdf1fed982e04c48000ca5682ad79
focused HEM tests:      63 passed, 0 skipped
full repository:        447 passed, 0 skipped
sound-speed states:     10 / 10
two-phase states:       7 / 7
CoolProp two-phase A:   never requested
```

The closure uses guarded phase-preserving finite differences of `p(rho,e)`. The
observed two-phase values are not an approved physical acoustic map.

### PR #57 — uniform HEM-state preservation

Status: `OBSERVED; MERGED`. Merge commit:
`f27ec42d0e191065cd4d3d214a14009b07be800f`.

```text
p / q / u:             2 MPa / 0.50 / 0 m/s
cells / steps:         8 / 8
CFL:                   0.25
workflow run:          29751190749
artifact ID:           8464712262
artifact SHA256:       71f7934f6f0061191f8af09b9cdf802a5b797f628878cd045a13a94273f5e999
focused HEM tests:     76 passed, 0 skipped
full repository:       460 passed, 0 skipped
```

Every measured drift in conservative state, primitive variables, acoustic quantities,
and inventories was exactly zero. This proves preservation of one uniform open-two-phase
state, not dynamic flashing.

### PR #58 — HEM foundation record synchronization

Status: `MERGED`. Merge commit:
`dd5d3d0d10d0f93bb0d7a066e6d861f54c153b25`.

Only the central verification index and execution log changed. Production source and
numerical behavior were unchanged.

## 2026-07-21 — Dynamic equilibrium-quality synchronization

### PR #59 — synchronization specification

Status: `MERGED`. Merge commit:
`70dc41ab7bc3c5ef46d83a49e3ea8de48d84ebad`.

The specification selected a verification-only projection:

```text
rho*q <- rho*q_eq
rho unchanged bitwise
rho*u unchanged bitwise
rho*E unchanged bitwise
no silent clipping
whole-step fail-fast for unsupported states
```

### PR #60 — projection implementation

Status: `IMPLEMENTED; MERGED`. Merge commit:
`a4d525a004ae7bf5e284a882706155dce41b3eba`.

```text
workflow run:       29800804296
artifact ID:        8483707741
artifact SHA256:    bdf06b22fbc81ca044ed57dfab9b3a18987c05914bc03b0da3734dc7e7885a6f
focused tests:      72 passed
full repository:    478 passed
```

`HEMEquilibriumQualityProjection` evaluates equilibrium quality directly from `rho/e`,
projects only `rho*q`, preserves conservative mass/momentum/energy, and fails without
clipping on unsupported states.

### PR #61 — nonuniform pressure-offset activated case

Status: `OBSERVED; MERGED`. Merge commit:
`ceca2b48eb2f34cb8c1d584d80ae2619ff77271a`.

```text
left / right:       2.01 MPa, q=0.45 / 1.99 MPa, q=0.55
cells / CFL / steps: 32 / 0.10 / 4
workflow run:       29801484953
artifact ID:        8483939146
artifact SHA256:    4156346821f0c04b5d5a569fd6bb64edeb07854a4ae905c4b29f5b3e51152447
focused tests:      46 passed
full repository:    493 passed
projection updates: 20
max |delta q|:      2.4143668471476865e-5
```

All projection states remained open two phase. Mass, momentum, energy, and phase-vapor
budgets closed.

### PR #62 — equal-pressure contact/no-op comparison

Status: `OBSERVED; MERGED`. Merge commit:
`3e116cbcd853bcb1b52fe001819a4b300d5997ff`.

```text
left / right:       2.00 MPa, q=0.45 / 2.00 MPa, q=0.55
cells / CFL / steps: 32 / 0.10 / 4
workflow run:       29812617503
artifact ID:        8488096499
focused tests:      67 passed
full repository:    514 passed
projection updates: 0
max |delta q|:      4.440892098500626e-16
projection source:  0.0 kg
```

The contact was transported and diffused, but conservative mixing stayed on the same
saturation line. The zero projection count is an exercised no-op. Backend, version, and
`not_approved_for_design_use` traceability were added to the final artifacts.

### PR #63 — central quality-sync record synchronization

Status: `MERGED`. Merge commit:
`33349ff6c16373443b2626d13c1a867d54275d0a`.

Only the central verification index and execution log changed. No production source or
numerical behavior changed.

## 2026-07-22 — Liquid-to-two-phase boundary-crossing groundwork

### PR #64 — first crossing specification

Status: `MERGED`. Merge commit:
`f2b8335132741765b6d5e42f65f742cf5e241c66`.

The specification fixed the first narrow liquid-to-open-two-phase gate. Principal
choices:

```text
raw transition detection: direct rho/e evaluation before projection
transported q:            not a phase classifier
q=0 liquid vs endpoint:   distinguished by explicit phase class
endpoint landing:         BOUNDARY_TOUCH and fail-fast in first FVM gate
crossing vs projection:   separate definitions
endpoint tolerance:       existing configured value
projection tolerance:     existing configured value
crossing evidence q:      1e-6, test-only
current solver guard:     e >= 0 retained
negative control:         matched physical-time horizon
case exploration:         logged; algorithms and thresholds fixed
```

PR #64 changed documentation only. It did not connect to `FvmSolver` or prove an actual
phase-boundary crossing.

### PR #65 — boundary-region and transition classifier

Status: `IMPLEMENTED; MERGED`. Merge commit:
`fb078da84fa17d6aa8d840616c494a0bf3efd71c`.

The implementation added the verification-only regions:

```text
LIQUID_CANDIDATE
SATURATED_LIQUID_ENDPOINT
OPEN_TWO_PHASE
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
```

and transition events:

```text
NO_TRANSITION
BOUNDARY_TOUCH
LIQUID_TO_TWO_PHASE_CROSSING
REVERSE_TRANSITION
FORBIDDEN_TRANSITION
```

The classifier evaluates direct `rho/e` phase state, is independent of transported
quality, performs no clipping, forwards the configured endpoint tolerance, retains the
current non-negative-internal-energy integration guard, and fails atomically for guarded,
invalid, undefined, or inconsistent states.

Authoritative validation:

```text
validation run:        29927030452
validated head:        6fcecb578f4e061c533cf4c39aa5c968d8c72a78
artifact ID:           8532470595
artifact SHA256:       c8968363e4c2cd612fd34a96fcade13bb012dbba1b73ba90568712431d930915
focused tests:         32 passed, 0 skipped
related Stage 7 HEM:   67 passed, 0 skipped
full repository:       546 passed, 0 skipped
failures / errors:     0 / 0
compileall:            success
git diff --check:      success
CoolProp:              8.0.0
```

The installed-CoolProp endpoint test confirmed through the canonical `rho/e` path:

```text
2 MPa / Q=0 -> SATURATED_LIQUID_ENDPOINT
2 MPa / Q=1 -> SATURATED_VAPOR_ENDPOINT
```

The temporary validation workflow was removed after evidence capture. All four permanent
CoolProp workflows passed on the final permanent head.

PR #65 does not modify `FvmSolver`, flux, CFL, EOS, projection, or acoustic behavior. It
does not yet demonstrate a liquid-to-two-phase FVM crossing.

### PR #66 — crossing-groundwork central record synchronization

Status: `MERGED`. Merge commit:
`7acaa005c6d32cd48042ca5a333dcc19b5006d23`.

The central verification index and execution log were synchronized through PR #65. No
solver, EOS, flux, CFL, projection, or production behavior changed.

## 2026-07-22 to 2026-07-23 — Mixed accepted-state EOS and state-pair survey

### PR #67 — mixed liquid/open-two-phase accepted-state EOS

Status: `IMPLEMENTED; VALIDATED; MERGED`. Merge commit:
`74b019993823ec4c52f1be38fa8c12580f560686`.

The adapter `VerificationHEMLiquidOpenTwoPhaseEOS` accepts synchronized arrays containing
both `LIQUID_CANDIDATE` and `OPEN_TWO_PHASE` cells. It rejects endpoints, vapor-side and
guarded states, invalid acoustic values, and transported/equilibrium quality mismatch.
The same existing equilibrium sound-speed estimator is used on both accepted regions.

```text
quality tolerance:       1e-10
projection activation:   1e-12
transported q bounds:    strict [0, 1]
quality clipping:        none
runtime CoolProp A:      none
FvmSolver.step:          not exercised
```

The installed-CoolProp mixed-array test combined `5 MPa / 280 K` liquid and
`2 MPa / Q=0.50` open two phase. The `2 MPa / Q=0` endpoint was rejected with the expected
`endpoint_acoustic_closure_not_established` message.

Authoritative validation:

```text
validated head:             e8814c5d724f923a38f3acfa0120c10edde2c202
workflow run:               29933435558
artifact ID:                8535107304
artifact SHA256:            55a0362a7e40b681d017f1ae7405f581129c55acecef81e6e95e5bcf324a0c61
focused mixed-EOS tests:   37 passed, 0 skipped
related Stage 7 HEM:      141 passed, 0 skipped
full repository:          583 passed, 0 skipped
failures / errors:          0 / 0
CoolProp:                   8.0.0
```

The temporary validation workflow was removed after evidence capture. All four permanent
CoolProp workflows passed on the final permanent head.

### PR #68 — liquid state-pair property survey

Status: `VALIDATED; MERGED`. Merge commit:
`640b69c576501ec812cbc2919f35c62526b15974`.

The deterministic survey constructed 11 liquid candidates over 2–5 MPa and 0.5–10 K
subcooling. Every candidate was converted to canonical `rho/e` and re-evaluated through
the reviewed phase and acoustic paths. All 11 were accepted as supported liquids.

Nine controlled ordered pairs were screened with a stationary conservative-blend proxy.
The proxy is not an FVM update, physical process path, or formal crossing result.

```text
candidate count:             11
accepted liquid candidates:  11
pair count:                   9
ALL_LIQUID:                   1
OPEN_TWO_PHASE:               8
endpoint/guard/backend:       0
```

Leading dry-run candidate:

```text
left:                         5 MPa / 5 K subcooling
right:                        2 MPa / 5 K subcooling
first sampled open fraction:  lambda = 0.1
maximum screened q_eq:        1.3397273027615007e-3
```

Moderate candidate:

```text
left:                         5 MPa / 5 K subcooling
right:                        3 MPa / 5 K subcooling
first sampled open fraction:  lambda = 0.2
maximum screened q_eq:        5.331295761643359e-4
```

Liquid negative-control candidate:

```text
left:                         5 MPa / 5 K subcooling
right:                        4 MPa / 5 K subcooling
outcome:                      ALL_LIQUID
maximum screened q_eq:        0
```

Authoritative validation:

```text
validated head:             cac6887fee4f6accc4be77d59075e0da08fab77d
workflow run:               30008209125
artifact ID:                8563976259
artifact SHA256:            688b7e0c79647a9c203f24317e7404f34e5a471c22852095796f72391ca36f02
focused survey tests:       18 passed, 0 skipped
related Stage 7 HEM:       159 passed, 0 skipped
full repository:           601 passed, 0 skipped
failures / errors:           0 / 0
CoolProp:                   8.0.0
```

The temporary validation workflow was removed after evidence capture. All four permanent
CoolProp workflows passed on the final permanent head.

### PR #69 — central record synchronization through PR #68

Status: `MERGED`. Merge commit:
`4c0960d32a03269828a8a0d3e2d2c8c9c8322f62`.

Only `MASTER_VERIFICATION_INDEX.md` and `stage7_execution_log.md` changed. The active gate
was advanced from mixed accepted-state construction to the minimal first-order FVM dry
run. Solver and numerical behavior were unchanged.

## 2026-07-23 — First actual raw and projected FVM crossing

### PR #70 — actual one-step raw FVM crossing

Status: `OBSERVED; VALIDATED; MERGED`. Merge commit:
`38e841af97ac0adbebf42dbe36a17c1edc6c5246`.

The fixed eight-cell matrix used one actual existing first-order FVM step:

```text
cells / length / diameter: 8 / 1.0 m / 0.10 m
interface:                 between cells 3 and 4
CFL / flux:                0.20 / existing Rusanov
boundaries / source:       transmissive / none
initial velocity / q:      0 m/s / exactly 0
projection:                not applied in this increment
```

Observed raw outcomes:

```text
strong 5 -> 2 MPa:    OPEN_TWO_PHASE; crossing cells 3, 4
moderate 5 -> 3 MPa:  OPEN_TWO_PHASE; crossing cell 4
control 5 -> 4 MPa:   ALL_LIQUID; crossing cells none
```

Strong case:

```text
dt:                         3.356317173211922e-5 s
maximum raw q_eq:           5.911503500507591e-4
maximum raw q mismatch:     5.911503500507591e-4
```

Moderate case:

```text
dt:                         3.9278457537062076e-5 s
maximum raw q_eq:           6.844477600333753e-5
maximum raw q mismatch:     6.844477600333753e-5
```

Control case remained liquid with zero equilibrium quality. Only the two cells adjacent
to the initial discontinuity changed. Boundary budgets closed to numerical precision.

Authoritative validation:

```text
validated head:            a870d313bd821bc05ba5e3fdd2ab155edadb8de9
workflow run:              30015273238
artifact ID:               8566944015
artifact SHA256:           15569960f65261d16f79d8341ab2706fb61309a5bfd044e1cc0a846bf099f34c
focused tests:             15 passed, 0 skipped
related Stage 7 HEM:      174 passed, 0 skipped
full repository:          616 passed, 0 skipped
failures / errors:          0 / 0
```

The raw crossed cells retained transported `q=0`; therefore this increment observed the
required pre-projection state but did not yet complete the accepted crossing path.

### PR #71 — projection, post-EOS recovery, and vapor accounting

Status: `OBSERVED; VALIDATED; MERGED`. Merge commit:
`ceaba980e5e7f7305424df8bd1e9e6b4f1acfe40`.

The PR #70 matrix was regenerated without changing conditions. The existing projection
was then applied, the synchronized state was accepted by the mixed EOS, a fresh second
projection was required to be a no-op, and projection vapor mass was accounted.

```text
strong crossing / projection cells:   3, 4 / 3, 4
strong projection vapor source:       7.054022964126832e-4 kg
moderate crossing / projection cells: 4 / 4
moderate projection vapor source:     6.563798045383618e-5 kg
control crossing / projection cells:  none / none
control projection vapor source:      0 kg
post q mismatch:                      0 for all cases
second projection cells:              none for all cases
```

Mass, momentum, and total energy remained bitwise unchanged by projection. Post pressure,
temperature, and sound speed were finite and positive. Projection-only and combined
boundary-plus-projection vapor budgets closed with zero retained residual.

Authoritative validation:

```text
validated head:            7c04a728b1369ed41f083d68b73deb81e92ac374
workflow run:              30018942238
artifact ID:               8568448978
artifact SHA256:           fc577459c65f29a95179dc5a98ef7813a82f14ba8de945a254626555a29c59da
focused tests:             12 passed, 0 skipped
related Stage 7 HEM:      186 passed, 0 skipped
full repository:          628 passed, 0 skipped
failures / errors:          0 / 0
```

This established a complete one-step projected crossing-path observation, while formal
Case A/B freeze remained false until repeatability was checked.

## 2026-07-24 to 2026-07-25 — Repeated first-crossing Case A/B freeze

### PR #72 — first software-verification crossing pair

Status: `VERIFIED; FROZEN; MERGED`. Merge commit:
`628800530851b0cb677bc0a6bedcb85a13a303d1`.

The strong crossing candidate and matched liquid control were executed three times each
using fresh solver and EOS instances. No case condition, algorithm, tolerance, or
acceptance threshold was changed after PR #71.

Frozen setup:

```text
cells / length / diameter: 8 / 1.0 m / 0.10 m
interface:                 between cells 3 and 4
CFL / flux:                0.20 / existing first-order Rusanov
boundaries / source:       transmissive / none
repeat count:              3 each
Case A safety limit:       8 steps

Case A: 5 MPa / 5 K -> 2 MPa / 5 K subcooling
Case B: 5 MPa / 5 K -> 4 MPa / 5 K subcooling
```

Every Case A repeat produced:

```text
outcome:                    ACCEPTED_CROSSING
crossing step:              1
crossing time:              3.356317173211922e-5 s
crossing cells:             3, 4
projection cells:           3, 4
maximum crossing q_eq:      5.911503500507591e-4
projection vapor source:    7.054022964126832e-4 kg
post q mismatch:            0
second projection:          no-op
final state SHA256:         78897b5c8ca57221186ccf3e0aa69e1492a942cc2e8dee0abb440a3e2e08e039
repeatability signature:    914ed2249c9546a1d32f6d6dbcd8b30236e1c1f2b37ecf9306100ad30622b612
```

Case A budget observations:

```text
mass residual:              0
momentum residual:          0
energy residual:            2.3283064365386963e-10
energy relative residual:   1.742733258599977e-16
phase-vapor residual:       0 kg
```

Every Case B repeat was advanced to exactly the Case A crossing time and produced:

```text
outcome:                    MATCHED_ALL_LIQUID
final time:                 3.356317173211922e-5 s
crossing cells:             none
projection cells:           none
projection vapor source:    0 kg
all final regions:          LIQUID_CANDIDATE
final state SHA256:         8c09735ee9185cfb34b2186be30b32d78ec73350e211762d92c372e0b9f23a59
repeatability signature:    3bd7edc37842a00a0c27964a17029f5c66ef973b59bd7670f513c82fc7e85669
```

Case B mass, momentum, energy, vapor, and phase-vapor residuals were zero in retained
evidence. The Case B final step used the existing `compute_dt(t_end=...)` path to reach
the matched physical-time horizon without changing the CFL upper bound.

Freeze result:

```text
case_a_repeatable = true
case_b_repeatable = true
case_b_matched_physical_time = true
case_a_frozen = true
case_b_frozen = true
actual_first_order_fvm_crossing_verified = true
```

Authoritative validation:

```text
validated head:            825ebba11b7ea273c81db717c097d8f1122ae092
workflow run:              30105917479
artifact ID:               8601660179
artifact SHA256:           02b13cb63704ea63d826f1e1feab209c4bd5b83b4a5fec7e3936af114e0cbc7b
focused tests:             14 passed, 0 skipped
related Stage 7 HEM:      200 passed, 0 skipped
full repository:          642 passed, 0 skipped
failures / errors:          0 / 0
```

This `verified` result is limited to software verification of the current first-order FVM
and reviewed HEM chain. It does not establish experimental agreement, mesh-independent
accuracy, physical Validation, design-use acceptance, production activation, or an
approved two-phase acoustic band.

## 2026-07-25 — Pipeline-depressurization specification and boundary Increment 1

### PR #73 — first-crossing central-record synchronization

Status: `MERGED`. Merge commit:
`3e55b3fae88d813437654c144d0157de5b6d398f`.

Only the master verification index and execution log changed. The frozen Case A/B pair was
recorded as the first-order crossing regression control.

### PR #74 — minimal pipeline-depressurization prototype specification

Status: `SPECIFIED; VALIDATED; MERGED`. Merge commit:
`49b34bf955a5dd1f0d106f2e81f55aff3bd24add`.

The fixed verification-only prototype uses one 1.0 m x 0.10 m horizontal pipe with 32 cells,
a uniform stationary 5 MPa / 5 K-subcooled liquid initial state, reflective left boundary,
and a prescribed right boundary closed by `T_b = T_sat(p_b) - 5 K`. The existing first-order
Rusanov flux and CFL 0.10 are retained; friction, heat transfer, gravity, and internal
interfaces are disabled.

```text
fixed outlet paths:          5→2, 5→3, and 5→4 MPa
formal stop:                 first accepted crossing
preflight samples:           65 per path
endpoint / forbidden:        explicit fail-fast
reverse flow:                explicit fallback diagnostic and prototype rejection
boundary vapor transport:    separate from projection vapor source
schedule/algorithm tuning:   forbidden
```

Authoritative validation:

```text
validated head:            8640d6f73421ec3d4b7bf64b20e09f7445d32149
workflow run:              30135136669
artifact ID:               8612546071
artifact SHA256:           5b2e391e32b984eab82c6e5d316add05c54f9e2ecc411580523e1f4323b1b69b
specification tests:       9 passed, 0 skipped
frozen Case A/B tests:    14 passed, 0 skipped
full repository:         651 passed, 0 skipped
failures / errors:          0 / 0
```

### PR #75 — prescribed-subcooled outlet boundary Increment 1

Status: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED`. Merge commit:
`9982c52bc4c26fac991972f0a8156c857e4bf21f`.

The increment implemented only boundary construction and preflight. No pipeline FVM time
step was executed.

```text
state closure:               p_b(t), T_sat(p_b)-5 K, CoolProp P,T -> rho,e
required region:             LIQUID_CANDIDATE
right boundary policy:       outlet_only
velocity policy:             copy adjacent interior velocity
ghost quality:               equilibrium quality from boundary rho/e
interior quality copy:       forbidden
reverse flow:                reflective fallback with explicit counter
mutation policy:             validate completely before ghost write
```

The real CoolProp 8.0.0 preflight accepted all 195 fixed samples:

```text
5→2 MPa:                    65 / 65 accepted liquid candidates
5→3 MPa:                    65 / 65 accepted liquid candidates
5→4 MPa:                    65 / 65 accepted liquid candidates
endpoint samples:           0
open-two-phase samples:     0
guard/backend failures:     0
q_eq / alpha:               0 / 0 for all samples
```

Authoritative validation:

```text
validated implementation head: c94458933741866812286ea1e77bd288f7c4e0a2
workflow run:                  30137665050
artifact ID:                   8613415710
artifact SHA256:               27f43c28566868fd13ec69e207cba3c5ac12e6795627c6045ac9d28b496ef5e0
dependency-free tests:         18 passed, 0 skipped
installed-CoolProp tests:       6 passed, 0 skipped
prototype specification:        9 passed, 0 skipped
frozen Case A/B:                14 passed, 0 skipped
full repository:               675 passed, 0 skipped
failures / errors:               0 / 0
```

Post-normalization permanent CoolProp Wave, Controlled Pressure Ramp, Boundary Reflection,
and Internal Valve regressions all passed before merge.

## 2026-07-25 to 2026-07-26 — Boundary-driven pipeline continuation

### PR #77 — fixed first-crossing pipeline matrix

Status: `OBSERVED; MERGED`. Merge commit:
`5657d26b3f37443ef63971245dce66ddd72c681e`.

The unchanged 1.0 m / 0.10 m / 32-cell first-order Rusanov prototype executed the fixed
5→2, 5→3, and 5→4 MPa schedules at CFL 0.10.

| case | formal result | step | crossing time [s] | cell | outlet distance [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa row retained the raw crossing before the fixed `1e-6` evidence check. It is not
an accepted crossing and not an all-liquid control. Gate P2 remained false.

### PR #79 — fixed 4 MPa subthreshold forensic diagnosis

Status: `OBSERVED; MERGED`. Merge commit:
`e40562e03657dec526f84b3911cbf181973462fa`.

The exact PR #77 4 MPa row was reproduced before diagnosis. Retained categories:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

The raw state was on the equilibrium two-phase side in both internal-energy and
specific-volume coordinates. Perturbation classification was `WEAKLY_RESOLVED`. The narrow
last-step tests did not retain `NUMERICAL_DIFFUSION_CONSISTENT` or
`BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT`; accumulated first-order diffusion and indirect
boundary influence remained open questions.

The equilibrium sound-speed candidate changed from approximately `461.2567 m/s` in the
accepted liquid state to `43.2231 m/s` in the raw micro-quality two-phase state. No acoustic
accuracy or post-crossing propagation approval was granted.

### PR #82 — fixed 32/64/128-cell mesh sensitivity

Status: `OBSERVED; MERGED`. Merge commit:
`08d34069b45083537e1d5c4035993d3fc5c01de5`.

The fixed 2/3/4 MPa matrix was executed at 32, 64, and 128 cells with CFL 0.10. Only cell
count, derived `dx`, and the predeclared 2000/4000/8000 step caps varied. The 32-cell/4 MPa
row reproduced PR #77 exactly before refined-mesh evidence was retained.

4 MPa observations:

| cells | formal result | maximum q_eq | normalized crossing time | outlet distance [m] |
|---:|---|---:|---:|---:|
| 32 | `GUARD_FAILURE` | `9.672588429198319e-9` | `0.9318710632753395` | `0.203125` |
| 64 | `GUARD_FAILURE` | `5.977506779042054e-7` | `0.8590001798084317` | `0.1484375` |
| 128 | `GUARD_FAILURE` | `3.8580990283897163e-7` | `0.8060444782479008` | `0.11328125` |

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

Authoritative evidence:

```text
validated implementation head: 0abb04ed052b3684ee33f1a8fad1927153701512
workflow run:                  30182329139
artifact ID:                   8626539673
artifact SHA256:               70b5abb9e54f677241ac513a8c0b7dbef4e8f1edaedda91e190f7c96ab9991f2
mesh contract tests:           28 passed
PR #77/#79 regressions:        48 passed
full repository:               751 passed
skips / failures / errors:     0 / 0 / 0
```

The result did not establish formal convergence order or mesh-independent physical
accuracy.

### PR #84 — fixed CFL contract and exact CFL 0.10 replay

Status: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED`. Merge commit:
`827d99bce97cea2785aa3334b3f5e950389c9aad`.

The reviewed next matrix is fixed to 128 cells, final pressures 2/3/4 MPa, CFL values
0.10/0.05/0.025, and 8000/16000/32000 step caps. Every other PR #77/PR #82 setting is
immutable. Severe or non-threshold guard outcomes return only
`CFL_SENSITIVITY_INCONCLUSIVE`.

The three CFL 0.10 rows reproduced PR #82 exactly. CFL 0.05 and 0.025 were not executed.

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
pre-execution checkout state: clean
```

## Current technical conclusion — 2026-07-26

The HEM verification path on recorded substantive development `main`
`827d99bce97cea2785aa3334b3f5e950389c9aad` now supports:

- guarded pure-CO2 `rho/e` thermodynamic evaluation;
- explicit phase classification and raw boundary-region transition detection;
- an independently defined equilibrium sound-speed candidate;
- first-order Rusanov/CFL operation on liquid and open-two-phase accepted states;
- exact uniform open-two-phase preservation;
- dynamic transported/equilibrium-quality synchronization;
- projection activation and true no-op behavior;
- mixed liquid/open-two-phase accepted-state recovery;
- actual raw liquid-to-open-two-phase crossing from an all-liquid initial state;
- post-crossing projection, EOS recovery, second-projection no-op, and vapor-budget closure;
- deterministic repeated Case A crossing and exact matched-time all-liquid Case B;
- frozen first-order Case A/B software-regression controls;
- a prescribed-subcooled outlet with 195/195 accepted boundary preflight samples;
- a fixed boundary-driven 2/3/4 MPa pipeline first-crossing matrix;
- a fixed 4 MPa forensic diagnosis retaining the raw observation without threshold tuning;
- a fixed 32/64/128-cell mesh-sensitivity matrix at CFL 0.10;
- a fixed 128-cell CFL contract with exact CFL 0.10 baseline replay and traceable artifacts.

The current evidence does not support the following claims:

```text
Gate P2:                                      false
all-liquid 4 MPa control:                     false
formal mesh-independent accuracy:             not established
CFL-independent crossing:                     not verified
CFL 0.05 / 0.025 matrix:                      not executed / not accepted
near-saturation acoustic continuity:          not approved
post-crossing propagation:                    not approved
open-two-phase to vapor crossing:             not verified
physical Validation:                          false
design-use acceptance:                        false
production HEM activation:                    false
```

## Approval boundary

```text
verification_only = true
software_verification_only = true
property_backend_name = coolprop_co2
property_backend_design_status = not_approved_for_design_use
actual_first_order_fvm_crossing_verified = true
case_a_frozen = true
case_b_frozen = true
boundary_driven_pipeline_first_crossing_observed = true
four_mpa_subthreshold_crossing_observed = true
mesh_sensitivity_executed = true
mesh_independent_crossing_verified = false
cfl_contract_implemented = true
cfl_0p10_baseline_reproduced_exactly = true
low_cfl_matrix_executed = false
CFL_independent_crossing_verified = false
local_pc_reproduction_checkpoint_completed = true
local_pc_reproduction_disposition = NUMERICALLY_EQUIVALENT
algorithms_or_tolerances_tuned = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
post_crossing_propagation_approved = false
numeric_accuracy_band_approved = false
```

## Next

1. synchronize the merged PR #91 Gate 3 disposition into the three central records;
2. execute the fixed 128-cell 2/3/4 MPa × CFL 0.10/0.05/0.025 matrix in Issue #86, first
   requiring the CFL 0.10 rows to reproduce the retained PR #82 baseline exactly;
3. keep all CFL 0.05/0.025 results unaccepted until their dedicated review and promotion;
4. retain PRs #52/#53 as later numerical-improvement assets until the first-order temporal
   and near-saturation acoustic questions are separated;
5. perform the independent near-saturation acoustic-continuity gate before approving any
   post-crossing propagation;
6. keep production activation, physical Validation, design use, and acoustic/numerical
   accuracy approval false until separately established.

## 2026-07-26 to 2026-07-27 — Gate 3 cross-runtime closure

### PR #91 — local-PC checkpoint and numeric-equivalence disposition

Status: `NUMERICALLY_EQUIVALENT; MERGED`. Merge commit:
`1bb1765617de72741086b199efa0d72be16ae651`.

The Ubuntu 24.04 reference remained authoritative for bitwise-exact PR #82 scalar and
SHA256 values. The independent Windows 11 runtime used Python 3.12.10, NumPy 2.5.1, and
CoolProp 8.0.0. Its raw histories were not bitwise identical, but all reviewed outcomes,
step counts, crossing steps, crossing cells, crossing positions, and failure categories
were exact.

```text
Ubuntu reference artifact:          8632513953
Ubuntu artifact SHA256:             78002ddb524c9f1cac00040a14139d6da512f66f19d39a65afc53dbcac188060
Windows raw-history ZIP SHA256:     508e9b727a2e0d00974e4650c3f927e93af89eed9af96cde5c2b0b3e12368738
maximum normalized difference:      5.519112370006797e-12
predeclared comparison guard:       1.0e-10
```

The first platform-dependent difference was present in the initial CoolProp-backed state
before time integration. No discrete-event divergence or crossing-threshold reversal was
observed. Inventory differences remained inside the pre-existing absolute budget limits.

The corrected independent Windows full-suite packet v2 recorded:

```text
source main:                         f1b2c76827482164a12e2924bf7119a0b150e421
runtime:                             Windows 11 / Python 3.12.10
NumPy / CoolProp / Matplotlib:       2.5.1 / 8.0.0 / 3.11.1
full repository:                     796 tests
passed / failures / errors / skips:  785 / 4 / 7 / 0
known exact mismatches:              11
unexpected / missing / changed:      0 / 0 / 0
packet SHA256:                       67a0113b63db1b4770baf4bbd4104312c5c24839cf50956e57592f487fd7755f
```

The 11 Windows problems are the reviewed bitwise-exact baseline mismatches only. Ubuntu
hashes were not replaced, exact guards were not weakened, and no solver algorithm or
tolerance changed.

```text
Gate_3_disposition = NUMERICALLY_EQUIVALENT
Gate_3_complete = true
Gate_4_execution_paused_until_central_record_sync = true
low_cfl_result_accepted = false
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

