# Stage 7 P2-A3.2 — Controlled Finite-Pipe HNE Hydrodynamic Coupling

## 1. Purpose

P2-A3.1 activated the guarded HNE candidate only in a dedicated interior FVM
harness:

```text
candidate p_HNE(rho,e,q_actual) -> interior Euler flux
candidate c_frozen(rho,e,q_actual) -> Rusanov and CFL
```

P2-A3.2 extends that same candidate into one finite pipe with a controlled
external pressure disturbance. The increment is intentionally narrow. It asks
whether the following numerical feedback loop can be closed without granting
physical-discharge authority:

```text
downstream prescribed pressure decrease
        -> upstream-running rarefaction / pressure disturbance
        -> rho and e change
        -> q_eq(rho,e) changes
        -> q_actual relaxes with finite delay
        -> p_HNE(rho,e,q_actual) changes
        -> c_frozen(rho,e,q_actual) changes
        -> next conservative FVM update changes
```

This is a working verification slice. It is not real-CO2 Physical Validation,
a rupture calculation, or a design discharge calculation.

## 2. Pinned source

The implementation starts from the green P2-A3.1 source:

| Item | Pinned value |
|---|---|
| P2-A3.1 HEAD | `d4db09a6447ba4c98fcf0618e37e3ad6fe859ec1` |
| Dedicated workflow run | `32638595911` |
| Dedicated job | `97192025339` |
| Evidence artifact | `9493006871` |
| Artifact digest | `sha256:21fbde78e47b271d12061dd8c2be67a2128f44645aa6434fe487d50b16d6d423` |

The A3.2 workflow also runs the A3.1 and Acoustic Authority Gate focused tests.
The branch change envelope is limited to a new A3.2 module, tests,
documentation, and dedicated workflow.

## 3. Property backend and maturity

The only property backend used by this increment is:

```text
surrogate_lco2
```

It is a verification surrogate. Its pressures, temperatures, qualities,
void fractions, and wave responses are not design-quality quantitative CO2
predictions.

A green result may establish only:

```text
IMPLEMENTED                                      true
WORKING VERIFICATION SLICE                       true
WORKING VERTICAL SLICE                           true
CONTROLLED FINITE-PIPE HNE COUPLING              true
```

It does not establish:

```text
VERIFIED / ACCEPTED                              false
PHYSICALLY VALIDATED                             false
DESIGN-USE ACCEPTED                              false
PRODUCTION APPROVED                              false
```

## 4. Governing state and split relaxation

The conservative state remains

```text
U = [rho, rho*u, rho*E, rho*q_actual]
```

and the candidate physical flux remains

```text
F(U) = [
    rho*u,
    rho*u^2 + p_HNE,
    u*(rho*E + p_HNE),
    rho*q_actual*u,
]
```

The exact relaxation source inherited from P2-A3.1 is

```text
q_new = q_eq + (q_old - q_eq) exp(-dt/tau)
```

The source changes only `rho*q_actual`. It does not change `rho`, `rho*u`, or
`rho*E`.

The three regimes are evaluated under the same pipe, initial state, pressure
schedule, grid, and CFL:

```text
tau = 1e-18 s   -> near-zero / HEM limit
tau = 8e-4 s    -> finite HNE delay
tau = infinity  -> Frozen-quality limit
```

`tau` remains an uncalibrated verification parameter. It is not interpreted as
a measured nucleation, bubble-growth, or interfacial-transfer time.

## 5. Controlled finite-pipe case

The focused default case is:

| Quantity | Value |
|---|---:|
| Pipe length | `1.2 m` |
| Diameter | `0.05 m` |
| Cells | `64` |
| CFL | `0.25` |
| Initial pressure | `3.2 MPa` |
| Final prescribed right pressure | `2.6 MPa` |
| Initial equilibrium quality | `0.12` |
| Ramp start | `0.2 ms` |
| Ramp duration | `1.2 ms` |
| Final observation time | `7.0 ms` |
| Probe locations | `x/L = 0.25, 0.50, 0.75` |

The left end is reflective/closed. The right end applies a prescribed
verification ghost state following the pressure ramp.

## 6. Boundary authority

The right boundary constructs an exact equilibrium-manifold ghost state at the
prescribed pressure and fixed boundary quality. The adjacent interior velocity
is copied into the ghost state.

This boundary is named:

```text
prescribed_verification_ghost_state_pressure_ramp
```

It is an external deterministic excitation only. It is not any of the
following:

```text
HNE characteristic boundary
critical-flow or choking relation
valve/orifice discharge law
rupture model
physical mass-discharge closure
U3 B2 closed-loop discharge model
```

The implementation fails closed if the prescribed pressure or quality leaves
the open Acoustic Authority domain, if the candidate EOS cannot recover the
prescribed pressure, or if any ghost state becomes nonfinite or nonphysical.

## 7. Interior authority retained from A3.1

Within the dedicated A3.2 solver only:

```text
candidate p_HNE -> Euler physical flux          true
candidate c_frozen -> Rusanov |u|+c             true
candidate c_frozen -> CFL |u|+c                 true
```

Still closed:

```text
equilibrium c -> solver                         false
finite-relaxation phase speed -> solver         false
HNE boundary characteristics                    false
HNE critical discharge                          false
physical discharge model                        false
rupture model                                   false
production/default path modification            false
```

## 8. Pressure-wave evidence

A pressure-drop threshold is monitored at all three probes. Since the
excitation enters at the right boundary, a valid upstream-running disturbance
must arrive in this order:

```text
x/L = 0.75
    before
x/L = 0.50
    before
x/L = 0.25
```

Pairwise front speeds are estimated only as focused propagation diagnostics.
The pressure ramp is finite-amplitude and the threshold is not a rigorous
characteristic tracker, so the estimates are gated only against a broad,
declared band around the initial Frozen speed. They are not used as a new sound
speed or solver closure.

## 9. HNE feedback evidence

For the finite-tau case, the following must all occur:

- the disturbance changes recovered `q_eq`;
- `q_actual` differs measurably from `q_eq`;
- `p_HNE` differs measurably from the equilibrium-manifold pressure;
- the active Frozen speed varies through the transient;
- the finite-tau trajectory differs from both the near-zero and Frozen
  trajectories;
- repeated finite-tau execution produces identical state and history hashes.

The near-zero case must recover `q_actual = q_eq` and the corresponding
equilibrium pressure within the focused roundoff/numerical tolerance.

The Frozen case must have zero internal phase source and preserve transported
quality while `q_eq` moves away from it.

## 10. Conservation budgets

The existing `BoundaryBudgetTracker` records the external numerical fluxes of:

```text
mass
momentum
total energy
vapor mass
```

For mass, momentum, and total energy, the required balance is:

```text
inventory change = left boundary contribution - right boundary contribution
                 + roundoff residual
```

The relaxation source changes only vapor inventory. Therefore the required
vapor balance is:

```text
vapor inventory change
    = boundary vapor transport
    + internal phase-change source
    + roundoff residual
```

The existing `PhaseChangeBudgetTracker` supplies the internal source term. The
A3.2 gate checks relative residuals rather than hiding errors with a fallback or
post-hoc correction.

## 11. Evidence contract

The dedicated evidence envelope is exactly:

```text
summary.json
case_summary.csv
probe_history.csv
step_history.csv
operator_report.md
manifest.json
```

Every evidence stream identifies `surrogate_lco2` and the prescribed boundary
model. The summary records the A3.1 source SHA, workflow run, job, artifact ID,
and artifact digest.

Runtime provenance is separated from the deterministic analysis hash. NumPy
scalars and arrays are recursively converted to Python-native values before
hashing, JSON serialization, CSV writing, `execute()` return, and CLI output.

The operator report is fail closed. If any gate fails, it prints `STOP` and the
failed gate names; it does not instruct the operator to proceed.

## 12. Focused gates

A3.2 requires:

1. Pinned, green A3.1 source.
2. Candidate pressure active in the finite-pipe interior flux.
3. Candidate Frozen speed active in Rusanov and CFL.
4. Identical controlled ramp across near-zero, finite, and Frozen regimes.
5. Outlet-to-upstream pressure-wave arrival at all probes.
6. Finite, positive states inside the open authority domain.
7. Mass, momentum, and energy boundary-budget closure.
8. Vapor boundary-plus-phase-source budget closure.
9. Near-zero-tau HEM limit.
10. Measurable finite-tau quality/pressure/acoustic feedback.
11. Frozen-quality limit.
12. Deterministic finite-tau repeatability.
13. Existing production/default paths unchanged.
14. Characteristic, critical, rupture, physical-discharge, design, and
    production authority closed.

## 13. Fail-closed conditions

The A3.2 harness stops rather than falling back when any of the following
occurs:

- density, internal energy, pressure, temperature, quality, void fraction, or
  Frozen speed is nonfinite;
- density, temperature, or Frozen speed is nonpositive;
- actual or equilibrium quality leaves the open authority interval;
- candidate or equilibrium pressure leaves the open authority interval;
- pressure-root or equilibrium recovery fails;
- the pressure schedule leaves the declared domain;
- relaxation leaves the quality domain;
- the controlled case misses its final time or exceeds the step limit;
- a required budget field is absent;
- a focused gate fails.

No empirical pressure, sound-speed, quality, or boundary fallback is permitted.

## 14. Next action

After all A3.2 gates pass, the next permitted increment is a separately gated
U3 physical-discharge coupling step. That work must introduce and verify a
physical boundary/discharge closure explicitly. A3.2 itself grants no such
authority.

Critical discharge, rupture, HNE characteristic boundaries, physical tau
calibration, nucleation, bubble growth, slip, two-fluid modeling, broad
mesh/CFL campaigns, real-CO2 Physical Validation, design use, and production
activation remain outside this increment.
