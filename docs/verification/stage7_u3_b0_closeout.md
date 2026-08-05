# Stage 7 U3 B0 Closeout — Single-phase discharge component benchmark

## Status

```text
Issue #109:                              COMPLETE
reference implementation:               PR #124 / MERGED
adapter comparison:                     PR #125 / MERGED
u3_b0_contract_locked:                  true
u3_b0_reference_implemented:            true
u3_b0_adapter_implemented:              true
u3_b0_component_benchmark_complete:     true
u3_component_benchmark_accepted:        true
```

B0 closes only the verification-only, subcooled single-phase liquid component benchmark. It does not approve a production FVM boundary or a physical CO2 blowdown model.

## Locked model level

```text
Delta_p = p0 - pb
Aeff    = Aref * f_open
m_dot   = Cd * Aeff * sqrt(2 * rho0 * Delta_p)
u_exit  = m_dot / (rho0 * Aeff)
M_dot   = m_dot * u_exit
E_dot   = m_dot * h0
```

The retained sign convention is positive outward from the modeled domain. Static pressure-force mapping is excluded from B0 and remains deferred to the later finite-volume boundary adapter.

## Independent reference authority

```text
PR:                    #124
main merge SHA:        b4442d3df1a7517539520f79d82b85ef1c5aaec0
workflow run:          30898882922
artifact ID:           8890056064
artifact ZIP SHA256:   7005055beb8b0722dd035f37c0fa6d10f46ddd121d6ead5906a8d941fb6c23a6
dedicated / related / full: 6 / 12 / 909 passed
skips / failures / errors:   0 / 0 / 0
```

## Adapter comparison authority

```text
PR:                    #125
source head SHA:       42f9bd8384ebc06604924fc34ba05b45813e6b48
main merge SHA:        3937a276f8fefb62f297caa0e679660ec0d4c421
workflow run:          30954035596
artifact ID:           8912067053
artifact ZIP SHA256:   4d7848ad06afd4765f37e102d155bc73df5663b3efb47a77513aa61410f6d7b2
dedicated / related / full: 7 / 13 / 916 passed
skips / failures / errors:   0 / 0 / 0
```

All 15 workflows triggered on the final PR head completed successfully.

## Fixed result matrix

```text
case count:                         10
success cases:                       7
guard cases:                         3
mass / momentum / energy compares: 30
comparison passes:                  30
formal outcomes match:              true
exact-zero identities retained:     true
```

The fixed families were:

```text
B0-01 CLOSED_ELEMENT
B0-02 ZERO_PRESSURE_DROP
B0-03 SUBCOOLED_LIQUID_LIMIT
B0-04A/B AREA_SCALING
B0-05A/B DISCHARGE_COEFFICIENT_SCALING
G-01 REVERSE_PRESSURE_NOT_SUPPORTED
G-02 OPENING_OUTSIDE_RANGE
G-03 SINGLE_PHASE_SCOPE_FAILURE
```

## CI isolation disposition

Two tests require the immutable reference artifact. In the authoritative adapter workflow, the artifact and a required flag are supplied, so all 916 repository tests execute. In unrelated workflows, the two tests are deselected rather than skipped. This preserves the repository zero-skip policy without weakening the authoritative B0 comparison.

## Supported claims

```text
independent reference and adapter are separate code paths
locked single-phase limiting law is reproduced
closed and zero-pressure-drop identities are exact
area and Cd scaling are retained
mass, momentum-stream, and enthalpy transfers follow the locked sign convention
invalid, reverse-pressure, and phase-scope rows are explicitly categorized
B0 component benchmark is accepted
```

## Claims not supported

```text
physical discharge boundary approved
static pressure-force/FVM face mapping approved
compressible critical-state search approved
two-phase choking accuracy approved
integrated pipeline blowdown approved
high-point flashing or pump-trip application approved
physical validation established
design use accepted
production HEM activation approved
```

## Next controlled work

Primary next development:

```text
U3 B1 — single-phase compressible / critical-state contract and reference
```

Parallel application-oriented specification candidates:

```text
gravity and elevation benchmark for high-point pressure minima
prescribed-head-decay pilot for pump-trip negative-pressure propagation
```

These parallel pilots may begin at specification and simplified numerical-verification level, but they do not bypass the separate requirements for rotating-inertia pump coupling, reverse-flow treatment, two-phase critical discharge, and physical validation.

## Approval boundary after B0

```text
u3_b0_contract_locked = true
u3_b0_reference_implemented = true
u3_b0_adapter_implemented = true
u3_b0_component_benchmark_execution_complete = true
u3_component_benchmark_accepted = true

physical_discharge_boundary_approved = false
two_phase_critical_discharge_accuracy_approved = false
integrated_blowdown_model_approved = false
high_point_flashing_design_use_approved = false
pump_trip_design_use_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
