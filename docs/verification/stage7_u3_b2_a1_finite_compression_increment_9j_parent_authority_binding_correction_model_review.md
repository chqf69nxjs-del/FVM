# Stage 7 U3 B2 A1 Increment 9J parent-authority binding correction

## Status

`MODEL_REVIEW_ONLY / BOOKKEEPING_CORRECTION_ONLY / NO_SOLVER_ADVANCE`

This record corrects only the immutable parent-evidence binding used by Increment 9J. It does not replace or revise the fixed root/endpoint diagnostic method in:

`docs/verification/stage7_u3_b2_a1_finite_compression_increment_9j_zero_flow_endpoint_diagnostic_model_review.md`

The earlier record remains immutable historical evidence. This correction supersedes only its stale parent source SHA and step-637 time identity.

## Failed Increment 9J attempt

The first Increment 9J workflow attempt stopped before running the ultrafine scan or zero-flow endpoint diagnostic.

```text
workflow run:
31671344840

job:
94356427565

failure location:
Verify and bind parent GitHub artifact metadata

classification:
implementation / bookkeeping defect

physical model evaluated:
no

root search evaluated:
no

FvmSolver step 638 attempted:
no
```

The artifact download succeeded, but the workflow compared the artifact metadata against a stale parent source SHA.

## Authoritative parent artifact

The immutable GitHub artifact and its internal evidence establish the following authority chain:

```text
parent workflow run:
31670285271

parent job:
94353300958

parent artifact:
9169437776

parent artifact name:
u3-b2-a1-finite-compression-increment-9i-root-schema-31670285271

parent artifact SHA256:
ed48b82be9f6cc8d6e081a416ab2b61bd97401782279506d83c8afd4d173f5d3

parent workflow head/source Git SHA:
c89a992d69c2985fc081fe3750c5b27136d3941e
```

The downloaded ZIP SHA256 equals the GitHub artifact metadata digest. Its internal `artifact_sha256.txt` manifest contains 14 entries, and all 14 files reproduce their recorded SHA256 values.

## Authoritative accepted state

The parent artifact `summary.json`, `finite_compression_full_horizon_states.npz`, step ledger, and root ledger agree on:

```text
outcome:
INCREMENT_9I_STOPPED

starting solver step:
636

additional accepted steps:
1

final solver step:
637

final solver time:
0.004269583083221582 s

nominal target:
0.004285834855172021 s

remaining nominal time:
1.6251771950439448e-5 s

final conserved-state SHA256:
7d2633e58adcc36e7ea7a1204af95455f5e8942e2c4e9a6dbf76cf437efd2a25

stop classification:
DiagnosticStop

stop reason:
dynamic seeded interval contains no admissible island
```

The accepted step-637 root recorded by the authoritative parent artifact is:

```text
root chi:
1.3736804864166541e-5

root pressure:
4,950,000.003429235 Pa

root velocity:
0.0012307192355706714 m/s

root Mach:
2.642066500018377e-6

root mass residual:
2.1291983346252187e-9 kg/s

root stagnation-pressure margin above back pressure:
0.004147276282310486 Pa

root phase:
liquid

root gate:
PASS
```

The state remains positive, finite, single-phase liquid, outward and subsonic. `rho*xv` remains exact zero. The accepted-step mass, momentum, and energy ledgers close within their unchanged gates.

## Stale bindings being corrected

The failed Increment 9J source bound the parent evidence to:

```text
stale/non-resolvable source SHA:
8d0568abd827684562783393650d6f63f3aa390f

stale step-637 time:
0.0042695827462251995 s
```

The stale SHA is not the head SHA recorded by GitHub for artifact `9169437776`, is not the `source_git_sha` recorded inside that artifact, and is not resolvable as a commit in the repository's current history.

## Limited correction

The correction wrapper shall override only:

```text
PARENT_SOURCE_SHA = c89a992d69c2985fc081fe3750c5b27136d3941e
EXPECTED_TIME_S = 0.004269583083221582
```

Before overriding, it shall assert that the imported Increment 9J diagnostic still contains the exact stale values identified above and that the fixed run, job, artifact, artifact name, step, scan sizes, scope limits, and tolerances remain unchanged.

No change is permitted to:

```text
Hugoniot equations
B1 behavior
local admissibility
root residual tolerance
velocity-zero tolerance
chi lower bound or cap
4097-node ultrafine interval
513-node endpoint interval
boundary-refinement rule
root topology rule
FvmSolver
production Adapter
locked B2 Contract
accepted parent state
```

## Rerun rule

The corrected workflow shall:

1. bind run `31670285271`, job `94353300958`, artifact `9169437776`, source `c89a992...`, and artifact digest `ed48b82b...`;
2. verify the parent artifact metadata and internal manifest;
3. load the exact step-637 state without mutation;
4. execute the already-fixed Increment 9J diagnostic only;
5. keep solver step 638 unattempted;
6. accept only one of the two predeclared supported classifications;
7. fail closed for every other result.

## Formal-state boundary

Regardless of the corrected diagnostic result, retain:

```text
finite_compression_branch_approved = false
multi_step_finite_compression_continuation_authorized = false
full_two_l_over_c0_passed = false
formal_state_promoted = false
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
