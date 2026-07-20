# Stage 7 — Pure-CO2 HEM Uniform-State Preservation

## Status

`VALIDATED STACKED DRAFT PR #57; VERIFICATION-ONLY FVM CONNECTION`

This increment is based on PR #56 final head
`3e032ced2cb8f65e058783886b36b58a72b7719e`.

## Objective

Exercise the existing first-order `FvmSolver`, Rusanov flux, transmissive boundaries and CFL
calculation with one uniform real-fluid liquid-vapor HEM state. A correct conservative
connection must not change an initially uniform stationary state.

Fixed case:

```text
pure CO2
p = 2 MPa
quality q = 0.50
u = 0 m/s
uniform rho/e/rho*q in every cell
transmissive left and right boundaries
NoSource
NoPhaseChange
no internal interfaces
first-order Rusanov FVM
```

## Narrow verification EOS adapter

The new adapter is local to this verification increment. It:

1. converts conserved `rho`, `rho*u`, `rho*E`, `rho*q` to `rho/e`;
2. uses explicit CoolProp phase classification from PR #55;
3. requires an open liquid-vapor two-phase supported state;
4. requires transported quality to match equilibrium CoolProp quality;
5. obtains pressure, temperature, quality and void fraction from the phase-state path;
6. obtains equilibrium sound speed from the guarded finite-difference closure in PR #56;
7. returns the existing `PrimitiveState` used by Rusanov flux and CFL;
8. caches repeated identical `rho/e` evaluations.

A quality mismatch is rejected. This increment does not silently project `rho*q` to an
equilibrium value.

## Existing production code boundary

The increment does not modify:

- `FvmSolver`;
- `rusanov_flux` or physical flux definitions;
- CFL logic;
- common EOS defaults;
- boundary-condition classes;
- source or phase-change operators;
- internal interfaces;
- production configuration or UI.

The existing solver is exercised through structural compatibility with the verification-only
EOS adapter.

## Preservation requirements

After multiple explicit steps:

```text
conserved U unchanged
rho unchanged
u unchanged
p unchanged
T unchanged
quality unchanged
void fraction unchanged
equilibrium sound speed unchanged
mass inventory unchanged
momentum inventory unchanged
energy inventory unchanged
vapor-mass inventory unchanged
```

The fixed case is expected to preserve the state exactly in floating-point arithmetic because
all interfaces see identical left and right states and therefore have identical fluxes.
Conservative and primitive drift metrics are recorded even when they are zero.

## Validation evidence

Primary validation:

```text
validation head:          068bd1d9d1a57c30687cf217273d9f87eb04f424
workflow run:             29751190749
artifact ID:              8464712262
artifact SHA256:          71f7934f6f0061191f8af09b9cdf802a5b797f628878cd045a13a94273f5e999
focused HEM tests:        76 passed, 0 skipped
full repository:          460 passed, 0 skipped
uniform cells / steps:    8 / 8
final time:               0.018414079163974254 s
dt:                       0.002301759895496782 s
CFL maximum:              0.25
```

Fixed-state thermodynamics:

```text
rho:                       99.97757528102285 kg/m3
e:                         276181.4404260976 J/kg
T:                         253.64735829812284 K
quality:                   0.5
void fraction:             0.951436972434191
equilibrium sound speed:   135.76568112572576 m/s
```

Observed drift after eight first-order steps:

```text
conserved maximum absolute drift:  0.0
conserved maximum relative drift:  0.0
rho drift:                         0.0
velocity drift:                    0.0
pressure drift:                    0.0
temperature drift:                 0.0
quality drift:                     0.0
void-fraction drift:               0.0
sound-speed drift:                 0.0
mass inventory drift:              0.0
momentum inventory drift:          0.0
energy inventory drift:            0.0
vapor-mass inventory drift:        0.0
```

The EOS cache contained one unique `rho/e` state, and phase and sound-speed evaluation were
each performed once. The result demonstrates exact uniform-state preservation for this fixed
software path. It does not demonstrate accuracy for a nonuniform two-phase flow.

## Evidence artifacts

The runner emits:

```text
stage7_lco2_hem_uniform_state_preservation.json
stage7_lco2_hem_uniform_state_preservation.csv
stage7_lco2_hem_uniform_state_preservation.md
stage7_lco2_hem_uniform_state_preservation.npz
```

Required flags remain:

```text
fvm_solver_exercised = true
rusanov_flux_exercised = true
cfl_exercised = true
verification_only_hem_eos_adapter = true
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

## Deliberately excluded

This increment does not:

- handle a nonuniform state;
- cross a liquid/two-phase phase boundary;
- apply HEM projection after transport;
- add wall friction, heat transfer, valves or pressure boundaries;
- support HNE, impurities, critical states or solid CO2;
- establish a sound-speed accuracy band;
- add a one-dimensional expansion or depressurization problem;
- claim physical Validation or design use.

## Next gate

The next increment is a first-order one-dimensional liquid-to-two-phase expansion problem
with simple transmissive boundaries. That case will introduce real spatial gradients and test
whether phase classification, equilibrium flash, sound speed, flux and CFL remain consistent
when a two-phase region evolves.
