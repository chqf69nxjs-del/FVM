# Stage 7 Gate 9 D4 — event-aligned step/cell/stage統合 第1増分

## 状態

```text
Issue:                         #110
前提D1:                        COMPLETE / main
前提D2:                        COMPLETE / main
前提D3:                        COMPLETE / main
対象列:                        CFL 0.10
candidate step:                125
candidate cell:                29
window:                        前8 accepted steps / candidate / 可能な後8 steps
post-candidate continuation:   formal stopのため作成しない
Gate 9 execution complete:     false
```

## 1. 目的

D1、D2、D3では、それぞれcell state、Rusanov flux、acoustic
trialを観測できるようにした。ただし、独立した記録だけでは、
candidate transitionに対する時間順序を厳密に比較できない。

D4第1増分では、固定CFL `0.10`について、各証拠を次の共通座標へ
対応付ける。

```text
absolute step
physical time
dt
cell / interface
state stage
candidate-relative step
```

加えて、`FvmSolver.compute_dt()`が実際に用いたprimitive stateから、
CFL時間刻み決定そのものを記録する。

## 2. 対象window

固定candidateは以下である。

```text
step:       125
time:       0.0007999325695335248 s
cell:       29
outcome:    ACCEPTED_FIRST_CROSSING
```

取得対象はstep `117...125`とする。

```text
candidate前: 8 accepted steps
candidate:   step 125
candidate後: 0 steps
```

既存formal pathはcandidateで停止するため、後8 stepを作る目的で
計算を継続しない。artifactには、

```text
post_window_status = NOT_AVAILABLE_DUE_TO_FORMAL_STOP
```

を明示する。

## 3. exact state stage

既存runnerを変更せず、D4 context中だけ一時wrapperを設置し、
すでに存在する配列のcopyを取得する。

```text
PRE_STEP_ACCEPTED
RAW_POST_FVM
POST_FIRST_PROJECTION
POST_SECOND_PROJECTION
FINAL_ACCEPTED
```

各copyはnon-writeableとし、対象cell `28 / 29 / 30 / 31`の保存変数を
記録する。

固定ケースではsource、friction、heat、gravity、production
phase-change operatorが無効であるため、`RAW_POST_FVM`は既存
`FvmSolver.step()`が返したpost-step stateをそのまま保持する。

## 4. CFL decision alignment

`compute_dt()`は、

```text
max(|u| + c)
target CFL
dx
t_endまでの残り時間
```

からproduction `dt`を決める。

D4では、`compute_dt()`内部の実primitive returnをcopyし、各stepについて
次を記録する。

```text
maximum characteristic speed
limiting cell
limiting velocity / sound speed
unconstrained CFL dt
t_end clippingの有無
production dt
measured CFL
focused cell 28...31のu / c / |u|+c
```

同じ演算でproduction `dt`をbitwiseに再構成できなければD4 failureとする。
音速estimatorが新規に呼ばれなかった場合、trial eventを推測せず、

```text
NO_NEW_SOUND_SPEED_ESTIMATOR_CALL_OBSERVED_DURING_COMPUTE_DT
```

と記録する。これは、`compute_dt()`で実際に使われたsound speedを
記録しないという意味ではない。sound speed値はproduction primitive
から直接取得する。

## 5. D2 flux alignment

D2のproduction Rusanov observerを同じdiagnostic-on runへ組み込み、
対象interfaceの記録をstep `117...125`へ切り出す。

```text
27|28
28|29
29|30
30|31
RIGHT_BOUNDARY
```

central成分とdissipative成分は、production fluxをnormalized residual
`<= 5e-13`で再構成しなければならない。

統合timelineでは、各interface record自身が保持する
`absolute_time_s`を使用する。別stageから時刻を推定せず、欠落時刻を
`0.0`で補完しない。

## 6. D3 acoustic alignment

D4は、既存classとfunctionへcontext中だけ一時wrapperを設置する。

- `FvmSolver.compute_dt / primitive / step`
- production fluxへ渡すEOS proxy
- `VerificationHEMLiquidOpenTwoPhaseEOS.primitive_from_conserved`
- scalar `_evaluate_scalar`
- pipeline moduleが参照する`run_one_projected_fvm_case`

これにより、実際に発生したD3 acoustic eventへ次を付与する。

```text
absolute step
physical time
dt
cell index
stage
vector role
```

`compute_dt()`中に新しいsound-speed estimator callが発生した場合は
`CFL_DT_EVALUATION`として記録する。cache等により新規trialが発生しない
場合は、存在しないtrialを生成しない。

production methodの戻り値、exception、評価順序、cache、flux、音速式は
変更しない。context終了時には、すべてのmethod/function参照を元へ
復元する。

## 7. 非侵襲性

D4 diagnostic OFFとONで、以下を完全一致させる。

```text
formal outcome / failure reason
step count / final time
candidate metadata
final state SHA256
run signature
full time history
full pressure history
full accepted-state history
```

D4 wrapperはstateを補正せず、EOSを追加評価せず、formal stop後に
継続しない。

## 8. 成果物

```text
summary.json
event_aligned_exact_cell_stage_history.csv
event_aligned_d1_cell_stage_history.csv
event_aligned_interface_flux_history.csv
event_aligned_acoustic_history.csv
event_aligned_cfl_decision_history.csv
candidate_event_timeline.csv
candidate_summary.json
artifact_sha256.txt
JUnit XML
```

CFL `0.10`では、固定件数は以下である。

```text
window steps:                    9
exact stages per step:           5
focused cells:                   4
exact cell-stage records:        180
D1 retained cell-stage records:  108
focused interface records:       45
CFL decision records:             9
```

acoustic record数は、cache利用と実際のproduction evaluationに従うため
固定値を事前指定しない。ただし、artifactへ含める全acoustic recordは
step/cell/stage/dtを持たなければならない。

timelineの全rowは、そのsource record自身の正のphysical timeを持つ。

## 9. 明示的に行わないこと

```text
CFL 0.05 / 0.025への展開
cross-CFL比較
threshold / tolerance変更
quality clipping
one-sided acoustic fallback
音速式変更
Rusanov flux変更
phase classifier変更
projection変更
boundary変更
guard後の強制継続
root-cause承認
physical validation
design-use acceptance
production activation
```

## 10. 完了境界

D4第1増分の完了条件は以下である。

```text
CFL 0.10 window 117...125を固定
5 exact stagesを全window stepで取得
D1 / D2 / D3を共通step/timeへ対応付け
production CFL decisionを9 stepで取得
focused acoustic recordへcell/stage/dtを付与
timelineでsource固有時刻を保持
D2 residual guardを維持
OFF/ON exact identity
専用・関連・全repository testがclean
```

本増分完了後も、以下はfalseのままとする。

```text
Gate_9_execution_complete = false
crossing_depth_CFL_sensitivity_characterized = false
crossing_depth_root_cause_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
