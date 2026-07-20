# Stage 7 — Pure-CO2 HEM Explicit Phase Classification

## Status

`VALIDATED STACKED DRAFT PR #55; NOT SOLVER CONNECTED`

This increment separates equilibrium phase/property evaluation from acoustic closure. It is
stacked on PR #54 head `39a394698383879225216aee403c1221fe454e0e` and does not depend on
the MUSCL/TVD line.

## Objective

Before a real-fluid HEM state can enter the production FVM, the code must distinguish:

- compressed or subcooled high-density liquid candidates;
- liquid-vapor two-phase states;
- ordinary single-phase vapor;
- supercritical states outside the first liquid-vapor scope;
- critical-region states;
- solid or below-triple-temperature states;
- unknown backend classifications.

Quality alone is not sufficient for this classification. This increment therefore uses
explicit CoolProp `PhaseSI` information.

## Core design

The phase-state path accepts `rho/e` and obtains only:

```text
p
T
raw phase
quality where defined
void fraction where defined
phase class
scope status
```

It deliberately does not request sound speed. Every result fixes:

```text
sound_speed_evaluated = false
equilibrium_two_phase_sound_speed_closure_approved = false
```

This allows equilibrium state evaluation to be reviewed independently from the acoustic
closure later used by Rusanov flux and CFL.

## Current supported-candidate scope

```text
compressed_or_subcooled_liquid
liquid_vapor_two_phase
single_phase_vapor
```

CoolProp labels the representative `8 MPa / 280 K` dense state as
`supercritical_liquid`. Because it is below the critical temperature and outside the
configured critical guard box, this label is mapped to the high-density liquid candidate
class. This is a software scope decision for the first LCO2 HEM path, not a general claim
that every supercritical-labelled state is an ordinary liquid.

The following remain guarded out:

```text
supercritical
supercritical_gas
critical_region
solid_or_below_triple_guard
```

Unknown backend labels remain explicit `unknown`; they are not silently mapped.

## Quality and void-fraction policy

- liquid candidate: `q=0`, `alpha=0`;
- ordinary vapor: `q=1`, `alpha=1`;
- explicit two-phase: obtain `Q` from CoolProp and compute `alpha` from saturated
  liquid/vapor densities;
- supercritical, critical, solid-guarded, and unknown states: quality and alpha are
  undefined (`NaN` internally and `null` in JSON).

This avoids presenting an artificial vapor quality where it has no thermodynamic meaning.

## Guard policy

Critical constants and triple temperature are queried from CoolProp. A configurable guard
box is applied around `(Tcrit, Pcrit)`. States at or below the triple temperature are outside
the liquid-vapor-only scope. These are software stop guards, not validated physical
phase-boundary tolerances.

## Representative phase map

The installed-CoolProp evidence uses nine fixed states:

```text
8 MPa / 280 K dense liquid candidate
5 MPa / 280 K liquid
2 MPa saturated-liquid endpoint
2 MPa q=0.10
2 MPa q=0.50
2 MPa q=0.90
2 MPa saturated-vapor endpoint
1 MPa / 280 K superheated vapor
8 MPa / 310 K high-temperature supercritical state
```

The map emits JSON, CSV, and Markdown evidence. No sound-speed query is made by the
phase-map path.

## Validation evidence

Primary validation head:

```text
bb02e2865c39bc78dabc9e468a486ca7bdd58f6c
```

```text
workflow run:          29744597504
artifact ID:           8461927762
artifact SHA256:       d91869f6d7fd3d18ab9e2abf1b3e9b6fecfa87228dabd5546fd8024aa7252c6a
focused HEM tests:     39 passed, 0 skipped
full repository:       423 passed, 0 skipped
phase-map states:      9 / 9
sound-speed calls:     none
```

The first diagnostic run exposed that CoolProp reports `8 MPa / 280 K` as
`supercritical_liquid`; the classification policy was corrected and revalidated. A separate
full-suite diagnostic failure was traced to missing plotting dependencies in the temporary
workflow, not to the HEM implementation. Revalidation with the repository plotting extra
passed the full suite.

After evidence capture, the temporary phase-validation workflow was removed and the
permanent CoolProp wave workflow was restored byte-for-byte to the main-branch version.

## Tests

The focused tests cover:

- phase-label normalization;
- configuration validation;
- liquid/two-phase/gas/supercritical/critical/solid/unknown classification;
- `supercritical_liquid` handling away from the critical guard;
- below-triple guard priority;
- critical-box guard priority;
- input immutability;
- two-phase quality and void fraction;
- undefined quality for guarded states;
- representative-map inventory;
- false production, sound-speed, Validation, and design-use flags.

## Deliberately excluded

This increment does not:

- modify `FvmSolver`;
- modify numerical flux or CFL;
- define equilibrium two-phase sound speed;
- modify `LCO2PropertyEOSAdapter`;
- modify HEM/HNE phase-change operators;
- add a 1-D HEM case;
- validate critical or solid thermodynamics;
- support high-temperature supercritical states in the first liquid-vapor HEM path;
- claim physical Validation or design-use acceptance.

## Completion boundary

The increment is review-ready when:

- installed-CoolProp focused tests run without skips;
- the representative nine-state map is generated;
- no phase-map code requests sound speed;
- the full repository suite passes;
- permanent workflows remain green;
- temporary validation workflow is removed;
- the permanent CoolProp wave workflow matches main;
- final diff contains only permanent source, tests, and documentation.

## Next gate

Define and independently verify the equilibrium two-phase sound-speed closure. Only after
both explicit phase classification and the acoustic closure are reviewed should a
first-order uniform HEM state be connected to `FvmSolver`.
