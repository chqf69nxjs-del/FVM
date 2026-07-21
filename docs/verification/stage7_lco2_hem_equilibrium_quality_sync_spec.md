# Stage 7 — Dynamic Equilibrium-Quality Synchronization Specification

## Status

`PROPOSED; DESIGN REVIEW REQUIRED; NOT IMPLEMENTED`

This document defines the next pure-CO2 HEM increment after the merged uniform-state
preservation work in PR #57. It is a specification only. It does not activate a
production HEM path and does not change solver behavior.

## Objective

Define and verify an operator-split projection that keeps the transported fourth
conservative component, `rho*q`, consistent with the equilibrium quality implied by
the primary thermodynamic state `rho/e`.

For the current four-variable solver,

```text
U = [rho, rho*u, rho*E, rho*q]
```

the first three components remain the primary conservative state. The fourth component
is retained for compatibility with the current flux, diagnostics, phase budgets, and
future HNE development, but it is thermodynamically redundant in a single-component
HEM model.

The required post-update invariant is

```text
q_transport = (rho*q)/rho
q_eq        = equilibrium quality from rho/e
rho*q       <- rho*q_eq
```

while leaving `rho`, `rho*u`, and `rho*E` unchanged.

## Why this gate is required

The first-order FVM transports `rho*q` conservatively. After a spatially nonuniform
update, the transported value can differ from the equilibrium quality obtained from the
updated density and internal energy. The strict verification HEM EOS introduced in PR
#57 intentionally rejects such a mismatch.

A dynamic HEM path therefore needs an explicit operator between the FVM/source update
and the next primitive-state evaluation:

```text
synchronized state at step n
        |
        v
FVM flux update
        |
        v
operator-split source update
        |
        v
rho/e equilibrium evaluation
        |
        v
rho*q equilibrium projection
        |
        v
synchronized state at step n+1
```

The existing `FvmSolver.step()` phase-change slot already has the required location:
it is applied after the conservative FVM update and after source terms, and before the
next time step.

## Existing implementation that must not be reused unchanged

`phase_change.py` already contains a generic `HEMPhaseChange` skeleton. It is not the
selected implementation for this increment because:

1. it calls `eos.primitive_from_conserved(U)` before obtaining equilibrium quality;
2. the strict PR #57 verification EOS rejects the very transported/equilibrium mismatch
   that the projection needs to repair;
3. it clips equilibrium quality silently;
4. it exposes no cellwise phase, mismatch, or projection diagnostics;
5. its current behavior is used by earlier toy-EOS verification and should not be changed
   casually.

The next increment therefore adds a separate verification-only pure-CO2 operator. A
later gate may promote or refactor the generic `HEMPhaseChange` after the new behavior is
validated.

## Selected architecture

### New module

```text
src/liquid_gas_transient/hem_equilibrium_quality_sync.py
```

### Proposed public objects

```python
HEMEquilibriumQualitySyncConfig
HEMEquilibriumQualitySyncReport
HEMEquilibriumQualitySync
project_equilibrium_quality
```

### Evaluator dependency

The projection core receives an injected equilibrium phase evaluator with the effective
contract:

```python
evaluate(rho, e) -> HEMPhaseState
```

The default installed-property path uses
`evaluate_coolprop_hem_phase_state(rho, e)` from PR #55. Dependency injection permits
pure tests with a deterministic fake evaluator and keeps CoolProp tests separate.

The operator must not obtain `q_eq` through `eos.primitive_from_conserved(U)`, because
that route may reject the unsynchronized fourth component before projection.

### Solver integration

`HEMEquilibriumQualitySync` implements the existing `PhaseChangeModel.apply()` shape:

```python
apply(U, eos, dt, t) -> U_after
```

The `eos` parameter remains part of the structural solver interface. The quality
projection obtains equilibrium state through its injected evaluator, not through the
transported-quality-sensitive primitive conversion.

No change to `FvmSolver`, Rusanov flux, CFL, boundaries, source terms, or interfaces is
required for the first increment.

## Projection algorithm

For every cell:

1. validate the conservative-array shape and finite values;
2. recover

   ```text
   rho = U[rho]
   u   = U[rho*u] / rho
   E   = U[rho*E] / rho
   e   = E - u^2/2
   q_before = U[rho*q] / rho
   ```

3. require finite positive `rho`, finite `e`, and finite transported quality;
4. require transported quality to lie within the configured bound tolerance around
   `[0, 1]`; do not clip it;
5. evaluate explicit phase state from `rho/e`;
6. require `scope_status == supported_candidate`;
7. require equilibrium quality to be explicitly defined;
8. require the phase class to be allowed by configuration;
9. set

   ```text
   q_after       = q_eq
   (rho*q)_after = rho*q_eq
   ```

10. return a new state array;
11. verify that columns `rho`, `rho*u`, and `rho*E` are bitwise unchanged;
12. store a detailed projection report.

The operation is independent of `dt`; `dt` and `t` are recorded for traceability.

## Sign convention

```text
delta_q     = q_after - q_before
delta_rho_q = (rho*q)_after - (rho*q)_before
```

Interpretation:

```text
delta_q > 0  local equilibrium vapor generation
delta_q < 0  local equilibrium condensation
delta_q = 0  no quality correction
```

This is an instantaneous equilibrium source in the fourth equation. It is not a
finite-rate HNE model.

## Configuration

Proposed initial configuration:

```text
quality_bound_tolerance:    1e-12
consistency_tolerance:      1e-10
allowed_phase_classes:
  - compressed_or_subcooled_liquid
  - liquid_vapor_two_phase
  - single_phase_vapor
fail_on_guarded_state:      true
fail_on_unknown_state:      true
record_cellwise_arrays:     true
```

The consistency tolerance is diagnostic: it decides whether a cell is reported as
materially projected. The stored fourth component is still set to the evaluator's
returned equilibrium value.

No invalid value is silently clipped. Endpoint normalization already performed inside
the reviewed phase evaluator is retained only after that evaluator has checked its
endpoint tolerance.

## Phase policy

### Operator-level supported candidates

The projection core may support:

```text
compressed_or_subcooled_liquid  -> q_eq = 0
liquid_vapor_two_phase          -> 0 <= q_eq <= 1
single_phase_vapor              -> q_eq = 1
```

This prepares the operator for a later phase-boundary test.

### First FVM integration scope

The first dynamic FVM case remains strictly inside the open liquid-vapor two-phase
region. Liquid/two-phase crossing is a later gate because the current PR #57 EOS adapter
accepts only open two-phase states.

### Rejected states

The complete step fails on any cell classified as:

```text
supercritical
critical_region
solid_or_below_triple_guard
unknown
```

Backend evaluation failure, undefined quality, nonfinite values, and invalid array shape
also fail the complete step. There is no per-cell fallback in the first increment.

## State invariants

For projection from `U_before` to `U_after`:

```text
U_after[..., rho]   == U_before[..., rho]      bitwise
U_after[..., rho*u] == U_before[..., rho*u]    bitwise
U_after[..., rho*E] == U_before[..., rho*E]    bitwise
```

Consequently, projection alone must preserve exactly:

```text
total mass
total momentum
total conservative energy
rho/e thermodynamic state
pressure derived from rho/e
temperature derived from rho/e
```

The vapor-mass inventory may change and must be recorded as an internal phase source.

For this pure-CO2 HEM formulation, no energy projection is permitted. The conserved
internal energy already determines the equilibrium phase split. Adding or subtracting
latent heat when only synchronizing redundant `rho*q` would double-count the equilibrium
thermodynamics. Any model that evolves quality independently and changes energy belongs
to a separate HNE closure.

## Projection report

`HEMEquilibriumQualitySyncReport` should include cellwise arrays:

```text
rho
e
q_before
q_equilibrium
q_after
delta_q
rho_q_before
rho_q_after
delta_rho_q
raw_phase
phase_class
scope_status
projection_applied
```

and scalar summaries:

```text
time_s
dt_s
cell_count
projected_cell_count
vapor_generation_cell_count
condensation_cell_count
no_change_cell_count
max_abs_delta_q
max_abs_delta_rho_q
sum_delta_rho_q
mass_max_abs_change
momentum_max_abs_change
energy_max_abs_change
```

`projection_applied` is true when `abs(delta_q) > consistency_tolerance`.

The operator stores `last_report`. Long histories belong to the verification runner, not
to the production solver object.

## Budget integration

The existing `PhaseChangeBudgetTracker` already records the domain-integrated change in
`rho*q` caused by an operator-split phase step. The first implementation should use that
tracker unchanged and verify:

```text
vapor inventory change
  = boundary vapor flux
  + equilibrium-quality projection source
  + residual
```

The existing `EnergySourceBudgetTracker` should record zero conservative energy change
for the projection. `latent_heat_placeholder_j_kg` must remain zero for this HEM quality
synchronization verification.

## Verification ladder

### Gate A — Pure operator tests

Use a dependency-free fake phase evaluator.

Required tests:

1. invalid configuration is rejected;
2. input state is not mutated;
3. output is memory-independent;
4. an already equilibrated state is an exact no-op;
5. an intentionally low transported quality is projected upward;
6. an intentionally high transported quality is projected downward;
7. the first three conservative columns remain bitwise unchanged;
8. applying the operator twice is idempotent;
9. liquid, open-two-phase, and vapor equilibrium endpoints are handled;
10. guarded, unknown, and undefined-quality states are rejected;
11. invalid density, nonfinite energy, invalid transported bounds, and evaluator failures
    are rejected;
12. report signs, counts, and extrema are correct.

### Gate B — Installed-CoolProp representative states

At minimum:

```text
8 MPa / 280 K dense-liquid candidate
2 MPa / q=0.50 open two-phase
1 MPa / 280 K vapor
```

For each state, deliberately replace transported `q` with a different in-bound value and
verify that projection recovers the explicit equilibrium quality without changing
`rho`, momentum, or energy.

### Gate C — Strict-EOS handoff

Construct one open-two-phase state with an intentional quality mismatch.

Expected sequence:

```text
strict PR #57 EOS before projection: rejects mismatch
quality projection: succeeds
strict PR #57 EOS after projection: succeeds
```

This proves that the operator closes the current chicken-and-egg gap.

### Gate D — Equal-pressure nonuniform contact

Fixed initial proposal:

```text
pure CO2
p_left = p_right = 2 MPa
q_left = 0.45
q_right = 0.55
u = 0 m/s
all cells open two-phase
transmissive boundaries
NoSource
first-order Rusanov FVM
```

This is primarily an equilibrium-manifold/contact-preservation case. At constant
saturation pressure, conservative mixing of neighboring equilibrium states can remain
on the same equilibrium manifold, so the projection may be exactly zero or near
roundoff. Therefore this case is useful as a nonuniform no-op check, but it is not
sufficient evidence that the projection activates dynamically.

Acceptance:

```text
solver advances multiple steps
all cells remain supported open two-phase
no EOS or phase guard failure
mass, momentum, and energy budgets close
projection is no-op or roundoff only
```

### Gate E — Weak dynamic open-two-phase case

A separate case must force a nonzero quality correction while remaining away from phase
boundaries.

Initial fixed proposal:

```text
pure CO2
left state:   p = 2.01 MPa, q = 0.45, u = 0
right state:  p = 1.99 MPa, q = 0.55, u = 0
length:       10 m
diameter:     0.10 m
cells:        32
CFL:          0.10
steps:        4
boundaries:   transmissive
source:       none
interfaces:   none
all initial states: open liquid-vapor two-phase
```

The pressure offset is deliberately small. It introduces a real nonuniform conservative
update without crossing a phase boundary.

Before evidence capture, one dry run may adjust only the pressure offset or CFL if the
case is not evaluable. Once a run produces a finite supported path and at least one
material projection, the case values must be frozen and documented before final
validation.

Acceptance:

```text
all full steps complete
at least one cell has projection_applied = true
q_after matches q_eq within 1e-12
all post-projection states pass the strict HEM EOS
rho, rho*u, rho*E are bitwise unchanged by every projection
mass, momentum, energy projection drift is exactly zero
phase vapor source reconciles with vapor inventory
all cells remain liquid_vapor_two_phase
sound speed remains finite and positive
CFL remains finite and within configured target
NaN / infinity / backend failure count = 0
second projection of each completed state is a no-op
```

No pressure-wave accuracy claim is made from this small case.

## Human-review artifacts

The verification runner should emit:

```text
JSON
CSV
Markdown
NPZ
```

and, when the validation environment includes plotting support, the following figures:

1. `quality_sync_snapshot.png`
   - `q_before`, `q_eq`, `q_after` versus position;
   - `delta_q` versus position;
2. `hem_state_profiles.png`
   - pressure, velocity, density, void fraction, equilibrium sound speed;
   - explicit phase-class strip;
3. `conservation_and_projection_history.png`
   - mass, momentum, and energy drift;
   - vapor inventory and phase source;
   - maximum `abs(delta_q)` and projected-cell count.

Plotting must consume saved numerical artifacts. It must not rerun or alter the solver.

## Required evidence flags

```text
scope = verification_only
fvm_solver_modified = false
rusanov_flux_modified = false
cfl_modified = false
production_default_changed = false
quality_projection_implemented = true
nonuniform_open_two_phase_case_completed = true | false
liquid_two_phase_boundary_crossing_verified = false
pipeline_depressurization_implemented = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

## Known integration constraints

1. `check_physical_state()` currently requires nonnegative internal energy, while a real
   property backend may use a reference state with negative absolute internal energy. The
   first dynamic case must remain in the currently positive-energy region. A broader
   real-fluid state range requires a separate solver-state validation review.
2. `check_physical_state()` also checks transported quality bounds before the phase-change
   slot. The first-order open-two-phase case is chosen away from endpoints so that no
   pre-projection overshoot is expected. High-order transport or phase-boundary work will
   need an explicit positivity/bounds policy.
3. The PR #57 verification EOS accepts only open two-phase states. The projection core may
   support liquid and vapor endpoints, but the first FVM integration does not cross those
   boundaries.
4. The fourth equation is retained for compatibility. A future architecture review may
   compare this four-variable projection approach with a three-variable HEM formulation
   that derives quality only from `rho/e`.

## Implementation file set

The intended first implementation increment is limited to:

```text
src/liquid_gas_transient/hem_equilibrium_quality_sync.py
tests/test_stage7_lco2_hem_equilibrium_quality_sync.py
docs/verification/stage7_lco2_hem_equilibrium_quality_sync_plan.md
docs/verification/stage7_lco2_hem_equilibrium_quality_sync_validation_commands.md
```

A later integration increment may add the nonuniform runner and visualization artifacts
as separate files if the first PR becomes too large.

## Deliberately excluded

This specification does not approve or implement:

- production HEM defaults;
- changes to the numerical flux or CFL calculation;
- higher-order reconstruction;
- liquid/two-phase phase-boundary crossing;
- critical or solid CO2;
- wall heat transfer or friction;
- discharge or rupture boundaries;
- finite-rate HNE relaxation;
- impurity mixtures;
- a two-phase acoustic accuracy band;
- physical Validation or design-use acceptance.

## Review decisions required

Before implementation begins, review should confirm:

1. a separate verification-only operator is preferred over modifying the existing generic
   `HEMPhaseChange` skeleton;
2. direct injected phase evaluation from `rho/e` is the correct route around strict-EOS
   mismatch rejection;
3. no conservative-energy projection is allowed in this pure-CO2 HEM increment;
4. the equal-pressure quality step is treated as a no-op/contact test, not activation
   evidence;
5. a weak pressure-offset open-two-phase case is required to demonstrate nonzero dynamic
   synchronization;
6. fail-fast whole-step behavior is preferred over clipping or local fallback;
7. phase and energy budget trackers remain unchanged for the first implementation.

## Next action after design approval

1. implement the pure projection core and report object;
2. complete dependency-free and installed-CoolProp operator tests;
3. verify strict-EOS handoff;
4. connect the operator through the existing `phase_change` slot;
5. run the equal-pressure contact no-op case;
6. freeze and validate a weak dynamic open-two-phase activation case;
7. only then design the liquid-to-two-phase boundary-crossing problem.
