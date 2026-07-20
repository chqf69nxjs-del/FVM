# Stage 7 — Pure-CO2 HEM Explicit Phase Classification Plan

## Status

`IN_PROGRESS; STACKED ON PR #54; NOT SOLVER CONNECTED`

This increment separates equilibrium phase/property evaluation from acoustic closure.
It is based on PR #54 head `39a394698383879225216aee403c1221fe454e0e` and does not depend on the MUSCL/TVD line.

## Objective

Before a real-fluid HEM state can enter the production FVM, the code must distinguish:

- ordinary compressed/subcooled liquid;
- liquid-vapor two-phase states;
- ordinary single-phase vapor;
- supercritical states;
- critical-region states;
- solid or below-triple-temperature states;
- unknown backend classifications.

Quality alone is not sufficient for this classification. This increment therefore uses explicit CoolProp `PhaseSI` information.

## Core design

The new phase-state path accepts `rho/e` and obtains only:

```text
p
T
raw phase
quality where defined
void fraction where defined
phase class
scope status
```

It deliberately does not request sound speed. The output fixes:

```text
sound_speed_evaluated = false
equilibrium_two_phase_sound_speed_closure_approved = false
```

This allows the real-fluid liquid/two-phase/vapor property path to be reviewed independently from the later acoustic closure used by Rusanov flux and CFL.

## Current supported-candidate scope

```text
compressed_or_subcooled_liquid
liquid_vapor_two_phase
single_phase_vapor
```

The following are guarded out of the first liquid-vapor HEM solver connection:

```text
supercritical
critical_region
solid_or_below_triple_guard
```

Unknown backend classifications remain explicit `unknown`; they are not silently mapped to liquid or vapor.

## Quality and void-fraction policy

- ordinary liquid: `q=0`, `alpha=0`;
- ordinary vapor: `q=1`, `alpha=1`;
- explicit two-phase: obtain `Q` from CoolProp and compute `alpha` from saturated liquid/vapor densities;
- supercritical, critical, solid-guarded, and unknown states: quality and alpha are undefined (`NaN` internally, `null` in JSON).

This avoids presenting an artificial quality for states where vapor quality has no thermodynamic meaning.

## Guard policy

Critical constants and triple temperature are queried from CoolProp.

A critical guard box is applied around `(Tcrit, Pcrit)` using configurable margins. Any state below or at the triple temperature is outside the liquid-vapor-only scope. These guards are software scope guards, not validated physical phase-boundary tolerances.

## Representative phase map

The installed-CoolProp evidence uses nine fixed states:

```text
8 MPa / 280 K compressed liquid
5 MPa / 280 K liquid
2 MPa saturated liquid
2 MPa q=0.10
2 MPa q=0.50
2 MPa q=0.90
2 MPa saturated vapor
1 MPa / 280 K superheated vapor
8 MPa / 310 K supercritical
```

The map emits JSON, CSV and Markdown evidence. No sound-speed query is made by the phase-map path.

## Tests

The focused tests cover:

- phase-label normalization;
- configuration validation;
- liquid/two-phase/gas/supercritical/critical/solid/unknown classification;
- below-triple guard priority;
- critical-box guard priority;
- input immutability;
- two-phase quality and void fraction;
- undefined quality for supercritical states;
- representative-map inventory;
- false production, sound-speed, Validation and design-use flags.

## Deliberately excluded

This increment does not:

- modify `FvmSolver`;
- modify numerical flux or CFL;
- define equilibrium two-phase sound speed;
- modify `LCO2PropertyEOSAdapter`;
- modify HEM/HNE phase-change operators;
- add a 1-D HEM case;
- validate critical or solid thermodynamics;
- support supercritical states in the first liquid-vapor HEM solver path;
- claim physical Validation or design-use acceptance.

## Completion boundary

The increment is review-ready when:

- installed-CoolProp focused tests run without skips;
- the representative nine-state map is generated;
- no phase-map code requests sound speed;
- full repository tests pass;
- permanent workflows remain green;
- temporary validation workflow is removed;
- final diff contains only permanent source, tests and documentation.

## Next gate

After explicit phase classification is accepted, define and independently verify the equilibrium two-phase sound-speed closure. Only after both phase classification and acoustic closure are reviewed should a first-order uniform HEM state be connected to `FvmSolver`.
