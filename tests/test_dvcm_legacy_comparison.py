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
    assert (tmp_path / "case_c_dvcm_legacy_comparison_report_v0_6_2.md").exists()
    assert (tmp_path / "case_c_dvcm_comparison_summary_v0_6_2.csv").exists()
    assert metrics["dvcm_summary"]["alpha_max_overall"] >= 0.0
