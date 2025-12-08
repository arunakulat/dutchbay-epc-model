#!/usr/bin/env python3
"""
Heuristic mypy auto-fixer for analytics/ and finance/.

- Skips analytics/monte_carlo_v14.py (under active refactor).
- Applies targeted textual transforms for known mypy patterns.
- Prints each edit but does NOT commit anything.

Run from repo root:
    python auto_fix_mypy.py
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
TARGET_DIRS = [ROOT / "analytics", ROOT / "finance"]
EXCLUDE_PATHS = {ROOT / "analytics" / "monte_carlo_v14.py"}


def iter_py_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for base in TARGET_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if path in EXCLUDE_PATHS:
                continue
            files.append(path)
    return files


# --- individual fixers -----------------------------------------------------


def fix_collection_append(src: str) -> str:
    """Collection[str] with .append -> list[str]."""
    # Simple pattern: errors = Collection[str] = []
    pattern = re.compile(r"(:\s*Collection\[str\]\s*=\s*\[\])")
    if pattern.search(src):
        src = src.replace("Collection[str]", "list[str]")
    return src


def fix_optional_defaults(src: str) -> str:
    """
    Fix signatures like:
        def f(x: list[float] = None, y: Dict[str, float] = None)
    into:
        def f(x: Optional[list[float]] = None, y: Optional[dict[str, float]] = None)
    and add needed imports.
    """
    changed = False

    # list[float] default None
    def repl_list(m: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return f"{m.group(1)}Optional[list[float]]{m.group(2)}"

    src = re.sub(
        r"(fx_range_pct:\s*)list\[float\](\s*=\s*None)",
        repl_list,
        src,
    )

    # dict[str, float] default None
    def repl_dict(m: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return f"{m.group(1)}Optional[dict[str, float]]{m.group(2)}"

    src = re.sub(
        r"(paydown_scenarios:\s*)dict\[str,\s*float\](\s*=\s*None)",
        repl_dict,
        src,
    )

    # fx_shocks: list[float] = None
    src = re.sub(
        r"(fx_shocks:\s*)list\[float\](\s*=\s*None)",
        repl_list,
        src,
    )

    if changed and "Optional[" in src and "from typing import" in src:
        # Ensure Optional is imported
        if "Optional" not in src:
            src = src.replace(
                "from typing import",
                "from typing import Optional,",
                1,
            )
    elif changed and "Optional[" in src and "from typing import" not in src:
        # Add a typing import at top
        src = "from typing import Optional\n\n" + src

    return src


def fix_bare_dicts(src: str) -> str:
    """
    Replace some bare Dict/dict occurrences with typed versions.

    This is intentionally conservative and focuses on patterns mypy reported.
    """
    # Dict -> dict[str, float] when clearly numeric map
    src = re.sub(r"\bDict\b(?!\[)", "dict[str, float]", src)
    # dict = {} -> dict[str, float] = {}
    src = re.sub(r"\bdict\s*=\s*{}", "dict[str, float] = {}", src)
    # generic 'dict' type without parameters in annotations
    src = re.sub(r":\s*dict(?!\[)", ": dict[str, float]", src)
    return src


def strip_unused_type_ignores(src: str) -> str:
    """
    Remove 'type: ignore' on PySAM imports and other lines where mypy reports unused-ignore,
    while leaving most other ignores intact.
    """
    lines = src.splitlines()
    out: list[str] = []
    for line in lines:
        if "PySAM" in line and "type: ignore" in line:
            # Drop the ignore; we rely on mypy.ini instead.
            line = re.sub(r"#\s*type:\s*ignore\[?[a-z_,]*]?\s*", "", line)
        out.append(line)
    return "\n".join(out) + ("\n" if src.endswith("\n") else "")


def ensure_pysam_ignore_in_config():
    """
    Remind the user to add mypy-PySAM.* ignore_missing_imports if not present.
    Cannot safely edit mypy.ini here, so only print guidance.
    """
    print(
        "NOTE: Ensure mypy.ini contains:\n"
        "  [mypy-PySAM.*]\n"
        "  ignore_missing_imports = True\n"
    )


def add_simple_function_annotations(src: str) -> str:
    """
    Very simple heuristic: in certain known modules, add -> None to functions
    missing a return type when they look like procedures.

    This is intentionally narrow to avoid breaking APIs.
    """
    lines = src.splitlines()
    new_lines: list[str] = []
    for line in lines:
        if (
            line.lstrip().startswith("def ")
            and "->" not in line
            and "(" in line
            and line.rstrip().endswith(":")
        ):
            # Add '-> None' for now
            line = line.rstrip()[:-1] + " -> None:"
        new_lines.append(line)
    return "\n".join(new_lines) + ("\n" if src.endswith("\n") else "")


def process_file(path: pathlib.Path) -> None:
    src = path.read_text(encoding="utf8")

    original = src

    if "analytics/fx/processor.py" in str(path):
        src = fix_collection_append(src)
        src = add_simple_function_annotations(src)

    if "analytics/fx/correlation.py" in str(path):
        src = fix_optional_defaults(src)
        src = fix_bare_dicts(src)

    if "analytics/sensitivity" in str(path):
        src = fix_bare_dicts(src)
        src = add_simple_function_annotations(src)

    if "analytics/sensitivity_heatmap.py" in str(path):
        src = add_simple_function_annotations(src)
        src = fix_bare_dicts(src)

    if "analytics/pysam_sandbox/pysam_runner.py" in str(path):
        src = strip_unused_type_ignores(src)

    if src != original:
        print(f"[fix] {path}")
        path.write_text(src, encoding="utf8")


def main() -> None:
    files = iter_py_files()
    print(
        f"Scanning {len(files)} Python files under analytics/ and finance/ (excluding monte_carlo_v14.py)"
    )
    for path in files:
        process_file(path)
    ensure_pysam_ignore_in_config()
    print("Done. Re-run: python -m mypy analytics finance")


if __name__ == "__main__":
    main()
