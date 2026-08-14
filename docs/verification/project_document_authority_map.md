# Project Document Authority Map

## 1. Purpose

This document identifies the role, authority, overlap, and update policy of the principal project documents.

It is an **index and governance map**, not a new physics specification, Verification result, Acceptance decision, or design-use approval.

The project purpose is defined as:

> Develop a practical analysis tool that can support bounded studies of transient pressure waves, depressurization, flashing, and liquid-to-two-phase behavior in finite-length liquid-CO₂ pipelines, with explicit applicability, limitations, fail-closed behavior, output authority, and reproducibility.

Complete explanation of the physical phenomena, comprehensive all-domain Verification, and full Physical Validation are not completion requirements for a Working Vertical Slice.

## 2. Branch-aware reading rule

Project records must distinguish between:

```text
formal state recorded on main
and
a newer development-branch state
```

A document dated before later branch work remains authoritative for the state it records, but it must not be silently treated as the latest development state.

At the time this map was created:

- `stage7_current_gate_snapshot.md`, `MASTER_VERIFICATION_INDEX.md`, and `stage7_execution_log.md` primarily represent the formally synchronized state recorded before the Working Tool v0-B A6/A7 closeout;
- branch `agent/u3-b2-a1-working-tool-v0-b` contains the later Working Tool v0-B closeout evidence;
- no branch-only result becomes a `main` formal state merely because it is linked from this map.

When reporting a status, include the branch or SHA whenever the distinction affects interpretation.

## 3. Authority hierarchy

| Layer | Document | Authority role | Use for | Do not use for |
|---|---|---|---|---|
| Project charter | [`../../AGENTS.md`](../../AGENTS.md) | Governing purpose and development rules | project mission, development principles, prohibitions, Verification stop rule | detailed current status, individual result claims |
| Repository entry | [`../../README.md`](../../README.md) | Navigation and high-level orientation | finding the relevant charter, strategy, specification, evidence, and closeout | granting Verification, Validation, Acceptance, or design-use authority |
| Development strategy | [`stage7_real_problem_application_strategy.md`](stage7_real_problem_application_strategy.md) | Current capability and application direction | prioritization, U1/U2/U3 portfolio, capability roadmap, maturity policy | claiming that a specific implementation passed its evidence gate |
| Current snapshot | [`stage7_current_gate_snapshot.md`](stage7_current_gate_snapshot.md) | Concise formal-state snapshot as of its stated date / branch | answering “where is the formally synchronized project now?” | replacing detailed evidence or representing later unsynchronized branch work |
| Master authority index | [`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md) | SHA / Workflow / Artifact / authority index | tracing authoritative implementation and evidence records | redefining project mission or future priority |
| Execution history | [`stage7_execution_log.md`](stage7_execution_log.md) | Chronological audit history | determining what was executed and in what order | acting as a compact current-status summary |
| Technical specification | physics and interface specifications listed below | Predeclared technical contract | determining required behavior, scope, state variables, guards, and PASS / FAIL conditions | assuming that specification status equals implementation or Validation status |
| Evidence / closeout | evidence and closeout documents | Result-specific claim boundary | determining what was executed and what may be claimed | expanding claims beyond the documented case and scope |
| Technical report | versioned report workspace | Integrated explanation and communication | explaining results, methods, limitations, and development history | overriding the specification, evidence, or master authority records |

## 4. Principal technical specifications

### 4.1 Liquid-to-two-phase transition contract

[`stage7_lco2_hem_liquid_to_two_phase_boundary_crossing_spec.md`](stage7_lco2_hem_liquid_to_two_phase_boundary_crossing_spec.md)

Authority role:

- defines how an updated conservative state is classified as liquid or open two phase;
- defines the role of `rho`, `e`, equilibrium quality, and quality synchronization;
- defines transition guards and prohibited interpretations.

It does not define a complete physical blowdown case or prove that the specified behavior has been implemented in every later branch.

### 4.2 Prescribed-boundary depressurization prototype

[`stage7_lco2_hem_pipeline_depressurization_prototype_spec.md`](stage7_lco2_hem_pipeline_depressurization_prototype_spec.md)

Authority role:

- defines the controlled pipeline pressure-wave case leading to first liquid-to-two-phase crossing;
- defines geometry, initial state, prescribed outlet-pressure cases, pressure-wave evidence, and crossing evidence.

It is a controlled prototype specification. It is not a physical discharge / choking boundary and does not by itself define post-crossing pressure-wave / flashing coupling.

### 4.3 U3 B2 single-phase physical-discharge coupling

[`stage7_u3_b2_fvm_discharge_coupling_specification.md`](stage7_u3_b2_fvm_discharge_coupling_specification.md)

Authority role:

- defines the single-phase FVM discharge-face mapping and finite-pipe coupling contract;
- governs the U3 B0 / B1 / B2 physical-discharge development path within its stated scope.

It does not authorize two-phase physical discharge, HEM/HNE blowdown, or general design use.

## 5. Working Tool authority

[`stage7_u3_b2_a1_working_tool_v0_b_closeout.md`](stage7_u3_b2_a1_working_tool_v0_b_closeout.md)

Authority role:

- closes the Working Tool v0-B operation / storage increment;
- records the authoritative canonical regression, output-file contract, FULL / SAMPLED state-history behavior, manifest, and Artifact authority;
- establishes a `PROVISIONAL ENGINEERING END-TO-END WORKING SLICE` for the bounded canonical tool path.

Working Tool v0-B is an operation layer. It does not change or validate:

- EOS physics;
- HEM/HNE phase-change physics;
- finite-pipe boundary physics;
- physical blowdown accuracy;
- two-phase pressure-wave propagation accuracy;
- design-use suitability.

## 6. Intentional overlaps and their boundaries

### 6.1 `README.md` versus `AGENTS.md`

```text
README
= navigation and orientation

AGENTS
= governing project charter and development rules
```

Shared mission wording is intentional. In case of a development-rule conflict, `AGENTS.md` governs.

### 6.2 Strategy versus current snapshot

```text
strategy
= where the project is going and why

snapshot
= formally synchronized state as of a stated point
```

A later strategy update does not automatically promote the status recorded in the snapshot.

### 6.3 Boundary-crossing specification versus depressurization prototype

```text
boundary-crossing specification
= thermodynamic / conservative transition contract

depressurization prototype
= boundary-driven pressure-wave test-case contract
```

They address different layers and must both remain.

### 6.4 HEM pressure-wave path versus U3 B2 discharge path

```text
HEM path
= liquid-to-two-phase crossing and post-crossing phase evidence

U3 B2 path
= bounded physical-discharge and finite-pipe coupling foundation
```

They are complementary. The next tool capability is to connect them under a bounded integration increment; neither document should be rewritten as though that integration already exists.

### 6.5 Working Tool documents versus physics specifications

```text
Working Tool documents
= case execution, result contracts, storage, manifest, sampling, reproducibility

physics specifications
= physical and numerical behavior of the solver, EOS, phase transition, and boundaries
```

Working Tool completion does not promote physics maturity.

### 6.6 Specification status versus later implementation status

A specification may retain historical wording such as:

```text
SPECIFICATION ONLY
NOT IMPLEMENTED
```

when that wording correctly records the state at specification time.

Do not retroactively rewrite historical specification status merely because later implementation or evidence exists. Instead, connect the sequence through this authority map, the master index, evidence, and closeout records.

## 7. Expected document lifecycle

```text
Project charter
→ development strategy
→ technical specification
→ implementation / execution plan
→ evidence
→ closeout
→ central snapshot / master index / execution-log synchronization
```

The same topic may appear in several documents because each stage answers a different question:

| Stage | Question answered |
|---|---|
| Charter | What are we developing, and under what rules? |
| Strategy | Which capabilities and use cases are prioritized? |
| Specification | What must this increment do? |
| Plan | How will it be implemented or tested? |
| Evidence | What actually happened? |
| Closeout | What may now be claimed? |
| Central sync | What is the formally indexed current state? |

## 8. Update policy

### Update `AGENTS.md` when

- the project purpose or governing development rule changes;
- a new prohibition or maturity rule must apply repo-wide.

Do not use it as a daily progress log.

### Update `README.md` when

- the project entry point, principal links, or high-level maturity explanation changes.

Do not duplicate detailed specifications or evidence tables there.

### Update the strategy when

- capability priority, application sequence, or maturity policy changes;
- a new use case becomes the selected pilot;
- a previously separate technical path must be integrated.

Do not use strategy wording alone to promote implementation status.

### Update snapshot / master index / execution log when

- branch work is formally merged or otherwise accepted as a central recorded state;
- an authoritative SHA, Workflow, Artifact, or formal result must be synchronized.

Perform these central-record updates together whenever practical so they do not disagree.

### Update a technical specification when

- the technical contract itself changes before or during the governed increment.

For historical completed work, prefer an amendment, successor specification, or explicit supersession link rather than silently changing the original contract.

## 9. Verification and Validation boundary

Verification and Validation are subordinate to analysis-tool development.

Verification is performed against predeclared conditions and concrete tool risks. After the active acceptance conditions are met, additional Verification requires an observed failure, a scope expansion, a decision-relevant sensitivity, or a specified Acceptance / Validation need.

Physical Validation is added for representative outputs and intended uses as the tool matures. It is not an automatic prerequisite for every exploratory or provisional Working Vertical Slice.

The following states must remain distinct:

```text
IMPLEMENTED
WORKING VERTICAL SLICE
VERIFIED
ACCEPTED
VALIDATED
APPROVED
```

## 10. Current capability direction

The authoritative roadmap is maintained in [`stage7_real_problem_application_strategy.md`](stage7_real_problem_application_strategy.md).

The current direction can be summarized, without creating a separate specification, as:

```text
retain existing HEM first-crossing and continuation evidence
+ retain U3 B2 A1 physical-discharge / Working Tool foundation
→ create a bounded post-crossing pressure-wave / flashing analysis slice
→ apply only targeted numerical gates required by that slice
→ begin early HNE / relaxation comparison
→ connect the two-phase path to the physical-discharge path
→ add representative Validation when required by the intended use
```

This summary does not itself authorize implementation, Verification promotion, Acceptance, Validation, or design use.
