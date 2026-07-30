# Stage 7 Gate 7 Boundary-Adjacent Phase-Chatter Diagnosis Plan

## Status

`CONTRACT LOCKED BEFORE FOCUSED DIAGNOSTIC EXECUTION; VERIFICATION ONLY`

This plan implements Issue #100 after Gate 6 execution closeout. It diagnoses the
49 region changes observed in cell 30 without changing or suppressing them.

## Fixed baseline

```text
case:                              pipeline_crossing_candidate_p5m5_to_p2m5
cells / CFL:                       32 / 0.10
post-crossing horizon:             +64 accepted steps
first crossing step / cell:        125 / 29
first crossing time:               7.999325695335248e-4 s
Gate 6 final accepted-state SHA:    62bbaf5d7014af258180fe29622324a2228a0c5eec507ef10eb6b9f3e411d440
expected cell-30 region changes:    49
```

## Fixed diagnostic targets

```text
cell 29:          stable open-two-phase comparison
cell 30:          chatter target
cell 31:          boundary-adjacent liquid comparison
interfaces:       29|30 / 30|31 / right external boundary
comparison rule:  event step versus immediately preceding accepted step
```

No additional cell, time window, smoothing rule, or event subset may replace the
fixed targets after results.

## Recorded cell stages

For every successful post-crossing step and each fixed cell:

1. pre-step accepted state;
2. raw post-FVM state before quality projection;
3. post-projection accepted state.

The record includes conservative and primitive states, direct phase information,
quality, void fraction, projection activity, full acoustic derivative evidence,
and two saturated-liquid margin coordinates:

```text
delta_e = e - e_sat_liquid(p)
delta_v = 1/rho - 1/rho_sat_liquid(p)
```

## Recorded interfaces

The exact pre-step first-order states and Rusanov flux are retained at:

```text
cell 29 | cell 30
cell 30 | cell 31
cell 31 | prescribed right-boundary ghost
```

Mass, momentum, total-energy, and vapor-component fluxes are stored with the
local left/right wave-speed estimates and right-boundary requested state.

## Event-aligned comparison

Each accepted cell-30 region change is compared only with the immediately
preceding accepted step. The event record retains:

- sign changes in `delta_e` and `delta_v`;
- sound-speed branch switching;
- changes in the fixed interface-flux divergence;
- projection activity;
- boundary-pressure and `dt` changes;
- simultaneous region changes in cells 29 and 31.

## Predeclared correlation rule

A correlation label requires the relevant event-aligned condition on at least
`90%` of the fixed 49 events. This threshold is locked in source and tests before
execution. It is a screening convention, not a statistical confidence claim.

Permitted labels:

```text
PHASE_MARGIN_OSCILLATION_CORRELATED
BOUNDARY_FORCING_CORRELATED
ACOUSTIC_BRANCH_SWITCH_CORRELATED
INTERFACE_FLUX_OSCILLATION_CORRELATED
PROJECTION_ACTIVITY_CORRELATED
STABLE_FRONT_SEPARATED_FROM_CHATTER
MULTI_FACTOR_CHATTER
CHATTER_REVIEW_INCONCLUSIVE
```

`CHATTER_REVIEW_INCONCLUSIVE` remains because correlation and ordering do not
establish root cause.

## Added files

```text
src/liquid_gas_transient/hem_pipeline_phase_chatter_diagnosis.py
tests/test_stage7_lco2_hem_pipeline_phase_chatter_diagnosis.py
.github/workflows/stage7-phase-chatter-diagnosis.yml
docs/verification/stage7_gate7_phase_chatter_diagnosis_plan.md
```

## Required artifacts

```text
summary.json
cell_29_30_31_history.csv
cell_30_transition_events.csv
interface_flux_history.csv
saturation_margin_history.csv
report.md
phase_margin_sound_speed.png
interface_flux_boundary_pressure.png
projection_quality.png
artifact_sha256.txt
JUnit XML
runtime / Git provenance
```

## Approval boundary

```text
Gate_7_execution_complete = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
post_crossing_propagation_approved = false
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
CFL_independent_crossing_verified = false
mesh_independent_crossing_verified = false
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

No production solver, flux, boundary, phase classifier, acoustic formula,
threshold, projection, property model, hysteresis, or chatter suppression
change is authorized.
