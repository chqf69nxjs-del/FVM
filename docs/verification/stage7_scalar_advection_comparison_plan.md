# Stage 7 Numerical-Diffusion Improvement — Scalar Linear-Advection Comparison

## 1. Status

`OBSERVED; STACKED DRAFT; VERIFICATION ONLY`

This increment is stacked on the MUSCL/TVD reconstruction scaffold in PR #52. It does
not modify the production `FvmSolver`, numerical flux, EOS, boundaries, source terms,
phase-change path, or V-013 baseline.

The purpose is to measure transport diffusion in a problem with a known exact solution
before reconstruction is connected to the real-fluid production path.

Validated implementation blobs:

```text
scalar harness: 99de19041123fd521aa3326b7fca44601e033f75
scalar tests:   8fdea83b04678e74a29117b9c8b72b41370d39d4
```

These blobs are unchanged by the post-validation branch cleanup and restacking.

## 2. Why scalar linear advection comes next

The periodic scalar equation

```text
q_t + a q_x = 0
```

has a simple exact solution: the initial profile translates at constant speed without
changing shape. Any peak loss, width growth, phase shift, or artificial oscillation is
therefore attributable to the numerical transport path rather than to:

- thermodynamic inversion;
- CoolProp calls;
- pressure or temperature coupling;
- external boundaries;
- internal interfaces;
- source splitting;
- phase change;
- physical-model uncertainty.

This makes the case suitable for isolating the effect of piecewise-constant versus
MUSCL/TVD spatial reconstruction.

## 3. Fixed canonical problem

The observed comparison uses:

```text
domain:                  periodic [0, 1)
advection velocity:      +1
initial Gaussian centre: 0.25
Gaussian sigma:          0.05
Gaussian amplitude:      1
background:              0
final time:              1 domain transit
meshes:                  n=100 / 200 / 400
CFL:                     0.5
```

After one domain transit, the exact cell-centre profile is the initial wrapped Gaussian.
The wrapped profile also exercises the periodic interface rather than avoiding it.

These values define a software/numerical verification case only. They are not LCO2
operating conditions and do not create an engineering accuracy requirement.

## 4. Comparison matrix

| variant | spatial reconstruction | time integration | role |
|---|---|---|---|
| `first_order_euler` | piecewise constant | Forward Euler | current-style scalar transport control |
| `first_order_ssprk2` | piecewise constant | SSP-RK2 | time-integration control |
| `muscl_minmod_ssprk2` | MUSCL + minmod | SSP-RK2 | conservative limiter candidate |
| `muscl_mc_ssprk2` | MUSCL + MC | SSP-RK2 | balanced limiter candidate |
| `muscl_van_leer_ssprk2` | MUSCL + van Leer | SSP-RK2 | smooth limiter candidate |

The first-order SSP-RK2 row is included so MUSCL rows can be compared against the same
time integrator. This prevents an apparent improvement from being attributed to MUSCL
when it is actually caused by changing time integration.

SSP-RK2 is a verification candidate in this harness. Its inclusion does not approve it
for the production FVM.

## 5. Numerical path

For each time stage:

1. extend the scalar state periodically with two ghost cells per side;
2. use the PR #52 reconstruction module to create interface states;
3. select the upwind state from the sign of the constant velocity;
4. compute conservative interface flux differences;
5. update with Forward Euler or SSP-RK2;
6. fail explicitly on a non-finite state.

A separate negative-velocity test confirms that the right interface state is selected
when information travels in the negative-x direction.

## 6. Reported metrics

Each run records:

- pulse-mass conservation error;
- final peak retention;
- pulse-width growth;
- circular pulse-centre phase error;
- phase error normalized by cell width;
- L1, L2, and L-infinity error against the exact translated profile;
- initial and final periodic total variation;
- total-variation ratio;
- overshoot and undershoot;
- time-step count and actual maximum CFL;
- measured runtime.

Runtime is diagnostic only and varies by runner. It is not a pass band.

## 7. Observed canonical results

### 7.1 Peak retention

| n | first-order Euler | first-order SSP-RK2 | MUSCL minmod | MUSCL MC | MUSCL van Leer |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.57895792 | 0.44923115 | 0.75970845 | 0.90777156 | 0.86734396 |
| 200 | 0.70743850 | 0.57795218 | 0.88811719 | 0.96768181 | 0.94953622 |
| 400 | 0.81655330 | 0.70726739 | 0.95101921 | 0.98833595 | 0.98125212 |

### 7.2 Width growth ratio

An exact translation has width-growth ratio `1`.

| n | first-order Euler | first-order SSP-RK2 | MUSCL minmod | MUSCL MC | MUSCL van Leer |
|---:|---:|---:|---:|---:|---:|
| 100 | 1.73205079 | 2.23604966 | 1.24064758 | 1.03259226 | 1.05981393 |
| 200 | 1.41421356 | 1.73205253 | 1.06683355 | 1.00127071 | 1.00663696 |
| 400 | 1.22474487 | 1.41421370 | 1.01552339 | 1.00015655 | 1.00080623 |

### 7.3 L2 error

| n | first-order Euler | first-order SSP-RK2 | MUSCL minmod | MUSCL MC | MUSCL van Leer |
|---:|---:|---:|---:|---:|---:|
| 100 | 1.20343750e-01 | 1.61133712e-01 | 5.88751429e-02 | 2.95008920e-02 | 3.67475670e-02 |
| 200 | 8.10759398e-02 | 1.20284527e-01 | 2.28191548e-02 | 1.01832762e-02 | 1.27240836e-02 |
| 400 | 4.95020384e-02 | 8.10557940e-02 | 8.79996761e-03 | 3.34003465e-03 | 4.01000495e-03 |

All 15 runs conserved scalar pulse mass to floating-point tolerance, created no new
maximum or minimum, and did not increase periodic total variation.

## 8. Main numerical findings

At `n=200`, compared with the same-time-integrator first-order SSP-RK2 control:

| MUSCL variant | peak-retention increase | L2-error reduction | width-excess reduction |
|---|---:|---:|---:|
| minmod | 53.7% | 81.0% | 90.9% |
| MC | 67.4% | 91.5% | 99.8% |
| van Leer | 64.3% | 89.4% | 99.1% |

The fixed smooth-Gaussian case supports the following observations:

- all three MUSCL/TVD variants materially reduce numerical diffusion;
- MC gives the highest peak retention and lowest L2 error in this comparison;
- van Leer is close to MC and was faster in the recorded runner measurements;
- minmod is more diffusive but remains much sharper than first order;
- every variant improves with mesh refinement;
- changing to SSP-RK2 alone does not cure first-order spatial diffusion;
- the first-order SSP-RK2 control is more diffusive than first-order Euler in this fixed
  semi-discrete comparison, confirming that spatial reconstruction and time integration
  must be assessed separately.

These findings rank candidates for the next experiment only. They do not approve MC,
van Leer, minmod, or SSP-RK2 as a production default.

## 9. Verification evidence

The validation head was:

```text
40e1741f0dd4bc0176447a5bbe2516ef49f148a8
```

Primary validation run:

```text
workflow:                  CoolProp Wave Regression
run ID:                    29724623614
artifact ID:               8453783798
artifact SHA256:           642bbea77078f30ce920876ea2b89bee2d8683099e3ae277ce0431f37612e6f2
V-013 baseline tests:      4 passed
MUSCL reconstruction:      9 passed
scalar-advection tests:    18 passed
focused inventory:         31 passed
full repository:           416 passed, 0 skipped
canonical comparison runs: 15 / 15
comparison artifacts:      4 / 4
committed diff checks:     success
tracked/staged unchanged:  success
```

The four permanent workflows at the validation head all succeeded:

```text
CoolProp Wave Regression:                     29724623614
CoolProp Controlled Pressure Ramp Regression: 29724623616
CoolProp Boundary Reflection Regression:      29724623622
CoolProp Internal Valve Regression:           29724623627
```

The validation artifact contains:

```text
stage7_scalar_advection_comparison.json
stage7_scalar_advection_comparison.csv
stage7_scalar_advection_summary.md
stage7_scalar_advection_profiles.npz
stage7-scalar-full-junit.xml
stage7-scalar-full-summary.json
```

The JSON evidence retains false production-connection, production-behavior-change,
production-time-integrator-approval, physical-Validation, design-use, and numeric-band
flags.

## 10. Deliberately excluded from this increment

This increment does not decide or implement:

- production reconstruction variables;
- production SSP-RK2 or MUSCL-Hancock selection;
- production default limiter;
- positivity preservation for density, pressure, or internal energy;
- EOS-validity checks;
- local first-order fallback;
- rigid-wall or fixed-pressure boundary reconstruction;
- valve, reservoir, or junction reconstruction;
- V-013A/B/C higher-order results;
- a numerical or design-accuracy band.

A scalar TVD result cannot by itself prove that a reconstructed multi-variable real-fluid
state is EOS-valid.

## 11. Completion boundary and next action

The scalar comparison is complete as a software/numerical observation package. PR #53
remains stacked on PR #52 and should not be merged before the reconstruction scaffold.

After PR #52 and this comparison are reviewed, the next design increment should choose
the first production-connected experiment:

1. reconstruction-variable policy;
2. EOS-validity and positivity checks;
3. local first-order fallback;
4. second-order-compatible time integration;
5. transmissive-boundary-only V-013A integration before any reflection case.

V-013B/C remain deferred until boundary-adjacent reconstruction policy is explicit.
