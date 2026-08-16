# Stage 7 P2-A1R — Transported-Quality Disequilibrium Audit

## Why this review exists

P2-A1 successfully established a software/model-form slice:

- the locked P1 HEM baseline was reproduced;
- HEM and three relaxation-time cases completed 65 accepted steps;
- conservation, positivity, reverse-flow and finiteness Guards passed;
- `tau = 1e-9 s` reproduced the HEM state path bitwise;
- finite tau produced a nonzero transported/equilibrium quality difference.

A post-run audit found that the first interpretation was too broad. Finite tau
does not produce a uniformly delayed transported-quality front. Independent
transport can move nonzero quality into a cell that the unchanged HEM `rho/e`
closure classifies as thermodynamic liquid. Therefore the q-threshold evidence
front can transiently lead as well as lag the HEM thermodynamic boundary.

P2-A1R preserves the original P2-A1 calculation and classifies this interaction
without changing the solver, EOS wrapper, tau values, threshold or Guard.

## Retained model matrix

```text
HEM_EQUILIBRIUM
HNE_TAU_NEAR_ZERO  tau = 1e-9 s
HNE_TAU_MEDIUM     tau = 1e-5 s
HNE_TAU_SLOW       tau = 1e-4 s
```

Tau remains an assumed sensitivity parameter, not a validated CO2 property.

## Audit definitions

Signed quality disequilibrium is

```text
q_lag = q_equilibrium - q_transport
```

Thus:

- positive: transported quality is below the HEM equilibrium target;
- negative: transported quality is above the HEM equilibrium target.

At every retained snapshot, the transported-q evidence front is classified as:

```text
absent while thermodynamic front is present
behind
coincident
ahead
present while thermodynamic front is absent
```

## Authoritative interpretation after A1R

- The near-zero tau limit remains bitwise HEM.
- Finite tau creates mixed-sign transported/equilibrium quality disequilibrium.
- At the tested resolution, `tau=1e-5 s` has no resolved onset delay and has
  transient q-front lead.
- `tau=1e-4 s` has an initial onset delay and later exhibits both front lag and
  front lead.
- The q-threshold front is a scaffold diagnostic, not a validated physical
  phase front.
- Pressure, temperature, sound speed and the thermodynamic boundary remain HEM
  quantities by construction.

Therefore the broad phrase “finite tau delays the kinetic phase front” is
superseded by:

> Finite tau creates transported/equilibrium quality disequilibrium whose
> threshold-front relation is mixed under the current independent-transport /
> HEM-closure scaffold.

## Development decision

P2-A1 remains useful as a working software/model-form slice, but a broad tau
sweep should not be treated as physical HNE evidence. P2-A2 should first refine
or replace the thermodynamic closure so that non-equilibrium quality has a
well-defined relationship to pressure, temperature, energy and acoustics.

## Evidence contract

P2-A1R writes exactly nine files:

```text
audit_summary.json
case_disequilibrium.csv
front_relation_history.csv
signed_quality_lag_history.csv
closure_limitations.csv
signed_quality_lag_envelope.png
front_relation_counts.png
operator_report.md
audit_manifest.json
```

## Maturity boundary

```text
IMPLEMENTED                       true
DIAGNOSTIC EVIDENCE READY         true
P2 MODEL-FORM VERTICAL SLICE      true
PHYSICAL HNE VERTICAL SLICE       false
PROJECT WORKING VERTICAL SLICE    false
VERIFIED                          false
ACCEPTED                          false
PHYSICALLY VALIDATED              false
DESIGN-USE ACCEPTED               false
PRODUCTION APPROVED               false
```
