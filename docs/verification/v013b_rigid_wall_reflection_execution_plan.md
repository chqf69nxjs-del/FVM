# V-013B Rigid-Wall Reflection Execution Plan

## 1. Status

`IN_PROGRESS; SPECIFICATION SCAFFOLD IMPLEMENTED`

This increment fixes the V-013B observation contract before connecting the
production FVM path. It does not change the production solver, numerical flux, or
boundary implementation.

## 2. Starting evidence

```text
branch: agent/stage7-v013b-rigid-wall-reflection
base: PR #48 merge commit 613b21622b22402fbf7b8d77b1d881db7ff5f28e
working tree at start: clean
full repository baseline: 316 passed in 141.44 s
```

V-013A is merged and observed. V-013 overall remains `IN_PROGRESS`.

## 3. Scope and guardrails

V-013B is software / numerical verification only. It is not:

- physical Validation;
- design-use acceptance;
- approval of `coolprop_co2` for design use;
- a production MOC solver;
- an equipment-fidelity wall or valve model;
- a two-phase, flashing, cavitation, HEM, HNE, ESD, or pump-trip result.

The reference path shall not import or call the production FVM solver, numerical
fluxes, production boundary classes, existing FVM case runners, or CoolProp.
No phase shifting or parameter fitting is permitted.

## 4. Existing implementation alignment

Three existing assets were reviewed before fixing this plan.

1. The independent reference core defines
   `A+ = 0.5 (p' + rho0 c0 u')` and `A- = 0.5 (p' - rho0 c0 u')`.
2. Its right rigid-wall identity is `A-_reflected = A+_incident`, giving pressure
   coefficient `+1`, velocity coefficient `-1`, total wall pressure ratio `2`, and
   wall velocity perturbation `0`.
3. The production `ReflectiveBoundary` mirrors the ghost-cell momentum while
   retaining the other conserved components. Stage 5 already observes that boundary
   through `CoolPropBoundaryReflectionConfig`.

V-013B does not replace or modify those assets. It adds an independently fixed
FVM / MOC / analytical comparison contract with the Stage 7 low-amplitude profile.

## 5. Fixed problem

```text
verification item: V-013B
case role: rigid_wall_reflection
pipe length: 100 m
diameter: 0.30 m
base pressure: 8 MPa
base temperature: 280 K
pulse: right-going Gaussian A+
pulse pressure amplitude: 100 Pa
pulse centre: 65 m
pulse sigma: 2 m
left boundary: transmissive observation boundary
right boundary: rigid wall
FVM meshes: n=100 / 200 / 400
FVM CFL: 0.5
MOC meshes: n=100 / 200 / 400
MOC CFL: 1.0
probe x/L: 0.75 / 0.85 / 0.90
probe-window half width: 2.0 sigma
matched-field boundary guard: 5.0 sigma
```

The Stage 5 boundary-reflection runner uses a 1000 Pa pulse centred at 50 m. Those
values are not inherited by V-013B. V-013B uses the common Stage 7 100 Pa profile
and `x0=65 m` fixed by the V-013 specification.

## 6. Stable run identifiers

```text
v013b_n0100_fvmcfl0p5_moccfl1
v013b_n0200_fvmcfl0p5_moccfl1
v013b_n0400_fvmcfl0p5_moccfl1
```

Each row records `V-013B`, `rigid_wall_reflection`, the two CFL values, the two
boundary types, schema version `v013b_matched_samples_v1`, and that production
solver behaviour is unchanged. Direct case-ID construction rejects FVM CFL values
above one and MOC CFL values other than one.

## 7. Matched field samples

Cumulative path travel is used so incident, wall-contact, and reflected samples use
one unambiguous time convention: `t = path_travel / c0`.

| path travel [m] | phase | expected pulse centre [m] | dominant characteristic |
|---:|---|---:|---|
| 0 | incident | 65 | A+ |
| 15 | incident | 80 | A+ |
| 25 | incident | 90 | A+ |
| 35 | wall contact | 100 | A+ + A- |
| 45 | reflected | 90 | A- |
| 55 | reflected | 80 | A- |
| 65 | reflected | 70 | A- |

All distances align with the `n=100 / 200 / 400` MOC grids. The final pre-contact
sample at centre `90 m` has its five-sigma leading edge at the wall but not beyond
it. The first post-contact sample is symmetric at centre `90 m`. The wall-contact
sample is therefore the only matched sample whose five-sigma envelope overlaps the
primary boundary.

The last reflected centre remains 70 m from the left origin; its five-sigma left
edge is 60 m, so the accepted matched-field set is well before left-boundary
contact. Configuration checks reject any custom incident/reflected matched sample
that enters the wrong boundary guard envelope.

Analytical values will be evaluated directly at recorded FVM cell centres and
times. MOC values will use fixed linear time/space interpolation. No signal shift
will be applied.

## 8. Probe timing plan

The fixed probe locations give the following centre-path distances.

| probe x [m] | incident path [m] | wall path [m] | reflected path [m] |
|---:|---:|---:|---:|
| 75 | 10 | 35 | 60 |
| 85 | 20 | 35 | 50 |
| 90 | 25 | 35 | 45 |

With sigma `2 m` and half width `2.0 sigma`, each event window has a path
half-width of `4 m`. At the closest probe, adjacent event centres are separated by
`10 m`, leaving a strict `2 m` path gap between the incident, wall-contact, and
reflected windows. Endpoint sharing is therefore excluded even when artifact
selection uses inclusive comparisons.

Each probe row records the theoretical incident, wall-contact, and reflected times,
strict window limits, the return time of any initial left-going component, the time
of a right-wall/left-wall secondary return, the earliest of those two contamination
times, and an explicit `evaluation_window_contaminated` flag.

## 9. Required observation metrics

The implementation phase shall record at least:

- FVM, MOC, and analytical pressure, velocity, `A+`, and `A-` fields;
- incident and reflected peak pressure and velocity;
- pressure reflection coefficient;
- velocity reflection coefficient;
- wall velocity residual;
- total wall pressure amplification relative to the incident peak;
- reflected-wave arrival offsets at all probes;
- FVM/MOC/analytical normalized field errors;
- opposite-direction characteristic leakage;
- acoustic-energy-proxy difference;
- FVM health, positivity, single-phase status, and conserved-budget fields;
- `rho0`, `c0`, provenance, backend, and CoolProp version;
- explicit false Validation, design-evaluation, and acceptance flags.

These are observations. No FVM CI-light or design-accuracy band is introduced in
this increment.

## 10. Planned artifacts

Top-level:

```text
v013b_config.json
v013b_reference_constants.json
v013b_run_plan.json
v013b_matched_sample_plan.json
v013b_probe_plan.json
v013b_summary.csv
v013b_metrics.json
v013b_observation_report.md
v013b_plot_metrics.json
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

Plots shall be generated from saved artifacts without rerunning either solver and
shall include case, model, backend, CoolProp version, output version, and the
non-design-use disclaimer.

## 11. Implementation sequence

1. Fix stable configuration, case IDs, run plan, path-state convention, probe
   windows, and pure tests.
2. Re-run the focused V-013 reference/specification tests and the full repository
   suite.
3. Connect a dedicated V-013B runner to the existing small-amplitude FVM and
   `ReflectiveBoundary` without changing solver physics.
4. Record `rho0` and `c0` once from the FVM uniform state and pass only those scalars
   to the independent analytical/MOC path.
5. Implement saved field/probe/boundary artifacts and fixed matched comparisons.
6. Execute `n=100 / 200 / 400`, generate figures from saved artifacts, and review
   reflection sign, timing, wall residual, and numerical diffusion.
7. Keep V-013 `IN_PROGRESS`; proceed to V-013C only after V-013B review.

## 12. Current completion boundary

This scaffold is complete when:

- the pure module imports no production solver, boundary, case runner, or CoolProp;
- the default case IDs, mesh matrix, pulse, probes, path samples, and windows are
  fixed by tests;
- the rigid-wall identity agrees with the independent reference core;
- the repository full suite is rerun from the branch;
- canonical Stage 7 documents identify V-013B as active.

An isolated pure-scaffold check passes all 28 collected tests. This is not a
substitute for the requested repository focused and full-suite recheck.

The actual FVM/MOC/analytical observation has not yet been executed.
