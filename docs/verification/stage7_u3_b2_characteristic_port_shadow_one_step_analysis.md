# Stage 7 U3 B2 — characteristic upstream-port shadow one-step analysis

## 1. Status and claim boundary

```text
analysis type:                     MODEL_REVIEW_ONLY
source main:                       aa108961762c9ae70ee9940405024eb5188064b8
shadow source:                     2882cc14128b10f2e4809deba3957d8b65d2aaa9
workflow run / job:                31454022375 / 93664025775
Artifact ID:                       9087387994
Artifact ZIP SHA256:               691dc305550fc17d56481be8d791ec2899fc25aee85381c1a008c8ca6328370c
B2 Contract modification:          none
B1 modification:                   none
production Adapter modification:   none
solver modification:               none
accepted tolerance modification:   none
formal finite-pipe promotion:      none
physical validation:               false
design use:                        false
production activation:             false
```

This note records one actual `FvmSolver` step for each B2-10 state family using a diagnostic-only A1 pipe-side Euler port. It does not select A1 as the production boundary and does not revise the locked B2 v1 Contract.

---

## 2. Gate result

```text
shadow_one_step_gate_passed:       true
B2-10A:                            PASS
B2-10B:                            PASS
B2-10C:                            PASS
reverse-flow Guard triggered:      false / false / false
single-phase identity retained:    true
restriction-reaction ledger:       exact in all rows
```

The A1 port was computed from the characteristic-compatible root at the initial state and supplied to the existing solver through its direct right external-face hook. The solver itself was not modified.

---

## 3. One-step results

| Case | accepted $\Delta t$ [s] | root $u_P$ [m/s] | final outlet $u$ [m/s] | final outlet $p$ [Pa] | phase |
|---|---:|---:|---:|---:|---|
| B2-10A LIQUID_SMALL_DROP | 6.696616961e-6 | 0.12254010 | **+0.01223854** | 4,995,001.385 | liquid |
| B2-10B GAS_UNCHOKED | 1.149722381e-5 | 34.1510280 | **+2.83724258** | 986,353.977 | supercritical_gas |
| B2-10C GAS_CHOKED | 1.149722381e-5 | 64.1703819 | **+4.52117049** | 977,675.251 | supercritical_gas |

All three cases acquired positive outward momentum after the actual conservative update. The deterministic reverse-velocity behavior seen with the old direct stream-momentum mapping did not occur.

---

## 4. Conservative update closure

The global one-step update was independently reconstructed from the external left and right fluxes:

$$
\Delta \mathbf Q
=
\Delta t\,A
\left(\mathbf F_L-\mathbf F_R\right).
$$

Retained residuals were:

| Case | mass residual [kg] | momentum residual [kg m/s] | energy residual [J] | vapor mass [kg] |
|---|---:|---:|---:|---:|
| B2-10A | 7.7503e-18 | 0.0 | 1.4798e-13 | 0.0 exact |
| B2-10B | 1.0948e-19 | 0.0 | 1.0236e-13 | 0.0 exact |
| B2-10C | -9.5715e-20 | 0.0 | -5.7843e-14 | 0.0 exact |

Thus the actual solver step applied the pipe-side A1 flux conservatively to machine-level residuals.

---

## 5. Momentum interpretation

### B2-10A

```text
left external momentum port:       500.0000000037 N
A1 pipe-side right port:            495.0047598563 N
net pipe acceleration force:         +4.9952401474 N
restriction reaction on fluid:     -247.5021337283 N
```

### B2-10B

```text
left external momentum port:       100.0000000000 N
A1 pipe-side right port:             86.8564484062 N
net pipe acceleration force:        +13.1435515938 N
restriction reaction on fluid:      -43.1396517258 N
```

### B2-10C

```text
left external momentum port:       100.0000000000 N
A1 pipe-side right port:             79.2146606980 N
net pipe acceleration force:        +20.7853393020 N
restriction reaction on fluid:      -41.0185545344 N
```

The pipe receives the positive-outward acceleration from the difference between its own left and right Euler ports. The additional downstream stream momentum remains balanced by the separate unresolved restriction reaction. The reaction-ledger residual was exactly zero in all three rows.

---

## 6. What this establishes

```text
A1 root can be placed on actual FvmSolver face:       supported
one actual conservative step succeeds:               supported
positive-outward first response for 10A/B/C:          supported
old deterministic reverse-flow blocker removed:      supported
mass / momentum / energy update closes:               supported
single-phase rho*xv identity retained:                supported
restriction force kept separate and auditable:       supported
```

This is stronger than a static root calculation: the existing production solver accepted and advanced the state with the A1 pipe-side Euler port.

---

## 7. What remains unestablished

```text
A1 dynamically recomputed at every accepted step:    not yet tested
multi-step stability:                                not yet tested
full acoustic horizon:                               not yet tested
mesh / CFL characterization:                         not started
revised Contract:                                    not prepared
production Adapter implementation:                   not changed
finite-pipe benchmark accepted:                      false
physical validation:                                 false
```

The next safe model-review gate is a short diagnostic multi-step execution in which the A1 characteristic root is recomputed from the evolving adjacent cell before every candidate step. It must retain the same mass, energy, momentum and reaction ledgers and stop before any full acoustic horizon or mesh/CFL matrix.
