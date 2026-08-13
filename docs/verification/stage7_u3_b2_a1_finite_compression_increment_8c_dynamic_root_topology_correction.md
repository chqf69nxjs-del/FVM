# Stage 7 U3 B2 A1 finite-compression Increment 8C dynamic root-topology correction

## Status

`IMPLEMENTATION_CORRECTION_ONLY / FIXED_BEFORE_RERUN_RESULT`

The first Increment 8C run loaded the authoritative step-494 state and stopped before step 495. The fixed 12-node Hugoniot scan already contained exactly one B1-success compatibility bracket. The step-493 diagnostic helper intentionally treated that condition as a reproduction mismatch because its sole purpose was to reproduce the earlier `NO_UNIQUE_HUGONIOT_ROOT` stop.

That reproduction requirement is not a physical or numerical condition for later evolving states.

The corrected dynamic classifier applies:

```text
fixed successful-domain bracket count = 1
  -> solve that bracket directly

fixed bracket count = 0 and leading B1-unavailable domain exists
  -> perform the fixed 48-iteration Guard-front refinement
  -> solve one refined successful-domain bracket

fixed/refined bracket count > 1
  -> fail-closed multiple-root stop

no root through chi cap
  -> fail-closed cap or scope classification
```

Every selected root must retain the unchanged Hugoniot, B1, Lax, entropy, phase, direction, energy, reaction and compatibility gates. Failed B1 states remain unavailable and never form a root endpoint or applied flux.

The correction changes only the applicability of the step-493 reproduction assertion. It does not change any model, contract, tolerance, scan node, `chi` limit, solver update, conservation gate or formal project state.
