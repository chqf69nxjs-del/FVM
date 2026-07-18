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
- fixed-pressure ends are zero-impedance numerical idealizations
- the hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`

## 2026-07-15 — Specification-first start

Starting point:

- V-011 was `COMPLETE`
- main full Windows suite passed (`223 passed`)
- the repository already contained `KvLiquidValve`, `LinearRampOpening`, and
  `InternalValveInterface`
- no V-012 operation runner was present

Case sequence fixed by the specification:

1. V-012A uniform-state constant-opening preservation
2. V-012B small driven-flow constant-opening baseline
3. V-012C controlled opening ramp
4. V-012D controlled closing ramp through complete closure and post-closure review
5. mesh/CFL, CI-light, formal report, and manifest

Stop rules:

- stop if a solver-physics, governing-equation, Kv-law, Mach-cap, boundary-meaning,
  or conserved-energy change is required
- stop on non-finite or non-positive state
- stop on unexpected phase appearance
- stop if required budget fields are missing
- stop if actual two-sided interface fluxes cannot be recorded
- stop if regression bands would need to be selected before observation evidence

PR #34 merged the implementation-ready specification at
`6f4bc16c38361b0fffec3267766224aff0160a90`.

## 2026-07-15 — V-012A telemetry and uniform baseline

PR #35 implemented:

- raw Kv target flow telemetry
- Mach-limited applied flow and flow limit
- cap activation state
- hydraulic-separation state
- flow direction and upwind state
- exact two-sided interface flux evaluation used by the solver update
- a uniform single-phase CoolProp baseline
- four human-review plots generated from saved artifacts

The telemetry path and solver update share the same evaluated interface flux; no
second reconstructed diagnostic flux is used.

V-012A problem:

```text
pressure difference: 0 Pa
opening:             0.5 constant
temperature:         280 K
initial velocity:    0 m/s
```

Observed result:

- requested and actual opening coincided
- raw Kv Q, applied Q, and flux-derived Q remained zero
- Mach cap remained inactive
- zero-flow hydraulic separation remained active
- all probes showed no material pressure or velocity disturbance
- mass, energy, vapor-mass, and momentum-difference residuals were zero
- the case remained finite, positive, and single phase
- software observation pass: `True`
- plot-focused tests: `3 passed in 3.57s`
- full repository suite: `234 passed in 76.82s`

A temporary Windows application-control event blocked a CoolProp native module.
The branch was safely preserved. A Windows update and restart restored the same
virtual environment without disabling or bypassing security controls.

PR #35 merged at `128596593ae99e61289475cb79a39ec2127f72aa`.

## 2026-07-16 — V-012B small driven-flow constant opening

PR #36 implemented a small left-to-right driven-flow observation:

```text
left pressure:       8,000,500 Pa
right pressure:      7,999,500 Pa
temperature:         280 K
opening:             0.5 constant
mesh / CFL:          n=100 / 0.5
initial velocity:    0 m/s
```

The two pipe segments were initialized from separate consistent CoolProp `(p,T)`
states. The evaluation ended before a valve-generated wave reached either fixed-
pressure end.

Observed result:

- initial raw Kv Q: `3.534291735286872e-05 m3/s`
- initial applied Q: `3.534291735286872e-05 m3/s`
- initial flux-derived Q: `3.534291735286872e-05 m3/s`
- flow-sign consistency: `72 / 72 = 1.0`
- Mach-cap activation count: `0`
- hydraulic-separation count: `0`
- maximum applied face Mach: `8.969569363202504e-07`
- maximum pressure perturbation: `199.445663 Pa`
- maximum velocity: `3.876598270354068e-04 m/s`
- interface mass, energy, vapor-mass, and momentum-difference residuals: `0`
- maximum flux-Q minus applied-Q: `3.3881317890172014e-21 m3/s`
- energy budget relative residual: `-1.7941570435960072e-16`
- remained single phase: `True`
- full repository suite: `239 passed in 69.97s`

Human review showed the expected upstream decompression, downstream compression,
positive flow, and acoustic-scale relation `rho*c*u ≈ delta-p`.

PR #36 merged at `8cb3deee003b141c0cb8e8d56ccc3eaa77c01d8f`.

## 2026-07-16 — V-012C controlled opening ramp

PR #37 implements the primary opening operation:

```text
opening:       0.0 -> 1.0
initial hold:  0.005 s
ramp duration: 0.010 s
ramp end:      0.015 s
```

The V-012B pipe, thermodynamic state, Kv calibration, and fixed-pressure numerical
boundaries are retained.

Added numerical artifacts:

- config and metrics JSON
- valve schedule and valve history CSV
- exact two-sided interface-flux history CSV
- probe history and characteristic-summary CSV
- boundary and final-profile CSV
- full pressure / velocity / temperature / density field-history NPZ
- observation report Markdown

Added nine human-review figures:

1. valve command and flow
2. probe pressure and velocity
3. probe `A_plus / A_minus`
4. pressure x-t map
5. velocity x-t map
6. interface-flux consistency
7. budget and consistency summary
8. representative field profiles
9. pressure-difference / flow path

Windows execution evidence:

```text
focused tests:        6 passed in 4.27s
full repository:      245 passed in 72.53s
working tree:         clean
plot count:           9
overall observation:  True
```

Key numerical results:

- opening monotonic non-decreasing: `True`
- maximum opening error: `0`
- zero-opening hydraulic-separation fraction: `1.0`
- finite-opening hydraulic-separation count: `0`
- initial applied Q: `0 m3/s`
- final applied Q: `4.3125747224746e-05 m3/s`
- maximum raw/applied relative difference: `0`
- maximum applied/flux relative difference: `1.9174770433785486e-16`
- flow-sign consistency: `78 / 78 = 1.0`
- Mach-cap activation count: `0`
- maximum applied face Mach: `1.0944969604068111e-06`
- primary characteristic direction pass: `True`
- maximum opposite-direction characteristic ratio: `1.6229101813567113e-06`
- upstream decompression observed: `True`
- downstream compression observed: `True`
- maximum pressure perturbation: `313.8912506327033 Pa`
- maximum velocity: `6.101059874685836e-04 m/s`
- interface mass, energy, vapor-mass, and momentum-difference residuals: `0`
- maximum flux-Q minus applied-Q: `6.776263578034403e-21 m3/s`
- mass budget relative residual: `-1.394135662426362e-16`
- energy and vapor-mass budget relative residuals: `0`
- remained single phase: `True`
- target time: `0.0697143731 s`
- first valve-generated boundary arrival: `0.0946929534 s`

Visual review:

- requested and actual openings coincide through hold, ramp, and full-open period
- raw Kv, applied, and flux-derived Q remain coincident
- upstream probes are dominated by negative left-going `A_minus`
- downstream probes are dominated by positive right-going `A_plus`
- near probes respond before far probes
- pressure and velocity x-t fronts follow the theoretical ramp-start and ramp-end
  acoustic lines
- no growing oscillation, checkerboard pattern, isolated non-valve spike, or
  premature boundary-return signature was observed
- field profiles remain smooth at the resolved scale
- the delta-p/Q path is smooth and contains only a bounded acoustic-adjustment loop

Presentation limitation:

- the delta-p/Q `ramp start` marker uses the nearest stored sample and therefore
  displays opening `0.038` rather than the exact prescribed `0.0` at `0.005 s`
- this affects only the label, not the schedule, solver, metrics, or acceptance

Current decision:

- no critical numerical, conservation, sign, timing, phase-state, or data-integrity
  blocker was found
- no solver-physics or regression-band change occurred
- PR #37 was merged at `f933479658d61b30d2214a2ceb9cd64d0efa671a`
- V-012 remains `IN_PROGRESS`
- V-012D controlled closing ramp is the next implementation increment

## 2026-07-16 — V-012D controlled closing ramp through complete closure

PR #38 implements the primary closing operation without splitting complete closure
into a separate verification item:

```text
opening:           1.0 -> 0.0
initial hold:      0.005 s
ramp duration:     0.010 s
post-closure hold: 0.005 s
```

Complete closure uses the existing `InternalValveInterface` zero-opening branch,
which supplies two independent reflective-wall fluxes. The finite-opening and
post-closure states are evaluated separately:

- finite opening: Kv-law tracking, applied-flow/flux consistency, common mass /
  energy / vapor-mass flux, and documented momentum-flux difference
- complete closure: hydraulic separation, no flow direction, zero mass / energy /
  vapor-mass through-flux, and independent side-specific wall reactions

GitHub Actions evidence:

```text
focused tests:        7 passed in 7.53s
full repository:      252 passed in 106.74s
static checks:        success
baseline metrics gate: success
nine review plots:    generated
V-012D overall pass:  True
```

Baseline configuration and timing:

- left/right pressure: `8,000,500 / 7,999,500 Pa`
- temperature: `280 K`
- mesh / CFL: `n=100 / 0.5`
- target time: `0.06971437311556053 s`
- first initial-state boundary arrival: `0.08969295335583746 s`
- accepted window precedes boundary contamination

Schedule and flow:

- opening monotonic non-increasing: `True`
- maximum opening error: `0`
- initial / maximum applied Q: `7.068583469428279e-05 m3/s`
- final applied Q: `0 m3/s`
- finite-opening raw/applied relative difference: `0`
- finite-opening applied/flux relative difference: `1.8702192872045635e-16`
- flow-sign consistency: `1.0`
- Mach-cap activation count: `0`
- maximum applied face Mach: `1.7939138723497895e-06`

Complete-closure observation:

- post-closure sample count: `61`
- hydraulic-separation fraction: `1.0`
- no-flow-direction fraction: `1.0`
- maximum raw / applied Q: `0 / 0 m3/s`
- maximum flux-derived Q: `4.151910405935732e-24 m3/s`
- maximum mass through-flux: `5.421010862427522e-20 kg/m2/s`
- maximum energy through-flux: `0 W/m2`
- maximum vapor-mass through-flux: `0 kg/m2/s`
- each through quantity remained below its numerical roundoff tolerance
- finite-opening momentum relation was not applied to closed rows

Interface, budgets, and state:

- maximum mass-flux mismatch: `5.421010862427522e-20 kg/m2/s`
- maximum energy / vapor-mass mismatch: `0 / 0`
- maximum flux-Q minus applied-Q: `6.776263578034403e-21 m3/s`
- mass / energy / vapor-mass budget relative residual: `0 / 0 / 0`
- required budget fields missing: none
- remained single phase: `True`
- pressure, temperature, density, and sound speed remained positive

Wave observation:

- upstream compression observed: `True`
- downstream decompression observed: `True`
- primary characteristic-direction pass: `True`
- maximum opposite-direction characteristic ratio: `1.2305912228546978e-06`

The characteristic comparison is rebased to each probe's pre-arrival state so the
closure-generated increment is separated from the initial full-open startup wave.
Human review of all nine figures found the expected directions and timing, smooth
flow decay, stable complete closure, and no early external-boundary return.

Numerical decision:

- the finite-opening relative-flow gate excludes complete-closure rows because a
  relative ratio at numerical zero is ill-conditioned
- complete closure is instead protected by explicit absolute Q and through-flux
  tolerances
- this is a scope correction, not a relaxed acceptance threshold
- no solver physics or energy treatment changed
- PR #38 is `OBSERVED; READY FOR REVIEW`
- V-012 remains `IN_PROGRESS`; mesh/CFL observation, CI-light, formal report, and
  SHA256 manifest remain

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
