# Stage 7 U3 B2 — characteristic upstream-port root robustness analysis

## 1. Status and claim boundary

```text
analysis type:                     MODEL_REVIEW_ONLY
source main:                       aa108961762c9ae70ee9940405024eb5188064b8
final diagnostic source:           060c6da295ecf7dec8c1497877c1aa2f93de2b36
workflow run / job:                31453380049 / 93662105216
Artifact ID:                       9087227632
Artifact ZIP SHA256:               b5ef2d245a247ac0ab81392bf5364b250697ba06e9fde16ce01cfc8608b88660
B2 Contract modification:          none
B1 modification:                   none
Adapter modification:              none
solver modification:               none
accepted tolerance modification:   none
formal finite-pipe promotion:      none
physical validation:               false
design use:                        false
production activation:             false
```

This note records the completed robustness gate for the A1 characteristic-compatible upstream pipe port. It does not select A1 as the production boundary law and does not revise the locked B2 v1 Contract.

---

## 2. Final gate result

```text
root_robustness_gate_passed:        true
cases:                              B2-10A / B2-10B / B2-10C
quadrature orders:                  16 / 32 / 64
root rows:                          9
all roots subsonic:                 true
all fixed root residuals passed:    true
all local residual slopes nonzero:  true
all momentum ledgers closed:        true
all energy ports closed:            true
all h0 round trips passed:          true
```

The retained pressure, velocity, mass-flow and Mach roots were unchanged to displayed precision across quadrature orders 16, 32 and 64.

| Case | retained $p_P$ [Pa] | retained $u_P$ [m/s] | Mach | retained $\dot m$ [kg/s] |
|---|---:|---:|---:|---:|
| B2-10A LIQUID_SMALL_DROP | 4,950,034.467925421 | 0.122540099459384 | 0.000263064614 | 0.0107153799923 |
| B2-10B GAS_UNCHOKED | 850,854.977953713 | 34.1510280160343 | 0.127629029306 | 0.0518564363562 |
| B2-10C GAS_CHOKED | 736,299.448361388 | 64.1703819470500 | 0.243229430430 | 0.0870294938629 |

---

## 3. Numerical robustness

### B2-10A

```text
pressure spread across quadrature:       0.0 Pa
velocity relative spread:                2.604772813045796e-15
mass-rate relative spread:               2.590255841183863e-15
Mach spread:                             6.505213034913027e-19
local residual slope:                   -1.3075930052138e-4 kg/(s Pa)
```

### B2-10B

```text
pressure spread across quadrature:       0.0 Pa
velocity relative spread:                4.161179191598521e-16
mass-rate relative spread:               5.352387777862121e-16
Mach spread:                             5.551115123125783e-17
local residual slope:                   -6.9717474238e-7 kg/(s Pa)
```

### B2-10C

```text
pressure spread across quadrature:       0.0 Pa
velocity relative spread:                0.0
mass-rate relative spread:               0.0
Mach spread:                             0.0
local residual slope:                   -3.6502100794e-7 kg/(s Pa)
```

The negative, nonzero local slopes show that each retained root is locally isolated rather than a flat accidental crossing.

---

## 4. Choked connected subsonic branch

The B2-10C diagnostic also scanned the connected admissible subsonic interval:

```text
pressure interval:                      1,000,000 Pa → 339,062.5 Pa
scan nodes:                             33
all nodes admissible:                   true
all nodes subsonic:                     true
maximum Mach:                           0.8863043038644052
residual monotone as pressure drops:    true
sign-change count:                      1
unique root branch passed:              true
```

This strengthens the earlier 65-node exploratory result. The previous failed low-pressure nodes were outside this connected admissible subsonic interval and did not represent competing roots on the retained branch.

---

## 5. Energy closure and locked tolerance use

The pipe and B1 energy ports satisfy

$$
\dot E_P-\dot E_{B1}
=
h_{0,P}(\dot m_P-\dot m_{B1})
+
\dot m_{B1}(h_{0,P}-h_{0,B1}).
$$

The final gate used only:

```text
fixed mass-root residual tolerance:                 1e-8 kg/s
locked B2 h0 round-trip absolute tolerance:         1e-5 J/kg
scale-based floating-point roundoff allowance
```

No new result-driven tolerance was introduced.

Maximum retained values were:

| Case | max $|\Delta h_0|$ [J/kg] | locked limit [J/kg] | max $|\Delta \dot E|$ [W] |
|---|---:|---:|---:|
| B2-10A | 5.0204107538e-8 | 1.0e-5 | 2.3281379526e-5 |
| B2-10B | 1.1641532183e-10 | 1.0e-5 | 1.6279846022e-6 |
| B2-10C | 5.8207660913e-11 | 1.0e-5 | 2.2877866286e-6 |

All energy rows passed the fixed mass-root plus locked h0 round-trip ledger.

---

## 6. Diagnostic-method corrections retained in history

Two earlier runs failed before the final successful run:

```text
31452306190:
  fixed absolute 1e-6 W energy threshold was inconsistent with a finite,
  already bounded mass-root residual

31452854808:
  energy consistency was compared against pure floating-point roundoff and
  omitted the already locked B2 h0 round-trip tolerance
```

These were diagnostic acceptance-definition errors, not changes in the A1 physical root. The final run retained the same roots and used the pre-existing locked Contract tolerance.

---

## 7. Current model disposition

```text
old direct B2 momentum mapping:          not promotable for finite-pipe use
A1 characteristic root existence:       supported for B2-10A/B/C
A1 root local isolation:                 supported
A1 quadrature robustness:                supported
A1 connected choked root branch:         supported
A1 actual FvmSolver one-step coupling:   not yet executed
A1 Contract readiness:                   not established
finite-pipe verification:                false
physical validation:                     false
```

The next authorized model-review gate is a diagnostic-only A1 shadow one-step coupling on the actual `FvmSolver` for B2-10A, B2-10B and B2-10C. No full horizon, mesh sequence, CFL sequence, Contract revision or formal promotion is authorized before that gate.
