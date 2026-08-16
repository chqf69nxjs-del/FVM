# Stage 7 P1-A3 Mesh / CFL Sensitivity Increment

## 1. Purpose

P1-A2 established that the observed ordering

```text
pressure-front arrival
→ accepted equilibrium OPEN_TWO_PHASE onset
```

is robust to the predeclared pressure-front threshold envelope
`0.5e-6 / 1.0e-6 / 2.0e-6`.

P1-A3 addresses the next question:

> Does the same bounded engineering interpretation persist when spatial and
> temporal resolution are changed?

This increment is a **characterization layer**. It does not establish formal
mesh independence, CFL independence, physical Validation, design-use
acceptance, or production approval.

## 2. Authority boundary

The existing Gate 6 contract remains locked:

```text
length              1.0 m
diameter            0.10 m
mesh                32 cells
CFL                 0.10
first-crossing case 5 MPa → 2 MPa
continuation        +1 / +4 / +16 / +64 accepted steps
```

P1-A3 does not modify `HEMPostCrossingPropagationConfig` or
`HEMPipelineDepressurizationConfig`.

The exact `32 cells / CFL=0.10` case is executed by the unchanged Gate 6
runner. Four additional cases use a separate verification-only adapter that
permits only the predeclared mesh/CFL pairs while retaining every other
physical model, boundary, EOS, phase classifier, quality projection,
conservation tolerance, and stopping rule.

## 3. Predeclared matrix

| case ID | role | cells | CFL |
|---|---|---:|---:|
| `mesh_16_cfl_0p10` | coarse mesh | 16 | 0.10 |
| `baseline_32_cfl_0p10` | locked Gate 6 baseline | 32 | 0.10 |
| `mesh_64_cfl_0p10` | fine mesh | 64 | 0.10 |
| `cfl_32_0p05` | low CFL | 32 | 0.05 |
| `cfl_32_0p20` | high CFL | 32 | 0.20 |

No case is added or removed after observing the result.

## 4. Compared outputs

The following decision-relevant quantities are retained:

- first-crossing time,
- first-crossing cell and distance from outlet,
- pressure-front position,
- accepted equilibrium phase-front position,
- pressure/phase-front separation,
- vapor mass inventory,
- maximum equilibrium quality,
- maximum void fraction,
- pressure-first ordering at every phase-bearing retained snapshot,
- first-crossing and last-valid-state SHA-256 evidence keys.

The pressure front remains defined by the inherited relative pressure-drop
threshold:

```text
(p_initial - p_cell) / p_initial >= 1e-6
```

The phase front remains the furthest-upstream accepted
`OPEN_TWO_PHASE` cell center.

Both front locations are discrete cell-center diagnostics. They are not
validated physical wave or boiling-front velocities.

## 5. Common physical horizon

Exactly 64 post-crossing accepted steps correspond to different physical
durations when `dx` or CFL changes. Comparing only the final `+64` state would
therefore mix numerical resolution with elapsed physical time.

P1-A3 declares the common horizon as:

```text
minimum completed physical duration from first crossing to +64 steps
across all five cases
```

Each case is sampled at the latest accepted snapshot **not later than** that
common horizon. The sample time and horizon shortfall are retained explicitly.

The final `+64` state is also retained as a diagnostic, but common-horizon
metrics are used for direct case comparison.

## 6. Mesh trend classification

For the `16 / 32 / 64` cell sequence at CFL `0.10`, each metric retains:

```text
coarse value
medium value
fine value
coarse→medium difference
medium→fine difference
difference ratio
apparent order, when defined
```

The trend labels are:

- `INVARIANT_TO_REPORTED_PRECISION`
- `MONOTONIC_CONVERGENT_TREND`
- `OSCILLATORY_DAMPED_TREND`
- `NONCONVERGENT_AT_TESTED_LEVELS`
- `MIXED_TREND`
- `UNAVAILABLE`

Three mesh levels are sufficient for a bounded trend diagnosis, but not by
themselves for formal GCI acceptance or mesh-independent verification.

## 7. CFL sensitivity classification

For `CFL=0.05 / 0.10 / 0.20` at 32 cells, maximum deviation from the locked
`CFL=0.10` reference is classified using predeclared bands:

```text
LOW       <= 2%
MODERATE  <= 10%
HIGH       > 10%
```

For spatial positions, deviation is normalized by the 1.0 m pipe length.
Other positive metrics are normalized by the locked reference magnitude.

These bands classify sensitivity. They are not model calibration tolerances.

## 8. Verdict separation

P1-A3 separates two questions.

### 8.1 Ordering verdict

- `ROBUST`: pressure front is strictly ahead at every phase-bearing
  common-horizon snapshot in every completed case.
- `SENSITIVE`: at least one completed case violates that ordering.
- `INCONCLUSIVE`: required evidence is unavailable.

### 8.2 Numerical verdict

- `ROBUST_ORDERING_WITH_BOUNDED_NUMERICAL_SENSITIVITY`
- `ROBUST_ORDERING_BUT_NUMERICALLY_SENSITIVE`
- `SENSITIVE`
- `INCONCLUSIVE`

A robust ordering verdict does not automatically imply bounded quantitative
mesh/CFL sensitivity.

## 9. Fail-closed gates

The evidence bundle is `SENSITIVITY_READY` only if all of the following hold:

1. the exact five-case matrix is present,
2. the locked Gate 6 baseline reproduces exactly,
3. every case reaches an accepted first crossing,
4. every case completes all 64 continuation steps,
5. a positive common physical horizon exists,
6. every case has a valid sample at or before that horizon,
7. available decision metrics are finite,
8. first-crossing and last-valid-state hashes are present.

A physically interesting partial case does not bypass these gates.

## 10. Output contract

The exact artifact bundle contains nine files:

```text
mesh_cfl_summary.json
case_metrics.csv
mesh_convergence.csv
cfl_sensitivity.csv
front_history.csv
front_comparison.png
decision_metrics.png
operator_report.md
mesh_cfl_manifest.json
```

The manifest records file hashes, sizes, result digest, verdicts, and the
formal maturity boundary.

## 11. Formal maturity

```text
IMPLEMENTED                              true
WORKING VERTICAL SLICE                  false
VERIFIED                                false
ACCEPTED                                false
MESH-INDEPENDENT CROSSING VERIFIED      false
CFL-INDEPENDENT CROSSING VERIFIED       false
PHYSICALLY VALIDATED                    false
DESIGN-USE ACCEPTED                     false
PRODUCTION APPROVED                     false
```

Even a fully successful P1-A3 run remains branch evidence until separately
reviewed and promoted through the project authority process.
