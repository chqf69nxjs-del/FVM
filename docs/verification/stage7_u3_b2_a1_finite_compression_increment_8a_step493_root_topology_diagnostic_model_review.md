# Stage 7 U3 B2 A1 finite-compression Increment 8A step-493 root-topology diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

This increment diagnoses the fail-closed stop before requested solver step 494 in the corrected Increment 8 execution. It does not advance `FvmSolver`, change B1, relax a tolerance, enlarge the finite-compression diagnostic cap, change the Hugoniot relation, modify the locked B2 Contract, modify production code, or promote any formal state.

## Authoritative parent evidence

```text
source Git SHA:
9fd7ac6bcb6eefcf12099028da2fc731ae96dd3c

workflow run:
31661720453

job:
94327704607

artifact:
9166412782

artifact name:
u3-b2-a1-finite-compression-increment-8-rerun-31661720453

artifact SHA256:
d1d704997ec5e8fd038a0645b31e598939528cd9295de8762c06aaf3b81081d8

outcome:
INCREMENT_8_STOPPED

accepted continuation:
step 492 -> 493

final accepted time:
0.0033036489591120113 s

stop before requested step:
494

stop classification:
NO_UNIQUE_HUGONIOT_ROOT
```

The accepted step 493 retained an outward, subsonic, liquid state, positive density and internal energy, exact-zero `rho*xv`, root residual inside `1e-8 kg/s`, negative root slope, B1 success, Lax ordering, Hugoniot closure, and step/cumulative conservation closure.

## Diagnostic question

The fixed Hugoniot scan uses:

```text
chi =
1.0e-6,
1.05e-6,
1.10e-6,
1.25e-6,
1.50e-6,
2.0e-6,
3.0e-6,
5.0e-6,
1.0e-5,
2.0e-5,
5.0e-5,
1.0e-4
```

The stop classification means no successful-successful sign-change bracket was present and the highest successful residual was not positive beyond the unchanged root tolerance. The diagnostic must distinguish:

```text
A. root returned to or below the Weak Compression limit
B. compatibility zero lies inside the B1-unavailable domain
C. coarse fixed scan jumped over a root that remains inside the B1-success domain
D. multiple roots or nonmonotone successful-domain topology
E. another formal evaluation failure
```

## Fixed method

Load and verify the exact accepted step-493 state. Do not call `FvmSolver.step`.

1. Reconstruct the outlet state and evaluate the unchanged 12-node general-EOS Hugoniot scan.
2. Record every formal B1 outcome, residual, admissibility result, Hugoniot closure, Lax ordering, entropy change, phase, direction, and pressure coordinate.
3. Build the successful/admissible residual topology using only successful B1 states.
4. If the fixed scan has leading B1-unavailable nodes followed by successful nodes but no root bracket, categorically refine the last-unavailable / first-successful interval for exactly 48 iterations.
5. The unavailable side may contain only:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
NONPOSITIVE_KINETIC_ENERGY_HEAD
```

Both remain failed B1 states and may not be root endpoints or construct a flux.
6. Use only the final refined first-success state and higher fixed successful states for compatibility-root topology.
7. If exactly one successful-domain bracket exists, solve the compatibility root with the unchanged 48-iteration bisection and complete all retained root/ledger checks.

## Fixed limits

```text
Weak Compression limit:
1.0e-6

finite-compression diagnostic cap:
1.0e-4

root residual tolerance:
1.0e-8 kg/s

Guard-front categorical iterations:
48

compatibility-root bisection maximum:
48
```

No result-dependent change is permitted.

## Classifications

### `FINITE_COMPRESSION_GUARD_FRONT_REFINEMENT_SUPPORTED`

Requires one B1-success-domain root with:

```text
chi > 1.0e-6
chi <= 1.0e-4
absolute residual <= 1.0e-8 kg/s
negative slope
outward subsonic liquid state
Hugoniot and identity-accounted closure
Lax 1-shock ordering
entropy bound
B1 success
stagnation pressure above back pressure
energy and reaction ledgers closed
```

### `ROOT_RETURNED_TO_WEAK_COMPRESSION_SCOPE`

The successful residual at `chi = 1.0e-6` is already negative beyond tolerance, or a solved root has `chi <= 1.0e-6`.

### `ROOT_LIES_INSIDE_B1_UNAVAILABLE_DOMAIN`

After categorical refinement, the first B1-success residual is negative beyond tolerance.

### `FINITE_COMPRESSION_DIAGNOSTIC_CAP_REQUIRED`

The successful residual remains positive through `chi = 1.0e-4`.

### Fail-closed

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
UNEXPECTED_B1_FAILURE
SUCCESS_DOMAIN_NONMONOTONE
MULTIPLE_COMPATIBILITY_ROOTS
NO_SUCCESSFUL_DOMAIN
ROOT_OR_LEDGER_FAILURE
STATE_MUTATION_DETECTED
```

## Required evidence

Record fixed scan rows, categorical-refinement rows, root-topology rows, optional selected root, exact state identity, parent authority, summary and internal SHA256 manifest.

## Formal-state boundary

Regardless of result, retain all Verification, Validation, design-use, production and formal-promotion flags as `false`. A passing diagnostic authorizes no actual solver step.
