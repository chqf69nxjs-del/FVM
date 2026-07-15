# Stage 6 V-012 Execution Log

This log records material decisions, implementation checkpoints, tests,
artifacts, and stop conditions for V-012 single-phase internal-valve operation.

Persistent guardrails:

- software / numerical verification only
- physical Validation = false
- design-use acceptance = false
- `property_backend_design_status = not_approved_for_design_use`
- single-phase scope only
- no flashing, cavitation, choked/two-phase discharge, ESD, or pump trip
- CI-light meshes are not design meshes
- finest meshes are comparison references, not exact solutions

## 2026-07-15 — V-012 specification-first start

Starting point:

- V-011 is `COMPLETE`
- main is synchronized and the full Windows suite passes (`223 passed`)
- V-012 is `IN_PROGRESS`
- the repository contains an existing internal-valve / Kv software path
- no V-012 runner is present yet

Work opened on:

```text
agent/stage6-v012-internal-valve-spec
```

Draft PR scope:

- fix the V-012 scope and case order
- define internal-face telemetry and artifact schemas
- document budget and sign conventions
- define stop conditions
- survey the existing internal-valve code path
- make no solver-physics, valve-law, or total-energy change

Initial case order:

1. V-012A uniform-state constant-opening preservation
2. V-012B small driven-flow constant-opening baseline
3. V-012C small controlled opening ramp
4. V-012D small controlled closing ramp to nonzero opening
5. V-012E closed-limit observation only after separate review

Initial risk assessment:

- no critical blocker prevents specification work
- the current hydraulic-loss proxy remains diagnostic
- the relationship between that diagnostic and conserved `rhoE` is not changed
- actual shared internal-face numerical-flux telemetry is a hard requirement
- V-012A can proceed without resolving a driven-flow energy-loss model because
  its expected material flow is zero

Stop rule for the next implementation PR:

If the solver cannot expose one shared internal-face flux, or if the baseline
requires a valve-law / energy-treatment change, save the branch and stop for
owner review.

## 2026-07-15 — V-012A implementation checkpoint

Specification PR #34 was merged at commit
`6f4bc16c38361b0fffec3267766224aff0160a90`.

Implementation work was opened on:

```text
agent/stage6-v012-uniform-valve-baseline
```

Implemented diagnostic-only interface additions:

- raw Kv target flow
- Mach-limited applied flow and flow limit
- cap activation state
- hydraulic-separation state
- flow direction and upwind state
- applied face velocity and Mach number
- exact two-sided interface flux evaluation used by the solver update

`InternalValveInterface.apply()` now consumes the same `evaluate_fluxes()`
result that is exposed to telemetry. This avoids reconstructing a second,
independent valve flux from cell-center values.

Compatibility and physics constraints retained:

- the existing Kv equation is unchanged
- the existing Mach cap is unchanged
- finite-opening mass, total-enthalpy energy, and vapor-mass flux formulae are unchanged
- the documented momentum-flux difference is unchanged
- the legacy raw-Q diagnostic fields remain available
- the hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`
- no governing-equation or external-boundary meaning was changed

The first runner implements V-012A:

- uniform single-phase CoolProp CO2 at `8 MPa` and `280 K`
- zero initial velocity and zero driving pressure difference
- nonzero constant valve opening at the pipe midpoint
- transmissive, non-driving external boundaries
- exact internal-face valve and flux telemetry
- probe, boundary, final-profile, budget, metrics, and observation-report artifacts

Expected implementation behavior:

- requested and actual opening agree to roundoff
- raw and applied flow remain at numerical zero
- the Mach cap remains inactive
- the existing no-flow hydraulic-separation path is active
- no material pressure or velocity disturbance is introduced
- two-sided mass, energy, and vapor-mass mismatches remain at roundoff scale
- momentum-flux difference remains consistent with the pressure difference
- the case remains finite, positive, and single phase

Pure tests were added for uniform flow, finite-opening flux identities, deliberate
Mach clipping, exact `apply()`/telemetry flux identity, and legacy diagnostic
compatibility. An installed-CoolProp mini-run test was also added.

Test status at this checkpoint:

- source files are committed to the branch
- local Windows focused and full-suite execution is pending
- no numerical baseline artifact has yet been accepted
- no regression or acceptance band has been defined

No critical solver-physics or data-integrity blocker has been found. The branch
must remain unmerged until the focused tests and installed-CoolProp baseline are
executed and reviewed.

## 2026-07-15 — Human-review plotting checkpoint

A CSV/JSON-driven plotter was added for the V-012A baseline. Plotting is kept
strictly downstream of the numerical run: it reads saved artifacts, does not
reconstruct or alter the interface flux, does not rerun the solver, and does not
change numerical results.

The V-012A baseline plot set is:

1. `*_valve_command_and_flow.png`
   - requested and actual opening
   - valve pressure difference
   - raw Kv, applied, flux-derived, and limiting flow rates
   - Mach-cap activation markers
2. `*_probe_pressure_velocity.png`
   - pressure perturbation and velocity at all recorded probes
3. `*_interface_flux_consistency.png`
   - mass, energy, and vapor-mass flux mismatches
   - momentum-flux difference versus valve pressure difference
   - flux-derived Q minus applied Q
4. `*_budget_and_health.png`
   - final mass, energy, and vapor-mass residuals normalized by their documented
     numerical tolerances
   - pressure, velocity, flux, momentum, and Q-consistency observations normalized
     by their documented numerical tolerances

The plotting command is:

```powershell
python -m liquid_gas_transient.plot_internal_valve_results `
  verification/internal_valve_uniform_baseline
```

A one-command artifact runner was also added:

```powershell
python -m liquid_gas_transient.cases.coolprop_internal_valve_uniform_artifacts `
  verification/internal_valve_uniform_baseline
```

The isolated synthetic plotter test passed (`2 passed`). Repository-focused,
installed-CoolProp, and full-suite Windows tests remain pending. The dynamic
V-012B/C/D plots—characteristics, x-t maps, profile snapshots, and the valve
`delta-p` versus Q path—remain deferred until driven-flow and opening/closing
histories exist.

No regression band was introduced. Plotting remains a human-review aid and is
not a substitute for software regression checks, physical Validation, or
design-use acceptance.

## 2026-07-15 — Windows recovery and first V-012A observation

The temporary Windows application-control blocker was resolved after a Windows
update and restart. No security setting was deliberately disabled or bypassed.
The same repository virtual environment then produced:

```text
CoolProp version: 8.0.0
CO2 density at 8 MPa and 280 K: 922.9172130294444 kg/m3
full repository suite: 234 passed in 69.79s
```

The V-012A numerical artifacts and four PNGs were generated and reviewed.
Observed behavior matched the uniform-state expectation:

- requested and actual opening coincide at `0.5`
- valve pressure difference remains zero
- raw Kv Q, applied Q, and flux-derived Q remain zero
- the Mach cap remains inactive
- all four probes show no material pressure or velocity disturbance
- mass, energy, and vapor-mass flux mismatches remain on the zero line
- momentum-flux difference matches the zero pressure difference
- flux-derived Q minus applied Q remains zero
- the budget/health summary reports software observation pass `True`

The numerical observation revealed no solver-physics or conservation blocker.
Two readability issues were identified in the first plots:

1. the large positive Q limit shared an axis with zero through-flow and visually
   compressed the quantities of interest;
2. exact-zero normalized residuals were drawn at an artificial `1e-30` log-scale
   floor without explicit zero labels.

A readability-only plotter revision was committed. It separates through-flow
from the Q-limit / cap-state panel and labels exact-zero ratios explicitly at a
visualization floor. This revision does not rerun the solver or change any
numerical result.

PR #35 remains draft until the refined plotter is pulled, the four PNGs are
regenerated from the existing CSV/JSON artifacts, and the plot-focused plus full
Windows suites pass on the refined head.
