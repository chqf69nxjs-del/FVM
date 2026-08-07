# 液化CO₂配管過渡解析 技術報告書 — 証拠対応表 v0.4

## 1. Evidence use rules

```text
E1 software verification:
  identity、guard、budget、CI、SHA、independent-path parity
E2 numerical characterization:
  mesh／CFL感度、非単調性、formal outcome divergence
E3 model characterization:
  HEM、acoustic、phase、critical-state model behavior
E4 physical validation / design use:
  current status is NOT ESTABLISHED
```

定量値の優先順位：closeout record → authoritative Artifact → reviewed PR record → current snapshot → source default。

## 2. Chapter-to-evidence matrix

| 章 | 中心主張 | Primary record | Evidence level |
|---:|---|---|---|
| 1 | 段階的verificationとTrack N / Aが必要 | application strategy / literature | E3 |
| 2 | 共通基盤は一次元保存形FVM | source / Gate closeout | E1 |
| 3 | raw classification、projection、accepted EOS、sound-speed guardを分離 | PR #54–#72 / Gate 5–7 | E1/E3 |
| 4 | first-order Rusanov / CFL controlとtraceability | source / Gate contracts | E1/E2 |
| 5 | Stage 1〜U3 B1はverification hierarchy | master / execution log | E1–E3 |
| 6 | 単相wave・reflection・boundaryを検証 | archived master | E1/E2 |
| 7 | raw crossingとprojected recoveryを確認 | PR #70–#72 | E1 |
| 8 | prescribed-boundary pipeline analogueを実行 | PR #74–#91 | E1/E2 |
| 9 | fixed continuationとlocalized chatterを診断 | Gate 6–7 closeout | E1/E2/E3 |
| 10 | crossing depthはCFL-sensitive / non-monotone、root cause false | Gate 8–9 closeout | E1/E2/E3 |
| 11 | B0は10ケース・30比較のverification-only limit component | B0 closeout | E1 |
| 12 | B1は17ケース・77比較のsingle-phase critical component | B1 closeout / Artifact 8958246394 | E1/E3 |
| 13 | 文献はdiagnosis / future comparisonを支援 | Gate 9 literature registry | E3 |
| 14 | physical validation / design use / productionは未成立 | snapshot / approval flags | E4=false |
| 15 | 次はsingle-phase FVM mapping / coupling contract | B1 closeout | E1–E3 |
| 16 | current pathはverification baselineである | chapters 6–15 | E1–E4 |

## 3. Gate 9 evidence

```text
D5 run / artifact:                    30805641241 / 8855725551
D6 run / artifact:                    30860513453 / 8875962770
D6 tests:                             6 / 52 / 903 passed
candidate time / position:            comparatively stable across fixed CFL
crossing depth:                       CFL-sensitive / non-monotone
root cause approval:                  false
```

Allowed: fixed sequenceのcharacterization。Prohibited: convergence、root cause、physical front accuracy。

## 4. U3 B0 evidence

```text
Reference PR / merge:                 #124 / b4442d3df1a7517539520f79d82b85ef1c5aaec0
Adapter PR / merge:                   #125 / 3937a276f8fefb62f297caa0e679660ec0d4c421
cases:                                10
success / guard:                      7 / 3
transfer comparisons:                 30
passes:                               30 / 30
```

Allowed: locked liquid limit, exact zero, area / Cd scaling, explicit guards。Prohibited: compressible choking、physical boundary、FVM coupling。

## 5. U3 B1 authority

### Reference

```text
PR / source / merge:                  #131 / c7c25efae0e53a8b5f5ed164f9135238c6e005e0 / fa6c0ba14eb15dae482ee7766d03f7e1fca3574f
run / artifact:                       31051697864 / 8951665941
ZIP SHA256:                           b3ba4ed848c9d01a9c1232efa8fa97b46e80bf61185c151f2f6acde6440a4f94
fixed outcomes:                       17 / 17 MATCH
tests:                                11 / 27 / 930 passed
```

### Adapter

```text
PR / source / merge:                  #133 / 5939f152180fbc6ce9a638eeca670b34e1a6650f / e97be21de9b6cc62f527548e1047bc9d4ad759c1
run / job / artifact:                 31073576151 / 92526482937 / 8958246394
ZIP SHA256:                           b2b5b0ba68f58f72538c98a4570756360c5e8e3be87d3afdd797064464cf6aa2
internal manifest:                    12 / 12 verified
final-head workflows:                 16 / 16 SUCCESS
tests:                                11 / 38 / 941 passed
skips / failures / errors:            0 / 0 / 0
```

## 6. U3 B1 quantitative register

| ID | Quantity | Value | Source | Allowed use |
|---|---|---:|---|---|
| B1-Q01 | upstream pressure | `1.0 MPa` | contract | fixed benchmark condition |
| B1-Q02 | upstream temperature | `320 K` | contract | fixed benchmark condition |
| B1-Q03 | critical pressure ratio | `0.5468849014513074` | critical_state_summary.json | locked state family only |
| B1-Q04 | critical pressure | `546884.9014513075 Pa` | critical_state_summary.json | locked state family only |
| B1-Q05 | critical temperature | `278.641212617351 K` | critical_state_summary.json | locked state family only |
| B1-Q06 | ideal critical mass flux | `2757.298423561355 kg/(m² s)` | critical_state_summary.json | component result |
| B1-Q07 | effective flux, Cd=0.4 | `1102.919369424542 kg/(m² s)` | critical_state_summary.json | fixed scaling case |
| B1-Q08 | effective flux, Cd=0.8 | `2205.838738849084 kg/(m² s)` | critical_state_summary.json | fixed scaling case |
| B1-Q09 | case count | `17` | summary.json | fixed matrix |
| B1-Q10 | comparison count / pass | `77 / 77` | summary.json | parity result |
| B1-Q11 | area scaling ratio | `2.0` | summary.json | fixed cases only |
| B1-Q12 | Cd scaling ratio | `2.0` | summary.json | fixed cases only |
| B1-Q13 | plateau relative difference | `0.0` | summary.json | fixed plateau pair |

## 7. B0 limiting comparison

| Measure | Relative error | Locked tolerance | Result |
|---|---:|---:|---|
| mass flow | `0.0001972791257517814` | `0.01` | PASS |
| effective velocity | `6.571376381353641e-05` | `0.01` | PASS |
| momentum stream | `0.0001315783258920566` | `0.02` | PASS |
| energy transfer | `0.000197279125751925` | `0.01` | PASS |

## 8. Independent-path register

```text
adapter imports Reference module:      false
shared property-path helper:           false
shared critical-search helper:         false
shared refinement helper:              false
shared transfer helper:                false
Reference reconstruction:              pinned source SHA
```

## 9. Final claim audit

True may be stated:

```text
Gate_9_execution_complete
crossing_depth_CFL_sensitivity_characterized
u3_component_benchmark_accepted
u3_b1_component_benchmark_accepted
```

Must remain false:

```text
crossing_depth_root_cause_approved
CFL_independent_crossing_verified
mesh_independent_crossing_verified
phase_chatter_root_cause_approved
physical_discharge_boundary_approved
two_phase_critical_discharge_accuracy_approved
integrated_blowdown_model_approved
physical_validation
design_use_acceptance
production_hem_activation_approved
```

## 10. Evidence gaps before later chapters are finalized

1. FVM-face static pressure force and sign contract。
2. finite-pipe inventory and cumulative discharge closure。
3. reflected pressure-wave reference and tolerance。
4. single-phase coupled stability matrix。
5. two-phase choking contract only after items 1–4。
6. experimental / field validation plan and data authority。
