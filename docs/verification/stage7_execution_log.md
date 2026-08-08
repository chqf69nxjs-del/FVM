# Stage 7 Execution Log

## Record policy

Earlier execution detail is preserved in:

- [`archive/stage7_execution_log_through_v013_reference_core.md`](archive/stage7_execution_log_through_v013_reference_core.md)
- [`archive/stage7_execution_log_before_u3_b1_central_sync.md`](archive/stage7_execution_log_before_u3_b1_central_sync.md)

このファイルは、現在のcloseoutに関係する実行履歴を簡潔に保持する。

## 2026-08-09 — U3 B2 Independent Reference final audit and merge

### PR #138 — final state audit

```text
state before merge:               OPEN / ready / mergeable
expected head SHA:                0e2c8188961175b3c2cd56836296e713735bf8d9
base SHA:                         cffc32c257f58942e602614d69b6dad49bd1add8
changed files:                    5
production solver changes:        0
future B2 Adapter changes:        0
unresolved review threads:        0
blocking findings:                0
```

対象は次の5 pathに限定した。

```text
.github/workflows/stage7-u3-b2-independent-reference.yml
docs/verification/stage7_u3_b2_independent_reference.md
src/liquid_gas_transient/u3_b2_fvm_discharge_reference.py
src/liquid_gas_transient/u3_b2_fvm_discharge_reference_authoritative.py
tests/test_stage7_u3_b2_fvm_discharge_reference.py
```

### Historical failed authority and correction boundary

最初のexact-source authorityはB2-02 exact wall identityで停止した。

```text
superseded source:                e0bf39185e5096a9f2838688efe03e14131b24cc
failed run / job:                 31169594679 / 92839021237
failed checks:                    face_formal_outcomes
                                  B2-02_ZERO_DROP_LIQUID_WALL_IDENTITY_exact_wall_identity
```

原因は、B2-02がadjacent-cell static coordinatesで`u_i = 0`、`p_b = p_i`をexact identityとする一方、immutable B1 componentがreconstructed stagnation pressure `p0_i`とのbitwise equalityを保持するためであった。CoolProp state-pair round tripの浮動表現差により、raw B1が微小なunchoked streamを返した。

修正はlocked B2-02 case identity、locked pressure／opening／Cd、exact-zero adjacent velocity、raw B1 successful outcomeに限定したB2 face-layer canonicalizationとした。raw B1 outcomeとpressure-coordinate differenceはprovenanceへ残した。

```text
B1 equation / exact predicate:    unchanged
B2 contract:                      unchanged
accepted tolerances:              unchanged
other 25 case conditions:         unchanged
raw B1 Guard disposition:         unchanged / never promoted
```

failed runはhistorical evidenceとして保持し、authorityには使用しない。

### Authoritative Reference execution

```text
workflow:                         Stage 7 U3 B2 Independent Reference
run ID:                           31203989733
job ID:                           92950477552
source SHA:                       0e2c8188961175b3c2cd56836296e713735bf8d9
status:                           SUCCESS
artifact ID:                      9007750537
artifact name:                    stage7-u3-b2-reference-31203989733
artifact size:                    306728 bytes
artifact ZIP SHA256:              1816e60920052391cb9ffde9242597b56571c9ed113c60ece8aa9f32cdb8c7cd
internal SHA256 manifest:         17 / 17 verified
```

```text
physical / guard / total cases:   19 / 7 / 26
face/reference rows:              13
inventory ledgers / rows:         3 / 12
acoustic rows:                     9
all face outcomes match:          true
all guard outcomes match:         true
all locked checks pass:           true
```

```text
Reference dedicated:             10 passed
related U3:                       37 passed
full repository:                960 passed
skips / failures / errors:         0 / 0 / 0
pytest deselected:                 4
```

```text
maximum mass residual:            2.7755575615628914e-17 kg
maximum energy residual:          3.637978807091713e-12 J
maximum momentum residual:        2.31239994600424e-19 kg m/s
maximum pressure residual:        1.1641532182693481e-10 Pa
```

### Merge

PR #138はexpected head SHA `0e2c8188961175b3c2cd56836296e713735bf8d9`を指定してmergeした。

```text
main merge SHA:                   4a70a831bb317ea70218e93801c469a12d7e046e
merge method:                     merge commit
```

これにより、mainのformal stateとして次をtrueへ昇格できる。

```text
u3_b2_contract_locked = true
u3_b2_reference_implemented = true
```

Adapter、finite-pipe execution、B2 acceptance、物理Validation、設計利用はfalseのまま維持する。

## 2026-08-09 — U3 B2 central-record synchronization

次をReference merge時点へ同期する。

```text
stage7_current_gate_snapshot.md
MASTER_VERIFICATION_INDEX.md
stage7_execution_log.md
Issue #135 progress record
```

Technical ReportはReference単独では細分更新せず、Adapterおよびfinite-pipe couplingがまとまった時点でv0.5相当として同期する。

次のcontrolled incrementは、Referenceをimportしないproduction-side B2 FVM discharge-face Adapterである。verificationはface parity、one-step parity、finite-pipe executionの順とする。

## 2026-08-06 — U3 B1 Adapter final audit and merge

### PR #133 — final state audit

```text
state before merge:               OPEN / ready / mergeable
head SHA:                         5939f152180fbc6ce9a638eeca670b34e1a6650f
changed files:                    6
review findings addressed:        5 / 5
unresolved review threads:        0
final-head workflows:             16 / 16 SUCCESS
```

### Authoritative Adapter execution

```text
workflow:                         Stage 7 U3 B1 Adapter Comparison
run ID:                           31073576151
job ID:                           92526482937
status:                           SUCCESS
artifact ID:                      8958246394
artifact name:                    stage7-u3-b1-adapter-31073576151
artifact ZIP SHA256:              b2b5b0ba68f58f72538c98a4570756360c5e8e3be87d3afdd797064464cf6aa2
internal SHA256 manifest:         12 / 12 verified
```

```text
physical / guard / total cases:   12 / 5 / 17
flux-transfer comparisons:        68
critical-pressure comparisons:     9
total comparison passes:          77 / 77
formal outcomes:                  all match
```

```text
Adapter dedicated:                11 passed
related U3:                       38 passed
full repository:                941 passed
skips / failures / errors:         0 / 0 / 0
pytest deselected:                 2
```

### Merge

PR #133はexpected head SHA `5939f152180fbc6ce9a638eeca670b34e1a6650f`を指定してmergeした。

```text
main merge SHA:                   e97be21de9b6cc62f527548e1047bc9d4ad759c1
merge method:                     merge commit
```

## 2026-08-06 — Issue #127 formal closeout

Issue #127へ次を記録した。

- PR #131 Reference authority。
- PR #133 Adapter authority。
- authoritative run / Artifact / ZIP SHA256。
- 17ケース、77比較、テスト結果。
- B1でtrueとなる5つのflag。
- falseのまま維持する物理・設計・production flag。

その後、Issue #127を`completed`としてcloseした。

## 2026-08-06 — central documentation synchronization

次を同期対象として固定した。

```text
stage7_u3_b1_closeout.md
stage7_current_gate_snapshot.md
MASTER_VERIFICATION_INDEX.md
stage7_execution_log.md
technical-report README / contract / evidence matrix
figure-table register / skeleton / chapter 12 / figures
```

旧central index/logはarchive pathへblob identityを保ったまま移し、現行ファイルはB1 closeout時点のcurrent indexへ整理する。

## End-of-entry approval boundary

```text
u3_b1_contract_locked = true
u3_b1_reference_implemented = true
u3_b1_adapter_implemented = true
u3_b1_component_benchmark_execution_complete = true
u3_b1_component_benchmark_accepted = true
u3_b2_contract_locked = true
u3_b2_reference_implemented = true

u3_b2_fvm_adapter_implemented = false
u3_b2_finite_pipe_execution_complete = false
u3_b2_verification_benchmark_accepted = false
single_phase_fvm_discharge_mapping_verified = false
single_phase_finite_pipe_coupling_verified = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
