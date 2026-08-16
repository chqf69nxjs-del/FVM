# Stage 7 P1 Numerical Sensitivity Closeout

## Purpose

This closeout integrates the existing P1 evidence chain without changing any production physics or numerical authority:

- P1-A2 — pressure-front threshold sensitivity
- P1-A3 — mesh / CFL sensitivity
- P1-A3F — subthreshold crossing forensics
- P1-A3G — Event A / Event B crossing alignment

The closeout is an evidence synthesis increment. It is **not** a solver change, threshold change, tolerance change, validation increment, or maturity promotion.

## Frozen authorities

| evidence | branch | frozen HEAD |
|---|---|---|
| main | `main` | `aa108961762c9ae70ee9940405024eb5188064b8` |
| P1-A2 | `agent/stage7-p1-threshold-sensitivity-a2` | `247148c8ee7ac119fb030f07240ca0e5b05e8ff4` |
| P1-A3 | `agent/stage7-p1-mesh-cfl-sensitivity-a3` | `b9e36507370c6c7e8136e1635bb9c4382c6a292a` |
| P1-A3F | `agent/stage7-p1-a3-subthreshold-crossing-forensics` | `994124c38828459e866f0d4f874ecf05bd15299a` |
| P1-A3G | `agent/stage7-p1-a3-crossing-event-alignment` | `5d58291e0debe103092c4b7ebd6ad751eb5ea9bd` |

The focused workflow checks these refs against the exact SHAs before accepting closeout evidence.

## Closeout logic

`CLOSEOUT_READY_WITH_LIMITATIONS` requires all of the following simultaneously:

1. A2 reproduces `SENSITIVITY_READY / ROBUST` for the predeclared 0.5e-6 / 1.0e-6 / 2.0e-6 pressure-front threshold envelope.
2. A3 remains exactly `FAIL_CLOSED / INCONCLUSIVE / INCONCLUSIVE`.
3. A3F reproduces `FORENSICS_READY` and `direct_failure_mechanism = CONFIRMED` with no unrelated failure category.
4. A3G reproduces `ALIGNMENT_READY`, reaches Event B for every case, and retains the frozen A3 verdict.
5. The fine-mesh and low-CFL cases remain the exact subthreshold pair.
6. The fixed crossing-evidence floor remains exactly `1.0e-6`.
7. Solver, EOS, threshold, tolerance, production numerics, and locked Gate 6 authority remain unchanged.
8. No source maturity flag is promoted.
9. Mesh independence and CFL independence remain explicitly **not verified**.

A3 becoming a successful or robust sensitivity result without a separately reviewed authority change is therefore a **closeout failure**, not an automatic improvement.

## Consolidated interpretation

The P1 evidence supports the narrow engineering interpretation that the diagnostic pressure front precedes the accepted equilibrium `OPEN_TWO_PHASE` phase front over the predeclared pressure-front threshold envelope.

The A3 fine-mesh and low-CFL Guard failures do not mean that two-phase entry failed to occur. A3F and A3G show positive thermodynamic Event A crossings below the unchanged `1e-6` evidence floor, followed by Event B one accepted step later. This strongly supports a discrete event-definition / resolution interaction.

The A-to-B interval is an HEM numerical/thermodynamic diagnostic. It is not a physical nucleation delay, flashing delay, or validated relaxation time.

Absolute first-crossing timing remains numerically sensitive, especially to mesh. Therefore the closeout does not claim mesh or CFL independence.

## What this closeout permits

If all closeout gates pass, P1 is considered **closed as a bounded numerical-sensitivity study with explicit limitations**. This permits progression to P2 HNE model-form sensitivity while carrying the P1 limitations forward.

It does not permit design use or physical validation claims.

## Formal maturity boundary

```text
IMPLEMENTED                    true
WORKING VERTICAL SLICE         false
VERIFIED                       false
ACCEPTED                       false
MESH-INDEPENDENT VERIFIED      false
CFL-INDEPENDENT VERIFIED       false
PHYSICALLY VALIDATED           false
DESIGN-USE ACCEPTED            false
PRODUCTION APPROVED            false
```

## Deterministic output contract

Exactly eight closeout files are generated:

```text
closeout_summary.json
evidence_authorities.csv
threshold_synthesis.csv
mesh_cfl_event_synthesis.csv
limitations.csv
numerical_sensitivity_overview.png
operator_report.md
closeout_manifest.json
```

The PNG is generated from the executed numerical data. No image-generation model is used for quantitative evidence.
