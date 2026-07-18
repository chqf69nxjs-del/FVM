# Stage 6 V-012 Internal-Valve Mesh/CFL Observation Notes

## Status

`OBSERVED; MERGED`

Work branch:

```text
agent/stage6-v012-mesh-cfl-observation
```

Pull request:

```text
#40 Add V-012 internal-valve mesh/CFL observation
```

The observation follows the merged V-012A through V-012D baseline cases. It is
software / numerical verification only. It is not physical Validation,
design-use acceptance, or approval of a real valve or actuator model.

## Fixed run matrix

The implementation-ready plan was executed without duplication:

```text
V-012A preservation sentinel: n=50, CFL=0.5
V-012B finite opening:         n=50/100/200, CFL=0.5
                               n=100, CFL=0.25
V-012C controlled opening:     n=50/100/200, CFL=0.5
                               n=100, CFL=0.25
V-012D controlled closing:     n=50/100/200, CFL=0.5
                               n=100, CFL=0.25
unique total:                  13 runs
```

The `n=100`, `CFL=0.5` result is reused within each dynamic case for both the mesh
and CFL observations.

## GitHub Actions execution evidence

Observed numerical source head:

```text
9a63dd2bafc264c2a9e41ba68769b5b38cfafe78
```

Execution result:

```text
focused mesh/CFL tests:       12 passed, 0 skipped
complete planned matrix:      13 / 13 runs
selected execution pass:      true
full sweep execution pass:    true
aggregate trend analysis:     complete
comparison plots:             9 / 9
full repository suite:        264 passed in 121.80 s
CoolProp version:             8.0.0
sweep runtime:                512.37 s
```

The corresponding GitHub Actions artifact was:

```text
v012-mesh-cfl-full-d0b15a620dd3e65f27d620f547e5daeb6ffda9f2
sha256:c1cdf41cde8697cdecbd368ee380d925922921fbc77c1c8b77cb8820feb0d372
```

The existing CoolProp Wave, Boundary Reflection, and Controlled Pressure Ramp
regression workflows also passed on the observed head.

## Common health result

All 13 runs:

- completed their requested observation windows;
- passed their existing per-case numerical checks;
- produced finite histories;
- retained positive pressure, temperature, density, and sound speed;
- remained single phase;
- retained every required budget field;
- kept the Mach cap inactive;
- passed the expected characteristic-direction observation.

Maximum observed cross-run diagnostics remained small:

- mass-budget relative residual: `4.1824069873e-16`;
- energy-budget relative residual: `1.7941570436e-16`;
- vapor-mass budget relative residual: `0`;
- mass-flux mismatch: `3.4694469520e-18 kg/m2/s`;
- energy / vapor-mass flux mismatch: `0 / 0`;
- flux-derived Q minus applied Q: `1.3552527156e-20 m3/s`.

These are software/numerical observations, not physical accuracy claims.

## Mesh observation

### V-012B finite-opening driven flow

At `CFL=0.5`, the maximum applied flow was identical across `n=50/100/200`:

```text
3.5342917347e-05 m3/s
```

The maximum near-probe p50 timing offset decreased monotonically:

```text
n=50:  4.5636 ms
n=100: 3.0810 ms
n=200: 2.1543 ms
```

The opposite-direction characteristic ratio remained approximately
`1.52e-06` to `1.56e-06`. Its absolute level is very small and the change between
successive meshes contracts. It is retained as a diagnostic rather than treated
as a physical error norm.

### V-012C controlled opening

The final applied flow was effectively mesh-independent:

```text
n=50:  4.3125746448e-05 m3/s
n=100: 4.3125747220e-05 m3/s
n=200: 4.3125747200e-05 m3/s
```

The maximum near-probe p50 timing offset decreased strongly:

```text
n=50:  1.9002 ms
n=100: 0.7526 ms
n=200: 0.1132 ms
```

The mean dominant characteristic peak contracted toward approximately `273 Pa`:

```text
275.994 / 272.529 / 272.878 Pa
```

The opposite-direction ratio remained approximately `1.81e-06` to `1.85e-06`.

### V-012D controlled closing and complete closure

The maximum near-probe p50 timing offset decreased monotonically:

```text
n=50:  4.8728 ms
n=100: 3.0317 ms
n=200: 2.1373 ms
```

The mean dominant characteristic peak increased with resolution while the
successive normalized differences contracted:

```text
193.549 / 232.039 / 267.626 Pa
```

This is consistent with reduced first-order numerical smearing; the finest mesh is
not treated as an exact solution.

The recorded minimum finite-opening Q is sensitive to the last stored sample before
the discrete zero-opening branch and is therefore not used as a standalone
accuracy surrogate. Complete closure is instead protected by the explicit absolute
zero-through-flow observations below.

For `n=50/100/200`, respectively:

```text
maximum post-closure flux-derived Q:
2.5949e-25 / 4.1519e-24 / 1.9798e-30 m3/s

maximum post-closure mass through-flux:
3.3881e-21 / 5.4210e-20 / 2.5849e-26 kg/m2/s
```

Post-closure energy and vapor-mass through-flux were exactly zero in all planned
mesh runs. Hydraulic-separation and no-flow-direction fractions were `1.0` for
every V-012D run. Independent closed-wall momentum reactions remained diagnostic
and were not tested with the finite-opening momentum relation.

## CFL observation

At `n=100`, changing `CFL` from `0.5` to `0.25` approximately doubled both step
count and runtime:

```text
V-012B: 72 -> 143 steps; 21.43 -> 42.42 s
V-012C: 78 -> 156 steps; 25.16 -> 50.27 s
V-012D: 78 -> 156 steps; 25.34 -> 50.32 s
```

The lower-CFL result was not uniformly closer to the mesh trend. For example, the
near-probe p50 offset at `CFL=0.25` was larger than at `CFL=0.5` for V-012B,
V-012C, and V-012D. This confirms the interpretation rule that lower CFL is not
truth.

## Human review of the nine comparison figures

The saved aggregate artifacts generated nine figures without rerunning or changing
the solver result:

1. representative applied Q versus dx;
2. near-probe p50 timing offset versus dx;
3. dominant characteristic amplitude versus dx;
4. opposite-direction characteristic ratio versus dx;
5. V-012D post-closure Q versus dx;
6. V-012D post-closure mass flux versus dx;
7. budget-residual envelope versus dx;
8. runtime versus cell count;
9. CFL runtime and step-count ratios.

Human review found:

- stable finite-opening flow metrics;
- monotonic p50 timing improvement with mesh refinement;
- contracting opening- and closing-wave amplitude differences;
- opposite-direction ratios remaining of order `1e-06`;
- complete-closure through quantities remaining at numerical zero;
- budgets at zero or roundoff scale;
- approximately fourfold runtime growth when the cell count doubles;
- approximately twofold runtime and step growth when CFL is halved;
- no sign reversal, non-finite value, phase-state change, or data-integrity issue.

## 400-cell decision

**No 400-cell run is required for this observation increment.**

The initial `50 / 100 / 200` plan answered the primary questions:

- timing offsets improve clearly;
- finite-opening flow is stable;
- dynamic amplitude differences contract;
- directional leakage remains very small;
- complete-closure zero-through-flow remains protected at numerical floor;
- all conservation and state-health checks pass.

The machine summary flagged the small leakage ratios and the last finite-opening
sample as review items because they are not monotonic error norms. Human review
found neither to be evidence of an unresolved primary mesh trend. Adding `n=400`
would therefore add cost without resolving a material ambiguity in the stated
verification scope.

## Constraints retained

- software / numerical verification only;
- physical Validation is not performed;
- design-use acceptance is not performed;
- CoolProp remains `not_approved_for_design_use`;
- the Kv relation remains for single-phase liquid flow;
- fixed-pressure boundaries remain zero-impedance numerical idealizations;
- the hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`;
- prescribed opening schedules are not actuator-dynamics or hysteresis models;
- the finest mesh is not an exact solution;
- lower CFL is not truth;
- no CI-light regression band is defined or relaxed in this observation increment.

## Review decision

No solver-physics, conservation, sign, timing, phase-state, reproducibility, or
data-integrity blocker was found. PR #40 was merged at
`ddc83bc390cbb712900017e9ff82112fae81200f`. V-012 overall remains `IN_PROGRESS`; CI-light band specification,
permanent GitHub Actions coverage, formal report, and SHA256 manifest remain before
V-012 completion.
