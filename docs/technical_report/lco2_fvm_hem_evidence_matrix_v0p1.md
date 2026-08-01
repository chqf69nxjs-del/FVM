# 液化CO₂配管過渡解析 技術報告書 — 証拠対応表 v0.1

## 1. 目的

本表は、技術報告書中の主張を、authoritativeなrepository record、PR、workflow、
artifact、CSV／figureへ結びつける。

本文に定量値を記載する前に、本表へsourceを登録する。source未登録の数値は、
最終稿へ使用しない。

## 2. 証拠利用ルール

```text
E1 software verification:
  identity、budget、guard、CI、SHA、再現性を主張可能

E2 numerical characterization:
  mesh／CFL感度、非単調性、formal outcome divergenceを主張可能

E3 model characterization:
  acoustic／HEM／phase-model limitationを観測・考察可能

E4 physical validation and design use:
  現在は未成立。accuracy／design claimは禁止
```

### 定量値の優先順位

1. closeout documentに固定された値。
2. authoritative workflow artifactのJSON／CSV。
3. PR merge時のreviewed comment。
4. current snapshot／master index。
5. source codeのdefault値。

複数sourceが異なる場合、最終closeoutとauthoritative artifactを優先し、差異を
注記する。

---

# 3. 章別証拠対応

| 章 | 中心主張 | Primary record | Secondary record | Evidence level |
|---:|---|---|---|---|
| 1 | 液化CO₂過渡解析には段階的verificationと二つの開発trackが必要 | `stage7_real_problem_application_strategy.md` | `stage7_gate9_literature_review.md` | E3 |
| 2 | 共通基盤は一次元保存形FVMで、Gate 8では摩擦・熱・重力を無効化 | `stage7_gate8_closeout.md` | source／case config | E1 |
| 3 | raw phase classification、quality projection、accepted EOS、sound-speed guardを分離 | PR #54〜#72 records | Gate 5／7／8 closeout | E1/E3 |
| 4 | first-order Rusanov FVMをcontrolとして固定し、CI／SHA／budgetで証拠化 | archived master index | Gate 3〜8 closeout | E1/E2 |
| 5 | Stage 1〜Gate 9準備は不確かさ削減の階層 | archived／current master indexes | execution log | E1-E3 |
| 6 | 二相化以前にbackend、wave、reflection、ramp、valveを検証 | archived master index V-001〜V-012 | PR #34〜#51 records | E1/E2 |
| 7 | actual first-order raw crossingとprojected mixed-state recoveryを確認 | PR #70〜#72 records | master index crossing section | E1 |
| 8 | pipeline analogueで2／3 MPa accepted、4 MPa subthreshold、mesh／CFL非単調性 | PR #77／#79／#82／#90 | master index | E1/E2 |
| 9 | CFL 0.10固定列でfront persistence、cell 30 localized chatterを観測 | Gate 6／7 closeout | artifacts 8730632937／8744210262 | E1/E2/E3 |
| 10 | Gate 8は3列formal outcomeが分岐しpost-crossing comparability未成立 | `stage7_gate8_closeout.md` | artifact 8761925785 | E1/E2/E3 |
| 11 | 類似するCO₂音速・数値法・relaxation問題が文献に存在 | Gate 9 literature review／registry | primary papers | E3 |
| 12 | physical validation、design use、production activationは未成立 | current snapshot | Gate 5〜8 closeout | E4=false |
| 13 | Gate 9とU3 discharge component benchmarkを分離して進める | Gate 9 contract／U3 spec | application strategy | E3 |
| 14 | current pathはverification baselineでありdesign modelではない | chapter 6〜13 evidence | report contract | E1-E4 |

---

# 4. Stage 1〜6基礎証拠

Stage 1〜6は、本文では機能の羅列ではなく、二相検討へ進む前の基礎層として
まとめる。詳細は付録A／Eへ置く。

| ID | Verification item | Status | 本文で使う主要結論 | Authoritative record |
|---|---|---|---|---|
| V-001 | CoolProp backend traceability／API | COMPLETE | backend名・version・未承認statusを追跡可能 | archived master index |
| V-002 | Uniform-state preservation | COMPLETE | 静止一様状態とbudget residualを保持 | archived master index |
| V-003 | CoolProp Case C mini-run | COMPLETE | CoolPropを通る基本計算経路を確認 | archived master index |
| V-004 | Small-amplitude incident wave | COMPLETE | 波の方向、到達、単相維持を確認 | archived master index |
| V-005 | Incident-wave mesh／CFL | COMPLETE | mesh／CFLによる数値広がりを観測 | archived master index |
| V-006 | Incident-wave report／manifest | COMPLETE | formal reportとSHA256を整備 | archived master index |
| V-007 | Incident-wave CI-light | COMPLETE | permanent regressionを整備 | archived master index |
| V-008 | GitHub Actions CoolProp | COMPLETE | CoolProp installed CIをskipなし実行 | archived master index |
| V-009 | Rigid-wall reflection | COMPLETE | pressure正反射、velocity反転、zero wall flux | archived master index |
| V-010 | Fixed-pressure reflection | COMPLETE | pressure負反射、velocity正反射 | archived master index |
| V-011 | Controlled pressure step／ramp | COMPLETE | monotone boundary、front、budget、CI | archived master index |
| V-012 | Single-phase internal-valve operation | COMPLETE | opening／closing／complete closureを確認 | PR #34〜#42 records |

### Stage 6／V-012代表証拠

```text
controlled closing:
  opening 1.0 → 0.0
  post-closure hydraulic-separation fraction = 1.0
  maximum post-closure mass through-flux ≈ numerical zero
  remained single phase = true

mesh/CFL observation:
  planned / executed runs = 13 / 13
  focused tests = 12 passed
  full repository = 264 passed

formalization:
  focused tests = 14 passed
  full repository = 276 passed
  formal artifact count = 193
```

これらの値は本文で必要なものだけを選び、詳細は付録へ回す。

---

# 5. Stage 7前半およびcrossing経路

| Milestone | PR | 本文で使う結論 | Evidence type |
|---|---:|---|---|
| Incident propagation reference | #48 | actual FVM波動の方向・速度と数値広がり | E1/E2 |
| Rigid-wall reference | #49 | ideal wall reflection identity | E1 |
| Fixed-pressure reference | #50 | pressure-boundary reflection identity | E1 |
| First-order baseline formalization | #51 | first-order FVMをcontrolとして固定 | E1 |
| MUSCL/TVD scaffold | #52 | 将来改善asset、現baseline未変更 | future asset |
| Scalar-advection comparison | #53 | later numerical-diffusion comparison asset | future asset |
| HEM thermodynamic scaffold | #54 | real-fluid HEM path foundation | E1 |
| Explicit phase classification | #55 | phase categoryとguard foundation | E1 |
| Equilibrium sound-speed candidate | #56 | current acoustic closure candidate | E1/E3 |
| Uniform HEM-state preservation | #57 | HEM uniform-state behavior | E1 |
| Dynamic quality-sync specification | #59 | projection contract | E1 |
| Quality projection implementation | #60 | rho*q synchronization | E1 |
| Pressure-offset dynamic case | #61 | nonuniform projection behavior | E1/E2 |
| Equal-pressure no-op comparison | #62 | unnecessary projectionを避けるcontrol | E1 |
| First crossing specification | #64 | raw／accepted crossing contract | E1 |
| Transition classifier | #65 | phase-boundary event classification | E1 |
| Mixed accepted-state EOS | #67 | liquid／open-two-phase mixed acceptance | E1 |
| Liquid state-pair survey | #68 | crossing候補のproperty feasibility | E1/E3 |
| Actual one-step raw FVM crossing | #70 | actual first-order raw crossing | E1 |
| Projected crossing and vapor budget | #71 | accepted recovery、second no-op、budget | E1 |
| Case A／B freeze | #72 | repeatable crossing／matched liquid control | E1 |

---

# 6. Pipeline first-crossing evidence

## 6.1 Boundary-driven pressure matrix

Primary source: PR #77／`MASTER_VERIFICATION_INDEX.md`

| Case | Formal outcome | Step | Time [s] | Cell | Outlet distance [m] | max q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | ACCEPTED_FIRST_CROSSING | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | ACCEPTED_FIRST_CROSSING | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | GUARD_FAILURE | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

### 許される主張

- 2／3 MPa条件でaccepted crossingを観測した。
- 4 MPa条件で有限のsubthreshold raw crossingを観測した。

### 禁止する主張

- 4 MPa条件はall-liquid controlである。
- crossing pressureは物理的nucleation pressureである。

## 6.2 4 MPa forensic review

Primary source: PR #79

```text
retained categories:
  THERMODYNAMIC_TWO_PHASE_SUPPORTED
  NEAR_SATURATION_PROPERTY_SENSITIVE
  MULTI_FACTOR_EVIDENCE

rho/e perturbation:
  stable through relative 1e-8
  changes for some 1e-6 perturbations
```

## 6.3 Mesh sensitivity at CFL 0.10

Primary source: PR #82

| Cells | Formal result | max q_eq | normalized time | distance [m] |
|---:|---|---:|---:|---:|
| 32 | GUARD_FAILURE | `9.672588429198319e-9` | `0.9318710632753395` | `0.203125` |
| 64 | GUARD_FAILURE | `5.977506779042054e-7` | `0.8590001798084317` | `0.1484375` |
| 128 | GUARD_FAILURE | `3.8580990283897163e-7` | `0.8060444782479008` | `0.11328125` |

Retained labels:

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

---

# 7. Gate 3〜8 evidence register

| Gate | Purpose | PR／Issue | Workflow | Artifact | Main disposition |
|---:|---|---|---:|---:|---|
| 3 | cross-runtime reproduction | PR #91／Issue #85 | Ubuntu reference + Windows packet | retained records | NUMERICALLY_EQUIVALENT |
| 4 | low-CFL first crossing | PR #90／Issue #86 | 30313389184 | 8675117973 | CFL_SENSITIVITY_OBSERVED |
| 5 | near-saturation acoustic review | PR #96 | 30451125151 | 8723959176 | ACOUSTIC_REVIEW_INCONCLUSIVE |
| 6 | post-crossing propagation | PR #99 | 30466063542 | 8730632937 | fixed continuation complete; approval false |
| 7 | boundary-adjacent chatter diagnosis | PR #102 | 30501363884 | 8744210262 | MULTI_FACTOR_CHATTER; root cause false |
| 8 | post-crossing CFL matrix | PR #107／#108／Issue #105 | 30544667388 | 8761925785 | divergent non-monotone outcomes |
| 9 prep | literature and execution contract | PR #113／Issue #110 | 30679654460 | 8811747214 | contract locked; execution not started |

---

# 8. Gate 6 quantitative evidence

Primary source: `stage7_current_gate_snapshot.md`／Gate 6 artifact

| Offset | Open-two-phase cells | Indices | Furthest distance [m] | max q_eq | max alpha |
|---:|---:|---|---:|---:|---:|
| +1 | 1 | `[29]` | `0.078125` | `9.9651e-6` | `7.3594e-5` |
| +4 | 2 | `[28,29]` | `0.109375` | `2.7667e-5` | `2.0583e-4` |
| +16 | 4 | `[27,28,29,30]` | `0.140625` | `1.3211e-4` | `9.3335e-4` |
| +64 | 7 | `[24,25,26,27,28,29,30]` | `0.234375` | `1.2605e-3` | `9.0086e-3` |

### 許される主張

- fixed CFL 0.10列でregionがpersistし、furthest upstream位置が移動した。
- successful statesでbudget evidenceを保持した。

### 禁止する主張

- 上表がphysical front speedのvalidationである。
- 64 stepsでmesh／CFL independenceを確認した。

---

# 9. Gate 7 quantitative evidence

Primary source: `stage7_current_gate_snapshot.md`／Gate 7 closeout

```text
cell 29: 0 toggles; stable OPEN_TWO_PHASE
cell 30: 49 toggles; localized chatter
cell 31: 0 toggles; stable LIQUID_CANDIDATE
focused cell records: 576
focused interface records: 192
transition events: 49
```

Retained labels:

```text
STABLE_FRONT_SEPARATED_FROM_CHATTER
PHASE_MARGIN_OSCILLATION_CORRELATED
ACOUSTIC_BRANCH_SWITCH_CORRELATED
PROJECTION_ACTIVITY_CORRELATED
MULTI_FACTOR_CHATTER
CHATTER_REVIEW_INCONCLUSIVE
```

### 許される主張

- cell 30のregion changesは、両saturation margin、acoustic branch、projection activityと同期した。
- stable front cellとlocalized chatter cellを分離して観測した。

### 禁止する主張

- projectionがroot causeである。
- boundary fluxがroot causeである。
- chatter mitigationが承認された。

---

# 10. Gate 8 quantitative evidence

Primary source: `stage7_gate8_closeout.md`／artifact `8761925785`

| CFL | First crossing | Step | Time [s] | Cell | max q_eq | Continuation | Checkpoints |
|---:|---|---:|---:|---:|---:|---|---|
| 0.10 | ACCEPTED_FIRST_CROSSING | 125 | `7.999325695335248e-4` | 29 | `3.773646403587342e-6` | COMPLETED_FIXED_CHECKPOINTS | T1〜T4 |
| 0.05 | GUARD_FAILURE | 249 | `7.967173062790038e-4` | 29 | `1.1006096906989802e-7` | NOT_STARTED | none |
| 0.025 | ACCEPTED_FIRST_CROSSING | 499 | `7.981201399992095e-4` | 29 | `1.3949366092287805e-6` | ACOUSTIC_REFUSAL after 64 valid steps | T1／T2 |

All candidate locations: `0.078125 m` from outlet.

CFL 0.025 additional evidence:

```text
last valid absolute step:        563
last valid elapsed:              9.542346840227527e-5 s
T3 target:                       9.544429181626145e-5 s
cell-30 region changes:          15
last valid state SHA256:         8692bf59750a25ebf40c7c87577a11e479deb040f9a207ded118ed333a462653
failure:                         no valid central rho stencil after 12 halvings
```

Retained labels:

```text
FIXED_HORIZON_OUTCOME_DIVERGENCE
CFL_SEQUENCE_NON_MONOTONE
POST_CROSSING_CFL_REVIEW_INCONCLUSIVE
```

### 許される主張

- Gate 8 fixed executionは完了した。
- crossing depthとformal outcomeはCFLに対して非単調であった。
- post-crossing comparabilityは成立しなかった。
- acoustic evaluatorがunchanged guardで停止した。

### 禁止する主張

- CFL 0.025が0.05より物理的に正しい。
- acoustic refusalが物性backendだけの欠陥である。
- CFL independenceを確認した。

---

# 11. Literature evidence

Primary source: `stage7_gate9_literature_review.md`／registry

| Literature group | Report use | Claim limit |
|---|---|---|
| CO₂ depressurization + discontinuous sound speed | observed issueの公知性を示す | current caseと同一原因とは断定しない |
| HRM／finite-rate phase transfer | HEM model-dependenceの将来比較根拠 | Gate 9中のmodel replacementを正当化しない |
| Two-fluid non-equilibrium validation | long-duration validation roadmap | HEMを一律に棄却しない |
| HEM／two-fluid experimental comparison | case-specific model adequacy | universal superiorityを主張しない |
| Relaxation hierarchy／subcharacteristic | intrinsic acoustic reference候補 | current c formula validationとは扱わない |
| Roe／MUSTA／WENO／preconditioning | later numerical comparison候補 | Gate 9 baseline変更には使わない |

---

# 12. Application-track evidence

Primary source: `stage7_real_problem_application_strategy.md`

## Current confidence classes

```text
fixed prescribed-boundary 5→2 MPa analogue: C2
physical blowdown prediction:                 C1 or below
ESD-valve HEM result:                         C1 or below
pump-trip HEM result:                         C1 or below
approved design use:                          not reached
```

## U3 pilot ladder

```text
P0 prescribed-boundary verification analogue
P1 physical orifice／discharge component benchmark
P2 friction and wall thermal inventory
P3 integrated pipe + blowdown device benchmark
P4 physical-data validation
P5 sensitivity-bounded engineering screening
```

### 報告書での使い方

- current pipeline caseがP0であることを示す。
- prescribed boundaryとphysical discharge boundaryを区別する。
- B0／B1／integrated workの位置づけを示す。

---

# 13. Approval boundary for final claim audit

最終稿で次をtrueとしてはならない。

```text
post_crossing_CFL_sensitivity_characterized
CFL_independent_post_crossing_verified
mesh_independent_post_crossing_verified
post_crossing_propagation_approved
phase_chatter_root_cause_approved
chatter_mitigation_authorized
near_saturation_acoustic_continuity_approved
two_phase_acoustic_accuracy_band_approved
Gate_P2_passed
physical_validation
design_use_acceptance
production_hem_activation_approved
```

Gate 8についてtrueとできるのは、次のみである。

```text
Gate_8_execution_complete
formal_outcome_comparison_complete
```

Gate 9については、本報告書v0.1では次の状態である。

```text
literature review:              complete for initial screening
execution contract:            locked
contract CI:                   passed
forensic execution:            not started
root-cause approval:           false
```

---

# 14. Evidence gaps before full drafting

本文開始前に、次の確認を行う。

1. Stage 1〜6の正式なStage名称とV-ID対応を再確認する。
2. Chapter 2〜4で使用するproduction source fileと式をsource SHA付きで登録する。
3. Gate 6／7 artifactから本文掲載用figureを選定する。
4. Gate 8 artifact figureの軸、単位、captionを再確認する。
5. PR #72のCase A／B定量表をauthoritative artifactから抽出する。
6. Gate 4 low-CFL matrixの本文掲載範囲を確定する。
7. 公知文献14件のbibliographic formatを統一する。
8. 図再生成のrecipeまたはartifact sourceをfigure registerへ記録する。
