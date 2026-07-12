# Stage 5 PR-D boundary-reflection CI-light regression band specification

## 1. Purpose

This document defines software/numerical regression bands for the Stage 5 rigid-wall and fixed-pressure boundary-reflection paths.

These bands are intended only to detect severe software regressions in a lightweight CI profile. They are not physical Validation criteria, design-accuracy criteria, design-mesh criteria, CoolProp approval criteria, or models of actual valves and reservoirs.

Guardrails:

- `software_path_verification = true`
- `numerical_verification = true`
- `validation = false`
- `design_evaluation = false`
- `acceptance_gate = false`
- `property_backend_design_status = not_approved_for_design_use`

## 2. Evidence base

Merged PR-C Windows CoolProp sweep:

- rigid wall and fixed pressure
- `n_cells = 50 / 100 / 200`, `CFL = 0.5`
- `n_cells = 100`, `CFL = 0.25 / 0.5`
- 8 unique runs
- `overall_sweep_execution_pass = True`

Observed values at `x/L = 0.90`:

| Metric | Rigid wall n=50 / 100 / 200 | Fixed pressure n=50 / 100 / 200 |
|---|---|---|
| reflection magnitude error | 0.17098 / 0.14392 / 0.11284 | 0.22749 / 0.17657 / 0.13039 |
| reflected-arrival relative error | 1.317e-5 / 1.559e-5 / 1.787e-5 | 0.01638 / 0.008251 / 0.008283 |
| boundary residual | 0 / 0 / 0 | 0.06006 / 0.05975 / 0.04892 |
| reflected characteristic leakage | 0.11323 / 0.03166 / 0.005273 | 0.12150 / 0.03291 / 0.005379 |
| waveform L2 difference vs n=200 reference | 0.35581 / 0.17639 / 0 | 0.38666 / 0.19060 / 0 |

The n=200 waveform difference is zero by definition because it is the comparison reference. It is not an exact-solution error of zero.

Observed n=50/CFL=0.5 budget residuals:

| Metric | Rigid wall | Fixed pressure |
|---|---:|---:|
| mass relative residual | 0 | -2.788269443542063e-16 |
| energy balance relative residual | -3.588314206712315e-16 | -3.5883142067326763e-16 |
| vapor-mass balance relative residual | 0 | 0 |

## 3. CI-light profile

One low-cost case per boundary:

- `n_cells = 50`
- `CFL = 0.5`
- `pressure_amplitude_pa = 1.0e3`
- `p0 = 8.0e6 Pa`
- `T0 = 280 K`
- probes at `x/L = 0.75` and `0.90`
- plots disabled

Profile name:

```text
coolprop_boundary_reflection_ci_light_v1
```

This is a coarse software-regression sentinel, not a recommended analysis mesh.

## 4. Regression gates

### 4.1 Hard health gates

- execution complete
- target time reached
- step limit not exceeded
- all recorded values finite
- positive pressure, temperature, density, and sound speed
- single-phase retained
- required budget fields present
- reflection detected
- expected sign observed
- evaluation windows uncontaminated
- backend status remains `not_approved_for_design_use`

### 4.2 Broad numerical bands

| Check | Rigid wall | Fixed pressure | Basis |
|---|---:|---:|---|
| max reflection magnitude error | 0.25 | 0.30 | observed 0.171 / 0.227 with margin |
| max reflected-arrival relative error | 0.005 | 0.03 | observed ~1e-5 / 0.0164 |
| max reflected characteristic leakage ratio | 0.18 | 0.18 | observed 0.113 / 0.122 |
| max normalized wall-velocity residual | 1e-12 | n/a | observed 0 |
| max normalized fixed-pressure residual | n/a | 0.09 | observed 0.0601 |
| max absolute mass relative residual | 1e-12 | 1e-12 | observed at machine precision |
| max absolute energy balance relative residual | 1e-12 | 1e-12 | observed at machine precision |
| max absolute vapor-mass balance relative residual | 1e-12 | 1e-12 | observed 0 |

These are intentionally wider than observed values. They are regression sentinels, not accuracy acceptance criteria.

### 4.3 Diagnostic-only values

The following are emitted but do not fail CI-light v1:

- waveform L1/L2 difference against a finest-mesh comparison reference
- local convergence-order estimates
- FWHM ratio
- CFL comparison direction
- exact arrival-time monotonicity
- runtime

## 5. Band-change rule

A band change requires:

1. documented reason
2. comparison with the current accepted baseline artifact
3. confirmation that the change is not solely to pass a failing test
4. updated tests and report text
5. MASTER VERIFICATION INDEX update in the same PR

Band widening after a solver change is an investigation trigger, not routine maintenance.

## 6. PR-D implementation sequence

1. Implement a pure evaluator for precomputed metrics.
2. Implement a lightweight two-boundary runner.
3. Add pass/fail/missing-field/wrong-sign/status tests.
4. Add formal Stage 5 report generation.
5. Add SHA256 manifest generation.
6. Add GitHub Actions execution and artifact upload.
7. Run Windows verification.
8. Review V-009 / V-010 and Stage 5 for `COMPLETE`.

## 7. Completion rule

This specification alone does not make Stage 5 complete. Stage 5 remains `IN_PROGRESS` until CI-light, formal report, manifest, reproducible execution, and final review are present.
