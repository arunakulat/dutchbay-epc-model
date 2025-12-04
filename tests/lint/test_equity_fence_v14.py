from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FINANCE_DIR = PROJECT_ROOT / "finance"
ANALYTICS_DIR = PROJECT_ROOT / "analytics"

# Functions that must only be defined in finance/equity_v14.py
EQUITY_METRIC_FUNCS = {
    "summarise_equity_cashflows",
    "calculate_equity_irr",
    "calculate_cash_on_cash",
    "calculate_moic",
    "calculate_payback_period",
    "calculate_pe_triad",
    "calculate_equity_performance",
}


def _iter_source_files() -> list[Path]:
    """
    Yield Python files under finance/ and analytics/, excluding:

    - finance/equity_v14.py (canonical equity implementation),
    - any obvious __init__ files we don't care about structurally.
    """
    paths: list[Path] = []

    for root in (FINANCE_DIR, ANALYTICS_DIR):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            # Skip the canonical home
            if path.name == "equity_v14.py" and path.parent == FINANCE_DIR:
                continue
            paths.append(path)

    return paths


def test_equity_metric_functions_only_defined_in_equity_v14() -> None:
    """
    Guardrail: core equity metric functions must be defined only in
    finance/equity_v14.py.

    Other modules (including analytics/*) may *use* these via imports
    or via dataclasses (EquityPerformance), but must not re-define
    the core implementations.
    """
    offending: list[str] = []

    for path in _iter_source_files():
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            # If a file is syntactically broken, other tests will fail loudly.
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in EQUITY_METRIC_FUNCS:
                rel = path.relative_to(PROJECT_ROOT)
                offending.append(f"{rel}: defines {node.name}()")

    assert not offending, (
        "Equity metric functions must only be defined in finance/equity_v14.py.\n"
        "Found extra definitions in:\n  - " + "\n  - ".join(offending)
        if offending
        else ""
    )
