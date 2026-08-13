# Stage 7 U3 B2 A1 Increment 9L Guard-front topology authority binding correction

## Status

`MODEL_REVIEW_ONLY / AUTHORITY_BOOKKEEPING_CORRECTION / NO EXECUTION OR PHYSICS CHANGE`

## Failed binding workflow

The first Increment 9L topology-corrected workflow was:

```text
source Git SHA:
4a9d54e84302d4e329b53b5a650be401296ac05d

workflow run:
31687885990

job:
94408149222
```

Source-scope verification, dependency installation, and failed Increment 9L precursor authority verification passed. The workflow stopped before executing the FVM runner while verifying the older authoritative topology-correction precursor.

## Mismatch

The older topology-correction source records:

```text
run:
31619671593

job:
94191039227

source SHA:
618f49c0a75620751cb517d669a4da868e82f41e

artifact ID:
9150769457

recorded artifact SHA256:
2d00f5fc739a218657de9cc82d0fb1193649decfa3d4813d15ef0782d8dc6927
```

GitHub live immutable metadata confirms the same run, job, source SHA, artifact ID, artifact name, and non-expired status, but the artifact digest is:

```text
artifact name:
u3-b2-a1-weak-compression-bridge-increment-4f-31619671593

correct authoritative artifact SHA256:
64ce6c2ee282163a841c3df518f27bd45eac6bf2e3c91a061ff3007bbab09034
```

Therefore only the recorded artifact digest binding was stale or incorrect.

## Classification

```text
workflow / authority bookkeeping defect
```

This is not:

```text
a physical failure
a root-topology failure
a conservation failure
a change in B1 behavior
a change in the Increment 9L state-machine design
```

No FvmSolver step was attempted by the failed binding workflow.

## Correction

Increment 9L shall retain the existing topology-correction implementation and bind its precursor authority to:

```text
source SHA:
618f49c0a75620751cb517d669a4da868e82f41e

workflow run:
31619671593

job:
94191039227

artifact ID:
9150769457

artifact name:
u3-b2-a1-weak-compression-bridge-increment-4f-31619671593

artifact SHA256:
64ce6c2ee282163a841c3df518f27bd45eac6bf2e3c91a061ff3007bbab09034
```

The old digest remains visible in the historical source and correction records. It shall not be silently overwritten; this record supersedes only that authority-binding field for Increment 9L.

## Invariants

The correction does not change:

```text
Guard-front topology algorithm
root-selection logic
B1 equations or guards
production adapter
FvmSolver core
locked B2 contract
tolerances
chi cap
scan node counts
state-machine transitions
closure model
```

## Evidence requirement

The corrected workflow shall verify the live artifact metadata and include a dedicated authority-correction JSON recording:

```text
failed binding run/job/source
stale recorded digest
correct live digest
run/job/source/artifact/name equality
artifact non-expired
physics/model changes = false
```

Only after this binding gate passes may the topology-corrected Increment 9L FVM trajectory execute.

## Formal-state boundary

All formal verification, acceptance, validation, approval, design-use, and production-activation fields remain false.
