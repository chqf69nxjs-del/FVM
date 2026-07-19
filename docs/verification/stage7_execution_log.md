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

## 2026-07-19 — V-013B rigid-wall reflection

Status: `IN_PROGRESS; PLOTTER KEY FIX APPLIED; RECHECK PENDING` on branch
`agent/stage7-v013b-rigid-wall-reflection`; Draft PR #49 is open.

Starting evidence:

```text
base: PR #48 merge commit 613b21622b22402fbf7b8d77b1d881db7ff5f28e
working tree: clean
full repository baseline: 316 passed in 141.44 s
```

The fixed Stage 7 contract is:

```text
pulse: 100 Pa right-going Gaussian
x0 / sigma: 65 / 2 m
right boundary: rigid_wall
left boundary: transmissive
FVM mesh / CFL: 100, 200, 400 / 0.5
MOC mesh / CFL: 100, 200, 400 / 1.0
probes x/L: 0.75, 0.85, 0.90
probe event-window half width: 2 sigma
matched-field boundary guard: 5 sigma
matched cumulative path travel: 0, 15, 25, 35, 45, 55, 65 m
wall-contact path travel: 35 m
final reflected centre: 70 m
```

The independent reference uses pressure-dimension `A+ / A-` variables. The right
rigid-wall identity is `A-_reflected = A+_incident`; the ideal pressure and velocity
reflection coefficients are `+1 / -1`; reconstructed wall velocity perturbation is
zero and total wall pressure is twice the incident pressure amplitude. The production
`ReflectiveBoundary` mirrors ghost-cell momentum and is not modified.

The initial `30 m` pre-wall sample was tightened to `25 m`, and the probe half width
was tightened from `2.5 sigma` to `2.0 sigma`. This keeps the accepted incident,
wall-contact, and reflected windows strictly separated and before a secondary return.

Draft review produced two P2 findings and both are resolved:

1. package compatibility exports are lazy, and a fresh-interpreter test verifies that
   importing the pure V-013B module does not load the production solver, production
   boundary, CoolProp case runners, or CoolProp;
2. secondary-return safety is measured from the return pulse leading edge rather than
   its centre, including an equality-edge contamination test.

Specification-scaffold validation:

```text
focused reference/V-013B tests: 53 passed in 0.56 s
full repository:                346 passed in 121.38 s
git diff --check:               success
failures / errors:              0 / 0
```

Production-connected runner validation at head `8464dc5`:

```text
focused reference/specification/runner tests: 55 passed in 5.02 s
full repository:                            348 passed in 89.39 s
git diff --check:                           success
failures / errors / skips:                  0 / 0 / 0
```

`v013_rigid_wall_observation.py` uses the existing CoolProp initialization and
`ReflectiveBoundary`, lands exactly on fixed matched times, records FVM field/probe/
boundary/health/budget evidence, passes only scalar reference inputs to the independent
analytical/MOC paths, and writes traceable JSON, CSV, and NPZ artifacts. No FVM
regression or design-accuracy band is applied.

`plot_v013_rigid_wall_results.py` reads saved artifacts only and targets seven figures:
pressure, velocity, characteristics, probe history, reflection coefficients,
field/energy differences, and rigid-wall residuals. Each figure includes case, model,
backend, CoolProp version, output version, and the non-design-use disclaimer.

The first Windows plotter recheck exposed one non-numerical defect:

```text
focused result:       56 passed, 1 failed
full repository:      349 passed, 1 failed
observed plot count:  6 / 7
failed figure:        near-wall probe pressure history
```

The runner and saved comparison artifact use the timing field
`theoretical_wall_time_s`. The plotter requested the nonexistent
`theoretical_boundary_time_s`, so the probe-history figure was caught by the local
`try/except`, leaving six valid figures and one plotting error. FVM execution,
reflection signs, saved artifacts, and the other six figures succeeded.

The plotter fix now reads `theoretical_wall_time_s` and accepts
`theoretical_boundary_time_s` only as a compatibility alias. The integration test also
asserts the saved wall-time schema and reports `plotting_errors` before the plot count.
No numerical result, solver behaviour, or saved observation value is changed.

Next actions:

1. pull the fix head and rerun focused tests, the full repository suite, and
   `git diff --check`;
2. require `7/7` figures, empty plotting errors, zero failures, and zero skips;
3. execute the fixed `n=100 / 200 / 400` observation;
4. generate all seven figures from saved artifacts and review signs, coefficients,
   timing, wall residuals, numerical diffusion, and traceability.

Guardrails remain: software/numerical verification only; physical Validation and
design-use acceptance `False`; backend `not_approved_for_design_use`; MOC
verification-only; finest mesh not exact; no V-013 CI-light band. V-013C remains
later work.
