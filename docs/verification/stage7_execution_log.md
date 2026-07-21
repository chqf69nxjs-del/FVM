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
Production solver behavior is unchanged.

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

Final evidence:

```text
workflow run:       29684930259
focused tests:      57 passed, 0 skipped
full repository:    350 passed, 0 skipped
runs / figures:     3 / 3, 7 / 7
artifact ID:        8441899419
artifact SHA256:    709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861
```

Pressure and velocity reflection signs are correct. Wall-face velocity, mass flux, and
energy flux are exactly zero. Strong first-order numerical broadening remains at the
finest mesh.

## 2026-07-19 to 2026-07-20 — V-013C fixed-pressure reflection

Status: `OBSERVED; MERGED` in PR #50. Merge commit:
`f403103c46a1d618ce2f2345c986e29b921b664a`.

Fixed identities:

```text
A-_reflected = -A+_incident
pressure reflection coefficient = -1
velocity reflection coefficient = +1
boundary pressure perturbation = 0
boundary velocity / incident velocity amplitude = 2
```

Final evidence:

```text
workflow run:       29692477941
PR head:            2f5c10b3f99f561d457ab8d391d5e91be98b7ff3
focused tests:      58 passed, 0 skipped
full repository:    385 passed, 0 skipped
runs / figures:     3 / 3, 7 / 7
artifact ID:        8444138380
artifact SHA256:    6432fb8502687cb974c161356e4ac8364235ef2ba5c92ac7bb9f1e52dca54786
```

The reflected pressure sign is negative, reflected velocity sign is positive, and the
returning characteristic is left-going `A-`. The finest-mesh final peak ratio is
`0.57212615`, confirming that strong numerical diffusion remains the dominant
limitation.

## 2026-07-20 — V-013 baseline formalization merged

Status: `FORMALIZED; MERGED` in PR #51. Merge commit:
`62390bd526ae99b6702f4ed76e3594e1bf01259b`.

Review-readiness validation:

```text
baseline-definition integrity:  4 passed
full repository:               389 passed
committed diff:                clean
working tree:                  clean
permanent GitHub Actions:      4 / 4 success
```

The first-order FVM is fixed as the selectable software/numerical control. It is not an
exact solution, physical Validation result, design-use approval, or approved numeric
accuracy/regression band. CI-light remains `PROPOSED; NOT APPROVED; NOT IMPLEMENTED`.

## 2026-07-20 — Numerical-diffusion improvement assets

PR #52 is `OPEN; READY FOR REVIEW` and contains a solver-independent MUSCL/TVD
reconstruction scaffold. Final head:
`829880e88010ea808b316e09f28f26a0a18c7f03`.

Its intended diff contains four files:

```text
src/liquid_gas_transient/reconstruction.py
tests/test_stage7_muscl_reconstruction.py
docs/verification/stage7_muscl_reconstruction_scaffold_plan.md
docs/verification/stage7_muscl_scaffold_validation_commands.md
```

PR #53 is a `VALIDATED STACKED DRAFT` based on PR #52. Final head:
`ff72bd303a99d832bad6d13536ff9b5682eeb4f9`.

The scalar-advection evidence shows material reduction in numerical diffusion for all
MUSCL variants. At `n=200`, peak retention under SSP-RK2 was:

```text
first order:       0.57795218
MUSCL minmod:      0.88811719
MUSCL MC:          0.96768181
MUSCL van Leer:    0.94953622
```

The numerical-improvement line remains separate from the HEM physical-model line.
Production activation is deferred.

## 2026-07-20 to 2026-07-21 — Pure-CO2 HEM foundation

### PR #54 — thermodynamic scaffold and 0-D path

Status: `MERGED`. Merge commit:
`6e0779346a9adb0f3c74d790f558a6813f009ee7`.

Final reviewed head:
`39a394698383879225216aee403c1221fe454e0e`.

Primary evidence:

```text
workflow run:         29739900542
artifact ID:          8459985478
artifact SHA256:      98c3e973d0f81c68bf0cf86396679964d87a3f4f1ecdb542bdbe1dbaeecf8103
focused tests:        24 passed, 0 skipped
full repository:      406 passed, 0 skipped
0-D path states:      23 / 23
artifact formats:     4 / 4
permanent workflows:  4 / 4 success
```

The increment adds an HEM-oriented wrapper around
`RealFluidPropertyBackend.state_from_rho_e`, explicit finite-value guards, backend-error
traceability, input immutability, and a deterministic liquid/two-phase/vapor path.

Backend-reported sound speed remains diagnostic only. No production solver, flux, CFL,
boundary, source, interface, or phase-change behavior was changed.

### PR #55 — explicit CoolProp phase classification

Status: `MERGED`. Merge commit:
`e45362d1aa07bf7144f606dc32595d4ab2f7093d`.

Final reviewed head:
`97ffe4e57c3a006ae27702749c417f9e3989aba8`.

Primary evidence:

```text
workflow run:         29744597504
artifact ID:          8461927762
artifact SHA256:      d91869f6d7fd3d18ab9e2abf1b3e9b6fecfa87228dabd5546fd8024aa7252c6a
focused tests:        39 passed, 0 skipped
full repository:      423 passed, 0 skipped
phase-map states:     9 / 9
sound-speed calls:    none
permanent workflows:  4 / 4 success
```

The increment uses CoolProp `PhaseSI` rather than inferring phase from quality alone. It
separates equilibrium state evaluation from acoustic closure and defines explicit
critical, solid/below-triple, and unknown-state guards.

CoolProp reports `8 MPa / 280 K` as `supercritical_liquid`; away from the critical
guard this is treated as a high-density liquid candidate for the first LCO2 path.

### PR #56 — equilibrium sound-speed closure candidate

Status: `MERGED`. Merge commit:
`b098f67b71bf53bd20fc14bf80d7f4cea595a707`.

Final reviewed head:
`3c21be4410e808f22888edd9814204a25df40a4c`.

Implemented candidate:

```text
c_eq^2 = (dp/drho)|e + (p/rho^2) (dp/de)|rho
```

Primary evidence:

```text
workflow run:           29748093054
artifact ID:            8463388994
artifact SHA256:        97b6f04a38cd6debafc66fac3dc8b902d1abdf1fed982e04c48000ca5682ad79
focused HEM tests:      63 passed, 0 skipped
full repository:        447 passed, 0 skipped
sound-speed states:     10 / 10
two-phase states:       7 / 7
CoolProp two-phase A:   never requested
permanent workflows:    4 / 4 success
```

The closure uses adaptive phase-preserving central finite differences of `p(rho,e)`.
Non-finite or non-positive results are rejected without clipping. Single-phase estimates
agree with CoolProp reference sound speed within the qualitative test guard.

Representative two-phase observations at `2 MPa` range from `37.846900 m/s` at
`q=0.05` to `197.788354 m/s` at `q=0.95`. These are closure observations, not approved
physical accuracy results.

### PR #57 — uniform HEM-state preservation

Status: `OBSERVED; MERGED`. Merge commit:
`f27ec42d0e191065cd4d3d214a14009b07be800f`.

Final reviewed head:
`45cdfe3da409e98825bc3b2ab52265f5f51f2900`.

Fixed case:

```text
p:                    2 MPa
quality:              0.50
velocity:             0 m/s
cells / steps:        8 / 8
CFL:                  0.25
boundaries:           transmissive
source:               NoSource
phase change:         NoPhaseChange
internal interfaces:  none
```

Primary evidence:

```text
workflow run:          29751190749
artifact ID:           8464712262
artifact SHA256:       71f7934f6f0061191f8af09b9cdf802a5b797f628878cd045a13a94273f5e999
focused HEM tests:     76 passed, 0 skipped
full repository:       460 passed, 0 skipped
uniform cells / steps: 8 / 8
permanent workflows:   4 / 4 success
```

Fixed-state observations:

```text
rho:                       99.97757528102285 kg/m3
temperature:               253.64735829812284 K
quality:                   0.5
void fraction:             0.951436972434191
equilibrium sound speed:   135.76568112572576 m/s
dt:                        0.002301759895496782 s
final time:                0.018414079163974254 s
```

Every measured drift in conservative state, primitive variables, acoustic quantities,
and mass/momentum/energy/vapor-mass inventories was exactly zero after eight steps.

This demonstrates exact preservation of one uniform stationary open-two-phase state
through the verification-only adapter. It does not establish nonuniform-flow accuracy,
dynamic flashing, phase-boundary crossing, or production readiness.

## 2026-07-21 — Stacked PR convergence

PRs #54–#57 were originally prepared as a stacked sequence. They were merged
sequentially into `main` using squash merge. After each parent merge, the next PR was:

1. rebased onto the updated `main`;
2. force-pushed with `--force-with-lease`;
3. retargeted from the former parent branch to `main`;
4. checked for the intended PR-specific file set;
5. checked against the four permanent workflows;
6. marked ready for review and merged.

Final PR-specific diffs after restacking were:

```text
PR #54: 6 files
PR #55: 3 files
PR #56: 4 files
PR #57: 4 files
```

During the PR #57 restack, an initial rebase used the new PR #56 head instead of the
original stacked boundary and encountered already-upstream commits and an add/add
documentation conflict. The rebase was aborted. A stale `.git/rebase-merge` directory,
held under the OneDrive-synchronized working path, was renamed and retained for recovery.
A backup branch `backup/pr57-before-rebase` was created before retrying.

The correct original PR #56 head
`3e032ced2cb8f65e058783886b36b58a72b7719e` was then used as the cut boundary. The
resulting PR #57 diff contained only the intended four files and was merged normally.

No production source changes were introduced by the restacking operation itself.

## Current technical conclusion

The HEM foundation on `main` now supports:

- guarded `rho/e` thermodynamic evaluation;
- explicit phase classification;
- an independently defined equilibrium sound-speed candidate;
- verification-only connection to existing Rusanov flux and CFL;
- exact preservation of one uniform stationary open-two-phase state.

The current evidence does not support the following claims:

```text
dynamic equilibrium-quality synchronization:  not implemented
nonuniform two-phase flow:                     not verified
phase-boundary crossing:                       not verified
pipeline depressurization:                     not implemented
two-phase acoustic accuracy band:              not approved
production HEM activation:                     not approved
physical Validation:                           false
design-use acceptance:                         false
```

## Next

1. merge this documentation synchronization PR;
2. define and verify dynamic equilibrium-quality synchronization;
3. run a small nonuniform open-two-phase case before phase-boundary crossing;
4. add a first-order one-dimensional liquid-to-two-phase expansion case;
5. build the first LCO2 pipeline depressurization prototype;
6. retain PR #52/#53 as later numerical-improvement assets until the first-order dynamic
   HEM path is stable.
