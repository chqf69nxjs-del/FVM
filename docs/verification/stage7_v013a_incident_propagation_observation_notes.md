# Stage 7 V-013A Incident-Propagation Observation Notes

Detailed pre-finalization evidence is preserved in
[`archive/stage7_v013a_observation_evidence_pre_finalization.md`](archive/stage7_v013a_observation_evidence_pre_finalization.md).

Status: `OBSERVED; MERGED` in PR #48. Merge commit:
`613b21622b22402fbf7b8d77b1d881db7ff5f28e`. V-013 baseline formalization is in
progress.

## Primary observation evidence

- GitHub Actions run `29647234616`
- focused `39 passed, 0 skipped`; full `315 passed, 0 skipped`
- runs `3/3`; saved-artifact plots `7/7`; CoolProp `8.0.0`
- artifact SHA256 `ee537e0e32a14d01501e36b427af68f94881905bc01f4a3b68684508c15c0961`

| n | Δx [m] | final FVM pressure peak ratio |
|---:|---:|---:|
| 100 | 1.00 | 0.33987050 |
| 200 | 0.50 | 0.44696360 |
| 400 | 0.25 | 0.57499430 |

The wave direction and approximate speed are consistent. The dominant error is
strong numerical broadening and peak loss, decreasing monotonically with mesh
refinement but still substantial at `n=400`. This is an observation, not an
accuracy-acceptance band.

## Review-close traceability

Every saved result figure now embeds:

- case name: `v013a_incident_propagation`;
- model: production FVM plus independent linear-acoustic MOC/analytical reference;
- property backend: `coolprop_co2`;
- installed CoolProp version;
- output version: `v013a_incident_propagation_v1`;
- the software/numerical-verification and non-design-use disclaimer.

The same metadata is persisted in `v013a_plot_metrics.json`, and missing required
metadata raises an explicit error instead of producing an untraceable figure.
The primary `n=100/200/400` saved artifacts were replotted without rerunning any
solver or changing numerical results. All `7/7` figures were generated without
plotting errors and were visually reviewed for footer readability and the
increasing `mesh spacing Δx [m]` axis.

Review-close validation used GitHub Actions run `29673595870` at code/test head
`14afc9add7c7bb8c7b141d62625c27c3700ea1f8`:

- focused `40 passed, 0 skipped`;
- full repository `316 passed, 0 skipped`;
- `git diff --check` success;
- CoolProp `8.0.0`;
- artifact digest
  `sha256:d531f959327f0c36b86223bc96fa2e85a5fb2727790f8739cb941643ccffa148`.

The temporary validation helper was removed after evidence capture. Production
solver physics is unchanged. Physical Validation/design-use acceptance remain
`False`; the backend is `not_approved_for_design_use`; MOC is verification-only;
the finest mesh is not exact; no V-013 CI-light band exists yet.
