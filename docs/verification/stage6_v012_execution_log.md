# Stage 6 V-012 Execution Log

This log records material decisions, implementation checkpoints, tests,
artifacts, and stop conditions for V-012 single-phase internal-valve operation.

Persistent guardrails:

- software / numerical verification only
- physical Validation = false
- design-use acceptance = false
- `property_backend_design_status = not_approved_for_design_use`
- single-phase scope only
- no flashing, cavitation, choked/two-phase discharge, ESD, or pump trip
- CI-light meshes are not design meshes
- finest meshes are comparison references, not exact solutions

## 2026-07-15 — V-012 specification-first start

Starting point:

- V-011 is `COMPLETE`
- main is synchronized and the full Windows suite passes (`223 passed`)
- V-012 is `IN_PROGRESS`
- the repository contains an existing internal-valve / Kv software path
- no V-012 runner is present yet

Work opened on:

```text
agent/stage6-v012-internal-valve-spec
```

Draft PR scope:

- fix the V-012 scope and case order
- define internal-face telemetry and artifact schemas
- document budget and sign conventions
- define stop conditions
- survey the existing internal-valve code path
- make no solver-physics, valve-law, or total-energy change

Initial case order:

1. V-012A uniform-state constant-opening preservation
2. V-012B small driven-flow constant-opening baseline
3. V-012C small controlled opening ramp
4. V-012D small controlled closing ramp to nonzero opening
5. V-012E closed-limit observation only after separate review

Initial risk assessment:

- no critical blocker prevents specification work
- the current hydraulic-loss proxy remains diagnostic
- the relationship between that diagnostic and conserved `rhoE` is not changed
- actual shared internal-face numerical-flux telemetry is a hard requirement
- V-012A can proceed without resolving a driven-flow energy-loss model because
  its expected material flow is zero

Stop rule for the next implementation PR:

If the solver cannot expose one shared internal-face flux, or if the baseline
requires a valve-law / energy-treatment change, save the branch and stop for
owner review.

## 2026-07-15 — V-012A implementation checkpoint

Specification PR #34 was merged at commit
`6f4bc16c38361b0fffec3267766224aff0160a90`.

Implementation work was opened on:

```text
agent/stage6-v012-uniform-valve-baseline
```

Implemented diagnostic-only interface additions:

- raw Kv target flow
- Mach-limited applied flow and flow limit
- cap activation state
- hydraulic-separation state
- flow direction and upwind state
- applied face velocity and Mach number
- exact two-sided interface flux evaluation used by the solver update

`InternalValveInterface.apply()` now consumes the same `evaluate_fluxes()`
result that is exposed to telemetry. This avoids reconstructing a second,
independent valve flux from cell-center values.

Compatibility and physics constraints retained:

- the existing Kv equation is unchanged
- the existing Mach cap is unchanged
- finite-opening mass, total-enthalpy energy, and vapor-mass flux formulae are unchanged
- the documented momentum-flux difference is unchanged
- the legacy raw-Q diagnostic fields remain available
- the hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`
- no governing-equation or external-boundary meaning was changed

The first runner implements V-012A:

- uniform single-phase CoolProp CO2 at `8 MPa` and `280 K`
- zero initial velocity and zero driving pressure difference
- nonzero constant valve opening at the pipe midpoint
- transmissive, non-driving external boundaries
- exact internal-face valve and flux telemetry
- probe, boundary, final-profile, budget, metrics, and observation-report artifacts

Expected implementation behavior:

- requested and actual opening agree to roundoff
- raw and applied flow remain at numerical zero
- the Mach cap remains inactive
- the existing no-flow hydraulic-separation path is active
- no material pressure or velocity disturbance is introduced
- two-sided mass, energy, and vapor-mass mismatches remain at roundoff scale
- momentum-flux difference remains consistent with the pressure difference
- the case remains finite, positive, and single phase

Pure tests were added for uniform flow, finite-opening flux identities, deliberate
Mach clipping, exact `apply()`/telemetry flux identity, and legacy diagnostic
compatibility. An installed-CoolProp mini-run test was also added.

Test status at this checkpoint:

- source files are committed to the branch
- local Windows focused and full-suite execution is pending
- no numerical baseline artifact has yet been accepted
- no regression or acceptance band has been defined

No critical solver-physics or data-integrity blocker has been found. The branch
must remain unmerged until the focused tests and installed-CoolProp baseline are
executed and reviewed.
