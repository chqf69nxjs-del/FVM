# Stage 7 Real-Problem Application Strategy

## Status — 2026-07-30

```text
application track:                 ACTIVE
application specification:         REVIEWED DRAFT
first pilot use case:              U3 pipeline depressurization / blowdown
physical validation:               NOT ESTABLISHED
design-use acceptance:             NOT APPROVED
production HEM activation:         NOT APPROVED
```

Related control records:

- Issue #104 — real-problem application specification
- Issue #105 — Gate 8 post-crossing CFL sensitivity
- [`stage7_current_gate_snapshot.md`](stage7_current_gate_snapshot.md)
- [`stage7_gate6_closeout.md`](stage7_gate6_closeout.md)
- [`stage7_gate7_closeout.md`](stage7_gate7_closeout.md)

## 1. Purpose

Stage 7 has moved beyond proving that a liquid-to-open-two-phase crossing can occur. The current verification path can recover a mixed accepted state, continue for a fixed post-crossing horizon, retain conservative and vapor budgets, and diagnose localized phase chatter.

The project must now advance along two controlled tracks:

```text
Track N — numerical / model characterization
Track A — real-problem application definition and validation planning
```

Track N determines how results change with CFL, mesh, flux structure, acoustic closure, and model assumptions. Track A determines what engineering decisions the tool should support, which input and output contracts are required, and what evidence is needed before those results can be used.

Neither track alone is sufficient:

- numerical studies without an application target can become open-ended;
- application development without numerical and physical bounds can overstate confidence.

## 2. Current technical position

The reviewed first-order verification path currently supports:

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

The evidence does **not** yet establish:

- post-crossing CFL or mesh independence;
- physical phase-front speed;
- phase-chatter root cause or mitigation;
- strict `q -> 0+` acoustic continuity;
- a two-phase acoustic accuracy band;
- physical blowdown, ESD-valve, or pump-trip validation;
- design use or production HEM activation.

## 3. Common engineering-result contract

Every future real-problem result must present four layers together:

```text
1. representative result
2. numerical and model sensitivity envelope
3. applicability warnings / guard outcomes
4. unapproved or unvalidated model elements
```

A single pressure peak, crossing time, or phase-front position without those layers is not an accepted engineering deliverable.

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
CFL / mesh / model sensitivity range
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
friction / gravity / heat-transfer verification
wave-reflection benchmark cases
post-crossing CFL and mesh sensitivity
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

Pump concepts exist in the wider project context, but no pump-trip problem is connected to the reviewed Stage 7 HEM path with end-to-end crossing, propagation, sensitivity, and validation evidence.

### Critical gaps

```text
verified pump-inertia coupling
reverse-flow / turbine-region treatment
check-valve and reservoir coupling
high-point gravity effects
post-crossing numerical sensitivity
physical benchmark or experimental validation
```

## U3 — pipeline depressurization / blowdown

### Engineering decisions

- depressurization time;
- discharge and inventory histories;
- crossing time and location;
- two-phase-region growth, persistence, and propagation;
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

The 5→2 MPa prescribed-subcooled outlet case is the closest current verification analogue. It proves that the existing HEM path can cross and continue, but it is not a physical blowdown closure. The outlet is not an orifice / critical-discharge model, thermal effects are absent, post-crossing sensitivity is unknown, and propagation speed is unvalidated.

### Critical gaps

```text
physical discharge / choking boundary
post-crossing CFL and mesh sensitivity
wall heat transfer and thermal inventory
longer-duration continuation
solid-CO2 approach guard
HEM versus non-equilibrium applicability assessment
pressure / discharge / phase-front validation
```

## 5. Applicability and exclusion matrix

| Topic | Current project status | Permitted interpretation |
|---|---|---|
| Fluid | pure CO2 | within reviewed property scope only |
| Backend | CoolProp 8.0.0 | fixed verification reference |
| Dimension | one-dimensional | axial network transients only |
| Phase model | equilibrium HEM | verification-only |
| Spatial method | first-order FVM / Rusanov | numerical characteristics still being mapped |
| First crossing | verified in fixed cases | crossing existence / location evidence |
| Quality projection | verified in fixed cases | synchronization, not physical nucleation kinetics |
| Post-crossing continuation | one 32-cell / CFL 0.10 case | fixed-case verification evidence |
| Conservative budgets | closed in fixed continuation | software / numerical integrity evidence |
| Post-crossing CFL sensitivity | not yet executed | no timing independence claim |
| Post-crossing mesh sensitivity | not yet executed | no spatial convergence claim |
| Local chatter | observed and diagnosed for correlation | root cause and mitigation unapproved |
| Friction / gravity / heat in Stage 7 path | not established | do not infer full real-pipeline response |
| Physical discharge boundary | not established | no physical blowdown-rate claim |
| ESD-valve HEM path | not established | exploratory only |
| Pump-trip HEM path | not established | exploratory only |
| Non-condensable gas | outside evidence | unsupported |
| Solid CO2 | outside evidence | unsupported; guard required |
| Non-equilibrium flashing | outside current HEM evidence | no nucleation-delay claim |
| Physical validation | not established | no accuracy claim |
| Design use | not approved | prohibited |

## 6. Validation ladder

Each use case advances through the same staged ladder.

### V0 — scope and conservation checks

- inputs remain inside property and phase scope;
- solver guards are explicit;
- mass, momentum, energy, and vapor accounting close.

### V1 — numerical characterization

- CFL and mesh sensitivity;
- event and guard repeatability;
- front, peak, and timing envelopes;
- local oscillation characterization.

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

## 7. Selected first pilot — U3 depressurization / blowdown

U3 is selected as the first pilot application because:

1. it is closest to the existing 5→2 MPa verification analogue;
2. it directly exercises crossing, propagation, acoustic, quality, and vapor-inventory behavior already under review;
3. it avoids adding pump inertia and full valve-network reflection complexity at the first application step;
4. it creates reusable discharge-boundary and thermal capabilities needed by later ESD and relief studies;
5. it provides a clear path from simplified verification to physical benchmark validation.

This selection does **not** mean the current prescribed-subcooled outlet is accepted as a blowdown boundary.

### Pilot progression

```text
P0 — existing prescribed-boundary verification analogue
P1 — fixed physical orifice / discharge-boundary benchmark
P2 — add friction and wall thermal inventory under controlled evidence
P3 — integrated pipe + blowdown device benchmark
P4 — physical-data validation
P5 — sensitivity-bounded engineering screening review
```

### Pilot decision outputs

```text
depressurization time
pressure envelope
crossing time and position
phase-region extent and propagation
vapor-generation and inventory envelope
maximum q_eq / alpha
discharge-flow history
solid-CO2 approach warning
CFL / mesh / boundary-model sensitivity
```

## 8. Mapping numerical gates to engineering decisions

| Numerical work | Engineering risk reduced |
|---|---|
| Gate 8 post-crossing CFL sensitivity | timing, front speed, chatter frequency, peak / phase-event timing |
| post-crossing mesh sensitivity | front position, front thickness, local peak q / alpha, spatial localization |
| local flux / acoustic contribution analysis | interpretation of chatter and Rusanov branch coupling |
| physical discharge-boundary benchmark | blowdown rate and pressure-history credibility |
| heat-transfer / wall-inventory study | temperature and vapor-generation credibility |
| HEM / non-equilibrium comparison | flashing-delay and rapid-depressurization applicability |
| physical validation | accuracy and design-use envelope |

## 9. Two-track roadmap

### Track N — numerical and model characterization

```text
Gate 8 post-crossing CFL sensitivity
→ post-crossing mesh sensitivity
→ local flux / acoustic contribution discrimination
→ longer-duration continuation
→ HEM / non-equilibrium comparison
```

### Track A — application and validation

```text
U3 pilot specification
→ physical discharge-boundary benchmark
→ thermal / friction / elevation extensions
→ integrated blowdown case
→ validation data comparison
→ engineering-screening review

U1 and U2 component specifications proceed in parallel but do not bypass the common numerical and validation ladder.
```

## 10. Governance decision

```text
application_specification_complete = true
real_problem_pilot_selected = true
selected pilot = U3 pipeline depressurization / blowdown
Gate 8 = next active numerical gate

ESD_design_use_approved = false
pump_trip_design_use_approved = false
blowdown_design_use_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

This strategy authorizes planning and controlled verification only. It does not authorize a production model, equipment-model claim, physical-accuracy claim, or engineering design decision.