# Stage 7 — Nonuniform Pure-CO2 HEM Quality Synchronization

## Status

`VALIDATED DYNAMIC CASE; VERIFICATION ONLY; OPEN TWO-PHASE REGION`

## Objective

Exercise the merged equilibrium-quality projection in a real-fluid, spatially
nonuniform, first-order FVM run before attempting a liquid-to-two-phase phase
boundary crossing.

The test asks one narrow question:

> When conservative transport creates disagreement between transported `rho*q`
> and the equilibrium quality implied by `rho/e`, does the post-source projection
> repair the state without changing mass, momentum or total energy?

## Fixed case

```text
fluid:                    pure CO2
left pressure / quality:  2.01 MPa / 0.45
right pressure / quality: 1.99 MPa / 0.55
initial velocity:         0 m/s
pipe length / diameter:   10 m / 0.10 m
cells:                    32
CFL:                      0.10
steps:                    4
boundaries:               transmissive / transmissive
source terms:             none
internal interfaces:      none
flux:                     existing first-order Rusanov
phase operator:           HEMEquilibriumQualityProjection
EOS:                      PR #57 verification-only real-fluid HEM adapter
```

Both initial states are deliberately inside the open liquid-vapor region. The
small pressure offset activates the projection while avoiding a phase boundary.

## Existing code boundary

This increment does not modify:

- `FvmSolver`;
- Rusanov or physical fluxes;
- CFL calculation;
- boundary classes;
- source terms;
- internal interfaces;
- the merged equilibrium-quality projection;
- production defaults or UI.

The new module is a verification runner and artifact/plot writer only.

## Step sequence

Each explicit step uses the existing solver order:

```text
projected equilibrium state at time n
        ↓ boundary / Rusanov flux evaluation
conservative FVM update
        ↓
source update (NoSource)
        ↓
equilibrium-quality projection
        ↓
strict HEM primitive evaluation at time n+1
```

The strict EOS remains valid before every flux evaluation because the previous
step has already synchronized `rho*q`.

## Dynamic acceptance requirements

Across four steps:

```text
at least one cell is projected
max |delta q| is finite and positive
q_after matches q_equilibrium within tolerance
rho / rho*u / rho*E are bitwise unchanged by each projection
all projection states remain liquid_vapor_two_phase
all equilibrium sound speeds are finite and positive
CFL does not exceed 0.10
```

The case does not compare against an exact transient solution and does not set a
pressure-wave accuracy band.

## Budget requirements

The existing trackers must show:

- mass change explained by external boundary fluxes;
- momentum change explained by external boundary fluxes;
- energy change explained by external boundary fluxes and zero phase-energy
  projection;
- vapor-mass change explained by boundary vapor flux plus the integrated
  projection source;
- zero conservative energy change from the projection itself.

The fixed relative budget tolerance is `1e-11`.

## Validation evidence

Primary validation completed at head
`8284bf549f9937bdd5d75ed4640dee37a0baae1b`.

```text
workflow run:          29801484953
artifact ID:           8483939146
artifact SHA256:       4156346821f0c04b5d5a569fd6bb64edeb07854a4ae905c4b29f5b3e51152447
focused tests:         46 passed, 0 failed, 0 errors, 0 skipped
full repository:       493 passed, 0 failed, 0 errors, 0 skipped
focused duration:      4.556 s
full duration:         166.858 s
fixed runner:          success
committed diff check:  success
tracked-file check:    success
artifact upload:       success
```

### Numerical observations

```text
completed steps:                         4
final time:                              8.695454540831607e-4 s
maximum CFL:                             0.10
projection total cell updates:          20
projected cells by step:                 2, 4, 6, 8
maximum |delta q|:                       2.4143668471476865e-5
maximum post-projection q mismatch:      5.551115123125783e-16
maximum velocity:                        0.2547984084365163 m/s
pressure range:                          1.99 to 2.01 MPa
quality range:                           0.45 to 0.55
all projection states open two-phase:    true
all sound speeds finite and positive:    true
```

The projection region expands outward from the initial interface as the first-
order Rusanov update spreads the nonuniform state. The maximum correction is at
the interface and decreases from step to step.

### Budget observations

```text
maximum mass relative residual:          1.121454445127481e-16
maximum momentum relative residual:      8.465450562766819e-16
maximum energy relative residual:        0.0
maximum phase-vapor relative residual:   4.528904014764725e-16
maximum conservative phase-energy delta: 0.0 J
cumulative vapor source after step 4:    3.501570117236952e-5 kg
initial vapor mass:                      3.9222314611531215 kg
final vapor mass:                        3.922266476854292 kg
```

The vapor-mass change is therefore accounted for by boundary vapor transport plus
the projection source, while mass, momentum and conservative total energy remain
closed to floating-point tolerance.

## Evidence artifacts

The runner produced:

```text
stage7_lco2_hem_nonuniform_quality_sync.json
stage7_lco2_hem_nonuniform_quality_sync_history.csv
stage7_lco2_hem_nonuniform_quality_sync_final_profile.csv
stage7_lco2_hem_nonuniform_quality_sync.md
stage7_lco2_hem_nonuniform_quality_sync.npz
quality_sync_snapshot.png
hem_state_profiles.png
conservation_and_projection_history.png
```

The PNG files are generated from the completed result. Plotting does not rerun or
alter the numerical solution.

## Human-review findings

`quality_sync_snapshot.png` shows that the correction is localized near the
initial interface. `q_after` overlaps `q_equilibrium`; the visible correction is
of order `1e-5`.

`hem_state_profiles.png` shows smooth first-order transition profiles without
isolated non-finite spikes. The pressure remains inside the prescribed 1.99–2.01
MPa range, velocity remains small, and quality, void fraction and sound speed
remain bounded.

`conservation_and_projection_history.png` shows the projected-cell count expanding
as `2, 4, 6, 8`, conservative residuals at approximately `1e-16`, and cumulative
vapor source growth with a near-zero vapor-budget residual.

Phase classification is stored cellwise in the final-profile CSV and is uniformly
`liquid_vapor_two_phase`.

## Acceptance result

```text
completed steps = 4:                              PASS
projection ever applied:                          PASS
projection total cell updates >= 1:               PASS
all projection invariants satisfied:              PASS
all projection states open two-phase:             PASS
all sound speeds finite and positive:             PASS
post-projection mismatch <= 1e-10:                 PASS
required relative budget residuals <= 1e-11:      PASS
conservative phase-energy delta = 0:               PASS
all artifact and PNG files nonempty:               PASS
```

## Required flags

```text
verification_only = true
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

## Deliberately excluded

This increment does not:

- cross liquid/two-phase or two-phase/vapor boundaries;
- validate flashing-wave speed or amplitude;
- introduce wall heat transfer, friction, valves or discharge boundaries;
- support HNE, impurities, critical states or solid CO2;
- select MUSCL/TVD for production;
- claim design use.

## Next gate

1. remove the temporary validation workflow and confirm the permanent four-file diff;
2. complete final-head permanent CI and merge this activated dynamic case;
3. add the equal-pressure `q=0.45 / 0.55` nonuniform contact/no-op case;
4. compare its near-zero projection against this pressure-offset case;
5. then define the first liquid-to-two-phase expansion problem.
