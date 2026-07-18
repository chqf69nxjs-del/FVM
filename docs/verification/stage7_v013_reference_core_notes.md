# Stage 7 V-013 Independent Reference Core Notes

## Status

`IMPLEMENTED; TESTED; READY FOR REVIEW`

## Scope

This increment implements only the independent linear-acoustic reference core required
before connecting V-013A/B/C to the production FVM cases.

It is software / numerical verification only. It is not physical Validation,
design-use acceptance, a production MOC solver, or a nonlinear / two-phase reference.

## Implemented reference path

```text
src/liquid_gas_transient/verification/linear_acoustic_reference.py
```

Implemented components:

- pressure-dimension characteristic transforms `A+ / A-`;
- pressure and velocity reconstruction;
- Gaussian characteristic profile;
- bounded analytical translation with at most one reflection;
- transmissive, rigid-wall, and fixed-pressure characteristic identities;
- independent nodal MOC translation at `CFL=1`;
- complete `A+`, `A-`, pressure, and velocity histories;
- linear acoustic-energy proxy;
- deterministic UTF-8 JSON snapshot output.

## Independence evidence

The reference module imports only:

- Python standard-library modules;
- NumPy and `numpy.typing`.

It does not import or call:

- `FvmSolver`;
- production numerical fluxes;
- production boundary-condition classes;
- production case runners;
- FVM timestep or telemetry logic;
- CoolProp.

The pure test suite parses the module AST and rejects prohibited import roots.

## Reference self-test result

Verification head:

```text
f44b569b5dbe388840860415987486bef47602cf
```

Results:

```text
reference-core self-tests: 23 passed, 0 skipped
full repository tests:     299 passed in 150.31 s
compileall:                 success
deterministic JSON:         byte-identical across repeated writes
```

The self-tests cover:

- characteristic round-trip reconstruction;
- pure right-going and left-going states;
- exact grid-aligned Gaussian translation;
- exact one-cell MOC transport at `CFL=1`;
- rigid-wall reflection identity;
- fixed-pressure reflection identity;
- MOC-versus-analytical agreement before reflection;
- MOC-versus-analytical agreement after one reflection;
- pressure / velocity boundary residuals;
- acoustic-energy-proxy identity;
- input-array immutability;
- invalid-configuration rejection;
- deterministic artifact output;
- prohibited-import separation.

## Temporary verification artifact

```text
artifact name: v013-reference-core-c571bff4f796f2814814d178beaebf6a04014a4c
artifact SHA256: eeaccfdccf8b791b037b28b46b41e3446dc4e70bec5b5beb8b9d9b3868c245e3
deterministic JSON SHA256: a5d2a5764b4c65613aed9d6254f315b41055fa51968a89d9cf7d5b290c3cbd64
```

The temporary workflow is removed before review and is not a permanent CI-light gate.

## Guardrails retained

- the reference remains verification-only;
- the analytical evaluator solves the fixed linearized PDE, not nonlinear real-fluid
  equations;
- MOC `CFL=1` exact translation is an algebraic self-check, not proof that MOC is
  physical truth;
- the finest MOC or FVM mesh is not an exact solution;
- no FVM regression band is defined in this increment;
- no production solver behaviour changed;
- physical Validation and design-use acceptance remain false.

## Next action

1. define stable V-013A case and sample identifiers;
2. connect the existing small-amplitude FVM source case without changing solver
   physics;
3. record `rho0` and `c0` provenance for the independent reference;
4. compare FVM, MOC, and analytical incident-wave results;
5. only after V-013A review, proceed to rigid-wall and fixed-pressure reflection.
