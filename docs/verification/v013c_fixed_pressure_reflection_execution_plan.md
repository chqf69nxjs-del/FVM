# V-013C Fixed-Pressure Reflection Execution Plan

## 1. Status

`IN_PROGRESS; SPECIFICATION SCAFFOLD VERIFIED; WINDOWS RECHECK PENDING`

V-013C compares the existing production FVM fixed-pressure boundary with the
independent linear-acoustic MOC and analytical reference. The production solver,
numerical flux, and boundary implementation are not changed.

V-013A incident propagation and V-013B rigid-wall reflection are merged. V-013
overall remains `IN_PROGRESS`.

## 2. Branch and starting point

```text
branch: agent/stage7-v013c-fixed-pressure-reflection
Draft PR: #50
base: post-PR #49 main
base commit: 30ab7715e79d96c48f1cbe3ba7051815877e288a
```

A Windows project-environment recheck remains required after the branch is pulled.

## 3. Scope and guardrails

V-013C is software / numerical verification only. It is not:

- physical Validation;
- design-use acceptance;
- approval of `coolprop_co2` for design use;
- a production MOC solver;
- an equipment-fidelity reservoir, tank, valve, or pressure-control model;
- a two-phase, flashing, cavitation, HEM, HNE, ESD, or pump-trip result.

No time shifting, phase fitting, or post-result parameter tuning is permitted. No
FVM regression, CI-light, or design-accuracy band is introduced before the
observation is reviewed.

The pure specification module imports no production solver, production numerical
flux, production boundary class, existing FVM case runner, or CoolProp module.

## 4. Existing implementation alignment

The independent reference core already supports `fixed_pressure` with the right-boundary
characteristic identity

```text
A-_reflected = -A+_incident
```

Therefore the ideal linear-acoustic conditions are

```text
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

The production Stage 5 fixed-pressure path uses the existing
`PressureTankBoundary` with:

```text
pressure schedule: ConstantPressure(p0)
flow direction: bidirectional
velocity policy: copy
```

V-013C observes that existing path. It does not alter `PressureTankBoundary`, its EOS
inversion, or the FVM numerical flux.

Unlike the rigid wall, a fixed-pressure boundary is not a zero-flux boundary.
Boundary mass and energy fluxes and their time integrals are recorded as observations;
they are not required to be zero.

## 5. Fixed problem

```text
verification item: V-013C
case role: fixed_pressure_reflection
pipe length: 100 m
pipe diameter: 0.30 m
base pressure: 8 MPa
base temperature: 280 K
pulse: right-going Gaussian A+
pulse pressure amplitude: 100 Pa
pulse centre: 65 m
pulse sigma: 2 m
left boundary: transmissive observation boundary
right boundary: fixed pressure p0
FVM meshes: n=100 / 200 / 400
FVM CFL: 0.5
MOC meshes: n=100 / 200 / 400
MOC CFL: 1.0
probe x/L: 0.75 / 0.85 / 0.90
probe-window half width: 2.0 sigma
matched-field boundary guard: 5.0 sigma
```

The geometry, initial state, Gaussian pulse, meshes, CFL values, probes, and sample
times match V-013B. The intended independent variable is the right-boundary type.

## 6. Stable run identifiers

```text
v013c_n0100_fvmcfl0p5_moccfl1
v013c_n0200_fvmcfl0p5_moccfl1
v013c_n0400_fvmcfl0p5_moccfl1
```

Each run records V-013C, both CFL values, both boundary types, schema version
`v013c_matched_samples_v1`, and `production_solver_behavior_changed = false`.

## 7. Matched field samples

Cumulative characteristic travel is the common time convention:

```text
t = path_travel / c0
```

| path travel [m] | phase | expected centre [m] | expected characteristic state |
|---:|---|---:|---|
| 0 | incident | 65 | A+ |
| 15 | incident | 80 | A+ |
| 25 | incident | 90 | A+ |
| 35 | boundary contact | 100 | A+ and A- with opposite sign |
| 45 | reflected | 90 | A- |
| 55 | reflected | 80 | A- |
| 65 | reflected | 70 | A- |

Analytical values will be evaluated directly at recorded FVM cell centres and times.
MOC values will use fixed linear time/space interpolation. No signal shift is allowed.

The final pre-contact and first reflected samples are symmetric about the boundary
contact. The contact sample is the only matched field whose five-sigma envelope
overlaps the primary boundary. The final reflected sample remains well before the
left-boundary guard.

## 8. Probe windows and secondary-return safety

| probe x [m] | incident path [m] | boundary path [m] | reflected path [m] |
|---:|---:|---:|---:|
| 75 | 10 | 35 | 60 |
| 85 | 20 | 35 | 50 |
| 90 | 25 | 35 | 45 |

Each event window has a path half-width of `4 m`. At the closest probe, adjacent
event centres are `10 m` apart, leaving a strict `2 m` gap.

A reflected window is unsafe when its trailing edge reaches the leading edge of the
earliest secondary-return pulse. The comparison must not use only the return-pulse
centre. The equality-edge case is classified as contaminated.

## 9. Specification validation evidence

The initial Actions validation passed, but Codex review correctly noted that a bare
`git diff --check` after checkout examined only the clean working tree. It did not
prove that the committed PR range was free of whitespace errors. The final evidence
therefore uses an explicit base/head range and supersedes the initial record:

```text
workflow run:          29689975579
PR head:               d61919b30ca39f50d85a4702483ad0489c9a4f18
Actions merge SHA:     b882d05ecd50710eacd206cc305e50a091219919
committed diff range:  origin/main...HEAD
committed diff check:  success
focused tests:         53 passed in 0.26 s, 0 skipped
full repository:       380 passed in 141.94 s, 0 skipped
failures / errors:     0 / 0
CoolProp:              8.0.0
artifact ID:           8443286895
artifact SHA256:       c2df88965f4fd0104dbba3d53d4407c3f6a02d8e863a49a0d11a9120b8e3a046
permanent CI:          4 / 4 success
```

The focused suite contains the independent reference tests and the new V-013C pure
specification tests. Temporary validation workflows are removed after evidence
capture. The Windows project-environment focused/full recheck remains a separate gate.

## 10. Required observation metrics

The runner shall record at least:

- FVM, MOC, and analytical pressure, velocity, `A+`, and `A-` fields;
- incident and reflected signed pressure and velocity peaks;
- pressure reflection coefficient, expected `-1`;
- velocity reflection coefficient, expected `+1`;
- boundary pressure residual relative to `p0`;
- boundary velocity amplification relative to the incident velocity amplitude,
  expected `2` in the ideal reference;
- boundary mass flux, energy flux, and time-integrated mass/energy transfer;
- reflected-wave arrival offsets at all probes;
- opposite-direction characteristic leakage;
- normalized field differences and acoustic-energy-proxy difference;
- FVM health, positivity, single-phase status, and conserved-budget fields;
- `rho0`, `c0`, provenance, backend, and CoolProp version;
- explicit false Validation, design-evaluation, and acceptance flags.

Pressure and characteristic relative errors use the analytical pressure scale. Velocity
relative errors use the nonzero acoustic scale
`analytical_pressure_perturbation_pa / (rho0 * c0)`, including at exact boundary
contact.

## 11. Planned artifacts

Top level:

```text
v013c_config.json
v013c_reference_constants.json
v013c_run_plan.json
v013c_matched_sample_plan.json
v013c_probe_plan.json
v013c_summary.csv
v013c_metrics.json
v013c_observation_report.md
v013c_plot_metrics.json
```

Per run:

```text
fvm_config.json
fvm_metrics.json
fvm_probe_history.csv
fvm_boundary_history.csv
fvm_field_history.npz
moc_config.json
moc_metrics.json
moc_history.npz
analytical_samples.csv
matched_samples.csv
probe_comparison.csv
comparison_metrics.json
```

Figures shall be produced from saved artifacts only and shall state case, model,
property backend, CoolProp version, output version, and the software/numerical-only,
non-design-use disclaimer.

## 12. Planned figures

The initial target is seven figures aligned with V-013B:

1. pressure profiles through incident, contact, and reflected phases;
2. velocity profiles at the same samples;
3. reflected `A+ / A-` characteristic profiles;
4. near-boundary probe pressure history with theoretical event markers;
5. pressure and velocity reflection coefficients versus mesh spacing;
6. field and acoustic-energy differences versus mesh spacing;
7. fixed-pressure residual and boundary-velocity amplification error versus mesh spacing.

The seventh figure must not treat nonzero mass or energy flux as a boundary failure.
Those fluxes are reported separately as physical/numerical observations of the
pressure-boundary idealization.

## 13. Implementation sequence

1. Fix configuration, IDs, reference identities, path convention, probe windows,
   return-pulse guard, and pure tests. `COMPLETE`
2. Run focused/full GitHub Actions scaffold validation, check the committed PR range,
   and preserve the corrected evidence. `COMPLETE`
3. Pull the branch into the Windows project environment and run focused plus full
   repository tests and `git diff --check`. `NEXT`
4. Connect a dedicated V-013C runner to the existing Stage 5 fixed-pressure builder
   without changing solver or boundary physics.
5. Save FVM/MOC/analytical fields, probes, boundary telemetry, comparisons, and
   traceability metadata.
6. Implement the saved-artifact-only seven-figure plotter.
7. Execute `n=100 / 200 / 400`, review the observation, and preserve exact artifact
   evidence.
8. Keep V-013 overall `IN_PROGRESS`; formalize A/B/C only after V-013C review.

## 14. Current completion boundary

The fixed-pressure specification scaffold and pure tests are implemented, the committed
PR diff passes `git diff --check origin/main...HEAD`, and the focused/full GitHub
Actions validation passes. The Windows project-environment recheck is pending. The
production-connected runner, saved numerical artifacts, figures, and full three-mesh
observation are not yet implemented or accepted.
