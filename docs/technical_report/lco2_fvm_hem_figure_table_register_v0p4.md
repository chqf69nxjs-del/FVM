# 液化CO₂配管過渡解析 技術報告書 — 図表台帳 v0.4

## 1. Rules

- 解析結果図にはcase、model、backend、version、source SHA、run / artifactを残す。
- conceptual figureには`CONCEPTUAL / NOT TO SCALE`を表示する。
- 色だけに依存しない。
- Artifact-derived figureは再生成sourceを記録する。
- B0 / B1図をphysical validation図として扱わない。

## 2. Retained pre-B1 register

v0.1のF01–F17、T01–T16はhistorical planning recordとして保持する。v0.4では章番号を次のように読み替える。

```text
old literature chapter 12  -> chapter 13
old limitations chapter 13 -> chapter 14
old roadmap chapter 14     -> chapter 15
old conclusion chapter 15  -> chapter 16
```

## 3. Chapter 11 — U3 B0

| ID | Figure / table | Status | Source | Claim limit |
|---|---|---|---|---|
| F18 | B0 liquid-limit component workflow | NEW | B0 contract / closeout | physical boundaryと描かない |
| F19 | B0 exact-zero and scaling summary | NEW / REFORMAT | B0 Artifact 8912067053 | fixed cases only |
| T17 | B0 10-case / 30-comparison matrix | AVAILABLE | B0 closeout | choking claim禁止 |

## 4. Chapter 12 — U3 B1 figures

| ID | Repository path | Type | Source / provenance | Claim limit |
|---|---|---|---|---|
| F20 | `figures/ch12/fig12_01_back_pressure_response.svg` | fixed-case quantitative | Adapter Artifact 8958246394; `adapter_cases.csv` | discrete fixed cases; physical release curveではない |
| F21 | `figures/ch12/fig12_02_critical_mechanism.svg` | conceptual | locked law $G=\rho u$ | conceptual / not to scale |
| F22 | `figures/ch12/fig12_03_cd_scaling.svg` | fixed-case quantitative | `critical_state_summary.json` | locked coefficient placement only |
| F23 | `figures/ch12/fig12_04_area_scaling.svg` | fixed-case quantitative | `adapter_cases.csv` | fixed effective areas only |
| F24 | `figures/ch12/fig12_05_reference_adapter_parity.svg` | quantitative parity | `reference_adapter_comparison.csv` | verification parity, not physical accuracy |
| F25 | `figures/ch12/fig12_06_b0_limit.svg` | quantitative limiting comparison | `summary.json` / contract tolerances | one fixed small-drop case |
| F26 | `figures/ch12/table12_01_guard_matrix.svg` | result table | `guard_outcomes.csv` | guard behavior only |

All F20–F26 include:

```text
model: U3 B1 verification-only single-phase component
backend: CoolProp 8.0.0
Adapter source SHA: 5939f152180fbc6ce9a638eeca670b34e1a6650f
run / artifact: 31073576151 / 8958246394
```

## 5. Chapter 12 tables

| ID | Contents | Source | Status |
|---|---|---|---|
| T18 | Reference / Adapter authority | B1 closeout | AVAILABLE |
| T19 | 17-case / 77-comparison summary | summary.json | AVAILABLE |
| T20 | critical-state values | critical_state_summary.json | AVAILABLE |
| T21 | B0 limiting relative errors and tolerances | summary.json / contract | AVAILABLE |
| T22 | approval boundary true / false flags | B1 closeout | AVAILABLE |

## 6. Later chapters

| ID | Figure / table | Chapter | Status |
|---|---|---:|---|
| F27 | HEM / HRM / two-fluid and numerical-method candidate hierarchy | 13 | NEW |
| F28 | multi-axis applicability ladder | 14 | NEW |
| F29 | single-phase FVM coupling contract and verification ladder | 15 | NEW |
| T23 | current supported / prohibited claim matrix | 14 | AVAILABLE / REFORMAT |
| T24 | future gate input / output / completion boundary | 15 | NEW |

## 7. Preparation priority

```text
P0-1  F20–F26 chapter-12 figures
P0-2  T18–T22 chapter-12 tables
P0-3  Gate 9 chapter-10 principal figures
P0-4  B0 chapter-11 summary
P0-5  F28 applicability ladder
P0-6  F29 single-phase coupling roadmap
```
