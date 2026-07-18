# Stage 7 V-013A Incident-Propagation Observation Notes

## Status

`OBSERVED; READY FOR REVIEW`

V-013 remains `IN_PROGRESS`.  This increment covers only the reflection-free
incident-wave comparison.  Rigid-wall reflection, fixed-pressure reflection,
CI-light bands, formal reporting, and the SHA256 manifest remain later work.

## Scope and guardrails

This is software / numerical verification only.  It is not:

- physical Validation;
- design-use acceptance;
- CoolProp backend approval;
- a production MOC solver;
- a nonlinear valve, flashing, cavitation, HEM, HNE, ESD, or pump-trip result.

The FVM path retains
`property_backend_design_status = not_approved_for_design_use`.  The independent
MOC / analytical path receives recorded scalar `rho0` and `c0` values and does not
call CoolProp.

## Source and execution evidence

```text
PR:                         #48
source branch head:         043f9f5c769ca3781b3144d9f430f3a60853e562
observed PR merge ref:      39fbdc522c6afcc282d3c863d361fdf466f85d28
GitHub Actions run:         29647234616
artifact name:              v013a-incident-propagation-39fbdc522c6afcc282d3c863d361fdf466f85d28
artifact SHA256:            ee537e0e32a14d01501e36b427af68f94881905bc01f4a3b68684508c15c0961
focused tests:              39 passed, 0 skipped
full repository tests:      315 passed, 0 skipped
planned / executed runs:    3 / 3
aggregate runtime:          474.31903558 s
comparison plots:           7 / 7
```

The existing permanent CoolProp wave, controlled-pressure-ramp,
boundary-reflection, and internal-valve workflows also passed on the same source
head.

## Fixed problem

```text
pipe length:                100 m
base pressure:              8 MPa
base temperature:           280 K
pressure amplitude:         100 Pa
pulse centre:               20 m
pulse sigma:                2 m
probe x/L:                  0.35 / 0.50 / 0.65 / 0.80
FVM meshes:                 100 / 200 / 400
FVM CFL:                    0.5
MOC meshes:                 100 / 200 / 400
MOC CFL:                    1.0
matched centre travel:      0 / 20 / 40 / 60 / 65 m
```

The last accepted sample places the Gaussian centre at `85 m`; the observation
window ends before right-boundary reflection contaminates the comparison.

## Reference constants and provenance

```text
rho0: 922.9172130294444 kg/m3
c0:   557.4488783994866 m/s
```

- `rho0` provenance: `CoolPropCO2Backend.density_from_pT` at the recorded `p0/T0`.
- `c0` provenance: `LCO2PropertyEOSAdapter` primitive sound speed at the same
  uniform state.
- the values were identical across the three FVM meshes;
- the independent MOC path did not call CoolProp;
- no time shifting or parameter fitting was used.

## Software-health result

Every FVM run:

- reached the prescribed final matched-sample time;
- remained finite;
- retained positive pressure, temperature, density, and sound speed;
- remained single phase with zero vapor mass fraction and zero alpha;
- retained all required mass, total-energy, and vapor-mass budget fields;
- stayed within the configured step limit.

Representative relative budget residuals remained at zero or floating-point
roundoff (`O(1e-16)`).

## Quantitative mesh observation

The values below are maximum differences over the prescribed matched field samples.
They are observations, not formal regression or design-accuracy limits.

| n | dx [m] | FVM pressure L2 error | FVM max |p50 offset| [s] | FVM p50 speed error | FVM max |energy difference| | MOC pressure L2 error | MOC max |p50 offset| [s] | MOC max |energy difference| |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 1.00 | 0.6654954870 | 0.0078785444 | 0.0685331694 | 0.6693306771 | 0.0267143668 | 0.0002219875 | 0.0302934686 |
| 200 | 0.50 | 0.5441232217 | 0.0048810641 | 0.0430619393 | 0.5556955812 | 0.0067438537 | 0.0000634065 | 0.0077517815 |
| 400 | 0.25 | 0.4071310259 | 0.0028902909 | 0.0259801110 | 0.4256973184 | 0.0016900802 | 0.0000142610 | 0.0019493153 |

### Interpretation

- FVM pressure, velocity, arrival-time, propagation-speed, and acoustic-energy-proxy
  differences all decrease monotonically with mesh refinement.
- FVM arrival crossings are early relative to the analytical signal.  The early bias
  is consistent with the visibly broadened numerical leading edge and must not be
  interpreted as the physical wave travelling faster than `c0`.
- FVM pressure and velocity L2 differences remain substantial even at `n=400`.
  The finest mesh is therefore not accepted as an exact or design-accurate solution.
- FVM opposite-direction characteristic leakage remains approximately `1.0e-6` to
  `1.2e-6` in the aggregate observation, while the dominant issue is numerical
  diffusion of the intended `A+` pulse rather than a spurious reflected wave.
- Native grid-aligned MOC translation agrees with the analytical evaluator exactly
  in the saved MOC metrics.  Its reported FVM-grid comparison error comes from the
  fixed spatial/time interpolation used to sample the nodal MOC at FVM cell centres
  and probe times.
- MOC pressure and acoustic-energy-proxy differences decrease approximately
  second-order with grid refinement, as expected for linear interpolation of the
  smooth Gaussian profile.

## Final matched profile observation

At centre travel `65 m`:

| n | analytical pressure peak [Pa] | FVM pressure peak [Pa] | FVM peak ratio | FVM peak-location error [m] | MOC peak ratio |
|---:|---:|---:|---:|---:|---:|
| 100 | 96.92332345 | 32.94137877 | 0.33987050 | 1.00 | 0.97112688 |
| 200 | 99.22179383 | 44.34853010 | 0.44696360 | 0.50 | 0.99233906 |
| 400 | 99.80487811 | 57.38723632 | 0.57499430 | 0.25 | 0.99805640 |

This confirms strong but systematically decreasing FVM diffusion of the narrow
Gaussian pulse.  It does not show instability, a wrong propagation direction, or a
secondary-boundary return.

## Human-review figures

The seven saved-artifact figures were reviewed without rerunning either solver:

1. pressure profiles at several matched times;
2. final velocity profile;
3. final `A+ / A-` characteristic profiles;
4. far-probe pressure history and p50 markers;
5. field error versus mesh spacing;
6. arrival / fitted-speed observation versus mesh spacing;
7. acoustic-energy-proxy difference versus mesh spacing.

The figures consistently show:

- analytical and MOC curves nearly overlapping;
- the FVM pulse travelling in the correct direction;
- decreasing FVM broadening and peak loss with refinement;
- no visible incident-window boundary reflection;
- no anomalous oscillatory growth.

## Mesh decision

The initial `100 / 200 / 400` matrix is sufficient to establish the direction and
character of the V-013A error: the FVM result is stable and improves monotonically,
but remains strongly diffusive for this `sigma = 2 m` pulse.

No `n=800` run is added in this increment.  This does **not** assert that `n=400` is
converged.  A finer incident-wave run may be reconsidered before final V-013 band
selection if the combined V-013A/B/C evidence cannot justify a meaningful
software-regression gate.

## Review conclusion

No software-health, direction, independence, traceability, or secondary-boundary
blocker was found for V-013A.  The observation should be read as a quantified
numerical-diffusion result, not an accuracy acceptance.

Next action after merge: implement and observe V-013B rigid-wall reflection using the
same independent reference conventions, followed by V-013C fixed-pressure
reflection.  Final CI-light bands shall be proposed only after all three cases are
reviewed.
