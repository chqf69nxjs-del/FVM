# V-013B Rigid-Wall Reflection Execution Plan

## 1. Status

`IN_PROGRESS; RUNNER AND SAVED-ARTIFACT PLOTTER VERIFIED; THREE-MESH OBSERVATION PENDING`

This increment fixes and implements the V-013B observation path without changing the
production solver, numerical flux, or boundary implementation.

## 2. Starting evidence

```text
branch: agent/stage7-v013b-rigid-wall-reflection
Draft PR: #49
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

The pure specification module shall not import or call the production FVM solver,
numerical fluxes, production boundary classes, existing FVM case runners, or
CoolProp. No phase shifting or parameter fitting is permitted.

The top-level `liquid_gas_transient` and `liquid_gas_transient.cases` compatibility
exports are resolved lazily. This preserves their public names while allowing a fresh
interpreter to import `cases.v013_rigid_wall_reflection` without loading the
production solver, boundary module, CoolProp cases, or CoolProp package. This is an
import-timing change only; numerical solver behaviour is unchanged.

## 4. Existing implementation alignment

Three existing assets were reviewed before fixing this plan.

1. The independent reference core defines
   `A+ = 0.5 (p' + rho0 c0 u')` and `A- = 0.5 (p' - rho0 c0 u')`.
2. Its right rigid-wall identity is `A-_reflected = A+_incident`, giving pressure
   coefficient `+1`, velocity coefficient `-1`, total wall pressure ratio `2`, and
   wall velocity perturbation `0`.
3. The production `ReflectiveBoundary` mirrors ghost-cell momentum while retaining
   the other conserved components. Stage 5 already exercises that production boundary.

V-013B does not replace or modify those numerical assets. It adds an independently
fixed FVM / MOC / analytical comparison contract with the Stage 7 low-amplitude
profile.

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

The Stage 5 boundary-reflection runner uses a different `1000 Pa`, `x0=50 m`,
`sigma=3 m` profile. Those values are not inherited by V-013B.

## 6. Stable run identifiers

```text
v013b_n0100_fvmcfl0p5_moccfl1
v013b_n0200_fvmcfl0p5_moccfl1
v013b_n0400_fvmcfl0p5_moccfl1
```

Each row records `V-013B`, `rigid_wall_reflection`, both CFL values, both boundary
types, schema version `v013b_matched_samples_v1`, and that production solver behaviour
is unchanged.

## 7. Matched field samples

Cumulative path travel provides one unambiguous time convention:
`t = path_travel / c0`.

| path travel [m] | phase | expected pulse centre [m] | dominant characteristic |
|---:|---|---:|---|
| 0 | incident | 65 | A+ |
| 15 | incident | 80 | A+ |
| 25 | incident | 90 | A+ |
| 35 | wall contact | 100 | A+ + A- |
| 45 | reflected | 90 | A- |
| 55 | reflected | 80 | A- |
| 65 | reflected | 70 | A- |

All distances align with the `n=100 / 200 / 400` MOC grids. The final pre-contact and
first post-contact samples are symmetric about the wall-contact event. The final
reflected sample remains well before left-boundary contact.

Analytical values are evaluated directly at recorded FVM cell centres and times. MOC
values use fixed linear time/space interpolation. No signal shift is applied.

## 8. Probe timing and return-pulse safety

| probe x [m] | incident path [m] | wall path [m] | reflected path [m] |
|---:|---:|---:|---:|
| 75 | 10 | 35 | 60 |
| 85 | 20 | 35 | 50 |
| 90 | 25 | 35 | 45 |

With sigma `2 m` and half width `2.0 sigma`, each event window has a path half-width
of `4 m`. At the closest probe, adjacent event centres are separated by `10 m`,
leaving a strict `2 m` gap.

A reflected window is unsafe when its trailing edge reaches the leading edge of the
earliest secondary return pulse. Comparing only against the return pulse centre is
prohibited. An equality-edge test fixes this rule.

## 9. Runtime independence verification

The leaf-module AST check remains, but it is not the runtime independence gate. A
fresh-interpreter subprocess imports the public module path and inspects `sys.modules`.
It fails if any production solver, production boundary, CoolProp case runner, or
CoolProp module is loaded as an import side effect.

## 10. Validation evidence

### Specification scaffold

```text
focused result: 53 passed in 0.56 s
full repository result: 346 passed in 121.38 s
failures / errors: 0 / 0
git diff --check: success
```

### Production-connected runner

```text
focused result: 55 passed in 5.02 s
full repository result: 348 passed in 89.39 s
failures / errors / skips: 0 / 0 / 0
git diff --check: success
```

### Saved-artifact plotter

The first Windows recheck generated `6 / 7` figures because the probe-history plot
requested `theoretical_boundary_time_s` while the saved comparison schema correctly
used `theoretical_wall_time_s`. This was a plotting-key mismatch only; numerical
solver execution, reflection calculations, and saved values were unchanged.

After correcting the key and retaining the old name solely as a compatibility alias:

```text
focused result: 57 passed in 17.65 s
full repository result: 350 passed in 165.79 s
failures / errors / skips: 0 / 0 / 0
git diff --check: success
installed-CoolProp integration figures: 7 / 7
plotting errors: none
solver rerun during plotting: false
numerical results changed during plotting: false
```

The full repository result confirms that lazy package exports and the plotting fix
remain compatible with existing use. Both Draft review threads are resolved. No
workflow file is modified.

## 11. Production-connected observation runner

`src/liquid_gas_transient/cases/v013_rigid_wall_observation.py`:

- uses the existing `build_coolprop_boundary_reflection_solver` and
  `ReflectiveBoundary`;
- lands exactly on the seven fixed matched times;
- records scalar `rho0`, `c0`, provenance, backend, and CoolProp version;
- passes only scalar reference inputs to the independent analytical/MOC path;
- records FVM field, probe, boundary, timestep, positivity, phase, health, and budget
  evidence;
- records MOC and analytical fields, reflection coefficients, signs, arrivals,
  leakage, wall residuals, field norms, and acoustic-energy proxy;
- writes top-level and per-run JSON, CSV, and NPZ artifacts;
- applies no FVM regression or design-accuracy band.

## 12. Saved-artifact-only figures

`src/liquid_gas_transient/plot_v013_rigid_wall_results.py` reads completed JSON and
CSV artifacts and does not import or call the FVM/MOC/analytical runner.

Output count: `7`.

1. pressure profiles;
2. velocity profiles;
3. reflected `A+ / A-` profiles;
4. near-wall probe pressure history with theoretical timing markers;
5. pressure and velocity reflection coefficients versus mesh spacing;
6. field L2 and acoustic-energy differences versus mesh spacing;
7. normalized wall velocity and pressure-amplification residuals versus mesh spacing.

Each figure includes case, model, property backend, CoolProp version, output version,
and the software/numerical-only, non-design-use disclaimer.

`v013b_plot_metrics.json` records the same traceability fields together with
`solver_rerun = false` and `numerical_results_changed = false`. The plotter updates
`v013b_metrics.json` only with generated filenames, plotting errors, and plot
completion status.

## 13. Required observation metrics

The implementation records:

- FVM, MOC, and analytical pressure, velocity, `A+`, and `A-` fields;
- incident and reflected peak pressure and velocity;
- pressure and velocity reflection coefficients;
- wall velocity residual and wall pressure amplification;
- reflected-wave arrival offsets at all probes;
- FVM/MOC/analytical normalized field errors;
- opposite-direction characteristic leakage;
- acoustic-energy-proxy difference;
- FVM health, positivity, single-phase status, and conserved-budget fields;
- `rho0`, `c0`, provenance, backend, and CoolProp version;
- explicit false Validation, design-evaluation, and acceptance flags.

These are observations. No FVM CI-light or design-accuracy band is introduced in this
increment.

## 14. Artifacts

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
seven PNG figures after plotting
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

## 15. Implementation sequence

1. Fix configuration, IDs, path convention, probe windows, independence, and pure tests. `COMPLETE`
2. Validate the specification scaffold. `COMPLETE`
3. Connect the production FVM and existing rigid wall without changing solver physics. `COMPLETE`
4. Record scalar reference inputs and provenance. `COMPLETE`
5. Implement saved numerical artifacts and matched comparisons. `COMPLETE`
6. Implement the saved-artifact plotter and traceability. `COMPLETE`
7. Validate the runner and plotter. `COMPLETE`
8. Execute `n=100 / 200 / 400`, generate figures, and review the observation. `NEXT`
9. Keep V-013 `IN_PROGRESS`; proceed to V-013C only after V-013B review.

## 16. Current completion boundary

The contract, production-connected runner, saved numerical artifacts, saved-artifact
plotter, and one-mesh installed-CoolProp integration path are verified. The actual
fixed three-mesh FVM/MOC/analytical observation has not yet been executed or accepted.
