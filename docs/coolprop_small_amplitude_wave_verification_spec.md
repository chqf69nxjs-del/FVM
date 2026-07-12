# CoolProp 小振幅単相圧力波 verification 仕様書

## 0. 位置づけ

本仕様書は、`coolprop_co2` backend と保存形 `FvmSolver` を使い、小振幅・単相の圧力波が妥当な波速、到達時刻、振幅、保存性で伝播するかを確認するための software / numerical verification 仕様を固定するものである。

これは design-use evaluation ではない。CoolProp backend の design-use 承認でもない。実設備 Validation でもない。HEM / HNE / DVCM の検証でもない。ESD 急閉、pump trip、二相化、フラッシングの評価でもない。

- fluid: `CO2`
- property backend: `coolprop_co2`
- eos_model: `coolprop_lco2`、または専用 verification builder で同等の `LCO2PropertyEOSAdapter` 経路
- `property_backend_design_status`: `not_approved_for_design_use`
- 初期状態: `p0 = 8.0e6 Pa`, `T0 = 280.0 K`, `u0 = 0`
- `phase_change_model = none`
- `quality_source = transported`
- initial vapor mass fraction: `0`
- friction / gravity / local loss: `0`
- constant cross-section straight pipe
- single-phase liquid-side / supercritical-liquid-side state を維持する
- acceptance gate ではない。正式 regression threshold は初回メッシュ依存性結果を見て次 PR で固定する。

## 1. 既存コード調査

### 1.1 単純直管 network / grid を構築できる既存機構

現行コードには、完全な汎用 graph solver ではなく、一次元の ordered component chain を `ComponentNetwork` として記述し、`discretize_network(...)` で `UniformGrid` へ平坦化する機構がある。`PipeSegmentSpec` は `length_m`, `diameter_m`, `darcy_friction_factor`, `elevation_start_m`, `elevation_end_m` を持ち、`DiscretizedNetwork` は `geometry`, `grid`, cell-wise `area`, friction, `dzdx` などを保持する。

ただし `ComponentNetwork` は `esd_valve` を必須 field としており、`discretize_network(...)` も ESD valve が隣接する upstream/downstream segment 間にあることを前提に `device_face_indices` を作る。このため、今回の verification で「純粋な単一直管」を作るなら、Case C builder を流用して valve を常時全開・十分大きな `Kv` とするより、`PipeGeometry` と `UniformGrid` を直接組み合わせる専用 builder の方が境界反射・内部 interface の影響を分離しやすい。

`UniformGrid` は `PipeGeometry(length_m, diameter_m, roughness_m)` と `n_cells` だけで、`dx`, `cell_centers`, `face_positions` を提供する。小振幅波 verification ではこの直接経路を推奨する。

### 1.2 `FvmSolver` の境界条件構造

`FvmSolver` は `left_boundary` と `right_boundary` に `BoundaryCondition` protocol を受け取り、`extend_with_ghosts(t)` 内で左右 ghost cell を埋める。`step(dt)` は ghost cell を含む配列から数値 flux を作り、内部 cell を保存形で更新する。

既存境界条件は以下である。

- `TransmissiveBoundary`: zero-gradient。ghost cell は隣接内部 cell のコピー。
- `ReflectiveBoundary`: slip-wall / closed-end reflection。運動量符号を反転。
- `PressureTankBoundary`: time-dependent `PressureSchedule` で静圧を与え、`velocity_policy` と `flow_direction` を指定可能。
- `PressureReservoirBoundary`: `PressureTankBoundary(ConstantPressure(...), velocity_policy="copy")` の互換 wrapper。
- `ValveOutletBoundary`: 右端 liquid valve 境界。
- `PumpInletBoundary`: 左端 pump discharge 圧力境界。

### 1.3 時間依存圧力境界、流量境界、速度境界の実装有無

時間依存圧力境界として `PressureSchedule` protocol と `LinearPressureRamp` が実装済みであり、`PressureTankBoundary` へ渡せる。`PumpInletBoundary` も `PumpHeadSchedule` を通じて時間依存 discharge pressure を作れる。

一方、一般的な time-dependent velocity boundary または mass-flow boundary は現時点では確認できない。`PressureTankBoundary.velocity_policy="fixed"` は固定速度を ghost cell に入れる機能だが、時間依存速度 schedule ではない。`ValveOutletBoundary` は valve law 由来の target velocity を作るが、今回の小振幅線形波入力としては余分な非線形要素になる。

### 1.4 初期保存量へ局所圧力摂動を与える方法

既存の `build_uniform_initial_state_from_pT(...)` は `CoolPropCO2Backend.density_from_pT(p, T)` と `internal_energy_from_pT(p, T)` から uniform な `U0` を作る。局所 pressure pulse を入れる場合は、cell-wise `p(x)` と一定 `T0` から cell-wise `rho(x)` と `e(x)` を取得し、`make_conserved(rho, u, e, xv)` で `U0` を作るのが最も明示的である。

注意点として、圧力 pulse と速度摂動を整合させない初期条件は左右に分かれる acoustic pulse を作る。片方向伝播を初回評価の中心にするなら、線形音響関係 `Δu = Δp / (rho0 * c0)` で同符号の速度 pulse も同時に入れる必要がある。ただし CoolProp real-fluid EOS で cell-wise `p,T` から作った `rho,e` と、`LCO2PropertyEOSAdapter.state_from_rho_e(...)` の戻り値が十分一致することを実装時に確認する。

### 1.5 history / probe / profile 出力の既存機構

`FvmSolver.run(t_end, max_steps, sample_every)` は scalar diagnostics history を返す。`diagnostics(dt)` には `p_min_pa`, `p_max_pa`, `rho_min_kg_m3`, `rho_max_kg_m3`, `xv_min/max`, `alpha_min/max`, `c_min/max`, `u_min/max` と budget diagnostics が含まれる。

Case C report 系には final profile CSV 用の cell-wise profile 生成がある。Case C CoolProp mini-run には `history.csv`, `final_profile.csv`, `metrics.json`, `config.json`, Markdown report を出す実装がある。ただし、現時点で任意 probe 位置の `p(t), T(t), rho(t), u(t), c(t)` を直接保存する汎用 probe history collector は見当たらない。次 PR では専用 probe collector を追加するのがよい。

### 1.6 CFL 設定方法

`FvmSolver.cfl` は `NumericsConfig` または solver 生成時に渡される。`compute_dt(t_end)` は `max(|u| + c)` から `dt = cfl * dx / max_speed` を計算し、`t_end` を超えないように切る。したがって `CFL = 0.25, 0.5` の比較は solver config を変えるだけで実施できる。

### 1.7 既存 MOC または単相波動比較コードの有無

現行 tree では、主ソルバとしての MOC は確認できない。`dvcm_legacy.py` は DVCM-like cavity field を作る legacy comparison proxy であり、full MOC-DVCM solver ではないと明記されている。単相 acoustic arrival を直接比較する MOC helper も確認できない。今回の理論比較は `CoolProp` 初期状態の `c0` に基づく `t = x / c0` を基準にする。

### 1.8 時系列取得方法

既存 scalar history から領域全体の extrema は取れるが、到達時刻判定には probe 別時系列が必要である。実装時は、各 solver step 後に `solver.primitive()` を呼び、probe 位置に最も近い cell の `p`, `T`, `rho`, `u`, `xv`, `alpha`, `c` を記録する。補間は初回では使わず nearest-cell とし、probe cell center の実座標を metadata に残す。

### 1.9 boundary 反射を避ける、または反射前だけ評価する方法

現行の `TransmissiveBoundary` は zero-gradient であり、厳密な non-reflecting characteristic boundary ではない。`PressureTankBoundary` も完全無反射ではない。したがって初回 verification は反射を完全に消すのではなく、入射波が各 probe に到達してから、下流端反射が当該 probe へ戻る前の時間窓だけで判定する。

## 2. 推奨する摂動方式

候補 A〜D のうち、初回 verification では **C. 管内初期圧力の局所パルス** を推奨する。

理由:

1. 境界入力を使わないため、`PressureTankBoundary` の圧力 schedule、ghost-cell energy copying、`velocity_policy` の影響を到達時刻評価から切り離せる。
2. `TransmissiveBoundary` を使っても、少なくとも最初の下流端反射が戻る前は入射波の評価ができる。
3. Gaussian など滑らかな局所 pulse にすれば、境界 step / ramp より高周波成分を抑えやすく、数値拡散と非線形性の観察がしやすい。
4. pulse 中心を上流寄りに置き、右向き成分を評価すれば、`t = (x_probe - x0) / c0` と比較できる。

推奨初期条件は **right-going Gaussian pressure-velocity pulse** とする。

```text
p(x, 0) = p0 + Δp * exp(-0.5 * ((x - x0) / sigma)^2)
u(x, 0) = Δp(x) / (rho0 * c0)
T(x, 0) = T0
xv(x, 0) = 0
```

`u = Δp/(rho0*c0)` を同時に与えることで、線形音響の右向き Riemann invariant に近い状態を作る。厳密な real-fluid isentropic perturbation ではないため、初回では振幅を十分小さくし、温度・密度変化と波形の左右分離を確認する。実装上この初期化が不安定な場合の fallback は、`u=0` の pressure-only pulse とし、左右に分かれる pulse の右向きピークのみを評価対象にする。

A/B の境界圧力入力は将来の boundary verification として有用だが、初回では境界条件自体の反射・エネルギー扱いが混ざる。D の速度 pulse は圧力振幅への換算が必要で、入力振幅の説明が圧力 pulse より直感的でない。

## 3. 基準解析条件

初回仕様として以下を基準にする。

| 項目 | 値 | 理由 |
|---|---:|---|
| `length_m` | `100.0` | 反射前窓を確保しつつ計算量を抑える。Case C の 2500 m は初回には長すぎる。 |
| `diameter_m` | `0.30` | Case C 既定径と同じで、area budget の解釈がしやすい。摩擦なしなので波速評価への影響はない。 |
| `n_cells` | `50, 100, 200` | メッシュ依存性の最小セット。 |
| `cfl` | `0.25, 0.5` | 既存 mini-run と同じ 0.5、および時間刻み依存性確認用 0.25。 |
| `p0` | `8.0e6 Pa` | 既存 CoolProp mini-run と同じ。 |
| `T0` | `280.0 K` | 既存 CoolProp mini-run と同じ。 |
| `Δp` | `1.0e3 Pa` | `Δp/p0 = 1.25e-4` で小振幅を保つ。 |
| `x0` | `0.10 L` | 上流境界から離し、L/4, L/2, 3L/4 probe の右向き到達を評価しやすくする。 |
| `sigma` | `0.03 L` | 数 cell 以上に広がる滑らかな pulse。`n_cells=50` でも約 1.5 cell なので、実装時に必要なら `0.04 L` へ広げる。 |
| probes | `L/4`, `L/2`, `3L/4` | 到達時刻の距離依存性を確認する。 |
| boundaries | `TransmissiveBoundary` both ends | 厳密無反射ではないが、境界圧力入力を避け、反射前のみ評価する。 |
| `sample_every` | `1` | 到達時刻判定を粗くしない。後で出力間引きは可能。 |
| `max_steps` | `100000` | 異常な小 `dt` を停止条件で検知する。 |

`t_end_s` は固定秒ではなく、初期音速 `c0` から計算する。

```text
t_downstream = (L - x0) / c0
t_reflect_back_to_L4 = t_downstream + (L - L/4) / c0
initial_end_target = min(1.05 * t_downstream, 0.90 * t_reflect_back_to_L4)
```

3 probes すべての入射波到達を含め、L/4 への下流端反射戻りより前に止める。厳密な無反射境界を実装しない限り、反射後は初回合否判定から除外する。

## 4. 理論値

実装時に初期 uniform state から `rho0`, `c0` を取得する。

```text
rho0 = mean(primitive.rho)
c0 = mean(primitive.c)
center_arrival_time_i = (x_probe_i - x0) / c0

Gaussian: dp(x) = A * exp(-0.5 * ((x - x0) / sigma)^2)
threshold_fraction = f
threshold_offset = sigma * sqrt(-2 * ln(f))
threshold_initial_x = x0 + threshold_offset  # right-going leading side
threshold_arrival_time_i = (x_probe_i - threshold_initial_x) / c0
inferred_wave_speed_i = (x_probe_i - threshold_initial_x) / numerical_arrival_time_i
```

`theoretical_center_arrival_time_*` は Gaussian 中心の到達時刻として後方互換・診断用に残す。主比較の `arrival_time_*`、`inferred_wave_speed_m_s`、`wave_speed_relative_error` は、数値検出と同じ立ち上がり側 threshold 特徴点に対する `theoretical_threshold_arrival_time_*` を基準にする。probe が `threshold_initial_x` より右側にあることを validation する。

right-going pressure-velocity pulse では、線形音響関係として以下を確認用に使う。

```text
Δp = rho0 * c0 * Δu
Δu = Δp / (rho0 * c0)
```

ただし、Gaussian pulse は有限幅を持ち、FVM は first-order Rusanov flux を使うため、peak amplitude は数値拡散で低下する。到達時刻は peak ではなく 50% crossing で定義する。

## 5. 到達時刻の判定方法

初回 verification では **baseline からの圧力変化が probe peak amplitude の 50% を初めて超える時刻**を `numerical_arrival_time_s` / `numerical_threshold_arrival_time_s` とする。理論値も Gaussian 中心ではなく同じ threshold fraction の初期 leading-side 位置と比較する。

手順:

1. 各 probe の `p(t)` から初期 baseline `p_baseline = p(t=0)` を取る。
2. 反射前評価窓内で `dp(t) = p(t) - p_baseline` を計算する。
3. `probe_peak_pressure_amplitude_pa = max(dp)` を求める。
4. threshold `= 0.5 * probe_peak_pressure_amplitude_pa` とする。
5. `dp(t)` が threshold を初めて上回る隣接 sample を線形補間して crossing time を求める。

この方法は実装が簡単で、peak 時刻より数値拡散に強い。各 probe の local peak 50% crossing を使うため、数値拡散で観測 peak が減衰しても到達を検出しやすい。一方で、local peak 50% 方式は波形変形の影響を受け、初期 Gaussian の厳密な 50% 位置と完全には同一でない可能性がある。このため正式な wave-speed acceptance threshold はまだ固定せず、修正後のメッシュ/CFL 比較後に決定する。

## 6. 評価指標

`metrics.json` には少なくとも以下を含める。

- `case_name`
- `software_numerical_verification = true`
- `design_evaluation = false`
- `acceptance_gate = false`
- `validation = false`
- `property_backend_name = coolprop_co2`
- `property_backend_design_status = not_approved_for_design_use`
- `coolprop_version`
- `git_commit_hash`
- `p0_pa`, `T0_K`, `rho0_kg_m3`, `c0_m_s`
- `length_m`, `diameter_m`, `n_cells`, `dx_m`, `cfl`
- `pulse_center_m`, `pulse_sigma_m`, `input_pressure_amplitude_pa`
- probe 別:
  - `probe_x_m`
  - `theoretical_arrival_time_s`
  - `numerical_arrival_time_s`
  - `arrival_time_absolute_error_s`
  - `arrival_time_relative_error`
  - `inferred_wave_speed_m_s`
  - `wave_speed_relative_error`
  - `probe_peak_pressure_amplitude_pa`
  - `amplitude_ratio`
  - `pressure_baseline_drift_pa`
- 全体:
  - `max_temperature_change_K`
  - `max_density_change_kg_m3`
  - `max_velocity_m_s`
  - `mass budget residual`
  - `energy budget residual`
  - `vapor mass budget residual`
  - `all_history_finite`
  - `remained_single_phase`
  - `missing_budget_fields`
  - `min_positive_dt_s`
  - `step_count`
  - `overall_verification_pass`

`remained_single_phase` は `quality=0` and `alpha=0` を基本条件とし、CoolProp backend の thermodynamic quality が single-phase sentinel を返す場合でも transported `xv=0` と adapter output `alpha=0` を優先して記録する。

## 7. 合格基準

この仕様段階では、根拠のない厳しい数値 threshold を正式固定しない。以下を区別する。

### 7.1 初回観測用の暫定目標

- `wave_speed_relative_error`: 数 % 以内を観測目標。
- `arrival_time_relative_error`: 数 % 以内を観測目標。
- `all_history_finite = true`: 必須。
- `p > 0`, `rho > 0`, `T > 0`, `c > 0`: 必須。
- `quality=0`, `alpha=0` 維持: 必須。
- budget residual: 既存 diagnostics で重大な破綻なし。
- reflected wave が到達判定を汚染しない。
- `property_backend_design_status = not_approved_for_design_use`: 必須。

### 7.2 次 PR 以降に regression test として固定する候補

初回メッシュ・CFL 依存性の実測後に、以下を正式 threshold 化する。

- `n_cells=100`, `cfl=0.5` の arrival / wave-speed error 上限。
- `n_cells` 増加で理論到達時刻への誤差が悪化しない、または十分小さいこと。
- amplitude ratio の許容下限。ただし first-order Rusanov の数値拡散を考慮し、過度に厳しくしない。
- budget residual の絶対値または相対値。

### 7.3 設計利用基準ではないこと

これらの threshold は software / numerical verification 用であり、設計評価・実設備 Validation・CoolProp design-use 承認の基準ではない。

## 8. メッシュ・CFL 依存性計画

初回比較 matrix:

| `n_cells` | `CFL` |
|---:|---:|
| 50 | 0.25 |
| 50 | 0.5 |
| 100 | 0.25 |
| 100 | 0.5 |
| 200 | 0.25 |
| 200 | 0.5 |

比較項目:

- `arrival_time`
- `inferred_wave_speed`
- `peak amplitude`
- `waveform broadening`（例: 50% crossing と peak time の差、または half-width）
- budget residual
- computational `step_count`
- `min_positive_dt_s`

最細メッシュを正解扱いしない。理論値 `t = distance/c0` との誤差傾向を主評価にする。

## 9. 反射と評価時間窓

pulse center を `x0`、probe を `xp`、下流端を `L` とする。

```text
入射波到達時刻:              t_incident(xp) = (xp - x0) / c0
下流端到達時刻:              t_downstream   = (L - x0) / c0
下流端反射が probe へ戻る時刻: t_reflect(xp) = t_downstream + (L - xp) / c0
```

初回到達判定 window は以下とする。

```text
t_start = max(0, t_incident(xp) - 3*sigma/c0)
t_end   = min(t_reflect(xp) - 3*sigma/c0, global_t_end_s)
```

`probe_peak_pressure_amplitude_pa` と 50% crossing はこの window 内で求める。`t_end <= t_start` となる probe がある場合は `reflection_free_window_unavailable` として明示停止する。

上流側へ進む左向き pulse は上流端で反射する可能性がある。`x0 = 0.10L` の場合、上流端反射が L/4 に届く時刻は概算で `(x0 + L/4)/c0` であり、右向き入射到達 `(L/4 - x0)/c0` より後である。したがって L/4 の評価 window では早すぎる上流反射混入を監視する。

## 10. 将来実装で生成すべき成果物

- `config JSON`
- `metrics JSON`
- `probe history CSV`
- `final profile CSV`
- Markdown report
- 可能なら `pressure history plot`
- `mesh/CFL comparison CSV`
- backend metadata:
  - `property_backend_name`
  - `property_backend_design_status`
  - `eos_model`
  - `quality_source`
  - `CoolProp version`
  - `git commit hash`
- 実行環境 metadata:
  - Python version
  - platform
  - `numpy` version

## 11. 停止条件

以下の場合は verification failure または明示停止とする。

- `NaN` / `inf`
- `p <= 0`
- `rho <= 0`
- `T <= 0`
- `c <= 0`
- `quality` または `alpha` が単相想定から外れる。
- `max_steps` 超過。
- 理論到達前に不自然な全域変化が発生する。
- boundary 条件により摂動が入力できない。
- 反射前評価窓を確保できない。
- budget diagnostics が取得不能で、原因も不明。
- `property_backend_design_status` が `not_approved_for_design_use` 以外になる。

## 12. 次 PR の最小実装計画

既存 Case C 本体、HEM/HNE、DVCM、UI には変更を加えない。

推奨する最小範囲:

1. `src/liquid_gas_transient/cases/coolprop_small_amplitude_wave.py` を追加。
   - 専用 `Config` dataclass。
   - `UniformGrid` 直接利用の dedicated builder。
   - `CoolPropCO2Backend` + `LCO2PropertyEOSAdapter`。
   - `NoPhaseChange`, `NoSource`, `TransmissiveBoundary`。
2. 初期 Gaussian right-going pulse builder。
   - cell-wise `p(x), T0` から `rho,e` を作る。
   - `u(x) = Δp(x)/(rho0*c0)` を与える。
3. probe history collector。
   - nearest-cell probe。
   - `p, T, rho, u, xv, alpha, c` を全 sample で保存。
4. metrics function。
   - 50% crossing。
   - 反射前 window。
   - budget residual と finite / positive checks。
5. artifact writer。
   - config, metrics, probe history, final profile, report。
6. tests。
   - dependency-free config validation test。
   - CoolProp installed-only smoke test (`pytest.importorskip("CoolProp")`)。
   - artifact schema test。

## 13. 設計上の注意

- 本 verification は software / numerical verification 用である。
- `coolprop_co2` の design-use 承認ではない。
- 実設備 Validation ではない。
- HEM / HNE の検証ではない。
- ESD 急閉や pump trip 評価ではない。
- DVCM との優劣判定ではない。
- `surrogate_lco2` と実在物性 backend を混同しない。
- `property_backend_design_status = not_approved_for_design_use` を成果物に必ず残す。

## 8. 波形可視化 artifact

小振幅波 verification では、到達時刻・推定波速・振幅比だけでは波形の拡散、歪み、反射前後の様子を直感的に確認しにくい。このため、case module は optional dependency の `matplotlib` が利用可能な場合に以下の PNG を自動生成する。

- `coolprop_small_amplitude_wave_probe_pressure_history.png`: 全 probe の `delta pressure [Pa]` と `time [s]` を重ね描きし、理論 threshold arrival と数値 threshold arrival を縦線で示す。`primary_for_wave_speed_assessment` の probe と diagnostic probe は凡例で区別する。
- `coolprop_small_amplitude_wave_xt_pressure_map.png`: 計算中に `sample_every` と整合して保持した全セル圧力場から、`x [m]` - `time [s]` の `delta pressure [Pa]` ヒートマップを描く。伝播速度、反射前評価 window、不要な波の有無を確認するための図である。
- `coolprop_small_amplitude_wave_pressure_snapshots.png`: `t=0`、L/2 近傍 probe の理論 threshold arrival、3L/4 近傍 probe の理論 threshold arrival、`0.9 * target_time_s` に近い sampled time の空間分布を重ね描きする。Gaussian 波形の広がりや数値拡散を確認するための図である。

`matplotlib` が利用できない環境では、run、metrics、probe history、final profile、Markdown report は成功させ、図生成だけを skip する。`metrics.json` には `plotting_available`、`generated_plots`、`figure_paths` を記録する。

これらの図は software / numerical verification の解釈補助であり、CoolProp backend の design-use 承認、Validation、HEM/HNE/DVCM 評価、Case C 本体の設計評価を意味しない。local peak 50% crossing に基づく到達検出は、振幅減衰と波形変形の影響を受けるため、正式な acceptance threshold はまだ固定しない。

## 11. Mesh/CFL sweep 表示と収束観察の整理

Mesh comparison の dx 図は、`comparison_groups` に `mesh_comparison` を含み、かつ `cfl == mesh_comparison_cfl` の run だけを対象にする。CFL comparison run は別 table / overlay に分離し、同じ `dx` の点を同一折れ線に混入させない。

`speed_error_vs_dx` は以下を別系列として表示する。

- threshold speed error: diagnostic metric
- peak speed error: primary phase-speed metric
- centroid speed error: supporting metric
- cross-correlation speed error: supporting metric

Peak speed error は error floor 近傍になり得るため、log scale または別表現で可読性を確保する。`waveform_difference_vs_dx` は finest-grid comparison reference との差であり、参照 run の 0 は定義による 0 で、厳密解に対する真の誤差 0 ではない。

`convergence_by_metric` は単一の混合判定だけにせず、指標別に `monotonic_improvement`、`at_error_floor_or_non_monotonic`、`monotonic_improvement_against_finest_reference` などを記録する。3 mesh levels から計算する `local_order_estimates` は formal order verification ではなく、局所的な診断値として扱う。正式な design-use / acceptance threshold はまだ設定しない。

Optional high-cost observation として `mesh_cells=(50, 100, 200, 400)` を指定できる。finest-grid comparison reference は指定された `mesh_cells` の最大値かつ `mesh_comparison_cfl` の run から自動選択する。
