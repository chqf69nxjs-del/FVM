# Stage 7 Current Gate Snapshot

## Status — 2026-08-04

```text
Stage 1–6:                              COMPLETE
Stage 7:                                IN_PROGRESS
recorded substantive main:              5f0099101cbc9e9694297394a4c424904260ba94
Gate 3 cross-runtime checkpoint:        NUMERICALLY_EQUIVALENT
Gate 4 low-CFL execution:               CFL_SENSITIVITY_OBSERVED
Gate 5 acoustic execution:              COMPLETE; approval withheld
Gate 6 propagation execution:           COMPLETE; approval withheld
Gate 7 chatter diagnosis:               COMPLETE; root cause unapproved
Gate 8 three-CFL execution:             COMPLETE
Gate 9 D0-D6 diagnosis:                 COMPLETE; PR #122; Issue #110 CLOSED
crossing-depth CFL sensitivity:          CHARACTERIZED
crossing-depth root cause:               NOT APPROVED
Application Track A1:                   COMPLETE
selected first pilot:                   U3 pipeline depressurization / blowdown
active primary implementation:          Issue #109 U3 B0 discharge benchmark
active documentation track:             Issue #114 technical report
physical validation:                    NOT ESTABLISHED
design-use acceptance:                  NOT ESTABLISHED
production HEM activation:              NOT APPROVED
```

Detailed historical evidence remains in the gate closeout records, execution log, and master verification index. Gate 9 is summarized in [`stage7_gate9_closeout.md`](stage7_gate9_closeout.md).

## Project-level current conclusion

The first-order pure-CO2 HEM verification path now supports:

- direct liquid-to-open-two-phase crossing from an all-liquid initial state;
- equilibrium-quality projection and accepted mixed-state recovery;
- exact second-projection no-op behavior;
- fixed mesh and CFL sensitivity evidence;
- an independent near-saturation acoustic map;
- one fixed 64-step post-crossing continuation;
- conservative and vapor-budget closure in retained successful states;
- event-aligned diagnosis of localized boundary-adjacent phase chatter;
- full three-CFL event integration and temporal / correlation classification.

The evidence also establishes the following limitations:

- crossing depth is CFL-sensitive and non-monotone;
- accepted / guard classification changes across the fixed CFL sequence;
- candidate time and position remain stable, but crossing depth does not converge monotonically;
- raw thermodynamic crossing precedes quality projection;
- the fixed threshold discretizes a continuous crossing-depth difference;
- candidate `dt`, Rusanov dissipation, boundary net flux, and acoustic branch do not individually explain the complete depth ordering;
- strict near-saturation acoustic continuity, chatter root cause, physical phase-front speed, mesh / CFL independence, physical validation, and design use remain unapproved.

## Gate 9 authoritative closeout

```text
D5 PR / source head:                   #121 / 45894a3fbe8c176c8435517c6204d94359dccccc
D5 workflow / artifact:                30805641241 / 8855725551
D5 artifact ZIP SHA256:                6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850

D6 PR / source head:                   #122 / b90aa04ca3e1d8f2958f6a700c4ae73917ce39c8
D6 main merge SHA:                     5f0099101cbc9e9694297394a4c424904260ba94
D6 workflow / artifact:                30860513453 / 8875962770
D6 artifact ZIP SHA256:                b0c4b490eedeb7332659051d13cc1e108ef08dfd381eec9fbf63773c4e4aa088
D6 dedicated / related / full:         6 / 52 / 903 passed
skips / failures / errors:             0 / 0 / 0
```

Assigned D6 labels:

```text
CANDIDATE_TIME_POSITION_STABLE_ACROSS_CFL
CROSSING_DEPTH_CFL_SENSITIVE
CROSSING_DEPTH_SEQUENCE_NON_MONOTONE
SATURATION_MARGIN_DISPLACEMENT_CORRELATED
PROJECTION_ACTIVITY_POSTDATES_RAW_CROSSING
THRESHOLD_CLASSIFICATION_DISCONTINUITY_OBSERVED
CROSSING_DEPTH_REVIEW_INCONCLUSIVE
```

Not assigned:

```text
CANDIDATE_STEP_OVERSHOOT_CORRELATED
RUSANOV_DISSIPATION_CORRELATED
BOUNDARY_FLUX_IMBALANCE_CORRELATED
ACOUSTIC_BRANCH_SELECTION_CORRELATED
MULTI_FACTOR_CROSSING_DEPTH
```

```text
D6_temporal_correlation_classification_complete = true
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true
crossing_depth_root_cause_approved = false
```

## Active next controlled work — U3 B0

Issue #109 implements the first independently benchmarkable physical-discharge component: the subcooled-liquid orifice limit.

```text
Delta_p  = p0 - pb
Aeff     = Aref * f_open
m_dot    = Cd * Aeff * sqrt(2 * rho0 * Delta_p)
E_dot    = m_dot * h0
```

Required benchmark families:

```text
B0-01 CLOSED_ELEMENT
B0-02 ZERO_PRESSURE_DROP
B0-03 SUBCOOLED_LIQUID_LIMIT
B0-04 AREA_SCALING
B0-05 DISCHARGE_COEFFICIENT_SCALING
G-01 REVERSE_PRESSURE_NOT_SUPPORTED
G-02 INPUT_OR_PROPERTY_FAILURE
G-03 SINGLE_PHASE_SCOPE_FAILURE
```

B0 remains component-only and verification-only. B1 choking, two-phase critical discharge, pipe coupling, receiver dynamics, physical validation, design use, and production activation remain out of scope.

## Parallel documentation track

Issue #114 retains the controlled technical-report structure. It must now be updated from its pre-Gate-9 scope to include:

- Gate 9 execution and closeout;
- the final CFL sensitivity disposition;
- explicit root-cause and approval boundaries;
- U3 B0 as the active next implementation track.

## Approval boundary

```text
application_specification_complete = true
real_problem_pilot_selected = true
Gate_8_execution_complete = true
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true

crossing_depth_root_cause_approved = false
CFL_independent_crossing_verified = false
mesh_independent_crossing_verified = false
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
physical_discharge_boundary_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
