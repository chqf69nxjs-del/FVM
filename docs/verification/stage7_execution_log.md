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

## Current technical conclusion

The HEM verification path on recorded development `main`
`fb078da84fa17d6aa8d840616c494a0bf3efd71c` now supports:

- guarded pure-CO2 `rho/e` thermodynamic evaluation;
- explicit phase classification;
- an independently defined equilibrium sound-speed candidate;
- verification-only Rusanov/CFL connection for open two-phase states;
- exact preservation of one uniform stationary open-two-phase state;
- dynamic synchronization of transported `rho*q` with equilibrium quality;
- nonuniform open-two-phase transport with measurable projection activity;
- equal-pressure contact transport as a true projection no-op;
- budget closure and backend/design-status traceability for the reviewed dynamic cases;
- direct liquid-side boundary-region and transition-event classification independent of
  transported quality.

The current evidence does not support the following claims:

```text
mixed liquid/open-two-phase accepted-state EOS: not implemented
liquid-to-two-phase FVM boundary crossing:      not verified
open-two-phase to vapor crossing:               not verified
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
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

## Next

1. add and unit-test a mixed liquid/open-two-phase accepted-state verification EOS;
2. verify the same existing equilibrium sound-speed estimator on both supported regions;
3. perform a logged CoolProp state-pair survey within the current guards;
4. perform minimal first-order FVM dry runs while varying only permitted case parameters;
5. freeze the first successful crossing Case A and matched no-crossing Case B;
6. implement and validate the first-crossing capture runner and budgets;
7. synchronize formal crossing evidence into the central records;
8. only after stable crossing, begin a longer pipeline-depressurization prototype.
