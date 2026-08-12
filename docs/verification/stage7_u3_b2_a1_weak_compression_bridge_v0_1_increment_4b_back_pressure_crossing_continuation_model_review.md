# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4B back-pressure crossing continuation

## Status

`MODEL_REVIEW_ONLY / WORKING_VERTICAL_SLICE / BRANCH_DOMAIN_CORRECTION / FIXED_BEFORE_EXECUTION_RESULT`

This increment applies one narrow verification-only branch-domain correction after the Increment 4A diagnostic. It reruns the Increment 4 full-`2L/c0` continuation from the authoritative accepted Increment 3 step-369 artifact.

It does not change the locked B2 v1 Contract, B1 equations or guards, the production B2 Adapter, `FvmSolver`, the root tolerance, the fixed Weak Compression `chi` scope, the positive-pressure scan sequence, the bisection limit, the pipe-side Euler flux law, or any formal project state.

## Authoritative Increment 4A evidence

```text
source Git SHA:
bee4b753bf6ab3563f57f82aceb9012fcfc82111

workflow run:
31614026739

job:
94172200536

artifact:
9148419818

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4a-31614026739

artifact SHA256:
0db60a1c3b3d0a3d42adf1627d170df6085267ac5ade484682e9925475e54cfe

outcome:
BACK_PRESSURE_CROSSING_BRANCH_DOMAIN_CORRECTION_SUPPORTED
```

The exact accepted step-443 state was diagnosed without advancing `FvmSolver`:

```text
outlet static pressure:
4949999.458183482 Pa

back pressure:
4950000.0 Pa

static-pressure margin:
-0.5418165177106857 Pa

outlet stagnation pressure:
4950005.982901173 Pa

stagnation-pressure margin:
+5.982901172712445 Pa

outlet velocity:
+0.12216061588858795 m/s

outlet Mach:
0.0002622502898547208

outlet phase:
liquid

neutral endpoint residual:
+0.00659056855273247 kg/s

connected rarefaction requested/admissible nodes:
0 / 0

local rarefaction-side root brackets:
0

positive-pressure root brackets:
1

candidate Weak Compression root pressure:
4950034.20694752 Pa

candidate root pressure offset:
+34.74876403808594 Pa

candidate root chi:
1.831384879413157e-7

candidate root residual:
-7.976138846621517e-11 kg/s

candidate root slope:
-1.3125672396063336e-4 kg/(s Pa)

candidate root B1 outcome:
SUCCESS_UNCHOKED_FACE_MAPPING

candidate root reaction-ledger residual:
0.0 N
```

The conserved state remained unchanged and FvmSolver step 444 was not attempted.

## Diagnosis

The Increment 4 stop was caused by two verification-implementation preconditions inherited from the earlier `p_i > p_back` regime:

```text
1. The branch classifier required at least two connected-rarefaction scan nodes
   before evaluating the positive-pressure Weak Compression scan.

2. The verification-only Weak Compression context required outlet-cell static
   pressure to be above back pressure even when outlet stagnation pressure,
   the candidate boundary state, B1, direction, phase, and ledgers remained
   admissible.
```

At step 443, there is no ordered connected-rarefaction interval from `p_i` downward to `p_back` because `p_i <= p_back`. Increment 4A found no local rarefaction-side root and found one admissible positive-pressure Weak Compression root. Therefore this topology is treated as `RAREFACTION_DOMAIN_UNAVAILABLE`, not as a root or conservation failure.

## Fixed correction

The correction is active only when all of the following are true before a candidate step:

```text
neutral endpoint evaluation succeeds
neutral endpoint is locally admissible
neutral endpoint is outside the unchanged root tolerance
outlet static pressure <= retained back pressure
outlet stagnation pressure > retained back pressure
outlet velocity is outward
outlet Mach is subsonic
outlet phase remains in the allowed liquid scope
connected rarefaction scan has zero nodes because p_i <= p_back
connected rarefaction sign-change count = 0
local rarefaction-side admissible sign-change count = 0
```

In this topology:

```text
connected Rarefaction is classified as unavailable
positive-pressure scan is evaluated without changing its nodes or chi scope
exactly one admissible positive-pressure bracket is required
unchanged bisection is applied
```

The Weak Compression context replaces only the verification-only interior-static-pressure precondition:

```text
old precondition:
p_i > p_back

corrected precondition for this topology:
p_0,i > p_back
```

The selected boundary root must additionally satisfy:

```text
p_P > p_back
p_P > p_i
0 < chi <= 1.0e-6
absolute root residual <= 1.0e-8 kg/s
negative local residual slope
outward root velocity
0 <= root Mach < 1
allowed liquid phase
B1 success
stagnation-enthalpy round trip
energy/mass consistency
energy-port closure
restriction-reaction ledger closure
```

When `p_i > p_back`, the existing unmodified three-branch implementation is used. The correction may not alter any accepted step before the back-pressure crossing.

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

authoritative continuation parent:
Increment 3 corrected artifact 9144936292

parent solver step:
369

parent solver time:
0.0024719939763977834 s

target full 2L/c0:
0.004285834855172021 s

maximum operational solver step:
10000

root mass residual absolute tolerance:
1.0e-8 kg/s

Weak Compression scope:
0 < chi <= 1.0e-6

maximum bisection iterations:
32
```

The first 74 continuation steps through accepted step 443 must reproduce the authoritative failed Increment 4 evidence before the correction is activated for requested step 444.

## Required evidence

At minimum, record:

```text
Increment 3 parent artifact identity and internal manifest verification
Increment 4A authority identity
first 74 continuation rows through step 443 reproduction
first correction activation step
number of correction-activated roots
static- and stagnation-pressure margins at each corrected root
rarefaction-domain availability classification
branch sequence and transitions
positive scan and root evidence
accepted dt and halving count
outlet direction, Mach, phase, density, and internal energy
mass, momentum, energy, and reaction ledgers
rho*xv exact-zero identity
final solver time and horizon fraction
full 2L/c0 target reach status
```

## Working-slice pass gate

A passing result requires:

```text
first 74 continuation steps reproduce the prior Increment 4 evidence
correction first activates no earlier than requested step 444
all correction activations satisfy the fixed topology gate
all selected corrected roots pass the unchanged root and ledger gates
no crash or nonfinite state
positive density and internal energy
no reverse velocity or reverse-flow Guard
liquid phase maintained
rho*xv remains exact zero
no clear five-point branch chatter
all accepted-step and cumulative mass/momentum/energy gates pass
solver reaches the clipped full 2L/c0 target
```

The working-slice outcome token is:

```text
WEAK_COMPRESSION_INCREMENT_4B_FULL_HORIZON_WORKING_SLICE_PASS
```

## Immediate stop conditions

```text
parent or Increment 4A authority mismatch
pre-crossing step reproduction mismatch
correction activates while p_i > p_back
stagnation pressure not above back pressure
local or connected rarefaction root present in corrected topology
no unique positive-pressure root
multiple roots
Weak Compression chi scope exceeded
root, B1, direction, phase, positivity, or ledger failure
reverse flow
clear branch chatter
full-horizon operational step cap exceeded
```

No tolerance, Contract, production source, or formal state may be changed to obtain a passing result.

## Formal-state boundary

Even if the working slice reaches full `2L/c0`, retain:

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

A pass means only that the B2-10A MODEL_REVIEW / WORKING_VERTICAL_SLICE reached the nominal full acoustic horizon under the fixed branch-domain correction.
