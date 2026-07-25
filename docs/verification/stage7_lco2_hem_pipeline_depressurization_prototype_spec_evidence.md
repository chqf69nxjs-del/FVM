# Stage 7 — Pipeline-Depressurization Prototype Specification Evidence

## Status

`VALIDATED SPECIFICATION; BOUNDARY ADAPTER NOT IMPLEMENTED; PIPELINE RUN NOT EXECUTED`

This record retains the authoritative validation evidence for the first narrow LCO2
pipeline-depressurization prototype specification.

## Validation environment

```text
validated head:            8640d6f73421ec3d4b7bf64b20e09f7445d32149
workflow run:              30135136669
artifact ID:               8612546071
artifact SHA256:           5b2e391e32b984eab82c6e5d316add05c54f9e2ecc411580523e1f4323b1b69b
CoolProp:                  8.0.0
compileall:                success
JSON parse:                success
git diff --check:          success
specification tests:       9 passed, 0 skipped
frozen Case A/B tests:    14 passed, 0 skipped
full repository:         651 passed, 0 skipped
failures / errors:          0 / 0
```

The artifact retains the three Markdown specifications, the machine-readable JSON contract,
all JUnit XML files, and the validation summary.

## Fixed specification result

The first boundary-driven prototype is defined as:

```text
pipe:                  horizontal 1.0 m x 0.10 m
cells:                 32
initial state:         uniform 5 MPa / 5 K subcooled liquid
initial u / q:         0 m/s / 0 exactly
left boundary:         reflective
right boundary:        prescribed subcooled outlet, outlet_only
flux / order / CFL:    existing Rusanov / first order / 0.10
sources:               none
```

The selected right-boundary thermodynamic closure is:

```text
p_b(t) prescribed
T_b(t) = T_sat(p_b(t)) - 5 K
rho_b/e_b from CoolProp P,T
q_b = equilibrium quality of the exact rho_b/e_b state
required boundary region = LIQUID_CANDIDATE
```

Pressure-only real-fluid inversion and copying interior transported quality into the ghost
state are explicitly forbidden.

## Fixed schedule matrix

All cases use a one-initial-acoustic-time linear ramp and a maximum three-acoustic-time
horizon.

```text
2 MPa: first-crossing candidate
3 MPa: moderate diagnostic
4 MPa: liquid negative control
```

The schedule path must pass a 65-point canonical property, phase, acoustic, and mixed-EOS
preflight before an FVM run is allowed.

## Fixed stop and acceptance logic

Explicit outcomes:

```text
ACCEPTED_FIRST_CROSSING
NO_CROSSING_WITHIN_HORIZON
ENDPOINT_LANDING
FORBIDDEN_TRANSITION
REVERSE_FLOW_GUARD
GUARD_FAILURE
BACKEND_FAILURE
```

A crossing is accepted only when:

```text
boundary preflight passed
reverse-flow fallback count = 0
endpoint and forbidden counts = 0
crossing cells = projection cells
at least one crossing q_eq >= 1e-6
post q = q_eq
post mixed EOS succeeds
second projection is a no-op
boundary and phase-vapor budgets close
```

The first gate permits a boundary-adjacent internal crossing but does not approve an
interface-propagation speed.

## Implementation staging

```text
Increment 1:
boundary state provider + outlet adapter + 65-point path preflight
no FVM time step

Increment 2:
fixed 2/3/4 MPa short-run matrix + first-crossing stop + budgets
```

The boundary construction and transient runner remain separate so property/boundary failure
cannot be confused with FVM failure.

## Frozen regression protection

The PR #72 Case A/B state and repeatability hashes are retained in the contract and must pass
before and after both implementation increments.

## Approval boundary

```text
verification_only = true
prototype_specification_validated = true
boundary_adapter_implemented = false
pipeline_depressurization_executed = false
interface_propagation_speed_verified = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
```
