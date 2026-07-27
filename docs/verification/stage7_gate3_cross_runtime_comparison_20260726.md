# Stage 7 Gate 3 Cross-Runtime Numeric Comparison

Date: 2026-07-26

## Executive assessment

`RAW NUMERIC EVIDENCE SUPPORTS NUMERICALLY_EQUIVALENT; FINAL GATE 3 CLOSURE PENDING FULL-REPOSITORY SUITE AND FORMAL RECORD`

The Windows candidate and Ubuntu reference retain exact discrete event identity for all three fixed 128-cell / CFL 0.10 cases. Raw time, pressure, and accepted-state arrays are not bitwise identical, but their differences are extremely small, finite, and well below existing inventory-budget tolerances. The difference is already present in the uniform initial thermodynamic state before the first FVM update, localizing the seed to the platform/property-runtime path rather than a later change in event logic.

This report does not approve physical Validation, design use, acoustic accuracy, post-crossing propagation, CFL independence, or production HEM activation.

## Evidence integrity

- Windows candidate ZIP: `stage7-gate3-numeric-candidate-20260726-222235.zip`
  - size: `4392060` bytes
  - SHA256: `508e9b727a2e0d00974e4650c3f927e93af89eed9af96cde5c2b0b3e12368738`
- ZIP CRC check: passed
- Ubuntu reference ZIP: `stage7-gate3-numeric-reference-30202888092.zip`
  - size: `4374864` bytes
  - SHA256: `78002ddb524c9f1cac00040a14139d6da512f66f19d39a65afc53dbcac188060`
- ZIP CRC check: passed

## Runtime identity

- Windows: `Windows-11-10.0.26200-SP0` / Python `3.12.10` / NumPy `2.5.1` / CoolProp `8.0.0`
- Windows solver checkout: `f1b2c76827482164a12e2924bf7119a0b150e421`; clean tree
- Ubuntu reference: Python `3.12.13` / NumPy `2.5.1` / CoolProp `8.0.0`

## Exact event identity

| Case | Outcome | Step | Crossing cell | Outlet distance [m] | Discrete identity |
|---|---|---:|---:|---:|---|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 403 | 120 | 0.05859375 | EXACT |
| 5→3 MPa | `GUARD_FAILURE` | 578 | 118 | 0.07421875 | EXACT |
| 5→4 MPa | `GUARD_FAILURE` | 1086 | 113 | 0.11328125 | EXACT |

## Raw-array maximum differences

| Case | max |Δt| [s] | max |Δp| [Pa] | max |Δρ| [kg/m³] | max |Δρu| | max |ΔρE| [J/m³] | max |Δxᵥ| |
|---|---:|---:|---:|---:|---:|---:|
| 5→2 MPa | 2.690e-15 | 1.244e-05 | 2.419e-10 | 9.739e-09 | 3.079e-05 | 6.135e-16 |
| 5→3 MPa | 1.394e-15 | 1.190e-05 | 4.204e-10 | 8.245e-09 | 5.430e-05 | 2.624e-15 |
| 5→4 MPa | 9.929e-16 | 1.446e-05 | 2.528e-10 | 8.812e-09 | 3.490e-05 | 2.251e-15 |

Worst global-scale-normalized errors across all cases:

- time history: `4.189e-12`
- pressure history: `2.893e-12`
- density: `4.604e-13`
- momentum density: `5.519e-12`
- energy density: `2.863e-13`

The largest global-scale-normalized error is `5.519e-12`, below the proposed `1e-10` cross-runtime guard.

Pointwise relative errors near zero are intentionally not used for acceptance because they can become order unity when both compared values are round-off residuals.

## Initial-state localization

The first state difference occurs at time index 0, before any FVM time step. All three cases share the same initial seed:

- initial density difference: `1.251e-12 kg/m³`
- initial specific internal-energy difference: `4.366e-10 J/kg`
- initial energy-density difference: `6.557e-07 J/m³`
- recovered initial-pressure difference: `5.290e-07 Pa`
- first time-step difference: `4.176e-18 s`

Momentum remains exactly zero initially; its first difference appears only after boundary-driven evolution begins. The transported vapor variable remains exactly zero until the crossing step and differs only in the crossing cell(s).

## Inventory comparison against existing absolute tolerances

| Quantity | max cross-runtime difference | existing absolute tolerance | Result |
|---|---:|---:|---|
| Mass [kg] | 2.842e-14 | 1.000e-12 | PASS |
| Momentum [kg·m/s] | 1.358e-11 | 1.000e-10 | PASS |
| Energy [J] | 1.723e-08 | 1.000e-06 | PASS |
| Vapor mass [kg] | 2.392e-16 | 1.000e-12 | PASS |

Large relative percentages reported for some budget residuals are not physically meaningful because both values are near machine zero. Their absolute magnitudes remain far below the fixed tolerances.

## Crossing-threshold robustness

| Case | q candidate | distance from 1e-6 threshold | Windows–Ubuntu | difference / threshold margin |
|---|---:|---:|---:|---:|
| 5→2 MPa | 1.199e-06 | 1.991e-07 | 6.135e-16 | 3.082e-09 |
| 5→3 MPa | 5.978e-07 | 4.022e-07 | 2.624e-15 | 6.523e-09 |
| 5→4 MPa | 3.858e-07 | 6.142e-07 | 2.251e-15 | 3.665e-09 |

The cross-runtime differences are many orders of magnitude smaller than the distance to the fixed `1e-6` acceptance threshold, so the accepted/guard outcomes are not threshold-fragile in this comparison.

## Recommended disposition

### Numeric evidence

`SUPPORTS NUMERICALLY_EQUIVALENT`

Rationale:

1. All array shapes are identical.
2. All arrays are finite; no NaN or infinity is present.
3. Outcome, step count, crossing step, crossing cell, crossing position, and failure reason are exact for all three cases.
4. The difference seed exists in the initial CoolProp-backed thermodynamic state before time integration.
5. State, pressure, time, and inventory differences remain extremely small and do not alter any discrete event.
6. Integrated inventory differences fit the existing absolute budget tolerances.

### Gate status

`Gate_3_disposition = INVESTIGATION_REQUIRED` should remain temporarily until the aligned Python 3.12 environment completes the full repository suite and the comparison contract is formally recorded. After those two items, the recommended final disposition is:

`Gate_3_disposition = NUMERICALLY_EQUIVALENT`

Gate 4 must remain paused until that formal closure is complete.

## Approval boundary

```text
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
near_saturation_acoustic_continuity_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
