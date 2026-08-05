# Stage 7 U3 B1 — Independent single-phase critical-state reference

## 目的

Issue #127で固定したB1 contractに対し、将来のadapterとhelperを共有しない独立Reference evaluatorを実装する。

この増分は、単相圧縮性流出について次を計算する。

```text
上流stagnation state
→ fixed-s0 isentropic candidate path
→ effective velocity / mass flux
→ interior critical-state search
→ unchoked / choked classification
→ mass / momentum-stream / enthalpy transfer
```

## 独立経路

Reference module：

```text
src/liquid_gas_transient/u3_b1_critical_state_reference.py
```

将来のB1 adapter moduleは未作成であり、本moduleはB0 reference / adapterの計算helperも使用しない。

## 固定式

候補圧力`p`について、

```text
s(p) = s0
head = h0 - h(p,s0)
u_ideal = sqrt(2*head)
u_eff = Cd*u_ideal
G_eff = rho(p,s0)*u_eff
m_dot = Aeff*G_eff
M_dot_stream = m_dot*u_eff
E_dot = m_dot*h0
```

を使用する。

Static pressure force、FVM face mapping、pipe couplingは含めない。

## Critical-state探索

`GAS_CRITICAL`状態について、固定4097点の圧力比走査を行う。

```text
pressure ratio: 1.00 → 0.05
spacing: uniform descending
argmax tie: highest pressure
required bracket: admissible neighbor on both sides
refinement: golden-section maximization
final pressure bracket width: <= 1 Pa
```

低圧側でCoolPropまたは単相scopeを外れた場合は最初の失敗を記録し、その手前までのadmissible pathを保持する。Critical maximumが両側のadmissible stateで挟めない場合は`CRITICAL_SEARCH_NOT_BRACKETED`とする。

## 固定17ケース

```text
physical cases: 12
guard cases:     5
```

確認対象：

- exact closed / zero-drop identities
- liquid small-drop B0 limiting behavior
- unchoked back-pressure ordering
- interior critical-state maximum
- below-critical mass-flow plateau
- area scaling
- Cd scaling
- critical pressureのCd独立性
- reverse pressure / invalid input / phase scope / kinetic-head / unbracketed-search guards

## Artifact

Reference実行は次を生成する。

```text
summary.json
benchmark_contract.json
candidate_states.csv
critical_state_summary.json
back_pressure_sweep.csv
b0_limiting_comparison.csv
scaling_checks.csv
guard_outcomes.csv
conservative_transfer_table.csv
mass_flux_vs_pressure.png
back_pressure_response.png
report.md
artifact_sha256.txt
```

CIはさらにdedicated / related / full-repository JUnitを添付する。

## 承認境界

この増分でtrue候補：

```text
u3_b1_contract_locked = true
u3_b1_reference_implemented = true
```

以下はfalseのまま維持する。

```text
u3_b1_adapter_implemented = false
u3_b1_component_benchmark_execution_complete = false
u3_b1_component_benchmark_accepted = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
