# Stage 7 P1-A3F Sub-threshold Crossing Forensics

## 1. Purpose

P1-A3 attempted the predeclared mesh/CFL matrix:

| case | cells | CFL |
|---|---:|---:|
| `mesh_16_cfl_0p10` | 16 | 0.10 |
| `baseline_32_cfl_0p10` | 32 | 0.10 |
| `mesh_64_cfl_0p10` | 64 | 0.10 |
| `cfl_32_0p05` | 32 | 0.05 |
| `cfl_32_0p20` | 32 | 0.20 |

The fine-mesh and low-CFL cases returned:

```text
GUARD_FAILURE
crossing quality evidence is below the fixed minimum
```

P1-A3F determines exactly what happened at the retained first crossing without
changing the fixed evidence floor or allowing the failed cases to continue.

## 2. Questions

P1-A3F answers three bounded questions.

1. Did every case actually retain a liquid-to-two-phase crossing event?
2. Was the only distinction between accepted and guarded cases whether the
   first-crossing equilibrium quality was above or below `1e-6`?
3. Do the observed values support an interaction between first-crossing depth
   and mesh/CFL resolution?

It does not answer whether the `1e-6` floor should be changed.

## 3. Frozen authority boundary

The following remain unchanged:

```text
physical model                       HEM equilibrium
fluid                                pure CO2
pipe length / diameter               1.0 m / 0.10 m
initial pressure / subcooling        5 MPa / 5 K
outlet path                          5 MPa -> 2 MPa linear ramp
phase classifier                     unchanged
quality projection                   unchanged
solver and Rusanov flux              unchanged
conservation tolerances              unchanged
crossing evidence floor              1e-6
```

The original A3 failure remains valid evidence. A3F is a separate diagnostic
increment based on the A3 branch head.

## 4. Retained evidence

For each of the five cases, A3F records:

- outcome and failure reason,
- crossing step, time, and time step,
- mesh size and CFL,
- crossing cells and positions,
- maximum first-crossing equilibrium quality,
- quality-to-floor ratio and margin,
- final-state and run-signature SHA-256 values.

For each crossing cell, A3F additionally records:

- previous, raw, and accepted regions,
- transition event,
- previous accepted quality,
- raw equilibrium quality,
- post-projection quality,
- transported raw vapor fraction,
- post-projection void fraction,
- density and internal energy,
- previous, raw, and post-projection pressure,
- raw temperature,
- first and second projection flags.

The failed first-crossing runner already retains this partial state before it
returns `GUARD_FAILURE`; A3F exposes it rather than altering the runner.

## 5. Direct mechanism rule

The direct failure mechanism is `CONFIRMED` only when all five cases retain a
positive crossing and every case falls into exactly one of these categories:

```text
ACCEPTED_ABOVE_FIXED_FLOOR
    outcome == ACCEPTED_FIRST_CROSSING
    q_cross / 1e-6 >= 1

SUBTHRESHOLD_CROSSING_RETAINED
    outcome == GUARD_FAILURE
    0 < q_cross / 1e-6 < 1
    failure reason names the fixed crossing-quality floor
```

Any backend, conservation, reverse-flow, nonfinite, or unrelated guard failure
causes A3F to fail closed.

## 6. Resolution-interaction diagnosis

A3F separates two observations.

### CFL axis

At 32 cells, it retains the first-crossing quality at:

```text
CFL = 0.05 / 0.10 / 0.20
```

The trend is reported as increasing, decreasing, invariant, nonmonotonic, or
unavailable. No trend is hardcoded.

### Mesh axis

At CFL `0.10`, it retains the first-crossing quality at:

```text
16 / 32 / 64 cells
```

A fine-mesh boundary effect is present when the locked 32-cell case is at or
above the fixed floor while the 64-cell case remains below it. This diagnoses a
classification interaction; it is not formal mesh convergence.

## 7. Fail-closed gates

The diagnostic bundle is `FORENSICS_READY` only if:

1. the original five-case matrix is exact,
2. every case retains a first crossing,
3. accepted/guarded classification is explained by the unchanged quality floor,
4. no unrelated failure category appears,
5. crossing quality, time, and time step are finite,
6. deterministic hashes are present for every case,
7. the `1e-6` evidence floor is unchanged.

## 8. Output contract

The exact artifact bundle contains eight files:

```text
forensic_summary.json
case_forensics.csv
cell_forensics.csv
quality_scaling.csv
quality_vs_dx.png
quality_vs_cfl.png
operator_report.md
forensic_manifest.json
```

The manifest records hashes, sizes, forensic digest, status, and maturity
boundary.

## 9. Interpretation boundary

A successful A3F run may establish:

> the direct A3 fail-closed mechanism is confirmed and the fixed evidence-floor
> classification interacts with the tested mesh/CFL resolution.

It does not establish:

- that the physical solution failed,
- that the evidence floor is wrong,
- that the threshold may be lowered,
- mesh independence,
- CFL independence,
- physical Validation,
- design-use acceptance,
- production approval.

## 10. Formal maturity

```text
IMPLEMENTED                              true
DIAGNOSTIC EVIDENCE READY               false until separately reviewed
WORKING VERTICAL SLICE                  false
VERIFIED                                false
ACCEPTED                                false
MESH-INDEPENDENT CROSSING VERIFIED      false
CFL-INDEPENDENT CROSSING VERIFIED       false
PHYSICALLY VALIDATED                    false
DESIGN-USE ACCEPTED                     false
PRODUCTION APPROVED                     false
```
