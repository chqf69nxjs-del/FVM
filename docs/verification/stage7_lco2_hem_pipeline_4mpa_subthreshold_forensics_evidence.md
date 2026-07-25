# Stage 7 — Fixed 4 MPa Subthreshold-Crossing Forensic Evidence

## Status

`IMPLEMENTED; PR #77 BASELINE REPRODUCED EXACTLY; SOFTWARE DIAGNOSTIC; MULTI-FACTOR EVIDENCE; GATE P2 FALSE`

This record diagnoses the fixed PR #77 5→4 MPa observation without changing its mesh,
CFL, pressure schedule, boundary model, HEM phase/projection settings, or `1e-6`
accepted-crossing evidence threshold.

The result remains a software/numerical diagnostic. It is not physical Validation, design
acceptance, production HEM approval, or an approved two-phase acoustic band.

## Immutable baseline

The diagnostic first reproduced the merged PR #77 observation exactly:

```text
formal outcome:               GUARD_FAILURE
crossing step / time:         313 / 1.996923102525957e-3 s
crossing cell / distance:     25 / 0.203125 m from outlet
maximum q_eq:                 9.672588429198319e-9
final-state SHA256:           7e8b6a6bc715755e0419d8a469140c02a79ec5e8bb419eb4868553c3228242e1
run-signature SHA256:         fdd25cbf669428790d1f3d877ab3b86ec329726d7b10e3a8461443ba6340b202
```

No PR #77 observation was reclassified.

## Retained diagnostic window

```text
steps:                         300 through 313 inclusive
cells:                         23 through 27 inclusive
accepted / raw / post states:  210 records
raw saturation margins:         70 records
Rusanov decompositions:          70 records
rho/e perturbations:             81 records
```

## Finding 1 — independent thermodynamic coordinates support a real HEM crossing

At step 313 / cell 25, the raw state was:

```text
pressure:                      4,273,927.110515705 Pa
rho:                           876.1793486610264 kg/m3
internal energy:               215,231.8639318858 J/kg
temperature:                   281.06502329585885 K
q_eq:                          9.672588429198319e-9
void fraction:                 6.721608823263323e-8
raw boundary region:           OPEN_TWO_PHASE
transition event:              LIQUID_TO_TWO_PHASE_CROSSING
```

At the same recovered pressure, the saturated-liquid internal energy was
`215231.8622310403 J/kg`. Therefore:

```text
Delta_u_sat = u - u_f:         +1.7008455179166049e-3 J/kg
Delta_v_sat = v - v_f:         +6.567548805139212e-11 m3/kg
q from internal energy:        9.672598473952674e-9
q from specific volume:        9.672589435031626e-9
CoolProp q_eq:                 9.672588429198319e-9
coordinate support:            TWO_PHASE_SIDE_SUPPORT
```

Both independent signed margins are positive, and both independently reconstructed quality
coordinates agree with the direct CoolProp quality. The reviewed diagnostic therefore
retains:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED = true
```

This supports the statement that the raw `rho/e` point is just inside the equilibrium
two-phase region. It does not establish that an actual pipe would nucleate vapor
instantaneously at this state.

## Finding 2 — isentropic reference places the raw pressure beyond saturation

The initial-state entropy and saturated-liquid root were:

```text
initial entropy s0:            1075.2689514867911 J/(kg K)
isentropic flash pressure:     4,343,948.305362968 Pa
root residual:                 2.0691004465334117e-11 J/(kg K)
```

The crossing raw pressure was `70,021.19484726246 Pa` below that reference pressure.
The local raw entropy was `1069.404803582071 J/(kg K)`, or
`-5.864147904720085 J/(kg K)` relative to the initial state.

The isentropic curve is a reference trajectory only. The cell is Eulerian and is influenced
by neighbouring fluxes, so this comparison is not a material-particle entropy proof or a
physical Validation criterion.

## Finding 3 — the exact local Rusanov dissipative term did not create the crossing

For every selected step/cell, the reconstructed central-plus-dissipative update reproduced
the stored raw FVM state. Maximum errors were:

```text
maximum absolute error:        2.2737367544323206e-13
maximum relative error:        1.685312437739661e-16
```

At step 313 / cell 25, the offline central-only counterfactual was also accepted as
`OPEN_TWO_PHASE`:

```text
central-only q_eq:             3.690684903157135e-7
central-only Delta_u_sat:      +6.489150400739163e-2 J/kg
central-only Delta_v_sat:      +2.5053992923265017e-9 m3/kg
full Rusanov q_eq:             9.672588429198319e-9
```

The central-only two-phase depth was about 38.16 times the full Rusanov value. Under the
reviewed one-step criterion, the dissipative contribution moved the state closer to the
liquid side rather than creating the crossing. Consequently:

```text
NUMERICAL_DIFFUSION_CONSISTENT = false under the local counterfactual criterion
```

This does not rule out accumulated first-order diffusion over earlier steps. Mesh and CFL
sensitivity remain separate later increments.

## Finding 4 — no direct outlet-face dominance was established at the crossing cell

At step 313 / cell 25:

```text
left-face rhoE update contribution:   +72,313.84219419633
right-face rhoE update contribution:  -78,331.75429422488
absolute right/left ratio:             1.0832193659945168
```

Cell 25 is not boundary-adjacent. The narrow reviewed direct-boundary criterion was not
satisfied, so:

```text
BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT = false under the direct criterion
```

The prescribed outlet still launches the pressure wave and may influence the state
indirectly. This diagnostic does not rule out that broader causal pathway.

## Finding 5 — the state is weakly resolved, but not round-off sensitive in the tested grid

The 9×9 independent relative perturbation grid used:

```text
0, ±1e-12, ±1e-10, ±1e-8, ±1e-6
```

No phase-region change occurred through `1e-8`. At `1e-6`, some perturbation directions
returned to `LIQUID_CANDIDATE` while others remained `OPEN_TWO_PHASE`.

```text
perturbation classification:    WEAKLY_RESOLVED
NEAR_SATURATION_PROPERTY_SENSITIVE = true
```

The state is therefore not classified as floating-point round-off sensitive by this test,
but it is not robust throughout the tested `1e-6` envelope. These labels are confidence
diagnostics and do not alter the thermodynamic phase result.

## Acoustic-closure caution

Across the crossing step, the equilibrium sound-speed candidate changed from approximately
`461.25669095385655 m/s` in the accepted liquid state to `43.22308393386989 m/s` in the raw
micro-quality two-phase state.

This is retained as a software observation. The near-saturation continuity and physical
accuracy of the two-phase acoustic closure are not approved. The runner stops at the first
crossing, so this diagnostic does not claim valid downstream wave propagation using that
post-crossing sound speed.

## Diagnostic conclusion

The retained categories are:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

`MULTI_FACTOR_EVIDENCE` means the raw point is independently supported as an equilibrium
two-phase state while its classification is still sensitive at the `1e-6` relative
perturbation scale. It does not mean that a physical cause has been uniquely identified.

The following categories were not triggered by their reviewed narrow criteria:

```text
NUMERICAL_DIFFUSION_CONSISTENT
BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT
```

## Final authoritative validation

```text
validated implementation head:      719301dd64c9ee2571cf3296605466a2ee9de27f
workflow run:                       30162194409
artifact ID:                        8620823392
artifact SHA256:                    1b2c14790c3c66be47386f60ddb9c8b21ee5d253dcc0ab1d78e9deaa7b5184d7
CoolProp:                           8.0.0
forensic source Git blob:           af02452313fd942004f6b8d6ce1662e30c16ac1f
focused test Git blob:              9671974b63ee6d97839a53ff55cac7a5df1ecf98
contract test Git blob:             409f97edda208885de6eabc9d67dbf674f8a3a5f
```

```text
dependency-free forensic tests:    8 passed, 0 skipped
installed-CoolProp forensics:      9 passed, 0 skipped
related Stage 7 regressions:      69 passed, 0 skipped
full repository:                 723 passed, 0 skipped
failures / errors:                 0 / 0
```

The final workflow completed compile/diff checks, pure tests, CoolProp tests, artifact
generation, machine-readable contract checks, related Stage 7 regressions, full-repository
tests, and the explicit no-skip/no-failure assertion.

The validated head also passed the permanent CoolProp Wave, Controlled Pressure Ramp,
Boundary Reflection, and Internal Valve workflows in runs `30162194483`, `30162194405`,
`30162194415`, and `30162194406`.

## Approval boundary

```text
verification_only = true
software_diagnostic_only = true
PR77_observation_reclassified = false
Gate_P2_passed = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
two_phase_acoustic_accuracy_band_approved = false
mesh_independent_crossing_verified = false
```

## Recommended next increments

1. Review and freeze this fixed-case forensic result.
2. Perform a separate 32/64/128-cell mesh study with CFL held at 0.10.
3. Perform a separate CFL study after the mesh result is understood.
4. Add a near-saturation acoustic-continuity study before allowing post-crossing propagation.
5. Compare boundary closures only after the fixed numerical sensitivities are separated.
