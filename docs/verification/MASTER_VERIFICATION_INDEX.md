# MASTER VERIFICATION INDEX

Historical detail through the V-013 reference-core checkpoint is preserved in
[`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md).

## Current state — 2026-07-19

- Stage 1–6: `COMPLETE`
- Stage 7 / V-013: `IN_PROGRESS`
- V-013 independent analytical / CFL=1 MOC reference core: merged in PR #46
- V-013A incident propagation (PR #48): `OBSERVED; READY FOR REVIEW`
- Next: V-013B rigid-wall reflection

## V-013A evidence

- meshes: `n=100 / 200 / 400`; FVM CFL `0.5`; MOC CFL `1.0`
- focused tests: `39 passed`, `0 skipped`
- full repository: `315 passed`, `0 skipped`
- runs: `3 / 3`; figures: `7 / 7`; CoolProp: `8.0.0`
- propagation direction and approximate wave speed: consistent
- final `n=400` FVM pressure peak ratio: `0.57499430` (about `57.5%`)
- dominant observation: strong, monotonically decreasing FVM numerical diffusion
- production solver behaviour changes: none

These are observation results, not an acceptance band. Physical Validation and
design-use acceptance remain `False`; the property backend remains
`not_approved_for_design_use`; MOC is verification-only; the finest mesh is not
exact; no V-013 CI-light band has been selected.
