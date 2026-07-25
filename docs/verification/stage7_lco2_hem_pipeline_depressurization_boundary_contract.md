# Stage 7 — HEM Prescribed-Subcooled Outlet Boundary Contract

## Status

`SPECIFICATION ONLY; VERIFICATION-ONLY BOUNDARY; NOT A PHYSICAL TANK MODEL`

This document defines the implementation contract for the right-end boundary required by
the first LCO2 pipeline-depressurization prototype.

It supplements:

- [`stage7_lco2_hem_pipeline_depressurization_prototype_spec.md`](stage7_lco2_hem_pipeline_depressurization_prototype_spec.md)
- [`stage7_lco2_hem_pipeline_depressurization_prototype_contract_v1.json`](stage7_lco2_hem_pipeline_depressurization_prototype_contract_v1.json)

---

## 1. Existing limitation

The existing generic pressure boundary calls:

```text
eos.density_from_pressure(p_boundary)
```

and optionally:

```text
eos.internal_energy_from_pressure(p_boundary)
```

The strict mixed liquid/open-two-phase HEM verification EOS intentionally does not provide
a pressure-only inversion because pressure does not uniquely determine a real-fluid CO2
state.

The new boundary shall not add `density_from_pressure` to
`VerificationHEMLiquidOpenTwoPhaseEOS`.

---

## 2. Planned components

The first implementation increment should contain three narrow components.

### 2.1 Prescribed schedule

A schedule returns pressure as a function of time:

```python
class PressureSchedule(Protocol):
    def pressure_pa(self, t: float) -> float: ...
```

The existing `LinearPressureRamp` may be reused.

The schedule remains responsible only for pressure. It does not infer density, energy,
quality, or phase.

### 2.2 Thermodynamic boundary-state provider

Conceptual protocol:

```python
class HEMPrescribedBoundaryStateProvider(Protocol):
    def state_at(self, t: float) -> HEMPrescribedBoundaryState: ...
```

Conceptual state record:

```python
@dataclass(frozen=True)
class HEMPrescribedBoundaryState:
    time_s: float
    pressure_requested_pa: float
    subcooling_K: float
    saturation_temperature_K: float
    temperature_requested_K: float
    rho_kg_m3: float
    e_j_kg: float
    equilibrium_quality: float
    void_fraction: float
    pressure_recovered_pa: float
    temperature_recovered_K: float
    sound_speed_m_s: float
    phase_class: str
    boundary_region: str
    scope_status: str
```

The provider is responsible for the pressure/subcooling closure and canonical thermodynamic
validation. It does not write ghost cells.

### 2.3 Boundary adapter

Conceptual boundary:

```python
@dataclass
class VerificationHEMPrescribedSubcooledOutletBoundary:
    state_provider: HEMPrescribedBoundaryStateProvider
    flow_direction: Literal["outlet_only"] = "outlet_only"
    velocity_policy: Literal["copy"] = "copy"
```

The adapter is responsible for flow-direction policy, conservative ghost construction,
ghost placement, and diagnostics. It does not perform property inversion itself.

---

## 3. State-provider algorithm

For a requested time `t`:

```text
1. p_b = pressure_schedule.pressure_pa(t)
2. require p_b finite and positive
3. T_sat = CoolProp T(P=p_b, Q=0)
4. T_b = T_sat - DeltaT_sub,b
5. require DeltaT_sub,b > 0
6. rho_b = CoolProp Dmass(P=p_b, T=T_b)
7. e_b = CoolProp Umass(P=p_b, T=T_b)
8. require rho_b > 0 and e_b >= 0
9. evaluate exact rho_b/e_b through reviewed HEM phase classification
10. derive boundary region
11. estimate equilibrium sound speed through the reviewed estimator
12. require boundary region = LIQUID_CANDIDATE
13. require q_eq = 0 under the existing endpoint tolerance
14. build a stationary q_eq conservative state
15. require VerificationHEMLiquidOpenTwoPhaseEOS to accept it
16. compare recovered p/T with requested p/T
17. return the immutable state record
```

No intermediate value may be clipped.

---

## 4. Boundary-state cache

Property evaluation is expensive. The implementation may cache exact scheduled states.

The minimum safe cache key is:

```text
(pressure_requested_pa, subcooling_K)
```

A cache hit must return a state generated from exactly the same key. Approximate or nearest-
neighbor cache lookup is forbidden in the first implementation.

Diagnostics shall include:

```text
state_provider_evaluation_count
state_provider_cache_hit_count
state_provider_cache_size
```

Caching must not change any requested value or acceptance decision.

---

## 5. Conservative ghost construction

Given the validated boundary state and adjacent interior velocity `u_i`:

```text
rho_g = rho_b
u_g   = u_i
e_g   = e_b
q_g   = q_eq,b = 0
```

The ghost conservative state is:

```text
U_g = [rho_g,
       rho_g u_g,
       rho_g (e_g + 0.5 u_g^2),
       rho_g q_g]
```

The implementation should use `make_conserved` or an equivalent exact construction rather
than modifying selected components of an interior state.

### Required invariant

The boundary ghost must be a self-consistent accepted thermodynamic state. Therefore:

```text
rho_g/e_g determines LIQUID_CANDIDATE
transported q_g equals equilibrium q_eq,g
mixed accepted-state EOS accepts U_g
```

Copying interior `rho*q` or interior quality is forbidden.

---

## 6. Flow-direction policy

The boundary is implemented only for the right side in the first increment.

The existing coordinate convention is positive from left to right.

```text
u_i >= 0: domain-to-outlet motion is allowed
u_i < 0:  reverse flow is forbidden
```

When reverse flow is detected, the adapter applies the existing reflective ghost policy and
increments a diagnostic counter.

The first prototype acceptance contract requires:

```text
reverse_flow_fallback_count = 0
```

No hysteresis or velocity tolerance is introduced in this increment. If exact-zero policy
causes switching, that observation is reported and reviewed separately rather than hidden
by a new threshold.

---

## 7. Ghost placement

For a right boundary and `n_ghost > 0`, every right ghost cell receives the same validated
conservative boundary state.

The adapter shall reject:

```text
left-side application
n_ghost <= 0
invalid U_ext shape
non-finite adjacent interior state
non-positive adjacent interior density
```

The adapter shall not modify internal cells.

---

## 8. Pressure and temperature recovery checks

After the provider constructs `(rho_b,e_b)`, the reviewed phase path returns recovered
pressure and temperature.

Required comparisons:

```text
|p_recovered - p_requested|
<= max(1 Pa, 1e-6 * |p_requested|)

|T_recovered - T_requested|
<= max(1e-6 K, 1e-8 * |T_requested|)
```

These checks verify software consistency of the `P,T -> rho,e -> P,T` path. They are not
property-accuracy validation.

---

## 9. Phase and quality checks

Use the existing configuration values:

```text
phase endpoint tolerance:          1e-10
projection activation tolerance:   1e-12
accepted-state quality tolerance:  1e-10
```

At every scheduled boundary state:

```text
scope_status = supported_candidate
phase_class = compressed_or_subcooled_liquid
boundary_region = LIQUID_CANDIDATE
quality_defined = true
alpha_defined = true
q_eq = 0 under the reviewed contract
```

The first boundary adapter does not support:

```text
SATURATED_LIQUID_ENDPOINT
OPEN_TWO_PHASE
SATURATED_VAPOR_ENDPOINT
VAPOR_CANDIDATE
critical or supercritical-gas states
solid or below-triple states
unknown states
```

A later boundary model may expand scope only through a separate reviewed specification.

---

## 10. Path preflight

Before creating the transient solver, the full linear pressure path is evaluated at 65
uniform schedule fractions:

```text
s_j = j / 64,  j=0,...,64
p_j = (1-s_j) p_initial + s_j p_final
```

Each sample is evaluated through the full state-provider contract.

The preflight result should retain one record per sample:

```text
case_id
sample_index
fraction
pressure_requested_pa
saturation_temperature_K
temperature_requested_K
rho_kg_m3
e_j_kg
pressure_recovered_pa
temperature_recovered_K
quality
void_fraction
phase_class
boundary_region
sound_speed_m_s
accepted
failure_reason
```

The entire case is rejected if any sample fails.

---

## 11. Diagnostics contract

The boundary adapter shall expose a flat diagnostic snapshot suitable for step artifacts:

```text
boundary_pressure_requested_pa
boundary_temperature_requested_K
boundary_rho_kg_m3
boundary_e_j_kg
boundary_equilibrium_quality
boundary_void_fraction
boundary_sound_speed_m_s
boundary_region_code or string in retained record
boundary_active_count
reverse_flow_fallback_count
last_flow_policy
state_provider_evaluation_count
state_provider_cache_hit_count
```

String-valued diagnostics may be retained in runner records rather than passed into legacy
numeric-only diagnostic maps.

---

## 12. Boundary-face verification tests

The first implementation increment shall include tests for:

### 12.1 Dependency-free contract tests

Use fake state providers and a simple accepted-state EOS to verify:

```text
right-side ghost fill
all ghost cells identical
copy-velocity policy
q uses provider equilibrium quality, not interior quality
outlet flow activates prescribed state
reverse flow activates reflection
reverse-flow counter increments
internal cells remain unchanged
invalid side and invalid inputs fail fast
cache semantics do not alter state
```

### 12.2 Installed-CoolProp tests

For 5 K subcooling at 5, 4, 3, and 2 MPa:

```text
provider constructs finite positive rho, p, T, c
internal energy is non-negative
region is LIQUID_CANDIDATE
q_eq = 0
mixed accepted-state EOS accepts the conservative state
recovered p/T satisfy tolerance
```

### 12.3 Full path tests

For each 5 -> 2, 5 -> 3, and 5 -> 4 MPa linear schedule:

```text
65 / 65 samples accepted
endpoint count = 0
open-two-phase count = 0
guarded/backend count = 0
```

No `FvmSolver.step()` is required for the boundary implementation PR.

---

## 13. Failure categories

The boundary implementation should distinguish at least:

```text
INVALID_SCHEDULE
PROPERTY_BACKEND_FAILURE
NONFINITE_OR_NONPOSITIVE_STATE
NEGATIVE_INTERNAL_ENERGY
UNSUPPORTED_PHASE_REGION
QUALITY_CONTRACT_FAILURE
ACOUSTIC_EVALUATION_FAILURE
ROUND_TRIP_MISMATCH
MIXED_EOS_REJECTION
REVERSE_FLOW_FALLBACK
INVALID_BOUNDARY_APPLICATION
```

Exceptions may share one implementation error type, but the retained message and evidence
must preserve the specific reason.

---

## 14. Explicit non-goals

This boundary does not model:

```text
a finite tank inventory
tank energy balance
valve area or Kv/Cv
orifice discharge coefficient
critical or choked release
atmospheric flashing outside the pipe
phase slip
heat transfer at the boundary
non-equilibrium nucleation
```

The prescribed state is an external numerical boundary used to generate a controlled
pressure-wave problem.

---

## 15. Approval boundary

```text
verification_only = true
boundary_is_physical_tank_model = false
boundary_is_release_rate_model = false
pressure_only_real_fluid_inversion_approved = false
production_default_changed = false
physical_validation = false
design_use_acceptance = false
```

Approval of this contract permits only the boundary-adapter and preflight implementation
increment described here.
