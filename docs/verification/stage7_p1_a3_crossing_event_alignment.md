# Stage 7 P1-A3G — Crossing Event Alignment

## Purpose

P1-A3G quantifies the separation between two definitions that were previously
implicitly treated as the same crossing event in the HEM mesh/CFL study.

- **Event A — thermodynamic crossing:** the first retained
  `LIQUID_TO_TWO_PHASE_CROSSING` with positive equilibrium quality and an
  accepted `OPEN_TWO_PHASE` state.
- **Event B — evidence-floor crossing:** the first accepted state for which an
  `OPEN_TWO_PHASE` cell reaches the unchanged crossing evidence floor
  `q >= 1.0e-6`.

This increment is diagnostic only. It does not change the production solver,
EOS, prescribed boundary, phase classifier, equilibrium projection, CFL
algorithm, crossing threshold, conservation tolerances, or any Gate 6/A3
contract.

## Authority boundary

The authoritative P1-A3 result remains frozen as:

```text
sensitivity_execution_status = FAIL_CLOSED
ordering_verdict             = INCONCLUSIVE
numerical_verdict            = INCONCLUSIVE
```

In particular, a sub-threshold Event A is **not** promoted to
`ACCEPTED_FIRST_CROSSING`. The original first-crossing runner is replayed
unchanged for all five predeclared A3 cases. When it returns `GUARD_FAILURE`
because `q_cross < 1e-6`, A3G starts a separate shadow continuation from the
retained accepted Event A state.

## Fixed matrix

| case | cells | CFL | authority role |
|---|---:|---:|---|
| `mesh_16_cfl_0p10` | 16 | 0.10 | coarse mesh |
| `baseline_32_cfl_0p10` | 32 | 0.10 | locked Gate 6 baseline |
| `mesh_64_cfl_0p10` | 64 | 0.10 | fine mesh |
| `cfl_32_0p05` | 32 | 0.05 | low CFL |
| `cfl_32_0p20` | 32 | 0.20 | high CFL |

Only `n_cells` and `CFL` vary on the existing A3 verification-only path.

## Shadow continuation contract

For a sub-threshold Event A, the diagnostic path reconstructs the reviewed
post-crossing FVM environment at the retained Event A time and absolute step:

1. same prescribed 5 MPa → 2 MPa outlet pressure schedule;
2. same first-order FVM / Rusanov solver;
3. same mixed liquid/open-two-phase EOS;
4. same equilibrium quality projection;
5. same conservation budget checks;
6. same positivity/nonfinite checks;
7. same reverse-flow guard;
8. fixed evidence floor `1.0e-6`;
9. bounded continuation of at most 64 accepted shadow steps and no later than
   the original first-crossing horizon.

The shadow path stops at the first accepted Event B. Any unrelated solver,
phase/EOS, projection, budget, backend, nonfinite, positivity, or reverse-flow
failure is retained as a fail-closed diagnostic result rather than bypassed.

## Recorded evidence

For Event A and Event B, A3G records the event time, absolute step, cell,
distance from outlet, equilibrium quality, pressure, temperature, density,
internal energy, void fraction, state SHA-256, and front location. Event A also
records the accepted step size and mesh spacing.

For the A→B interval it records:

```text
Delta t_A_to_B
Delta step_A_to_B
Delta x_front_A_to_B
```

The interval history additionally retains maximum equilibrium quality,
accepted open-two-phase cell count, phase-front distance, conservation
residuals, reverse-flow count, and state SHA at each diagnostic step.

## Interpretation rule

The main hypothesis is that smaller time steps / finer resolution can detect
Event A at a shallower discrete penetration into the two-phase region, while
Event B remains a later evidence threshold crossing.

A3G therefore compares the mesh and CFL series separately. If only the fine
mesh and low-CFL variants require extra accepted steps while the coarse,
baseline, and high-CFL cases have `A == B`, the result may be labeled as strong
support for **discrete event aliasing / event-definition sensitivity**.

That label remains numerical. The A→B interval is **not** a physical nucleation
delay or a validated flashing relaxation time. HEM is still an equilibrium
model, and neither mesh independence nor CFL independence is claimed here.

## Output contract

Exactly nine files are produced:

```text
event_alignment_summary.json
event_alignment_cases.csv
event_a_cells.csv
event_b_cells.csv
event_interval_history.csv
event_ab_time_comparison.png
event_ab_step_comparison.png
operator_report.md
event_alignment_manifest.json
```

The two PNG plots are generated from computed Event A/B data, never from an
image-generation model. The manifest records SHA-256 and byte size for each
payload file.

## A3G closeout gates

A3G is `ALIGNMENT_READY` only when all of the following pass:

- exact five-case A3 matrix retained;
- Event A reproduced for every case;
- Event A state SHA retained;
- authoritative sub-threshold A3 guards preserved;
- above-floor cases correctly coalesce `A == B`;
- Event B observed for every case;
- Event B state SHA retained;
- A→B time/step/front deltas finite;
- no unrelated shadow failure;
- shadow history finite;
- no reverse-flow fallback;
- fixed `1.0e-6` evidence floor unchanged.

Failure of any gate leaves A3G `FAIL_CLOSED` and does not alter the A3 verdict.

## Maturity boundary

Even after a successful A3G diagnostic run:

```text
IMPLEMENTED                    true
WORKING VERTICAL SLICE         false
VERIFIED                       false
ACCEPTED                       false
MESH-INDEPENDENT VERIFIED      false
CFL-INDEPENDENT VERIFIED       false
PHYSICALLY VALIDATED           false
DESIGN-USE ACCEPTED            false
PRODUCTION APPROVED            false
```

`ALIGNMENT_READY` means the Event A/B diagnostic evidence package is complete;
it is not a maturity promotion.
