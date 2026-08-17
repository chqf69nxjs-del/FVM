# Stage 7 P2-A2.4-1 — Nonequilibrium Acoustic Closure Contract

## 1. Purpose

P2-A2.3 proved that the A2 nonequilibrium thermodynamic closure can run as a
read-only shadow on accepted finite-pipeline states without changing the
conservative trajectory. Its formal closeout retained one decisive gap:

> the project does not yet have a defensible nonequilibrium acoustic closure.

P2-A2.4-1 defines the contract that must be satisfied before any HNE acoustic
quantity can influence flux, CFL, Riemann structure, boundary characteristics,
or hydrodynamic coupling.

This increment implements no sound-speed formula and changes no solver code.

## 2. Frozen source authority

A2.4-1 starts from the green A2.3 formal closeout:

| Item | Frozen value |
|---|---|
| A2.3 closeout SHA | `4479d0ed4ee76975564e58cdfd152c2a9e554069` |
| Closeout workflow run | `32006617206` |
| Closeout artifact ID | `9280233147` |
| Closeout artifact SHA-256 | `85beec5faaef8715bdf5b7b2dee7687db8856a033aa0e1803ab23f2abb9debe6` |
| Underlying A2.3 SHA | `799edb09faa1502e25837c97fa5d168ad79e492e` |
| Hydrodynamic coupling | `false` |

A2.4-1 may define future evidence requirements, but it may not reinterpret the
A2.3 result as physical HNE validation.

## 3. Why one number called “sound speed” is not enough

The A2 state contains an independent transported quality `q`. During a pressure
perturbation, the response depends on the ratio between the disturbance time
scale and the phase-relaxation time `tau`.

A pressure wave can therefore encounter three distinct regimes:

```text
fast disturbance                 comparable scales                 slow disturbance
relative to relaxation                                            relative to relaxation

omega*tau >> 1                   omega*tau = O(1)                  omega*tau << 1
      |                                  |                                |
      v                                  v                                v
q approximately frozen           q responds with lag               q follows equilibrium
```

The perturbation path must be stated before a pressure-density derivative has a
physical meaning. Holding `q` fixed, moving along the equilibrium manifold, and
solving a finite-rate relaxation problem are different closures.

## 4. Regime A — Frozen quality

### 4.1 Definition

The disturbance is much faster than phase relaxation:

```text
omega*tau >> 1
```

The quality perturbation is frozen:

```text
delta q = 0
```

### 4.2 Required derivative path

A future frozen candidate may use a constrained derivative of the schematic
form

\[
c_f^2 = \left(\frac{\partial p}{\partial \rho}\right)_{q,\,\mathcal C_f},
\]

but `q` alone does not complete the definition. The additional thermodynamic
constraint `C_f`—for example a properly derived entropy or energy path—must be
stated and justified for the governing equations.

A2.4-1 does not select that constraint and therefore does not produce `c_f`.

### 4.3 Mandatory evidence

A frozen candidate requires at least:

- a declared state and backend scope;
- an explicit perturbation constraint;
- an independently checked derivative;
- finite and positive `c_f^2` where a real hyperbolic wave speed is claimed;
- a hyperbolicity check;
- recovery of the `tau -> infinity` or high-frequency limit;
- deterministic reproducibility.

The result remains diagnostic until a later authority gate is passed.

## 5. Regime B — Equilibrium manifold

### 5.1 Definition

Phase relaxation is much faster than the disturbance:

```text
omega*tau << 1
```

Quality follows the declared equilibrium manifold rather than remaining fixed:

```text
q = q_eq(rho, e, ...)
```

### 5.2 Required derivative path

A future equilibrium candidate must be tangent to the selected equilibrium
manifold and to the declared thermodynamic perturbation constraint. It is not
the same partial derivative as the frozen-quality case.

### 5.3 Mandatory limit

Within the present surrogate scope, the candidate must recover the authoritative
HEM acoustic limit as `tau -> 0`. A nonzero unexplained HEM-limit residual is a
fail-closed condition.

The relaxation-system literature motivates an additional stability check: where
the subcharacteristic condition applies, the equilibrium characteristic speed
should not outrun the corresponding relaxation-system characteristic speed.
A2.4-1 records this as a required check; it does not claim that the current A2
surrogate model has already satisfied it.

## 6. Regime C — Finite-relaxation dispersive response

### 6.1 Definition

The disturbance and relaxation time scales are comparable:

```text
omega*tau = O(1)
```

Then `q` changes during the disturbance but can lag pressure, density, and energy
perturbations.

### 6.2 Required formulation

The coupled conservation and relaxation equations must be linearized together.
A static derivative such as

\[
\left(\partial p/\partial\rho\right)
\]

by itself is not a complete finite-relaxation acoustic model.

The minimum output is a dispersion or transfer relation such as

\[
D(k,\omega)=0,
\]

from which the project can distinguish:

- phase speed;
- attenuation rate;
- frozen-limit residual;
- equilibrium-limit residual;
- stable and unstable modes.

Depending on the chosen formulation, `k` or `omega` may be complex. Therefore a
frequency-dependent response must not be silently collapsed into one
unqualified real scalar `c`.

### 6.3 Authority consequence

Finite-relaxation acoustic output remains diagnostic even after it is first
implemented. It cannot enter CFL or Rusanov dissipation merely because a phase
speed can be plotted.

## 7. Required evidence before any promotion

The contract requires the following evidence set:

1. state and backend scope declared;
2. perturbation path declared;
3. energy or entropy constraint declared;
4. independent derivative cross-check;
5. finite and positive `c^2` where a real candidate is claimed;
6. hyperbolicity or dispersion-stability check;
7. `tau -> 0` HEM limit;
8. `tau -> infinity` frozen limit;
9. subcharacteristic-condition check where applicable;
10. finite-relaxation phase speed and attenuation;
11. backend parameter coherence;
12. no branch chatter or derivative-path switching;
13. deterministic reproducibility;
14. finite-pipeline read-only acoustic shadow before coupling.

Passing only a subset does not authorize solver coupling.

## 8. Fail-closed conditions

The work must stop rather than substitute an undocumented value if any of the
following occurs:

- perturbation path unspecified;
- energy or entropy constraint unspecified;
- frequency/time scale unspecified for finite relaxation;
- backend or parameter mismatch;
- nonfinite or out-of-scope state;
- quality outside `[0, 1]`;
- nonfinite derivative;
- nonpositive `c^2` where real hyperbolicity is required;
- loss of hyperbolicity or an unresolved unstable mode;
- HEM or frozen limit not recovered;
- unexplained subcharacteristic-condition violation;
- multiple derivative branches or branch chatter;
- complex response collapsed to an unjustified real scalar;
- attempted use in flux, CFL, or boundaries without a new authority gate.

## 9. Solver authority

Every solver permission remains false:

```text
frozen candidate -> flux/CFL                 false
equilibrium candidate -> flux/CFL            false
finite-relaxation candidate -> flux/CFL       false
HNE boundary characteristics                 false
HNE Riemann structure                         false
hydrodynamic HNE coupling                     false
```

The existing A2 acoustic value remains:

```text
SURROGATE_DIAGNOSTIC_ONLY_NOT_HYDRODYNAMIC_CLOSURE
```

## 10. Maturity

```text
IMPLEMENTED                                  true
ACOUSTIC CONTRACT READY                      true

FROZEN ACOUSTIC FORMULA IMPLEMENTED          false
EQUILIBRIUM ACOUSTIC FORMULA IMPLEMENTED     false
FINITE-RELAXATION DISPERSION IMPLEMENTED     false
FINITE-PIPELINE ACOUSTIC SHADOW READY        false
HYDRODYNAMIC COUPLING ALLOWED                false
PHYSICAL HNE VERTICAL SLICE                  false
WORKING VERTICAL SLICE                       false
VERIFIED / ACCEPTED                          false
PHYSICALLY VALIDATED                         false
DESIGN-USE / PRODUCTION                      false
```

## 11. Next authorized action

The contract authorizes only:

```text
P2-A2.4-2
Frozen and Equilibrium Acoustic Diagnostic Prototypes
```

A2.4-2 shall construct and cross-check frozen and equilibrium candidates as
read-only diagnostics. It shall not implement finite-relaxation dispersion and
shall not connect any candidate to FVM flux or CFL.

## 12. Primary literature basis

The contract framing is informed by the following primary literature:

- G. Linga, *A Hierarchy of Non-Equilibrium Two-Phase Flow Models*,
  arXiv:1804.05241 (2018): relaxation hierarchy and subcharacteristic-condition
  context.
- K. H. Ardron and R. B. Duffey, *Acoustic wave propagation in a flowing
  liquid-vapour mixture*, International Journal of Multiphase Flow 4 (1978),
  303–322, DOI `10.1016/0301-9322(78)90004-6`: frequency-dependent sound speed
  and attenuation in nonequilibrium liquid-vapour acoustics.
- H. Lund, *A Hierarchy of Relaxation Models for Two-Phase Flow*, SIAM Journal
  on Applied Mathematics 72 (2012), 1713–1741, DOI `10.1137/12086368X`:
  hyperbolic relaxation systems and the subcharacteristic condition.

These references support the need to distinguish relaxation regimes and
stability conditions. They do not validate the project’s surrogate closure or
provide design-use authority for liquid CO2.
