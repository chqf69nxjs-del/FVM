# Stage 7 U3 B2 A1 finite-compression Increment 9E upper-boundary local-admissibility correction

## Status

`MODEL_REVIEW_ONLY / DIAGNOSTIC_CLASSIFICATION_CORRECTION / FIXED_BEFORE_RERUN_RESULT`

This note corrects one diagnostic classification defect observed in the first Increment 9E run. It does not change B1, the Hugoniot relation, local admissibility rules, any root gate, the root tolerance, the fixed `chi` nodes, the finite-compression `chi` cap, the production Adapter, `FvmSolver`, or any formal project state.

## Parent failed diagnostic

```text
source Git SHA:
efb562869058db5a092cae9656726baa35d2f13a

workflow run:
31668071341

job:
94346848601

artifact:
none; the diagnostic stopped before creating the output directory

failed operation:
upper success-window boundary refinement

observed midpoint formal outcome:
SUCCESS_UNCHOKED_FACE_MAPPING

observed midpoint local candidate admissibility:
false
```

The source/scope checks, dependency installation, parent artifact download, parent metadata verification, state reproduction and fixed-scan topology checks completed before this stop.

## Defect classification

The original Increment 9E upper-boundary refinement treated the two categorical sides as:

```text
lower:
B1 success and locally admissible

upper:
B1 unavailable
```

The first run found an intermediate candidate that:

```text
passed B1 mapping
but
failed the retained local-candidate admissibility gate
```

B1 success and local root admissibility are distinct requirements. A B1-success/local-inadmissible state is not an acceptable compatibility-root state and may not construct an applied flux. However, it is also not a B1-unavailable state.

The diagnostic incorrectly treated this third category as an unexpected internal failure rather than retaining it on the excluded side of the admissible root window.

## Fixed upper-boundary classification

For upper-boundary categorical refinement only, retain:

```text
lower included side:
  evaluation_succeeded = true
  local_candidate_admissible = true

upper excluded side, either:
  A. exact B1-unavailable state
     - REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
     - NONPOSITIVE_KINETIC_ENERGY_HEAD

  B. B1-success but local-candidate-inadmissible state
     - evaluation_succeeded = true
     - local_candidate_admissible = false
```

The excluded B category remains unusable as:

```text
a root-topology member
a compatibility-root endpoint
an applied flux state
```

No local admissibility failure is converted to success. No B1 outcome is modified. No magnitude tolerance is introduced.

Run exactly 48 deterministic upper-boundary bisection iterations. Update the lower endpoint only with a B1-success and locally admissible midpoint. Update the upper endpoint with either fixed excluded category. Any other result remains fail-closed.

The compatibility-root topology remains unchanged:

```text
refined lower first-success state
plus
higher fixed B1-success and locally admissible states inside the one contiguous
fixed admissible-success block
```

Intermediate upper-boundary rows remain evidence only.

## Rerun evidence

The corrected rerun must separately record:

```text
upper-boundary B1-unavailable midpoint count
upper-boundary B1-success/local-inadmissible midpoint count
formal outcomes and local-admissibility flags
final included lower chi
final excluded upper chi
final boundary width
```

A passing diagnostic still requires one monotone, successful and locally admissible root topology, exactly one root bracket, and a selected root passing all unchanged Hugoniot, B1, Lax, entropy, direction, phase, energy and reaction gates.

## Formal-state boundary

All approval, Verification, Validation, design-use and production flags remain false regardless of result.
