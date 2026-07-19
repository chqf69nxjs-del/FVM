# Stage 7 V-013B Rigid-Wall Reflection Observation Notes

Status: `OBSERVED; MERGED` in PR #49. Merge commit:
`bc874193de6a4c019073b6cf629e99ec5dfa6602`. V-013 baseline formalization is in
progress.

## Primary observation evidence

- GitHub Actions run `29684930259`
- PR head `dbb17b45f19a973741da4998e57591a529fb25f2`
- Actions merge SHA `8670c95122cc0d470469b8445590cd03029133b8`
- focused `57 passed, 0 skipped`; full repository `350 passed, 0 skipped`
- runs `3/3`; saved-artifact plots `7/7`; plotting errors `0`
- CoolProp `8.0.0`; artifact entries `59`
- artifact ID `8441899419`
- artifact digest
  `sha256:709a78a29bd21d9b01d8785e296b30a8085c7d5af6a26aba7b808c9c6be19861`
- plotting records `solver_rerun = false` and `numerical_results_changed = false`

Recorded reference state:

```text
rho0 = 922.9172130294444 kg/m3
c0   = 557.4488783994866 m/s
```

## Primary numerical observations

| n | Δx [m] | mean FVM pressure reflection coefficient | mean FVM velocity reflection coefficient | wall pressure amplification ratio | final reflected pressure peak ratio |
|---:|---:|---:|---:|---:|---:|
| 100 | 1.00 | 0.65777978 | -0.65771904 | 0.85567464 | 0.33987059 |
| 200 | 0.50 | 0.71062343 | -0.71062316 | 1.11654918 | 0.44696373 |
| 400 | 0.25 | 0.77589432 | -0.77589440 | 1.38056539 | 0.57499450 |

The expected rigid-wall signs and direction are observed: the right-going `A+`
incident pulse returns as a left-going `A-` pulse, pressure remains positive, and
velocity reverses sign. The right wall has exactly zero recorded face velocity,
mass flux, and energy flux for all three meshes.

The measured reflection amplitudes and wall pressure rise move monotonically toward
the ideal linear-acoustic values (`+1`, `-1`, and `2`) as the mesh is refined. They
remain materially below the ideal values at `n=400`. The final reflected pressure
peak retains about `57.5%` of the analytical peak, consistent with the strong FVM
numerical diffusion already observed in V-013A.

Maximum FVM normalized L2 differences also decrease monotonically:

| n | maximum pressure L2 difference | maximum velocity L2 difference |
|---:|---:|---:|
| 100 | 0.66558518 | 0.66558532 |
| 200 | 0.54412398 | 0.54412425 |
| 400 | 0.40713104 | 0.40713146 |

These are observations, not accuracy-acceptance or CI regression bands.

## Derived-metric and figure review

The first full three-mesh evidence run completed successfully, but review found that
the wall-contact analytical velocity field is zero. Normalizing velocity error by
that zero field produced meaningless relative values. The corrected policy is now
persisted in each comparison artifact:

```text
pressure: analytical_pressure_perturbation_pa
velocity: analytical_pressure_perturbation_pa / (rho0 * c0)
A+ / A-:  analytical_pressure_perturbation_pa
```

After correction, all FVM/MOC velocity norms are finite. The FVM wall-contact
velocity L2 differences are approximately `3.08e-6`, `4.85e-6`, and `7.37e-6` for
`n=100 / 200 / 400`. Production FVM states and the principal reflection results are
unchanged.

The rigid-wall-condition figure now displays exact zero wall velocity as zero on a
linear axis rather than replacing it with a machine-tiny positive value. All seven
figures embed case, model, property backend, CoolProp version, output version, and
the software/numerical-verification, non-design-use disclaimer.

## Completion guardrails

The temporary observation/fix workflows, trigger, and patch script were removed
after evidence capture. Production solver, numerical-flux, and `ReflectiveBoundary`
behaviour are unchanged. Physical Validation and design-use acceptance remain
`False`; the backend is `not_approved_for_design_use`; MOC remains verification-only;
the finest mesh is not exact; no V-013 CI-light or design-accuracy band has been set.
