from __future__ import annotations

import json
from pathlib import Path


VALIDATED_HEAD = "2bbe2ad210d45c6403aa0b9a6a097dff56b44685"
WORKFLOW_RUN = 30154880687
ARTIFACT_ID = 8618870653
ARTIFACT_SHA256 = "7d254126a741e7d92e5ed1a2b6da94c703bbc2da91f1769d58c11deaa22b89b9"
RUNNER_BLOB = "87df463996ea68789764e11f4ce9799ec214440e"
TEST_BLOB = "817cb1c8c42658481ab0babcdddc34ab7966c4a2"


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"replacement anchor missing: {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


EVIDENCE = "docs/verification/stage7_lco2_hem_pipeline_depressurization_increment2_evidence.md"
COMMANDS = "docs/verification/stage7_lco2_hem_pipeline_depressurization_increment2_validation_commands.md"
CONTRACT = "docs/verification/stage7_lco2_hem_pipeline_depressurization_increment2_observation_contract_v1.json"

replace_once(
    EVIDENCE,
    '''```text
validated head:                    2d09fd98af32f77969be49f5c1394c05e6314ea5
workflow run:                      30146579752
artifact ID:                       8616354622
artifact SHA256:                   3e5dce108b433ffc3caa288487fb461e461a2fb7bc5b47bd724546ae730acd6a
CoolProp:                          8.0.0
runner source Git blob:            414f6019710091cd51ed8732859f71b695783d18
focused test Git blob:             e9823c6c66d6f664e095f986066aa9213863736b
```

```text
dependency-free Increment 2:       12 passed, 0 skipped
installed-CoolProp Increment 2:     3 passed, 0 skipped
related pre-existing Stage 7 HEM:  74 passed, 0 skipped
full repository:                  690 passed, 0 skipped
failures / errors:                  0 / 0
```

The validated head also passed the permanent CoolProp Wave, Controlled Pressure Ramp,
Boundary Reflection, and Internal Valve regressions.
''',
    f'''```text
validated head:                    {VALIDATED_HEAD}
workflow run:                      {WORKFLOW_RUN}
artifact ID:                       {ARTIFACT_ID}
artifact SHA256:                   {ARTIFACT_SHA256}
CoolProp:                          8.0.0
runner source Git blob:            {RUNNER_BLOB}
focused test Git blob:             {TEST_BLOB}
```

```text
dependency-free Increment 2:       26 passed, 0 skipped
installed-CoolProp Increment 2:     5 passed, 0 skipped
related pre-existing Stage 7 HEM:  74 passed, 0 skipped
full repository:                  706 passed, 0 skipped
failures / errors:                  0 / 0
```

The installed-CoolProp focused set executed the fixed three-case matrix twice and required
exact equality of outcomes, failure reasons, step counts, crossing times and cells, maximum
qualities, final-state SHA256 values, and run signatures. Both executions reproduced the
contract exactly.

The validated head also passed the permanent CoolProp Wave, Controlled Pressure Ramp,
Boundary Reflection, and Internal Valve regressions in runs `30154880697`, `30154880677`,
`30154880664`, and `30154880684`.
''',
)

replace_once(
    COMMANDS,
    '''```text
12 passed, 0 skipped, 0 failed, 0 errors
```''',
    '''```text
26 passed, 0 skipped, 0 failed, 0 errors
```''',
)
replace_once(
    COMMANDS,
    '''```text
3 passed, 0 skipped, 0 failed, 0 errors
```''',
    '''```text
5 passed, 0 skipped, 0 failed, 0 errors
```''',
)
replace_once(
    COMMANDS,
    '''They also verify all 195 boundary-path samples, zero reverse-flow fallback, artifact bundle
completeness, and exact frozen PR #72 Case A/B regression signatures.
''',
    '''They also verify all 195 boundary-path samples, zero reverse-flow fallback, exact
machine-readable observation-contract fields, complete effective configuration output,
artifact bundle completeness, exact frozen PR #72 Case A/B signatures, and a second full
fixed-matrix execution with exact repeatability.
''',
)
replace_once(
    COMMANDS,
    '''```text
690 passed, 0 skipped, 0 failed, 0 errors
```''',
    '''```text
706 passed, 0 skipped, 0 failed, 0 errors
```''',
)
replace_once(
    COMMANDS,
    '''```text
validated head:                  2d09fd98af32f77969be49f5c1394c05e6314ea5
workflow run:                    30146579752
artifact ID:                     8616354622
artifact SHA256:                 3e5dce108b433ffc3caa288487fb461e461a2fb7bc5b47bd724546ae730acd6a
runner source Git blob:          414f6019710091cd51ed8732859f71b695783d18
focused test Git blob:           e9823c6c66d6f664e095f986066aa9213863736b
```

Permanent workflow results on the validated head:

```text
CoolProp Wave Regression:                 success, run 501 / 30146579780
CoolProp Controlled Pressure Ramp:        success, run 445 / 30146579751
CoolProp Boundary Reflection Regression:  success, run 466 / 30146579786
CoolProp Internal Valve Regression:       success, run 321 / 30146579741
```
''',
    f'''```text
validated head:                  {VALIDATED_HEAD}
workflow run:                    {WORKFLOW_RUN}
artifact ID:                     {ARTIFACT_ID}
artifact SHA256:                 {ARTIFACT_SHA256}
runner source Git blob:          {RUNNER_BLOB}
focused test Git blob:           {TEST_BLOB}
```

Permanent workflow results on the validated head:

```text
CoolProp Wave Regression:                 success, run 513 / 30154880697
CoolProp Controlled Pressure Ramp:        success, run 457 / 30154880677
CoolProp Boundary Reflection Regression:  success, run 478 / 30154880664
CoolProp Internal Valve Regression:       success, run 333 / 30154880684
```
''',
)

contract_path = Path(CONTRACT)
contract = json.loads(contract_path.read_text(encoding="utf-8"))
contract["validated_head"] = VALIDATED_HEAD
validation = contract["authoritative_validation"]
validation.update(
    {
        "validated_head": VALIDATED_HEAD,
        "workflow_run": WORKFLOW_RUN,
        "artifact_id": ARTIFACT_ID,
        "artifact_sha256": ARTIFACT_SHA256,
        "coolprop_version": "8.0.0",
        "runner_source_git_blob": RUNNER_BLOB,
        "focused_test_git_blob": TEST_BLOB,
        "dependency_free_tests": {
            "passed": 26,
            "skipped": 0,
            "failed": 0,
            "errors": 0,
        },
        "installed_coolprop_tests": {
            "passed": 5,
            "skipped": 0,
            "failed": 0,
            "errors": 0,
        },
        "related_pre_existing_stage7_tests": {
            "passed": 74,
            "skipped": 0,
            "failed": 0,
            "errors": 0,
        },
        "full_repository_tests": {
            "passed": 706,
            "skipped": 0,
            "failed": 0,
            "errors": 0,
        },
        "permanent_workflows": {
            "coolprop_wave": 30154880697,
            "controlled_pressure_ramp": 30154880677,
            "boundary_reflection": 30154880664,
            "internal_valve": 30154880684,
        },
    }
)
contract["repeatability"] = {
    "matrix_execution_count_in_focused_validation": 2,
    "exact_match": True,
    "compared_fields": [
        "summary",
        "outcome",
        "failure_reason",
        "step_count",
        "final_time_s",
        "crossing_step",
        "crossing_time_s",
        "crossing_cell_indices",
        "crossing_distances_from_outlet_m",
        "maximum_crossing_quality",
        "final_state_sha256",
        "run_signature_sha256",
    ],
}
contract_path.write_text(
    json.dumps(contract, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
