# Stage 7 U3 B2 — 独立FVM流出coupling Reference

## 1. Status

```text
Issue:                              #135
parent contract:                    LOCKED / main
contract PR / merge:                #136 / cffc32c257f58942e602614d69b6dad49bd1add8
increment:                          independent Reference
B1 component law:                   immutable upstream authority
B2 FVM Adapter:                     not implemented
finite-pipe authoritative execution: not complete
physical validation:                false
design use:                         false
production activation:              false
```

本増分は、U3 B1でacceptedとなった単相圧縮性・臨界状態componentを、将来のFVM右端面Adapterと比較するための**独立Reference**を実装する。

このReferenceはproduction solverを変更せず、将来のB2 Adapter moduleをimportしない。また、B2-specificなface mapping、one-step balance、inventory ledger、probe interpolationおよびacoustic event helperをAdapterと共有しない。

---

## 2. Reference層

Referenceは次の6層を分離して構築する。

```text
R1  adjacent-cell static / stagnation reconstruction
R2  accepted B1 transfer → right-face flux algebra
R3  one-step finite-volume conservative balance
R4  cumulative mass / energy / momentum ledger
R5  linear-acoustic / MOC arrival-time targets
R6  fixed-mesh probe interpolation and explicit Guards
```

### 2.1 B1との境界

B1は次を上流component authorityとして提供する。

```text
unchoked / choked classification
retained discharge-state pressure
critical pressure and pressure ratio
effective velocity and mass flux
mass transfer
advective momentum-stream transfer
stagnation-enthalpy transfer
```

B2 Referenceは、B1の式、係数配置、4097-node探索、golden-section refinementまたはGuardを変更しない。

一方、次はB2 Reference自身が独立に実装する。

```text
static pressure-force decomposition
per-pipe-area FVM flux mapping
one-step conservative update
inventory orientation and quadrature
probe interpolation
acoustic arrival references
```

---

## 3. Adjacent-cellから停滞状態への復元

右端隣接cellの保存状態を、

$$
\rho_i,\qquad
u_i=\frac{(\rho u)_i}{\rho_i},\qquad
e_i=\frac{(\rho E)_i}{\rho_i}-\frac{u_i^2}{2}
$$

とする。

CoolPropの`Dmass,Umass`経路でstatic stateを復元し、

$$
h_{0,i}=h_i+\frac{u_i^2}{2},
\qquad
s_{0,i}=s_i
$$

を構築する。その後、`Hmass,Smass`経路から、

$$
p_{0,i},\qquad T_{0,i}
$$

を復元する。

H/S round tripはcontractで固定された絶対許容差を満たさなければならない。逆向き隣接速度、非有限状態、単相scope外状態およびproperty inversion failureは、flux・ledger・stateを更新する前にGuardする。

---

## 4. 右端面flux Reference

開口面積と閉止面積を、

$$
A_{\mathrm{open}}=A_{\mathrm{pipe}}f_{\mathrm{open}},
\qquad
A_{\mathrm{closed}}=A_{\mathrm{pipe}}-A_{\mathrm{open}}
$$

とする。

B1が返すtransferを、

$$
\dot m_{B1},
\qquad
\dot I_{\mathrm{adv},B1},
\qquad
\dot E_{B1}
$$

とする。Referenceは静圧面力を独立に追加し、

$$
\dot I_{\mathrm{open},p}=p_d A_{\mathrm{open}},
$$

$$
\dot I_{\mathrm{closed},p}=p_i A_{\mathrm{closed}},
$$

$$
\dot I_{\mathrm{total}}
=
\dot I_{\mathrm{adv},B1}
+
\dot I_{\mathrm{open},p}
+
\dot I_{\mathrm{closed},p}
$$

とする。

FVM面fluxは、

$$
\mathbf F_R
=
\begin{bmatrix}
\dot m_{B1}/A_{\mathrm{pipe}}\\
\dot I_{\mathrm{total}}/A_{\mathrm{pipe}}\\
\dot E_{B1}/A_{\mathrm{pipe}}\\
0
\end{bmatrix}
$$

である。

Closedおよびzero-dropでは、stream transferをexact zeroとし、

$$
\mathbf F_R=
\begin{bmatrix}
0\\p_i\\0\\0
\end{bmatrix}
$$

をexact identityとして保持する。

---

## 5. One-step balance

固定32-cell / CFL 0.10ケースについて、既存CFL制限に加えて、右端cellのmassおよびenergy removal fractionを用いる。

$$
\Delta t
=
\min
\left(
\Delta t_{\mathrm{CFL}},
\Delta t_M,
\Delta t_E
\right)
$$

右端cell更新は、

$$
\mathbf U_N^{n+1}
=
\mathbf U_N^n
-
\frac{\Delta t}{\Delta x}
\left(
\mathbf F_R-\mathbf F_{N-1/2}
\right)
$$

でReference計算する。

配管全体について、

$$
M_{\mathrm{pipe}}^{n+1}
+
\dot m_R\Delta t
-
M_{\mathrm{pipe}}^n
=R_M
$$

$$
E_{\mathrm{pipe}}^{n+1}
+
\dot E_R\Delta t
-
E_{\mathrm{pipe}}^n
=R_E
$$

を確認する。

Momentumは、left rigid-wall pressure impulseとright total momentum impulseを分離して記録する。

---

## 6. Acoustic / MOC Reference

`LIQUID_SMALL_DROP`の初期音速を$c_0$、配管長を$L$、requested probe位置を$x_p$とする。

Direct rarefactionの基準到達時刻は、

$$
t_{\mathrm{direct}}
=
\frac{L-x_p}{c_0}
$$

left rigid-wallで反射した波の基準到達時刻は、

$$
t_{\mathrm{reflected}}
=
\frac{L+x_p}{c_0}
$$

とする。

```text
direct:
  Delta p < 0
  Delta u > 0
  order 0.75 → 0.50 → 0.25

reflected:
  Delta p < 0
  Delta u < 0
  order 0.25 → 0.50 → 0.75
```

これは単相software／numerical verification用のarrival targetであり、実測wave amplitudeのphysical validationではない。

---

## 7. Probe interpolation

Requested probeは、

```text
x/L = 0.25 / 0.50 / 0.75
```

で固定する。

固定16／32／64-cell meshについて、requested probeを挟む隣接internal cell centerを$x_j,x_{j+1}$とし、

$$
\lambda
=
\frac{x_p-x_j}{x_{j+1}-x_j}
$$

$$
q_p
=
(1-\lambda)q_j+\lambda q_{j+1}
$$

でpressureとaxial velocityを別々に補間する。

Arrival-time Referenceにはrequested probe座標を使用し、nearest-cell、distance tieまたはeffective sampled coordinateへ置換しない。

---

## 8. Fixed outcomes

```text
physical rows:  19
Guard rows:      7
total rows:     26
```

Referenceは26行すべてについてformal targetを構築する。ただし、finite-pipe caseのReference行は、将来のAdapter実行に対するface、balance、ledger、arrival targetであり、finite-pipe execution completeを意味しない。

---

## 9. Evidence package

Authoritative workflowは少なくとも次を保持する。

```text
summary.json
benchmark_contract.json
event_provenance_contract.json
state_family_properties.csv
face_state_and_choking_adoption.csv
face_flux_reference.csv
one_step_balance_reference.csv
inventory_ledger_reference.csv
acoustic_arrival_reference.csv
probe_mapping_reference.csv
mesh_cfl_reference.csv
guard_outcomes.csv
locked_checks.csv
face_flux_reference.png
acoustic_arrival_reference.png
one_step_balance_reference.png
report.md
artifact_sha256.txt
dedicated / related / full-repository JUnit
```

Artifactはsource head SHA、checkout SHA、workflow run、CoolProp version、B1 Reference source SHA、parent／extension contract SHA256を保持する。

---

## 10. Approval boundary

Reference PRでtrue候補となるのは、

```text
u3_b2_contract_locked = true
u3_b2_reference_implemented = true
```

のみである。

以下はfalseのまま維持する。

```text
u3_b2_fvm_adapter_implemented = false
u3_b2_finite_pipe_execution_complete = false
u3_b2_verification_benchmark_accepted = false
single_phase_fvm_discharge_mapping_verified = false
single_phase_finite_pipe_coupling_verified = false

physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
