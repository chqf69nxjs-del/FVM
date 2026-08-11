# Stage 7 U3 B2 — characteristic upstream-port diagnostic analysis

## 1. Status and claim boundary

```text
analysis type:                     MODEL_REVIEW_ONLY
source main:                       aa108961762c9ae70ee9940405024eb5188064b8
A1 diagnostic source:              ce68547c202aad35ff022928b4f6a13f6bde3d64
workflow run / job:                31449484751 / 93650680481
Artifact ID:                       9085879312
Artifact ZIP SHA256:               2cdccf64d5b06de7cadb3efeafe58e679301f2561db5b7c4222f6f76645d07d5
B2 Contract modification:          none
B1 modification:                   none
Adapter modification:              none
solver modification:               none
tolerance modification:            none
formal finite-pipe promotion:      none
physical validation:               false
design use:                        false
production activation:             false
```

This note audits the retained A1 characteristic-compatible upstream-port diagnostic. It does not select the A1 model for production and does not modify the locked B2 v1 Contract.

The retained ZIP and its four-file internal manifest were independently re-hashed after download. The external ZIP SHA256 and every internal file digest matched the recorded values.

---

## 2. What the diagnostic solved

For each baseline family, the diagnostic solved one scalar compatibility equation for the pipe-side boundary pressure $p_P$:

$$
R(p_P)
=
\rho_P(p_P,s_i)
\,u_P(p_P;s_i,p_i,u_i)
\,A_{{pipe}}
-
\dot m_{{B1}}(h_{{0,P}},s_i,p_b,f,C_d)
=0.
$$

The boundary velocity was obtained from the outgoing acoustic characteristic inherited from the pipe interior,

$$
u_P
=
u_i+
\int_{p_P}^{p_i}
\frac{dp}{\rho(p,s_i)c(p,s_i)}.
$$

The accepted B1 component law was then evaluated from the trial boundary stagnation state. Only the B1 mass-flow result was used to close the pipe-side characteristic state. The old B2 direct momentum mapping was not used as the pipe-side momentum closure.

At a root, the pipe-side Euler port is

$$
\dot m=\rho_Pu_PA,
$$

$$
\Pi_P=\dot m u_P+p_PA,
$$

$$
\dot E_P=\dot m h_{{0,P}}.
$$

The downstream B1 stream diagnostic remains

$$
\Pi_E=\dot m u_{{eff}}+p_dA_o,
$$

and the unresolved restriction reaction on the fluid is retained as

$$
R_w=\Pi_E-\Pi_P.
$$

---

## 3. Exact identities

The diagnostic retained the existing exact closed and zero-drop wall identities using the same pressure coordinate as the accepted Adapter authority.

```text
B2-01 CLOSED LIQUID:
F = [0, 5000000.000037119, 0, 0] exact

B2-02 ZERO-DROP LIQUID:
F = [0, 5000000.000037119, 0, 0] exact
```

Both identity rows passed exact array equality.

---

## 4. Root results

| Case | $p_P$ [Pa] | $u_P$ [m/s] | Mach | $\dot m$ [kg/s] | B1 outcome | $R_w$ [N] |
|---|---:|---:|---:|---:|---|---:|
| B2-10A LIQUID_SMALL_DROP | 4,950,034.4679 | 0.1225401 | 0.0002631 | 0.01071538 | SUCCESS_UNCHOKED_FACE_MAPPING | -247.5021 |
| B2-10B GAS_UNCHOKED | 850,854.9780 | 34.1510280 | 0.1276290 | 0.05185644 | SUCCESS_UNCHOKED_FACE_MAPPING | -43.13965 |
| B2-10C GAS_CHOKED | 736,299.4484 | 64.1703819 | 0.2432294 | 0.08702949 | SUCCESS_CHOKED_FACE_MAPPING | -41.01855 |

The pipe and B1 mass rates agreed at the retained roots:

```text
B2-10A residual: -1.2520835063201119e-12 kg/s
B2-10B residual:  3.4694469519536140e-16 kg/s
B2-10C residual:  1.3877787807814457e-17 kg/s
```

All three roots were single phase and subsonic.

---

## 5. Case interpretation

### 5.1 B2-10A — liquid small pressure drop

```text
initial pipe pressure:              4,999,999.999980528 Pa
pipe-side root pressure:            4,950,034.467923772 Pa
external back pressure:             4,950,000.0 Pa
pipe-side velocity:                 +0.1225400995 m/s
B1 effective stream velocity:       0.2450802435 m/s
```

The root has positive outward velocity and no recoil threshold. Almost all of the initial 50 kPa release appears first as a pipe-side acoustic pressure reduction:

```text
p_i - p_P:                          49,965.5321 Pa
p_0,P - p_b:                            41.0333 Pa
```

This is consistent with the derived acoustic-impedance-limited $t=0^+$ response. It is materially different from applying the quasi-steady B1 law directly to the unchanged initial cell-centre state; therefore it requires a Contract-level model change rather than a local momentum patch.

The approximately one-half ratio between $u_P$ and $u_{{eff}}$ is consistent with the full pipe area being twice the locked open area, with nearly equal liquid densities at P and the retained discharge state.

### 5.2 B2-10B — unchoked gas

```text
initial pipe pressure:              1,000,000.0 Pa
pipe-side root pressure:              850,854.9780 Pa
external back pressure:               800,000.0 Pa
pipe-side velocity:                    +34.1510 m/s
Mach:                                    0.1276
B1 critical pressure:                 469,366.1994 Pa
```

The root remains unchoked because the external back pressure is above the trial-state critical pressure. The residual scan was fully admissible and monotone across all 65 fixed nodes, with one sign change.

### 5.3 B2-10C — choked gas

```text
initial pipe pressure:              1,000,000.0 Pa
pipe-side root pressure:              736,299.4484 Pa
pipe-side stagnation pressure:        764,639.0812 Pa
B1 critical/discharge pressure:       416,868.8514 Pa
external back pressure:               100,000.0 Pa
pipe-side velocity:                    +64.1704 m/s
Mach:                                    0.2432
```

The restriction is choked while the pipe-side characteristic state remains subsonic. This is a physically permissible architecture: the sonic condition belongs to the unresolved restriction/throat, not necessarily to the upstream pipe port.

The fixed scan found one sign change and one retained root. However, this case is not yet as strong as 10A/10B:

```text
successful scan nodes:               57 / 65
failed low-pressure nodes:            8
residual globally monotone:           false
```

The failed nodes lie well below the retained root and arise from single-phase property admissibility or the existing B1 critical-search guard. They do not invalidate the retained root, but the 65-node scan is not a proof of global uniqueness.

---

## 6. Restriction reaction interpretation

All retained roots have

$$
R_w<0.
$$

With downstream-positive convention, the unresolved restriction therefore exerts an upstream-directed net force on the fluid. The fluid exerts the equal-and-opposite downstream load on the restriction/support structure.

The magnitude includes the blocked-area pressure contribution when the locked opening fraction is less than one. For the liquid case, the approximately $-247.5$ N reaction is dominated by pressure acting on the closed half of the full pipe cross-section. This is not by itself a failure; it is the force that was hidden when the downstream stream port was directly identified with the upstream pipe face.

The reaction must remain a separate, auditable ledger quantity. It must not be silently added to or removed from the pipe Euler flux.

---

## 7. Current model classification

```text
old B2 direct momentum mapping:
  structurally inconsistent with locked small-drop wave sign

A1 characteristic architecture:
  exact closed identity retained                     PASS
  exact zero-drop identity retained                  PASS
  positive-outward root for B2-10A                  PASS
  positive-outward root for B2-10B                  PASS
  positive-outward subsonic root for B2-10C         PASS
  B1 law changed                                     NO
  Contract-ready                                     NOT YET
  finite-pipe verified                               NO
  physical validation                                NO
```

The A1 diagnostic is strong evidence that a characteristic-compatible pipe port can remove the deterministic reverse-velocity blocker without changing B1. It is not yet evidence that the complete time-dependent A1 boundary is unique, robust or physically validated.

---

## 8. Required next gate before Contract revision

The next model-review increment is fixed as follows.

### 8.1 Root robustness

For each B2-10 family, repeat the root analysis with independently varied numerical resolution:

```text
pressure scan nodes:      65 / 257 / 1025
quadrature order:         16 / 32 / 64
root refinement:          fixed bracketed method
```

Require:

```text
same admissible root branch
stable p_P, u_P, m_dot and Mach
no additional admissible sign-change bracket
nonzero local residual slope at the root
```

For B2-10C, define and report the connected admissible pressure interval containing the retained root rather than scanning blindly through invalid single-phase states.

### 8.2 Port and energy closure

At every retained root, explicitly verify:

```text
rho_P*u_P*A == B1 m_dot
rho_P*u_P*h0_P*A == B1 energy transfer
Pi_E - Pi_P - R_w == 0
single-phase identity rho*xv == 0
```

### 8.3 Shadow one-step coupling

Only after the root robustness gate passes, construct a diagnostic-only A1 boundary hook and run one actual FvmSolver step for B2-10A/B/C. The required evidence is:

```text
positive or zero outward boundary velocity
no reverse-flow Guard
mass / energy conservative update
momentum update from the pipe-side Euler port
separate restriction-reaction ledger
no production or Contract modification
```

No full finite-pipe horizon, mesh matrix or CFL matrix is authorized before this one-step shadow gate.
