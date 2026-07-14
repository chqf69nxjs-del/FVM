# Stage 6 controlled pressure ramp mesh/CFL observation notes

## Scope

This note records the first V-011 controlled-pressure-ramp mesh/CFL observation.
It is software / numerical verification only. It is not physical Validation,
design-use acceptance, or approval of `PressureTankBoundary` as a real tank
model.

The finest mesh is a comparison reference, not an exact solution. Lower CFL is
not treated as truth. No formal regression or acceptance band is defined here.

## Run matrix

Four unique runs were executed:

| case | cells | dx [m] | CFL | groups |
|---|---:|---:|---:|---|
| `n0050_cfl050` | 50 | 2.0 | 0.5 | mesh |
| `n0100_cfl025` | 100 | 1.0 | 0.25 | CFL |
| `n0100_cfl050` | 100 | 1.0 | 0.5 | mesh and CFL |
| `n0200_cfl050` | 200 | 0.5 | 0.5 | mesh |

The shared `n=100`, `CFL=0.5` point was executed once.

All four runs:

- completed successfully
- remained single phase
- retained `property_backend_design_status = not_approved_for_design_use`
- kept mass, energy, and vapor-mass residuals near machine precision
- completed baseline, probe analysis, pressure-field replay, and p50 front fit

## Mesh observations at CFL = 0.5

### Common p50 launch / phase offset

The absolute common offset decreased monotonically:

```text
dx = 2.0 m : 4.212 ms
dx = 1.0 m : 2.230 ms
dx = 0.5 m : 1.189 ms
```

The decrease is close to first-order over these three meshes. This supports the
interpretation that the baseline `2.23 ms` offset is primarily a discretization
or boundary-cell phase effect rather than a physical tank-response delay.

### Mean p50 arrival relative error

The mean three-probe p50 error also decreased monotonically:

```text
dx = 2.0 m : 5.028 %
dx = 1.0 m : 2.583 %
dx = 0.5 m : 1.352 %
```

This trend is also close to first-order over the observed range.

The pressure-front tails are more sensitive to numerical diffusion:

```text
mean p10 error: 8.117 % -> 5.650 % -> 3.642 %
mean p90 error: 23.336 % -> 11.701 % -> 6.549 %
```

The larger p90 error is consistent with the rounded trailing portion of a finite
ramp front. It is an observation, not a formal accuracy classification.

### Pressure amplitude

The primary-probe peak-amplitude error decreased monotonically and was already
extremely small:

```text
2.117e-7 -> 6.893e-8 -> 3.369e-8
```

The pressure ramp therefore retained its approximately `1 kPa` amplitude across
the observed meshes.

### Opposite-direction characteristic leakage

The leakage ratio remained nearly constant at approximately `5.2e-6`:

```text
5.169e-6 -> 5.193e-6 -> 5.207e-6
```

The small upward change is below one percent across the whole mesh range and is
not interpreted as a meaningful loss of directionality. It appears closer to a
measurement / decomposition floor than a mesh-converging error in this case.

### Inferred wave-speed error

The fitted wave-speed error was non-monotonic:

```text
dx = 2.0 m : 1.284e-3
dx = 1.0 m : 6.910e-6
dx = 0.5 m : 3.822e-4
```

The `dx=1.0 m` result lies very close to the reference sound speed and likely
contains a favourable cancellation between front fit, interpolation, and
boundary phase effects. The `dx=0.5 m` result remains substantially better than
the coarse-grid result, but the three values do not support a monotonic wave-
speed convergence claim.

The p50 fit remained highly linear in all cases (`R^2` near one), so the main
mesh-dependent result is still the reduced common offset and reduced arrival-
time error.

## CFL observations at n = 100

Comparing `CFL=0.25` and `CFL=0.5`:

| metric | CFL 0.25 | CFL 0.5 |
|---|---:|---:|
| wave-speed relative error | `4.139e-5` | `6.910e-6` |
| common offset | `2.153 ms` | `2.230 ms` |
| mean p50 relative error | `2.498 %` | `2.583 %` |
| mean p10 relative error | `8.211 %` | `5.650 %` |
| mean p90 relative error | `14.147 %` | `11.701 %` |
| amplitude error | `6.455e-8` | `6.893e-8` |
| leakage ratio | `5.181e-6` | `5.193e-6` |
| total runtime | `206.6 s` | `67.1 s` |

Lower CFL slightly reduced the common offset and mean p50 error, but worsened the
p10, p90, and fitted wave-speed errors in this observation. It also increased
total runtime by about a factor of three. This confirms that lower CFL must not
be treated as truth or as an automatically superior result.

## Overall classification

The automated mesh classification is `mixed_behavior` because:

- common offset improved monotonically
- p50 timing improved monotonically
- amplitude error improved monotonically
- wave-speed error improved overall but was non-monotonic
- characteristic leakage stayed essentially flat

The dominant timing and phase indicators show a clear useful mesh trend.

## 400-cell decision

A 400-cell run is not added for this observation.

Reasons:

- common offset, p10/p50/p90 timing, and amplitude already show clear improvement
- the wave-speed fit is already very close to the reference and its remaining
  non-monotonicity is consistent with fit / interpolation cancellation
- characteristic leakage is already at an approximately `5e-6` floor
- the 200-cell run cost about `355 s`, so a higher-cost case is not justified by
  an unresolved primary trend

## Status and next action

V-011 should move from `IN_PROGRESS` to `OBSERVED` after this PR is merged.

The next V-011 step is formalization:

1. define broad CI-light regression-band candidates from the observed results
2. choose a low-cost CI profile without treating it as a design mesh
3. add CI-light evaluation and GitHub Actions
4. generate a formal report and SHA256 manifest
5. review V-011 for `COMPLETE`

Single-phase valve operation remains a separate V-012 activity.