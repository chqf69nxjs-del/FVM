# Stage 7 — Minimal LCO2 Pipeline-Depressurization Prototype Specification

## Status

`SPECIFICATION ONLY; IMPLEMENTATION NOT STARTED; VERIFICATION ONLY; REVIEW REQUIRED`

This specification defines the first narrow pipeline-depressurization prototype after the
frozen first-order liquid-to-open-two-phase Case A/B pair in PR #72 and its central-record
synchronization in PR #73.

The objective is deliberately limited:

> Start from a uniform stationary liquid-CO2 pipe, lower the prescribed thermodynamic state
> at the right boundary, observe the resulting depressurization wave, and stop immediately
> after the first accepted liquid-to-open-two-phase crossing.

The authoritative machine-readable contract is:

- [`stage7_lco2_hem_pipeline_depressurization_prototype_contract_v1.json`](stage7_lco2_hem_pipeline_depressurization_prototype_contract_v1.json)

This increment does not implement the boundary or run the prototype.

---

## 1. Why a new prototype is needed

The frozen PR #72 pair verifies a real first-order FVM crossing from an initial interior
pressure discontinuity:

```text
Case A: 5 MPa / 5 K subcooling -> 2 MPa / 5 K subcooling
Case B: 5 MPa / 5 K subcooling -> 4 MPa / 5 K subcooling
```

That pair is now the software regression control. It proves the reviewed chain:

```text
accepted liquid state
-> Rusanov/CFL conservative update
-> raw liquid-to-open-two-phase crossing
-> equilibrium-quality projection
-> mixed accepted-state EOS recovery
-> second-projection no-op
-> boundary and phase-vapor budget closure
```

It does not yet represent a pipe that begins uniformly liquid and is depressurized from an
end boundary. The next physical-model increment must therefore replace the interior initial
discontinuity with a controlled boundary schedule while leaving the reviewed FVM, EOS,
phase classifier, projection, and budget algorithms unchanged.

---

## 2. Central modeling decision

### 2.1 Pressure alone does not define a real-fluid boundary state

The generic `PressureTankBoundary` obtains ghost density from
`eos.density_from_pressure(p)`. That is sufficient only when an EOS provides a reviewed
single-valued inversion.

For real CO2, pressure alone does not uniquely determine:

```text
density rho
internal energy e
temperature T
phase
quality q
```

The current `VerificationHEMLiquidOpenTwoPhaseEOS` therefore intentionally raises
`NotImplementedError` for `density_from_pressure`.

The first prototype shall not add an arbitrary pressure-only inversion to that EOS.

### 2.2 Selected closure: pressure plus positive subcooling

The right-boundary thermodynamic state shall be closed by:

```text
prescribed pressure p_b(t)
constant positive subcooling DeltaT_sub,b
```

with

```text
T_b(t) = T_sat(p_b(t)) - DeltaT_sub,b
```

The corresponding boundary density and internal energy are evaluated from the direct
CoolProp `P,T` state:

```text
rho_b(t) = rho_CO2(p_b(t), T_b(t))
e_b(t)   = e_CO2(p_b(t), T_b(t))
```

The resulting `(rho_b,e_b)` state is then re-evaluated through the reviewed canonical
`rho/e` phase and equilibrium-acoustic paths. The boundary state is accepted only when it
is a supported `LIQUID_CANDIDATE` with equilibrium quality exactly zero under the existing
quality contract.

This closure is a prescribed verification boundary. It is not a coupled tank model and
must not be interpreted as one.

---

## 3. Fixed minimum geometry and numerics

```text
pipe:                  one horizontal straight pipe
length:                1.0 m
diameter:              0.10 m
cells:                 32
dx:                    0.03125 m
left boundary:         reflective closed end
right boundary:        verification-only prescribed subcooled outlet
spatial order:         first order
numerical flux:        existing Rusanov
CFL limit:             0.10
ghost cells:           2
initial velocity:      0 m/s
physical source:       none
friction:              none
wall heat transfer:    none
gravity:               none
internal interfaces:   none
```

The 32-cell mesh is a verification starting point. It is not a mesh-converged or approved
accuracy level.

The production solver, numerical flux, CFL calculation, phase classifier, sound-speed
estimator, quality projection, and accepted-state EOS shall not be modified to make the
prototype pass.

---

## 4. Initial state

Every internal cell starts from the same prescribed liquid state:

```text
fluid:                 pure CO2
pressure:              5 MPa
subcooling:            5 K
T0:                    T_sat(5 MPa) - 5 K
velocity:              0 m/s
transported quality:   q = 0 exactly
required region:       LIQUID_CANDIDATE
```

The state is constructed through the same pressure/subcooling -> `rho/e` path already used
by the PR #68 liquid-state survey.

At `t=0`, the right-boundary pressure and subcooling are identical to the internal state.
Therefore the prototype begins without an artificial thermodynamic discontinuity at the
outlet face.

---

## 5. Right-boundary contract

The planned boundary adapter is named conceptually:

```text
VerificationHEMPrescribedSubcooledOutletBoundary
```

The exact class name may be adjusted during implementation, but its contract may not be
weakened.

### 5.1 Flow policy

```text
side:                 right
flow direction:       outlet_only
allowed direction:    pipe -> prescribed exterior state
reverse-flow action:  reflective fallback and explicit diagnostic count
```

A successful prototype run requires zero reverse-flow fallbacks. A fallback is a guarded
outcome, not a hidden correction.

### 5.2 Velocity policy

The ghost velocity shall copy the adjacent interior velocity.

This avoids adding an independent velocity jump while the pressure/thermodynamic schedule
provides the intended driving condition. No valve, orifice, discharge coefficient, or
choked-flow law is introduced.

### 5.3 Quality policy

The boundary quality shall be the equilibrium quality of the prescribed `(rho_b,e_b)`
state. For the first prototype path it must be zero.

Copying the interior transported quality into the ghost state is forbidden. Once the
rightmost interior cell becomes two phase, copying its positive quality into a prescribed
subcooled-liquid ghost would create a transported/equilibrium mismatch and would violate
the strict mixed accepted-state EOS contract.

### 5.4 Runtime state checks

Each new scheduled boundary state shall satisfy:

```text
rho finite and positive
e finite and non-negative
p finite and positive
T finite and positive
sound speed finite and positive
boundary region = LIQUID_CANDIDATE
q_eq = 0 under the existing endpoint contract
mixed accepted-state EOS accepts the ghost state
recovered p and T agree with the schedule within the contract tolerances
```

No clipping of quality, density, energy, pressure, or temperature is permitted.

---

## 6. Pressure schedule and initial fixed matrix

The pressure schedule is linear:

```text
p_b(0) = 5 MPa
p_b(t_ramp) = p_final
```

There is no initial hold because the boundary and pipe state already match at `t=0`.

The ramp time is defined from the uniform initial acoustic state:

```text
t_acoustic,0 = L / c_initial
t_ramp       = 1.0 * t_acoustic,0
```

The maximum observation horizon is:

```text
t_max = t_ramp + 2 * t_acoustic,0
      = 3 * t_acoustic,0
```

The runner also has a hard maximum of 2000 steps.

### Fixed case matrix

| case | role | final boundary pressure | boundary subcooling | ramp time |
|---|---|---:|---:|---:|
| `pipeline_crossing_candidate_p5m5_to_p2m5` | first crossing candidate | 2 MPa | 5 K | `1.0 t_acoustic,0` |
| `pipeline_moderate_diagnostic_p5m5_to_p3m5` | intermediate diagnostic | 3 MPa | 5 K | `1.0 t_acoustic,0` |
| `pipeline_liquid_control_p5m5_to_p4m5` | liquid negative control | 4 MPa | 5 K | `1.0 t_acoustic,0` |

All cases use identical geometry, mesh, CFL, boundary policies, EOS, projection, and
acceptance thresholds. Only the final pressure changes.

If the 2 MPa candidate does not cross within the fixed horizon, the implementation PR must
record `NO_CROSSING_WITHIN_HORIZON`. It must not change ramp time, pressure, algorithms, or
tolerances in that same increment to manufacture a crossing.

---

## 7. Mandatory boundary-path preflight

Before any FVM time step, each pressure schedule is sampled at 65 points including both
endpoints.

At every point:

1. compute `T_sat(p)` and subtract 5 K;
2. obtain `rho` and `e` from the direct CoolProp `P,T` state;
3. re-evaluate the exact `(rho,e)` through the reviewed phase classifier;
4. derive the boundary region;
5. evaluate the existing equilibrium sound-speed candidate;
6. construct a conservative ghost state with equilibrium quality;
7. require the mixed accepted-state EOS to accept that state;
8. recover pressure and temperature and compare them with the scheduled values.

Every sample must remain a `LIQUID_CANDIDATE`. Endpoint, open-two-phase, vapor, critical,
solid/below-triple, unknown, negative-energy, non-finite, or acoustically invalid samples
reject the entire schedule before the FVM run starts.

The preflight is not evidence that the pipe solution remains liquid. It only establishes
that the prescribed exterior boundary path is internally valid and does not inject an
unsupported state.

---

## 8. Per-step calculation sequence

The prototype runner shall orchestrate the existing components explicitly:

```text
accepted state U^n
    |
    v
1. accepted-state EOS -> p, T, c
    |
    v
2. CFL -> dt
    |
    v
3. apply reflective left and prescribed subcooled right ghost states
    |
    v
4. existing Rusanov boundary/interior fluxes
    |
    v
5. conservative FVM update -> raw U^(n+1,*)
    |
    v
6. direct raw rho/e phase-region and transition detection
    |
    v
7. stop immediately on endpoint, forbidden, guard, backend, or reverse-flow event
    |
    v
8. existing HEMEquilibriumQualityProjection
    |
    v
9. require crossing cells = projection cells when a first crossing occurs
    |
    v
10. existing mixed accepted-state EOS recovery
    |
    v
11. fresh second projection must be a no-op
    |
    v
12. update boundary and phase-vapor budgets
    |
    v
13. stop on first accepted crossing, otherwise continue
```

The runner may manually orchestrate the split path as the PR #70–#72 verification runners
do. A production `FvmSolver` redesign is outside this gate.

---

## 9. Event classification and stop priority

Possible outcomes are:

```text
ACCEPTED_FIRST_CROSSING
NO_CROSSING_WITHIN_HORIZON
ENDPOINT_LANDING
FORBIDDEN_TRANSITION
REVERSE_FLOW_GUARD
GUARD_FAILURE
BACKEND_FAILURE
```

When multiple events appear in the same step, the stop priority is:

```text
BACKEND_FAILURE
GUARD_FAILURE
REVERSE_FLOW_GUARD
FORBIDDEN_TRANSITION
ENDPOINT_LANDING
ACCEPTED_FIRST_CROSSING
NO_CROSSING_WITHIN_HORIZON
```

Therefore a step containing both an open-two-phase crossing and an endpoint or forbidden
transition is not a successful crossing step.

---

## 10. Accepted first-crossing criteria

A case may be labeled `ACCEPTED_FIRST_CROSSING` only when all applicable checks pass:

```text
initial all cells are LIQUID_CANDIDATE
boundary path preflight passed
reverse-flow fallback count = 0
at least one LIQUID_TO_TWO_PHASE_CROSSING exists
endpoint count = 0
forbidden transition count = 0
crossing cells = first-projection cells
at least one crossing q_eq >= 1e-6
post q matches q_eq within 1e-12
post mixed accepted-state EOS accepts every cell
post p, T, and c are finite and positive
second projection modifies zero cells
projection vapor source is counted exactly once
boundary and phase-vapor budgets close
```

The `1e-6` quality threshold is retained as evidence strength only. It is not a solver,
phase, projection, or boundary switch.

For this first gate, a crossing in the rightmost internal cell is allowed. The result proves
only a first accepted boundary-driven crossing. It does not prove a front-propagation speed
or a mesh-independent interface location.

---

## 11. Pressure-wave evidence

The runner shall record, but not use as a solver switch:

```text
pressure profile by step
first time each cell exceeds a 1e-6 relative pressure drop from its initial pressure
boundary pressure and thermodynamic state by step
crossing distance from the right boundary
```

The threshold is evidence-only. No pressure-wave speed acceptance band is approved in this
prototype.

A later propagation gate may use these records to define and verify a moving liquid/two-
phase front. The present prototype stops at the first accepted crossing.

---

## 12. Budget contract

### 12.1 Conservative boundary budgets

With no physical source, friction, heat transfer, gravity, or internal interface:

```text
inventory change = left boundary contribution - right boundary contribution + residual
```

The left reflective boundary must have zero mass and energy flux.

The right boundary may legitimately remove mass, momentum, energy, and vapor inventory.
The actual Rusanov numerical face flux is the authoritative boundary contribution.

### 12.2 Vapor budget

The vapor inventory is decomposed as:

```text
post vapor inventory
=
initial vapor inventory
+ cumulative boundary vapor contribution
+ cumulative equilibrium-projection vapor source
+ residual
```

Boundary vapor transport and internal phase-change source must remain separate. The same
vapor mass may not be counted twice.

### 12.3 Fixed tolerances

```text
mass:       max(1e-12 kg, 1e-10 relative)
momentum:   max(1e-10 kg m/s, 1e-10 relative)
energy:     max(1e-6 J, 1e-10 relative)
vapor:      1e-12 kg absolute
phase vapor 1e-12 kg absolute
combined:   1e-12 kg absolute
```

These are software-verification tolerances, not physical accuracy claims.

---

## 13. Frozen Case A/B regression requirement

The PR #72 pair remains the first-order HEM regression control.

Before and after each prototype implementation increment, require the retained signatures:

```text
Case A final state SHA256:
78897b5c8ca57221186ccf3e0aa69e1492a942cc2e8dee0abb440a3e2e08e039

Case A signature:
914ed2249c9546a1d32f6d6dbcd8b30236e1c1f2b37ecf9306100ad30622b612

Case B final state SHA256:
8c09735ee9185cfb34b2186be30b32d78ec73350e211762d92c372e0b9f23a59

Case B signature:
3bd7edc37842a00a0c27964a17029f5c66ef973b59bd7670f513c82fc7e85669
```

A changed signature requires explicit review. It may not be silently rebaselined as part of
the depressurization prototype.

---

## 14. Required artifacts

The eventual runner shall write:

```text
JSON summary
case CSV
step CSV
cell CSV
boundary-path preflight CSV
Markdown evidence
NPZ arrays
```

Minimum retained evidence includes:

```text
resolved initial acoustic time
resolved ramp duration
scheduled and recovered boundary p/T/rho/e/q
boundary region and sound speed
reverse-flow fallback count
pressure-wave threshold arrival time by cell
raw regions and events by step
projection cells and delta q by step
first crossing step/time/cells/distance from outlet
post quality mismatch
second projection count
boundary budgets
phase-vapor budget
combined vapor budget
failure reason
```

---

## 15. Implementation staging

### Increment 1 — boundary adapter and path preflight

Required scope:

```text
prescribed pressure-plus-subcooling state provider
outlet-only boundary adapter
equilibrium-quality ghost construction
65-point path preflight
ghost accepted-state EOS check
reverse-flow fallback diagnostics
dependency-free contract tests
installed-CoolProp boundary tests
```

No FVM time step is required in this increment.

### Increment 2 — short first-crossing runner

Required scope:

```text
fixed 2/3/4 MPa case matrix
short first-order FVM time evolution
first crossing stop
pressure-wave evidence
projection and post-EOS chain
boundary and phase budgets
frozen Case A/B regressions
```

The two increments shall remain separate so a boundary-construction failure cannot be
confused with a transient-solver failure.

---

## 16. Explicit exclusions

The prototype does not include:

```text
friction
wall heat transfer
gravity
valve or orifice law
discharge coefficient
choked flow
tank mass/energy evolution
slip or drift flux
nucleation delay
metastable liquid
HNE
open-two-phase to vapor crossing
endpoint acoustic closure
reverse-transition handling
MUSCL/TVD
mesh convergence
long-pipeline scaling
experimental comparison
physical Validation
design use
```

---

## 17. Approval boundary

```text
verification_only = true
software_verification_only = true
pipeline_depressurization_executed = false
interface_propagation_speed_verified = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```

---

## 18. Review decision requested

Approval of this specification means only:

> The first boundary-driven LCO2 depressurization prototype may be implemented in two
> narrow verification increments using this fixed boundary closure, geometry, numerical
> matrix, stop rules, budgets, and approval boundary.

It does not approve a physical tank boundary, a release model, a design calculation, a
production HEM model, or an acoustic accuracy band.
