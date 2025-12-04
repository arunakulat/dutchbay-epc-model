from __future__ import annotations

import re
from pathlib import Path

# Project root: tests/lint/ -> tests -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# We care about internal code, not venvs or tests.
SEARCH_ROOTS = (
    PROJECT_ROOT / "finance",
    PROJECT_ROOT / "analytics",
    PROJECT_ROOT / "api",
)

# Patterns that suggest someone is re-defining WACC formulas rather than
# just *using* the outputs from finance/wacc_v14.py.
WACC_DEF_PATTERNS: list[str] = [
    r"weighted\s+average\s+cost\s+of\s+capital",
    r"WACC\s*=\s*\(",
    r"WACC\s*=\s*(\(E\s*/\s*V|E\s*/\s*V)",  # WACC = (E/V ... style
    r"\(E\s*/\s*V\)\s*\*\s*Ke\s*\+\s*\(D\s*/\s*V\)\s*\*\s*Kd",  # (E/V)*Ke + (D/V)*Kd
]


def _iter_python_files() -> list[Path]:
    """Yield Python files under the core code packages.

    We *exclude* tests and virtualenvs on purpose.
    """
    files: list[Path] = []
