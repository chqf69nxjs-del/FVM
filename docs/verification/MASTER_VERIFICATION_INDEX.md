# MASTER VERIFICATION INDEX

## Record policy

Detailed historical records are preserved in:

- [`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md)
- [`archive/MASTER_VERIFICATION_INDEX_before_u3_b1_central_sync.md`](archive/MASTER_VERIFICATION_INDEX_before_u3_b1_central_sync.md)

このファイルは、現在のauthoritative stateと主要closeoutへの索引を保持する。個別Gateの詳細値は、各closeout／current recordとArtifactをsource of truthとする。

## Current state — 2026-08-09

```text
Stage 1–6:                              COMPLETE
Stage 7:                                IN_PROGRESS
recorded substantive main:              4a70a831bb317ea70218e93801c469a12d7e046e
Gate 3–9 execution:                     COMPLETE
Gate 9 crossing-depth diagnosis:        CHARACTERIZED / ROOT CAUSE NOT APPROVED
Application Track A1:                   COMPLETE
U3 B0:                                  COMPLETE / ACCEPTED
U3 B1:                                  COMPLETE / ACCEPTED
U3 B2 contract:                         LOCKED
U3 B2 independent Reference:            IMPLEMENTED
U3 B2 FVM Adapter:                      NOT IMPLEMENTED
next controlled work:                   B2 FVM ADAPTER → FACE / ONE-STEP PARITY
physical validation:                    NOT ESTABLISHED
design-use acceptance:                  NOT ESTABLISHED
production HEM activation:              NOT APPROVED
```

## Authoritative milestone index

| Milestone | Status | Primary record | Authority |
|---|---|---|---|
| Gate 3 cross-runtime | `NUMERICALLY_EQUIVALENT` | Gate 3 records | PR #91 |
| Gate 4 low-CFL | `CFL_SENSITIVITY_OBSERVED` | Gate 4 records | PR #90 |
| Gate 5 acoustic review | `COMPLETE; approval withheld` | `stage7_gate5_closeout.md` | PR #96 |
| Gate 6 post-crossing propagation | `COMPLETE; approval withheld` | `stage7_gate6_closeout.md` | PR #99 |
| Gate 7 chatter diagnosis | `COMPLETE; root cause false` | `stage7_gate7_closeout.md` | PR #102 |
| Gate 8 three-CFL integration | `COMPLETE` | `stage7_gate8_closeout.md` | PR #107/#108 |
| Gate 9 temporal/correlation diagnosis | `COMPLETE` | `stage7_gate9_closeout.md` | PR #121/#122 |
| U3 B0 liquid limiting component | `COMPLETE / ACCEPTED` | `stage7_u3_b0_closeout.md` | PR #124/#125; Issue #109 |
| U3 B1 compressible critical component | `COMPLETE / ACCEPTED` | `stage7_u3_b1_closeout.md` | PR #131/#133; Issue #127 |
| U3 B2 FVM coupling contract | `LOCKED` | `stage7_u3_b2_fvm_discharge_coupling_contract_v1.json` | PR #136; Issue #135 |
| U3 B2 independent Reference | `IMPLEMENTED; Adapter pending` | `stage7_u3_b2_independent_reference.md` | PR #138; Issue #135 |

## Gate 9 retained disposition

```text
candidate time and position:            comparatively stable across fixed CFL
crossing depth:                         CFL-sensitive and non-monotone
accepted / guard classification:        changes across fixed CFL sequence
crossing-depth root cause:               NOT APPROVED
phase-chatter root cause:                NOT APPROVED
```

## U3 B0 retained result

```text
cases:                                  10
success / guard:                        7 / 3
mass-momentum-energy comparisons:       30
passes:                                 30 / 30
exact-zero identities:                  retained
```

## U3 B1 retained result

```text
Reference PR / merge:                   #131 / fa6c0ba14eb15dae482ee7766d03f7e1fca3574f
Adapter PR / merge:                     #133 / e97be21de9b6cc62f527548e1047bc9d4ad759c1
Adapter run / artifact:                 31073576151 / 8958246394
Artifact ZIP SHA256:                    b2b5b0ba68f58f72538c98a4570756360c5e8e3be87d3afdd797064464cf6aa2
cases:                                  17
physical / guard:                       12 / 5
comparisons:                            77
passes:                                 77 / 77
critical pressure ratio:                0.5468849014513074
critical pressure:                      546884.9014513075 Pa
ideal critical mass flux:               2757.298423561355 kg/(m^2 s)
```

## U3 B2 retained result

### Locked contract

```text
Contract PR / merge:                    #136 / cffc32c257f58942e602614d69b6dad49bd1add8
Contract source:                        75661d9464ea079203b97e8274321d7d7ab2b9c1
Contract run / artifact:                31162802612 / 8989104336
Artifact ZIP SHA256:                    3f6592f7a68a8c67aa76a19c8404434e990692561a3aeb3f10f6f4b80c13d75a
parent contract SHA256:                 de7afe696c04cd9306eb7de304d2ffe1723d4d967637e5f4daeb7f3cde412a72
event/provenance SHA256:                dfa4908741609494f45c3845122d09f1107af299e50ecd61da6bdabf6507fc30
```

### Independent Reference

```text
Reference PR / merge:                   #138 / 4a70a831bb317ea70218e93801c469a12d7e046e
Reference source:                       0e2c8188961175b3c2cd56836296e713735bf8d9
Reference run / job:                    31203989733 / 92950477552
Reference artifact:                     9007750537
Artifact ZIP SHA256:                    1816e60920052391cb9ffde9242597b56571c9ed113c60ece8aa9f32cdb8c7cd
cases:                                  26
physical / guard:                       19 / 7
face rows / ledgers / acoustic rows:    13 / 3 / 9
locked checks:                          all passed
Dedicated / related / full:             10 / 37 / 960 passed
skips / failures / errors:              0 / 0 / 0
```

```text
maximum mass residual:                  2.7755575615628914e-17 kg
maximum energy residual:                3.637978807091713e-12 J
maximum momentum residual:              2.31239994600424e-19 kg m/s
maximum pressure decomposition residual: 1.1641532182693481e-10 Pa
```

このReferenceはdirect external-face flux mapping、one-step balance、inventory／impulse ledger、requested-probe acoustic targetを独立に固定した。production FVM Adapter、finite-pipe result、物理Validation、設計利用は未成立である。

## Current approval flags

```text
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true
u3_component_benchmark_accepted = true
u3_b1_component_benchmark_accepted = true
u3_b2_contract_locked = true
u3_b2_reference_implemented = true

u3_b2_fvm_adapter_implemented = false
u3_b2_finite_pipe_execution_complete = false
u3_b2_verification_benchmark_accepted = false
single_phase_fvm_discharge_mapping_verified = false
single_phase_finite_pipe_coupling_verified = false
crossing_depth_root_cause_approved = false
CFL_independent_crossing_verified = false
mesh_independent_crossing_verified = false
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

## Next controlled work

```text
accepted B1 component
→ independent production-side B2 FVM Adapter
→ face parity against Reference
→ one-step conservative parity
→ finite-pipe single-phase execution
→ mass / energy inventory and momentum-impulse closure
→ direct / reflected rarefaction comparison
→ fixed mesh / CFL characterization
→ B2 closeout
```

AdapterはB2 Reference moduleまたはB2-specific helperをimportしない。face／one-step parityを成立させる前にfinite-pipe acceptanceへ進まない。Two-phase critical dischargeは、このsingle-phase coupling layerがacceptedになるまで明示的に延期する。
