# Stage 7 P1-A2 — Pressure-Front Threshold Sensitivity

## Purpose

P1-A2 checks whether the principal P1 interpretation,

> the pressure front reaches farther upstream before the accepted equilibrium
> `OPEN_TWO_PHASE` front,

is sensitive to the numerical definition used to detect the pressure front.

The predeclared relative pressure-drop thresholds are:

- `0.5e-6`
- `1.0e-6` — inherited P1-A0/P1-A1 reference
- `2.0e-6`

The purpose is not to calibrate a preferred threshold. The purpose is to test
whether a decision-relevant interpretation survives a bounded change in the
measurement definition.

## Inherited authority

P1-A2 is a postprocessing successor to:

1. the fixed Stage 7 Gate 6 continuation,
2. P1-A0 post-crossing analysis, and
3. P1-A1 pressure-arrival / phase-onset relationship analysis.

P1-A2 reruns the same deterministic fixed case and records the inherited Gate 6,
P1-A0, and P1-A1 evidence hashes. It does not use a conversationally copied
number as authority.

## Physics and numerics held fixed

P1-A2 does not change:

- the conservative FVM solver,
- the EOS or CoolProp backend,
- mesh size,
- CFL,
- initial or boundary conditions,
- phase classifier,
- quality projection,
- accepted-state recovery,
- post-crossing step count, or
- HEM equilibrium assumptions.

Only the postprocessing threshold used to identify pressure arrival and the
pressure-front position is changed.

## Decision scope

The formal A2 verdict is limited to:

> whether pressure-front precedence over the accepted equilibrium phase front
> is retained for all three predeclared thresholds.

The result is classified as:

- `ROBUST` — the ordering conclusion is retained at all thresholds;
- `SENSITIVE` — the ordering conclusion changes at one or more thresholds;
- `INCONCLUSIVE` — the inherited evidence or structural comparison gates fail.

The verdict does not assert that exact pressure-arrival times or discrete
cell-center front speeds are threshold independent.

## Decision checks

For each threshold, P1-A2 records and checks:

- pressure-arrival time at every cell,
- arrival-time shift relative to the `1.0e-6` reference,
- pressure-to-first-phase-onset lag at every comparable cell,
- pressure-front position at every accepted snapshot,
- accepted phase-front position at every accepted snapshot,
- pressure/phase front separation,
- the number of phase-bearing snapshots for which pressure is strictly ahead,
- final pressure-front and phase-front positions, and
- discrete pressure-front advancement slopes.

A `ROBUST` verdict requires all of the following across all three thresholds:

1. every cell that shows an accepted phase onset also has a pressure arrival;
2. pressure-to-phase lag remains positive at every comparable cell;
3. pressure remains strictly ahead at every phase-bearing snapshot; and
4. the final pressure front is not behind the final phase front.

## Output contract

The A2 workflow emits exactly nine evidence files:

1. `threshold_summary.json`
2. `threshold_comparison.csv`
3. `threshold_cell_arrivals.csv`
4. `threshold_front_history.csv`
5. `threshold_pressure_front_speed.csv`
6. `threshold_front_position.png`
7. `threshold_phase_lag.png`
8. `operator_report.md`
9. `threshold_manifest.json`

The manifest contains SHA-256 digests and sizes for the other eight payload
files, plus the deterministic A2 sensitivity digest and inherited source
evidence hashes.

## Interpretation boundaries

### HEM limitation

The phase onset is the first accepted equilibrium `OPEN_TWO_PHASE` state at the
cell. The pressure-to-phase lag must not be interpreted as a validated physical
nucleation delay. Thermodynamic non-equilibrium belongs to the later HNE /
relaxation increment.

### Front-speed limitation

The pressure-front speed records are discrete slopes between cell-center
threshold events. They are diagnostics, not validated physical wave speeds.
Changes in these slopes across thresholds are reported rather than hidden.

### Remaining sensitivities

P1-A2 does not establish:

- pressure-front threshold independence outside the declared envelope,
- mesh independence,
- CFL independence,
- physical phase-front speed,
- two-phase acoustic accuracy,
- physical flashing delay,
- phase-chatter root cause,
- physical blowdown Validation,
- design-use acceptance, or
- production approval.

## Formal maturity

P1-A2 may establish an implemented, reproducible threshold-sensitivity evidence
slice. It does not elevate the project to `VERIFIED`, `ACCEPTED`, `VALIDATED`,
`DESIGN-USE ACCEPTED`, or `PRODUCTION APPROVED`.

The formal status remains:

- IMPLEMENTED: `true`
- WORKING VERTICAL SLICE: `false`
- VERIFIED: `false`
- ACCEPTED: `false`
- PHYSICALLY VALIDATED: `false`
- DESIGN-USE ACCEPTED: `false`
- PRODUCTION APPROVED: `false`

## Next step after A2

After the A2 evidence is reviewed, the next P1 task is a bounded mesh/CFL
sensitivity matrix for decision-relevant outputs:

- first crossing time and position,
- pressure-front position,
- phase-front position,
- vapor inventory,
- maximum equilibrium quality, and
- maximum void fraction.

That work remains separate from the threshold-definition sensitivity addressed
here.
