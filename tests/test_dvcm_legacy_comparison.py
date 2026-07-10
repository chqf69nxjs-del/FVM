from pathlib import Path

from liquid_gas_transient.dvcm_comparison import (
    DVCMComparisonConfig,
    generate_dvcm_legacy_comparison_package,
)


def test_dvcm_legacy_comparison_smoke(tmp_path: Path):
    metrics = generate_dvcm_legacy_comparison_package(
        tmp_path,
        config=DVCMComparisonConfig(sample_every=20, include_figures=False),
    )
    assert metrics["version"] == "0.6.2"
    rows = metrics["summary_rows"]
    variants = {row["variant"] for row in rows}
    assert {"hem", "hne_tau005", "dvcm_legacy"}.issubset(variants)
    assert metrics["n_field_rows"] > 0
    assert metrics["base_backend_metadata"] == {
        "eos_model": "lco2_surrogate",
        "property_backend_name": "surrogate_lco2",
        "property_backend_design_status": "not_approved_for_design_use",
    }
    assert all("eos_model" in row for row in rows)
    assert all("property_backend_name" in row for row in rows)
    dvcm_row = next(row for row in rows if row["variant"] == "dvcm_legacy")
    assert dvcm_row["property_backend_design_status"] == "not_applicable_legacy_proxy_not_design_model"
    report_path = tmp_path / "case_c_dvcm_legacy_comparison_report_v0_6_2.md"
    assert report_path.exists()
    assert "`property_backend_name`: `surrogate_lco2`" in report_path.read_text(encoding="utf-8")
    assert (tmp_path / "case_c_dvcm_comparison_summary_v0_6_2.csv").exists()
    assert metrics["dvcm_summary"]["alpha_max_overall"] >= 0.0
