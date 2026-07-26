# Stage 7 — Pipeline CFL-Sensitivity Contract Status

`CONTRACT IMPLEMENTED; CFL 0.10 BASELINE REPRODUCED; LOW-CFL EXECUTION NOT ACCEPTED; VERIFICATION ONLY`

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
budget tolerances remain the merged PR #77 / PR #82 values.

## Baseline guard and replay

All three 128-cell / CFL 0.10 rows are fixed to the authoritative PR #82 artifact,
including outcomes, crossing evidence, saturation margins, sound-speed candidates,
budgets, final-state SHA256 values, and run-signature SHA256 values. Lower-CFL comparison
is rejected unless all three rows reproduce exactly.

The dedicated baseline replay reproduced all three rows exactly:

```text
2 MPa: ACCEPTED_FIRST_CROSSING, step 403, cell 120,
       q_max=1.1990738237934995e-6
3 MPa: GUARD_FAILURE, step 578, cell 118,
       q_max=5.977506786571329e-7
4 MPa: GUARD_FAILURE, step 1086, cell 113,
       q_max=3.8580990283897163e-7
```

The replay does not execute CFL 0.05 or 0.025.

## Authoritative contract/baseline evidence

```text
contract workflow:              30182474750
contract artifact:              8625979612
contract artifact SHA256:       5c422a6a9cbdb8b295e5feac382878cff61d13acccac033e7e16766194b5b337

CFL 0.10 baseline workflow:     30182474773
baseline artifact:              8626482513
baseline artifact SHA256:       c4d257eb83be1932d10b97e7396a30afb65104f9cad2460d199e17368c6d0a1c
```

```text
contract + baseline pure tests: 40 passed
related Stage 7 regressions:    115 passed
full repository:                791 passed
skips / failures / errors:      0 / 0 / 0
```

## Current status

```text
config contract:                    implemented
unauthorized-setting rejection:     implemented
fixed nine-run ordering:             implemented
CFL 0.10 exact baseline guard:       implemented
CFL 0.10 exact numerical replay:     complete
machine-readable contract:           implemented
low-CFL numerical execution:         not executed / not accepted
local-PC reproduction checkpoint:    open in Issue #85
CFL-independent crossing:            not verified
near-saturation acoustic continuity: not approved
post-crossing propagation:           not approved
Gate P2:                             false
physical Validation:                 false
design-use acceptance:               false
production HEM activation:           false
```

PR #82 is merged. This contract/baseline increment is now based directly on `main`.
Final acceptance of a future CFL 0.05/0.025 sensitivity conclusion remains blocked by
the independent local-PC checkpoint recorded in Issue #85.
