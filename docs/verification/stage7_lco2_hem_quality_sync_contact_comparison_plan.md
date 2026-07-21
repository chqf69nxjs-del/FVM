# Stage 7 — Equal-Pressure HEM Contact / Projection Contrast

## Status

`PLANNED VERIFICATION INCREMENT; NO PRODUCTION HEM ACTIVATION`

## Objective

Add the negative-control case for the merged equilibrium-quality projection and
compare it directly with the activated pressure-offset case merged in PR #61.

The increment asks two narrow questions:

1. When two open two-phase states have the same pressure and velocity but
   different qualities, does first-order Rusanov transport diffuse the contact
   without creating a physically meaningful equilibrium-quality mismatch?
2. Does the existing `2.01 / 1.99 MPa` pressure-offset case remain clearly
   distinguishable from that no-op contact by projection count, `|delta q|`, and
   vapor-source activity?

## Physical basis of the no-op expectation

At one fixed saturation pressure, the equilibrium mixture relations are linear
in quality:

```text
v(q) = (1-q) v_l + q v_v
e(q) = (1-q) e_l + q e_v
```

The stationary contact has equal pressure and velocity on both sides. The
Rusanov dissipation mixes conservative extensive quantities. A conservative
mixture of two states on the same saturation line should therefore remain on
that same line, even though the contact profile spreads numerically.

The expected result is not an unchanged solution. The expected result is:

```text
contact profile diffuses
conservative state changes near the interface
maximum quality jump decreases
intermediate-quality cells appear
equilibrium projection updates zero cells
```

## Fixed cases

### Equal-pressure no-op contact

```text
fluid:                    pure CO2
left pressure / quality:  2.00 MPa / 0.45
right pressure / quality: 2.00 MPa / 0.55
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
projection activation:    1e-12
EOS:                      verification-only real-fluid HEM adapter
```

### Activated comparison case

```text
left pressure / quality:  2.01 MPa / 0.45
right pressure / quality: 1.99 MPa / 0.55
all remaining settings:   identical to the no-op contact
```

The activated case is the merged PR #61 runner and is not reimplemented.

## Code boundary

The increment adds one verification runner and its tests/documents. It does not
modify:

- `FvmSolver`;
- physical or Rusanov fluxes;
- CFL calculation;
- boundary classes;
- source terms;
- internal interfaces;
- the merged quality projection;
- the verification HEM EOS;
- production defaults or UI behavior.

## Equal-pressure acceptance requirements

Across four steps:

```text
FvmSolver / Rusanov / CFL are exercised
at least two cells change conservatively
intermediate-quality cells appear
maximum adjacent quality jump decreases
projection cell count is zero at every step
max |delta q| <= 1e-12
q_after matches q_equilibrium within 1e-12
all states remain open liquid-vapor two-phase
all equilibrium sound speeds remain finite and positive
maximum pressure span <= 1e-2 Pa
```

The total variation of a monotone contact is not required to decrease; first-
order diffusion can spread the jump while preserving endpoint-to-endpoint total
variation. The acceptance metric is the maximum adjacent jump and the count of
mixed cells.

## Contrast acceptance requirements

The activated case must show:

```text
projection total cell updates > 0
activated projection count > no-op projection count
activated max |delta q| / max(no-op max |delta q|, machine epsilon) >= 1e6
activated cumulative vapor source magnitude > no-op magnitude
```

Both cases must independently satisfy the existing mass, momentum, energy, and
phase-vapor budget tolerances.

## Budget requirements

For both runs:

- mass change is explained by external boundary fluxes;
- momentum change is explained by external boundary fluxes;
- energy change is explained by external boundary fluxes and zero projection
  energy change;
- vapor-mass change is explained by boundary vapor transport plus the integrated
  projection source;
- relative residuals are no larger than `1e-11`.

For the equal-pressure no-op case, the integrated projection vapor source must
remain exactly zero because no cell crosses the projection activation threshold.

## Evidence artifacts

The runner writes:

```text
stage7_lco2_hem_quality_sync_contact_comparison.json
stage7_lco2_hem_quality_sync_contact_comparison_history.csv
stage7_lco2_hem_quality_sync_contact_comparison_final_profile.csv
stage7_lco2_hem_quality_sync_contact_comparison.md
stage7_lco2_hem_quality_sync_contact_comparison.npz
quality_contact_comparison.png
projection_activity_comparison.png
contact_comparison_budgets.png
```

## Human-review expectations

`quality_contact_comparison.png` should show contact spreading in both cases,
with no isolated spikes.

`projection_activity_comparison.png` should show zero projected cells and
roundoff-level `|delta q|` for the equal-pressure case, while the pressure-offset
case shows nonzero activity.

`contact_comparison_budgets.png` should show zero no-op vapor source, nonzero
activated vapor source, and near-zero vapor-budget residuals for both.

## Approval boundary

```text
verification_only = true
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

This increment does not validate flashing-wave speed, pressure amplitude,
liquid-to-two-phase boundary crossing, production robustness, or design use.

## Next gate

After this negative-control comparison is validated and merged:

1. define the first liquid-to-two-phase boundary-crossing state pair;
2. specify phase-class transitions allowed per step;
3. define projection behavior at `q=0` entry and endpoint tolerances;
4. separate software acceptance from physical flashing validation;
5. only then implement the boundary-crossing runner.
