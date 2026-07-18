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
- V-012 mesh/CFL observationはPR #40でマージ済み。merge commitは`ddc83bc390cbb712900017e9ff82112fae81200f`。
- 13 / 13 runs、aggregate analysis、9 comparison plots、264 testsをsuccessで確認した。
- `n=400`追加は人間レビューの結果、初期50 / 100 / 200観測で主要傾向が明確なため不要と判断した。
- V-012 CI-light regression band、4-case runner、permanent GitHub ActionsはPR #42で整備し、skipなしでsuccess。
- V-012 formal report / SHA256 manifest generatorを整備し、実13-run成果物から193 artifactを索引化した。
- formalization確認ではfocused 14 tests、全repository 276 testsがskipなしでsuccess。
- V-012 CI-light and formalizationはPR #42でマージ済み。merge commitは`c6155d8ea959abbcf90e8e1692dd2710b6b33666`。
- Stage 6全体およびV-012全体は`COMPLETE`。
- Stage 7 / V-013 MOC / linear-acoustic cross-verification specificationはPR #44でマージ済み。merge commitは`349bdefe16816b55b0b64495b1ebf17bedab71e5`。
- Stage 7 / V-013 independent reference coreはPR #46で実装し、`IMPLEMENTED; TESTED; READY FOR REVIEW`。
- characteristic algebra、Gaussian analytical evaluator、`CFL=1` MOC、rigid / fixed-pressure identityを23 self-testsで確認した。
- 全repository `299 passed in 150.31 s`、deterministic reference JSON、prohibited-import guardをsuccess。
- Stage 7 / V-013は`IN_PROGRESS`。次はV-013A incident propagation接続。
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
- merge commit: `ddc83bc390cbb712900017e9ff82112fae81200f`
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

### 直近formalization段階

V-012 single-phase internal-valve CI-light and formalization

- PR: `#42`
- status: `COMPLETE; MERGED`
- merge commit: `c6155d8ea959abbcf90e8e1692dd2710b6b33666`
- CI-light profile: V-012A/B/C/D at `n=50`, `CFL=0.5`
- permanent workflow: `CoolProp Internal Valve Regression`
- installed CoolProp regression: success, skip `0`
- CI-light artifact SHA256: `6513dc51c5692e8b6a20fe3e980f8872c9d0f9ceff419f083510c27c8bda4047`
- formalization source head: `6e6a096dba2cfc2e8613cb0d775cd2668fd830b5`
- full 13-run sweep: success
- comparison plots: `9`
- CI-light regression pass: `True`
- focused formalization tests: `14 passed`, `0 skipped`
- full repository tests: `276 passed in 126.56 s`
- formal artifact count: `193`
- report: `coolprop_internal_valve_verification_report_v1.md`
- report SHA256: `ef33fe47074a21048d1bb31bdc8a206d0dc4d0d7c559445bf0f49115727e3a18`
- manifest: `coolprop_internal_valve_verification_manifest_v1.json`
- manifest SHA256: `368cdaa4a033d837123e668677c477379fd7666425032c6ac46754fc51a60b81`
- formalization artifact SHA256: `479168b98ddeaa89c07384db6877e2a6ada37fdc4db063ad8d11b1703f2d4572`
- property backend: `coolprop_co2`
- CoolProp version: `8.0.0`
- property backend design status: `not_approved_for_design_use`
- physical Validation: `False`
- design-use acceptance: `False`

### 直近reference-core段階

V-013 independent analytical / MOC reference core

- PR: `#46`
- status: `IMPLEMENTED; TESTED; READY FOR REVIEW`
- verification head: `f44b569b5dbe388840860415987486bef47602cf`
- implementation: `linear_acoustic_reference.py`
- self-tests: `23 passed`, `0 skipped`
- full repository: `299 passed in 150.31 s`
- analytical / MOC grid-aligned incident agreement: floating-point roundoff
- rigid-wall and fixed-pressure reflection identities: pass
- input mutation: none
- production solver / flux / boundary / case imports: none
- CoolProp calls from reference: none
- deterministic JSON SHA256: `a5d2a5764b4c65613aed9d6254f315b41055fa51968a89d9cf7d5b290c3cbd64`
- temporary artifact SHA256: `eeaccfdccf8b791b037b28b46b41e3446dc4e70bec5b5beb8b9d9b3868c245e3`
- production solver changes: none

### 次の段階

Stage 7 / V-013 MOC / linear-acoustic cross verification

### Next action

1. stable V-013A case ID、run plan、matched-sample schemaを固定する。
2. existing small-amplitude FVM source caseをsolver physics変更なしで接続する。
3. independent referenceへ渡す`rho0` / `c0` provenanceを記録する。
4. V-013A incident propagationを`n=100 / 200 / 400`で実行・比較する。
5. V-013Aレビュー後にV-013B / V-013Cへ進み、全観測後にのみCI-light bandを提案する。

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
| V-012 | Single-phase valve operation | COMPLETE | PR #34 specification、PR #35 V-012A、PR #36 V-012B、PR #37 V-012C、PR #38 V-012D、PR #40 13-run mesh/CFL、PR #42 CI-light / permanent Actions / formal report / 193-artifact manifest、276 tests | physical Validationとdesign-use approvalは別問題 | solver/interface/schema変更時に再実行 |
| V-013 | MOC / linear-acoustic cross verification | IN_PROGRESS | PR #44 specification、PR #46 independent analytical / CFL=1 MOC reference core、23 self-tests、299 full tests、deterministic artifact | FVM接続とV-013A/B/C観測は未実施。MOCはverification用限定 | V-013A incident propagation integration |
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

### Stage 6 / V-012 CI-light and formalization

```text
docs/verification/v012_internal_valve_regression_band_spec.md
docs/verification/stage6_v012_formalization_notes.md
.github/workflows/coolprop-internal-valve-regression.yml
```

Final formal artifacts generated from the traceable 13-run artifact set:

- `coolprop_internal_valve_verification_report_v1.md`
- `coolprop_internal_valve_verification_manifest_v1.json`
- artifact count: `193`
- report SHA256: `ef33fe47074a21048d1bb31bdc8a206d0dc4d0d7c559445bf0f49115727e3a18`
- manifest SHA256: `368cdaa4a033d837123e668677c477379fd7666425032c6ac46754fc51a60b81`
- formalization artifact SHA256: `479168b98ddeaa89c07384db6877e2a6ada37fdc4db063ad8d11b1703f2d4572`
- CI-light artifact SHA256: `6513dc51c5692e8b6a20fe3e980f8872c9d0f9ceff419f083510c27c8bda4047`
- source CoolProp version: `8.0.0`
- property backend design status: `not_approved_for_design_use`
- V-012 completion status: `COMPLETE; MERGED`

### Stage 7 / V-013 MOC / linear-acoustic cross verification

```text
docs/verification/v013_moc_linear_acoustic_cross_verification_spec.md
docs/verification/stage7_execution_log.md
docs/verification/stage7_v013_reference_core_notes.md
src/liquid_gas_transient/verification/linear_acoustic_reference.py
tests/test_linear_acoustic_reference.py
```

Initial specification:

- analytical characteristic evaluator and discrete `CFL=1` MOC are separately testable;
- MOC does not import the production FVM solver, numerical flux, or boundary classes;
- MOC receives explicit `rho0` and `c0` and does not call CoolProp;
- V-013A incident propagation, V-013B rigid-wall reflection, and V-013C fixed-pressure reflection;
- FVM `n=100 / 200 / 400`, `CFL=0.5`;
- MOC `n=100 / 200 / 400`, `CFL=1.0`;
- no FVM regression band before observation review;
- no production solver behaviour change in the specification increment.

Reference-core evidence:

- `A+ / A-` conversion and pressure / velocity reconstruction;
- bounded Gaussian analytical translation with at most one reflection;
- independent nodal MOC exact one-cell translation at `CFL=1`;
- transmissive, rigid-wall, and fixed-pressure characteristic identities;
- 23 self-tests and 299 full repository tests;
- AST guard confirms no production solver / flux / boundary / case or CoolProp imports;
- deterministic JSON artifact output;
- V-013A FVM integration remains the next action.

## 6. Roadmap

| Stage | Status | Remaining work |
|---|---|---|
| Stage 1〜5 | COMPLETE | Validation / design-use approvalは別問題 |
| Stage 6 | COMPLETE | V-011 / V-012 software・numerical verificationとformalizationを完了。Validation / design-use approvalは別問題 |
| Stage 7 | IN_PROGRESS | V-013 reference core implemented and tested; V-013A/B/C FVM comparison and observation remain |
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

- PR #40: V-012 mesh/CFL observation implementationをマージ。merge commit `ddc83bc390cbb712900017e9ff82112fae81200f`。13-run execution、aggregate analysis、9-figure review、264-test evidenceを記録。V-012は`IN_PROGRESS`を維持し、次はCI-light band specification。

- PR #42: V-012 CI-light regression band、4-case permanent GitHub Actions、formal report、193-artifact SHA256 manifest、276-test evidenceを整備。branch上でV-012およびStage 6を`COMPLETE; READY FOR REVIEW`へ移行。

- PR #42 merge commit: `c6155d8ea959abbcf90e8e1692dd2710b6b33666`。V-012 CI-light、permanent GitHub Actions、formal report、193-artifact manifestをmainへ反映し、V-012およびStage 6を`COMPLETE`へ移行。

- V-013 implementation-ready MOC / linear-acoustic cross-verification specificationを固定。独立reference規則、3ケース、100/200/400観測matrix、artifact、stop conditionを記録。

- PR #44 merge commit: `349bdefe16816b55b0b64495b1ebf17bedab71e5`。V-013 implementation-ready specificationとStage 7 execution logをmainへ反映。次は独立analytical / MOC reference implementation。

- PR #46: V-013 independent analytical / CFL=1 MOC reference core、23 self-tests、299-test full-suite evidenceを記録。V-013は`IN_PROGRESS`を維持し、次はV-013A incident propagation。
