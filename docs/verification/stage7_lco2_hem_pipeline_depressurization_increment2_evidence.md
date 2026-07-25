# Stage 7 — LCO2 HEM Pipeline Depressurization Increment 2 Evidence

## Status

`IMPLEMENTED; FIXED MATRIX EXECUTED; SOFTWARE OBSERVATION RETAINED; GATE P2 NOT PASSED; VERIFICATION ONLY`

This record preserves the first fixed boundary-driven LCO2 pipeline-depressurization matrix
implemented in PR #77. The run uses the PR #74 specification and the PR #75 prescribed-
subcooled outlet boundary without changing the fixed geometry, pressure schedules, CFL,
phase/projection algorithms, or tolerances.

The result must be read as a software/numerical observation. It is not physical Validation,
design-use acceptance, production HEM activation, or an approved two-phase acoustic band.

## Fixed problem

```text
pipe length / diameter:        1.0 m / 0.10 m
cells / dx:                    32 / 0.03125 m
initial state:                 5 MPa / 5 K subcooling, u=0, q=0
left boundary:                 ReflectiveBoundary
right boundary:                prescribed subcooled outlet_only boundary
spatial flux:                  existing first-order Rusanov
CFL:                           0.10
friction / heat / gravity:     none / none / none
internal interfaces:           none
initial acoustic time:         0.00214291781473198 s
ramp duration:                 0.00214291781473198 s
maximum horizon:               0.00642875344419594 s
maximum steps:                 2000
crossing evidence threshold:   q_eq >= 1.0e-6
```

Each 5→2, 5→3, and 5→4 MPa boundary path was preflighted at 65 points before
FVM execution. All 195 prescribed exterior states were accepted as
`LIQUID_CANDIDATE`, with zero endpoint, open-two-phase boundary, guard, or backend
failures.

## Fixed-matrix observations

| case | formal outcome | steps | crossing time [s] | cell | distance from outlet [m] | maximum crossing q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa crossing candidate | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa moderate diagnostic | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa intended liquid control | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

### 5→2 MPa

The fixed strong case produced a raw `LIQUID_TO_TWO_PHASE_CROSSING` at cell 29.
The crossing cell equaled the first-projection cell, the post state was accepted by the
mixed liquid/open-two-phase EOS, and the second projection was a no-op. The maximum
crossing quality exceeded the fixed evidence threshold and the run stopped as
`ACCEPTED_FIRST_CROSSING`.

```text
projection vapor source:       8.208652184713565e-7 kg
boundary vapor transport:      0 kg
mass residual:                  0 kg
momentum residual:             -1.5987211554602254e-14 kg m/s
energy residual:                2.3283064365386963e-10 J
combined vapor residual:        0 kg
final-state SHA256:             170ce66c02a320d50389d0cf26fed78f21042f83dec6f64a0978e451cd91e361
run signature SHA256:           28a5f8b1fd43f6208807bd15d96eaf09a568349007a1994273717aa264505fea
```

### 5→3 MPa

The fixed moderate diagnostic also produced an accepted crossing, at cell 28. This result
was retained diagnostically without changing the case definition or acceptance rules.

```text
projection vapor source:       3.4689332286792897e-7 kg
boundary vapor transport:      0 kg
mass residual:                  -1.7763568394002505e-15 kg
momentum residual:             7.993605777301127e-15 kg m/s
energy residual:                2.3283064365386963e-10 J
combined vapor residual:        0 kg
final-state SHA256:             9de8f0db938fd60ed27aac1009e22646b891cbafffd6c7df7001dab1baf62f46
run signature SHA256:           bc1a655daea7457f6d750a218fc18488b16d6fd5e46ceb8735dbbe5787cbd4ba
```

### 5→4 MPa

The intended liquid control did not remain wholly liquid. A direct raw `rho/e`
classification detected a liquid-to-open-two-phase transition at cell 25. The projected
state was internally consistent, the crossing and projection cells agreed, the second
projection was a no-op, and the budgets closed. However, the maximum equilibrium quality
was only `9.672588429198319e-9`, below the already-fixed evidence threshold `1.0e-6`.

The observation is therefore retained as:

```text
raw thermodynamic crossing:     observed
accepted crossing claim:        false
formal outcome:                 GUARD_FAILURE
failure reason:                 crossing quality evidence is below the fixed minimum
```

No pressure schedule, mesh, CFL, algorithm, or tolerance was changed to turn this result
into an all-liquid control or an accepted crossing.

```text
projection vapor source:       2.0800588606845708e-9 kg
boundary vapor transport:      0 kg
mass residual:                  8.881784197001252e-16 kg
momentum residual:             2.3092638912203256e-14 kg m/s
energy residual:                0 J
combined vapor residual:        0 kg
final-state SHA256:             7e8b6a6bc715755e0419d8a469140c02a79ec5e8bb419eb4868553c3228242e1
run signature SHA256:           fdd25cbf669428790d1f3d877ab3b86ec329726d7b10e3a8461443ba6340b202
```

## Gate decision

```text
fixed_matrix_explicit_outcomes_retained = true
pipeline_depressurization_executed = true
5_to_2_mpa_accepted_crossing = true
5_to_3_mpa_diagnostic_crossing = true
5_to_4_mpa_all_liquid_control = false
5_to_4_mpa_subthreshold_raw_crossing = true
gate_p2_passed = false
```

Gate P2 remains false because the intended 4 MPa liquid-control observation did not remain
all liquid and instead reached a subthreshold two-phase state. This is an outcome of the
fixed matrix, not an implementation result to be hidden or tuned away.

The existing frozen PR #72 Case A/B pair remains the authoritative first-order crossing and
matched all-liquid regression control. PR #77 does not replace or rebaseline those hashes.

## Authoritative validation

```text
validated head:                    2d09fd98af32f77969be49f5c1394c05e6314ea5
workflow run:                      30146579752
artifact ID:                       8616354622
artifact SHA256:                   3e5dce108b433ffc3caa288487fb461e461a2fb7bc5b47bd724546ae730acd6a
CoolProp:                          8.0.0
runner source Git blob:            414f6019710091cd51ed8732859f71b695783d18
focused test Git blob:             e9823c6c66d6f664e095f986066aa9213863736b
```

```text
dependency-free Increment 2:       12 passed, 0 skipped
installed-CoolProp Increment 2:     3 passed, 0 skipped
related pre-existing Stage 7 HEM:  74 passed, 0 skipped
full repository:                  690 passed, 0 skipped
failures / errors:                  0 / 0
```

The validated head also passed the permanent CoolProp Wave, Controlled Pressure Ramp,
Boundary Reflection, and Internal Valve regressions.

## Approval boundary

```text
verification_only = true
software_verification_only = true
algorithms_or_tolerances_tuned = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
interface_propagation_speed_verified = false
mesh_independent_crossing_verified = false
boundary_driven_liquid_control_frozen = false
```

## Next review gate

The next work shall diagnose the fixed 4 MPa subthreshold crossing before selecting or
freezing any new boundary-driven control. That diagnostic must remain separate from this
observation PR and must not silently redefine the fixed PR #74 matrix or the accepted-
crossing threshold.
