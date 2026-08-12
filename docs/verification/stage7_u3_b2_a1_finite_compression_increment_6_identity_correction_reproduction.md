# Stage 7 U3 B2 A1 finite-compression Increment 6 identity-correction reproduction

## Status

`MODEL_REVIEW_ONLY / REPRODUCTION_CONFIGURATION_CORRECTION / FIXED_BEFORE_RERUN`

This note corrects one omitted Increment 5 numerical-identity setting in the first Increment 6 one-step run. It does not change the Hugoniot equation, EOS state, density root, B1, Lax ordering, entropy bound, compatibility-root tolerance, diagnostic `chi` cap, solver update, or any formal project state.

## First Increment 6 run

```text
source Git SHA:
a2e09032108a4fd80b9df79288ad948256af23af

workflow run:
31652640473

job:
94300122587

conclusion:
failure
```

The run completed:

```text
source and scope inspection
accepted step-483 artifact download
Increment 5 artifact download
GitHub artifact metadata and digest verification
```

It stopped before root completion, flux construction, `compute_dt`, or actual solver step 484 with:

```text
independent Increment 5 reproduction did not support one-step review:
ROOT_OR_LEDGER_FAILURE
```

No Increment 6 evidence directory was created and no artifact was uploaded.

## Cause

The authoritative Increment 5 result includes the fixed enthalpy-identity correction:

```text
abs(H_e) <= 1.0e-6 J/kg
abs(H_h) <= 1.0e-6 J/kg
raw H_e - H_h recorded but not directly gated at 1.0e-8 J/kg
identity-accounted difference <= 1.0e-10 J/kg
```

The Increment 6 independent reproduction selected the final identity-corrected Hugoniot class, but did not set the core raw-form comparison to its Increment 5 observation limit before calling the core diagnostic.

The core density solver therefore reapplied the superseded raw `1.0e-8 J/kg` direct gate and rejected the same states that the authoritative Increment 5 correction had already shown to satisfy both physical Hugoniot closures and the identity-accounted equivalence.

The failure occurred during reproduction configuration, not in the authoritative Hugoniot root, B1, Lax condition, energy ledger, or actual FVM update.

## Fixed reproduction

Before invoking the Increment 5 core diagnostic inside Increment 6, apply exactly the authoritative Increment 5 setting:

```text
HUGONIOT_EQUIVALENCE_TOLERANCE_J_KG
= HUGONIOT_ENERGY_TOLERANCE_J_KG
= 1.0e-6 J/kg
```

This value is only the observation limit for the raw two-form difference. The final identity-corrected Hugoniot class still requires:

```text
identity-accounted difference <= 1.0e-10 J/kg
```

and both physical Hugoniot forms must independently satisfy:

```text
abs(H_e) <= 1.0e-6 J/kg
abs(H_h) <= 1.0e-6 J/kg
```

No new tolerance is introduced. The rerun reproduces the already-authoritative Increment 5 numerical treatment.

## Rerun boundary

Rerun the unchanged Increment 6 one-step specification through a narrow wrapper that sets only this reproduction configuration before calling the existing Increment 6 runner.

The actual solver step remains authorized only if the independently recomputed root matches Increment 5 and every pre-step gate passes.

All formal states remain false regardless of result.
