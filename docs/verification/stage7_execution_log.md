# Stage 7 Execution Log

Earlier entries through the V-013 reference-core checkpoint are preserved in
[`archive/stage7_execution_log_through_v013_reference_core.md`](archive/stage7_execution_log_through_v013_reference_core.md).

## 2026-07-19 to 2026-07-20 — V-013 reference baseline

### PR #48 — incident propagation

Status: `OBSERVED; MERGED`. Merge commit:
`613b21622b22402fbf7b8d77b1d881db7ff5f28e`.

```text
primary run:         29647234616
focused / full:      39 / 315 passed
CoolProp:            8.0.0
n=400 peak ratio:    0.57499430
```

Wave direction and approximate propagation speed were consistent. Strong numerical
broadening remained material at the finest mesh.

### PR #49 — rigid-wall reflection

Status: `OBSERVED; MERGED`. Merge commit:
`bc874193de6a4c019073b6cf629e99ec5dfa6602`.

```text
workflow run:       29684930259
focused tests:      57 passed, 0 skipped
full repository:    350 passed, 0 skipped
artifact ID:        8441899419
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

Pressure reflection was positive, velocity reflection was negative, and wall-face
velocity, mass flux, and energy flux were exactly zero.

### PR #50 — fixed-pressure reflection

Status: `OBSERVED; MERGED`. Merge commit:
`f403103c46a1d618ce2f2345c986e29b921b664a`.

```text
workflow run:       29692477941
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
artifact ID:        8444138380
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
n=400 peak ratio:   0.57212615
```

The reflected pressure sign was negative, reflected velocity sign was positive, and the
returning characteristic was left-going `A-`.

### PR #51 — first-order baseline formalization

Status: `FORMALIZED; MERGED`. Merge commit:
`62390bd526ae99b6702f4ed76e3594e1bf01259b`.

## 2026-07-22 — first liquid-to-two-phase crossing groundwork

### PR #64 — boundary-crossing specification

Status: `SPECIFIED; MERGED`. Merge commit:
`f2b8335132741765b6d5e42f65f742cf5e241c66`.

The specification fixed the first narrow gate for a conservative liquid-to-open-two-phase
transition. It requires raw phase evaluation directly from updated `rho/e`, before quality
projection, and separates:

```text
thermodynamic crossing
projection activation
accepted-state EOS evaluation
test-evidence threshold
```

It retained the current `e >= 0` solver integration guard and prohibited clipping,
hysteresis, fallback, reverse-crossing support, production activation, or tolerance tuning.

Exact saturated-liquid endpoint landing remains fail-fast with:

```text
endpoint_acoustic_closure_not_established
```

### PR #65 — boundary-region and transition classifier

Status: `IMPLEMENTED; MERGED`. Merge commit:
`fb078da84fa17d6aa8d840616c494a0bf3efd71c`.

The classifier added the verification regions:

```text
LIQUID_CANDIDATE
SATURATED_LIQUID_ENDPOINT
OPEN_TWO_PHASE
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
```

and transition events for no transition, boundary touch, target crossing, reverse
transition, and forbidden transition. Transported quality is not used as the phase
classifier.

Authoritative validation:

```text
validation run:       29927030452
artifact ID:          8532470595
artifact SHA256:      c8968363e4c2cd612fd34a96fcade13bb012dbba1b73ba90568712431d930915
focused tests:        32 passed, 0 skipped
related Stage 7 HEM:  67 passed, 0 skipped
full repository:      546 passed, 0 skipped
failures / errors:     0 / 0
CoolProp:              8.0.0
```

The installed-CoolProp endpoint test confirmed at 2 MPa:

```text
Q=0 -> SATURATED_LIQUID_ENDPOINT
Q=1 -> SATURATED_VAPOR_ENDPOINT
```

### PR #66 — crossing-groundwork central synchronization

Status: `MERGED`. Merge commit:
`7acaa005c6d32cd48042ca5a333dcc19b5006d23`.

The central index and execution log were synchronized through the crossing specification
and transition-classifier milestones. No solver, EOS, flux, CFL, projection, or production
behavior changed.

## 2026-07-22 to 2026-07-23 — accepted mixed-phase EOS and state-pair survey

### PR #67 — mixed liquid/open-two-phase accepted-state EOS

Status: `IMPLEMENTED; VALIDATED; MERGED`. Merge commit:
`74b019993823ec4c52f1be38fa8c12580f560686`.

The verification-only adapter
`VerificationHEMLiquidOpenTwoPhaseEOS` was added for synchronized accepted arrays that
contain both supported liquid and open liquid-vapor two-phase cells.

Accepted per cell:

```text
LIQUID_CANDIDATE
OPEN_TWO_PHASE
```

Rejected per cell:

```text
SATURATED_LIQUID_ENDPOINT
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
critical / supercritical / solid / unknown / backend-invalid
```

The adapter:

- evaluates each cell from canonical `rho/e`;
- requires transported quality to match equilibrium quality within `1e-10`;
- keeps transported quality strictly inside `[0, 1]` without clipping;
- uses the same existing equilibrium sound-speed estimator on liquid and open-two-phase cells;
- rejects non-finite or non-positive acoustic results;
- does not advance `FvmSolver.step()` or activate production HEM behavior.

Real-CoolProp mixed-array evidence used:

```text
5 MPa / 280 K liquid
+
2 MPa / Q=0.50 open two phase
```

The `2 MPa / Q=0` saturated-liquid endpoint was rejected with the expected unresolved
endpoint-acoustic message.

Authoritative validation:

```text
validated head:             e8814c5d724f923a38f3acfa0120c10edde2c202
workflow run:               29933435558
artifact ID:                8535107304
artifact SHA256:            55a0362a7e40b681d017f1ae7405f581129c55acecef81e6e95e5bcf324a0c61
CoolProp:                   8.0.0
focused mixed-EOS tests:   37 passed, 0 skipped
related Stage 7 HEM:      141 passed, 0 skipped
full repository:          583 passed, 0 skipped
failures / errors:          0 / 0
```

Permanent wave, controlled-pressure-ramp, boundary-reflection, and internal-valve
workflows passed on the final branch head before merge. The temporary validation workflow
was removed before merge.

Interpretation:

```text
mixed accepted liquid/open-two-phase primitive evaluation established
actual liquid-to-two-phase FVM crossing not yet exercised
```

### PR #68 — liquid state-pair property survey

Status: `VALIDATED; MERGED`. Merge commit:
`640b69c576501ec812cbc2919f35c62526b15974`.

The deterministic survey created 11 pure-CO2 liquid candidates over 2–5 MPa and
0.5–10 K subcooling. Every candidate was constructed from `P/T`, converted to canonical
`rho/e`, and re-evaluated through the reviewed phase and acoustic paths before acceptance.

Candidate results:

```text
candidate count:             11
accepted liquid candidates:  11
endpoint candidates:          0
guard failures:               0
backend failures:             0
```

Nine controlled ordered pairs were screened through a stationary conservative-blend
proxy. The proxy is a property-screening device only; it is not an FVM step, Rusanov
update, isentropic path, isenthalpic path, or formal crossing result.

Pair results:

```text
pair count:                   9
ALL_LIQUID:                   1
OPEN_TWO_PHASE:               8
endpoint-only pairs:          0
guard/backend/forbidden:      0
```

Leading dry-run candidate:

```text
left:                         5 MPa / 5 K subcooling
right:                        2 MPa / 5 K subcooling
first sampled open fraction:  lambda = 0.1
maximum screened q_eq:        1.3397273027615007e-3
sampled open acoustics:       finite and positive
```

Moderate candidate:

```text
left:                         5 MPa / 5 K subcooling
right:                        3 MPa / 5 K subcooling
first sampled open fraction:  lambda = 0.2
maximum screened q_eq:        5.331295761643359e-4
```

Liquid negative-control candidate:

```text
left:                         5 MPa / 5 K subcooling
right:                        4 MPa / 5 K subcooling
outcome:                      ALL_LIQUID
maximum screened q_eq:        0
```

Within the fixed survey, pressure span was more influential than reducing the
lower-pressure subcooling margin. This is a ledger observation only, not a solver rule or
physical-model approval.

Authoritative validation:

```text
validated head:             cac6887fee4f6accc4be77d59075e0da08fab77d
workflow run:               30008209125
artifact ID:                8563976259
artifact SHA256:            688b7e0c79647a9c203f24317e7404f34e5a471c22852095796f72391ca36f02
CoolProp:                   8.0.0
focused survey tests:       18 passed, 0 skipped
related Stage 7 HEM:       159 passed, 0 skipped
full repository:           601 passed, 0 skipped
failures / errors:           0 / 0
```

Permanent wave, controlled-pressure-ramp, boundary-reflection, and internal-valve
workflows passed on the final branch head before merge. The temporary validation workflow
was removed before merge.

Interpretation:

```text
ledger-backed FVM dry-run candidates established
screening_is_fvm_solution = false
FvmSolver.step exercised = false
Case A frozen = false
Case B frozen = false
```

## Current conclusion — 2026-07-23

Current development main:

```text
640b69c576501ec812cbc2919f35c62526b15974
```

The software now contains the individual verification components required for a first
liquid-to-two-phase dry run:

```text
supported liquid candidates
mixed liquid/open-two-phase accepted-state EOS
direct raw rho/e transition classification
equilibrium-quality projection
existing first-order Rusanov flux and CFL path
```

The remaining gap is not further property screening. It is observation of the actual
first-order conservative update.

The active gate is therefore:

```text
minimal first-order liquid-to-two-phase FVM dry run
```

Recommended first trial matrix:

```text
strong candidate:   5 MPa / 5 K -> 2 MPa / 5 K
moderate candidate: 5 MPa / 5 K -> 3 MPa / 5 K
liquid control:     5 MPa / 5 K -> 4 MPa / 5 K
```

Recommended execution order:

1. start with 8–16 cells, first order, transmissive boundaries, no source, and low CFL;
2. execute and record one raw FVM step before projection;
3. classify each case as all-liquid, endpoint landing, open-two-phase crossing, forbidden,
   guard failure, or backend failure;
4. only after the raw update is understood, connect projection and mixed accepted-state EOS;
5. retain every attempt in a reproducible ledger;
6. freeze Case A and matched Case B only after repeatable behavior is observed.

## Approval boundary

```text
verification_only = true
actual_first_order_fvm_crossing_verified = false
screening_is_fvm_solution = false
case_a_frozen = false
case_b_frozen = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```
