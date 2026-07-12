# MASTER VERIFICATION INDEX

この文書は verification 活動の single entry point / master index である。作業再開時は、まず本書で現在地、完了事項、成果物、制約、次の作業を確認する。

## 1. Restart here

### 現在地

- Stage 1〜5 の CoolProp 単相 CO2 software / numerical verification は完了。
- Stage 5 では rigid-wall / fixed-pressure boundary reflectionについて、仕様、boundary telemetry、baseline runner、可視化、mesh/CFL observation、CI-light regression、formal report、SHA256 manifest、GitHub Actionsを整備した。
- PR-Cの8 unique runsはすべて完走し、`overall_sweep_execution_pass = True`。
- rigid wall / fixed pressureとも、反射係数誤差、characteristic leakage、waveform differenceはmesh refinementで改善した。
- rigid wallのboundary residualは50 / 100 / 200 cellsで0。
- fixed pressureのnormalized pressure residualは`0.06006 -> 0.05975 -> 0.04892`と改善した。
- arrival-time metricはrigid wallで約`1e-5`の微小非単調、fixed pressureで`0.01638 -> 0.00825 -> 0.00828`と改善後plateauしたため、mesh classificationは`mixed_behavior`。
- 主要shape / reflection指標の改善傾向が明確なため、Stage 5では400-cell runを追加していない。
- Stage 5 CI-light profileは両境界の`n_cells = 50`, `CFL = 0.5`を使用し、WindowsとGitHub Actionsでpassした。
- formal reportとSHA256 manifestをPR-C成果物から生成済み。manifest artifact countは58、report SHA256は`9589276f8b1c3d5fa5f0b704d9fd912ba22340f31d44c2113808cf115430b15c`。
- `property_backend_design_status = not_approved_for_design_use`。
- physical Validation、design acceptance、two-phase verificationは未実施。

### 直近完了段階

Stage 5 PR-D formalization

- regression band specificationをPR-C実測値から確定。
- budget relative residual bandはmass / energy / vapor massすべて`1e-12`。
- pure evaluator、2-boundary CI-light runner、import-order regression testを追加。
- formal Stage 5 report generatorとSHA256 manifest generatorを追加。
- Windows focused tests: report 3 passed、import-order 2 passed、boundary regression 10 passed、sweep 4 passed、baseline reflection 6 passed。
- actual formal artifacts: report / manifest生成成功、artifact count 58、full sweep pass。
- GitHub Actions: `CoolProp Wave Regression` success、`CoolProp Boundary Reflection Regression` success。

### 次の段階

Stage 6 単相境界操作・部品 verification

### Next action

Stage 6は実装より先に仕様を固定する。

1. controlled pressure stepの入力定義、理論応答、timing、budget、artifact、停止条件を仕様化する。
2. single-phase valve operationの弁則、開度履歴、圧力波応答、保存性、artifact、停止条件を仕様化する。
3. Stage 5のideal boundary reflectionとStage 6の時間依存境界操作を混同しない。
4. solver変更は仕様レビュー後に行う。

## 2. Resume checklist

```powershell
git switch main
git pull origin main
$env:PYTHONPATH = "src"
python -m pytest -q
Get-Content docs/verification/MASTER_VERIFICATION_INDEX.md
git switch -c <new-work-branch>
```

確認順序:

1. mainを更新する。
2.全testを実行する。
3.直近のCoolProp workflowsを確認する。
4.本書の`Next action`を読む。
5.最新formal report / manifestを確認する。
6.新しいbranchで作業する。

## 3. Status definitions

| Status | Definition |
|---|---|
| `PLANNED` | 作業対象として登録済みだが、仕様・実装・判定は未完了。 |
| `IN_PROGRESS` | 仕様化、実装、実行、レビューのいずれかが進行中。完了判定はまだ出していない。 |
| `OBSERVED` | 実行結果は確認済みだが、formal gate、report、manifest、CI、再現手順のいずれかが不足。 |
| `COMPLETE` | test、成果物、判定、再現手順が揃い、同じ確認を追跡できる。 |
| `BLOCKED` | 外部依存、未決仕様、環境制約、設計判断待ちで停止中。 |

## 4. Master verification table

| ID | Verification item | Status | Current evidence | Open limitations | Next action |
|---|---|---|---|---|---|
| V-001 | CoolProp backend traceability/API | COMPLETE | backend名と`not_approved_for_design_use`を出力・判定に保持 | design-use approval未実施 | statusを後続stageでも維持 |
| V-002 | Uniform-state multistep preservation | COMPLETE | 静止一様状態とbudget residualを確認 | physical Validationではない | solver変更時に再実行 |
| V-003 | CoolProp Case C mini-run | COMPLETE | CoolProp経路と未承認statusを確認 | design-use / Validationではない | 必要時に再評価 |
| V-004 | Small-amplitude Gaussian incident wave | COMPLETE | CoolProp音速、到達時刻、単相維持を確認 | finest gridは厳密解でない | 後続wave verificationに再利用 |
| V-005 | Incident-wave mesh/CFL sweep | COMPLETE | 50 / 100 / 200 / 400 cellsとCFL比較 | formal design thresholdではない | scheme変更時に再実行 |
| V-006 | Incident-wave formal report / manifest | COMPLETE | formal reportとSHA256 manifest生成済み | local/gitignored artifactの可能性 | artifact schema変更時に更新 |
| V-007 | Incident-wave CI-light regression | COMPLETE | `coolprop_wave_ci_light_v1` pass | n=50はdesign meshでない | solver変更時に再実行 |
| V-008 | GitHub Actions CoolProp regression | COMPLETE | CoolProp 8.0.0 skipなしworkflow pass | design-use approvalではない | workflow/backend変更時に再実行 |
| V-009 | Closed/rigid-wall reflection | COMPLETE | positive reflection、wall velocity / mass / energy flux 0、mesh improvement、CI-light、formal report/manifest | infinite-impedance idealization、実弁ではない | solver/boundary変更時に再実行 |
| V-010 | Fixed-pressure reflection | COMPLETE | negative reflection、boundary exchange、mesh improvement、CI-light、formal report/manifest | zero-impedance idealization、実reservoirではない | solver/boundary変更時に再実行 |
| V-011 | Controlled pressure step | PLANNED | 未着手 | 未仕様化 | Stage 6 specification |
| V-012 | Single-phase valve operation | PLANNED | 未着手 | 未仕様化 | Stage 6 specification |
| V-013 | MOC / linear-acoustic cross verification | PLANNED | 未着手 | MOCはverification用に限定 | Stage 7 |
| V-014 | Saturation-near property sanity | PLANNED | 未着手 | reference/backend gate未定 | Stage 8前 |
| V-015 | HEM minimum phase-change problem | PLANNED | 未着手 | physical Validation未実施 | Stage 8/9 |
| V-016 | HNE / relaxation | PLANNED | 未着手 | `tau`未確定 | Stage 9 |
| V-017 | Event-level ESD / pump trip | PLANNED | 未着手 | event verification未仕様化 | Stage 9 |
| V-018 | Physical Validation | PLANNED | 未着手 | independent data / criteria未設定 | Stage 10 |
| V-019 | Design-use acceptance | PLANNED | 未着手 | approved backend / formal threshold / review gate未整備 | Stage 10 |

## 5. Current evidence and artifact paths

### Stage 1〜4

```text
verification/coolprop_small_amplitude_wave_sweep_final_v1/
```

主要成果物:

- sweep metrics JSON / summary CSV / report Markdown
- formal verification report
- SHA256 manifest
- comparison PNG
- per-run directories
- CI-light regression JSON

### Stage 5 baseline

```text
verification/boundary_reflection_rigid/
verification/boundary_reflection_fixed_pressure/
```

各case:

- `*_config.json`
- `*_metrics.json`
- `*_probe_history.csv`
- `*_boundary_history.csv`
- `*_final_profile.csv`
- `*_report.md`
- `*_probe_pressure_history.png`
- `*_characteristic_history.png`
- `*_boundary_face_history.png`
- `*_boundary_flux_budget_history.png`

### Stage 5 full sweep and formal artifacts

```text
verification/boundary_reflection_sweep_pr_c/
```

主要成果物:

- `coolprop_boundary_reflection_sweep_sweep_config.json`
- `coolprop_boundary_reflection_sweep_sweep_metrics.json`
- `coolprop_boundary_reflection_sweep_sweep_summary.csv`
- `coolprop_boundary_reflection_sweep_sweep_report.md`
- `coolprop_boundary_reflection_verification_report_v1.md`
- `coolprop_boundary_reflection_verification_manifest_v1.json`
- comparison PNG files
- 8 per-run directories

Formal artifact result:

- `artifact_count = 58`
- `report_sha256 = 9589276f8b1c3d5fa5f0b704d9fd912ba22340f31d44c2113808cf115430b15c`
- `overall_sweep_execution_pass = True`
- `property_backend_design_status = not_approved_for_design_use`

CI-light profile:

```text
coolprop_boundary_reflection_ci_light_v1
```

- rigid wall: n=50, CFL=0.5
- fixed pressure: n=50, CFL=0.5
- both GitHub Actions and Windows installed-CoolProp execution passed

## 6. Roadmap

| Stage | Status | Remaining work |
|---|---|---|
| Stage 1〜5 | COMPLETE | physical Validation / design-use approvalは別問題 |
| Stage 6 | PLANNED | controlled pressure step、single-phase valve operation |
| Stage 7 | PLANNED | MOC / linear acoustic cross verification |
| Stage 8 | PLANNED | saturation-near property sanity、minimum phase-change problem |
| Stage 9 | PLANNED | HEM/HNE、ESD/pump trip event verification |
| Stage 10 | PLANNED | physical Validation、design-use acceptance |

## 7. Do not forget

- regression passはValidationではない。
- finest-grid referenceは厳密解ではない。
- lower CFLは真値ではない。
- `n = 50`はdesign meshではない。
- CoolProp backendはdesign-use未承認。
- regression bandをtest通過目的だけで緩めない。
- fixed pressureはzero-impedance idealizationであり、実reservoirと同一視しない。
- rigid wallはinfinite-impedance idealizationであり、実弁と同一視しない。

## 8. Update rule

verificationに関係するPRでは、同じPR内で本書を更新する。最低限、status、artifact、reference commit、test command、regression band、backend version、next action、known limitationが変わった場合に更新する。

## 9. Change history

- Stage 1〜4: incident-wave verification、formal report / manifest、CI-light、GitHub Actions完了。
- PR #21: Stage 5 boundary-reflection specification。
- PR #22: boundary telemetry / helpers。
- PR #23: rigid-wall / fixed-pressure baseline runners。
- PR #24: result plots and boundary flux / cumulative budget visualization。
- PR #25: baseline evidenceをmaster indexに同期。
- PR #26: Stage 5 mesh/CFL sweep。8 runs pass、主要shape / reflection metrics改善、400-cell追加なし。
- PR #27: PR-C evidenceをmaster indexに同期し、PR-D planを固定。
- PR #28: Stage 5 regression bands、CI-light、formal report / manifest、GitHub Actions、completion review。
- Next action: Stage 6 specification。
