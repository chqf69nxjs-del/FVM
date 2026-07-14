# Stage 6 V-012 internal valve observation notes

## Scope

This note records the first single-phase internal-valve operation observations
using the existing `KvLiquidValve` and `InternalValveInterface` implementation.

Guardrails:

- software / numerical verification only
- not physical Validation
- not design-use acceptance
- not an ESD-event acceptance study
- no flashing, cavitation, choked flow, or two-phase discharge
- the existing Kv law and interface flux construction are unchanged
- the valve hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`
- CoolProp remains `not_approved_for_design_use`

## Baseline problem

- 100 m, 0.30 m diameter pipe
- 100 finite-volume cells, CFL 0.5
- valve on the centre internal face
- initial left pressure 8.001 MPa
- initial right pressure 8.000 MPa
- initial temperature 280 K
- initially stationary, single-phase CO2
- Kv = 10 m3/h
- transmissive external boundaries
- evaluation stops before the first external-boundary return reaches the valve

Operation kinds:

- constant opening = 0.5
- opening ramp 0 -> 1
- closing ramp 1 -> 0

## Implementation evidence

The runner records:

- prescribed opening and schedule metadata
- left/right valve pressure and pressure difference
- raw Kv target flow and Mach-limited target flow
- actual volumetric flow inferred from the common mass flux
- face velocity, face Mach, and clipping flag
- exact left-segment and right-segment interface fluxes
- mass, momentum, energy, and vapor-mass flux differences
- diagnostic valve loss power
- probe histories, final profile, and global budgets

The runner does not alter the valve law, the governing equations, or the current
energy treatment.

## Clean-environment verification

A clean Python 3.11 environment with project dependencies and CoolProp 8.0.0
was used.

```text
focused V-012 tests: 6 passed
full repository: 223 passed
```

## Initial numerical observations

### Constant opening

- `overall_observation_execution_pass = True`
- remained single phase
- no Mach clipping
- target and mass-flux-derived flow matched to reported precision
- common mass, energy, and vapor-mass flux mismatches were zero to reported precision
- mass and energy budget residuals remained near machine precision

The initial flow was approximately `7.96e-4 m3/s` for the 1 kPa pressure
difference and opening 0.5. The pressure difference relaxed during the selected
window and the flow decreased smoothly.

### Opening ramp

- `overall_observation_execution_pass = True`
- opening history was monotonic non-decreasing
- the initial zero-opening samples had zero through mass, energy, and vapor-mass flux
- no Mach clipping occurred
- finite-opening common flux checks passed
- remained single phase

### Closing ramp

- `overall_observation_execution_pass = True`
- opening history was monotonic non-increasing
- through-flow decayed to zero
- closed samples had zero through mass, energy, and vapor-mass flux
- no Mach clipping occurred
- remained single phase

## Interpretation

The first observations support the expected software path:

- finite opening uses common mass, energy, and vapor-mass fluxes on both valve sides
- momentum flux may differ because the valve body supplies the reaction force
- zero opening degenerates to two independent reflective-wall fluxes
- the prescribed opening schedule is traceable
- Mach limiting is explicitly observable rather than silent

These observations do not establish real-valve performance, actuator dynamics,
loss-coefficient accuracy, physical Validation, or design-use acceptance.

## Next actions

1. confirm the same focused tests and mini-run on Windows
2. add artifact-only plots for opening, pressure difference, flow, interface mismatches, and probes
3. review constant-opening, opening-ramp, and closing-ramp plots
4. define the V-012 mesh/CFL observation only after baseline review
5. defer regression bands, CI-light, report, and manifest until observed trends exist
