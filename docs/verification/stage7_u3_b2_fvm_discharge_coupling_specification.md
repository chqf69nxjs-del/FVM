# Stage 7 U3 B2 — 単相FVM流出面mappingおよび有限配管coupling仕様

## 1. Status

```text
Issue:                    #135
contract status:          LOCKED_BEFORE_RESULTS
development order:        contract → independent Reference → FVM Adapter → finite-pipe execution
B1 component:             immutable
two-phase discharge:      out of scope
physical validation:      false
design use:               false
production activation:    false
```

本仕様は、accepted U3 B1単相圧縮性・臨界状態componentを、一次元保存形FVM配管の右端面へ接続するための**結果前contract**である。

この増分では、B1が返す質量、運動量stream、エンタルピーtransferを、静圧面力と区別しながらFVM fluxへmappingする。さらに、有限配管内inventoryの減少、累積流出量、および単相圧力波を独立Referenceと比較する。

本仕様は、物理的に妥当性確認済みのCO₂ブローダウン境界を承認するものではない。

---

## 2. Preconditions

B2実装開始前に次が成立していなければならない。

```text
U3 B0:                         accepted
U3 B1:                         accepted
B1 Reference PR:               #131
B1 Adapter PR:                 #133
B1 central-record sync PR:     #134 / MERGED
```

B2では、B1の数式、係数配置、臨界探索、Guardおよびaccepted toleranceを変更しない。

---

## 3. 固定FVM baseline

対象solverは、既存の一次精度保存形FVMである。

```text
module:               src/liquid_gas_transient/solver.py
solver:               FvmSolver
conserved variables:  rho, rho*u, rho*E, rho*xv
numerical flux:       first-order Rusanov
time integration:     explicit forward Euler
left boundary:        reflective
right boundary:       direct external-face flux override
source term:          none
phase change:         none
```

右端流出fluxは、ghost stateから間接的に生成しない。

理由は、B1 contractが、

\[
u_{\mathrm{eff}}=C_d u_{\mathrm{ideal}}
\]

および、

\[
\dot E=\dot m h_0
\]

を同時に保持するためである。このtransfer tupleは、一般には単一のEuler primitive ghost stateへ一意に置換できない。したがって、B1が返すtransferをFVM面fluxへ直接mappingする。

適用順序は、

```text
ghost-state Rusanov flux
→ internal-interface overrides
→ B2 right external-face override
→ boundary-budget recording
→ conservative update
```

とする。

---

## 4. 固定geometry

B1 reference areaと配管断面積を一致させる。

\[
A_{\mathrm{pipe}}
=
A_{\mathrm{ref}}
=
1.0\times10^{-4}\ \mathrm{m^2}
\]

対応する内径は、

\[
D
=
\sqrt{\frac{4A_{\mathrm{pipe}}}{\pi}}
=
0.011283791670955126\ \mathrm{m}
\]

である。

```text
length:             1.0 m
baseline cells:     32
baseline CFL:       0.10
ghost cells:        2 each side
mesh sequence:      16 / 32 / 64
CFL sequence:       0.10 / 0.05 / 0.025
```

摩擦、重力、壁熱伝達、receiver dynamicsは無効とする。

---

## 5. 隣接cellからstagnation stateへの復元

右端内部cellの保存状態から、

\[
u_i=\frac{(\rho u)_i}{\rho_i}
\]

\[
e_i=\frac{(\rho E)_i}{\rho_i}-\frac{u_i^2}{2}
\]

を得る。

同じ \((\rho_i,e_i)\) 状態からCoolPropで、

\[
p_i,\quad T_i,\quad h_i,\quad s_i
\]

を評価する。

停滞エンタルピーと停滞エントロピーは、

\[
h_{0,i}=h_i+\frac{u_i^2}{2}
\]

\[
s_{0,i}=s_i
\]

とする。

その後、CoolPropの \((h,s)\) 入力から、

\[
p_{0,i},\quad T_{0,i}
\]

を復元し、これをB1 componentの上流停滞状態として使用する。

復元後は、enthalpy、entropy、phaseおよび有限性のround-trip checkを行う。

右端cell速度が負方向で、

\[
u_i<-10^{-12}\ \mathrm{m/s}
\]

の場合はreverse flowとして拒否し、reflective fallbackへ黙って置換しない。

---

## 6. B1 discharge stateの採用

### 6.1 非チョーク

\[
p_b>p_*+\varepsilon_p
\]

の場合、B1は背圧 \(p_b\) における単相等エントロピー状態を採用する。

### 6.2 チョーク

\[
p_b\le p_*+\varepsilon_p
\]

の場合、B1は臨界圧力 \(p_*\) の状態を採用する。

チョーク時も外部背圧はdiagnosticとして保持する。ただし、FVM面のopen部分の静圧には臨界圧力を使用し、外部背圧を直接代入しない。

Critical state cacheは、次が完全一致するときだけ使用できる。

```text
stagnation state identity
Cd
property backend and version
B1 source SHA
```

B2 v1ではcritical state interpolationを行わない。

---

## 7. 面積分解

\[
A_{\mathrm{open}}
=
A_{\mathrm{pipe}}f_{\mathrm{open}}
\]

\[
A_{\mathrm{closed}}
=
A_{\mathrm{pipe}}-A_{\mathrm{open}}
\]

とする。

B1のeffective areaは \(A_{\mathrm{open}}\) と同一とする。

open部分にはB1 discharge state圧力 \(p_d\)、closed部分には隣接cell静圧 \(p_i\) を用いる。

---

## 8. Right-face flux mapping

B1が返すtransferを、

\[
\dot m_{\mathrm{B1}}
\]

\[
\dot I_{\mathrm{adv,B1}}
=
\dot m_{\mathrm{B1}}u_{\mathrm{eff}}
\]

\[
\dot E_{\mathrm{B1}}
=
\dot m_{\mathrm{B1}}h_{0,i}
\]

とする。

静圧面力を加えたtotal momentum rateは、

\[
\dot I_{\mathrm{total}}
=
\dot I_{\mathrm{adv,B1}}
+
p_d A_{\mathrm{open}}
+
p_i A_{\mathrm{closed}}
\]

である。

配管断面積あたりのFVM fluxは、

\[
\mathbf{F}_{R}
=
\begin{bmatrix}
\dot m_{\mathrm{B1}}/A_{\mathrm{pipe}}\\[4pt]
\dot I_{\mathrm{total}}/A_{\mathrm{pipe}}\\[4pt]
\dot E_{\mathrm{B1}}/A_{\mathrm{pipe}}\\[4pt]
0
\end{bmatrix}
\]

とする。

### 8.1 Closed identity

\(f_{\mathrm{open}}=0\) では、

\[
\mathbf{F}_{R}
=
\begin{bmatrix}
0\\
p_i\\
0\\
0
\end{bmatrix}
\]

をexactに保持する。

### 8.2 Zero-drop identity

初期速度ゼロかつ \(p_b=p_i\) では、openingが有限でも、

\[
\mathbf{F}_{R}
=
\begin{bmatrix}
0\\
p_i\\
0\\
0
\end{bmatrix}
\]

をexactに保持する。

これにより、mass、advective momentum、energyはzeroであっても、静圧面力はzeroではないことを明示する。

---

## 9. Conservative updateと時間刻み

内部CFL時間刻みに加えて、右端cellから1 stepで除去できるmassおよびenergyをそれぞれ10%以下に制限する。

\[
\Delta t_m
=
0.10
\frac{\rho_i V_i}{\dot m_{\mathrm{B1}}}
\]

\[
\Delta t_E
=
0.10
\frac{(\rho E)_i V_i}{\dot E_{\mathrm{B1}}}
\]

\[
\Delta t
=
\min
\left(
\Delta t_{\mathrm{CFL}},
\Delta t_m,
\Delta t_E,
t_{\mathrm{end}}-t
\right)
\]

とする。

trial update後に、

```text
finite conserved state
rho > 0
e > 0
declared single-phase scope
rho*xv exact zero
```

を確認する。

不成立の場合は、最大12回のdeterministic halvingを行う。12回後も不成立なら、

```text
BOUNDARY_UPDATE_POSITIVITY_FAILURE
```

として停止し、toleranceや物理則を変更しない。

---

## 10. Inventory closure

配管massは、

\[
M_{\mathrm{pipe}}(t)
=
\sum_i \rho_i(t)V_i
\]

累積流出massは、

\[
M_{\mathrm{out}}(t)
=
\sum_n \dot m_n\Delta t_n
\]

とする。

mass residualは、

\[
R_M(t)
=
M_{\mathrm{pipe}}(t)
+
M_{\mathrm{out}}(t)
-
M_{\mathrm{pipe}}(0)
\]

である。

同様に、

\[
E_{\mathrm{pipe}}(t)
=
\sum_i (\rho E)_i(t)V_i
\]

\[
E_{\mathrm{out}}(t)
=
\sum_n \dot E_n\Delta t_n
\]

\[
R_E(t)
=
E_{\mathrm{pipe}}(t)
+
E_{\mathrm{out}}(t)
-
E_{\mathrm{pipe}}(0)
\]

を保持する。

Momentumについては、left／right boundaryのtotal numerical momentum fluxを使用した既存BoundaryBudgetTrackerをauthoritative budgetとする。

右端momentumは別ledgerで、

```text
advective momentum
open-area pressure impulse
closed-area pressure impulse
```

へ分解し、その和がapplied total right-face momentum fluxを再構成することを確認する。

---

## 11. Acoustic reference

Full acoustic horizonは、`LIQUID_SMALL_DROP` caseに限定する。

初期音速を \(c_0\)、pipe lengthを \(L\)、probe位置を \(x\) とすると、直接rarefactionの基準到達時間は、

\[
t_{\mathrm{direct}}
=
\frac{L-x}{c_0}
\]

である。

left rigid wallで反射したwaveのprobe到達時間は、

\[
t_{\mathrm{reflected}}
=
\frac{L+x}{c_0}
\]

とする。

固定probeは、

```text
x/L = 0.25
x/L = 0.50
x/L = 0.75
```

である。

直接rarefactionは、

```text
pressure perturbation: negative
velocity perturbation: positive outward
arrival order: 0.75 → 0.50 → 0.25
```

を満たす必要がある。

Rigid wallでは、

```text
mass flux: exact zero
energy flux: exact zero
pressure reflection: incident pressure perturbationと同符号
velocity reflection: incident velocity perturbationと逆符号
```

を確認する。

これはsingle-phase acoustic verificationであり、実配管の波高Validationではない。

---

## 12. Fixed state families

### LIQUID_SMALL_DROP

```text
p = 5.0 MPa
T = Tsat(p,Q=0)-5 K
u = 0
pb = 4.95 MPa
critical search = false
```

このcaseをinventory、rarefaction、reflection、mesh／CFL matrixへ使用する。

### GAS_UNCHOKED

```text
p = 1.0 MPa
T = 320 K
u = 0
pb = 0.8 MPa
finite-pipe cap = 32 accepted steps
```

### GAS_CHOKED

```text
p = 1.0 MPa
T = 320 K
u = 0
pb = 0.1 MPa
finite-pipe cap = 16 accepted steps
```

Gas finite-pipe casesは、mappingと短時間inventory verificationに限定し、長時間blowdown accuracyを主張しない。

---

## 13. Fixed benchmark matrix

```text
physical rows: 19
Guard rows:     7
total rows:     26
```

Physical rowsは次を含む。

```text
closed liquid and gas wall identities
zero-drop identity
B0 limiting face mapping
unchoked B1 parity
critical-transition mapping
below-critical plateau
area scaling
Cd scaling
one-step conservative update
liquid finite-pipe inventory closure
short gas unchoked / choked coupling
direct rarefaction probe ordering
rigid-wall reflection
fixed mesh / CFL characterization
```

Guard rowsは次を含む。

```text
reverse pressure
reverse adjacent-cell velocity
nonfinite state
single-phase scope failure
stagnation reconstruction failure
positivity failure after 12 halvings
inventory sign/orientation mismatch
```

---

## 14. Independent Reference

B2 Referenceは、FVM Adapter under testから独立して、少なくとも次を構築する。

```text
algebraic face-flux decomposition
one-step finite-volume balance
cumulative mass / energy inventory ledger
linearized acoustic or MOC arrival-time reference
```

共有を禁止するもの：

```text
B2 face-mapping helper
B2 one-step update helper
B2 inventory-ledger helper
B2 acoustic-event helper
```

B1 componentは上流component authorityとして共有可能である。ただし、B2-specific mappingは共有しない。

---

## 15. Acceptance boundary

B2完了時にtrue候補となるのは、

```text
u3_b2_contract_locked
u3_b2_reference_implemented
u3_b2_fvm_adapter_implemented
u3_b2_finite_pipe_execution_complete
u3_b2_verification_benchmark_accepted
single_phase_fvm_discharge_mapping_verified
single_phase_finite_pipe_coupling_verified
```

である。

以下はB2完了後も自動的にはtrueにならない。

```text
physical_discharge_boundary_approved
two_phase_critical_discharge_accuracy_approved
integrated_blowdown_model_approved
physical_validation
design_use_acceptance
production_hem_activation_approved
```

---

## 16. Out of scope

```text
two-phase equilibrium choking
HNE / non-equilibrium flashing
metastability / nucleation
receiver pressure and temperature dynamics
friction
gravity / elevation
wall heat transfer
solid CO2
real valve / rupture geometry validation
experimental or field physical validation
design sizing
production activation
```

---

## 17. Planned increment order

```text
1. contract-only increment
2. independent face / one-step / inventory / acoustic Reference
3. FVM discharge-face Adapter
4. finite-pipe coupled authoritative execution
5. closeout and technical-report synchronization
```

単相coupling benchmarkがacceptedとなる前に、two-phase critical-discharge workを開始しない。
