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

D1、D2、D3では、それぞれcell state、Rusanov flux、acoustic trialを観測できるようにした。ただし、独立した記録だけでは、どの現象がcandidate transitionより前に起き、どの現象が後に起きたかを厳密に比較できない。

D4第1増分では、固定CFL `0.10`について、各証拠を次の共通座標へ対応付ける。

```text
absolute step
physical time
dt
cell / interface
state stage
candidate-relative step
```

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

既存formal pathはcandidateで停止するため、後8 stepを作る目的で計算を継続しない。artifactには、

```text
post_window_status = NOT_AVAILABLE_DUE_TO_FORMAL_STOP
```

を明示する。

## 3. exact state stage

既存runnerを変更せず、D4 context中だけ一時wrapperを設置し、すでに存在する配列のcopyを取得する。

```text
PRE_STEP_ACCEPTED
RAW_POST_FVM
POST_FIRST_PROJECTION
POST_SECOND_PROJECTION
FINAL_ACCEPTED
```

各copyはnon-writeableとし、対象cell `28 / 29 / 30 / 31`の保存変数を記録する。

固定ケースではsource、friction、heat、gravity、production phase-change operatorが無効であるため、`RAW_POST_FVM`は既存`FvmSolver.step()`が返したpost-step stateをそのまま保持する。

## 4. D2 flux alignment

D2のproduction Rusanov observerを同じdiagnostic-on runへ組み込み、対象interfaceの記録をstep `117...125`へ切り出す。

```text
27|28
28|29
29|30
30|31
RIGHT_BOUNDARY
```

central成分とdissipative成分は、引き続きproduction fluxをnormalized residual `<= 5e-13`で再構成しなければならない。

## 5. D3 acoustic alignment

D4は、既存classとfunctionへcontext中だけ一時wrapperを設置する。

- `FvmSolver.compute_dt / primitive / step`
- production fluxへ渡すEOS proxy
- `VerificationHEMLiquidOpenTwoPhaseEOS.primitive_from_conserved`
- scalar `_evaluate_scalar`
- pipeline moduleが参照する`run_one_projected_fvm_case`

これにより、D3 acoustic eventへ次を付与する。

```text
absolute step
physical time
dt
cell index
stage
vector role
```

production methodの戻り値、exception、評価順序、cache、flux、音速式は変更しない。context終了時には、すべてのmethod/function参照を元へ復元する。

## 6. 非侵襲性

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

D4 wrapperはstateを補正せず、EOSを追加評価せず、formal stop後に継続しない。

## 7. 成果物

```text
summary.json
event_aligned_exact_cell_stage_history.csv
event_aligned_d1_cell_stage_history.csv
event_aligned_interface_flux_history.csv
event_aligned_acoustic_history.csv
candidate_event_timeline.csv
candidate_summary.json
artifact_sha256.txt
JUnit XML
```

CFL `0.10`では、予定する固定件数は以下である。

```text
window steps:                    9
exact stages per step:           5
focused cells:                   4
exact cell-stage records:        180
D1 retained cell-stage records:  108
focused interface records:       45
```

acoustic record数は、cache利用と実際のproduction evaluationに従うため固定値を事前指定しない。ただし、artifactへ含めるすべてのacoustic recordはstep/cell/stageを持たなければならない。

## 8. 明示的に行わないこと

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

## 9. 完了境界

D4第1増分の完了条件は以下である。

```text
CFL 0.10 window 117...125を固定
5 exact stagesを全window stepで取得
D1 / D2 / D3を共通step/timeへ対応付け
focused acoustic recordへcell/stageを付与
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
