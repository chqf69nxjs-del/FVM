# Stage 7 U3 B1 — Verification adapter comparison

## Purpose

This increment implements a verification-only component adapter for the locked
U3 B1 single-phase critical-state contract and compares it with the immutable
authoritative independent-reference artifact.

The adapter does not import `u3_b1_critical_state_reference` and does not share
its property-path, critical-search, refinement, or conservative-transfer
helpers. It uses an independent low-level CoolProp state path and separately
implements the locked 4097-node pressure-ratio search and deterministic
refinement.

## Fixed comparison matrix

```text
physical cases:             12
guard cases:                 5
total cases:                17
transfer/flux comparisons:  68 = 17 × 4
critical-pressure rows:      9
total comparison rows:      77
```

Compared quantities are effective mass flux, outward mass transfer,
momentum-stream transfer, enthalpy transfer, and critical pressure where the
contract requires a critical-state search.

## Independence boundary

```text
adapter imports reference module:       false
shared critical-search helper:          false
shared property-path helper:             false
shared transfer-construction helper:     false
static pressure-force FVM mapping:       false
production FVM connection:               false
```

## Authoritative execution

The final source head, workflow run, immutable reference artifact provenance,
JUnit totals, and reference-adapter residual results are pinned in the pull
request after the authoritative workflow succeeds.

## Approval boundary

On successful authoritative execution this increment may establish:

```text
u3_b1_contract_locked = true
u3_b1_reference_implemented = true
u3_b1_adapter_implemented = true
u3_b1_component_benchmark_execution_complete = true
u3_b1_component_benchmark_accepted = true
```

The following remain false:

```text
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```


## Durable reference resolution

The comparison does not depend on the continued availability of a retention-limited
GitHub Actions artifact.  Each authoritative run resolves the immutable Reference
through the reviewed source commit and fixed runtime instead:

```text
reference_resolution_mode:  recomputed_from_pinned_source_sha
reference source SHA:        c7c25efae0e53a8b5f5ed164f9135238c6e005e0
Python:                      3.12.13
CoolProp:                    8.0.0
NumPy:                       2.5.1
Matplotlib:                  3.11.1
Pytest:                      9.1.1
```

The historical workflow run, Artifact ID, and ZIP SHA256 remain recorded as the
original authoritative evidence, but are not a runtime availability dependency.
The regenerated Reference is checked against the pinned source SHA, fixed outcomes,
locked checks, critical-state values, contract, and internal SHA256 manifest before
the Adapter is evaluated.
