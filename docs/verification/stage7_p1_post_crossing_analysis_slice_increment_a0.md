# Stage 7 P1 — Bounded Post-Crossing Pressure-Wave / Flashing Analysis Slice — Increment A0

## 1. Status and claim boundary

This document defines the first implementation increment for:

> **P1 — bounded post-crossing pressure-wave / flashing analysis slice**

Increment A0 adds a non-invasive analysis layer on top of the existing Stage 7
HEM first-crossing and Gate 6 post-crossing evidence. It does **not** change the
physical solve.

Current claim boundary:

- IMPLEMENTED: **true after merge of this increment**
- WORKING VERTICAL SLICE: **false until an authoritative workflow run passes**
- VERIFIED: **false**
- ACCEPTED: **false**
- PHYSICALLY VALIDATED: **false**
- DESIGN-USE ACCEPTED: **false**
- PRODUCTION APPROVED: **false**

`ANALYSIS_READY` is an execution status for this bounded output contract. It is
not a maturity promotion.

## 2. Existing authority reused; no duplicate physics specification

A0 is a successor analysis increment, not a replacement for the existing
contracts.

| Existing asset | Authority retained | A0 reuse |
|---|---|---|
| `stage7_lco2_hem_liquid_to_two_phase_boundary_crossing_spec.md` | thermodynamic and conservative liquid-to-two-phase transition | phase classification and quality-sync results are consumed unchanged |
| `stage7_lco2_hem_pipeline_depressurization_prototype_spec.md` | controlled pressure wave through first accepted crossing | first-crossing time, position, and pressure-arrival evidence are consumed unchanged |
| `hem_pipeline_post_crossing_propagation.py` | fixed Gate 6 +1 / +4 / +16 / +64 accepted-step continuation | complete step/cell evidence, acoustic response, inventories, budgets, and hashes are consumed unchanged |
| `stage7_u3_b2_a1_working_tool_v0_b_closeout.md` | single-phase Working Tool output/storage/reproducibility claim boundary | output-discipline principles are reused; the v0-B public contract is not modified |

A0 does not introduce a second first-crossing specification, a second HEM
solver, or a second post-crossing physical authority.

## 3. Minimal P1 A0 scope

The fixed case remains:

- pure CO2 / CoolProp HEM baseline;
- 1.0 m pipe;
- 0.10 m diameter;
- 32 cells;
- CFL = 0.10;
- initial pressure = 5 MPa;
- 5 K subcooling;
- prescribed outlet reduction to 2 MPa;
- exact accepted first crossing from the existing prototype;
- fixed 64 accepted post-crossing steps from Gate 6.

A0 derives, without rerunning or modifying any state update:

1. pressure-front position versus time;
2. flashing/phase-front position versus time;
3. pressure-front minus phase-front separation;
4. two-phase occupied length, span, and contiguity;
5. first-crossing time and position;
6. existing pressure-drop arrival times;
7. vapor quality, void fraction, and vapor inventory indicators;
8. local sound speed at both tracked fronts plus liquid/two-phase acoustic ranges;
9. existing mass, momentum, energy, and vapor budget residuals;
10. deterministic source and analysis SHA-256 evidence keys.

## 4. Front definitions

### 4.1 Pressure front

At each accepted post-crossing step, the pressure front is the furthest-upstream
cell satisfying the existing fixed evidence condition:

```text
(p_initial - p_cell) / p_initial >= 1e-6
```

No new result-dependent threshold is introduced.

### 4.2 Flashing / phase front

At each accepted post-crossing step, the phase front is the furthest-upstream
accepted cell whose existing post-projection region is:

```text
OPEN_TWO_PHASE
```

Transported quality is not used as a phase classifier.

### 4.3 Relationship metric

```text
front separation
= pressure-front distance from outlet
- phase-front distance from outlet
```

A positive value means the pressure disturbance has propagated farther upstream
than the accepted open two-phase region.

### 4.4 Two-phase extent

A0 reports both:

- occupied length = open-two-phase cell count x `dx`;
- span = distance covered from the minimum to maximum open-two-phase cell index.

It also reports whether the open indices are contiguous. Non-contiguity is
visible as an explicit warning; it is not silently converted into a continuous
front.

## 5. Exact output contract

A0 writes exactly four analysis files, separate from the Gate 6 evidence bundle:

1. `analysis_summary.json`
2. `front_history.csv`
3. `pressure_arrival.csv`
4. `analysis_manifest.json`

`cell_history.csv` is not duplicated. Gate 6 remains the detailed cell-level
physical/evidence authority.

The manifest records:

- exact declared filenames and file count;
- payload SHA-256 and byte size;
- source summary SHA-256;
- last valid source-state SHA-256;
- analysis SHA-256;
- model identifier;
- execution status;
- explicit formal maturity flags.

## 6. PASS / FAIL gates

A0 returns `ANALYSIS_READY` only when all of the following pass:

| Gate | PASS condition |
|---|---|
| Source baseline | existing first-crossing replay remains exact |
| Bounded continuation | all fixed 64 post-crossing steps completed |
| Structural history | one complete 32-cell history exists for every accepted step |
| Finite outputs | required thermodynamic, acoustic, front, inventory, and budget values are finite |
| Positivity and bounds | density, pressure, and temperature remain positive; quality and void fraction remain bounded |
| Acoustic output | every accepted cell retains a positive successful equilibrium sound speed |
| Conservation | existing mass, momentum, and energy residuals remain within existing fixed tolerances |
| Vapor budget | existing vapor residual remains within the existing fixed tolerance |
| Pressure front | the fixed pressure-drop criterion identifies a front at every accepted step |
| Phase front | at least one accepted `OPEN_TWO_PHASE` cell identifies the phase front at every accepted step |
| Evidence keys | source and accepted-state SHA-256 keys are present |

Any failed required gate produces:

```text
FAIL_CLOSED
```

with named failed gates in `warnings`. Partial output may be retained for
diagnosis, but it must not be promoted to a Working Vertical Slice.

## 7. Explicit non-goals

A0 does not:

- change the production solver;
- change the EOS or CoolProp backend version;
- change Rusanov flux or add a higher-order scheme;
- change the prescribed boundary model;
- change CFL, mesh, horizon, crossing threshold, or any tolerance;
- change phase classification or equilibrium quality projection;
- prove HEM physical accuracy;
- establish a two-phase acoustic accuracy band;
- establish mesh or CFL independence for P1 outputs;
- integrate U3 B2 physical discharge with the HEM path;
- implement HNE, slip, wall heat transfer, friction, non-condensable gas, or relief-device dynamics;
- authorize design use or production activation.

## 8. Implementation increments

| Increment | Purpose | Exit condition |
|---|---|---|
| **P1-A0** | non-invasive analysis contract, front metrics, fail-closed gates, exact 4-file bundle | focused tests and authoritative HEM execution pass |
| **P1-A1** | decision-relevant plots and concise operator-facing interpretation | plots reproduce A0 data without changing the solve |
| **P1-A2** | targeted CFL/mesh checks for selected outputs only | selected front/time/inventory outputs are sensitivity-bounded or limitations are explicit |
| **P1-A3** | connect the analysis contract to an integrated two-phase tool runner | end-to-end bounded run with reproducible outputs and explicit warnings |

The sequence must not expand into open-ended Verification after its predefined
exit conditions are met.

## 9. P2 HNE / relaxation interface

A0 establishes a model-neutral comparison surface:

- `model_id`;
- first-crossing time and position;
- pressure-arrival table;
- pressure-front history;
- phase-front history;
- pressure/phase-front separation;
- vapor quality, void fraction, and vapor inventory;
- local and range-based acoustic response;
- budget residuals;
- deterministic evidence hashes.

The current model identifier is:

```text
HEM_EQUILIBRIUM
```

The planned P2 counterpart is:

```text
HNE_RELAXATION
```

P2 may therefore compare flashing onset, pressure undershoot/plateau, wave and
phase-front speeds, vapor generation, and temperature response without changing
P1 field names or redefining the HEM baseline.

## 10. Central-record rule

This branch-only increment does not update:

- `stage7_current_gate_snapshot.md`;
- `MASTER_VERIFICATION_INDEX.md`;
- `stage7_execution_log.md`.

Those records should be updated only after the branch is reviewed, merged or
otherwise centrally synchronized, and an authoritative workflow/artifact claim
has been established.
