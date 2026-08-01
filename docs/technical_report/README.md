# Stage 1–Gate 9 Technical Report Workspace

## Status — 2026-08-01

```text
report type:                    internal technical report / research record
scope start:                    Stage 1
scope end:                      Gate 9 literature and execution-contract preparation
current activity:               structure and evidence design
full prose drafting:            NOT STARTED
physical validation claim:      PROHIBITED
approved design-use claim:      PROHIBITED
```

This directory is the controlled workspace for reorganizing the development from
Stage 1 through the Gate 9 preparation into one logically consistent technical
report.

The report is not intended to be a chronological list of pull requests. Its
purpose is to explain the research logic:

```text
why each verification layer was needed
→ what evidence was obtained
→ what the evidence supports
→ what remains unresolved
→ why the next controlled work is necessary
```

## Controlled deliverables

- [`lco2_fvm_hem_technical_report_contract_v0p1.json`](lco2_fvm_hem_technical_report_contract_v0p1.json)
  - machine-readable scope, title, claims, non-claims, chapter structure, and update rules;
- [`lco2_fvm_hem_writing_design_v0p1.md`](lco2_fvm_hem_writing_design_v0p1.md)
  - chapter-by-chapter purpose, central message, evidence, figures, tables, and writing cautions;
- [`lco2_fvm_hem_evidence_matrix_v0p1.md`](lco2_fvm_hem_evidence_matrix_v0p1.md)
  - traceability from report statements to Stage/Gate records, PRs, workflows, and artifacts;
- [`lco2_fvm_hem_figure_table_register_v0p1.md`](lco2_fvm_hem_figure_table_register_v0p1.md)
  - planned figure and table inventory, data source, status, and drafting priority;
- [`lco2_fvm_hem_technical_report_skeleton_v0p1.md`](lco2_fvm_hem_technical_report_skeleton_v0p1.md)
  - empty report body with drafting notes and evidence placeholders.

## Working principle

The report follows four evidence levels.

| Level | Meaning | Current status |
|---|---|---|
| Software verification | code paths, identities, budgets, guards, and reproducibility | substantially established for the reviewed fixed cases |
| Numerical characterization | mesh, CFL, numerical diffusion, event and guard sensitivity | observed; several independence claims remain false |
| Model characterization | HEM assumptions, acoustic closure, phase classification, relaxation alternatives | partially characterized; important open questions remain |
| Physical validation and design use | comparison against experimental or field data and approved applicability envelope | not established |

No statement from a lower level may be presented as proof of a higher level.

## Baseline central thesis

> A conservative one-dimensional finite-volume HEM path for pure CO2 was built
> and progressively verified from single-phase wave propagation through discrete
> liquid-to-open-two-phase crossing and a fixed post-crossing continuation. The
> reviewed evidence demonstrates software integrity and useful fixed-case
> behavior, but crossing depth and continuation outcomes are non-monotone with
> CFL, and near-saturation acoustic evaluation remains a limiting factor.
> Therefore the current path is an evidence-rich verification baseline rather
> than a physically validated design model; numerical/acoustic forensic
> diagnosis and an independently benchmarked physical discharge boundary are
> required before integrated blowdown use.

## Drafting order

```text
1. lock structure, claims, evidence, and figure/table register
2. draft result chapters from authoritative artifacts
3. draft methods from source and verification contracts
4. draft literature comparison and discussion
5. draft introduction after the technical story is stable
6. draft abstract and conclusion last, then reconcile them with the body
```

The report should remain versioned rather than overwritten:

```text
v0.1  Stage 1–Gate 8 evidence and Gate 9 preparation
v0.2  add Gate 9 forensic execution
v0.3  add U3 B0 component benchmark
v1.0  reviewed report through accepted physical-discharge component evidence
```
