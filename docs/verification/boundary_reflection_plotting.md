# Stage 5 boundary-reflection plotting

This utility visualizes the CSV/JSON artifacts produced by the Stage 5 PR-B boundary-reflection runner.
It does not rerun or modify the solver.

## Install plotting support

```powershell
python -m pip install -e ".[plotting]"
```

For CoolProp execution and plotting together:

```powershell
python -m pip install -e ".[coolprop,plotting]"
```

## Generate plots

When an output directory contains exactly one boundary-reflection case:

```powershell
$env:PYTHONPATH = "src"
python -m liquid_gas_transient.plot_boundary_reflection_results `
  verification/<case-output-directory>
```

When the directory contains multiple `*_metrics.json` files, select the artifact stem explicitly:

```powershell
python -m liquid_gas_transient.plot_boundary_reflection_results `
  verification/<case-output-directory> `
  --case-name coolprop_rigid_wall_boundary_reflection
```

The command writes three PNG files into the same directory:

- `*_probe_pressure_history.png`: pressure disturbance at each probe
- `*_characteristic_history.png`: right-going `A+` and left-going `A-`, with incident/reflected evaluation windows
- `*_boundary_face_history.png`: right-boundary diagnostic pressure and velocity

## Interpretation guardrails

- These figures are software/numerical verification evidence only.
- They are not physical Validation or design-use acceptance.
- The rigid wall is an infinite-impedance idealization, not an actual closed valve.
- The fixed-pressure boundary is a zero-impedance idealization, not an actual reservoir.
- Boundary pressure and velocity are documented diagnostic midpoint values, not a Godunov star state.
- CoolProp remains `not_approved_for_design_use`.
