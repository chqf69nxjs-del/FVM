# Stage 1–U3 B1 Technical Report Workspace

## Status — 2026-08-06

```text
report type:                    internal technical report / research record
scope start:                    Stage 1
scope end:                      U3 B1 accepted component benchmark
report workspace version:       v0.4
chapter 12 prose:               INTEGRATED
full report prose:              NOT COMPLETE
physical validation claim:      PROHIBITED
approved design-use claim:      PROHIBITED
production activation claim:    PROHIBITED
```

このdirectoryは、Stage 1からGate 9、U3 B0、U3 B1までのdevelopment evidenceを、一つの論理的なtechnical reportへ再構成するcontrolled workspaceである。

報告書はPRの時系列一覧ではなく、次の関係を説明する。

```text
why each verification layer was needed
→ what evidence was obtained
→ what the evidence supports
→ what remains unresolved
→ why the next controlled work is necessary
```

## Controlled v0.4 deliverables

- [`lco2_fvm_hem_technical_report_contract_v0p4.json`](lco2_fvm_hem_technical_report_contract_v0p4.json)
- [`lco2_fvm_hem_writing_design_v0p4.md`](lco2_fvm_hem_writing_design_v0p4.md)
- [`lco2_fvm_hem_evidence_matrix_v0p4.md`](lco2_fvm_hem_evidence_matrix_v0p4.md)
- [`lco2_fvm_hem_figure_table_register_v0p4.md`](lco2_fvm_hem_figure_table_register_v0p4.md)
- [`lco2_fvm_hem_technical_report_skeleton_v0p4.md`](lco2_fvm_hem_technical_report_skeleton_v0p4.md)
- [`chapters/chapter12_u3_b1_single_phase_critical_state_benchmark.md`](chapters/chapter12_u3_b1_single_phase_critical_state_benchmark.md)

## Historical v0.1 compatibility records

The existing structure workflow still verifies that the original v0.1 workspace remains present and discoverable. These files are retained as historical records and are not the active v0.4 contract:

- [`lco2_fvm_hem_technical_report_contract_v0p1.json`](lco2_fvm_hem_technical_report_contract_v0p1.json)
- [`lco2_fvm_hem_writing_design_v0p1.md`](lco2_fvm_hem_writing_design_v0p1.md)
- [`lco2_fvm_hem_evidence_matrix_v0p1.md`](lco2_fvm_hem_evidence_matrix_v0p1.md)
- [`lco2_fvm_hem_figure_table_register_v0p1.md`](lco2_fvm_hem_figure_table_register_v0p1.md)
- [`lco2_fvm_hem_technical_report_skeleton_v0p1.md`](lco2_fvm_hem_technical_report_skeleton_v0p1.md)

v0.1 files are retained as historical structure records and are not silently rewritten.

## Evidence levels

| Level | Meaning | Current status |
|---|---|---|
| E1 Software verification | code paths, identities, budgets, guards, reproducibility | established for reviewed fixed cases, B0 and B1 component benchmarks |
| E2 Numerical characterization | mesh, CFL, diffusion, event and guard sensitivity | crossing-depth CFL sensitivity characterized; independence remains false |
| E3 Model characterization | HEM assumptions, acoustic closure, phase classification, critical-flow alternatives | partial; single-phase B1 component accepted, integrated boundary not yet built |
| E4 Physical validation / design use | experiment/field comparison and approved envelope | not established |

No lower-level result may be presented as proof of a higher level.

## Central thesis after U3 B1

> A conservative one-dimensional finite-volume HEM path for pure CO₂ was built and progressively verified from single-phase wave propagation through liquid-to-open-two-phase crossing, quality synchronization, and fixed post-crossing diagnostics. Gate 9 retained comparatively stable first-candidate time and position across the fixed CFL sequence while crossing depth remained CFL-sensitive and non-monotone. U3 B0 and U3 B1 then established two independent, verification-only discharge-component layers: a subcooled-liquid limiting law and a single-phase compressible critical-state law. B1 reproduced 17 fixed outcomes and 77 Reference–Adapter comparisons, including choking, scaling, exact-zero identities, B0 limiting behavior, and explicit guards. These results do not yet constitute a physical FVM discharge boundary, finite-pipe blowdown model, physical validation, or design-use approval.

## Gate 9 authority

```text
D5 integration PR / artifact:          #121 / 8855725551
D6 classification PR / merge:          #122 / 5f0099101cbc9e9694297394a4c424904260ba94
D6 workflow / artifact:                30860513453 / 8875962770
```

Primary record: [`../verification/stage7_gate9_closeout.md`](../verification/stage7_gate9_closeout.md)

## U3 B0 authority

```text
Reference PR / merge:                  #124 / b4442d3df1a7517539520f79d82b85ef1c5aaec0
Adapter PR / merge:                    #125 / 3937a276f8fefb62f297caa0e679660ec0d4c421
fixed cases / comparisons:             10 / 30
passes:                                30 / 30
```

Primary record: [`../verification/stage7_u3_b0_closeout.md`](../verification/stage7_u3_b0_closeout.md)

## U3 B1 authority

```text
Reference PR / source / merge:         #131 / c7c25efae0e53a8b5f5ed164f9135238c6e005e0 / fa6c0ba14eb15dae482ee7766d03f7e1fca3574f
Reference run / artifact:              31051697864 / 8951665941
Reference ZIP SHA256:                  b3ba4ed848c9d01a9c1232efa8fa97b46e80bf61185c151f2f6acde6440a4f94
Adapter PR / source / merge:           #133 / 5939f152180fbc6ce9a638eeca670b34e1a6650f / e97be21de9b6cc62f527548e1047bc9d4ad759c1
Adapter run / artifact:                31073576151 / 8958246394
Adapter ZIP SHA256:                    b2b5b0ba68f58f72538c98a4570756360c5e8e3be87d3afdd797064464cf6aa2
fixed cases / comparisons:             17 / 77
passes:                                77 / 77
```

Primary record: [`../verification/stage7_u3_b1_closeout.md`](../verification/stage7_u3_b1_closeout.md)

## U3 B1 supported claims

```text
independent Reference and Adapter computation paths agree
fixed unchoked and choked single-phase component behavior is reproduced
critical pressure search is deterministic for the locked state family
closed and zero-pressure-drop stream transfers are exact zero
area and Cd scaling are retained
critical pressure is Cd-independent under the locked coefficient placement
B0 liquid limiting behavior is recovered within fixed tolerances
guard rows return explicit formal outcomes
```

## U3 B1 prohibited claims

```text
physical discharge boundary approved
static-pressure-force FVM face mapping approved
finite-pipe coupling approved
two-phase choking accuracy approved
integrated blowdown approved
physical validation established
design sizing or design use accepted
production HEM activation approved
```

## Report structure v0.4

```text
1.  緒言
2.  解析対象および支配方程式
3.  熱力学モデルと相状態処理
4.  数値解析手法
5.  段階的検証戦略
6.  基礎検証結果
7.  液相から二相への遷移検証
8.  配管減圧解析への拡張
9.  Post-crossing挙動とphase chatter
10. Gate 8–9 CFL感度とcrossing-depth診断
11. U3 B0 単相液体流出component benchmark
12. U3 B1 単相圧縮性流出および臨界状態benchmark
13. 公知文献との比較
14. 現在の適用限界
15. FVM境界coupling・高所・ポンプトリップへの展開
16. 結論
```

## Drafting order

```text
1. lock v0.4 structure and claim boundary
2. integrate Gate 9, B0 and B1 into evidence/registers
3. retain chapter 12 as reviewed working prose
4. draft result chapters 6–12 from authoritative records
5. draft methods chapters 2–5
6. draft literature comparison chapter 13
7. draft limitations and roadmap chapters 14–15
8. draft introduction, abstract and conclusion last
9. perform quantitative, provenance and prohibited-claim audit
```

## Next controlled evidence

Primary:

```text
single-phase discharge component FVM boundary-face mapping and finite-pipe coupling
```

The contract must lock static pressure force, transfer signs, face mapping, boundary-cell update, choking adoption, cumulative discharge, pipe-inventory closure, reflected waves, numerical stability, tolerances, and independent paths before implementation.

## Version intent

```text
v0.1  Stage 1–Gate 8 evidence and Gate 9 preparation
v0.2  Gate 9 D0–D6 execution and closeout
v0.3  U3 B0 accepted component benchmark
v0.4  U3 B1 accepted component benchmark and chapter-12 integration
v0.5  accepted single-phase FVM discharge coupling evidence
v1.0  reviewed report through physical-validation evidence; not yet reached
```
