# Stage 7 U3 B2 A1 Weak Compression Bridge v0.1 Increment 4F refinement evidence-gate correction

## Status

`MODEL_REVIEW_ONLY / EVIDENCE_AGGREGATION_CORRECTION / FIXED_BEFORE_EXECUTION_RESULT`

This note corrects one over-constrained evidence aggregation rule found during read-back review of the Increment 4F implementation before any Increment 4F workflow result was produced.

It does not change the Guard-front refinement algorithm, B1, a B1 formal outcome, the root law, the root tolerance, the Weak Compression `chi` scope, the characteristic relation, the positive-pressure scan, the locked B2 v1 Contract, the production B2 Adapter, `FvmSolver`, or any formal project state.

## Over-constrained rule

The first Increment 4F postprocessor required every accepted Guard-front-refined step to contain at least one midpoint with:

```text
NONPOSITIVE_KINETIC_ENERGY_HEAD
```

The physical and implementation contract fixed by Increment 4F is instead:

```text
the lower categorical side is B1-unavailable
```

with its allowed exact formal outcomes limited to:

```text
REVERSE_PRESSURE_OR_FLOW_NOT_SUPPORTED
NONPOSITIVE_KINETIC_ENERGY_HEAD
```

A particular refined step may contain only the reverse-pressure outcome, only the nonpositive-kinetic-head outcome, or both, depending on where floating-point-representable midpoint pressures fall relative to the unchanged B1 categorical boundaries.

Requiring both categories to appear on every step is not a physics, root, B1, or conservation requirement. It is an unnecessary evidence-shape constraint.

## Fixed aggregation gate

For every accepted Guard-front-refined root, require:

```text
guard_front_reverse_pressure_count
+
guard_front_nonpositive_head_count
> 0
```

Also require:

```text
guard_front_success_count > 0
```

Across the complete Increment 4F evidence, require at least one refined step to reproduce:

```text
guard_front_nonpositive_head_count > 0
```

because the authoritative corrected Increment 4E diagnostic established that this formal outcome exists at the first Guard-front crossing.

All other Increment 4F gates remain unchanged, including:

```text
first refinement step = 452
failed B1 states never serve as root endpoints
failed B1 states never construct a flux
final lower categorical endpoint remains unavailable
final upper categorical endpoint remains B1-success and admissible
refined first-success residual >= -1.0e-8 kg/s
refined first-success stagnation pressure > back pressure
selected root pressure and stagnation pressure > back pressure
root chi <= 1.0e-6
root residual <= 1.0e-8 kg/s
negative root slope
outward, subsonic, liquid root
energy and reaction ledgers close
pre-step-452 reproduction passes
full 2L/c0 target is reached for a working-slice pass
formal project states remain false
```

No failed B1 state is reclassified as success. No tolerance is introduced. This correction changes evidence aggregation only.
