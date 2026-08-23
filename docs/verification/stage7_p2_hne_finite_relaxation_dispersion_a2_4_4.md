# Stage 7 P2-A2.4-4 — Finite-Relaxation Dispersion Investigation

## 1. Purpose

P2-A2.4-3 showed that the guarded A2.4-2R equilibrium and frozen acoustic
limits can be evaluated on every accepted state of the focused finite-pipeline
matrix without changing the authoritative trajectory.

P2-A2.4-4 addresses the intermediate regime:

```text
omega*tau = O(1)
```

In this regime the transported quality responds with a lag. A single static
real sound speed is therefore not assumed. The increment retains a complex
spatial wavenumber, phase speed, attenuation, and a separate temporal
stability analysis.

This is a dependency-free verification model. It is not a calibrated real-CO2
acoustic prediction and grants no hydrodynamic authority.

## 2. Frozen source authority

A2.4-4 starts from the green A2.4-3 read-only shadow:

| Item | Frozen value |
|---|---|
| A2.4-3 head SHA | `3fdd2fbdd81bafecfa44607324c5e47dddd43d52` |
| Workflow run | `32626001623` |
| Artifact ID | `9489698258` |
| Artifact SHA-256 | `c8bf96be49dc1a0116aac005b66261c3f22e1220627081062fc231e0aaa8d8f1` |
| Analysis SHA-256 | `e0f41106b62f8da85eae6870a1bda01d8e39fc1addabf0c565ba3b009f4fc837` |
| Hydrodynamic coupling | `false` |

The six source states are the five A2.4-2R representative states plus the
focused A2.4-3 pipeline state. Each state supplies a positive equilibrium
limit `c_eq^2` and a strictly larger frozen limit `c_f^2`.

## 3. Linear single-relaxation model

Use the convention

\[
\exp\{i(kx-\omega t)\}.
\]

For a scalar quality-relaxation linearization, define the complex dynamic
acoustic modulus

\[
c_{\rm dyn}^2(\omega)
=
c_f^2+
\frac{c_{\rm eq}^2-c_f^2}{1-i\omega\tau}.
\]

This formula has the required endpoint behavior:

\[
\omega\tau\rightarrow 0
\quad\Longrightarrow\quad
c_{\rm dyn}^2\rightarrow c_{\rm eq}^2,
\]

and

\[
\omega\tau\rightarrow \infty
\quad\Longrightarrow\quad
c_{\rm dyn}^2\rightarrow c_f^2.
\]

The intermediate value is complex. It must not be silently converted into one
unqualified real scalar sound speed.

## 4. Spatial dispersion problem

For a prescribed real angular frequency, the verification dispersion relation
is

\[
k^2 c_{\rm dyn}^2-\omega^2=0.
\]

A2.4-4 selects the outgoing branch with

```text
Re(k) > 0
Im(k) >= 0
```

for the selected time-space convention. The recorded observables are

\[
c_{\rm phase}=\frac{\omega}{\operatorname{Re}(k)},
\]

\[
\alpha_k=\operatorname{Im}(k),
\]

and the dimensionless attenuation per wavelength

\[
A_\lambda=
2\pi\frac{\operatorname{Im}(k)}{\operatorname{Re}(k)}.
\]

A real-frequency spatial calculation is considered acceptable only if the
branch is attenuating rather than growing and the dispersion residual is
small.

## 5. Temporal stability problem

Spatial attenuation alone is not sufficient evidence of a stable relaxation
system. A2.4-4 therefore performs an independent temporal eigenanalysis.

Define

\[
z=s\tau,
\qquad
K=k c_f\tau,
\qquad
r=\frac{c_{\rm eq}^2}{c_f^2}.
\]

The dimensionless characteristic polynomial is

\[
z^3+z^2+K^2z+rK^2=0.
\]

The same roots are independently computed from the linear matrix

\[
\begin{bmatrix}
0 & -iK & 0\\
-iK & 0 & -iK(r-1)\\
1 & 0 & -1
\end{bmatrix}.
\]

The cubic and matrix roots must agree, their polynomial residuals must be
small, and all temporal growth rates must satisfy

\[
\operatorname{Re}(z)\le 0.
\]

For this scalar model, the Routh-Hurwitz condition reduces to the strict
subcharacteristic margin

\[
0<c_{\rm eq}^2<c_f^2.
\]

This is a model-stability check. It is not by itself Physical Validation.

## 6. Focused frequency and wavenumber grids

The spatial sweep uses

```text
omega*tau =
1e-6, 1e-4, 1e-2, 0.1, 0.3, 1, 3, 10, 100, 1e4, 1e6
```

with a reference

```text
tau = 1e-4 s
```

only to dimensionalize frequency and wavenumber. The response depends on
`omega*tau`; the reference `tau` is not physically calibrated.

The temporal sweep uses

```text
K = 1e-3, 1e-2, 0.1, 1, 10, 100, 1000
```

for every source state.

Expected evidence sizes are

```text
6 source states
66 spatial-dispersion rows
42 temporal-stability rows
```

This is a focused model-form investigation, not a broad parameter study.

## 7. Required gates

A2.4-4 is ready only if all of the following pass:

1. A2.4-3 source and evidence are pinned exactly;
2. A2.4-3 solver authority remains closed;
3. A2.4-4 solver authority remains closed;
4. all six source states are valid;
5. every state has a strict positive subcharacteristic margin;
6. the low-frequency equilibrium limit is recovered;
7. the high-frequency frozen limit is recovered;
8. the outgoing spatial branch is attenuating;
9. phase speed remains between the equilibrium and frozen limits;
10. the spatial dispersion residual is small;
11. attenuation peaks at an order-one value of `omega*tau`;
12. every temporal mode is stable;
13. cubic and matrix roots agree independently;
14. repeated calculations are deterministic;
15. maturity is not promoted.

An invalid acoustic limit, nonpositive limit, absent strict subcharacteristic
margin, nonfinite frequency, nonpositive relaxation time, or unstable branch
fails closed.

## 8. Evidence products

The command

```bash
python -m liquid_gas_transient.hne_finite_relaxation_dispersion \
  --output-dir artifacts/stage7/p2-hne-finite-relaxation-dispersion-a2-4-4
```

writes exactly:

```text
summary.json
state_summary.csv
spatial_dispersion.csv
temporal_stability.csv
operator_report.md
manifest.json
```

JSON is strict (`allow_nan = false`), and every payload file is recorded by
size and SHA-256.

## 9. Solver authority

Every authority remains false:

```text
complex wavenumber -> CFL                 false
phase speed -> CFL                        false
phase speed -> Rusanov                    false
attenuation -> flux                       false
dynamic modulus -> flux                   false
dispersion -> boundary characteristics   false
hydrodynamic coupling                     false
```

No A2.4-4 quantity enters the authoritative FVM state, pressure, numerical
flux, spectral radius, timestep, or boundary condition.

## 10. Maturity

A green result may establish only

```text
IMPLEMENTED                                  true
WORKING VERIFICATION SLICE                   true
FINITE-RELAXATION DISPERSION INVESTIGATION   true
SPATIAL DISPERSION EVIDENCE READY            true
TEMPORAL STABILITY EVIDENCE READY            true
```

The following remain false:

```text
ACOUSTIC AUTHORITY GATE READY
HYDRODYNAMIC COUPLING ALLOWED
WORKING VERTICAL SLICE
VERIFIED / ACCEPTED
PHYSICALLY VALIDATED
DESIGN-USE ACCEPTED
PRODUCTION APPROVED
```

## 11. Interpretation of a green result

A green A2.4-4 result means:

> Within the declared single-relaxation verification model, the finite-rate
> response joins the equilibrium and frozen acoustic limits through a stable,
> frequency-dependent, attenuating dispersion relation.

It does not mean:

- the model is a calibrated liquid-CO2 acoustic closure;
- the relaxation time is a nucleation or bubble-growth time;
- one real scalar phase speed may be used in the FVM;
- the frozen candidate may enter CFL or Rusanov;
- P2-A3 coupling is authorized.

## 12. Next action

The next authorized increment is an **Acoustic Authority Gate formulation**.
It should derive the proposed hyperbolic HNE flux Jacobian, compare analytic
and numerical eigenvalues, define the exact validity domain, and decide whether
`p_HNE + c_frozen` may be promoted together for a very limited interior-FVM
slice.

## 13. Primary literature context

The regime separation and stability framing are informed by:

- G. Linga, *A Hierarchy of Non-Equilibrium Two-Phase Flow Models*,
  arXiv:1804.05241 (2018): relaxation hierarchy and subcharacteristic context.
- H. Lund, *A Hierarchy of Relaxation Models for Two-Phase Flow*, SIAM Journal
  on Applied Mathematics 72 (2012), 1713–1741: hyperbolic relaxation and the
  subcharacteristic stability condition.
- K. H. Ardron and R. B. Duffey, *Acoustic wave propagation in a flowing
  liquid-vapour mixture*, International Journal of Multiphase Flow 4 (1978),
  303–322: frequency-dependent propagation and attenuation context.

These references motivate the questions and evidence categories. They do not
validate this project-specific surrogate or grant design-use authority.
