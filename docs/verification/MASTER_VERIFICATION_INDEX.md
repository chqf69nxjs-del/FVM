# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-20

- Stage 1–6: `COMPLETE`
- Stage 7: `IN_PROGRESS`
- V-013 first-order propagation/reflection baseline: `FORMALIZED; MERGED` in PR #51
- PR #51 merge commit: `62390bd526ae99b6702f4ed76e3594e1bf01259b`
- independent analytical / CFL=1 MOC reference core: merged in PR #46
- V-013A incident propagation: `OBSERVED; MERGED` in PR #48
- PR #48 merge commit: `613b21622b22402fbf7b8d77b1d881db7ff5f28e`
- V-013B rigid-wall reflection: `OBSERVED; MERGED` in PR #49
- PR #49 merge commit: `bc874193de6a4c019073b6cf629e99ec5dfa6602`
- V-013C fixed-pressure reflection: `OBSERVED; MERGED` in PR #50
- PR #50 merge commit: `f403103c46a1d618ce2f2345c986e29b921b664a`
- MUSCL/TVD pure reconstruction scaffold: `OPEN; READY FOR REVIEW` in PR #52
- scalar-advection comparison: `VALIDATED STACKED DRAFT` in PR #53
- pure-CO2 HEM thermodynamic scaffold: `VALIDATED DRAFT; NOT SOLVER CONNECTED` in PR #54
- active physical-model branch: `agent/stage7-lco2-hem-thermodynamic-scaffold`

The main development objective remains a conservative one-dimensional LCO2 pipeline
transient code that can progress from liquid states through flashing and liquid-vapor
two-phase formation. The immediate physical-model line is the pure-CO2 HEM thermodynamic
closure. Higher-order transport remains a separate later numerical-improvement line.

## First-order baseline formalization

The post-PR #50 main state was independently rechecked on Windows with `385 passed` and a
clean working tree. PR #51 review-readiness validation then completed at head
`61c4810d3aa0a13c2a0709628955512d1f1243a2`:

```text
baseline-definition integrity tests: 4 passed
full repository suite:              389 passed
committed diff:                     clean
working tree:                       clean
permanent GitHub Actions:           4 / 4 success
```

The current first-order production FVM is fixed as a selectable software/numerical control.
It is not physical Validation, design-use acceptance, an exact solution, or an approved
wave-amplitude accuracy band.

Formalization documents:

- joint baseline and limitations:
  [`stage7_v013_baseline_and_limitations.md`](stage7_v013_baseline_and_limitations.md)
- machine-readable baseline:
  [`v013_baseline_definition_v1.json`](v013_baseline_definition_v1.json)
- cautious CI-light proposal:
  [`stage7_v013_ci_light_proposal.md`](stage7_v013_ci_light_proposal.md)

CI-light remains `PROPOSED; NOT APPROVED; NOT IMPLEMENTED`. No numeric V-013 regression or
design-accuracy band has been approved.

## V-013 case matrix

| item | purpose | ideal reflection identity | current state |
|---|---|---|---|
| V-013A | incident-wave propagation | right-going `A+` | observed and merged |
| V-013B | right rigid-wall reflection | `A-_reflected = A+_incident` | observed and merged |
| V-013C | right fixed-pressure reflection | `A-_reflected = -A+_incident` | observed and merged |

Common fixed conditions for A/B/C include a `100 Pa` Gaussian perturbation, `x0=65 m`,
`sigma=2 m`, FVM meshes `n=100 / 200 / 400`, FVM CFL `0.5`, and independent MOC
CFL `1.0`.

## V-013A evidence

Observation notes:
[`stage7_v013a_incident_propagation_observation_notes.md`](stage7_v013a_incident_propagation_observation_notes.md)

- observation tests: focused `39 passed`; full repository `315 passed`; skips `0`;
- review-close tests: focused `40 passed`; full repository `316 passed`; skips `0`;
- runs `3 / 3`; figures `7 / 7`; CoolProp `8.0.0`;
- direction and approximate wave speed are consistent;
- dominant error is strong numerical diffusion decreasing with refinement.

| n | Delta x [m] | final pressure peak ratio |
|---:|---:|---:|
| 100 | 1.00 | 0.33987050 |
| 200 | 0.50 | 0.44696360 |
| 400 | 0.25 | 0.57499430 |

## V-013B evidence

Execution plan:
[`v013b_rigid_wall_reflection_execution_plan.md`](v013b_rigid_wall_reflection_execution_plan.md)

Observation notes:
[`stage7_v013b_rigid_wall_reflection_observation_notes.md`](stage7_v013b_rigid_wall_reflection_observation_notes.md)

```text
workflow run:       29684930259
focused tests:      57 passed, 0 skipped
full repository:    350 passed, 0 skipped
runs / figures:     3 / 3, 7 / 7
artifact ID:        8441899419
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

| n | pressure reflection | velocity reflection | wall pressure ratio | final peak ratio |
|---:|---:|---:|---:|---:|
| 100 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 |
| 200 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 |
| 400 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 |

Pressure and velocity reflection signs are correct. Wall-face velocity, mass flux, and
energy flux are exactly zero. Strong numerical broadening remains at `n=400`.

## V-013C evidence

Execution plan:
[`v013c_fixed_pressure_reflection_execution_plan.md`](v013c_fixed_pressure_reflection_execution_plan.md)

Observation notes:
[`stage7_v013c_fixed_pressure_reflection_observation_notes.md`](stage7_v013c_fixed_pressure_reflection_observation_notes.md)

Fixed-pressure identities:

```text
A-_reflected = -A+_incident
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

Final observation evidence:

```text
workflow run:       29692477941
PR head:            2f5c10b3f99f561d457ab8d391d5e91be98b7ff3
Actions merge SHA:  e2eb1a075d229d51d28366aa211a1642fbcc1463
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
Windows recheck:    focused 58 / full 385 passed
runs / figures:     3 / 3, 7 / 7
plotting errors:    0
CoolProp:           8.0.0
artifact ID:        8444138380
artifact entries:   59
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
```

| n | pressure reflection | velocity reflection | fixed-pressure residual | boundary velocity ratio | final peak ratio |
|---:|---:|---:|---:|---:|---:|
| 100 | -0.63395297 | 0.63399661 | 0.05654903 | 0.82447607 | 0.33190828 |
| 200 | -0.69829946 | 0.69829998 | 0.04880759 | 1.09704849 | 0.44185022 |
| 400 | -0.77022729 | 0.77022778 | 0.03712903 | 1.37073388 | 0.57212615 |

The negative pressure reflection, positive velocity reflection, and left-going return are
observed. The fixed-pressure residual decreases and the boundary velocity ratio moves
toward `2` with refinement. Nonzero boundary mass and energy transfer are expected
observations for this pressure boundary, not zero-flux failures.

## Joint Stage 7 first-order finding

The production FVM consistently reproduces the direction, approximate timing, reflection
signs, and essential boundary-condition behaviour across V-013A/B/C. The common limiting
issue is strong numerical diffusion: the finest `n=400` mesh retains only about `57%` of
the final pressure peak in all three cases, and field L2 differences remain material.

Therefore the current solver is suitable as a robust first-order software/numerical
verification baseline, but not as a physically validated or design-accurate wave-amplitude
model. The approximately `57%` peak retention is an observed limitation, not an approved
accuracy target, design margin, or CI regression band.

## Numerical-diffusion improvement assets

PR #52 contains a solver-independent MUSCL/TVD reconstruction layer with first-order,
minmod, MC, and van Leer paths plus pure invariant tests. It does not change production
solver behaviour.

PR #53 contains a periodic scalar-advection comparison. The validated fixed Gaussian case
shows material peak-retention, width-preservation, and L2-error improvements for all MUSCL
variants relative to the same-time-integrator first-order control. These results rank later
numerical candidates; they do not approve a production limiter or time integrator.

The first-order path remains the control. Higher-order production connection is deferred
until the HEM thermodynamic and first-order two-phase paths are established.

## Pure-CO2 HEM thermodynamic scaffold — PR #54

Draft PR #54 adds a solver-independent HEM-oriented wrapper around the existing
`RealFluidPropertyBackend.state_from_rho_e` contract and a deterministic surrogate 0-D
liquid/two-phase/vapor path.

Primary validation evidence:

```text
validation head:           c96567cb63a67b3d9be2f3f20e7e5790e7ee3828
workflow run:              29739900542
artifact ID:               8459985478
artifact SHA256:           98c3e973d0f81c68bf0cf86396679964d87a3f4f1ecdb542bdbe1dbaeecf8103
focused tests:             24 passed, 0 skipped
full repository:           406 passed, 0 skipped
0-D path states:           23 / 23
0-D artifact formats:       4 / 4
committed diff:             clean
tracked/staged files:       unchanged
permanent workflows:       4 / 4 success
```

The scaffold:

- validates finite positive density and finite real-fluid internal energy;
- does not impose a universal `e >= 0` rule on real-fluid reference states;
- validates pressure, temperature, quality, void fraction, and backend-reported sound speed;
- classifies quality endpoints and the open two-phase quality interval;
- wraps backend failures with backend-name context;
- preserves input arrays and memory independence;
- emits JSON, CSV, Markdown, and NPZ evidence with false approval flags.

Important limitations remain explicit:

```text
production solver connected:                         false
pure-CO2 HEM thermodynamic core complete:             false
equilibrium two-phase sound-speed closure approved:  false
backend-reported sound speed:                         diagnostic only
critical region validated:                           false
solid phase supported:                               false
physical Validation:                                 false
design-use acceptance:                               false
```

The current labels are quality-regime labels, not a complete thermodynamic phase
classification. Explicit CoolProp phase classification, critical/solid guards, and an
approved equilibrium two-phase sound-speed closure remain before solver connection.

## Guardrails

- software / numerical verification only;
- physical Validation and design-use acceptance remain `False`;
- property backends remain `not_approved_for_design_use` unless a separate gate says otherwise;
- MOC is verification-only and the finest mesh is not exact;
- no time shift or parameter tuning is permitted;
- CI-light for V-013 remains proposed, not approved or implemented;
- no numeric V-013 regression or design-accuracy band has been approved;
- PR #54 does not change production solver, numerical flux, EOS adapter, phase-change,
  source, boundary, or interface behaviour.

## Next action

1. review the pure-CO2 HEM thermodynamic scaffold in PR #54;
2. close PR #52 and PR #53 independently as numerical-improvement assets without making
   them dependencies of the HEM line;
3. expose explicit CoolProp phase classification for safe representative `rho/e` states;
4. separate two-phase equilibrium property evaluation from sound-speed evaluation;
5. define and verify an equilibrium two-phase sound-speed closure;
6. generate a CoolProp pure-CO2 0-D phase/property map away from critical and solid regions;
7. then connect the reviewed closure to a first-order uniform HEM-state preservation case.
