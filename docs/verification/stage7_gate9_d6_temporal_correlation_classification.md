# Stage 7 Gate 9 D6 — Temporal/correlation classification

## 状態

```text
Issue:                                      #110
D0-D5:                                      COMPLETE / main
D5 merge SHA:                               ede646078f5d9cc094f0efa430b87ef4bc5e232a
D5 authoritative workflow run:              30805641241
D5 authoritative artifact ID:               8855725551
D5 artifact ZIP SHA256:                     6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850
D6 implementation:                          THIS PR
D6 authoritative execution:                 PENDING CI
production solver changes:                  none
```

## 1. 目的

D6は、D5で固定された3 CFLの同一schema証拠だけを入力とし、Issue #110で
事前許可された12個のlabelを機械判定する。

D6はsolverを再実行しない。D5 artifactをGitHub Actionsからartifact IDで取得し、
ZIP SHA256と内部`artifact_sha256.txt`を検証した後、次を分類する。

```text
candidate time / position stability
continuous crossing-depth sensitivity
non-monotone depth sequence
candidate-step dt ordering
Rusanov dissipative ordering
boundary-adjacent net flux ordering
saturation-margin ordering
acoustic branch ordering
raw crossing / projection temporal order
fixed threshold / formal outcome relation
multi-factor evidence
review inconclusive disposition
```

相関labelはroot causeを承認しない。

## 2. 入力境界

入力は次のauthoritative D5 artifactへ固定する。

```text
workflow run:       30805641241
artifact ID:        8855725551
source head SHA:    45894a3fbe8c176c8435517c6204d94359dccccc
merge SHA:          ede646078f5d9cc094f0efa430b87ef4bc5e232a
ZIP SHA256:         6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850
```

D6 loaderは次をfail-fastで確認する。

```text
D5 schema / scope
locked CFL sequence
immutable candidate identities
fixed record counts
D5 completion flags
Rusanov / CFL / timeline / projection / budget guards
D5 source head SHA
locked 18-file set
17 internal file digests
```

D5 artifactの一部を編集、再生成、補完したものは受理しない。

## 3. 分類規則

### 3.1 Candidate time / position stability

3列すべてについて、

```text
candidate cellが一致
outlet distanceが一致
CFL 0.10とのcandidate time差 <= 3列中最大candidate dt
```

を要求する。

この判定はevent alignmentであり、物理的front speedの精度承認ではない。

### 3.2 Crossing-depth sensitivity

3つのCFL pairすべてについて、

```text
max(q_i, q_j) / min(q_i, q_j) >= 2
```

を要求する。

### 3.3 Pairwise ordering test

候補mechanismの値がcrossing depthを説明すると呼ぶには、3 CFLから得られる
3つのpairすべてで大小関係が一致しなければならない。

```text
full-order match: 3 / 3
partial match:    labelを付与しない
```

3点だけから相関係数を強く解釈しない。

### 3.4 Candidate-step overshoot

```text
measure: candidate dt
required: 3 / 3 pairwise ordering match
temporal position: RAW_POST_FVMより前
```

### 3.5 Rusanov dissipation

cell 29とcell 31について、candidate-stepの次の絶対値を比較する。

```text
mass dissipative increment
momentum dissipative increment
energy dissipative increment
```

6 measure × 3 pair = 18比較すべての一致を要求する。vapor成分は全列ゼロのため、
ordering evidenceから除外する。

### 3.6 Boundary flux imbalance

境界隣接cell 31のcandidate-step net updateを用いる。

```text
net component = central increment + dissipative increment
measure: |mass| / |momentum| / |energy|
required: 3 measure × 3 pair = 9 / 9
```

これはcandidate-stepの局所判定であり、過去stepからの累積境界影響を否定しない。

### 3.7 Saturation margins

RAW_POST_FVMの次を比較する。

```text
q_u
q_v
|Delta e from saturated liquid|
|Delta v from saturated liquid|
```

4 measure × 3 pair = 12 / 12を要求する。

これらは`q_eq`と熱力学的に結合した連続座標であり、独立したroot-cause証拠ではない。

### 3.8 Acoustic branch

label付与には、

```text
少なくとも1つのcross-CFL branch差
accepted sound speedの3 / 3 ordering match
```

の両方を要求する。

D5 candidate metricの音速は`FINAL_ACCEPTED`で取得され、raw crossingより後である。

### 3.9 Projection temporal ordering

各CFLについて、timelineとprojection historyから次を要求する。

```text
RAW_POST_FVM(cell 29) sequence
  <
POST_FIRST_PROJECTION(cell 29) sequence

raw q_eq > 0
raw rho*q = 0
first projection delta rho*q > 0
second projection = exact no-op
final state = second projection
```

### 3.10 Threshold classification

各CFLについて、

```text
q_eq >= 1e-6  -> ACCEPTED_FIRST_CROSSING
q_eq <  1e-6  -> GUARD_FAILURE
```

の一致を要求し、さらに3列が閾値の両側を含むことを要求する。

### 3.11 Multi-factor / inconclusive

独立candidate mechanismは次の4種類へ限定する。

```text
candidate-step overshoot
Rusanov dissipation
boundary flux imbalance
acoustic branch selection
```

2種類以上がfull-order matchした場合のみ`MULTI_FACTOR_CROSSING_DEPTH`を付与する。

4種類すべてがfull-order matchしない場合は、
`CROSSING_DEPTH_REVIEW_INCONCLUSIVE`を付与する。

## 4. 固定D5証拠への分類結果

実装の固定判定は次を返す。

### 付与

```text
CANDIDATE_TIME_POSITION_STABLE_ACROSS_CFL
CROSSING_DEPTH_CFL_SENSITIVE
CROSSING_DEPTH_SEQUENCE_NON_MONOTONE
SATURATION_MARGIN_DISPLACEMENT_CORRELATED
PROJECTION_ACTIVITY_POSTDATES_RAW_CROSSING
THRESHOLD_CLASSIFICATION_DISCONTINUITY_OBSERVED
CROSSING_DEPTH_REVIEW_INCONCLUSIVE
```

### 非付与

```text
CANDIDATE_STEP_OVERSHOOT_CORRELATED
RUSANOV_DISSIPATION_CORRELATED
BOUNDARY_FLUX_IMBALANCE_CORRELATED
ACOUSTIC_BRANCH_SELECTION_CORRELATED
MULTI_FACTOR_CROSSING_DEPTH
```

主要denominatorは次のとおり。

```text
candidate dt:                 2 / 3
Rusanov dissipation:         12 / 18
boundary flux imbalance:      6 / 9
saturation margins:          12 / 12
acoustic branch differences:  0 / 3
projection temporal order:    3 / 3
threshold outcome match:      3 / 3
```

## 5. 成果物

```text
summary.json
label_evidence.csv
temporal_order_evidence.csv
mechanism_rank_comparison.csv
threshold_classification_evidence.csv
report.md
artifact_sha256.txt
dedicated JUnit
related Stage 7 JUnit
full-repository JUnit
```

## 6. 数値・model境界

```text
production solver equations:             unchanged
Rusanov flux expression:                 unchanged
CFL calculation:                         unchanged
sound-speed formula:                     unchanged
phase classifier:                        unchanged
quality projection:                      unchanged
accepted-crossing threshold:             unchanged
boundary condition:                      unchanged
formal stop:                              unchanged
forced post-guard continuation:           none
solver re-execution for D6:               none
```

## 7. 完了・承認境界

authoritative CIがcleanになった場合、次だけをtrueへできる。

```text
D6_temporal_correlation_classification_complete = true
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true
```

次はfalseのまま維持する。

```text
crossing_depth_root_cause_approved = false
threshold_change_authorized = false
flux_change_authorized = false
sound_speed_change_authorized = false
projection_change_authorized = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

Gate 9完了後にroot causeへ進む場合は、additional CFL/mesh pointsまたは
single-factor interventionを事前契約した別Issue / 別Gateで実施する。
