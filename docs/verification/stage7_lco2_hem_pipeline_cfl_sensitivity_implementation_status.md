# Stage 7 — Pipeline CFL-Sensitivity Contract Status

`CONTRACT IMPLEMENTED; STACKED ON PR #82; EXECUTION NOT YET ACCEPTED; VERIFICATION ONLY`

## Fixed scope

The contract fixes a 128-cell, nine-run matrix:

```text
final pressures:  2 / 3 / 4 MPa
CFL values:       0.10 / 0.05 / 0.025
step caps:        8000 / 16000 / 32000
spatial flux:     existing first-order Rusanov
```

Only CFL and its predeclared inverse-CFL step cap may vary. Geometry, mesh, physical
horizon, boundary schedules, HEM phase/projection settings, evidence threshold, and all
budget tolerances remain the PR #77 values.

## Baseline guard

All three 128-cell / CFL 0.10 rows are fixed to the authoritative PR #82 artifact,
including outcomes, crossing evidence, saturation margins, sound-speed candidates,
budgets, final-state SHA256 values, and run-signature SHA256 values. Lower-CFL comparison
is rejected unless all three rows reproduce exactly.

## Current status

```text
config contract:                    implemented
unauthorized-setting rejection:     implemented
fixed nine-run ordering:             implemented
CFL 0.10 exact baseline guard:       implemented
machine-readable contract:           implemented
low-CFL numerical execution:         not yet accepted
CFL-independent crossing:            not verified
Gate P2:                             false
physical Validation:                 false
design-use acceptance:               false
production HEM activation:           false
```

This branch is stacked from PR #82 because PR #82 is Ready but not yet merged. It must be
retargeted to `main` only after PR #82 lands.
