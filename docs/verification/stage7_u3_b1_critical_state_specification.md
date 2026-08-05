# Stage 7 U3 B1 — Single-phase compressible critical-state specification

## Status

```text
contract:                     LOCKED BEFORE RESULTS
scope:                        verification-only component benchmark
reference implementation:     NOT STARTED
adapter implementation:       NOT STARTED
two-phase choking approval:   false
physical validation:          false
design use:                   false
```

Authoritative machine-readable contract:

- [`stage7_u3_b1_critical_state_contract_v1.json`](stage7_u3_b1_critical_state_contract_v1.json)

## Purpose

B0 verified the small-pressure-drop, subcooled-liquid orifice limit. B1 adds compressibility and a reproducible single-phase critical-state search before any two-phase discharge law or finite-pipe coupling is introduced.

The B1 component must answer two distinct questions without conflating them:

```text
1. Does the compressible law recover the accepted B0 liquid limit for a small pressure drop?
2. Does a clearly single-phase gas path exhibit an interior maximum mass flux and a choked plateau?
```

For this reason, the contract fixes two upstream state families.

## Upstream state families

### LIQUID_LIMIT

```text
p0 = 5 MPa
T0 = Tsat(p0) - 5 K
purpose = B0 limiting comparison and unchoked liquid path only
critical-state search = not required
```

This state preserves direct traceability to the accepted B0 case. The retained path may not be extended through a two-phase state.

### GAS_CRITICAL

```text
p0 = 1 MPa
T0 = 320 K
purpose = single-phase gas critical-state and choking benchmark
critical-state search = required
```

This family isolates the critical-state algorithm from liquid-to-two-phase transition physics. A two-phase candidate is a formal scope failure, not an alternative branch.

## Retained equations

At a candidate pressure `p`, the independent reference will evaluate the isentropic state from

```text
s(p) = s0
h = h(p, s0)
rho = rho(p, s0)
```

The thermodynamic and effective stream quantities are separated:

```text
u_ideal = sqrt(2 * (h0 - h))
u_eff   = Cd * u_ideal
G_ideal = rho * u_ideal
G_eff   = rho * u_eff
m_dot   = Aeff * G_eff
```

The retained outward-positive component transfers are

```text
mass transfer            = m_dot
momentum stream transfer = m_dot * u_eff
energy transfer          = m_dot * h0
```

This coefficient placement is deliberate. It retains the B0 effective-velocity convention in the small-drop liquid limit and makes the critical pressure independent of a constant `Cd`.

Static pressure-force mapping remains outside B1 and is deferred to a future finite-volume face adapter.

## Critical-state search

The GAS_CRITICAL path uses a deterministic two-stage search.

### Coarse search

```text
pressure ratio range: 1.00 down to 0.05
nodes:                4097
spacing:              uniform in pressure ratio
argmax tie rule:      choose the highest pressure
```

Every candidate must remain in the fixed single-phase phase allowlist and must produce finite positive density and a positive kinetic-energy head.

### Refinement

The coarse maximum must have one admissible neighbor on each pressure side. The retained bracket is refined with deterministic golden-section maximization in pressure.

```text
pressure bracket tolerance: 1 Pa
maximum iterations:         128
final tie rule:             choose the highest pressure
```

If the maximum lies at the retained path boundary, the search is not declared critical. The formal result is `CRITICAL_SEARCH_NOT_BRACKETED`.

## Back-pressure classification

```text
pb > p0
  → REVERSE_PRESSURE_NOT_SUPPORTED

pb = p0
  → SUCCESS_ZERO_PRESSURE_DROP

pb > pcrit + 1 Pa
  → SUCCESS_UNCHOKED_SINGLE_PHASE_DISCHARGE
  → evaluate the exit state at pb

pb <= pcrit + 1 Pa
  → SUCCESS_CHOKED_SINGLE_PHASE_DISCHARGE
  → evaluate the exit state at pcrit
```

Below the critical pressure, further back-pressure reduction must not change the retained mass flow or stream transfers beyond the locked plateau tolerance.

## Fixed benchmark matrix

The contract freezes 17 rows before the first result is viewed.

```text
B1-01  closed identity
B1-02  zero-pressure-drop identity
B1-03  B0 small-drop limiting comparison
B1-04A/B unchoked back-pressure ordering
B1-05  interior critical-state search
B1-06A/B below-critical plateau
B1-07A/B area scaling
B1-08A/B Cd scaling and critical-pressure independence
G-01   reverse pressure
G-02   nonfinite input
G-03   upstream phase-scope failure
G-04   nonpositive kinetic-energy head
G-05   unbracketed critical search
```

The synthetic guard rows exist so that failure paths are tested without forcing a real-fluid state into an artificial condition.

## Locked comparison requirements

### B0 limit

The B1 small-drop liquid case is compared against accepted B0 case `B0-03` for

```text
mass flow
 effective stream velocity
momentum stream transfer
energy transfer
```

The tolerances are fixed in the JSON contract before B1 execution.

### Critical state and plateau

The independent reference and later adapter must agree on

```text
critical pressure
critical effective mass flux
mass flow
momentum stream transfer
energy transfer
formal outcome
```

The below-critical cases must retain a common plateau. Area and `Cd` ratios must remain exactly the predeclared 2:1 ratios within the locked numerical tolerance.

## Independent implementation boundary

The work order is fixed:

```text
1. contract and tolerances
2. independent reference evaluator
3. authoritative reference artifact
4. verification-only adapter
5. reference / adapter comparison
```

The reference and adapter may not share

```text
critical-search helper
property-path helper
transfer-construction helper
```

The adapter may consume the immutable reference artifact but may not import the reference implementation.

## Required evidence

The final B1 evidence set must include candidate-state and back-pressure histories, critical-state summary, B0 comparison, scaling checks, guards, transfers, plots, JUnit, runtime provenance, Git provenance, and SHA256 manifests exactly as listed in the contract.

## Approval boundary

A successful B1 result would establish only an accepted **single-phase compressible component benchmark**.

It would not establish

```text
two-phase HEM critical-discharge accuracy
non-equilibrium flashing accuracy
physical discharge boundary approval
finite-pipe coupling
integrated blowdown approval
physical validation
design-use acceptance
production HEM activation
```

Current state after this contract increment:

```text
u3_b1_contract_locked = true
u3_b1_reference_implemented = false
u3_b1_adapter_implemented = false
u3_b1_component_benchmark_execution_complete = false
u3_b1_component_benchmark_accepted = false
```
