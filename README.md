# Phase 2 Ver.0.7.0: Case D/E/A Review Reports

This package adds reviewer-layered reports for three model-discrimination cases:

- Case D: high-point flashing
- Case E: near-saturation ESD closure
- Case A: pump trip / pump stop placeholder

Start with:

`verification/outputs_v0_7_0/case_d_e_a_reviewer_index_v0_7_0.md`

Then open each case-specific `*_reviewer_one_page_v0_7_0.md` and, if needed, `*_engineer_report_v0_7_0.md`.

Important: these are discrimination cases using surrogate/amplified settings. They are not design-use LCO2 results.

## Backend naming roles

- `coolprop_lco2` is a Case C `eos_model` selector. It selects the CoolProp-backed LCO2 adapter path for a Case C run.
- `coolprop_co2` is the canonical property backend name reported by `CoolPropCO2Backend.name`.
- Property verification, reference comparison, and acceptance-gate artifacts should use `backend.name` as the formal backend tracking name.
- `coolprop_lco2` does not indicate that the CoolProp backend or a Case C result is approved for design use; design-use status must come from the reference/acceptance-gate workflow.

