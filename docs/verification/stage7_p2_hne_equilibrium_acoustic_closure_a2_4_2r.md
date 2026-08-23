# Stage 7 P2-A2.4-2R — Equilibrium Acoustic Closure Resolution

## 1. Purpose

This increment resolves the immediate model-form limitation identified in
P2-A2.4-2: the existing open-two-phase surrogate maps equilibrium states to an
approximately constant pressure, so the thermodynamic derivative produces
`c_eq^2 ~= 0`.

A2.4-2R does **not** alter that established HEM/HNE baseline. Instead, it adds an
independent analytic verification closure whose only purpose is to make the
equilibrium acoustic derivative finite, positive, reproducible, and directly
checkable.

Authoritative source baseline:

```text
P2-A2.4-1 SHA
3001480c5c4235c898be866c71335464f5d112d7
```

Formal outcome when all focused gates pass:

```text
A2_4_2R_WORKING_VERIFICATION_SLICE_WITH_SOLVER_AUTHORITY_CLOSED
```

## 2. Model boundary

The implementation is deliberately independent of:

- accepted FVM conservative state updates,
- production pressure and flux evaluation,
- CFL calculation,
- Rusanov dissipation,
- boundary characteristics,
- phase-transfer source integration.

Every solver-authority flag remains `false`. No empirical sound-speed blend is
used as a fallback.

## 3. Analytic equilibrium manifold

The verification manifold is parameterized by pressure `p` and equilibrium
vapor mass fraction `q`.

The pressure-dependent constituent densities use the same reference values and
pressure slopes as `SurrogateLCO2PropertyBackend`:

```text
rho_l(p) = rho_l_ref + (p - p_ref) / c_l^2
rho_v(p) = rho_v_ref + (p - p_ref) / c_v^2
```

The saturation-temperature and internal-energy branches are:

```text
T_sat(p) = T_ref + (p - p_ref) / p_per_kelvin

e_l(p) = e_l_ref + cv_l [T_sat(p) - T_ref]
e_v(p) = e_l(p) + L
```

The homogeneous equilibrium mixture manifold is:

```text
v = 1/rho = (1-q)/rho_l(p) + q/rho_v(p)

e = e_l(p) + q L
```

Unlike the earlier constant-pressure open-two-phase mapping, this manifold has
an explicit pressure-dependent saturation path and therefore a non-zero
thermodynamic acoustic response.

## 4. Equilibrium acoustic derivative

For the local isentropic Euler perturbation path:

```text
dv/drho = -1/rho^2

de/drho = p/rho^2
```

write the manifold Jacobian as:

```text
[ v_p  v_q ] [ dp/drho ] = [ -1/rho^2 ]
[ e_p  e_q ] [ dq/drho ]   [  p/rho^2 ]
```

The equilibrium candidate is:

```text
c_eq^2 = dp/drho
```

The same volume closure with frozen quality, `dq = 0`, gives:

```text
c_frozen^2 = -1 / (rho^2 v_p)
```

The implementation evaluates the 2x2 solution analytically and independently
checks `c_eq^2` with a centered finite difference along the same local
isentropic tangent.

## 5. Claimed domain

The model is claimed only as a liquid-rich open-two-phase **verification**
closure:

```text
1.5 MPa < p < 5.0 MPa
0.02    < q < 0.45
```

The interval is open. A small numerical boundary guard prevents pressure-root
roundoff from promoting an exact boundary state into the claimed domain.

A state fails closed when any of the following occurs:

- no unique pressure root exists inside recovery scope,
- constituent density becomes non-positive,
- the equilibrium Jacobian is singular or insufficiently conditioned,
- the state is outside the claimed pressure/quality domain,
- no centered derivative stencil remains inside the claimed domain,
- `c_eq^2` or `c_frozen^2` is non-positive,
- the analytic and finite-difference derivatives disagree beyond tolerance,
- the configured subcharacteristic check is not satisfied.

The claimed interval is a software/derivative-verification scope. It is **not**
a certified real-CO2 property range.

## 6. Focused numerical evidence

The deterministic representative cases are:

| Case | p [MPa] | q | c_eq [m/s] | c_frozen [m/s] | derivative relative error |
|---|---:|---:|---:|---:|---:|
| LOW_QUALITY_REFERENCE | 1.900 | 0.050 | 60.017 | 101.387 | 1.38e-6 |
| EARLY_FLASHING | 2.500 | 0.100 | 81.616 | 116.795 | 1.35e-6 |
| MID_QUALITY | 3.500 | 0.300 | 137.865 | 159.297 | 1.01e-6 |
| UPPER_QUALITY_MARGIN | 1.600 | 0.440 | 171.442 | 173.807 | 2.79e-7 |
| HIGH_PRESSURE_MARGIN | 4.800 | 0.300 | 136.572 | 166.266 | 1.56e-6 |

For these focused cases:

- `c_eq^2` is finite and positive,
- the independent derivative cross-check passes,
- `c_eq <= c_frozen` passes,
- repeated evaluation is deterministic,
- an out-of-domain vapor-rich state returns no acoustic value,
- all solver-authority flags remain `false`.

These results demonstrate a working verification slice. They do not establish
real-CO2 acoustic accuracy.

## 7. Real-fluid reference position

The repository already contains a separate CoolProp-oriented equilibrium sound-
speed reference path in:

```text
liquid_gas_transient.hem_equilibrium_sound_speed
```

A numerical CoolProp comparison is intentionally **not** a pass/fail dependency
of this A2.4-2R slice. The present increment is dependency-free and verifies the
model algebra, state recovery, derivative implementation, guards, and authority
boundary.

Before any `PHYSICALLY_VALIDATED`, design-use, or hydrodynamic-authority claim,
a representative real-fluid comparison remains mandatory. A CoolProp result
must not be interpreted as validation of the separate HNE frozen-quality
closure or finite-relaxation acoustics.

## 8. Implementation and evidence package

The implementation is separated into a public facade, model, types/authority
contract, and evidence module. This keeps the analytic closure independent of
evidence formatting while preserving one stable public import path.

The public module writes exactly:

```text
summary.json
equilibrium_acoustic_cases.csv
operator_report.md
manifest.json
```

The focused workflow also records an eight-test JUnit result.

## 9. Maturity statement

```text
IMPLEMENTED                         true
WORKING VERIFICATION SLICE          true
WORKING VERTICAL SLICE              false
FINITE-PIPELINE ACOUSTIC SHADOW     false
VERIFIED                            false
ACCEPTED                            false
PHYSICALLY VALIDATED                false
DESIGN-USE ACCEPTED                 false
PRODUCTION APPROVED                 false
HYDRODYNAMIC COUPLING ALLOWED       false
```

Passing A2.4-2R authorizes only the next read-only step:

```text
P2-A2.4-3
finite-pipeline read-only acoustic shadow
```

It does not authorize use of the candidate in CFL, fluxes, boundaries, or the
accepted hydrodynamic trajectory.
