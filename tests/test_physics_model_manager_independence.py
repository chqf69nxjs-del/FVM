from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import inspect

import pytest

import liquid_gas_transient.physics_model_manager as module
from liquid_gas_transient.physics_model_manager import (
    BoundaryRegime,
    PhysicsBoundaryModelManager,
)


def test_module_has_no_solver_or_property_backend_imports() -> None:
    tree = ast.parse(inspect.getsource(module))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any("CoolProp" in name for name in imported)
    assert not any(name.endswith("solver") for name in imported)
    assert not any(name.endswith("properties") for name in imported)


def test_selection_snapshots_are_immutable() -> None:
    manager = PhysicsBoundaryModelManager()

    with pytest.raises(FrozenInstanceError):
        manager.selection.boundary_regime = BoundaryRegime.ZERO_TRANSFER_CLOSED  # type: ignore[misc]
