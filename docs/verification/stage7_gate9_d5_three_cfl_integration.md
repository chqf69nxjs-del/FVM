# Stage 7 Gate 9 D5 — Three-CFL event-aligned integration

## 状態

```text
Issue:                         #110
base main SHA:                 543a6b972d31f0ea0cf7aaab27faa957ba7dcc57
D0-D3:                         COMPLETE / main
D4 CFL 0.10:                   COMPLETE / main
D4 CFL 0.05 / 0.025:           COMPLETE / main
対象CFL:                       0.10 / 0.05 / 0.025
mesh:                          32 cells
production solver changes:     none
D5 integration:                IN PROGRESS
D6 classification:             NOT STARTED
Gate 9 execution complete:     false
```

## 1. 目的

D4までに、固定32-cellケースの3 CFLについて、candidate前8 accepted stepsと
candidate stepの次の証拠が列別に揃った。

```text
exact five-stage cell states
D1 retained cell evidence
production Rusanov decomposition
acoustic trial / halving history
production CFL decisions
source-timed event timeline
```

D5では3列を再び固定順で実行・検証し、同じschemaの一つのartifactへ統合する。

```text
1. CFL 0.10 Gate 8 identity replay
2. CFL 0.05 independent formal path
3. CFL 0.025 independent formal path
4. D4 window validation
5. same-schema record integration
6. neutral cross-CFL tables and figures
```

D5はD6の相関labelやroot-cause判断を行わない。

## 2. immutable formal identities

| CFL | formal outcome | candidate step | candidate time [s] | cell | maximum q_eq |
|---:|---|---:|---:|---:|---:|
| 0.10 | `ACCEPTED_FIRST_CROSSING` | 125 | 0.0007999325695335248 | 29 | 3.773646403587342e-6 |
| 0.05 | `GUARD_FAILURE` | 249 | 0.0007967173062790038 | 29 | 1.1006096906989802e-7 |
| 0.025 | `ACCEPTED_FIRST_CROSSING` | 499 | 0.0007981201399992095 | 29 | 1.3949366092287805e-6 |

D5はこれらを変更せず入力として扱う。CFL 0.05のsubthreshold candidateを
強制acceptせず、CFL 0.025の後続`ACOUSTIC_REFUSAL`をfirst-candidate windowへ
混在させない。

## 3. same-schema integration

### Focused cell-stage history

3 CFL × 9 steps × 5 stages × 4 cellsを一つのCSVへ統合する。

```text
expected rows: 540

PRE_STEP_ACCEPTED
RAW_POST_FVM
POST_FIRST_PROJECTION
POST_SECOND_PROJECTION
FINAL_ACCEPTED
```

exact conserved stateへ、診断post-processingとして次を付与する。

```text
p / T / explicit phase class
q_u / q_v continuous saturation coordinates
q_eq / alpha
Delta e from saturated liquid
Delta v from saturated liquid
measured CFL
observed accepted sound speed and branch when available
projection deltas and exact no-op status
conservative displacement from PRE_STEP_ACCEPTED
```

phase-stateとsaturation referenceの追加評価はsolver終了後に行い、productionの
property evaluation順序やsound-speed評価回数を変更しない。D5 post-processingは
sound speedを再評価せず、D3で観測済みのaccepted `c^2`だけを対応付ける。

### Interface history

```text
3 CFL × 9 steps × 5 interfaces = 135 rows
```

production Rusanov flux、central成分、dissipative成分、左右cellへの`dt/dx`寄与を
同一schemaへ統合する。normalized residual上限は引き続き`5e-13`である。

### Projection history

```text
3 CFL × 9 steps × 4 cells = 108 rows
```

```text
RAW_POST_FVM rho*q
POST_FIRST_PROJECTION rho*q
POST_SECOND_PROJECTION rho*q
FINAL_ACCEPTED rho*q
first projection delta
second projection delta
second projection exact no-op
final state equals second projection
```

### Budget history

各window stepについて、retained step recordから次を保存する。

```text
boundary pressure
left / right mass flux rate
left / right energy flux rate
boundary vapor transport
projection vapor source
raw / projection / combined vapor residual
candidate時のfinal cumulative mass / momentum / energy / vapor residual
```

## 4. candidate tables

`per_cfl_candidate_metrics.csv`は各CFL一行で、次を保存する。

```text
formal outcome
candidate step / time / position
maximum q_eq and threshold distance
candidate dt / measured CFL / boundary pressure
q_u / q_v / Delta e / Delta v
PRE-to-RAW conservative displacement
projection delta rho*q
accepted sound speed branch
cell 29 / 31 central and dissipative increments
right-boundary Rusanov components
state SHA / run signature
```

`candidate_event_comparison.csv`はCFL 0.10との差・ratioと、continuous sequenceの
中立的なstatusだけを保存する。

```text
CONSTANT
MONOTONE_NONDECREASING
MONOTONE_NONINCREASING
NON_MONOTONE
INCOMPLETE
```

これらはD6の許可labelではなく、単なる表データである。

## 5. artifacts

```text
summary.json
per_cfl_candidate_metrics.csv
focused_cell_stage_history.csv
focused_interface_flux_decomposition.csv
candidate_event_comparison.csv
saturation_margin_history.csv
projection_history.csv
budget_history.csv
acoustic_attempt_history.csv
cfl_decision_history.csv
candidate_event_timeline.csv
report.md
candidate_quality_vs_physical_time.png
saturation_margins_vs_physical_time.png
candidate_step_flux_decomposition.png
acoustic_branch_vs_margin.png
cross_cfl_depth_comparison.png
artifact_sha256.txt
JUnit XML
```

## 6. numerical/model boundary

```text
production solver equations:             unchanged
Rusanov flux expression:                 unchanged
CFL calculation:                         unchanged
sound-speed formula:                     unchanged
production property evaluation order:    unchanged
phase classifier:                        unchanged
quality projection:                      unchanged
accepted-crossing threshold:              unchanged
boundary condition:                      unchanged
formal stop:                              unchanged
forced post-guard continuation:           none
```

## 7. approval boundary

D5完了時にtrueへできるのは、same-schema integrationの完了だけである。

```text
D5_three_cfl_integration_complete = true
D6_temporal_correlation_classification_complete = false
Gate_9_execution_complete = false
crossing_depth_CFL_sensitivity_characterized = false
crossing_depth_root_cause_approved = false
threshold_change_authorized = false
flux_change_authorized = false
sound_speed_change_authorized = false
projection_change_authorized = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## 8. 次工程

D5がmainへ確定した後、D6で次を比較・分類する。

```text
candidate time / position stability
continuous crossing depth sequence
one-step overshoot
saturation-margin displacement
central / dissipative Rusanov contribution
boundary flux imbalance
acoustic branch ordering
raw crossing and projection ordering
threshold classification discontinuity
```

相関だけで因果関係を承認しない。
