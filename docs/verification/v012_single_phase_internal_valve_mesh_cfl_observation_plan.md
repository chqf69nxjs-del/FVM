# V-012 Single-Phase Internal-Valve Mesh/CFL Observation Plan

## 1. Status

`PLANNED; IMPLEMENTATION READY`

This document fixes the observation plan that follows the merged V-012A through
V-012D baseline cases. It does not define formal regression bands, physical
Validation criteria, a design mesh, or design-use acceptance.

## 2. Purpose

The purpose is to determine how the existing single-phase internal-valve numerical
observations change with spatial resolution and explicit time-step size before
selecting a low-cost CI-light profile and broad software-regression bands.

The observation shall answer:

- whether finite-opening valve flow and actual interface flux remain mutually
  consistent across the planned mesh/CFL cases;
- whether opening- and closing-generated wave direction, timing, and amplitude
  remain qualitatively and numerically stable;
- whether complete closure continues to produce hydraulic separation and numerical
  zero through mass, energy, and vapor-mass flux;
- whether global budgets, positivity, and single-phase state remain healthy;
- how runtime and step count scale for the candidate CI-light and observation
  meshes.

## 3. Guardrails

Persistent constraints:

- software / numerical verification only;
- physical Validation is not performed;
- design-use acceptance is not performed;
- `property_backend_design_status = not_approved_for_design_use`;
- the Kv relation remains a single-phase liquid relation;
- fixed-pressure boundaries remain zero-impedance numerical idealizations;
- the hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`;
- opening schedules remain prescribed operations rather than actuator-dynamics or
  hysteresis models;
- the finest mesh is a comparison reference, not an exact solution;
- lower CFL is not truth and is not automatically superior;
- no regression band is selected or relaxed before the observation evidence is
  reviewed.

No governing equation, EOS path, Kv law, Mach cap, interface-energy treatment, or
boundary meaning may be changed in this observation item. If such a change appears
necessary, save the branch and stop for a separate physics decision.

## 4. Case roles

| Case | Existing baseline | Role in mesh/CFL observation |
|---|---|---|
| V-012A | uniform state, opening `0.5`, zero pressure difference | low-cost preservation sentinel only |
| V-012B | constant opening `0.5`, `1 kPa` driven flow | finite-opening flow and interface-consistency trend |
| V-012C | opening `0 -> 1` | opening-wave timing, direction, amplitude, and flow-growth trend |
| V-012D | closing `1 -> 0` through complete closure | closing-wave trend and closed-state zero-through-flux trend |

V-012A is deliberately not used as a full dynamic mesh sweep. Its expected signal
is exact or roundoff-scale preservation, so one coarse sentinel is sufficient to
protect the no-spurious-flow path while keeping the observation cost focused on
V-012B/C/D.

## 5. Fixed run matrix

### 5.1 Dynamic cases V-012B/C/D

For each of V-012B, V-012C, and V-012D, execute four unique runs:

| Comparison group | Cells | CFL |
|---|---:|---:|
| mesh | `50` | `0.5` |
| mesh and CFL shared baseline | `100` | `0.5` |
| mesh | `200` | `0.5` |
| CFL | `100` | `0.25` |

The shared `n=100`, `CFL=0.5` run is executed once per physical case and reused in
both the mesh and CFL comparisons.

### 5.2 V-012A sentinel

Execute one low-cost sentinel:

| Cells | CFL | Purpose |
|---:|---:|---|
| `50` | `0.5` | uniform-state preservation and zero-flow telemetry |

### 5.3 Total planned executions

```text
V-012A sentinel: 1
V-012B dynamic:  4
V-012C dynamic:  4
V-012D dynamic:  4
unique total:   13
```

A `400`-cell run is not part of the initial plan. It may be added only when the
`50 / 100 / 200` observation leaves a primary timing, phase, amplitude, flow, or
closure trend materially unclear. The reason for adding or rejecting it shall be
recorded explicitly.

## 6. Stable identifiers and directory layout

Each numerical execution requires a collision-free case identifier containing the
verification case, cell count, and round-trip-safe CFL token, for example:

```text
v012b_n0050_cfl0p5
v012c_n0100_cfl0p25
v012d_n0200_cfl0p5
```

Planned top-level output:

```text
verification/internal_valve_mesh_cfl_sweep/
```

Planned aggregate artifacts:

```text
v012_internal_valve_mesh_cfl_sweep_config.json
v012_internal_valve_mesh_cfl_sweep_metrics.json
v012_internal_valve_mesh_cfl_sweep_summary.csv
v012_internal_valve_mesh_cfl_sweep_report.md
```

Per-run numerical artifacts remain inside their case directory. The sweep shall
reuse the existing V-012A/B/C/D runners rather than reproduce solver logic.

## 7. Required aggregate summary fields

### 7.1 Identity and execution

Every summary row shall include:

- case ID and verification item;
- comparison groups;
- `n_cells`, `dx_m`, and `cfl`;
- execution pass and analysis-complete flags;
- step count and runtime;
- exact property backend name and CoolProp version;
- design status;
- positivity and single-phase flags;
- missing-budget-field list.

All rows shall agree on backend identity, CoolProp version, and design status.

### 7.2 Common conservation and interface fields

For every relevant case record:

- mass, energy, and vapor-mass budget relative residuals;
- maximum mass, energy, and vapor-mass two-sided interface mismatch;
- maximum flux-derived Q minus applied Q;
- maximum raw/applied and applied/flux relative difference where the reference is
  finite;
- flow-sign consistency;
- Mach-cap activation count and maximum applied face Mach.

Relative flow comparisons shall not be used when both reference quantities are
numerical zero. Zero-opening and complete-closure states use explicit absolute Q
and through-flux tolerances instead.

### 7.3 V-012A sentinel fields

Record:

- maximum requested/actual opening error;
- maximum raw, applied, and flux-derived Q magnitude;
- maximum pressure and velocity disturbance;
- hydraulic-separation fraction;
- all required budget and state-health fields.

The V-012A row is a preservation sentinel and is excluded from dynamic convergence
classification.

### 7.4 V-012B finite-opening fields

Record:

- initial, maximum, and final applied Q;
- representative valve pressure difference;
- near-probe pressure and velocity extrema;
- dominant characteristic direction and opposite-direction leakage;
- characteristic-peak timing relative to the theoretical acoustic arrival;
- interface consistency and budget fields.

### 7.5 V-012C opening-ramp fields

Record:

- opening monotonicity and maximum schedule error;
- initial, maximum, and final applied Q;
- upstream decompression and downstream compression flags;
- dominant characteristic increment, opposite-direction leakage, and peak time at
  the near probes;
- observed-minus-theoretical characteristic-peak time offset;
- maximum pressure and velocity disturbance;
- interface consistency and budget fields.

### 7.6 V-012D closing-ramp fields

Record:

- opening monotonicity and maximum schedule error;
- initial, minimum finite-opening, and final applied Q;
- upstream compression and downstream decompression flags;
- pre-arrival-rebased dominant characteristic increment, leakage, and peak time at
  the near probes;
- observed-minus-theoretical closure-wave peak time offset;
- post-closure sample count;
- hydraulic-separation and no-flow-direction fractions;
- maximum post-closure raw, applied, and flux-derived Q;
- maximum post-closure mass, energy, and vapor-mass through-flux;
- finite-opening momentum residual separately from closed-wall momentum-reaction
  diagnostics;
- interface consistency and budget fields.

The finite-opening momentum relation shall never be applied to complete-closure
rows.

## 8. Observation and classification rules

### 8.1 Mesh comparison

At `CFL=0.5`, order the `n=50 / 100 / 200` rows from coarse to fine and report the
raw values and normalized differences for each primary metric.

Classification labels may include:

- `monotonic_improvement`;
- `improved_but_non_monotonic`;
- `mixed_behavior`;
- `no_clear_improvement`;
- `near_numerical_floor`;
- `insufficient_data`.

A classification is an observation summary, not an acceptance threshold or formal
order-of-accuracy claim.

### 8.2 CFL comparison

At `n=100`, compare `CFL=0.25` with `CFL=0.5` and report:

- metric differences;
- runtime and step-count ratio;
- whether either result appears closer to the mesh trend;
- whether a metric is already near a numerical floor.

The lower-CFL result is not labelled as truth.

### 8.3 Primary trend groups

The aggregate report shall group conclusions under:

1. finite-opening flow and interface consistency;
2. opening-wave direction, timing, and amplitude;
3. closing-wave direction, timing, and amplitude;
4. complete-closure hydraulic separation and zero through-flux;
5. global budgets, state health, and runtime.

## 9. Planned comparison figures

Generate aggregate plots from saved summary artifacts without rerunning the solver.
Recommended figures are:

- applied-Q metric versus `dx` for V-012B/C/D;
- characteristic timing offset versus `dx` for V-012B/C/D;
- characteristic amplitude or leakage versus `dx` for V-012C/D;
- complete-closure Q and through-flux magnitude versus `dx` for V-012D;
- budget residual magnitude versus `dx`;
- `CFL=0.25 / 0.5` metric and runtime comparison at `n=100`;
- per-case execution time versus cell count.

Exact zeros shall be labelled explicitly and plotted at a documented visualization
floor only for readability.

## 10. Implementation sequence

1. implement the de-duplicated run-plan and stable case-ID helpers;
2. implement per-case metric extractors using existing numerical artifacts;
3. add a one-case injected-runner mini test that produces one summary row without
   requiring the full 13-run sweep;
4. add pure tests for plan uniqueness, comparison-group assignment, missing fields,
   backend-identity consistency, and zero-reference handling;
5. execute the 13 planned CoolProp runs;
6. review aggregate CSV/JSON/report and comparison plots;
7. document the `400`-cell decision;
8. only after observation review, propose CI-light bands and a permanent workflow.

## 11. Stop conditions

Stop, preserve the branch, and report if:

- any existing baseline runner must change its solver physics to participate;
- a run becomes non-finite, non-positive, or unexpectedly two phase;
- required actual two-sided interface flux or budget fields are unavailable;
- the accepted observation window is contaminated by an external-boundary return;
- case identifiers collide or one numerical execution is unintentionally repeated;
- backend identity or CoolProp version differs between rows;
- a regression or acceptance band would need to be chosen before the observation is
  complete;
- complete closure cannot be evaluated with explicit absolute zero-flow gates.

## 12. Observation-PR completion criteria

The mesh/CFL observation increment is ready for review when:

- the 13-run plan is executed or an explicitly documented stop condition is reached;
- every planned row is traceable to its per-run config and metrics artifact;
- aggregate config, metrics, summary CSV, report, and comparison plots exist;
- all runs remain single phase and satisfy their existing software-observation gate;
- mesh and CFL trends are described without treating the finest mesh or lower CFL as
  truth;
- the `400`-cell decision is recorded;
- focused, installed-CoolProp, and full repository tests pass;
- MASTER VERIFICATION INDEX and Stage 6 logs are synchronized.

After this observation PR, a separate formalization increment shall define CI-light
bands, add the permanent GitHub Actions regression, generate the formal V-012 report
and SHA256 manifest, and decide whether V-012 can move to `COMPLETE`.
