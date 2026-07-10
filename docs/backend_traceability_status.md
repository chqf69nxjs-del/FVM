# Backend traceability 整備状況メモ

## 1. 位置づけ

本メモは、Case C 系 report / metrics / CSV artifact に対する backend traceability 整備の現状を記録するものである。
ここでいう backend traceability は、Case C の計算条件としての `eos_model` と、実際に物性値を返す property backend canonical name を混同しないための出力整理を指す。

本メモは開発・verification 用の状態記録であり、`surrogate_lco2` や `coolprop_co2` を設計評価用 backend として承認するものではない。

## 2. 整備した内容

以下の 3 項目を Case C 系 artifact で追跡できるようにした。

| 項目 | 意味 |
|---|---|
| `eos_model` | Case C の EOS 選択子。例: `linear`, `toy_hem`, `lco2_surrogate`, `coolprop_lco2`。 |
| `property_backend_name` | 実際に物性値を返す backend の canonical name。例: `surrogate_lco2`, `coolprop_co2`。property backend を使わない場合は `none`。 |
| `property_backend_design_status` | 当該 backend を設計評価用として扱えるかを示す保守的な status。現状は report 用 metadata であり、acceptance gate の正式判定ではない。 |

特に、`coolprop_lco2` は Case C の `eos_model` selector であり、property backend canonical name ではない。
CoolProp backend の canonical name は `coolprop_co2` である。

## 3. 反映済みの artifact

### 3.1 Case C automated report v0.4.4

反映済み:

- `case_c_auto_evaluation_report_v0_4_4.md`
- `case_c_summary_comparison_v0_4_4.csv`
- `case_c_report_summary_v0_4_4.json`
- generator 戻り値の `base_backend_metadata`
- generator 戻り値の `summary_rows[*]`

### 3.2 Case C visualization package v0.6.1

反映済み:

- `case_c_visual_report_v0_6_1.md`
- `case_c_visual_summary_v0_6_1.csv`
- `case_c_visual_metrics_v0_6_1.json`
- metrics の `base_backend_metadata`
- metrics の `summary_rows[*]`

### 3.3 Case C DVCM legacy comparison package v0.6.2

反映済み:

- `case_c_dvcm_legacy_comparison_report_v0_6_2.md`
- `case_c_dvcm_comparison_summary_v0_6_2.csv`
- `case_c_dvcm_comparison_metrics_v0_6_2.json`
- metrics の `base_backend_metadata`
- metrics の `summary_rows[*]`

DVCM legacy row は property backend ではないため、以下のように明示する。

```text
eos_model: dvcm_legacy_proxy
property_backend_name: none
property_backend_design_status: not_applicable_legacy_proxy_not_design_model
```

### 3.4 Case C trial evaluation v0.6.0

反映済み:

- `case_c_trial_evaluation_report_v0_6_0.md`
- `case_c_trial_summary_v0_6_0.csv`
- `case_c_trial_metrics_v0_6_0.json`
- metrics の `base_backend_metadata`
- metrics の `summary_rows[*]`

trial evaluation report では、単独の `Backend` 表示ではなく、`eos_model`, `property_backend_name`, `property_backend_design_status` を併記する。
`backend_name` 設定値は reference backend 設定として残す。

### 3.5 property verification / reference / acceptance 系

property verification では、Case C selector である `eos_model` は対象外である。
そのため、従来どおり `backend` または `backend_name` を formal tracking name として扱う。

反映済みの考え方:

- property verification table: `backend`
- property verification metrics: `metrics_by_backend[*].backend`
- external reference / project reference / acceptance gate: `backend_name`

これらは Case C report 用の 3 項目形式とは異なるが、backend tracking としては現時点で許容する。

## 4. 未反映だが現時点で許容するもの

以下の高頻度・大容量系 CSV には、現時点では 3 項目を毎行付与しない。

- history CSV
- final profile CSV
- x-t field CSV
- DVCM field CSV

理由:

- これらは時系列またはセル分布の数値データであり、metadata を毎行付与すると冗長になる。
- 同じ package 内の summary CSV、metrics JSON、Markdown report に backend traceability metadata が含まれている。
- artifact 一式を同じ directory で保管する運用であれば、現時点では traceability を維持できる。

ただし、CSV 単体で外部共有する運用が増える場合は、metadata sidecar JSON の追加や CSV header comment 相当の仕組みを検討する必要がある。

## 5. `property_backend_design_status` の現状

現状の `property_backend_design_status` は report / metrics 用の保守的な metadata である。
正式な acceptance gate 判定結果そのものではない。

現状の扱い:

| backend / row | status |
|---|---|
| `surrogate_lco2` | `not_approved_for_design_use` |
| `coolprop_co2` | `not_approved_for_design_use` |
| property backend なし | `not_applicable_no_property_backend` |
| DVCM legacy proxy | `not_applicable_legacy_proxy_not_design_model` |
| その他の backend | `requires_acceptance_gate_before_design_use` |

重要事項:

- `surrogate_lco2` の結果を設計評価結果と呼ばない。
- `coolprop_co2` が利用可能であっても、それだけでは設計評価用承認を意味しない。
- DVCM legacy proxy は HEM/HNE と同等の熱力学モデルではなく、legacy comparison 用 proxy である。

## 6. acceptance gate との今後の接続

今後、設計評価用の property backend / reference table を扱うには、`property_backend_design_status` を acceptance gate の正式判定と接続する必要がある。

今後必要な整理:

1. reference table または backend の acceptance gate 結果を Case C report generator に渡す。
2. `property_backend_design_status` を固定文字列ではなく、acceptance gate decision に基づいて設定する。
3. design-use 可否を report / metrics / summary CSV に一貫して出力する。
4. `ACCEPTED_FOR_DESIGN_USE` 以外の状態では、設計評価結果として扱わない guardrail を維持する。

現時点では、backend traceability は verification / trial evaluation の出力追跡を目的とした整備段階であり、設計評価用承認 workflow は未完である。
