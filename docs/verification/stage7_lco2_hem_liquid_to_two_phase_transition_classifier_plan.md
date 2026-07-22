# Stage 7 — Liquid-to-Two-Phase Transition Classifier Increment

## Status

`IMPLEMENTED DRAFT; NOT SOLVER CONNECTED; REVIEW REQUIRED`

This increment follows the specification merged in PR #64. It implements only the
boundary-region mapper and transition-event classifier required before a liquid/open-
two-phase verification EOS or FVM crossing runner is attempted.

The increment is based on:

```text
main: f2b8335132741765b6d5e42f65f742cf5e241c66
PR #64: merged liquid-to-two-phase boundary-crossing specification
```

## Objective

Add a small, dependency-light classification layer that can answer two separate
questions without changing solver behavior:

```text
1. Which boundary region does a reviewed rho/e phase state represent?
2. Which transition event occurred between a previous accepted state and a raw state?
```

The implementation must not project quality, evaluate sound speed, modify conservative
variables, or connect to `FvmSolver` in this increment.

## Implementation file

```text
src/liquid_gas_transient/hem_liquid_to_two_phase_crossing.py
```

## Public objects

```text
BoundaryRegion
TransitionEvent
HEMLiquidToTwoPhaseCrossingError
HEMBoundaryRegionEvaluation
HEMTransitionClassification
HEMRawTransitionDetection
derive_boundary_regions
evaluate_boundary_regions_from_conserved
classify_transition_events
detect_raw_transition_events
```

## Boundary regions

The mapper derives the following verification-only regions from the existing
`HEMPhaseState` contract:

```text
LIQUID_CANDIDATE
SATURATED_LIQUID_ENDPOINT
OPEN_TWO_PHASE
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
```

No public Stage 7 phase-class enum is expanded.

The mapper uses the endpoint tolerance from the supplied
`HEMPhaseClassificationConfig`. It validates required equilibrium quality without
clipping or adding a second endpoint threshold.

## Direct rho/e evaluation

`evaluate_boundary_regions_from_conserved` obtains:

```text
rho = U[rho]
e   = U[rho*E] / rho - 0.5 * (U[rho*u] / rho)^2
```

and calls the reviewed phase evaluator directly.

The transported fourth component is not used as a phase classifier. This permits a raw
post-FVM quality mismatch to be classified before equilibrium-quality projection.

The function retains the current solver integration constraint:

```text
e >= 0
```

This is a software guard for the first gate, not a general real-fluid thermodynamic rule.

## Evaluator contract

The injected evaluator receives copies of `rho` and `e` plus the same instantiated
`HEMPhaseClassificationConfig` used by the region mapper.

The returned `HEMPhaseState` must preserve the requested `rho/e` values and shape.
Backend failures or contract violations fail atomically.

## Mapping policy

```text
supported compressed_or_subcooled_liquid
    q_eq approximately 0
    -> LIQUID_CANDIDATE

supported liquid_vapor_two_phase
    q_eq <= endpoint_tolerance
    -> SATURATED_LIQUID_ENDPOINT

supported liquid_vapor_two_phase
    endpoint_tolerance < q_eq < 1 - endpoint_tolerance
    -> OPEN_TWO_PHASE

supported liquid_vapor_two_phase
    q_eq >= 1 - endpoint_tolerance
    -> SATURATED_VAPOR_ENDPOINT

supported single_phase_vapor
    q_eq approximately 1
    -> VAPOR_CANDIDATE
```

The mapper rejects:

- guarded, unknown, or unsupported scope;
- undefined quality;
- non-finite quality;
- quality outside `[0, 1]`;
- a liquid candidate with materially positive quality;
- a vapor candidate with quality materially below one;
- an unsupported phase class;
- an endpoint tolerance outside `[0, 0.5)`.

## Transition events

The pure transition table emits:

```text
NO_TRANSITION
BOUNDARY_TOUCH
LIQUID_TO_TWO_PHASE_CROSSING
REVERSE_TRANSITION
FORBIDDEN_TRANSITION
```

Target first-gate transitions are:

```text
LIQUID_CANDIDATE -> OPEN_TWO_PHASE
SATURATED_LIQUID_ENDPOINT -> OPEN_TWO_PHASE  # unit-test definition only
```

Endpoint landing is classified as `BOUNDARY_TOUCH`. The later integration runner remains
responsible for enforcing the PR #64 policy that every endpoint landing fails the first
FVM gate.

## Test file

```text
tests/test_stage7_lco2_hem_liquid_to_two_phase_crossing.py
```

Dependency-free tests cover:

- liquid `q=0` versus saturated-liquid endpoint `q=0`;
- endpoint and open-two-phase interval boundaries;
- guarded, unknown, undefined, non-finite, and out-of-range states;
- inconsistent single-phase quality;
- invalid endpoint tolerance;
- no-transition, boundary-touch, target crossing, reverse, and forbidden events;
- deterministic event summary counts;
- unknown region and shape errors;
- direct `rho/e` evaluation independent of transported quality;
- propagation of the instantiated phase configuration;
- input immutability and evaluator contract enforcement;
- backend failure wrapping;
- the current non-negative internal-energy guard;
- previous/raw cell-shape consistency.

The installed-CoolProp test constructs saturated liquid and saturated vapor at 2 MPa,
converts them to `rho/e`, and verifies the actual endpoint classification through the
canonical path.

## Local pre-check performed outside the repository checkout

Because the connected execution environment cannot access the user's WSL checkout or
clone GitHub directly, the pure implementation was syntax-checked and exercised in a
minimal local package with matching Stage 7 contracts:

```text
compileall: success
dependency-free tests: 16 passed
CoolProp test: 1 skipped because CoolProp is unavailable in that minimal environment
```

The authoritative validation remains the repository CI and the user's configured WSL
CoolProp environment.

## Deliberately excluded

This increment does not:

- modify `FvmSolver`;
- add a mixed liquid/open-two-phase verification EOS;
- evaluate equilibrium sound speed;
- call CoolProp single-phase sound speed at runtime;
- apply equilibrium-quality projection;
- enforce first-gate endpoint termination in a runner;
- perform state-pair exploration;
- run a liquid-to-two-phase FVM case;
- add clipping, hysteresis, or local fallback;
- approve production HEM, physical Validation, an acoustic accuracy band, or design use.

## Completion boundary

This increment is review-ready when:

- dependency-free focused tests pass;
- the installed-CoolProp endpoint test passes without skip in the intended environment;
- the full repository suite passes;
- permanent workflows remain green;
- the diff contains only the classifier, tests, and verification documentation;
- production, Validation, acoustic-accuracy, and design-use flags remain false.

## Next increment after merge

1. add the narrow mixed liquid/open-two-phase accepted-state EOS adapter;
2. verify the same existing equilibrium sound-speed estimator on both supported regions;
3. only then begin the logged CoolProp state-pair survey and minimal FVM dry runs.
