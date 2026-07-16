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
- V-012 implementation-ready specificationはPR #34でマージ済み。merge commitは`6f4bc16c38361b0fffec3267766224aff0160a90`。
- V-012A telemetry / uniform-state baselineはPR #35でマージ済み。merge commitは`128596593ae99e61289475cb79a39ec2127f72aa`。
- V-012Aでは開度`0.5`、圧力差ゼロで、raw/applied/flux-derived Qがゼロ、不要な圧力・速度変動なし、two-sided flux mismatchゼロ、software observation pass `True`を確認済み。
- V-012Aの人間確認用4図、再描画コマンド、installed-CoolProp testsを整備済み。
- Windows全体testは`234 passed in 76.82s`、plot-focused testsは`3 passed in 3.57s`。
- 最新GitHub ActionsではCoolProp Controlled Pressure Ramp Regression、CoolProp Wave Regression、CoolProp Boundary Reflection Regressionがすべてsuccess。
- V-012B small driven-flow constant-opening baselineをbranch `agent/stage6-v012b-driven-valve-baseline`で開始。
- Stage 6全体およびV-012全体は`IN_PROGRESS`。
- `property_backend_design_status = not_approved_for_design_use`。
- physical Validation、design acceptance、two-phase verificationは未実施。

### 直近完了段階

V-012A internal-valve telemetry and uniform-state baseline

- PR #35 merge commit: `128596593ae99e61289475cb79a39ec2127f72aa`
- CoolProp version: `8.0.0`
- reference density at `8 MPa`, `280 K`: `922.9172130294444 kg/m3`
- Windows plot-focused tests: `3 passed in 3.57s`
- Windows full repository tests: `234 passed in 76.82s`
- requested / actual opening: `0.5 / 0.5`
- valve pressure difference: numerical zero
- raw / applied / flux-derived Q: numerical zero
- probe pressure and velocity disturbance: no material response
- mass / energy / vapor-mass interface mismatch: numerical zero
- momentum-difference residual: numerical zero
- plotter reads existing CSV/JSON and does not rerun the solver

### 次の段階

V-012B small driven-flow constant-opening baseline

### Next action

1. `1 kPa`の左高・右低圧力差、開度`0.5`のV-012B runnerを実装する。
2. raw Kv Q、Mach-clipped applied Q、flux-derived Qの初期整合を確認する。
3. 実際のtwo-sided interface flux、probe、boundary、budget artifactsを生成する。
4. valve command/flow、probe pressure/velocity、interface consistency、budget/healthの4図を目視確認する。
5. focused / installed-CoolProp / full testsを実行し、観測結果をDraft PRへ記録する。
6. V-012B確認後にcontrolled opening / closing rampsへ進む。

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
| V-011 | Controlled pressure step/ramp | COMPLETE | baseline、4-run sweep、CI-light、GitHub Actions、traceable formal report/manifest | physical Validationとdesign-use approvalは別問題 | solver/BC変更時に再実行 |
| V-012 | Single-phase valve operation | IN_PROGRESS | PR #34 specification、PR #35 telemetry / V-012A uniform baseline、234 tests、4 review plots | driven-flow、opening/closing ramps、mesh/CFL、CI、formalization未完了 | V-012B driven-flow baseline |
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
docs/verification/v012_single_phase_internal_valve_operation_spec.md
docs/verification/stage6_execution_log.md
docs/verification/stage6_v012_execution_log.md
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

### Stage 6 V-012 specification and V-012A baseline

```text
docs/verification/v012_single_phase_internal_valve_operation_spec.md
verification/internal_valve_uniform_baseline/
```

Fixed implementation decisions:

- valve at `x/L = 0.5` in a `100 m`, `0.30 m` pipe
- left/right driven baseline pressures `8,000,500 / 7,999,500 Pa` at `280 K`
- full-open Kv derived for `1.0e-3 m/s` target face velocity at `1 kPa`
- separate raw Kv target、Mach-clipped applied flow、cap flag、hydraulic-separation telemetry
- actual two-sided interface fluxes are required; cell-center or ghost substitutes are not accepted
- hydraulic-loss proxy remains diagnostic and is not removed from `rhoE`

V-012A artifacts:

- config / metrics JSON
- valve schedule / valve / two-sided interface / probe / boundary / final-profile CSV
- observation Markdown report
- valve command and flow PNG
- probe pressure and velocity PNG
- interface-flux consistency PNG
- budget and health PNG

## 6. Roadmap

| Stage | Status | Remaining work |
|---|---|---|
| Stage 1〜5 | COMPLETE | Validation / design-use approvalは別問題 |
| Stage 6 | IN_PROGRESS | V-012B driven flow、opening/closing ramps、mesh/CFL、CI、formalization |
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
- fixed-pressure boundaryはzero-impedance numerical idealizationであり、実reservoirそのものではない。
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
- PR #34: V-012 implementation-ready specificationをマージ。merge commit `6f4bc16c38361b0fffec3267766224aff0160a90`。
- PR #35: V-012A telemetry / uniform baseline / plottingをマージ。merge commit `128596593ae99e61289475cb79a39ec2127f72aa`。
- V-012B driven-flow baselineをbranch `agent/stage6-v012b-driven-valve-baseline`で開始。
