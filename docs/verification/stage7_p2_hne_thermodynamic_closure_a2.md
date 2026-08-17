# Stage 7 / P2-A2 Thermodynamic Closure Refinement

## Status

`SOURCE_ONLY_THERMODYNAMIC_FEEDBACK_PROTOTYPE`

This increment is a deliberately narrow bridge from the P2-A1 transported-quality scaffold toward a thermodynamically coupled HNE model. It is not a physical HNE vertical slice and it is not connected to the 1-D FVM flux.

## Authority boundary

P2-A2 starts from the green P2-A1R authority at:

`ae484cecf181afa187e91dc19c294f303c6fe38e`

The existing HEM path remains unchanged and is the reference limit. P1 mesh/CFL limitations and all P2-A1R model-form limitations remain active.

## Purpose

P2-A1 transported an independent vapor mass fraction but still evaluated pressure, temperature and acoustic speed from the HEM rho/e state. P2-A2 introduces the smallest deterministic closure in which transported nonequilibrium quality feeds back into the thermodynamic state.

The source-only independent variables are:

- mixture mass density `rho`
- mixture specific internal energy `e`
- transported vapor mass fraction `q`

During the phase-transfer source step:

- `rho` is conserved exactly
- `e` is conserved exactly
- `q` relaxes toward the existing surrogate HEM equilibrium quality

## Constituent definitions

For this verification closure only, the surrogate reference pressure branches are reused:

```text
rho_l(p) = rho_l_ref + (p - p_ref) / c_l^2
rho_v(p) = rho_v_ref + (p - p_ref) / c_v^2
```

Constituent internal energies use the existing surrogate reference values:

```text
e_l(T) = e_l_ref + cv_l (T - T_ref)
e_v(T) = e_l_ref + h_lv_ref + cv_v (T - T_ref)
```

There is no slip: liquid and vapor share the homogeneous mixture velocity. The source-only prototype also assumes common pressure and common temperature. These are model assumptions for verification, not validated CO2 nonequilibrium physics.

## Mixture closure

At prescribed `(rho, e, q)`, temperature follows the total internal-energy constraint:

```text
e = (1-q) e_l(T) + q e_v(T)
```

and pressure is the positive root of the mixture-volume constraint:

```text
1/rho = (1-q)/rho_l(p) + q/rho_v(p)
```

Void fraction is then

```text
alpha = (q/rho_v) / ((1-q)/rho_l + q/rho_v)
```

The pressure root is solved deterministically and fails closed if it cannot be bracketed or if constituent density, pressure, temperature or void fraction becomes non-admissible.

## Phase-transfer source

The transported quality uses the same exact exponential relaxation form as P2-A1:

```text
q_new = q_eq + (q_old - q_eq) exp(-dt/tau)
```

`tau` remains an **ASSUMED sensitivity parameter**. It is not a nucleation delay, bubble-growth time, metastability parameter, or experimentally validated flashing time.

Because the source update changes only q while keeping rho and e fixed, latent/internal-energy redistribution is represented through the algebraic mixture closure rather than by injecting or removing mixture energy.

## Limiting cases

### tau -> 0

For the constructed surrogate equilibrium reference states used by the focused verification, exact relaxation reaches `q_eq`; the closure then recovers the existing surrogate HEM pressure, temperature, void fraction and surrogate acoustic diagnostic.

This is a tested constructed-state limiting-case check, not a theorem over the complete CO2 state space.

### tau -> infinity

`q_new = q_old`, so the source approaches a frozen-quality state while rho and e remain unchanged.

## Acoustic treatment

The current `acoustic_speed_diagnostic_m_s` reuses the existing surrogate quality-dependent sound-speed mapping so that q feedback is visible in diagnostics and the equilibrium surrogate limit is retained.

Its authority is explicitly:

`SURROGATE_DIAGNOSTIC_ONLY_NOT_HYDRODYNAMIC_CLOSURE`

It is **not** a derived nonequilibrium isentropic acoustic closure and must not yet be used by the FVM Riemann/flux path.

## Guards / fail-closed conditions

The prototype fails closed for:

- nonfinite or nonpositive mixture density
- nonfinite internal energy
- q outside `[0,1]`
- nonpositive/nonfinite pressure
- nonpositive constituent density
- nonpositive/nonfinite temperature
- pressure-root bracketing/convergence failure
- volume residual above tolerance
- invalid void fraction
- invalid acoustic diagnostic
- nonpositive finite relaxation time
- negative/nonfinite source-step dt

The exact exponential source is not subject to an explicit Euler `dt/tau` stability limit, but `dt/tau` is retained as a stiffness diagnostic. This does not remove the physical need to validate tau.

## Explicitly OPEN after A2

The following remain outside this increment:

1. real-fluid nonequilibrium constituent EOS / property validation
2. rigorous nonequilibrium acoustic derivative
3. nucleation / metastability / bubble-growth kinetics
4. interfacial area and heat/mass-transfer correlations
5. slip / two-fluid momentum disequilibrium
6. state-dependent or experimentally calibrated tau
7. deterministic phase switching over the full CO2 phase map
8. 1-D finite-pipeline coupling
9. physical discharge-feedback loop
10. P1 mesh/CFL independence
11. physical validation against experiment

## Maturity

```text
IMPLEMENTED                                  : true
SOURCE-ONLY THERMODYNAMIC FEEDBACK PROTOTYPE: true

PHYSICAL HNE VERTICAL SLICE                  : false
WORKING VERTICAL SLICE                       : false
VERIFIED                                     : false
ACCEPTED                                     : false
PHYSICALLY VALIDATED                         : false
DESIGN-USE ACCEPTED                          : false
PRODUCTION APPROVED                          : false
```

## Next decision

If the focused A2 tests and CI are green, the allowed next step is a targeted A2.3 integration design for finite-pipeline coupling. That integration must preserve the HEM reference path and must not use the diagnostic acoustic value as a production flux closure without a separate acoustic-closure decision.
