"""Grid-FREE gateway / CCCDIR-boundary tests for the D3 grid study (#874).

Imports NO grid library (pandapower/andes). Proves the STATIC properties of the D3
gateway that must hold in the default (grid-free) install:

  * the grid modules (contracts, reactive screen, gateway) import cleanly with NO grid
    extra installed (CASPER: pandapower is guarded at call-time, never at import time);
  * the gateway reaches grid RESULT types ONLY through ``analytics.contracts_v14`` and
    does NOT import the finance engine or a pipeline module (CCCDIR boundary), verified
    by static LibCST inspection of the gateway's own module-level imports;
  * ``evaluate_grid`` strictly gates on ``grid.study_enabled`` (CESSPIT: no silent
    no-op) and refuses a missing ``grid`` block.
"""

from __future__ import annotations

from pathlib import Path

import libcst as cst
import pytest

_REPO = Path(__file__).resolve().parents[2]
_GATEWAY = _REPO / "analytics" / "grid" / "evaluate_grid.py"


def test_grid_modules_import_without_pandapower() -> None:
    """CASPER: the D3 grid surface imports cleanly in a grid-free environment."""
    import importlib

    # These imports must NOT require pandapower (the guard is call-time only).
    for mod in (
        "analytics.contracts_v14",
        "analytics.grid",
        "analytics.grid.reactive_screen",
        "analytics.grid.evaluate_grid",
    ):
        importlib.import_module(mod)

    from analytics.contracts_v14 import (  # noqa: F401
        GridStudyResult,
        PowerFlowResult,
        ReactiveCapabilityResult,
    )
    from analytics.grid.evaluate_grid import evaluate_grid  # noqa: F401


def _module_level_imports(path: Path) -> list[str]:
    """Return the fully-qualified names imported at MODULE scope in ``path``."""
    tree = cst.parse_module(path.read_text())
    names: list[str] = []

    class _Collector(cst.CSTVisitor):
        def __init__(self) -> None:
            self.depth = 0

        # Only inspect top-level statements (depth 0) — skip function/class bodies.
        def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
            self.depth += 1
            return True

        def leave_FunctionDef(self, node: cst.FunctionDef) -> None:
            self.depth -= 1

        def visit_ClassDef(self, node: cst.ClassDef) -> bool:
            self.depth += 1
            return True

        def leave_ClassDef(self, node: cst.ClassDef) -> None:
            self.depth -= 1

        def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
            if self.depth != 0 or node.module is None:
                return
            names.append(_dotted(node.module))

        def visit_Import(self, node: cst.Import) -> None:
            if self.depth != 0:
                return
            for alias in node.names:
                names.append(_dotted(alias.name))

    tree.visit(_Collector())
    return names


def _dotted(node: cst.BaseExpression) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{_dotted(node.value)}.{node.attr.value}"
    return ""


def test_gateway_imports_grid_results_only_from_contracts_v14() -> None:
    """CCCDIR: the gateway imports result types only from contracts_v14, engine only via grid.*."""
    imports = _module_level_imports(_GATEWAY)

    # The gateway must NOT import the finance engine or a pipeline module directly.
    for name in imports:
        assert not (
            name == "finance" or name.startswith("finance.")
        ), f"gateway imports finance engine directly: {name}"
        assert not name.startswith(
            "analytics.pipeline_"
        ), f"gateway imports a pipeline module directly: {name}"

    # It MUST source the grid RESULT contracts from the centralised module.
    assert (
        "analytics.contracts_v14" in imports
    ), "gateway must import grid result types from analytics.contracts_v14 (CCCDIR)."
    # And reach the engine ONLY via analytics.grid.* screen modules.
    grid_engine_imports = [n for n in imports if n.startswith("analytics.grid")]
    assert (
        grid_engine_imports
    ), "gateway must import the grid screens from analytics.grid.*"


def test_evaluate_grid_requires_grid_block() -> None:
    from analytics.grid.evaluate_grid import evaluate_grid

    with pytest.raises(ValueError, match="grid"):
        evaluate_grid({"fx": {"start_lkr_per_usd": 333.79}})


def test_evaluate_grid_gates_on_study_enabled() -> None:
    from analytics.grid.evaluate_grid import evaluate_grid

    with pytest.raises(ValueError, match="study_enabled"):
        evaluate_grid({"grid": {"study_enabled": False}})
