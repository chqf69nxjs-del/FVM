# Stage 7 U3 B2 single-phase finite-pipe baseline preflight

## Status

```text
IMPLEMENTATION PREFLIGHT ONLY
NO FORMAL FINITE-PIPE PROMOTION
```

## 目的

mainへ正式採用済みのU3 B2 discharge-face Adapterを実際の有限長FVM配管へ接続し、locked baselineの3系列を複数stepで実行できるproduction-side実行層を追加する。

```text
B2-10A LIQUID_SMALL_DROP
B2-10B GAS_UNCHOKED
B2-10C GAS_CHOKED
```

このincrementでは、次を確認する。

```text
accepted dtによる複数step更新
mass / energy inventory closure
left/right momentum impulse closure
right-face advective / open-pressure / closed-pressure decomposition
single-phase rho*xv exact-zero identity
LIQUID_SMALL_DROPのdirect / reflected rarefaction event
locked probe interpolation
```

## 固定条件

既存のlocked Contractおよびevent/provenance extensionを変更しない。

```text
pipe length: 1.0 m
pipe area: 1.0e-4 m^2
baseline cells / CFL: 32 / 0.10
left boundary: ReflectiveBoundary
right boundary: direct external-face Adapter
quadrature: exact accepted face transferによるleft-endpoint rule
liquid horizon: 2.0 L / c0
gas accepted-step caps: 32 / 16
```

Acoustic eventは、固定されたrequested probe、線形補間、expected-time window、minimum centered pressure slope、sign rule、およびarrival toleranceを使用する。結果を見てevent window、probe、toleranceまたはtie-breakを変更しない。

## Independence boundary

production-side finite-pipe moduleはU3 B2 Independent Referenceをimportしない。

```text
Reference:
locked expected arrival / ledger target

production finite-pipe runner:
actual FvmSolver execution、inventory、probe、event detection

later authoritative layer:
Referenceとproduction結果の比較のみ
```

## Preflight成果物

```text
summary.json
baseline_run_summary.csv
baseline_step_history.csv
baseline_probe_history.csv
baseline_acoustic_events.csv
benchmark_contract.json
event_provenance_contract.json
b1_component_contract.json
report.md
artifact_sha256.txt
```

## Claim boundary

本preflightが成功しても、以下はfalseのまま維持する。

```text
u3_b2_finite_pipe_execution_complete = false
single_phase_fvm_discharge_mapping_verified = true
single_phase_finite_pipe_coupling_verified = false
u3_b2_verification_benchmark_accepted = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

baseline preflight完了後、固定mesh / CFL matrix、正式Authority writer、full repository JUnit、Artifact provenanceを別incrementで追加する。
