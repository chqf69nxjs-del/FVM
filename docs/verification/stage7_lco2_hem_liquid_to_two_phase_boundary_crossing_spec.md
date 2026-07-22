# Stage 7 — First Liquid-to-Two-Phase Boundary-Crossing Specification

## Status

`PROPOSED; INTERNAL SPECIFICATION REVIEW COMPLETE; HUMAN DESIGN APPROVAL REQUIRED; SPECIFICATION ONLY; NOT IMPLEMENTED`

This document defines the first pure-CO2 HEM increment after the merged dynamic
quality-synchronization work in PRs #59–#62. It is based on `main` commit
`33349ff6c16373443b2626d13c1a867d54275d0a`.

It does not change solver behavior, approve a production HEM path, establish physical
Validation, approve an acoustic accuracy band, or permit design use.

## Objective

Define a narrow first-order verification gate in which every cell starts as a supported
single-phase liquid candidate and at least one cell enters the open liquid-vapor
two-phase region through a conservative FVM update.

The gate must demonstrate that:

- the thermodynamic transition is detected from the updated `rho/e` state;
- raw transition detection occurs before equilibrium-quality projection;
- the raw transition evaluator does not call a transported-quality-sensitive EOS path;
- `rho`, `rho*u`, and `rho*E` remain bitwise unchanged by projection;
- the phase-vapor inventory increase is attributed exactly once to projection;
- endpoint, vapor, critical, solid, unknown, backend-invalid, and solver-guarded states
  fail explicitly;
- a matched negative-control case remains liquid and produces no projection activity.

## Why this gate is different from PRs #61–#62

PRs #61–#62 kept every cell inside the open two-phase region. The current gate changes
the thermodynamic region itself:

```text
supported liquid candidate
        |
        v
open liquid-vapor two-phase state
```

The gate therefore needs separate definitions for:

```text
thermodynamic region
transition event
projection activation
test-evidence strength
```

These definitions must not be collapsed into one quality threshold.

## Existing contracts retained unchanged

### Conservative state

```text
U = [rho, rho*u, rho*E, rho*q]
```

The first three components remain the primary conservative state. The fourth component
is the transported vapor-quality inventory used by the current solver architecture.

### Canonical thermodynamic state

For raw and accepted states:

```text
rho = U[rho]
u   = U[rho*u] / rho
E   = U[rho*E] / rho
e   = E - u^2/2
```

Phase and equilibrium quality are evaluated from this same `rho/e` state. No separate
`p/T` flash, phase-majority vote, or quality-only phase inference is allowed for
transition detection.

A `p/T` pair may be used only to construct or survey candidate initial states. Every
candidate used by the solver must be converted to `rho/e` and re-evaluated through the
canonical path before acceptance.

### Existing phase classes

This specification does not add a new public `PhaseClass`. It retains:

```text
compressed_or_subcooled_liquid
liquid_vapor_two_phase
single_phase_vapor
supercritical
critical_region
solid_or_below_triple_guard
unknown
```

A narrower boundary-region view is derived from the existing `phase_class`, `raw_phase`,
`scope_status`, and equilibrium-quality outputs.

### Existing software-quality convention

The reviewed phase evaluator currently returns:

```text
compressed_or_subcooled_liquid -> q_eq = 0
liquid_vapor_two_phase          -> CoolProp Q in [0, 1]
single_phase_vapor              -> q_eq = 1
```

Therefore `q_eq = 0` alone does not identify the saturated-liquid endpoint. Phase class
must be considered. A compressed liquid candidate and a saturated-liquid endpoint may
both carry software quality zero while representing different thermodynamic regions.

### Existing equilibrium-quality projection

The first implementation reuses `HEMEquilibriumQualityProjection` without changing its
conservative contract:

```text
rho*q <- rho*q_eq
```

while preserving `rho`, `rho*u`, and `rho*E` bitwise.

The projection remains responsible only for quality synchronization. It is not the
transition classifier and it must not alter energy to represent latent heat.

## Current solver constraints retained by this gate

`FvmSolver.step()` applies `check_physical_state()` after the FVM update and after the
source update, before the phase-change slot. The current global guard requires:

```text
all conservative values finite
rho > 0
e >= 0
transported quality within the existing global pre-check range
```

The first crossing case must therefore stay in the current non-negative internal-energy
region at initialization, in every raw update, and after projection. This is a software
integration constraint, not a general thermodynamic statement about real-fluid reference
energy.

This specification does not weaken or bypass `check_physical_state()`. If state-pair
exploration reaches a valid CoolProp state with `e < 0`, that candidate is outside this
first integration gate and requires a separate review of the global solver-state guard.

The formal Case A/B contract begins with exact `q=0` in every cell and requires exact
transported-quality bounds before projection. No new transported-quality limiter or
clipping policy is introduced.

## Step-state definitions

For one transition step, define three states.

### Previous accepted state

```text
U_n_post
```

This is the synchronized state at the end of time step `n`. Its transported quality must
match equilibrium quality within the accepted-state EOS tolerance.

### Raw updated state

```text
U_n1_raw
```

This is the state after the first-order FVM update and any configured physical source,
but before equilibrium-quality projection.

Transition detection uses the thermodynamic state derived from `rho/e` in `U_n1_raw`.
It must not use transported quality as the phase classifier.

The raw transition evaluator must call the reviewed phase/property evaluator directly
from `rho/e`. It must not call `primitive_from_conserved(U_n1_raw)`, because the strict
accepted-state EOS may reject the transported/equilibrium quality mismatch that the
projection is intended to repair.

### Post-projection accepted state

```text
U_n1_post
```

This is the state after `HEMEquilibriumQualityProjection` has synchronized `rho*q`.
Because projection does not change `rho/e`, its thermodynamic region must be identical to
the raw thermodynamic region.

## Derived boundary-region view

Let `q_eq` be the equilibrium quality returned by the existing phase evaluator and let
`endpoint_tolerance` come from the same instantiated
`HEMPhaseClassificationConfig` used by that evaluator.

| derived region | required existing output |
|---|---|
| `LIQUID_CANDIDATE` | `scope_status == supported_candidate` and `phase_class == compressed_or_subcooled_liquid` |
| `SATURATED_LIQUID_ENDPOINT` | supported `liquid_vapor_two_phase` and `q_eq <= endpoint_tolerance` |
| `OPEN_TWO_PHASE` | supported `liquid_vapor_two_phase` and `endpoint_tolerance < q_eq < 1 - endpoint_tolerance` |
| `SATURATED_VAPOR_ENDPOINT` | supported `liquid_vapor_two_phase` and `q_eq >= 1 - endpoint_tolerance` |
| `VAPOR_CANDIDATE` | supported `single_phase_vapor` |
| `GUARDED_OR_INVALID` | guarded, unknown, undefined, non-finite, out-of-range, or backend-failed state |

The derived region is a verification view. It does not replace the public phase-class
contract in this specification increment.

The mapper must reject a required equilibrium quality outside `[0, 1]`. Existing reviewed
endpoint normalization performed inside the phase evaluator within its configured
endpoint tolerance is retained. No additional clipping or reclassification is allowed in
the crossing layer.

## `q=0` endpoint policy

The first gate distinguishes:

```text
LIQUID_CANDIDATE
    phase_class = compressed_or_subcooled_liquid
    q_eq = 0 by the existing software convention

SATURATED_LIQUID_ENDPOINT
    phase_class = liquid_vapor_two_phase
    q_eq = 0 within endpoint tolerance
```

The distinction is based on phase classification, not on the numerical value of quality
alone.

An endpoint-only raw state is recorded as `BOUNDARY_TOUCH`, not as a completed
liquid-to-two-phase crossing.

The current equilibrium sound-speed scaffold deliberately excludes exact `q=0` and
`q=1` endpoints because a centered finite-difference stencil may cross the phase
boundary. Therefore any raw saturated-liquid endpoint cell causes the first integration
gate to fail with:

```text
endpoint_acoustic_closure_not_established
```

This is unconditional for the first integration gate, including a step in which another
cell reaches `OPEN_TWO_PHASE`. The formal acceptance criterion is:

```text
raw endpoint landing count = 0
```

This policy avoids silently inventing an endpoint sound-speed closure.

## Transition-event definitions

The previous region is evaluated from `U_n_post`. The raw region is evaluated from
`U_n1_raw`.

| previous accepted region | raw region | event | first-gate policy |
|---|---|---|---|
| `LIQUID_CANDIDATE` | `LIQUID_CANDIDATE` | `NO_TRANSITION` | allowed |
| `LIQUID_CANDIDATE` | `SATURATED_LIQUID_ENDPOINT` | `BOUNDARY_TOUCH` | classify, then fail the integration gate |
| `LIQUID_CANDIDATE` | `OPEN_TWO_PHASE` | `LIQUID_TO_TWO_PHASE_CROSSING` | target event |
| `SATURATED_LIQUID_ENDPOINT` | `OPEN_TWO_PHASE` | `LIQUID_TO_TWO_PHASE_CROSSING` | unit-test definition only; endpoint is not an accepted FVM state |
| `LIQUID_CANDIDATE` | vapor-side or guarded region | `FORBIDDEN_TRANSITION` | fail-fast |
| `OPEN_TWO_PHASE` | liquid-side region | reverse transition | outside this first gate |
| any supported region | `GUARDED_OR_INVALID` | invalid transition | fail-fast |

A discrete first-order step may move directly from `LIQUID_CANDIDATE` to
`OPEN_TWO_PHASE`; the numerical trajectory is not required to land exactly on the
endpoint.

## Crossing and projection are separate concepts

```text
crossing event
    = thermodynamic region changed from liquid side to open two-phase

projection activation
    = abs(q_eq - q_transport) exceeds projection activation tolerance
```

The solver contract must keep these definitions separate.

For the specially constructed first-crossing capture case, stronger test conditions make
the two cell sets coincide at the first crossing step:

- all cells begin with `rho*q = 0`;
- no physical vapor source is active;
- the fourth-component FVM flux is zero while every accepted cell has `q=0`;
- the runner stops immediately after the first crossing step.

Under those conditions:

```text
first-crossing cell set = projection-applied cell set
```

This equality is a property of the fixed first-crossing test, not a general HEM solver
invariant for later multi-step two-phase transport.

## Tolerance policy and single sources of truth

The crossing implementation must read tolerance values from the instantiated reviewed
configurations. It must not duplicate numeric literals in the classifier, runner, tests,
or artifact writer.

```text
phase endpoint tolerance:
    HEMPhaseClassificationConfig.endpoint_tolerance = 1e-10

projection activation/synchronization tolerance:
    HEMEquilibriumQualitySyncConfig.activation_tolerance = 1e-12

accepted-state EOS quality tolerance:
    reuse the Stage 7 case-level value = 1e-10

minimum crossing evidence quality:
    crossing_evidence_min_quality = 1e-6
```

The actual instantiated values must be recorded in every formal artifact.

### Endpoint tolerance

This tolerance only separates endpoint-classified two-phase states from the open
interior. It does not activate projection and is not a physical nucleation threshold.

The same phase-classification configuration must be used by both the phase evaluator and
the derived-region mapper.

### Projection activation tolerance

This tolerance only decides whether the fourth component is materially changed and
reported as projected. It does not decide whether a phase boundary was crossed.

The runner must obtain the value from the instantiated projection configuration.

### Accepted-state EOS quality tolerance

The verification EOS accepts only synchronized states. Its quality tolerance must not be
tighter than the projection activation tolerance:

```text
projection activation tolerance <= accepted-state EOS quality tolerance
```

The first gate reuses the prior Stage 7 case-level value `1e-10`; it does not introduce a
fourth independent quality tolerance.

### Minimum crossing evidence quality

`crossing_evidence_min_quality` is an integration-test acceptance threshold. It prevents
roundoff-scale endpoint noise from being presented as the principal crossing evidence.
It must not be used inside solver, EOS, projection, or transition-classifier branching.

The final frozen state pair must also produce a finite positive equilibrium sound-speed
candidate. Meeting `crossing_evidence_min_quality` alone does not establish acoustic
evaluability or physical accuracy.

### Transported-quality bounds

The first-order gate retains the current projection precondition:

```text
0 <= q_transport <= 1
```

Any transported overshoot or undershoot fails fast in the crossing/projection path. No
new clipping, floor, ceiling, positivity limiter, or bound tolerance is introduced.

### Budget tolerances

Mass, momentum, energy, and vapor accounting reuse the existing scale-aware budget
checks. No new dimensioned absolute tolerance is scattered through the crossing runner.

## Required processing order

```text
accepted synchronized state U_n_post
        |
        v
existing solver-state pre-check
        |
        v
first-order FVM flux update
        |
        v
existing solver-state pre-check
        |
        v
configured physical source update
        |
        v
existing solver-state pre-check
        |
        v
direct raw rho/e phase and quality evaluation
        |
        v
transition-event classification
        |
        v
HEM equilibrium-quality projection
        |
        v
post-projection invariant and solver-state checks
        |
        v
accepted-state EOS/acoustic evaluation
        |
        v
phase, acoustic, and budget evidence capture
```

The transition classifier must observe the raw state before projection. The current
`FvmSolver` source and pre-check ordering is retained.

## Verification EOS and acoustic prerequisites

The existing `VerificationHEMEquilibriumEOS` is intentionally restricted to open
two-phase states and cannot initialize this gate from liquid.

A later implementation increment must add a separate verification-only EOS adapter with
the following narrow per-cell accepted scope:

```text
accepted:  compressed_or_subcooled_liquid
accepted:  open liquid_vapor_two_phase
rejected:  saturated endpoints, vapor, supercritical,
           critical, solid/below-triple, unknown
```

After the first crossing, one accepted array contains both crossed open-two-phase cells
and uncrossed liquid cells. The adapter must therefore handle heterogeneous phase arrays
cell by cell; it must not assume one phase class for the complete domain.

For every accepted cell, the adapter must:

- evaluate phase and primitive properties from the canonical `rho/e` path;
- require transported quality to match equilibrium quality within the accepted-state
  tolerance;
- use the existing `estimate_coolprop_equilibrium_sound_speed` path for both supported
  liquid and open-two-phase cells;
- reject non-finite or non-positive acoustic results;
- make no physical accuracy or production-closure claim.

CoolProp single-phase `A` may remain a reference in acoustic scaffold tests, but it must
not be introduced as a separate runtime liquid closure. Using the same reviewed acoustic
estimator on both sides avoids an unreviewed phase-dependent algorithm switch.

Exact endpoint acoustic behavior remains deliberately unresolved by this gate.

## Fixed integration-case architecture

### Case A — first liquid-to-two-phase crossing

The eventual fixed runner must use:

```text
fluid:                pure CO2
spatial method:       existing first-order FVM
numerical flux:       existing Rusanov flux
time step:            existing CFL path
initial velocity:     0 m/s
initial phases:       all LIQUID_CANDIDATE
initial quality:      q = 0 in every cell
boundaries:           transmissive
physical source:      none
internal interfaces:  none
termination:          immediately after first accepted crossing step
```

The initial condition is a piecewise-constant pair of supported liquid states that
creates an expansion at their interface. Both states must be away from critical and
triple-point guards, must have finite positive density/pressure/temperature/sound speed,
and must have `e >= 0` under the current solver-state guard. No initial cell may be
two-phase.

### Case B — matched no-crossing control

The negative control must keep Case A's numerical architecture and change only the
physical driver, preferably the pressure/internal-energy offset or subcooling margin.

It must use the same frozen mesh, CFL, boundary type, flux, source, projection, property
algorithms, and maximum-step safety limit. It must advance through at least Case A's
first-crossing physical time:

```text
Case B final time >= Case A first-crossing time
```

The control may require a different completed step count because its CFL time steps can
differ. It must remain entirely in `LIQUID_CANDIDATE` over that matched physical-time
horizon.

## Controlled exploration protocol

Small trial and error is expected, but it is limited to case construction.

### Stage 1 — property/state-pair survey

Before running FVM, survey candidate liquid states through CoolProp and then re-evaluate
each candidate through the canonical `rho/e` path. The survey may vary:

```text
left/right pressure
left/right temperature or internal energy
subcooling margin
pressure/internal-energy offset
```

Reject candidates that approach critical/triple guards, have `e < 0`, or do not provide
finite positive liquid acoustic estimates.

### Stage 2 — documented minimal FVM dry runs

Use a small first-order case. During the documented dry-run phase, the following case
parameters may be varied one at a time:

```text
state pair
mesh cell count
CFL
maximum-step safety limit
```

Every attempt must record the changed parameter and one outcome:

```text
all liquid
endpoint landing
open-two-phase crossing
forbidden/backend/solver-guard failure
```

The following may not be tuned to make the case pass:

```text
flux algorithm
source algorithm
boundary algorithm
phase/property evaluator
acoustic algorithm
transition definitions
projection algorithm
tolerances
budget acceptance rules
```

Once one finite supported Case A and one matched Case B satisfy the proposed criteria,
all case values are frozen before formal evidence capture. No post hoc threshold or
algorithm change is permitted without reopening design review.

## Case A acceptance criteria

### Initial-state requirements

```text
all cells derived region = LIQUID_CANDIDATE
all cells q_transport = 0 exactly
all cells q_eq = 0 by existing software convention
initial two-phase cell count = 0
all rho, p, T and sound speed values finite and positive
all internal energies finite and non-negative
```

### First-crossing requirements

```text
first crossing step exists within configured maximum steps
crossing cell count >= 1
all crossing cells raw region = OPEN_TWO_PHASE
all crossing cells previous region = LIQUID_CANDIDATE
at least one crossing cell q_eq >= crossing_evidence_min_quality
raw endpoint landing count = 0
forbidden transition count = 0
```

### Projection requirements

```text
max abs(q_transport_raw) <= activation_tolerance before first projection
projection-applied cell set = crossing cell set
all crossing-cell delta_q > activation_tolerance
condensation projection count = 0
max abs(q_post - q_eq) <= activation_tolerance
second projection of U_n1_post is a no-op
```

### Conservative invariants

```text
rho   bitwise unchanged by projection
rho*u bitwise unchanged by projection
rho*E bitwise unchanged by projection
```

### Post-state requirements

```text
all crossed cells remain OPEN_TWO_PHASE after projection
all uncrossed cells remain LIQUID_CANDIDATE
accepted EOS handles the mixed liquid/open-two-phase array
all required property and acoustic values are finite
rho, p, T and sound speed are positive
internal energy remains non-negative under the current solver guard
```

### Budget requirements

```text
mass budget closed
momentum budget closed
energy budget closed
phase-vapor accounting closed
projection conservative-energy contribution = 0
```

Because every accepted pre-crossing cell has `q=0`, the first crossing step must also
satisfy:

```text
initial vapor inventory = 0
cumulative boundary vapor contribution = 0 within budget tolerance
physical vapor-source contribution = 0
raw vapor inventory before projection = 0 within budget tolerance
post vapor inventory
    = equilibrium-quality projection source
    + residual
```

The projection source must be recorded once by `PhaseChangeBudgetTracker`. It must not be
counted as a boundary contribution, physical source, or conservative-energy source.

## Case B acceptance criteria

```text
Case B reaches at least Case A first-crossing physical time
all cells remain LIQUID_CANDIDATE
crossing cell count = 0
endpoint landing count = 0
projection-applied cell count = 0
max abs(q_transport) <= activation_tolerance
boundary vapor contribution = 0 within budget tolerance
phase-vapor projection source = 0
mass budget closed
momentum budget closed
energy budget closed
phase-vapor accounting closed
all required property and acoustic evaluations finite
all internal energies non-negative
```

## Required tests before integration evidence

1. derived-region mapping distinguishes liquid candidate from saturated-liquid endpoint
   even though both carry software quality zero;
2. installed-CoolProp `rho/e` states generated from saturated liquid and saturated vapor
   endpoints exercise the actual backend endpoint classification;
3. two-phase values at and inside `endpoint_tolerance` map to the liquid endpoint;
4. open two-phase values above endpoint tolerance map to `OPEN_TWO_PHASE`;
5. out-of-range, undefined, non-finite, guarded, and backend-failed qualities map to an
   explicit failure;
6. transition table identifies `NO_TRANSITION`, `BOUNDARY_TOUCH`, target crossing, reverse,
   and forbidden transitions;
7. crossing detection uses previous accepted and current raw thermodynamic regions;
8. raw crossing detection calls the direct phase evaluator and does not call the strict
   accepted-state EOS;
9. crossing detection is independent of transported quality;
10. projection activation remains based only on quality mismatch;
11. first-crossing set equality is enforced only under the fixed all-`q=0` test contract;
12. any endpoint landing produces the explicit unresolved-acoustic-closure failure;
13. the new accepted-state EOS handles a mixed liquid/open-two-phase array;
14. the same equilibrium sound-speed estimator is used for supported liquid and open
    two-phase cells, with no runtime CoolProp `A` branch;
15. the current non-negative internal-energy solver guard is exercised explicitly;
16. conservative columns remain bitwise unchanged;
17. second projection is a no-op;
18. boundary vapor contribution, physical source, and projection source are separated;
19. vapor projection source is included exactly once in accounting;
20. Case B is evaluated through at least Case A's first-crossing physical time.

## Fail-fast conditions

The runner or complete step fails on any of the following:

- invalid conservative-array shape;
- non-finite conservative value;
- non-positive density;
- non-finite or negative internal energy under the current solver-state guard;
- transported quality outside `[0, 1]` in the crossing/projection path;
- phase/property backend failure;
- undefined, non-finite, or out-of-range required equilibrium quality;
- guarded or unknown phase classification;
- any raw saturated-liquid endpoint landing in the integration gate;
- raw saturated-vapor endpoint or vapor state;
- critical, solid/below-triple, or unsupported supercritical state;
- non-finite or non-positive required sound speed;
- use of a transported-quality-sensitive accepted-state EOS for raw transition detection;
- inability of the accepted-state EOS to process the mixed post-crossing phase array;
- projection modification of `rho`, `rho*u`, or `rho*E`;
- post-projection quality mismatch above activation tolerance;
- nonzero second projection of the accepted state;
- phase-vapor source double counting or budget non-closure;
- any NaN or infinity in evidence arrays;
- missing property-backend, tolerance, or design-status traceability.

No invalid state outside the existing reviewed endpoint-normalization policy is silently
clipped, reclassified, or locally bypassed.

## Required evidence

### Exploration ledger

```text
attempt identifier
changed parameter
left/right candidate state
mesh
CFL
maximum steps
outcome category
failure reason or crossing summary
```

### Per-step scalar evidence

```text
step
time_s
dt_s
CFL maximum
liquid cell count
saturated-liquid endpoint count
open-two-phase cell count
forbidden-state count
crossing cell count
projection-applied cell count
maximum abs(delta_q)
maximum post-projection quality mismatch
mass, momentum and energy residuals
initial, raw and post vapor inventories
boundary vapor contribution
physical vapor-source contribution
projection vapor source
```

### First-crossing cellwise evidence

```text
cell index
previous phase class
previous derived region
raw phase
raw phase class
raw derived region
q_transport_raw
q_equilibrium_raw
q_post
delta_q
projection_applied
rho
u
e
p
T
alpha
equilibrium sound-speed candidate
scope status
```

### Traceability

```text
commit hash
case identifier
model name
fluid name
property_backend_name = coolprop_co2
property_backend_design_status = not_approved_for_design_use
CoolProp version
NumPy version
mesh
CFL
maximum steps
first crossing step
first crossing time
endpoint tolerance actually used
projection activation tolerance actually used
accepted-state EOS tolerance actually used
crossing evidence minimum quality
output version
verification_only = true
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Human-review artifacts

The later fixed runner should emit:

```text
JSON
CSV
Markdown
NPZ
```

and figures generated only from saved numerical artifacts:

1. phase-region and quality snapshot immediately before and after first crossing;
2. pressure, density, velocity, internal-energy, alpha, and acoustic profiles;
3. conservative and vapor-budget history through first crossing;
4. Case A / Case B comparison with explicit verification-only metadata.

Plotting must not rerun or alter the numerical case.

## Deliberately excluded

This specification does not approve or implement:

- production HEM defaults;
- an endpoint acoustic closure;
- hysteresis or chattering control;
- transported-quality clipping or positivity limiting;
- reverse two-phase-to-liquid crossing;
- open-two-phase-to-vapor crossing;
- long-time repeated boundary motion;
- higher-order reconstruction;
- discharge, rupture, wall-friction, or wall-heat-transfer models;
- finite-rate HNE relaxation;
- impurity mixtures;
- critical or solid CO2 operation;
- a two-phase acoustic accuracy band;
- a general negative-internal-energy real-fluid solver policy;
- pipeline depressurization Validation;
- physical Validation or design-use acceptance.

## Expected implementation file set

A later implementation increment is expected to add a narrow, separate path such as:

```text
src/liquid_gas_transient/hem_liquid_to_two_phase_crossing.py
tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py
docs/verification/stage7_lco2_hem_liquid_to_two_phase_crossing_plan.md
docs/verification/stage7_lco2_hem_liquid_to_two_phase_crossing_validation_commands.md
```

The existing projection, phase-classification, acoustic, and budget modules should be
reused unless a reviewed incompatibility is demonstrated.

## Design decisions requiring human approval

Before implementation begins, human review must confirm:

1. the boundary-region view is derived without expanding the public phase-class enum;
2. `q=0` liquid and `q=0` saturated endpoint are distinguished by phase class;
3. any endpoint landing is rejected until an endpoint acoustic closure is separately
   established;
4. the current global non-negative internal-energy guard remains a first-gate constraint;
5. raw transition detection uses direct `rho/e` phase evaluation and bypasses the strict
   accepted-state EOS;
6. the same existing equilibrium sound-speed estimator is used for supported liquid and
   open two-phase cells;
7. the new verification EOS accepts mixed liquid/open-two-phase arrays after crossing;
8. existing endpoint, projection, and Stage 7 accepted-state tolerances are reused from
   their configuration objects;
9. `crossing_evidence_min_quality = 1e-6` remains test-only;
10. the first runner stops immediately after the first crossing step;
11. the all-`q=0` first-crossing contract justifies equality of crossing and projection
    cell sets for this case only;
12. the matched no-crossing control runs through at least Case A's crossing time;
13. limited state-pair/mesh/CFL/max-step exploration is permitted and logged, while
    algorithms and thresholds remain fixed;
14. no transported-quality clipping, endpoint hysteresis, or local fallback is added;
15. fail-fast whole-step behavior is retained;
16. production, Validation, acoustic-accuracy, and design-use approvals remain false.

## Next action after design approval

1. implement and unit-test the derived boundary-region and transition-event classifier;
2. add the narrow mixed liquid/open-two-phase accepted-state EOS adapter;
3. perform the documented CoolProp state-pair survey away from critical/triple guards and
   within the current `e >= 0` solver constraint;
4. perform logged minimal FVM dry runs without changing algorithms or thresholds;
5. freeze the first evaluable Case A and matched Case B values;
6. implement the first-crossing capture runner;
7. validate focused tests and the full repository suite;
8. capture review artifacts and synchronize the central verification records;
9. only then begin a longer pipeline-depressurization prototype.
