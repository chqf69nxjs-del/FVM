# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 3 scope-roundoff correction

## Status

`MODEL_REVIEW_ONLY / IMPLEMENTATION_CORRECTION / FIXED_BEFORE_RERUN_RESULT`

This note fixes one diagnostic bookkeeping defect observed in the first Increment 3 run. It does not change the Weak Compression model, the root tolerance, the fixed `chi` scope, the positive-pressure scan sequence, the bisection limit, the B1 component, the locked B2 v1 Contract, the production B2 Adapter, or `FvmSolver`.

## Parent failed run

```text
source Git SHA:
c2149f208541ef91cf7150cdb1f08d5d0e9e628b

workflow run:
31604342356

job:
94139330954

artifact:
9144587240

artifact SHA256:
3501bf7b1570bf5aacaf4bd3677d17f0afd5a35f34e9796a00edc0fa7c1825f3

outcome:
INCREMENT_3_STOPPED

stop classification:
POSITIVE_SCAN_SCOPE_FAILURE

accepted steps completed:
6

solver step:
337 -> 343
```

The six accepted rows all classified as `WEAK_COMPRESSION`. They retained liquid phase, positive density and internal energy, outward velocity, exact-zero `rho*xv`, root/energy/reaction-ledger closure, and step/cumulative mass, momentum, and energy closure.

Observed accepted range:

```text
maximum accepted Weak Compression chi:
5.122116859523432e-11

maximum absolute accepted root residual:
9.649011277479413e-9 kg/s

maximum accepted root Mach:
2.6305715005834273e-4

maximum halving count:
0

clear branch chatter:
false
```

Therefore the accepted solution did not approach the fixed Weak Compression applicability limit `chi = 1.0e-6`.

## Defect classification

The stop occurred while constructing the next positive-pressure scan, before solver step 344.

The final scan node is requested as

```text
Delta_p_requested = chi_max rho_i c_i^2
```

The original short-run diagnostic then formed the absolute pressure and reconstructed the offset as

```text
p_candidate = p_i + Delta_p_requested

Delta_p_reconstructed = p_candidate - p_i
```

At approximately `p_i = 4.95 MPa`, floating-point addition and subtraction can shift the reconstructed offset by one or a few representable absolute-pressure units. The diagnostic compared that reconstructed value directly with the exact requested `chi_max` and classified the scan endpoint as outside scope.

This is a numerical representation defect in diagnostic bookkeeping. It is not evidence that the physical root reached or exceeded the fixed Weak Compression scope.

## Fixed correction

For scan topology and scope classification, retain the requested scan coordinate as authoritative:

```text
Delta_p_scan = the exact decade or cap offset requested by the scan

chi_scan = Delta_p_scan / (rho_i c_i^2)
```

The EOS/B1 evaluation continues to use the representable absolute pressure:

```text
p_candidate = float(p_i + Delta_p_scan)
```

Record both values:

```text
requested_pressure_offset_pa
realized_pressure_offset_pa = p_candidate - p_i

requested_chi
realized_chi
```

Use `requested_chi` for the fixed scan-scope gate. Use the realized candidate state and pressure for all EOS, B1, flux, root, and ledger calculations.

No tolerance is added. No `chi` limit is enlarged. No root is accepted outside

```text
0 < requested_chi <= 1.0e-6
```

The bisection root itself remains accepted only by the unchanged physical residual and completed root-state checks.

## Rerun scope

Rerun the unchanged Increment 3 32-accepted-step diagnostic through a narrow wrapper that replaces only the positive-scan coordinate bookkeeping described above.

The rerun must still satisfy every fixed Increment 3 gate and must preserve:

```text
root mass tolerance = 1.0e-8 kg/s
chi_max = 1.0e-6
maximum bisection iterations = 32
allowed branches = RAREFACTION / NEUTRAL_ENDPOINT / WEAK_COMPRESSION
CLEAR_BRANCH_CHATTER = five-point A-B-A-B-A
formal state flags = false
```

A passing rerun remains `MODEL_REVIEW / WORKING_VERTICAL_SLICE` evidence only.
