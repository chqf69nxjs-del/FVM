# Stage 7 U3 B2 A1 Increment 9M A2 live FVM composition closeout

## Status

```text
IMPLEMENTED
MODEL-MANAGED LIVE FVM COMPOSITION EXECUTED
EXACT INCREMENT 9L BEHAVIORAL EQUIVALENCE PASS
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
NOT VERIFIED / NOT ACCEPTED / NOT VALIDATED / NOT APPROVED
```

## Objective completed

Increment 9M A2 placed the A0 `PhysicsBoundaryModelManager` and A1 transactional delegate composer in the actual `FvmSolver` right-boundary flux path. The locked `LIQUID_SMALL_DROP` initial state was rebuilt from the locked B2 contract and advanced with one solver instance from `t = 0`, step 0, to nominal `2L/c0`.

No Increment 9L checkpoint state was used. The immutable Increment 9L artifact was used only after the run as comparison authority.

## Authoritative execution

```text
source Git SHA:
947b0f0bf006e8015c3c109e57a8aeb7460cca02

branch:
agent/u3-b2-a1-9m-a2

workflow run / job:
31719604102 / 94512927800

conclusion:
SUCCESS

artifact ID:
9189445884

artifact name:
u3-b2-a1-increment-9m-a2-31719604102

artifact SHA256:
4678ecd9f919ea513bed16652a1fe5b484d6c664b74209bf7dbaffa2dc0a2b64

artifact expired:
false
```

All workflow stages passed: protected-source checks, wrapper-only checks, parent authority and manifest verification, the 32 A0/A1 tests, the actual A2 trajectory, exact-equivalence inspection, artifact upload, and final require.

## Live composition

```text
one FvmSolver
    -> ModelManagedLiveFvmHook
        -> PhysicsBoundaryModelManager
        -> A1 transactional composer
        -> existing Increment 9L delegates
```

The manager selected the active model. Existing Increment 9L delegates continued to own root search, B1/Hugoniot calculations, admissibility gates, and flux construction. No physical equation was copied into the manager or A2 wrapper.

After a successful transactional manager commit, A2 restored the exact successful delegate context and flux through the existing `_install_context(context, U, t)` method. It did not reconstruct a root, replace EOS values, or modify the physical flux.

```text
successful context restorations:
640 / 640 accepted steps

restoration gate:
PASS for every accepted step

root reconstruction by manager:
false

flux modification by manager:
false
```

## Manager transition history

Exactly two transitions were recorded.

```text
1. outward_flow_model
   observed step: 484
   time: 0.0032365792102672024 s
   THREE_BRANCH_WAVE_MODEL
       -> GENERAL_EOS_FINITE_COMPRESSION
   trigger: FINITE_COMPRESSION_MODEL_REQUIRED

2. boundary_regime
   observed step: 638
   time: 0.004269583083221582 s
   OUTWARD_FLOW
       -> ZERO_TRANSFER_CLOSED
   trigger: NO_ADMISSIBLE_ISLAND
```

Both events record `absolute_step_number_trigger_used = false`. Step and time are evidence fields only.

## End-to-end result

```text
accepted steps:
640

final solver step:
640

final time / target 2L/c0:
0.004285834855172021 s

horizon error:
0.0 s

starting state SHA256:
deaae67e672d92fb1da7c40b1a7a03d904b58f35db12bcec81008b55f9014c21

final state SHA256:
8e73e394f3101840c73c278bbc4521ec4fefeebaee4c7f0db774d87013fd5014

OUTWARD_FLOW:
637 steps

ZERO_TRANSFER_CLOSED:
3 steps

public transition count:
1

chatter:
false
```

## Exact Increment 9L equivalence

A2 matched the immutable Increment 9L authority exactly for starting and final state SHA256, accepted-step count, final step/time, transition sequence, state/model/branch counts, closed-flux identities, positivity and liquid-phase gates, conservation metrics, and selected key evidence CSV SHA256 values.

No exact-field mismatch and no selected evidence-file mismatch was reported.

```text
outcome:
INCREMENT_9M_A2_EXACT_INCREMENT_9L_BEHAVIORAL_EQUIVALENCE_PASS
```

The cumulative residuals were identical to the Increment 9L authority:

```text
mass:       2.6461309272224343e-17 kg
momentum:   1.214306433183765e-17 kg m/s
energy:     9.457323812966933e-12 J
```

## Protected-source confirmation

A2 did not modify the A0 manager, A1 composer, Increment 9L delegates, `FvmSolver`, B1, the locked B2 contract, production adapter, EOS/Hugoniot equations, tolerances, or chi scope.

## Claim boundary

A2 proves architecture and behavior are exactly equivalent to the provisional Increment 9L path. It does not prove that the near-zero-flow closure is the unique physical solution. The strongest permitted state remains `PROVISIONAL ENGINEERING END-TO-END WORKING SLICE`.

All formal fields remain false:

```text
finite_compression_branch_approved
multi_step_finite_compression_continuation_authorized
full_two_l_over_c0_passed
formal_state_promoted
u3_b2_finite_pipe_execution_complete
single_phase_finite_pipe_coupling_verified
u3_b2_verification_benchmark_accepted
physical_validation
design_use_acceptance
production_hem_activation_approved
```

## Increment 9M status

```text
A0 pure manager semantics: COMPLETE
A1 delegate composition: COMPLETE
A2 live FVM composition and exact 9L equivalence: COMPLETE
```

## Next controlled work

Build a reusable working-tool shell around the A2 path without adding new physics: normal case input, reusable run API, structured transition/warning log, standard CSV/NPZ outputs, concise run summary, explicit provisional-model warning, and behavioral regression against A2 authority.

Re-entry, reverse-flow physics, two-phase activation, new closure criteria, hysteresis validation, physical validation, design approval, and production integration remain deferred.
