# Stage 6 V-012 Single-Phase Internal Valve Verification Specification

## 1. Status and purpose

- verification item: `V-012 Single-phase valve operation`
- document status: specification-first draft
- implementation status: runner not yet approved by this document
- software / numerical verification: `true`
- physical Validation: `false`
- design evaluation: `false`
- acceptance gate: `false`
- property backend design status: `not_approved_for_design_use`

The purpose of V-012 is to verify the existing single-phase internal-valve
software path under controlled opening schedules. The verification must show
that the requested opening reaches the valve interface, the interface numerical
flux is recorded at the actual internal face, the flow direction and pressure
response are consistent with the implemented valve law, and the global
conservative budgets remain traceable.

This work does not establish fidelity to a real valve, reservoir, actuator,
ESD system, or operating plant.

## 2. Scope boundary

### Included

- the existing `InternalValveInterface` software path
- the existing single-phase opening / effective-Kv relation
- constant-opening observation
- small controlled opening ramp
- small controlled closing ramp
- internal-face mass, momentum, total-energy, and vapor-mass flux telemetry
- valve-adjacent diagnostic pressure, density, temperature, and velocity
- flow-direction and pressure-drop sign checks
- probe histories on both sides of the internal valve
- whole-domain mass, energy, and vapor-mass budgets
- single-phase health checks
- visualization, mesh/CFL observation, CI-light, report, and manifest in later PRs

### Excluded

- flashing or cavitation
- choked or critical discharge
- two-phase valve correlations
- HEM / HNE discharge modelling
- actuator mechanics, hysteresis, stiction, or travel-time Validation
- ESD events and emergency closure qualification
- pump trip
- equipment sizing or design acceptance
- comparison with vendor Cv/Kv test data

The existing Kv-style law is treated as a single-phase numerical idealization.
It must not be presented as a flashing, cavitating, choked, or two-phase valve
model.

## 3. Existing implementation constraints

The repository already contains an internal-valve interface and a diagnostic
hydraulic-loss path. V-012 shall use the existing implementation before any
solver-physics change is considered.

Known constraints that must remain explicit:

1. The hydraulic-loss proxy is diagnostic.
2. The current proxy is not interpreted as an approved removal of energy from
   the conserved `rhoE` equation.
3. A hydraulic-loss-power diagnostic therefore cannot, by itself, be used as an
   energy-dissipation acceptance gate.
4. Any proposal to change the valve law, momentum treatment, or total-energy
   treatment is a critical design decision and requires a separate owner review.
5. Cell-center or ghost-cell values shall not be substituted for actual
   internal-face numerical-flux telemetry.

The first runner PR must remain observational and avoid changes to governing
equations or solver conservation semantics.

## 4. Coordinate and sign convention

- pipe coordinate increases from left to right
- positive mass flow is left-to-right
- internal valve face is located at a documented physical coordinate and face
  index
- pressure drop is defined as

```text
delta_p_valve_pa = p_face_left_pa - p_face_right_pa
```

- positive valve flow is expected when `delta_p_valve_pa > 0`
- negative valve flow is expected when `delta_p_valve_pa < 0`
- zero pressure difference must not produce a material valve mass flux above the
  documented roundoff / numerical-noise scale

The exact same internal-face numerical flux must be used to update the two
adjacent control volumes with opposite signs. Two independently reconstructed
"left" and "right" valve fluxes are not accepted as evidence of conservation.

## 5. Verification cases

### V-012A — Uniform-state, constant-opening preservation

Purpose:

- confirm that introducing the internal valve into a uniform, stationary,
  single-phase state does not create a spurious pressure wave or net flow
- exercise opening, effective-Kv, interface registration, face telemetry, and
  budget accounting without a driving pressure difference

Initial candidate configuration:

- single-phase CO2
- `p0 = 8 MPa`
- `T0 = 280 K`
- uniform velocity `u0 = 0`
- valve near the pipe midpoint
- constant, nonzero opening
- transmissive or otherwise non-driving outer boundaries consistent with the
  existing uniform-state verification path

Primary observations:

- requested and actual opening are identical within schedule roundoff
- internal-face mass, momentum, energy, and vapor-mass fluxes are finite
- no material pressure or velocity disturbance is generated
- whole-domain budget residuals remain near the established machine-precision
  scale
- the run remains single phase

This is the first baseline to implement.

### V-012B — Small driven-flow, constant-opening baseline

Purpose:

- verify pressure-drop / flow-direction consistency
- compare the measured internal-face mass flux with the result predicted by the
  exact existing implementation-law helper
- establish valve-adjacent telemetry before time-varying opening is introduced

The driving pressure difference must be small enough to remain in the
single-phase, low-Mach, small-perturbation regime. Boundary forcing and the
observation window must be selected so that the valve response is not confused
with unrelated reflected waves.

Required observations:

- sign of mass flow agrees with sign of valve pressure drop
- the implementation-reference mass-flow prediction is recorded separately from
  the measured numerical flux
- measured and reference values are compared as an observation, not vendor-data
  Validation
- left and right adjacent-cell updates use one shared interface flux
- all primitive variables stay finite and positive
- single-phase state is retained
- whole-domain budgets close using the solver's documented boundary and internal
  interface accounting

### V-012C — Controlled opening ramp

Purpose:

- verify a small increase in opening under established single-phase flow
- confirm that schedule timing, effective Kv, internal-face flux, and upstream /
  downstream pressure responses evolve consistently

The opening change must be deliberately small. A fully closed-to-open startup is
not the first dynamic case.

### V-012D — Controlled closing ramp

Purpose:

- verify a small reduction in opening under established single-phase flow
- observe the expected reduction in mass flow and the associated pressure-wave
  response

The first closing case shall stop at a nonzero opening. Full closure is deferred
until the nonzero-opening path is understood.

### V-012E — Closed-limit observation

This is a later, separately reviewed case. It may examine whether the existing
interface approaches zero mass flow and a wall-like pressure response as opening
approaches zero.

It is not automatically equivalent to a real closed valve. If implementation of
zero opening requires changing boundary/interface meaning, solver physics, or
energy treatment, work must stop for owner review.

## 6. Opening schedule requirements

Every time-dependent case must distinguish:

- requested opening
- actual opening returned by the schedule / interface
- effective Kv or implementation-native flow coefficient
- schedule error

Opening is dimensionless and constrained to the implementation-supported closed
interval. The schedule must define behavior:

- before ramp start
- during ramp
- at ramp end
- after ramp end
- at exactly zero ramp duration, if supported

Pure unit tests shall cover endpoints, monotonicity, invalid ranges, and
floating-point roundoff behavior.

## 7. Internal-face telemetry

A `*_valve_history.csv` artifact shall contain at least:

```text
time_s
step
dt_s
valve_face_index
valve_x_m
requested_opening
actual_opening
opening_error
effective_kv
pressure_face_left_pa
pressure_face_right_pa
delta_p_valve_pa
velocity_face_left_m_s
velocity_face_right_m_s
density_face_left_kg_m3
density_face_right_kg_m3
temperature_face_left_K
temperature_face_right_K
sound_speed_face_left_m_s
sound_speed_face_right_m_s
mass_flux_kg_m2_s
momentum_flux_pa
energy_flux_w_m2
vapor_mass_flux_kg_m2_s
mass_flow_kg_s
energy_flow_w
vapor_mass_flow_kg_s
implementation_reference_mass_flow_kg_s
mass_flow_reference_relative_difference
flow_direction
hydraulic_loss_power_diagnostic_w
```

Field names may be adjusted to match established repository conventions, but
all listed meanings must remain available and documented.

The face pressures and velocities must be diagnostic internal-face quantities
used by, or directly derived from, the interface numerical-flux evaluation.
Cell-center values may be stored as supplementary data but cannot replace the
face quantities in a pass decision.

## 8. Probe and boundary telemetry

At least two probes are required:

- one upstream of the valve
- one downstream of the valve

A third probe on either side is recommended for wave-arrival interpretation.
Probe history shall include pressure, pressure perturbation, velocity,
temperature, density, sound speed, vapor mass fraction, and phase fraction.

The established `*_boundary_history.csv` schema shall remain active at both
outer boundaries so that domain exchange and valve response can be separated.

## 9. Budget requirements

Required whole-domain diagnostics:

- mass budget residual and normalized residual
- total-energy budget residual and normalized residual
- vapor-mass budget residual and normalized residual
- explicit external-boundary exchange
- documented internal-interface contribution semantics

The single shared conservative interface flux should cancel internally in the
whole-domain balance. Diagnostic hydraulic-loss power must be reported
separately unless and until the conserved-energy treatment is explicitly
approved.

A run shall not pass by subtracting an unimplemented diagnostic loss from the
energy budget after the fact.

## 10. Analysis metrics

### Execution and health

- target time reached
- maximum step count not exceeded
- finite histories
- positive pressure, temperature, density, and sound speed
- remained single phase
- no missing budget fields
- backend identity and version recorded
- `property_backend_design_status = not_approved_for_design_use`

### Valve-path metrics

- maximum absolute opening schedule error
- maximum absolute internal-face flux non-finiteness count, expected zero
- flow-direction sign consistency
- pressure-drop sign consistency
- implementation-reference mass-flow comparison
- shared-interface-flux consistency
- uniform-state spurious mass-flow scale for V-012A
- upstream and downstream pressure extrema and arrival times for dynamic cases

### Diagnostic-only metrics

- runtime and step count
- hydraulic-loss-power proxy
- cell-center-to-face differences
- waveform comparisons before formal bands are defined

No regression or acceptance band is defined in the specification PR.

## 11. Visualization requirements

Later runner / plotting PRs shall generate, at minimum:

1. requested opening, actual opening, and effective Kv versus time
2. valve pressure drop and mass flow versus time
3. upstream and downstream probe pressure histories
4. upstream and downstream velocity histories
5. internal-face mass, energy, and vapor-mass flow histories
6. implementation-reference versus measured mass flow
7. budget residual histories or summary visualization

For opening and closing ramps, theoretical schedule transition times and
observed response windows shall be marked.

## 12. Artifacts

Each run shall produce:

```text
*_config.json
*_metrics.json
*_valve_schedule.csv
*_valve_history.csv
*_probe_history.csv
*_boundary_history.csv
*_final_profile.csv
*_observation_report.md
```

Plotting may produce PNG files from the CSV/JSON artifacts. Mesh/CFL aggregation,
CI-light results, formal report, and SHA256 manifest are later deliverables and
must not be added before baseline behavior is reviewed.

## 13. Test plan

### Pure tests

- opening schedule endpoint and monotonicity tests
- invalid opening and duration tests
- flow-direction sign helper tests
- implementation-reference valve-law helper tests
- valve-history schema tests
- missing-field failure tests
- zero-pressure-drop / zero-flow synthetic tests
- shared-interface-flux accounting tests

### Installed CoolProp tests

- V-012A short uniform-state run
- V-012B short constant-opening driven-flow run after specification review
- no skip when CoolProp is installed
- backend identity and design-status assertions

## 14. Stop conditions

Work must be saved and stopped for owner review if any of the following occurs:

- governing-equation or solver-physics changes are required
- the valve flow law must be changed to obtain the expected result
- total-energy treatment must be changed
- a diagnostic hydraulic-loss term would need to be presented as conservative
  energy removal
- one shared internal-face flux is not available for both adjacent updates
- only cell-center or ghost values are available as substitutes for face
  telemetry
- the case leaves the single-phase regime
- non-finite or non-positive thermodynamic states occur
- a result would require widening a regression band, once such a band exists
- destructive Git history changes would be required

## 15. Planned PR sequence

### PR V12-A — specification and code-path survey

- this document
- exact symbol / file survey for the existing internal-valve path
- telemetry and artifact schema confirmation
- no solver change
- MASTER index and Stage 6 log synchronization

### PR V12-B — telemetry and V-012A baseline

- internal-face valve telemetry
- constant-opening uniform-state runner
- synthetic and installed-CoolProp tests
- no mesh/CFL or formal bands

### PR V12-C — driven-flow baseline and controlled ramps

- V-012B, V-012C, and V-012D runners
- diagnostic plots
- observation notes

### PR V12-D — mesh/CFL observation

- de-duplicated run matrix
- observation-only trends
- no formal acceptance band

### PR V12-E — formalization

- broad CI-light software-regression bands
- GitHub Actions
- formal report and SHA256 manifest
- review for `V-012 COMPLETE`

## 16. Completion criteria

V-012 may be marked `COMPLETE` only after:

- the specification is merged
- the constant-opening and controlled-ramp paths are implemented and reviewed
- actual internal-face telemetry is present
- single-phase and conservation health are demonstrated
- mesh/CFL observations are documented
- CI-light runs without skip on installed CoolProp
- formal report and SHA256 manifest are generated
- limitations and backend status remain explicit
- the final status change is reviewed
