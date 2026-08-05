# Stage 7 U3 B0 — Verification-only adapter comparison

## Status

```text
execution:                            COMPLETE
PR:                                   #125 / MERGED
source head SHA:                      42f9bd8384ebc06604924fc34ba05b45813e6b48
main merge SHA:                       3937a276f8fefb62f297caa0e679660ec0d4c421
u3_b0_adapter_implemented:            true
u3_b0_component_benchmark_complete:   true
u3_component_benchmark_accepted:      true
```

## 目的

U3 B0のlocked contractに対し、独立referenceとhelperを共有しないverification-only component adapterを実装し、authoritative reference artifactの固定10ケースと比較した。

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

固定10ケースについて次を比較した。

```text
formal outcome: exact match
mass transfer: locked absolute + relative tolerance
momentum stream transfer: locked absolute + relative tolerance
energy transfer: locked absolute + relative tolerance
```

合計は`10 cases × 3 measures = 30 comparisons`である。

## Authoritative result

```text
workflow run:                       30954035596
artifact ID:                        8912067053
artifact ZIP SHA256:                4d7848ad06afd4765f37e102d155bc73df5663b3efb47a77513aa61410f6d7b2
case count:                         10
success / guard:                     7 / 3
comparison count / pass:            30 / 30
formal outcomes match:              true
all transfer comparisons pass:      true
exact-zero identities retained:     true
```

Tests:

```text
dedicated:          7 passed
related:           13 passed
full repository:  916 passed
skips:               0
failures:            0
errors:              0
```

All 15 workflows triggered on the final head completed successfully.

## CI isolation

Reference-artifact-backed tests are marked explicitly.

```text
Adapter authoritative workflow:
  artifact required
  → all 916 tests executed

Unrelated workflows:
  artifact not downloaded
  → two tests deselected, not skipped
  → JUnit skipped count remains zero
```

This prevents irrelevant workflows from depending on the B0 artifact while retaining mandatory artifact-backed execution in the authoritative workflow.

## Accepted completion boundary

```text
u3_b0_contract_locked = true
u3_b0_reference_implemented = true
u3_b0_adapter_implemented = true
u3_b0_component_benchmark_execution_complete = true
u3_component_benchmark_accepted = true
```

## Approval boundary retained

```text
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

The consolidated authority and next work are recorded in [`stage7_u3_b0_closeout.md`](stage7_u3_b0_closeout.md).
