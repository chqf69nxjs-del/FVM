# Stage 6 execution log

This file records significant implementation, verification, review, and stop decisions for Stage 6.

Guardrails throughout this log:

- software / numerical verification only
- not physical Validation
- not design-use acceptance
- CoolProp remains `not_approved_for_design_use`
- CI-light meshes are not design meshes
- finest meshes are comparison references, not exact solutions
- lower CFL is not treated as truth

## 2026-07-14 — Delegated continuation

The remaining V-011 formalization work and V-012 single-phase valve-operation work were delegated for continued execution.

Operating rule:

- record material progress in this log and associated PR comments
- continue without waiting for routine confirmation
- if a critical numerical, traceability, data-loss, or reproducibility problem is found, save all changes to a branch and stop

### V-011 state at delegation

Completed:

- baseline runner and telemetry
- real-fluid pressure-boundary thermodynamic-state correction
- visualization, arrival analysis, x-t pressure history, and p50 front fit
- 50 / 100 / 200-cell and CFL observation
- CI-light evaluator and broad regression limits
- Windows focused and full test passes
- GitHub Actions installed-CoolProp regression pass without skips
- formal report and SHA256 manifest generation

Open before V-011 completion:

- preserve exact backend name and CoolProp version in aggregate sweep artifacts and formal outputs
- make custom CFL case identifiers collision-free
- regenerate formal artifacts after traceability hardening
- synchronize `MASTER_VERIFICATION_INDEX.md`
- complete PR #32 review and merge

### Initial risk assessment

No critical solver or data-integrity blocker is present. The remaining V-011 items are traceability and robustness hardening. Work continues.

## 2026-07-15 — V-011 formalization completion checkpoint

Implemented on PR #32:

- collision-free CFL tokens based on round-trip-safe float representations
- uniqueness guard for generated sweep case IDs
- exact `property_backend_name`, `coolprop_version`, and design-status propagation into every aggregate summary row
- aggregate identity consistency guards across all four sweep cases
- no-solver-rerun backfill utility for existing local sweep artifacts
- formal report validation of metrics/summary backend identity agreement
- formal report traceability section with source backend and source CoolProp version
- manifest backend identity and provenance fields
- tests for close-CFL ID separation, row inconsistency, metrics/summary mismatch, and unexpected design status
- MASTER VERIFICATION INDEX synchronization

Verification evidence before the final local artifact refresh:

- Windows focused tests: `28 passed in 10.91s`
- Windows full suite: `217 passed in 66.22s`
- direct CI-light regression: pass, no failed checks
- GitHub Actions controlled-pressure-ramp regression: success
- installed CoolProp regression was not skipped
- wave and boundary-reflection workflows also passed

## 2026-07-15 — Final V-011 artifact refresh

The existing four-run sweep artifacts were updated from their per-run metrics without rerunning the solver.

Backfill result:

- `property_backend_name = coolprop_co2`
- `coolprop_version = 8.0.0`
- `property_backend_design_status = not_approved_for_design_use`
- `updated_row_count = 4`
- `solver_rerun = False`
- `numerical_results_changed = False`

Formal outputs were regenerated after traceability hardening:

- artifact count: `46`
- final report SHA256: `dadc6a4a982ff24e6cdf70b70d43ca8b6dadac71ac51c31c19ac7277828a3cf2`
- overall sweep execution pass: `True`
- source backend: `coolprop_co2`
- source CoolProp version: `8.0.0`

Final Windows test result:

- full suite: `223 passed in 78.44s`

Final GitHub Actions state before merge:

- CoolProp Controlled Pressure Ramp Regression: success
- CoolProp Wave Regression: success
- CoolProp Boundary Reflection Regression: success
- installed CoolProp regression was not skipped
- CI-light artifact upload succeeded

Completion decision:

- no solver-physics or governing-equation change occurred
- no regression band was relaxed
- no numerical result changed during traceability backfill
- all required tests, artifacts, reproducibility instructions, and CI evidence are present

## 2026-07-15 — V-011 COMPLETE

- PR #32 was marked ready and merged.
- merge commit: `83bcf51322e88707835f4c500c012aa49ef5602b`
- no unresolved review thread remained at merge time
- all three current GitHub Actions workflows completed successfully
- `MASTER_VERIFICATION_INDEX.md` was updated on `main`
- V-011 status changed to `COMPLETE`
- Stage 6 remains `IN_PROGRESS` because V-012 single-phase internal-valve operation remains

The V-011 completion claim is limited to software/numerical verification and regression protection. It does not establish physical Validation, equipment fidelity, a design mesh, or design-use acceptance.

## 2026-07-15 — V-012 specification checkpoint

The current `KvLiquidValve`, `LinearRampOpening`, `InternalValveInterface`, solver interface application path, and interface energy-budget diagnostics were reviewed before runner implementation.

Current semantics retained:

- single-phase incompressible-liquid Kv relation
- explicit two-sided internal-interface fluxes
- common mass, total-enthalpy energy, and vapor-mass flux at finite opening
- side-specific pressure contribution to momentum flux
- independent reflective walls at zero opening
- Mach-based flow cap
- hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`

A refined implementation-ready specification was added at:

```text
docs/verification/v012_single_phase_internal_valve_operation_spec.md
```

The primary baseline is fixed as a small `1 kPa` left-to-right pressure difference at `280 K`, a valve at `x/L = 0.5`, and a derived Kv that gives a full-open target face velocity of `1.0e-3 m/s`.

The implementation sequence is fixed as:

1. diagnostic-only raw/applied/capped flow telemetry and constant-opening baseline
2. controlled opening and closing ramps with probe characteristics and visualization
3. mesh/CFL observation, CI-light, formal report, and manifest

Identified telemetry gap:

- existing scalar valve diagnostics report the raw Kv flow but not the Mach-clipped flow actually applied to the interface flux

This is a diagnostic gap only. Closing it must not change the applied numerical flux.

No critical solver-physics or data-integrity blocker was found. No regression band is defined at this stage. V-012 remains `IN_PROGRESS`.

## 2026-07-15 — V-012A uniform-state baseline

PR #35 introduced diagnostic-only raw/applied/capped-flow telemetry, exact two-sided interface-flux telemetry, the V-012A uniform-state runner, four human-review plots, and installed-CoolProp tests.

Observed result:

- nonzero opening `0.5` with zero pressure difference produced zero raw/applied/flux-derived Q
- no material probe pressure or velocity disturbance occurred
- mass, energy, vapor-mass, and momentum-difference residuals stayed at numerical zero
- the case remained finite, positive, and single phase
- the software observation pass was `True`
- Windows full suite: `234 passed`

PR #35 was merged at `128596593ae99e61289475cb79a39ec2127f72aa`.

## 2026-07-16 — V-012B small driven-flow baseline

PR #36 added the constant-opening `1 kPa` driven-flow observation using separate consistent CoolProp `(p,T)` states and a pre-boundary-arrival evaluation window.

Observed result:

- initial raw/applied/flux-derived Q all equalled `3.534291735286872e-05 m3/s`
- flow-sign consistency was `1.0`
- Mach cap did not activate
- interface mass, energy, vapor-mass, and momentum-difference residuals were zero
- maximum `flux Q - applied Q` was `3.3881317890172014e-21 m3/s`
- upstream probes decompressed, downstream probes compressed, and velocity remained positive
- energy budget relative residual was `-1.7941570435960072e-16`
- the case remained single phase
- Windows full suite: `239 passed in 69.97s`

PR #36 was merged at `8cb3deee003b141c0cb8e8d56ccc3eaa77c01d8f`.

## 2026-07-16 — V-012C controlled opening-ramp observation

PR #37 implements the prescribed opening operation:

```text
opening:       0.0 -> 1.0
initial hold:  0.005 s
ramp duration: 0.010 s
```

Added evidence:

- exact opening schedule telemetry
- raw/applied/flux-derived Q histories
- two-sided interface-flux histories
- probe `A_plus / A_minus` histories and direction summary
- full pressure, velocity, temperature, and density field history
- nine human-review plots, including pressure/velocity x-t maps, profile snapshots, and the delta-p/Q path

Windows observation:

- focused tests: `6 passed in 4.27s`
- full repository suite: `245 passed in 72.53s`
- supplied working tree was clean
- `overall_observation_execution_pass = True`
- opening monotonic non-decreasing: `True`
- initial/final applied Q: `0 / 4.3125747224746e-05 m3/s`
- flow-sign consistency: `1.0`
- Mach-cap activation count: `0`
- primary characteristic direction pass: `True`
- maximum opposite-direction characteristic ratio: `1.6229101813567113e-06`
- upstream decompression and downstream compression observed
- all documented interface residuals were zero
- mass budget relative residual: `-1.394135662426362e-16`
- the case remained finite, positive, and single phase
- target time `0.0697143731 s` preceded first boundary arrival `0.0946929534 s`

Human review found no growing oscillation, checkerboard pattern, isolated non-valve spike, premature boundary return, direction error, or conservation blocker. The nearest-sample `ramp start` label in the delta-p/Q figure is a presentation-only limitation and does not change numerical data or acceptance.

Decision:

- no solver-physics, governing-equation, Kv-law, Mach-cap, fixed-pressure-boundary, or conserved-energy change occurred
- no regression band was introduced or relaxed
- PR #37 was merged at `f933479658d61b30d2214a2ceb9cd64d0efa671a`
- V-012 remains `IN_PROGRESS`; V-012D controlled closing ramp is next

## 2026-07-16 — V-012D controlled closing-ramp observation

PR #38 implements the specification-defined complete closing operation:

```text
opening:          1.0 -> 0.0
initial hold:     0.005 s
ramp duration:    0.010 s
post-closure hold: 0.005 s
```

The V-012B/C pipe, CoolProp states, Kv calibration, fixed-pressure numerical
boundaries, and baseline `n=100`, `CFL=0.5` are retained. The closing schedule is
prescribed component operation, not actuator dynamics or ESD-event verification.

Implemented evidence:

- monotonic full-open-to-zero schedule telemetry
- finite-opening raw/applied/flux-derived Q consistency
- exact two-sided interface-flux history
- explicit post-closure hydraulic-separation and no-flow checks
- independent reflective-wall momentum reactions after complete closure
- probe characteristic increments rebased to the pre-arrival state
- full pressure / velocity / temperature / density field history
- nine human-review plots

GitHub Actions observation:

```text
focused tests:        7 passed in 7.53s
full repository:      252 passed in 106.74s
static checks:        success
baseline metrics gate: success
plot count:           9
overall observation:  True
CoolProp version:     8.0.0
```

Key numerical results:

- target time: `0.06971437311556053 s`
- first initial-state boundary arrival: `0.08969295335583746 s`
- opening monotonic non-increasing: `True`
- initial / final applied Q: `7.068583469428279e-05 / 0 m3/s`
- finite-opening raw/applied relative difference: `0`
- finite-opening applied/flux relative difference: `1.8702192872045635e-16`
- post-closure sample count: `61`
- post-closure hydraulic-separation fraction: `1.0`
- post-closure no-flow-direction fraction: `1.0`
- maximum post-closure mass through-flux: `5.421010862427522e-20 kg/m2/s`
- maximum post-closure energy / vapor-mass through-flux: `0 / 0`
- maximum post-closure flux-derived Q: `4.151910405935732e-24 m3/s`
- all closure through quantities remained below their roundoff tolerances
- flow-sign consistency: `1.0`
- Mach-cap activation count: `0`
- maximum applied face Mach: `1.7939138723497895e-06`
- primary characteristic direction pass: `True`
- maximum opposite-direction characteristic ratio: `1.2305912228546978e-06`
- upstream compression and downstream decompression observed
- mass / energy / vapor-mass budget relative residuals: `0 / 0 / 0`
- the case remained finite, positive, and single phase

The relative Q-consistency gate is deliberately evaluated only on finite-opening
rows. At complete closure, Q is numerically zero and is verified with explicit
absolute through-flux tolerances; a relative ratio at zero has no useful numerical
meaning. No tolerance was relaxed.

Human review found the expected left-going compression and right-going
decompression, smooth flow decay, complete-closure wall reactions, and no growing
oscillation, checkerboard pattern, isolated non-valve spike, or premature boundary
return. The delta-p/Q event marker remains a nearest-sample presentation detail and
does not change the schedule or numerical result.

Decision:

- no solver-physics, governing-equation, Kv-law, Mach-cap, fixed-pressure-boundary,
  or conserved-energy change occurred
- hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`
- no regression band was introduced before mesh/CFL observation
- PR #38 is ready for review after documentation synchronization
- V-012 remains `IN_PROGRESS`; mesh/CFL observation is next

## 2026-07-18 — V-012 mesh/CFL observation

PR #40 executed the fixed 13-run V-012A/B/C/D mesh/CFL matrix.

```text
planned / executed runs:     13 / 13
overall sweep pass:          True
aggregate analysis:          complete
comparison plots:            9
focused tests:               12 passed, 0 skipped
full repository:             264 passed in 121.80 s
CoolProp:                    8.0.0
source head:                 9a63dd2bafc264c2a9e41ba68769b5b38cfafe78
artifact sha256:             c1cdf41cde8697cdecbd368ee380d925922921fbc77c1c8b77cb8820feb0d372
```

Observed decisions:

- V-012B/C/D near-probe p50 timing offsets improved with mesh refinement;
- finite-opening flow and interface-Q consistency remained stable;
- V-012D complete-closure through quantities remained at numerical zero;
- all runs remained single phase with positive states and required budgets;
- halving CFL approximately doubled step count and runtime but was not uniformly closer to the mesh trend;
- `n=400` is not required for this observation increment after human review;
- no solver-physics, Kv-law, boundary-meaning, or energy-treatment change occurred;
- no CI-light band was defined in this observation increment.

V-012 remains `IN_PROGRESS`; CI-light, permanent GitHub Actions, formal report, and SHA256 manifest remain.

## 2026-07-18 — PR #40 merged

V-012 mesh/CFL observation was merged at:

```text
ddc83bc390cbb712900017e9ff82112fae81200f
```

The next V-012 increment is CI-light band specification followed by permanent
GitHub Actions coverage, formal report, SHA256 manifest, and completion review.
V-012 remains `IN_PROGRESS`.
