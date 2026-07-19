# V-013C Fixed-Pressure Reflection Execution Plan

## 1. Status

`OBSERVED; READY FOR REVIEW`

The fixed V-013C production-FVM / independent-MOC / analytical observation has been
executed and reviewed without changing the production solver, numerical flux, EOS
inversion, or fixed-pressure boundary implementation. V-013 overall remains
`IN_PROGRESS`.

## 2. Scope and guardrails

V-013C is software / numerical verification only. It is not physical Validation,
design-use acceptance, approval of `coolprop_co2` for design use, a production MOC
solver, an equipment-fidelity reservoir model, or a two-phase/flashing result.

No time shifting, phase fitting, or post-result parameter tuning is permitted. No FVM
regression, CI-light, or design-accuracy band is introduced in this increment.

The pure specification module imports no production solver, numerical flux, boundary
class, existing FVM runner, or CoolProp module. A fresh-interpreter test enforces this
runtime independence.

## 3. Fixed problem

```text
verification item: V-013C
case role: fixed_pressure_reflection
pipe length / diameter: 100 / 0.30 m
base pressure / temperature: 8 MPa / 280 K
pulse: right-going Gaussian A+
pulse amplitude / centre / sigma: 100 Pa / 65 m / 2 m
left boundary: transmissive observation boundary
right boundary: fixed pressure p0
FVM meshes / CFL: 100, 200, 400 / 0.5
MOC meshes / CFL: 100, 200, 400 / 1.0
probe x/L: 0.75 / 0.85 / 0.90
probe-window half width: 2.0 sigma
matched-field boundary guard: 5.0 sigma
matched path travel: 0 / 15 / 25 / 35 / 45 / 55 / 65 m
```

Stable run identifiers:

```text
v013c_n0100_fvmcfl0p5_moccfl1
v013c_n0200_fvmcfl0p5_moccfl1
v013c_n0400_fvmcfl0p5_moccfl1
```

## 4. Reference identities

The independent core defines
`A+ = 0.5 (p' + rho0 c0 u')` and `A- = 0.5 (p' - rho0 c0 u')`.
For the right fixed-pressure boundary:

```text
A-_reflected = -A+_incident
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

The production path uses the existing:

```text
PressureTankBoundary(
    ConstantPressure(p0),
    flow_direction="bidirectional",
    velocity_policy="copy",
)
```

Unlike the rigid wall, this is not a zero-flux boundary. Boundary mass and energy
fluxes and their time integrals are recorded as observations and are not required to be
zero.

## 5. Sampling and contamination protection

Cumulative path travel is the common time convention: `t = path_travel / c0`.

| path travel [m] | phase | expected centre [m] | characteristic state |
|---:|---|---:|---|
| 0 | incident | 65 | `A+` |
| 15 | incident | 80 | `A+` |
| 25 | incident | 90 | `A+` |
| 35 | boundary contact | 100 | `A+` and opposite-sign `A-` |
| 45 | reflected | 90 | `A-` |
| 55 | reflected | 80 | `A-` |
| 65 | reflected | 70 | `A-` |

Analytical values are evaluated at recorded FVM cell centres and times. MOC uses fixed
linear time/space interpolation. Probe windows are strictly separated, and a reflected
window is classified as contaminated when its trailing edge reaches the leading edge of
the earliest secondary-return pulse.

## 6. Implemented path and artifacts

`v013_fixed_pressure_observation.py`:

- uses the existing CoolProp initial-state builder and fixed-pressure production boundary;
- lands exactly on the seven fixed matched times;
- records FVM field, probe, boundary, health, positivity, phase, and budget evidence;
- passes scalar `rho0` and `c0` to independent analytical/MOC paths;
- records reflection signs and coefficients, timing, leakage, field norms, acoustic
  energy proxy, fixed-pressure residual, boundary velocity amplification, mass flux,
  energy flux, and integrated transfer;
- writes traceable JSON, CSV, and NPZ artifacts.

`plot_v013_fixed_pressure_results.py` reads saved artifacts only and generates seven
figures:

1. pressure profiles;
2. velocity profiles;
3. reflected `A+ / A-` characteristic profiles;
4. near-boundary pressure history with theoretical event markers;
5. pressure and velocity reflection coefficients versus mesh spacing;
6. field and acoustic-energy differences versus mesh spacing;
7. fixed-pressure residual and boundary-velocity amplification error versus mesh spacing.

Every figure includes case, model, backend, CoolProp version, output version, and the
software/numerical-only non-design-use disclaimer.

## 7. Error normalization

Fixed-pressure contact may produce an analytical pressure field that is zero at the
boundary while the two characteristics remain nonzero. Field normalization therefore
uses a finite characteristic amplitude scale derived from `|A+| + |A-|` for pressure
and characteristic comparisons, and the corresponding acoustic velocity scale divided
by `rho0 c0` for velocity. The policy is persisted in comparison artifacts and tested
for finite values.

## 8. Validation evidence

### Specification scaffold

```text
committed-range workflow: 29689975579
focused tests:            53 passed, 0 skipped
full repository:          380 passed, 0 skipped
git diff range:           origin/main...HEAD
committed diff check:     success
```

The initial working-tree-only diff evidence was superseded after a P3 review finding.
The corrected review thread is resolved.

### Windows project recheck

```text
focused tests:       58 passed in 10.61 s
full repository:     385 passed in 277.41 s
committed diff:      clean
working tree:        clean
```

### Final observation

```text
workflow run:       29692477941
PR head:            2f5c10b3f99f561d457ab8d391d5e91be98b7ff3
Actions merge SHA:  e2eb1a075d229d51d28366aa211a1642fbcc1463
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
runs:               3 / 3
figures:            7 / 7
plotting errors:    0
CoolProp:           8.0.0
artifact ID:        8444138380
artifact entries:   59
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
```

Plotting confirms:

```text
solver_rerun = false
numerical_results_changed = false
```

Temporary observation, finalization, and review-helper workflows were removed after
evidence capture.

## 9. Observation results

| n | Δx [m] | pressure reflection | velocity reflection | fixed-pressure residual | boundary velocity ratio | final peak ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 1.00 | -0.63395297 | 0.63399661 | 0.05654903 | 0.82447607 | 0.33190828 |
| 200 | 0.50 | -0.69829946 | 0.69829998 | 0.04880759 | 1.09704849 | 0.44185022 |
| 400 | 0.25 | -0.77022729 | 0.77022778 | 0.03712903 | 1.37073388 | 0.57212615 |

The reflection direction and signs are correct. The boundary-pressure residual decreases
and the velocity amplification moves toward the ideal value `2` with refinement.
Nonzero boundary transfer is expected and retained in the evidence.

Maximum pressure/velocity L2 relative differences decrease from approximately `0.681`
at `n=100` to `0.413` at `n=400`. Strong numerical broadening and peak loss remain
substantial, so the finest mesh is not an accuracy-acceptance result.

## 10. Completion boundary

Complete for V-013C review:

- fixed specification, IDs, samples, event windows, and contamination guards;
- independent identities and runtime independence;
- production-connected runner and traceable artifacts;
- saved-artifact-only seven-figure plotter;
- finite error normalization;
- focused/full tests, Windows recheck, three-mesh execution, and artifact digest;
- temporary evidence/review helpers removed.

Physical Validation, design-use acceptance, and V-013 regression/design-accuracy bands
remain outside this increment.

Next: complete final review and merge PR #50, then formalize the combined V-013A/B/C
baseline and propose cautious CI-light monitoring before beginning the numerical-diffusion
improvement phase.
