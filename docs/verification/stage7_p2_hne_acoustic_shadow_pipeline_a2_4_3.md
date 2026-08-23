# Stage 7 P2-A2.4-3 — Finite-Pipeline Read-Only Acoustic Shadow

## 1. Purpose

P2-A2.4-2R established a guarded analytic verification manifold on which both
an equilibrium acoustic candidate and a frozen-quality acoustic candidate are
finite and positive. P2-A2.4-3 attaches that diagnostic to accepted states from
the existing A2.3 finite-pipeline solver without granting any hydrodynamic
authority.

This increment asks one narrow question:

> Can every accepted state in the focused finite-pipeline matrix be observed by
> the A2.4-2R acoustic closure, reproducibly and without changing one bit of the
> authoritative trajectory?

It does not ask whether the analytic surrogate predicts physical liquid-CO2
sound speed.

## 2. Frozen source and corrective prerequisite

The direct source is the A2.4-2R branch commit:

```text
fd4380472e5487dccb7824d4eddac1dcb134e18e
```

Review of that source found a one-token variable-name error in the private
pressure/energy quality helper. The A2.4-3 branch adds a compatibility bridge
and routes the public facade through it. The correction changes no equation,
coefficient, claimed domain, or authority boundary.

Corrected facade head before the A2.4-3 payload:

```text
f95a1bd248849cfb8c72dac942823191e9023c63
```

## 3. Authoritative trajectory

The authoritative computation remains the A2.3 focused pipeline:

```text
surrogate HEM EOS
+ conservative FVM
+ transported quality relaxation source
```

The observer receives accepted conservative states only after the solver has
accepted a time step.

```text
accepted U
   |
   +--> authoritative HEM/FVM trajectory
   |
   +--> A2.4-3 acoustic observer
          |
          +-- equilibrium c^2
          +-- frozen c^2
          +-- derivative residual
          +-- subcharacteristic margin
          +-- domain/failure reason
```

There is no return arrow from the observer.

## 4. Acoustic quantities

For each cell, the observer calls the guarded A2.4-2R closure using the accepted
`rho` and specific internal energy `e`.

Recorded values include:

- recovered equilibrium pressure and equilibrium quality;
- equilibrium sound-speed squared and sound speed;
- frozen sound-speed squared and sound speed;
- `c_frozen^2 - c_equilibrium^2`;
- centered-derivative relative error;
- positive-hyperbolicity and subcharacteristic checks;
- explicit validity and failure reason;
- explicit `solver_authority_granted = false`;
- explicit `empirical_fallback_used = false`.

The transported nonequilibrium quality is recorded for context, but the present
A2.4-2R verification pair is recovered from the analytic equilibrium manifold.
It is not yet a finite-frequency HNE dispersion model.

## 5. Claimed domain and fail-closed behavior

The inherited analytic acoustic domain is the open interval:

```text
1.5 MPa < p < 5.0 MPa
0.02 < q_eq < 0.45
```

A state outside this domain is not assigned a substitute sound speed. The row is
retained with:

```text
valid = false
failure_reason = <explicit reason>
equilibrium c^2 = null
frozen c^2 = null
empirical fallback = false
```

The focused A2.4-3 slice is ready only if every accepted state in every declared
case remains inside the claimed domain and all diagnostics are valid.

## 6. Focused finite-pipeline matrix

The evidence matrix retains the three A2.3 relaxation limits:

| Case | Relaxation time | Meaning |
|---|---:|---|
| `TAU_NEAR_ZERO` | `1e-18 s` | HEM-limit quality relaxation |
| `TAU_FINITE` | `1e-4 s` | finite-rate transported quality |
| `TAU_FROZEN` | `infinity` | frozen transported quality |

The default A2.4-3 evidence run uses eight cells and eight accepted steps. This
is a focused integration slice, not a mesh or CFL investigation.

## 7. Required gates

The increment requires all of the following:

1. exact A2.4-2R source pin;
2. the pressure-recovery name error is corrected without model-form change;
3. all parent and A2.4-3 solver-authority flags remain false;
4. acoustic-shadow ON/OFF full trajectories are bitwise equal;
5. acoustic-shadow ON/OFF hydrodynamic trajectories are bitwise equal;
6. every accepted state lies in the claimed acoustic domain;
7. every acoustic diagnostic is valid;
8. equilibrium and frozen `c^2` are finite and positive;
9. the subcharacteristic margin is nonnegative;
10. the independent derivative cross-check remains satisfied;
11. no empirical acoustic fallback is used;
12. no cell grants solver authority;
13. mass, momentum, and energy are not damaged;
14. repeated runs are deterministic;
15. maturity is not promoted beyond a working verification slice.

Any failed gate leaves `a2_4_3_acoustic_shadow_ready = false`.

## 8. Evidence products

The command

```bash
python -m liquid_gas_transient.hne_acoustic_shadow_pipeline \
  --output-dir artifacts/stage7/p2-hne-acoustic-shadow-pipeline-a2-4-3
```

writes exactly:

```text
summary.json
case_summary.csv
step_history.csv
cell_history.csv
operator_report.md
manifest.json
```

JSON is strict (`allow_nan = false`) and the payload is digest-recorded.

## 9. Solver authority

Every permission remains false:

```text
equilibrium c^2 -> CFL                  false
equilibrium c^2 -> Rusanov              false
frozen c^2 -> CFL                       false
frozen c^2 -> Rusanov                   false
acoustic pressure -> flux               false
acoustic state -> conservative state    false
acoustic values -> boundaries           false
hydrodynamic coupling                   false
```

The A2.3 HEM backend continues to provide the pressure and sound speed used by
the authoritative FVM.

## 10. Maturity

```text
IMPLEMENTED                              true
WORKING VERIFICATION SLICE               true
FINITE-PIPELINE ACOUSTIC SHADOW          true
READ-ONLY SHADOW EVIDENCE READY          true

WORKING VERTICAL SLICE                   false
VERIFIED / ACCEPTED                      false
PHYSICALLY VALIDATED                     false
DESIGN-USE / PRODUCTION                  false
```

The acoustic values remain verification-surrogate outputs and must not be read
as design values for real CO2.

## 11. Interpretation of a green result

A green result means:

> The guarded A2.4-2R equilibrium/frozen acoustic diagnostic can be evaluated on
> every accepted state of the focused finite-pipeline matrix, with positive
> derivatives, correct ordering, deterministic evidence, and no solver effect.

It does not mean:

- the finite-relaxation acoustic response has been derived;
- a single real sound speed is valid for `omega*tau = O(1)`;
- real-CO2 acoustics have been physically validated;
- any HNE acoustic value may enter CFL, flux, Rusanov, or boundaries;
- P2-A3 hydrodynamic coupling is authorized.

## 12. Next action

The next authorized action is:

```text
P2-A2.4-4
Finite-Relaxation Dispersion Investigation
```

That increment should linearize the coupled conservation/relaxation response,
retain frequency and attenuation information, and recover the equilibrium and
frozen limits before an Acoustic Authority Gate is considered.
