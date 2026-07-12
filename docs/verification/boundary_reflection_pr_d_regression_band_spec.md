# Stage 5 PR-D boundary-reflection CI-light regression band specification

## 1. Purpose

This document defines candidate software/numerical regression bands for the Stage 5 rigid-wall and fixed-pressure boundary-reflection paths.

These bands are intended only to detect severe software regressions in a lightweight CI profile. They are not:

- physical Validation criteria
- design-accuracy acceptance criteria
- design-mesh acceptance criteria
- CoolProp backend approval criteria
- representations of an actual valve or reservoir

The governing guardrails remain:

- `software_path_verification = true`
- `numerical_verification = true`
- `validation = false`
- `design_evaluation = false`
- `acceptance_gate = false`
- `property_backend_design_status = not_approved_for_design_use`

## 2. Evidence base

The initial candidate bands are based on the merged PR-C Windows CoolProp sweep:

- boundary kinds: rigid wall and fixed pressure
- mesh observation: `n_cells = 50 / 100 / 200`, `CFL = 0.5`
- CFL observation: `n_cells = 100`, `CFL = 0.25 / 0.5`
- unique runs: 8
- `overall_sweep_execution_pass = True`

Observed mesh values at the primary `x/L = 0.90` probe:

| Metric | Rigid wall n=50 / 100 / 200 | Fixed pressure n=50 / 100 / 200 |
|---|---|---|
| pressure-reflection magnitude error | 0.17098 / 0.14392 / 0.11284 | 0.22749 / 0.17657 / 0.13039 |
| reflected-arrival relative error | 1.317e-5 / 1.559e-5 / 1.787e-5 | 0.01638 / 0.008251 / 0.008283 |
| boundary residual | 0 / 0 / 0 | 0.06006 / 0.05975 / 0.04892 |
| reflected characteristic leakage ratio | 0.11323 / 0.03166 / 0.005273 | 0.12150 / 0.03291 / 0.005379 |
| waveform L2 difference vs n=200 reference | 0.35581 / 0.17639 / 0 | 0.38666 / 0.19060 / 0 |

The n=200 waveform difference is zero by definition because it is the comparison reference. It is not an exact-solution error of zero.

## 3. CI-light profile candidate

The first CI-light profile should use one low-cost case per boundary:

- `n_cells = 50`
- `CFL = 0.5`
- `pressure_amplitude_pa = 1.0e3`
- `p0 = 8.0e6 Pa`
- `T0 = 280 K`
- probes at `x/L = 0.75` and `0.90`
- no plots required in CI

Profile name candidate:

```text
coolprop_boundary_reflection_ci_light_v1
```

The profile is deliberately coarse. It is a software-regression sentinel, not a recommended analysis mesh.

## 4. Candidate regression bands

### 4.1 Hard health gates

These checks must pass without a tolerance derived from PR-C trends:

- execution completes without exception
- target time reached
- step limit not exceeded
- all recorded values finite
- pressure, temperature, density, and sound speed remain positive
- single-phase condition retained
- required budget fields present
- reflection detected
- expected reflection sign observed
- evaluation windows not contaminated
- backend status remains `not_approved_for_design_use`

### 4.2 Broad numerical bands

The following are candidate CI-light limits for the coarse n=50/CFL=0.5 path.

| Check | Rigid-wall candidate | Fixed-pressure candidate | Basis |
|---|---:|---:|---|
| max pressure-reflection magnitude error | 0.25 | 0.30 | PR-C observed 0.171 and 0.227, with margin for software/environment variation |
| max reflected-arrival relative error | 0.005 | 0.03 | PR-C observed ~1e-5 and 0.0164 |
| max reflected characteristic leakage ratio | 0.18 | 0.18 | PR-C observed 0.113 and 0.122 |
| max normalized wall-velocity residual | 1e-12 | n/a | PR-C observed exact zero; broad near-zero software guard |
| max normalized fixed-pressure residual | n/a | 0.09 | PR-C observed 0.0601 |
| max waveform L2 difference vs formal reference | diagnostic only | diagnostic only | CI-light must not require n=200 reference execution |

These limits are intentionally wider than the observed values. They should detect large implementation regressions while avoiding false precision.

### 4.3 Budget bands

Mass, energy, and vapor-mass balance limits must be taken from the actual PR-C metrics JSON before implementation.

Until those values are extracted and reviewed, the candidate limits remain:

```text
max_abs_mass_relative_residual = TBD
max_abs_energy_balance_relative_residual = TBD
max_abs_vapor_mass_balance_relative_residual = TBD
```

No guessed value may be committed as a gate.

### 4.4 Diagnostic-only values

The following should be emitted but should not fail CI-light v1:

- waveform L1/L2 difference against a finest-mesh comparison reference
- local convergence-order estimates
- FWHM ratio
- CFL comparison direction
- exact arrival-time monotonicity
- runtime

## 5. Band-change rule

A band change requires all of the following:

1. a documented reason
2. comparison with the current accepted baseline artifact
3. confirmation that the change is not made solely to pass a failing test
4. updated tests and report text
5. MASTER VERIFICATION INDEX update in the same PR

Band widening after a solver change must be treated as an investigation trigger, not routine maintenance.

## 6. PR-D implementation sequence

1. Extract budget values from the existing PR-C sweep metrics artifact.
2. Finalize the broad CI-light limits.
3. Implement a pure evaluator that consumes precomputed metrics.
4. Implement a lightweight runner for both boundary kinds.
5. Add tests for pass, fail, missing-field, wrong-sign, and status-guard cases.
6. Add formal Stage 5 report generation.
7. Add SHA256 artifact manifest generation.
8. Add GitHub Actions execution and artifact upload.
9. Run Windows verification.
10. Review V-009 / V-010 and Stage 5 for `COMPLETE` status.

## 7. Completion rule

This specification alone does not make Stage 5 complete. Stage 5 remains `IN_PROGRESS` until CI-light, formal report, manifest, reproducible execution, and final review are all present.
