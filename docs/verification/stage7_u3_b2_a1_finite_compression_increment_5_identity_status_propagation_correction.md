# Stage 7 U3 B2 A1 finite-compression Increment 5 identity-status propagation correction

## Status

`MODEL_REVIEW_ONLY / EVIDENCE_PROPAGATION_CORRECTION / FIXED_BEFORE_RERUN`

This note corrects one evidence-field propagation defect observed in the first enthalpy-identity-corrected Increment 5 rerun. It does not change the Hugoniot equation, CoolProp state construction, density search, B1, Lax ordering, entropy bound, compatibility-root tolerance, diagnostic `chi` nodes, diagnostic cap, or any formal project state.

## Parent rerun

```text
source Git SHA:
3c89512189dd1f19f0d5bf94f7579ea4ef22ca9c

workflow run:
31651902818

job:
94297894819

artifact:
9162881047

artifact name:
u3-b2-a1-finite-compression-increment-5-rerun-31651902818

GitHub artifact SHA256:
769916024115c051b2c7a1e8c5bbef345636de15b4286433cf47405cbed020a7
```

The diagnostic computation completed and uploaded evidence. The later inspection step failed.

## What passed

For all fixed Hugoniot density roots, the corrected identity accounting retained:

```text
maximum absolute raw H_e - H_h:
9.06117065824219e-8 J/kg

maximum absolute identity-accounted difference:
7.389644451905042e-13 J/kg

fixed identity-accounted tolerance:
1.0e-10 J/kg

identity correction gate:
passed
```

The fixed `chi = 1.0e-6` Hugoniot candidate also returned:

```text
B1 outcome:
SUCCESS_UNCHOKED_FACE_MAPPING

compatibility residual:
+0.0009859277105667332 kg/s

Lax 1-shock ordering:
passed

entropy bound:
passed

outward / subsonic / liquid:
passed
```

The next fixed node `chi = 1.05e-6` had a negative compatibility residual, so the physical scan contains a root bracket immediately beyond the approved Weak Compression scope.

## Defect

The corrected density solver returned only after verifying:

```text
identity_accounted_hugoniot_passed = true
```

The subsequent B1 evaluation rebuilt a compact evidence dictionary that did not copy that field. The wrapper then queried the absent field, interpreted it as `false`, and overwrote:

```text
hugoniot_closure_passed = false
local_candidate_admissible = false
```

This caused all otherwise successful Hugoniot scan nodes to be excluded from root topology. It also caused the workflow inspection assertion requiring the propagated field to fail.

The defect is in evidence propagation after a successful density solve. It is not a Hugoniot closure, EOS, B1, Lax, entropy, phase, or root failure.

## Fixed propagation

Use the unchanged identity-corrected density solver. When the core Hugoniot candidate evaluation succeeds after that solver returns, record:

```text
hugoniot_identity_accounted_passed = true
```

and preserve the core evaluation's existing:

```text
hugoniot_closure_passed
local_candidate_admissible
```

No failed density solve may reach this propagation path. Any identity-accounted density failure remains fail-closed before B1 evaluation.

The corrected evidence must demonstrate:

```text
all successful fixed Hugoniot candidates carry the propagated true field
cap Hugoniot residual is finite and positive
Hugoniot residual sequence is monotone nonincreasing
exactly one Hugoniot sign-change bracket exists
any selected Hugoniot root independently passes closure, B1, Lax, entropy,
direction, phase, compatibility residual, energy, and reaction-ledger gates
state remains unchanged
FvmSolver step 484 is not attempted
finite-compression flux is not applied
```

## Formal-state boundary

All approval states remain false regardless of result.
