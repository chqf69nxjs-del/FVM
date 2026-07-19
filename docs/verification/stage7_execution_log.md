# Stage 7 Execution Log

Earlier entries are preserved in
[`archive/stage7_execution_log_through_v013_reference_core.md`](archive/stage7_execution_log_through_v013_reference_core.md).

## 2026-07-19 — V-013A incident propagation

Status: `OBSERVED; READY FOR REVIEW` (PR #48). V-013 remains `IN_PROGRESS`.

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

Guardrails remain: software/numerical verification only; physical Validation
and design-use acceptance `False`; backend `not_approved_for_design_use`; MOC
verification-only; finest mesh not exact; no V-013 CI-light band. Next:
V-013B rigid-wall reflection.
