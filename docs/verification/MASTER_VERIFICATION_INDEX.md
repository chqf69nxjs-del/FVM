# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-19

- Stage 1–6: `COMPLETE`
- Stage 7 / V-013: `IN_PROGRESS`
- V-013 independent analytical / CFL=1 MOC reference core: merged in PR #46
- V-013A incident propagation: `OBSERVED; MERGED` in PR #48
- PR #48 merge commit: `613b21622b22402fbf7b8d77b1d881db7ff5f28e`
- V-013B rigid-wall reflection: `OBSERVED; READY FOR REVIEW` in PR #49
- Active branch: `agent/stage7-v013b-rigid-wall-reflection`
- V-013C fixed-pressure reflection: `PLANNED`

## V-013A evidence

- meshes: `n=100 / 200 / 400`; FVM CFL `0.5`; MOC CFL `1.0`
- primary observation tests: focused `39 passed`; full repository `315 passed`; skips `0`
- review-close validation: focused `40 passed`; full repository `316 passed`; skips `0`
- runs: `3 / 3`; figures: `7 / 7`; CoolProp: `8.0.0`
- propagation direction and approximate wave speed: consistent
- final `n=400` FVM pressure peak ratio: `0.57499430` (about `57.5%`)
- dominant observation: strong, monotonically decreasing FVM numerical diffusion
- production solver behaviour changes: none

## V-013B evidence

Execution plan:
[`v013b_rigid_wall_reflection_execution_plan.md`](v013b_rigid_wall_reflection_execution_plan.md)

Observation notes:
[`stage7_v013b_rigid_wall_reflection_observation_notes.md`](stage7_v013b_rigid_wall_reflection_observation_notes.md)

Fixed contract:

- right-going `100 Pa` Gaussian, `x0=65 m`, `sigma=2 m`;
- right rigid wall and left transmissive observation boundary;
- FVM meshes `n=100 / 200 / 400`, FVM CFL `0.5`;
- MOC meshes `n=100 / 200 / 400`, MOC CFL `1.0`;
- probes `x/L=0.75 / 0.85 / 0.90`;
- cumulative matched path travel `0 / 15 / 25 / 35 / 45 / 55 / 65 m`;
- expected rigid-wall identity `A-_reflected = A+_incident`;
- ideal pressure/velocity reflection coefficients `+1 / -1`;
- ideal wall velocity `0` and total wall pressure ratio `2`;
- no time shifting, parameter tuning, or FVM regression band;
- production solver behaviour changes: none.

Final observation evidence:

- GitHub Actions run `29684930259`;
- PR head `dbb17b45f19a973741da4998e57591a529fb25f2`;
- Actions merge SHA `8670c95122cc0d470469b8445590cd03029133b8`;
- focused `57 passed, 0 skipped`; full repository `350 passed, 0 skipped`;
- runs `3 / 3`; figures `7 / 7`; plotting errors `0`; CoolProp `8.0.0`;
- artifact ID `8441899419`; artifact entries `59`;
- artifact digest
  `sha256:709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861`;
- plotting did not rerun a solver or change numerical results;
- all temporary evidence-capture workflows, triggers, and patch scripts were removed.

| n | pressure reflection coefficient | velocity reflection coefficient | wall pressure ratio | final reflected peak ratio |
|---:|---:|---:|---:|---:|
| 100 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 |
| 200 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 |
| 400 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 |

The reflection direction and signs are correct, and wall face velocity, mass flux,
and energy flux are exactly zero. Reflection amplitude and wall pressure rise improve
monotonically with refinement, but strong numerical diffusion remains at `n=400`.
V-013B is therefore observed and reviewable, not an accuracy or design-use acceptance.

## Guardrails

These are software / numerical verification results, not physical Validation or an
acceptance band. Physical Validation and design-use acceptance remain `False`; the
property backend remains `not_approved_for_design_use`; MOC is verification-only; the
finest mesh is not exact; no V-013 CI-light band has been selected.

## Next action

1. complete review and merge PR #49;
2. start V-013C fixed-pressure reflection on a new branch;
3. keep V-013 overall `IN_PROGRESS` until A/B/C review and formalization are complete.
