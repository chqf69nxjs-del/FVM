# V-012 Windows CoolProp application-control blocker

## Status

V-012A local installed-CoolProp execution is blocked on the current Windows
machine. Work is saved on branch
`agent/stage6-v012-uniform-valve-baseline` and draft PR #35. No merge or
acceptance decision is permitted while this blocker remains.

## Observed behavior

The local `CoolProp` package is present, but importing its native extension
fails with:

```text
ImportError: DLL load failed while importing _constants:
application control policy blocked this file
```

The failure occurs before the V-012A solver starts, while Python imports
`CoolProp.constants` / the `_constants` native module.

Observed local evidence:

- focused V-012 tests: `8 passed, 3 skipped in 13.24s`
- the skipped tests are installed-CoolProp paths and therefore do not constitute
  V-012A numerical evidence
- V-012A artifact generation did not start
- no V-012A PNG was accepted
- full repository run: `18 failed, 205 passed, 11 skipped`
- all 18 failures trace to the same blocked CoolProp native import

## Interpretation

This is an operating-environment / application-control failure, not evidence of
a valve solver, telemetry, plotting, or numerical-regression failure. The
package is discoverable, so tests that use `pytest.importorskip("CoolProp")`
encounter an import-time native-module failure rather than a normal
package-missing skip.

The three existing GitHub regression workflows pass on the PR head, but they do
not replace the required local installed-CoolProp V-012A baseline and visual
review.

## Safe stop

- branch and draft PR are preserved
- no destructive Git operation occurred
- no accepted baseline artifact was overwritten
- no regression band was created or relaxed
- no solver physics, Kv law, Mach-cap formula, or energy treatment was changed
- PR #35 remains draft

## Required resolution

1. Identify the exact blocked CoolProp `.pyd` or dependent DLL from the Windows
   CodeIntegrity Operational log.
2. Determine the enforcing App Control policy and whether the block is expected.
3. Have the device owner or administrator allow an approved CoolProp/Python
   binary source, or provide an approved environment in which the official
   CoolProp package imports successfully.
4. Do not disable or bypass organizational application-control policy merely to
   pass the test.
5. After remediation, verify the import directly, then rerun the focused V-012
   tests, generate the baseline and four PNGs, visually review them, and rerun
   the full suite.

## Resume gate

The minimum resume check is:

```powershell
python -c "import CoolProp; from CoolProp.CoolProp import PropsSI; print(CoolProp.__version__); print(PropsSI('D','P',8e6,'T',280,'CO2'))"
```

V-012A work may resume only when this command succeeds in the same virtual
environment used for the repository tests.
