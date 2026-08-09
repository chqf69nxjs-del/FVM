# Stage 7 MUSCL Scaffold Validation Commands

## Windows review recheck

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_stage7_v013_baseline_definition.py tests/test_stage7_muscl_reconstruction.py
python -m pytest -q
git diff --check origin/main...HEAD
git status -sb
```

Expected committed inventory at the validated scaffold head:

```text
V-013 baseline-definition tests:  4
MUSCL reconstruction tests:       9
focused total:                    13
full repository total:           398
```

## GitHub validation evidence

```text
validation head:  c00cd2ccd5ced099bf4ea0e31a3f8a1070681a92
workflow run:     29721475855
focused step:     success
full suite step:  success
committed diff:   success
clean checkout:   success
tracked files:    unchanged
permanent CI:     4 / 4 success
```

The temporary validation workflow reports generated untracked test/build artifacts after
execution. It separately proves that the checkout was clean before setup and that no
tracked or staged repository file changed.
