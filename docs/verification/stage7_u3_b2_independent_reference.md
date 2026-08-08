# Stage 7 U3 B2 — 独立FVM流出coupling Reference

## 1. Status

```text
Issue:                              #135
parent contract:                    LOCKED / main
contract PR / merge:                #136 / cffc32c257f58942e602614d69b6dad49bd1add8
Reference implementation:           THIS INCREMENT
FVM discharge Adapter:              NOT IMPLEMENTED
finite-pipe coupled execution:       NOT PERFORMED
B2 verification benchmark accepted: false
physical validation:                false
design use:                          false
production activation:              false
```

本増分は、U3 B2 contractで結果前に固定した比較基準を、将来のFVM Adapterとhelperを共有しない独立経路で実装する。

Accepted U3 B1 componentは、上流停滞状態から単相流出transferを返すauthorityとしてのみ利用する。B2固有のstatic-pressure-force mapping、one-step balance、inventory ledgerおよびacoustic referenceは、本Reference内で新規かつ独立に構築する。

---

## 2. Referenceの4層

### 2.1 Face-flux algebra

右端面のoutward-positive conventionについて、B1から得るstream transferを、静圧面力と分けて保持する。

$$
A_{\mathrm{open}}=A_{\mathrm{pipe}}f_{\mathrm{open}}
$$

$$
A_{\mathrm{closed}}=A_{\mathrm{pipe}}-A_{\mathrm{open}}
$$

$$
\dot I_{\mathrm{total}}
=
\dot m u_{\mathrm{eff}}
+p_d A_{\mathrm{open}}
+p_i A_{\mathrm{closed}}
$$

したがって、FVMへ渡す単位面積当たりfluxは、

$$
\mathbf F_R=
\begin{bmatrix}
\dot m/A_{\mathrm{pipe}}\\
\dot I_{\mathrm{total}}/A_{\mathrm{pipe}}\\
\dot E/A_{\mathrm{pipe}}\\
0
\end{bmatrix}
$$

である。

Closedおよびzero-dropでは、stream transferをexact zeroとしながら、

$$
\mathbf F_R=
\begin{bmatrix}
0\\p_i\\0\\0
\end{bmatrix}
$$

を保持する。

### 2.2 One-step finite-volume balance

一様な32-cell配管の最終cellについて、左面を同一静止状態のEuler flux、右面を上記B2 Reference fluxとして、

$$
\mathbf U_N^{n+1}
=
\mathbf U_N^n
-
\frac{\Delta t}{\Delta x}
\left(
\mathbf F_R-\mathbf F_L
\right)
$$

を直接評価する。

時間刻みは、既存CFL制約、mass-removal制約およびenergy-removal制約の最小値とする。

### 2.3 Inventory ledger

有限配管Adapterを実行せず、離散積算規則そのものを独立に固定・検証する。

$$
M_{\mathrm{pipe}}^n+M_{\mathrm{out}}^n-M_{\mathrm{pipe}}^0=R_M^n
$$

$$
E_{\mathrm{pipe}}^n+E_{\mathrm{out}}^n-E_{\mathrm{pipe}}^0=R_E^n
$$

Momentumは、左端pressure impulseと、右端のadvective／open-pressure／closed-pressure impulseを分離する。

このledgerは、将来のcoupled solver resultそのものではない。Adapterが生成するhistoryを比較するための符号・離散積算Referenceである。

### 2.4 Linear acoustic / MOC arrival reference

`LIQUID_SMALL_DROP`について、初期音速$c_0$とrequested probe位置$x_p$を用い、

$$
t_{\mathrm{direct}}=
\frac{L-x_p}{c_0}
$$

$$
t_{\mathrm{reflected}}=
\frac{L+x_p}{c_0}
$$

を計算する。

固定probeは、

```text
x/L = 0.25 / 0.50 / 0.75
```

である。16／32／64-cell meshではprobeがcell centerと一致しないため、同一accepted stateの隣接internal cell-center間でprimitive pressureとaxial velocityを線形補間する。

Arrival referenceにはcell centerではなく、requested probe座標を使用する。

---

## 3. Independence boundary

```text
accepted B1 component used as upstream authority: true
Reference imports future B2 Adapter:               false
shared B2 face-mapping helper:                     false
shared B2 one-step helper:                         false
shared B2 inventory-ledger helper:                 false
shared B2 acoustic helper:                         false
production FVM solver modified:                    false
```

B1のcritical-state探索、係数配置またはGuardは変更しない。

---

## 4. Fixed Reference outputs

```text
summary.json
runtime_and_git_provenance.json
benchmark_contract.json
event_provenance_contract.json
b1_component_contract.json
reference_case_matrix.csv
face_state_and_choking_adoption.csv
face_flux_decomposition.csv
one_step_conservative_update_reference.csv
cumulative_discharge_and_inventory_reference.csv
momentum_impulse_reference.csv
acoustic_arrival_reference.csv
guard_outcomes.csv
locked_checks.csv
face_flux_reference.png
acoustic_arrival_reference.png
report.md
artifact_sha256.txt
```

Reference artifactは、Adapter parityやfinite-pipe resultを捏造しない。該当caseは、比較targetが定義済みであることだけを記録する。

---

## 5. Promotion boundary

Authoritative CI、review、merge後にtrueへできるのは、

```text
u3_b2_contract_locked = true
u3_b2_reference_implemented = true
```

である。

次はfalseのまま維持する。

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

本Referenceは、実配管の流出量、減圧時間、最低圧力または設計口径の妥当性を承認しない。

---

## 6. Next controlled increment

Reference merge後、B2-specific helperを共有しないFVM discharge-face Adapterを実装する。

その後にのみ、finite-pipe coupled execution、inventory closure、rarefaction event、mesh/CFL matrixおよびReference–Adapter comparisonへ進む。
