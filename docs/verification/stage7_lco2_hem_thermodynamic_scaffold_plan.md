# Stage 7 — Pure-CO2 HEM Thermodynamic Scaffold and 0-D Flash Plan

## 1. Status

`IN_PROGRESS; THERMODYNAMIC SCAFFOLD; NOT SOLVER CONNECTED`

This increment begins the project line that leads from the established first-order FVM
baseline toward a pure-CO2 liquid/vapor homogeneous-equilibrium model (HEM).

The branch starts from merged PR #51 at:

```text
62390bd526ae99b6702f4ed76e3594e1bf01259b
```

Open MUSCL/TVD PRs #52 and #53 are intentionally not dependencies of this work. Higher-order
transport remains a later numerical-improvement option after the two-phase thermodynamic
closure and first-order HEM path are established.

## 2. Project objective

The wider project objective remains a one-dimensional conservative transient code for LCO2
pipeline reliability studies, including depressurization, flashing, liquid-vapor formation,
pressure/temperature histories, vapor quality, and void fraction.

The first practical physical-model target is:

```text
pure CO2
one-dimensional homogeneous mixture
liquid / vapor / liquid-vapor equilibrium states
conservative mass, momentum, and total-energy transport
instantaneous local thermodynamic equilibrium (HEM)
```

This increment does not yet solve that full target. It establishes a small and reviewable
thermodynamic validation layer before changing `FvmSolver` or the EOS adapter.

## 3. Scope of this increment

The increment adds a solver-independent module that:

1. accepts density `rho` and mass-specific internal energy `e`;
2. calls the existing `RealFluidPropertyBackend.state_from_rho_e` contract;
3. validates pressure, temperature, quality, void fraction, and backend-reported sound speed;
4. does not require internal energy to be positive, because real-fluid energy reference
   states may shift the absolute value;
5. classifies the quality regime as:
   - `liquid_endpoint`;
   - `two_phase`;
   - `vapor_endpoint`;
6. wraps backend errors with backend-name context;
7. guarantees that caller input arrays are not changed or aliased;
8. generates a deterministic dependency-free surrogate 0-D path;
9. emits JSON, CSV, Markdown, and NPZ evidence with explicit false approval flags.

The 0-D path includes one compressed-liquid point, a saturated-mixture quality path, and
one expanded-vapor point. It is a software/thermodynamic-path exercise using
`surrogate_lco2`; it is not a design-quality CO2 property result.

## 4. Important terminology boundary

The current classification is deliberately a **quality-regime classification**. It is not
a complete thermodynamic phase classifier.

In particular, this increment does not yet distinguish all of:

```text
compressed liquid
subcooled liquid
saturated liquid
liquid-vapor mixture
saturated vapor
superheated vapor
supercritical liquid-like state
supercritical gas-like state
critical region
solid-containing state
```

A later CoolProp-backed phase-map increment must use explicit backend phase information and
must define critical- and solid-region guards before those labels are used in solver logic.

## 5. Sound-speed boundary

The existing property backend contract returns a field named `c`. Its meaning is backend
specific. For the surrogate backend it is a development-only diagnostic mixture sound-speed
model. For CoolProp single-phase states it is the backend speed-of-sound result.

This increment records that field as:

```text
backend_reported_sound_speed
```

It does **not** approve it as the equilibrium liquid-vapor HEM acoustic closure.

The evidence therefore fixes:

```text
equilibrium_two_phase_sound_speed_closure_approved = false
backend_reported_sound_speed_is_diagnostic_only = true
```

Before `FvmSolver` is connected to real-fluid HEM states, a separate increment must define
and verify the equilibrium sound-speed closure used in the CFL condition and numerical
flux.

## 6. EOS-aware state validation

The common conservative-state helper currently treats negative internal energy as invalid.
That rule is useful for the simple verification EOS models, but it is not a universal
real-fluid rule because absolute internal energy depends on the property reference state.

The scaffold therefore uses the following checks for a backend `rho/e` result:

```text
rho is finite and > 0
internal energy is finite
backend returns the same rho/e pair requested
p, T, quality, alpha, and reported c are finite
p > configured minimum
T > configured minimum
reported c > configured minimum
quality lies in [0, 1] within tolerance
alpha lies in [0, 1] within tolerance
```

It does not change `state.check_physical_state` in this increment. The production solver's
EOS-aware validation policy remains a separate design gate.

## 7. Pure invariants and tests

The focused tests cover:

- invalid validation settings;
- quality endpoint/open-interval classification;
- rejection of non-finite and out-of-range quality;
- acceptance of finite negative reference-state internal energy;
- backend error wrapping with traceable backend name;
- early rejection of non-positive density;
- rejection of invalid backend quality;
- liquid/two-phase/vapor coverage of the surrogate 0-D path;
- monotonic quality and void fraction along the fixed path;
- positive finite pressure, temperature, and reported sound speed;
- no input mutation or output aliasing;
- deterministic four-format artifact output;
- false production, Validation, design-use, sound-speed-approval, and accuracy-band flags.

## 8. Deliberately excluded

This increment does not:

- modify `FvmSolver`;
- modify the Rusanov flux;
- change `LCO2PropertyEOSAdapter` behavior;
- change `HEMPhaseChange` or `HNERelaxationPhaseChange`;
- perform a CoolProp two-phase map;
- approve a two-phase sound-speed model;
- introduce a phase-boundary Riemann problem;
- add pipe depressurization or discharge boundaries;
- add wall heat transfer or friction;
- add HNE relaxation parameters;
- support impurities or solid CO2;
- connect MUSCL/TVD to production;
- claim physical Validation or design-use acceptance.

## 9. Next technical increments

After this scaffold is reviewed, the recommended sequence is:

1. expose explicit backend phase classification for safe representative `rho/e` states;
2. separate CoolProp equilibrium `p/T/Q/phase` evaluation from sound-speed evaluation so
   liquid-vapor states can be mapped without relying on an undefined single-phase `A` call;
3. define and verify an equilibrium two-phase sound-speed closure;
4. generate a CoolProp pure-CO2 0-D property/phase map away from the critical and solid
   regions;
5. connect the reviewed HEM closure to a uniform-state, first-order FVM preservation case;
6. add a one-dimensional expansion problem crossing from liquid into the two-phase region;
7. only then build the first LCO2 pipeline depressurization prototype;
8. retain MUSCL/TVD as a later comparison option after the first-order HEM baseline exists.

## 10. Completion boundary

This scaffold is complete for review when:

- focused tests pass;
- the dependency-free 0-D artifact set is generated and checked;
- the full repository suite remains green;
- committed-diff and tracked-file checks are clean;
- permanent GitHub Actions remain green;
- no production solver, flux, EOS-adapter, phase-change, boundary, or source behavior changes.

Completion of this scaffold does not mean that the pure-CO2 HEM thermodynamic core, the
HEM sound-speed closure, or the LCO2 pipeline two-phase prototype is complete.
