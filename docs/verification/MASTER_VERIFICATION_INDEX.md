# MASTER VERIFICATION INDEX

この文書はverification活動のsingle entry pointである。作業再開時は、現在地、成果物、制約、次の作業をここで確認する。

## 1. Restart here

### 現在地

- Stage 1〜5のCoolProp単相CO2 software / numerical verificationは完了。
- Stage 5ではrigid-wall / fixed-pressure reflectionの仕様、telemetry、baseline、可視化、mesh/CFL、CI-light、formal report、SHA256 manifest、GitHub Actionsを整備済み。
- PR #28はマージ済み。merge commitは`e3fdccaef86e566b5d1d210c13862ff1f2b7d365`。
- Stage 6 specificationはPR #29でマージ済み。merge commitは`1ea2147868e07b594774ee14656c7320ea6b9864`。
- V-011 controlled pressure ramp baselineはPR #30でマージ済み。merge commitは`aad43b0b12fec57ad52ea70cf3cd1ce05f076623`。
- V-011 mesh/CFL observationはPR #31でマージ済み。merge commitは`90a58548158cd22c78daf7b1667707d3c99b3a62`。
- V-011 formalizationはPR #32でマージ済み。merge commitは`83bcf51322e88707835f4c500c012aa49ef5602b`。
- V-011はbaseline、telemetry、可視化、p10/p50/p90 analysis、front fit、mesh/CFL、CI-light、GitHub Actions、backend traceability、formal report、SHA256 manifestまで整備し、`COMPLETE`。
- 既存46成果物へのbackend identity backfillとformal report/manifest再生成は完了。solver rerunおよび数値結果変更はない。
- 最終Windows全体testは`223 passed in 78.44s`。
- 最新GitHub ActionsではCoolProp Controlled Pressure Ramp Regression、CoolProp Wave Regression、CoolProp Boundary Reflection Regressionがすべてsuccess。
- V-012 single-phase valve operationは仕様済みだがrunner未実装。
- Stage 6全体は`IN_PROGRESS`。
- `property_backend_design_status = not_approved_for_design_use`。
- physical Validation、design acceptance、two-phase verificationは未実施。

### 直近完了段階

V-011 controlled pressure ramp formalization

- V-011 status: `COMPLETE`
- PR #32 merge commit: `83bcf51322e88707835f4c500c012aa49ef5602b`
- Windows focused tests: `28 passed in 10.91s`
- Windows full repository tests: `223 passed in 78.44s`
- CI-light direct run: `overall_regression_pass = True`、`failed_checks = []`
- GitHub Actions installed-CoolProp regression: success、skipなし
- final artifact count: `46`
- final report SHA256: `dadc6a4a982ff24e6cdf70b70d43ca8b6dadac71ac51c31c19ac7277828a3cf2`
- property backend: `coolprop_co2`
- source CoolProp version: `8.0.0`
- property backend design status: `not_approved_for_design_use`
- overall sweep execution pass: `True`
- traceability backfill: `solver_rerun = False`、`numerical_results_changed = False`

### 次の段階

V-012 single-phase internal valve operation

### Next action

1. V-012 specificationと既存Kv/interface surveyを再確認する。
2. small controlled internal-valve operationの入力、理論応答、telemetry、停止条件を固定する。
3. baseline runnerを小規模PRで実装する。
4. visualization、mesh/CFL、CI、formalizationを順次追加する。

Stage 6ではESD event、pump trip、flashing、two-phase dischargeへ進まない。これらは後続stageで扱う。

## 2. Resume checklist

```powershell
git switch main
git pull origin main
$env:PYTHONPATH = "src"
python -m pytest -q
Get-Content docs/verification/MASTER_VERIFICATION_INDEX.md
git switch -c <new-work-branch>
```

## 3. Status definitions

| Status | Definition |
|---|---|
| `PLANNED` | 登録済みだが仕様・実装・判定は未完了。 |
| `IN_PROGRESS` | 仕様化、実装、実行、レビューのいずれかが進行中。 |
| `OBSERVED` | 実行結果はあるがformal gate、artifact、CI、再現手順のいずれかが不足。 |
| `COMPLETE` | test、artifact、判定、再現手順が揃う。 |
| `BLOCKED` | 外部依存または未決事項により停止中。 |

## 4. Master verification table

| ID | Verification item | Status | Current evidence | Open limitations | Next action |
|---|---|---|---|---|---|
| V-001 | CoolProp backend traceability/API | COMPLETE | backend名と未承認statusを保持 | design-use approval未実施 | statusを維持 |
| V-002 | Uniform-state preservation | COMPLETE | 静止一様状態とbudget residualを確認 | Validationではない | solver変更時に再実行 |
| V-003 | CoolProp Case C mini-run | COMPLETE | CoolProp経路確認 | design-use未承認 | 必要時に再評価 |
| V-004 | Small-amplitude incident wave | COMPLETE | 音速、到達時刻、単相維持 | finest gridは厳密解でない | 後続wave検証へ再利用 |
| V-005 | Incident-wave mesh/CFL | COMPLETE | 50/100/200/400およびCFL比較 | design thresholdではない | scheme変更時に再実行 |
| V-006 | Incident-wave report/manifest | COMPLETE | formal reportとSHA256 manifest | local artifactの場合あり | schema変更時に更新 |
| V-007 | Incident-wave CI-light | COMPLETE | `coolprop_wave_ci_light_v1` pass | n=50はdesign meshでない | solver変更時に再実行 |
| V-008 | GitHub Actions CoolProp | COMPLETE | CoolProp 8.0.0 skipなし | design-use approvalではない | workflow変更時に再実行 |
| V-009 | Rigid-wall reflection | COMPLETE | sign、flux、mesh、CI、formal artifacts | ideal wall | boundary変更時に再実行 |
| V-010 | Fixed-pressure reflection | COMPLETE | sign、exchange、mesh、CI、formal artifacts | ideal pressure boundary | boundary変更時に再実行 |
| V-011 | Controlled pressure step/ramp | COMPLETE | baseline、4-run sweep、CI-light、223 tests、GitHub Actions、traceable formal report/manifest | physical Validationとdesign-use approvalは別問題 | solver/BC変更時に再実行 |
| V-012 | Single-phase valve operation | IN_PROGRESS | Stage 6 specification追加、既存Kv/interface survey | operation runner未実装 | internal valve baseline runner |
| V-013 | MOC / linear-acoustic cross verification | PLANNED | 未着手 | MOCはverification用限定 | Stage 7 |
| V-014 | Saturation-near property sanity | PLANNED | 未着手 | reference gate未定 | Stage 8前 |
| V-015 | HEM minimum phase-change problem | PLANNED | 未着手 | Validation未実施 | Stage 8/9 |
| V-016 | HNE / relaxation | PLANNED | 未着手 | `tau`未確定 | Stage 9 |
| V-017 | ESD / pump trip event | PLANNED | 未着手 | event verification未仕様化 | Stage 9 |
| V-018 | Physical Validation | PLANNED | 未着手 | data/criteria未設定 | Stage 10 |
| V-019 | Design-use acceptance | PLANNED | 未着手 | approved backend/gate未整備 | Stage 10 |

## 5. Evidence and artifact paths

### Stage 1〜4

```text
verification/coolprop_small_amplitude_wave_sweep_final_v1/
```

### Stage 5

```text
verification/boundary_reflection_rigid/
verification/boundary_reflection_fixed_pressure/
verification/boundary_reflection_sweep_pr_c/
```

Stage 5 formal artifacts:

- `coolprop_boundary_reflection_verification_report_v1.md`
- `coolprop_boundary_reflection_verification_manifest_v1.json`
- artifact count 58
- report SHA256 `9589276f8b1c3d5fa5f0b704d9fd912ba22340f31d44c2113808cf115430b15c`

### Stage 6 specification

```text
docs/verification/stage6_single_phase_boundary_operation_spec.md
```

### Stage 6 V-011 baseline

```text
verification/controlled_pressure_ramp_baseline/
docs/verification/stage6_controlled_pressure_ramp_observation_notes.md
```

Key baseline artifacts:

- config / metrics JSON
- pressure schedule / probe / boundary CSV
- analysis JSON and probe observation summary CSV
- pressure-field NPZ
- p50 front-fit JSON
- diagnostic PNG plots

### Stage 6 V-011 mesh/CFL and formalization

```text
verification/controlled_pressure_ramp_sweep/
docs/verification/stage6_controlled_pressure_ramp_sweep_observation_notes.md
docs/verification/controlled_pressure_ramp_regression_band_spec.md
docs/verification/stage6_execution_log.md
```

Four unique runs:

- `n=50`, `CFL=0.5`
- `n=100`, `CFL=0.25`
- `n=100`, `CFL=0.5`
- `n=200`, `CFL=0.5`

Observed mesh trends at `CFL=0.5`:

- common p50 offset: `4.212 ms -> 2.230 ms -> 1.189 ms`
- mean p50 relative error: `5.028% -> 2.583% -> 1.352%`
- peak-amplitude error: `2.117e-7 -> 6.893e-8 -> 3.369e-8`
- characteristic leakage remained near `5.2e-6`
- wave-speed error was non-monotonic but the 200-cell result remained better than the 50-cell result
- automated overall classification: `mixed_behavior`

Formalization components:

- `coolprop_controlled_pressure_ramp_ci_light_v1`
- broad software/numerical regression limits
- installed CoolProp regression test and no-skip assertion
- GitHub Actions artifact generation/upload
- formal Markdown report generator
- SHA256 manifest generator
- exact `property_backend_name` / `coolprop_version` propagation and consistency guards
- collision-free custom CFL case IDs
- no-solver-rerun traceability backfill utility

Final formal artifacts:

- `coolprop_controlled_pressure_ramp_verification_report_v1.md`
- `coolprop_controlled_pressure_ramp_verification_manifest_v1.json`
- artifact count: `46`
- report SHA256: `dadc6a4a982ff24e6cdf70b70d43ca8b6dadac71ac51c31c19ac7277828a3cf2`
- property backend: `coolprop_co2`
- source CoolProp version: `8.0.0`
- property backend design status: `not_approved_for_design_use`

A 400-cell run is not added because the primary timing、phase、amplitude trends are already clear。

## 6. Roadmap

| Stage | Status | Remaining work |
|---|---|---|
| Stage 1〜5 | COMPLETE | Validation / design-use approvalは別問題 |
| Stage 6 | IN_PROGRESS | V-012 internal valve operation |
| Stage 7 | PLANNED | MOC / linear acoustic cross verification |
| Stage 8 | PLANNED | saturation-near property sanity、minimum phase-change |
| Stage 9 | PLANNED | HEM/HNE、ESD/pump trip |
| Stage 10 | PLANNED | physical Validation、design-use acceptance |

## 7. Do not forget

- regression passはValidationではない。
- finest meshは厳密解ではない。
- lower CFLは真値ではない。
- CI-light meshはdesign meshではない。
- CoolProp backendはdesign-use未承認。
- Kv則はsingle-phase liquid relationであり、flashing/choked discharge modelではない。
- current valve hydraulic-loss proxyはdiagnosticであり、`rhoE`から除去されていない。
- bandをtest通過目的だけで緩めない。

## 8. Update rule

verification関連PRでは同じPR内で本書を更新する。status、artifact、commit、test、band、backend、next action、limitationが変わった場合に同期する。

## 9. Change history

- Stage 1〜4: incident-wave verification完了。
- PR #21〜#28: Stage 5 specificationからformalizationまで完了。
- PR #28 merge commit: `e3fdccaef86e566b5d1d210c13862ff1f2b7d365`。
- PR #29: Stage 6 specificationをマージ。merge commit `1ea2147868e07b594774ee14656c7320ea6b9864`。
- PR #30: V-011 baseline observationをマージ。merge commit `aad43b0b12fec57ad52ea70cf3cd1ce05f076623`。
- PR #31: V-011 mesh/CFL observationをマージ。merge commit `90a58548158cd22c78daf7b1667707d3c99b3a62`。
- PR #32: V-011 formalizationをマージ。merge commit `83bcf51322e88707835f4c500c012aa49ef5602b`。V-011を`COMPLETE`へ移行。
