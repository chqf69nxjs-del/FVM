# V-012 Windows CoolProp application-control blocker

## Status

`RESOLVED` on 2026-07-15 after a Windows update and restart.

Work remains on branch `agent/stage6-v012-uniform-valve-baseline` and draft PR
#35. Resolution of this environment blocker does not by itself authorize merge
or mark V-012 complete.

## Initial observed behavior

The local `CoolProp` package was present, but importing its native extension
failed with:

```text
ImportError: DLL load failed while importing _constants:
application control policy blocked this file
```

The failure occurred before the V-012A solver started, while Python imported
`CoolProp.constants` / the `_constants` native module.

Initial local evidence:

- focused V-012 tests: `8 passed, 3 skipped in 13.24s`
- the skipped tests were installed-CoolProp paths and did not constitute V-012A
  numerical evidence
- V-012A artifact generation did not start
- no V-012A PNG was accepted at that point
- full repository run: `18 failed, 205 passed, 11 skipped`
- all 18 failures traced to the same blocked CoolProp native import

CodeIntegrity identified:

```text
policy ID: {0283ac0f-fff1-49ae-ada1-8a933130cad6}
blocked file: CoolProp/_constants.cp311-win_amd64.pyd
reason: Enterprise signing-level requirement / code-integrity policy
```

The CoolProp native files had existed since 2026-07-11 and had not been replaced
on the day of the failure. They were reported as unsigned. The incident was
therefore treated as an operating-environment / application-control event, not
as evidence of a valve solver, telemetry, plotting, or numerical-regression
failure.

## Safe stop taken

- branch and draft PR were preserved
- no destructive Git operation occurred
- no accepted baseline artifact was overwritten
- no regression band was created or relaxed
- no solver physics, Kv law, Mach-cap formula, or energy treatment was changed
- PR #35 remained draft

## Resolution evidence

After a Windows update and restart, the same repository virtual environment
successfully imported CoolProp and evaluated the reference density:

```text
CoolProp version: 8.0.0
PropsSI('D','P',8e6,'T',280,'CO2') = 922.9172130294444 kg/m3
```

The full repository suite was then run from the FVM repository root:

```text
234 passed in 69.79s
```

The V-012A baseline and four human-review PNGs were generated. Initial visual
review showed:

- requested and actual opening coincide at `0.5`
- valve pressure difference remains zero
- raw Kv Q, applied Q, and flux-derived Q remain zero
- no probe pressure or velocity disturbance is visible
- mass, energy, vapor-mass, momentum-difference, and Q-consistency residuals
  remain on the zero line
- software observation pass is `True`

The most plausible explanation is that the Windows update/restart refreshed or
corrected the active code-integrity state. No security policy was deliberately
disabled or bypassed.

## Remaining gate

The environment blocker is closed, but PR #35 remains draft until:

1. the readability-only plotter refinement is pulled,
2. the four PNGs are regenerated without rerunning the solver,
3. the plot-focused tests and full suite pass on the refined head,
4. the revised figures are reviewed.

The direct environment check remains:

```powershell
python -c "import CoolProp; from CoolProp.CoolProp import PropsSI; print(CoolProp.__version__); print(PropsSI('D','P',8e6,'T',280,'CO2'))"
```
