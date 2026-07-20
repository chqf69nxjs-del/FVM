# Stage 7 Scalar-Advection Validation Commands and Evidence

This increment is stacked on PR #52. Until PR #52 is merged, use its branch as the
committed-diff base.

## Focused and full tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q `
  tests/test_stage7_v013_baseline_definition.py `
  tests/test_stage7_muscl_reconstruction.py `
  tests/test_stage7_scalar_advection.py
python -m pytest -q
```

Validated inventory:

```text
V-013 baseline-definition tests:  4 passed
MUSCL reconstruction tests:       9 passed
scalar-advection tests:           18 passed
focused total:                    31 passed
full repository:                  416 passed, 0 skipped
```

## Canonical comparison artifacts

```powershell
$env:PYTHONPATH = "src"
python -m liquid_gas_transient.verification_scalar_advection `
  --output-dir .tmp/stage7_scalar_advection `
  --meshes 100 200 400
```

Expected artifact names:

```text
stage7_scalar_advection_comparison.json
stage7_scalar_advection_comparison.csv
stage7_scalar_advection_summary.md
stage7_scalar_advection_profiles.npz
```

Validated matrix:

```text
meshes:                   100 / 200 / 400
variants per mesh:        5
planned / completed runs: 15 / 15
required artifacts:       4 / 4
mass conservation:        all within 1e-12 relative error
new extrema:              none
TV increase:              none
scope flags:              all guarded / false as required
```

## Committed diff and working tree

Before PR #52 is merged:

```powershell
git diff --check origin/agent/stage7-muscl-reconstruction-scaffold...HEAD
git diff --check origin/main...HEAD
git status -sb
```

After PR #52 is merged and this PR is retargeted to `main`:

```powershell
git fetch origin main
git diff --check origin/main...HEAD
git status -sb
```

Generated evidence should be written outside tracked repository paths or removed before
review-ready state. Validation must distinguish generated untracked files from changes to
tracked or staged repository files.

## Recorded GitHub validation

```text
validation head:  40e1741f0dd4bc0176447a5bbe2516ef49f148a8
workflow run:     29724623614
artifact ID:      8453783798
artifact SHA256:  642bbea77078f30ce920876ea2b89bee2d8683099e3ae277ce0431f37612e6f2
focused tests:    success
full suite:       success
artifact checks:  success
stacked diff:     success
main diff:        success
tracked/staged:   unchanged
```

Permanent workflows at the validation head:

```text
CoolProp Wave Regression:                     29724623614 success
CoolProp Controlled Pressure Ramp Regression: 29724623616 success
CoolProp Boundary Reflection Regression:      29724623622 success
CoolProp Internal Valve Regression:           29724623627 success
```

The temporary validation modifications were removed after evidence capture. The scalar
harness and tests retained the validated blobs:

```text
99de19041123fd521aa3326b7fca44601e033f75
8fdea83b04678e74a29117b9c8b72b41370d39d4
```

Final-head permanent workflow results should be recorded in the PR body after stacked
branch cleanup. Runtime values remain diagnostic and are not portable acceptance bands.
