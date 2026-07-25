# Stage 7 — Minimal Pipeline-Depressurization Prototype Validation Plan

## Status

`SPECIFICATION VALIDATION PLAN; NO PROTOTYPE RUN YET`

This plan defines how the two implementation increments authorized by the prototype
specification will be checked.

References:

- [`stage7_lco2_hem_pipeline_depressurization_prototype_spec.md`](stage7_lco2_hem_pipeline_depressurization_prototype_spec.md)
- [`stage7_lco2_hem_pipeline_depressurization_boundary_contract.md`](stage7_lco2_hem_pipeline_depressurization_boundary_contract.md)
- [`stage7_lco2_hem_pipeline_depressurization_prototype_contract_v1.json`](stage7_lco2_hem_pipeline_depressurization_prototype_contract_v1.json)

---

## 1. Validation layers

The prototype is validated in five separate layers.

```text
Layer 0: specification integrity
Layer 1: boundary-state property path
Layer 2: ghost-cell boundary adapter
Layer 3: short FVM depressurization runner
Layer 4: frozen Case A/B non-regression
```

A later layer may not be used to hide failure in an earlier layer.

---

## 2. Layer 0 — specification integrity

The specification PR shall add a dependency-free test that loads the JSON contract and
checks its fixed invariants.

Required checks:

```text
schema and verification-only status
1 m / 0.10 m / 32-cell geometry
dx = L / n_cells
first-order Rusanov and CFL 0.10
uniform 5 MPa / 5 K / q=0 initial liquid state
left reflective boundary
right outlet-only pressure-plus-subcooling boundary
copy velocity and equilibrium-quality ghost policies
pressure-only inversion and copied interior quality forbidden
2 / 3 / 4 MPa fixed matrix
one acoustic-time ramp and three-acoustic-time horizon
65-point path preflight
existing endpoint/projection/accepted-quality tolerances
fixed stop priority and outcomes
budget tolerances
frozen PR #72 hashes and signatures
all production, Validation, design-use, and acoustic approvals false
```

The Markdown specifications must reference the machine-readable contract.

---

## 3. Layer 1 — boundary-state property path

### 3.1 Dependency-free tests

Use fake property and phase evaluators to exercise:

```text
pressure schedule validation
positive subcooling validation
P/subcooling -> prescribed state record
round-trip mismatch detection
unsupported phase rejection
negative-energy rejection
acoustic failure propagation
cache exact-key behavior
whole-path atomic failure
```

These tests verify control flow only. They do not stand in for CoolProp evidence.

### 3.2 Installed-CoolProp scalar states

Evaluate fixed 5 K subcooled states at:

```text
5 MPa
4 MPa
3 MPa
2 MPa
```

For each state require:

```text
finite positive rho, p, T, c
finite non-negative e
q_eq = 0
region = LIQUID_CANDIDATE
scope = supported_candidate
mixed accepted-state EOS succeeds
pressure and temperature round trip within contract tolerance
```

No installed-CoolProp test may be skipped in the authoritative workflow.

### 3.3 Full schedule preflight

For each linear schedule:

```text
5 -> 2 MPa
5 -> 3 MPa
5 -> 4 MPa
```

sample 65 points and require:

```text
65 accepted liquid samples
0 endpoints
0 open-two-phase boundary samples
0 vapor samples
0 guarded samples
0 backend failures
```

Retain a CSV and JSON record of every sample.

---

## 4. Layer 2 — ghost-cell boundary adapter

### 4.1 Right-side application

With a synthetic interior accepted state and two ghost cells:

```text
adapter writes both right ghost cells
ghost states are identical
interior cells are bitwise unchanged
ghost rho/e/q come from the provider
ghost velocity copies adjacent interior velocity
```

### 4.2 Quality consistency

Use a two-phase adjacent interior cell with positive transported quality while the provider
returns subcooled liquid `q_eq=0`.

Require:

```text
ghost q = 0
ghost q is not copied from the interior
mixed accepted-state EOS accepts the ghost
```

This test protects the key difference from the generic `PressureTankBoundary` helper.

### 4.3 Flow policy

At the right boundary:

```text
u_i > 0: prescribed outlet state is active
u_i = 0: prescribed outlet state is active
u_i < 0: reflective fallback is active
```

Require exact reflection of momentum in the fallback and one increment of the reverse-flow
counter.

### 4.4 Rusanov face smoke test

Construct one accepted interior state and the prescribed ghost state, then call the existing
Rusanov flux.

Require:

```text
flux vector shape is correct
all flux components finite
EOS accepts both sides
wave speed finite and positive
```

This is a face-level smoke test, not a pipe transient.

---

## 5. Layer 3 — short FVM depressurization runner

### 5.1 Fixed matrix

Use exactly:

```text
32 cells
1.0 m length
0.10 m diameter
CFL 0.10
left reflective
right prescribed subcooled outlet
5 MPa / 5 K uniform initial liquid
linear ramp over one initial acoustic time
2, 3, and 4 MPa final-pressure cases
maximum horizon = three initial acoustic times
maximum steps = 2000
```

### 5.2 Per-step assertions

Before the first crossing:

```text
current accepted EOS succeeds
boundary schedule state succeeds
CFL dt is finite and positive
raw conserved state is finite and physical
raw phase detection succeeds
no unsupported transition is silently ignored
projection returns a finite state
post mixed EOS succeeds
second projection is a no-op
budgets remain within tolerance
```

### 5.3 Crossing candidate result

The 2 MPa case is successful only if it produces `ACCEPTED_FIRST_CROSSING` under the fixed
contract.

Record:

```text
crossing step and time
crossing cell indices
crossing distance from outlet
raw and post rho/e/p/T/q/alpha/c
first projection cells and delta q
second projection count
boundary and phase-vapor contributions
pressure-wave threshold arrival times
```

If it does not cross, record `NO_CROSSING_WITHIN_HORIZON`; do not tune the case in the same
PR.

### 5.4 Moderate diagnostic

The 3 MPa case may cross or remain liquid. Its result is diagnostic and must be retained
without changing acceptance rules.

### 5.5 Liquid control

The 4 MPa case is intended as the first boundary-driven liquid control. The first runner PR
shall report whether it stays liquid over the fixed horizon.

Formal freezing of a boundary-driven control is a later gate. The current PR #72 Case B
remains the authoritative regression control until then.

---

## 6. Layer 4 — frozen Case A/B non-regression

Before and after boundary-adapter and runner changes, execute the PR #72 regression pair.

Required exact evidence:

```text
Case A final state SHA256:
78897b5c8ca57221186ccf3e0aa69e1492a942cc2e8dee0abb440a3e2e08e039

Case A signature:
914ed2249c9546a1d32f6d6dbcd8b30236e1c1f2b37ecf9306100ad30622b612

Case B final state SHA256:
8c09735ee9185cfb34b2186be30b32d78ec73350e211762d92c372e0b9f23a59

Case B signature:
3bd7edc37842a00a0c27964a17029f5c66ef973b59bd7670f513c82fc7e85669
```

A mismatch blocks merge unless separately explained and reviewed. The signatures may not be
updated inside the prototype PR merely to make CI pass.

---

## 7. Budget checks

### 7.1 Boundary budgets

For mass, momentum, and energy:

```text
residual tolerance = max(fixed absolute tolerance, 1e-10 * budget scale)
```

Use the fixed absolute tolerances in the JSON contract.

### 7.2 Vapor accounting

Require all three diagnostics:

```text
boundary-only vapor residual
phase-projection vapor residual
combined boundary-plus-phase vapor residual
```

The combined residual must be within `1e-12 kg`.

### 7.3 Left reflective face

Require cumulative left mass and energy flux to be zero within the fixed absolute tolerance.

### 7.4 Right face

Retain the actual numerical flux components and cumulative contribution by step. Do not
replace them with a separately calculated engineering flow estimate.

---

## 8. Required artifact bundle

The authoritative workflow shall upload:

```text
focused JUnit XML
related Stage 7 JUnit XML
full repository JUnit XML
boundary path JSON and CSV
case summary JSON and CSV
step CSV
cell CSV
Markdown evidence
NPZ arrays
validation summary
```

The artifact summary shall state explicitly:

```text
verification_only = true
boundary_is_physical_tank_model = false
pipeline_depressurization_physical_validation = false
design_use_acceptance = false
```

---

## 9. Test execution groups

### Specification PR

```bash
python -m pytest -q \
  tests/test_stage7_lco2_hem_pipeline_depressurization_spec.py \
  --strict-markers

python -m pytest -q --strict-markers
```

### Boundary implementation PR

Expected focused set:

```text
spec integrity tests
new boundary provider/adapter tests
phase classification tests
mixed accepted-state EOS tests
equilibrium sound-speed tests
frozen Case A/B tests
```

### Runner implementation PR

Expected focused set additionally includes:

```text
raw crossing tests
projected crossing tests
first-crossing Case A/B tests
new pipeline prototype tests
boundary budget tests
phase-vapor budget tests
```

---

## 10. Failure handling

Any of the following blocks a success label:

```text
boundary path preflight failure
reverse-flow fallback
endpoint landing
forbidden transition
negative or non-finite state
property backend error
acoustic evaluation error
crossing/projection cell mismatch
post EOS rejection
second projection activity
budget residual above tolerance
frozen Case A/B signature mismatch
```

The runner shall stop and retain the failure reason. It shall not retry with changed
thresholds or silently clipped values.

---

## 11. Review gates

### Gate P0 — specification

Pass when:

```text
Markdown and JSON contract agree
integrity tests pass
scope and exclusions are explicit
boundary closure and budgets are implementable without solver changes
```

### Gate P1 — boundary adapter

Pass when:

```text
all fixed boundary paths preflight successfully
all ghost states are accepted and self-consistent
outlet-only and reverse-flow policies are exercised
no FVM time step is needed
```

### Gate P2 — first pipeline crossing

Pass when:

```text
fixed runner completes without changing a fixed case, algorithm, or tolerance
2 MPa case produces accepted crossing or an honest no-crossing result
3 MPa result is retained diagnostically as accepted crossing or honest no-crossing
4 MPa control completes as NO_CROSSING_WITHIN_HORIZON
4 MPa control contains no raw liquid-to-two-phase crossing, including subthreshold crossing
reverse-flow fallback remains zero
budgets close
frozen Case A/B regressions remain exact
```

A raw 4 MPa crossing below the `1e-6` accepted-crossing evidence threshold must be
retained as a guarded observation. It is neither an accepted crossing nor an all-liquid
control, and Gate P2 remains false.

Only a later gate may freeze a boundary-driven prototype pair or evaluate front propagation.

---

## 12. Approval boundary

```text
prototype_specification_approved = false until review
boundary_adapter_implemented = false
pipeline_depressurization_executed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
