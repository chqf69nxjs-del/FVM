# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-19

- Stage 1–6: `COMPLETE`
- Stage 7 / V-013: `IN_PROGRESS`
- V-013 independent analytical / CFL=1 MOC reference core: merged in PR #46
- V-013A incident propagation: `OBSERVED; MERGED` in PR #48
- PR #48 merge commit: `613b21622b22402fbf7b8d77b1d881db7ff5f28e`
- V-013B rigid-wall reflection: `OBSERVED; MERGED` in PR #49
- PR #49 merge commit: `bc874193de6a4c019073b6cf629e99ec5dfa6602`
- V-013C fixed-pressure reflection: `IN_PROGRESS; SPECIFICATION SCAFFOLD IMPLEMENTED; VALIDATION PENDING`
- Active branch: `agent/stage7-v013c-fixed-pressure-reflection`

## V-013A evidence

- meshes: `n=100 / 200 / 400`; FVM CFL `0.5`; MOC CFL `1.0`
- focused/full observation tests: `39 / 315 passed`; close tests: `40 / 316 passed`
- runs: `3 / 3`; figures: `7 / 7`; CoolProp: `8.0.0`
- final `n=400` FVM pressure peak ratio: `0.57499430` (about `57.5%`)
- propagation direction and approximate wave speed: consistent
- dominant observation: strong numerical diffusion decreasing with mesh refinement
- production solver behaviour changes: none

## V-013B evidence

Execution plan:
[`v013b_rigid_wall_reflection_execution_plan.md`](v013b_rigid_wall_reflection_execution_plan.md)

Observation notes:
[`stage7_v013b_rigid_wall_reflection_observation_notes.md`](stage7_v013b_rigid_wall_reflection_observation_notes.md)

Final observation evidence:

- GitHub Actions run `29684930259`;
- focused `57 passed, 0 skipped`; full repository `350 passed, 0 skipped`;
- runs `3 / 3`; figures `7 / 7`; plotting errors `0`; CoolProp `8.0.0`;
- artifact ID `8441899419`, entries `59`, digest
  `sha256:709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861`;
- temporary evidence-capture files removed before merge;
- production solver, numerical flux, and `ReflectiveBoundary` behaviour unchanged.

| n | pressure reflection coefficient | velocity reflection coefficient | wall pressure ratio | final reflected peak ratio |
|---:|---:|---:|---:|---:|
| 100 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 |
| 200 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 |
| 400 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 |

The rigid-wall direction and signs are correct, and wall-face velocity, mass flux, and
energy flux are exactly zero. Reflection amplitude and wall pressure rise improve
monotonically, but strong FVM numerical diffusion remains at `n=400`.

## V-013C active increment

Implementation plan:
[`v013c_fixed_pressure_reflection_execution_plan.md`](v013c_fixed_pressure_reflection_execution_plan.md)

Starting point:

```text
branch: agent/stage7-v013c-fixed-pressure-reflection
base: post-PR #49 main
base commit: 30ab7715e79d96c48f1cbe3ba7051815877e288a
```

Fixed observation contract:

- right-going `100 Pa` Gaussian, `x0=65 m`, `sigma=2 m`;
- right fixed-pressure boundary at `p0` and left transmissive observation boundary;
- FVM meshes `n=100 / 200 / 400`, FVM CFL `0.5`;
- MOC meshes `n=100 / 200 / 400`, MOC CFL `1.0`;
- probes `x/L=0.75 / 0.85 / 0.90`;
- cumulative matched path travel `0 / 15 / 25 / 35 / 45 / 55 / 65 m`;
- expected identity `A-_reflected = -A+_incident`;
- ideal pressure/velocity reflection coefficients `-1 / +1`;
- ideal boundary pressure perturbation `0`;
- ideal boundary velocity / incident velocity ratio `2`;
- nonzero mass and energy flux are permitted and shall be recorded, not classified as
  a fixed-pressure boundary failure;
- no time shifting, parameter tuning, or FVM regression band;
- production solver and boundary behaviour changes: none.

Implemented scaffold:

- pure configuration, stable case IDs, run plan, matched samples, and probe windows;
- five-sigma field guards and two-sigma strictly separated event windows;
- secondary-return safety measured from the return-pulse leading edge;
- fixed-pressure identities cross-checked against the independent reference core;
- fresh-interpreter runtime import-independence test;
- no production solver, boundary, existing FVM runner, or CoolProp import in the pure
  specification module.

The V-013C scaffold still requires the Windows focused/full recheck. The dedicated
production-connected runner, saved-artifact plotter, and `n=100 / 200 / 400`
observation are not yet implemented or reviewed.

## Guardrails

These are software / numerical verification results and plans, not physical Validation
or an acceptance band. Physical Validation and design-use acceptance remain `False`;
the property backend remains `not_approved_for_design_use`; MOC is verification-only;
the finest mesh is not exact; no V-013 CI-light or design-accuracy band has been
selected.

## Next action

1. pull the V-013C branch and run the focused reference/V-013C tests, full repository
   suite, and `git diff --check`;
2. fix any specification or compatibility defect;
3. connect the existing Stage 5 fixed-pressure FVM path to a dedicated V-013C runner;
4. add traceable saved artifacts and seven saved-artifact-only figures;
5. execute and review `n=100 / 200 / 400` before formalizing V-013 A/B/C.
