# Stage 7 — Minimal Liquid-to-Two-Phase Raw FVM Dry Run

## Status

`IMPLEMENTED DRAFT; ONE RAW FIRST-ORDER FVM STEP; VERIFICATION ONLY; REVIEW REQUIRED`

This increment follows merged PRs #67–#69. It uses the three state pairs nominated by
the PR #68 property survey and exercises one actual first-order conservative update
through the existing `FvmSolver.step()` path.

Base:

```text
main: 4c0960d32a03269828a8a0d3e2d2c8c9c8322f62
PR #67: mixed liquid/open-two-phase accepted-state EOS
PR #68: liquid state-pair property survey
PR #69: central record synchronization
```

## Objective

Answer one narrow question before connecting equilibrium-quality projection:

> What thermodynamic regions are produced by one actual first-order Rusanov/CFL update
> from the three ledger-backed all-liquid state pairs?

The increment must distinguish:

```text
property-screening proxy
    from
actual conservative FVM update
```

It must retain every case result even when the result is all-liquid, an endpoint,
forbidden, or a guarded/backend failure.

## Deliberate scope boundary

This increment does:

- construct the exact PR #68 liquid candidates through the existing survey path;
- initialize every cell as a supported liquid with `u=0` and transported `q=0`;
- use the existing mixed liquid/open-two-phase verification EOS for the accepted initial state;
- compute `dt` through the existing CFL path;
- advance exactly one `FvmSolver.step()` using the existing Rusanov flux;
- use transmissive boundaries, no physical source, and the existing no-op phase-change model;
- classify the final raw state directly from conserved `rho/e`;
- record cellwise regions, transition events, raw equilibrium quality, and boundary budgets;
- write JSON, case CSV, cell CSV, Markdown, and NPZ evidence.

This increment does not:

- apply `HEMEquilibriumQualityProjection`;
- call the strict accepted-state EOS after the raw update;
- claim that a raw crossing is a formally verified complete crossing step;
- freeze Case A or Case B;
- vary mesh, CFL, or state conditions after observing the result;
- change the solver, Rusanov flux, CFL formula, EOS, phase evaluator, acoustic model,
  projection, boundaries, sources, or budget algorithms;
- approve production HEM, physical Validation, design use, or an acoustic accuracy band.

## Fixed numerical architecture

```text
spatial method:       existing first-order finite volume
numerical flux:       existing Rusanov flux
solver call:          FvmSolver.step()
cell count:           8
pipe length:          1.0 m
pipe diameter:        0.10 m
interface:            between cells 3 and 4
initial velocity:     0 m/s in every cell
initial quality:      q=0 exactly in every cell
CFL:                  0.20
boundaries:           transmissive
physical source:      none
phase projection:     none
internal interface:   none
steps:                exactly 1
```

The initial discontinuity is piecewise constant, with four left-state cells and four
right-state cells.

### Why the first fixed CFL is 0.20

For a stationary first-order Rusanov discontinuity, the dissipative contribution to an
interface-adjacent conservative state has a leading mixing scale of approximately
`CFL/2`. A fixed CFL of `0.20` therefore corresponds to an approximate `0.10` mixing
scale at the first interface update. This matches the first sampled open-two-phase
fraction observed for the strong PR #68 property-screen candidate.

This observation only motivates the first dry-run condition. The actual update also
contains pressure-driven momentum and kinetic-energy effects, so it is not identical to
the PR #68 linear conservative-blend proxy. The CFL was fixed before the actual result
was observed and is not a solver threshold.

## Fixed case matrix

### Strong candidate

```text
case ID: strong_p5m5_to_p2m5
left:    5 MPa / 5 K subcooling
right:   2 MPa / 5 K subcooling
```

PR #68 property screen:

```text
first sampled open point: lambda=0.1
maximum screened q_eq:    1.3397273027615007e-3
```

### Moderate candidate

```text
case ID: moderate_p5m5_to_p3m5
left:    5 MPa / 5 K subcooling
right:   3 MPa / 5 K subcooling
```

PR #68 property screen:

```text
first sampled open point: lambda=0.2
maximum screened q_eq:    5.331295761643359e-4
```

### Liquid negative-control candidate

```text
case ID: control_p5m5_to_p4m5
left:    5 MPa / 5 K subcooling
right:   4 MPa / 5 K subcooling
```

PR #68 property screen:

```text
all sampled points liquid
maximum screened q_eq: 0
```

These labels are candidate roles only. They do not freeze formal Case A or Case B.

## Initial-state path

The existing state-pair survey constructs each candidate from pressure and subcooling:

```text
T_sat = CoolProp(P, Q=0)
T_initial = T_sat - subcooling
rho, e = CoolProp(P, T_initial)
```

Every candidate is accepted only after canonical `rho/e` re-evaluation and positive
finite acoustic evaluation.

The dry-run initial state is then:

```text
U = [rho, 0, rho*e, 0]
```

for each cell.

Required initial conditions:

```text
all cells = LIQUID_CANDIDATE
all q_transport = 0 exactly
all q_eq = 0
all alpha = 0
all rho, p, T, c finite and positive
all e >= 0 under the current solver guard
```

## One-step processing order

```text
accepted all-liquid U_initial
        |
        v
VerificationHEMLiquidOpenTwoPhaseEOS primitive evaluation
        |
        v
existing CFL calculation
        |
        v
transmissive ghost-cell construction
        |
        v
existing Rusanov numerical flux
        |
        v
one FvmSolver.step()
        |
        v
NoSource
        |
        v
NoPhaseChange (no projection)
        |
        v
U_raw after one conservative step
        |
        v
direct rho/e phase and transition classification
        |
        v
raw evidence and boundary-budget capture
```

The strict mixed accepted-state EOS is not called on `U_raw`, because raw transported
quality may differ from equilibrium quality. That mismatch is evidence for the later
projection increment.

## Case outcomes

Each case is classified as one of:

```text
ALL_LIQUID
ENDPOINT_LANDING
OPEN_TWO_PHASE
FORBIDDEN_REGION
GUARD_FAILURE
BACKEND_FAILURE
```

Priority:

```text
FORBIDDEN transition
endpoint landing
liquid-to-two-phase crossing
all liquid
```

A case can be recorded as `OPEN_TWO_PHASE` when at least one initially liquid cell has a
raw `LIQUID_TO_TWO_PHASE_CROSSING` event.

## Required raw evidence

### Per case

```text
case ID and role
left/right candidate IDs
left/right pressure and subcooling
dx and dt
target and measured CFL
outcome and failure reason
changed cell indices
raw region counts
transition event counts
maximum raw q_eq
maximum abs(q_transport_raw - q_eq_raw)
boundary mass/momentum/energy/vapor residuals
```

### Per cell

```text
cell index and center
initial and raw region
transition event
initial/raw rho
initial/raw velocity
initial/raw internal energy
initial/raw pressure and temperature
initial/raw transported quality
initial/raw equilibrium quality
initial/raw void fraction
```

## Expected conservative structure

Because all initial cells have exact `q=0` and zero velocity, the fourth-component
physical and Rusanov flux is zero for the first step. Therefore:

```text
q_transport_raw = 0 exactly
```

for every cell unless the solver path is incorrect.

Only the two cells adjacent to the initial discontinuity should change in the one-step
piecewise-constant, transmissive configuration. The external mass and energy fluxes are
zero initially; pressure forces can produce a net momentum boundary contribution. The
existing `BoundaryBudgetTracker` must close mass, momentum, energy, and vapor inventory
against the recorded external fluxes.

## Interpretation rules

### If the strong case reaches open two phase

This establishes an observed raw first-order FVM crossing candidate:

```text
actual Rusanov/CFL raw transition observed = true
formal complete crossing verification = false
```

Projection, accepted-state recovery, second-projection no-op, and full vapor accounting
remain for the next increment.

### If the strong case remains liquid

The result is retained without changing algorithms or thresholds. A later controlled
attempt may vary one permitted case parameter, beginning with CFL or state pair, while
preserving a complete attempt ledger.

### If an endpoint is reached

The case is recorded as `ENDPOINT_LANDING`. No endpoint sound speed is invented and the
complete crossing path is not continued.

### If a guard or backend failure occurs

The exact failure is retained. No clipping, local fallback, tolerance widening, or
unreviewed model switch is allowed.

## Implementation file

```text
src/liquid_gas_transient/
  hem_liquid_to_two_phase_minimal_fvm_dry_run.py
```

Primary entry points:

```text
build_piecewise_liquid_initial_state
run_one_minimal_raw_fvm_case
run_minimal_raw_fvm_dry_run_matrix
write_minimal_raw_fvm_dry_run_artifacts
```

## Test file

```text
tests/
  test_stage7_lco2_hem_liquid_to_two_phase_minimal_fvm_dry_run.py
```

Dependency-free tests cover:

- invalid dry-run configuration;
- unknown candidate references;
- exact piecewise all-`q=0` initialization;
- one actual `FvmSolver.step()` with injected deterministic EOS/classification paths;
- interface-adjacent changed-cell identification;
- raw crossing plumbing and quality mismatch evidence;
- boundary-budget closure;
- summary approval boundaries;
- artifact content.

Installed-CoolProp testing must execute the fixed three-case matrix with zero skips and
must reject any guard/backend failure.

## Outputs

```text
stage7_lco2_hem_minimal_raw_fvm_dry_run.json
stage7_lco2_hem_minimal_raw_fvm_dry_run_cases.csv
stage7_lco2_hem_minimal_raw_fvm_dry_run_cells.csv
stage7_lco2_hem_minimal_raw_fvm_dry_run.md
stage7_lco2_hem_minimal_raw_fvm_dry_run.npz
```

## Completion criteria

The increment is review-ready when:

```text
source compiles
git diff --check is clean
dependency-free focused tests pass
installed-CoolProp focused test executes with zero skips
fixed three-case runner completes
no default case has GUARD_FAILURE or BACKEND_FAILURE
related Stage 7 HEM tests pass
full repository tests pass
artifacts are uploaded
actual case outcomes are recorded in the PR and plan
permanent workflows pass on the final head
temporary validation workflow is removed
final diff contains only source, tests, and verification documents
```

## Approval boundary

```text
verification_only = true
FvmSolver.step exercised = true
raw first-order crossing may be observed
quality projection exercised = false
post-projection accepted EOS exercised = false
actual_first_order_fvm_crossing_verified = false
case_a_frozen = false
case_b_frozen = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Next increment after review and merge

1. review the raw one-step outcome ledger;
2. if a repeatable raw crossing exists, connect equilibrium-quality projection;
3. evaluate the post-projection mixed accepted state;
4. verify a second projection is a no-op;
5. extend to a small number of steps only after the complete one-step path is understood;
6. freeze Case A and matched Case B only after repeatable complete behavior is observed.
