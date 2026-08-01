# 液化CO₂配管過渡解析 技術報告書 — 図表台帳 v0.1

## 1. 目的

本文25〜35ページの範囲で、必要な論理を最小限の図表で伝えるための台帳である。

章別執筆設計で挙げた個別図候補は、可能な限り複合図へ統合する。本文の図表は
「見栄え」ではなく、次のいずれかを担うものだけに限定する。

```text
モデルを理解させる
検証階層を理解させる
主要な定量結果を比較させる
適用限界を明示する
次の検討の必然性を示す
```

## 2. Status definitions

| Status | Meaning |
|---|---|
| `AVAILABLE` | authoritative artifactまたはrepositoryに使用可能な図表がある |
| `REFORMAT` | dataはあるが、論文用の軸・単位・captionへ再整形が必要 |
| `NEW` | 新規模式図または集約図を作成する |
| `SELECT` | artifact内の候補から本文掲載版を選ぶ |
| `APPENDIX` | 本文ではなく付録へ配置する |
| `DEFER` | v0.1では作成しない |

## 3. Figure design rules

- 本文図は原則17点以下とする。
- 一つの主張に一つの図を対応させる。
- 色だけに依存せず、線種、marker、annotationも使う。
- physical resultとformal outcome／guardを同じ記号で混同しない。
- artifact figureはsource run、artifact ID、file名をcaptionまたは付録へ残す。
- 既存の説明用生成画像は概念整理には使えるが、定量図の代替にはしない。
- axis、unit、normalization、sampling ruleをcaptionで明示する。

---

# 4. Planned figures

## F01 — 開発対象と二つの制御トラック

```text
Type:                 conceptual composite
Status:               NEW
Chapter:              1
Priority:             P0
```

### 内容

左側にU1 ESD、U2 pump trip、U3 blowdownを配置し、中央に共通のFVM／HEM
verification baseline、右側にTrack NとTrack Aを示す。

### 中心メッセージ

> 工学適用を目指す一方、数値・モデル診断とapplication／validation planningを
> 分離して進める必要がある。

### Primary source

- `stage7_real_problem_application_strategy.md`
- `stage7_current_gate_snapshot.md`

### Claim limit

現在のU1〜U3が解析可能または承認済みとは示さない。

---

## F02 — 一次元FVMセルと保存変数

```text
Type:                 method schematic
Status:               NEW
Chapter:              2
Priority:             P0
```

### 内容

- cell average `U_i`。
- interfaces `i-1/2`, `i+1/2`。
- left／right boundary。
- `rho`, `rho*u`, `rho*E`, `rho*q`。
- flux differenceとsource。

### 中心メッセージ

> 検討全体は共通の保存形control volume上で構築されている。

### Claim limit

三次元効果や実配管の全物理項を含む図にしない。

---

## F03 — 熱力学状態処理とquality projection

```text
Type:                 thermodynamic workflow composite
Status:               NEW
Chapter:              3
Priority:             P0
```

### Panel A

CO₂ phase map上のliquid、saturation boundary、open two phase。

### Panel B

```text
PRE_STEP_ACCEPTED
→ RAW_POST_FVM
→ phase classification from rho/e
→ first projection
→ accepted mixed EOS
→ second projection exact no-op
```

### Panel C

`q_e`, `q_v`, void fractionの概念。

### Primary source

- PR #54〜#72 records。
- Gate 9 execution contract stage order。

### Claim limit

projectionをnucleation modelとして描かない。

---

## F04 — 液相／二相音速branchとCFLへの影響

```text
Type:                 acoustic conceptual diagram
Status:               NEW
Chapter:              3 / 4 / 11
Priority:             P0
```

### 内容

- liquid sound-speed band。
- open-two-phase sound-speed band。
- `|u|+c`からdtへつながる関係。
- central density stencilとhalving／refusalの模式図。

### Primary source

- Gate 5 closeout。
- Gate 7 acoustic bands。
- Gate 8 acoustic refusal。
- LIT-004／LIT-005。

### Claim limit

branch gapの物理妥当性を承認済みとして描かない。

---

## F05 — Rusanov fluxのcentral／dissipative分解

```text
Type:                 numerical-method schematic
Status:               NEW
Chapter:              4 / 13
Priority:             P0
```

### 内容

\[
F_{Rus}=\frac{F_L+F_R}{2}-\frac{a_{max}}{2}(U_R-U_L)
\]

- central component。
- dissipative component。
- adjacent-cell increment。
- Gate 9 reconstruction residual guard `5e-13`。

### Primary source

- Gate 9 execution contract。

### Claim limit

Rusanov dissipationがcrossing depthの原因と示さない。

---

## F06 — Stage 1〜Gate 9準備のverification ladder

```text
Type:                 project logic diagram
Status:               NEW
Chapter:              5
Priority:             P0
```

### 内容

```text
backend / uniform state
→ incident wave
→ reflection
→ pressure ramp / internal valve
→ independent acoustic reference
→ real-fluid HEM foundation
→ raw crossing / projection
→ pipeline first crossing
→ acoustic / propagation / chatter / CFL gates
→ Gate 9 preparation
```

各段階に「減らした不確かさ」を付す。

### Primary source

- archived master index。
- current master index。
- current gate snapshot。

### Claim limit

完了Stageをphysical validation完了の意味で表示しない。

---

## F07 — Stage 1〜6代表結果の複合図

```text
Type:                 result composite
Status:               SELECT / REFORMAT
Chapter:              6
Priority:             P1
```

### Candidate panels

- incident wave propagation。
- rigid-wall reflection。
- fixed-pressure reflection。
- internal-valve closing and zero through-flux。

### Primary source

- PR #42 formal artifact。
- PR #48〜#50 artifacts。

### Required work

- authoritative figure fileを選定。
- axis／unitを統一。
- 4 panel以内へ集約。

### Claim limit

Stage 1〜6の全結果を一図に詰め込まない。

---

## F08 — Case A／Case Bとraw→accepted crossing

```text
Type:                 result + workflow composite
Status:               REFORMAT
Chapter:              7
Priority:             P0
```

### Panel A

Case A crossing／Case B matched liquid controlの初期・target state。

### Panel B

raw FVM crossing cellのstate displacement。

### Panel C

projection後のaccepted stateとsecond no-op。

### Primary source

- PR #70〜#72 artifact。

### Evidence gap

本文用のauthoritative Case A／B figure fileと数値tableをartifactから抽出する。

### Claim limit

Case Aをphysical flashing experimentと表現しない。

---

## F09 — Prescribed-boundary pipeline analogueと2／3／4 MPa結果

```text
Type:                 setup + result composite
Status:               NEW / REFORMAT
Chapter:              8
Priority:             P0
```

### Panel A

1 m、0.10 m、32-cell pipeline、reflective left、prescribed-subcooled right。

### Panel B

2／3／4 MPaのcrossing time／position／formal outcome。

### Primary source

- PR #74／#75 specification。
- PR #77 result matrix。

### Claim limit

right boundaryをphysical orificeと描かない。

---

## F10 — First-crossing mesh／CFL sensitivity

```text
Type:                 quantitative comparison
Status:               REFORMAT
Chapter:              8
Priority:             P0
```

### Panel A

meshに対するcrossing time／position。

### Panel B

meshに対するmaximum q_eq。

### Panel C

CFLに対するmaximum q_eqとformal outcome。

### Primary source

- PR #82 artifact。
- PR #90 artifact `8675117973`。

### Claim limit

trend lineからformal convergence orderを計算しない。

---

## F11 — Gate 6 post-crossing front／quality progression

```text
Type:                 quantitative result composite
Status:               AVAILABLE / SELECT
Chapter:              9
Priority:             P0
```

### Candidate panels

- front position versus elapsed time。
- open-two-phase cell count。
- maximum q_eq／alpha。
- vapor inventory or budget residual。

### Primary source

- Gate 6 artifact `8730632937`。
- Gate 8 CFL 0.10 replay figureもcross-checkに使用可能。

### Claim limit

front positionをphysical validationされたfront speedと呼ばない。

---

## F12 — Gate 7 cell 29〜31 phase chatter diagnosis

```text
Type:                 event-aligned result composite
Status:               AVAILABLE / SELECT
Chapter:              9
Priority:             P0
```

### Candidate panels

- cell 29／30／31 region history。
- cell 30 saturation margins。
- acoustic branch。
- projection events。

### Primary source

- Gate 7 artifact `8744210262`。

### Claim limit

同期をroot causeと表現しない。

---

## F13 — Gate 8 formal-outcome matrix

```text
Type:                 principal result figure
Status:               NEW / REFORMAT
Chapter:              10
Priority:             P0
```

### Panel A

```text
CFL 0.10 accepted → T1-T4
CFL 0.05 guard → no continuation
CFL 0.025 accepted → T1/T2 → acoustic refusal
```

### Panel B

candidate time／location／maximum q_eq比較。

### Panel C

CFL 0.025 last valid timeとT3 targetの差。

### Primary source

- `stage7_gate8_closeout.md`
- artifact `8761925785`。

### Existing explanatory asset

- conversation-generated Gate 8 overview imageはlayout referenceとして使用可能。
- authoritative numeric figureはartifact dataから再生成する。

### Claim limit

0.025を0.05より正確と表現しない。

---

## F14 — Gate 8 artifact selected evidence panel

```text
Type:                 quantitative artifact panel
Status:               SELECT
Chapter:              10
Priority:             P1
```

### Candidate files

```text
front_position_vs_time.png
quality_void_fraction_vs_time.png
cell30_phase_acoustic_margin.png
chatter_frequency_comparison.png
budget_residual_comparison.png
```

### Selection rule

本文ではF13と重複しない最大2〜3 panelだけを選ぶ。全figureは付録またはartifact
referenceへ回す。

### Primary source

- Gate 8 artifact `8761925785`。

---

## F15 — HEM／HRM／two-fluidと数値手法候補の位置づけ

```text
Type:                 literature synthesis
Status:               NEW
Chapter:              11
Priority:             P1
```

### Panel A

HEM → HRM → two-fluidのrelaxation／non-equilibrium hierarchy。

### Panel B

current baselineとfuture candidates:

```text
current: first-order Rusanov HEM
future numerical: Roe / MUSTA / central-upwind / WENO / preconditioning
future model: HRM / metastable / two-fluid
```

### Primary source

- Gate 9 literature review／registry。

### Claim limit

候補を推奨採用済みとして表示しない。

---

## F16 — 現在の適用限界とvalidation ladder

```text
Type:                 applicability diagram
Status:               NEW
Chapter:              12
Priority:             P0
```

### 内容

```text
software verification
→ numerical characterization
→ model characterization
→ component benchmark
→ integrated benchmark
→ physical validation
→ design use
```

現在位置を複数軸で示す。

### Primary source

- application strategy。
- current gate snapshot。

### Claim limit

単一の進捗率barにして、異なる証拠レベルを一つの百分率へ潰さない。

---

## F17 — Track N／Track Aの将来ロードマップ

```text
Type:                 roadmap composite
Status:               NEW
Chapter:              13
Priority:             P0
```

### Panel A — Track N

Gate 9 → mesh → flux/acoustic discrimination → long duration → model comparison。

### Panel B — Track A

B0 → adapter → B1 → physical boundary → integrated blowdown → validation。

### Panel C — Merge conditions

両trackが合流するために必要なevidence。

### Primary source

- Gate 9 contract。
- U3 physical discharge specification。
- B0 contract。
- application strategy。

### Existing explanatory asset

conversation-generated physical-discharge infographicはconcept sourceとして使用可能。

### Claim limit

roadmapをdate commitmentとして表現しない。

---

# 5. Planned tables

## T01 — 主張範囲／非主張範囲

```text
Chapter:        1
Status:         NEW
Priority:       P0
```

Authorized claimsとprohibited claimsを対比する。

## T02 — 保存変数と単位

```text
Chapter:        2
Status:         NEW
Priority:       P0
```

`rho`, `rho*u`, `rho*E`, `rho*q`およびprimitive quantitiesを整理する。

## T03 — 検証段階ごとの物理項

```text
Chapter:        2
Status:         NEW
Priority:       P1
```

friction／heat／gravity／phase transfer／boundary modelの有効・無効を整理する。

## T04 — Phase category／formal outcome／guard dictionary

```text
Chapter:        3 / Appendix C
Status:         NEW
Priority:       P0
```

本文は主要category、付録は完全一覧とする。

## T05 — Boundary modelとverification purpose

```text
Chapter:        4
Status:         NEW
Priority:       P1
```

reflective、fixed pressure、pressure ramp、internal valve、prescribed-subcooled outlet、
future physical dischargeを区別する。

## T06 — Stage／Gate verification hierarchy

```text
Chapter:        5
Status:         NEW
Priority:       P0
```

目的、代表証拠、残課題を整理する。

## T07 — Stage 1〜6 representative evidence

```text
Chapter:        6
Status:         REFORMAT
Priority:       P1
```

V-001〜V-012を本文用に集約する。完全版は付録A。

## T08 — Case A／Case B crossing evidence

```text
Chapter:        7
Status:         REFORMAT
Priority:       P0
```

初期条件、target、raw outcome、projection、budget、SHAを整理する。

## T09 — 2／3／4 MPa pipeline matrix

```text
Chapter:        8
Status:         AVAILABLE
Priority:       P0
```

PR #77 matrixを論文形式へ再整形する。

## T10 — Mesh／first-crossing CFL sensitivity

```text
Chapter:        8
Status:         REFORMAT
Priority:       P0
```

meshとCFLを別subtableとし、formal outcomeを含める。

## T11 — Gate 6 T1〜T4 checkpoints

```text
Chapter:        9
Status:         AVAILABLE
Priority:       P0
```

front position、q_eq、alphaを整理する。

## T12 — Gate 7 chatter metrics

```text
Chapter:        9
Status:         AVAILABLE / REFORMAT
Priority:       P0
```

cell 29／30／31 toggle、event count、acoustic bands、projection fraction。

## T13 — Gate 8 formal outcome matrix

```text
Chapter:        10
Status:         AVAILABLE
Priority:       P0
```

Gate 8 closeout tableをauthoritative sourceとする。

## T14 — Literature evidence matrix

```text
Chapter:        11
Status:         REFORMAT
Priority:       P1
```

phenomenon、model、method、reported issue、project use、limitation。

## T15 — Current applicability and exclusion matrix

```text
Chapter:        12
Status:         REFORMAT
Priority:       P0
```

application strategyのmatrixをGate 8／9 current stateへ更新する。

## T16 — Future gates and completion evidence

```text
Chapter:        13
Status:         NEW
Priority:       P1
```

Gate／track、input、output、completion boundary、still-false approvals。

---

# 6. Appendix-only registers

## A-F01〜A-Fxx

- full Stage 1〜6 plots。
- full Gate 6／7／8 artifact figures。
- detailed CI／runtime plots if any。

## A-T01

Full Stage／Gate／Issue／PR／workflow／artifact／SHA correspondence。

## A-T02

All formal outcomes and guard categories。

## A-T03

All approval flags by Gate。

## A-T04

All public literature registry entries。

## A-T05

Artifact and CSV schema definitions。

---

# 7. Immediate figure/table preparation order

```text
P0-1  F06 verification ladder
P0-2  F03 thermodynamic / projection workflow
P0-3  F13 Gate 8 principal result
P0-4  T13 Gate 8 formal matrix
P0-5  F11 Gate 6 progression
P0-6  F12 Gate 7 chatter
P0-7  F09 / T09 pipeline matrix
P0-8  F08 / T08 Case A/B
P0-9  F16 applicability ladder
P0-10 F17 future roadmap
```

まず主要結果の図表を固定し、その後にmethods schematicを整える。

# 8. Remaining source-identification tasks

1. PR #42 artifactからStage 6掲載候補を選定する。
2. PR #48〜#50 artifactからsingle-phase composite panelを選定する。
3. PR #72 authoritative artifactを特定し、Case A／B tableとfigureを抽出する。
4. Gate 6 artifact `8730632937`のfile listを記録する。
5. Gate 7 artifact `8744210262`のfile listを記録する。
6. Gate 8 artifact `8761925785`から本文採用figureを2〜3点に絞る。
7. 全figureの再生成recipeとsource SHAを付録Hへ登録する。
