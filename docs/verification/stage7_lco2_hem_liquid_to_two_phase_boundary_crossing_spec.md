# Stage 7 — First Liquid-to-Two-Phase Boundary-Crossing Specification

## Status

`PROPOSED; DESIGN REVIEW REQUIRED; SPECIFICATION ONLY; NOT IMPLEMENTED`

This document defines the first pure-CO2 HEM increment after the merged dynamic
quality-synchronization work in PRs #59–#62. It is based on `main` commit
`33349ff6c16373443b2626d13c1a867d54275d0a`.

It does not change solver behavior, approve a production HEM path, establish physical
Validation, or permit design use.

## Objective

Define a narrow first-order verification gate in which every cell starts as a supported
single-phase liquid candidate and at least one cell enters the open liquid-vapor
two-phase region through a conservative FVM update.

The gate must demonstrate that:

- the thermodynamic phase transition is detected from the updated `rho/e` state;
- the transported fourth component is synchronized only after the raw transition is
  identified;
- `rho`, `rho*u`, and `rho*E` remain bitwise unchanged by the projection;
- the phase-vapor inventory increase is attributed exactly once to the projection;
- unsupported endpoint, vapor, critical, solid, unknown, and backend-invalid states fail
  explicitly;
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

### Canonical thermodynamic evaluation

The raw and accepted phase states are evaluated from the same `rho/e` path already used
by the Stage 7 HEM foundation:

```text
rho = U[rho]
u   = U[rho*u] / rho
E   = U[rho*E] / rho
e   = E - u^2/2
```

No separate `p/T` flash, phase-majority vote, or quality-only phase inference is allowed
for transition detection.

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
and equilibrium-quality outputs.

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

### Existing projection

The first implementation reuses `HEMEquilibriumQualityProjection` without changing its
conservative contract:

```text
rho*q <- rho*q_eq
```

while preserving `rho`, `rho*u`, and `rho*E` bitwise.

## Step-state definitions

For one transition step, define three states.

### Previous accepted state

```text
U_n_post
```

This is the synchronized state at the end of time step `n`. Its transported quality must
match the equilibrium quality within the accepted EOS tolerance.

### Raw updated state

```text
U_n1_raw
```

This is the state after the first-order FVM update and any configured physical source,
but before equilibrium-quality projection.

Transition detection uses the thermodynamic state derived from `rho/e` in `U_n1_raw`.
It must not use the transported quality as the phase classifier.

### Post-projection accepted state

```text
U_n1_post
```

This is the state after `HEMEquilibriumQualityProjection` has synchronized `rho*q`.
Because projection does not change `rho/e`, its thermodynamic region must be identical to
the raw thermodynamic region.

## Derived boundary-region view

Let `q_eq` be the equilibrium quality returned by the existing phase evaluator and let
`endpoint_tolerance` be the existing
`HEMPhaseClassificationConfig.endpoint_tolerance`.

| derived region | required existing output |
|---|---|
| `LIQUID_CANDIDATE` | `phase_class == compressed_or_subcooled_liquid` |
| `SATURATED_LIQUID_ENDPOINT` | `phase_class == liquid_vapor_two_phase` and `q_eq <= endpoint_tolerance` |
| `OPEN_TWO_PHASE` | `phase_class == liquid_vapor_two_phase` and `endpoint_tolerance < q_eq < 1 - endpoint_tolerance` |
| `SATURATED_VAPOR_ENDPOINT` | `phase_class == liquid_vapor_two_phase` and `q_eq >= 1 - endpoint_tolerance` |
| `VAPOR_CANDIDATE` | `phase_class == single_phase_vapor` |
| `GUARDED_OR_INVALID` | guarded, unknown, undefined, non-finite, or backend-failed state |

The derived region is a verification view. It does not replace the public phase-class
contract in this specification increment.

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

An endpoint-only raw state is recorded as a boundary touch, not as a completed
liquid-to-two-phase crossing.

The current equilibrium sound-speed scaffold deliberately excludes exact `q=0` and
`q=1` endpoints because a centered finite-difference stencil may cross the phase
boundary. This first FVM gate therefore does not approve an endpoint as a completed
accepted state. A raw endpoint landing fails the integration gate with an explicit
`endpoint_acoustic_closure_not_established` reason unless the same update reaches a
verified open-two-phase state.

This policy avoids silently inventing an endpoint sound-speed closure.

## Transition-event definitions

The previous region is evaluated from `U_n_post`. The raw region is evaluated from
`U_n1_raw`.

| previous accepted region | raw region | event | first-gate policy |
|---|---|---|---|
| `LIQUID_CANDIDATE` | `LIQUID_CANDIDATE` | `NO_TRANSITION` | allowed |
| `LIQUID_CANDIDATE` | `SATURATED_LIQUID_ENDPOINT` | `BOUNDARY_TOUCH` | classified, but integration gate stops as unsupported endpoint landing |
| `LIQUID_CANDIDATE` | `OPEN_TWO_PHASE` | `LIQUID_TO_TWO_PHASE_CROSSING` | target event |
| `SATURATED_LIQUID_ENDPOINT` | `OPEN_TWO_PHASE` | `LIQUID_TO_TWO_PHASE_CROSSING` | definition retained for unit tests; endpoint is not an accepted FVM state in this gate |
| `LIQUID_CANDIDATE` | vapor-side or guarded region | `FORBIDDEN_TRANSITION` | fail-fast |
| `OPEN_TWO_PHASE` | liquid-side region | reverse transition | outside this first gate |
| any supported region | guarded or invalid region | invalid transition | fail-fast |

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
- there is no vapor source before the projection;
- the fourth-component FVM flux is zero while every accepted cell has `q=0`;
- the runner stops immediately after the first crossing step.

Under those conditions:

```text
first-crossing cell set = projection-applied cell set
```

This equality is a property of the fixed first-crossing test, not a general HEM solver
invariant for later multi-step two-phase transport.

## Tolerance policy

The first specification reuses existing tolerances instead of introducing duplicate
solver thresholds.

```text
phase endpoint tolerance:
    HEMPhaseClassificationConfig.endpoint_tolerance = 1e-10

projection activation/synchronization tolerance:
    HEMEquilibriumQualitySyncConfig.activation_tolerance = 1e-12

minimum crossing evidence quality:
    crossing_evidence_min_quality = 1e-6
```

### Endpoint tolerance

This tolerance only separates endpoint-classified two-phase states from the open
interior. It does not activate projection and is not a physical nucleation threshold.

### Projection activation tolerance

This tolerance only decides whether the fourth component is materially changed and
reported as projected. It does not decide whether a phase boundary was crossed.

### Minimum crossing evidence quality

`crossing_evidence_min_quality` is an integration-test acceptance threshold. It prevents
roundoff-scale endpoint noise from being presented as the principal crossing evidence.
It must not be used inside production or verification solver branching.

The final frozen state pair must also produce a finite positive equilibrium sound-speed
candidate. Meeting `crossing_evidence_min_quality` alone does not establish acoustic
evaluability or physical accuracy.

### Transported-quality bounds

The first-order gate retains the current projection precondition:

```text
0 <= q_transport <= 1
```

Any transported overshoot or undershoot fails fast. No clipping, floor, ceiling,
positivity limiter, or new bound tolerance is introduced in this specification.
If a future run exposes a roundoff-only bound excursion, that requires a separate
reviewed policy change with its own tests.

### Budget tolerances

Mass, momentum, energy, and vapor accounting reuse the existing scale-aware budget
checks. No new dimensioned absolute tolerance is scattered through the crossing runner.

## Required processing order

```text
accepted synchronized state U_n_post
        |
        v
first-order FVM flux update
        |
        v
configured physical source update
        |
        v
raw rho/e phase and quality evaluation
        |
        v
transition-event classification
        |
        v
HEM equilibrium-quality projection
        |
        v
post-projection invariant checks
        |
        v
phase, acoustic, and budget evidence capture
```

The transition classifier must observe the raw state before projection.

## Verification EOS prerequisite

The existing `VerificationHEMEquilibriumEOS` is intentionally restricted to open
two-phase states and cannot initialize this gate from liquid.

A later implementation increment must add a separate verification-only EOS adapter or a
reviewed extension with the following narrow accepted phase scope:

```text
accepted before crossing:  compressed_or_subcooled_liquid
accepted after crossing:   open liquid_vapor_two_phase
rejected:                   vapor endpoint, vapor, supercritical,
                            critical, solid/below-triple, unknown
```

For every accepted state, the adapter must:

- evaluate phase and primitive properties from the same `rho/e` path;
- require transported quality to match equilibrium quality within its accepted-state
  tolerance;
- use the reviewed single-phase liquid acoustic evaluation before crossing;
- use the existing equilibrium two-phase sound-speed candidate only in the open
  two-phase interior;
- reject non-finite or non-positive acoustic results;
- make no physical accuracy or production-closure claim.

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
creates an expansion at their interface. Both states must be away from the critical and
triple-point guards. No initial cell may be two-phase.

Exact pressure, temperature, mesh, CFL, and maximum-step values are not frozen in this
specification. They are selected in a separate property/state-pair exploration. Once one
finite supported run reaches the acceptance conditions, all case values must be frozen
before formal evidence capture.

Only the state pair or CFL may be adjusted during one documented dry-run phase. Flux,
source, boundary, projection, and property algorithms may not be tuned to make the case
pass.

### Case B — matched no-crossing control

The negative control must keep the Case A architecture and change only the physical
driver, preferably the pressure/internal-energy offset or subcooling margin.

It must remain entirely in `LIQUID_CANDIDATE` for the same frozen mesh, CFL, boundary
type, and maximum-step count used to reach Case A's first crossing.

## Case A acceptance criteria

### Initial-state requirements

```text
all cells derived region = LIQUID_CANDIDATE
all cells q_transport = 0
all cells q_eq = 0 by existing software convention
initial two-phase cell count = 0
all primitive and acoustic quantities finite
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
all pressure, temperature, density, internal energy, alpha, and sound speed values finite
all pressure, temperature, density, and sound-speed values positive where required
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
raw vapor inventory before projection = 0 within budget tolerance
post vapor inventory
    = equilibrium-quality projection source
    + residual
```

The projection source must not be counted as a boundary or physical-source contribution.

## Case B acceptance criteria

```text
all cells remain LIQUID_CANDIDATE
crossing cell count = 0
endpoint landing count = 0
projection-applied cell count = 0
max abs(q_transport) <= activation_tolerance
mass budget closed
momentum budget closed
energy budget closed
phase-vapor accounting closed
all property and acoustic evaluations finite
```

## Required unit tests before integration

1. derived-region mapping distinguishes liquid candidate from saturated-liquid endpoint
   even though both carry software quality zero;
2. two-phase values at and inside `endpoint_tolerance` map to the liquid endpoint;
3. open two-phase values above the endpoint tolerance map to `OPEN_TWO_PHASE`;
4. vapor endpoint and guarded states are classified explicitly;
5. transition table identifies `NO_TRANSITION`, `BOUNDARY_TOUCH`, target crossing, and
   forbidden transitions;
6. crossing detection uses previous accepted and current raw thermodynamic regions;
7. crossing detection is independent of transported quality;
8. projection activation remains based only on quality mismatch;
9. first-crossing set equality is enforced only under the fixed all-`q=0` test contract;
10. endpoint landing produces the explicit unresolved-acoustic-closure failure;
11. conservative columns remain bitwise unchanged;
12. vapor projection source is included exactly once in accounting.

## Fail-fast conditions

The runner or complete step fails on any of the following:

- invalid conservative-array shape;
- non-finite conservative value;
- non-positive density;
- non-finite internal energy;
- transported quality outside `[0, 1]`;
- phase/property backend failure;
- undefined or non-finite required equilibrium quality;
- guarded or unknown phase classification;
- raw saturated-liquid endpoint landing in the integration gate;
- raw saturated-vapor endpoint or vapor state;
- critical, solid/below-triple, or unsupported supercritical state;
- non-finite or non-positive required sound speed;
- projection modification of `rho`, `rho*u`, or `rho*E`;
- post-projection quality mismatch above activation tolerance;
- phase-vapor source double counting or budget non-closure;
- any NaN or infinity in evidence arrays;
- missing property-backend or design-status traceability.

No invalid state is silently clipped, reclassified, or locally bypassed.

## Required evidence

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
mass, momentum, energy residuals
raw and post vapor inventories
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
3. conservative and vapor-budget history through the first crossing;
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

The existing projection and phase-classification modules should be reused unless a
reviewed incompatibility is demonstrated.

## Review decisions required

Before implementation begins, review must confirm:

1. the boundary-region view is derived without expanding the public phase-class enum;
2. `q=0` liquid and `q=0` saturated endpoint are distinguished by phase class;
3. exact endpoint landing is not accepted until an acoustic closure is separately
   established;
4. the existing endpoint and projection tolerances are reused;
5. `crossing_evidence_min_quality = 1e-6` remains test-only;
6. the first runner stops immediately after the first crossing step;
7. the all-`q=0` first-crossing contract justifies equality of crossing and projection
   cell sets for this case only;
8. a separate liquid/open-two-phase verification EOS adapter is preferred over weakening
   the open-two-phase-only adapter silently;
9. no transported-quality clipping or endpoint hysteresis is added in this gate;
10. the matched no-crossing control changes only the physical driver;
11. fail-fast whole-step behavior is retained;
12. production, Validation, acoustic-accuracy, and design-use approvals remain false.

## Next action after design approval

1. implement and unit-test the derived boundary-region and transition-event classifier;
2. add the narrow liquid/open-two-phase verification EOS adapter;
3. perform a documented CoolProp state-pair exploration away from critical/triple guards;
4. freeze the first evaluable Case A and matched Case B values;
5. implement the first-crossing capture runner;
6. validate focused tests and the full repository suite;
7. capture review artifacts and synchronize the central verification records;
8. only then begin a longer pipeline-depressurization prototype.
