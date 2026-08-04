# Stage 7 U3 B0 — Verification-only adapter comparison

## 目的

U3 B0のlocked contractに対し、独立referenceとhelperを共有しないverification-only component adapterを実装し、authoritative reference artifactの固定10ケースと比較する。

```text
reference artifact ID:          8890056064
reference artifact ZIP SHA256:  7005055beb8b0722dd035f37c0fa6d10f46ddd121d6ead5906a8d941fb6c23a6
```

## Adapter境界

Adapterは次だけを返す。

```text
positive outward mass transfer
positive outward momentum stream transfer
positive outward enthalpy transfer
formal outcome
explicit guard category
```

次は含めない。

```text
static pressure-force mapping
production FVM boundary connection
reverse flow
compressible critical-state search
two-phase choking
receiver dynamics
physical validation
design use
```

## 独立性

`u3_b0_discharge_adapter.py`は`u3_b0_discharge_reference.py`をimportせず、reference helperを再利用しない。

Adapter側では、

```text
u_exit = Cd * sqrt(2*Delta_p/rho0)
m_dot = rho0 * Aeff * u_exit
M_dot_stream = m_dot * u_exit
E_dot = m_dot * h0
```

としてtransferを構築する。Reference側の演算順序とは分離されている。

## 比較契約

固定10ケースについて次を比較する。

```text
formal outcome: exact match
mass transfer: locked absolute + relative tolerance
momentum stream transfer: locked absolute + relative tolerance
energy transfer: locked absolute + relative tolerance
```

合計は`10 cases × 3 measures = 30 comparisons`である。

## 完了境界

Authoritative CIで全比較、dedicated、related、full repositoryがcleanの場合、次をtrueへできる。

```text
u3_b0_contract_locked = true
u3_b0_reference_implemented = true
u3_b0_adapter_implemented = true
u3_b0_component_benchmark_execution_complete = true
u3_component_benchmark_accepted = true
```

次はfalseのまま維持する。

```text
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
