# Stage 7 Gate 3 Final Disposition — 2026-07-27

`GATE 3 COMPLETE; NUMERICALLY_EQUIVALENT; GATE 4 REMAINS PAUSED UNTIL CENTRAL-RECORD SYNCHRONIZATION`

## Decision

The independent Windows local-PC checkpoint is accepted as `NUMERICALLY_EQUIVALENT` to the authoritative Ubuntu evidence for the reviewed Stage 7 scope.

The Windows and Ubuntu runs are not bitwise identical. Ubuntu remains the authoritative source for exact scalar values, state SHA256 values, and run-signature SHA256 values. The Windows values do not replace or weaken those exact baselines.

## Reviewed scope

```text
source main:        f1b2c76827482164a12e2924bf7119a0b150e421
mesh:               128 cells
CFL:                0.10
maximum steps:      8000
final pressures:    2 / 3 / 4 MPa
spatial flux:       existing first-order Rusanov
property backend:   CoolProp 8.0.0
NumPy:              2.5.1
```

## Evidence identities

### Ubuntu reference

```text
artifact ID:        8632513953
artifact digest:    sha256:78002ddb524c9f1cac00040a14139d6da512f66f19d39a65afc53dbcac188060
runtime:            Ubuntu 24.04 / Python 3.12.13 / NumPy 2.5.1 / CoolProp 8.0.0
```

### Windows raw-history candidate

```text
file:               stage7-gate3-numeric-candidate-20260726-222235.zip
SHA256:             508e9b727a2e0d00974e4650c3f927e93af89eed9af96cde5c2b0b3e12368738
runtime:            Windows 11 / Python 3.12.10 / NumPy 2.5.1 / CoolProp 8.0.0
ZIP CRC:            passed
```

### Windows complete-repository checkpoint v2

```text
file:               stage7-gate3-windows-full-suite-v2-20260727-215656.zip
size:               30264 bytes
SHA256:             67a0113b63db1b4770baf4bbd4104312c5c24839cf50956e57592f487fd7755f
ZIP CRC:            passed
source main:        f1b2c76827482164a12e2924bf7119a0b150e421
pre-run tree:       clean
post-run tree:      clean
runtime:            Windows 11 / Python 3.12.10 / NumPy 2.5.1 / CoolProp 8.0.0 / Matplotlib 3.11.1
full suite:         796 tests
passed:             785
failures:           4
errors:             7
skipped:            0
pytest exit code:   1
inspector exit:     0
inspector result:   KNOWN_EXACT_WINDOWS_MISMATCHES_ONLY
```

All 11 problems are the pre-reviewed Windows bitwise-exact baseline mismatches. There are no unexpected failures or errors, no missing reviewed mismatch, no changed failure mechanism, and no skipped test.

## Cross-runtime result

The three fixed 128-cell / CFL 0.10 cases retained exact identity for:

```text
case ID
formal outcome and failure category
step count
crossing step
crossing cell
crossing distance from outlet
```

All raw-history array shapes match and all values are finite. The maximum global-scale-normalized difference is:

```text
5.519112370006797e-12
```

against the predeclared cross-runtime guard:

```text
1.0e-10
```

Maximum inventory differences also remain inside the existing absolute budget limits:

```text
mass:       2.842170943040401e-14 kg       <= 1.0e-12 kg
momentum:   1.3575363055906564e-11 kg m/s  <= 1.0e-10 kg m/s
energy:     1.7229467630386353e-08 J        <= 1.0e-06 J
vapor mass: 2.3924178250423736e-16 kg       <= 1.0e-12 kg
```

The first cross-platform difference is already present in the uniform CoolProp-backed initial thermodynamic state before the first FVM update. It does not produce a discrete-event divergence or a crossing-threshold reversal.

## Formal disposition

```text
Gate_3_disposition = NUMERICALLY_EQUIVALENT
Gate_3_complete = true
Ubuntu_exact_baseline_retained = true
Windows_hashes_replace_Ubuntu_hashes = false
solver_logic_changed = false
algorithm_or_tolerance_changed = false
```

Gate 4 remains paused only until this disposition and PR #91 are merged and the central Stage 7 records are synchronized. This disposition does not accept or promote any CFL 0.05 or 0.025 result.

## Approval boundary

```text
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
near_saturation_acoustic_continuity_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
