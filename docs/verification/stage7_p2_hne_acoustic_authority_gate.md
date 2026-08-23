# Stage 7 P2 — HNE Acoustic Authority Gate

## 1. Purpose

A2.4-2R established a guarded analytic equilibrium/frozen acoustic pair.
A2.4-3 showed that those diagnostics can be evaluated after accepted finite-pipe
steps without changing the authoritative trajectory. A2.4-4 then connected the
equilibrium and frozen limits with a stable single-relaxation dispersion model.

This increment answers the narrower question required before P2-A3.1:

> Can one pressure closure and one frozen acoustic derivative form a coherent,
> hyperbolic four-variable interior Euler system?

The gate does **not** activate HNE hydrodynamic coupling. It grants permission
only to implement and verify a limited interior candidate in P2-A3.1.

## 2. Source authority

| Item | Frozen value |
|---|---|
| A2.4-4 HEAD | `b844741da4775f2e2970cbbe92a6b8be35fd3c79` |
| A2.4-4 workflow run | `32626761290` |
| A2.4-4 artifact ID | `9489909447` |
| A2.4-4 artifact SHA-256 | `0164a54af61696aa6c955a4f5854589f4ad9b164c095d914e3f30446c865a4b2` |
| A2.4-4 analysis SHA-256 | `1357f0c768df7834a84d8c3d00dbb27e7524d7c9df9c6e1e744b23aca3b326cd` |

A2.4-4 retained every CFL, flux, Rusanov, boundary and hydrodynamic permission
as `false`. This gate begins from that closed authority state.

## 3. Why the legacy A2 equilibrium map is not promoted

The legacy A2 thermodynamic prototype computes equilibrium quality from density
alone. The A2.4-2R verification manifold is pressure dependent and recovers
equilibrium quality from `rho` and `e`. Away from the reference pressure, these
maps differ materially.

The gate therefore uses the legacy A2 closure only to demonstrate and record the
mismatch. Its density-only equilibrium map is explicitly quarantined and is not
used by the P2-A3.1 candidate.

## 4. Acoustic-compatible verification EOS

The candidate state uses transported quality `q` as an independent variable.
Its pressure is recovered from the same constituent-volume equation used by the
A2.4-2R manifold:

\[
\frac{1}{\rho}
=
\frac{1-q}{\rho_l(p)}
+
\frac{q}{\rho_v(p)}.
\]

The constituent density slopes are

\[
\rho_l(p)=\rho_{l,0}+\frac{p-p_0}{c_l^2},
\qquad
\rho_v(p)=\rho_{v,0}+\frac{p-p_0}{c_v^2}.
\]

For the verification caloric closure,

\[
T=T_0+\frac{e-e_{l,0}-qL}{c_{v,l}}.
\]

This common caloric slope is deliberately simple. When `q` equals the A2.4-2R
equilibrium quality, it recovers the A2.4-2R equilibrium temperature exactly.
It is not asserted to be a real-CO2 nonequilibrium caloric EOS.

## 5. Frozen derivatives from the same pressure model

At fixed transported quality,

\[
\left(\frac{\partial p}{\partial\rho}\right)_q
=
\frac{-1/\rho^2}{(\partial v/\partial p)_q}
\equiv c_f^2.
\]

The composition derivative at fixed density is

\[
\left(\frac{\partial p}{\partial q}\right)_\rho
=
-\frac{(\partial v/\partial q)_p}{(\partial v/\partial p)_q}.
\]

Both derivatives therefore come from the same pressure closure used by the
candidate physical flux. No empirical sound-speed blend is used.

## 6. Four-variable interior system

The conservative state is

\[
U=[\rho,\rho u,\rho E,\rho q]^T,
\]

with Euler-type physical flux

\[
F(U)=
\begin{bmatrix}
\rho u\\
\rho u^2+p\\
u(\rho E+p)\\
\rho q u
\end{bmatrix}.
\]

For `p=p(rho,q)` in the hyperbolic transport step, the expected characteristics
are

\[
\lambda = u-c_f,\quad u,\quad u,\quad u+c_f.
\]

The repeated `u` characteristic represents the energy/contact and transported
quality modes. The gate requires geometric multiplicity two, not merely a
repeated numerical eigenvalue.

## 7. Independent checks

For five equilibrium and seven finite-quality-offset states, the gate checks:

1. equilibrium pressure and temperature recover A2.4-2R;
2. frozen derivative recovers the A2.4-2R frozen candidate at equilibrium;
3. strict equilibrium subcharacteristic margin remains positive;
4. production physical-flux formula matches an independent implementation;
5. analytic conservative Jacobian matches a five-point numerical Jacobian;
6. analytic and numerical eigenvalues recover `u±c_f,u,u`;
7. the double velocity mode has nullity two;
8. `|u|+c_f` bounds the spectral radius;
9. out-of-domain states fail closed;
10. evidence is deterministic and no existing solver path is modified.

The focused matrix contains 12 states. It covers both positive and negative
velocities, low and moderate quality, and finite deviations from the equilibrium
quality map within the guarded pressure/quality domain.

## 8. Authority decision

When every gate passes, this increment grants only the following permission:

```text
candidate pressure -> P2-A3.1 interior Euler flux implementation     true
candidate frozen c -> P2-A3.1 interior Rusanov implementation        true
candidate frozen c -> P2-A3.1 interior CFL implementation            true
```

The following remain closed:

```text
equilibrium c -> solver                              false
finite-relaxation phase speed -> solver              false
HNE boundary characteristics                         false
HNE critical discharge                               false
finite-pipe discharge feedback                       false
design use                                            false
production use                                        false
```

This is permission to implement the next verification increment. It is not a
claim that coupling is already active.

## 9. Required P2-A3.1 verification

P2-A3.1 must still demonstrate, with coupling confined to an interior test
solver:

- exact uniform-state preservation;
- small-amplitude wave speed consistent with `u±c_f`;
- mass, momentum, energy and transported-quality conservation;
- positivity and bounded quality;
- frozen-limit recovery;
- near-equilibrium / HEM-limit behavior under refinement;
- unchanged production path when the candidate coupling is disabled;
- no boundary or discharge promotion.

## 10. Maturity

```text
IMPLEMENTED                                         true
WORKING VERIFICATION SLICE                          true
ACOUSTIC AUTHORITY GATE PASSED                      gate-dependent
LIMITED P2-A3.1 IMPLEMENTATION AUTHORIZED           gate-dependent

HYDRODYNAMIC COUPLING IMPLEMENTED                   false
FINITE-PIPELINE HNE COUPLING                        false
BOUNDARY / DISCHARGE AUTHORITY                      false
VERIFIED / ACCEPTED                                 false
PHYSICALLY VALIDATED                                false
DESIGN-USE / PRODUCTION                             false
```

## 11. Interpretation

A passing gate means the proposed pressure and Frozen sound speed are internally
consistent enough to enter the next **limited software-verification slice**.
It does not establish a real-CO2 HNE EOS, calibrated phase-transfer time,
validated attenuation, or design-quality blowdown prediction.
