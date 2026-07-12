# Single-phase boundary reflection verification specification

この文書は、CoolProp 単相 CO2 small-amplitude Gaussian wave の Stage 5 として、右端境界における 1 回目の反射を numerical verification するための事前仕様である。今回の PR は仕様策定のみであり、solver、boundary condition、runner、runtime test は変更しない。

## 1. Purpose and guardrails

目的は、剛壁境界と固定圧力境界について、実装前に理論、符号規約、試験条件、評価 window、metrics、budget の扱い、artifact、停止条件を固定することである。

この verification は以下ではない。

- physical Validation ではない。
- design-use acceptance ではない。
- fixed pressure boundary を実 reservoir そのものとして扱うものではない。
- rigid wall を実弁閉止と同一視するものではない。
- `R_p = +/-1` を実機境界の一般結果とするものではない。
- 400-cell reference を厳密解とするものではない。
- CoolProp backend を design-use approved とするものではない。
- acceptance threshold を実測前に固定するものではない。

Metadata 方針:

- `software_path_verification = true`
- `numerical_verification = true`
- `design_evaluation = false`
- `acceptance_gate = false`
- `validation = false`
- `property_backend_design_status = not_approved_for_design_use`

## 2. Sign convention and characteristic diagnostics

この仕様で使う符号規約を以下に固定する。

- `x` は左から右を正とする。
- 右端境界は `x = L` とする。
- velocity perturbation `u' > 0` は右向きとする。
- pressure perturbation は `p' = p - p0` とする。
- reference acoustic impedance は `Z0 = rho0 * c0` とする。

pressure-like characteristic amplitude を verification 診断として以下で定義する。

```text
A_plus  = 0.5 * (p' + Z0 * u')
A_minus = 0.5 * (p' - Z0 * u')
```

線形小振幅域では以下を期待する。

- 右向き波: `A_plus = p'`, `A_minus = 0`
- 左向き波: `A_plus = 0`, `A_minus = p'`

この定義をすべての reflection metric で使用する。既存 solver 内部の characteristic 変数名と一致する必要はなく、verification 用の診断定義として独立に扱う。

## 3. Current repository survey

### 3.1 Conservative FVM solver boundary path

現行の conservative FVM solver は `FvmSolver` であり、`left_boundary` と `right_boundary` に `BoundaryCondition` protocol を受け取る。`extend_with_ghosts(t)` が内部 cell の左右に ghost cell を作り、各 boundary の `apply()` で ghost cell を埋める。`step(dt)` は ghost cell を含む隣接 state から `flux_function`、既定では Rusanov flux、を計算し、外部境界に隣接する `flux_left[0]` と `flux_right[-1]` を含めて内部 cell を保存形で更新する。

実装場所:

- `src/liquid_gas_transient/solver.py`: `FvmSolver`, `extend_with_ghosts`, `step`, `diagnostics`
- `src/liquid_gas_transient/boundary.py`: ghost-cell boundary implementations
- `src/liquid_gas_transient/flux.py`: numerical flux implementation

### 3.2 Ghost cell / boundary face state / boundary flux

Ghost cell は `BoundaryCondition.apply(U_ext, n_ghost, side, t, eos)` が直接 `U_ext` を変更する方式で実装されている。現行 solver は boundary face state を独立 object として返しておらず、外部 face の numerical flux は `step()` 内の局所変数である。

Boundary budget tracker は外部 face numerical flux を step ごとに受け取り、最後の flux と累積 flux を保持する。したがって mass / momentum / energy / vapor mass の boundary flux rate と cumulative flux は diagnostics から取得可能である。一方で、boundary face pressure、boundary face velocity、boundary face primitive state を時系列として直接記録する汎用 telemetry は確認できない。

Implementation gap:

- `boundary_face_pressure_pa` と `boundary_face_velocity_m_s` の厳密な face telemetry は未実装である。
- ghost cell または最隣接 cell-center 値を boundary face telemetry の代替として合格扱いしてはならない。
- 次 PR 以降で、boundary face state / flux を artifact に保存する minimal telemetry を設計する必要がある。

### 3.3 Existing fixed-pressure / reservoir-like boundary

`PressureTankBoundary` は `ConstantPressure` または schedule に基づく tank / reservoir 境界として実装されている。圧力 boundary が active な場合、ghost-cell density は `eos.density_from_pressure(p_b)` で作られ、velocity は `copy`、`zero`、`fixed` から選ぶ。`flow_direction` は `bidirectional`、`outlet_only`、`inlet_only` を持ち、禁止方向流れでは reflective wall fallback になる。

`PressureReservoirBoundary` は compatibility wrapper であり、`PressureTankBoundary(ConstantPressure(...), flow_direction="bidirectional", velocity_policy="copy")` として振る舞う。

Implementation gap / caution:

- 固定圧力 `p(L,t)=p0` の理想境界として Stage 5 にそのまま採用できるかは、ghost-cell density inversion、velocity policy、Rusanov flux、boundary face pressure residual の測定方法を含め、baseline runner design で確認する。
- CoolProp path では pressure-only density inversion が `boundary_temperature_K` に依存するため、固定圧力境界の熱力学整合性を specification と implementation survey に分けて扱う。

### 3.4 Existing wall / closed-end / zero-velocity-like boundary

`ReflectiveBoundary` は slip-wall / closed-end reflection boundary として実装され、ghost cell の momentum 符号を反転する。`ValveOutletBoundary` は opening = 0 のとき target face velocity が 0 になり、ghost momentum を mirror するため reflective closed-end wall に退化することが test されている。

Implementation gap / caution:

- `ReflectiveBoundary` による ghost-cell momentum 反転は存在するが、boundary face velocity residual、boundary pressure amplification ratio、zero mass flux、zero energy flux を直接 artifact 化する runner は未実装である。
- 壁は流体へ力を与えるため、流体領域単独の momentum が一定であることを合格条件にしない。

### 3.5 Case builder boundary specification

`coolprop_small_amplitude_wave` case は `build_coolprop_small_amplitude_wave_solver()` で `TransmissiveBoundary()` を左右に設定している。初期化 helper は CoolProp backend から `rho0`、`e0`、`c0` を取得し、右向き Gaussian pressure-velocity pulse を作る。probe history、profile、metrics、plotting helper、budget diagnostics は既存 case から再利用可能である。

Stage 5 では、この初期化、probe collector、plotting、budget field collection を再利用しつつ、右境界だけを rigid wall または fixed pressure に差し替える runner を次 PR 以降で設計する。

### 3.6 Boundary telemetry availability

取得可能なもの:

- `BoundaryBudgetTracker` による last left / right flux と cumulative flux。
- diagnostics による `budget_mass_*`, `budget_momentum_*`, `budget_energy_*`, `budget_vapor_mass_*`。
- solver primitive からの cell-center pressure / velocity / density / sound speed。

現状不足しているもの:

- boundary face pressure / velocity の dedicated telemetry。
- boundary face primitive state の dedicated history。
- `*_boundary_history.csv` artifact writer。
- reflection coefficient と window metadata を計算する Stage 5 専用 metrics。

### 3.7 Existing tests

関連する既存 test は以下である。

- `tests/test_smoke.py`: reflective boundary、closed valve boundary、pressure tank boundary、boundary budget、phase/energy budget diagnostics。
- `tests/test_coolprop_small_amplitude_wave.py`: CoolProp small-amplitude wave config、initial pulse、probe history、artifacts、plotting。
- `tests/test_coolprop_small_amplitude_wave_sweep.py`: mesh / CFL sweep と comparison metrics。
- `tests/test_coolprop_wave_regression.py`: CI-light numerical regression profile。
- `tests/test_wave_verification_report.py`: formal verification report rendering。

今回の仕様 PR では新しい runtime test は追加しない。

### 3.8 MOC or linear acoustic comparison code

現行 tree では、主ソルバとしての MOC は確認しない。`dvcm_comparison.py` は DVCM-like cavity field を作る legacy comparison proxy であり、full MOC-DVCM solver ではない。単相線形音響の reflection helper も現状確認しない。初回 Stage 5 では、CoolProp reference state の `c0` と本仕様の線形音響式を理論基準とする。

### 3.9 Reusable small-amplitude wave components

再利用候補:

- CoolProp reference state と right-going Gaussian pulse initialization。
- nearest-cell probe selection と probe history collection。
- final profile CSV writer。
- scalar health / budget diagnostics。
- FigureCanvasAgg による headless plotting と、plot failure を run failure にしない方針。
- formal report / manifest の artifact traceability 方針。

Implementation gap:

- Stage 5 の `A_plus` / `A_minus` history、incident/reflected windowing、boundary history、reflection coefficient、boundary residual、classification、comparison plots は未実装である。

## 4. Scope

対象:

- single-phase CO2
- CoolProp backend
- conservative FVM
- 一様断面直管
- 小振幅線形音響域
- 右向き Gaussian pressure pulse
- 右端境界での 1 回目の反射
- friction なし
- gravity なし
- local loss なし
- phase change なし

対象境界:

- A. closed / rigid wall
- B. fixed pressure at base pressure

対象外:

- valve closure
- finite-amplitude shock
- frictional attenuation
- reservoir impedance
- partial reflection
- area change
- junction
- two-phase flow
- flashing
- HEM / HNE
- ESD / pump trip
- physical Validation
- design-use acceptance

## 5. Boundary theory

### 5.1 Closed / rigid wall

Boundary condition:

```text
u'(L,t) = 0
```

理論:

```text
A_minus = A_plus
R_p = A_minus_reflected / A_plus_incident = +1
R_u = u_reflected / u_incident = -1
```

境界面では理想的に以下を期待する。

- pressure perturbation は入射波の約 2 倍。
- velocity perturbation は 0。
- mass flux は 0。
- energy flux は 0。

重要: 壁は流体へ力を与えるため、流体領域単独の momentum が一定であることを要求しない。要求するのは mass conservation、energy conservation、zero boundary mass flux、zero boundary energy flux、wall velocity residual である。

### 5.2 Fixed pressure boundary

Boundary condition:

```text
p'(L,t) = 0
p(L,t) = p0
```

理論:

```text
A_minus = -A_plus
R_p = -1
R_u = +1
```

境界面では理想的に以下を期待する。

- pressure perturbation は 0。
- velocity perturbation は入射速度の約 2 倍。
- mass / energy は境界を通過し得る。

重要: 固定圧力境界では、領域内の total mass / total energy が一定であることを要求しない。要求するのは boundary flux を含む mass balance、boundary flux を含む energy balance、fixed-pressure residual、不明な外部エネルギー生成がないことである。`energy is constant` と `energy balance residual is small` を混同しない。

## 6. Baseline configuration

既存 small-amplitude wave case と可能な限り揃える。

| item | baseline candidate |
|---|---:|
| `L` | `100.0 m` |
| `D` | `0.30 m` |
| `p0` | `8.0e6 Pa` |
| `T0` | `280.0 K` |
| pressure amplitude | `1.0e3 Pa` |
| Gaussian sigma | `3.0 m` |
| pulse center `x0` | `0.50 L` |
| `n_cells` | `100` |
| `CFL` | `0.5` |
| probes | `x/L = 0.75`, `x/L = 0.90` |
| primary timing probe | `x/L = 0.75` |
| primary reflection-coefficient probe | `x/L = 0.90` |
| right boundary | rigid wall or fixed pressure |
| left boundary | repository survey で利用可能な base-state-compatible boundary |
| plotting | observation run では有効 |
| phase change | none |
| quality | `0` |
| alpha | `0` |

左境界は、評価時間内に左端由来の戻り波が probe へ到達しないように選ぶ。実際の boundary 構成で追加 contamination path がある場合は metadata に記録する。

初期条件は右向き波だけを作る。

```text
p'(x,0) = dp0 * exp(-(x - x0)^2 / (2 * sigma^2))
u'(x,0) = p'(x,0) / (rho0 * c0)
```

Internal energy / density は CoolProp 経路から整合的に設定する。property 値を hard-code しない。

## 7. Theoretical timing

Probe 位置 `xp` について以下を定義する。

```text
t_incident(xp) = (xp - x0) / c0
t_boundary = (L - x0) / c0
t_reflected(xp) = (L - x0 + L - xp) / c0
                = (2L - x0 - xp) / c0
delta_t_roundtrip(xp) = 2 * (L - xp) / c0
sigma_t = sigma / c0
```

恒等関係:

```text
t_reflected(xp) - t_incident(xp)
= (2L - x0 - xp - xp + x0) / c0
= 2 * (L - xp) / c0
```

上記は target coordinate だけでなく、実際に採用された cell-center coordinate についても計算・記録する。

## 8. Evaluation windows

Incident と reflected を混ぜない。各 probe について候補 window を定義する。

```text
incident window  = t_incident  +/- 2.5 * sigma_t
reflected window = t_reflected +/- 2.5 * sigma_t
boundary window  = t_boundary  +/- 2.5 * sigma_t
```

Window が重なる場合は midpoint で clip する。Overlap を黙って許容せず、window metadata へ clip 理由を記録する。

Evaluation end time は自動計算する。最低条件は以下である。

- primary probe の reflected pulse 全体を含む。
- 左端由来の戻り波を含まない。
- 2 回目の境界反射を含まない。

左端由来の最早 contamination time 候補:

```text
t_left_return(xp) = (x0 + xp) / c0
t_end < t_left_return(primary probes) - safety_margin
safety_margin = 2.5 * sigma_t
```

実際の boundary 構成により別の contamination path がある場合は repository survey に基づき追加する。

## 9. Primary metrics

各 probe で以下を記録する。

Reference:

- `rho0`
- `c0`
- `Z0`
- actual cell-center coordinate
- theoretical incident time
- theoretical reflected time
- window boundaries

Incident:

- `incident_A_plus_peak_pa`
- `incident_A_plus_peak_time_s`
- `incident_A_minus_leakage_peak_pa`
- `incident_characteristic_leakage_ratio`

Reflected:

- `reflected_A_minus_signed_extremum_pa`
- `reflected_A_minus_extremum_time_s`
- `reflected_A_plus_leakage_peak_pa`
- `reflected_characteristic_leakage_ratio`

Reflection:

- `pressure_reflection_coefficient`
- `velocity_reflection_coefficient`
- `pressure_reflection_magnitude_error`
- `expected_pressure_reflection_sign`
- `observed_pressure_reflection_sign`
- `reflected_arrival_time_error_s`
- `reflected_arrival_time_relative_error`
- `roundtrip_time_error_s`

Signed extremum:

- rigid wall では reflected `A_minus` の正の最大値。
- fixed pressure では reflected `A_minus` の負の最小値。

```text
R_p = reflected_A_minus_signed_extremum / incident_A_plus_peak
incident velocity amplitude = incident_A_plus_peak / Z0
reflected velocity amplitude = -reflected_A_minus_signed_extremum / Z0
R_u = reflected_velocity_amplitude / incident_velocity_amplitude
```

理論上 `R_u = -R_p` であり、この整合誤差も記録する。

## 10. Boundary-face metrics

Boundary face state または flux を取得できる場合、以下を記録する。

Common:

- `boundary_face_pressure_pa`
- `boundary_face_velocity_m_s`
- `boundary_mass_flux`
- `boundary_energy_flux`
- boundary sample time

Rigid wall:

- `max_abs_wall_velocity_m_s`
- `normalized_wall_velocity_residual`
- `max_abs_wall_mass_flux`
- `max_abs_wall_energy_flux`
- `boundary_pressure_amplification_ratio`

理論: `boundary_pressure_amplification_ratio ≈ 2`。

Fixed pressure:

- `max_abs_fixed_pressure_residual_pa`
- `normalized_fixed_pressure_residual`
- `boundary_velocity_amplification_ratio`
- `integrated_boundary_mass_flux`
- `integrated_boundary_energy_flux`

理論: `boundary_velocity_amplification_ratio ≈ 2`。

Boundary face telemetry が現状取得できない場合は required implementation gap として記録する。Cell-center 値で代替して合格扱いしない。

## 11. Health and budget metrics

Common health:

- `completed_without_exception`
- `reached_target_time`
- `within_max_steps`
- `all_history_finite`
- `positive_pressure`
- `positive_temperature`
- `positive_density`
- `positive_sound_speed`
- `remained_single_phase`
- `max_alpha`
- `max_vapor_mass_fraction`
- `missing_budget_fields`

Rigid wall:

- mass relative residual
- energy balance relative residual
- vapor mass balance relative residual
- integrated boundary mass flux
- integrated boundary energy flux

期待:

- mass / energy flux ≈ 0。
- mass / energy balance residual ≈ machine precision。

Fixed pressure:

- mass balance including boundary flux
- energy balance including boundary flux
- vapor mass balance
- integrated boundary fluxes

期待:

- total mass / energy そのものは一定でなくてよい。
- flux-accounted balance residual が小さいこと。

Momentum:

- boundary force を含まない単純な constant momentum を要求しない。
- momentum balance を評価する場合は wall / pressure boundary force を含める。
- 初回仕様では必須 gate にしない。

## 12. Secondary waveform diagnostics

候補:

- incident / reflected temporal FWHM
- reflected-to-incident FWHM ratio
- reflected-to-incident waveform correlation
- reflected-to-incident normalized L1 difference
- reflected-to-incident normalized L2 difference
- pressure / velocity phase relation
- reflected pulse centroid time

これらは初回 implementation では diagnostic でよい。Reflection coefficient と timing を primary とする。Fixed-pressure case では sign を反転して shape comparison する。

## 13. Test matrix

### Phase A: baseline observation

- boundary = rigid wall, `n_cells = 100`, `CFL = 0.5`
- boundary = fixed pressure, `n_cells = 100`, `CFL = 0.5`

### Phase B: mesh observation

各 boundary について:

- `n_cells = 50`, `CFL = 0.5`
- `n_cells = 100`, `CFL = 0.5`
- `n_cells = 200`, `CFL = 0.5`

400-cell は初回 default へ入れない。必要性が確認された場合のみ high-cost observation とする。

### Phase C: CFL observation

各 boundary について:

- `n_cells = 100`, `CFL = 0.25`
- `n_cells = 100`, `CFL = 0.5`

CFL が小さい方を正解扱いしない。

## 14. Observation classification

正式な accuracy acceptance threshold は今回設定しない。

Execution classification:

- `execution_complete`
- `execution_failed`

Theoretical consistency classification:

- `expected_sign_and_timing_observed`
- `expected_sign_observed_but_timing_or_magnitude_mixed`
- `reflection_detected_but_theory_not_supported`
- `reflection_not_detected`
- `insufficient_data`

Mesh observation:

- `monotonic_improvement`
- `mixed_behavior`
- `no_clear_improvement`
- `insufficient_data`

Hard health failure:

- exception
- target time 未達
- NaN / Inf
- non-positive `p/T/rho/c`
- phase change
- missing required budget
- evaluation window contamination
- reflection 未検出

Reflection coefficient の絶対精度 band は、baseline と mesh 結果を確認した後の別 PR で決める。

## 15. Required artifacts

各 run:

- `*_config.json`
- `*_metrics.json`
- `*_probe_history.csv`
- `*_boundary_history.csv`
- `*_final_profile.csv`
- `*_report.md`

Plotting available 時:

- pressure and velocity probe histories
- `A_plus` / `A_minus` characteristic histories
- pressure x-t map
- velocity x-t map
- pressure snapshots before / during / after reflection
- velocity snapshots before / during / after reflection
- boundary-face pressure / velocity history

比較 run:

- reflection coefficient vs `dx`
- reflected arrival-time error vs `dx`
- wall velocity residual vs `dx`
- fixed-pressure residual vs `dx`
- incident / reflected waveform overlay
- CFL overlay

Headless `FigureCanvasAgg` 方式を使用する。1 図の失敗で他の成功図を失わない。

## 16. Report structure

生成 report 候補章:

1. Purpose and guardrail
2. Boundary theory
3. Sign convention
4. Repository implementation path
5. Configuration
6. Timing and window construction
7. Characteristic decomposition
8. Reflection coefficient
9. Boundary residual
10. Conservation and boundary flux
11. Mesh / CFL observation
12. Figures
13. Result classification
14. Limitations
15. Next action

明記:

- numerical verification である。
- physical Validation ではない。
- design-use 承認ではない。
- fixed pressure は zero impedance idealization である。
- rigid wall は infinite impedance idealization である。
- actual reservoir / valve / equipment reflection ではない。

## 17. Formula and sign consistency check

Rigid wall:

```text
A_minus = A_plus
R_p = +1
R_u = -R_p = -1
```

Fixed pressure:

```text
A_minus = -A_plus
R_p = -1
R_u = -R_p = +1
```

Timing:

```text
t_reflected - t_incident = 2 * (L - xp) / c0
```

この恒等関係は Markdown review または軽量 script で確認する。新しい runtime test は追加しない。

## 18. Implementation plan for later PRs

PR-A:

- Existing boundary implementation survey 結果に基づく minimal boundary telemetry / gap 対応。
- Solver physics 変更を最小化。
- Pure helper tests。

PR-B:

- Baseline rigid-wall observation runner。
- Baseline fixed-pressure observation runner。
- Metrics / artifacts。
- CoolProp installed-only smoke tests。

PR-C:

- Mesh / CFL sweep。
- Comparison plots。
- Report。

PR-D:

- CI-light regression 候補。
- Formal report integration。
- `MASTER_VERIFICATION_INDEX.md` を COMPLETE へ更新。

1 PR で全部実装しない。
