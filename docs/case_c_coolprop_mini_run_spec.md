# Case C CoolProp mini-run 仕様書

## 0. 目的と制約

本仕様書は、CoolProp backend を使用した保存形 FVM solver の最小試走を、実装前に固定するための設計メモである。対象は `CaseCParameters` と現行の Case C solver 構造を使った **Case C CoolProp mini-run** であり、今回はコード、tests、数値実行スクリプトは変更しない。

本仕様書で扱う数値は、software-path verification の入力候補である。CoolProp 未導入環境で CoolProp 物性値を推測して補完しない。

## 1. 位置づけ

Case C CoolProp mini-run は以下の位置づけとする。

- software-path verification 用の最小試走である。
- 実設計 Case C の評価ではない。
- CoolProp backend の設計利用承認を意味しない。
- acceptance gate、Validation、実在 LCO2 物性の承認手続きの代替ではない。
- 主目的は、保存形 FVM solver と CoolProp backend の接続経路が、最小条件で例外なく動くかを確認することである。
- ESD 急閉、pump trip、二相化、臨界点近傍挙動を評価する run ではない。
- 図化や設計判断よりも、入力、metadata、finite check、budget check の traceability を優先する。

## 2. 使用する代表状態

### 2.1 第一候補

| 項目 | 値 |
|---|---:|
| 初期圧力 `p0` | `8.0e6 Pa` |
| 初期温度 `T0` | `280.0 K` |
| `eos_model` | `coolprop_lco2` |
| `property_backend_name` | `coolprop_co2` |
| `property_backend_design_status` | `not_approved_for_design_use` |
| `quality_source` | `transported` |
| 初期蒸気質量分率 `xv0` | `0` |
| `boundary temperature` | `280.0 K` |

### 2.2 初期密度・初期内部エネルギーの扱い

初期密度と初期内部エネルギーは固定数値を手入力しない。CoolProp 導入環境で、同一の `p0`、`T0` から生成する。

```python
rho0 = density_from_pT(p0, T0)

e0 = internal_energy_from_pT(p0, T0)
```

CoolProp 未導入環境では、`rho0` と `e0` の実値を推測して記載しない。mini-run test または実行 entry point は、CoolProp 未導入時に明示的に skip する。8 MPa、280 K は CoolProp 上で dense single-phase / supercritical-liquid 側として扱われ得る状態であり、`p > pcrit` では `T_sat(p)` は定義対象外である。このため saturation temperature との差は `not_applicable_above_critical_pressure` として記録し、design-use 承認を意味しない。


### 2.3 CaseCParameters への対応方針

現行 `CaseCParameters` では、初期圧力、初期流速、内部エネルギー、boundary temperature、phase-change selector、EOS selector などを dataclass field として指定できる。初回 mini-run では以下を候補とする。

| `CaseCParameters` field | mini-run 候補 | 備考 |
|---|---:|---|
| `upstream_initial_pressure_pa` | `8.0e6` | pump head を `0` とし、pump discharge 初期圧も同じ値にする候補。 |
| `downstream_initial_pressure_pa` | `8.0e6` | 初期一様状態保持を優先する候補。 |

| `internal_energy_j_kg` | backend の `internal_energy_from_pT(...)` から生成 | 固定値を仕様書に書かない。 |

| `lco2_boundary_temperature_K` | `280.0` | `LCO2PropertyEOSAdapter` の boundary temperature。 |
| `lco2_quality_source` | `transported` | 初期 `xv=0` の transport 経路確認を優先。 |
| `eos_model` | `coolprop_lco2` | Case C selector。 |
| `phase_change_model` | `none` | 初回は phase-change operator を無効化。 |
| `enable_hem` | `False` | `phase_change_model="none"` と整合。 |

現行 `_initial_state` は `eos.density_from_pressure(p0)` と `internal_energy_j_kg` から初期保存量を作る構造であるため、CoolProp の p-T から `rho0` と `e0` を厳密にそろえるには、実装時に初期化経路の追加または専用 mini-run builder が必要になる可能性がある。これは本仕様書では実装しない。

## 3. 最小解析規模

### 3.1 推奨候補

初回 mini-run は、短時間、低負荷、イベントなし、単相保持を優先する。

| 項目 | 推奨候補 |
|---|---:|
| `n_cells` | `20` |
| `t_end_s` | `1.0e-4 s` |
| `sample_every` | `1` |
| `max_steps` | `10000` |
| `phase_change_model` | `none` |
| `pump_delta_p_nominal_pa` | `0.0` |
| `pump_trip_start_s` | `None` |
| `pump_trip_duration_s` | `0.0` |
| `pump_delta_p_final_pa` | `0.0` |
| `valve_close_start_s` | `1.0 s` 以上、または `t_end_s` より十分後 |
| `valve_close_time_s` | 現行正値を維持、例 `0.02 s` |
| `initial_velocity_m_s` | `0.0` 第一候補 |
| `darcy_friction_factor` | `0.0` 候補 |
| elevation | 全 segment の start/end を同値にする候補 |
| local loss | 現行 Case C builder では `local_loss_k=0.0` |

`n_cells=20` は指定目安 `10〜30` の中央付近であり、Case C の 3 segment と内部 ESD valve face を維持しつつ低負荷である。`t_end_s=1.0e-4 s` は、CoolProp flash 経路の反復回数を抑え、初期一様状態の保持確認に集中する値である。

### 3.2 イベント無効化方針

- ESD 弁操作は、`valve_close_start_s` を `t_end_s` より十分後に設定し、解析時間内に開始しない。
- pump trip は `pump_trip_start_s=None` とし、解析時間内に開始しない。
- pump head は `pump_delta_p_nominal_pa=0.0` とし、初期一様圧力の保持を優先する。
- 初期流速は `initial_velocity_m_s=0.0` 第一候補とする。初期流速を与える場合は、boundary と valve の整合性により一様状態が崩れる可能性を別途記録する。

### 3.3 標高・摩擦・局所損失

初回 mini-run では、CoolProp 接続経路の健全性を主目的とするため、標高、摩擦、局所損失は単純化してよい。

- 摩擦は `darcy_friction_factor=0.0` を候補とする。
- 標高は全 segment の start/end を同値にし、重力 source による初期変化を避ける候補とする。
- 現行 Case C builder の `CellwisePipeSourceTerms.from_discretized_network(..., local_loss_k=0.0, include_gravity_energy_source=True)` は、local loss を 0 としている。一方、標高差が残ると gravity source が有効になるため、mini-run では elevation をそろえる。

## 4. 初回 mini-run で確認する項目

### 4.1 実行健全性

以下を全 step または最終 summary で確認する。

- 例外なく終了する。
- 最終時刻 `t_end_s` まで到達する。
- 主要出力に `NaN` / `inf` がない。
- `rho > 0`。
- `p > 0`。
- `T > 0`。現行 diagnostics に `T` がない場合は、実装時に profile/metadata 側で取得する候補とする。
- `sound speed > 0`。
- CFL で決まる `dt` が finite かつ正である。
- `step_count <= max_steps`。

### 4.2 状態保持

イベントを発生させない最初の run では、初期一様状態が大きく崩れないことを確認する。以下の初期値、最終値、最大絶対変化、最大相対変化を metrics JSON に残す。

- 圧力 `p`。
- 温度 `T`。
- 密度 `rho`。
- 流速 `u`。
- 蒸気質量分率 `xv`。

この段階では、相対変化の厳密な許容値を根拠なく断定しない。初回 run の実測値を保存し、閾値はその結果と数値丸め、境界条件、CoolProp flash の挙動を見て別 PR で決定する。

### 4.3 保存性

以下の既存 budget diagnostics を取得できる範囲で確認する。

- `budget_mass_residual`。
- `budget_mass_relative_residual`。
- `energy_budget_balance_residual_j`。
- `energy_budget_balance_relative_residual`。
- `phase_budget_residual_kg` または現行 phase budget で取得可能な vapor budget residual。
- `phase_budget_relative_residual` または現行 phase budget で取得可能な相対 residual。
- interface budget diagnostics。

`phase_change_model="none"` でも、transported `xv` と phase budget tracker の出力が取得できる場合は記録する。取得できない項目は failure にせず、`not_recorded_in_current_diagnostics` として metadata に明示する。

### 4.4 traceability

以下が artifact に残ることを必須候補とする。

- `eos_model`。
- `property_backend_name`。
- `property_backend_design_status`。
- `quality_source`。
- code version。
- git commit hash。
- Case 名。
- `mini_run: true`。
- `result_type: simulation_result`。
- `design_evaluation: false`。
- `acceptance_gate: false`。
- `validation: false`。
- CoolProp availability と CoolProp version。

## 5. 合格条件候補

初回 mini-run の最低限の合格条件候補は以下とする。

- CoolProp 導入環境で mini-run が完走する。
- CoolProp 未導入環境では明示的に skip する。
- 全主要状態量が finite である。
- 密度、圧力、温度、音速が正である。
- CFL で決まる `dt` が finite かつ正である。
- `step_count <= max_steps` である。
- 重大な budget 破綻がない。
- metadata に `eos_model`、`property_backend_name`、`property_backend_design_status`、code version、Case 名、mini-run であることが出力される。
- 既存標準テストに failure を追加しない。

数値許容値、たとえば圧力、温度、密度、速度、budget residual の具体的閾値は、初回 run で実測後に決定する。初回仕様では「finite、positive、完走、metadata、明示 skip」を先に固定する。

## 6. 停止・失敗条件

### 6.1 停止・失敗条件

以下が発生した場合、mini-run は停止または failure とする。

- CoolProp flash failure。
- 二相域や臨界点近傍への意図しない侵入。
- `sound speed` が非有限または非正。
- `dt` が非有限、非正、または極端に小さくなる。
- 密度、圧力、温度が非物理値になる。
- budget residual が急増する。
- `max_steps` を超過する。
- `NaN` / `inf` が主要 field または diagnostics に出る。
- metadata が欠落し、backend traceability が確認できない。

### 6.2 失敗時に記録する情報

失敗時 artifact には最低限以下を残す。

- 失敗種別、例 `coolprop_flash_failure`、`nonfinite_sound_speed`、`max_steps_exceeded`。
- 失敗 step、時刻 `time_s`、直前 `dt_s`。
- `min/max` の `rho`、`p`、`T`、`u`、`xv`、`sound speed`。
- `cfl_max`。
- 失敗 cell index と位置 `x_m`。
- CoolProp input pair、例 `Dmass-Umass` または `P-T`。
- `eos_model`、`property_backend_name`、`property_backend_design_status`。
- CoolProp version、code version、git commit hash。
- 直前の budget residual。
- CaseCParameters の実行設定 JSON。

## 7. 出力成果物

初回 mini-run では図を必須にせず、非図生成 artifact を優先する。

最低限残す候補は以下とする。

- mini-run 設定 JSON。
- 実行結果 metrics JSON。
- 短い Markdown verification report。
- 時系列 CSV。
- 最終状態 summary JSON または CSV。
- backend traceability metadata JSON。
- 失敗時 diagnostics JSON。

Markdown verification report は日本語中心とし、最初に解析対象と評価指標を説明する。図を追加する場合も、概念図と解析結果図を混同せず、case、model、backend、version、mini-run であることを明記する。

## 8. 実装候補箇所

本節は実装候補の調査結果であり、本 PR ではコード変更しない。

### 8.1 mini-run test を置く候補ファイル

候補は新規 `tests/test_case_c_coolprop_mini_run.py` とする。理由は、CoolProp installed-only test と同様に optional dependency を明示 skip しやすく、既存 Case C report tests と分離できるためである。

既存の CoolProp installed-only test は `pytest.importorskip("CoolProp")` を使用しているため、同じ skip 方針を採用する候補とする。

### 8.2 CaseCParameters で指定する項目

実装時に指定する候補 field は以下である。

```python
CaseCParameters(
    n_cells=20,
    t_end_s=1.0e-4,
    upstream_initial_pressure_pa=8.0e6,
    downstream_initial_pressure_pa=8.0e6,
    initial_velocity_m_s=0.0,
    internal_energy_j_kg=e0,
    darcy_friction_factor=0.0,
    onshore_elevation_start_m=0.0,
    onshore_elevation_end_m=0.0,
    jetty_elevation_start_m=0.0,
    jetty_elevation_end_m=0.0,
    loading_arm_elevation_start_m=0.0,
    loading_arm_elevation_end_m=0.0,
    valve_close_start_s=1.0,
    valve_close_time_s=0.02,
    pump_delta_p_nominal_pa=0.0,
    pump_trip_start_s=None,
    pump_trip_duration_s=0.0,
    pump_delta_p_final_pa=0.0,
    phase_change_model="none",
    enable_hem=False,
    eos_model="coolprop_lco2",
    lco2_boundary_temperature_K=280.0,
    lco2_quality_source="transported",
)
```

`sample_every` と `max_steps` は `CaseCParameters` field ではなく、現行 `FvmSolver.run(...)` または report runner の引数で扱う候補である。

### 8.3 初期 `rho/e` の生成を追加する候補箇所

候補は以下のいずれかである。


1. mini-run 専用 builder で `CoolPropCO2Backend().density_from_pT(p0, T0)` と `CoolPropCO2Backend().internal_energy_from_pT(p0, T0)` から `U0` を作り、既存 `FvmSolver` に渡す。
2. `CaseCParameters` に p-T 初期化用の optional field を追加し、`_initial_state` で `coolprop_lco2` の場合だけ `density_from_pT` を使う。
3. 既存 `_initial_state` を壊さず、別関数として `_initial_state_from_pT` を追加する。

初回実装では 1 または 3 を優先し、既存 Case C regression の挙動を変えない。

### 8.4 CoolProp 未導入時の skip 方法

候補は以下である。

```python
pytest.importorskip("CoolProp")
```

または、project helper として `coolprop_available()` を使い、skip reason に `CoolProp is not installed` を明記する。

### 8.5 既存 report / metrics 生成機能を再利用できる箇所

- `case_c_property_backend_metadata(params)` は、`eos_model`、`property_backend_name`、`property_backend_design_status` を取得する候補である。
- `run_case_c_for_report(params, sample_every=..., max_steps=...)` は history と final profiles を返す候補である。ただし、初期 p-T 生成経路が必要な場合は、そのまま使う前に初期化経路の整合を確認する。
- `FvmSolver.run(t_end, max_steps=..., sample_every=...)` は最小 history 取得に使える候補である。
- `solver.diagnostics(dt)` は pressure、density、velocity、sound speed、budget diagnostics の取得に使える候補である。

## 9. 実装時 TODO

- CoolProp p-T 初期化と現行 `density_from_pressure` 初期化の差を、仕様どおり解消する。
- diagnostics または profile に `T` を残す経路を決める。
- 初回実測後に、状態保持と budget residual の数値閾値を決める。
- mini-run artifact の保存先と命名規則を決める。
- この mini-run が design-use 承認ではないことを report header と metadata に残す。
