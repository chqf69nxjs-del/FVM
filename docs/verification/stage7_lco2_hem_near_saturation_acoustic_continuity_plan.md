# Stage 7 Gate 5 near-saturation acoustic-continuity review

## Status

`ACTIVE GATE 5; CONTRACT LOCKED BEFORE RESULTS; VERIFICATION ONLY`

This plan implements Issue #95 without changing production FVM, the equilibrium sound-speed formula, Rusanov flux, boundary conditions, crossing thresholds, or quality projection.

## Reviewed closure

```text
c_eq^2 = (dp/drho)|e + (p/rho^2) (dp/de)|rho
```

The existing guarded, phase-preserving central finite-difference implementation is called directly. No alternative endpoint stencil, clipping, threshold tuning, or formula substitution is permitted.

## Fixed grid

- Pure CO2 with CoolProp 8.0.0.
- Pressure: 2, 3, and 4 MPa.
- Liquid-side subcooling: 5, 1, 0.1, and 0.01 K.
- Saturated-liquid endpoint: q = 0.
- Open-two-phase quality: 1e-12, 1e-10, 1e-8, 1e-6, 1e-4, and 1e-2.
- Independent rho/e relative perturbations: 0, +/-1e-10, +/-1e-8, and +/-1e-6.

The perturbation grid is applied to the 0.01 K subcooled state and q = 1e-10, 1e-8, and 1e-6 states at every pressure. Perturbations are diagnostic only and never alter the base-state classification.

## Isolation boundary

The diagnostic imports no solver, grid, boundary, flux, or CFL module. It uses only CoolProp phase/property evaluation and the existing equilibrium acoustic estimator.

## Required evidence

The workflow generates:

- `summary.json`
- `state_points.csv`
- `perturbations.csv`
- `report.md`
- `sound_speed_vs_quality.png`
- `sound_speed_vs_saturation_approach.png`
- `perturbation_sensitivity.png`
- `artifact_sha256.txt`
- dedicated, related Stage 7, and full-repository JUnit XML
- exact Git/runtime provenance

The exact q = 0 endpoint remains in the state table even when the phase-preserving central stencil refuses evaluation.

## PR #79 forensic comparison

The independent map retains, but does not rerun or reclassify, the following observation:

```text
accepted liquid c_eq:  461.25669095385655 m/s
raw micro-quality c_eq: 43.22308393386989 m/s
raw pressure:           4273927.110515705 Pa
raw q_eq:               9.672588429198319e-9
```

## Permitted initial labels

- `CONTINUOUS_LIMIT_SUPPORTED`
- `FINITE_JUMP_MODEL_CONSISTENT`
- `NEAR_SATURATION_PROPERTY_SENSITIVE`
- `PHASE_CLASSIFIER_SENSITIVE`
- `IMPLEMENTATION_DISCONTINUITY_SUSPECTED`
- `ACOUSTIC_REVIEW_INCONCLUSIVE`

Labels are evidence classifications only. They do not approve physical accuracy.

## Approval boundary

All remain false in this PR:

```text
Gate_5_execution_complete
near_saturation_acoustic_continuity_approved
two_phase_acoustic_accuracy_band_approved
post_crossing_propagation_approved
Gate_P2_passed
physical_validation
design_use_acceptance
production_hem_activation_approved
```
