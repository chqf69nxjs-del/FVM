# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4E B1 Guard-front root diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

This increment diagnoses the fail-closed stop immediately before requested solver step 452 in the first Increment 4D candidate-state continuation. It does not advance `FvmSolver`, change B1, disable a B1 Guard, relax a tolerance, enlarge the Weak Compression scope, revise the locked B2 v1 Contract, modify the production B2 Adapter, modify `FvmSolver`, promote a formal state, or approve a finite-compression model.

## Authoritative parent evidence

```text
source Git SHA:
cb56cfa0f856dc8f1ebe1463eeb80f2a269aa2a8

workflow run:
31616654684

job:
94181021964

artifact:
9149565073

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4d-31616654684

artifact SHA256:
a24c491035bbe296b9ad2cc128fc98302025cc90a03f1bda190ee4d9cb5dbd0c

accepted continuation:
solver step 369 -> 451
82 additional accepted steps

solver time after step 451:
0.003021957828880739 s

full 2L/c0 target:
0.004285834855172021 s

horizon fraction reached:
0.7051036568135441

stop before requested solver step:
452

stop reason:
no in-scope candidate-state positive root was found
```

## Accepted-state observations before the stop

The candidate-state correction introduced in Increment 4D accepted requested steps 448 through 451. The last accepted step retained:

```text
outlet pressure after step 451:
4949982.64443048 Pa

retained back pressure:
4950000.0 Pa

outlet static-pressure margin:
-17.355569519214332 Pa

outlet velocity after step:
+0.12195607191279084 m/s

outlet Mach after step:
0.0002618113405926055

outlet phase:
liquid

rho*xv exact zero:
true

maximum accepted Weak Compression chi through step 451:
2.584058200156504e-7

fixed chi limit:
1.0e-6

maximum halving count:
0
```

The selected step-451 root before the accepted update was:

```text
interior static pressure:
4949985.059636723 Pa

interior static-pressure margin:
-14.94036327674985 Pa

interior stagnation-pressure margin:
-8.434278888627887 Pa

root pressure:
4950034.089597356 Pa

root static-pressure margin above back:
+34.08959735557437 Pa

root stagnation-pressure margin above back:
+40.58286795578897 Pa

root pressure offset:
+49.02996063232422 Pa

root chi:
2.584058200156504e-7

root residual:
-3.247740940764965e-9 kg/s

root velocity:
+0.12186568882590718 m/s

root Mach:
0.00026161682337584607

root phase:
liquid

B1 outcome:
SUCCESS_UNCHOKED_FACE_MAPPING

restriction-reaction ledger residual:
0.0 N
```

The continuation remained liquid, outward, positive, conservative, and free of clear branch chatter through accepted step 451.

## Observed scan-topology problem

At accepted step 451, the fixed decade scan used for requested step 451 showed:

```text
Delta-p = 10 Pa:
B1 success
compatibility residual = +0.008573394136719089 kg/s

Delta-p = 100 Pa:
B1 success
compatibility residual = -0.005359102428308693 kg/s
```

and therefore bracketed the accepted root near `49 Pa`.

After the next accepted update, the outlet static and stagnation pressures decrease further. The requested-step-452 stop occurred before any root was selected. The likely topology is:

```text
Delta-p = 10 Pa:
still inside the exact B1 reverse-pressure Guard domain

Delta-p = 100 Pa:
B1 success, but residual already negative
```

In that topology the physical candidate root may remain between `10` and `100 Pa`, but the fixed decade scan contains no successful admissible node below it. The absence of a successful-successful sign-change bracket would then be a bracketing-resolution problem at the B1 Guard front, not evidence that the fixed Weak Compression root or chi scope has disappeared.

Increment 4E tests this hypothesis without advancing the solver.

## Fixed diagnostic method

Load and verify the authoritative failed Increment 4D artifact and reconstruct its exact accepted step-451 final state.

### 1. Retain the existing positive-pressure scan

Run the unchanged requested-coordinate positive scan:

```text
Delta-p =
0,
1e-4,
1e-3,
1e-2,
1e-1,
1,
10,
100 Pa,
and the fixed chi cap when distinct
```

Record all nodes. Failed nodes are permitted only when they return exactly:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
```

All failed nodes must precede all successful nodes.

### 2. Identify the B1 Guard-front bracket

Require:

```text
last fixed Guard node < first fixed successful node
```

Use those two requested pressure offsets as a categorical Guard-to-success bracket.

### 3. Refine only the Guard front

Apply deterministic bisection for exactly 32 iterations to the pressure offset interval:

```text
lower endpoint:
exact retained B1 Guard

upper endpoint:
B1 success and locally admissible
```

At each midpoint, evaluate the unchanged characteristic state and unchanged B1 component.

Update:

```text
lower = midpoint only when the exact retained B1 Guard is returned
upper = midpoint only when B1 succeeds and the candidate is locally admissible
```

Any other failure is fail-closed. If a successful midpoint is followed by a Guard midpoint only because the interval update moves downward, that is expected; the categorical lower/upper invariant must remain valid. No pressure tolerance is introduced. The successful upper bound after exactly 32 iterations is the refined first-success probe.

Record:

```text
initial and final Guard offsets
initial and final success offsets
final bracket width
first-success stagnation-pressure margin
first-success compatibility residual
```

### 4. Test root availability in the successful B1 domain

The refined successful upper state and the next higher successful fixed scan node are used to test a sign change.

A candidate root is supported only when:

```text
refined first-success residual is positive or inside the unchanged root tolerance
higher successful residual is negative or inside the unchanged root tolerance
exactly one successful admissible sign-change bracket exists
```

Use the unchanged maximum 32 bisection iterations for the compatibility root. Every root-evaluation state must individually pass the unchanged B1 component; a Guard state may not be used as a root-bracket endpoint.

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

accepted state loaded:
solver step 451

next requested solver step:
452

root mass residual absolute tolerance:
1.0e-8 kg/s

Weak Compression chi scope:
0 < chi <= 1.0e-6

Guard-front bisection iterations:
32

root bisection iterations:
maximum 32
```

No tolerance, scope, B1 rule, or accepted physical model may be changed after observing the result.

## Required evidence

At minimum, record:

```text
parent artifact identity and internal SHA256 manifest verification
solver step and time identity
outlet conserved-state SHA256
outlet static and stagnation pressure margins
outlet velocity, Mach, phase, density, and internal energy
endpoint B1 outcome
unchanged fixed positive scan
last fixed Guard node and first fixed success node
all 32 Guard-front bisection rows
final categorical Guard-front bracket width
refined first-success state and residual
successful-domain sign-change count
selected root pressure, pressure offset, chi, residual, slope,
velocity, Mach, phase, B1 outcome, stagnation-pressure margin,
and energy/reaction ledgers
confirmation that FvmSolver step 452 was not attempted
confirmation that the state remained unchanged
```

## Diagnostic classifications

### `B1_GUARD_FRONT_REFINED_POSITIVE_ROOT_SUPPORTED`

This classification requires all of the following:

```text
parent artifact and exact state reproduction pass
outlet velocity remains outward
outlet Mach remains subsonic
outlet phase remains liquid
positive density and internal energy
endpoint returns the exact retained B1 reverse-pressure Guard
connected/local rarefaction root count = 0
fixed positive scan has leading Guard nodes followed by successful nodes
last fixed Guard offset < first fixed success offset
Guard-front bisection retains exact Guard/success endpoints for all 32 iterations
refined successful upper state has stagnation pressure > back pressure
refined successful upper residual is positive or inside root tolerance
a higher successful scan state has negative residual or is inside root tolerance
exactly one successful admissible root bracket exists
root pressure > back pressure
root stagnation pressure > back pressure
0 < root chi <= 1.0e-6
absolute root residual <= 1.0e-8 kg/s
negative root residual slope
outward root velocity
0 <= root Mach < 1
root phase remains liquid
B1 succeeds
stagnation-enthalpy, energy/mass, energy-port, and reaction ledgers close
state remains unchanged
FvmSolver step 452 is not attempted
```

A passing result means only that the step-452 stop was caused by coarse bracketing across the unchanged B1 Guard front and that one B1-admissible Weak Compression root remains. It does not authorize continuation.

### `ROOT_LIES_INSIDE_B1_GUARD_DOMAIN`

Return this classification when the refined first-success residual is already negative beyond the unchanged root tolerance. This means the compatibility zero lies below the first B1-admissible candidate and cannot be used without changing B1 physics. Stop for physics review.

### `FINITE_COMPRESSION_MODEL_REQUIRED`

Return this classification when successful residual remains positive through the fixed chi cap. Do not enlarge `chi_max`.

### Other fail-closed classifications

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
UNEXPECTED_ENDPOINT_OUTCOME
RAREFACTION_ROOT_PRESENT
UNEXPECTED_FIXED_SCAN_FAILURE
NO_GUARD_TO_SUCCESS_BRACKET
GUARD_FRONT_BISECTION_FAILURE
SUCCESS_DOMAIN_NONMONOTONE
MULTIPLE_ROOTS
NO_UNIQUE_WEAK_COMPRESSION_ROOT
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

Only a passing `B1_GUARD_FRONT_REFINED_POSITIVE_ROOT_SUPPORTED` result may support a later, separately fixed continuation increment. Any later correction must retain the exact B1 Guard, use only successful B1 states as compatibility-root bracket endpoints, and preserve the unchanged Weak Compression scope and root tolerance.
