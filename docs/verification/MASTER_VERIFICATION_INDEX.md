# MASTER VERIFICATION INDEX

この文書はverification活動のsingle entry pointである。作業再開時は、現在地、成果物、制約、次の作業をここで確認する。

## 1. Restart here

### 現在地

- Stage 1〜5のCoolProp単相CO2 software / numerical verificationは完了。
- Stage 5ではrigid-wall / fixed-pressure reflectionの仕様、telemetry、baseline、可視化、mesh/CFL、CI-light、formal report、SHA256 manifest、GitHub Actionsを整備済み。
- Stage 6 / V-011 controlled pressure rampはbaseline、telemetry、可視化、p10/p50/p90 analysis、front fit、mesh/CFL、CI-light、GitHub Actions、backend traceability、formal report、SHA256 manifestまで整備し、`COMPLETE`。
- V-012 implementation-ready specificationはPR #34でマージ済み。merge commitは`6f4bc16c38361b0fffec3267766224aff0160a90`。
- V-012A telemetry / uniform-state baselineはPR #35でマージ済み。merge commitは`128596593ae99e61289475cb79a39ec2127f72aa`。
- V-012B small driven-flow constant-opening baselineはPR #36でマージ済み。merge commitは`8cb3deee003b141c0cb8e8d56ccc3eaa77c01d8f`。
- V-012C controlled opening rampはPR #37でマージ済み。merge commitは`f933479658d61b30d2214a2ceb9cd64d0efa671a`。
- V-012D controlled closing rampはPR #38でマージ済み。merge commitは`56591c60d7ea91c2ba9872681115ededac8aff15`。
- V-012Dでは開度`1 -> 0`、初期hold `0.005 s`、ramp duration `0.010 s`、完全閉止後hold `0.005 s`を実行し、`overall_observation_execution_pass = True`を確認済み。
- V-012D focused testsは`7 passed in 7.53s`、GitHub Actions全体testは`252 passed in 106.74s`。static checks、baseline metrics gate、9図生成もsuccess。
- V-012Dの9図を目視確認済み。上流の左向き圧縮波、下流の右向き減圧波、流量減少、完全閉止後のindependent reflective-wall stateとzero through-fluxを確認した。
- PR #38最終headのCoolProp Controlled Pressure Ramp Regression、CoolProp Wave Regression、CoolProp Boundary Reflection Regressionはすべてsuccess。
- V-012 mesh/CFL observationはPR #40で13-run計画を完走し、`OBSERVED; READY FOR REVIEW`。
- 13 / 13 runs、aggregate analysis、9 comparison plots、264 testsをsuccessで確認した。
- `n=400`追加は人間レビューの結果、初期50 / 100 / 200観測で主要傾向が明確なため不要と判断した。
- Stage 6全体およびV-012全体は`IN_PROGRESS`。
- `property_backend_design_status = not_approved_for_design_use`。
- physical Validation、design acceptance、two-phase verificationは未実施。

### 直近完了段階

V-012D controlled internal-valve closing ramp

- PR: `#38`
- merge commit: `56591c60d7ea91c2ba9872681115ededac8aff15`
- schedule: opening `1.0 -> 0.0`
- initial hold: `0.005 s`
- ramp duration: `0.010 s`
- post-closure hold: `0.005 s`
- left/right pressure: `8,000,500 / 7,999,500 Pa`
- temperature: `280 K`
- baseline mesh/CFL: `n=100`, `CFL=0.5`
- target time: `0.0697143731 s`
- first initial-state boundary arrival: `0.0896929534 s`
- opening monotonic non-increasing: `True`
- initial / final applied Q: `7.0685834694e-05 / 0 m3/s`
- finite-opening raw/applied relative difference: `0`
- finite-opening applied/flux relative difference: `1.8702192872e-16`
- post-closure sample count: `61`
- post-closure hydraulic-separation fraction: `1.0`
- post-closure no-flow-direction fraction: `1.0`
- maximum post-closure mass through-flux: `5.4210108624e-20 kg/m2/s`
- maximum post-closure energy / vapor-mass through-flux: `0 / 0`
- maximum post-closure flux-derived Q: `4.1519104059e-24 m3/s`
- flow-sign consistency: `1.0`
- Mach-cap activation count: `0`
- primary characteristic direction pass: `True`
- maximum opposite-direction characteristic ratio: `1.2305912229e-06`
- upstream compression observed: `True`
- downstream decompression observed: `True`
- mass / energy / vapor-mass interface mismatch: within numerical roundoff
- mass / energy / vapor-mass budget relative residual: `0 / 0 / 0`
- remained single phase: `True`
- focused tests: `7 passed in 7.53s`
- full repository tests: `252 passed in 106.74s`
- human-review plots: `9`

### 直近観測段階

V-012 single-phase internal-valve mesh/CFL observation

- PR: `#40`
- observed source head: `9a63dd2bafc264c2a9e41ba68769b5b38cfafe78`
- planned / executed runs: `13 / 13`
- V-012A sentinel: `n=50`, `CFL=0.5`
- V-012B/C/D mesh: `n=50 / 100 / 200`, `CFL=0.5`
- V-012B/C/D CFL: `n=100`, `CFL=0.25 / 0.5`
- overall sweep execution pass: `True`
- aggregate trend analysis complete: `True`
- human-review comparison plots: `9`
- focused tests: `12 passed`, `0 skipped`
- full repository tests: `264 passed in 121.80 s`
- CoolProp version: `8.0.0`
- artifact SHA256: `c1cdf41cde8697cdecbd368ee380d925922921fbc77c1c8b77cb8820feb0d372`
- p50 timing offset improved monotonically with mesh refinement for V-012B/C/D
- finite-opening flow remained stable and applied/flux consistency stayed at roundoff
- complete-closure Q and mass / energy / vapor-mass through-flux remained at numerical zero
- all runs remained single phase with required budgets present
- `n=400` decision: not required for this observation increment

### 次の段階

V-012 CI-light band specification and formalization

### Next action

1. PR #40のmesh/CFL observation implementationと人間レビューを確定する。
2. 観測済み13-run結果からCI-light候補caseとregression band案を仕様化する。
3. bandはtest通過目的で緩めず、mesh/CFL差とnumerical floorから根拠を記録する。
4. permanent GitHub Actions CI-lightを追加し、skipなしで確認する。
5. V-012 formal reportとSHA256 manifestを整備する。
6. V-012全体のcompletion gateをレビューする。

Stage 6ではESD event、pump trip、flashing、two-phase dischargeへ進まない。これらは後続stageで扱う。

## 2. Resume checklist

```powershell
git switch main
git pull --ff-only
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
| V-012 | Single-phase valve operation | IN_PROGRESS | PR #34 specification、PR #35 V-012A、PR #36 V-012B、PR #37 V-012C、PR #38 V-012D、PR #40 13-run mesh/CFL observation、264 tests、9 comparison plots | CI-light、permanent Actions、formal report、manifest未完了 | CI-light band specification |
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
- artifact count: `58`
- report SHA256: `9589276f8b1c3d5fa5f0b704d9fd912ba22340f31d44c2113808cf115430b15c`

### Stage 6 specifications and logs

```text
docs/verification/stage6_single_phase_boundary_operation_spec.md
docs/verification/v012_single_phase_internal_valve_operation_spec.md
docs/verification/v012_single_phase_internal_valve_mesh_cfl_observation_plan.md
docs/verification/stage6_execution_log.md
docs/verification/stage6_v012_execution_log.md
```

### Stage 6 / V-011

```text
verification/controlled_pressure_ramp_baseline/
verification/controlled_pressure_ramp_sweep/
docs/verification/stage6_controlled_pressure_ramp_observation_notes.md
docs/verification/stage6_controlled_pressure_ramp_sweep_observation_notes.md
docs/verification/controlled_pressure_ramp_regression_band_spec.md
```

V-011 final formal artifacts:

- `coolprop_controlled_pressure_ramp_verification_report_v1.md`
- `coolprop_controlled_pressure_ramp_verification_manifest_v1.json`
- artifact count: `46`
- report SHA256: `dadc6a4a982ff24e6cdf70b70d43ca8b6dadac71ac51c31c19ac7277828a3cf2`
- property backend: `coolprop_co2`
- source CoolProp version: `8.0.0`
- property backend design status: `not_approved_for_design_use`

### Stage 6 / V-012A

```text
verification/internal_valve_uniform_baseline/
```

Artifacts:

- config / metrics JSON
- valve schedule / valve / two-sided interface / probe / boundary / final-profile CSV
- observation Markdown report
- four human-review PNGs

### Stage 6 / V-012B

```text
verification/internal_valve_driven_baseline/
docs/verification/stage6_v012b_driven_flow_observation_notes.md
```

Artifacts:

- config / metrics JSON
- valve / interface-flux / probe / boundary / final-profile CSV
- observation Markdown report
- four human-review PNGs

### Stage 6 / V-012C

```text
verification/internal_valve_opening_ramp_baseline/
docs/verification/stage6_v012c_opening_ramp_observation_notes.md
```

Numerical artifacts:

- config / metrics JSON
- valve schedule / valve / interface-flux / probe / characteristic-summary / boundary / final-profile CSV
- full field-history NPZ
- observation Markdown report

Human-review figures:

- valve command and flow
- probe pressure and velocity
- probe characteristics
- pressure x-t map
- velocity x-t map
- interface-flux consistency
- budget and consistency summary
- representative field profiles
- pressure-difference / flow path

### Stage 6 / V-012D

```text
verification/internal_valve_closing_ramp_baseline/
docs/verification/stage6_v012d_closing_ramp_observation_notes.md
```

Numerical artifacts:

- config / metrics JSON
- valve schedule / valve / interface-flux / probe / characteristic-summary / boundary / final-profile CSV
- full field-history NPZ
- observation Markdown report

Human-review figures:

- valve command and flow
- probe pressure and velocity
- pre-arrival-rebased probe characteristics
- pressure x-t map
- velocity x-t map
- finite-opening / closed-wall interface consistency
- budget, finite-opening consistency, and complete-closure summary
- representative field profiles
- pressure-difference / flow path

### Stage 6 / V-012 mesh/CFL observation

```text
docs/verification/v012_single_phase_internal_valve_mesh_cfl_observation_plan.md
docs/verification/stage6_v012_mesh_cfl_observation_notes.md
```

Observed GitHub Actions artifact:

- source head: `9a63dd2bafc264c2a9e41ba68769b5b38cfafe78`
- planned / executed runs: `13 / 13`
- aggregate comparison plots: `9`
- full repository tests: `264 passed`
- artifact SHA256: `c1cdf41cde8697cdecbd368ee380d925922921fbc77c1c8b77cb8820feb0d372`

Fixed plan:

- V-012A: one `n=50`, `CFL=0.5` preservation sentinel
- V-012B/C/D: `n=50 / 100 / 200` at `CFL=0.5`
- V-012B/C/D: `n=100` at `CFL=0.25`
- unique planned run count: `13`
- `n=400` was reviewed and is not required for the current observation increment
- no formal regression band is defined before observation review

## 6. Roadmap

| Stage | Status | Remaining work |
|---|---|---|
| Stage 1〜5 | COMPLETE | Validation / design-use approvalは別問題 |
| Stage 6 | IN_PROGRESS | V-012 CI-light、permanent GitHub Actions、formal report、SHA256 manifest |
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
- opening scheduleはprescribed operationであり、actuator dynamicsやhysteresis modelではない。
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
- PR #36: V-012B driven-flow baselineをマージ。merge commit `8cb3deee003b141c0cb8e8d56ccc3eaa77c01d8f`。
- PR #37: V-012C opening-ramp implementationをマージ。merge commit `f933479658d61b30d2214a2ceb9cd64d0efa671a`。
- PR #38: V-012D complete-closing-ramp implementationをマージ。merge commit `56591c60d7ea91c2ba9872681115ededac8aff15`。GitHub Actions observation、9-figure review、252-test evidenceを記録。
- V-012 mesh/CFL observation planを固定。V-012は`IN_PROGRESS`を維持し、次は13-run sweep implementation。

- PR #40: V-012 mesh/CFL observation implementation、13-run execution、aggregate analysis、9-figure review、264-test evidenceを記録。V-012は`IN_PROGRESS`を維持し、次はCI-light band specification。
