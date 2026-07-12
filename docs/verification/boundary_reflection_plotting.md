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

## Generate the three primary wave plots

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

## Generate the boundary flux and cumulative-budget plot

The fourth diagnostic figure uses the numerical flow rates recorded in
`*_boundary_history.csv`:

```powershell
python -m liquid_gas_transient.plot_boundary_reflection_fluxes `
  verification/<case-output-directory> `
  --case-name coolprop_rigid_wall_boundary_reflection
```

For the fixed-pressure case, use:

```powershell
python -m liquid_gas_transient.plot_boundary_reflection_fluxes `
  verification/<case-output-directory> `
  --case-name coolprop_fixed_pressure_boundary_reflection
```

The command writes:

- `*_boundary_flux_budget_history.png`

The four panels show:

1. right-boundary numerical mass flow rate `[kg/s]`
2. right-boundary numerical energy flow rate `[W]`
3. cumulative boundary mass exchange `[kg]`
4. cumulative boundary energy exchange `[J]`

The cumulative quantities are stepwise integrals using the recorded rates and
`dt_s` values. Positive values follow the sign convention stored in the boundary
telemetry; they must be interpreted together with the documented positive-x and
domain-rate conventions.

For an ideal rigid wall, the mass and energy exchange should remain near zero.
For the ideal fixed-pressure boundary, nonzero exchange is allowed and should be
consistent with the domain budget diagnostics.

## Interpretation guardrails

- These figures are software/numerical verification evidence only.
- They are not physical Validation or design-use acceptance.
- The rigid wall is an infinite-impedance idealization, not an actual closed valve.
- The fixed-pressure boundary is a zero-impedance idealization, not an actual reservoir.
- Boundary pressure and velocity are documented diagnostic midpoint values, not a Godunov star state.
- Numerical mass and energy flow rates are the external-face fluxes used by the FVM update.
- CoolProp remains `not_approved_for_design_use`.
