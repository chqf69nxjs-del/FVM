from pathlib import Path

MAIN_SHA = "1bb1765617de72741086b199efa0d72be16ae651"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


master_path = Path("docs/verification/MASTER_VERIFICATION_INDEX.md")
master = master_path.read_text(encoding="utf-8")
master = replace_once(master, "## Current state — 2026-07-26", "## Current state — 2026-07-27", "master date")
master = replace_once(
    master,
    "- recorded substantive development `main`: `827d99bce97cea2785aa3334b3f5e950389c9aad`",
    f"- recorded substantive development `main`: `{MAIN_SHA}`",
    "master main",
)
pr84_bullet = "- fixed 128-cell CFL-sensitivity contract and exact CFL 0.10 replay: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` in PR #84"
master = replace_once(
    master,
    pr84_bullet,
    pr84_bullet
    + "\n- Gate 3 cross-runtime capture and local-PC checkpoint: `NUMERICALLY_EQUIVALENT; MERGED` in PR #91"
    + "\n- Ubuntu remains authoritative for bitwise-exact scalars and SHA256 values; Windows hashes do not replace the Ubuntu baselines",
    "master PR91 bullets",
)
master = replace_once(
    master,
    "- active operational gate: local-PC reproduction checkpoint in Issue #85",
    "- Gate 3 local-PC reproduction checkpoint: `COMPLETE; NUMERICALLY_EQUIVALENT` in PR #91; Issue #85 closed",
    "master active gate",
)
master = replace_once(
    master,
    "- next numerical execution gate: fixed low-CFL matrix in Issue #86 after the local checkpoint",
    "- next numerical execution gate: fixed low-CFL matrix in Issue #86 after this central-record synchronization",
    "master next gate",
)
pr84_row = "| PR #84 | fixed CFL contract and exact 128-cell/CFL 0.10 replay | `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` | merge `827d99bce97cea2785aa3334b3f5e950389c9aad` |"
master = replace_once(
    master,
    pr84_row,
    pr84_row + "\n| PR #91 | Gate 3 cross-runtime numeric-equivalence closure | `NUMERICALLY_EQUIVALENT; MERGED` | merge `1bb1765617de72741086b199efa0d72be16ae651` |",
    "master milestone",
)
master = replace_once(
    master,
    "The low-CFL 0.05/0.025 matrix has not been executed or accepted. Its final acceptance is\nblocked on the independent local-PC reproduction checkpoint in Issue #85; execution is\ntracked in Issue #86.",
    "The independent local-PC reproduction checkpoint completed as `NUMERICALLY_EQUIVALENT`\nin PR #91, with Issue #85 closed. The low-CFL 0.05/0.025 matrix remains unexecuted and\nunaccepted; its controlled execution and review remain tracked in Issue #86.",
    "master PR84 continuation",
)
gate3_section = """
### PR #91 — Gate 3 cross-runtime numeric-equivalence closure

The authoritative Ubuntu 24.04 reference retained exact PR #82 scalar and SHA256 identity.
An independent Windows 11 replay used Python 3.12.10, NumPy 2.5.1, and CoolProp 8.0.0.
The Windows result was not bitwise identical, but all three reviewed 128-cell / CFL 0.10
cases retained exact formal outcomes, step counts, crossing steps, crossing cells, crossing
positions, and failure categories.

```text
Ubuntu reference artifact:       8632513953
Ubuntu artifact SHA256:          78002ddb524c9f1cac00040a14139d6da512f66f19d39a65afc53dbcac188060
Windows raw-history ZIP SHA256:  508e9b727a2e0d00974e4650c3f927e93af89eed9af96cde5c2b0b3e12368738
maximum normalized difference:   5.519112370006797e-12
predeclared comparison guard:    1.0e-10
```

The first cross-platform difference was already present in the CoolProp-backed uniform
initial state before the first FVM update. It did not change a discrete event or reverse a
crossing-threshold decision. All raw-history shapes matched, all values were finite, and
mass, momentum, energy, and vapor inventory differences remained inside the existing
absolute budget limits.

The independent Windows full-repository packet v2 completed:

```text
source main:                       f1b2c76827482164a12e2924bf7119a0b150e421
full repository:                   796 tests
passed / failed / errors / skips:  785 / 4 / 7 / 0
reviewed exact mismatches:         11
unexpected problems:               0
inspector result:                  KNOWN_EXACT_WINDOWS_MISMATCHES_ONLY
packet SHA256:                     67a0113b63db1b4770baf4bbd4104312c5c24839cf50956e57592f487fd7755f
```

The exact Ubuntu baselines remain unchanged. The formal Gate 3 disposition is
`NUMERICALLY_EQUIVALENT`; this is a cross-runtime software-verification conclusion, not a
physical Validation, acoustic-accuracy, design-use, or production-activation approval.

"""
master = replace_once(master, "## First-order V-013 baseline", gate3_section + "## First-order V-013 baseline", "master Gate3 section")
master_path.write_text(master, encoding="utf-8")

snapshot_path = Path("docs/verification/stage7_current_gate_snapshot.md")
snapshot = snapshot_path.read_text(encoding="utf-8")
snapshot = replace_once(snapshot, "## Status — 2026-07-26", "## Status — 2026-07-27", "snapshot date")
snapshot = replace_once(
    snapshot,
    "recorded substantive main:         827d99bce97cea2785aa3334b3f5e950389c9aad",
    f"recorded substantive main:         {MAIN_SHA}",
    "snapshot main",
)
snapshot = replace_once(
    snapshot,
    "CFL contract / 0.10 replay:        MERGED in PR #84\nGate P2:                           FALSE\nactive operational gate:           local-PC reproduction checkpoint — Issue #85\nnext numerical execution gate:     fixed low-CFL matrix — Issue #86",
    "CFL contract / 0.10 replay:        MERGED in PR #84\nGate 3 cross-runtime checkpoint:   NUMERICALLY_EQUIVALENT; MERGED in PR #91\nIssue #85:                         COMPLETE; CLOSED\nGate P2:                           FALSE\nactive numerical execution gate:   fixed low-CFL matrix — Issue #86",
    "snapshot status block",
)
snapshot_gate3 = """
## PR #91 — merged Gate 3 cross-runtime closure

```text
Gate 3 disposition:                  NUMERICALLY_EQUIVALENT
Ubuntu exact baseline retained:      true
Windows hashes replace Ubuntu:       false
all reviewed discrete events exact:  true
maximum normalized array difference: 5.519112370006797e-12
comparison guard:                    1.0e-10
Windows full suite:                  796 tests
passed / failed / errors / skips:    785 / 4 / 7 / 0
unexpected Windows problems:         0
```

The Windows least-significant-bit differences begin in the CoolProp-backed initial state
before the first FVM update. They do not change outcomes, step counts, crossing locations,
or fixed-threshold decisions. Issue #85 is complete. This conclusion is limited to
cross-runtime software reproduction and does not approve physical or design interpretation.

"""
snapshot = replace_once(snapshot, "## Active next gate", snapshot_gate3 + "## Active next gate", "snapshot Gate3 section")
snapshot = replace_once(
    snapshot,
    "Issue #85 is the manual local-PC checkpoint. It must record the local OS/WSL, Python,\nNumPy, CoolProp, Git SHA, working-tree state, focused regressions, exact CFL 0.10 replay,\nand full-suite result as `EXACT`, `NUMERICALLY_EQUIVALENT`, or\n`INVESTIGATION_REQUIRED`.\n\nIssue #86 then executes the fixed nine-run low-CFL matrix. CI preparation may proceed, but\nits final sensitivity conclusion must not be accepted into the central record before Issue\n#85 is completed or explicitly dispositioned.",
    "Issue #85 is complete with the Gate 3 disposition `NUMERICALLY_EQUIVALENT`. Issue #86 is\nthe next numerical execution gate for the fixed nine-run low-CFL matrix. The CFL 0.10 rows\nmust first reproduce the retained PR #82 baseline exactly; CFL 0.05 and 0.025 results remain\nunaccepted until their dedicated execution, review, and central-record promotion.",
    "snapshot next gate text",
)
snapshot_path.write_text(snapshot, encoding="utf-8")

log_path = Path("docs/verification/stage7_execution_log.md")
log = log_path.read_text(encoding="utf-8")
marker = "## 2026-07-26 to 2026-07-27 — Gate 3 cross-runtime closure"
if marker in log:
    raise RuntimeError("execution log Gate 3 entry already exists")
log_entry = f"""

{marker}

### PR #91 — local-PC checkpoint and numeric-equivalence disposition

Status: `NUMERICALLY_EQUIVALENT; MERGED`. Merge commit:
`1bb1765617de72741086b199efa0d72be16ae651`.

The Ubuntu 24.04 reference remained authoritative for bitwise-exact PR #82 scalar and
SHA256 values. The independent Windows 11 runtime used Python 3.12.10, NumPy 2.5.1, and
CoolProp 8.0.0. Its raw histories were not bitwise identical, but all reviewed outcomes,
step counts, crossing steps, crossing cells, crossing positions, and failure categories
were exact.

```text
Ubuntu reference artifact:          8632513953
Ubuntu artifact SHA256:             78002ddb524c9f1cac00040a14139d6da512f66f19d39a65afc53dbcac188060
Windows raw-history ZIP SHA256:     508e9b727a2e0d00974e4650c3f927e93af89eed9af96cde5c2b0b3e12368738
maximum normalized difference:      5.519112370006797e-12
predeclared comparison guard:       1.0e-10
```

The first platform-dependent difference was present in the initial CoolProp-backed state
before time integration. No discrete-event divergence or crossing-threshold reversal was
observed. Inventory differences remained inside the pre-existing absolute budget limits.

The corrected independent Windows full-suite packet v2 recorded:

```text
source main:                         f1b2c76827482164a12e2924bf7119a0b150e421
runtime:                             Windows 11 / Python 3.12.10
NumPy / CoolProp / Matplotlib:       2.5.1 / 8.0.0 / 3.11.1
full repository:                     796 tests
passed / failures / errors / skips:  785 / 4 / 7 / 0
known exact mismatches:              11
unexpected / missing / changed:      0 / 0 / 0
packet SHA256:                       67a0113b63db1b4770baf4bbd4104312c5c24839cf50956e57592f487fd7755f
```

The 11 Windows problems are the reviewed bitwise-exact baseline mismatches only. Ubuntu
hashes were not replaced, exact guards were not weakened, and no solver algorithm or
tolerance changed.

```text
Gate_3_disposition = NUMERICALLY_EQUIVALENT
Gate_3_complete = true
Gate_4_execution_paused_until_central_record_sync = true
low_cfl_result_accepted = false
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
"""
log_path.write_text(log.rstrip() + log_entry + "\n", encoding="utf-8")

for helper in (
    Path(".github/workflows/stage7-gate3-central-record-sync-once.yml"),
    Path(".github/workflows/stage7-gate3-central-record-sync-pr.yml"),
    Path("scripts/stage7_gate3_central_record_sync.py"),
):
    if helper.exists():
        helper.unlink()
