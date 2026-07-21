# Stage 7 — Nonuniform Pure-CO2 HEM Quality Synchronization

## Status

`IMPLEMENTATION DRAFT; VERIFICATION ONLY; OPEN-TWO-PHASE DYNAMIC CASE`

## Objective

Exercise the merged equilibrium-quality projection in a real-fluid, spatially
nonuniform, first-order FVM run before attempting a liquid-to-two-phase phase
boundary crossing.

The test asks one narrow question:

> When conservative transport creates a disagreement between transported
> `rho*q` and the equilibrium quality implied by `rho/e`, does the post-source
> projection repair the state without changing mass, momentum or total energy?

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

Both initial states are deliberately placed well inside the open liquid-vapor
region. The small pressure offset is intended to activate the projection while
avoiding a phase boundary.

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

The strict EOS is expected to be valid before each flux evaluation because the
previous step has already synchronized `rho*q`.

## Required dynamic evidence

Across the four steps:

```text
at least one cell is projected
max |delta q| is finite and positive
q_after matches q_equilibrium within tolerance
rho / rho*u / rho*E are bitwise unchanged by each projection
all projection states remain liquid_vapor_two_phase
all equilibrium sound speeds are finite and positive
CFL does not exceed the fixed value
second-order or production activation is not implied
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

## Recorded history

Each step records:

```text
step / time / dt / CFL
projected / evaporation / condensation cell counts
max |delta q| / sum delta(rho*q)
pressure / velocity / density extrema
quality / void-fraction / sound-speed extrema
mass / momentum / energy relative budget residuals
phase-vapor relative budget residual
cumulative phase-vapor source
cumulative conservative phase-energy delta
```

## Evidence artifacts

The runner writes:

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

The PNG files are generated from the in-memory result returned by the completed
run. Plotting does not rerun or alter the numerical solution.

## Human-review plots

`quality_sync_snapshot.png` shows:

- quality before projection;
- equilibrium quality;
- quality after projection;
- cellwise `delta q`.

`hem_state_profiles.png` shows final pressure, velocity, density, void fraction,
equilibrium sound speed and quality profiles. Phase classification is recorded
cellwise in the profile CSV and must be uniformly `liquid_vapor_two_phase` for
this fixed case.

`conservation_and_projection_history.png` shows projection activity, conservative
budget residuals, cumulative vapor source and vapor-budget residual.

## Acceptance conditions

The case passes only if:

```text
completed steps = 4
projection ever applied = true
projection total cell updates >= 1
all projection invariants satisfied = true
all projection states open two-phase = true
all sound speeds finite and positive = true
maximum post-projection quality mismatch <= 1e-10
all required relative budget residuals <= 1e-11
maximum conservative phase-energy delta = 0
EOS / phase / acoustic failure count = 0
all artifact and PNG files exist and are nonempty
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

After this case is reviewed:

1. add the equal-pressure `q=0.45 / 0.55` nonuniform contact/no-op case;
2. compare its near-zero projection against this activated pressure-offset case;
3. then define the first liquid-to-two-phase expansion problem.
