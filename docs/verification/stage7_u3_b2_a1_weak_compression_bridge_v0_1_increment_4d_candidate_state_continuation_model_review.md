# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4D candidate-state continuation

## Status

`MODEL_REVIEW_ONLY / WORKING_VERTICAL_SLICE / CANDIDATE_STATE_CLASSIFICATION / FIXED_BEFORE_EXECUTION_RESULT`

This increment applies one narrow verification-only classification correction after the Increment 4C diagnostic. It reruns the full-`2L/c0` continuation from the authoritative accepted Increment 3 step-369 artifact.

It does not change the locked B2 v1 Contract, B1 equations or guards, the production B2 Adapter, `FvmSolver`, the root tolerance, the Weak Compression `chi` scope, the positive-pressure scan sequence, the maximum 32 bisection iterations, the characteristic relation, the pipe-side Euler flux law, or any formal project state.

## Authoritative Increment 4C evidence

```text
source Git SHA:
2edd55307658e578f880bf99e661fee6753be874

workflow run:
31615812004

job:
94178201383

artifact:
9149147400

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4c-31615812004

artifact SHA256:
260806e46275ff0c5d3bf6b1acd45bfd0f93268743a684342b92e00511f5e80e

outcome:
STAGNATION_PRESSURE_CROSSING_POSITIVE_ROOT_SUPPORTED
```

The exact accepted step-447 state was diagnosed without advancing `FvmSolver`:

```text
outlet static pressure:
4949991.7454562355 Pa

static-pressure margin relative to back:
-8.254543764516711 Pa

outlet stagnation pressure:
4949998.260289005 Pa

stagnation-pressure margin relative to back:
-1.7397109949961305 Pa

outlet velocity:
+0.12206804832113326 m/s

outlet Mach:
0.0002620516418539126

outlet phase:
liquid

endpoint evaluation:
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED

endpoint message:
Back pressure exceeds upstream pressure.

connected rarefaction requested/admissible nodes:
0 / 0

local rarefaction-side root brackets:
0
```

The unchanged positive-pressure scan returned:

```text
leading expected B1 Guard nodes:
6

Guard offset range:
0 through 1 Pa

first successful positive-pressure offset:
10 Pa

first successful stagnation pressure:
4950008.257687358 Pa

successful scan nodes:
3

positive-pressure root brackets:
1

residual sequence:
monotone nonincreasing
```

The selected diagnostic-only root was:

```text
root pressure:
4950034.14456703 Pa

root pressure offset:
+42.39911079406738 Pa

root chi:
2.234587011476356e-7

root residual:
+6.563213462290607e-10 kg/s

root slope:
-1.3137642886229105e-4 kg/(s Pa)

root velocity:
+0.12196395760291068 m/s

root Mach:
0.00026182778269844475

root phase:
liquid

root B1 outcome:
SUCCESS_UNCHOKED_FACE_MAPPING

root stagnation-pressure margin above back:
+40.64831479266286 Pa

restriction-reaction ledger residual:
0.0 N
```

The conserved state remained unchanged and FvmSolver step 448 was not attempted.

## Diagnosis

B1 correctly refuses the unmodified endpoint state when its stagnation pressure does not exceed back pressure. That Guard remains authoritative and must not be disabled.

For a subsonic FVM boundary, however, the selected boundary state is not required to equal the adjacent-cell endpoint. Increment 4C found that the same outgoing pipe characteristic reaches a later positive-pressure state that individually satisfies the unchanged B1 admissibility rules and all retained root, direction, phase, energy, and reaction-ledger checks.

Therefore the endpoint B1 result is treated as classification evidence, not as an unconditional rejection of every candidate boundary state.

## Fixed correction

When the neutral endpoint evaluation succeeds, use the existing Increment 4B implementation without modification.

When the neutral endpoint evaluation fails, the new path is permitted only when all of the following are true:

```text
endpoint formal outcome is exactly
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED

outlet static pressure <= back pressure
outlet stagnation pressure <= back pressure
outlet velocity remains outward
outlet Mach remains subsonic
outlet phase remains liquid
positive density and internal energy
connected rarefaction domain is unavailable because p_i <= p_back
connected rarefaction root count = 0
local rarefaction-side admissible root count = 0
```

The positive-pressure scan then:

```text
uses the unchanged decade nodes and fixed chi cap
retains requested Delta-p / requested chi for scope bookkeeping
records leading B1 Guard nodes without accepting or using them
requires every failed node to precede every successful node
requires all failed nodes to return exactly the retained reverse-pressure Guard
requires at least two later successful admissible nodes
requires exactly one successful admissible sign-change bracket
uses the unchanged maximum 32 bisection iterations
```

B1 is evaluated normally at every candidate state. No Guard result is converted to success.

The selected root must individually satisfy:

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

Only the selected successful root constructs the pipe-side Euler flux.

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

The first 78 continuation steps through accepted step 447 must reproduce the authoritative failed Increment 4B evidence before the candidate-state correction is activated for requested step 448.

## Required evidence

At minimum, record:

```text
Increment 3 parent authority
Increment 4C authority
failed Increment 4B authority
first 78 continuation rows through step 447 reproduction
first candidate-state correction activation step
number of candidate-state correction roots
endpoint B1 outcome for each corrected step
leading Guard-node count and pressure range
first successful candidate pressure and stagnation pressure
selected root pressure and stagnation-pressure margins
branch sequence and transitions
root chi, residual, slope, direction, Mach, phase, and B1 outcome
accepted dt and halving count
outlet direction, phase, density, internal energy, and rho*xv identity
mass, momentum, energy, and reaction ledgers
final solver time and horizon fraction
full 2L/c0 target reach status
```

## Working-slice pass gate

A passing result requires:

```text
first 78 continuation steps reproduce the prior failed Increment 4B evidence
candidate-state correction first activates at requested step 448
all correction activations satisfy the fixed topology gate
all leading failed scan nodes retain the exact B1 reverse-pressure Guard
all selected candidate roots pass the unchanged root and ledger gates
no crash or nonfinite state
positive density and internal energy
no reverse velocity or reverse-flow Guard at an accepted root
liquid phase maintained
rho*xv remains exact zero
no clear five-point branch chatter
all accepted-step and cumulative mass/momentum/energy gates pass
solver reaches the clipped full 2L/c0 target
```

The working-slice outcome token is:

```text
WEAK_COMPRESSION_INCREMENT_4D_FULL_HORIZON_WORKING_SLICE_PASS
```

## Immediate stop conditions

```text
parent or authority mismatch
pre-correction step reproduction mismatch
correction activates before requested step 448
endpoint failure is not the exact retained B1 reverse-pressure Guard
rarefaction-side root present
failed positive scan node appears after a successful node
no successful positive-pressure domain
no unique positive-pressure root
multiple roots
Weak Compression chi scope exceeded
selected root pressure or stagnation pressure not above back
root, B1, direction, phase, positivity, or ledger failure
reverse flow
clear branch chatter
full-horizon operational step cap exceeded
```

If the root reaches the fixed `chi` limit before full horizon, stop with `FINITE_COMPRESSION_MODEL_REQUIRED`. Do not enlarge the Weak Compression scope to obtain passage.

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

A pass means only that the B2-10A MODEL_REVIEW / WORKING_VERTICAL_SLICE reached the nominal full acoustic horizon under the fixed candidate-state classification correction.
