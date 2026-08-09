# Stage 7 U3 B2 — FVM流出面Adapter

## 1. 現在の状態

```text
IMPLEMENTATION CANDIDATE
FACE / ONE-STEP AUTHORITY QUEUED
FINITE-PIPE NOT EXECUTED
```

本incrementでは、accepted U3 B1単相流出componentを、一次元保存形FVM solverの右外部面へ接続する。
対象はVerificationのみであり、物理的にValidation済みのCO₂ blowdown boundaryを承認しない。

## 2. 固定済みauthority

```text
Issue:
#135

B2 Contract PR / source / merge:
#136 / 75661d9464ea079203b97e8274321d7d7ab2b9c1 / cffc32c257f58942e602614d69b6dad49bd1add8

B2 Reference PR / source / merge:
#138 / 0e2c8188961175b3c2cd56836296e713735bf8d9 / 4a70a831bb317ea70218e93801c469a12d7e046e

accepted B1 Adapter source:
5939f152180fbc6ce9a638eeca670b34e1a6650f

Reference authority run / Artifact:
31203989733 / 9007750537

Reference Artifact ZIP SHA256:
1816e60920052391cb9ffde9242597b56571c9ed113c60ece8aa9f32cdb8c7cd
```

B1 equation、coefficient placement、critical-search rule、case condition、Guard disposition、accepted toleranceは変更しない。
authority workflowは、現在のB1 Adapter file blobがaccepted B1 Adapter source SHA上のblobと同一であることを要求する。

## 3. 実装独立性

```text
Adapter imports U3 B2 Reference module:       false
shared B2 face-mapping helper:                 false
shared B2 one-step helper:                     false
shared B2 inventory helper:                    false
shared B2 acoustic helper:                     false
accepted B1 Adapter reused as upstream law:    true
Reference used only as comparison target:      true
```

production側の物性経路は、adjacent static stateにCoolProp `AbstractState`の`Dmass / Umass`、stagnation stateに`Hmass / Smass`を使用する。
独立B2 Referenceは別実装である`PropsSI`経路を維持する。

## 4. Solverへの接続順序

```text
ghost-state Rusanov
→ internal-interface override
→ B2 right external-face override
→ trial conservative update
→ single-phase / positivity validation
→ accepted boundary budget
→ committed conservative state
```

optional hookが`None`の場合は、既存solver経路を保持する。

候補時間刻みは次で制限する。

```text
dt = min(
    existing CFL dt,
    boundary mass-removal dt,
    boundary energy-removal dt,
    t_end - t
)
```

質量とenergyのremovalは、accepted stepごとにadjacent-cell inventoryの10%以下とする。
trialが拒否された場合は、最大12回まで決定論的にdtを半減して再試行する。
全試行が失敗した場合は`BOUNDARY_UPDATE_POSITIVITY_FAILURE`を返し、boundary budget、solver state、solver time、step countをcommitしない。

`FvmSolver.run()`のdiagnostic historyには、候補dtではなく`step()`が実際に採用したhalving後のaccepted dtを記録する。

## 5. 右外部面への直接mapping

```text
A_open   = A_pipe * opening
A_closed = A_pipe - A_open

I_dot_total
  = m_dot_B1 * u_eff_B1
  + p_d * A_open
  + p_i * A_closed

F_right
  = [m_dot_B1 / A_pipe,
     I_dot_total / A_pipe,
     E_dot_B1 / A_pipe,
     0]
```

discharge ghost primitiveは合成しない。
advective momentum streamとstatic pressure forceは別々に追跡可能な状態を維持する。

## 6. Exact identityの境界

closed caseおよびlocked static-coordinate zero-drop caseでは、次をexactに保持する。

```text
F_right = [0, p_i, 0, 0] exact
```

B2-02 correctionの適用範囲は、次に限定する。

```text
locked case identityがexactに一致
nominal pressureがexactに一致
openingがexactに一致
discharge coefficientがexactに一致
adjacent velocityがexact zero
raw B1 outcomeがすでにsuccessful
```

raw B1 outcome、およびstatic pressure coordinateとstagnation pressure coordinateの差はprovenanceに保持する。
B1 equation、B1 exact predicate、B2 Contract、accepted toleranceは変更しない。

## 7. Face / one-step authority contract

専用workflowは、pinned SHA `0e2c818...`とsource identityが一致する独立Referenceを再生成し、次を証明しなければならない。

```text
13 face rows
52 conserved-flux comparisons
1 actual 32-cell / CFL 0.10 FvmSolver step
7 Guard outcomes
12-halving atomic exhaustion
exact single-phase rho*xv = 0
accepted B1 Adapter source/blob identity
```

必須test layerは次の3層とする。

```text
dedicated Adapter tests: exactly 11
related U3 tests
full-repository tests
JUnit skips / failures / errors = 0 / 0 / 0
```

CoolProp未導入環境ではCoolProp依存testだけを明示skipする。
一方、正式authority workflowはCoolProp 8.0.0を固定導入するため、authority JUnitではskipを認めない。

保持すべきEvidenceは次のとおりである。

```text
summary.json
runtime_and_git_provenance.json
benchmark_contract.json
event_provenance_contract.json
b1_component_contract.json
adapter_face_results.csv
reference_adapter_face_flux_comparison.csv
one_step_conservative_update_comparison.csv
guard_outcomes.csv
locked_checks.csv
reference_adapter_face_flux_parity.png
report.md
dedicated_junit.xml
related_junit.xml
full_repository_junit.xml
artifact_sha256.txt
```

provenance recordは、次をそれぞれ分離して保持しなければならない。

```text
analysis source Git SHA
checkout Git SHA
Reference source Git SHA
accepted B1 Adapter source Git SHA
accepted B1 Adapter pinned/current blob identity
Adapter source Git SHA
historical Reference Artifact ID and ZIP SHA256
parent B2 contract source and retained-artifact SHA256
B2 event/provenance contract source and retained-artifact SHA256
B1 component contract source and retained-artifact SHA256
Python / NumPy / Matplotlib / Pytest / CoolProp versions
workflow run ID and attempt
pre-execution and post-execution checkout state
```

`artifact_sha256.txt`は、自身を除くすべての保持Evidence fileを対象とする。

## 8. merge後の昇格候補

final headに対するauthoritative evidence、Artifact監査、review closeout、expected-head merge、central record synchronizationが完了した場合に限り、本incrementは次の昇格を支持できる。

```text
u3_b2_fvm_adapter_implemented = true
single_phase_fvm_discharge_mapping_verified = true
```

次はfalseのまま維持する。

```text
u3_b2_finite_pipe_execution_complete = false
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

本incrementから、mesh/CFL independence、finite-pipe response、inventory/acoustic closure、acoustic-arrival agreement、物理精度、commercial-code agreement、実験Validation、design applicability、production readinessを推定または承認しない。
