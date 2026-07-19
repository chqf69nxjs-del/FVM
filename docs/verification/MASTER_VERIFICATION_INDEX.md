# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-19

- Stage 1–6: `COMPLETE`
- Stage 7 / V-013: `IN_PROGRESS`
- V-013 independent analytical / CFL=1 MOC reference core: merged in PR #46
- V-013A incident propagation: `OBSERVED; MERGED` in PR #48
- PR #48 merge commit: `613b21622b22402fbf7b8d77b1d881db7ff5f28e`
- V-013B rigid-wall reflection: `IN_PROGRESS; SPECIFICATION SCAFFOLD IMPLEMENTED`
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

The configuration, stable case IDs, run plan, path-state convention, probe windows,
and pure tests are added. A separated pure-scaffold run passes `28` tests. This is
not a substitute for the repository focused/full recheck. The actual
FVM/MOC/analytical observation remains unexecuted.

Permanent workflows triggered by Draft PR #49 pass on the initial scaffold head;
the current tightened head must also remain green. No workflow file is changed.

## Guardrails

These are software / numerical verification results and plans, not an acceptance
band. Physical Validation and design-use acceptance remain `False`; the property
backend remains `not_approved_for_design_use`; MOC is verification-only; the finest
mesh is not exact; no V-013 CI-light band has been selected.

## Next action

1. pull the current Draft PR #49 head and run the focused V-013 reference/V-013B
   tests plus the full repository suite;
2. address review findings while keeping the PR in Draft;
3. connect a dedicated V-013B runner to the existing FVM and rigid-wall boundary
   without changing solver physics;
4. generate traceable FVM, MOC, analytical, matched-sample, probe, boundary, and
   plotting artifacts;
5. execute and review `n=100 / 200 / 400` before starting V-013C.
