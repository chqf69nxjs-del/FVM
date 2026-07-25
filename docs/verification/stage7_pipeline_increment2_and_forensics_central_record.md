# Stage 7 — Pipeline Increment 2 and Fixed 4 MPa Forensics Central Record

## Status

`PR #77 MERGED; PR #79 MERGED; SOFTWARE VERIFICATION/DIAGNOSTIC ONLY; GATE P2 FALSE`

This document is the central continuation record for the work merged after PR #76. It
records the boundary-driven pipeline observation in PR #77 and the fixed 4 MPa forensic
diagnostic in PR #79. It does not alter solver behavior or reclassify any observation.

## Development references

```text
PR #77 merge:  5657d26b3f37443ef63971245dce66ddd72c681e
PR #79 merge:  e40562e03657dec526f84b3911cbf181973462fa
recorded main: e40562e03657dec526f84b3911cbf181973462fa
```

## PR #77 — fixed boundary-driven pipeline matrix

### Fixed problem

```text
pipe length / diameter:        1.0 m / 0.10 m
cells:                         32
initial state:                 5 MPa / 5 K subcooling, u=0, q=0
left boundary:                 ReflectiveBoundary
right boundary:                prescribed subcooled outlet_only boundary
spatial flux:                  existing first-order Rusanov
CFL:                           0.10
friction / heat / gravity:     none / none / none
internal interfaces:           none
crossing evidence threshold:   q_eq >= 1.0e-6
```

All three pressure schedules passed the existing 65-point boundary preflight, for a total
of 195 accepted liquid-candidate boundary states.

### Fixed observations

| case | formal result | step | time [s] | cell | distance from outlet [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa raw transition was retained before evidence-threshold evaluation. It was not
clipped, hidden, accepted, or relabelled as all liquid.

### Gate P2 rule and result

The fixed 4 MPa liquid-control role requires:

```text
formal outcome = NO_CROSSING_WITHIN_HORIZON
raw liquid-to-two-phase crossing = false
reverse-flow fallback count = 0
```

The actual 4 MPa result does not satisfy this rule.

```text
fixed matrix executed honestly = true
4 MPa all-liquid control established = false
4 MPa subthreshold raw crossing retained = true
Gate P2 passed = false
```

### Reproducibility and validation

```text
validated implementation head:     2bbe2ad210d45c6403aa0b9a6a097dff56b44685
workflow run:                       30154880687
artifact ID:                        8618870653
artifact SHA256:                    7d254126a741e7d92e5ed1a2b6da94c703bbc2da91f1769d58c11deaa22b89b9
CoolProp:                           8.0.0
dependency-free tests:              26 passed, 0 skipped
installed-CoolProp tests:            5 passed, 0 skipped
related Stage 7 tests:              74 passed, 0 skipped
full repository:                   706 passed, 0 skipped
failures / errors:                   0 / 0
```

The full three-case matrix was executed twice in the focused validation. Outcomes, failure
reasons, step counts and times, crossing cells and distances, maximum qualities,
final-state SHA256 values, and run-signature SHA256 values matched exactly.

## PR #79 — fixed 4 MPa subthreshold-crossing forensics

### Immutable baseline

The diagnostic was permitted to continue only after reproducing the exact PR #77 baseline:

```text
formal outcome:               GUARD_FAILURE
crossing step / time:         313 / 1.996923102525957e-3 s
crossing cell / distance:     25 / 0.203125 m
maximum q_eq:                 9.672588429198319e-9
final-state SHA256:           7e8b6a6bc715755e0419d8a469140c02a79ec5e8bb419eb4868553c3228242e1
run-signature SHA256:         fdd25cbf669428790d1f3d877ab3b86ec329726d7b10e3a8461443ba6340b202
```

### Retained evidence

```text
selected steps:                  300–313
selected cells:                  23–27
accepted/raw/post state records: 210
raw saturation margins:           70
Rusanov decompositions:            70
rho/e perturbation states:         81
```

### Thermodynamic finding

At step 313 / cell 25:

```text
pressure:                    4,273,927.110515705 Pa
rho:                         876.1793486610264 kg/m3
internal energy:             215,231.8639318858 J/kg
q_eq:                        9.672588429198319e-9
void fraction:               6.721608823263323e-8
Delta_u_sat:                 +1.7008455179166049e-3 J/kg
Delta_v_sat:                 +6.567548805139212e-11 m3/kg
q from internal energy:      9.672598473952674e-9
q from specific volume:      9.672589435031626e-9
```

The internal-energy and specific-volume coordinates independently support a point just
inside the HEM equilibrium two-phase region.

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED = true
```

This is not proof of instantaneous physical nucleation in a real pipe.

### Isentropic reference

```text
initial entropy:                 1075.2689514867911 J/(kg K)
isentropic saturated-liquid p:  4,343,948.305362968 Pa
raw crossing pressure offset:   -70,021.19484726246 Pa
```

This is a reference trajectory only. The observed cell is Eulerian and is affected by
neighbouring fluxes.

### Local Rusanov decomposition

The exact central-plus-dissipative reconstruction reproduced the selected raw updates with:

```text
maximum absolute error:  2.2737367544323206e-13
maximum relative error:  1.685312437739661e-16
```

At the crossing step/cell, the offline central-only state was also open two phase:

```text
central-only q_eq:  3.690684903157135e-7
full Rusanov q_eq:  9.672588429198319e-9
```

The narrow last-step criterion therefore did not identify the Rusanov dissipative term as
the direct creator of the crossing. Accumulated first-order diffusion over prior steps
remains unresolved pending mesh sensitivity.

### Direct boundary criterion

The crossing cell was not boundary-adjacent, and the direct right/left conservative-energy
contribution ratio was `1.0832193659945168`. The reviewed narrow direct-boundary criterion
was not triggered. Indirect boundary influence through the launched pressure wave remains
possible.

### Property sensitivity

The fixed 9×9 perturbation grid used relative `rho/e` changes of:

```text
0, ±1e-12, ±1e-10, ±1e-8, ±1e-6
```

No phase-region change occurred through `1e-8`. Some `1e-6` perturbations returned to the
liquid side.

```text
perturbation classification = WEAKLY_RESOLVED
NEAR_SATURATION_PROPERTY_SENSITIVE = true
```

### Retained diagnostic categories

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

Not triggered under the reviewed narrow criteria:

```text
NUMERICAL_DIFFUSION_CONSISTENT
BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT
```

No single physical cause was established.

### Acoustic caution

The equilibrium sound-speed candidate changed from approximately `461.2567 m/s` in the
accepted liquid state to `43.2231 m/s` in the raw micro-quality two-phase state.
Near-saturation continuity and physical accuracy remain unapproved. No post-crossing
propagation claim is accepted.

### Final validation

```text
validated implementation head:     719301dd64c9ee2571cf3296605466a2ee9de27f
workflow run:                       30162194409
artifact ID:                        8620823392
artifact SHA256:                    1b2c14790c3c66be47386f60ddb9c8b21ee5d253dcc0ab1d78e9deaa7b5184d7
CoolProp:                           8.0.0
dependency-free forensic tests:      8 passed, 0 skipped
installed-CoolProp forensics:        9 passed, 0 skipped
related Stage 7 regressions:        69 passed, 0 skipped
full repository:                   723 passed, 0 skipped
failures / errors:                   0 / 0
```

## Current approval boundary

```text
verification_only = true
software_diagnostic_only = true
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
two_phase_acoustic_accuracy_band_approved = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
post_crossing_propagation_approved = false
```

## Active next gate

Proceed to a separate 32/64/128-cell mesh sensitivity study with CFL fixed at 0.10. The
reviewed plan is
[`stage7_lco2_hem_pipeline_4mpa_mesh_sensitivity_plan.md`](stage7_lco2_hem_pipeline_4mpa_mesh_sensitivity_plan.md).

CFL sensitivity, near-saturation acoustic continuity, boundary-model comparison, MUSCL/TVD,
HNE/metastability, and physical Validation remain separate later increments.
