# Stage 1–Gate 9 Technical Report Workspace

## Status — 2026-08-04

```text
report type:                    internal technical report / research record
scope start:                    Stage 1
scope end:                      Gate 9 D6 closeout
current activity:               Gate 9 evidence integration and result drafting
full prose drafting:            NOT STARTED
physical validation claim:      PROHIBITED
approved design-use claim:      PROHIBITED
```

This directory is the controlled workspace for reorganizing the development from Stage 1 through the Gate 9 closeout into one logically consistent technical report.

The report is not a chronological list of pull requests. Its purpose is to explain the research logic:

```text
why each verification layer was needed
→ what evidence was obtained
→ what the evidence supports
→ what remains unresolved
→ why the next controlled work is necessary
```

## Controlled deliverables

- [`lco2_fvm_hem_technical_report_contract_v0p1.json`](lco2_fvm_hem_technical_report_contract_v0p1.json)
  - machine-readable scope, title, claims, non-claims, chapter structure, and update rules;
- [`lco2_fvm_hem_writing_design_v0p1.md`](lco2_fvm_hem_writing_design_v0p1.md)
  - chapter-by-chapter purpose, central message, evidence, figures, tables, and writing cautions;
- [`lco2_fvm_hem_evidence_matrix_v0p1.md`](lco2_fvm_hem_evidence_matrix_v0p1.md)
  - traceability from report statements to Stage/Gate records, PRs, workflows, and artifacts;
- [`lco2_fvm_hem_figure_table_register_v0p1.md`](lco2_fvm_hem_figure_table_register_v0p1.md)
  - planned figure and table inventory, data source, status, and drafting priority;
- [`lco2_fvm_hem_technical_report_skeleton_v0p1.md`](lco2_fvm_hem_technical_report_skeleton_v0p1.md)
  - report body with drafting notes and evidence placeholders.

## Working principle

The report follows four evidence levels.

| Level | Meaning | Current status |
|---|---|---|
| Software verification | code paths, identities, budgets, guards, and reproducibility | substantially established for reviewed fixed cases |
| Numerical characterization | mesh, CFL, numerical diffusion, event and guard sensitivity | crossing-depth CFL sensitivity characterized; independence remains false |
| Model characterization | HEM assumptions, acoustic closure, phase classification, relaxation alternatives | partially characterized; root causes remain unresolved |
| Physical validation and design use | comparison against experimental or field data and approved applicability envelope | not established |

No statement from a lower level may be presented as proof of a higher level.

## Baseline central thesis after Gate 9

> A conservative one-dimensional finite-volume HEM path for pure CO2 was built and progressively verified from single-phase wave propagation through liquid-to-open-two-phase crossing, quality synchronization, and a fixed post-crossing continuation. Gate 9 showed that the first-crossing candidate remains aligned in time and position across the fixed CFL sequence, while continuous crossing depth is strongly CFL-sensitive and non-monotone. Raw thermodynamic crossing precedes quality projection, and the fixed threshold discretizes the continuous depth into accepted / guard outcomes. Candidate time step, Rusanov dissipation, boundary net flux, and accepted acoustic branch do not individually explain the full ordering. The current path is therefore an evidence-rich verification baseline, not a physically validated design model. The next controlled implementation is an independently benchmarked physical discharge component.

## Gate 9 authority

The report must use the following authoritative closeout chain:

```text
D5 integration PR:                  #121
D5 workflow / artifact:             30805641241 / 8855725551
D5 artifact SHA256:                 6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850

D6 classification PR:               #122
D6 main merge SHA:                  5f0099101cbc9e9694297394a4c424904260ba94
D6 workflow / artifact:             30860513453 / 8875962770
D6 artifact SHA256:                 b0c4b490eedeb7332659051d13cc1e108ef08dfd381eec9fbf63773c4e4aa088
```

Primary closeout record:

- [`../verification/stage7_gate9_closeout.md`](../verification/stage7_gate9_closeout.md)

## Gate 9 claim boundary

Supported:

```text
candidate time / position stable across fixed CFL sequence
crossing depth CFL-sensitive
crossing depth sequence non-monotone
raw crossing precedes first projection
fixed threshold discretizes continuous depth
saturation margins preserve depth ordering
```

Not supported:

```text
crossing-depth root cause established
threshold change authorized
Rusanov dissipation proven causal
boundary flux proven causal
acoustic branch proven causal
mesh- or CFL-independent two-phase solution established
physical phase-front speed validated
physical validation or design use approved
```

## Updated report structure

```text
1. 緒言
2. 解析対象および支配方程式
3. 熱力学モデルと相状態処理
4. 数値解析手法
5. 段階的検証戦略
6. 基礎検証結果
7. 液相から二相への遷移検証
8. 配管減圧解析への拡張
9. Post-crossing挙動とphase chatter
10. Gate 8–9 CFL感度とcrossing-depth診断
11. 公知文献との比較
12. 現在の適用限界
13. 物理流出境界への展開と開発ロードマップ
14. 結論
```

## Drafting order

```text
1. integrate Gate 9 closeout into evidence matrix and figure/table register
2. draft result chapters 6–10 from authoritative artifacts
3. draft methods chapters 2–5
4. draft literature comparison and discussion
5. draft limitations and U3 roadmap
6. draft introduction, abstract, and conclusion last
7. perform quantitative, provenance, and prohibited-claim audit
```

The report should remain versioned rather than overwritten:

```text
v0.1  Stage 1–Gate 8 evidence and Gate 9 preparation
v0.2  Gate 9 D0–D6 execution and closeout
v0.3  U3 B0 component benchmark
v1.0  reviewed report through accepted physical-discharge component evidence
```
