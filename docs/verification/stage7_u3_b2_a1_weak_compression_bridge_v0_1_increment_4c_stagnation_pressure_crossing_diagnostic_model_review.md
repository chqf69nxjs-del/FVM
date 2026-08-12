# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4C stagnation-pressure crossing diagnostic

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_ONLY / FIXED_BEFORE_EXECUTION_RESULT`

This increment diagnoses the fail-closed stop immediately before requested solver step 448 in the first Increment 4B continuation. It does not advance `FvmSolver`, change a branch law, relax a tolerance, revise the locked B2 v1 Contract, modify B1, modify the production B2 Adapter, modify `FvmSolver`, promote a formal state, or approve a finite-compression model.

## Authoritative parent evidence

```text
source Git SHA:
532ba7388915e8d484aae5a65de87dc760c200aa

workflow run:
31614869209

job:
94175042813

artifact:
9148819125

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4b-31614869209

artifact SHA256:
71f1e2bfa2959f526466a0effbfd8daaa50e56d416f37697679d829b69c26437

accepted continuation:
solver step 369 -> 447
78 additional accepted steps

solver time after step 447:
0.002995130267713174 s

full 2L/c0 target:
0.004285834855172021 s

horizon fraction reached:
0.6988440686413144

stop before requested solver step:
448

stop reason:
neutral endpoint evaluation did not succeed
```

## Accepted-state observations before the stop

The correction introduced in Increment 4B first activated at requested step 444. Steps 444 through 447 were accepted with the branch classified as `WEAK_COMPRESSION`.

The last accepted step retained:

```text
accepted solver step:
447

accepted dt:
6.706888059277248e-6 s

outlet pressure after step:
4949991.7454562355 Pa

retained back pressure:
4950000.0 Pa

outlet static-pressure margin:
-8.254543764516711 Pa

outlet velocity after step:
+0.12206804832113326 m/s

outlet Mach after step:
0.0002620516418539126

outlet phase:
liquid

rho*xv exact zero:
true

step mass residual:
6.4194509490035295e-18 kg

step momentum residual:
1.3552527156068804e-20 kg m/s

step energy residual:
-9.499172282101398e-13 J

cumulative mass residual:
1.0123737785583399e-17 kg

cumulative momentum residual:
-8.673617379884035e-18 kg m/s

cumulative energy residual:
-2.3412383143295297e-12 J
```

The selected step-447 Weak Compression root before the accepted update was:

```text
interior static-pressure margin:
-6.203082278370857 Pa

interior stagnation-pressure margin:
+0.31440282333642244 Pa

root pressure:
4950034.161240894 Pa

root pressure margin above back:
+34.16124089434743 Pa

root pressure offset above the interior:
+40.364322662353516 Pa

root chi:
2.1273459544390068e-7

root residual:
+5.1734589490153304e-9 kg/s

root slope:
negative

root velocity:
positive

root Mach:
subsonic

root phase:
liquid

B1 outcome:
SUCCESS_UNCHOKED_FACE_MAPPING
```

Thus the Increment 4B correction itself advanced four accepted steps while retaining the fixed Weak Compression scope, direction, phase, positivity, conservation, and ledgers.

## New diagnostic question

At the final accepted step-447 state, the outlet static pressure remains below back pressure and the next neutral endpoint evaluation fails before a positive-pressure scan is attempted.

The likely new topology is:

```text
p_i <= p_back
p_0,i <= p_back
u_i > 0
```

In this topology, B1 is expected to refuse the unmodified endpoint candidate because its stagnation pressure does not exceed back pressure. That endpoint refusal does not by itself prove that every pressure state on the incoming weak-compression characteristic is inadmissible.

Increment 4C tests, without advancing the solver, whether:

```text
the endpoint and the first small positive-pressure scan nodes are unavailable
because B1 correctly applies its unchanged reverse-pressure Guard,

but

a larger positive-pressure state within the unchanged chi scope restores
p_0,P > p_back and contains one admissible B1-compatible root.
```

This is a diagnostic question only. A positive result does not authorize continuation.

## Fixed diagnostic method

Load and verify the authoritative failed Increment 4B artifact and reconstruct its exact accepted step-447 final state.

Evaluate:

```text
1. outlet conserved and reconstructed state identity
2. outlet static and stagnation pressure relative to back pressure
3. outlet direction, Mach, phase, density, and internal energy
4. the neutral endpoint evaluation and exact B1 formal outcome
5. the connected/local rarefaction-domain topology
6. the unchanged positive-pressure scan from Delta-p = 0 through chi_max
```

For the positive-pressure scan only:

```text
- retain the requested Delta-p / requested chi coordinate correction
- record every scan node
- permit a leading sequence of failed nodes only when B1 returns exactly
  REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
- no successful node may be followed by another failed node
- all successful nodes must be locally admissible, finite, outward,
  subsonic, liquid, and inside the fixed chi scope
- root bracketing uses successful admissible nodes only
```

The first successful scan node must have stagnation pressure above back pressure. No B1 guard is disabled or changed.

If exactly one admissible positive-pressure sign-change bracket exists, use the unchanged maximum 32-step bisection and complete the root with the retained root, energy, phase, direction, and reaction-ledger checks.

## Fixed execution scope

```text
case:
B2-10A_FINITE_PIPE_LIQUID_INVENTORY_CLOSURE

cells:
32

CFL:
0.10

accepted state loaded:
solver step 447

next requested solver step:
448

root mass residual absolute tolerance:
1.0e-8 kg/s

Weak Compression chi scope:
0 < chi <= 1.0e-6

positive-pressure scan:
unchanged decade sequence plus fixed chi cap

maximum bisection iterations:
32
```

No tolerance, scan node, root rule, or scope may be changed after observing the result.

## Required evidence

At minimum, record:

```text
parent artifact identity and internal SHA256 manifest verification
solver step and solver time identity
outlet conserved-state SHA256
outlet static pressure and margin above back
outlet stagnation pressure and margin above back
outlet velocity, Mach, phase, density, and internal energy
endpoint evaluation_succeeded, formal outcome, and formal message
connected rarefaction requested/admissible nodes and stop reason
local rarefaction-side root count
all positive-pressure scan rows
number and pressure range of expected leading B1 Guard nodes
first successful positive-pressure node
successful-node residual monotonicity
positive-pressure sign-change count
selected root pressure, pressure offset, chi, residual, slope, velocity,
Mach, phase, B1 outcome, stagnation-pressure margin, and ledgers
confirmation that FvmSolver step 448 was not attempted
confirmation that the state remained unchanged
```

## Diagnostic classifications

### `STAGNATION_PRESSURE_CROSSING_POSITIVE_ROOT_SUPPORTED`

This classification requires all of the following:

```text
parent artifact and exact state reproduction pass
outlet static pressure <= back pressure
outlet stagnation pressure <= back pressure
outlet velocity remains outward
outlet Mach remains subsonic
outlet phase remains liquid
positive density and internal energy
neutral endpoint evaluation fails exactly with
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
connected rarefaction domain is unavailable
local rarefaction-side admissible root count = 0
positive-pressure scan begins with one or more expected B1 Guard nodes
all failed nodes precede all successful nodes
all successful scan nodes are admissible and inside chi scope
the first successful node has stagnation pressure > back pressure
successful-node residuals are monotone nonincreasing
exactly one admissible positive-pressure root bracket exists
selected root pressure > back pressure
selected root stagnation pressure > back pressure
0 < root chi <= 1.0e-6
absolute root residual <= 1.0e-8 kg/s
negative root residual slope
outward root velocity
0 <= root Mach < 1
root phase remains liquid
B1 succeeds
stagnation-enthalpy, energy/mass, energy-port, and reaction ledgers close
state remains unchanged
FvmSolver step 448 is not attempted
```

A passing result means only that the step-448 stop is consistent with an endpoint-classification precondition and that the unchanged B1 component admits one positive-pressure boundary root. It does not authorize an actual step.

### `STAGNATION_PRESSURE_CROSSING_REQUIRES_PHYSICS_REVIEW`

Return this classification when the endpoint failure is not the exact retained B1 reverse-pressure Guard, a rarefaction-side root exists, the positive scan never becomes admissible, no unique positive root exists, the required root leaves the Weak Compression scope, or any direction, phase, positivity, B1, root, energy, or reaction check fails.

### Fail-closed classifications

```text
PARENT_ARTIFACT_MISMATCH
STATE_REPRODUCTION_MISMATCH
NONFINITE_OR_NONPOSITIVE_STATE
UNEXPECTED_ENDPOINT_OUTCOME
RAREFACTION_ROOT_PRESENT
UNEXPECTED_POSITIVE_SCAN_FAILURE
POSITIVE_SCAN_SUCCESS_THEN_FAILURE
NO_ADMISSIBLE_POSITIVE_SCAN_DOMAIN
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

Only a passing `STAGNATION_PRESSURE_CROSSING_POSITIVE_ROOT_SUPPORTED` result may support a later, separately fixed continuation increment. Any later correction must remain verification-only, preserve the B1 Guard unchanged, and apply the B1 component only to candidate boundary states that individually satisfy its original admissibility rules.
