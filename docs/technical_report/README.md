# Stage 1–U3 B0 Technical Report Workspace

## Status — 2026-08-05

```text
report type:                    internal technical report / research record
scope start:                    Stage 1
scope end:                      U3 B0 accepted component benchmark
current activity:               Gate 9 + U3 B0 evidence integration
report workspace version:       v0.3 target
full prose drafting:            NOT STARTED
physical validation claim:      PROHIBITED
approved design-use claim:      PROHIBITED
```

This directory is the controlled workspace for reorganizing the development from Stage 1 through Gate 9 and the accepted U3 B0 component benchmark into one logically consistent technical report.

The report is not a chronological pull-request list. Its purpose is to explain:

```text
why each verification layer was needed
→ what evidence was obtained
→ what the evidence supports
→ what remains unresolved
→ why the next controlled work is necessary
```

## Controlled deliverables

- [`lco2_fvm_hem_technical_report_contract_v0p1.json`](lco2_fvm_hem_technical_report_contract_v0p1.json)
- [`lco2_fvm_hem_writing_design_v0p1.md`](lco2_fvm_hem_writing_design_v0p1.md)
- [`lco2_fvm_hem_evidence_matrix_v0p1.md`](lco2_fvm_hem_evidence_matrix_v0p1.md)
- [`lco2_fvm_hem_figure_table_register_v0p1.md`](lco2_fvm_hem_figure_table_register_v0p1.md)
- [`lco2_fvm_hem_technical_report_skeleton_v0p1.md`](lco2_fvm_hem_technical_report_skeleton_v0p1.md)

## Evidence levels

| Level | Meaning | Current status |
|---|---|---|
| Software verification | code paths, identities, budgets, guards, and reproducibility | substantially established for reviewed fixed cases and U3 B0 component |
| Numerical characterization | mesh, CFL, diffusion, event and guard sensitivity | crossing-depth CFL sensitivity characterized; independence remains false |
| Model characterization | HEM assumptions, acoustic closure, phase classification, critical-flow alternatives | partially characterized; U3 B1 not yet locked |
| Physical validation and design use | experiment/field comparison and approved applicability envelope | not established |

No lower-level result may be presented as proof of a higher level.

## Central thesis after U3 B0

> A conservative one-dimensional finite-volume HEM path for pure CO2 was built and progressively verified from single-phase wave propagation through liquid-to-open-two-phase crossing, quality synchronization, and a fixed post-crossing continuation. Gate 9 established stable first-candidate time and position across the fixed CFL sequence while continuous crossing depth remained strongly CFL-sensitive and non-monotone. U3 B0 then added an independently benchmarked, verification-only subcooled-liquid discharge component: separate reference and adapter paths retained exact zero identities, fixed area and discharge-coefficient scaling, explicit guards, and 30/30 mass, momentum-stream, and energy comparisons. This closes the simplest component limit, not a physical blowdown boundary. Compressible critical-state search, static pressure-force mapping, finite-volume coupling, two-phase choking, high-point flashing, pump-trip integration, physical validation, and design use remain future work.

## Gate 9 authority

```text
D5 integration PR:                  #121
D5 workflow / artifact:             30805641241 / 8855725551
D5 artifact SHA256:                 6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850

D6 classification PR:               #122
D6 main merge SHA:                  5f0099101cbc9e9694297394a4c424904260ba94
D6 workflow / artifact:             30860513453 / 8875962770
D6 artifact SHA256:                 b0c4b490eedeb7332659051d13cc1e108ef08dfd381eec9fbf63773c4e4aa088
```

Primary record:

- [`../verification/stage7_gate9_closeout.md`](../verification/stage7_gate9_closeout.md)

## U3 B0 authority

Independent reference:

```text
PR / merge SHA:                    #124 / b4442d3df1a7517539520f79d82b85ef1c5aaec0
workflow / artifact:               30898882922 / 8890056064
artifact SHA256:                   7005055beb8b0722dd035f37c0fa6d10f46ddd121d6ead5906a8d941fb6c23a6
```

Adapter comparison:

```text
PR / merge SHA:                    #125 / 3937a276f8fefb62f297caa0e679660ec0d4c421
source head:                       42f9bd8384ebc06604924fc34ba05b45813e6b48
workflow / artifact:               30954035596 / 8912067053
artifact SHA256:                   4d7848ad06afd4765f37e102d155bc73df5663b3efb47a77513aa61410f6d7b2
```

Primary record:

- [`../verification/stage7_u3_b0_closeout.md`](../verification/stage7_u3_b0_closeout.md)

## U3 B0 supported claims

```text
locked subcooled-liquid component law reproduced
reference and adapter computation paths independent
closed and zero-pressure-drop identities exact
area and Cd scaling retained
10 fixed cases: 7 success and 3 guard
30 transfer comparisons: 30 pass
formal outcomes match
signed mass, momentum-stream, and enthalpy transfers retained
all final-head workflows successful
```

## U3 B0 prohibited claims

```text
physical discharge boundary approved
static pressure-force mapping approved
production FVM connection approved
single- or two-phase choking accuracy approved
integrated blowdown model approved
high-point flashing prediction validated
pump-trip prediction validated
physical validation or design use approved
```

## Report structure

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
11. U3 B0単相流出component benchmark
12. 公知文献との比較
13. 現在の適用限界
14. Critical discharge・高所・ポンプトリップへの展開
15. 結論
```

## Drafting order

```text
1. integrate Gate 9 and U3 B0 into evidence matrix and figure/table register
2. draft result chapters 6–11 from authoritative artifacts
3. draft methods chapters 2–5
4. draft literature comparison and discussion
5. draft limitations and next-roadmap chapter
6. draft introduction, abstract, and conclusion last
7. perform quantitative, provenance, and prohibited-claim audit
```

## Next controlled evidence

Primary:

```text
U3 B1 single-phase compressible / critical-state contract and independent reference
```

Parallel specification candidates:

```text
gravity/elevation benchmark for high-point pressure minima
prescribed-head-decay pump-trip negative-pressure propagation pilot
```

## Version intent

```text
v0.1  Stage 1–Gate 8 evidence and Gate 9 preparation
v0.2  Gate 9 D0–D6 execution and closeout
v0.3  U3 B0 accepted component benchmark
v0.4  U3 B1 critical-state evidence and parallel application specifications
v1.0  reviewed report through accepted physical-discharge boundary evidence
```
