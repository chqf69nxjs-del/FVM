from pathlib import Path

MAIN_SHA = "1bb1765617de72741086b199efa0d72be16ae651"
PR91_SHA = "1bb1765617de72741086b199efa0d72be16ae651"


def replace_if_present(text: str, old: str, new: str) -> str:
    return text.replace(old, new, 1) if old in text else text


master_path = Path("docs/verification/MASTER_VERIFICATION_INDEX.md")
master = master_path.read_text(encoding="utf-8")
master = replace_if_present(
    master,
    "## Current state — 2026-07-26",
    "## Current state — 2026-07-27",
)
master = replace_if_present(
    master,
    "- recorded substantive development `main`: `827d99bce97cea2785aa3334b3f5e950389c9aad`",
    f"- recorded substantive development `main`: `{MAIN_SHA}`",
)

pr84_bullet = (
    "- fixed 128-cell CFL-sensitivity contract and exact CFL 0.10 replay: "
    "`IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` in PR #84"
)
pr91_bullet = (
    "- Gate 3 cross-runtime capture and local-PC checkpoint: "
    "`NUMERICALLY_EQUIVALENT; MERGED` in PR #91"
)
if pr91_bullet not in master:
    master = master.replace(
        pr84_bullet,
        pr84_bullet
        + "\n"
        + pr91_bullet
        + "\n- Ubuntu remains authoritative for bitwise-exact scalars and SHA256 values; "
        "Windows hashes do not replace the Ubuntu baselines",
        1,
    )

master = replace_if_present(
    master,
    "- active operational gate: local-PC reproduction checkpoint in Issue #85",
    "- Gate 3 local-PC reproduction checkpoint: `COMPLETE; NUMERICALLY_EQUIVALENT` "
    "in PR #91; Issue #85 closed",
)
master = replace_if_present(
    master,
    "- next numerical execution gate: fixed low-CFL matrix in Issue #86 after the local checkpoint",
    "- next numerical execution gate: fixed low-CFL matrix in Issue #86 after this "
    "central-record synchronization",
)

pr84_row = (
    "| PR #84 | fixed CFL contract and exact 128-cell/CFL 0.10 replay | "
    "`IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` | merge "
    "`827d99bce97cea2785aa3334b3f5e950389c9aad` |"
)
pr91_row = (
    "| PR #91 | Gate 3 cross-runtime numeric-equivalence closure | "
    "`NUMERICALLY_EQUIVALENT; MERGED` | merge `1bb1765617de72741086b199efa0d72be16ae651` |"
)
if pr91_row not in master:
    master = master.replace(pr84_row, pr84_row + "\n" + pr91_row, 1)

master = replace_if_present(
    master,
    "The low-CFL 0.05/0.025 matrix has not been executed or accepted. Its final acceptance is\n"
    "blocked on the independent local-PC reproduction checkpoint in Issue #85; execution is\n"
    "tracked in Issue #86.",
    "The independent local-PC reproduction checkpoint completed as `NUMERICALLY_EQUIVALENT`\n"
    "in PR #91, with Issue #85 closed. The low-CFL 0.05/0.025 matrix remains unexecuted and\n"
    "unaccepted; its controlled execution and review remain tracked in Issue #86.",
)

section_heading = "### PR #91 — Gate 3 cross-runtime numeric-equivalence closure"
if section_heading not in master:
    section = """
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
    anchor = "## First-order V-013 baseline"
    if anchor not in master:
        raise RuntimeError("MASTER insertion anchor is missing")
    master = master.replace(anchor, section + anchor, 1)

master = replace_if_present(
    master,
    "The current active operational gate is Issue #85, followed by the fixed low-CFL execution\n"
    "in Issue #86. Gate P2, mesh-independent accuracy, CFL-independent crossing, near-saturation\n"
    "acoustic continuity, post-crossing propagation, physical Validation, design use, and\n"
    "production HEM activation remain unapproved.",
    "Issue #85 is complete with the Gate 3 disposition `NUMERICALLY_EQUIVALENT`. The next\n"
    "controlled numerical gate is the fixed low-CFL execution in Issue #86. Gate P2,\n"
    "mesh-independent accuracy, CFL-independent crossing, near-saturation acoustic continuity,\n"
    "post-crossing propagation, physical Validation, design use, and production HEM activation\n"
    "remain unapproved.",
)

for required in (
    "## Current state — 2026-07-27",
    pr91_bullet,
    pr91_row,
    section_heading,
    "Issue #85 closed",
):
    if required not in master:
        raise RuntimeError(f"MASTER final marker missing: {required}")
master_path.write_text(master, encoding="utf-8")

log_path = Path("docs/verification/stage7_execution_log.md")
log = log_path.read_text(encoding="utf-8")
log = replace_if_present(
    log,
    "local_pc_reproduction_checkpoint_completed = false",
    "local_pc_reproduction_checkpoint_completed = true\n"
    "local_pc_reproduction_disposition = NUMERICALLY_EQUIVALENT",
)
if "local_pc_reproduction_disposition = NUMERICALLY_EQUIVALENT" not in log:
    marker = "local_pc_reproduction_checkpoint_completed = true"
    if marker not in log:
        raise RuntimeError("execution-log checkpoint marker is missing")
    log = log.replace(
        marker,
        marker + "\nlocal_pc_reproduction_disposition = NUMERICALLY_EQUIVALENT",
        1,
    )

closure_heading = "## 2026-07-26 to 2026-07-27 — Gate 3 cross-runtime closure"
new_tail = """
## Next

1. execute the fixed 128-cell 2/3/4 MPa × CFL 0.10/0.05/0.025 matrix in Issue #86, first
   requiring the CFL 0.10 rows to reproduce the retained PR #82 baseline exactly;
2. keep all CFL 0.05/0.025 results unaccepted until their dedicated review and promotion;
3. retain PRs #52/#53 as later numerical-improvement assets until the first-order temporal
   and near-saturation acoustic questions are separated;
4. perform the independent near-saturation acoustic-continuity gate before approving any
   post-crossing propagation;
5. keep production activation, physical Validation, design use, and acoustic/numerical
   accuracy approval false until separately established.

## 2026-07-26 to 2026-07-27 — Gate 3 cross-runtime closure

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
low_cfl_result_accepted = false
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```
"""

if closure_heading in log:
    prefix = log.split("\n## Next\n", 1)[0].rstrip()
    log = prefix + "\n\n" + new_tail.strip() + "\n"
else:
    next_index = log.rfind("\n## Next\n")
    if next_index < 0:
        raise RuntimeError("execution-log final Next section is missing")
    log = log[:next_index].rstrip() + "\n\n" + new_tail.strip() + "\n"

for required in (
    "local_pc_reproduction_checkpoint_completed = true",
    "local_pc_reproduction_disposition = NUMERICALLY_EQUIVALENT",
    closure_heading,
    "Gate_3_disposition = NUMERICALLY_EQUIVALENT",
):
    if required not in log:
        raise RuntimeError(f"execution-log final marker missing: {required}")
log_path.write_text(log, encoding="utf-8")
