# Stage 7 — Pure-CO2 HEM Equilibrium Sound-Speed Scaffold

## Status

`VALIDATED STACKED DRAFT PR #56; NOT SOLVER CONNECTED`

This increment defines a verification-first acoustic closure candidate after explicit phase
classification. It is based on PR #55 closeout head
`edc4bcc4a1b38c2a6fbd674dadece287afd7958e`.

## Objective

The first-order HEM FVM will require one acoustic speed for:

- the Rusanov maximum signal speed;
- the CFL time-step limit;
- pressure-wave and depressurization-front propagation.

CoolProp and REFPROP do not define a general bulk speed of sound for an equilibrium
liquid-vapor mixture. The project therefore defines an application-specific HEM acoustic
closure candidate rather than silently using a backend two-phase `A` result.

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

For every liquid-vapor two-phase state, CoolProp is used only for equilibrium pressure and
phase/property evaluation. CoolProp speed of sound `A` is not requested.

For representative single-phase liquid and vapor states only, the finite-difference result
is compared with CoolProp `A`. This checks the identity and numerical implementation; it is
not physical Validation of the two-phase closure.

## Representative evidence

The validated map contains ten states:

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

Observed equilibrium sound-speed candidates:

| state | phase | c_eq [m/s] | single-phase relative error |
|---|---|---:|---:|
| 8 MPa / 280 K | dense liquid candidate | 557.448855 | 4.21e-08 |
| 5 MPa / 280 K | liquid | 495.517491 | 1.76e-07 |
| 2 MPa / q=0.05 | two-phase | 37.846900 | not applicable |
| 2 MPa / q=0.10 | two-phase | 52.645642 | not applicable |
| 2 MPa / q=0.25 | two-phase | 89.300480 | not applicable |
| 2 MPa / q=0.50 | two-phase | 135.765681 | not applicable |
| 2 MPa / q=0.75 | two-phase | 172.533607 | not applicable |
| 2 MPa / q=0.90 | two-phase | 191.745205 | not applicable |
| 2 MPa / q=0.95 | two-phase | 197.788354 | not applicable |
| 1 MPa / 280 K | vapor | 252.326565 | 3.54e-10 |

Endpoints `q=0` and `q=1` are excluded because a central finite-difference stencil can cross
the phase boundary there.

The low sound speed near the liquid-side two-phase onset is a numerical observation of the
selected equilibrium closure and CoolProp EOS. It is not yet an approved physical accuracy
statement.

## Validation evidence

Primary validation head:

```text
2458ed2a3beb8ad1e80721a47a11f445822b4641
```

```text
workflow run:          29748093054
artifact ID:           8463388994
artifact SHA256:       97b6f04a38cd6debafc66fac3dc8b902d1abdf1fed982e04c48000ca5682ad79
focused HEM tests:     63 passed, 0 skipped
full repository:       447 passed, 0 skipped
sound-speed states:    10 / 10
two-phase states:      7 / 7
CoolProp two-phase A:  never requested
```

The generic implementation recovered the analytic ideal-gas sound speed. The three
single-phase CoolProp states agreed with backend `A` far inside the qualitative `1%` test
guard. Open two-phase states were finite, positive, phase-preserving, and stable under a
moderate finite-difference step refinement check.

After evidence capture, the temporary sound-speed workflow was removed and the permanent
CoolProp wave workflow was restored byte-for-byte to main.

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

- pure and installed-CoolProp focused tests pass without skips;
- all representative states produce finite positive estimates;
- single-phase estimates agree with CoolProp references;
- two-phase records contain no backend `A` request;
- finite-difference step sensitivity is recorded;
- full repository tests pass;
- permanent workflows remain green;
- temporary validation helpers are removed;
- no production solver behavior changes.

## Next gate

Define a cautious acceptance and change-control policy for this acoustic map, then use the
reviewed closure in a uniform first-order HEM-state preservation test. A 1-D
liquid-to-two-phase expansion problem follows only after uniform-state preservation is
established.
