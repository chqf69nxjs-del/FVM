# Stage 7 P2-A2.3 — Finite-Pipeline HNE Shadow Integration

## 1. Purpose

P2-A2 established a source-only thermodynamic-feedback prototype in which an
independent vapor mass fraction `q` changes reconstructed pressure, temperature,
void fraction and a diagnostic acoustic response while density and internal
energy remain fixed.

P2-A2.3 moves that closure onto accepted states from a finite one-dimensional FVM
pipe, but only as a **read-only shadow calculation**. It does not authorize HNE
pressure or acoustic feedback into the hydrodynamic solver.

The increment answers one narrow question:

> Can the A2 closure be evaluated on every cell and accepted time step of a
> deterministic finite-pipeline calculation without changing the authoritative
> conservative trajectory?

## 2. Authority boundary

### 2.1 Authoritative line

The authoritative line remains:

```text
surrogate_lco2 backend
        ↓
HEM state from rho/e
        ↓
p_HEM, T_HEM, c_HEM
        ↓
Rusanov flux and CFL
        ↓
accepted conservative state U
```

The EOS adapter is fixed to:

```text
LCO2PropertyEOSAdapter(quality_source="backend")
```

Therefore transported `rho*q` does not select authoritative pressure,
temperature, void fraction or acoustic speed.

### 2.2 Shadow line

After a state is accepted, the shadow observer reads:

```text
U = [rho, rho*u, rho*E, rho*q]
        ↓
rho, u, e, q_transport
        ↓
SurrogateFrozenQualityThermodynamicClosure
        ↓
p_HNE, T_HNE, alpha_HNE, c_HNE(diagnostic)
```

The observer may record and compare these values. It may not mutate `U`, the EOS,
the flux, CFL, boundaries, source operators or solver control flow.

## 3. Backend compatibility rule

The A2 closure is tied to `SurrogateLCO2PropertyBackend`. P2-A2.3 therefore fails
closed unless:

1. the authoritative EOS is `LCO2PropertyEOSAdapter`;
2. the authoritative backend name is `surrogate_lco2`;
3. the authoritative and shadow backend types and parameter sets are equal;
4. authoritative `quality_source` is `backend`.

A CoolProp state may not be passed into this surrogate A2 closure. This increment
contains no real-fluid HNE compatibility claim.

## 4. Conservative state and operator order

The finite-pipeline state remains:

\[
U = [\rho,\;\rho u,\;\rho E,\;\rho q]^T.
\]

Each accepted step follows the existing first-order split order:

1. FVM transport using HEM pressure and sound speed;
2. exact transported-quality relaxation source;
3. physical-state guard;
4. read-only A2 shadow observation.

The quality source reads `rho*q` directly and applies:

\[
q^{n+1}=q_{eq}+(q^*-q_{eq})\exp(-\Delta t/\tau).
\]

Only the fourth conservative component may change in the source. Mass,
momentum and total energy are required to remain bitwise unchanged by it.

## 5. Focused finite-pipeline case

The authoritative verification case uses:

- 16 uniform cells;
- a 0.16 m long, 0.05 m diameter pipe;
- transmissive boundaries;
- uniform `rho`, `u` and `e`;
- a left/right step in transported quality;
- a constructed surrogate equilibrium state with `q_eq = 0.20` and `T = 260 K`;
- 16 accepted CFL-controlled steps.

The initial quality step is transported and relaxed, but it cannot affect the
first three conservative components because authoritative thermodynamics remains
HEM backend thermodynamics.

## 6. Required cases

| Case | Relaxation time | Required interpretation |
|---|---:|---|
| `TAU_NEAR_ZERO` | `1e-18 s` | finite-pipeline HEM limit |
| `TAU_FINITE` | `1e-4 s` | visible HNE thermodynamic difference, no feedback |
| `TAU_FROZEN` | `+inf` | source equivalent to `NoPhaseChange` |

## 7. Mandatory gates

P2-A2.3 is ready only if all of the following pass:

1. surrogate backend contract retained;
2. HEM pressure and sound speed remain flux/CFL authority;
3. shadow observation is read-only;
4. shadow ON/OFF full conservative trajectories are bitwise identical;
5. hydrodynamic trajectories remain unchanged;
6. every closure evaluation succeeds;
7. all states are finite and `q` remains bounded;
8. total mass, momentum and energy are not damaged;
9. `tau -> 0` recovers the finite-pipeline HEM limit;
10. finite `tau` produces visible `p/T/alpha` differences;
11. `tau -> inf` equals a `NoPhaseChange` source reference;
12. closure volume residual remains within tolerance;
13. repeated execution is deterministic;
14. HNE acoustic output remains diagnostic only;
15. the hydrodynamic coupling gate remains closed;
16. maturity is not promoted.

## 8. Acoustic restriction

The two acoustic quantities have different authority:

```text
c_HEM  : authoritative surrogate HEM value used by Flux/CFL
c_HNE  : surrogate diagnostic only
```

The present evidence does not establish a nonequilibrium derivative such as a
defensible `(partial p / partial rho)` along the required constrained path.
Consequently `c_HNE` must not enter Rusanov dissipation, CFL selection,
characteristic interpretation or boundary coupling.

## 9. Evidence files

The focused workflow produces exactly six files:

```text
summary.json
case_summary.csv
step_history.csv
cell_history.csv
operator_report.md
manifest.json
```

The manifest records file sizes and SHA-256 digests. The summary retains the
source A2 SHA, gate results, authority contract, limitations and maturity status.

## 10. Maturity

After successful focused execution:

```text
IMPLEMENTED                                  true
FINITE-PIPELINE SHADOW INTEGRATION           true
DIAGNOSTIC EVIDENCE READY                    true
HYDRODYNAMIC COUPLING ALLOWED                false
PHYSICAL HNE VERTICAL SLICE                  false
WORKING VERTICAL SLICE                       false
VERIFIED / ACCEPTED                          false
PHYSICALLY VALIDATED                         false
DESIGN-USE ACCEPTED / PRODUCTION APPROVED    false
```

This is deliberately narrower than a working HNE pipeline solver.

## 11. Open limitations

- surrogate constituent EOS only;
- no validated nonequilibrium acoustic closure;
- no HNE pressure feedback to flux;
- no nucleation, metastability or bubble-growth model;
- no slip model;
- no physically calibrated relaxation time;
- no real-fluid backend compatibility;
- no physical discharge-feedback loop;
- P1 mesh/CFL limitations remain active.

## 12. Next decision

A green A2.3 authorizes the next **design investigation**, not hydrodynamic
coupling:

> P2-A2.4 — define and test the thermodynamic path and numerical authority needed
> for a defensible nonequilibrium acoustic closure.
