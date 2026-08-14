# Stage 7 P1 — Pressure-to-Phase Relationship and Operator Visualization — Increment A1

## 1. Status and claim boundary

This document defines the successor increment to:

- `stage7_p1_post_crossing_analysis_slice_increment_a0.md`
- the fixed Stage 7 Gate 6 post-crossing continuation

Increment A1 adds a non-invasive relationship-analysis and visualization layer for the fixed HEM case. It answers the bounded engineering-analysis questions:

1. when does the inherited pressure-drop signal reach each cell;
2. when does that same cell first enter accepted `OPEN_TWO_PHASE`;
3. when, if ever, does it enter `OPEN_TWO_PHASE` and remain there through the observed horizon;
4. how large is the pressure-arrival-to-phase-onset lag `Δt(x)`;
5. how do discrete pressure-front and phase-front advancement slopes compare with the local retained equilibrium sound speed;
6. how sensitive the pressure-arrival record is to a predeclared one-decade threshold envelope.

Current formal boundary:

```text
IMPLEMENTED:                true after merge of this increment
WORKING VERTICAL SLICE:     false until an authoritative workflow passes and review promotes it
VERIFIED:                   false
ACCEPTED:                   false
PHYSICALLY VALIDATED:       false
DESIGN-USE ACCEPTED:        false
PRODUCTION APPROVED:        false
```

`RELATIONSHIP_READY` is an execution status for this bounded output contract. It is not physical Validation or design approval.

## 2. Existing authority reused

A1 does not create a second physical solve or redefine A0.

| Existing asset | Authority retained | A1 reuse |
|---|---|---|
| `hem_pipeline_depressurization_first_crossing.py` | fixed pre-crossing pressure history, first pressure-arrival records, and first accepted crossing | complete accepted pre-crossing/crossing history is consumed unchanged |
| `hem_pipeline_post_crossing_propagation.py` | fixed 64-step Gate 6 continuation, cell regions, sound speeds, transitions, budgets, and state hashes | post-crossing cell history is consumed unchanged |
| `hem_pipeline_post_crossing_analysis.py` | A0 pressure-front / phase-front output contract and fail-closed status | A1 requires an `ANALYSIS_READY` A0 result and binds its analysis SHA-256 |
| `stage7_gate6_closeout.md` | persistence, upstream propagation, and localized cell-30 toggle observations | A1 quantifies first and persistent onset without assigning physical root cause |

No production solver, EOS, boundary, flux, phase classifier, quality projection, mesh, CFL, threshold, or tolerance is changed.

## 3. Fixed scope

The inherited physical case remains exactly:

```text
fluid / backend:                 pure CO2 / CoolProp 8.0.0
model:                           HEM_EQUILIBRIUM
pipe length / diameter:          1.0 m / 0.10 m
cells / dx:                      32 / 0.03125 m
CFL:                             0.10
initial state:                   5 MPa / 5 K subcooling / u=0 / q=0
outlet schedule:                 prescribed reduction to 2 MPa
first crossing:                  existing exact accepted crossing
post-crossing horizon:           fixed 64 accepted steps
friction / wall heat / gravity:  none / none / none
```

A1 is postprocessing only. It may fail closed when inherited histories are incomplete, nonfinite, non-monotone, or inconsistent with the retained A0/Gate 6 records.

## 4. Relationship definitions

### 4.1 Reference pressure arrival

The reference pressure-arrival criterion remains the existing A0/Gate 6 evidence condition:

```text
(p_initial - p_cell) / p_initial >= 1e-6
```

For cells reached before or at first crossing, the A1 result must reproduce the already-retained first-arrival time exactly. For cells not reached by first crossing, A1 may extend the same unchanged criterion through the fixed post-crossing history.

### 4.2 First accepted phase onset

For each cell:

```text
first phase onset
= first accepted history state with post_region == OPEN_TWO_PHASE
```

Transported quality alone is not used as a phase classifier.

### 4.3 Persistent accepted phase onset

For each cell:

```text
persistent phase onset
= earliest accepted OPEN_TWO_PHASE state after which every retained state
  through the fixed horizon also remains OPEN_TWO_PHASE, with at least two
  retained accepted samples from onset through the horizon
```

This separates a stable upstream phase-front observation from a locally toggling cell and prevents a last-sample-only opening from being called persistent. A cell may therefore have a first onset but no persistent onset within the bounded horizon.

### 4.4 Cellwise lag

```text
Δt_first(x)      = t_first_phase(x)      - t_pressure(x)
Δt_persistent(x) = t_persistent_phase(x) - t_pressure(x)
```

A negative lag beyond the fixed numerical comparison tolerance fails closed because it would mean accepted phase onset is recorded before the inherited pressure-arrival criterion at the same cell.

These lags are model-output relationships. In HEM they are not measurements of physical nucleation delay because HEM assumes instantaneous local equilibrium.

### 4.5 Phase-toggle counts

A1 counts accepted-state changes for every cell:

```text
LIQUID_CANDIDATE -> OPEN_TWO_PHASE
OPEN_TWO_PHASE   -> LIQUID_CANDIDATE
```

A cell is flagged as toggling when it opens more than once or closes at least once. This records event history only and does not assign root cause.

### 4.6 Discrete front advancement slopes

For each newly furthest-upstream cell-center event:

```text
v_segment = Δ(distance from outlet) / Δt
```

Separate records are produced for:

- the reference pressure front;
- the accepted phase front.

Each segment is paired with the destination cell's retained equilibrium sound speed and reports:

```text
v_segment / c_local
```

These are discrete event slopes on a coarse first-order mesh. They are not approved physical wave speeds or boiling-front velocities.

## 5. Predeclared pressure-threshold sensitivity

A1 evaluates exactly three multipliers around the inherited reference threshold:

```text
0.1 x reference = 1e-7
1.0 x reference = 1e-6
10  x reference = 1e-5
```

This is a fixed one-decade diagnostic envelope. It is not threshold tuning or calibration.

For each cell and threshold A1 reports:

- first arrival time;
- whether it is available within the retained history;
- pre-/crossing/post-crossing source segment;
- time shift from the unchanged `1e-6` reference arrival.

Required ordering:

```text
t_arrival(1e-7) <= t_arrival(1e-6) <= t_arrival(1e-5)
```

for all available arrivals.

## 6. Exact output contract

A1 writes exactly eight files:

1. `relationship_summary.json`
2. `cell_lag.csv`
3. `front_speed.csv`
4. `threshold_sensitivity.csv`
5. `front_relationship.png`
6. `cell_phase_lag.png`
7. `operator_report.md`
8. `relationship_manifest.json`

The two plots must be generated from the retained A1 tables and must not rerun or alter the physical calculation.

The manifest records:

- exact declared filenames and count;
- SHA-256 and byte size for every non-manifest payload;
- inherited A0 analysis SHA-256;
- inherited Gate 6 last-valid-state SHA-256;
- A1 relationship SHA-256;
- model identifier;
- execution status;
- explicit maturity flags.

## 7. PASS / FAIL gates

A1 returns `RELATIONSHIP_READY` only when all required gates pass.

| Gate | PASS condition |
|---|---|
| A0 source | inherited A0 result is `ANALYSIS_READY` |
| Fixed source | all 64 Gate 6 post-crossing steps completed |
| Combined history | initial, pre-crossing, crossing, and post-crossing histories are complete and strictly time ordered |
| Reference arrival identity | every pre-crossing `1e-6` arrival retained by the baseline matches the combined-history result exactly |
| Temporal ordering | no accepted first or persistent phase onset precedes the reference pressure arrival in the same cell |
| Threshold ordering | higher predeclared pressure-drop thresholds never arrive earlier than lower thresholds |
| Discrete speed records | pressure and phase advancement records are present, finite, and positive |
| Relationship values | every available arrival, onset, lag, and local acoustic value is finite |
| Evidence identity | inherited A0 and Gate 6 hashes are present |
| Output contract | exactly eight declared files are emitted and all payload hashes are recorded |

Any failed required gate produces:

```text
FAIL_CLOSED
```

with the failed gate name retained in `warnings`.

## 8. Operator-facing interpretation

The report and plots may state bounded observations such as:

- the pressure threshold reaches a cell before or at its accepted HEM phase onset;
- first onset and persistent onset differ in a toggling cell;
- the accepted upstream phase region advances across specified cell centers;
- threshold choice within the predeclared envelope shifts recorded arrival times by a reported amount.

They may not state:

- experimentally validated nucleation delay;
- validated physical pressure-wave speed;
- validated physical flashing-front speed;
- HEM physical accuracy;
- mesh/CFL independence;
- design safety or production suitability;
- root cause of localized phase toggling.

## 9. Successor path

After A1:

- **P1-A2** performs targeted CFL/mesh sensitivity only for decision-relevant outputs such as first crossing, `Δt(x)`, front-event slopes, phase extent, and vapor inventory;
- **P1-A3** connects the bounded HEM analysis contract to an integrated two-phase tool runner;
- **P2** supplies an `HNE_RELAXATION` counterpart using the same comparison fields, allowing equilibrium-versus-delayed-flashing comparison without redefining the HEM baseline.

## 10. Central-record rule

This branch-only increment must not update:

- `stage7_current_gate_snapshot.md`;
- `MASTER_VERIFICATION_INDEX.md`;
- `stage7_execution_log.md`.

Central synchronization occurs only after review/merge and an authoritative workflow/artifact record. Completion of A1 does not promote `VERIFIED`, `ACCEPTED`, `VALIDATED`, design-use, or production status.
