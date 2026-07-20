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

Status: `OBSERVED; MERGED` in PR #50. Merge commit:
`f403103c46a1d618ce2f2345c986e29b921b664a`. V-013 overall remains `IN_PROGRESS`.

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
before review-ready state. Final-head permanent workflows passed `4 / 4`, and all
review threads were resolved. Production solver, numerical flux, EOS inversion, and
boundary behaviour remain unchanged. Physical Validation, design-use acceptance, and
V-013 acceptance bands remain outside this increment.

## Joint Stage 7 first-order conclusion

V-013A/B/C consistently support the following conclusions:

- propagation direction and approximate timing are correct;
- rigid-wall and fixed-pressure reflection signs are correct;
- the essential boundary-condition behaviour is reproduced;
- all principal differences improve with mesh refinement;
- strong first-order FVM numerical diffusion remains common to all three cases;
- the current solver is a robust software/numerical verification baseline, not a
  physically validated or design-accurate wave-amplitude model.

## 2026-07-20 — V-013 baseline formalization merged

Status: `FORMALIZED; MERGED` in PR #51. Merge commit:
`62390bd526ae99b6702f4ed76e3594e1bf01259b`.

Starting point:

```text
base main commit:      afba28c56dc43bee82dd6f169d0249333ed7bfe2
Windows full baseline: 385 passed in 151.59 s
working tree:          clean
production changes:    none
```

The formalization increment added:

- a combined A/B/C baseline and limitation statement;
- machine-readable baseline version `v013_baseline_v1`;
- pure integrity tests for source commits, fixed configuration, signs, refinement trends,
  and false acceptance flags;
- a two-tier CI-light proposal that separates exact qualitative invariants from future
  numeric drift bands;
- synchronized merged status in the V-013A and V-013B observation notes.

Windows review-readiness validation at head
`61c4810d3aa0a13c2a0709628955512d1f1243a2` passed:

```text
baseline-definition integrity: 4 passed
full repository:              389 passed
committed diff:               clean
working tree:                 clean
permanent GitHub Actions:     4 / 4 success
```

The current first-order FVM is now the selectable software/numerical control. The baseline
does not approve physical Validation, design use, an exact solution, or any numeric
accuracy/regression band. CI-light remains `PROPOSED; NOT APPROVED; NOT IMPLEMENTED`.

## 2026-07-20 — Numerical-diffusion improvement assets

PR #52 is `OPEN; READY FOR REVIEW` and contains a solver-independent MUSCL/TVD
reconstruction scaffold. Its final intended diff contains first-order and MUSCL
reconstruction, minmod/MC/van Leer limiters, pure tests, and verification documentation.
It does not connect to `FvmSolver` or change production numerical states.

PR #53 is a `VALIDATED STACKED DRAFT` based on PR #52. It contains a periodic scalar
linear-advection comparison and records material peak-retention, width-preservation, and
L2-error improvements for all MUSCL variants relative to the same-time-integrator
first-order control. It does not approve a production limiter or time integrator.

These PRs remain useful numerical assets but are not dependencies of the HEM thermodynamic
line. Higher-order production connection is deferred until a first-order HEM baseline is
established.

## 2026-07-20 — Pure-CO2 HEM thermodynamic scaffold

Status: `VALIDATED DRAFT; NOT SOLVER CONNECTED` in PR #54 on branch
`agent/stage7-lco2-hem-thermodynamic-scaffold`.

The branch starts directly from PR #51 merge commit
`62390bd526ae99b6702f4ed76e3594e1bf01259b`.

The increment adds:

- an HEM-oriented wrapper for `RealFluidPropertyBackend.state_from_rho_e`;
- finite-positive density and finite internal-energy validation without imposing a
  universal real-fluid `e >= 0` rule;
- validation of pressure, temperature, quality, void fraction, and backend-reported sound
  speed;
- quality-regime classification for liquid endpoint, open two-phase interval, and vapor
  endpoint;
- backend-error wrapping with backend-name context;
- input immutability and memory-independence guards;
- a deterministic surrogate liquid/two-phase/vapor 0-D path;
- JSON, CSV, Markdown, and NPZ evidence with explicit false approval flags.

Primary validation:

```text
validation head:           c96567cb63a67b3d9be2f3f20e7e5790e7ee3828
workflow run:              29739900542
artifact ID:               8459985478
artifact SHA256:           98c3e973d0f81c68bf0cf86396679964d87a3f4f1ecdb542bdbe1dbaeecf8103
focused tests:             24 passed, 0 skipped
full repository:           406 passed, 0 skipped
CoolProp wrapper states:    2 compressed-liquid states passed
0-D path states:           23 / 23
0-D artifact formats:       4 / 4
committed diff:             clean
tracked/staged files:       unchanged
permanent workflows:       4 / 4 success
```

The CoolProp states at `5 MPa / 280 K` and `8 MPa / 280 K` returned finite properties,
quality `0`, void fraction `0`, and quality regime `liquid_endpoint`.

The dependency-free 0-D path covered compressed liquid, saturated liquid, the open
liquid-vapor quality interval, saturated vapor, and expanded vapor. All states had finite
positive pressure, temperature, and backend-reported sound speed; quality and void fraction
were monotone along the fixed path.

Important limitations remain:

```text
production solver connected:                         false
pure-CO2 HEM thermodynamic core complete:             false
complete phase classification:                       false
equilibrium two-phase sound-speed closure approved:  false
backend-reported sound speed:                         diagnostic only
critical region validated:                           false
solid phase supported:                               false
physical Validation:                                 false
design-use acceptance:                               false
```

The current labels are quality-regime labels rather than complete phase labels. The next
technical work must expose explicit backend phase classification, separate two-phase
property evaluation from sound-speed evaluation, and establish a reviewed equilibrium
sound-speed closure before solver connection.

Temporary validation workflow changes were removed after evidence capture. No production
solver, flux, EOS-adapter, phase-change, boundary, interface, or source behaviour changed.

## Next

1. review PR #54 as a thermodynamic scaffold, not a completed HEM model;
2. complete PR #52/#53 independently as later numerical-improvement assets;
3. expose explicit CoolProp phase classification for safe representative `rho/e` states;
4. define critical- and solid-region stop guards;
5. separate equilibrium two-phase `p/T/Q/phase` evaluation from sound-speed evaluation;
6. define and verify an equilibrium two-phase sound-speed closure;
7. generate a CoolProp pure-CO2 0-D phase/property map;
8. then connect the closure to a first-order uniform HEM-state preservation case.
