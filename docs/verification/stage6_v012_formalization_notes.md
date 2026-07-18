# Stage 6 V-012 CI-light and Formalization Notes

## Status

`COMPLETE; MERGED`

Merge commit: `c6155d8ea959abbcf90e8e1692dd2710b6b33666`

## Scope

This formalization closes the V-012 single-phase internal-valve software /
numerical verification sequence. It does not establish physical Validation,
equipment fidelity, operating limits, a design mesh, or design-use acceptance.

## CI-light profile

```text
V-012A / V-012B / V-012C / V-012D
n_cells = 50
CFL = 0.5
CoolProp = 8.0.0
```

The four cases protect uniform preservation, finite-opening driven flow,
controlled opening, controlled closing, and complete closure. Expected-zero
quantities use absolute limits rather than ill-conditioned relative ratios.

## Permanent regression result

- workflow: `CoolProp Internal Valve Regression`
- installed CoolProp numerical test: success
- skipped tests: `0`
- overall regression pass: `True`
- failed checks: none
- CI-light artifact SHA256: `6513dc51c5692e8b6a20fe3e980f8872c9d0f9ceff419f083510c27c8bda4047`

## Formal artifact result

The fixed 13-run sweep, nine comparison plots, CI-light profile, report, and
manifest were generated together on source head
`6e6a096dba2cfc2e8613cb0d775cd2668fd830b5`.

```text
focused tests:        14 passed, 0 skipped
full repository:      276 passed in 126.56 s
formal artifacts:     193
report SHA256:         ef33fe47074a21048d1bb31bdc8a206d0dc4d0d7c559445bf0f49115727e3a18
manifest SHA256:       368cdaa4a033d837123e668677c477379fd7666425032c6ac46754fc51a60b81
workflow artifact:     479168b98ddeaa89c07384db6877e2a6ada37fdc4db063ad8d11b1703f2d4572
```

The manifest records `coolprop_co2`, source CoolProp `8.0.0`, and
`not_approved_for_design_use`. Its Validation, design-evaluation, and
acceptance-gate flags are all false.

## Completion decision

V-012 meets its software/numerical `COMPLETE` definition because baseline
cases, telemetry, mesh/CFL observation, human-review figures, regression
bands, permanent CI, formal report, manifest, and reproduction paths exist.

Persistent limitations remain unchanged:

- regression success is not physical Validation;
- the CI-light mesh is not a design mesh;
- the finest observed mesh is not an exact solution;
- lower CFL is not truth;
- the Kv relation is single-phase only;
- fixed-pressure boundaries are zero-impedance numerical idealizations;
- the hydraulic-loss proxy is diagnostic and is not removed from `rhoE`;
- prescribed opening schedules are not actuator-dynamics or hysteresis models.

## Next stage

Stage 7 / V-013 MOC / linear-acoustic cross verification.
