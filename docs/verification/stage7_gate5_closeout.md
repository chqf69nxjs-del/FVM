# Stage 7 Gate 5 Closeout — Near-Saturation Acoustic-Continuity Review

## Status

```text
Gate_5_execution_complete = true
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
post_crossing_propagation_approved = false
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

Gate 5 is closed as an **execution-complete, approval-withheld** verification gate. The
fixed diagnostic contract was executed and its evidence is accepted. The result does not
approve a strict acoustic continuity limit, a two-phase sound-speed accuracy band, physical
validity, design use, or production HEM activation.

## Scope

The review isolated the existing pure-CO2 equilibrium sound-speed candidate from transport
and boundary numerics.

```text
fluid / backend:             pure CO2 / CoolProp 8.0.0
pressures:                   2 / 3 / 4 MPa
FVM:                         not used
boundary model:              not used
Rusanov flux:                not used
CFL:                         not used
production solver changes:   none
threshold tuning:            none
sound-speed formula changes: none
```

Reviewed closure:

```text
c_eq^2 = (dp/drho)|e + (p/rho^2) (dp/de)|rho
```

The unchanged guarded, phase-preserving central finite-difference implementation was called
directly. No endpoint clipping or one-sided production substitute was introduced.

## Implementation reference

```text
PR:                              #96
merge:                           39937efaebe673ba16f156427957baef8e29ec32
source head:                     9cb9d64fb7a6ae7b30417083894f0b68cbe3747b
changed files:                   4
production source changes:       none outside the verification-only diagnostic module
```

PR #96 added:

- the independent 0-D Gate 5 diagnostic;
- the locked fixed-grid and perturbation tests;
- the dedicated evidence workflow;
- the Gate 5 execution plan.

## Authoritative evidence

```text
workflow run:                    30451125151
artifact ID:                     8723959176
artifact upload SHA256:          018fa92a8395524bcb7bf28e5258d76cda88b539f037bc66f528d50358793949
internal evidence-set SHA256:    a91b3d6f544c1cf9fae986e0c1d466c747d54a383a0be2764985926d45fca411
pre-execution checkout:          clean
property backend version:        8.0.0
state-point records:             33
perturbation records:            588
successful acoustic records:     24
failed or refused records:       9
Gate 5 dedicated JUnit:          2 / 0 skipped / 0 failures / 0 errors
related Stage 7 JUnit:            58 / 0 skipped / 0 failures / 0 errors
full repository JUnit:            811 / 0 skipped / 0 failures / 0 errors
```

The artifact was downloaded after execution. Its internal evidence-set digest was
independently recomputed and matched `artifact_sha256.txt` exactly.

Run `30452424448` also completed successfully on the same source head, but it is retained as
a redundant non-authoritative re-execution and does not supersede the evidence above.

## Fixed state grid

At each pressure, the diagnostic retained:

```text
liquid subcooling:  5 K / 1 K / 0.1 K / 0.01 K
endpoint:           q = 0
open two phase:     q = 1e-12 / 1e-10 / 1e-8 / 1e-6 / 1e-4 / 1e-2
```

Independent relative perturbations in rho and e were:

```text
0 / +/-1e-10 / +/-1e-8 / +/-1e-6
```

The perturbation matrix was applied to the 0.01 K subcooled state and q=1e-10, q=1e-8,
and q=1e-6 states at each pressure.

## Principal numerical observations

| pressure | 0.01 K subcooled liquid c_eq | q=1e-8 c_eq | q=1e-6 c_eq | q=1e-8 / liquid |
|---:|---:|---:|---:|---:|
| 2 MPa | `703.727350 m/s` | `21.085651 m/s` | `21.086007 m/s` | `0.029963` |
| 3 MPa | `587.241362 m/s` | `30.621610 m/s` | `30.621899 m/s` | `0.052145` |
| 4 MPa | `486.545263 m/s` | `40.437298 m/s` | `40.437528 m/s` | `0.083111` |

At all pressures:

- q=0 was retained and explicitly refused by the current phase-preserving central rho
  stencil;
- q=1e-12 and q=1e-10 did not form a valid guarded central rho stencil after the fixed
  maximum of 12 halvings;
- q=1e-8 and all larger fixed qualities produced finite positive estimates;
- q=1e-8 and q=1e-6 differed by no more than `1.69e-5` relative.

The sampled evidence therefore supports a stable smallest-evaluable open-two-phase branch,
but not a directly evaluated strict q→0+ limit.

## Perturbation evidence

```text
normalized-phase changes:                         97 / 588
acoustic failures:                                75 / 588
failure location:                                 all q=1e-10 base states
failure category:                                 PHASE_PRESERVING_STENCIL_REFUSED
maximum |relative c_eq response| with phase fixed: 1.033e-5
```

Large acoustic changes coincide with normalized-phase reclassification. Successful
same-phase perturbations remain comparatively stable on the fixed grid.

## Reviewed disposition

```text
FINITE_JUMP_MODEL_CONSISTENT
PHASE_CLASSIFIER_SENSITIVE
NEAR_SATURATION_PROPERTY_SENSITIVE
ACOUSTIC_REVIEW_INCONCLUSIVE
```

### FINITE_JUMP_MODEL_CONSISTENT

Supported between the nearest sampled liquid branch and the smallest acoustically
evaluable open-two-phase branch. It is not a proof of the strict q→0+ mathematical limit.

### PHASE_CLASSIFIER_SENSITIVE

Strongly supported. The fixed perturbation evidence shows that large acoustic changes are
concentrated at normalized-phase changes, while same-phase successful results are stable.

### NEAR_SATURATION_PROPERTY_SENSITIVE

Retained only as a broad liquid-branch/open-two-phase-branch contrast label. It must not be
read as evidence of comparable instability within one retained phase.

### ACOUSTIC_REVIEW_INCONCLUSIVE

Retained narrowly for q=0, q=1e-12, q=1e-10, and the strict q→0+ limit, which are not
acoustically observable with the unchanged phase-preserving central stencil.

The fixed evidence does not support `CONTINUOUS_LIMIT_SUPPORTED` and does not trigger
`IMPLEMENTATION_DISCONTINUITY_SUSPECTED`.

## PR #79 comparison

The retained PR #79 observation was not rerun or reclassified:

```text
accepted liquid c_eq:       461.25669095385655 m/s
raw micro-quality c_eq:      43.22308393386989 m/s
raw pressure:                4273927.110515705 Pa
raw q_eq:                    9.672588429198319e-9
micro-quality / liquid:      0.09370722372500795
finite sound-speed difference: 418.0336070199867 m/s
```

It is qualitatively consistent with the Gate 5 liquid/open-two-phase branch contrast near
4 MPa and remains diagnostic only.

## Closeout rationale

Issue #95 defined completion by execution of the fixed contract, explicit endpoint behavior,
retention and categorization of all failures, perturbation evidence, the PR #79 comparison,
clean JUnit, and traceable provenance. It did not require an artificial value at q=0 or a
strict q→0+ estimate when the unchanged production candidate correctly refuses the central
stencil.

The strict limit is therefore retained as a known observability limitation rather than made
a result-dependent new Gate 5 requirement. No clipping, one-sided production stencil,
threshold adjustment, or formula alteration is authorized.

The artifact-level `Gate_5_execution_complete = false` remains a valid pre-review safeguard.
The separate review and central synchronization steps promote execution completion without
retroactively rewriting the executed artifact.

## Next controlled gate

The next gate is a specification-first **post-crossing propagation review**. Before any
production claim, it must determine whether a projected open-two-phase region can propagate
through multiple cells while preserving:

- finite physical accepted states;
- mass, momentum, total-energy, and vapor-mass accounting;
- phase/projection consistency;
- controlled phase-classification behavior;
- explicit mesh and CFL sensitivity records;
- the current fail-safe acoustic and endpoint guards.

The next gate must begin with all acoustic-accuracy, propagation, physical-validation,
design-use, and production-activation approvals false.
