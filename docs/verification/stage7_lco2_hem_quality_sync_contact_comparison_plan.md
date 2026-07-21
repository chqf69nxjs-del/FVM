# Stage 7 — Equal-Pressure HEM Contact / Projection Contrast

## Status

`VALIDATED NEGATIVE CONTROL; VERIFICATION ONLY; NO PRODUCTION HEM ACTIVATION`

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

The activated case uses the merged PR #61 runner and is not reimplemented.

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

## Validation evidence

Primary validation completed at head
`7a6dd47b7c72eb87f3415b66bdc4d034ff7c19b5`.

```text
workflow run:          29812617503
artifact ID:           8488096499
artifact SHA256:       db0a5e997bd3fc07cba2d5a7470724778f2a3ac831ea1c62804e26a97c37b19b
Python:                3.11.15
CoolProp:              8.0.0
matplotlib:            3.11.1
numpy:                 2.4.6
focused tests:         67 passed in 5.04 s
full repository:       514 passed in 127.91 s
fixed runner:          success
static diff checks:    success
artifact upload:       success
```

### Equal-pressure numerical observations

```text
completed steps:                         4
maximum CFL:                             0.10
projection total cell updates:          0
projected cells by step:                 0, 0, 0, 0
maximum |delta q|:                       4.440892098500626e-16
maximum post-projection q mismatch:      4.440892098500626e-16
transport-changed cells:                 8
mixed-quality cells:                     8
initial maximum adjacent quality jump:   0.10000000000000037
final maximum adjacent quality jump:     0.06788855198828081
maximum pressure span:                   1.6298145055770874e-9 Pa
maximum absolute velocity:               1.206100596343292e-14 m/s
projection vapor source:                 0.0 kg
```

The contact is therefore numerically transported and spread, but conservative
mixing stays on the same equilibrium saturation line to floating-point accuracy.
The zero projection count is an exercised no-op, not an unexercised solver path.

### Activated-case contrast

```text
projection total cell updates:          20
projected cells by step:                 2, 4, 6, 8
maximum |delta q|:                       2.4143668471476865e-5
maximum post-projection q mismatch:      5.551115123125783e-16
activated / no-op |delta q| ratio:       5.436670816575e10
cumulative projection vapor source:      3.501570117236952e-5 kg
```

The pressure-offset case remains separated from the no-op control by more than
ten orders of magnitude in maximum quality correction and by nonzero projection
cell count and vapor-source activity.

### Budget observations

```text
equal-pressure maximum mass residual:       0.0
equal-pressure maximum momentum residual:   5.314528579114535e-16
equal-pressure maximum energy residual:     0.0
equal-pressure maximum vapor residual:      1.132118480131348e-16
activated maximum mass residual:            1.121454445127481e-16
activated maximum momentum residual:        8.465450562766819e-16
activated maximum energy residual:          0.0
activated maximum vapor residual:           4.528904014764725e-16
maximum conservative phase-energy delta:    0.0 J in both cases
```

## Evidence artifacts

The runner produced:

```text
stage7_lco2_hem_quality_sync_contact_comparison.json
stage7_lco2_hem_quality_sync_contact_comparison_history.csv
stage7_lco2_hem_quality_sync_contact_comparison_final_profile.csv
stage7_lco2_hem_quality_sync_contact_comparison.md
stage7_lco2_hem_quality_sync_contact_comparison.npz
quality_contact_comparison.png
projection_activity_comparison.png
contact_comparison_budgets.png
focused_pytest.txt
full_pytest.txt
numerical_summary.txt
validation_environment.txt
SHA256SUMS.txt
```

## Human-review findings

`quality_contact_comparison.png` shows monotone first-order spreading in both
cases with no isolated quality spike or endpoint overshoot.

`projection_activity_comparison.png` shows zero projected cells and roundoff-
level `|delta q|` for all equal-pressure steps. The pressure-offset case expands
as `2, 4, 6, 8` projected cells and remains near `1e-5` in correction magnitude.

`contact_comparison_budgets.png` shows an exactly zero equal-pressure projection
vapor source and a monotone nonzero source in the activated case.

## Acceptance result

```text
equal-pressure contact transport exercised:        PASS
equal-pressure mixed cells >= 2:                    PASS
equal-pressure maximum quality jump reduced:       PASS
equal-pressure projection updates = 0:              PASS
equal-pressure max |delta q| <= 1e-12:              PASS
equal-pressure pressure span <= 1e-2 Pa:            PASS
activated projection updates > 0:                   PASS
activated/no-op |delta q| ratio >= 1e6:             PASS
activated vapor source > no-op vapor source:        PASS
both cases remain open two-phase:                    PASS
both cases close required budgets:                   PASS
comparison acceptance:                              PASS
```

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

After this negative-control comparison is merged:

1. define the first liquid-to-two-phase boundary-crossing state pair;
2. specify phase-class transitions allowed per step;
3. define projection behavior at `q=0` entry and endpoint tolerances;
4. separate software acceptance from physical flashing validation;
5. only then implement the boundary-crossing runner.
