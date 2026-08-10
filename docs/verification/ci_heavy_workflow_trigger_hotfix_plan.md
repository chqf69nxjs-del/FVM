# Stage 7 heavy CI trigger hotfix plan

## Status

`PLANNED / TRIGGER-ONLY CHANGE / NO NUMERICAL OR FORMAL-STATE CHANGE`

## Problem statement

Historical Stage 7 authority workflows still contain broad `pull_request:` triggers. A pull request unrelated to the historical HEM crossing studies can therefore start several long-running matrices, including CFL and mesh sensitivity, Gate 8 post-crossing execution, repeated related regressions, and repeated full-repository pytest runs.

The incident around abandoned PR #148 demonstrated that one branch/PR update can consume hours of runner time without providing new evidence for the active U3 B2 finite-pipe increment.

## Phase 1 — immediate isolation

The first hotfix will change trigger scope only. The numerical commands, fixed cases, tolerances, tests, Artifact structure, and approval boundaries remain unchanged.

The following completed historical authority workflows will no longer run for every pull request. Their branch-specific historical `push` trigger and explicit `workflow_dispatch` trigger will be retained.

```text
.github/workflows/stage7-pipeline-cfl-sensitivity-execution.yml
.github/workflows/stage7-pipeline-mesh-sensitivity-validation.yml
.github/workflows/stage7-gate8-full-cfl-sequence.yml
.github/workflows/stage7-post-crossing-cfl-sensitivity-increment1.yml
```

Current expensive behavior:

```text
unrelated pull request
→ fixed CFL 0.10 / 0.05 / 0.025 columns
→ fixed mesh 32 / 64 / 128 matrix
→ Gate 8 historical replay
→ repeated related regressions
→ repeated full-repository pytest
```

Target behavior:

```text
historical source branch push
OR explicit workflow_dispatch
→ historical authority workflow

ordinary unrelated pull request
→ no historical heavy replay
```

## Phase 2 — broader CI architecture

After the immediate isolation is merged and observed, a separate increment will address:

```text
specialized workflows:
  relevant paths only

full repository pytest:
  one authoritative run per source commit where practical

normal pull requests:
  compile + dedicated + related tests

heavy mesh / CFL / authority matrices:
  explicit gate or relevant-source change only
```

## Safety boundary

This hotfix must not change:

```text
production solver or numerical flux
HEM / EOS / phase classification
case conditions or fixed matrix
CFL or mesh values
thresholds or tolerances
Reference or Adapter implementation
existing retained Artifacts
formal Stage 7 or U3 approval flags
```

## Validation

Before merge:

```text
changed paths limited to the intended workflow files and this plan
YAML parses successfully
only the `on:` trigger block changes in each historical workflow
git diff --check passes
main source / tests / documentation results remain unchanged
```

The hotfix is an execution-resource and scheduling correction, not a replacement of any historical numerical authority.