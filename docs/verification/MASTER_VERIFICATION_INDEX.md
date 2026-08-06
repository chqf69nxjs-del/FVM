# MASTER VERIFICATION INDEX

## Record policy

Detailed historical records are preserved in:

- [`archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md`](archive/MASTER_VERIFICATION_INDEX_through_v013_reference_core.md)
- [`archive/MASTER_VERIFICATION_INDEX_before_u3_b1_central_sync.md`](archive/MASTER_VERIFICATION_INDEX_before_u3_b1_central_sync.md)

このファイルは、現在のauthoritative stateと主要closeoutへの索引を保持する。個別Gateの詳細値は、各closeout recordとArtifactをsource of truthとする。

## Current state — 2026-08-06

```text
Stage 1–6:                              COMPLETE
Stage 7:                                IN_PROGRESS
recorded substantive main:              e97be21de9b6cc62f527548e1047bc9d4ad759c1
Gate 3–9 execution:                     COMPLETE
Gate 9 crossing-depth diagnosis:        CHARACTERIZED / ROOT CAUSE NOT APPROVED
Application Track A1:                   COMPLETE
U3 B0:                                  COMPLETE / ACCEPTED
U3 B1:                                  COMPLETE / ACCEPTED
next controlled work:                   SINGLE-PHASE FVM FACE MAPPING + FINITE-PIPE COUPLING CONTRACT
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

## Current approval flags

```text
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true
u3_component_benchmark_accepted = true
u3_b1_component_benchmark_accepted = true

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
single-phase discharge component
→ static-pressure-force contract
→ FVM boundary-face mapping
→ finite-pipe coupling
→ pipe inventory / cumulative discharge closure
→ reflected pressure-wave verification
→ numerical-stability and guard matrix
```

Two-phase critical discharge is explicitly deferred until this single-phase coupling layer is complete.
