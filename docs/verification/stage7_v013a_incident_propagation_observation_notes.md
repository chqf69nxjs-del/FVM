# Stage 7 V-013A Incident-Propagation Observation Notes

Detailed pre-finalization evidence is preserved in
[`archive/stage7_v013a_observation_evidence_pre_finalization.md`](archive/stage7_v013a_observation_evidence_pre_finalization.md).

Status: `OBSERVED; READY FOR REVIEW`. V-013 remains `IN_PROGRESS`; V-013B
rigid-wall reflection is next.

## Evidence

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

Final artifacts persist the installed `coolprop_version`; mesh plots sort by
increasing `Δx` and label `mesh spacing Δx [m]`. Production solver physics is
unchanged. Physical Validation/design-use acceptance remain `False`; the
backend is `not_approved_for_design_use`; MOC is verification-only; the finest
mesh is not exact; no V-013 CI-light band exists yet.
