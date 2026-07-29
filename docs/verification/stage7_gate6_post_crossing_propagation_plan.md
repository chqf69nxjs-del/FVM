# Stage 7 Gate 6 post-crossing propagation review — first increment

## Status

`ACTIVE GATE 6; SPECIFICATION FIRST; CONTRACT LOCKED BEFORE RESULTS; VERIFICATION ONLY`

This implementation follows Issue #98 and its pre-execution case-ID erratum. The
authoritative merged PR #77 case identifier is:

```text
pipeline_crossing_candidate_p5m5_to_p2m5
```

## Objective

Replay the accepted 5 -> 2 MPa first crossing exactly, then continue the accepted
projected state for the fixed offsets:

```text
+1 / +4 / +16 / +64 accepted steps
```

The result may either reach all four checkpoints or stop earlier through an
explicit categorized fail-safe outcome.

## Exact baseline gate

Continuation is prohibited unless all retained PR #77 values match exactly:

```text
outcome:                 ACCEPTED_FIRST_CROSSING
step:                    125
time:                    7.999325695335248e-4 s
cell:                    29
distance from outlet:    0.078125 m
maximum q_eq:            3.773646403587342e-6
final-state SHA256:      170ce66c02a320d50389d0cf26fed78f21042f83dec6f64a0978e451cd91e361
run-signature SHA256:    28a5f8b1fd43f6208807bd15d96eaf09a568349007a1994273717aa264505fea
```

## Fixed numerical scope

```text
pure CO2 / CoolProp:           8.0.0
pipe:                          1.0 m / 0.10 m / 32 cells
initial state:                 5 MPa / 5 K subcooling / u=0 / q=0
left boundary:                 reflective
right boundary:                prescribed 2 MPa / 5 K subcooling
CFL:                           0.10
flux:                          existing first-order Rusanov
crossing evidence threshold:   1e-6
```

The production solver, flux, phase classifier, sound-speed formula, boundary,
quality projection, threshold, and tolerances are unchanged.

## Continuation method

1. Run the unchanged PR #77 runner to its accepted first crossing.
2. Require exact scalar and SHA identity.
3. Use the retained projected accepted state as the initial state of a new
   verification-only continuation segment at the same absolute time and step.
4. Reconstruct the same boundary schedule.
5. For each new FVM step:
   - evaluate raw rho/e regions and transition events;
   - allow supported liquid/open-two-phase persistence and reverse transitions;
   - apply the unchanged equilibrium-quality projection;
   - recover the strict mixed accepted-state EOS;
   - require the second projection to be an exact no-op;
   - retain conservative and vapor-mass budgets;
   - record sound-speed derivative evidence where observable.
6. Stop after +64 accepted steps or through a categorized fail-safe outcome.

The continuation budget is referenced to the accepted crossing state. The
complete PR #77 baseline budget remains retained separately in the exact replay.

## Required evidence

```text
summary JSON
checkpoint CSV
cell-history CSV
transition-event CSV
inventory / vapor-budget CSV
Markdown report
phase-region space-time figure
quality / void-fraction space-time figure
pressure / sound-speed figure
inventory-residual figure
JUnit XML
runtime / Git provenance
artifact digest
```

## Initial classification rules

The implementation may retain:

```text
POST_CROSSING_REGION_PERSISTS
POST_CROSSING_REGION_PROPAGATES
POST_CROSSING_REGION_DECAYS
POST_CROSSING_GUARD_LIMIT_REACHED
PHASE_CLASSIFIER_CHATTER_OBSERVED
PROJECTION_RECOVERY_STABLE
CONSERVATION_BUDGET_STABLE
PROPAGATION_REVIEW_INCONCLUSIVE
```

No classification approves physical accuracy.

## Approval boundary

All remain false in this implementation PR:

```text
Gate_6_execution_complete
post_crossing_propagation_approved
near_saturation_acoustic_continuity_approved
two_phase_acoustic_accuracy_band_approved
CFL_independent_crossing_verified
mesh_independent_crossing_verified
Gate_P2_passed
physical_validation
design_use_acceptance
production_hem_activation_approved
```
