# Stage 7 — Pipeline Mesh-Sensitivity Implementation Status

`IMPLEMENTED; FIXED NINE-RUN MATRIX EXECUTED; TRACEABLE VALIDATION REQUIRED; VERIFICATION ONLY`

## Fixed scope

The implementation follows the reviewed plan merged in PR #80:

```text
cell counts:       32 / 64 / 128
final pressures:   2 / 3 / 4 MPa
CFL:               0.10 for every run
spatial flux:      existing first-order Rusanov
step caps:         2000 / 4000 / 8000
matrix size:       9 runs
```

Only `n_cells`, derived `dx`, and the predeclared mesh-dependent step cap vary. The
merged PR #77 geometry, initial state, boundary schedules, phase/projection algorithms,
evidence threshold, accepted-state tolerance, and budget tolerances remain unchanged.

## Fixed observations

```text
2 MPa:
  32 cells   ACCEPTED_FIRST_CROSSING   q_max=3.773646403587342e-6
  64 cells   GUARD_FAILURE             q_max=4.859613684053916e-7
  128 cells  ACCEPTED_FIRST_CROSSING   q_max=1.1990738237934995e-6

3 MPa:
  32 cells   ACCEPTED_FIRST_CROSSING   q_max=1.6022773573103607e-6
  64 cells   GUARD_FAILURE             q_max=9.661600240860858e-9
  128 cells  GUARD_FAILURE             q_max=5.977506786571329e-7

4 MPa:
  32 cells   GUARD_FAILURE             q_max=9.672588429198319e-9
  64 cells   GUARD_FAILURE             q_max=5.977506779042054e-7
  128 cells  GUARD_FAILURE             q_max=3.8580990283897163e-7
```

The 32-cell 4 MPa row reproduces the merged PR #77 outcome, crossing evidence,
final-state SHA256, and run-signature SHA256 exactly before refined-mesh results are
accepted.

## Diagnostic interpretation

The 4 MPa raw crossing is present on all three reviewed meshes. Its crossing-depth
coordinates are non-monotone, while the normalized crossing time and position show a
smaller 64→128 change than the 32→64 change. The retained labels are:

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

These labels do not establish formal convergence order, a mesh-independent quality
value, physical nucleation, or design accuracy.

## Traceability

The authoritative artifact path records and validates:

```text
case ID
model = HEM
backend = coolprop_co2
CoolProp version
source and checkout Git SHA
GitHub workflow identity
Python and NumPy versions
runner and evidence-wrapper SHA256
```

Every generated result PNG visibly includes case, model, backend, version, and source
Git SHA; the same identity is embedded in PNG metadata.

## Approval boundary

```text
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
near_saturation_acoustic_continuity_approved = false
two_phase_acoustic_accuracy_band_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

The implementation is not merge-complete until the final traceable workflow, full
repository suite, and review-thread resolution succeed on the final head.
