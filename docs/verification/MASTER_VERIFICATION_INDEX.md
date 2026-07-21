# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-21

- Stage 1–6: `COMPLETE`
- Stage 7: `IN_PROGRESS`
- V-013 first-order propagation/reflection baseline: `FORMALIZED; MERGED` in PR #51
- pure-CO2 HEM thermodynamic scaffold: `MERGED` in PR #54
- explicit CoolProp phase classification: `MERGED` in PR #55
- equilibrium sound-speed closure candidate: `MERGED` in PR #56
- uniform first-order HEM-state preservation: `OBSERVED; MERGED` in PR #57
- MUSCL/TVD reconstruction scaffold: `OPEN; READY FOR REVIEW` in PR #52
- scalar-advection comparison: `VALIDATED STACKED DRAFT` in PR #53
- active physical-model gate: dynamic equilibrium-quality synchronization before nonuniform HEM flow
- physical Validation: `NOT ESTABLISHED`
- design-use acceptance: `NOT ESTABLISHED`
- production HEM activation: `NOT APPROVED`

The main development objective remains a conservative one-dimensional LCO2 pipeline
transient code that can progress from liquid states through flashing and liquid-vapor
two-phase formation. The first-order FVM remains the numerical control. The HEM
foundation is now present on `main`, but dynamic phase evolution and pipeline
depressurization are not yet demonstrated.

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
| PR #55 | explicit phase classification | `MERGED` | merge `e45362d1aa07bf7144f606dc32595d4ab2f7093d` |
| PR #56 | equilibrium sound-speed closure candidate | `MERGED` | merge `b098f67b71bf53bd20fc14bf80d7f4cea595a707` |
| PR #57 | uniform HEM-state preservation in first-order FVM | `OBSERVED; MERGED` | merge `f27ec42d0e191065cd4d3d214a14009b07be800f` |

## First-order V-013 baseline

The current production FVM is fixed as a selectable first-order software/numerical
control. It reproduces the wave direction, approximate timing, reflection signs, and
essential boundary-condition behavior across V-013A/B/C.

Common fixed conditions include:

```text
pressure perturbation:  100 Pa right-going Gaussian
x0 / sigma:             65 / 2 m
FVM meshes:             n = 100 / 200 / 400
FVM CFL:                0.5
independent MOC CFL:    1.0
```

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

PR #52 contains a solver-independent reconstruction layer with:

- exact first-order reconstruction;
- componentwise MUSCL reconstruction;
- minmod, MC, and van Leer limiters;
- constant/linear preservation, extrema, immutability, and error-path tests.

It does not connect to `FvmSolver` or change production numerical states.

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
path is established.

## Pure-CO2 HEM foundation — PRs #54–#57

### Summary

| PR | increment | final head | focused / full tests | principal evidence |
|---|---|---|---|---|
| #54 | thermodynamic scaffold and deterministic 0-D path | `39a394698383879225216aee403c1221fe454e0e` | `24 / 406` | path states `23 / 23`; artifact formats `4 / 4` |
| #55 | explicit CoolProp phase classification | `97ffe4e57c3a006ae27702749c417f9e3989aba8` | `39 / 423` | phase-map states `9 / 9`; sound-speed calls `0` |
| #56 | equilibrium sound-speed closure candidate | `3c21be4410e808f22888edd9814204a25df40a4c` | `63 / 447` | sound-speed states `10 / 10`; two-phase states `7 / 7` |
| #57 | uniform stationary two-phase FVM preservation | `45cdfe3da409e98825bc3b2ab52265f5f51f2900` | `76 / 460` | cells / steps `8 / 8`; all measured drift exactly `0` |

All four final heads passed the four permanent CoolProp workflows before merge.

### PR #54 — HEM thermodynamic scaffold

PR #54 adds an HEM-oriented wrapper around
`RealFluidPropertyBackend.state_from_rho_e` and a deterministic surrogate
liquid/two-phase/vapor path.

Primary evidence:

```text
artifact ID:         8459985478
artifact SHA256:     98c3e973d0f81c68bf0cf86396679964d87a3f4f1ecdb542bdbe1dbaeecf8103
focused tests:       24 passed
full repository:     406 passed
0-D path states:     23 / 23
artifact formats:    JSON / CSV / Markdown / NPZ
```

The scaffold validates finite positive density and finite real-fluid internal energy
without imposing an invalid universal `e >= 0` reference-state rule. Backend-reported
sound speed remains diagnostic only.

### PR #55 — explicit phase classification

PR #55 uses CoolProp `PhaseSI` instead of inferring phase from quality alone. It
separates equilibrium `p/T/Q/phase/alpha` evaluation from acoustic closure and defines
guards for unsupported critical, solid/below-triple, and unknown states.

Primary evidence:

```text
artifact ID:         8461927762
artifact SHA256:     d91869f6d7fd3d18ab9e2abf1b3e9b6fecfa87228dabd5546fd8024aa7252c6a
focused tests:       39 passed
full repository:     423 passed
phase-map states:    9 / 9
sound-speed calls:   none
```

`supercritical_liquid` away from the critical guard is treated as a high-density liquid
candidate for the first LCO2 path. Critical and solid-containing regions remain outside
the approved scope.

### PR #56 — equilibrium sound-speed closure candidate

The implemented candidate is:

```text
c_eq^2 = (dp/drho)|e + (p/rho^2) (dp/de)|rho
```

Pressure derivatives are evaluated by central finite differences with adaptive,
phase-preserving stencil control. Non-finite or non-positive `c_eq^2` is rejected
without clipping. CoolProp two-phase `A` is never requested.

Primary evidence:

```text
artifact ID:              8463388994
artifact SHA256:          97b6f04a38cd6debafc66fac3dc8b902d1abdf1fed982e04c48000ca5682ad79
focused tests:            63 passed
full repository:          447 passed
sound-speed states:       10 / 10
two-phase states:         7 / 7
CoolProp two-phase A:     never requested
```

Representative two-phase observations at `2 MPa`:

| quality | equilibrium sound speed [m/s] |
|---:|---:|
| 0.05 | 37.846900 |
| 0.10 | 52.645642 |
| 0.25 | 89.300480 |
| 0.50 | 135.765681 |
| 0.75 | 172.533607 |
| 0.90 | 191.745205 |
| 0.95 | 197.788354 |

These values are observations of the selected closure, not an approved acoustic
accuracy band or physical Validation result.

### PR #57 — uniform HEM-state preservation

PR #57 connects the HEM thermodynamic, phase, and sound-speed scaffolds to the existing
first-order `FvmSolver` through a verification-only adapter.

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
artifact ID:          8464712262
artifact SHA256:      71f7934f6f0061191f8af09b9cdf802a5b797f628878cd045a13a94273f5e999
focused tests:        76 passed
full repository:      460 passed
rho:                  99.97757528102285 kg/m3
temperature:          253.64735829812284 K
void fraction:        0.951436972434191
sound speed:          135.76568112572576 m/s
dt:                   0.002301759895496782 s
final time:           0.018414079163974254 s
```

Every measured conservative, primitive, acoustic, and inventory drift was exactly zero.
This demonstrates preservation of one uniform stationary open-two-phase state. It does
not demonstrate nonuniform-flow accuracy or dynamic flashing.

## Current technical interpretation

The merged foundation demonstrates that:

- a pure-CO2 `rho/e` state can be evaluated through explicit HEM-oriented guards;
- liquid, liquid-vapor two-phase, vapor, and excluded regions can be distinguished;
- an independently defined equilibrium sound-speed candidate can be evaluated without
  calling CoolProp two-phase sound speed;
- the resulting state can be connected to Rusanov flux and CFL calculation without
  creating artificial drift in a uniform stationary case.

The merged foundation does **not** demonstrate:

```text
dynamic equilibrium-quality synchronization:  not implemented
nonuniform two-phase flow:                     not verified
liquid-to-two-phase phase-boundary crossing:   not verified
pipeline depressurization:                     not implemented
two-phase acoustic accuracy band:              not approved
production HEM activation:                     not approved
physical Validation:                           false
design-use acceptance:                         false
```

## Dynamic HEM quality-consistency gate

The current solver transports `rho*q`, while single-component HEM thermodynamics derives
the equilibrium quality from `rho` and internal energy. Before a nonuniform expansion
case, the next increment must define how those two representations remain consistent.

Recommended first implementation:

```text
1. perform the conservative FVM update for rho, rho*u, and rho*E;
2. recover internal energy and evaluate equilibrium quality q_eq from rho/e;
3. synchronize rho*q to rho*q_eq;
4. leave rho, rho*u, and rho*E unchanged;
5. record the projection delta and phase classification;
6. reject critical, solid/below-triple, unknown, or backend-invalid states;
7. require exact no-op behavior for an already equilibrated uniform state.
```

This is a proposed dynamic HEM gate, not an implemented or approved production model.

## Guardrails

- software and numerical verification only;
- first-order FVM remains the control;
- property backends remain `not_approved_for_design_use` unless a separate gate says otherwise;
- equilibrium sound-speed values remain closure observations;
- critical and solid-containing regions remain outside the supported path;
- no numeric V-013 regression or design-accuracy band has been approved;
- no time shift or parameter tuning is permitted;
- HEM production activation, physical Validation, and design-use acceptance remain false.

## Next action

1. merge the documentation synchronization PR;
2. implement and verify equilibrium-quality synchronization;
3. run a small nonuniform open-two-phase case before crossing a phase boundary;
4. add a first-order one-dimensional liquid-to-two-phase expansion case;
5. build the first LCO2 pipeline depressurization prototype;
6. add wall heat transfer, friction, and discharge-boundary increments under separate gates;
7. introduce HNE, impurities, and higher-order transport only after the first-order HEM path
   has stable verification evidence.
