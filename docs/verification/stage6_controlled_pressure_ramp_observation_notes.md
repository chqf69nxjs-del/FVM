# Stage 6 controlled pressure ramp baseline observation notes

## Scope

This note records the first V-011 controlled-pressure-ramp observation. It is
software / numerical verification only. It is not physical Validation,
design-use acceptance, or an approval of `PressureTankBoundary` as a real tank
model.

## Thermodynamic boundary-state issue found and corrected

The initial real-fluid pressure-boundary path updated ghost density from the
requested pressure and configured boundary temperature, but retained the
adjacent cell's old internal energy. The resulting `(rho, e)` state reconstructed
a pressure about 2.5 times larger than the requested pressure perturbation.

The boundary path now updates both density and internal energy from the same
requested `(p, T)` state when the EOS adapter provides the required method.
Manual reconstruction after the correction matched requested ghost pressure to
about `3e-6 Pa` at an 8 MPa base pressure while keeping ghost temperature at
280 K.

## Corrected baseline observations

- requested and actual schedules overlap
- diagnostic boundary-face pressure follows the 1 kPa ramp smoothly
- x/L = 0.75 responds before x/L = 0.50, then x/L = 0.25
- probe pressure responses approach the imposed 1 kPa change
- `A_minus` dominates and `A_plus` remains near zero, consistent with a
  left-going wave from the right boundary
- the x-t pressure map shows a smooth left-running front without visible
  reflection or high-frequency oscillation in the selected observation window
- mass, energy, and vapor-mass balances remain near machine precision

## Arrival-time interpretation

The numerical p50 arrival is slightly later than the direct theoretical p50
arrival at all three probes. The offset appears nearly common while the
numerical and theoretical arrival curves remain nearly parallel.

This suggests that the dominant difference is a common boundary launch-time or
phase offset rather than an incorrect propagation speed. A dedicated front-fit
post-processor therefore separates:

1. slope: inferred propagation speed
2. intercept: fitted boundary p50 launch time and common launch delay

No formal regression band is defined from this single baseline.

## Additional artifacts

The baseline workflow now supports:

- schedule / boundary pressure plot
- probe pressure histories
- characteristic direction histories
- right-boundary flux histories
- p10 / p50 / p90 arrival observations
- p50 theory-versus-numerical comparison
- x-t pressure map
- propagation slope/intercept fit
- x-t map with theoretical and numerical p50 fronts

## Guardrails

- CoolProp remains `not_approved_for_design_use`
- the baseline mesh is not a design mesh
- the finest future mesh will be a comparison reference, not an exact solution
- lower CFL will not be treated as truth
- formal bands remain deferred until mesh/CFL observations exist
