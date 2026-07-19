# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-19

- Stage 1–6: `COMPLETE`
- Stage 7 / V-013: `IN_PROGRESS`
- V-013 independent analytical / CFL=1 MOC reference core: merged in PR #46
- V-013A incident propagation: `OBSERVED; MERGED` in PR #48
- PR #48 merge commit: `613b21622b22402fbf7b8d77b1d881db7ff5f28e`
- V-013B rigid-wall reflection: `IN_PROGRESS; SPECIFICATION SCAFFOLD VERIFIED`
- Active branch: `agent/stage7-v013b-rigid-wall-reflection`
- Draft PR: `#49 Add V-013B rigid-wall reflection specification scaffold`
- V-013C fixed-pressure reflection: `PLANNED`

## V-013A evidence

- meshes: `n=100 / 200 / 400`; FVM CFL `0.5`; MOC CFL `1.0`
- primary observation tests: focused `39 passed`; full repository `315 passed`; skips `0`
- review-close validation: focused `40 passed`; full repository `316 passed`; skips `0`
- runs: `3 / 3`; figures: `7 / 7`; CoolProp: `8.0.0`
- all figures state case, model, backend, CoolProp version, and output version
- plots were regenerated from saved artifacts without rerunning either solver
- propagation direction and approximate wave speed: consistent
- final `n=400` FVM pressure peak ratio: `0.57499430` (about `57.5%`)
- dominant observation: strong, monotonically decreasing FVM numerical diffusion
- production solver behaviour changes: none

## V-013B active increment

Implementation plan:
[`v013b_rigid_wall_reflection_execution_plan.md`](v013b_rigid_wall_reflection_execution_plan.md)

Starting evidence:

- branch started from PR #48 merge commit with a clean working tree;
- full repository baseline: `316 passed in 141.44 s`;
- production `ReflectiveBoundary`, Stage 5 reflection assets, and the independent
  linear-acoustic reference conventions were reviewed before fixing the plan.

Fixed observation contract:

- right-going `100 Pa` Gaussian, `x0=65 m`, `sigma=2 m`;
- right rigid wall and left transmissive observation boundary;
- FVM meshes `n=100 / 200 / 400`, FVM CFL `0.5`;
- MOC meshes `n=100 / 200 / 400`, MOC CFL `1.0`;
- probes `x/L=0.75 / 0.85 / 0.90`;
- probe-event windows use a half width of `2 sigma` and remain strictly separated;
- matched-field samples use a `5 sigma` boundary guard;
- cumulative matched path travel `0 / 15 / 25 / 35 / 45 / 55 / 65 m`;
- wall contact at path travel `35 m`;
- expected identity: `A-_reflected = A+_incident`;
- pressure coefficient `+1`, velocity coefficient `-1`, wall velocity perturbation
  `0`, and total wall pressure ratio `2`;
- no time shifting, parameter tuning, or FVM regression band;
- production solver behaviour changes: none.

Draft-review safeguards:

- top-level package and case compatibility exports are lazy, so importing the pure
  V-013B module in a fresh interpreter does not load solver, boundary, CoolProp case,
  or CoolProp modules;
- runtime independence is asserted through a fresh-interpreter `sys.modules` test;
- secondary-return safety compares the accepted reflected-window trailing edge with
  the return pulse leading edge, not merely its centre;
- a custom geometry fixes the equality-edge contamination case by test.

Repository validation on the current scaffold head:

- focused reference/V-013B tests: `53 passed in 0.56 s`;
- full repository: `346 passed in 121.38 s`;
- failures / errors: `0 / 0`;
- `git diff --check`: success;
- local branch tracks `origin/agent/stage7-v013b-rigid-wall-reflection` with no
  reported working-tree changes after the pull.

All Draft review threads are resolved. The actual FVM/MOC/analytical observation
remains unexecuted.

No workflow file is changed. The four existing permanent workflows also pass on the
current scaffold head; they remain regression sentinels rather than V-013B observation
execution.

## Guardrails

These are software / numerical verification results and plans, not an acceptance
band. Physical Validation and design-use acceptance remain `False`; the property
backend remains `not_approved_for_design_use`; MOC is verification-only; the finest
mesh is not exact; no V-013 CI-light band has been selected.

## Next action

1. connect a dedicated V-013B runner to the existing small-amplitude FVM and rigid-wall
   boundary without changing solver physics;
2. record `rho0`, `c0`, provenance, backend, and CoolProp version, and pass only scalar
   reference inputs to the independent analytical/MOC path;
3. generate traceable FVM, MOC, analytical, matched-sample, probe, boundary, and
   plotting artifacts;
4. add pure and installed-CoolProp integration tests for the runner and saved artifacts;
5. execute and review `n=100 / 200 / 400` before starting V-013C.
