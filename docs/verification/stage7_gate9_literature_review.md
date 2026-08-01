# Stage 7 Gate 9 — 公知文献調査と証拠マップ v0.1

## Status

```text
Issue:                         #110
scope:                         Gate 9開始前の一次文献調査
review date:                   2026-08-01
primary-source screening:      COMPLETE
detailed annotations:          6 papers
priority registry:             14 papers
model or solver changes:       NONE
Gate 9 execution:              NOT STARTED
```

本資料は、Gate 8で観察された次の三つの現象を、公知研究の中へ位置づけるための初期調査である。

```text
CFL 0.10: accepted crossing; T1–T4 complete
CFL 0.05: subthreshold guard; no continuation
CFL 0.025: accepted crossing; acoustic refusal before T3
```

調査の目的は、既往研究を根拠に直ちに音速式、閾値、数値流束を変更することではない。Gate 9で記録すべき量、将来比較すべきモデル、および現段階で変更してはいけない項目を分離することにある。

---

## 1. 調査課題

### RQ-1 — Crossing時刻・位置とcrossing深さを分離できるか

Gate 8では候補時刻と位置は比較的近かったが、最大平衡品質とformal outcomeは非単調であった。文献上、CO2減圧計算では数値法の精度と音速不連続の双方が減圧挙動へ影響することが報告されている。

### RQ-2 — Acoustic refusalは既知の数値・モデル課題と対応するか

HEMでは液相と二相混合域の音速が大幅に異なり得る。また、緩和の段階によってモデル固有の音速が変わる。Gate 9では、単なる「物性ライブラリ失敗」としてではなく、状態の有効域、音速branch、差分ステンシル、およびモデル固有波速の問題として記録する必要がある。

### RQ-3 — HEMの瞬時平衡仮定をどこまで信頼できるか

非平衡二流体モデルやhomogeneous relaxation modelがHEMより良い結果を示す報告がある一方、条件によってはHEMと二流体モデルの差が小さい報告もある。したがって、HEMを一律に棄却するのではなく、対象時間・境界・熱移動・相転移速度に応じて比較する。

### RQ-4 — Rusanov散逸と高解像度化をどう扱うか

高解像度法は急峻な相変化を鋭く捉え得るが、Gate 9の目的は現行一次精度Rusanov経路の原因候補を記録することである。WENO、Roe、MUSTA等はGate 9後の比較候補であり、Gate 9中のbaseline変更ではない。

### RQ-5 — 安定化策を導入する前に何を確認すべきか

positivity/hyperbolicity preserving、pressure-equilibrium preserving、preconditioning等は有用な候補だが、今回の失敗がどの条件違反に対応するかを確認せず導入すると、症状を隠す可能性がある。

---

## 2. 検索・評価テンプレート

各文献について、以下を記録する。

```text
citation / DOI
対象現象
流体と初期・境界条件
HEM / HRM / two-fluid / relaxation hierarchy
EOS
音速定義または固有波速
空間離散化
時間積分・relaxation解法
検証データ
報告された問題
提案された対処
本プロジェクトへの適用可能性
適用上の注意
```

### 主な検索語

```text
CO2 pipeline depressurization HEM sound velocity discontinuity
CO2 pipeline homogeneous relaxation delayed phase transition
CO2 pipeline non-equilibrium two-fluid experimental validation
two-phase relaxation subcharacteristic condition sound speed
homogeneous equilibrium model Roe preconditioning arbitrary EOS
compressible two-phase WENO positivity hyperbolicity preserving
```

---

## 3. 詳細注釈

### LIT-001 — Lund, Flåtten & Munkejord (2011)

**Depressurization of carbon dioxide in pipelines—Models and methods**  
Energy Procedia 4, 2984–2991.  
DOI: <https://doi.org/10.1016/j.egypro.2011.02.208>

#### 何を扱ったか

相移動を含む二相CO2配管減圧モデルについて、MUSTAとRoe法の収束性・精度を比較し、不連続な音速が減圧へ与える影響を議論している。

#### 今回との類似点

- CO2配管の急減圧
- 相変化を含む双曲型保存則
- 音速の急変が数値流束と時間刻みに影響
- 数値法の差が減圧解へ影響

#### Gate 9への反映

1. Rusanov流束を中央項と散逸項へ厳密に分解する。
2. 候補stepの波速推定値を保存する。
3. 音速branchの変更とcrossing深さの時間順序を保存する。
4. Gate 9中にRoe/MUSTAへ置換せず、将来比較候補として登録する。

#### 注意

同論文のEOSおよびモデルは本実装と同一ではない。したがって「Rusanovが原因」と直接結論づける根拠にはならない。

---

### LIT-002 — Brown et al. (2013)

**A homogeneous relaxation flow model for the full bore rupture of dense phase CO2 pipelines**  
International Journal of Greenhouse Gas Control 17, 349–356.  
DOI: <https://doi.org/10.1016/j.ijggc.2013.05.020>

#### 何を扱ったか

相平衡への有限緩和時間を導入し、遅れた液体–蒸気相転移を表すhomogeneous relaxation modelを構築した。実規模配管破断データと比較し、相転移遅れを無視すると過渡放出流量を過小評価し得ることを示した。

#### 今回との関係

Gate 8のCFL依存をすべて離散化誤差とみなすのは早い。瞬時平衡HEMでは、時間刻みごとに平衡状態へ移るため、実際の有限速度相変化とは異なる応答を持ち得る。

#### Gate 9への反映

- Gate 9ではHEMを変更しない。
- raw保存状態から平衡qualityへ移る過程を段階別に保存する。
- HRMはGate 9後のモデル比較候補とする。
- 「数値誤差」と「瞬時平衡モデル依存」を別の仮説として維持する。

#### 注意

この報告では減圧率への影響と放出流量への影響が同じではない。何を評価量とするかを明確にする必要がある。

---

### LIT-003 — Brown et al. (2014)

**Modelling the non-equilibrium two-phase flow during depressurisation of CO2 pipelines**  
International Journal of Greenhouse Gas Control 30, 9–18.  
DOI: <https://doi.org/10.1016/j.ijggc.2014.08.013>

#### 何を扱ったか

相間の質量・熱・運動量交換をrelaxationとして扱う二流体モデルを構築し、配管壁との熱交換も含めて実規模破断試験と比較した。二流体モデルは全減圧過程で実験と比較的よく一致し、HEMは破断面近傍と初期段階では良好だが、その後の過程では劣ると報告した。

#### 今回との関係

現在のGate 8は非常に短い時間域のverification analogueであり、この文献は直ちにHEMを不採用とする根拠ではない。しかし、長時間ブローダウンや設計利用へ進む前に非平衡比較が必要であることを支持する。

#### Gate 9への反映

- Gate 9は短時間の数値・熱力学診断に限定する。
- 長時間伝播の物理承認を行わない。
- 将来ロードマップにHEM/HRM/two-fluid比較を維持する。

#### 注意

境界条件、配管長、壁熱伝達、初期状態が本pilotと異なる。適用範囲を揃えた比較が必要である。

---

### LIT-004 — Clerc (2000)

**Numerical Simulation of the Homogeneous Equilibrium Model for Two-Phase Flows**  
Journal of Computational Physics 161(1), 354–375.  
DOI: <https://doi.org/10.1006/jcph.2000.6515>

#### 何を扱ったか

HEMでは液相と二相混合域の音速が数桁異なり得るため、広いMach数範囲を扱える数値法が必要であると整理した。任意EOSへ拡張したRoe法とTurkel preconditioningを検討した。

#### 今回との直接関係

Gate 7で液相音速と二相音速に大きな非重複bandが観察され、Gate 8のCFL 0.025では中央密度ステンシルによる平衡音速評価が拒否された。これは、音速差に起因する数値的硬さと、音速評価の有効域を独立に記録すべきことを示す。

#### Gate 9への反映

- 液相・二相branchを明示的に保存する。
- 各stepの局所Mach数と最大波速を保存する。
- 音速評価の試行履歴を保存する。
- preconditioningは将来比較候補であり、Gate 9中には導入しない。

#### 注意

preconditioningは時間精度や波動速度を変え得るため、既存baselineへ暗黙に混ぜてはならない。

---

### LIT-005 — Lund (2012)

**A Hierarchy of Relaxation Models for Two-Phase Flow**  
SIAM Journal on Applied Mathematics 72(6), 1713–1741.  
DOI: <https://doi.org/10.1137/12086368X>

#### 何を扱ったか

圧力・温度・化学ポテンシャル差によるvolume、heat、mass transferを持つ二相relaxationモデルの階層を整理した。平衡モデルの波速は対応するrelaxation systemの波速を超えないというsubcharacteristic conditionを示した。

#### 今回との関係

現在の音速はEOS有限差分だけで評価されている部分があり、モデル本来のJacobian固有値との整合は未承認である。将来的には、モデル固有音速とsubcharacteristic orderingを独立referenceとして確認する価値が高い。

#### Gate 9への反映

Gate 9では式を変更せず、次を保存する。

- 使用された音速branch
- `c^2`の有限性・正値性
- 音速評価拒否の具体的状態
- 中央ステンシルの各試行点が有効かどうか

モデル固有音速の導出は別Gateのreference taskとする。

---

### LIT-006 — Munkejord & Hammer (2015)

**Depressurization of CO2-rich mixtures in pipes: Two-phase flow modelling and comparison with experiments**  
International Journal of Greenhouse Gas Control 37, 398–411.  
DOI: <https://doi.org/10.1016/j.ijggc.2015.03.029>

#### 何を扱ったか

CO2-rich mixtureの五つの減圧実験と、HEMおよび二流体モデルを比較した。検討した摩擦・熱伝達モデルの範囲では、二流体モデルがHEMより大幅に優れるとは限らず、配管熱容量の考慮が重要であった。

#### なぜ重要か

非平衡モデルが常に必要という単純な結論を防ぐ。モデル選択は、対象現象、時間範囲、熱移動、混合物、評価量によって変わる。

#### 本プロジェクトへの反映

- HEMはverification baselineとして維持する。
- 将来のモデル比較は同じ境界・EOS・熱条件で行う。
- 物理validationは圧力だけでなく温度、dry-out、流量等を含む複数指標で行う。

---

## 4. 優先文献一覧

| ID | 優先度 | 主題 | Gate 9での用途 |
|---|---|---|---|
| LIT-001 | P0 | CO2減圧、Roe/MUSTA、音速不連続 | 流束・音速の診断設計 |
| LIT-002 | P0 | HRM、相転移遅れ | 有限速度相転移の将来比較 |
| LIT-003 | P0 | 非平衡二流体、実規模試験 | HEM適用限界 |
| LIT-004 | P0 | HEM音速差、preconditioning | acoustic refusalの位置づけ |
| LIT-005 | P0 | relaxation階層、subcharacteristic | モデル固有音速の将来reference |
| LIT-006 | P1 | HEM対二流体、実験比較 | 過度なモデル複雑化を防ぐ |
| LIT-007 | P1 | metastable liquid、相転移front | 準安定・有限速度front |
| LIT-008 | P1 | multicomponent wave speed | 一般EOSの音速ordering |
| LIT-009 | P1 | 温度・速度relaxation | 平衡仮定と波速 |
| LIT-010 | P1 | intrinsic sound speed、hyperbolicity | Jacobian reference |
| LIT-011 | P1 | CO2 phase-transfer relaxation | HRM architecture |
| LIT-012 | P1 | CO2 HEM、central-upwind/WENO | 高解像度比較候補 |
| LIT-013 | P2 | positivity/hyperbolicity preserving | robust scheme候補 |
| LIT-014 | P2 | incremental-stencil WENO | 高密度比・衝撃安定化候補 |

機械可読な詳細は `stage7_gate9_literature_registry_v0p1.json` に保持する。

---

## 5. Gate 8症状と公知知見の対応

| Gate 8症状 | 公知文献での関連知見 | Gate 9で行うこと | Gate 9では行わないこと |
|---|---|---|---|
| crossing時刻・位置は近いが深さが非単調 | 数値法精度と音速不連続がCO2減圧へ影響 | 保存量変位、margin、流束分解を保存 | threshold変更 |
| CFL 0.025でacoustic refusal | HEMでは音速差が非常に大きく、relaxation段階で波速が変わる | branch、試行ステンシル、`c^2`、失敗理由を保存 | 一方向fallback |
| cell 30の相・音速branch切替 | equilibrium assumptionsが波動速度を変える | event順序を保存 | chatter抑制 |
| HEMの瞬時projection | finite-rate phase transferで放出量が変わり得る | raw crossingとprojectionを分離 | HRMをbaselineへ混入 |
| Rusanov一次精度 | Roe/MUSTA/WENO等の比較報告あり | central/dissipative項を再構成 | flux置換・高次化 |

---

## 6. 対処候補台帳

### Gate 9で直ちに採用

```text
event-aligned state capture
continuous saturation margins
Rusanov central/dissipative decomposition
acoustic evaluation attempt history
raw crossing versus projection temporal separation
formal guard preservation
```

### Gate 9後の診断用prototype

```text
model-intrinsic sound-speed reference
subcharacteristic-condition checks
same-phase derivative reference
Roe / MUSTA / central-upwind comparison branch
first-order versus higher-order reconstruction comparison
HRM reference case
```

### 現時点では採用しない

```text
crossing threshold reduction
quality clipping
one-sided acoustic fallback in production path
hidden sound-speed substitution
Rusanov replacement in Gate 9
WENO/MUSCL activation in Gate 9
HRM/two-fluid replacement of the Gate 8 baseline
physical or design-use approval
```

---

## 7. 文献から導かれるGate 9設計原則

1. **連続量を先に見る。**  
   binaryなaccepted/guardより前に、内部エネルギー・比容積margin、quality、保存量変位を比較する。

2. **音速を一つの数値として扱わない。**  
   branch、評価法、試行点の有効性、`c^2`、wave-speed estimateを保存する。

3. **数値流束と熱力学モデルを分離する。**  
   Rusanov分解は診断だけに使い、相平衡式やEOSを変えない。

4. **HEMの評価は対象依存とする。**  
   HEMで十分な報告と不十分な報告の双方があるため、短時間verificationと長時間physical validationを区別する。

5. **対処法は別PR・別Gateにする。**  
   Gate 9は原因候補の相関と時間順序を記録し、solver変更を承認しない。

---

## 8. 次の文献作業

Gate 9実装と並行して、次を継続する。

```text
P0文献の本文精読と式・case条件の抽出
音速定義の比較表
HEM / HRM / two-fluid model hierarchy表
CO2減圧experiment一覧
Roe / MUSTA / Rusanov / central-upwind / WENO比較表
U3 physical discharge boundary用critical-flow文献の別レビュー
```

本v0.1はGate 9契約固定に必要な初期スクリーニングであり、物理モデル選定の最終レビューではない。
