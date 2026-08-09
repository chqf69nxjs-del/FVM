# Stage 7 Current Gate Snapshot

## Status — 2026-08-09

```text
Stage 1–6:                              COMPLETE
Stage 7:                                IN_PROGRESS
recorded substantive main:              615139825247953897bbcbc4e379d4a4a46a4c5a
Gate 3–9 execution:                     COMPLETE
Gate 9 crossing candidate time/position: COMPARATIVELY_STABLE_ACROSS_FIXED_CFL
Gate 9 crossing depth:                  CFL_SENSITIVE / NON_MONOTONE
crossing-depth root cause:              NOT APPROVED
phase chatter diagnosis:                COMPLETE; root cause NOT APPROVED
Application Track A1:                   COMPLETE
selected first pilot:                   U3 pipeline depressurization / blowdown
U3 B0 component benchmark:              COMPLETE / ACCEPTED; Issue #109 CLOSED
U3 B1 component benchmark:              COMPLETE / ACCEPTED; Issue #127 CLOSED
U3 B2 contract:                         LOCKED; PR #136 MERGED
U3 B2 independent Reference:            IMPLEMENTED; PR #138 MERGED
U3 B2 FVM Adapter:                      IMPLEMENTED / FACE-AND-ONE-STEP VERIFIED; PR #144 MERGED
active primary implementation:          B2 finite-pipe single-phase authoritative execution
active documentation track:             technical report workspace v0.4; B2 v0.5 sync deferred
physical validation:                    NOT ESTABLISHED
design-use acceptance:                  NOT ESTABLISHED
production HEM activation:              NOT APPROVED
```

Primary closeout／current records：

- [`stage7_gate9_closeout.md`](stage7_gate9_closeout.md)
- [`stage7_u3_b0_closeout.md`](stage7_u3_b0_closeout.md)
- [`stage7_u3_b1_closeout.md`](stage7_u3_b1_closeout.md)
- [`stage7_u3_b2_fvm_discharge_coupling_contract_v1.json`](stage7_u3_b2_fvm_discharge_coupling_contract_v1.json)
- [`stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1.json`](stage7_u3_b2_fvm_discharge_coupling_event_provenance_contract_v1.json)
- [`stage7_u3_b2_independent_reference.md`](stage7_u3_b2_independent_reference.md)
- [`stage7_u3_b2_fvm_discharge_adapter.md`](stage7_u3_b2_fvm_discharge_adapter.md)

## Project-level current conclusion

現在のverification evidenceは、次を支持する。

- pure-CO₂ HEMの段階的software verification path。
- 固定条件における液相からopen-two-phaseへのraw crossingとquality projection。
- fixed mesh / three-CFL系列での候補時刻・位置の比較的安定性。
- crossing depthのCFL依存性と非単調性。
- localized phase chatterのevent-aligned診断。
- U3 B0のsubcooled-liquid limiting component benchmark。
- U3 B1のsingle-phase compressible / critical-state component benchmark。
- B0およびB1における独立Reference–Adapter parity、明示Guard、Artifact traceability。
- U3 B2におけるdirect external-face flux override、static-pressure-force decomposition、one-step balance、inventory ledger、linear-acoustic arrival targetのlocked contract。
- 将来のB2 AdapterとB2-specific helperを共有しない独立Reference、26ケース、7 Guard、Artifact／Git／runtime provenance。
- production FVM側のB2 discharge-face Adapter、13 face rows、52 / 52 flux parity、actual 32-cell one-step、7 Guard atomicity、Artifact／Git／runtime provenance。

一方、次は成立していない。

- crossing depthのroot-cause approval。
- mesh／CFL-independent two-phase solution。
- phase chatter root causeまたはmitigation authorization。
- finite-pipe discharge coupling、inventory closure、rarefaction event comparison。
- two-phase choking、non-equilibrium flashing。
- friction、gravity、wall heat transfer、receiver dynamics、solid CO₂。
- physical validation、design use、production activation。

## Gate 9 authoritative closeout

```text
D5 PR / source head:                   #121 / 45894a3fbe8c176c8435517c6204d94359dccccc
D5 workflow / artifact:                30805641241 / 8855725551
D5 artifact ZIP SHA256:                6b4f8f8076d9e7b61d4edb91c2653b2a010a05ee231c45b4c61dae9da6216850

D6 PR / source head:                   #122 / b90aa04ca3e1d8f2958f6a700c4ae73917ce39c8
D6 main merge SHA:                     5f0099101cbc9e9694297394a4c424904260ba94
D6 workflow / artifact:                30860513453 / 8875962770
D6 artifact ZIP SHA256:                b0c4b490eedeb7332659051d13cc1e108ef08dfd381eec9fbf63773c4e4aa088
D6 dedicated / related / full:         6 / 52 / 903 passed
skips / failures / errors:             0 / 0 / 0
```

```text
D6_temporal_correlation_classification_complete = true
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true
crossing_depth_root_cause_approved = false
```

## U3 B0 authoritative closeout

```text
Reference PR / merge:                  #124 / b4442d3df1a7517539520f79d82b85ef1c5aaec0
Reference workflow / artifact:         30898882922 / 8890056064
Reference ZIP SHA256:                  7005055beb8b0722dd035f37c0fa6d10f46ddd121d6ead5906a8d941fb6c23a6
Adapter PR / merge:                    #125 / 3937a276f8fefb62f297caa0e679660ec0d4c421
Adapter workflow / artifact:           30954035596 / 8912067053
Adapter ZIP SHA256:                    4d7848ad06afd4765f37e102d155bc73df5663b3efb47a77513aa61410f6d7b2
fixed cases / comparisons:             10 / 30
comparison passes:                     30 / 30
```

## U3 B1 authoritative closeout

```text
Reference PR / source / merge:         #131 / c7c25efae0e53a8b5f5ed164f9135238c6e005e0 / fa6c0ba14eb15dae482ee7766d03f7e1fca3574f
Reference workflow / artifact:         31051697864 / 8951665941
Reference ZIP SHA256:                  b3ba4ed848c9d01a9c1232efa8fa97b46e80bf61185c151f2f6acde6440a4f94
Reference dedicated / related / full:  11 / 27 / 930 passed

Adapter PR / source / merge:           #133 / 5939f152180fbc6ce9a638eeca670b34e1a6650f / e97be21de9b6cc62f527548e1047bc9d4ad759c1
Adapter workflow / artifact:           31073576151 / 8958246394
Adapter ZIP SHA256:                    b2b5b0ba68f58f72538c98a4570756360c5e8e3be87d3afdd797064464cf6aa2
Adapter dedicated / related / full:    11 / 38 / 941 passed
skips / failures / errors:             0 / 0 / 0
final-head workflows:                  16 / 16 SUCCESS
```

```text
physical / guard / total cases:        12 / 5 / 17
flux-transfer / critical comparisons:  68 / 9
comparison passes:                     77 / 77
critical pressure ratio:               0.5468849014513074
critical pressure:                     546884.9014513075 Pa
ideal critical mass flux:              2757.298423561355 kg/(m^2 s)
```

## U3 B2 contract, independent Reference, and Adapter

```text
Contract PR / source / merge:          #136 / 75661d9464ea079203b97e8274321d7d7ab2b9c1 / cffc32c257f58942e602614d69b6dad49bd1add8
Contract workflow / artifact:          31162802612 / 8989104336
Contract ZIP SHA256:                   3f6592f7a68a8c67aa76a19c8404434e990692561a3aeb3f10f6f4b80c13d75a
Contract dedicated / related / full:   11 / 16 / 950 passed

Reference PR / source / merge:         #138 / 0e2c8188961175b3c2cd56836296e713735bf8d9 / 4a70a831bb317ea70218e93801c469a12d7e046e
Reference workflow / job:              31203989733 / 92950477552
Reference artifact:                    9007750537
Reference ZIP SHA256:                  1816e60920052391cb9ffde9242597b56571c9ed113c60ece8aa9f32cdb8c7cd
Reference dedicated / related / full:  10 / 37 / 960 passed
skips / failures / errors:             0 / 0 / 0
```

```text
physical / guard / total cases:        19 / 7 / 26
face / one-step prerequisite rows:     13
inventory ledgers / rows:              3 / 12
acoustic rows:                         9
all face outcomes match:               true
all guard outcomes match:              true
all locked checks pass:                true
```

```text
maximum mass residual:                 2.7755575615628914e-17 kg
maximum energy residual:               3.637978807091713e-12 J
maximum momentum residual:             2.31239994600424e-19 kg m/s
maximum pressure decomposition residual: 1.1641532182693481e-10 Pa
```

B2 Referenceは比較targetを固定したものであり、production FVM Adapter、finite-pipe coupled result、物理精度または設計利用を承認しない。

### Production FVM Adapter

```text
Adapter PR / source / merge:            #144 / 732b7259ac3738c47f7eb7cbd23d8e49195a0d7b / 615139825247953897bbcbc4e379d4a4a46a4c5a
Adapter workflow / job:                 31305482286 / 93225055346
Adapter artifact:                       9037246372
Adapter ZIP SHA256:                     6315461ba4f0fb69d9f001014a3d38046f108fea1a7a87b979a2c27ac2328378
Adapter dedicated / related / full:     11 / 57 / 971 passed
JUnit skips / failures / errors:        0 / 0 / 0
pytest deselected related / full:       2 / 4
```

```text
face rows:                              13
conserved-flux comparisons:            52
comparison passes:                     52 / 52
actual FvmSolver one-step:              PASS
Guard outcome / atomicity rows:         7 / 7 PASS
all locked Adapter checks:              true
external Artifact manifest audit:      15 / 15 verified; 0 mismatches
```

B2 Adapter authorityは、single-phase direct external-face mappingとactual one-step conservative couplingをVerificationした。finite-pipe coupled response、inventory／acoustic closure、mesh／CFL characterization、物理精度または設計利用は承認しない。

## Active next controlled work

### Primary — B2 finite-pipe authoritative execution

production FVM Adapterのface parity、actual one-step conservative parity、および7 Guard atomicityはPR #144で完了した。次のcontrolled incrementは、mainへmerge済みのAdapterを用いるfinite-pipe single-phase executionである。

```text
LIQUID_SMALL_DROP
→ GAS_UNCHOKED
→ GAS_CHOKED
→ mass / energy inventory closure
→ momentum impulse closure
→ direct rarefaction / rigid-wall reflection
→ fixed mesh / CFL characterization
→ B2 closeout
```

finite-pipe結果を見る前に、実行matrix、probe、ledger、event、許容差およびprovenanceを既存locked contractどおり保持する。

### Subsequent finite-pipe matrix

```text
LIQUID_SMALL_DROP
GAS_UNCHOKED
GAS_CHOKED
mesh: 16 / 32 / 64
CFL: 0.10 / 0.05 / 0.025
```

確認対象はmass／energy inventory、momentum impulse、direct rarefaction、rigid-wall reflection、およびmesh／CFL characterizationである。B2 closeout前にmesh／CFL independenceを主張しない。

### Parallel specification work

```text
gravity/elevation benchmark for static head and high-point pressure minima
prescribed pump-head decay for negative-pressure wave propagation
```

これらは仕様・簡略verificationを進められるが、high-point flashing design use、rotating-inertia pump model、reverse-flow/turbine region、physical validationを承認しない。

## Approval boundary

```text
application_specification_complete = true
real_problem_pilot_selected = true
Gate_8_execution_complete = true
Gate_9_execution_complete = true
crossing_depth_CFL_sensitivity_characterized = true
u3_b0_contract_locked = true
u3_b0_reference_implemented = true
u3_b0_adapter_implemented = true
u3_b0_component_benchmark_execution_complete = true
u3_component_benchmark_accepted = true
u3_b1_contract_locked = true
u3_b1_reference_implemented = true
u3_b1_adapter_implemented = true
u3_b1_component_benchmark_execution_complete = true
u3_b1_component_benchmark_accepted = true
u3_b2_contract_locked = true
u3_b2_reference_implemented = true

u3_b2_fvm_adapter_implemented = true
u3_b2_finite_pipe_execution_complete = false
u3_b2_verification_benchmark_accepted = false
single_phase_fvm_discharge_mapping_verified = true
single_phase_finite_pipe_coupling_verified = false
crossing_depth_root_cause_approved = false
CFL_independent_crossing_verified = false
mesh_independent_crossing_verified = false
post_crossing_propagation_approved = false
phase_chatter_root_cause_approved = false
chatter_mitigation_authorized = false
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
high_point_flashing_design_use_approved = false
pump_trip_design_use_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```