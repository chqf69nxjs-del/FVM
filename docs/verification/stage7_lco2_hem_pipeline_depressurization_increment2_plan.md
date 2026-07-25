# Stage 7 — LCO2 HEM Pipeline Depressurization Increment 2 Plan

## Status

`IMPLEMENTED IN PR #77; FIXED-MATRIX OBSERVATION UNDER REVIEW; VERIFICATION ONLY`

## Objective

Connect the merged PR #75 prescribed-subcooled outlet boundary to the fixed PR #74
1.0 m / 32-cell first-order Rusanov prototype and execute the fixed 5→2, 5→3,
and 5→4 MPa short-run matrix.

The runner shall stop at the first accepted crossing or retain an explicit guarded outcome.
It shall not tune the fixed case definitions, algorithms, or tolerances to manufacture a
crossing or an all-liquid control.

## Fixed implementation scope

```text
geometry:                    1.0 m x 0.10 m horizontal pipe
mesh:                        32 uniform cells, dx=0.03125 m
ghost cells:                 2
initial state:               5 MPa / 5 K subcooling, u=0, q=0
left boundary:               existing ReflectiveBoundary
right boundary:              PR #75 prescribed-subcooled outlet_only boundary
numerical flux:              existing first-order Rusanov
CFL:                         0.10
ramp duration:               one initial acoustic time
maximum horizon:             three initial acoustic times
maximum steps:               2000
physical sources:            none
friction / heat / gravity:   none / none / none
internal interfaces:         none
```

## Fixed case matrix

```text
pipeline_crossing_candidate_p5m5_to_p2m5
pipeline_moderate_diagnostic_p5m5_to_p3m5
pipeline_liquid_control_p5m5_to_p4m5
```

Every boundary schedule is preflighted at 65 points before the first FVM step.

## Per-step sequence

```text
accepted U^n
  -> accepted-state EOS and CFL dt
  -> left reflective and right prescribed-subcooled ghost states
  -> existing Rusanov FVM raw update
  -> direct raw rho/e boundary-region and transition detection
  -> fail-fast endpoint / forbidden / reverse-flow / backend handling
  -> existing equilibrium-quality projection
  -> require crossing cells = first-projection cells
  -> existing mixed liquid/open-two-phase EOS recovery
  -> require second projection no-op
  -> record boundary and projection vapor contributions separately
  -> record pressure-wave and cellwise evidence
  -> stop on accepted crossing or explicit guarded result
```

## Required retained evidence

```text
case summary JSON and CSV
step CSV
cell CSV
boundary-path CSV
Markdown summary
NPZ arrays
initial acoustic time and pressure-ramp duration
boundary thermodynamic state by step
pressure-drop arrival time by cell
raw phase region and transition event by cell and step
projection cells and delta q
crossing step, time, cell, and distance from outlet
post quality mismatch and second-projection count
conservative boundary budgets
boundary vapor transport
internal projection vapor source
combined vapor residual
failure reason
state and run signatures
```

## Guardrails

The increment does not modify the production solver, Rusanov flux, CFL algorithm, phase
classifier, projection algorithm, accepted-state EOS, or fixed tolerances. It does not add
MUSCL/TVD, friction, heat transfer, gravity, a valve/orifice law, choked flow, tank
coupling, HNE, mesh convergence, or physical Validation.

The fixed `q_eq >= 1e-6` accepted-crossing threshold is evidence strength only. A raw
thermodynamic crossing below that value must be retained as an explicit guard result; it
must not be silently relabeled as all liquid or accepted crossing.

## Gate decision rule

Gate P2 may pass only when all of the following are true:

```text
the fixed matrix is executed without changing a case, algorithm, or tolerance
the 2 MPa candidate is ACCEPTED_FIRST_CROSSING or NO_CROSSING_WITHIN_HORIZON
the 3 MPa diagnostic is ACCEPTED_FIRST_CROSSING or NO_CROSSING_WITHIN_HORIZON
the 4 MPa control is exactly NO_CROSSING_WITHIN_HORIZON
the 4 MPa control has no raw liquid-to-two-phase crossing, including a subthreshold one
reverse-flow fallback remains zero
budgets close
frozen PR #72 Case A/B regressions remain exact
```

A 4 MPa raw crossing with `0 < q_eq < 1e-6` is retained as an explicit
`GUARD_FAILURE`, but it does not satisfy the all-liquid control and therefore keeps
Gate P2 false.

The authoritative outcome and Gate decision are recorded in:

- [`stage7_lco2_hem_pipeline_depressurization_increment2_evidence.md`](stage7_lco2_hem_pipeline_depressurization_increment2_evidence.md)
- [`stage7_lco2_hem_pipeline_depressurization_increment2_observation_contract_v1.json`](stage7_lco2_hem_pipeline_depressurization_increment2_observation_contract_v1.json)
