# Stage 7 Gate 9 D1 — Read-only instrumentation scaffold

## Status

```text
Issue:                         #110
base:                          latest main after PR #113
increment:                     D1
solver execution changes:      NONE
Rusanov decomposition:         PENDING D2
acoustic attempt hooks:        PENDING D3
event-window retention:        PENDING D4
Gate 9 execution:              NOT STARTED
```

## Implementation boundary

D1 consumes `PipelineCaseResult` only after the unchanged solver has returned.
It does not inject a callback into `FvmSolver`, recompute the time step, call a
replacement EOS, change a guard, or continue beyond a formal stop.

The retained evidence already contains:

```text
accepted state history
pressure history
step / time / dt / formal outcome / state SHA
raw cell rho / velocity / internal energy / transported quality
raw and post region labels
raw transition event
post equilibrium quality / void fraction / sound speed
projection activity flags
```

D1 reconstructs read-only records for cells `28/29/30/31` at:

```text
PRE_STEP_ACCEPTED
RAW_POST_FVM
FINAL_ACCEPTED_IF_AVAILABLE
```

The intermediate first- and second-projection state arrays are not retained by the
current result object. D1 therefore does not synthesize those stages. They remain
explicitly `PENDING` for the later event-aligned capture increment.

## Fixed record types

```text
Gate9CellStageRecord
Gate9InterfaceFluxRecord
Gate9AcousticAttemptRecord
Gate9CandidateSummary
Gate9RunResult
```

`Gate9InterfaceFluxRecord` and `Gate9AcousticAttemptRecord` are fixed now so D2 and
D3 cannot silently change column names after results exist. Their D1 CSV files
contain headers only and carry explicit pending status.

## Non-mutation proof

The scaffold hashes the retained time, pressure, and accepted-state histories plus
the formal solver identity immediately before and after record creation. A mismatch
is a hard instrumentation error.

The dedicated installed-CoolProp test additionally executes the candidate case with
diagnostics off and on and requires exact equality of:

```text
formal outcome and failure reason
step count and physical time
candidate step / time / cell / maximum q_eq
final state SHA256 and run signature
full time history
full pressure history
full accepted conservative-state history
```

## Explicitly unavailable in D1

The following are not inferred:

```text
measured CFL retained per step
q from internal-energy coordinate
q from specific-volume coordinate
saturation e/v margins
raw-state void fraction
raw-state sound speed and branch
exact first-projection intermediate state
exact second-projection state equality
Rusanov central/dissipative terms
acoustic trial and halving history
```

They are stored as `None` or a named pending category. No clipping, fallback,
threshold change, or extra continuation is used.

## Approval boundary

```text
Gate_9_execution_complete = false
crossing_depth_CFL_sensitivity_characterized = false
crossing_depth_root_cause_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
