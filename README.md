# Liquid CO₂ Pipeline Transient Analysis Tool

## 1. Project purpose

本プロジェクトの目的は、有限長液体CO₂配管における過渡圧力波、減圧、フラッシング、および気液二相化を、明示された適用範囲・制限・fail-closed条件のもとで**解析検討できる実用的な計算ツールを開発すること**である。

圧力伝播やフラッシング現象の完全な解明、全物理領域に対する包括的Verification、または全面的なPhysical Validationそのものを、Working Vertical Sliceの完成条件とはしない。

まず目指すのは、限定されたscope内で次を満たすツールである。

- 保存形一次元FVMにより一連の過渡計算を実行できる。
- 使用した物理モデル、物性backend、適用範囲、および制限を記録できる。
- solver crash、nonfinite、positivity loss、scope departure、root failureなどを明示的に検出し、必要に応じてfail closedできる。
- 圧力履歴、流動状態、相状態、transition、warning、および再現用manifestを保存できる。
- 結果を比較、感度検討、モデル差の確認、および将来の設計検討に利用できる。

開発原則は次のとおりである。

> Working vertical slice first → targeted Physics refinement / Verification second.

VerificationとValidationはツール開発を支える証拠活動であり、事前に定義した受入条件と具体的な利用目的に従って実施する。単に不安を減らすためだけの無期限な追加検証は行わない。

## 2. Primary analysis capabilities

本ツールが主に扱う解析検討対象は次である。

- 有限長配管内の過渡圧力波伝播
- 急減圧およびblowdown
- 液相から気液二相へのflashing
- pressure-wave arrival、crossing time / location、およびphase-region propagation
- HEMをbaselineとした平衡二相化
- HNE / relaxation modelによる相変化遅れの比較検討
- ESD弁、ポンプ停止、高所部、および流出境界を含む将来の実問題検討

これらは**ツールに要求する解析能力**であり、すべての現象を完全に解明・検証することを意味しない。

## 3. Current formal position

Stage 7は開発中であり、最初の実問題pilotはU3 pipeline depressurization / blowdownである。

Working Tool v0-Bは、canonical caseを実行し、結果、状態履歴、transition、warning、manifestをrun単位で保存できる、次の状態まで到達している。

```text
PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
```

ただし、次は成立していない。

```text
VERIFIED
ACCEPTED
PHYSICALLY VALIDATED
DESIGN-USE ACCEPTED
PRODUCTION APPROVED
```

正式な状態、SHA、Workflow、およびArtifact authorityはREADMEではなく、snapshot、master index、execution log、および各closeout文書で管理する。

## 4. Document authority and navigation

このREADMEは入口と案内を担う。physics仕様、Verification結果、Acceptance、Validation、またはdesign-use authorityを単独では付与しない。

### Project charter and strategy

- [`AGENTS.md`](AGENTS.md) — プロジェクト目的、開発原則、禁止事項
- [`docs/verification/project_document_authority_map.md`](docs/verification/project_document_authority_map.md) — 文書の役割、authority、重複関係
- [`docs/verification/stage7_real_problem_application_strategy.md`](docs/verification/stage7_real_problem_application_strategy.md) — Stage 7のツール開発・実問題適用戦略

### Current state and evidence authority

- [`docs/verification/stage7_current_gate_snapshot.md`](docs/verification/stage7_current_gate_snapshot.md) — current formal snapshot
- [`docs/verification/MASTER_VERIFICATION_INDEX.md`](docs/verification/MASTER_VERIFICATION_INDEX.md) — authoritative SHA / Workflow / Artifact index
- [`docs/verification/stage7_execution_log.md`](docs/verification/stage7_execution_log.md) — chronological execution history

### Main pressure-wave / flashing specifications

- [`docs/verification/stage7_lco2_hem_liquid_to_two_phase_boundary_crossing_spec.md`](docs/verification/stage7_lco2_hem_liquid_to_two_phase_boundary_crossing_spec.md) — liquid-to-open-two-phase transition contract
- [`docs/verification/stage7_lco2_hem_pipeline_depressurization_prototype_spec.md`](docs/verification/stage7_lco2_hem_pipeline_depressurization_prototype_spec.md) — prescribed-boundary pressure-wave to first-crossing prototype
- [`docs/verification/stage7_u3_b2_fvm_discharge_coupling_specification.md`](docs/verification/stage7_u3_b2_fvm_discharge_coupling_specification.md) — single-phase physical discharge boundary and finite-pipe coupling contract

### Working Tool operation layer

- [`docs/verification/stage7_u3_b2_a1_working_tool_v0_b_closeout.md`](docs/verification/stage7_u3_b2_a1_working_tool_v0_b_closeout.md) — Working Tool v0-B output / storage closeout

Working Tool documents define execution, output, storage, manifest, and reproducibility behavior. They do not replace the physics specifications above.

## 5. Maturity terminology

The following states must remain distinct.

| State | Meaning in this project |
|---|---|
| `IMPLEMENTED` | The function exists in code. |
| `WORKING VERTICAL SLICE` | A bounded end-to-end analysis study can be executed with explicit limitations. |
| `VERIFIED` | Predeclared numerical or contract conditions are satisfied. |
| `ACCEPTED` | A specified use case satisfies its acceptance criteria. |
| `VALIDATED` | Representative physical data or trusted references have been compared. |
| `APPROVED` | Organizational approval permits the bounded intended use. |

A successful calculation alone does not promote a result to Verification, Acceptance, Validation, or Approval.

## 6. Historical Phase 2 Ver.0.7.0 material

The earlier Phase 2 Ver.0.7.0 package contains reviewer-layered reports for three model-discrimination cases:

- Case D: high-point flashing
- Case E: near-saturation ESD closure
- Case A: pump trip / pump stop placeholder

Start with:

`verification/outputs_v0_7_0/case_d_e_a_reviewer_index_v0_7_0.md`

Then open each case-specific `*_reviewer_one_page_v0_7_0.md` and, if needed, `*_engineer_report_v0_7_0.md`.

These are historical discrimination cases using surrogate/amplified settings. They are not design-use LCO₂ results and are not the current project-status authority.

## 7. Backend naming roles

- `coolprop_lco2` is a Case C `eos_model` selector. It selects the CoolProp-backed LCO₂ adapter path for a Case C run.
- `coolprop_co2` is the canonical property backend name reported by `CoolPropCO2Backend.name`.
- Property verification, reference comparison, and acceptance-gate artifacts should use `backend.name` as the formal backend tracking name.
- `coolprop_lco2` does not indicate that the CoolProp backend or a Case C result is approved for design use; design-use status must come from the reference/acceptance-gate workflow.
