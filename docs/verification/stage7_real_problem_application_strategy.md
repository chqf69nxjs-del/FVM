# Stage 7 Analysis-Tool Development and Real-Problem Application Strategy

## Status — 2026-08-14

```text
project purpose:                    PRACTICAL ANALYSIS-TOOL DEVELOPMENT
primary required capability:        PRESSURE-WAVE / FLASHING / TWO-PHASE STUDIES
application track:                  ACTIVE
application specification:          REVIEWED BASELINE; STRATEGY UPDATED
first pilot use case:               U3 pipeline depressurization / blowdown
Working Tool v0-B:                  PROVISIONAL ENGINEERING END-TO-END WORKING SLICE
physical validation:                NOT ESTABLISHED
design-use acceptance:              NOT APPROVED
production HEM activation:          NOT APPROVED
```

Related control records:

- Issue #104 — real-problem application specification
- Issue #105 — Gate 8 post-crossing CFL sensitivity
- [`project_document_authority_map.md`](project_document_authority_map.md)
- [`stage7_current_gate_snapshot.md`](stage7_current_gate_snapshot.md)
- [`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md)
- [`stage7_execution_log.md`](stage7_execution_log.md)
- [`stage7_u3_b2_a1_working_tool_v0_b_closeout.md`](stage7_u3_b2_a1_working_tool_v0_b_closeout.md)
- [`stage7_gate6_closeout.md`](stage7_gate6_closeout.md)
- [`stage7_gate7_closeout.md`](stage7_gate7_closeout.md)

## 1. Purpose and completion policy

The purpose of Stage 7 is to develop a practical analysis tool that can support bounded engineering studies of pressure-wave propagation, depressurization, flashing, and liquid-to-two-phase transition in finite-length liquid-CO2 pipelines.

The project is **not** defined as an open-ended effort to completely explain those phenomena. Pressure propagation, flashing, and two-phase behavior are required analysis capabilities of the tool, not an unlimited research completion criterion.

The target development sequence is:

```text
bounded physics capability
→ end-to-end Working Vertical Slice
→ explicit scope / guards / outputs / reproducibility
→ targeted Physics refinement / Verification
→ representative Validation when required by the intended use
```

A Working Vertical Slice is complete when a declared case can be executed end to end within a bounded scope, the relevant result and state histories can be inspected, limitations and fail-closed conditions are explicit, and the run can be reproduced. Comprehensive Verification of every physical regime and full Physical Validation are not prerequisites for that status.

Stage 7 has moved beyond proving that a liquid-to-open-two-phase crossing can occur. The reviewed HEM path can recover a mixed accepted state, continue for a fixed post-crossing horizon, retain conservative and vapor budgets, and diagnose localized phase chatter. In parallel, the U3 B2 A1 path has established a provisional finite-pipe discharge Working Tool with reproducible output and storage behavior.

The project advances along two controlled tracks:

```text
Track N — targeted numerical / model characterization
Track A — analysis-tool capability and real-problem application
```

Track N determines whether a specific result used by the tool is sufficiently stable, conservative, repeatable, and bounded for its declared purpose. Track A determines what analysis studies the tool must execute, which input and output contracts are required, and what evidence is necessary for each maturity level.

Neither track alone is sufficient:

- numerical studies without a concrete tool capability or decision target can become open-ended;
- application development without numerical and physical bounds can overstate confidence.

### 1.1 Verification stop rule

Verification is limited to predeclared acceptance conditions for the active increment, such as conservation, finite / positivity behavior, repeatability, state transitions, guard behavior, and the sensitivity of decision-relevant outputs.

After those conditions are met, additional Verification is undertaken only when one of the following is identified:

- an observed solver, conservation, positivity, root, branch, or reproducibility failure;
- a new physical regime, input range, or intended use;
- a sensitivity capable of changing an engineering comparison or conclusion;
- a prerequisite for a specified Acceptance or representative Validation activity.

Additional work is not justified solely by the possibility that more Verification could increase general confidence.

## 2. Current technical position

The reviewed first-order HEM verification path currently supports:

- pure CO2 properties through CoolProp 8.0.0;
- one-dimensional conservative FVM with the existing Rusanov flux;
- direct liquid-to-open-two-phase crossing from an all-liquid initial state;
- equilibrium-quality synchronization;
- accepted liquid / open-two-phase state recovery;
- exact second-projection no-op behavior;
- one fixed 5→2 MPa continuation for 64 accepted post-crossing steps;
- a persistent open-two-phase region moving upstream in that fixed case;
- conservative and vapor-budget closure;
- focused event-aligned diagnosis of the boundary-adjacent cell-30 chatter.

The U3 B2 A1 development path additionally provides:

- a finite-pipe single-phase discharge working slice with explicit boundary-model transitions;
- guarded finite-compression, near-zero-flow, and zero-transfer behavior for the canonical case;
- a Working Tool v0-B operation layer for run directories, output files, state-history storage, sampling, manifest, and reproducibility;
- an authoritative canonical regression for that bounded working case.

These two foundations are complementary:

```text
existing HEM path
= liquid-to-two-phase transition and post-crossing physics evidence

U3 B2 A1 / Working Tool path
= physical-discharge and reproducible tool-operation foundation
```

They are not yet an integrated physical two-phase blowdown tool.

The evidence does **not** yet establish:

- post-crossing CFL or mesh independence;
- physical phase-front speed;
- phase-chatter root cause or mitigation;
- strict `q -> 0+` acoustic continuity;
- a two-phase acoustic accuracy band;
- non-equilibrium flashing-delay accuracy;
- an integrated two-phase physical discharge / choking boundary;
- physical blowdown, ESD-valve, or pump-trip validation;
- design use or production HEM activation.

These open items are tracked as bounded capability gaps. They do not invalidate the existing Working Vertical Slices outside their stated scope.

## 3. Common engineering-result contract

Every future accepted engineering result must present four layers together:

```text
1. representative result
2. numerical and model sensitivity envelope required for that use
3. applicability warnings / guard outcomes
4. unapproved or unvalidated model elements
```

A single pressure peak, crossing time, or phase-front position without those layers is not an accepted engineering deliverable.

Exploratory C1 Working-Slice results may still be used for development comparison, model discrimination, workflow testing, and sensitivity exploration when their limitations and authority are explicit.

### 3.1 Minimum common outputs

```text
maximum pressure, position, and time
minimum pressure, position, and time
pressure-wave arrival times at selected components
first crossing time, position, and accepted / guard status
maximum two-phase-region length
persistence duration and propagation history
maximum q_eq and void fraction
vapor generation and inventory history
flow-reversal occurrence and duration
relief-set-pressure exceedance duration
design-pressure exceedance duration
solver / property / phase / acoustic guard history
CFL / mesh / model sensitivity range required for the intended use
applicability status and result-confidence class
```

### 3.2 Result-confidence classes

```text
C0 — unsupported or outside modeled scope
C1 — exploratory model result; no verification claim
C2 — numerically verified for a fixed simplified case
C3 — sensitivity-bounded screening result with benchmark support
C4 — approved design use within a documented applicability envelope
```

Current classification:

```text
fixed prescribed-boundary 5→2 MPa analogue: C2
canonical U3 B2 A1 Working Tool case:         C1 operational working slice
physical blowdown prediction:                 C1 or below
ESD valve operation with HEM:                 C1 or below
pump trip with HEM:                           C1 or below
approved design use:                          not reached
```

## 4. Use-case portfolio

## U1 — ESD valve operation / rapid isolation

### Engineering decisions

- maximum and minimum pressure;
- incident and reflected wave arrival times;
- local liquid-to-two-phase crossing near the valve or high points;
- relief or design-pressure exceedance;
- reverse flow and unstable phase switching.

### Required inputs

```text
network geometry, elevation, roughness, and thermal data
initial pressure, temperature, and flow
valve location
Cv / loss coefficient versus opening
opening versus time / closure law
upstream and downstream equipment boundaries
relief settings
```

### Current readiness

The generic solver infrastructure and Stage 7 HEM evidence provide useful foundations. The ESD-valve path is not yet integrated into the same crossing / propagation evidence chain and is not physically validated.

### Critical gaps

```text
HEM-connected transient valve characteristic
friction / gravity / heat-transfer verification required by the intended use
wave-reflection benchmark cases
post-crossing targeted CFL and mesh sensitivity
physical pressure-peak and flashing-onset validation
```

## U2 — pump trip / rotating-inertia rundown

### Engineering decisions

- pump speed and flow rundown;
- reverse flow or turbine-mode operation;
- minimum pressure and its location;
- pump-inlet or high-point flashing;
- check-valve, tank, pit, or accumulator interaction.

### Required inputs

```text
pump complete characteristic or accepted normalized representation
rotor / coupled-machine inertia
initial operating point and speed
motor torque / trip law
check-valve behavior
reservoir, tank, pit, or gas-volume boundaries
network elevation, friction, and thermal data
```

### Current readiness

Pump concepts exist in the wider project context, but no pump-trip problem is connected to the reviewed Stage 7 HEM path with end-to-end crossing, propagation, bounded sensitivity, and validation evidence.

### Critical gaps

```text
verified pump-inertia coupling
reverse-flow / turbine-region treatment
check-valve and reservoir coupling
high-point gravity effects
post-crossing targeted numerical sensitivity
physical benchmark or experimental validation
```

## U3 — pipeline depressurization / blowdown

### Engineering decisions

- depressurization time;
- discharge and inventory histories;
- crossing time and location;
- two-phase-region growth, persistence, and propagation;
- interaction between flashing and the pressure-wave history;
- maximum q_eq and void fraction;
- temperature reduction and approach to out-of-scope solid-CO2 conditions;
- controlling influence of the discharge boundary.

### Required inputs

```text
pipe geometry, elevation, roughness, and wall thermal mass
initial pressure, temperature, flow, and inventory
blowdown valve / orifice characteristic and opening law
back pressure or receiving-volume model
external heat transfer
vent / relief arrangement
solid-CO2 and non-condensable-gas screening information
```

### Current readiness

The 5→2 MPa prescribed-subcooled outlet case is the closest current HEM verification analogue. It proves that the existing HEM path can cross and continue, but it is not a physical blowdown closure.

The U3 B2 A1 path now provides a bounded single-phase physical-discharge and Working Tool foundation, but it has not yet been connected to the existing HEM post-crossing path. The next application capability is therefore not a new first-crossing specification; it is a bounded integration that follows the pressure wave and flashing region after crossing and then connects that path to the physical discharge model.

### Critical gaps

```text
post-crossing pressure-wave / flashing coupling output path
targeted post-crossing CFL and mesh checks for decision outputs
early HEM versus HNE / relaxation comparison
integrated two-phase physical discharge / choking boundary
wall heat transfer and thermal inventory required for later use
longer-duration continuation when required by the study horizon
solid-CO2 approach guard
representative pressure / discharge / phase-front validation
```

## 5. Applicability and exclusion matrix

| Topic | Current project status | Permitted interpretation |
|---|---|---|
| Fluid | pure CO2 | within reviewed property scope only |
| Backend | CoolProp 8.0.0 | fixed verification reference |
| Dimension | one-dimensional | axial network transients only |
| Phase model | equilibrium HEM | fixed-case verification baseline |
| Spatial method | first-order FVM / Rusanov | numerical characteristics still being mapped |
| First crossing | verified in fixed cases | crossing existence / location evidence |
| Quality projection | verified in fixed cases | synchronization, not physical nucleation kinetics |
| Post-crossing continuation | one 32-cell / CFL 0.10 case | fixed-case verification evidence |
| Conservative budgets | closed in fixed continuation | software / numerical integrity evidence |
| Working Tool v0-B | canonical provisional working slice | execution / output / storage foundation only |
| Post-crossing CFL sensitivity | not yet executed | no general timing-independence claim |
| Post-crossing mesh sensitivity | not yet executed | no general spatial-convergence claim |
| Local chatter | observed and diagnosed for correlation | root cause and mitigation unapproved |
| Friction / gravity / heat in Stage 7 HEM path | not established | do not infer full real-pipeline response |
| Physical discharge boundary | single-phase bounded working foundation | no integrated two-phase blowdown-rate claim |
| ESD-valve HEM path | not established | exploratory only |
| Pump-trip HEM path | not established | exploratory only |
| Non-condensable gas | outside evidence | unsupported |
| Solid CO2 | outside evidence | unsupported; guard required |
| Non-equilibrium flashing | early comparison target; outside current evidence | no nucleation-delay accuracy claim |
| Physical validation | not established | no accuracy claim |
| Design use | not approved | prohibited |

## 6. Evidence and maturity ladder

The following ladder defines increasing evidence and use maturity. It is **not** a mandatory serial checklist that must be completed in full before a Working Vertical Slice can exist.

### V0 — scope and conservation checks

- inputs remain inside property and phase scope;
- solver guards are explicit;
- mass, momentum, energy, and vapor accounting close to the predeclared criterion.

### V1 — targeted numerical characterization

- CFL and mesh sensitivity for outputs that matter to the declared use;
- event and guard repeatability;
- front, peak, and timing envelopes when required;
- local oscillation characterization when it affects interpretation.

### V2 — component-level benchmark

- valve, pump, or discharge element against an analytical, trusted-code, or controlled benchmark;
- boundary and equipment energy / momentum consistency.

### V3 — integrated system benchmark

- representative pipeline network with coupled equipment;
- comparison of pressure, flow, crossing, and inventory histories.

### V4 — physical validation

- experimental or field data with uncertainty bounds;
- documented model discrepancy and applicability range.

### V5 — design-use review

- accepted sensitivity envelope;
- warning and fail-safe policy;
- independent review;
- explicit approval for a bounded use case.

A feature may be an `IMPLEMENTED` or `WORKING VERTICAL SLICE` capability before V1–V5 are complete. Its status, limits, and prohibited interpretations must remain explicit.

## 7. Selected first pilot — U3 depressurization / blowdown

U3 is selected as the first pilot application because:

1. it is closest to the existing 5→2 MPa HEM verification analogue;
2. it directly exercises crossing, propagation, acoustic, quality, and vapor-inventory behavior already under review;
3. it can reuse the U3 B2 A1 physical-discharge and Working Tool foundations;
4. it avoids adding pump inertia and full valve-network reflection complexity at the first application step;
5. it creates reusable discharge-boundary and thermal capabilities needed by later ESD and relief studies;
6. it supports early HEM / HNE comparison for pressure-propagation and flashing-delay studies.

This selection does **not** mean the current prescribed-subcooled outlet or single-phase discharge path is accepted as an integrated two-phase blowdown boundary.

### Pilot progression

```text
P0 — existing prescribed-boundary HEM first-crossing and continuation analogue
P0B — existing U3 B2 A1 single-phase discharge and Working Tool foundation
P1 — bounded post-crossing pressure-wave / flashing coupling analysis slice
P2 — early HNE / relaxation prototype and HEM comparison
P3 — integrated two-phase physical-discharge benchmark
P4 — representative physical-data validation for selected outputs
P5 — sensitivity-bounded engineering screening review
```

The progression is capability-driven. P1 and P2 may proceed while targeted P0 / P0B numerical checks continue, provided each result retains its own scope and status.

### Pilot decision outputs

```text
depressurization time
pressure envelope
pressure-wave arrival and propagation history
crossing time and position
phase-region extent and propagation
pressure-front versus flashing-front relationship
vapor-generation and inventory envelope
maximum q_eq / alpha
discharge-flow history
solid-CO2 approach warning
targeted CFL / mesh / boundary-model sensitivity
HEM / HNE model-difference envelope
```

## 8. Mapping technical work to tool and engineering risks

| Technical work | Tool or engineering risk reduced |
|---|---|
| bounded conservation / finite / reproducibility gate | silent corruption, nonphysical state, irreproducible output |
| post-crossing pressure / phase-front output path | inability to study pressure-wave / flashing interaction |
| targeted post-crossing CFL sensitivity | timing, front speed, chatter frequency, peak / phase-event timing used by the study |
| targeted post-crossing mesh sensitivity | front position, front thickness, local peak q / alpha, spatial localization used by the study |
| early HEM / HNE comparison | flashing-delay and rapid-depressurization model dependence |
| local flux / acoustic contribution analysis | interpretation of chatter and Rusanov branch coupling when it affects results |
| physical discharge-boundary benchmark | blowdown-rate and pressure-history credibility |
| heat-transfer / wall-inventory study | temperature and vapor-generation credibility for longer studies |
| representative physical validation | accuracy and applicability envelope for selected outputs |

Not every row is required for every exploratory Working-Slice run. Required evidence is selected from the intended use and predeclared acceptance criteria.

## 9. Two-track roadmap

### Track N — targeted numerical and model characterization

```text
minimum conservation / finite / positivity / reproducibility gate
→ bounded post-crossing HEM pressure-wave / flashing continuation
→ targeted CFL / mesh checks for decision-relevant outputs
→ early HNE / relaxation prototype and HEM comparison
→ additional risk-specific checks only when triggered by evidence or scope expansion
```

### Track A — analysis-tool capability and application

```text
Working Tool v0-B operation baseline
→ pressure-wave and phase-front analysis outputs
→ U3 post-crossing two-phase analysis slice
→ integrated physical discharge / two-phase coupling
→ representative benchmark and Validation for selected outputs
→ bounded engineering-screening review
```

U1 and U2 component specifications may proceed in parallel. They do not require every U3 Verification or Validation task to finish first, but they must retain explicit model scope, guards, result authority, and use restrictions.

## 10. Governance decision

```text
project_primary_goal = practical_analysis_tool_development
required_primary_capability = pressure_wave_flashing_two_phase_studies
complete_phenomenon_understanding_required_for_working_slice = false
comprehensive_all_domain_verification_required_for_working_slice = false
verification_stop_rule_defined = true

application_specification_complete = true
real_problem_pilot_selected = true
selected_pilot = U3_pipeline_depressurization_blowdown
Working_Tool_v0_B = PROVISIONAL_ENGINEERING_END_TO_END_WORKING_SLICE
post_crossing_pressure_flashing_slice = NEXT_CAPABILITY_FOCUS
early_HNE_relaxation_comparison = PLANNED_HIGH_PRIORITY

ESD_design_use_approved = false
pump_trip_design_use_approved = false
blowdown_design_use_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

This strategy authorizes bounded tool development, controlled analysis studies, targeted Verification, and Validation planning. It does not authorize a production model, equipment-model accuracy claim, general physical-accuracy claim, or engineering design decision.
