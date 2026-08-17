# Stage 7 P2-A2.3 — Formal Closeout

## 1. Decision

P2-A2.3 is formally closed at:

```text
799edb09faa1502e25837c97fa5d168ad79e492e
```

The frozen result is:

```text
A2_3_FORMALLY_CLOSED_WITH_HYDRODYNAMIC_COUPLING_GATE_CLOSED
```

This closeout records the successful finite-pipeline read-only HNE shadow
integration. It does not modify or promote the A2 closure, the A2.3 shadow
implementation, the FVM solver, the EOS, the numerical flux, the CFL rule,
boundaries, or phase-change source ordering.

## 2. Frozen evidence

| Item | Frozen value |
|---|---|
| A2 authority SHA | `b45156f349ddc9754d481c285a8e1efde5d74d22` |
| A2.3 authority SHA | `799edb09faa1502e25837c97fa5d168ad79e492e` |
| Focused workflow run | `31999652196` |
| Workflow conclusion | `success` |
| Focused tests | `5 passed, 0 skipped, 0 failures, 0 errors` |
| Artifact ID | `9277959046` |
| Artifact SHA-256 | `9af5b48eb941e55c027ca4ad6ca7aab74f8d7f7ab6fc7b8426f32066f9db547c` |
| Analysis SHA-256 | `4d20bf56f020eeed33d49f70722a00a9f2fc1445f80181fe52ab84de68e749f5` |

The closeout workflow independently freezes these identifiers and rejects a
different source, artifact, analysis digest, maturity status, or authority
boundary.

## 3. What A2.3 established

Within its focused surrogate verification scope, A2.3 established that:

1. the A2 closure can be evaluated on every cell and accepted step of the
   focused finite-pipeline case;
2. the shadow observer is read-only;
3. shadow ON and OFF produce bitwise-identical authoritative conservative
   trajectories;
4. HEM pressure and HEM acoustic speed retain flux and CFL authority;
5. total mass, momentum, and energy are not damaged;
6. the constructed `tau -> 0` case recovers the HEM limit;
7. finite `tau` produces visible shadow differences in pressure, temperature,
   void fraction, and quality lag;
8. `tau -> infinity` is bitwise equivalent to `NoPhaseChange`;
9. the focused execution is deterministic and reproducible.

These are software and model-architecture findings for the configured surrogate
case. They are not a validated physical prediction for liquid CO2.

## 4. Authority boundary retained

The authoritative line remains:

```text
accepted conservative state
        ↓
surrogate HEM rho/e closure
        ↓
p_HEM, T_HEM, c_HEM
        ↓
Rusanov flux and CFL
```

The shadow line remains:

```text
accepted conservative state
        ↓
rho, e, transported q
        ↓
A2 HNE shadow closure
        ↓
p_HNE, T_HNE, alpha_HNE, c_HNE(diagnostic)
        ↓
record and compare only
```

The following permissions remain false:

```text
p_HNE -> flux                         false
T_HNE -> flux                         false
alpha_HNE -> flux                     false
c_HNE -> flux or CFL                  false
HNE boundary characteristics         false
hydrodynamic HNE coupling             false
```

## 5. Maturity after closeout

```text
IMPLEMENTED                                  true
FINITE-PIPELINE SHADOW INTEGRATION           true
DIAGNOSTIC EVIDENCE READY                    true
A2.3 FORMALLY CLOSED                         true

HYDRODYNAMIC COUPLING ALLOWED                false
PHYSICAL HNE VERTICAL SLICE                  false
WORKING VERTICAL SLICE                       false
VERIFIED                                     false
ACCEPTED                                     false
PHYSICALLY VALIDATED                         false
DESIGN-USE ACCEPTED                          false
PRODUCTION APPROVED                          false
```

Formal closeout means that the result and its limits are frozen. It does not mean
that the HNE model has reached verification, validation, or design-use maturity.

## 6. Retained limitations

The following limitations remain active:

- surrogate constituent EOS only;
- no validated nonequilibrium acoustic derivative;
- no HNE pressure feedback to flux;
- no nucleation, metastability, or bubble-growth model;
- no slip model;
- relaxation time `tau` is not physically validated;
- no real-fluid HNE backend compatibility;
- no physical discharge-feedback loop;
- P1 mesh/CFL limitations remain active.

None of these limitations is silently relaxed by this closeout.

## 7. Next authorized action

The only next action authorized by this closeout is:

```text
P2-A2.4-1
Nonequilibrium Acoustic Closure Contract
```

A2.4-1 shall define, without changing the FVM solver:

1. the perturbation path used to define each acoustic response;
2. the distinction between frozen-quality, equilibrium-manifold, and
   finite-relaxation regimes;
3. the required thermodynamic constraint, such as the energy or entropy path;
4. the meaning and authority of any derivative used to construct `c^2`;
5. positivity and hyperbolicity requirements;
6. fail-closed conditions;
7. evidence required before any acoustic value can enter flux, CFL, boundary
   characteristics, or hydrodynamic coupling.

A2.4-1 is a contract and design increment only. The coupling gate remains closed
throughout that increment.
