# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 working vertical slice baseline

## Status

`RETRACTED_FULL_HORIZON_CLAIM / AUTHORITATIVE_SCOPE_LIMIT_RECORDED / NOT_FORMALLY_VERIFIED`

The earlier version of this record stated that B2-10A reached the nominal full `2L/c0` horizon. That claim is retracted.

The workflow identifiers cited by the earlier record were not resolvable as an executed authoritative GitHub Actions run. A subsequent audit found that the actual root-topology rerun had stopped during read-only authority inspection before the corrected solver was executed.

After correcting the authority inspection and executing the actual `FvmSolver` continuation, the Weak Compression v0.1 branch reached its fixed `chi` scope limit before the full horizon. This file now records that authoritative result.

This correction does not change the physical model or any formal project state.

## Authoritative evidence

```text
repository:
chqf69nxjs-del/FVM

branch:
agent/u3-b2-a1-wave-curve-review

source Git SHA:
2c1e1e26138b7d3bd3cf0e7f1d2f7a2c11b443c1

workflow:
Agent U3 B2 A1 Weak Compression Bridge Increment 4F Root Topology Rerun

workflow run:
31650819553

job:
94294552017

artifact:
9162559698

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4f-root-topology-31650819553

GitHub artifact SHA256:
6f611e1935d2680a04046d1fc7fbb595f19bc99d12ccc274700fd92c086ddb93

outcome:
INCREMENT_4F_STOPPED

stop classification:
GuardFrontContinuationStop

stop reason:
GuardFrontContinuationStop: successful residual remains positive through the fixed chi scope
```

The workflow completed:

```text
source and correction-scope inspection
Increment 3 parent artifact download
corrected Increment 4E artifact download
failed Increment 4D artifact download
failed Increment 4F artifact download
GitHub artifact metadata and digest verification
internal artifact SHA256 verification
actual FvmSolver continuation
failure-evidence upload
```

The stop occurred in the actual full-horizon continuation, not in authority inspection.

## Fixed case

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

fluid:
CO2

cells:
32

CFL:
0.10

pipe length:
1.0 m

nominal target:
2L/c0 = 0.004285834855172021 s
```

## Authoritative result

The authoritative Increment 3 state was loaded at:

```text
solver step:
369

solver time:
0.0024719939763977834 s
```

The corrected continuation accepted:

```text
additional accepted steps:
114

final accepted solver step:
483

final solver time:
0.0032365792102672024 s

nominal horizon fraction:
0.7551805703295805
```

Therefore the authoritative current working vertical slice reached approximately:

```text
75.52% of nominal 2L/c0
```

It did not reach the nominal full horizon.

Together with the authoritative Increment 3 continuation, accepted solver steps 338 through 483 form 146 post-Neutral Weak Compression steps after the accepted step-337 Neutral endpoint.

## Why the run stopped

At the final accepted step, the selected root remained inside the fixed Weak Compression scope:

```text
selected root pressure offset:
189.63561215624213 Pa

selected root chi:
9.994599988803244e-7

fixed chi limit:
1.0e-6

selected root residual:
-4.57096713604721e-9 kg/s

root residual absolute tolerance:
1.0e-8 kg/s
```

The selected step-483 root was therefore admissible and accepted.

Before requested solver step 484, the successful-domain compatibility residual remained positive through the fixed `chi = 1.0e-6` cap. No root existed inside the approved Weak Compression v0.1 scope.

The correct classification is:

```text
FINITE_COMPRESSION_MODEL_REQUIRED
```

The run was intentionally stopped rather than:

```text
enlarging chi_max
relaxing the root tolerance
using a failed B1 state
extrapolating an unapproved compression branch
```

## Branch and Guard-front behavior

The authoritative continuation retained:

```text
accepted branch:
WEAK_COMPRESSION

accepted continuation branch count:
114

continuation branch transitions:
0

clear five-point branch chatter:
false

maximum dt-halving count:
0
```

Guard-front root-topology refinement first activated at requested solver step:

```text
452
```

It produced 24 accepted refined roots before the Weak Compression scope was exhausted.

The refinement evidence retained:

```text
B1-unavailable categorical states on the lower side
B1-success and locally admissible states on the upper side
exactly 32 categorical Guard-front iterations
failed B1 states excluded from compatibility-root endpoints
failed B1 states excluded from applied fluxes
root-topology pressure coordinates strictly increasing
root-topology residuals monotone nonincreasing
one successful-domain root bracket for each accepted refined root
```

The allowed B1-unavailable formal outcomes remained:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
NONPOSITIVE_KINETIC_ENERGY_HEAD
```

Neither outcome was converted into B1 success.

## Numerical condition at the stop

The final accepted state retained:

```text
outlet pressure:
4949835.984027787 Pa

outlet velocity:
+0.11988239287295711 m/s

outlet Mach:
0.0002573609958280351

outlet phase:
liquid

minimum density:
874.2107493787249 kg/m3

minimum internal energy:
216871.9740989991 J/kg

rho*xv exact zero:
true
```

The continuation remained finite, positive, outward, subsonic, and liquid through the last accepted step.

Maximum absolute closure residuals remained small:

```text
step mass:
2.138377026990844e-17 kg

step momentum:
2.256495771485456e-18 kg m/s

step energy:
7.921698019774936e-12 J

cumulative mass:
2.1673879054343037e-17 kg

cumulative momentum:
1.1275702593849246e-17 kg m/s

cumulative energy:
7.082334718688799e-12 J
```

The stop was not caused by nonfinite state, reverse velocity, phase departure, positivity failure, conservation failure, branch chatter, root-tolerance failure, or time-step rejection.

## Correct claim boundary

This baseline establishes only:

> Under the fixed B2-10A case, mesh, CFL, unchanged B1 component, verification-only Guard-front logic, and `0 < chi <= 1.0e-6` Weak Compression v0.1 scope, the actual `FvmSolver` advances from the authoritative step-369 state through accepted step 483 while retaining the fixed minimum working-slice gates. The next requested step requires a finite-compression model outside the current scope.

It does not establish:

```text
full nominal 2L/c0 passage
general finite-compression validity
shock validity
mesh independence
CFL independence
formal convergence order
independent implementation equivalence
acoustic amplitude validation
experimental validation
full B2 finite-pipe Verification
benchmark acceptance
Physical Validation
design-use acceptance
production activation
```

## Formal states

The following remain unchanged:

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

The distinction remains:

```text
WORKING VERTICAL SLICE PARTIALLY EXTENDED
!=
FULL HORIZON REACHED
!=
VERIFIED
!=
ACCEPTED
!=
VALIDATED
!=
APPROVED FOR DESIGN OR PRODUCTION
```

## Next-phase boundary

Weak Compression Bridge v0.1 is now closed at its fixed scope boundary.

The next phase must be fixed separately as a finite-compression MODEL_REVIEW and should begin with diagnostic-only comparison of:

```text
1. continued isentropic characteristic extrapolation outside the approved scope
2. a general-EOS Hugoniot compression locus
3. entropy production and Lax admissibility
4. B1 compatibility-root existence and uniqueness
5. the pressure and chi distance from the current scope cap
```

No finite-compression flux may be applied until that diagnostic and its model-selection review are complete.
