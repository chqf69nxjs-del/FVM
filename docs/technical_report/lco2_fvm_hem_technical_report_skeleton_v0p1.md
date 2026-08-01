# 液化CO₂配管過渡解析に向けた一次元有限体積HEMモデルの段階的検証

## ― 液相から二相への遷移、数値感度、音速評価限界および物理流出境界への展開 ―

```text
Draft version:                 v0.1-skeleton
Scope:                         Stage 1〜Gate 8完了、Gate 9契約準備まで
Full prose status:             NOT STARTED
Quantitative claim audit:      REQUIRED
Physical validation:           NOT ESTABLISHED
Design-use acceptance:         NOT APPROVED
```

---

# 要旨

<!--
Draft last.
Required elements:
1. background and objective
2. conservative FVM / pure-CO2 HEM path
3. raw crossing + projection + fixed continuation
4. Gate 8 non-monotone outcome matrix
5. acoustic refusal
6. current limitations and next work
Target: 400〜600 Japanese characters.
Do not claim physical validation or design use.
-->

[本文未執筆]

**キーワード：** 液化CO₂、有限体積法、均質平衡モデル、配管減圧、相遷移、
数値感度、二相音速、Rusanov流束

---

# 1. 緒言

## 1.1 背景

<!-- Source: application strategy + public literature. -->

[本文未執筆]

## 1.2 液化CO₂配管過渡解析の技術的課題

<!--
Cover real-fluid nonlinearity, saturation crossing, acoustic branch differences,
numerical diffusion, HEM assumptions, and boundary-model dependence.
-->

[本文未執筆]

## 1.3 本検討の目的

[本文未執筆]

## 1.4 本報告書の対象範囲

<!-- Insert T01 authorized / prohibited claims. -->

[本文未執筆]

## 1.5 本報告書の構成

[本文未執筆]

---

# 2. 解析対象および支配方程式

## 2.1 解析対象

<!-- Define common 1-D pipe and separate the Gate 8 fixed case from future U3. -->

[本文未執筆]

## 2.2 保存変数

\[
\mathbf{U}=
\begin{bmatrix}
\rho & \rho u & \rho E & \rho q
\end{bmatrix}^{\mathsf{T}}
\]

<!-- Insert T02. -->

[本文未執筆]

## 2.3 保存則

\[
\frac{\partial \mathbf{U}}{\partial t}
+
\frac{\partial \mathbf{F}(\mathbf{U})}{\partial x}
=
\mathbf{S}
\]

[本文未執筆]

## 2.4 HEMの基本仮定

[本文未執筆]

## 2.5 物理項と簡略化

<!-- Insert T03. Explicitly state friction/heat/gravity disabled in Gate 8. -->

[本文未執筆]

---

# 3. 熱力学モデルと相状態処理

## 3.1 純CO₂実在流体EOS

[本文未執筆]

## 3.2 相状態分類

[本文未執筆]

## 3.3 平衡品質と飽和margin

\[
q_e=\frac{e-e_f}{e_g-e_f}
\]

\[
q_v=\frac{v-v_f}{v_g-v_f}
\]

[本文未執筆]

## 3.4 ボイド率

[本文未執筆]

## 3.5 Quality projection

<!-- Insert F03. Distinguish raw rho/e crossing from rho*q synchronization. -->

[本文未執筆]

## 3.6 Mixed accepted-state evaluation

[本文未執筆]

## 3.7 音速評価とguard

<!-- Insert F04 and T04. -->

[本文未執筆]

---

# 4. 数値解析手法

## 4.1 有限体積離散化

\[
\mathbf{U}_i^{n+1}
=
\mathbf{U}_i^n
-
\frac{\Delta t}{\Delta x}
\left(
\mathbf{F}_{i+1/2}-\mathbf{F}_{i-1/2}
\right)
+
\Delta t\mathbf{S}_i
\]

[本文未執筆]

## 4.2 Rusanov flux

\[
\mathbf{F}_{i+1/2}
=
\frac{\mathbf{F}_L+\mathbf{F}_R}{2}
-
\frac{a_{\max}}{2}
\left(
\mathbf{U}_R-\mathbf{U}_L
\right)
\]

<!-- Insert F05. -->

[本文未執筆]

## 4.3 CFL時間刻み

\[
\Delta t
=
\mathrm{CFL}
\frac{\Delta x}{\max_i(|u_i|+c_i)}
\]

[本文未執筆]

## 4.4 境界条件

<!-- Insert T05. -->

[本文未執筆]

## 4.5 Conservative and phase budgets

[本文未執筆]

## 4.6 再現性、CIおよびtraceability

[本文未執筆]

---

# 5. 段階的検証戦略

## 5.1 Verification hierarchy

<!-- Insert F06 and T06. -->

[本文未執筆]

## 5.2 Stage 1〜6の位置づけ

[本文未執筆]

## 5.3 Stage 7前半の位置づけ

[本文未執筆]

## 5.4 Gate 3〜8の位置づけ

[本文未執筆]

## 5.5 Gate 9準備と二つの開発トラック

[本文未執筆]

---

# 6. 基礎検証結果

## 6.1 Backend traceabilityとuniform-state preservation

[本文未執筆]

## 6.2 Small-amplitude incident wave

[本文未執筆]

## 6.3 Incident-wave mesh／CFL observation

[本文未執筆]

## 6.4 Rigid-wall reflection

[本文未執筆]

## 6.5 Fixed-pressure reflection

[本文未執筆]

## 6.6 Controlled pressure ramp

[本文未執筆]

## 6.7 Single-phase internal-valve operation

<!-- Insert F07 and T07. -->

[本文未執筆]

## 6.8 基礎検証の小括

<!-- State that these are software/numerical controls, not physical validation. -->

[本文未執筆]

---

# 7. 液相から二相への遷移検証

## 7.1 Crossing specification and event classification

[本文未執筆]

## 7.2 Mixed liquid／open-two-phase EOS

[本文未執筆]

## 7.3 Liquid state-pair property survey

[本文未執筆]

## 7.4 Actual one-step raw FVM crossing

[本文未執筆]

## 7.5 Projected crossing and accepted-state recovery

[本文未執筆]

## 7.6 Second-projection no-op and vapor budget

[本文未執筆]

## 7.7 Frozen Case A／Case B verification pair

<!-- Insert F08 and T08. -->

[本文未執筆]

## 7.8 遷移検証の小括

<!-- Explicitly exclude physical nucleation validation. -->

[本文未執筆]

---

# 8. 配管減圧解析への拡張

## 8.1 Minimal pipeline-depressurization specification

[本文未執筆]

## 8.2 Prescribed-subcooled outlet boundary

[本文未執筆]

## 8.3 5→2／3／4 MPa first-crossing matrix

<!-- Insert F09 and T09. -->

[本文未執筆]

## 8.4 4 MPa subthreshold forensic review

[本文未執筆]

## 8.5 Mesh sensitivity

[本文未執筆]

## 8.6 First-crossing CFL sensitivity

<!-- Insert F10 and T10. -->

[本文未執筆]

## 8.7 Cross-runtime numeric equivalence

[本文未執筆]

## 8.8 配管減圧crossingの小括

[本文未執筆]

---

# 9. Post-crossing挙動とphase chatter

## 9.1 Gate 6固定continuation

[本文未執筆]

## 9.2 T1〜T4におけるopen-two-phase region

<!-- Insert F11 and T11. -->

[本文未執筆]

## 9.3 Quality、void fraction、vapor inventory

[本文未執筆]

## 9.4 Conservative and vapor-budget evidence

[本文未執筆]

## 9.5 Cell 29／30／31 phase history

[本文未執筆]

## 9.6 Saturation-margin、acoustic branch、projection correlation

<!-- Insert F12 and T12. -->

[本文未執筆]

## 9.7 Gate 7 classification

[本文未執筆]

## 9.8 Post-crossing固定列の小括

<!-- Do not approve physical front speed or root cause. -->

[本文未執筆]

---

# 10. Gate 8 Post-crossing CFL感度

## 10.1 Gate 8の目的と固定条件

[本文未執筆]

## 10.2 CFL 0.10 exact replay

[本文未執筆]

## 10.3 CFL 0.05 formal guard

[本文未執筆]

## 10.4 CFL 0.025 accepted crossing

[本文未執筆]

## 10.5 CFL 0.025 acoustic refusal

[本文未執筆]

## 10.6 Formal outcome matrix

<!-- Insert F13 and T13. -->

[本文未執筆]

## 10.7 Cross-CFL quantitative evidence

<!-- Insert selected F14 panels. -->

[本文未執筆]

## 10.8 Gate 8 classification and approval boundary

[本文未執筆]

## 10.9 Gate 8の小括

<!-- Gate execution complete, comparability not established. -->

[本文未執筆]

---

# 11. 公知文献との比較

## 11.1 文献調査の目的と方法

[本文未執筆]

## 11.2 CO₂配管減圧と音速不連続

[本文未執筆]

## 11.3 HEMとhomogeneous relaxation

[本文未執筆]

## 11.4 Two-fluid non-equilibrium modelling

[本文未執筆]

## 11.5 Relaxation hierarchy and subcharacteristic condition

[本文未執筆]

## 11.6 Roe、MUSTA、central-upwind、WENO、preconditioning

[本文未執筆]

## 11.7 Positivity／hyperbolicity／pressure-equilibrium preservation

[本文未執筆]

## 11.8 本プロジェクトへの示唆

<!-- Insert F15 and T14. -->

[本文未執筆]

## 11.9 文献比較の小括

<!-- Literature supports diagnosis and later comparison, not immediate baseline changes. -->

[本文未執筆]

---

# 12. 現在の適用限界

## 12.1 数値的限界

[本文未執筆]

## 12.2 熱力学的限界

[本文未執筆]

## 12.3 音響的限界

[本文未執筆]

## 12.4 境界条件の限界

[本文未執筆]

## 12.5 Pipeline physicsの限界

[本文未執筆]

## 12.6 Physical validation／design useの限界

<!-- Insert F16 and T15. -->

[本文未執筆]

## 12.7 Applicability statement

[本文未執筆]

---

# 13. 今後の開発ロードマップ

## 13.1 Track N — numerical／model characterization

[本文未執筆]

## 13.2 Gate 9 event-aligned forensic diagnosis

[本文未執筆]

## 13.3 Track A — U3 physical-discharge development

[本文未執筆]

## 13.4 B0／B1／integrated blowdown ladder

[本文未執筆]

## 13.5 Track N／Aの合流条件

<!-- Insert F17 and T16. -->

[本文未執筆]

## 13.6 将来のreport versioning

[本文未執筆]

---

# 14. 結論

<!--
Draft after all chapters.
Required balance:
- established software path
- actual raw crossing and accepted recovery
- fixed continuation
- non-monotone CFL outcomes
- acoustic limitation
- no physical/design approval
- Gate 9 + physical discharge boundary as next work
-->

[本文未執筆]

---

# 参考文献

<!-- Generate from Gate 9 registry and primary DOI records. -->

[未整備]

---

# 付録A　Stage／Gate／Issue／PR／artifact対応表

[未整備]

# 付録B　固定解析条件およびtolerance

[未整備]

# 付録C　Formal outcome／guard dictionary

[未整備]

# 付録D　Approval boundary history

[未整備]

# 付録E　CI／runtime／SHA256 evidence

[未整備]

# 付録F　Annotated literature registry

[未整備]

# 付録G　主要software module map

[未整備]

# 付録H　Artifact／CSV schema and figure regeneration

[未整備]

---

# Draft completion checklist

```text
[ ] every quantitative claim appears in the evidence matrix
[ ] every figure/table appears in the figure-table register
[ ] every figure has source artifact or regeneration recipe
[ ] Stage 1〜6 names and V-ID mapping are verified
[ ] method equations match the reviewed production source
[ ] abstract and conclusion contain no prohibited claim
[ ] physical validation remains false unless explicitly changed by a later gate
[ ] design-use acceptance remains false unless explicitly changed by a later gate
[ ] production activation remains false unless explicitly changed by a later gate
```
