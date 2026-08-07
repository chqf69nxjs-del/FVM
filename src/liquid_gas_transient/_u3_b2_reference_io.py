"""CSV, plot, and manifest writers for U3 B2 Reference evidence."""
from __future__ import annotations
import csv
import hashlib
from pathlib import Path
from typing import Any, Iterable
from ._u3_b2_reference_types import AcousticArrivalReference, FaceReferenceResult, OneStepReference

def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    values = list(rows)
    if not values:
        raise ValueError(f"No rows for {path}")
    fieldnames: list[str] = []
    for row in values:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(values)
def plot_provenance_text(
    case_or_matrix: str,
    backend_version: str,
    source_git_sha: str,
    workflow_run_id: str,
) -> str:
    return (
        f"case={case_or_matrix} | model=U3 B2 independent FVM-face reference | "
        f"backend=CoolProp {backend_version} | source={source_git_sha[:12]} | "
        f"run={workflow_run_id}"
    )
def write_plots(
    output_dir: Path,
    face_results: list[FaceReferenceResult],
    one_step: OneStepReference,
    acoustic_rows: list[AcousticArrivalReference],
    *,
    backend_version: str,
    source_git_sha: str,
    workflow_run_id: str,
) -> None:
    import matplotlib.pyplot as plt

    physical = [
        row
        for row in face_results
        if row.succeeded and row.execution_level == "face_mapping"
    ]
    plt.figure(figsize=(10, 5))
    plt.plot(
        range(len(physical)),
        [row.F_rho_kg_m2_s for row in physical],
        marker="o",
    )
    plt.xticks(
        range(len(physical)),
        [row.case_id.replace("B2-", "") for row in physical],
        rotation=70,
        ha="right",
        fontsize=7,
    )
    plt.ylabel("Outward mass flux [kg m$^{-2}$ s$^{-1}$]")
    plt.title(
        "U3 B2 independent right-face mass-flux targets\n"
        + plot_provenance_text(
            "face mapping", backend_version, source_git_sha, workflow_run_id
        ),
        fontsize=8,
    )
    plt.tight_layout()
    plt.savefig(output_dir / "face_flux_reference.png", dpi=160)
    plt.close()

    rows32 = sorted(
        (row for row in acoustic_rows if row.cells == 32),
        key=lambda row: row.probe_x_over_L,
    )
    plt.figure(figsize=(8, 5))
    probes = [row.probe_x_over_L for row in rows32]
    plt.plot(probes, [row.direct_arrival_time_s for row in rows32], marker="o", label="direct")
    plt.plot(probes, [row.reflected_arrival_time_s for row in rows32], marker="o", label="reflected")
    plt.xlabel("Probe x/L")
    plt.ylabel("Reference arrival time [s]")
    plt.legend()
    plt.title(
        "U3 B2 linear-acoustic arrival targets\n"
        + plot_provenance_text(
            "32-cell requested probes", backend_version, source_git_sha, workflow_run_id
        ),
        fontsize=8,
    )
    plt.tight_layout()
    plt.savefig(output_dir / "acoustic_arrival_reference.png", dpi=160)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.bar(
        ["mass", "energy", "momentum"],
        [
            abs(one_step.mass_inventory_residual_kg),
            abs(one_step.energy_inventory_residual_J),
            abs(one_step.momentum_inventory_residual_kg_m_s),
        ],
    )
    plt.yscale("symlog", linthresh=1e-16)
    plt.ylabel("Absolute one-step balance residual")
    plt.title(
        "U3 B2 one-step independent balance\n"
        + plot_provenance_text(
            one_step.case_id, backend_version, source_git_sha, workflow_run_id
        ),
        fontsize=8,
    )
    plt.tight_layout()
    plt.savefig(output_dir / "one_step_balance_reference.png", dpi=160)
    plt.close()
def artifact_manifest(output_dir: Path) -> None:
    lines = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.name == "artifact_sha256.txt" or not path.is_file():
            continue
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (output_dir / "artifact_sha256.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
