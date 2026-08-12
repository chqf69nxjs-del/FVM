# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4F Guard-front refined continuation

## Status

`MODEL_REVIEW_ONLY / WORKING_VERTICAL_SLICE / GUARD_FRONT_REFINEMENT / FIXED_BEFORE_EXECUTION_RESULT`

This increment applies one narrow verification-only bracketing correction after the corrected Increment 4E diagnostic. It reruns the full-`2L/c0` continuation from the authoritative accepted Increment 3 step-369 artifact.

It does not change B1, disable or reinterpret a B1 success, convert a failed B1 state into a successful state, relax a tolerance, add a pressure tolerance, enlarge the Weak Compression `chi` scope, change the characteristic relation, revise the locked B2 v1 Contract, modify the production B2 Adapter, modify `FvmSolver`, or promote any formal project state.

## Authoritative corrected Increment 4E evidence

```text
source Git SHA:
d88f9c979c594d0db74eee25ed5769e54d04821f

workflow run:
31618287187

job:
94186438807

artifact:
9150166208

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4e-rerun-31618287187

artifact SHA256:
a1bfbee4699cca03b0ddf50c1cf11f4fcdbc9cf066d5d4fbdffd167fd73750f8

outcome:
B1_GUARD_FRONT_REFINED_POSITIVE_ROOT_SUPPORTED
```

The exact accepted step-451 state was diagnosed without advancing `FvmSolver`.

The fixed decade scan retained:

```text
last fixed unavailable offset:
10 Pa

first fixed successful offset:
100 Pa
```

The Guard front was categorically refined for exactly 32 iterations. The midpoint classifications were:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED:
11

NONPOSITIVE_KINETIC_ENERGY_HEAD:
6

B1 success:
15
```

The final categorical bracket was:

```text
final unavailable lower offset:
10.855514390859753 Pa

final successful upper offset:
10.85551441181451 Pa

final bracket width:
2.0954757928848267e-8 Pa

first-success stagnation-pressure margin above back:
8.801929652690887e-6 Pa

first-success compatibility residual:
+0.010661053123812912 kg/s
```

The next higher successful fixed node was:

```text
offset:
100 Pa

compatibility residual:
-0.005148895980200964 kg/s
```

Using only B1-success states as the compatibility-root bracket, the diagnostic found:

```text
root pressure:
4950034.069520573 Pa

root pressure offset:
+51.425090093165636 Pa

root chi:
2.710290787290387e-7

root residual:
-1.4457359736458342e-9 kg/s

root slope:
-1.3152092096080283e-4 kg/(s Pa)

root velocity:
+0.12182982219958605 m/s

root Mach:
0.00026153982639472596

root phase:
liquid

root B1 outcome:
SUCCESS_UNCHOKED_FACE_MAPPING

root stagnation-pressure margin above back:
+40.558970380574465 Pa

restriction-reaction ledger residual:
0.0 N
```

The state remained unchanged and FvmSolver step 452 was not attempted.

## Diagnosis

At the B1 Guard front, a coarse decade scan may contain:

```text
last fixed node below the compatibility root:
B1 unavailable

first fixed B1-success node:
already above the compatibility root
```

In that topology, the absence of a successful-successful sign-change bracket does not show that the Weak Compression root disappeared. It shows that the fixed scan did not resolve the transition from the B1-unavailable domain to the B1-success domain.

The corrected Increment 4E evidence established that:

```text
the refined first B1-success state has positive residual
a higher B1-success state has negative residual
one B1-success-domain root exists inside the unchanged chi scope
```

Therefore Increment 4F adds categorical Guard-front refinement only when the unchanged fixed scan cannot form a successful-domain root bracket.

## Fixed continuation method

### Existing paths remain unchanged

Use the existing Increment 4D logic without modification when:

```text
the endpoint succeeds and the earlier Neutral / Rarefaction / Weak Compression
classification is available

or

the fixed positive-pressure scan already contains exactly one admissible
successful-domain root bracket
```

### Guard-front refinement path

The new path is permitted only when all of the following are true before a candidate step:

```text
endpoint formal outcome is exactly
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED

outlet velocity remains outward
outlet Mach remains subsonic
outlet phase remains liquid
positive density and internal energy
connected Rarefaction domain is unavailable because p_i <= p_back
connected/local Rarefaction root count = 0
fixed positive scan contains leading B1-unavailable nodes
all unavailable nodes precede every successful node
unavailable formal outcomes are limited to:
  REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
  NONPOSITIVE_KINETIC_ENERGY_HEAD
fixed positive scan contains at least one later B1-success state
fixed successful states do not already contain a root bracket
```

Both unavailable outcomes remain failed B1 states. Neither may construct a flux, serve as a compatibility-root state, or serve as a successful root-bracket endpoint.

### Guard-front categorical bisection

Use the last fixed unavailable pressure offset and first fixed successful pressure offset as a categorical bracket.

Run exactly 32 deterministic bisection iterations:

```text
lower update:
midpoint returns one of the two fixed unavailable B1 formal outcomes

upper update:
midpoint B1 evaluation succeeds and the candidate is locally admissible

other result:
fail-closed STOP
```

No pressure or energy tolerance is introduced. Retain requested pressure offsets as the authoritative scan coordinates.

After 32 iterations, the successful upper endpoint is the refined first-success probe.

### Compatibility root

Continuation is permitted only when:

```text
refined first-success residual >= -1.0e-8 kg/s
one higher B1-success state has residual <= +1.0e-8 kg/s
exactly one successful-domain sign-change bracket exists
```

Use the unchanged maximum 32 compatibility-root bisection iterations. Every evaluated root state must independently succeed through the unchanged B1 component and pass all retained admissibility checks.

The selected root must satisfy:

```text
root pressure > back pressure
root stagnation pressure > back pressure
root pressure > interior pressure
0 < chi <= 1.0e-6
absolute root residual <= 1.0e-8 kg/s
negative root residual slope
outward root velocity
0 <= root Mach < 1
liquid phase
B1 success
stagnation-enthalpy round trip
energy/mass consistency
energy-port closure
restriction-reaction ledger closure
```

Only the selected B1-success root constructs the existing pipe-side Euler flux.

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

Guard-front categorical iterations:
32

compatibility-root bisection maximum:
32
```

The first 82 continuation steps through accepted step 451 must reproduce the authoritative failed Increment 4D evidence before Guard-front refinement first activates for requested step 452.

## Required evidence

At minimum, record:

```text
Increment 3 parent authority
corrected Increment 4E authority
failed Increment 4D authority
first 82 continuation rows through step 451 reproduction
first Guard-front refinement activation step
number of Guard-front refinements
per-step unavailable formal-outcome counts
per-step successful midpoint counts
initial and final Guard-front brackets
refined first-success residuals and stagnation-pressure margins
selected higher successful states
selected root pressure and stagnation-pressure margins
root chi, residual, slope, direction, Mach, phase, B1 outcome, and ledgers
accepted dt and halving count
branch sequence and transitions
outlet direction, phase, density, internal energy, and rho*xv identity
mass, momentum, energy, and reaction ledgers
final solver time and horizon fraction
full 2L/c0 target reach status
```

## Working-slice pass gate

A passing result requires:

```text
first 82 continuation steps reproduce the prior failed Increment 4D evidence
Guard-front refinement first activates at requested step 452
all refinement activations satisfy the fixed topology gate
all lower-side states remain failed B1 evaluations
no failed B1 state is used as a root endpoint or applied flux
all selected roots pass the unchanged B1, root, scope, direction, phase,
energy, and reaction-ledger gates
no crash or nonfinite state
positive density and internal energy
no reverse velocity or accepted reverse-flow Guard
liquid phase maintained
rho*xv remains exact zero
no clear five-point branch chatter
all accepted-step and cumulative mass/momentum/energy gates pass
solver reaches the clipped full 2L/c0 target
```

The working-slice outcome token is:

```text
WEAK_COMPRESSION_INCREMENT_4F_FULL_HORIZON_WORKING_SLICE_PASS
```

## Immediate stop conditions

```text
parent or authority mismatch
pre-refinement step reproduction mismatch
refinement activates before requested step 452
endpoint failure is not the exact retained reverse-pressure Guard
Rarefaction-side root present
unavailable formal outcome outside the fixed two-outcome set
successful node followed by an unavailable node in pressure order
no successful positive-pressure domain
Guard-front categorical bisection failure
refined first-success residual < -1.0e-8 kg/s
  -> ROOT_LIES_INSIDE_B1_GUARD_DOMAIN
successful residual remains positive through chi cap
  -> FINITE_COMPRESSION_MODEL_REQUIRED
multiple roots
selected root pressure or stagnation pressure not above back
root, B1, direction, phase, positivity, or ledger failure
reverse flow
clear branch chatter
full-horizon operational step cap exceeded
```

Do not enlarge `chi_max`, change B1, or add a tolerance to obtain passage.

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

A pass means only that the B2-10A MODEL_REVIEW / WORKING_VERTICAL_SLICE reached the nominal full acoustic horizon under the fixed Guard-front refinement.
