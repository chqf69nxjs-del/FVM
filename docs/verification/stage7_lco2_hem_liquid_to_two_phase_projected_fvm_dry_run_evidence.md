# Stage 7 — Projected Liquid-to-Two-Phase FVM Dry-Run Evidence

## Status

`VALIDATED DRAFT; COMPLETE ONE-STEP PROJECTED CROSSING PATH OBSERVED; FORMAL CASE A/B NOT FROZEN`

This record follows merged PR #70. It regenerates the fixed one-step raw FVM matrix,
applies the existing equilibrium-quality projection, recovers the synchronized mixed
accepted state, verifies a second-projection no-op, and closes projection vapor accounting.

## Validation environment

```text
validated head:            7c04a728b1369ed41f083d68b73deb81e92ac374
workflow run:              30018942238
artifact ID:               8568448978
artifact SHA256:           fc577459c65f29a95179dc5a98ef7813a82f14ba8de945a254626555a29c59da
CoolProp:                  8.0.0
compileall:                success
git diff --check:          success
focused tests:             12 passed, 0 skipped
related Stage 7 HEM:      186 passed, 0 skipped
full repository:          628 passed, 0 skipped
failures / errors:          0 / 0
```

The temporary validation workflow executed the installed-CoolProp matrix without skips.
All four permanent CoolProp workflows also passed on the validated head.

## Fixed raw numerical matrix

```text
cells:              8
pipe length:        1.0 m
pipe diameter:      0.10 m
interface:          between cells 3 and 4
initial velocity:   0 m/s
initial q:          0 exactly
CFL:                0.20
boundaries:         transmissive
physical source:    none
raw FVM steps:      exactly 1
```

```text
strong:   5 MPa / 5 K subcooling -> 2 MPa / 5 K subcooling
moderate: 5 MPa / 5 K subcooling -> 3 MPa / 5 K subcooling
control:  5 MPa / 5 K subcooling -> 4 MPa / 5 K subcooling
```

No case, algorithm, or tolerance was changed after observing PR #70.

## Matrix result

```text
case count:                    3
ACCEPTED_CROSSING:             2
ACCEPTED_ALL_LIQUID_NOOP:      1
RAW_STATE_REJECTED:            0
GUARD_FAILURE:                 0
BACKEND_FAILURE:               0
```

```text
raw_first_order_fvm_crossing_observed = true
equilibrium_quality_projection_exercised = true
post_projection_accepted_eos_exercised = true
second_projection_noop_exercised = true
phase_vapor_budget_exercised = true
complete_one_step_crossing_path_observed = true
actual_first_order_fvm_crossing_verified = false
```

The final `actual_first_order_fvm_crossing_verified` flag remains false because formal
Case A and matched Case B have not yet been frozen and repeatability beyond this fixed
one-step matrix remains a separate gate.

## Strong candidate

```text
case ID:                       strong_p5m5_to_p2m5
raw outcome:                   OPEN_TWO_PHASE
projected outcome:             ACCEPTED_CROSSING
raw crossing cells:            3, 4
first projection cells:        3, 4
second projection cells:       none
maximum first delta q:         5.911503500507591e-4
maximum post q mismatch:       0
projection vapor source:       7.054022964126832e-4 kg
post vapor inventory:          7.054022964126832e-4 kg
```

Crossed cells:

| cell | raw/post region | q raw | q_eq = q post | second q | post pressure | post temperature | post alpha | post c |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 3 | `OPEN_TWO_PHASE` | `0` | `5.911503500507591e-4` | same | `3.9680896849 MPa` | `278.1364573 K` | `4.6051306477e-3` | `40.25590049 m/s` |
| 4 | `OPEN_TWO_PHASE` | `0` | `1.843904990122013e-4` | same | `1.8716583570 MPa` | `251.5064170 K` | `3.8956065955e-3` | `19.93047236 m/s` |

The first projection modified only `rho*q`. Mass, momentum, and total energy remained
bitwise unchanged. The second projection applied to zero cells and returned a bitwise-
identical conservative state.

Budget residuals:

```text
phase-vapor balance residual:          0 kg
projection source consistency:         0 kg
combined post-vapor balance residual:  0 kg
```

## Moderate candidate

```text
case ID:                       moderate_p5m5_to_p3m5
raw outcome:                   OPEN_TWO_PHASE
projected outcome:             ACCEPTED_CROSSING
raw crossing cells:            4
first projection cells:        4
second projection cells:       none
maximum first delta q:         6.844477600333753e-5
maximum post q mismatch:       0
projection vapor source:       6.563798045383618e-5 kg
post vapor inventory:          6.563798045383618e-5 kg
```

Cell 4 remained `OPEN_TWO_PHASE` after projection and was accepted by the mixed EOS at
approximately:

```text
pressure:       2.7261385459 MPa
temperature:    264.1662617 K
q post:         6.844477600333753e-5
alpha:          9.095235725033404e-4
sound speed:    28.01845434 m/s
```

The first projection modified only `rho*q`. The second projection was a no-op. All three
vapor-accounting residuals were exactly zero in the retained evidence.

## Liquid negative control

```text
case ID:                       control_p5m5_to_p4m5
raw outcome:                   ALL_LIQUID
projected outcome:             ACCEPTED_ALL_LIQUID_NOOP
raw crossing cells:            none
first projection cells:        none
second projection cells:       none
maximum first delta q:         0
maximum post q mismatch:       0
projection vapor source:       0 kg
post vapor inventory:          0 kg
```

All cells remained `LIQUID_CANDIDATE`. The first and second projections were both no-ops,
and the strict mixed accepted-state EOS recovered finite positive liquid pressure,
temperature, and sound speed.

## Common invariants

Every case satisfied:

```text
first projection cells = raw crossing cells
second projection cell count = 0
rho bitwise unchanged by projection
rho*u bitwise unchanged by projection
rho*E bitwise unchanged by projection
q_post = q_eq exactly in retained evidence
post region = raw thermodynamic region
post pressure finite and positive
post temperature finite and positive
post sound speed finite and positive
projection source counted once
projection-only vapor budget closed
combined raw-boundary-plus-projection vapor budget closed
```

## Technical interpretation

The fixed strong and moderate cases now demonstrate the complete verification chain for one
first-order time step:

```text
all-liquid accepted initial state
        |
        v
actual Rusanov/CFL FVM update
        |
        v
raw liquid-to-open-two-phase transition
        |
        v
equilibrium-quality projection on exactly the crossed cells
        |
        v
synchronized mixed liquid/open-two-phase accepted state
        |
        v
second projection no-op
        |
        v
closed projection vapor-mass account
```

The nearest pressure-span control remained liquid and generated no projection source.

This evidence establishes a complete **one-step projected crossing path observation**. It
does not yet establish repeatable multi-step behavior, formal Case A/B freeze, endpoint
acoustics, physical Validation, an approved acoustic accuracy band, production HEM, or
design use.

## Approval boundary

```text
verification_only = true
raw_first_order_fvm_crossing_observed = true
complete_one_step_crossing_path_observed = true
actual_first_order_fvm_crossing_verified = false
case_a_frozen = false
case_b_frozen = false
algorithms_or_tolerances_tuned = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Next increment

1. review and merge this one-step projected path;
2. repeat the fixed strong and control cases through a short first-crossing runner;
3. stop immediately after the first accepted crossing;
4. compare the control through the matched physical-time horizon;
5. freeze Case A and matched Case B only after repeatable behavior is demonstrated;
6. then synchronize formal evidence into the central records.
