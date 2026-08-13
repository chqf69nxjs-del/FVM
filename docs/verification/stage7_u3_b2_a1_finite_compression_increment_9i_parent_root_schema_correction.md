# Stage 7 U3 B2 A1 finite-compression Increment 9I parent-root schema correction

## Status

`IMPLEMENTATION_CORRECTION_ONLY / FIXED_BEFORE_RERUN_RESULT`

The first Increment 9I run verified the Increment 9H artifact and reached the common full-horizon runner before solver construction. It then stopped while restoring the previous accepted root pressure.

```text
source Git SHA:
825210c4b11850278c44d094486abbd89b170996

workflow run:
31670007778

job:
94352512260

failure:
KeyError: 'root_pressure_pa'
```

The Increment 9H `selected_root.csv` preserves the selected-root schema used by the seeded-island diagnostic:

```text
pressure_pa
requested_chi
root_mass_residual_kg_s
...
```

The shared full-horizon runner expects the accepted-parent alias:

```text
root_pressure_pa
```

Increment 9I therefore maps only:

```text
root_pressure_pa = pressure_pa
```

when restoring the previous accepted root from the verified Increment 9H artifact.

No numerical value is changed. The correction does not modify the state, root, B1 behavior, local admissibility, seeded interval rule, Hugoniot relation, tolerance, flux, solver update, conservation gate, or any formal project state.
