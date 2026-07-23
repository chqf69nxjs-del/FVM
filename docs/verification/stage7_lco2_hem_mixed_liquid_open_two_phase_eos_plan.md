# Stage 7 — Mixed Liquid/Open-Two-Phase Verification EOS Increment

## Status

`IMPLEMENTED DRAFT; VERIFICATION ONLY; NOT SOLVER-ACTIVATED; REVIEW REQUIRED`

This increment follows merged PRs #64–#66. It adds the narrow accepted-state
EOS required before any logged state-pair survey or liquid-to-two-phase FVM dry
run is attempted.

Base:

```text
main: 7acaa005c6d32cd48042ca5a333dcc19b5006d23
PR #64: boundary-crossing specification
PR #65: boundary-region and transition classifier
PR #66: central-record synchronization
```

## Objective

Add one verification-only EOS adapter that can process a synchronized accepted
array containing both:

```text
LIQUID_CANDIDATE
OPEN_TWO_PHASE
```

on a cell-by-cell basis.

The increment must establish the accepted-state thermodynamic and acoustic path
without selecting a crossing state pair, advancing an FVM step, or changing
production behavior.

## Implementation file

```text
src/liquid_gas_transient/hem_mixed_liquid_open_two_phase_eos.py
```

Primary class:

```text
VerificationHEMLiquidOpenTwoPhaseEOS
```

## Accepted and rejected scope

Accepted per cell:

```text
compressed_or_subcooled_liquid
    -> LIQUID_CANDIDATE

liquid_vapor_two_phase
with endpoint_tolerance < q_eq < 1 - endpoint_tolerance
    -> OPEN_TWO_PHASE
```

Rejected:

```text
SATURATED_LIQUID_ENDPOINT
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
supercritical
critical_region
solid_or_below_triple_guard
unknown
backend-invalid or non-finite states
```

A saturated-liquid endpoint fails explicitly with:

```text
endpoint_acoustic_closure_not_established
```

The adapter does not invent an endpoint sound-speed closure.

## Canonical accepted-state path

For each conserved cell:

```text
rho = U[rho]
u   = U[rho*u] / rho
E   = U[rho*E] / rho
e   = E - u^2/2
q_transport = U[rho*q] / rho
```

The adapter then:

1. evaluates the reviewed phase state directly from `rho/e`;
2. derives the PR #65 boundary region using the same instantiated
   `HEMPhaseClassificationConfig`;
3. accepts only liquid candidate or open two phase;
4. requires equilibrium quality and void fraction to be defined;
5. calls the existing `estimate_coolprop_equilibrium_sound_speed` path;
6. requires the acoustic center phase to agree with the phase classifier;
7. requires finite positive pressure, temperature and sound speed;
8. requires `q_transport` to match `q_eq` within the accepted-state tolerance;
9. returns the existing `PrimitiveState`.

## Quality policy

```text
projection activation tolerance:
    HEMEquilibriumQualitySyncConfig.activation_tolerance = 1e-12

accepted-state EOS quality tolerance:
    1e-10
```

The adapter validates:

```text
projection activation tolerance <= accepted-state EOS quality tolerance
```

Transported-quality bounds remain strict:

```text
0 <= q_transport <= 1
```

No clipping, flooring, ceiling, endpoint normalization, or local fallback is
added by this adapter.

## Acoustic policy

The same callable is used for every supported cell:

```text
estimate_coolprop_equilibrium_sound_speed
```

There is no runtime branch to CoolProp single-phase `A` for liquid cells.
Liquid and open-two-phase cells therefore use the same reviewed acoustic
algorithm.

The adapter rejects:

```text
non-finite sound speed
non-positive sound speed
rho/e mismatch returned by the estimator
center phase-class disagreement
```

The resulting values remain verification closure candidates. They are not a
physical acoustic Validation result or an approved accuracy band.

## Heterogeneous-array behavior

The adapter loops over cells and does not assume that the complete domain has
one phase class.

Representative accepted layout:

```text
LIQUID_CANDIDATE
LIQUID_CANDIDATE
OPEN_TWO_PHASE
LIQUID_CANDIDATE
```

Repeated exact `rho/e` states use a local cache. Cache and evaluation counters
are diagnostics only; they do not alter state acceptance.

## Solver boundary

This increment may demonstrate structural compatibility by calling:

```text
FvmSolver.primitive()
FvmSolver.compute_dt()
```

on an already synchronized mixed array.

It does not:

```text
advance FvmSolver.step()
connect crossing detection to the solver
apply equilibrium-quality projection
select or tune a liquid state pair
run Case A or Case B
change Rusanov flux or CFL
change boundary, source, or budget algorithms
```

## Test file

```text
tests/test_stage7_lco2_hem_mixed_liquid_open_two_phase_eos.py
```

Dependency-free tests cover:

- invalid adapter and endpoint tolerances;
- accepted tolerance versus projection activation tolerance;
- liquid/open-two-phase mixed-array recovery;
- exact `rho/e` caching;
- mismatch within and beyond the accepted-state tolerance;
- strict transported-quality bounds;
- saturated-liquid and saturated-vapor endpoint rejection;
- vapor, guarded, unknown, undefined, and incomplete-state rejection;
- phase-backend and acoustic-backend failure wrapping;
- non-finite or non-positive acoustic results;
- phase/acoustic-center agreement;
- input immutability and `rho/e` preservation;
- invalid conservative shape, density, finiteness, and internal energy;
- structural `FvmSolver` primitive/CFL compatibility without a time step.

Installed-CoolProp tests cover:

```text
5 MPa / 280 K liquid
+
2 MPa / Q=0.50 open two phase
```

in one synchronized array, and explicit rejection of the `2 MPa / Q=0`
saturated-liquid endpoint.

## Completion criteria

The increment is review-ready when:

```text
source compiles
git diff --check is clean
dependency-free focused tests pass
installed-CoolProp focused tests pass with zero skips
related Stage 7 HEM tests pass
full repository tests pass
permanent workflows remain green on the final head
final diff contains only source, tests, and verification documents
```

Approval boundary:

```text
verification_only = true
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Next increment after merge

Only after this adapter is reviewed and merged:

1. build a logged CoolProp liquid state-pair survey;
2. reject critical/triple/negative-energy/acoustically invalid candidates;
3. run documented minimal first-order FVM dry runs;
4. vary one case parameter at a time;
5. freeze Case A and matched Case B before formal crossing evidence.
