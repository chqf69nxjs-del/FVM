# 液化CO₂配管過渡解析に向けた一次元有限体積HEMモデルの段階的検証

## ― 液相から二相への遷移、数値感度、単相臨界流出componentおよびFVM境界couplingへの展開 ―

```text
Draft version:                 v0.4-skeleton
Scope:                         Stage 1〜Gate 9、U3 B0、U3 B1
Chapter 12 prose:              INTEGRATED
Full prose status:             NOT COMPLETE
Physical validation:           NOT ESTABLISHED
Design-use acceptance:         NOT APPROVED
```

# 要旨

<!-- Draft last. Must include Gate 9, B0/B1 and explicit approval limits. -->

[本文未執筆]

# 1. 緒言

## 1.1 背景

[本文未執筆]

## 1.2 技術的課題

[本文未執筆]

## 1.3 目的

[本文未執筆]

## 1.4 対象範囲とclaim boundary

[本文未執筆]

## 1.5 報告書の構成

[本文未執筆]

---

# 2. 解析対象および支配方程式

## 2.1 解析対象

[本文未執筆]

## 2.2 保存変数

[本文未執筆]

## 2.3 保存則

[本文未執筆]

## 2.4 HEMの基本仮定

[本文未執筆]

## 2.5 物理項と簡略化

[本文未執筆]

## 2.6 sign convention

[本文未執筆]

---

# 3. 熱力学モデルと相状態処理

## 3.1 純CO₂実在流体EOS

[本文未執筆]

## 3.2 相状態分類

[本文未執筆]

## 3.3 平衡品質と飽和margin

[本文未執筆]

## 3.4 Quality projection

[本文未執筆]

## 3.5 Mixed accepted-state

[本文未執筆]

## 3.6 音速評価とguard

[本文未執筆]

---

# 4. 数値解析手法

## 4.1 有限体積離散化

[本文未執筆]

## 4.2 Rusanov flux

[本文未執筆]

## 4.3 CFL時間刻み

[本文未執筆]

## 4.4 境界条件

[本文未執筆]

## 4.5 Conservative / phase budgets

[本文未執筆]

## 4.6 CIとtraceability

[本文未執筆]

---

# 5. 段階的検証戦略

## 5.1 Verification hierarchy

[本文未執筆]

## 5.2 Stage 1〜6

[本文未執筆]

## 5.3 Stage 7 crossing path

[本文未執筆]

## 5.4 Gate 3〜9

[本文未執筆]

## 5.5 Application Track A / U3 ladder

[本文未執筆]

---

# 6. 基礎検証結果

## 6.1 Backend / uniform state

[本文未執筆]

## 6.2 Incident wave

[本文未執筆]

## 6.3 Reflection

[本文未執筆]

## 6.4 Pressure ramp

[本文未執筆]

## 6.5 Internal valve

[本文未執筆]

## 6.6 小括

[本文未執筆]

---

# 7. 液相から二相への遷移検証

## 7.1 Crossing contract

[本文未執筆]

## 7.2 Raw crossing

[本文未執筆]

## 7.3 Projection and accepted recovery

[本文未執筆]

## 7.4 Second no-op / vapor budget

[本文未執筆]

## 7.5 Case A/B

[本文未執筆]

## 7.6 小括

[本文未執筆]

---

# 8. 配管減圧解析への拡張

## 8.1 Minimal pipeline specification

[本文未執筆]

## 8.2 Prescribed outlet

[本文未執筆]

## 8.3 2/3/4 MPa matrix

[本文未執筆]

## 8.4 Mesh / CFL sensitivity

[本文未執筆]

## 8.5 Cross-runtime

[本文未執筆]

## 8.6 小括

[本文未執筆]

---

# 9. Post-crossing挙動とphase chatter

## 9.1 Fixed continuation

[本文未執筆]

## 9.2 T1〜T4 region

[本文未執筆]

## 9.3 Budget

[本文未執筆]

## 9.4 Cell 29〜31 history

[本文未執筆]

## 9.5 Correlation classification

[本文未執筆]

## 9.6 小括

[本文未執筆]

---

# 10. Gate 8–9 CFL感度とcrossing-depth診断

## 10.1 Gate 8 matrix

[本文未執筆]

## 10.2 Gate 9 execution

[本文未執筆]

## 10.3 Temporal/correlation classification

[本文未執筆]

## 10.4 Crossing-depth limits

[本文未執筆]

## 10.5 Approval boundary

[本文未執筆]

## 10.6 小括

[本文未執筆]

---

# 11. U3 B0 単相液体流出component benchmark

## 11.1 B0 purpose and scope

[本文未執筆]

## 11.2 Locked liquid-limit law

[本文未執筆]

## 11.3 Independent paths

[本文未執筆]

## 11.4 10 cases / 30 comparisons

[本文未執筆]

## 11.5 Supported / prohibited claims

[本文未執筆]

## 11.6 小括

[本文未執筆]

---

# 12. U3 B1 単相圧縮性流出および臨界状態benchmark

Full working chapter is maintained in `chapters/chapter12_u3_b1_single_phase_critical_state_benchmark.md`.

---

# 13. 公知文献との比較

## 13.1 Literature method

[本文未執筆]

## 13.2 CO₂ depressurization and sound speed

[本文未執筆]

## 13.3 HEM / HRM / two-fluid

[本文未執筆]

## 13.4 Numerical methods

[本文未執筆]

## 13.5 Project implications

[本文未執筆]

## 13.6 小括

[本文未執筆]

---

# 14. 現在の適用限界

## 14.1 Numerical limits

[本文未執筆]

## 14.2 Thermodynamic / acoustic limits

[本文未執筆]

## 14.3 Boundary / pipeline limits

[本文未執筆]

## 14.4 Physical validation and design use

[本文未執筆]

## 14.5 Applicability statement

[本文未執筆]

---

# 15. FVM境界coupling・高所・ポンプトリップへの展開

## 15.1 Single-phase FVM face-mapping contract

[本文未執筆]

## 15.2 Finite-pipe coupling

[本文未執筆]

## 15.3 High-point benchmark

[本文未執筆]

## 15.4 Pump-trip specification

[本文未執筆]

## 15.5 Two-phase gate entry conditions

[本文未執筆]

## 15.6 Track merge conditions

[本文未執筆]

---

# 16. 結論

## 16.1 Established evidence

[本文未執筆]

## 16.2 Unresolved evidence

[本文未執筆]

## 16.3 Next controlled work

[本文未執筆]

## 16.4 Final approval statement

[本文未執筆]

---

# 参考文献

[Gate 9 registryから整備]

# 付録A　Stage / Gate / Issue / PR / workflow / artifact / SHA correspondence

[未整備]

# 付録B　Fixed conditions and tolerances

[未整備]

# 付録C　Formal outcome / guard dictionary

[未整備]

# 付録D　Approval flag history

[未整備]

# 付録E　Artifact and figure regeneration register

[未整備]
