# CoolProp-safe CO₂ 代表状態候補メモ

## 1. 文書の位置づけ

本書は、`coolprop_co2` backend を用いた Case C 最小試走に向けて、CoolProp API の software-path verification で扱いやすい CO₂ 代表状態候補を整理する開発メモである。主な目的は、`density_from_pT()`、`internal_energy_from_pT()`、`state_from_rho_e()`、`saturation_state()` の呼び出し経路を、数値的に過度に難しい状態を避けて確認することである。

本書は design-use 物性条件の承認文書ではない。ここに記載する圧力・温度・物性値は、CoolProp backend の実装経路確認、試走条件の候補整理、将来の verification 項目の準備に限定して扱う。

本書は acceptance gate、Validation、承認済み reference CSV、または設計評価用物性条件の代替ではない。`coolprop_co2` で取得した値であっても、acceptance gate 未通過の状態は `not_approved_for_design_use` として扱う。

## 2. 代表状態候補

### A. dense single-phase / supercritical-liquid 側状態

| 項目 | 候補 |
|---|---:|
| 圧力 | 8.0 MPa |
| 温度 | 280 K |
| backend | `coolprop_co2` |
| 主用途 | Case C mini-run 第一候補、`density_from_pT()` と `state_from_rho_e()` の往復確認 |

この状態は、既存の installed-only test で使用されている dense single-phase / supercritical-liquid 側として扱われ得る CO₂ 条件である。8 MPa は CO₂ の臨界圧力より高いため、`T_sat(p)` は定義対象外であり、飽和温度との差は `not_applicable_above_critical_pressure` として記録する。

確認事項は以下である。

- CoolProp 導入環境で dense single-phase / supercritical-liquid 側として評価され得ること。
- `p > pcrit` のため `T_sat(p)` を取得・記録する前提にしないこと。
- `density_from_pT(p, T)` で得た `rho` と、同じ `p, T` から CoolProp で得た `e` を用いて `state_from_rho_e(rho, e)` に戻したとき、`p` と `T` が許容誤差内で復元されること。
- `state_from_rho_e()` が正の有限音速を返し、solver の CFL 計算に使用できること。

本実行環境では CoolProp が未導入であるため、実物性値は記載しない。`rho`、`e`、`h`、sound speed、phase / quality は CoolProp 導入環境で取得予定である。

### B. 飽和線確認用状態

| 項目 | 候補 |
|---|---:|
| 代表圧力 | 1.9 MPa |
| backend | `coolprop_co2` |
| 主用途 | `saturation_state()` verification 専用 |
| 単相初期条件への使用 | 使用しない |

1.9 MPa は既存テストで `saturation_state()` の installed-only check に使われている代表圧力であり、飽和液密度、飽和蒸気密度、飽和温度、潜熱相当量が有限かつ物理的な大小関係を満たすことを確認する候補として扱う。

この候補は飽和線上の値を確認するための状態であり、単相初期条件として直接使用しない。特に、飽和線上では温度・圧力だけでは相が一意に決まらず、初期条件として使うと quality、音速、相分率の解釈が backend やモデル実装に強く依存する可能性がある。

確認事項は以下である。

- `saturation_state(1.9e6)` が有限の `T_sat`、`rho_l`、`rho_v`、`e_l`、`e_v`、`h_lv` を返すこと。
- `rho_l > rho_v` であること。
- `h_lv > 0` であること。
- 取得値は verification 用であり、design-use 承認値として扱わないこと。

本実行環境では CoolProp が未導入であるため、実物性値は CoolProp 導入環境で取得予定である。

### C. 飽和近傍だが単相側の状態

| 項目 | 候補 |
|---|---:|
| 代表圧力 | 1.9 MPa を起点候補とする |
| 代表温度 | `T_sat(p) - ΔT_margin` |
| 推奨する初期余裕 | まず `ΔT_margin = 2 K`、必要に応じて 5 K または 10 K も比較 |
| backend | `coolprop_co2` |
| 主用途 | 将来の Case D/E 識別ケース候補 |
| Case C mini-run 初期条件への採用 | 現時点では採用しない |

この候補は、将来の Case D/E で飽和近傍の液相側挙動を識別するための状態である。現時点では Case C mini-run の初期状態には採用せず、CoolProp の flash 安定性、単相判定、音速、`state_from_rho_e()` の逆変換安定性を確認した後に候補化する。

状態余裕の定義方法として、以下を提案する。

```text
ΔT_subcool(p) = T_sat(p) - T
```

液相側単相候補としては、指定圧力 `p` に対して `T = T_sat(p) - ΔT_margin` と置く。`ΔT_margin` は 2 K を最小候補とし、flash が不安定、音速が不定、または phase / quality 解釈が曖昧になる場合は 5 K、10 K と余裕を増やす。最終的な余裕は、CoolProp 導入環境で `density_from_pT()` と `state_from_rho_e()` の往復確認が安定することを条件に選ぶ。

## 3. 各状態で取得・保存する物性

CoolProp 未導入環境で実物性値を推測して埋めない方針とする。以下の表では、今回の環境で未取得の値を「CoolProp 導入環境で取得予定」と明記する。

| 状態 | p | T | rho | e | h | sound speed | phase / quality | saturation temperature との差 | 使用目的 | design-use status |
|---|---:|---:|---|---|---|---|---|---|---|---|
| A. dense single-phase / supercritical-liquid 側 | 8.0 MPa | 280 K | CoolProp 導入環境で取得予定 | CoolProp 導入環境で取得予定 | CoolProp 導入環境で取得予定 | CoolProp 導入環境で取得予定 | dense single-phase / supercritical-liquid 側として確認予定。CoolProp `Q` が単相特別値を返す場合は backend 側の quality 解釈を確認する | `not_applicable_above_critical_pressure` | Case C mini-run 第一候補、`density_from_pT()` / `internal_energy_from_pT()` / `state_from_rho_e()` 往復確認 | `not_approved_for_design_use` |
| B. 飽和線確認 | 1.9 MPa | `T_sat(1.9 MPa)` を取得予定 | `rho_l`, `rho_v` を取得予定 | `e_l`, `e_v` を取得予定 | `h_l`, `h_v` または潜熱相当量を取得予定 | 初期条件用には使用しない。二相域音速は未採用 | `Q=0` と `Q=1` の飽和端点として確認 | 0 K | `saturation_state()` verification 専用 | `not_approved_for_design_use` |
| C. 飽和近傍液相側 | 1.9 MPa 起点候補 | `T_sat(p) - ΔT_margin` | CoolProp 導入環境で取得予定 | CoolProp 導入環境で取得予定 | CoolProp 導入環境で取得予定 | CoolProp 導入環境で取得予定 | 単相液体側として確認予定。quality 特別値の解釈に注意 | `-ΔT_margin`。まず -2 K、必要に応じて -5 K / -10 K | 将来の Case D/E 識別ケース候補 | `not_approved_for_design_use` |

保存時は、少なくとも `p`、`T`、`rho`、`e`、`h`、sound speed、phase / quality、saturation temperature との差または `not_applicable_above_critical_pressure`、使用目的、design-use status を同一レコードに残す。特に、`coolprop_co2` の結果であっても design-use status を必ず併記する。

## 4. 選定基準

代表状態は以下の基準で選定する。

- CoolProp で安定して flash できること。
- 単相か二相かが明確であること。
- 臨界点近傍を避けること。`p > pcrit` の代表状態では `T_sat(p)` を取得する前提にしないこと。
- 飽和線上の値は、初期条件ではなく `saturation_state()` verification 用として分けること。
- `density_from_pT()` で得た `rho` と CoolProp で得た `e` を使い、`state_from_rho_e()` の逆変換確認ができること。
- solver の CFL 計算に必要な正の有限 sound speed が得られること。
- quality が単相で特別値を返す場合でも、transported quality と backend quality のどちらを使うかを明示できること。
- acceptance gate 未通過の値を design-use 条件と呼ばないこと。

## 5. 使用禁止・注意領域

以下の状態・解釈は、CoolProp backend の software-path verification であっても注意または禁止対象とする。

- 臨界点近傍を mini-run の第一候補にしない。密度・音速・熱物性の勾配が急で、flash や CFL 条件が不安定になりやすい。
- 飽和線上の `p, T_sat(p)` を単相初期条件として直接使わない。飽和線上の値は `saturation_state()` verification として扱う。
- CoolProp の `Q` が単相で負値などの特別値を返す場合、それを物理的な負の quality と解釈しない。backend では単相側 quality を 0 に丸める実装経路があるため、`quality_source` と併せて解釈する。
- 二相域で sound speed が未定義、非有限、または数値的に不安定な場合、その状態を CFL 計算を伴う mini-run 初期条件に使わない。
- metastable state を暗黙に期待しない。CoolProp の安定相 flash で得られる状態を前提とし、過冷却・過熱の準安定分岐を根拠なく設計条件化しない。
- acceptance gate 未通過状態を design-use と呼ばない。`coolprop_co2` は実在物性候補 backend であっても、本書の代表状態は `not_approved_for_design_use` である。

## 6. Case C mini-run への推奨

現時点の Case C mini-run 第一候補は、既存 installed-only test と同じ 8.0 MPa、280 K の dense single-phase / supercritical-liquid 側として扱われ得る状態とする。これは design-use 承認を意味しない。

| 項目 | 推奨値・方針 |
|---|---|
| 初期圧力 | 8.0 MPa |
| 初期温度 | 280 K |
| 初期密度 | `coolprop_co2.density_from_pT(8.0e6, 280.0)` で取得する。今回環境では CoolProp 未導入のため実値は CoolProp 導入環境で取得予定 |
| 初期内部エネルギー | `coolprop_co2.internal_energy_from_pT(8.0e6, 280.0)` で取得する。今回環境では CoolProp 未導入のため実値は CoolProp 導入環境で取得予定 |
| 初期蒸気質量分率 | mini-run では単相液体初期条件として 0 を候補にする。backend quality を使う場合は単相特別値の丸めを確認する |
| `quality_source` | 第一候補は `transported`。backend quality の採用は、CoolProp の単相 `Q` 特別値と backend 丸め処理を確認してから検討する |
| boundary temperature | 280 K を第一候補とし、pressure boundary の `density_from_pT(p, T_boundary)` と整合させる |
| 選定理由 | 既存 installed-only test で採用済みの dense single-phase / supercritical-liquid 側として扱われ得る条件であり、`p > pcrit` で `T_sat(p)` を前提にせず、`density_from_pT()`、`internal_energy_from_pT()`、`state_from_rho_e()` の往復確認に使えるため |
| 注意点 | 本書の条件は software-path verification 用であり design-use 条件ではない。CoolProp 導入環境で `rho`、`e`、sound speed、phase / quality を取得し、saturation temperature との差は `not_applicable_above_critical_pressure` として保存してから mini-run に使う |

コード構造上、`CoolPropCO2Backend.density_from_pT()` は `PropsSI("Dmass", "P", p, "T", T, "CO2")` を呼び、`internal_energy_from_pT()` は `PropsSI("Umass", "P", p, "T", T, "CO2")` を呼び、`state_from_rho_e()` は `PropsSI("P"/"T"/"Q"/"A", "Dmass", rho, "Umass", e, "CO2")` を呼ぶ。したがって 8.0 MPa、280 K は、`p, T` から `rho` を作り、同じ状態の `e` と組み合わせて `rho, e` flash の戻り値を確認する software-path verification に適している。
