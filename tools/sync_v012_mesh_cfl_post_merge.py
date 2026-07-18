"""Temporary post-merge synchronization for V-012 mesh/CFL documentation."""
from pathlib import Path


MERGE_COMMIT = "ddc83bc390cbb712900017e9ff82112fae81200f"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(
            f"replacement source not found in {path}: {old[:100]!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + "\n" + block.rstrip() + "\n", encoding="utf-8")


master = Path("docs/verification/MASTER_VERIFICATION_INDEX.md")
replace_exact(
    master,
    "- V-012 mesh/CFL observationはPR #40で13-run計画を完走し、`OBSERVED; READY FOR REVIEW`。",
    "- V-012 mesh/CFL observationはPR #40でマージ済み。merge commitは`ddc83bc390cbb712900017e9ff82112fae81200f`。",
)
replace_exact(
    master,
    "- PR: `#40`\n- observed source head:",
    "- PR: `#40`\n- merge commit: `ddc83bc390cbb712900017e9ff82112fae81200f`\n- observed source head:",
)
replace_exact(
    master,
    """1. PR #40のmesh/CFL observation implementationと人間レビューを確定する。
2. 観測済み13-run結果からCI-light候補caseとregression band案を仕様化する。
3. bandはtest通過目的で緩めず、mesh/CFL差とnumerical floorから根拠を記録する。
4. permanent GitHub Actions CI-lightを追加し、skipなしで確認する。
5. V-012 formal reportとSHA256 manifestを整備する。
6. V-012全体のcompletion gateをレビューする。""",
    """1. 観測済み13-run結果からCI-light候補caseとregression band案を仕様化する。
2. bandはtest通過目的で緩めず、mesh/CFL差とnumerical floorから根拠を記録する。
3. permanent GitHub Actions CI-lightを追加し、skipなしで確認する。
4. V-012 formal reportとSHA256 manifestを整備する。
5. V-012全体のcompletion gateをレビューする。""",
)
replace_exact(
    master,
    "- PR #40: V-012 mesh/CFL observation implementation、13-run execution、aggregate analysis、9-figure review、264-test evidenceを記録。V-012は`IN_PROGRESS`を維持し、次はCI-light band specification。",
    "- PR #40: V-012 mesh/CFL observation implementationをマージ。merge commit `ddc83bc390cbb712900017e9ff82112fae81200f`。13-run execution、aggregate analysis、9-figure review、264-test evidenceを記録。V-012は`IN_PROGRESS`を維持し、次はCI-light band specification。",
)

notes = Path("docs/verification/stage6_v012_mesh_cfl_observation_notes.md")
replace_exact(notes, "`OBSERVED; READY FOR REVIEW`", "`OBSERVED; MERGED`")
replace_exact(
    notes,
    "#40 Start V-012 mesh/CFL sweep implementation",
    "#40 Add V-012 internal-valve mesh/CFL observation",
)
replace_exact(
    notes,
    "No solver-physics, conservation, sign, timing, phase-state, reproducibility, or\ndata-integrity blocker was found. The V-012 mesh/CFL observation is ready for PR\nreview.",
    "No solver-physics, conservation, sign, timing, phase-state, reproducibility, or\ndata-integrity blocker was found. PR #40 was merged at\n`ddc83bc390cbb712900017e9ff82112fae81200f`.",
)

checkpoint = f"""## 2026-07-18 — PR #40 merged

V-012 mesh/CFL observation was merged at:

```text
{MERGE_COMMIT}
```

The next V-012 increment is CI-light band specification followed by permanent
GitHub Actions coverage, formal report, SHA256 manifest, and completion review.
V-012 remains `IN_PROGRESS`.
"""
for path in (
    Path("docs/verification/stage6_execution_log.md"),
    Path("docs/verification/stage6_v012_execution_log.md"),
):
    append_once(path, "## 2026-07-18 — PR #40 merged", checkpoint)
