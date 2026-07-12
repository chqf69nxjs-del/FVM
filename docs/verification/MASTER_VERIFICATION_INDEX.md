# MASTER VERIFICATION INDEX

この文書は、verification 活動の single entry point / master index である。一週間以上作業を中断した場合も、まずこの文書を開き、現在地、完了事項、成果物、未確認事項、次の作業を確認する。

## 1. Restart here

### 現在地

- Stage 1〜4 の CoolProp 単相 CO2 software / numerical verification は完了。
- 静止一様状態保持、質量・エネルギー・蒸気質量 budget、small-amplitude Gaussian incident wave、50 / 100 / 200 / 400 セルと CFL 比較を確認済み。
- formal verification report、SHA256 manifest、CI-light regression、GitHub Actions CoolProp regression を整備済み。
- Stage 5 の rigid-wall / fixed-pressure boundary reflection は、仕様、boundary telemetry、baseline runner、Windows CoolProp 実行、可視化まで完了。
- rigid wall では正符号反射、境界速度ほぼ 0、right-boundary mass / energy flow と累積交換量 0 を観測。
- fixed pressure では負符号反射、境界速度増幅、波到達時だけ right-boundary mass / energy exchange が発生し、その後累積値が plateau することを観測。
- Stage 5 は baseline observation 済みだが、mesh / CFL observation、formal accuracy band、Stage 5 CI-light regression、formal report / manifest は未完了。
- `property_backend_design_status = not_approved_for_design_use`。
- physical Validation、design acceptance、two-phase verification は未実施。

### 直近完了段階

Stage 5 baseline observation and visualization

- PR #23: rigid-wall / fixed-pressure baseline runner、reflection metrics、boundary / budget artifacts。
- PR #24: probe pressure、`A_plus` / `A_minus`、boundary-face pressure / velocity、boundary flux / cumulative budget plots。
- Windows focused tests: plotting 4 passed、flux plotting 5 passed、helpers 9 passed、CoolProp reflection 6 passed。
- GitHub Actions CoolProp Wave Regression: success。

### 次の段階

Stage 5 PR-C mesh / CFL observation

### Next action

PR-C の scope を以下に固定する。

- 各 boundary で `n_cells = 50 / 100 / 200`, `CFL = 0.5` を実行する。
- 各 boundary で `n_cells = 100`, `CFL = 0.25 / 0.5` を比較する。
- 400-cell は 200-cell までで傾向が不明な場合のみ high-cost observation として追加する。
- reflection coefficient、arrival-time error、boundary residual、characteristic leakage、waveform shape、budget residual を比較する。
- summary CSV / JSON と comparison PNG を生成する。
- mesh observation classification を付与する。
- formal accuracy threshold、CI-light regression、formal report / manifest、Stage 5 COMPLETE 化は PR-C に含めず、後続 PR-D で扱う。

## 2. Resume checklist

Windows PowerShell での作業再開手順:

```powershell
git switch main
git pull origin main
$env:PYTHONPATH = "src"
python -m pytest -q
# GitHub Actions の "CoolProp Wave Regression" が直近 main で pass していることを確認する。
Get-Content docs/verification/MASTER_VERIFICATION_INDEX.md
# Next action を読む。
# 最新 formal report と manifest を確認する。verification directory が git 管理外の場合は local artifact path として確認する。
git switch -c <new-work-branch>
```

確認順序:

1. `git switch main`
2. `git pull origin main`
3. `PYTHONPATH=src python -m pytest -q`
4. GitHub Actions の `CoolProp Wave Regression` を確認
5. `MASTER_VERIFICATION_INDEX.md` の `Next action` を読む
6. 最新 formal report と manifest を確認
7. 新しい作業 branch を作る

## 3. Status definitions

| Status | Definition |
|---|---|
| `PLANNED` | 作業対象として登録済みだが、仕様・実装・判定は未完了。 |
| `IN_PROGRESS` | 仕様化、実装、実行、レビューのいずれかが進行中。完了判定はまだ出していない。 |
| `OBSERVED` | 実行結果または現象は確認済みだが、test、artifact、判定、再現手順のいずれかが不足している。 |
| `COMPLETE` | 実装だけでなく、test、成果物、判定、再現手順が揃い、再開時に同じ確認を追跡できる状態。 |
| `BLOCKED` | 外部依存、未決仕様、環境制約、設計判断待ちなどで停止中。 |

## 4. Master verification table

不明な commit、PR、日付は推測しない。GitHub history または成果物から確認できるものだけ記載し、不明値は `unknown` とする。

| ID | Verification item | Physics / function | Status | Reference / expected behavior | Implementation | Tests | Artifacts | Last execution | Commit / PR | Result | Open limitations | Update trigger | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V-001 | CoolProp backend traceability/API | `coolprop_co2` backend と design-use status traceability | COMPLETE | backend 名と `not_approved_for_design_use` が出力・判定に残る | `src/liquid_gas_transient/properties`, CoolProp wave path | `tests/test_property_backend_pt_energy.py`, `tests/test_coolprop_backend_installed.py`, wave regression tests | docs と regression JSON | unknown | unknown | software traceability observed | design-use approval は未実施 | backend API/status 変更時 | Stage 5 / later stages でも status を維持 |
| V-002 | CoolProp uniform-state multistep preservation | 静止一様状態保持、保存性 | COMPLETE | 圧力・温度・密度・音速が有限正値、budget residual が regression band 内 | CoolProp/FVM uniform-state path | relevant CoolProp small-amplitude wave tests | local artifact path: `verification/coolprop_small_amplitude_wave_sweep_final_v1/` | unknown | unknown | pass reported in current evidence | physical Validation ではない | solver flux/time integration 変更時 | boundary / event verification に保存性判定を引き継ぐ |
| V-003 | CoolProp Case C mini-run software path | Case C mini-run の実在物性候補経路 | COMPLETE | CoolProp 経路が例外なく走り、設計未承認 status を残す | `src/liquid_gas_transient/cases/case_c_coolprop_mini_run.py` | `tests/test_case_c_coolprop_mini_run.py` | Case C mini-run outputs | unknown | unknown | software path observed | design-use / Validation ではない | Case C builder/report 変更時 | 必要時に実在物性再評価へ接続 |
| V-004 | Small-amplitude Gaussian incident wave | 単相小振幅進行波 | COMPLETE | CoolProp 音速との整合、単相維持、有限正値 | `src/liquid_gas_transient/cases/coolprop_small_amplitude_wave.py` | `tests/test_coolprop_small_amplitude_wave.py` | local artifact path: `verification/coolprop_small_amplitude_wave_sweep_final_v1/` | unknown | unknown | peak phase speed は高精度整合 | finest-grid reference は厳密解ではない | EOS/solver/probe logic 変更時 | Stage 5 反射波の入射波定義に再利用 |
| V-005 | Mesh/CFL sweep | mesh refinement / CFL comparison | COMPLETE | 50 / 100 / 200 / 400 cells と CFL 比較で shape metrics 改善 | `src/liquid_gas_transient/cases/coolprop_small_amplitude_wave_sweep.py` | `tests/test_coolprop_small_amplitude_wave_sweep.py` | sweep metrics JSON, summary CSV, PNG, per-run directories | unknown | unknown | `monotonic_shape_improvement_with_phase_speed_at_error_floor` | formal acceptance threshold は未設定 | numerical scheme 変更時 | 200/400 セル再実行要否を判断 |
| V-006 | Formal verification report and manifest | formal report / SHA256 manifest | COMPLETE | report と manifest で artifact を追跡可能 | `src/liquid_gas_transient/reporting_wave_verification.py` | `tests/test_wave_verification_report.py` | formal report and manifest under local artifact path | unknown | unknown | generated | artifact directory may be local/gitignored | report schema/artifact 変更時 | Stage 5 PR-D で同様の traceability を適用 |
| V-007 | CI-light numerical regression | 軽量 numerical regression | COMPLETE | `profile_name = coolprop_wave_ci_light_v1`, n=50, CFL=0.5, pass | `src/liquid_gas_transient/verification/wave_regression.py` | `tests/test_coolprop_wave_regression.py` | CI-light regression JSON | unknown | unknown | `overall_regression_pass = True`, `failed_checks = []` | n=50 は design mesh ではない。threshold speed は diagnostic-only | regression band/profile 変更時 | Stage 5 用 regression profile は PR-D で仕様化 |
| V-008 | GitHub Actions CoolProp regression | CI 上の CoolProp 8.0.0 skipなし regression | COMPLETE | CoolProp 8.0.0 を install し numerical regression を skip なしで実行 | `.github/workflows/coolprop-wave-regression.yml` | GitHub Actions `CoolProp Wave Regression` | uploaded JUnit and regression JSON artifacts | 2026-07-12 | PR #24 head / merged main checks | success | Stage 5 専用 regression は未導入 | workflow/dependency/backend version 変更時 | PR-D で Stage 5 CI-light 候補を追加 |
| V-009 | Closed/rigid-wall boundary reflection | 剛壁境界での反射 | OBSERVED | `R_p = +1`, reflected sign positive, arrival timing/window整合、wall velocity / mass / energy flux ≈ 0 | PR-A telemetry/helpers + `cases/coolprop_boundary_reflection.py` + plotting utilities; solver update path unchanged | `tests/test_boundary_reflection_helpers.py` 9 passed, `tests/test_coolprop_boundary_reflection.py` 6 passed, plotting tests 4 + 5 passed | config / metrics JSON, probe history, `boundary_history_v1`, final profile, report, 4 PNG classes | 2026-07-12 Windows CoolProp | PR #22, #23, #24; merge commits `121d3b8`, `808defb`, `18d5558` | positive reflection observed; right-boundary velocity, mass flow, energy flow, cumulative exchange observed at zero; no visible instability | infinite-impedance idealization; no mesh/CFL observation; no formal coefficient accuracy band; CoolProp design-use未承認 | Stage 5 runner/telemetry/plot changes | PR-C mesh/CFL observation |
| V-010 | Fixed-pressure boundary reflection | 固定圧力境界での反射 | OBSERVED | `R_p = -1`, reflected sign negative, arrival timing/window整合、pressure residual small、velocity amplification、boundary exchange allowed | same PR-B runner with constant-pressure right boundary and PR-A telemetry + plotting utilities | same focused test set: 9 + 6 + 4 + 5 passed | config / metrics JSON, probe history, `boundary_history_v1`, final profile, report, 4 PNG classes | 2026-07-12 Windows CoolProp | PR #22, #23, #24; merge commits `121d3b8`, `808defb`, `18d5558` | negative reflection observed; smooth mass / energy exchange during arrival and cumulative plateau afterward; no visible instability | zero-impedance idealization; real reservoirではない; no mesh/CFL observation; no formal coefficient accuracy band; CoolProp design-use未承認 | Stage 5 runner/telemetry/plot changes | PR-C mesh/CFL observation |
| V-011 | Controlled pressure step | 制御された圧力 step 応答 | PLANNED | 線形音響応答と境界条件仕様に整合 | unknown | unknown | unknown | unknown | unknown | not started | 未仕様化 | boundary operation 仕様時 | Stage 6 で仕様化 |
| V-012 | Single-phase valve operation | 単相 valve 操作 | PLANNED | valve law と単相保存性の確認 | unknown | unknown | unknown | unknown | unknown | not started | 未仕様化 | valve model 変更時 | Stage 6 で仕様化 |
| V-013 | MOC / linear acoustic cross-verification | MOC または線形音響との cross verification | PLANNED | FVM 到達時刻・波形が verification solver/解析解と整合 | unknown | unknown | unknown | unknown | unknown | not started | MOC は主ソルバではない | cross-verification 追加時 | Stage 7 で仕様化 |
| V-014 | Saturation-near property sanity | 飽和近傍物性 sanity | PLANNED | CoolProp/reference table の物性が有限・相判定明確 | unknown | unknown | unknown | unknown | unknown | not started | design-use 承認ではない | property backend 変更時 | Stage 8 前に仕様化 |
| V-015 | HEM minimum phase-change problem | HEM 最小相変化問題 | PLANNED | 即時平衡の最小問題で保存性と相変化傾向を確認 | unknown | unknown | unknown | unknown | unknown | not started | 未 Validation | HEM 変更時 | Stage 8/9 で仕様化 |
| V-016 | HNE / relaxation model | HNE / relaxation | PLANNED | `tau` を根拠なく固定せず感度/仕様を明示 | unknown | unknown | unknown | unknown | unknown | not started | `tau` 未確定 | HNE 変更時 | Stage 9 で仕様化 |
| V-017 | Event-level verification: ESD / pump trip | ESD / pump trip event | PLANNED | event-level の保存性、到達時刻、操作履歴が追跡可能 | unknown | unknown | unknown | unknown | unknown | not started | physical Validation ではない | event model 変更時 | Stage 9 で仕様化 |
| V-018 | Physical Validation | 実験・実設備 Validation | PLANNED | 独立データとの比較と受入基準 | unknown | unknown | unknown | unknown | unknown | not started | validation data/criteria 未設定 | validation 計画更新時 | Stage 10 で計画化 |
| V-019 | Design-use acceptance | design-use acceptance | PLANNED | approved backend、formal threshold、review gate が揃う | unknown | unknown | unknown | unknown | unknown | not started | CoolProp backend は未承認 | acceptance gate 定義時 | Stage 10 で条件定義 |

## 5. Current completed evidence

正式成果物として以下を索引する。ただし、この repository checkout で当該 directory が git 管理外または未配置の場合、Markdown link ではなく local artifact path として扱う。

### Stage 1〜4 local artifact path

```text
verification/coolprop_small_amplitude_wave_sweep_final_v1/
```

主要ファイル:

- `*_sweep_metrics.json`
- `*_sweep_summary.csv`
- `*_sweep_report.md`
- `coolprop_small_amplitude_wave_verification_report_v1.md`
- `coolprop_small_amplitude_wave_verification_manifest_v1.json`
- comparison PNG files
- per-run directories

正式結果:

- `overall_sweep_execution_pass = True`
- `numerical_convergence_observation = monotonic_shape_improvement_with_phase_speed_at_error_floor`
- `finest_grid_comparison_reference = n0400_cfl050`
- design-use status は未承認

CI regression:

- `profile_name = coolprop_wave_ci_light_v1`
- `n_cells = 50`
- `CFL = 0.5`
- `overall_regression_pass = True`
- `failed_checks = []`
- threshold speed は diagnostic-only

### Stage 5 baseline local artifact paths

```text
verification/boundary_reflection_rigid/
verification/boundary_reflection_fixed_pressure/
```

各 case の主要ファイル:

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

観測結果:

- rigid wall: positive reflection、wall diagnostic velocity 0、right-boundary mass / energy flow 0、cumulative exchange 0。
- fixed pressure: negative reflection、boundary velocity amplification、wave arrival 中のみ positive mass / energy exchange、その後 cumulative plateau。
- no visible oscillatory instability or post-wave drift。
- baseline coefficient / timing values は observations であり formal acceptance threshold ではない。

## 6. Roadmap

| Stage | 状態 | 完了条件 | 現在の成果 | 未確認事項 |
|---|---|---|---|---|
| Stage 1 基盤・物性経路 | COMPLETE | backend 経路、traceability、design-use status が追跡可能 | CoolProp backend traceability/API を確認 | design-use 承認は未実施 |
| Stage 2 静止一様状態・保存性 | COMPLETE | 静止一様状態保持と budget residual を確認 | uniform-state multistep preservation を確認 | physical Validation ではない |
| Stage 3 単相小振幅進行波 | COMPLETE | CoolProp 音速、到達時刻、単相維持、保存性を確認 | Gaussian incident wave verification 完了 | finest-grid reference は厳密解ではない |
| Stage 4 mesh/CFL・report・regression・CI | COMPLETE | sweep、formal report、manifest、CI-light、GitHub Actions が揃う | 50/100/200/400 セル、CFL 比較、CI regression 導入 | formal acceptance threshold は未設定 |
| Stage 5 単相境界反射 | IN_PROGRESS | baseline、mesh/CFL observation、formal band、CI-light、report/manifest、reproducible artifacts が揃う | specification、telemetry、baseline runner、Windows実行、4種類の可視化、V-009/V-010 OBSERVED | PR-C mesh/CFL、formal accuracy band、Stage 5 CI-light、formal report/manifest、COMPLETE判定 |
| Stage 6 単相境界操作・部品 | PLANNED | controlled pressure step と valve operation の単相 verification が揃う | 未着手 | 境界入力・部品モデルの期待挙動未整理 |
| Stage 7 MOC / 解析解との cross verification | PLANNED | MOC verification solver または線形音響解析解との cross check が揃う | 未着手 | MOC は主ソルバではなく verification 用に限定する |
| Stage 8 相変化の最小問題 | PLANNED | 飽和近傍物性 sanity と最小相変化問題が定義される | 未着手 | reference/backend と acceptance gate 未定 |
| Stage 9 HEM / HNE / event-level verification | PLANNED | HEM/HNE と ESD/pump trip event の verification が段階化される | 未着手 | HNE `tau` は未確定。根拠なく固定しない |
| Stage 10 physical Validation / design-use acceptance | PLANNED | Validation data、formal threshold、design-use acceptance gate が揃う | 未着手 | Validation と design acceptance は未実施 |

## 7. Do not forget

- regression pass は Validation ではない。
- finest-grid reference は厳密解ではない。
- `n = 50` は design mesh ではない。
- CoolProp backend は design-use 未承認。
- DVCM は legacy comparison proxy であり、thermodynamic two-phase model ではない。
- formal acceptance threshold は未設定。
- baseline / band を test 通過目的だけで緩めてはいけない。
- numerical scheme 変更時は 200 / 400 セル verification と formal report 更新を検討する。
- fixed pressure は zero-impedance idealization であり、実 reservoir と同一視しない。
- rigid wall は infinite-impedance idealization であり、実弁と同一視しない。

## 8. Update rule

今後、verification に関係する PR では、同じ PR 内で `docs/verification/MASTER_VERIFICATION_INDEX.md` を更新する。

最低限、以下が変わった場合に更新する。

- verification status
- latest artifact
- reference commit
- test command
- regression band
- backend version
- next action
- known limitation

文書先頭の `Restart here` は常に現在地だけを示す。古い現在地は `Change history` へ移す。

## 9. Change history

- Initial: Small-amplitude wave verification through GitHub Actions regression.
- Initial: Next action set to single-phase boundary reflection specification.
- Stage 5 boundary reflection specification added.
- V-009 / V-010 moved to IN_PROGRESS.
- Stage 5 PR-A added boundary numerical-flux telemetry, diagnostic face definition, characteristic/timing/window helpers, CSV schema, and synthetic pure tests without changing solver physics.
- Stage 5 PR-A merged as PR #22.
- Stage 5 PR-B baseline rigid-wall / fixed-pressure runner, metrics, artifacts, and CoolProp focused tests merged as PR #23.
- Stage 5 plotting and boundary flux / cumulative budget visualization merged as PR #24.
- V-009 / V-010 moved to OBSERVED after Windows CoolProp execution and visual review.
- Next action fixed to Stage 5 PR-C mesh / CFL observation; formal threshold / CI-light / report / manifest remain for PR-D.
