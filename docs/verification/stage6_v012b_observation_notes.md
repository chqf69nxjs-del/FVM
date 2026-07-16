# V-012B Small Driven-Flow Internal-Valve Observation Notes

## Scope

This note records software / numerical verification evidence for the V-012B
constant-opening, small driven-flow internal-valve baseline. It is not physical
Validation, design-use acceptance, or approval of a real valve model.

The fixed-pressure external boundaries are zero-impedance numerical
idealizations. The accepted observation window ends before the first
valve-generated wave reaches either external boundary.

## Configuration

- single-phase CoolProp CO2, CoolProp `8.0.0`
- pipe length `100 m`, diameter `0.30 m`
- valve at `x/L = 0.5`
- left/right requested pressure `8,000,500 / 7,999,500 Pa`
- temperature `280 K`
- constant opening `0.5`
- `n = 100`, `CFL = 0.5`
- initial velocity `0 m/s`
- initial valve pressure difference `1,000 Pa`
- target time `0.0636839425 s`
- first valve-generated boundary arrival `0.0896929534 s`

## Execution evidence

The one-command artifact run completed with
`overall_observation_execution_pass = true` and produced the numerical CSV/JSON
artifacts plus four PNG review figures.

Local Windows full repository result:

```text
239 passed in 69.97s
```

No working-tree output followed `git status --short` in the supplied log.

## Key numerical results

- initial raw Kv Q: `3.534291735286872e-05 m3/s`
- initial applied Q: `3.534291735286872e-05 m3/s`
- initial flux-derived Q: `3.534291735286872e-05 m3/s`
- initial raw/applied relative difference: `0`
- initial applied/flux relative difference: `0`
- minimum observed valve pressure difference: `485.794945 Pa`
- minimum applied Q: `2.4633668095242682e-05 m3/s`
- maximum applied face Mach: `8.969569363202504e-07`
- flow-sign consistency: `72 / 72 = 1.0`
- Mach-cap activation count: `0`
- hydraulic-separation count: `0`
- maximum pressure perturbation: `199.445663 Pa`
- maximum velocity: `3.876598270354068e-04 m/s`
- maximum flux-Q minus applied-Q: `3.3881317890172014e-21 m3/s`
- mass, energy, vapor-mass, and momentum-difference interface residuals: `0`
- energy budget relative residual: `-1.7941570435960072e-16`
- mass and vapor-mass budget relative residuals: `0`
- remained single phase: `true`

## Visual review

### Valve command and flow

- requested and actual opening coincide at `0.5`;
- the initial `1,000 Pa` valve pressure difference undergoes a bounded start-up
  adjustment and approaches approximately `600 Pa`;
- raw Kv, applied, and flux-derived Q remain visually coincident;
- the through-flow approaches approximately `2.74e-05 m3/s`;
- the Mach cap remains inactive.

### Probe pressure and velocity

- upstream probes develop negative pressure perturbations;
- downstream probes develop positive pressure perturbations;
- all observed velocities are positive, consistent with left-to-right flow;
- near-valve probes respond before the farther probes;
- the largest pressure perturbations are approximately `-200 / +200 Pa`, while
  the final observed velocity is approximately `3.88e-04 m/s`;
- `rho*c*u` is approximately `200 Pa`, providing a useful linear-acoustic
  consistency check for this small-disturbance case;
- no growing oscillation is visible within the pre-boundary-arrival window.

### Interface flux and budgets

- mass, energy, and vapor-mass two-sided flux mismatches remain on zero;
- momentum-flux difference follows `p_left - p_right`, with zero residual;
- flux-derived Q minus applied Q remains at roundoff scale;
- budget and consistency ratios remain well below their documented software
  observation tolerances.

## Interpretation

The initial pressure discontinuity does not remain as a static `1 kPa` valve
drop. The flow start-up launches a left-going decompression into the upstream
half and a right-going compression into the downstream half. Each side changes
by about `200 Pa`, leaving about `600 Pa` across the valve and producing the
observed positive flow. This pressure/velocity pattern is internally consistent
with the small-amplitude acoustic relation and the unchanged Kv law.

This is a numerical-path consistency observation, not physical Validation of
the valve or its loss/energy model. The hydraulic-loss proxy remains diagnostic
and is not removed from conserved `rhoE`.

## Status and next step

No solver-physics, conservation, sign, phase-state, or data-integrity blocker was
found for V-012B. The PR may proceed to review after current-head CI completes.
V-012 overall remains `IN_PROGRESS`; the next implementation increment is
V-012C, a small controlled opening ramp, followed by V-012D closing to a
nonzero opening and later mesh/CFL and formalization work.
