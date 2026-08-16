# Stage 7 P2-A1 — HEM / HNE Quality-Relaxation Model-Form Sensitivity

## Purpose

P1 closed the HEM numerical-sensitivity work with explicit limitations. P2-A1
adds the first bounded HNE model-form slice without changing the locked P1
geometry, mesh, CFL, boundary schedule, Rusanov flux, pressure threshold, or
production defaults.

The comparison starts one accepted step before the authoritative P1 first
thermodynamic crossing and advances through that crossing plus 64 accepted
post-crossing steps.

## Models

### HEM reference

The existing `HEMPhaseChange` operator sets transported vapor mass fraction to
the local equilibrium quality after each conservative FVM step.

### HNE quality-relaxation scaffold

The existing `HNERelaxationPhaseChange` operator applies the exact exponential
source update

```text
q_new = q_eq + (q_old - q_eq) exp(-dt/tau)
```

for three predeclared sensitivity values:

```text
1e-9 s   near-zero software limit
1e-5 s   medium assumed relaxation
1e-4 s   slow assumed relaxation
```

These values are assumptions for model-form sensitivity. They are not validated
CO2 relaxation times.

## Closure boundary

The P2-A1 EOS wrapper intentionally retains the reviewed HEM `rho/e` closure for
pressure, temperature, equilibrium quality and acoustic speed. The transported
quality is permitted to differ from equilibrium quality, and a diagnostic
homogeneous void fraction is reconstructed from transported quality and
saturation densities at the inherited pressure.

Consequently:

- transported quality and the kinetic evidence front can lag;
- mass, momentum, total energy, pressure, temperature and the thermodynamic
  `rho/e` phase front remain identical across tau cases by construction;
- no hydrodynamic feedback from non-equilibrium quality is present in this
  scaffold;
- this is not a full two-temperature, two-pressure, metastable, nucleation, slip,
  or two-fluid HNE model.

## Required gates

1. Locked P1 baseline and first crossing are reproduced.
2. HEM plus all three HNE cases complete the fixed 65-step sequence.
3. Conservation, positivity, finiteness and reverse-flow Guards remain active.
4. The near-zero tau case reproduces the HEM state path bitwise.
5. Finite tau produces a resolved transported-quality lag.
6. Hydrodynamic and thermodynamic-front invariance is retained as an explicit
   construction property, not misreported as physical validation.
7. Tau remains an unvalidated sensitivity parameter.
8. Project maturity is not promoted.

## Output contract

The focused workflow writes exactly nine evidence files:

```text
model_form_summary.json
case_comparison.csv
time_history.csv
cell_history.csv
tau_limit_comparison.csv
quality_lag_comparison.png
phase_front_comparison.png
operator_report.md
model_form_manifest.json
```

## Maturity boundary

```text
IMPLEMENTED                       true
P2 MODEL-FORM VERTICAL SLICE      true
PROJECT WORKING VERTICAL SLICE    false
VERIFIED                          false
ACCEPTED                          false
PHYSICALLY VALIDATED              false
DESIGN-USE ACCEPTED               false
PRODUCTION APPROVED               false
```

A successful P2-A1 result permits progression to targeted tau sensitivity and a
more thermodynamically complete HNE closure. It does not identify a physical
relaxation time and does not close the physical-discharge/two-phase feedback
loop.
