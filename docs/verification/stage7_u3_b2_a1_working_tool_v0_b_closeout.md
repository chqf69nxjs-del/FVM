# Stage 7 / U3 B2 A1 — Working Tool v0-B Closeout

## 1. Purpose

This document closes Working Tool v0-B after the A6 canonical authoritative regression completed successfully.

Working Tool v0-B is an **output / storage operation policy** increment. It does not change the finite-pipe physics, EOS, boundary physics, Hugoniot logic, near-zero-flow logic, or W2 backend physics.

The governing engineering rule remains:

> Working vertical slice first → Physics refinement / Verification second.

A successful A6 regression establishes preservation of the existing canonical W2 / v0-A behavior while adding v0-B output and storage behavior. It does **not** by itself establish physical validation, design-use acceptance, or production approval.

---

## 2. Authoritative implementation source and closeout identity

Authoritative implementation source SHA:

`f939b85a2bafbbae323b1e84e82783d70993ec9d`

This is the exact source SHA exercised by the successful A6 authoritative GitHub Actions run.

A7 closeout branch:

`agent/u3-b2-a1-working-tool-v0-b`

Closeout HEAD:

> The Git commit containing this document is the A7 documentation-only closeout HEAD. Its exact SHA is intentionally obtained from Git commit metadata rather than embedded into this file, because embedding a commit's own SHA in its contents would create a self-reference. The authoritative implementation source remains the fixed SHA above and must not be replaced by the later documentation-only closeout SHA.

---

## 3. A6 authoritative GitHub Actions evidence

Evidence class:

`A6_CANONICAL_AUTHORITATIVE_REGRESSION`

Successful run:

- source SHA: `f939b85a2bafbbae323b1e84e82783d70993ec9d`
- workflow run: `31791269061`
- workflow job: `94738489323`
- conclusion: `success`
- focused tests: `114 passed`
- artifact ID: `9216176956`
- artifact name: `u3-b2-a1-working-tool-v0-b-a6-31791269061`
- artifact digest: `sha256:51e645cc8b6dd859031f80c73892e56dd3b0db8f80bd02dc9315802fb40f12b0`

The artifact was uploaded from the same source SHA and the workflow evidence checksum verification completed successfully before upload.

---

## 4. Canonical execution result

A6 performed exactly one fresh canonical physical solve and then reused that same full result for the FULL and sampled storage projections and the legacy v0-A replay checks.

Canonical execution gates:

- fresh physical solve count = `1`
- accepted steps = `640`
- final time = `0.004285834855172021 s`
- starting state SHA256 = `deaae67e672d92fb1da7c40b1a7a03d904b58f35db12bcec81008b55f9014c21`
- final state SHA256 = `8e73e394f3101840c73c278bbc4521ec4fefeebaee4c7f0db774d87013fd5014`
- target horizon reached = `true`
- exact A2 behavioral regression = `PASS`
- full-horizon execution gate = `PASS`
- manager / restoration gate = `PASS`
- public / evidence separation = `PASS`

Retained canonical manager authority:

- manager transitions = `2`
- selections = `3`
- context restorations = `640 / 640`
- public boundary states: `OUTWARD_FLOW = 637`, `ZERO_TRANSFER_CLOSED = 3`
- outward internal models: `THREE_BRANCH_WAVE_MODEL = 483`, `GENERAL_EOS_FINITE_COMPRESSION = 154`
- outward branches: `CONNECTED_RAREFACTION = 336`, `NEUTRAL_ENDPOINT = 1`, `WEAK_COMPRESSION = 146`, `FINITE_COMPRESSION_HUGONIOT = 154`

The A6 run also verified the immutable A2 authority using its live GitHub run/job/artifact metadata and the fixed artifact/archive SHA256.

---

## 5. FULL v0-B regression

The FULL v0-B package preserved the v0-A five core outputs semantically exactly:

- `summary.json`: exact
- `history.csv`: exact
- `transitions.csv`: exact
- `warnings.csv`: exact
- `state_history.npz`: all required arrays exact
- full core mismatch count = `0`

Working Tool v0-B adds `run_manifest.json`, so the public v0-B output contract is exactly six files:

```text
summary.json
history.csv
transitions.csv
warnings.csv
state_history.npz
run_manifest.json
```

The legacy v0-A CLI replay retained its unchanged public contract of exactly five files.

---

## 6. Sampled storage regression

Sampling is applied **after** the full solver result exists and only changes `state_history.npz` storage projection.

Canonical sampled results:

| accepted-step interval | stored state samples | gate |
|---:|---:|---|
| 10 | 65 | PASS |
| 64 | 11 | PASS |
| 100 | 8 | PASS |
| 1000 | 2 | PASS |

For every sampled projection:

- solver summary mismatch count = `0`
- scalar CSV mismatch count = `0`
- initial state exact = `true`
- final state mismatch count = `0`
- static `x_m` mismatch count = `0`
- public verification-key count = `0`

The output manifest records that sampling is applied after the solver and that runtime state capture remains `FULL`.

---

## 7. Public output / verification evidence separation

The public six-file run package does not carry verification authority metadata such as:

- workflow run/job IDs
- artifact ID/digest
- immutable A2 authority identifiers
- exact regression PASS status
- mismatch counts
- pytest result
- CI success
- verification approval

Those items remain in verification evidence, not in the public run manifest.

---

## 8. Known limitations and scope

Working Tool v0-B is closed with the following explicit limitations:

1. **Canonical scope only for the authoritative A6 claim.** The successful authoritative regression is tied to the canonical A2/W2 case and does not establish arbitrary-input support.
2. **Sampled mode is disk-output reduction only.** The W2 backend still retains the full accepted state history in runtime memory.
3. **Not runtime-memory optimized.** `runtime_memory_optimized = false`.
4. **Not streaming capable.** `streaming_capable = false`.
5. **No physics refinement was performed for v0-B.** Storage/output requirements were not allowed to modify the solver or physical models.
6. **No physical validation claim.** Agreement with the existing canonical authority is a regression-preservation result, not experimental or external physical validation.
7. **No design-use or production approval.** Additional Verification / Validation / Acceptance work is still required before those states can change.

---

## 9. Formal status at closeout

A0–A5: `COMPLETE`

A6 Canonical Authoritative Regression: `COMPLETE`

A7 Closeout: `COMPLETE` when this documentation-only commit becomes branch HEAD.

Engineering state:

`PROVISIONAL ENGINEERING END-TO-END WORKING SLICE`

Formal authority state remains:

- VERIFIED: `false`
- ACCEPTED: `false`
- PHYSICALLY VALIDATED: `false`
- DESIGN-USE ACCEPTED: `false`
- PRODUCTION APPROVED: `false`

The successful A6 result must not be used to auto-promote any of those states.

---

## 10. Closeout statement

Working Tool v0-B has demonstrated, under the canonical authoritative A6 regression, that its output/storage operation features preserve the existing W2 / v0-A canonical physical behavior while adding safe run-directory, manifest, and post-solver storage-projection behavior.

Accordingly:

> **Working Tool v0-B A0–A7 is closed as a provisional engineering end-to-end working slice with authoritative canonical regression evidence, while broader Verification, physical Validation, Design-use Acceptance, and Production Approval remain future work.**
