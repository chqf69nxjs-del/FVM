# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4A back-pressure crossing diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

This increment diagnoses the fail-closed stop immediately before requested solver step 444 in the first full-`2L/c0` continuation. It does not advance `FvmSolver`, change a branch law, relax a tolerance, revise the locked B2 v1 Contract, modify B1, modify the production B2 Adapter, modify `FvmSolver`, promote a formal state, or approve a finite-compression model.

## Authoritative parent evidence

```text
source Git SHA:
2e9e2c1c3d01fd66d82b3a2ecb036b811e0469b0

workflow run:
31606368597

job:
94146232478

artifact:
9145306448

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4-31606368597

artifact SHA256:
633bffda60db2a886066772e693f83b5d1e4fd8887526d717637232ac7b3a35b

accepted continuation:
solver step 369 -> 443
74 additional accepted steps

solver time after step 443:
0.0029683027202354953 s

full 2L/c0 target:
0.004285834855172021 s

horizon fraction reached:
0.6925844836633016

stop before requested solver step:
444

stop reason:
connected rarefaction scan has fewer than two admissible subsonic nodes
```

## Accepted-state observations before the stop

The accepted continuation through step 443 retained:

```text
branch:
WEAK_COMPRESSION for all 74 continuation steps

clear branch chatter:
false

maximum Weak Compression chi:
1.7408586415040052e-7

fixed chi limit:
1.0e-6

maximum absolute root mass residual:
9.826877691784808e-9 kg/s

maximum halving count:
0

final outlet pressure:
4949999.458183482 Pa

retained back pressure:
4950000.0 Pa

final outlet velocity:
+0.12216061588858795 m/s

final outlet Mach:
0.0002622502898547208

final outlet phase:
liquid

final rho*xv exact zero:
true
```

The final outlet static pressure is approximately `0.541816518 Pa` below the retained back pressure. The accepted state nevertheless has positive outward velocity, very low Mach number, liquid phase, positive density and internal energy, exact-zero `rho*xv`, no clear branch chatter, and retained mass, momentum, energy, root, and reaction-ledger closure.

## Reviewed implementation preconditions

The current three-branch classifier first evaluates the neutral endpoint. When the endpoint is outside the retained root tolerance, it currently requires at least two admissible connected-rarefaction scan nodes before it evaluates the positive-pressure Weak Compression scan.

The connected-rarefaction diagnostic returns no scan domain when the outlet-cell static pressure is not above the retained back pressure. Therefore the current classifier stops before testing whether a unique positive-pressure Weak Compression root still exists.

The current verification-only Weak Compression context also contains an earlier precondition requiring the outlet-cell static pressure to be above back pressure. This Increment 4A does not change either precondition. It diagnoses whether those preconditions are the only obstacles at the exact step-443 state.

## Objective

Load and verify the authoritative Increment 4 artifact, reconstruct the exact accepted step-443 final state, and evaluate the candidate boundary state for requested step 444 without advancing the solver.

The diagnostic must answer:

```text
1. Is the conserved step-443 state reproduced exactly?
2. Is outlet static pressure at or below back pressure?
3. Is outlet stagnation pressure still above back pressure?
4. Is the neutral endpoint evaluable, outward, subsonic, liquid, and B1-admissible?
5. Is the neutral endpoint outside the unchanged 1.0e-8 kg/s root tolerance?
6. Is the connected rarefaction pressure domain unavailable rather than numerically nonfinite?
7. Are there zero admissible local rarefaction-side root brackets?
8. Does the unchanged positive-pressure scan contain exactly one admissible root bracket?
9. Does bisection find an in-scope Weak Compression root with all retained root and ledger checks passing?
```

## Fixed diagnostic inputs

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

accepted state loaded:
solver step 443

next requested solver step:
444

root mass residual absolute tolerance:
1.0e-8 kg/s

Weak Compression chi scope:
0 < chi <= 1.0e-6

positive-pressure scan coordinate correction:
retain requested Delta-p / requested chi as authoritative for scan-scope bookkeeping

maximum bisection iterations:
32
```

No tolerance or scope may be changed after observing the result.

## Required evidence

At minimum, record:

```text
artifact identity and internal SHA256 manifest verification
solver step and solver time identity
outlet conserved state SHA256
outlet static pressure, temperature, density, velocity, sound speed, Mach, phase
outlet stagnation pressure and stagnation-pressure margin above back pressure
static-pressure margin relative to back pressure
neutral endpoint residual and retained tolerance
neutral endpoint admissibility and energy/reaction-ledger checks
connected rarefaction requested/admissible node counts and stop reason
local rarefaction-side sign-change count
positive-pressure scan rows and requested/realized chi
positive-pressure sign-change count and monotonicity
selected root pressure, pressure offset, chi, residual, slope, Mach, phase
B1 outcome
stagnation-enthalpy, energy-port, energy/mass, and reaction-ledger closure
confirmation that no FvmSolver step 444 was attempted
confirmation that the conserved state was unchanged
```

## Diagnostic classifications

### `BACK_PRESSURE_CROSSING_BRANCH_DOMAIN_CORRECTION_SUPPORTED`

This classification requires all of the following:

```text
artifact and exact state reproduction pass
outlet static pressure <= back pressure
outlet stagnation pressure > back pressure
outlet velocity >= 0
0 <= outlet Mach < 1
outlet phase remains liquid
neutral endpoint evaluation succeeds and is locally admissible
neutral endpoint residual is outside the unchanged root tolerance
connected rarefaction scan has no physical pressure interval from p_i down to p_back
connected rarefaction sign-change count = 0
local rarefaction-side admissible sign-change count = 0
positive-pressure admissible sign-change count = 1
positive scan is monotone nonincreasing
selected root has 0 < chi <= 1.0e-6
absolute root residual <= 1.0e-8 kg/s
root velocity is outward and root Mach is subsonic
root phase remains liquid
B1 succeeds
root slope is negative
energy and restriction-reaction ledgers close
state remains unchanged
FvmSolver step 444 is not attempted
```

A passing result means only that the current stop is consistent with a verification-implementation branch-domain precondition rather than a demonstrated physical or conservative failure. It does not itself authorize a continuation step.

### `BACK_PRESSURE_CROSSING_REQUIRES_PHYSICS_REVIEW`

Return this classification if any required state, root, scope, direction, phase, B1, positivity, or ledger check fails; if a rarefaction-side root exists; if no unique positive-pressure root exists; or if multiple roots are observed.

### Fail-closed classifications

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
ENDPOINT_EVALUATION_FAILURE
ENDPOINT_INADMISSIBLE
STAGNATION_PRESSURE_NOT_ABOVE_BACK
RAREFACTION_ROOT_PRESENT
POSITIVE_SCAN_FAILURE
NO_UNIQUE_WEAK_COMPRESSION_ROOT
FINITE_COMPRESSION_MODEL_REQUIRED
ROOT_OR_LEDGER_FAILURE
STATE_MUTATION_DETECTED
```

## Formal-state boundary

Regardless of the diagnostic result, retain:

```text
finite_compression_branch_approved = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## Next action boundary

Only a passing `BACK_PRESSURE_CROSSING_BRANCH_DOMAIN_CORRECTION_SUPPORTED` result may support a later, separately fixed Increment 4B specification. Any later correction must remain verification-only and must preserve the unchanged root tolerance, Weak Compression chi limit, B1 behavior, locked B2 Contract, production Adapter, and `FvmSolver` implementation.
