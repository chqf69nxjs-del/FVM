"""One-shot materializer for the reviewed Stage 7 P1-A1 bundle.

The temporary payload files, this script, and its workflow remove themselves after
extracting the prepared source, tests, specification, and A1 workflow. The payload
SHA and exact path allowlist are checked before extraction.
"""

from __future__ import annotations

import base64
import hashlib
import io
import tarfile
from pathlib import Path

PAYLOAD_FILES = (
    "tools/p1_a1_payload_01.txt",
    "tools/p1_a1_payload_02.txt",
    "tools/p1_a1_payload_03.txt",
)
PAYLOAD_SHA256 = "480d72a142d444d4489406afa65cd994798e3e581410000ad9aae010fbae30be"
ALLOWED_FILES = {
    "src/liquid_gas_transient/hem_pipeline_pressure_phase_relationship.py",
    "tests/test_stage7_p1_pressure_phase_relationship.py",
    "docs/verification/stage7_p1_pressure_phase_relationship_increment_a1.md",
    ".github/workflows/stage7-p1-pressure-phase-relationship-a1.yml",
}
TEMPORARY_FILES = (
    *PAYLOAD_FILES,
    "tools/materialize_stage7_p1_a1.py",
    ".github/workflows/materialize-stage7-p1-a1.yml",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    encoded = "".join(
        (root / relative).read_text(encoding="ascii").strip()
        for relative in PAYLOAD_FILES
    )
    archive = base64.b64decode(encoded.encode("ascii"), validate=True)
    actual_sha = hashlib.sha256(archive).hexdigest()
    if actual_sha != PAYLOAD_SHA256:
        raise RuntimeError(
            f"payload SHA mismatch: expected={PAYLOAD_SHA256}, actual={actual_sha}"
        )

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        members = bundle.getmembers()
        names = {member.name for member in members if member.isfile()}
        if names != ALLOWED_FILES:
            raise RuntimeError(f"unexpected payload paths: {sorted(names)}")
        root_resolved = root.resolve()
        for member in members:
            destination = (root / member.name).resolve()
            if destination != root_resolved and root_resolved not in destination.parents:
                raise RuntimeError(f"unsafe payload path: {member.name}")
        bundle.extractall(root, filter="data")

    for relative in TEMPORARY_FILES:
        path = root / relative
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    main()
