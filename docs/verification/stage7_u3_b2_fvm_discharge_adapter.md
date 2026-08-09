# Stage 7 U3 B2 — FVM流出面Adapter

## 1. 現在の状態

```text
IMPLEMENTATION CANDIDATE
FACE / ONE-STEP AUTHORITY PENDING
FINITE-PIPE NOT EXECUTED
```

本incrementでは、accepted U3 B1単相流出componentを、一次元保存形FVM solverの右外部面へ接続する。対象はVerificationのみであり、物理的にValidation済みのCO2 blowdown boundaryを承認しない。

## 2. 固定済みauthority

```text
Issue: #135
B2 Contract: #136 / 75661d9464ea079203b97e8274321d7d7ab2b9c1 / cffc32c257f58942e602614d69b6dad49bd1add8
B2 Reference: #138 / 0e2c8188961175b3c2cd56836296e713735bf8d9 / 4a70a831bb317ea70218e93801c469a12d7e046e
accepted B1 Adapter source: 5939f152180fbc6ce9a638eeca670b34e1a6650f
Reference authority run / Artifact: 31203989733 / 9007750537
Reference ZIP SHA256: 1816e60920052391cb9ffde9242597b56571c9ed113c60ece8aa9f32cdb8c7cd
```

B1 equation、coefficient placement、critical-search rule、case condition、Guard disposition、accepted toleranceは変更しない。authority workflowは、現在のB1 Adapter file blobがaccepted source SHA上のblobと同一であることを要求する。

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

production側はCoolProp `AbstractState`の`Dmass / Umass`および`Hmass / Smass`経路を使用する。独立Referenceは別の`PropsSI`経路を維持する。

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

hookが`None`の場合は既存solver経路を保持する。候補時間刻みは、既存CFL、adjacent-cell質量・energyの10% removal limit、および`t_end - t`の最小値とする。trial拒否時は最大12回まで決定論的に半減し、全試行が失敗した場合は`BOUNDARY_UPDATE_POSITIVITY_FAILURE`を返す。失敗時はsolver state、time、step count、boundary budgetを変更しない。

`FvmSolver.run()`の履歴には、候補dtではなく`step()`が実際に採用したhalving後のdtを記録する。

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

discharge ghost primitiveは合成しない。advective momentum streamとstatic pressure forceは別々に追跡する。closed caseとlocked static-coordinate zero-drop caseでは、`F_right = [0, p_i, 0, 0]`をexactに保持する。

## 6. Face / one-step authority条件

正式workflowは、pinned sourceと同一の独立Referenceを再生成し、次を証明する。

```text
13 face rows
52 conserved-flux comparisons
1 actual 32-cell / CFL 0.10 FvmSolver step
7 Guard outcomes
maximum 12-halving atomic exhaustion
exact single-phase rho*xv = 0
accepted B1 Adapter source/blob identity
```

テストはdedicated Adapter、related U3、full repositoryの3層とし、CoolProp 8.0.0を固定導入したauthority環境ではJUnitのskip / failure / errorを`0 / 0 / 0`とする。CoolProp未導入環境ではCoolProp依存testだけを明示skipする。

保持Artifactには、summary、3 contract copies、runtime/Git provenance、face/one-step/Guard CSV、parity figure、report、3 JUnit、完全な内部SHA256 manifestを含める。

provenanceでは、analysis/checkout/Reference/accepted B1 Adapter/Adapterの各source SHA、B1 Adapter pinned/current blob identity、historical Reference Artifact ID/ZIP SHA256、contract source/artifact SHA256、runtime versions、workflow run identity、checkout cleanlinessを分離して保持する。

## 7. merge後の昇格候補

最終headに対するauthority SUCCESS、Artifact監査、review closeout、expected-head mergeの後に限り、次を昇格候補とする。

```text
u3_b2_fvm_adapter_implemented = true
single_phase_fvm_discharge_mapping_verified = true
```

## 8. 未承認の範囲

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

本incrementはfinite-pipe応答、inventory/acoustic closure、mesh/CFL characterization、物理精度、commercial-code agreement、実験Validation、design applicabilityまたはproduction readinessを承認しない。
