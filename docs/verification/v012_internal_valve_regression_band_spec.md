# V-012 single-phase internal-valve CI-light regression-band specification

## Purpose

This document defines broad software / numerical regression sentinels for the
single-phase CoolProp internal-valve path after the completed V-012 mesh/CFL
observation.

These limits are not:

- physical Validation criteria;
- design-use acceptance criteria;
- operating or equipment-protection limits;
- proof that the CI-light mesh is a design mesh;
- proof that the finest observed mesh is an exact solution;
- proof that lower CFL is truth;
- flashing, cavitation, choked-flow, or two-phase criteria.

The limits are deliberately wider than the observed PR #40 coarse-case values.
Their purpose is to detect material software-path regressions without presenting
numerical observation bands as physical accuracy requirements.

## CI-light profile

All four baseline roles are exercised at the least expensive observed common
profile:

```text
n_cells = 50
CFL = 0.5
property backend = coolprop_co2
CoolProp = 8.0.0
```

Included cases:

| item | role |
|---|---|
| V-012A | uniform-state preservation and zero-flow sentinel |
| V-012B | finite-opening driven-flow and interface consistency |
| V-012C | prescribed opening ramp and opening-wave direction/timing |
| V-012D | prescribed closing ramp, closing-wave direction, and complete closure |

The four-case profile is still low cost while covering paths that cannot be
represented by a single valve case.

## Observed PR #40 coarse reference values

At `n=50`, `CFL=0.5`:

| metric | V-012A | V-012B | V-012C | V-012D |
|---|---:|---:|---:|---:|
| initial applied Q [m3/s] | `0` | `3.5343e-5` | `0` | `7.0686e-5` |
| maximum applied Q [m3/s] | `0` | `3.5343e-5` | `4.3128e-5` | `7.0686e-5` |
| final applied Q [m3/s] | `0` | `2.7402e-5` | `4.3126e-5` | `0` |
| near-probe p50 offset max [s] | n/a | `4.5636e-3` | `1.9002e-3` | `4.8728e-3` |
| near-probe characteristic peak mean [Pa] | n/a | `107.883` | `275.994` | `193.549` |
| opposite-direction ratio max | n/a | `1.521e-6` | `1.810e-6` | `1.023e-6` |
| maximum pressure disturbance [Pa] | `0` | `200.000` | `313.891` | `202.130` |
| maximum velocity [m/s] | `0` | `3.887e-4` | `6.101e-4` | `3.929e-4` |

All observed coarse cases retained positive finite single-phase states, complete
budget telemetry, zero Mach-cap activations, and interface consistency at numerical
roundoff.

For V-012D, post-closure applied Q was zero, flux-derived Q was approximately
`2.6e-25 m3/s`, mass through-flux was approximately `3.4e-21 kg/m2/s`, and energy
and vapor-mass through-flux were zero.

## Formal CI-light limits

### Common health and conservation

| check | limit |
|---|---:|
| absolute mass relative residual | `<= 1e-12` |
| absolute energy relative residual | `<= 1e-12` |
| absolute vapor-mass relative residual | `<= 1e-12` |
| maximum opening error | `<= 1e-12` |
| mass-flux two-sided mismatch | `<= 1e-12 kg/m2/s` |
| energy-flux two-sided mismatch | `<= 1e-8 W/m2` |
| vapor-mass-flux two-sided mismatch | `<= 1e-12 kg/m2/s` |
| flux-derived Q minus applied Q | `<= 1e-15 m3/s` |
| raw/applied relative difference where evaluated | `<= 1e-10` |
| applied/flux relative difference where evaluated | `<= 1e-10` |
| opposite-direction characteristic ratio | `<= 1e-3` |
| Mach-cap activation count | `0` |

Required boolean and identity checks:

- all four expected V-012 items are present exactly once;
- `n_cells = 50` and `CFL = 0.5` for every row;
- execution and saved-artifact analysis complete;
- all histories finite;
- pressure, temperature, density, and sound speed positive;
- single-phase state retained;
- no required budget fields missing;
- property backend exactly `coolprop_co2`;
- CoolProp version exactly `8.0.0`;
- `property_backend_design_status = not_approved_for_design_use`;
- flow-sign consistency equals `1.0` for driven cases;
- near-probe characteristic-direction checks pass for V-012B/C/D.

### V-012A preservation sentinel

| check | limit |
|---|---:|
| maximum raw, applied, or flux-derived Q magnitude | `<= 1e-15 m3/s` |
| maximum pressure disturbance | `<= 1e-6 Pa` |
| maximum velocity | `<= 1e-12 m/s` |
| hydraulic-separation fraction | `1.0` |
| no-flow-direction fraction | `1.0` |

### V-012B finite-opening driven flow

| check | limit |
|---|---:|
| initial applied Q | `3.0e-5` to `4.0e-5 m3/s` |
| final applied Q | `2.0e-5` to `3.5e-5 m3/s` |
| maximum near-probe p50 timing offset | `<= 8e-3 s` |
| mean near-probe characteristic peak | `50` to `200 Pa` |
| expected finite-opening hydraulic separation fraction | `0` |

### V-012C opening ramp

| check | limit |
|---|---:|
| initial applied Q magnitude | `<= 1e-15 m3/s` |
| maximum applied Q | `3.0e-5` to `6.0e-5 m3/s` |
| final applied Q | `3.0e-5` to `6.0e-5 m3/s` |
| maximum near-probe p50 timing offset | `<= 5e-3 s` |
| mean near-probe characteristic peak | `150` to `400 Pa` |

Required direction checks:

- opening is monotonic non-decreasing;
- upstream decompression is observed;
- downstream compression is observed.

### V-012D closing ramp and complete closure

| check | limit |
|---|---:|
| initial applied Q | `6.0e-5` to `8.0e-5 m3/s` |
| final applied Q magnitude | `<= 1e-15 m3/s` |
| maximum near-probe p50 timing offset | `<= 8e-3 s` |
| mean near-probe characteristic peak | `100` to `300 Pa` |
| post-closure hydraulic-separation fraction | `1.0` |
| post-closure no-flow-direction fraction | `1.0` |
| post-closure raw/applied Q magnitude | `<= 1e-15 m3/s` |
| post-closure flux-derived Q magnitude | `<= 1e-15 m3/s` |
| post-closure mass through-flux magnitude | `<= 1e-12 kg/m2/s` |
| post-closure energy through-flux magnitude | `<= 1e-8 W/m2` |
| post-closure vapor-mass through-flux magnitude | `<= 1e-12 kg/m2/s` |
| finite-opening momentum residual | `<= 1e-8 Pa` |

Required direction and branch checks:

- opening is monotonic non-increasing;
- upstream compression is observed;
- downstream decompression is observed;
- the finite-opening momentum relation is not applied to closed rows.

## Rationale

The Q ranges are broad envelopes around the observed coarse values rather than
accuracy bands. Timing limits are approximately 1.6 to 2.6 times the observed
coarse p50 offsets. Characteristic-amplitude intervals are deliberately broad and
only protect against disappearance, sign/path corruption, or order-one changes.
The leakage limit is roughly three orders of magnitude above the observed values
because those values are near a diagnostic floor.

Quantities expected to be zero use absolute limits instead of relative ratios.
Budget limits remain `1e-12`, consistent with earlier verification stages.

Limits must not be weakened merely to make a future test pass. A failure shall first
be investigated as a possible change in:

- valve scheduling or Kv calculation;
- internal-interface flux construction;
- finite-opening versus closed-wall branch selection;
- numerical flux or timestep logic;
- characteristic decomposition and timing extraction;
- conservation accounting;
- CoolProp property behaviour;
- output schema or traceability.

## Deferred formalization

The permanent CI workflow shall run the four-case profile without skips and upload
a machine-readable result. The final V-012 formal report and SHA256 manifest remain
a separate completion artifact and shall preserve the distinction between
software/numerical verification, physical Validation, and design-use acceptance.
