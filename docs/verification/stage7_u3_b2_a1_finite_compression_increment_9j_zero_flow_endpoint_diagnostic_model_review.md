# Stage 7 U3 B2 A1 finite-compression Increment 9J zero-flow endpoint diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

Increment 9J diagnoses the fail-closed stop immediately before requested solver step 638 in the corrected dynamic-seeded final-horizon attempt.

It distinguishes between:

```text
A. a locally admissible outward-flow Hugoniot/B1 root that became narrower
   than the 257-node dynamic-seeded scan,

and

B. termination of the outward-flow compatibility root at a zero-transfer
   endpoint as stagnation pressure and velocity approach their back-pressure
   and zero-flow limits.
```

Increment 9J does not advance `FvmSolver`, change B1, change local candidate admissibility, relax a tolerance, enlarge the finite-compression `chi` cap, revise the locked B2 Contract, modify the production Adapter, modify `FvmSolver`, or promote any formal project state.

## Authoritative parent evidence

```text
source Git SHA:
8d0568abd827684562783393650d6f63f3aa390f

workflow run:
31670285271

job:
94353300958

artifact:
9169437776

artifact name:
u3-b2-a1-finite-compression-increment-9i-root-schema-31670285271

accepted continuation:
solver step 636 -> 637
one additional accepted step

solver time after step 637:
0.0042695827462251995 s

nominal target:
0.004285834855172021 s

remaining nominal time:
0.0000162521089468215 s

stop before requested solver step:
638

stop reason:
dynamic seeded interval contains no admissible island
```

The accepted step 637 retained the `FINITE_COMPRESSION_HUGONIOT` branch, liquid and outward subsonic outlet state, positive density and internal energy, exact-zero `rho*xv`, root residual within `1.0e-8 kg/s`, and mass, momentum and energy closure.

## Last accepted root

```text
requested solver step:
637

root chi:
1.3736804864166541e-5

root pressure:
4,950,000.003429048 Pa

root pressure offset:
2607.53826605808 Pa

root residual:
5.2838152264648175e-10 kg/s

root velocity:
0.0012306998670057814 m/s

root Mach:
2.641804838015834e-6

root stagnation-pressure margin above back:
approximately 0.00415 Pa
```

## Fixed seed

Reconstruct the exact accepted step-637 outlet state and derive:

```text
seed_chi =
(previous_root_pressure - current_outlet_static_pressure)
/
(current_outlet_density * current_outlet_sound_speed^2)
```

Require:

```text
1.0e-6 < seed_chi < 1.0e-4
```

## Fixed ultrafine root search

Evaluate exactly 4097 equally spaced requested `chi` values over:

```text
0.98 * seed_chi <= chi <= 1.02 * seed_chi
```

including both endpoints.

Every candidate is assigned to exactly one category:

```text
ADMISSIBLE_SUCCESS:
  B1 evaluation succeeds
  local_candidate_admissible = true

EXCLUDED_B1_UNAVAILABLE:
  B1 evaluation fails with exactly:
  - REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
  - NONPOSITIVE_KINETIC_ENERGY_HEAD

EXCLUDED_LOCAL_INADMISSIBLE:
  B1 evaluation succeeds
  local_candidate_admissible = false
```

Any other result is fail-closed.

If the ultrafine scan contains exactly one contiguous admissible island with at least two nodes, refine both categorical boundaries with the existing binary64-resolution-aware 48-logical-iteration rule. Build root topology only from admissible states and require one monotone sign-change bracket and one selected root passing every unchanged gate.

## Fixed endpoint search

Independently evaluate exactly 513 equally spaced requested `chi` values over:

```text
0.50 * seed_chi <= chi <= 2.00 * seed_chi
```

including both endpoints.

This broad diagnostic scan is used only to bracket two scalar endpoints on the unchanged Hugoniot characteristic:

```text
1. stagnation-pressure endpoint:
   p0_candidate - p_back = 0

2. velocity endpoint:
   u_candidate = 0
```

For each scalar, require at most one sign-change bracket. Use a deterministic maximum of 80 binary iterations. When the bracket endpoints become adjacent representable binary64 `chi` values, retain the endpoint with the smaller absolute scalar residual and record a floating-point-resolution hold. No scalar tolerance is added.

At the stagnation-pressure endpoint, record:

```text
candidate static pressure
candidate stagnation pressure and margin
candidate velocity and Mach number
candidate pipe mass rate
candidate phase
B1 formal outcome
local candidate admissibility
```

The existing compatibility-root mass tolerance remains:

```text
absolute pipe mass rate <= 1.0e-8 kg/s
```

for identifying a zero-transfer endpoint that is compatible with the retained root closure scale.

## Diagnostic classifications

### `ULTRAFINE_ADMISSIBLE_ISLAND_WITH_UNIQUE_ROOT_SUPPORTED`

Requires:

```text
parent and exact state verification pass
one ultrafine admissible island with at least two nodes
both categorical boundary refinements retain their invariants
root topology uses only admissible states
root topology is monotone nonincreasing
exactly one compatibility-root bracket exists
selected root remains within 1.0e-6 < chi <= 1.0e-4
absolute root residual <= 1.0e-8 kg/s
negative root slope
outward, subsonic, liquid root
B1 success
all Hugoniot, identity-accounted, Lax, entropy, energy and reaction gates pass
state remains unchanged
FvmSolver step 638 is not attempted
```

A pass supports a later separately fixed one-step continuation. It does not itself authorize a step.

### `ZERO_FLOW_ENDPOINT_WITHIN_COMPATIBILITY_TOLERANCE_SUPPORTED_FOR_BRANCH_REVIEW`

Requires:

```text
parent and exact state verification pass
no ultrafine admissible island and no admissible compatibility root
exactly one stagnation-pressure endpoint bracket exists
stagnation-pressure endpoint candidate remains finite, liquid and subsonic
absolute candidate pipe mass rate <= 1.0e-8 kg/s
candidate velocity is nonnegative within the locked velocity-zero tolerance
velocity endpoint is either independently bracketed nearby or the
stagnation-pressure endpoint already satisfies the locked velocity-zero test
state remains unchanged
FvmSolver step 638 is not attempted
```

A pass means only that the outward-flow root has reached a zero-transfer endpoint closely enough for a new closed/no-transfer branch review. It does not authorize applying a zero flux or advancing the solver.

### Fail-closed classifications

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
UNEXPECTED_CANDIDATE_OUTCOME
MULTIPLE_ULTRAFINE_ADMISSIBLE_ISLANDS
ULTRAFINE_ADMISSIBLE_ISLAND_TOO_NARROW
ULTRAFINE_SUCCESS_DOMAIN_NONMONOTONE
MULTIPLE_COMPATIBILITY_ROOTS
NO_UNIQUE_COMPATIBILITY_ROOT
MULTIPLE_STAGNATION_PRESSURE_ENDPOINTS
MULTIPLE_VELOCITY_ENDPOINTS
NO_STAGNATION_PRESSURE_ENDPOINT
ZERO_FLOW_ENDPOINT_OUTSIDE_COMPATIBILITY_TOLERANCE
ROOT_OR_LEDGER_FAILURE
STATE_MUTATION_DETECTED
```

## Required evidence

Record at minimum:

```text
parent artifact and internal SHA256 verification
exact step/time/state identity
outlet static and stagnation state
last accepted root identity
unchanged 12-node fixed scan
4097-node ultrafine scan
513-node broad endpoint scan
candidate category counts and island count
categorical boundary refinement rows when applicable
compatibility-root topology and selected root when applicable
stagnation-pressure endpoint bisection rows and selected candidate
velocity endpoint bisection rows and selected candidate
endpoint separation and mass-rate closure metrics
confirmation that step 638 was not attempted
confirmation that the conserved state remained unchanged
```

## Formal-state boundary

Regardless of result, retain:

```text
finite_compression_branch_approved = false
multi_step_finite_compression_continuation_authorized = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
