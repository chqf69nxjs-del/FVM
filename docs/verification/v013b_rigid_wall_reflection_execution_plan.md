# V-013B Rigid-Wall Reflection Execution Plan

## 1. Status

`OBSERVED; MERGED` in PR #49. Merge commit:
`bc874193de6a4c019073b6cf629e99ec5dfa6602`.

The fixed V-013B production-FVM / independent-MOC / analytical observation has been
executed and reviewed without changing the production solver, numerical flux, or
boundary implementation. V-013 overall remains `IN_PROGRESS`.

## 2. Scope and guardrails

V-013B is software / numerical verification only. It is not physical Validation,
design-use acceptance, approval of `coolprop_co2` for design use, a production MOC
solver, an equipment-fidelity wall model, or a two-phase/flashing result. No phase
shift or parameter fitting is permitted.

The pure specification module does not import or call production FVM, numerical flux,
production boundary classes, existing FVM case runners, or CoolProp. Public package
exports are lazy, and a fresh-interpreter test enforces runtime independence.

## 3. Fixed problem

```text
verification item: V-013B
case role: rigid_wall_reflection
pipe length / diameter: 100 / 0.30 m
base pressure / temperature: 8 MPa / 280 K
pulse: right-going Gaussian A+
pulse amplitude / centre / sigma: 100 Pa / 65 m / 2 m
left boundary: transmissive observation boundary
right boundary: rigid wall
FVM meshes / CFL: 100, 200, 400 / 0.5
MOC meshes / CFL: 100, 200, 400 / 1.0
probe x/L: 0.75 / 0.85 / 0.90
probe-window half width: 2.0 sigma
matched-field boundary guard: 5.0 sigma
```

Stable run identifiers:

```text
v013b_n0100_fvmcfl0p5_moccfl1
v013b_n0200_fvmcfl0p5_moccfl1
v013b_n0400_fvmcfl0p5_moccfl1
```

## 4. Reference identities and sampling

The independent core defines
`A+ = 0.5 (p' + rho0 c0 u')` and `A- = 0.5 (p' - rho0 c0 u')`.
For a right rigid wall:

```text
A-_reflected = A+_incident
pressure reflection coefficient = +1
velocity reflection coefficient = -1
wall velocity perturbation = 0
total wall pressure / incident amplitude = 2
```

Cumulative path travel is the common time convention: `t = path_travel / c0`.

| path travel [m] | phase | expected centre [m] | dominant characteristic |
|---:|---|---:|---|
| 0 | incident | 65 | A+ |
| 15 | incident | 80 | A+ |
| 25 | incident | 90 | A+ |
| 35 | wall contact | 100 | A+ + A- |
| 45 | reflected | 90 | A- |
| 55 | reflected | 80 | A- |
| 65 | reflected | 70 | A- |

Analytical values are evaluated at recorded FVM cell centres and times. MOC uses fixed
linear time/space interpolation. Probe windows remain strictly separated and end
before the leading edge of any secondary return pulse.

## 5. Implemented path and artifacts

`v013_rigid_wall_observation.py` uses the existing CoolProp initial-state builder and
`ReflectiveBoundary`, lands at the seven fixed times, records FVM health/budget/boundary
evidence, passes scalar `rho0/c0` to the independent reference, and writes traceable
JSON, CSV, and NPZ artifacts.

`plot_v013_rigid_wall_results.py` reads saved artifacts only and generates seven
figures: pressure, velocity, characteristics, probe history, reflection coefficients,
field/energy differences, and wall-condition residuals. Every figure includes case,
model, backend, CoolProp version, output version, and the non-design-use disclaimer.

## 6. Validation and corrected observation evidence

Implementation checks:

```text
specification scaffold focused/full: 53 / 346 passed
runner focused/full:                 55 / 348 passed
runner/plotter focused/full:         57 / 350 passed
failures / errors / skips:           0 / 0 / 0
git diff --check:                    success
```

Final evidence:

```text
workflow run:       29684930259
PR head:            dbb17b45f19a973741da4998e57591a529fb25f2
Actions merge SHA:  8670c95122cc0d470469b8445590cd03029133b8
runs:               3 / 3
figures:            7 / 7
plotting errors:    0
CoolProp:           8.0.0
artifact ID:        8441899419
artifact entries:   59
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

The velocity-error normalization policy is explicitly recorded:

```text
pressure: analytical_pressure_perturbation_pa
velocity: analytical_pressure_perturbation_pa / (rho0 * c0)
A+ / A-:  analytical_pressure_perturbation_pa
```

This avoids a zero denominator at exact wall contact. All velocity norms are finite.
The figure code displays exact zero wall velocity as zero. Plotting did not rerun a
solver or change numerical results.

## 7. Observation results

| n | Δx [m] | pressure reflection coefficient | velocity reflection coefficient | wall pressure ratio | final reflected peak ratio |
|---:|---:|---:|---:|---:|---:|
| 100 | 1.00 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 |
| 200 | 0.50 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 |
| 400 | 0.25 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 |

The reflection direction and signs are correct. Wall face velocity, mass flux, and
energy flux are exactly zero. All principal amplitude/error indicators improve with
mesh refinement. Strong FVM numerical diffusion remains substantial at `n=400`, so
this is not an accuracy-acceptance result.

## 8. Completion boundary

Completed and merged for V-013B:

- fixed specification, IDs, samples, windows, and guardrails;
- independent rigid-wall identities and runtime independence;
- production-connected runner and traceable artifacts;
- saved-artifact-only seven-figure plotter;
- corrected finite error normalization;
- focused/full tests, three-mesh execution, visual review, and artifact digest;
- temporary evidence/fix workflows, trigger, and script removed;
- final-head permanent workflows `4 / 4` successful;
- review threads resolved and final Codex review returned no findings.

Physical Validation, design-use acceptance, and V-013 CI-light/design-accuracy bands
remain outside this increment. Next: begin V-013C fixed-pressure reflection.
