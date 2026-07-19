# Stage 7 Execution Log

Earlier entries through the V-013 reference-core checkpoint are preserved in
[`archive/stage7_execution_log_through_v013_reference_core.md`](archive/stage7_execution_log_through_v013_reference_core.md).

## 2026-07-19 — V-013A incident propagation

Status: `OBSERVED; MERGED` in PR #48. Merge commit:
`613b21622b22402fbf7b8d77b1d881db7ff5f28e`.

```text
primary run:         29647234616
focused / full:      39 / 315 passed
runs / figures:      3 / 3, 7 / 7
CoolProp:            8.0.0
n=400 peak ratio:    0.57499430
```

Wave direction and approximate propagation speed are consistent. Strong numerical
broadening and peak loss decrease with mesh refinement but remain material at `n=400`.
Production solver behaviour is unchanged.

Review-close validation run `29673595870` passed focused `40` and full `316` tests,
with `git diff --check` clean. Temporary validation helpers were removed.

## 2026-07-19 — V-013B rigid-wall reflection

Status: `OBSERVED; MERGED` in PR #49. Merge commit:
`bc874193de6a4c019073b6cf629e99ec5dfa6602`.

Fixed identities:

```text
A-_reflected = A+_incident
pressure reflection coefficient = +1
velocity reflection coefficient = -1
wall velocity = 0
wall pressure ratio = 2
```

Draft review found and resolved runtime-import independence and secondary-return-window
issues. A plotting-key mismatch and a wall-contact zero-denominator error metric were
also corrected without changing production numerical states.

Final evidence:

```text
workflow run:       29684930259
focused tests:      57 passed, 0 skipped
full repository:    350 passed, 0 skipped
runs / figures:     3 / 3, 7 / 7
artifact ID:        8441899419
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

| n | pressure reflection | velocity reflection | wall pressure ratio | final peak ratio |
|---:|---:|---:|---:|---:|
| 100 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 |
| 200 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 |
| 400 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 |

Pressure and velocity reflection signs are correct. Wall-face velocity, mass flux, and
energy flux are exactly zero. Strong FVM numerical diffusion remains at the finest mesh.

## 2026-07-19 to 2026-07-20 — V-013C fixed-pressure reflection

Status: `OBSERVED; READY FOR REVIEW` on branch
`agent/stage7-v013c-fixed-pressure-reflection`; PR #50 remains open. V-013 overall
remains `IN_PROGRESS`.

### Fixed case

```text
pulse:                         100 Pa right-going Gaussian
x0 / sigma:                    65 / 2 m
right boundary:                fixed pressure at p0
left boundary:                 transmissive
FVM mesh / CFL:                100, 200, 400 / 0.5
MOC mesh / CFL:                100, 200, 400 / 1.0
probes x/L:                    0.75, 0.85, 0.90
matched path travel:           0, 15, 25, 35, 45, 55, 65 m
probe half width / field guard: 2 sigma / 5 sigma
```

Fixed identities:

```text
A-_reflected = -A+_incident
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

The production path is the existing
`PressureTankBoundary(ConstantPressure(p0), flow_direction="bidirectional",
velocity_policy="copy")`. Unlike the rigid wall, this pressure boundary may carry
nonzero mass and energy flux; those quantities are observations rather than zero-flux
acceptance conditions.

### Specification and platform validation

The initial scaffold validation passed but used a working-tree-only `git diff --check`.
A P3 review finding required an explicit committed range. The corrected validation used
`git diff --check origin/main...HEAD`, focused `53` tests, and full `380` tests; all
passed and the review thread was resolved.

The Windows project recheck then passed:

```text
focused tests:      58 passed in 10.61 s
full repository:    385 passed in 277.41 s
committed diff:     clean
working tree:       clean
```

### Final observation evidence

```text
workflow run:       29692477941
PR head:            2f5c10b3f99f561d457ab8d391d5e91be98b7ff3
Actions merge SHA:  e2eb1a075d229d51d28366aa211a1642fbcc1463
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
runs / figures:     3 / 3, 7 / 7
plotting errors:    0
CoolProp:           8.0.0
artifact ID:        8444138380
artifact entries:   59
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
```

Plotting used saved artifacts only:
`solver_rerun = false`, `numerical_results_changed = false`.

| n | pressure reflection | velocity reflection | fixed-pressure residual | boundary velocity ratio | final peak ratio |
|---:|---:|---:|---:|---:|---:|
| 100 | -0.63395297 | 0.63399661 | 0.05654903 | 0.82447607 | 0.33190828 |
| 200 | -0.69829946 | 0.69829998 | 0.04880759 | 1.09704849 | 0.44185022 |
| 400 | -0.77022729 | 0.77022778 | 0.03712903 | 1.37073388 | 0.57212615 |

The reflected pressure sign is negative, reflected velocity sign is positive, and the
returning characteristic is left-going `A-`. Fixed-pressure residuals and boundary
velocity amplification improve monotonically with refinement. Nonzero boundary mass and
energy transfer are recorded and expected for this ideal pressure boundary.

Maximum pressure/velocity L2 relative differences decrease from about `0.681` at
`n=100` to about `0.413` at `n=400`. The final peak ratio remains about `57.2%`,
confirming that strong numerical diffusion remains the dominant limitation.

Temporary V-013C observation, finalization, and review-helper workflows were removed
before review-ready state. Production solver, numerical flux, EOS inversion, and
boundary behaviour remain unchanged. Physical Validation, design-use acceptance, and
V-013 acceptance bands remain outside this increment.

## Joint Stage 7 conclusion

V-013A/B/C consistently support the following conclusions:

- propagation direction and approximate timing are correct;
- rigid-wall and fixed-pressure reflection signs are correct;
- the essential boundary-condition behaviour is reproduced;
- all principal differences improve with mesh refinement;
- strong first-order FVM numerical diffusion remains common to all three cases;
- the current solver is a robust software/numerical verification baseline, not a
  physically validated or design-accurate wave-amplitude model.

Next: complete PR #50 final review and merge, formalize the combined V-013 baseline,
and propose cautious CI-light monitoring before starting a separate numerical-diffusion
improvement phase.
