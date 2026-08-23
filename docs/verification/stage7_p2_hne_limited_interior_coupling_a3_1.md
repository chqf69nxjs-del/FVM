# Stage 7 P2-A3.1 — Limited Interior HNE Hydrodynamic Coupling

## 1. Purpose

P2-A2.4-3 established a finite-pipeline read-only acoustic shadow. P2-A2.4-4
then retained finite-relaxation phase speed and attenuation as diagnostic
quantities rather than collapsing them into an unqualified scalar sound speed.
The Acoustic Authority Gate subsequently checked an A2.4-2R-compatible
nonequilibrium candidate pressure closure, its conservative flux Jacobian, and
its Frozen characteristic speed.

P2-A3.1 is the first increment in which HNE thermodynamic quantities actually
influence an FVM update. The activation is deliberately narrow:

```text
candidate pressure p(rho,e,q)
        -> dedicated interior Euler physical flux

candidate Frozen c(rho,e,q)
        -> dedicated interior Rusanov dissipation
        -> dedicated interior CFL time step
```

This is a new verification harness. It does not change the existing production
or default solver configuration.

## 2. Source authority

The implementation is based on the green Acoustic Authority Gate:

| Item | Pinned value |
|---|---|
| Authority Gate HEAD | `d4c1daf4db9c6e367a75d77c6660f417a9aee061` |
| Authority Gate workflow run | `32629047962` |
| Authorized next action | `P2-A3.1 limited interior implementation` |

The Gate authorized only implementation and verification of the dedicated
interior candidate. It did not activate boundary characteristics, critical
discharge, finite-pipe discharge feedback, design use, or production use.

## 3. Candidate equation set

The conservative state remains

```text
U = [rho, rho*u, rho*E, rho*q]
```

and the Euler-type physical flux is

```text
F(U) = [
    rho*u,
    rho*u^2 + p_HNE,
    u*(rho*E + p_HNE),
    rho*q*u,
]
```

The pressure and Frozen sound speed are evaluated from the same
A2.4-2R-compatible transported-quality pressure closure. Therefore the
candidate hyperbolic characteristics are

```text
u - c_frozen
u
u
u + c_frozen
```

as checked by the preceding Authority Gate.

## 4. Numerical architecture

The existing `FvmSolver` already obtains pressure and sound speed through its
configured EOS interface. P2-A3.1 therefore constructs a dedicated solver with

```text
AcousticCompatibleHNEVerificationEOS
```

while retaining the existing Euler physical-flux formula and Rusanov formula.
In this dedicated path:

```text
EOS primitive pressure -> physical flux
EOS primitive Frozen c  -> Rusanov |u|+c
EOS primitive Frozen c  -> CFL |u|+c
```

No branch-specific edit is made to `solver.py` or `flux.py`. Existing solver
users continue to receive the historical/default behavior unless they
explicitly construct this P2-A3.1 verification harness.

## 5. Relaxation source

The transported quality source is

```text
q_new = q_eq + (q_old - q_eq) exp(-dt/tau)
```

and modifies only `rho*q`.

The source uses the same pressure-dependent equilibrium map declared by
A2.4-2R. It fails closed when equilibrium recovery is unavailable or when the
updated quality leaves the open acoustic authority domain.

The focused limits are:

```text
tau -> infinity
q frozen
source equals NoPhaseChange


tau -> 0
q -> q_eq
A2.4-2R equilibrium limit
```

`tau` remains an uncalibrated verification parameter. It is not interpreted as
a measured nucleation or bubble-growth time.

## 6. Focused verification matrix

### 6.1 Uniform nonequilibrium state

A uniform state with transported quality different from equilibrium quality is
advanced with the coupled candidate.

Required evidence:

- primitive pressure equals the candidate HNE pressure;
- primitive sound speed equals candidate Frozen sound speed;
- CFL time step uses `|u| + c_frozen`;
- Rusanov spectral bound uses `|u| + c_frozen`;
- the uniform conservative state is preserved bitwise.

This case proves that pressure and sound speed are activated together rather
than mixing two different thermodynamic closures.

### 6.2 Frozen limit

The `tau = infinity` candidate trajectory is compared with the same solver
using `NoPhaseChange`.

Required evidence:

```text
full conservative trajectory bitwise equal
```

### 6.3 Near-zero relaxation limit

A uniform off-equilibrium state is relaxed with `tau = 1e-18 s`.

Required evidence:

- quality reaches the recovered A2.4-2R equilibrium quality;
- density, momentum, and total energy are not changed by the source;
- candidate pressure and temperature recover the A2.4-2R equilibrium state.

### 6.4 Small-amplitude pressure pulse

A small Gaussian density disturbance is placed at the center of a uniform
pipe. The initial velocity is zero and transported quality is on the declared
equilibrium state. The pulse is kept far from the boundaries throughout the
focused observation interval.

Required evidence:

- left- and right-moving pressure disturbances appear;
- their measured mean speed agrees with `c_frozen` within the focused
  first-order numerical tolerance;
- left/right propagation remains approximately symmetric;
- the disturbances remain interior;
- global conserved quantities remain within the focused roundoff band.

The pulse case is software and mathematical verification of the candidate
hyperbolic coupling. It is not a real-CO2 acoustic validation case.

## 7. Authority boundary

Activated only in the dedicated P2-A3.1 harness:

```text
candidate p_HNE -> interior Euler flux       true
candidate c_frozen -> interior Rusanov       true
candidate c_frozen -> interior CFL           true
```

Still closed:

```text
existing production/default path modified   false
equilibrium c -> solver                      false
finite-relaxation phase speed -> solver      false
HNE boundary characteristics                 false
HNE critical discharge                       false
finite-pipe discharge feedback               false
Physical Validation                          false
design use                                   false
production use                               false
```

Transmissive boundaries are used only to isolate the interior pulse before it
reaches either boundary. Their use does not grant HNE boundary-characteristic
authority.

## 8. Fail-closed conditions

The dedicated candidate stops rather than substituting another EOS or acoustic
value when any of the following occurs:

- density or energy is nonfinite;
- transported quality leaves the open authority interval;
- pressure recovery leaves the claimed pressure interval;
- constituent density becomes invalid;
- the Frozen derivative becomes nonpositive;
- equilibrium recovery for the relaxation source fails;
- relaxation leaves the open authority interval;
- a focused verification gate fails.

There is no empirical sound-speed fallback.

## 9. Maturity

A green result establishes only:

```text
IMPLEMENTED                                      true
LIMITED INTERIOR HNE HYDRODYNAMIC COUPLING       true
WORKING VERTICAL SLICE                           true
```

It does not establish:

```text
FINITE-PIPELINE HNE COUPLING                     false
BOUNDARY CHARACTERISTICS                         false
CRITICAL DISCHARGE                               false
DISCHARGE FEEDBACK                               false
VERIFIED / ACCEPTED                              false
PHYSICALLY VALIDATED                             false
DESIGN-USE / PRODUCTION                          false
```

## 10. Next action

After all P2-A3.1 gates pass, the next permitted increment is

```text
P2-A3.2
Controlled finite-pipe HNE coupling
```

That increment should introduce a controlled depressurization while retaining
closed HNE boundary-characteristic and physical-discharge authority. The first
goal is to observe the closed interior feedback

```text
pressure disturbance
    -> q_eq changes
    -> transported q lags or relaxes
    -> p_HNE changes
    -> subsequent pressure-wave update changes
```

before any U3 B2 discharge integration is attempted.
