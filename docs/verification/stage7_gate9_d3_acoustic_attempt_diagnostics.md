# Stage 7 Gate 9 D3 — 音速trial・halving履歴観測 第1増分

## 状態

```text
Issue:                           #110
前提D1:                          COMPLETE
前提D2:                          PR #117でreview対応・再検証中
増分:                            D3 / CFL 0.10 identity column
property backend:                coolprop_co2
backend design-use status:       VERIFICATION_ONLY_NOT_APPROVED_FOR_DESIGN_USE
sound-speed formula:             変更なし
central-stencil loop:            変更なし
maximum step halvings:           12のまま
one-sided fallback:              追加なし
trial clipping:                  追加なし
step/cell/stage alignment:       D4へ明示的に保留
Gate 9 execution complete:       false
```

## 1. 目的

Gate 8では、CFL `0.025`のaccepted crossing後に、既存のequilibrium
sound-speed evaluatorが有効なcentral density stencilを最大12回のhalving後にも
構成できず、`ACOUSTIC_REFUSAL`となった。

D3の目的は、音速式や拒否条件を変更することではない。既存評価器が実際に要求した
`rho/e`状態と、その採用・拒否順序を読み取り専用で記録し、次を区別可能にすること
である。

```text
trial stateのproperty評価失敗
supported scope外
center phaseとの不一致
halving後の採用
最大halving後の正直なrefusal
最終c²の採用または拒否
```

第1増分では、観測機構が既存solver pathを変えないことをCFL `0.10`で確定する。
CFL `0.025`のrefusal event windowは、D4のstep/cell/stage alignmentと組み合わせて後続
増分で取得する。

## 2. 既存production経路

既存音速評価は次の式を使う。

\[
c_{eq}^{2}
=
\left.\frac{\partial p}{\partial \rho}\right|_e
+
\frac{p}{\rho^{2}}
\left.\frac{\partial p}{\partial e}\right|_\rho
\]

密度軸と内部エネルギー軸について、それぞれcentral stencilを構成する。

```text
halving index: 0, 1, 2, ... 12
trial step:    initial_step / 2^halving_index
```

trialの両側がsupported candidateであり、固定設定でcenterと同じphase classを保つ場合
のみ採用する。条件を満たさない場合は、次のhalvingへ進む。最大12回後も成立しない
場合は、one-sided derivativeや代替音速を使わずrefusalする。

## 3. 透過proxyによる観測

production moduleの`_central_stencil`、`_evaluate_guarded`、音速式は変更しない。
D3 context中だけ、module dispatchの`estimate_equilibrium_sound_speed`参照を透過wrapper
へ差し替える。

wrapperは、元のestimatorへ渡すproperty evaluatorをproxyで包む。proxyは、

```text
要求されたrho/e
返されたpressure
phase class
scope status
backend exception type
```

を記録してから、同じsampleをそのまま返す。または同じexceptionをそのまま再送出
する。元のestimatorは1回だけ実行される。

context終了時は、`finally`で元のdispatch参照へ復元する。nested contextは拒否する。
この仕組みはsingle-threaded verification runner専用であり、production defaultとして
有効化しない。

## 4. attempt sequenceの再構成

proxyが取得したproperty-call sequenceを、固定configと元のcentral-stencil順序に照合
する。診断側は新しいtrialを生成せず、すでに実行された呼出しだけを分類する。

各attemptでは次を保存する。

```text
evaluation_id
event_kind
axis: rho / e
center rho/e and center phase
base density / energy increment
halving index
trial step
rho-minus / rho-plus
e-minus / e-plus
minus / plus validity
minus / plus phase-or-scope category
accepted / refused
refusal category
backend error type
```

各音速評価の最後には`EVALUATION_RESULT`を1件保存し、採用時は計算済みの
`sound_speed_squared`を記録する。

## 5. 非侵襲性

D3 observer OFFとONで、次を完全一致させる。

```text
formal outcome / failure reason
step count / final time
candidate step / time / cell / maximum q_eq
final state SHA256
run signature SHA256
full time history
full pressure history
full accepted-state history
```

第1増分のimmutable referenceは次のとおりである。

```text
CFL:                0.10
formal outcome:     ACCEPTED_FIRST_CROSSING
candidate step:     125
candidate time:     0.0007999325695335248 s
candidate cell:     29
maximum q_eq:       3.773646403587342e-06
```

## 6. 単体テスト契約

### 初回trial採用

密度軸・energy軸ともhalving index `0`だけを記録し、余分なproperty callを行わない。

### phase mismatchによるhalving

trial stepが厳密に、

```text
2.0 → 1.0 → 0.5
```

と半減し、phaseが一致したindexで初めて採用されることを確認する。

### 最大12回後のrefusal

密度軸についてindex `0…12`の13 attemptを欠落なく保存し、元の
`no valid central rho stencil found after 12 halvings` exceptionを保持する。

### observer OFF/ON scalar identity

同一analytic evaluatorに対するestimate dataclassが完全一致することを確認する。

### installed-CoolProp pipeline identity

固定CFL `0.10` pipelineをOFF/ONで独立実行し、全solver evidenceを完全一致させる。

## 7. D4との境界

D3 observerは、production acoustic evaluator全体の呼出し順を取得する。一方、
FVM step、cell index、`PRE_STEP_ACCEPTED`や`RAW_POST_FVM`などのstage metadataは、
音速estimator自身には存在しない。

したがって第1増分では、

```text
event_alignment_status:
PENDING_D4_EVENT_ALIGNED_STEP_CELL_STAGE_MAPPING
```

を明示する。unknown metadataへ仮のstep/cell値を割り当てない。

D4では、candidate前8 accepted steps、candidate step、形式上可能な後8 accepted steps
のcapture hookと組み合わせ、D3 eventを固定step/cell/stageへ対応付ける。

## 8. 明示的に行わないこと

```text
sound-speed formula変更
maximum halving count変更
one-sided fallback追加
liquid sound speed代用
trial rho/e clipping
phase classifier変更
quality projection変更
crossing threshold変更
boundary retuning
guard後の強制継続
CFL 0.05 / 0.025の因果比較
root-cause approval
physical validation
design-use acceptance
production activation
```

## 9. 完了境界

D3第1増分の完了条件は、次のとおりである。

```text
0…12のattempt orderingを記録可能
trial stepの1/2系列を検証
accept / refusal categoryを記録
各evaluationにfinal recordが存在
CFL 0.10 diagnostic OFF/ON identity
backend provenanceをartifactへ保存
dedicated / related / full testsがclean
```

完了しても、以下はfalseのままとする。

```text
Gate_9_execution_complete = false
crossing_depth_root_cause_approved = false
sound_speed_change_authorized = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
