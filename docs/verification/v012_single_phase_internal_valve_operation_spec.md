# V-012 Single-Phase Internal Valve Operation Verification Specification

## 1. Purpose

This document refines the Stage 6 V-012 specification into an implementation-ready plan for `InternalValveInterface`.

The objective is to verify that the existing single-phase liquid valve software path:

- follows the implemented Kv relation and prescribed opening schedule,
- supplies explicit two-sided interface fluxes,
- matches mass, energy, and vapor-mass flux across a finite opening,
- permits the documented momentum-flux difference caused by valve-body force,
- reduces to two independent reflective walls at zero opening,
- remains numerically healthy, conservative in the documented channels, traceable, and reproducible.

This specification PR does not change solver physics, the Kv relation, interface energy treatment, boundary meaning, or regression bands.

## 2. Guardrails

V-012 is software / numerical verification only.

It is not:

- physical Validation,
- design-use acceptance,
- equipment sizing or valve selection,
- an ESD event acceptance calculation,
- a cavitation, flashing, choked-flow, or two-phase discharge model,
- an actuator-dynamics or hysteresis model.

Required metadata remains:

- `software_path_verification = true`
- `numerical_verification = true`
- `validation = false`
- `design_evaluation = false`
- `acceptance_gate = false`
- `property_backend_design_status = not_approved_for_design_use`

The CI-light mesh and the finest observation mesh are not design meshes or exact solutions.

## 3. Existing implementation semantics to preserve

### 3.1 Kv law

`KvLiquidValve` implements:

```text
Q [m3/h] = opening * Kv * sqrt(abs(delta_p) [bar] / SG)
SG = rho_upwind / 1000
```

with SI output in `m3/s`.

- Positive flow is left to right.
- Reverse pressure difference produces zero flow when `allow_reverse_flow = false`.
- Reverse pressure difference produces signed reverse flow when `allow_reverse_flow = true`.
- `opening = 0` or `Kv = 0` produces zero target flow.
- This is a single-phase liquid relation only.

### 3.2 Opening schedule

The existing schedules are:

- `ConstantOpening`
- `LinearRampOpening`

`LinearRampOpening` clamps the opening to the interval between its initial and final values and supports a zero-duration mathematical change. Zero-duration operation remains a secondary observation and is not the primary regression case.

### 3.3 Internal valve interface

For a finite opening, `InternalValveInterface`:

1. obtains raw target `Q` from the Kv law,
2. clips it to `max_mach * min(c_left, c_right) * area`,
3. uses the upwind state to construct common mass, total-enthalpy energy, and vapor-mass flux,
4. adds the local static pressure separately to each momentum flux.

Therefore the expected two-sided relations are:

```text
F_mass,left  = F_mass,right
F_energy,left = F_energy,right
F_vapor,left  = F_vapor,right
F_momentum,left - F_momentum,right = p_left - p_right
```

The momentum difference is a documented valve-body-force effect and is not an error.

For zero opening, each side uses its own reflective-wall flux. The expected through-flow quantities are zero while each side retains its own pressure reaction.

### 3.4 Energy limitation

The existing hydraulic-loss proxy is:

```text
max((p_left - p_right) * Q, 0)
```

It is diagnostic only and is not removed from `rhoE`.

V-012 must report this limitation explicitly. Changing the energy treatment is outside this verification item and requires a separate physics decision.

### 3.5 Telemetry gap to close without changing physics

The current scalar interface diagnostics expose the raw Kv target flow but do not distinguish it from the Mach-clipped flow actually applied to the numerical flux.

The V-012 implementation shall add diagnostic-only telemetry for:

- raw Kv target flow,
- applied flow after clipping,
- flow limit,
- Mach-cap activation,
- hydraulic-separation / wall-degeneration state.

The applied numerical flux shall not be changed by this telemetry work.

## 4. Baseline numerical problem

### 4.1 Geometry and state

| item | baseline value |
|---|---:|
| pipe length | `100 m` |
| diameter | `0.30 m` |
| valve location | `x/L = 0.50` |
| initial temperature | `280 K` |
| left-segment pressure | `8,000,500 Pa` |
| right-segment pressure | `7,999,500 Pa` |
| initial pressure difference | `1,000 Pa` |
| initial velocity | `0 m/s` |
| phase change | none |
| baseline cells | `100` |
| baseline CFL | `0.5` |

For an even mesh, the valve is placed between cells `n/2 - 1` and `n/2`.

Each segment is initialized from its own consistent CoolProp `(p, T)` state. Density and internal energy must therefore come from the same pressure and temperature pair.

### 4.2 External boundaries

The left and right external boundaries use constant pressure schedules equal to their corresponding initial segment pressures, with the same reference temperature.

These are numerical fixed-pressure idealizations, not real reservoirs. The evaluation window must avoid contamination from end-boundary reflections.

### 4.3 Kv calibration

The default full-open Kv is derived rather than hard-coded.

At the initial `1 kPa` pressure difference, use a target full-open face velocity of:

```text
1.0e-3 m/s
```

Then:

```text
Q_target = area * target_face_velocity
Kv = KvLiquidValve.kv_for_target_flow(
    Q_target,
    initial_delta_p,
    initial_upstream_density,
    opening=1,
)
```

This keeps the operation deeply subsonic and should leave the Mach cap inactive in the baseline.

The target velocity is a numerical verification input, not an equipment-design value.

### 4.4 Probes and evaluation time

Use symmetric probes around the valve:

- upstream near probe: `x/L = 0.375`
- downstream near probe: `x/L = 0.625`
- optional far probes: `x/L = 0.25` and `0.75`

The default target time shall be shorter than the earliest return of an external-boundary reflection to the valve or primary probes.

Helpers shall calculate:

- valve-to-probe acoustic arrival time,
- valve-to-end acoustic travel time,
- earliest reflected-contamination time,
- safe evaluation-window end.

No fixed time shall be accepted without checking it against the local sound speed and actual cell-center positions.

## 5. Verification cases

### 5.1 Case A — Constant opening

Primary constant-opening observations:

- `opening = 0`
- `opening = 0.25`
- `opening = 0.50`
- `opening = 1.00`

The primary installed-CoolProp baseline is `opening = 0.50`.

Required checks:

- requested and actual opening agree,
- raw target flow follows the implemented Kv relation,
- applied flow agrees with raw flow when the cap is inactive,
- mass / energy / vapor-mass two-sided mismatches are near roundoff,
- momentum-flux difference agrees with `p_left - p_right`,
- actual flux-derived volumetric flow agrees with applied flow,
- pressure, temperature, density, and sound speed remain positive,
- the case remains single phase.

### 5.2 Case B — Opening ramp

Primary opening schedule:

```text
opening: 0.0 -> 1.0
initial hold: 0.005 s
ramp duration: 0.010 s
```

Expected qualitative response for initial `p_left > p_right`:

- opening is monotonic non-decreasing,
- through-flow grows from zero,
- the upstream side experiences a decompression tendency propagating left,
- the downstream side experiences a compression tendency propagating right,
- raw and applied flow remain distinguishable if clipping occurs.

This is a controlled component-operation observation, not a physical actuator model.

### 5.3 Case C — Closing ramp

Primary closing schedule:

```text
opening: 1.0 -> 0.0
initial hold: 0.005 s
ramp duration: 0.010 s
```

Expected qualitative response:

- opening is monotonic non-increasing,
- through-flow decays toward zero,
- the upstream side experiences a compression tendency propagating left,
- the downstream side experiences a decompression tendency propagating right,
- after closure, through mass / energy / vapor-mass flux is zero within numerical tolerance,
- the two sides remain hydraulically separated and need not equalize in pressure.

This is not an ESD event verification.

### 5.4 Reverse-flow policy cases

Pure/component tests shall cover:

- reverse pressure difference with reverse flow disabled: target and applied flow are zero and the interface is hydraulically separated,
- reverse pressure difference with reverse flow enabled: signed flow is right to left and the upwind state is the right state.

The first installed-CoolProp operation runner uses forward flow only.

### 5.5 Mach-cap case

A synthetic pure test shall deliberately request a flow above the cap and verify:

- the raw target exceeds the limit,
- the applied target equals the signed limit,
- the activation flag is true,
- the numerical interface flux uses the applied target.

The normal baseline must not depend on cap activation to pass.

## 6. Required telemetry

### 6.1 `*_valve_history.csv`

Required columns:

- `time_s`, `step`, `dt_s`
- `opening_requested`, `opening_actual`
- `p_left_pa`, `p_right_pa`, `delta_p_pa`
- `rho_left_kg_m3`, `rho_right_kg_m3`
- `sound_speed_left_m_s`, `sound_speed_right_m_s`
- `upwind_side`, `rho_upwind_kg_m3`
- `raw_target_q_m3_s`
- `q_limit_m3_s`
- `applied_q_m3_s`
- `applied_face_velocity_m_s`
- `applied_face_mach`
- `mach_cap_active`
- `hydraulic_separation_active`
- `valve_loss_power_proxy_w`

### 6.2 `*_interface_flux_history.csv`

For the valve right face of the left segment and left face of the right segment:

- mass flux,
- momentum flux,
- energy flux,
- vapor-mass flux,
- mass-flux mismatch,
- energy-flux mismatch,
- vapor-mass-flux mismatch,
- momentum-flux difference,
- expected momentum-flux difference `p_left - p_right`,
- momentum-difference residual,
- flux-derived `Q` using the upwind density,
- difference between flux-derived `Q` and applied `Q`.

Cell-center or ghost values shall not be substituted for the actual two-sided interface fluxes.

### 6.3 `*_probe_history.csv`

For each probe:

- pressure and pressure perturbation,
- velocity,
- `A_plus` and `A_minus`,
- temperature, density, sound speed,
- vapor mass fraction and void fraction.

### 6.4 Health and budgets

Required metrics:

- execution completed and target time reached,
- finite histories,
- positive `p / T / rho / c`,
- remained single phase,
- required budget fields present,
- external-boundary mass / energy / vapor-mass balances,
- global mass / energy / vapor-mass residuals,
- cumulative valve-loss proxy, explicitly diagnostic only.

## 7. Pure helper requirements

Pure tests shall cover:

- Kv forward-flow equation,
- reverse-flow policy,
- constant and linear opening schedules,
- raw/applied/capped flow calculation,
- valve location for even meshes,
- safe acoustic evaluation windows,
- two-sided finite-opening flux identities,
- zero-opening reflective-wall identities,
- flux-derived volumetric flow,
- wave-sign expectation helpers for opening and closing.

Missing required fields shall be explicit failures rather than silently ignored diagnostics.

## 8. Artifact set

Each case shall produce:

- `*_config.json`
- `*_metrics.json`
- `*_valve_history.csv`
- `*_interface_flux_history.csv`
- `*_probe_history.csv`
- `*_final_profile.csv`
- `*_report.md`

Later PRs add:

- opening / pressure-difference / flow plots,
- interface-flux mismatch plots,
- probe pressure / velocity / characteristic plots,
- mesh/CFL summary JSON and CSV,
- CI-light result JSON,
- formal verification report,
- SHA256 manifest.

## 9. PR sequence

### PR-A — specification and implementation survey

- this specification,
- MASTER VERIFICATION INDEX update,
- Stage 6 execution-log checkpoint,
- no solver or runtime changes.

### PR-B — telemetry and constant-opening baseline

- diagnostic-only raw/applied/cap helpers,
- two-sided interface-flux telemetry,
- constant-opening CoolProp runner,
- pure and installed-CoolProp tests,
- baseline artifacts.

### PR-C — controlled opening and closing ramps

- opening-ramp and closing-ramp cases,
- probe characteristic diagnostics,
- safe evaluation windows,
- visualization.

### PR-D — mesh/CFL and formalization

- `n = 50 / 100 / 200` at `CFL = 0.5`,
- `n = 100` at `CFL = 0.25 / 0.5`,
- regression bands only after observations,
- CI-light and GitHub Actions,
- formal report and manifest,
- completion review.

## 10. Stop conditions

Stop immediately, save the branch, and report if any of the following occurs:

- solver-physics, governing-equation, Kv-law, or energy-treatment change is required,
- non-finite history,
- non-positive pressure, temperature, density, or sound speed,
- unexpected phase change,
- missing required budgets,
- opening schedule mismatch,
- finite-opening mass / energy / vapor-mass flux mismatch beyond roundoff-scale behavior,
- zero opening with nonzero through mass / energy / vapor-mass flux,
- untracked Mach clipping,
- end-boundary contamination inside an accepted evaluation window,
- regression bands would need to be chosen or relaxed before observation evidence exists,
- destructive Git operation or artifact loss risk.

## 11. Completion status

This specification does not complete V-012.

V-012 remains `IN_PROGRESS` until runner, telemetry, observations, tests, mesh/CFL, CI-light, formal report, manifest, and reproducible commands are complete.
