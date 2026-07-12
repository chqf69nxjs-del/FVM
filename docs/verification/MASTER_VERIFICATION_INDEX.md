# MASTER VERIFICATION INDEX

この文書はverification活動のsingle entry pointである。作業再開時は、現在地、成果物、制約、次の作業をここで確認する。

## 1. Restart here

### 現在地

- Stage 1〜5のCoolProp単相CO2 software / numerical verificationは完了。
- Stage 5ではrigid-wall / fixed-pressure reflectionの仕様、telemetry、baseline、可視化、mesh/CFL、CI-light、formal report、SHA256 manifest、GitHub Actionsを整備済み。
- PR #28はマージ済み。merge commitは`e3fdccaef86e566b5d1d210c13862ff1f2b7d365`。
- Stage 6のcontrolled pressure rampおよびsingle-phase valve operationは仕様化を開始。
- Stage 6では実装前に入力、理論応答、timing、flux、budget、artifact、停止条件を固定する。
- V-011 / V-012およびStage 6は`IN_PROGRESS`。
- `property_backend_design_status = not_approved_for_design_use`。
- physical Validation、design acceptance、two-phase verificationは未実施。

### 直近完了段階

Stage 5 PR-D formalization

- V-009 / V-010: `COMPLETE`
- Stage 5: `COMPLETE`
- Windows: report 3 passed、import-order 2 passed、boundary regression 10 passed、sweep 4 passed、baseline reflection 6 passed。
- GitHub Actions: `CoolProp Wave Regression` success、`CoolProp Boundary Reflection Regression` success。
- formal artifact count: 58
- report SHA256: `9589276f8b1c3d5fa5f0b704d9fd912ba22340f31d44c2113808cf115430b15c`

### 次の段階

Stage 6 単相境界操作・部品 verification

### Next action

1. Stage 6 specificationをレビューしてマージする。
2. controlled pressure ramp runnerを実装する。
3. schedule、boundary、probe、budget telemetryを追加する。
4. pure testsとinstalled-CoolProp baselineを実行する。
5. その後、internal valve operationへ進む。

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
| V-011 | Controlled pressure step/ramp | IN_PROGRESS | Stage 6 specification追加 | runner未実装 | controlled pressure ramp runner |
| V-012 | Single-phase valve operation | IN_PROGRESS | Stage 6 specification追加、既存Kv/interface survey | operation runner未実装 | V-011後にinternal valve runner |
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

Scope:

- controlled pressure rampをprimary pressure-input caseとする。
- mathematical stepはsecondary observationとする。
- internal valveをprimary valve componentとする。
- boundary valveは補助対象とする。
- ESD eventはStage 9へ残す。

## 6. Roadmap

| Stage | Status | Remaining work |
|---|---|---|
| Stage 1〜5 | COMPLETE | Validation / design-use approvalは別問題 |
| Stage 6 | IN_PROGRESS | controlled pressure ramp、internal valve operation |
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
- Stage 6 specification開始。V-011 / V-012を`IN_PROGRESS`へ移行。
