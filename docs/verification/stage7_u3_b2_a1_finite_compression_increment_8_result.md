# Stage 7 U3 B2 A1 finite-compression Increment 8 result

## Status

`MODEL_REVIEW_ONLY / THIRTY_TWO_ACTUAL_FVM_STEPS_PASS / NOT_FORMALLY_VERIFIED`

## Authoritative evidence

```text
source Git SHA:
55d414ac82b63ae93ce2866148af363dc76fa2cb

workflow run:
31654235903

job:
94304991819

artifact:
9163799106

artifact name:
u3-b2-a1-finite-compression-increment-8-31654235903

GitHub artifact SHA256:
45d726b422090c8ce00becb7d66a7a44b309678c0a7cb61b4f842dd08086be8b

outcome:
FINITE_COMPRESSION_INCREMENT_8_HUGONIOT_32_STEP_PASS
```

## Execution result

```text
solver step:
492 -> 524

accepted steps:
32

solver time:
0.003296941966003099 -> 0.003511644475195471 s

branch:
FINITE_COMPRESSION_HUGONIOT for all 32 steps

branch transitions:
0

clear five-point chatter:
false

maximum halving count:
0
```

Accepted time steps remained between:

```text
6.706917121394335e-6 s
6.706998966952139e-6 s
```

## Root sequence

The selected requested `chi` ranged from:

```text
1.4145637512207033e-6
```

to:

```text
2.7214050292968744e-6
```

The selected pressure offset ranged from:

```text
268.3937707655132 Pa
```

to:

```text
516.2656671926379 Pa
```

The final root remained well inside the fixed diagnostic cap:

```text
1.0e-4
```

The maximum absolute root residual was:

```text
9.93613154931583e-9 kg/s
```

inside the unchanged `1.0e-8 kg/s` tolerance.

Every selected root retained the general-EOS Hugoniot closure, identity-accounted equivalence, Lax 1-shock ordering, entropy bound, B1 success, outward subsonic liquid state, negative residual slope, stagnation pressure above back pressure, and energy/reaction-ledger closure.

The minimum root stagnation-pressure margin above back pressure was:

```text
34.81309639289975 Pa
```

## Final accepted state

```text
outlet pressure:
4949472.492122896 Pa

outlet velocity:
+0.11450168837317923 m/s

outlet Mach:
0.00024581151529926953

outlet phase:
liquid

minimum density:
874.2064393625172 kg/m3

minimum internal energy:
216871.94646481038 J/kg

rho*xv exact zero:
true
```

Maximum absolute closure residuals remained at numerical roundoff scale:

```text
step mass:
1.8905775021498536e-17 kg

step momentum:
2.256495771485456e-18 kg m/s

step energy:
6.504130567686374e-12 J

cumulative mass:
2.4867521248309257e-17 kg

cumulative momentum:
1.474514954580286e-17 kg m/s

cumulative energy:
1.2474465904686864e-11 J
```

## Claim boundary

This result establishes only that 32 additional verification-only actual FVM updates can be accepted from the authoritative step-492 state while recomputing the general-EOS Hugoniot and B1-compatible root at every step.

It does not authorize step 525, formal finite-compression approval, benchmark acceptance, Physical Validation, design use, or production activation.

## Formal states

All formal states remain false.
