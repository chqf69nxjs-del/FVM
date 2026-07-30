# Stage 7 U3 P1 — B0 Single-Phase Discharge-Boundary Implementation Plan

## Status

```text
Issue:                              #109
track:                              U3 application / component benchmark
stage:                              D1 contract lock -> D2 reference implementation
scope:                              verification only
contract:                           stage7_u3_b0_discharge_boundary_contract_v1.json
B1 choking model:                   out of scope
pipe coupling:                      out of scope
physical validation:                false
design use:                         false
production activation:              false
```

## 1. Purpose

Implement the simplest independently checkable limit of a future U3 physical
discharge boundary before adding compressible choking or connecting the element
to the finite-volume pipeline.

The B0 benchmark answers only:

1. does the component reproduce the locked incompressible liquid-orifice law;
2. are closed and zero-pressure-drop identities exact;
3. are area and discharge-coefficient scaling exact within predeclared tolerance;
4. are forward stream mass, momentum, and energy transfers exposed with an
   explicit sign convention;
5. are reverse pressure and phase-scope violations refused explicitly?

## 2. Locked state and geometry

```text
fluid / backend:                    pure CO2 / CoolProp 8.0.0
upstream pressure p0:               5.0e6 Pa
upstream temperature:               Tsat(p0,Q=0) - 5.0 K
reference area Aref:                1.0e-4 m2
base opening fraction:              0.5
base effective area Aeff:           5.0e-5 m2
base discharge coefficient Cd:      0.8
base back pressure:                 4.95e6 Pa
minimum downstream subcooling:      0.5 K
```

The exact `T0`, `rho0`, `h0`, and `s0` are evaluated and retained from the fixed
backend. The defining pressure/subcooling pair is the immutable thermodynamic
input; backend results are evidence, not values selected after execution.

## 3. Reference equations

```text
Delta_p = p0 - pb
Aeff = Aref * f_open
m_dot = Cd * Aeff * sqrt(2 * rho0 * Delta_p)
u_exit = m_dot / (rho0 * Aeff)
M_dot_stream = m_dot * u_exit
E_dot_stream = m_dot * h0
```

Positive values represent transfer out of the modeled domain.

At D1-D2, the momentum result is the discharged-stream advective transfer only.
Static pressure-force mapping to an FVM interface is explicitly deferred to the
D4 boundary adapter. This avoids silently treating a component benchmark as a
complete conservative pipe boundary.

## 4. Independent implementation paths

```text
Path R — independent analytical/property reference evaluator
Path A — verification-only B0 component adapter
```

Both paths may use the fixed CoolProp backend, but they must not share the
orifice-law calculation helper. Their retained inputs, property states, outputs,
and result hashes are compared row by row.

## 5. Fixed cases

| case | purpose | required outcome |
|---|---|---|
| B0-01 | closed element | exact zero stream transfer |
| B0-02 | zero pressure drop | exact zero forward stream transfer |
| B0-03 | subcooled liquid limit | reference-law agreement |
| B0-04A/B | opening / area scaling | mass-flow ratio `2.0` |
| B0-05A/B | discharge-coefficient scaling | mass-flow ratio `2.0` |
| G-01 | back pressure above upstream | explicit reverse-pressure refusal |
| G-02 | opening outside `[0,1]` | explicit input refusal |
| G-03 | non-positive subcooling | explicit upstream phase-scope refusal |

## 6. Predeclared tolerances

```text
exact-zero absolute:                0.0
mass-flow absolute / relative:      1e-12 kg/s / 1e-12
momentum absolute / relative:       1e-10 N / 1e-12
energy absolute / relative:         1e-7 W / 1e-12
scaling-ratio absolute:             1e-12
```

These tolerances are locked before execution and may not be changed in response
to the observed error distribution.

## 7. Evidence bundle

```text
summary.json
benchmark_contract.json
benchmark_cases.csv
property_scope_history.csv
conservative_flux_budget.csv
guard_outcomes.csv
report.md
mass_flow_vs_pressure_drop.png
area_and_Cd_scaling.png
energy_transfer_residual.png
artifact_sha256.txt
dedicated / related / full-repository JUnit
runtime / Git provenance
```

## 8. Completion boundary

D1-D2 completion requires the contract and independent reference to be frozen,
the verification adapter to reproduce all B0 rows and guards, clean authoritative
tests, and traceable evidence. It does not approve B1 choking, physical CO2
critical discharge, integrated blowdown, design use, or production activation.
