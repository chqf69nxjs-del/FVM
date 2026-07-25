# Stage 7 Current Gate Snapshot

## Status — 2026-07-25

```text
Stage 1–6:                         COMPLETE
Stage 7:                           IN_PROGRESS
recorded development main:         e40562e03657dec526f84b3911cbf181973462fa
pipeline Increment 2:              MERGED in PR #77
fixed 4 MPa forensic diagnostic:   MERGED in PR #79
Gate P2:                           FALSE
active next gate:                  32/64/128-cell mesh sensitivity at CFL 0.10
physical Validation:               NOT ESTABLISHED
design-use acceptance:             NOT ESTABLISHED
production HEM activation:         NOT APPROVED
two-phase acoustic accuracy band:  NOT APPROVED
```

This snapshot is the current continuation record after the existing
[`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md) and
[`stage7_execution_log.md`](stage7_execution_log.md). Detailed PR #77/#79 evidence is
recorded in
[`stage7_pipeline_increment2_and_forensics_central_record.md`](stage7_pipeline_increment2_and_forensics_central_record.md).

## Merged pipeline observation — PR #77

The fixed 1.0 m / 0.10 m / 32-cell, first-order Rusanov prototype executed the unchanged
5→2, 5→3, and 5→4 MPa matrix at CFL 0.10.

| case | formal result | crossing step | crossing time [s] | cell | outlet distance [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa observation is neither an accepted crossing nor an all-liquid control. It is a
reproducible subthreshold raw liquid-to-two-phase crossing. The fixed case, algorithm, and
`1e-6` accepted-crossing evidence threshold were not tuned.

## Merged fixed-case diagnosis — PR #79

The exact PR #77 4 MPa baseline was reproduced before diagnosis. The retained categories are:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

The raw crossing point is independently on the equilibrium two-phase side in both
internal-energy and specific-volume coordinates. The perturbation classification is
`WEAKLY_RESOLVED`: no phase-region change occurs through relative `rho/e` perturbations of
`1e-8`, while some `1e-6` perturbations return to the liquid side.

The narrow last-step criteria did not trigger:

```text
NUMERICAL_DIFFUSION_CONSISTENT
BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT
```

This does not rule out accumulated first-order diffusion over earlier steps or indirect
boundary influence. Those questions require separate sensitivity studies.

## Acoustic caution

At the micro-quality crossing, the equilibrium sound-speed candidate changed from
approximately `461.2567 m/s` in the accepted liquid state to `43.2231 m/s` in the raw
two-phase state. Near-saturation acoustic continuity and physical accuracy remain
unapproved. Post-crossing propagation is not yet an accepted capability.

## Active next gate

The next reviewed increment is
[`stage7_lco2_hem_pipeline_4mpa_mesh_sensitivity_plan.md`](stage7_lco2_hem_pipeline_4mpa_mesh_sensitivity_plan.md).
It keeps CFL at 0.10 and compares 32, 64, and 128 cells without changing the fixed pressure
schedules, HEM classification/projection settings, or evidence threshold.

```text
mesh-independent crossing verified = false
CFL sensitivity completed = false
near-saturation acoustic continuity approved = false
Gate P2 passed = false
```
