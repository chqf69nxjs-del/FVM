# Stage 7 Gate 9 — 実装計画 v0.1

## Status

```text
Issue:                       #110
prerequisite Gate 8:         CLOSED / COMPLETE
contract:                    stage7_gate9_execution_contract_v0p1.json
literature review:           stage7_gate9_literature_review.md
scope:                       verification-only forensic instrumentation
production changes:          prohibited
Gate 9 execution:            NOT STARTED
```

## 1. 目的

Gate 9は、Gate 8で確定した次の非単調系列を変更せず入力として扱う。

```text
CFL 0.10: accepted crossing
CFL 0.05: subthreshold guard
CFL 0.025: accepted crossing, later acoustic refusal
```

目的は、crossing深さの差と共に変化した保存量、飽和margin、Rusanov成分、音速branch、projection活動をevent-alignedに記録することである。

Gate 9はroot cause確定、閾値変更、solver改良を行わない。

---

## 2. 開発順序

### D0 — 契約と文献の固定

本PRの範囲。

```text
public-literature evidence map
priority literature registry
machine-readable Gate 9 contract
implementation plan
Issue #105 closeout
```

完了条件：

- JSONが構文的に有効
- Gate 8三列のreference値が中央記録と一致
- event window、対象cell/interface、単位、artifact、guardが結果前に固定
- 変更禁止事項が明示

### D1 — 読み取り専用instrumentation scaffold

新しい診断dataclassとwriterを追加するが、solver state、dt、formal outcomeを変更しない。

主なrecord：

```text
Gate9CellStageRecord
Gate9InterfaceFluxRecord
Gate9AcousticAttemptRecord
Gate9CandidateSummary
Gate9RunResult
```

必須テスト：

- record生成前後でsolver stateがbitwise同一
- diagnostics on/offでstep、time、outcome、state SHAが同一
- unsupported fieldは暗黙補完せず明示的にNone/category化

### D2 — Rusanov分解

既存の左右状態、物理流束、最大波速から診断専用に再構成する。

\[
F_{\mathrm{central}}=\frac{1}{2}(F_L+F_R)
\]

\[
F_{\mathrm{diss}}=-\frac{1}{2}a_{\max}(U_R-U_L)
\]

\[
F_{\mathrm{reconstructed}}=F_{\mathrm{central}}+F_{\mathrm{diss}}
\]

要求事項：

- production Rusanov fluxは変更しない
- normalized reconstruction residualは`5e-13`以下
- 各保存成分を別々に保存
- `dt/dx`を掛けた左右cellへの寄与を保存
- 不一致時は結果を解釈せずformal failure

### D3 — Acoustic attempt instrumentation

既存音速評価の試行を観測可能にする。

保存内容：

```text
initial density increment
halving index 0..12
rho-minus / rho-plus
各trial stateの有効性
phase / scope category
c^2
backend error
accepted / refused
```

禁止事項：

```text
最大halving回数変更
one-sided fallback追加
液相音速代用
trial point clipping
EOS入力の静かな修正
```

### D4 — Event-aligned capture

CFLごとのformal candidateを基準に、

```text
前8 accepted steps
candidate step
形式上許される場合のみ後8 accepted steps
```

を保持する。

各stepで次のstageを区別する。

```text
PRE_STEP_ACCEPTED
RAW_POST_FVM
POST_FIRST_PROJECTION_IF_AVAILABLE
POST_SECOND_PROJECTION_IF_AVAILABLE
FINAL_ACCEPTED_IF_AVAILABLE
```

guardやrefusal後の状態は作らない。

### D5 — 固定3列実行

実行順：

```text
1. CFL 0.10 Gate 8 identity replay
2. CFL 0.05 independent formal path
3. CFL 0.025 independent formal path
4. event window extraction
5. diagnostic reconstruction validation
6. cross-CFL table and figures
```

CFL 0.10 identity不一致時はGate 9全体を無効として停止する。

### D6 — 証拠分類

continuous measureをbinary outcomeより先に比較する。

主な比較：

```text
candidate time / position
candidate q_eq
q-u / q-v coordinates
Delta e_sat / Delta v_sat
one-step conserved-state displacement
dt and measured CFL
central / dissipative Rusanov contribution
boundary-interface contribution
sound-speed branch and c^2
projection timing
```

相関だけでroot causeを確定しない。

---

## 3. ソフトウェア境界

### 変更可能

```text
verification-only diagnostic modules
read-only hooks or callbacks
artifact writers
plots
tests
CI workflow
documentation
```

### 変更禁止

```text
production solver equations
Rusanov flux expression
CFL calculation
EOS
sound-speed formula
phase classifier
quality projection
crossing threshold
boundary schedule
formal guard logic
```

---

## 4. 予定ファイル

候補配置：

```text
src/liquid_gas_transient/
  hem_pipeline_crossing_depth_diagnosis.py
  hem_rusanov_diagnostic_decomposition.py
  hem_acoustic_attempt_diagnostics.py

tests/
  test_stage7_lco2_hem_gate9_contract.py
  test_stage7_lco2_hem_gate9_rusanov_decomposition.py
  test_stage7_lco2_hem_gate9_event_capture.py
  test_stage7_lco2_hem_gate9_execution.py

.github/workflows/
  stage7-gate9-crossing-depth-diagnosis.yml
```

実装PRで既存moduleへhookを加える場合も、診断無効時のbitwise identityを要求する。

---

## 5. テスト戦略

### Dependency-free contract tests

- JSON schema fieldの存在
- immutable problem値
- event window
- focused cells/interfaces
- artifact一覧
- approval flags
- prohibited changes

### Unit tests

- Rusanov分解の再構成
- normalized residual
- dt/dx cell contribution
- acoustic attempt record ordering
- missing post-guard historyの正直なcategory

### Integration tests

- diagnostics off/onのGate 8 identity
- CFL 0.10 exact reference
- CFL 0.05 formal guard preservation
- CFL 0.025 accepted crossingとacoustic refusal preservation
- state SHAとformal outcome不変

### CI

```text
dedicated Gate 9 tests
related Stage 7 regressions
full repository
zero authoritative skips/failures/errors
clean checkout
artifact digest
```

---

## 6. 文献を踏まえた将来分岐

Gate 9完了後、証拠に応じて別PR・別Gateで検討する。

### Acoustic reference branch

```text
model-intrinsic sound speed
Jacobian eigenvalue reference
subcharacteristic ordering
same-phase derivative reference
```

### Numerical-method comparison branch

```text
Roe
MUSTA
central-upwind
WENO / MUSCL reconstruction
preconditioning
positivity / hyperbolicity preserving limiter
```

### Physical-model comparison branch

```text
HEM
homogeneous relaxation model
metastable finite-rate model
two-fluid non-equilibrium model
```

いずれもGate 9 baselineへ混入しない。

---

## 7. 完了条件

Gate 9 execution completeと呼べるのは、以下を満たした場合のみ。

```text
Gate 8 formal outcomes are reproduced unchanged
all three CFL event windows are captured or honestly truncated by formal stop
Rusanov decomposition reconstructs production flux inside locked guard
acoustic attempt history is complete
raw crossing and projection are temporally separated
budgets remain traceable
all failures are categorized
all artifacts are generated
dedicated / related / full tests are clean
source SHA and clean checkout are retained
```

ただし完了しても、以下は自動的にtrueにならない。

```text
root cause approved
threshold change authorized
flux change authorized
sound-speed change authorized
projection change authorized
physical validation
design use
production activation
```
