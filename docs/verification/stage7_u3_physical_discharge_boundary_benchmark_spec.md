# Stage 7 U3 — Physical Discharge-Boundary Benchmark Specification Skeleton

## Status — component benchmark contract under development

```text
application track:                 Track A / U3 pipeline depressurization
pilot progression:                 P1 physical discharge-boundary benchmark
validation ladder:                 V2 component-level benchmark
implementation status:             NOT STARTED
reference-data status:             NOT SELECTED
acceptance tolerances:              NOT LOCKED
integrated pipe coupling:           OUT OF SCOPE FOR THIS INCREMENT
physical validation:                NOT ESTABLISHED
design-use acceptance:              NOT APPROVED
production HEM activation:          NOT APPROVED
```

Related records:

- Issue #104 — Stage 7 real-problem application strategy;
- Issue #105 — Gate 8 post-crossing CFL sensitivity;
- [`stage7_real_problem_application_strategy.md`](stage7_real_problem_application_strategy.md);
- [`stage7_gate8_post_crossing_cfl_sensitivity_plan.md`](stage7_gate8_post_crossing_cfl_sensitivity_plan.md).

## 1. Purpose

Define the minimum independently benchmarkable discharge-boundary contract required before the U3 pilot can replace the current prescribed-subcooled outlet with a physical blowdown element.

The first benchmark isolates the boundary component from pipe propagation. It must answer three separate questions without using the pipeline solution to hide a boundary error:

1. Does the component return the correct mass-flow branch for a specified upstream reservoir state, effective area, discharge coefficient, and receiving pressure?
2. Does it identify unchoked and choked operation consistently with an independent reference calculation?
3. Are mass, momentum, and total-energy transfers exposed in a form that closes the finite-volume boundary budget?

This document is a specification skeleton. Numerical tolerances, final reference datasets, and approval criteria must be locked in a dedicated implementation contract before executed results are interpreted.

## 2. Scope boundary

### In scope

```text
pure CO2
one discharge element
one upstream stagnation / reservoir state
one downstream back pressure or fixed receiving pressure
prescribed effective-area / opening history
forward discharge only in the first benchmark
single-phase liquid limiting law
compressible equilibrium-nozzle reference path
unchoked / choked branch selection
mass / momentum / energy boundary flux accounting
explicit property, phase, reverse-flow, and solid-CO2 guards
verification-only artifacts and provenance
```

### Out of scope

```text
coupled finite pipe propagation
Gate 8 phase-front or chatter interpretation
valve-body multidimensional flow
empirical two-phase critical-flow correlation selection
non-equilibrium nucleation or flashing delay
non-condensable gas
receiver pressure dynamics
wall heat transfer
friction or elevation in the connected pipe
solid-CO2 transport
relief-device certification
design sizing or production activation
```

## 3. Boundary input contract

The component accepts an immutable input record for each evaluation:

```text
fluid identifier                         pure CO2
property backend and version             fixed by benchmark contract
upstream stagnation pressure             p0 [Pa]
upstream stagnation temperature          T0 [K]
upstream stagnation enthalpy              h0 [J/kg]
upstream stagnation entropy               s0 [J/(kg K)]
upstream phase / scope classification     explicit
receiving / back pressure                 pb [Pa]
reference flow area                       Aref [m2]
opening fraction                          f_open in [0, 1]
effective area                            Aeff = Aref * f_open
discharge coefficient                    Cd
flow-direction convention                positive out of the modeled domain
requested evaluation time                t [s]
```

The benchmark must not infer missing thermodynamic inputs from an unrelated pipeline cell. An upstream-state provider may derive `h0` and `s0` from the fixed `p0, T0` pair, but the retained artifact must record all four values.

## 4. Reference model hierarchy

The implementation is developed and checked in two ordered levels. Passing the simple limit is required before the compressible / choking branch is interpreted.

### B0 — subcooled single-phase liquid limiting law

For a liquid state that remains demonstrably single phase over the prescribed pressure drop, retain the standard incompressible-orifice limit:

```text
Delta_p = p0 - pb
m_dot_ref = Cd * Aeff * sqrt(2 * rho0 * Delta_p)
```

Required behavior:

- `Delta_p <= 0` does not silently produce forward flow;
- `Aeff = 0` produces exact zero mass flow;
- mass flow is linear in `Cd` and `Aeff`;
- mass flow follows the square-root pressure-drop limit within the locked benchmark tolerance;
- the case is refused if the assumed single-phase liquid path is not valid.

B0 is a software and limiting-law benchmark. It is not accepted as the final physical CO2 blowdown closure.

### B1 — compressible equilibrium nozzle / critical-discharge reference

Treat the upstream state as a stagnation state and construct an equilibrium, adiabatic, reversible reference expansion. For a trial exit pressure `p`:

```text
s(p) = s0
h(p) = h(p, s0)
u(p) = sqrt(2 * (h0 - h(p)))
rho(p) = rho(p, s0)
G(p) = rho(p) * u(p)
m_dot(p) = Cd * Aeff * G(p)
```

The reference critical state is the admissible pressure that maximizes `G(p)` along the fixed isentrope while remaining inside the declared property and phase scope.

```text
p_star = argmax G(p),  p in admissible interval [p_min, p0]
```

Branch rule:

```text
if pb > p_star:
    unchoked; evaluate at p_exit = pb
else:
    choked;   evaluate at p_exit = p_star
```

The retained evidence must include the search interval, admissible sample / solve history, maximizing state, branch decision, and any rejected property states. A hidden backend optimization result without this trace is not acceptable benchmark evidence.

This B1 definition is an equilibrium reference path only. Agreement with it does not validate real two-phase CO2 critical discharge or authorize an HEM accuracy claim.

## 5. Component output contract

Every successful boundary evaluation returns:

```text
formal outcome
flow branch                              CLOSED / UNCHOKED / CHOKED
mass-flow rate                           m_dot [kg/s]
exit pressure                            p_exit [Pa]
exit temperature                         T_exit [K]
exit density                             rho_exit [kg/m3]
exit velocity                            u_exit [m/s]
exit enthalpy                            h_exit [J/kg]
exit entropy                             s_exit [J/(kg K)]
exit equilibrium quality                 q_eq, when defined
exit void fraction                       alpha, when defined
exit phase / scope classification
critical pressure                        p_star [Pa], when evaluated
critical mass flux                       G_star [kg/(m2 s)], when evaluated
choking margin                           pb - p_star [Pa]
mass flux into FVM boundary              signed conservative value
momentum flux into FVM boundary          signed conservative value
energy flux into FVM boundary            signed conservative value
guard / refusal category and reason
property-backend call provenance
```

For an adiabatic boundary with no shaft work, the energy-transfer reference is based on upstream stagnation enthalpy:

```text
E_dot_ref = m_dot * h0
```

The implementation contract must define the exact sign convention and pressure-force treatment used to map the component result to the finite-volume interface flux. Component flow-rate agreement without conservative boundary accounting is insufficient.

## 6. Mandatory guard outcomes

The first implementation must fail explicitly rather than clip, extrapolate, or substitute another model for:

```text
NONFINITE_INPUT
NONPOSITIVE_UPSTREAM_DENSITY
BACK_PRESSURE_ABOVE_UPSTREAM / REVERSE_FLOW_NOT_SUPPORTED
OPENING_OUTSIDE_UNIT_INTERVAL
NONPOSITIVE_AREA_OR_DISCHARGE_COEFFICIENT, except exact closed area
UPSTREAM_STATE_OUTSIDE_DECLARED_PHASE_SCOPE
PROPERTY_BACKEND_FAILURE
NO_ADMISSIBLE_ISENTROPIC_PATH
CRITICAL_STATE_NOT_BRACKETED
SOLID_CO2_APPROACH_GUARD
UNSUPPORTED_TWO_PHASE_CRITICAL_FLOW_MODEL
CONSERVATIVE_FLUX_CONSTRUCTION_FAILURE
```

No quality clipping, one-sided acoustic substitution, hidden fallback to the prescribed-subcooled boundary, or result-dependent change of the search interval is permitted.

## 7. Fixed benchmark families to lock before execution

The implementation PR must replace the placeholders below with exact states, units, solve intervals, and tolerances before results are generated.

| ID | Purpose | Required comparison |
|---|---|---|
| B0-01 | closed element | exact zero flow and zero transfer |
| B0-02 | zero pressure drop | exact zero forward flow |
| B0-03 | small subcooled-liquid pressure drop | incompressible-orifice limiting law |
| B0-04 | area scaling | `m_dot` proportional to `Aeff` |
| B0-05 | discharge-coefficient scaling | `m_dot` proportional to `Cd` |
| B1-01 | unchoked compressible discharge | exit state evaluated at `pb` |
| B1-02 | back-pressure sweep | monotone flow increase before choking |
| B1-03 | critical plateau | flow independent of further `pb` reduction within tolerance |
| B1-04 | critical-state search reproducibility | same `p_star` and `G_star` across fixed search refinements |
| B1-05 | energy transfer | `E_dot = m_dot h0` and discrete budget closure |
| B1-06 | prescribed opening history | quasi-steady area response without state-history leakage |
| G-01 | reverse pressure | explicit forward-only guard |
| G-02 | property failure | categorized backend refusal |
| G-03 | solid-CO2 approach | explicit scope guard |
| G-04 | unsupported two-phase critical-flow request | explicit model-scope refusal |

The matrix must include at least one state comfortably away from saturation and at least one state near the intended U3 operating envelope. Near-saturation cases are not permitted to weaken B0 assumptions retroactively.

## 8. Independent reference requirement

At least one reference path must be independent of the production boundary implementation.

Permitted reference sources, in order of preference:

1. a compact analytical / numerical reference evaluator implemented outside the production boundary class;
2. a published or trusted-code equilibrium-nozzle benchmark with fully specified inputs;
3. controlled experimental component data with uncertainty bounds.

Using the same helper function for both the implementation and the expected answer is not an independent benchmark.

## 9. Acceptance evidence

Each benchmark row must retain:

```text
complete immutable input record
formal outcome and branch
reference result
implementation result
absolute difference
normalized difference
locked acceptance tolerance
property / phase / scope history
critical-search history where applicable
mass / momentum / energy transfer residuals
runtime and Git provenance
accepted-state / result SHA256
```

Required aggregate checks:

```text
closed and zero-Delta-p identities
area and Cd scaling identities
unchoked back-pressure trend
critical plateau behavior
critical-search repeatability
energy-transfer consistency
finite-volume boundary-budget closure
all guard categories exercised
no authoritative skips, failures, or errors
```

No tolerance may be selected after viewing the executed error distribution.

## 10. Artifact contract

```text
summary.json
benchmark_cases.csv
critical_search_history.csv
property_scope_history.csv
conservative_flux_budget.csv
guard_outcomes.csv
report.md
mass_flow_vs_back_pressure.png
mass_flux_vs_exit_pressure.png
critical_state_search.png
energy_transfer_residual.png
JUnit evidence
runtime / Git provenance
artifact_sha256.txt
```

## 11. Staged implementation sequence

```text
D1 — lock signs, units, data classes, and formal outcomes
D2 — implement B0 independent liquid-orifice reference and tests
D3 — implement B1 independent isentropic equilibrium reference search
D4 — implement verification-only discharge boundary adapter
D5 — compare adapter against B0 / B1 matrix and close conservative budgets
D6 — freeze component benchmark evidence and review applicability
D7 — only after component acceptance, connect to a controlled finite pipe
```

The initial component benchmark uses a reservoir-style upstream state. It must not be coupled to Gate 8 post-crossing states in D1–D5. This separation prevents pipeline numerical behavior from being mistaken for discharge-boundary validation.

## 12. Interface with Gate 8

Gate 8 and the U3 discharge-boundary benchmark reduce different risks:

```text
Gate 8:     time-step sensitivity of the existing prescribed-boundary post-crossing path
U3 P1/V2:   correctness and conservative consistency of a physical discharge element
```

They may proceed in parallel, but neither supplies the missing approval of the other. In particular:

- a successful discharge-component benchmark does not approve phase-front speed or chatter;
- a stable Gate 8 CFL trend does not validate blowdown mass flow;
- the prescribed-subcooled outlet remains a verification analogue until the physical boundary is independently benchmarked;
- integrated U3 pipeline work begins only after both numerical and component evidence are explicitly reviewed.

## 13. Approval boundary

```text
u3_discharge_boundary_specification_complete = false
u3_discharge_boundary_implementation_complete = false
u3_component_benchmark_execution_complete = false
u3_component_benchmark_accepted = false
physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
