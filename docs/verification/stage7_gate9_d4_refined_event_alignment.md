# Stage 7 Gate 9 D4-B — CFL 0.05 / 0.025 event alignment

## 状態

```text
Issue:                         #110
前提D1:                        COMPLETE / main
前提D2:                        COMPLETE / main
前提D3:                        COMPLETE / main
前提D4 CFL 0.10:               COMPLETE / main
対象列:                        CFL 0.05 / 0.025
mesh:                          32 cells
formal stop後の強制継続:       なし
Gate 9 execution complete:     false
```

## 1. 目的

PR #119では、CFL `0.10`のcandidate周辺について、D1 cell state、D2
Rusanov flux、D3 acoustic trial、およびproduction CFL decisionを共通の
step / time / cell / stageへ対応付けた。

本増分では同じ読み取り専用のD4観測契約を、Gate 8で固定済みの次の2列へ
展開する。

```text
CFL 0.05
CFL 0.025
```

これにより、後続D5で3 CFLを同一schemaへ統合するための列別証拠を揃える。
本増分ではcross-CFL比較、相関分類、root-cause承認を行わない。

## 2. immutable Gate 8 identity

### CFL 0.05

```text
formal outcome:             GUARD_FAILURE
candidate step:             249
candidate time:             0.0007967173062790038 s
candidate cell:             29
maximum candidate q_eq:     1.1006096906989802e-7
final state SHA256:         d18e4bdf1477c29f1183b2f3276c84e086f6cfef80c336a7f6f13616769c5a29
run signature SHA256:       1292331d53eddd7ec700d8a76bc3900a501c40f4671c758b0ae4bd5c9487cfde
failure reason:             crossing quality evidence is below the fixed minimum
```

accepted-crossing thresholdは変更しない。subthreshold candidateを強制的に
accepted crossingへ昇格させず、post-crossing continuationも開始しない。

### CFL 0.025

```text
formal outcome:             ACCEPTED_FIRST_CROSSING
candidate step:             499
candidate time:             0.0007981201399992095 s
candidate cell:             29
maximum candidate q_eq:     1.3949366092287805e-6
final state SHA256:         cb2d5859775d1b1c736e936af798c36cd8d20c73d926de9ed47bcc0aadb1f688
run signature SHA256:       5af1d089f4139b209a7bfc192a4fc5d6afda9da4031a60a1d13f0ddf683e6dd7
```

このidentityはfirst-crossing runnerの停止点である。Gate 8 continuationで後に
発生した`ACOUSTIC_REFUSAL`は別のpost-crossing eventであり、本D4-Bの
candidate windowには混在させない。

## 3. 固定event window

各列について、first retained candidateを中心に次を取得する。

```text
candidate前8 accepted steps
candidate step
candidate後最大8 accepted steps（unchanged formal pathが許す場合のみ）
```

今回のfirst-crossing runnerは両列ともcandidateで停止するため、固定windowは
次のとおりである。

```text
CFL 0.05:   step 241...249
CFL 0.025:  step 491...499
```

```text
available_pre_step_count  = 8
available_post_step_count = 0
post_window_status        = NOT_AVAILABLE_DUE_TO_FORMAL_STOP
```

formal stop後の状態は生成しない。

## 4. exact state stage

既存D4 contextを再利用し、各window stepについて対象cell `28 / 29 / 30 / 31`
の既存配列をnon-writeable copyとして取得する。

```text
PRE_STEP_ACCEPTED
RAW_POST_FVM
POST_FIRST_PROJECTION
POST_SECOND_PROJECTION
FINAL_ACCEPTED
```

CFL 0.05では、projected step自体は既存projected-FVM契約を通過した後、固定
crossing quality minimumでformal guardとなる。そのためcandidate stepの
projected stateはlast valid stateとして保持されるが、formal outcomeは
`GUARD_FAILURE`のままとする。

## 5. D1 / D2 / D3 / CFL decision alignment

各recordへ次を対応付ける。

```text
absolute step
physical time
dt
cell / interface
stage
candidate-relative step
```

対象interfaceは固定する。

```text
27|28
28|29
29|30
30|31
RIGHT_BOUNDARY
```

Rusanov central + dissipative分解は、production fluxをnormalized residual
`<= 5e-13`で再構成しなければならない。

production `compute_dt()`については、各window stepの次を保持する。

```text
maximum |u| + c
limiting cell
limiting velocity / sound speed
unconstrained CFL dt
t_end clipping
production dt
measured CFL
focused cells 28...31のu / c / |u|+c
```

保存値からproduction `dt`を同じ演算でbitwiseに再構成できなければfailureと
する。

## 6. acoustic trialの取扱い

実際にsound-speed estimator callが発生した場合のみ、D3 trial / halving eventを
保持する。EOS cache再利用により新規callがなかった場合は架空のtrialを生成しない。

production primitiveが実際に使用したsound speedは、いずれの場合もCFL decision
recordへ保存する。

## 7. 非侵襲性

各CFL列をdiagnostic OFF / ONで独立実行し、次を完全一致させる。

```text
formal outcome / failure reason
step count / final time
candidate step / time / cell / q_eq
final state SHA256
run signature SHA256
full time history
full pressure history
full accepted-state history
```

さらに、OFF / ONの両方が上記Gate 8 identityと完全一致しなければならない。

## 8. 列別成果物

各CFL directoryへ次を生成する。

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
```

固定期待件数は各列で次のとおりである。

```text
window steps:                    9
exact cell-stage records:        180
D1 retained cell-stage records:  108
focused interface records:       45
CFL decision records:              9
aligned acoustic records:        >0
```

## 9. 集約成果物

root directoryには次を生成する。

```text
summary.json
per_cfl_candidate_metrics.csv
artifact_sha256.txt
cfl_0p050/
cfl_0p025/
```

このsummaryは列別診断の完成を示すが、3 CFL比較のD5/D6を完了扱いにはしない。

## 10. 明示的に行わないこと

```text
CFL 0.10証拠の再定義
cross-CFL comparison
correlation / causal labelの付与
threshold / tolerance変更
quality clipping
one-sided acoustic fallback
sound-speed formula変更
Rusanov flux変更
phase classifier変更
projection変更
boundary変更
guard後の強制継続
0.025 post-crossing acoustic refusalの混在
root-cause承認
physical validation
design-use acceptance
production activation
```

## 11. 完了境界

本増分の技術的完了条件は以下である。

```text
CFL 0.05 / 0.025のGate 8 identityを完全再現
各列のOFF / ON identity
各列の前8 step + candidate window
5 exact stages
D1 / D2 / D3 / CFL decisionの共通時刻対応
production dtのbitwise再構成
source固有時刻
Rusanov residual guard
formal stop後の強制継続なし
専用・関連・全repository CI clean
traceable artifact
```

完了後も以下はfalseのままとする。

```text
Gate_9_execution_complete = false
crossing_depth_CFL_sensitivity_characterized = false
crossing_depth_root_cause_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
