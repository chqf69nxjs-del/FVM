# Stage 7 — Pure-CO2 HEM Equilibrium Sound-Speed Scaffold

## Status

`IN_PROGRESS; STACKED ON PR #55; NOT SOLVER CONNECTED`

This increment defines a verification-first acoustic closure candidate after explicit phase
classification. It is based on PR #55 closeout head
`edc4bcc4a1b38c2a6fbd674dadece287afd7958e`.

## Objective

The first-order HEM FVM will require one acoustic speed for:

- the Rusanov maximum signal speed;
- the CFL time-step limit;
- pressure-wave and depressurization-front propagation.

CoolProp and REFPROP do not define a general bulk speed of sound for an equilibrium
liquid-vapor mixture. The project therefore must define an application-specific HEM
acoustic closure rather than silently using a backend two-phase `A` result.

## Thermodynamic identity

For an equilibrium equation of state written as `p=p(rho,e)`, the isentropic derivative is
estimated from:

```text
c_eq^2 = (dp/drho)|e + (p/rho^2) (dp/de)|rho
```

The relation follows from `c^2=(dp/drho)|s` and the isentropic first-law relation
`(de/drho)|s=p/rho^2`.

## Numerical method

The scaffold uses central finite differences around one `rho/e` state:

```text
(dp/drho)|e  ~= [p(rho+h_rho,e)-p(rho-h_rho,e)]/(2 h_rho)
(dp/de)|rho  ~= [p(rho,e+h_e)-p(rho,e-h_e)]/(2 h_e)
```

The stencil is guarded by explicit phase classification:

- center and both stencil states must be `supported_candidate`;
- by default, both stencil states must retain the center phase class;
- a failed or phase-crossing stencil is reduced by repeated step halving;
- non-finite or non-positive `c_eq^2` is rejected;
- no clipping or artificial minimum acoustic speed is applied.

## CoolProp boundary

For every liquid-vapor two-phase state, CoolProp is used only for:

```text
p
T
phase
quality
void fraction inputs
```

CoolProp speed of sound `A` is not requested for two-phase states.

For representative single-phase liquid and vapor states only, the finite-difference result
is compared with CoolProp `A`. This is a software/numerical cross-check of the identity and
finite-difference implementation; it is not physical Validation of the two-phase closure.

## Representative evidence

The initial map contains:

```text
8 MPa / 280 K dense liquid candidate
5 MPa / 280 K liquid
2 MPa q=0.05
2 MPa q=0.10
2 MPa q=0.25
2 MPa q=0.50
2 MPa q=0.75
2 MPa q=0.90
2 MPa q=0.95
1 MPa / 280 K vapor
```

Endpoints `q=0` and `q=1` are excluded from the first two-phase acoustic map because a
central finite-difference stencil can cross the phase boundary there.

## Tests

The focused tests cover:

- configuration validation;
- analytic ideal-gas recovery;
- adaptive step halving when a stencil changes phase;
- rejection of guarded center states;
- rejection of non-positive `c_eq^2`;
- single-phase CoolProp comparison;
- positive finite open-two-phase estimates;
- moderate finite-difference step refinement;
- representative-map inventory;
- proof that no CoolProp two-phase sound speed is requested;
- false production, Validation, design-use, and accuracy-band flags.

## Deliberately excluded

This increment does not:

- connect acoustic results to `FvmSolver`;
- change Rusanov flux or CFL;
- approve the closure for production use;
- establish an accuracy band for two-phase sound speed;
- compare with experimental acoustic or depressurization data;
- cover critical, solid, high-temperature supercritical, HNE, or impurity states;
- add a 1-D HEM case.

## Completion boundary

The scaffold is review-ready when:

- pure and installed-CoolProp focused tests pass without skips in the validation job;
- all representative states produce finite positive estimates;
- single-phase estimates agree qualitatively with CoolProp references;
- two-phase records contain no backend `A` request;
- finite-difference step sensitivity is recorded;
- full repository tests pass;
- permanent workflows remain green;
- temporary validation helpers are removed;
- no production solver behavior changes.

## Next gate

After review, the next increment should define acceptance criteria for the sound-speed map,
then use the reviewed closure in a uniform first-order HEM-state preservation test. A 1-D
liquid-to-two-phase expansion problem follows only after uniform-state preservation is
established.
