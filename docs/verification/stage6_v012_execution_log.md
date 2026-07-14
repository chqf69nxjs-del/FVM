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
