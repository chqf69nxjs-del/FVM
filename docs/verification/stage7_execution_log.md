# Stage 7 Execution Log

Earlier entries through the V-013 reference-core checkpoint are preserved in
[`archive/stage7_execution_log_through_v013_reference_core.md`](archive/stage7_execution_log_through_v013_reference_core.md).

## 2026-07-19 — V-013A incident propagation

Status: `OBSERVED; MERGED` in PR #48. Merge commit:
`613b21622b22402fbf7b8d77b1d881db7ff5f28e`.

```text
primary run:         29647234616
focused / full:      39 / 315 passed
runs / figures:      3 / 3, 7 / 7
CoolProp:            8.0.0
n=400 peak ratio:    0.57499430
```

Wave direction and approximate propagation speed are consistent. Strong numerical
broadening and peak loss decrease with mesh refinement but remain material at `n=400`.
Production solver behavior is unchanged.

Review-close validation run `29673595870` passed focused `40` and full `316` tests,
with `git diff --check` clean. Temporary validation helpers were removed.

## 2026-07-19 — V-013B rigid-wall reflection

Status: `OBSERVED; MERGED` in PR #49. Merge commit:
`bc874193de6a4c019073b6cf629e99ec5dfa6602`.

Fixed identities:

```text
A-_reflected = A+_incident
pressure reflection coefficient = +1
velocity reflection coefficient = -1
wall velocity = 0
wall pressure ratio = 2
```

Final evidence:

```text
workflow run:       29684930259
focused tests:      57 passed, 0 skipped
full repository:    350 passed, 0 skipped
runs / figures:     3 / 3, 7 / 7
artifact ID:        8441899419
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

Pressure and velocity reflection signs are correct. Wall-face velocity, mass flux, and
energy flux are exactly zero. Strong first-order numerical broadening remains at the
finest mesh.

## 2026-07-19 to 2026-07-20 — V-013C fixed-pressure reflection

Status: `OBSERVED; MERGED` in PR #50. Merge commit:
`f403103c46a1d618ce2f2345c986e29b921b664a`.

Fixed identities:

```text
A-_reflected = -A+_incident
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

Final evidence:

```text
workflow run:       29692477941
PR head:            2f5c10b3f99f561d457ab8d391d5e91be98b7ff3
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
runs / figures:     3 / 3, 7 / 7
artifact ID:        8444138380
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
```

The reflected pressure sign is negative, reflected velocity sign is positive, and the
returning characteristic is left-going `A-`. The finest-mesh final peak ratio is
`0.57212615`, confirming that strong numerical diffusion remains the dominant
limitation.

## 2026-07-20 — V-013 baseline formalization merged

Status: `FORMALIZED; MERGED` in PR #51. Merge commit:
`62390bd526ae99b6702f4ed76e3594e1bf01259b`.

Review-readiness validation:

```text
baseline-definition integrity:  4 passed
full repository:               389 passed
committed diff:                clean
working tree:                  clean
permanent GitHub Actions:      4 / 4 success
```

The first-order FVM is fixed as the selectable software/numerical control. It is not an
exact solution, physical Validation result, design-use approval, or approved numeric
accuracy/regression band. CI-light remains `PROPOSED; NOT APPROVED; NOT IMPLEMENTED`.

## 2026-07-20 — Numerical-diffusion improvement assets

PR #52 is `OPEN; READY FOR REVIEW` and contains a solver-independent MUSCL/TVD
reconstruction scaffold. Final head:
`829880e88010ea808b316e09f28f26a0a18c7f03`.

Its intended diff contains four files:

```text
src/liquid_gas_transient/reconstruction.py
tests/test_stage7_muscl_reconstruction.py
docs/verification/stage7_muscl_reconstruction_scaffold_plan.md
docs/verification/stage7_muscl_scaffold_validation_commands.md
```

PR #53 is a `VALIDATED STACKED DRAFT` based on PR #52. Final head:
`ff72bd303a99d832bad6d13536ff9b5682eeb4f9`.

The scalar-advection evidence shows material reduction in numerical diffusion for all
MUSCL variants. At `n=200`, peak retention under SSP-RK2 was:

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

Final reviewed head:
`39a394698383879225216aee403c1221fe454e0e`.

Primary evidence:

```text
workflow run:         29739900542
artifact ID:          8459985478
artifact SHA256:      98c3e973d0f81c68bf0cf86396679964d87a3f4f1ecdb542bdbe1dbaeecf8103
focused tests:        24 passed, 0 skipped
full repository:      406 passed, 0 skipped
0-D path states:      23 / 23
artifact formats:     4 / 4
permanent workflows:  4 / 4 success
```

The increment adds an HEM-oriented wrapper around
`RealFluidPropertyBackend.state_from_rho_e`, explicit finite-value guards, backend-error
traceability, input immutability, and a deterministic liquid/two-phase/vapor path.
Backend-reported sound speed remains diagnostic only.

### PR #55 — explicit CoolProp phase classification

Status: `MERGED`. Merge commit:
`e45362d1aa07bf7144f606dc32595d4ab2f7093d`.

Final reviewed head:
`97ffe4e57c3a006ae27702749c417f9e3989aba8`.

Primary evidence:

```text
workflow run:         29744597504
artifact ID:          8461927762
artifact SHA256:      d91869f6d7fd3d18ab9e2abf1b3e9b6fecfa87228dabd5546fd8024aa7252c6a
focused tests:        39 passed, 0 skipped
full repository:      423 passed, 0 skipped
phase-map states:     9 / 9
sound-speed calls:    none
permanent workflows:  4 / 4 success
```

The increment uses CoolProp `PhaseSI` rather than inferring phase from quality alone. It
separates equilibrium state evaluation from acoustic closure and defines explicit
critical, solid/below-triple, and unknown-state guards.

### PR #56 — equilibrium sound-speed closure candidate

Status: `MERGED`. Merge commit:
`b098f67b71bf53bd20fc14bf80d7f4cea595a707`.

Final reviewed head:
`3c21be4410e808f22888edd9814204a25df40a4c`.

Implemented candidate:

```text
c_eq^2 = (dp/drho)|e + (p/rho^2) (dp/de)|rho
```

Primary evidence:

```text
workflow run:           29748093054
artifact ID:            8463388994
artifact SHA256:        97b6f04a38cd6debafc66fac3dc8b902d1abdf1fed982e04c48000ca5682ad79
focused HEM tests:      63 passed, 0 skipped
full repository:        447 passed, 0 skipped
sound-speed states:     10 / 10
two-phase states:       7 / 7
CoolProp two-phase A:   never requested
permanent workflows:    4 / 4 success
```

The closure uses adaptive phase-preserving central finite differences of `p(rho,e)`.
Non-finite or non-positive results are rejected without clipping. The two-phase values
are closure observations, not approved physical acoustic results.

### PR #57 — uniform HEM-state preservation

Status: `OBSERVED; MERGED`. Merge commit:
`f27ec42d0e191065cd4d3d214a14009b07be800f`.

Final reviewed head:
`45cdfe3da409e98825bc3b2ab52265f5f51f2900`.

Fixed case:

```text
p:                    2 MPa
quality:              0.50
velocity:             0 m/s
cells / steps:        8 / 8
CFL:                  0.25
boundaries:           transmissive
source:               NoSource
phase change:         NoPhaseChange
internal interfaces:  none
```

Primary evidence:

```text
workflow run:          29751190749
artifact ID:           8464712262
artifact SHA256:       71f7934f6f0061191f8af09b9cdf802a5b797f628878cd045a13a94273f5e999
focused HEM tests:     76 passed, 0 skipped
full repository:       460 passed, 0 skipped
uniform cells / steps: 8 / 8
permanent workflows:   4 / 4 success
```

Every measured drift in conservative state, primitive variables, acoustic quantities,
and mass/momentum/energy/vapor-mass inventories was exactly zero after eight steps.
This demonstrates preservation of one uniform stationary open-two-phase state, not
nonuniform accuracy or dynamic flashing.

## 2026-07-21 — HEM foundation record synchronization

PR #58 synchronized the central Stage 7 documents after PRs #54–#57 were sequentially
restacked and merged. Status: `MERGED`. Merge commit:
`dd5d3d0d10d0f93bb0d7a066e6d861f54c153b25`.

The record synchronization changed only:

```text
docs/verification/MASTER_VERIFICATION_INDEX.md
docs/verification/stage7_execution_log.md
```

No production source or numerical behavior changed.

## 2026-07-21 — Dynamic equilibrium-quality synchronization

### PR #59 — synchronization specification

Status: `MERGED`. Merge commit:
`70dc41ab7bc3c5ef46d83a49e3ea8de48d84ebad`.

Final reviewed head:
`b7b00432dc6c0ad9197f3f9809c22fb1c247c4ed`.

The specification selected a separate verification-only projection that synchronizes
transported `rho*q` with the equilibrium quality implied by `rho/e`. The contract
requires:

```text
rho*q <- rho*q_eq
rho unchanged bitwise
rho*u unchanged bitwise
rho*E unchanged bitwise
no silent clipping
whole-step fail-fast for unsupported states
```

It also separated the equal-pressure contact no-op case from the weak pressure-offset
case that must produce measurable projection activity.

### PR #60 — projection implementation

Status: `IMPLEMENTED; MERGED`. Merge commit:
`a4d525a004ae7bf5e284a882706155dce41b3eba`.

Final reviewed head:
`1da2ffc9047a71aedc343eb932e7f4115bc004a2`.

Primary evidence:

```text
workflow run:       29800804296
artifact ID:        8483707741
artifact SHA256:    bdf06b22fbc81ca044ed57dfab9b3a18987c05914bc03b0da3734dc7e7885a6f
focused tests:      72 passed
full repository:    478 passed
```

`HEMEquilibriumQualityProjection` evaluates equilibrium quality directly from `rho/e`,
projects only `rho*q`, preserves conservative mass/momentum/energy, records cellwise
phase/quality evidence, and rejects unsupported or invalid states without clipping.

Production defaults, the generic phase-change skeletons, and physical-model approval
flags remained unchanged.

### PR #61 — nonuniform pressure-offset activated case

Status: `OBSERVED; MERGED`. Merge commit:
`ceca2b48eb2f34cb8c1d584d80ae2619ff77271a`.

Final reviewed head:
`a0e1024aa5bf9f54c205dfc8e81e614080354214`.

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

Primary evidence:

```text
workflow run:       29801484953
artifact ID:        8483939146
artifact SHA256:    4156346821f0c04b5d5a569fd6bb64edeb07854a4ae905c4b29f5b3e51152447
focused tests:      46 passed
full repository:    493 passed
```

Numerical observations:

```text
projection total cell updates:          20
projected cells by step:                 2, 4, 6, 8
maximum |delta q|:                       2.4143668471476865e-5
maximum post-projection q mismatch:      5.551115123125783e-16
maximum velocity:                        0.2547984084365163 m/s
cumulative vapor source:                 3.501570117236952e-5 kg
```

All projection states remained in the open liquid-vapor two-phase region. Mass,
momentum, energy, and phase-vapor budgets closed to floating-point tolerance.

### PR #62 — equal-pressure contact/no-op comparison

Status: `OBSERVED; MERGED`. Squash merge commit:
`3e116cbcd853bcb1b52fe001819a4b300d5997ff`.

Final reviewed head:
`1b4a754de4e79b0d4bb88acb22b94301d72ca142`.

The comparison used the PR #61 pressure-offset case and the negative-control case:

```text
left:        2.00 MPa / q=0.45 / u=0
right:       2.00 MPa / q=0.55 / u=0
cells:       32
CFL:         0.10
steps:       4
```

Original numerical evidence:

```text
workflow run:       29812617503
artifact ID:        8488096499
artifact SHA256:    db0a5e997bd3fc07cba2d5a7470724778f2a3ac831ea1c62804e26a97c37b19b
focused tests:      67 passed
full repository:    514 passed
```

Equal-pressure observations:

```text
projection total cell updates:          0
projected cells by step:                 0, 0, 0, 0
maximum |delta q|:                       4.440892098500626e-16
maximum post-projection mismatch:        4.440892098500626e-16
transport-changed cells:                 8
mixed-quality cells:                     8
initial maximum quality jump:            0.10000000000000037
final maximum quality jump:              0.06788855198828081
maximum pressure span:                   1.6298145055770874e-9 Pa
maximum absolute velocity:               1.206100596343292e-14 m/s
projection vapor source:                 0.0 kg
```

The contact was numerically transported and spread, but conservative mixing stayed on
the same saturation line. The zero projection count is therefore an exercised no-op,
not an unexercised solver path. The activated/no-op maximum-`|delta q|` ratio was about
`5.44e10`.

A P2 review found that the initial artifacts did not retain enough property-backend
traceability. The final implementation added the following metadata to JSON, Markdown,
CSV, NPZ, and PNG evidence:

```text
model_name
fluid_name
property_backend_name = coolprop_co2
property_backend_design_status = not_approved_for_design_use
coolprop_version
numpy_version
output_version
```

PNG figures include the same backend/design-status/version metadata and
`VERIFICATION ONLY` in their footers. Follow-up validation completed successfully:

```text
validated head:      6c4ef3717c3a669842c46cb7b42c52fbca2aa228
workflow run:        29820825656
artifact ID:         8491343302
artifact SHA256:     ec93eb009d6c9b0d870437d1a9b493ff16823d55d944726bacd5237c184eeec5
focused tests:       success
fixed runner:        success
full repository:     success
static checks:       success
artifact upload:     success
```

After temporary-workflow removal, final head `1b4a754de4e79b0d4bb88acb22b94301d72ca142`
passed all four permanent workflows:

```text
CoolProp Wave Regression:                 29821125960 success
CoolProp Controlled Pressure Ramp:        29821125850 success
CoolProp Boundary Reflection Regression:  29821125950 success
CoolProp Internal Valve Regression:       29821125883 success
```

The unresolved review thread was answered and resolved before merge.

## Current technical conclusion

The HEM verification path on `main` now supports:

- guarded `rho/e` thermodynamic evaluation;
- explicit phase classification;
- an independently defined equilibrium sound-speed candidate;
- verification-only connection to existing Rusanov flux and CFL;
- exact preservation of one uniform stationary open-two-phase state;
- dynamic synchronization of transported `rho*q` with equilibrium quality;
- nonuniform open-two-phase transport with measurable projection activity;
- equal-pressure contact transport as a true projection no-op;
- mass, momentum, energy, and phase-vapor budget closure for both dynamic cases;
- backend/design-use/version traceability in the latest evidence artifacts.

The current evidence does not support the following claims:

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

## Next

1. define the first liquid-to-two-phase boundary-crossing state pair;
2. specify allowed phase-class transitions per step;
3. define the `q=0` endpoint and tolerance policy;
4. define fail-fast behavior for critical, solid, unknown, and backend-invalid states;
5. define required phase, quality, sound-speed, projection, and budget evidence;
6. implement a short first-order transmissive-boundary expansion runner;
7. build the first LCO2 pipeline depressurization prototype only after stable boundary crossing;
8. retain PR #52/#53 as later numerical-improvement assets until the first-order dynamic HEM path is stable.
