# Stage 7 U3 B2 A1 finite-compression Increment 9G seeded admissible-island diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

Increment 9G diagnoses the fail-closed stop immediately before requested solver step 636 in Increment 9F. It tests whether the fixed 12-node `chi` scan lost a narrowing locally admissible B1-success island between two adjacent fixed nodes.

It does not advance `FvmSolver`, change B1, change local admissibility, relax a tolerance, enlarge the finite-compression `chi` cap, change a fixed scan node, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, or promote any formal project state.

## Authoritative parent evidence

```text
source Git SHA:
85933c7061d45ef13cf846c958469b44fe1e3d64

workflow run:
31668593946

job:
94348434251

artifact:
9168897325

artifact name:
u3-b2-a1-finite-compression-increment-9f-bounded-full-horizon-31668593946

artifact SHA256:
b4603bca6306ef3da1fe3a2fe5ff6e58bc2be599d8a040831445dd579b647288

accepted continuation:
solver step 605 -> 635
30 additional accepted steps

solver time after step 635:
0.004256164770712251 s

nominal target:
0.004285834855172021 s

horizon fraction reached:
0.9930771750516785

stop before requested solver step:
636

stop reason:
fixed scan has no admissible-success window
```

The accepted continuation retained 30 `FINITE_COMPRESSION_HUGONIOT` steps, zero branch transitions, no chatter, liquid and outward subsonic outlet state, positive density and internal energy, exact-zero `rho*xv`, root residual within `1.0e-8 kg/s`, `chi` within `1.0e-4`, and mass, momentum and energy closure.

## Last accepted root

```text
requested solver step:
635

root chi:
1.371240809306482e-5

root pressure:
4,950,000.0332580665 Pa

root pressure offset:
2601.2731664404273 Pa

root residual:
-4.308673777844458e-9 kg/s

root velocity:
0.003809108079997339 m/s

root Mach:
8.17726460280697e-6

root stagnation-pressure margin above back:
0.039657751098275185 Pa
```

At step 635, the fixed `chi=1.0e-5` candidate was excluded below the B1-success domain, while `chi=2.0e-5` remained admissible. The accepted root lay between these fixed nodes. After one update the admissible domain may have narrowed so that neither fixed endpoint samples it.

## Diagnostic interval

Select the two unchanged fixed `chi` nodes that enclose the last accepted root:

```text
lower fixed chi:
1.0e-5

upper fixed chi:
2.0e-5
```

The interval is fixed from the parent root before observing the step-636 result.

Evaluate exactly 129 equally spaced requested `chi` values including both endpoints:

```text
chi_j = 1.0e-5 + j * (1.0e-5 / 128)
for j = 0 ... 128
```

Every candidate is assigned to one exact category:

```text
ADMISSIBLE_SUCCESS:
  evaluation_succeeded = true
  local_candidate_admissible = true

EXCLUDED_B1_UNAVAILABLE:
  evaluation fails with exactly:
  - REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
  - NONPOSITIVE_KINETIC_ENERGY_HEAD

EXCLUDED_LOCAL_INADMISSIBLE:
  evaluation_succeeded = true
  local_candidate_admissible = false
```

Any other result is fail-closed.

## Admissible-island construction

Require the 129-point diagnostic scan to contain exactly one contiguous `ADMISSIBLE_SUCCESS` island with at least two nodes.

Refine both categorical boundaries for exactly 48 iterations:

```text
lower boundary:
  lower endpoint excluded
  upper endpoint admissible

upper boundary:
  lower endpoint admissible
  upper endpoint excluded
```

An excluded endpoint may be either retained excluded category. It remains unusable as a root endpoint or flux state.

For compatibility-root topology use only:

```text
final refined lower admissible endpoint
all diagnostic ADMISSIBLE_SUCCESS nodes strictly inside the refined interval
final refined upper admissible endpoint
```

Sort by requested `chi`, remove duplicate coordinates, and require:

```text
strictly increasing requested chi
monotone nonincreasing compatibility residual
exactly one admissible sign-change bracket
```

Use the unchanged compatibility-root bisection and complete the root with all existing Hugoniot, identity-accounted, B1, Lax, entropy, direction, phase, stagnation-pressure, energy and reaction-ledger gates.

## Fixed scope

```text
accepted state loaded:
solver step 635

next requested solver step:
636

solver time:
0.004256164770712251 s

fixed diagnostic interval:
1.0e-5 <= chi <= 2.0e-5

diagnostic scan nodes:
129

lower boundary refinement iterations:
48

upper boundary refinement iterations:
48

compatibility-root absolute tolerance:
1.0e-8 kg/s

finite-compression chi cap:
1.0e-4
```

No scan count, interval, tolerance, formal outcome, admissibility rule, or scope may be changed after observing the result.

## Required evidence

Record at minimum:

```text
parent artifact and internal SHA256 verification
exact step/time/state identity
outlet static and stagnation state
last accepted root identity
all 12 unchanged fixed scan rows
all 129 seeded diagnostic rows
category counts and contiguous-island count
island first/last requested chi
all 48 lower-boundary rows
all 48 upper-boundary rows
final admissible/excluded boundary coordinates
root-topology rows and residuals
root sign-change count
selected root pressure, chi, residual, slope, velocity, Mach, phase,
B1 outcome, Hugoniot closure, Lax ordering, entropy and ledgers
confirmation that step 636 was not attempted
confirmation that the conserved state remained unchanged
```

## Diagnostic classifications

### `SEEDED_ADMISSIBLE_ISLAND_WITH_UNIQUE_ROOT_SUPPORTED`

Requires:

```text
parent and state verification pass
outlet remains finite, positive, outward, subsonic and liquid
129-point interval contains exactly one admissible island
island contains at least two diagnostic nodes
both 48-iteration boundary refinements retain excluded/admissible invariants
root topology uses only admissible states
root topology is monotone nonincreasing
exactly one root bracket exists
selected root remains within 1.0e-6 < chi <= 1.0e-4
absolute root residual <= 1.0e-8 kg/s
negative root slope
outward, subsonic, liquid root
B1 success
all Hugoniot, Lax, entropy, energy and reaction gates pass
state remains unchanged
FvmSolver step 636 is not attempted
```

A pass means only that the fixed 12-node scan skipped a narrower admissible island and one valid step-636 root remains. It does not authorize an actual step.

### Fail-closed classifications

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
UNEXPECTED_CANDIDATE_OUTCOME
NO_ADMISSIBLE_ISLAND
MULTIPLE_ADMISSIBLE_ISLANDS
ADMISSIBLE_ISLAND_TOO_NARROW_FOR_FIXED_DIAGNOSTIC
LOWER_BOUNDARY_REFINEMENT_FAILURE
UPPER_BOUNDARY_REFINEMENT_FAILURE
SUCCESS_DOMAIN_NONMONOTONE
MULTIPLE_COMPATIBILITY_ROOTS
NO_UNIQUE_COMPATIBILITY_ROOT
ROOT_OR_LEDGER_FAILURE
STATE_MUTATION_DETECTED
```

## Formal-state boundary

All approval, Verification, Validation, design-use and production flags remain false regardless of result.
