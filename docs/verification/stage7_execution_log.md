# Stage 7 Execution Log

This log records V-013 MOC / linear-acoustic cross-verification work.

## 2026-07-18 — V-013 specification checkpoint

Status:

```text
IN_PROGRESS; SPECIFICATION MERGED
```

Specification:

```text
docs/verification/v013_moc_linear_acoustic_cross_verification_spec.md
```

The initial Stage 7 scope is restricted to:

1. small-amplitude incident-wave propagation;
2. rigid-wall reflection;
3. fixed-pressure reflection.

The reference path will contain two independently testable levels:

- an analytical characteristic evaluator for a smooth Gaussian pulse and at most one
  reflection;
- a discrete nodal MOC translator with `CFL=1`.

Independence rules:

- the reference shall not import `FvmSolver`, production numerical fluxes, production
  boundary classes, production case runners, or FVM telemetry recorders;
- MOC shall receive explicit `rho0` and `c0` values and shall not call CoolProp;
- comparison windows shall exclude secondary-boundary returns;
- no FVM error band is selected before the initial observation matrix is reviewed;
- MOC is a verification-only path and shall not be introduced into the production
  solver.

Planned initial matrix:

```text
cases: V-013A / V-013B / V-013C
FVM meshes: 100 / 200 / 400 at CFL 0.5
MOC meshes: 100 / 200 / 400 at CFL 1.0
```

No production solver behaviour is changed by this specification increment.

## 2026-07-18 — V-013 specification merged

- PR: `#44`
- merge commit: `349bdefe16816b55b0b64495b1ebf17bedab71e5`
- next action: pure analytical / MOC reference implementation
- production solver changes: none

## 2026-07-18 — V-013 independent reference core

Status:

```text
IMPLEMENTED; TESTED; MERGED
```

Implementation:

```text
src/liquid_gas_transient/verification/linear_acoustic_reference.py
tests/test_linear_acoustic_reference.py
docs/verification/stage7_v013_reference_core_notes.md
```

Verification head and results:

```text
head:                       f44b569b5dbe388840860415987486bef47602cf
reference-core self-tests:  23 passed, 0 skipped
full repository tests:      299 passed in 150.31 s
compileall:                  success
deterministic JSON SHA256:  a5d2a5764b4c65613aed9d6254f315b41055fa51968a89d9cf7d5b290c3cbd64
temporary artifact SHA256:  eeaccfdccf8b791b037b28b46b41e3446dc4e70bec5b5beb8b9d9b3868c245e3
```

Implemented and self-tested:

- `A+ / A-` conversion and pressure / velocity reconstruction;
- right-going and left-going Gaussian analytical translation;
- at-most-one-reflection image formulas;
- exact one-cell nodal MOC translation at `CFL=1`;
- transmissive, rigid-wall, and fixed-pressure boundary identities;
- MOC / analytical equality at grid-aligned incident and reflected samples;
- acoustic-energy proxy;
- input immutability and deterministic JSON output;
- AST-based prohibited-import guard.

The module imports only Python standard-library modules and NumPy. It does not import
production FVM solver, flux, boundary, case, timestep, telemetry, or CoolProp code.
No production solver behaviour was changed.

## 2026-07-18 — V-013 reference core merged

- PR: `#46`
- merge commit: `3945136dbe26db98044e49fb093b37122bf8b1fd`
- reference-core self-tests: `23 passed`, `0 skipped`
- full repository tests: `299 passed in 150.31 s`
- production solver changes: none
- V-013 status: `IN_PROGRESS`
- next action: V-013A incident propagation integration
