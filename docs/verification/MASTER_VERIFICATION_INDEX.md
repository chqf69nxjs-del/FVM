# MASTER VERIFICATION INDEX

この文書は verification 活動の single entry point / master index である。作業再開時は、まず本書で現在地、完了事項、成果物、制約、次の作業を確認する。

## 1. Restart here

### 現在地

- Stage 1〜4 の CoolProp 単相 CO2 software / numerical verification は完了。
- 静止一様状態保持、保存収支、小振幅 Gaussian 進行波、mesh/CFL 比較、formal report、SHA256 manifest、CI-light regression、GitHub Actions を整備済み。
- Stage 5 の rigid-wall / fixed-pressure boundary reflection は、仕様、boundary telemetry、baseline runner、可視化、Windows CoolProp 実行、mesh/CFL observation まで完了。
- PR #26 の 8 unique runs はすべて完走し、`overall_sweep_execution_pass = True`。
- rigid wall / fixed pressure とも、反射係数誤差、characteristic leakage、waveform difference は mesh refinement で改善。
- rigid wall の boundary residual は 50 / 100 / 200 cells で 0。
- fixed pressure の normalized pressure residual は `0.06006 -> 0.05975 -> 0.04892` と改善。
- arrival-time metric は rigid wall で約 `1e-5` の微小非単調、fixed pressure で `0.01638 -> 0.00825 -> 0.00828` と改善後 plateau。
- 主要な shape / reflection 指標は明確に改善しているため、PR-C では 400-cell run を追加しない。
- Stage 5 は formal accuracy band、Stage 5 CI-light regression、formal report / manifest、COMPLETE 判定が未完了。
- `property_backend_design_status = not_approved_for_design_use`。
- physical Validation、design acceptance、two-phase verification は未実施。

### 直近完了段階

Stage 5 PR-C mesh / CFL observation

- PR #26: boundary reflection sweep runner、8 unique runs、summary JSON / CSV、comparison PNG、observation classification。
- Windows focused tests: sweep 4 passed、helpers 9 passed、CoolProp reflection 6 passed。
- full CoolProp sweep: `unique_run_count = 8`、`overall_sweep_execution_pass = True`。
- GitHub Actions CoolProp Wave Regression: success。
- merge commit: `4bcdbd5b34f70c26922ab0f0dd2230502badb653`。

### 次の段階

Stage 5 PR-D formalization

### Next action

PR-D は以下の順序で進める。

1. PR-C 実測値を根拠に、accuracy band 候補と適用対象を文書化する。
2. band は software / numerical regression gate とし、physical Validation や design-use acceptance に転用しない。
3. Stage 5 CI-light profile を追加する。
4. formal verification report と SHA256 manifest を生成する。
5. Windows と GitHub Actions で再現性を確認する。
6. 上記が揃った後に V-009 / V-010 と Stage 5 の `COMPLETE` 判定を行う。

PR-D で避けること:

- test を通すためだけに band を緩めない。
- finest mesh を厳密解としない。
- lower CFL を真値としない。
- rigid wall を実弁、fixed pressure を実 reservoir と同一視しない。
- CoolProp backend を design-use approved としない。

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

1. main を更新する。
2. 全 test を実行する。
3. `CoolProp Wave Regression` の直近結果を確認する。
4. 本書の `Next action` を読む。
5. local artifact path の report / manifest を確認する。
6. 新しい branch で作業する。

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
| V-001 | CoolProp backend traceability/API | COMPLETE | backend 名と `not_approved_for_design_use` を出力・判定に保持 | design-use approval 未実施 | status を後続 stage でも維持 |
| V-002 | Uniform-state multistep preservation | COMPLETE | 静止一様状態と budget residual を確認 | physical Validation ではない | solver変更時に再実行 |
| V-003 | CoolProp Case C mini-run | COMPLETE | CoolProp 経路と未承認 status を確認 | design-use / Validation ではない | 必要時に再評価 |
| V-004 | Small-amplitude Gaussian incident wave | COMPLETE | CoolProp 音速、到達時刻、単相維持を確認 | finest grid は厳密解でない | Stage 5 入射波に再利用 |
| V-005 | Incident-wave mesh/CFL sweep | COMPLETE | 50 / 100 / 200 / 400 cells と CFL 比較 | formal acceptance threshold 未設定 | scheme変更時に再実行 |
| V-006 | Incident-wave formal report / manifest | COMPLETE | formal report と SHA256 manifest 生成済み | local/gitignored artifact の可能性 | Stage 5 PR-D で同じ方式を適用 |
| V-007 | Incident-wave CI-light regression | COMPLETE | `coolprop_wave_ci_light_v1` pass | n=50 は design mesh でない | Stage 5 profile を PR-D で追加 |
| V-008 | GitHub Actions CoolProp regression | COMPLETE | CoolProp 8.0.0 skipなし workflow pass | Stage 5 専用 gate 未導入 | PR-D で Stage 5 CI を追加 |
| V-009 | Closed/rigid-wall reflection | OBSERVED | positive reflection、wall velocity / mass / energy flux 0、meshで係数誤差・leakage・waveform改善 | infinite-impedance idealization、formal band/report/CI未完了 | PR-D formalization |
| V-010 | Fixed-pressure reflection | OBSERVED | negative reflection、boundary exchange、meshで係数誤差・residual・leakage・waveform改善 | zero-impedance idealization、real reservoirでない、formal band/report/CI未完了 | PR-D formalization |
| V-011 | Controlled pressure step | PLANNED | 未着手 | 未仕様化 | Stage 6 |
| V-012 | Single-phase valve operation | PLANNED | 未着手 | 未仕様化 | Stage 6 |
| V-013 | MOC / linear-acoustic cross verification | PLANNED | 未着手 | MOC は verification 用に限定 | Stage 7 |
| V-014 | Saturation-near property sanity | PLANNED | 未着手 | reference/backend gate 未定 | Stage 8 前 |
| V-015 | HEM minimum phase-change problem | PLANNED | 未着手 | physical Validation 未実施 | Stage 8/9 |
| V-016 | HNE / relaxation | PLANNED | 未着手 | `tau` 未確定 | Stage 9 |
| V-017 | Event-level ESD / pump trip | PLANNED | 未着手 | event verification 未仕様化 | Stage 9 |
| V-018 | Physical Validation | PLANNED | 未着手 | independent data / criteria 未設定 | Stage 10 |
| V-019 | Design-use acceptance | PLANNED | 未着手 | approved backend / formal threshold / review gate 未整備 | Stage 10 |

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

各 case:

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

### Stage 5 PR-C sweep

```text
verification/boundary_reflection_sweep_pr_c/
```

主要成果物:

- `coolprop_boundary_reflection_sweep_sweep_config.json`
- `coolprop_boundary_reflection_sweep_sweep_metrics.json`
- `coolprop_boundary_reflection_sweep_sweep_summary.csv`
- `coolprop_boundary_reflection_sweep_sweep_report.md`
- comparison PNG files
- 8 per-run directories

観測結果:

- rigid-wall pressure reflection magnitude error: `0.17098 -> 0.14392 -> 0.11284`
- rigid-wall reflected characteristic leakage: `0.11323 -> 0.03166 -> 0.00527`
- fixed-pressure pressure reflection magnitude error: `0.22749 -> 0.17657 -> 0.13039`
- fixed-pressure normalized pressure residual: `0.06006 -> 0.05975 -> 0.04892`
- fixed-pressure reflected characteristic leakage: `0.12150 -> 0.03291 -> 0.00538`
- both boundaries: waveform difference versus n=200 comparison reference improves to 0 by definition at the reference run
- both overall classifications: `mixed_behavior`。主要原因は arrival-time metric の微小非単調または plateau。

## 6. Roadmap

| Stage | Status | Remaining work |
|---|---|---|
| Stage 1〜4 | COMPLETE | design-use approval / physical Validation は別問題 |
| Stage 5 | IN_PROGRESS | accuracy band、CI-light、formal report / manifest、COMPLETE判定 |
| Stage 6 | PLANNED | controlled pressure step、single-phase valve operation |
| Stage 7 | PLANNED | MOC / linear acoustic cross verification |
| Stage 8 | PLANNED | saturation-near property sanity、minimum phase-change problem |
| Stage 9 | PLANNED | HEM/HNE、ESD/pump trip event verification |
| Stage 10 | PLANNED | physical Validation、design-use acceptance |

## 7. Do not forget

- regression pass は Validation ではない。
- finest-grid reference は厳密解ではない。
- lower CFL は真値ではない。
- `n = 50` は design mesh ではない。
- CoolProp backend は design-use 未承認。
- formal band を test 通過目的だけで緩めない。
- fixed pressure は zero-impedance idealization であり、実 reservoir と同一視しない。
- rigid wall は infinite-impedance idealization であり、実弁と同一視しない。

## 8. Update rule

verification に関係する PR では、同じ PR 内で本書を更新する。最低限、status、artifact、reference commit、test command、regression band、backend version、next action、known limitation が変わった場合に更新する。

## 9. Change history

- Stage 1〜4: incident-wave verification、formal report / manifest、CI-light、GitHub Actions 完了。
- PR #21: Stage 5 boundary-reflection specification。
- PR #22: boundary telemetry / helpers。
- PR #23: rigid-wall / fixed-pressure baseline runners。
- PR #24: result plots and boundary flux / cumulative budget visualization。
- PR #25: baseline evidence を master index に同期。
- PR #26: Stage 5 mesh/CFL sweep。8 runs pass、主要 shape / reflection metrics 改善、400-cell追加なし。
- Next action: Stage 5 PR-D formalization。
