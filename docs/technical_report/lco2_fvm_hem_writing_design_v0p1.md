# 液化CO₂配管過渡解析 技術報告書 — 執筆設計表 v0.1

## 0. 文書情報

```text
対象範囲:             Stage 1〜Gate 8完了、Gate 9契約準備まで
文書種別:             技術報告書／研究経緯整理
本文目標:             25〜35ページ
付録目標:             15〜30ページ
構成状態:             LOCKED FOR DRAFTING
本文執筆:             NOT STARTED
```

## 0.1 報告書の役割

本報告書は、開発履歴を時系列に並べるだけの記録ではない。各検討を、
次の論理関係として再構成する。

```text
研究上の問い
→ その問いに必要な検証
→ 固定した条件
→ 得られた証拠
→ 証拠が支持する主張
→ 証拠が支持しない主張
→ 次の検討が必要な理由
```

本文では研究上の問いと結論を中心に置き、PR番号、workflow、artifact、
SHA256等は本文中の最小限の参照と付録で保持する。

## 0.2 中心主張

> 本検討では、純CO₂の液相から気液二相状態への遷移を含む一次元保存形
> 有限体積HEM解析経路を段階的に構築・検証した。固定条件下では遷移後の
> 二相領域継続と保存収支を確認した一方、crossing深さおよびpost-crossing
> 継続可否はCFLに対して非単調であり、飽和境界近傍の音速評価も解析継続の
> 制約となった。したがって、現段階の解析経路はverification baselineとして
> 有用であるが、物理精度および設計利用の確立には、数値・音響要因の分離
> 診断と物理流出境界の独立検証が必要である。

## 0.3 執筆時の証拠レベル

| 記号 | 証拠レベル | 本文で許される表現 |
|---|---|---|
| E1 | software verification | 実装した、再現した、保存した、guardした、identityを確認した |
| E2 | numerical characterization | 感度を観測した、非単調であった、比較不能であった |
| E3 | model characterization | モデル上の制約を観測した、文献と対応する可能性がある |
| E4 | physical validation / design use | 現段階では未成立、未承認と明記する |

---

# 第1章　緒言

## 1.1 章の目的

液化CO₂配管過渡解析がなぜ難しく、なぜ単一の最終ケースではなく段階的な
verification ladderが必要であるかを示す。

## 1.2 中心となる問い

- 液化CO₂の急減圧で何が工学的に問題となるか。
- 単相圧力波と熱力学的相変化を同時に扱う際、何が難しいか。
- 本検討は何を解決し、何をまだ解決していないか。

## 1.3 中心メッセージ

```text
液化CO₂配管の減圧解析には、
波動・保存性・実在流体物性・相判定・音速・相変化・境界条件を
一つずつ検証した上で統合する必要がある。
```

## 1.4 記載内容

1. CCS／CO₂輸送と配管過渡現象の背景。
2. ESD、pump trip、depressurization／blowdownで生じる圧力波と相変化。
3. 実在流体EOS、飽和境界、音速差、数値拡散、HEM仮定の課題。
4. 本報告書の目的。
5. 主張範囲と非主張範囲。

## 1.5 主な根拠

- `stage7_real_problem_application_strategy.md`
- `stage7_gate9_literature_review.md`
- `stage7_current_gate_snapshot.md`

## 1.6 予定図表

- 図1：液化CO₂配管過渡解析における主要現象の関係図。
- 図2：本報告書の検証階層と二つの開発トラック。
- 表1：本報告書の主張範囲／非主張範囲。

## 1.7 執筆上の注意

- 実用化の必要性を示しても、現ツールが実用精度に到達したとは書かない。
- 文献知見と本プロジェクトの観測結果を明確に区別する。
- 緒言で個別PRの説明を始めない。

## 1.8 完了条件

読者が第1章だけで、検討目的、技術的難所、現在の成果レベル、未解決課題を
理解できること。

---

# 第2章　解析対象および支配方程式

## 2.1 章の目的

Stageを通じて共通する一次元保存形モデルと、各検証ケースで有効化・無効化
された物理項を整理する。

## 2.2 中心となる問い

- 何を保存変数として解いているか。
- 管路モデルの基本仮定は何か。
- どの物理効果が現在のGate 8ケースに含まれていないか。

## 2.3 中心メッセージ

```text
解析の共通基盤は一次元保存形FVMであり、
現在の二相verification caseでは摩擦・熱・重力を無効化し、
数値・熱力学挙動を切り分けている。
```

## 2.4 記載内容

### 2.4.1 管路モデル

- 一次元管路。
- 断面積一定を基本とする。
- 軸方向の保存量輸送。

### 2.4.2 保存変数

概念的に、

\[
\mathbf{U}=
\begin{bmatrix}
\rho & \rho u & \rho E & \rho q
\end{bmatrix}^{\mathsf{T}}
\]

を示し、各成分の役割を説明する。

### 2.4.3 保存則

\[
\frac{\partial \mathbf{U}}{\partial t}
+
\frac{\partial \mathbf{F}}{\partial x}
=
\mathbf{S}
\]

を基礎式として示す。

### 2.4.4 物理項の扱い

- Stage 1〜6：単相波動、圧力境界、弁操作を中心に段階的検証。
- Stage 7二相verification：摩擦、熱、重力を無効化。
- 将来のU3：摩擦、壁熱容量、高低差、受け側応答を追加予定。

## 2.5 主な根拠

- `archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`
- `stage7_gate8_closeout.md`
- `stage7_real_problem_application_strategy.md`
- production source modulesは本文草稿時に再照合する。

## 2.6 予定図表

- 図3：一次元FVMセル、interface、境界の模式図。
- 表2：保存変数、単位、物理的意味。
- 表3：検証段階ごとの有効／無効物理項。

## 2.7 執筆上の注意

- `rho*q`を独立な相変化速度式と誤解させない。
- 現在の検証で摩擦等が無効であることを、簡略化ではなく意図的な切り分けと説明する。
- 実配管モデルとの違いをこの章で明示する。

## 2.8 完了条件

後続章の数値式、相判定、budget、境界条件を理解するための共通記号が定義
されていること。

---

# 第3章　熱力学モデルと相状態処理

## 3.1 章の目的

実在流体CO₂の状態復元、相判定、平衡品質、ボイド率、quality projection、
音速評価、guardの関係を一つの処理経路として説明する。

## 3.2 中心となる問い

- 保存状態から圧力、温度、相状態をどう復元するか。
- raw crossingとquality projectionの役割はどう異なるか。
- 音速評価はどこで失敗し得るか。

## 3.3 中心メッセージ

```text
相遷移判定はrawなrho/e状態に基づき、
quality projectionは判定後のrho*qを平衡品質へ同期する。
音速評価は相状態と有効な熱力学微分領域に依存する。
```

## 3.4 記載内容

### 3.4.1 CoolPropによる純CO₂物性

- backend名とversion。
- 状態量復元。
- backend traceability。
- design-use未承認status。

### 3.4.2 相状態分類

- `LIQUID_CANDIDATE`。
- `OPEN_TWO_PHASE`。
- scope外／guard状態。

### 3.4.3 飽和座標と平衡品質

\[
q_e=\frac{e-e_f}{e_g-e_f},\qquad
q_v=\frac{v-v_f}{v_g-v_f}
\]

- 内部エネルギー座標。
- 比容積座標。
- 飽和液からのsigned margin。

### 3.4.4 ボイド率

品質と体積占有率の違いを説明する。

### 3.4.5 Quality projection

```text
pre-step accepted state
→ raw post-FVM state
→ rho/e phase classification
→ first quality projection
→ mixed-state EOS acceptance
→ second projection exact no-op check
→ accepted state
```

### 3.4.6 音速

- 単相音速。
- 平衡二相音速candidate。
- 液相／二相branch。
- 中央密度ステンシル。
- halvingとrefusal。

## 3.5 主な根拠

- PR #54〜#60の中央記録。
- PR #64〜#72のcrossing records。
- `stage7_gate5_closeout.md`
- `stage7_gate7_closeout.md`
- `stage7_gate8_closeout.md`
- `stage7_gate9_execution_contract_v0p1.json`

## 3.6 予定図表

- 図4：CO₂相図上の液相、飽和境界、open-two-phase領域。
- 図5：raw stateからaccepted stateまでの処理フロー。
- 図6：内部エネルギー座標と比容積座標の品質評価。
- 図7：液相音速branchと二相音速branchの概念図。
- 表4：phase categoryとformal outcome／guardの対応。

## 3.7 執筆上の注意

- projectionを物理的核生成モデルと表現しない。
- `OPEN_TWO_PHASE`を実験的に確認された気泡領域と表現しない。
- equilibrium sound speedを物理的に妥当と断定しない。
- Gate 8のacoustic refusalをCoolProp単独の不具合と断定しない。

## 3.8 完了条件

読者が、raw crossing、projection、accepted state、音速branch、guardの時間順序を
区別できること。

---

# 第4章　数値解析手法

## 4.1 章の目的

有限体積更新、Rusanov flux、CFL時間刻み、境界処理、budget、再現性証拠化を
整理する。

## 4.2 中心となる問い

- どの離散化がbaselineか。
- 数値散逸はどこに入るか。
- 結果の再現性とtraceabilityをどう確保したか。

## 4.3 中心メッセージ

```text
一次精度Rusanov FVMを数値controlとして固定し、
各改善候補をbaselineへ暗黙に混ぜず、
guard、budget、CI、SHA256で証拠化した。
```

## 4.4 記載内容

### 4.4.1 FVM更新式

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

### 4.4.2 Rusanov flux

\[
\mathbf{F}_{i+1/2}
=
\frac{\mathbf{F}_L+\mathbf{F}_R}{2}
-
\frac{a_{\max}}{2}(\mathbf{U}_R-\mathbf{U}_L)
\]

- central contribution。
- dissipative contribution。
- 頑健性と数値拡散。

### 4.4.3 CFL時間刻み

\[
\Delta t=\mathrm{CFL}
\frac{\Delta x}{\max_i(|u_i|+c_i)}
\]

### 4.4.4 境界条件

- reflective wall。
- fixed／scheduled pressure。
- internal valve verification。
- prescribed-subcooled outlet。

### 4.4.5 保存収支

- mass。
- momentum。
- total energy。
- vapor inventory／phase source。

### 4.4.6 再現性

- fixed configuration。
- exact replay。
- Ubuntu authoritative reference。
- Windows numeric equivalence。
- JUnit、workflow、artifact、SHA256。

## 4.5 主な根拠

- Stage 1〜6 master verification records。
- PR #48〜#53のfirst-order reference-core records。
- Gate 3 records。
- Gate 6〜8 closeout documents。

## 4.6 予定図表

- 図8：Rusanov central／dissipative分解。
- 図9：CFLと液相／二相音速がdtへ与える影響。
- 表5：主要boundaryとverification目的。
- 表6：budget／guard／traceability evidence。

## 4.7 執筆上の注意

- 一次精度を弱点として隠さず、比較controlとしての価値を説明する。
- MUSCL／WENO等は既存baselineへ導入済みと書かない。
- SHA一致を物理的正確さと混同しない。

## 4.8 完了条件

結果章に現れるCFL、Rusanov、budget、guard、SHAが、方法章だけで理解できること。

---

# 第5章　段階的検証戦略

## 5.1 章の目的

Stage 1〜6、Stage 7のmilestone、Gate 3〜9準備を、一つのverification hierarchy
として整理する。

## 5.2 中心となる問い

- なぜ単相検証を完了してから二相crossingへ進んだか。
- 各Stage／Gateが何の不確かさを減らしたか。
- 現在の二つの開発トラックはなぜ分離されるか。

## 5.3 中心メッセージ

```text
開発は機能追加の列ではなく、
数値基盤 → 単相波動 → 境界・弁 → 実在流体 → 相処理 → crossing
→ pipeline analogue → acoustic／CFL診断
という不確かさ削減の階層である。
```

## 5.4 検証階層

| 段階 | 主対象 | 代表証拠 | 減らした不確かさ |
|---|---|---|---|
| Stage 1〜5 | backend、均一状態、単相波、反射 | V-001〜V-010 | 基本solver／boundary integrity |
| Stage 6 | pressure ramp、internal valve | V-011〜V-012 | controlled boundary／component behavior |
| Stage 7前半 | independent acoustic reference、real-fluid HEM | V-013、PR #54〜#63 | wave reference、phase foundation |
| Crossing段階 | raw transition、projection、accepted EOS | PR #64〜#73 | discrete liquid-to-two-phase path |
| Pipeline段階 | prescribed-boundary depressurization | PR #74〜#90 | pipeline first crossing and sensitivity |
| Gate 3〜8 | runtime、acoustic、propagation、chatter、CFL | PR #91〜#112 | reproducibility and post-crossing limits |
| Gate 9準備 | literature and forensic contract | PR #113 | diagnosis before mitigation |

## 5.5 主な根拠

- `archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`
- `MASTER_VERIFICATION_INDEX.md`
- `stage7_execution_log.md`
- `stage7_current_gate_snapshot.md`

## 5.6 予定図表

- 図10：Stage 1〜Gate 9準備の検証階層図。
- 表7：Stage／Gate／目的／成果／残課題一覧。

## 5.7 執筆上の注意

- Stage番号とV-ID、Gate番号を混同しない。
- 全PRを本文で列挙せず、代表節目のみ本文に置く。
- detailed traceabilityは付録Aへ回す。

## 5.8 完了条件

読者が、後続の結果章を「どの検証段階の証拠か」と位置づけられること。

---

# 第6章　基礎検証結果

## 6.1 章の目的

二相検討に入る前に成立していた、backend traceability、uniform-state
preservation、単相波動、反射、pressure ramp、internal valveの証拠を要約する。

## 6.2 中心となる問い

- solverは単相状態で保存則と波動方向を正しく保持するか。
- idealized boundaryは期待される反射／流束identityを満たすか。
- controlled boundary operationを再現可能に扱えるか。

## 6.3 中心メッセージ

```text
Stage 1〜6で、二相化以前の数値基盤、波動、境界、弁操作、budget、CIを
段階的に固定したため、Stage 7の相遷移課題を基礎solver不良と混同せずに済む。
```

## 6.4 結果節

### 6.4.1 Backendと均一状態

- CoolProp traceability。
- uniform state preservation。
- budget residual。

### 6.4.2 Incident wave

- wave direction。
- arrival time。
- mesh／CFL observation。
- numerical broadening。

### 6.4.3 Rigid-wall reflection

- pressure positive reflection。
- velocity sign reversal。
- zero wall through-flux。

### 6.4.4 Fixed-pressure reflection

- pressure negative reflection。
- velocity positive reflection。
- outgoing／returning characteristic。

### 6.4.5 Controlled pressure ramp

- monotone boundary history。
- front fit／arrival timing。
- budget and CI。

### 6.4.6 Internal valve

- constant opening。
- opening ramp。
- closing ramp。
- complete closure and zero through-flux。

## 6.5 主な根拠

- V-001〜V-012 master verification records。
- PR #34〜#42 formal reports／manifests。
- PR #48〜#51 first-order baseline records。

## 6.6 予定図表

- 図11：単相incident／reflectionの代表波形。
- 図12：internal valve opening／closingと圧力波の模式図。
- 表8：V-001〜V-012の主要pass evidence。

## 6.7 執筆上の注意

- 全数値を本文へ詰め込まず、代表metricsと結論を示す。
- `COMPLETE`を物理Validation完了と誤解させない。
- numerical diffusionを隠さない。

## 6.8 完了条件

Stage 7で現れた問題が、基本的な単相solver・boundary identityを通過した上での
問題であることを示せること。

---

# 第7章　液相から二相への遷移検証

## 7.1 章の目的

実際の一次精度FVM更新が液相からopen-two-phaseへ入り、その後のprojectionと
mixed EOS recoveryが成立した経緯を整理する。

## 7.2 中心となる問い

- raw FVM stateで有限のcrossingが生じるか。
- crossing後に熱力学的にacceptedな状態へ戻せるか。
- projectionとvapor budgetは整合するか。

## 7.3 中心メッセージ

```text
固定Case Aではactual FVM raw crossingが生じ、
projection後のmixed EOS recovery、second-projection no-op、vapor budget closureを
確認した。これはsoftware verificationであり、physical nucleationの証明ではない。
```

## 7.4 結果節

### 7.4.1 Crossing specificationとtransition classifier

### 7.4.2 Mixed liquid／open-two-phase EOS

### 7.4.3 Liquid state-pair survey

### 7.4.4 One-step raw crossing matrix

### 7.4.5 Projected crossingとEOS recovery

### 7.4.6 Case A／Case B repeatability freeze

## 7.5 主な根拠

- PR #64〜#72。
- first-crossing formal report／artifact。
- `MASTER_VERIFICATION_INDEX.md` crossing section。

## 7.6 予定図表

- 図13：Case A／Case Bの状態配置。
- 図14：raw crossingからaccepted mixed stateまで。
- 表9：Case A／Bの条件とformal outcome。
- 表10：projection／second no-op／budget evidence。

## 7.7 執筆上の注意

- raw transitionとaccepted crossingを区別する。
- quality thresholdの役割を明記する。
- physical bubble nucleationやmetastabilityを扱っていないと明記する。

## 7.8 完了条件

Stage 7の重要なソフトウェア成果である「FVM crossing経路」が、数値・熱力学・
budgetの順序で理解できること。

---

# 第8章　配管減圧解析への拡張

## 8.1 章の目的

0-D／local crossing verificationを、1 m配管のprescribed-boundary depressurization
analogueへ拡張した過程と、first crossingの圧力・mesh・CFL感度を整理する。

## 8.2 中心となる問い

- 配管境界から到来する減圧波でcrossingが生じるか。
- 最終圧力、mesh、CFLで時刻、位置、深さはどう変わるか。
- どの結果がacceptedで、どの結果がguardとなるか。

## 8.3 中心メッセージ

```text
5→2／3 MPaではaccepted crossing、5→4 MPaではsubthreshold raw crossingを確認した。
時刻・位置には一定の傾向があるが、crossing深さはmesh／CFLに対して非単調であり、
independenceやaccuracyは確立していない。
```

## 8.4 結果節

### 8.4.1 Minimal pipeline specification

### 8.4.2 Prescribed-subcooled outlet verification

### 8.4.3 5→2／3／4 MPa matrix

### 8.4.4 4 MPa subthreshold forensic review

### 8.4.5 32／64／128-cell mesh sensitivity

### 8.4.6 128-cell first-crossing CFL matrix

### 8.4.7 Cross-runtime numeric equivalence

## 8.5 主な根拠

- PR #74、#75、#77、#79、#82、#84、#90、#91。
- Gate 3／4 records。
- `MASTER_VERIFICATION_INDEX.md`。

## 8.6 予定図表

- 図15：1 m prescribed-boundary pipeline analogue。
- 図16：2／3／4 MPa crossing位置と時刻。
- 図17：mesh／CFLに対するcrossing depth。
- 表11：pressure matrix。
- 表12：mesh sensitivity。
- 表13：first-crossing CFL sensitivity。

## 8.7 執筆上の注意

- prescribed outletをphysical blowdown boundaryと表現しない。
- crossing time／positionの傾向をconvergenceと表現しない。
- 4 MPa guardをall-liquid controlと誤記しない。

## 8.8 完了条件

Gate 5以降のpost-crossing検討が、どのfirst-crossing baselineから始まったかを
明確にできること。

---

# 第9章　Post-crossing挙動とphase chatter

## 9.1 章の目的

Gate 6の固定continuationと、Gate 7のcell 30 event-aligned diagnosisを整理する。

## 9.2 中心となる問い

- accepted crossing後、二相領域は固定条件で継続するか。
- どのセルがstable frontを構成し、どのセルがchatterするか。
- chatterと飽和margin、音速branch、projectionはどう対応するか。

## 9.3 中心メッセージ

```text
CFL 0.10の固定列ではopen-two-phase regionがT1〜T4まで継続し上流へ拡大した。
一方、cell 30では49回のlocalized chatterが生じ、飽和margin、acoustic branch、
projectionと強く同期したが、root causeは確定していない。
```

## 9.4 結果節

### 9.4.1 T1〜T4のfront progression

### 9.4.2 Quality、void fraction、vapor inventory

### 9.4.3 Conservative／vapor budget

### 9.4.4 Cell 29／30／31 phase history

### 9.4.5 Saturation-margin sign changes

### 9.4.6 Acoustic branch switching

### 9.4.7 Projection activity and temporal order

## 9.5 主な根拠

- `stage7_gate6_closeout.md`
- `stage7_gate7_closeout.md`
- Gate 6／7 artifacts。

## 9.6 予定図表

- 図18：T1〜T4 front position。
- 図19：q_eq／alpha／vapor inventory history。
- 図20：cell 29〜31 phase history。
- 図21：cell 30 saturation margin／sound speed／projection events。
- 表14：Gate 6 checkpoints。
- 表15：Gate 7 chatter metrics。

## 9.7 執筆上の注意

- upstream movementをphysical front speed approvalと表現しない。
- correlationをcausationと書かない。
- cell 30 chatterとstable frontを区別する。

## 9.8 完了条件

Gate 8でなぜCFL比較が必要になったかを、Gate 6／7の結果から論理的に導けること。

---

# 第10章　Gate 8 Post-crossing CFL感度

## 10.1 章の目的

32 cells固定、CFL 0.10／0.05／0.025で実行したformal-outcome matrixを、
Gate 8の中心結果として示す。

## 10.2 中心となる問い

- refined CFLでもaccepted first crossingは維持されるか。
- 同一post-crossing物理時間で比較可能か。
- acoustic evaluationは継続を制限するか。

## 10.3 中心メッセージ

```text
Gate 8は固定実験として完了したが、三列のformal outcomeは分岐した。
CFL 0.10はT1〜T4完了、0.05はsubthreshold guard、0.025はaccepted後にT3直前で
acoustic refusalとなり、post-crossing CFL comparabilityは成立しなかった。
```

## 10.4 結果節

### 10.4.1 Gate 6 exact replay

### 10.4.2 CFL 0.05 formal guard

### 10.4.3 CFL 0.025 accepted crossing

### 10.4.4 CFL 0.025 acoustic refusal

### 10.4.5 Formal outcome matrix

### 10.4.6 Non-monotone crossing depth

### 10.4.7 Gate 8 classification and approval boundary

## 10.5 主な根拠

- `stage7_gate8_closeout.md`
- Gate 8 artifact `8761925785`
- PR #107、#108、#112。

## 10.6 予定図表

- 図22：Gate 8 formal outcome flow。
- 図23：candidate q_eqのCFL比較。
- 図24：CFL 0.025 acoustic refusal位置とT3 target。
- 図25：Gate 8 artifactのfront／quality／chatter／budget figuresから選定。
- 表16：formal outcome matrix。
- 表17：approval disposition。

## 10.7 執筆上の注意

- `Gate_8_execution_complete=true`をCFL independence成功と解釈しない。
- 0.025の64 valid stepsとT1／T2のみ到達を正確に記載する。
- failureをprogram crashと表現せず、unchanged guardによるfail-safeと説明する。

## 10.8 完了条件

本報告書の主要な現在地が、表と図だけでも理解できること。

---

# 第11章　公知文献との比較

## 11.1 章の目的

Gate 8で観測したCFL非単調性、音速branch差、acoustic refusal、HEM適用範囲を
公知研究の中へ位置づける。

## 11.2 中心となる問い

- CO₂配管減圧で音速不連続と数値法感度は報告されているか。
- HEM、HRM、two-fluidはどの条件で差を生むか。
- 高解像度法やpreconditioningは何を改善し得るか。
- 何をGate 9中には変更してはいけないか。

## 11.3 中心メッセージ

```text
類似する音速・数値法・非平衡課題は公知である。
しかし文献は直ちに単一原因や単一対策を支持しないため、
Gate 9では現行baselineを保持し、correlationとtemporal orderを先に記録する。
```

## 11.4 論点別構成

### 11.4.1 CO₂ depressurization and sound-speed discontinuity

### 11.4.2 HEM and homogeneous relaxation

### 11.4.3 Two-fluid non-equilibrium validation

### 11.4.4 Relaxation hierarchy and subcharacteristic condition

### 11.4.5 Roe／MUSTA／central-upwind／WENO

### 11.4.6 Positivity／hyperbolicity／pressure-equilibrium preservation

### 11.4.7 本プロジェクトへのrecommendation register

## 11.5 主な根拠

- `stage7_gate9_literature_review.md`
- `stage7_gate9_literature_registry_v0p1.json`
- 原著DOI。

## 11.6 予定図表

- 図26：HEM／HRM／two-fluid model hierarchy。
- 表18：文献evidence matrix。
- 表19：手法候補と本プロジェクトでの扱い。

## 11.7 執筆上の注意

- 文献の条件と本ケースが同一でないことを明記する。
- 文献をRusanov原因断定やHEM棄却の根拠にしない。
- 直接引用は最小限とし、原著の意味を正確に要約する。

## 11.8 完了条件

Gate 9の診断契約が、文献を踏まえた合理的な次作業として説明できること。

---

# 第12章　現在の適用限界

## 12.1 章の目的

現在のbaselineが何に使え、何に使えないかを、数値、熱力学、音響、境界、
工学利用の各観点で明示する。

## 12.2 中心メッセージ

```text
現行経路は固定verification caseの調査基盤として有用であるが、
実配管の物理的blowdown、front speed、design pressure、discharge rateを
承認された精度で予測する段階ではない。
```

## 12.3 限界分類

### 12.3.1 数値的限界

- first-order spatial accuracy。
- Rusanov diffusion。
- mesh independence未成立。
- CFL independence未成立。

### 12.3.2 熱力学的限界

- equilibrium HEM。
- metastability／nucleation delayなし。
- finite-rate phase transferなし。

### 12.3.3 音響的限界

- liquid／two-phase branch gap。
- central stencil refusal。
- intrinsic acoustic validationなし。

### 12.3.4 境界条件の限界

- prescribed-subcooled outlet。
- physical discharge／choking未実装。
- receiver dynamicsなし。

### 12.3.5 Pipeline physicsの限界

- friction、heat、gravityなし。
- solid CO₂、non-condensable gasはscope外。

### 12.3.6 利用上の限界

- physical validation=false。
- design use=false。
- production activation=false。

## 12.4 主な根拠

- `stage7_current_gate_snapshot.md`
- `stage7_real_problem_application_strategy.md`
- Gate 5〜8 closeout。

## 12.5 予定図表

- 表20：適用可能範囲／非対応範囲／必要な次証拠。
- 図27：verification baselineからdesign-useまでのvalidation ladder。

## 12.6 執筆上の注意

- 限界章を弱気な付記ではなく、報告書の主要成果として扱う。
- 未承認と不可能を混同しない。
- 将来の改善候補を、現在の機能として書かない。

## 12.7 完了条件

第三者が本報告書を読んで、現行結果を過大利用できないこと。

---

# 第13章　今後の開発ロードマップ

## 13.1 章の目的

Track NとTrack Aを分け、両者の合流条件を明確にする。

## 13.2 中心メッセージ

```text
数値・モデル診断だけでも、実問題境界開発だけでも不十分である。
Gate 9による原因候補分離と、U3 physical discharge componentの独立benchmarkを
並行し、両者の証拠が揃った後に統合する。
```

## 13.3 Track N

```text
Gate 9 event-aligned forensic diagnosis
→ post-crossing mesh sensitivity
→ local flux／acoustic discrimination
→ longer-duration continuation
→ HEM／HRM／two-fluid comparison
```

### Gate 9で固定済みの観測

- cells 28〜31。
- interfaces 27|28〜right boundary。
- event前8／event／可能なら後8 steps。
- raw／projection stage separation。
- Rusanov central／dissipative reconstruction。
- acoustic trial／halving history。

## 13.4 Track A

```text
B0 single-phase orifice reference
→ verification-only adapter
→ B1 equilibrium critical-state reference
→ physical discharge boundary
→ friction／thermal／elevation
→ integrated blowdown
→ validation-data comparison
```

## 13.5 合流条件

- Gate 9で主要correlationが記録されている。
- physical discharge componentが独立referenceに合格している。
- boundary flux and energy accountingが閉じている。
- longer-duration caseのmodel scopeが定義されている。
- validation dataとuncertaintyが選定されている。

## 13.6 主な根拠

- `stage7_gate9_execution_contract_v0p1.json`
- `stage7_u3_physical_discharge_boundary_benchmark_spec.md`
- `stage7_u3_b0_discharge_boundary_contract_v1.json`
- `stage7_real_problem_application_strategy.md`

## 13.7 予定図表

- 図28：Track N／Track Aロードマップ。
- 図29：physical discharge componentからintegrated pipeまで。
- 表21：次Gateごとの入力、出力、complete条件、非承認事項。

## 13.8 執筆上の注意

- roadmapを予定日程ではなく、証拠依存のgate sequenceとして書く。
- Track AがGate 9結果を代替しないことを明記する。
- B0合格をtwo-phase critical discharge approvalと混同しない。

## 13.9 完了条件

次の開発者が、何から始め、何を完了条件とし、どこで統合するかを理解できること。

---

# 第14章　結論

## 14.1 章の目的

本報告書が確立した内容、確立していない内容、次段階の必要性を簡潔にまとめる。

## 14.2 結論の骨格

1. 一次元保存形FVMと実在流体EOSを組み合わせたpure-CO₂解析経路を構築した。
2. 単相波動、反射、boundary、valve、budgetの基礎verificationを完了した。
3. actual first-order FVM raw crossing、projection、mixed-state recoveryを確認した。
4. prescribed-boundary pipeline analogueでfirst crossingと固定continuationを確認した。
5. mesh／CFLに対するcrossing depthとformal outcomeの非単調性を観測した。
6. Gate 8のCFL 0.025でnear-saturation acoustic evaluationが継続制約となった。
7. 現在のbaselineはsoftware／numerical investigationに有用だがphysical validation／design useには未到達である。
8. Gate 9 forensic diagnosisとphysical discharge component benchmarkが次段階である。

## 14.3 執筆上の注意

- 結論に新しい結果を入れない。
- `確認した`、`観測した`、`未成立`を使い分ける。
- abstractと完全に整合させる。
- prohibited claimsを最終監査する。

## 14.4 完了条件

結論だけを読んでも、成果と限界が同じ重みで伝わること。

---

# 付録設計

## 付録A　Stage／Gate／Issue／PR／artifact対応表

全traceabilityを保持する。本文では代表参照のみとする。

## 付録B　固定解析条件とtolerance

各caseのgeometry、state、CFL、mesh、threshold、step capを整理する。

## 付録C　Formal outcome／guard dictionary

`ACCEPTED_FIRST_CROSSING`、`GUARD_FAILURE`、`ACOUSTIC_REFUSAL`等を定義する。

## 付録D　Approval boundary history

各Gate終了時のtrue／falseを一覧化する。

## 付録E　CI／runtime／SHA256 evidence

workflow、artifact、test数、backend version、source SHAを整理する。

## 付録F　Annotated literature registry

Gate 9文献14件と詳細注釈を収載する。

## 付録G　Software module map

主要module、data class、runner、artifact writerの役割を整理する。

## 付録H　Artifact／CSV schema

再解析や図再生成に必要なcolumn definitionを整理する。

---

# 執筆順序

```text
1. 第10章 Gate 8
2. 第9章 Gate 6／7
3. 第8章 pipeline crossing
4. 第7章 first crossing／projection
5. 第6章 Stage 1〜6基礎結果
6. 第2〜5章 方法と検証戦略
7. 第11章 文献比較
8. 第12〜13章 限界とroadmap
9. 第1章 緒言
10. 第14章 結論
11. 要旨
12. claim audit
```

結果章を先に書くことで、緒言や考察が将来構想だけに引っ張られることを防ぐ。
