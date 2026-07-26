from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "verification"

PR77_MERGE = "5657d26b3f37443ef63971245dce66ddd72c681e"
PR79_MERGE = "e40562e03657dec526f84b3911cbf181973462fa"
PR82_MERGE = "08d34069b45083537e1d5c4035993d3fc5c01de5"
PR84_MERGE = "827d99bce97cea2785aa3334b3f5e950389c9aad"


def replace_once(text: str, pattern: str, replacement: str, *, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"expected one {label} replacement, observed {count}")
    return updated


def update_master() -> None:
    path = DOCS / "MASTER_VERIFICATION_INDEX.md"
    text = path.read_text(encoding="utf-8")

    current_state = f"""## Current state — 2026-07-26

- Stage 1–6: `COMPLETE`
- Stage 7: `IN_PROGRESS`
- recorded substantive development `main`: `{PR84_MERGE}`
- V-013 first-order propagation/reflection baseline: `FORMALIZED; MERGED` in PR #51
- pure-CO2 HEM thermodynamic and phase foundation: `MERGED` in PRs #54–#57
- dynamic equilibrium-quality synchronization: `IMPLEMENTED; MERGED` in PRs #59–#60
- first repeatable liquid-to-open-two-phase crossing Case A and matched liquid Case B:
  `FROZEN; MERGED` in PR #72
- prescribed-subcooled outlet boundary Increment 1: `IMPLEMENTED; SOFTWARE-VERIFIED;
  MERGED` in PR #75
- fixed boundary-driven 5→2/3/4 MPa pipeline matrix: `OBSERVED; MERGED` in PR #77
- fixed 4 MPa subthreshold forensic diagnosis: `OBSERVED; MERGED` in PR #79
- fixed 32/64/128-cell mesh-sensitivity matrix at CFL 0.10: `OBSERVED; MERGED` in PR #82
- fixed 128-cell CFL-sensitivity contract and exact CFL 0.10 replay: `IMPLEMENTED;
  SOFTWARE-VERIFIED; MERGED` in PR #84
- 4 MPa raw crossing: present at 32, 64, and 128 cells; accepted-crossing threshold
  remains unchanged at `1e-6`
- Gate P2: `FALSE`
- mesh-independent crossing accuracy: `NOT ESTABLISHED`
- CFL-independent crossing: `NOT VERIFIED`
- active operational gate: local-PC reproduction checkpoint in Issue #85
- next numerical execution gate: fixed low-CFL matrix in Issue #86 after the local checkpoint
- MUSCL/TVD reconstruction scaffold: `OPEN; READY FOR REVIEW` in PR #52
- scalar-advection comparison: `VALIDATED STACKED DRAFT` in PR #53
- physical Validation: `NOT ESTABLISHED`
- design-use acceptance: `NOT ESTABLISHED`
- production HEM activation: `NOT APPROVED`
- two-phase acoustic accuracy band: `NOT APPROVED`

"""
    text = replace_once(
        text,
        r"## Current state — .*?\n\n(?=The main development objective remains)",
        current_state,
        label="current-state block",
    )

    updated_overview = """The merged HEM verification path now supports guarded real-fluid state evaluation,
explicit phase classification, an equilibrium sound-speed candidate, quality projection,
mixed liquid/open-two-phase accepted-state evaluation, direct raw transition detection,
an actual first-order Rusanov/CFL liquid-to-open-two-phase crossing, synchronized
post-crossing recovery, vapor-budget closure, a repeatable matched Case A/B software
verification pair, a fixed minimal pipeline-depressurization specification, a verified
prescribed-subcooled outlet boundary, a boundary-driven first-crossing pipeline runner,
a fixed 4 MPa forensic diagnosis, and a 32/64/128-cell software mesh-sensitivity matrix.
The next CFL comparison is contract-locked and its 128-cell/CFL 0.10 baseline has been
reproduced exactly. Physical Validation, a two-phase acoustic accuracy band, post-crossing
propagation approval, design use, and production HEM activation remain unestablished.

"""
    text = replace_once(
        text,
        r"The merged HEM verification path now supports.*?\n\n(?=## Stage 7 milestone index)",
        updated_overview,
        label="overview block",
    )

    pr75_row = (
        "| PR #75 | prescribed-subcooled outlet boundary Increment 1 | "
        "`IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` | merge "
        "`9982c52bc4c26fac991972f0a8156c857e4bf21f` |"
    )
    milestone_rows = f"""{pr75_row}
| PR #77 | fixed boundary-driven 2/3/4 MPa pipeline matrix | `OBSERVED; MERGED` | merge `{PR77_MERGE}` |
| PR #79 | fixed 4 MPa subthreshold forensic diagnosis | `OBSERVED; MERGED` | merge `{PR79_MERGE}` |
| PR #82 | fixed 32/64/128-cell mesh sensitivity at CFL 0.10 | `OBSERVED; MERGED` | merge `{PR82_MERGE}` |
| PR #84 | fixed CFL contract and exact 128-cell/CFL 0.10 replay | `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED` | merge `{PR84_MERGE}` |"""
    if "| PR #77 | fixed boundary-driven" not in text:
        if pr75_row not in text:
            raise RuntimeError("PR #75 milestone row not found")
        text = text.replace(pr75_row, milestone_rows, 1)

    continuation = f"""## Boundary-driven pipeline continuation — PRs #77, #79, #82, and #84

### PR #77 — fixed first-crossing pipeline matrix

The fixed 1.0 m / 0.10 m / 32-cell first-order Rusanov prototype executed the unchanged
5→2, 5→3, and 5→4 MPa schedules at CFL 0.10.

| case | formal result | step | crossing time [s] | cell | outlet distance [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa row is a reproducible subthreshold raw crossing, not an accepted crossing and
not an all-liquid control. Gate P2 remains false; no algorithm, schedule, or threshold was
tuned after observing the result.

### PR #79 — fixed 4 MPa forensic diagnosis

The exact PR #77 baseline was reproduced before diagnosis. Retained categories:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

The crossing point lies on the equilibrium two-phase side in both internal-energy and
specific-volume coordinates. The perturbation result is `WEAKLY_RESOLVED`: the phase
classification is stable through relative `rho/e` perturbations of `1e-8` but changes for
some `1e-6` perturbations. The narrow last-step tests did not support direct assignment to
Rusanov dissipation or one-sided boundary closure. Near-saturation acoustic continuity
remains unapproved.

### PR #82 — fixed mesh sensitivity at CFL 0.10

The 4 MPa raw crossing persisted on all three reviewed meshes:

| cells | formal result | maximum q_eq | normalized crossing time | outlet distance [m] |
|---:|---|---:|---:|---:|
| 32 | `GUARD_FAILURE` | `9.672588429198319e-9` | `0.9318710632753395` | `0.203125` |
| 64 | `GUARD_FAILURE` | `5.977506779042054e-7` | `0.8590001798084317` | `0.1484375` |
| 128 | `GUARD_FAILURE` | `3.8580990283897163e-7` | `0.8060444782479008` | `0.11328125` |

Retained labels:

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

The observations do not establish a formal convergence order, a mesh-independent quality
value, physical nucleation, or design accuracy.

### PR #84 — CFL contract and exact baseline replay

The next comparison is fixed at 128 cells with final pressures 2/3/4 MPa and CFL values
0.10/0.05/0.025. Only CFL and the predeclared 8000/16000/32000 step caps may vary. The
three CFL 0.10 rows reproduced PR #82 exactly before lower-CFL execution is allowed.

```text
validated head:               8564b97493686e06902e5fed0aeb2e117cbd662c
contract workflow:            30191706675
contract artifact:            8628766608
contract artifact SHA256:     dc62c44b9844fd07ac15b564140ae1ba2cedeb1684ccaa5539d9eab77cdca8a5
baseline workflow:            30191706654
baseline artifact:            8629224828
baseline artifact SHA256:     00260475d3b7630b3e77cdd3778db970e026bcfc8aab91104d283a6936d53318
contract + baseline tests:    45 passed
related Stage 7 regressions:  119 passed
full repository:              796 passed
skips / failures / errors:    0 / 0 / 0
```

The low-CFL 0.05/0.025 matrix has not been executed or accepted. Its final acceptance is
blocked on the independent local-PC reproduction checkpoint in Issue #85; execution is
tracked in Issue #86.

```text
Gate_P2_passed = false
mesh_independent_crossing_verified = false
CFL_independent_crossing_verified = false
near_saturation_acoustic_continuity_approved = false
post_crossing_propagation_approved = false
physical_validation = false
design_use_acceptance = false
production_hem_activation_approved = false
```

"""
    if "## Boundary-driven pipeline continuation — PRs #77, #79, #82, and #84" not in text:
        marker = "## First-order V-013 baseline"
        if marker not in text:
            raise RuntimeError("V-013 section marker not found")
        text = text.replace(marker, continuation + marker, 1)

    path.write_text(text, encoding="utf-8")


def update_snapshot() -> None:
    path = DOCS / "stage7_current_gate_snapshot.md"
    content = f"""# Stage 7 Current Gate Snapshot

## Status — 2026-07-26

```text
Stage 1–6:                         COMPLETE
Stage 7:                           IN_PROGRESS
recorded substantive main:         {PR84_MERGE}
pipeline Increment 2:              MERGED in PR #77
fixed 4 MPa forensic diagnostic:   MERGED in PR #79
mesh sensitivity at CFL 0.10:      MERGED in PR #82
CFL contract / 0.10 replay:        MERGED in PR #84
Gate P2:                           FALSE
active operational gate:           local-PC reproduction checkpoint — Issue #85
next numerical execution gate:     fixed low-CFL matrix — Issue #86
physical Validation:               NOT ESTABLISHED
design-use acceptance:             NOT ESTABLISHED
production HEM activation:         NOT APPROVED
two-phase acoustic accuracy band:  NOT APPROVED
post-crossing propagation:         NOT APPROVED
```

This snapshot supersedes the earlier pre-mesh continuation state. Detailed historic
entries remain in [`MASTER_VERIFICATION_INDEX.md`](MASTER_VERIFICATION_INDEX.md) and
[`stage7_execution_log.md`](stage7_execution_log.md).

## PR #77 — merged fixed pipeline matrix

| case | formal result | step | crossing time [s] | cell | outlet distance [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa observation is a reproducible subthreshold raw crossing. It is neither an
accepted crossing nor an all-liquid control. The fixed `1e-6` evidence threshold and the
physical/numerical contract were not tuned.

## PR #79 — merged fixed-case diagnosis

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
perturbation classification = WEAKLY_RESOLVED
```

The raw point is independently on the equilibrium two-phase side in internal-energy and
specific-volume coordinates. Last-step evidence did not support direct attribution to
Rusanov dissipation or one-sided boundary closure. The equilibrium sound-speed candidate
changed from about `461.26 m/s` before crossing to about `43.22 m/s` after the micro-quality
crossing; acoustic continuity and physical accuracy remain unapproved.

## PR #82 — merged mesh sensitivity

The 4 MPa raw crossing persisted at CFL 0.10:

| cells | maximum q_eq | normalized crossing time | outlet distance [m] |
|---:|---:|---:|---:|
| 32 | `9.672588429198319e-9` | `0.9318710632753395` | `0.203125` |
| 64 | `5.977506779042054e-7` | `0.8590001798084317` | `0.1484375` |
| 128 | `3.8580990283897163e-7` | `0.8060444782479008` | `0.11328125` |

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

The crossing exists on all three reviewed meshes, but crossing depth is non-monotone.
Formal convergence order and mesh-independent physical accuracy are not established.

## PR #84 — merged CFL contract and exact replay

```text
fixed cells:                    128
fixed final pressures:          2 / 3 / 4 MPa
reviewed CFL values:            0.10 / 0.05 / 0.025
reviewed step caps:             8000 / 16000 / 32000
CFL 0.10 baseline rows:         exact PR #82 replay
CFL 0.05 / 0.025:               not executed / not accepted
```

Authoritative evidence:

```text
validated head:                 8564b97493686e06902e5fed0aeb2e117cbd662c
contract workflow / artifact:   30191706675 / 8628766608
contract artifact SHA256:       dc62c44b9844fd07ac15b564140ae1ba2cedeb1684ccaa5539d9eab77cdca8a5
baseline workflow / artifact:   30191706654 / 8629224828
baseline artifact SHA256:       00260475d3b7630b3e77cdd3778db970e026bcfc8aab91104d283a6936d53318
contract + baseline tests:      45 passed
related Stage 7 regressions:    119 passed
full repository:                796 passed
skips / failures / errors:      0 / 0 / 0
pre-execution checkout state:   clean
```

## Active next gate

Issue #85 is the manual local-PC checkpoint. It must record the local OS/WSL, Python,
NumPy, CoolProp, Git SHA, working-tree state, focused regressions, exact CFL 0.10 replay,
and full-suite result as `EXACT`, `NUMERICALLY_EQUIVALENT`, or
`INVESTIGATION_REQUIRED`.

Issue #86 then executes the fixed nine-run low-CFL matrix. CI preparation may proceed, but
its final sensitivity conclusion must not be accepted into the central record before Issue
#85 is completed or explicitly dispositioned.

```text
mesh-independent crossing verified = false
CFL-independent crossing verified = false
near-saturation acoustic continuity approved = false
post-crossing propagation approved = false
Gate P2 passed = false
physical Validation = false
design-use acceptance = false
production HEM activation = false
```
"""
    path.write_text(content, encoding="utf-8")


def update_execution_log() -> None:
    path = DOCS / "stage7_execution_log.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Current technical conclusion — 2026-07-25"
    if marker not in text:
        raise RuntimeError("old current technical conclusion marker not found")
    prefix = text.split(marker, 1)[0].rstrip() + "\n\n"

    tail = f"""## 2026-07-25 to 2026-07-26 — Boundary-driven pipeline continuation

### PR #77 — fixed first-crossing pipeline matrix

Status: `OBSERVED; MERGED`. Merge commit:
`{PR77_MERGE}`.

The unchanged 1.0 m / 0.10 m / 32-cell first-order Rusanov prototype executed the fixed
5→2, 5→3, and 5→4 MPa schedules at CFL 0.10.

| case | formal result | step | crossing time [s] | cell | outlet distance [m] | maximum q_eq |
|---|---|---:|---:|---:|---:|---:|
| 5→2 MPa | `ACCEPTED_FIRST_CROSSING` | 125 | `7.999325695335248e-4` | 29 | `0.078125` | `3.773646403587342e-6` |
| 5→3 MPa | `ACCEPTED_FIRST_CROSSING` | 174 | `1.1121683091093555e-3` | 28 | `0.109375` | `1.6022773573103607e-6` |
| 5→4 MPa | `GUARD_FAILURE` | 313 | `1.996923102525957e-3` | 25 | `0.203125` | `9.672588429198319e-9` |

The 4 MPa row retained the raw crossing before the fixed `1e-6` evidence check. It is not
an accepted crossing and not an all-liquid control. Gate P2 remained false.

### PR #79 — fixed 4 MPa subthreshold forensic diagnosis

Status: `OBSERVED; MERGED`. Merge commit:
`{PR79_MERGE}`.

The exact PR #77 4 MPa row was reproduced before diagnosis. Retained categories:

```text
THERMODYNAMIC_TWO_PHASE_SUPPORTED
NEAR_SATURATION_PROPERTY_SENSITIVE
MULTI_FACTOR_EVIDENCE
```

The raw state was on the equilibrium two-phase side in both internal-energy and
specific-volume coordinates. Perturbation classification was `WEAKLY_RESOLVED`. The narrow
last-step tests did not retain `NUMERICAL_DIFFUSION_CONSISTENT` or
`BOUNDARY_CLOSURE_INFLUENCE_CONSISTENT`; accumulated first-order diffusion and indirect
boundary influence remained open questions.

The equilibrium sound-speed candidate changed from approximately `461.2567 m/s` in the
accepted liquid state to `43.2231 m/s` in the raw micro-quality two-phase state. No acoustic
accuracy or post-crossing propagation approval was granted.

### PR #82 — fixed 32/64/128-cell mesh sensitivity

Status: `OBSERVED; MERGED`. Merge commit:
`{PR82_MERGE}`.

The fixed 2/3/4 MPa matrix was executed at 32, 64, and 128 cells with CFL 0.10. Only cell
count, derived `dx`, and the predeclared 2000/4000/8000 step caps varied. The 32-cell/4 MPa
row reproduced PR #77 exactly before refined-mesh evidence was retained.

4 MPa observations:

| cells | formal result | maximum q_eq | normalized crossing time | outlet distance [m] |
|---:|---|---:|---:|---:|
| 32 | `GUARD_FAILURE` | `9.672588429198319e-9` | `0.9318710632753395` | `0.203125` |
| 64 | `GUARD_FAILURE` | `5.977506779042054e-7` | `0.8590001798084317` | `0.1484375` |
| 128 | `GUARD_FAILURE` | `3.8580990283897163e-7` | `0.8060444782479008` | `0.11328125` |

```text
FINITE_CROSSING_PERSISTS_ACROSS_MESHES
CROSSING_TIME_POSITION_TREND_STABLE
MESH_SEQUENCE_NON_MONOTONE
```

Authoritative evidence:

```text
validated implementation head: 0abb04ed052b3684ee33f1a8fad1927153701512
workflow run:                  30182329139
artifact ID:                   8626539673
artifact SHA256:               70b5abb9e54f677241ac513a8c0b7dbef4e8f1edaedda91e190f7c96ab9991f2
mesh contract tests:           28 passed
PR #77/#79 regressions:        48 passed
full repository:               751 passed
skips / failures / errors:     0 / 0 / 0
```

The result did not establish formal convergence order or mesh-independent physical
accuracy.

### PR #84 — fixed CFL contract and exact CFL 0.10 replay

Status: `IMPLEMENTED; SOFTWARE-VERIFIED; MERGED`. Merge commit:
`{PR84_MERGE}`.

The reviewed next matrix is fixed to 128 cells, final pressures 2/3/4 MPa, CFL values
0.10/0.05/0.025, and 8000/16000/32000 step caps. Every other PR #77/PR #82 setting is
immutable. Severe or non-threshold guard outcomes return only
`CFL_SENSITIVITY_INCONCLUSIVE`.

The three CFL 0.10 rows reproduced PR #82 exactly. CFL 0.05 and 0.025 were not executed.

```text
validated head:               8564b97493686e06902e5fed0aeb2e117cbd662c
contract workflow:            30191706675
contract artifact:            8628766608
contract artifact SHA256:     dc62c44b9844fd07ac15b564140ae1ba2cedeb1684ccaa5539d9eab77cdca8a5
baseline workflow:            30191706654
baseline artifact:            8629224828
baseline artifact SHA256:     00260475d3b7630b3e77cdd3778db970e026bcfc8aab91104d283a6936d53318
contract + baseline tests:    45 passed
related Stage 7 regressions:  119 passed
full repository:              796 passed
skips / failures / errors:    0 / 0 / 0
pre-execution checkout state: clean
```

## Current technical conclusion — 2026-07-26

The HEM verification path on recorded substantive development `main`
`{PR84_MERGE}` now supports:

- guarded pure-CO2 `rho/e` thermodynamic evaluation;
- explicit phase classification and raw boundary-region transition detection;
- dynamic transported/equilibrium-quality synchronization and mixed-phase EOS recovery;
- actual first-order liquid-to-open-two-phase crossing and frozen Case A/B regressions;
- a prescribed-subcooled outlet with 195/195 accepted boundary preflight samples;
- a fixed boundary-driven 2/3/4 MPa pipeline first-crossing matrix;
- a fixed 4 MPa forensic diagnosis retaining the raw observation without threshold tuning;
- a fixed 32/64/128-cell mesh-sensitivity matrix at CFL 0.10;
- a fixed 128-cell CFL contract with exact CFL 0.10 baseline replay and traceable artifacts.

The current evidence does not support the following claims:

```text
Gate P2:                                      false
all-liquid 4 MPa control:                     false
formal mesh-independent accuracy:             not established
CFL-independent crossing:                     not verified
CFL 0.05 / 0.025 matrix:                      not executed / not accepted
near-saturation acoustic continuity:          not approved
post-crossing propagation:                    not approved
open-two-phase to vapor crossing:             not verified
physical Validation:                          false
design-use acceptance:                        false
production HEM activation:                    false
```

## Approval boundary

```text
verification_only = true
software_verification_only = true
property_backend_name = coolprop_co2
property_backend_design_status = not_approved_for_design_use
actual_first_order_fvm_crossing_verified = true
boundary_driven_pipeline_first_crossing_observed = true
four_mpa_subthreshold_crossing_observed = true
mesh_sensitivity_executed = true
mesh_independent_crossing_verified = false
cfl_contract_implemented = true
cfl_0p10_baseline_reproduced_exactly = true
low_cfl_matrix_executed = false
CFL_independent_crossing_verified = false
local_pc_reproduction_checkpoint_completed = false
algorithms_or_tolerances_tuned = false
production_default_changed = false
production_hem_activation_approved = false
physical_validation = false
design_use_acceptance = false
two_phase_acoustic_accuracy_band_approved = false
post_crossing_propagation_approved = false
numeric_accuracy_band_approved = false
```

## Next

1. complete the local-PC reproduction checkpoint in Issue #85 and classify it as `EXACT`,
   `NUMERICALLY_EQUIVALENT`, or `INVESTIGATION_REQUIRED`;
2. only after the checkpoint is completed or explicitly dispositioned, execute and accept
   the fixed 128-cell 2/3/4 MPa × CFL 0.10/0.05/0.025 matrix in Issue #86;
3. retain PRs #52/#53 as later numerical-improvement assets until the first-order temporal
   and near-saturation acoustic questions are separated;
4. perform the independent near-saturation acoustic-continuity gate before approving any
   post-crossing propagation;
5. keep production activation, physical Validation, design use, and acoustic/numerical
   accuracy approval false until separately established.
"""

    path.write_text(prefix + tail, encoding="utf-8")


def main() -> None:
    update_master()
    update_snapshot()
    update_execution_log()


if __name__ == "__main__":
    main()
