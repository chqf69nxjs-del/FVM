# Stage 7 U3 B2 A1 finite-compression Increment 7 result

## Status

`MODEL_REVIEW_ONLY / EIGHT_ACTUAL_FVM_STEPS_PASS / NOT_FORMALLY_VERIFIED`

## Authoritative evidence

```text
source Git SHA:
559f34e9e578b8335295dc2ee16f975b9fdad586

workflow run:
31653551138

job:
94302870493

artifact:
9163478011

artifact name:
u3-b2-a1-finite-compression-increment-7-31653551138

GitHub artifact SHA256:
f208ac3a5125c7cd5265af6e0b19ef7705eee85614d282a639a3263223734de1

outcome:
FINITE_COMPRESSION_INCREMENT_7_HUGONIOT_8_STEP_PASS
```

The workflow completed source-scope inspection, Increment 6 GitHub metadata and digest verification, Increment 6 internal SHA256 verification, eight actual `FvmSolver` updates, full evidence inspection, internal artifact SHA256 inspection and artifact upload.

## Execution result

```text
starting solver step:
484

final solver step:
492

accepted steps:
8

starting solver time:
0.0032432861683330846 s

final solver time:
0.003296941966003099 s

branch:
FINITE_COMPRESSION_HUGONIOT for all eight steps

branch transitions:
0

clear five-point chatter:
false

maximum halving count:
0
```

Accepted time steps remained between:

```text
6.706961501730249e-6 s
6.706988735834439e-6 s
```

## Root sequence

The requested Hugoniot-root `chi` increased smoothly:

```text
step 485:
1.075407409667969e-6

step 492:
1.3760337829589844e-6
```

The selected root pressure offset increased from:

```text
204.04549738578498 Pa
```

to:

```text
261.08453609235585 Pa
```

The fixed diagnostic cap remained:

```text
1.0e-4
```

so the final selected root remained well inside the pre-fixed diagnostic observation scope.

The maximum absolute compatibility residual was:

```text
9.975014009233618e-9 kg/s
```

inside the unchanged absolute root tolerance:

```text
1.0e-8 kg/s
```

Every selected root retained:

```text
unique successful-domain bracket
monotone nonincreasing fixed-scan residuals
negative local residual slope
general-EOS Hugoniot closure
identity-accounted Hugoniot equivalence
Lax 1-shock ordering
entropy bound
B1 success
outward subsonic liquid state
stagnation pressure above back pressure
energy and reaction-ledger closure
```

The minimum root stagnation-pressure margin above back pressure was:

```text
38.180334532633424 Pa
```

The entropy deltas remained at numerical zero scale. The minimum recorded value was:

```text
-1.1368683772161603e-12 J/(kg K)
```

well inside the fixed numerical bound:

```text
-1.0e-7 J/(kg K)
```

## Final accepted state

```text
outlet pressure:
4949761.868058326 Pa

outlet velocity:
+0.11869397089115863 m/s

outlet Mach:
0.00025481039814647023

outlet phase:
liquid

minimum density:
874.2100374900915 kg/m3

minimum internal energy:
216871.96953483074 J/kg

rho*xv exact zero:
true
```

Maximum absolute closure residuals across the eight steps were:

```text
step mass:
1.7399578748930427e-17 kg

step momentum:
8.334804200982315e-19 kg m/s

step energy:
2.506394397583378e-12 J

cumulative mass:
1.819426770702237e-17 kg

cumulative momentum:
1.214306433183765e-17 kg m/s

cumulative energy:
4.192202140984591e-12 J
```

## Claim boundary

This result establishes only:

> Starting from the authoritative accepted step-484 state, eight additional verification-only actual FVM updates can be accepted using a newly recomputed general-EOS Hugoniot and unchanged B1-compatible root at every step while retaining the fixed physical, numerical and conservation gates.

It does not authorize step 493, a longer continuation, general finite-compression approval, formal B2 finite-pipe Verification, benchmark acceptance, Physical Validation, design use or production activation.

## Formal states

All formal states remain false:

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
