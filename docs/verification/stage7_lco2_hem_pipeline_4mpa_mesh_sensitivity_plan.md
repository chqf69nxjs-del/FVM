# Stage 7 — LCO2 HEM Pipeline 4 MPa Mesh-Sensitivity Gate Plan

## Status

`NEXT GATE SPECIFICATION; DOCUMENTATION ONLY; VERIFICATION ONLY`

## Objective

Determine whether the fixed PR #77 5→4 MPa subthreshold raw crossing is stable,
decaying, disappearing, or non-convergent under spatial refinement while holding the
reviewed time-step policy and physical/numerical model fixed.

The primary question is not whether a chosen mesh can be made to produce a preferred
answer. The question is how the already-observed first-order result changes under the
predeclared 32/64/128-cell matrix.

Passing this gate as a completed sensitivity study does not pass Gate P2, validate physical
nucleation, approve the two-phase acoustic closure, or authorize design use.

## Immutable reference

The 32-cell row must first reproduce the merged PR #77 observation exactly:

```text
case ID:                     pipeline_liquid_control_p5m5_to_p4m5
formal outcome:              GUARD_FAILURE
crossing step:               313
crossing time:               1.996923102525957e-3 s
crossing cell:               25
outlet distance:             0.203125 m
maximum q_eq:                9.672588429198319e-9
final-state SHA256:          7e8b6a6bc715755e0419d8a469140c02a79ec5e8bb419eb4868553c3228242e1
run-signature SHA256:        fdd25cbf669428790d1f3d877ab3b86ec329726d7b10e3a8461443ba6340b202
```

The diagnostic findings merged in PR #79 remain a separate baseline and are not
reclassified by this gate.

## Reviewed mesh-only override

The merged PR #77 configuration remains immutable and continues to reject a changed cell
count. This gate shall not weaken or mutate that contract.

A separate verification-only mesh-sensitivity configuration/harness shall be introduced.
It may vary only the following reviewed fields:

```text
n_cells:       one of {32, 64, 128}
dx:            derived exactly as L / n_cells
maximum_steps: derived deterministically as 2000 * n_cells / 32
```

Thus the fixed step caps are:

```text
32 cells:   2000 steps
64 cells:   4000 steps
128 cells:  8000 steps
```

The linear step-cap scaling prevents a refined no-crossing run from ending before the same
physical horizon merely because `dt` scales with `dx`. It is a predeclared computational
capacity rule, not a result-dependent horizon extension.

Every other field must match the merged PR #77 contract exactly. The generated artifact
shall record both the immutable PR #77 base contract and the explicit mesh-only override.

## Fixed model and solver settings

```text
pipe length / diameter:        1.0 m / 0.10 m
initial state:                 5 MPa / 5 K subcooling, u=0, q=0
left boundary:                 ReflectiveBoundary
right boundary:                prescribed subcooled outlet_only boundary
spatial flux:                  existing first-order Rusanov
CFL:                           0.10
n_ghost:                       2
ramp duration policy:          one initial acoustic time
maximum horizon policy:        three initial acoustic times
crossing evidence threshold:   q_eq >= 1.0e-6
phase/projection configs:       exact merged PR #77 values
accepted-state EOS:             exact merged PR #77 value
budget tolerances:              exact merged PR #77 values
friction / heat / gravity:      none / none / none
internal interfaces:            none
```

No limiter, MUSCL reconstruction, higher-order time integration, boundary replacement,
source term, or HNE/metastability model is included.

## Fixed mesh matrix

```text
32 cells:   dx = 0.03125 m
64 cells:   dx = 0.015625 m
128 cells:  dx = 0.0078125 m
```

The fixed 5→4 MPa case is the primary diagnostic. The 5→2 and 5→3 MPa cases shall also be
run at all three meshes as positive crossing controls, producing a total matrix of nine
runs.

```text
final boundary pressures:  2 MPa, 3 MPa, 4 MPa
meshes:                     32, 64, 128 cells
CFL:                        0.10 for every run
matrix size:                9 runs
```

The existing 65-point prescribed-boundary preflight shall be run for each pressure schedule
before the mesh matrix. The boundary path is not allowed to change with mesh.

## Time and position comparison

Cell indices are not comparable across meshes. The following physical and normalized
quantities shall be retained:

```text
physical crossing time [s]
normalized crossing time t / t_acoustic,0
cell-center position [m]
distance from outlet [m]
normalized outlet distance / L
```

The initial acoustic-time definition and pressure-ramp schedule shall remain identical in
physical meaning across meshes.

## Required per-run outputs

For each of the nine runs retain:

```text
formal outcome and failure reason
step count, configured maximum steps, and final time
crossing step and time, if any
crossing cell and physical position, if any
maximum raw crossing q_eq
maximum projected q
maximum void fraction
Delta_u_sat and Delta_v_sat at first raw crossing
quality from internal energy and specific volume
accepted-liquid sound speed immediately before crossing
raw sound-speed candidate at crossing
projection vapor source
boundary vapor transport
mass, momentum, energy, and combined-vapor residuals
reverse-flow fallback count
final-state SHA256
run-signature SHA256
```

If no crossing occurs within the fixed horizon, retain the minimum liquid-side saturation
margins and the cell/time where those minima occur.

## Cross-mesh analysis

The analysis shall compare the 4 MPa sequence without assuming a formal convergence order
at a phase-boundary event.

Required comparisons:

```text
outcome sequence across 32/64/128 cells
maximum q_eq versus dx
Delta_u_sat versus dx
Delta_v_sat versus dx
normalized crossing time versus dx
normalized crossing position versus dx
projection vapor source versus dx
sound-speed jump versus dx
```

Simple pairwise ratios and differences may be reported. Richardson extrapolation or an
observed-order claim is allowed only if the data are smooth, sign-consistent, and the
assumptions are explicitly documented. A three-point phase-event sequence alone is not an
accuracy band.

## Diagnostic classifications

The 4 MPa mesh result shall retain one or more of the following reviewed labels:

```text
CROSSING_VANISHES_WITH_REFINEMENT
CROSSING_DEPTH_DECAYS_WITH_REFINEMENT
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
CROSSING_TIME_POSITION_NOT_STABLE
MESH_SEQUENCE_NON_MONOTONE
MESH_SENSITIVITY_INCONCLUSIVE
```

Definitions:

- `CROSSING_VANISHES_WITH_REFINEMENT`: a raw crossing occurs on a coarser mesh but the
  128-cell run remains liquid through the fixed horizon.
- `CROSSING_DEPTH_DECAYS_WITH_REFINEMENT`: the two-phase-side depth measured by `q_eq`,
  `Delta_u_sat`, and `Delta_v_sat` decreases consistently with refinement, without claiming
  a zero limit from three points alone.
- `FINITE_CROSSING_PERSISTS_ACROSS_MESHES`: all three meshes cross and the 64/128 values do
  not show a clear decay toward zero under the reviewed metrics.
- `CROSSING_TIME_POSITION_TREND_STABLE`: the 64/128 physical time and position differences
  are smaller than the 32/64 differences for the declared comparison metrics.
- `CROSSING_TIME_POSITION_NOT_STABLE`: time or position does not show that trend.
- `MESH_SEQUENCE_NON_MONOTONE`: one or more principal crossing-depth metrics reverse trend.
- `MESH_SENSITIVITY_INCONCLUSIVE`: backend, guard, budget, or unsupported-state outcomes
  prevent a complete comparison.

Multiple labels may apply. None is a production phase-switch rule.

## Positive-control requirements

The 2 MPa and 3 MPa cases are not used to tune the 4 MPa conclusion. They verify that the
refined runner still exercises the established boundary-driven crossing path.

For each positive-control case:

```text
boundary preflight accepted
no reverse-flow fallback
no endpoint or forbidden transition
crossing/projection cell sets agree
post-projection accepted-state EOS succeeds
second projection is a no-op
budgets close under fixed tolerances
```

A change in formal outcome relative to the 32-cell baseline must be retained and reviewed;
it must not be hidden by changing the horizon, threshold, or schedule.

## Acceptance criteria for the mesh-sensitivity gate

The gate passes as a completed software sensitivity study when:

```text
32-cell PR #77 baseline reproduces exactly
only n_cells, derived dx, and deterministic maximum_steps vary
all nine fixed runs produce explicit outcomes
all boundary preflights complete successfully
all mesh-specific histories and physical positions are retained
all applicable budgets close
no fixed model, schedule, CFL, or tolerance is changed
cross-mesh classifications are generated from the retained data
frozen PR #72 Case A/B remain exact
PR #77 and PR #79 regressions remain exact
full repository tests pass with no authoritative skips
```

Passing this gate means only that the mesh dependence has been characterized under the
fixed first-order model.

## Required artifacts

```text
4mpa_mesh_sensitivity_summary.json
4mpa_mesh_sensitivity_cases.csv
4mpa_mesh_sensitivity_steps.csv
4mpa_mesh_sensitivity_cells.csv
4mpa_mesh_sensitivity_crossing_metrics.csv
4mpa_mesh_sensitivity.md
4mpa_mesh_sensitivity.npz
mesh_qeq_vs_dx.png
mesh_saturation_margin_vs_dx.png
mesh_crossing_time_position.png
mesh_sound_speed_jump.png
```

The JSON summary must contain the complete effective configuration, the mesh-only override,
exact Git provenance, CoolProp version, per-run state/signature hashes, and approval
boundary.

## Explicit exclusions

```text
CFL variation
MUSCL/TVD or limiter comparison
SSP-RK2 connection
boundary-model replacement
pressure-schedule exploration
accepted-crossing threshold change
friction, wall heat transfer, or gravity
post-crossing region-growth approval
HNE or metastability model
physical Validation
design-use acceptance
production HEM activation
```

## Approval boundary

```text
verification_only = true
software_sensitivity_only = true
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
two_phase_acoustic_accuracy_band_approved = false
mesh_independent_crossing_verified = false until reviewed evidence supports a narrower claim
CFL_independent_crossing_verified = false
post_crossing_propagation_approved = false
```

## Follow-on decisions

After this gate is implemented and reviewed:

1. perform CFL sensitivity without changing the selected mesh comparison baseline;
2. perform near-saturation acoustic-continuity diagnostics before post-crossing propagation;
3. compare boundary closures only after mesh and CFL effects are separated;
4. evaluate MUSCL/TVD using the existing PR #52/#53 assets only after the first-order
   sensitivity result is frozen;
5. consider HNE/metastability and physical Validation as separate physical-model gates.
