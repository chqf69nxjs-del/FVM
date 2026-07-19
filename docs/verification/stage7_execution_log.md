# Stage 7 Execution Log

Earlier entries are preserved in
[`archive/stage7_execution_log_through_v013_reference_core.md`](archive/stage7_execution_log_through_v013_reference_core.md).

## 2026-07-19 — V-013A incident propagation

Status: `OBSERVED; MERGED` in PR #48. Merge commit:
`613b21622b22402fbf7b8d77b1d881db7ff5f28e`. V-013 remains `IN_PROGRESS`.

Primary observation evidence: GitHub Actions run `29647234616`; focused
`39 passed, 0 skipped`; full repository `315 passed, 0 skipped`; runs `3/3`;
figures `7/7`; CoolProp `8.0.0`; artifact SHA256
`ee537e0e32a14d01501e36b427af68f94881905bc01f4a3b68684508c15c0961`.

The FVM wave travels in the correct direction at approximately the recorded
sound speed. The final `n=400` pressure peak ratio is `0.57499430`, showing
strong numerical diffusion that decreases with refinement. No accepted
incident-window boundary return was observed.

Finalization fixes provide NumPy 1.x/2.x-compatible trapezoidal integration,
persist `coolprop_version`, use increasing mesh spacing `Δx` in plots, and
remove temporary workflows. Production solver behaviour is unchanged.

Review-close plotting fixes embed case, model, property backend, CoolProp
version, and output version in every one of the seven figures. The same fields
are persisted in `v013a_plot_metrics.json`. The primary `n=100/200/400` saved
artifacts were replotted without rerunning FVM, MOC, or analytical calculations;
`7/7` figures were generated with no plotting errors and no numerical-result
change.

Close validation used GitHub Actions run `29673595870` at code/test head
`14afc9add7c7bb8c7b141d62625c27c3700ea1f8`: focused `40 passed, 0 skipped`,
full repository `316 passed, 0 skipped`, `git diff --check` success, and CoolProp
`8.0.0`. Artifact digest:
`sha256:d531f959327f0c36b86223bc96fa2e85a5fb2727790f8739cb941643ccffa148`.
The temporary validation helper was removed after evidence capture.

## 2026-07-19 — V-013B rigid-wall reflection start

Status: `IN_PROGRESS; SPECIFICATION SCAFFOLD IMPLEMENTED` on branch
`agent/stage7-v013b-rigid-wall-reflection`.

Starting evidence:

```text
base: PR #48 merge commit 613b21622b22402fbf7b8d77b1d881db7ff5f28e
working tree: clean
full repository baseline: 316 passed in 141.44 s
```

Existing assets were aligned before fixing the V-013B contract:

- the independent reference uses pressure-dimension `A+ / A-` variables;
- the right rigid-wall identity is `A-_reflected = A+_incident`;
- the ideal pressure and velocity reflection coefficients are `+1 / -1`;
- the reconstructed wall velocity perturbation is zero and total wall pressure
  is twice the incident pressure amplitude;
- the production `ReflectiveBoundary` mirrors ghost-cell momentum;
- the Stage 5 boundary-reflection runner already exercises that production
  boundary but uses a different `1000 Pa`, `x0=50 m`, `sigma=3 m` profile.

The V-013B Stage 7 contract is now fixed separately:

```text
pulse: 100 Pa right-going Gaussian
x0 / sigma: 65 / 2 m
right boundary: rigid_wall
left boundary: transmissive
FVM mesh / CFL: 100, 200, 400 / 0.5
MOC mesh / CFL: 100, 200, 400 / 1.0
probes x/L: 0.75, 0.85, 0.90
matched cumulative path travel: 0, 15, 30, 35, 45, 55, 65 m
wall-contact path travel: 35 m
final reflected centre: 70 m
```

Stable case IDs, the run plan, matched-sample schema, incident/wall/reflected
path-state mapping, non-overlapping probe windows, expected rigid-wall identity,
and a JSON-ready specification snapshot are implemented in
`cases/v013_rigid_wall_reflection.py`. Pure tests fix these values and guard
against production solver, production boundary, and CoolProp imports in the
scaffold.

No FVM, MOC, or analytical observation has been executed for V-013B yet. No
production solver behaviour has changed, and no FVM regression band has been
introduced.

Next actions:

1. run `tests/test_linear_acoustic_reference.py` and
   `tests/test_v013_rigid_wall_reflection.py`;
2. run the full repository suite;
3. connect a dedicated V-013B artifact runner to the existing small-amplitude FVM
   and `ReflectiveBoundary` without altering solver physics;
4. execute and review the fixed `n=100 / 200 / 400` observation.

Guardrails remain: software/numerical verification only; physical Validation
and design-use acceptance `False`; backend `not_approved_for_design_use`; MOC
verification-only; finest mesh not exact; no V-013 CI-light band. V-013C remains
later work.
