# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-20

- Stage 1–6: `COMPLETE`
- Stage 7 / V-013: `IN_PROGRESS; BASELINE FORMALIZATION UNDER REVIEW`
- independent analytical / CFL=1 MOC reference core: merged in PR #46
- V-013A incident propagation: `OBSERVED; MERGED` in PR #48
- PR #48 merge commit: `613b21622b22402fbf7b8d77b1d881db7ff5f28e`
- V-013B rigid-wall reflection: `OBSERVED; MERGED` in PR #49
- PR #49 merge commit: `bc874193de6a4c019073b6cf629e99ec5dfa6602`
- V-013C fixed-pressure reflection: `OBSERVED; MERGED` in PR #50
- PR #50 merge commit: `f403103c46a1d618ce2f2345c986e29b921b664a`
- post-PR #50 Windows baseline: `385 passed`, working tree clean
- active branch: `agent/stage7-v013-baseline-formalization`

## V-013 formalization documents

- joint baseline and limitations:
  [`stage7_v013_baseline_and_limitations.md`](stage7_v013_baseline_and_limitations.md)
- machine-readable baseline:
  [`v013_baseline_definition_v1.json`](v013_baseline_definition_v1.json)
- cautious CI-light proposal:
  [`stage7_v013_ci_light_proposal.md`](stage7_v013_ci_light_proposal.md)

The current first-order production FVM is being frozen as a software/numerical
observation baseline. The formalization does not approve physical Validation,
design-use acceptance, or numeric CI/accuracy bands.

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

| n | Δx [m] | final pressure peak ratio |
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

The negative pressure reflection, positive velocity reflection, and left-going return
are observed. The fixed-pressure residual decreases and the boundary velocity ratio
moves toward `2` with refinement. Nonzero boundary mass and energy transfer are
expected observations for this pressure boundary, not zero-flux failures.

## Joint Stage 7 finding

The production FVM consistently reproduces the direction, approximate timing, reflection
signs, and essential boundary-condition behaviour across V-013A/B/C. The common limiting
issue is strong numerical diffusion: the finest `n=400` mesh retains only about `57%` of
the final pressure peak in all three cases, and field L2 differences remain material.

Therefore the current solver is suitable as a robust first-order software/numerical
verification baseline, but not as a physically validated or design-accurate wave-amplitude
model.

The approximately `57%` peak retention is an observed limitation. It is not an approved
accuracy target, design margin, or CI regression band.

## Baseline integrity and future change control

The machine-readable baseline is covered by pure integrity tests that require:

- all three merged cases and source merge commits;
- fixed common-case configuration;
- expected reflection signs and boundary roles;
- monotonic refinement trends in the recorded observations;
- false Validation, design-use, and band-approval flags.

Future higher-order work shall retain the current first-order path as a selectable control,
rerun V-013A/B/C, and compare against baseline version `v013_baseline_v1`.

## Guardrails

- software / numerical verification only;
- physical Validation and design-use acceptance remain `False`;
- property backend remains `not_approved_for_design_use`;
- MOC is verification-only and the finest mesh is not exact;
- no time shift or parameter tuning is permitted;
- CI-light is `PROPOSED; NOT APPROVED; NOT IMPLEMENTED`;
- no numeric V-013 regression or design-accuracy band has been approved;
- production solver, numerical flux, EOS inversion, and boundary behaviour are unchanged.

## Next action

1. run the baseline-definition integrity tests and full repository suite on Windows;
2. review the baseline/limitation statement and CI-light proposal;
3. merge the formalization PR without changing production solver behavior;
4. decide Tier 1 CI-light runtime, path filters, and exact invariant list;
5. perform a repeatability study before proposing numeric drift bands;
6. start a separate numerical-diffusion improvement phase while retaining the current
   first-order solver as the reference baseline.
