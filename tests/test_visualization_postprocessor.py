from pathlib import Path

from liquid_gas_transient.visualization import (
    VisualizationConfig,
    generate_case_c_visualization_package,
)


def test_visualization_package_smoke(tmp_path: Path):
    metrics = generate_case_c_visualization_package(
        tmp_path,
        config=VisualizationConfig(sample_every=20, include_figures=False, include_gif=False),
    )
    assert metrics["version"] == "0.6.1"
    assert metrics["n_field_rows"] > 0
    assert (tmp_path / "case_c_visual_report_v0_6_1.md").exists()
    assert (tmp_path / "case_c_visual_xt_fields_v0_6_1.csv").exists()
    rows = metrics["summary_rows"]
    assert len(rows) == 3
    assert {r["variant"] for r in rows} == {"single_phase", "hem", "hne_tau005"}
