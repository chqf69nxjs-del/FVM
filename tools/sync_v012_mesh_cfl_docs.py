"""Temporary V-012 mesh/CFL documentation synchronizer."""
from pathlib import Path


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(
            f"replacement source not found in {path}: {old[:80]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(
        text + "\n" + block.rstrip() + "\n",
        encoding="utf-8",
    )


master = Path("docs/verification/MASTER_VERIFICATION_INDEX.md")
replace_exact(
    master,
    "- V-012 mesh/CFL observation planを`PLANNED; IMPLEMENTATION READY`として固定した。",
    "- V-012 mesh/CFL observationはPR #40で13-run計画を完走し、`OBSERVED; READY FOR REVIEW`。\n"
    "- 13 / 13 runs、aggregate analysis、9 comparison plots、264 testsをsuccessで確認した。\n"
    "- `n=400`追加は人間レビューの結果、初期50 / 100 / 200観測で主要傾向が明確なため不要と判断した。",
)

insertion = """### 直近観測段階

V-012 single-phase internal-valve mesh/CFL observation

- PR: `#40`
- observed source head: `9a63dd2bafc264c2a9e41ba68769b5b38cfafe78`
- planned / executed runs: `13 / 13`
- V-012A sentinel: `n=50`, `CFL=0.5`
- V-012B/C/D mesh: `n=50 / 100 / 200`, `CFL=0.5`
- V-012B/C/D CFL: `n=100`, `CFL=0.25 / 0.5`
- overall sweep execution pass: `True`
- aggregate trend analysis complete: `True`
- human-review comparison plots: `9`
- focused tests: `12 passed`, `0 skipped`
- full repository tests: `264 passed in 121.80 s`
- CoolProp version: `8.0.0`
- artifact SHA256: `c1cdf41cde8697cdecbd368ee380d925922921fbc77c1c8b77cb8820feb0d372`
- p50 timing offset improved monotonically with mesh refinement for V-012B/C/D
- finite-opening flow remained stable and applied/flux consistency stayed at roundoff
- complete-closure Q and mass / energy / vapor-mass through-flux remained at numerical zero
- all runs remained single phase with required budgets present
- `n=400` decision: not required for this observation increment

"""
replace_exact(
    master,
    "### 次の段階\n\nV-012 mesh/CFL observation\n",
    insertion
    + "### 次の段階\n\n"
    + "V-012 CI-light band specification and formalization\n",
)

replace_exact(
    master,
    """1. de-duplicated 13-run planとstable case IDを実装する。
2. V-012Aは`n=50`, `CFL=0.5`のuniform-state sentinelとして実行する。
3. V-012B/C/Dは`n=50 / 100 / 200`、`CFL=0.5`と、`n=100`、`CFL=0.25`を実行する。
4. finite-opening flow、wave direction/timing/amplitude、complete-closure zero through-flux、budget residual、runtimeのmesh/CFL傾向を比較する。
5. finest meshを厳密解、lower CFLを真値と扱わず、観測完了後にCI-light bandを提案する。
6. CI-light、formal report、SHA256 manifestを整備し、V-012全体のcompletion gateを判定する。""",
    """1. PR #40のmesh/CFL observation implementationと人間レビューを確定する。
2. 観測済み13-run結果からCI-light候補caseとregression band案を仕様化する。
3. bandはtest通過目的で緩めず、mesh/CFL差とnumerical floorから根拠を記録する。
4. permanent GitHub Actions CI-lightを追加し、skipなしで確認する。
5. V-012 formal reportとSHA256 manifestを整備する。
6. V-012全体のcompletion gateをレビューする。""",
)

replace_exact(
    master,
    "| V-012 | Single-phase valve operation | IN_PROGRESS | PR #34 specification、PR #35 V-012A、PR #36 V-012B、PR #37 V-012C、PR #38 V-012D、252 tests、opening/closing各9 review plots、mesh/CFL plan | mesh/CFL execution、CI-light、formal report、manifest未完了 | 13-run mesh/CFL observation |",
    "| V-012 | Single-phase valve operation | IN_PROGRESS | PR #34 specification、PR #35 V-012A、PR #36 V-012B、PR #37 V-012C、PR #38 V-012D、PR #40 13-run mesh/CFL observation、264 tests、9 comparison plots | CI-light、permanent Actions、formal report、manifest未完了 | CI-light band specification |",
)

replace_exact(
    master,
    "### Stage 6 / V-012 mesh/CFL observation plan",
    "### Stage 6 / V-012 mesh/CFL observation",
)
replace_exact(
    master,
    """```text
docs/verification/v012_single_phase_internal_valve_mesh_cfl_observation_plan.md
```""",
    """```text
docs/verification/v012_single_phase_internal_valve_mesh_cfl_observation_plan.md
docs/verification/stage6_v012_mesh_cfl_observation_notes.md
```

Observed GitHub Actions artifact:

- source head: `9a63dd2bafc264c2a9e41ba68769b5b38cfafe78`
- planned / executed runs: `13 / 13`
- aggregate comparison plots: `9`
- full repository tests: `264 passed`
- artifact SHA256: `c1cdf41cde8697cdecbd368ee380d925922921fbc77c1c8b77cb8820feb0d372`""",
)
replace_exact(
    master,
    "- `n=400` is conditional on unclear `50 / 100 / 200` trends",
    "- `n=400` was reviewed and is not required for the current observation increment",
)
replace_exact(
    master,
    "| Stage 6 | IN_PROGRESS | V-012 mesh/CFL execution、CI-light、formal report、SHA256 manifest |",
    "| Stage 6 | IN_PROGRESS | V-012 CI-light、permanent GitHub Actions、formal report、SHA256 manifest |",
)
append_once(
    master,
    "PR #40: V-012 mesh/CFL observation implementation",
    "- PR #40: V-012 mesh/CFL observation implementation、13-run execution、aggregate analysis、9-figure review、264-test evidenceを記録。V-012は`IN_PROGRESS`を維持し、次はCI-light band specification。",
)

log_block = """## 2026-07-18 — V-012 mesh/CFL observation

PR #40 executed the fixed 13-run V-012A/B/C/D mesh/CFL matrix.

```text
planned / executed runs:     13 / 13
overall sweep pass:          True
aggregate analysis:          complete
comparison plots:            9
focused tests:               12 passed, 0 skipped
full repository:             264 passed in 121.80 s
CoolProp:                    8.0.0
source head:                 9a63dd2bafc264c2a9e41ba68769b5b38cfafe78
artifact sha256:             c1cdf41cde8697cdecbd368ee380d925922921fbc77c1c8b77cb8820feb0d372
```

Observed decisions:

- V-012B/C/D near-probe p50 timing offsets improved with mesh refinement;
- finite-opening flow and interface-Q consistency remained stable;
- V-012D complete-closure through quantities remained at numerical zero;
- all runs remained single phase with positive states and required budgets;
- halving CFL approximately doubled step count and runtime but was not uniformly closer to the mesh trend;
- `n=400` is not required for this observation increment after human review;
- no solver-physics, Kv-law, boundary-meaning, or energy-treatment change occurred;
- no CI-light band was defined in this observation increment.

V-012 remains `IN_PROGRESS`; CI-light, permanent GitHub Actions, formal report, and SHA256 manifest remain.
"""
append_once(
    Path("docs/verification/stage6_execution_log.md"),
    "## 2026-07-18 — V-012 mesh/CFL observation",
    log_block,
)
append_once(
    Path("docs/verification/stage6_v012_execution_log.md"),
    "## 2026-07-18 — V-012 mesh/CFL observation",
    log_block,
)
