# Stage 7 U3 B2 A1 finite-compression Increment 8B import-binding correction

## Status

`IMPLEMENTATION_CORRECTION_ONLY / FIXED_BEFORE_RERUN_RESULT`

The first Ubuntu 22 fallback run for Increment 8B reached the actual one-step runner after source checks, dependency installation and both authority-artifact downloads. It then stopped before reconstructing or advancing the solver because the runner referenced the finite-compression base module through the name `base` without importing that module.

```text
run: 31662694419
job: 94330653832
failure: NameError
message: name 'base' is not defined
first failing expression: base.CASE_ID
FvmSolver step 494 attempted: false
```

This correction binds:

```python
import u3_b2_a1_finite_compression_hugoniot_8_step as base
```

into the Increment 8B runner module before calling its unchanged `main()` entry point.

The correction does not change:

```text
accepted step-493 state
Increment 8A root authority
Hugoniot relation
B1 behavior or guards
Guard-front iteration count
compatibility-root tolerance
finite-compression chi cap
Euler flux construction
FvmSolver
post-step gates
formal project states
```

The corrected rerun must still verify both parent artifacts, reproduce the Increment 8A root, compare it to authority, and pass exactly one actual update from solver step 493 to 494. A passing result authorizes no step beyond 494.
