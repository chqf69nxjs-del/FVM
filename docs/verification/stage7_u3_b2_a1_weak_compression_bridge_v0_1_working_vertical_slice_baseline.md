# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 working vertical slice baseline

## Status

`WORKING_VERTICAL_SLICE_BASELINE_FIXED / FULL_NOMINAL_2L_OVER_C0_REACHED / NOT_FORMALLY_VERIFIED`

This record fixes the first B2-10A branch-aware full-horizon working vertical slice as a reproducible development baseline.

It does not approve a general finite-compression model, verify single-phase finite-pipe coupling, accept the B2 benchmark, perform Physical Validation, approve design use, or activate production behavior.

## Authoritative evidence

```text
repository:
chqf69nxjs-del/FVM

branch:
agent/u3-b2-a1-wave-curve-review

source Git SHA:
3b533595f0f2ef22256961dcb7be7197738371d4

workflow:
Agent U3 B2 A1 Weak Compression Bridge Increment 4F Root Topology Rerun

workflow run:
31621090806

job:
94195575335

artifact:
9151318681

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4f-root-topology-31621090806

artifact SHA256:
83786020fb9f3038121c45dd87f2e799d9b3bf6c7d0fc6c614d972d8029e5dbc

outcome:
WEAK_COMPRESSION_INCREMENT_4F_FULL_HORIZON_WORKING_SLICE_PASS
```

The workflow completed source/scope checks, downloaded and verified its authoritative parent artifacts, executed the actual `FvmSolver` continuation, inspected the resulting evidence, verified every internal artifact SHA256 entry, and uploaded the authoritative evidence artifact.

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

## Result

The authoritative Increment 3 state was loaded at:

```text
solver step:
369

solver time:
0.0024719939763977834 s
```

The corrected continuation reached:

```text
solver step:
639

additional accepted steps:
270

solver time:
0.004285834855172023 s

horizon fraction:
1.0000000000000004

horizon time error:
1.734723475976807e-18 s

retained roundoff allowance:
6.938893903907228e-18 s

final step clipped to target:
true
```

Therefore the actual `FvmSolver` reached the nominal full `2L/c0` target within the retained floating-point roundoff allowance.

Together with the authoritative Increment 3 continuation, accepted solver steps 338 through 639 form 302 post-Neutral Weak Compression steps after the accepted step-337 Neutral endpoint.

## Branch behavior

The continuation retained:

```text
accepted continuation branch:
WEAK_COMPRESSION

continuation branch transitions:
0

clear five-point branch chatter:
false
```

The maximum selected Weak Compression strength was:

```text
maximum chi:
9.383657148556149e-7

fixed chi limit:
1.0e-6
```

The maximum selected root pressure offset was:

```text
178.16954076942056 Pa
```

The maximum absolute selected root mass residual was:

```text
9.949153223165696e-9 kg/s
```

which remained inside the unchanged absolute root tolerance:

```text
1.0e-8 kg/s
```

No `chi` limit or root tolerance was relaxed to obtain the pass.

## Guard-front refinement

The first Guard-front root-topology refinement activated at requested solver step:

```text
452
```

It remained active through the final requested step 639, for 188 accepted refined roots.

Each refined step retained:

```text
B1-unavailable categorical evidence on the lower side
B1-success and locally admissible evidence on the upper side
exactly 32 categorical Guard-front iterations
failed B1 states excluded from compatibility-root endpoints
failed B1 states excluded from applied fluxes
final refined first-success state plus higher fixed successful states used
for compatibility-root topology
strictly increasing topology pressure coordinates
monotone nonincreasing topology residuals
exactly one successful-domain root bracket
```

The retained B1-unavailable formal outcomes were limited to:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
NONPOSITIVE_KINETIC_ENERGY_HEAD
```

Both remained failed B1 evaluations. Neither was converted to success.

The root-topology correction retained every fixed scan and categorical-bisection row in the evidence while separating intermediate refinement evidence from the final compatibility-root topology.

## Physical and numerical minimum gates

Every accepted continuation step retained the working-slice gates:

```text
finite conserved state
positive density
positive internal energy
outward outlet velocity
subsonic selected root and outlet
liquid phase
rho*xv exact zero
B1 success at every selected root
root residual inside 1.0e-8 kg/s
negative local root slope
stagnation-enthalpy round trip passed
energy/mass consistency passed
energy-port closure passed
restriction-reaction ledger closure passed
step and cumulative mass closure passed
step and cumulative momentum closure passed
step and cumulative energy closure passed
no clear branch chatter
```

The final state retained:

```text
outward outlet velocity
subsonic outlet Mach number
liquid outlet phase
positive minimum density
positive minimum internal energy
rho*xv exact zero
```

## Reproduction boundary

The run reproduced the first 82 accepted continuation rows through solver step 451 exactly against the authoritative failed Increment 4D evidence before first applying Guard-front root-topology refinement at requested step 452.

The parent, corrected Increment 4E, failed Increment 4D, and failed Increment 4F authorities were independently retained and inspected. Existing failed evidence was not overwritten.

## Claim boundary

This baseline establishes only:

> Under the fixed B2-10A case, mesh, CFL, single-phase liquid scope, Weak Compression `chi` scope, unchanged B1 component, and verification-only branch logic, the actual `FvmSolver` can be advanced from the authoritative step-369 state to the nominal full `2L/c0` horizon while retaining the fixed minimum working-slice gates.

It does not establish:

```text
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
WORKING VERTICAL SLICE REACHED
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

Development stops at this baseline before adding further physics or formal promotion.

The next phase should begin with a separately fixed Verification plan that prioritizes:

```text
1. independent reproduction of the selected boundary-root sequence
2. targeted mesh/CFL characterization
3. direct and reflected acoustic timing checks using the retained probe series
4. review of the verification-only branch logic before any production integration
5. explicit B2 finite-pipe closeout criteria
```

No production Adapter or `FvmSolver` change is authorized by this baseline.
