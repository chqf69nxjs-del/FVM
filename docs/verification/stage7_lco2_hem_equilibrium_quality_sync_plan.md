# Stage 7 — Pure-CO2 HEM Equilibrium-Quality Synchronization

## Status

`VALIDATED IMPLEMENTATION DRAFT; VERIFICATION ONLY; NOT PRODUCTION HEM ACTIVATION`

The governing design contract is recorded in
[`stage7_lco2_hem_equilibrium_quality_sync_spec.md`](stage7_lco2_hem_equilibrium_quality_sync_spec.md).

## Objective

Add the minimum dynamic HEM consistency operator required before a nonuniform
pure-CO2 two-phase FVM case:

```text
rho, rho*u, rho*E
        ↓ recover u, E, e
explicit equilibrium phase/quality evaluation from rho/e
        ↓
rho*q <- rho*q_eq
```

The operator removes disagreement between the fourth transported conservative
component and the equilibrium quality implied by the primary conservative state.
It does not add a finite-rate phase-change law or an independent latent-energy
source.

## Implementation boundary

This increment adds:

- `HEMQualityEvaluation`, a minimal evaluator result contract;
- `HEMEquilibriumQualitySyncConfig`;
- `HEMEquilibriumQualitySyncResult` with cellwise and scalar diagnostics;
- `HEMEquilibriumQualityProjection`;
- an adapter to the reviewed explicit CoolProp phase-classification path;
- pure tests, an analytic strict-EOS FVM-slot test, and installed-CoolProp tests.

It does not modify:

- `FvmSolver` control flow;
- Rusanov or physical fluxes;
- CFL calculation;
- external boundaries or internal interfaces;
- source terms;
- the existing generic `HEMPhaseChange` and HNE skeletons;
- production EOS defaults or configuration;
- any physical-Validation or design-use flag.

## Why a separate projection is required

The PR #57 strict verification EOS rejects a state when transported quality does
not match equilibrium quality. The generic `HEMPhaseChange` skeleton first calls
`eos.primitive_from_conserved(U)` and only then asks for equilibrium quality.
That ordering cannot repair a mismatch because the strict EOS rejects the state
before the operator reaches its projection step.

The new projection therefore evaluates phase and equilibrium quality directly
from `rho/e`. It deliberately ignores the supplied EOS object in the
`PhaseChangeModel.apply` compatibility method.

## Conservative invariant

For every successful call:

```text
U_after[..., rho]   == U_before[..., rho]    bitwise
U_after[..., rho*u] == U_before[..., rho*u]  bitwise
U_after[..., rho*E] == U_before[..., rho*E]  bitwise
U_after[..., rho*q] =  rho*q_eq
```

The first three components are checked with `numpy.array_equal`.

No conservative total-energy correction is applied. For a single-component HEM
state, `rho/e` already identifies the equilibrium thermodynamic state; changing
`rhoE` again during the quality-label projection would risk double-counting the
same equilibrium physics.

## Fail-fast scope

The first implementation accepts only:

```text
compressed_or_subcooled_liquid
liquid_vapor_two_phase
single_phase_vapor
```

with `scope_status == supported_candidate` and explicitly defined equilibrium
quality.

It rejects the whole call without partially modifying the input when any cell
contains:

- non-finite conserved data;
- non-positive density;
- non-finite internal energy;
- transported quality outside `[0, 1]`;
- undefined or non-finite equilibrium quality;
- equilibrium quality outside `[0, 1]`;
- critical, high-temperature supercritical, solid/below-triple, unknown, or other
  unsupported phase classification;
- backend or evaluator failure;
- inconsistent evaluator array shapes.

The operator does not clip transported or equilibrium quality.

## Activation tolerance and no-op behavior

`activation_tolerance` determines whether a cell is counted as projected.

```text
projection_applied = abs(q_eq - q_before) > activation_tolerance
```

For cells within the tolerance, the original `rho*q` value is preserved bitwise.
This makes an already equilibrated state a true no-op and supports idempotence.
All cells must still satisfy:

```text
abs(q_after - q_eq) <= activation_tolerance
```

## Diagnostics

Each successful result records:

```text
U_before / U_after
rho / e
q_before / q_equilibrium / q_after
delta_q / delta_rho_q
raw_phase / phase_class / scope_status
projection_applied
```

The scalar summary records:

- cell count;
- projected-cell count;
- evaporation-cell count;
- condensation-cell count;
- maximum absolute quality correction;
- sum of `delta_rho_q`;
- bitwise mass, momentum and energy preservation;
- quality synchronization within tolerance;
- explicit false production, physical-Validation and design-use flags.

Positive `delta_q` denotes vapor generation; negative `delta_q` denotes
condensation.

## Gate A — pure operator tests

Dependency-free tests require:

1. exact bitwise no-op for an equilibrated state;
2. correction of intentional positive and negative quality mismatch;
3. unchanged input array;
4. bitwise preservation of the first three conservative components;
5. idempotence;
6. evaporation/condensation diagnostic signs;
7. rejection of guarded, unknown, unsupported or quality-undefined states;
8. rejection of out-of-range transported quality without clipping;
9. validation of `dt` and time arguments in the phase-change-slot adapter.

## Gate B — existing FVM phase-change slot

A dependency-free analytic strict HEM EOS creates a small nonuniform four-cell
state. The EOS rejects transported/equilibrium quality mismatch. Rusanov
diffusion creates a mismatch at the internal transition, and the projection runs
through the existing post-source phase-change slot.

Required evidence:

```text
at least one projected cell
post-projection strict EOS evaluation succeeds
rho / rho*u / rho*E bitwise unchanged by projection
phase-vapor source equals integrated delta_rho_q
phase-energy conservative delta = 0
phase-vapor budget residual closes
second projection is a no-op
```

This is a software-path verification case, not a real-fluid accuracy result.

## Gate C — installed CoolProp representative states

The projection is exercised for:

```text
8 MPa / 280 K dense-liquid candidate -> q_eq = 0
2 MPa / q=0.50 open two-phase state -> q_eq = 0.50
1 MPa / 280 K vapor candidate        -> q_eq = 1
```

Intentional transported-quality mismatch must be corrected without modifying
mass, momentum or total energy.

## Gate D — strict PR #57 EOS handoff

For a `2 MPa / q=0.50` state, transported quality is intentionally initialized at
`0.40`.

Expected sequence:

```text
strict VerificationHEMEquilibriumEOS rejects pre-projection state
projection repairs rho*q
strict VerificationHEMEquilibriumEOS accepts post-projection state
```

## Validation evidence

Primary corrected validation completed at head
`341657d17789d5b53b875f3f790c227f136e09d2`.

```text
workflow run:          29800804296
artifact ID:           8483707741
artifact SHA256:       bdf06b22fbc81ca044ed57dfab9b3a18987c05914bc03b0da3734dc7e7885a6f
focused tests:         72 passed, 0 failed, 0 errors, 0 skipped
full repository:       478 passed, 0 failed, 0 errors, 0 skipped
focused duration:      3.109 s
full duration:         152.2 s
committed diff check:  success
tracked-file check:    success
artifact upload:       success
```

The focused inventory includes the new synchronization tests together with the
phase-classification, equilibrium-sound-speed and uniform-state-preservation
suites. Gates A–D all passed.

The first temporary validation run (`29800573582`) also passed both focused and
full tests. It failed only because generated JUnit XML files were intentionally
untracked and the post-test check used `git status --porcelain`. The workflow was
corrected to check tracked files only with `--untracked-files=no`; no source,
test or numerical result changed as part of that correction.

At the corrected validation head, the four permanent CoolProp regression
workflows also passed:

```text
CoolProp Wave Regression:                 29800804335
CoolProp Controlled Pressure Ramp:        29800804313
CoolProp Boundary Reflection Regression:  29800804298
CoolProp Internal Valve Regression:       29800804342
```

## Deferred gate — real-fluid nonuniform dynamic run

This implementation does not yet claim the fixed real-CO2 weak pressure-offset
run from the specification. The next increment will add:

```text
left:  p near 2.01 MPa, q near 0.45, u = 0
right: p near 1.99 MPa, q near 0.55, u = 0
all initial cells in open two-phase scope
transmissive boundaries
short first-order run at low CFL
```

That run must demonstrate nonzero projection while remaining inside the open
two-phase region. It will also produce the human-review plots defined in the
specification.

## Required flags

```text
verification_only = true
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
numeric_accuracy_band_approved = false
```

## Next gate

1. remove the temporary validation workflow and confirm the permanent four-file diff;
2. complete final-head permanent CI and merge this operator foundation;
3. add the fixed weak pressure-offset real-CO2 run and saved artifacts;
4. add human-review plots from saved artifacts only;
5. run the equal-pressure nonuniform contact/no-op case;
6. only then attempt liquid-to-two-phase phase-boundary crossing.
