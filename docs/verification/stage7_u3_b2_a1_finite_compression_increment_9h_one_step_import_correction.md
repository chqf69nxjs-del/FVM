# Stage 7 U3 B2 A1 finite-compression Increment 9H one-step import correction

## Status

`IMPLEMENTATION_CORRECTION_ONLY / FIXED_BEFORE_RERUN_RESULT`

The first Increment 9H run verified both authoritative artifacts and reproduced the seeded-island root before stopping in the reused one-step runner prior to solver construction.

```text
source Git SHA:
8c9b9cd5f89e04fe42a8d7e11ed0b569801d8f79

workflow run:
31669549936

job:
94351167514

failure:
NameError: name 'base' is not defined
```

The reused module `u3_b2_a1_finite_compression_guard_front_one_step.py` references the module-global name `base` in `_run_one_step` but omits the import. The repository already contains the narrow correction pattern used by its earlier one-step workflow:

```python
import u3_b2_a1_finite_compression_hugoniot_8_step as base
runner.base = base
```

Increment 9H applies that same import binding before invoking the seeded-island one-step runner.

This correction changes no state, root, B1 behavior, Hugoniot relation, tolerance, diagnostic interval, flux, solver update, conservation gate, or formal project state.
