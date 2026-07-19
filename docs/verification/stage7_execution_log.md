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

The FVM wave travels in the correct direction at approximately the recorded sound
speed. The final `n=400` pressure peak ratio is `0.57499430`, showing strong numerical
diffusion that decreases with refinement. Production solver behaviour is unchanged.

Review-close validation used GitHub Actions run `29673595870`: focused
`40 passed, 0 skipped`; full repository `316 passed, 0 skipped`; `git diff --check`
success; CoolProp `8.0.0`; artifact digest
`sha256:d531f959327f0c36b86223bc96fa2e85a5fb2727790f8739cb941643ccffa148`.
Temporary validation helpers were removed after evidence capture.

## 2026-07-19 — V-013B rigid-wall reflection

Status: `OBSERVED; READY FOR REVIEW` on branch
`agent/stage7-v013b-rigid-wall-reflection`; PR #49 remains open. V-013 overall remains
`IN_PROGRESS`.

Starting evidence:

```text
base: PR #48 merge commit 613b21622b22402fbf7b8d77b1d881db7ff5f28e
working tree: clean
full repository baseline: 316 passed in 141.44 s
```

Fixed case:

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
```

The independent reference defines pressure-dimension `A+ / A-`; the right rigid-wall
identity is `A-_reflected = A+_incident`. Ideal pressure and velocity reflection
coefficients are `+1 / -1`; wall velocity is zero and total wall pressure is twice the
incident pressure amplitude. The production `ReflectiveBoundary` is not modified.

Draft review produced and resolved two P2 findings: runtime import independence and
secondary-return safety measured from the return-pulse leading edge. The first plotter
recheck also found a saved timing-key mismatch; it was corrected without changing any
numerical result.

Implementation validation history:

```text
specification scaffold focused/full: 53 / 346 passed
runner focused/full:                 55 / 348 passed
runner/plotter focused/full:         57 / 350 passed
failures / errors / skips:           0 / 0 / 0
git diff --check:                    success
```

The first full three-mesh observation was reviewed and a derived-metric defect was
found: the analytical velocity is zero at exact wall contact, so using that velocity
as the relative-error denominator was invalid. The final policy uses
`analytical_pressure_perturbation_pa / (rho0 * c0)` as the velocity normalization.
Pressure and `A+ / A-` normalization remain pressure-based. Tests require finite
velocity norms and persist the policy in each comparison artifact. The wall-condition
figure now displays exact zero wall velocity on a linear axis.

Final corrected observation evidence:

```text
workflow run:       29684930259
PR head:            dbb17b45f19a973741da4998e57591a529fb25f2
Actions merge SHA:  8670c95122cc0d470469b8445590cd03029133b8
focused tests:      57 passed, 0 skipped
full repository:    350 passed, 0 skipped
runs:               3 / 3
figures:            7 / 7
plotting errors:    0
CoolProp:           8.0.0
artifact ID:        8441899419
artifact entries:   59
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

Reference state: `rho0 = 922.9172130294444 kg/m3`; `c0 = 557.4488783994866 m/s`.
Plotting used saved artifacts only: `solver_rerun = false` and
`numerical_results_changed = false`.

| n | pressure reflection coefficient | velocity reflection coefficient | wall pressure ratio | final reflected peak ratio |
|---:|---:|---:|---:|---:|
| 100 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 |
| 200 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 |
| 400 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 |

The reflected pressure sign is positive, reflected velocity sign is negative, and the
returning characteristic is `A-`. Wall face velocity, mass flux, and energy flux are
exactly zero for all meshes. Reflection amplitude, wall pressure amplification, and
field differences improve monotonically with mesh refinement. Strong numerical
broadening and peak loss remain substantial at `n=400`; the finest mesh is not exact
or design-accurate.

All temporary observation/fix workflows, the temporary trigger, and the patch script
were removed after final evidence capture. Production solver, flux, and boundary
behaviour remain unchanged. Physical Validation and design-use acceptance are
`False`; the property backend is `not_approved_for_design_use`; MOC is
verification-only; no FVM regression, CI-light, or design-accuracy band is introduced.

Next: complete PR #49 review and merge, then start V-013C fixed-pressure reflection.
