# Stage 7 MUSCL Scaffold Validation Commands

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_stage7_v013_baseline_definition.py tests/test_stage7_muscl_reconstruction.py
python -m pytest -q
git diff --check origin/main...HEAD
git status -sb
```

The new reconstruction tests expand to nine pytest cases because the supported limiter
matrix is parametrized.
