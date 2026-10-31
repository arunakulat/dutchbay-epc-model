"""Split ``finance/debt_v14.py`` into the ``finance.debt`` package, verbatim.

The debt engine's top-level statements are copied byte for byte, each with the comment
block above it, into the module named in ``LAYOUT``. Each new module gets a short
header: its own docstring, the imports its statements use, and the shared
``"finance.debt_v14"`` logger. ``finance/debt_v14.py`` is then rewritten as a façade
that re-exports every name the original defined, so every import path still works.

The source is read from git, never from the working tree, so the split can be re-run
and compared against what is committed::

    python scripts/refactor/split_debt_v14.py <source-commit>          # write
    python scripts/refactor/split_debt_v14.py <source-commit> --check  # compare only

``--check`` regenerates into a temporary directory, formats it with isort and black,
and exits non-zero if any generated file differs from the working tree. It also checks
that every original top-level statement appears verbatim in exactly one generated file.
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = "finance/debt_v14.py"
PACKAGE = "finance.debt"

# Target module for every top-level definition in the source, in the order the modules
# are documented. A name the source defines that is missing here stops the split.
LAYOUT: dict[str, tuple[str, ...]] = {
    "constants": (
        "_BALLOON_VALID_TREATMENTS",
        "_BALLOON_DEFAULT_TREATMENT",
        "_AMORT_ANNUITY_STYLES",
        "_AMORT_SCULPTED_STYLES",
        "_AMORT_VALID_STYLES",
        "_AMORT_DEFAULT_STYLE",
        "_BALLOON_TOL",
        "_SERVICE_TOL",
        "REFINANCE_TERMS_BASIS",
    ),
    "helpers": (
        "_lookup_case_insensitive",
        "_section_case_insensitive",
        "_get",
        "_as_float",
        "_truthy_flag",
        "_pmt",
        "_npv",
        "_rate_decimal",
        "_finite_number",
    ),
    "placeholders": (
        "_PLACEHOLDER_WARNS_EMITTED",
        "_warn_placeholder_once",
        "reset_placeholder_warn_dedup",
        "_FORBID_TOY_FALLBACK_KEY",
        "_allow_toy_capex_fallback",
    ),
    "capex": ("_extract_capex_base_usd", "_extract_capex_usd"),
    "dscr_contract": (
        "_finite_dscr",
        "_clean_public_dscr_series",
        "_normalize_operating_year",
        "_build_dscr_periods",
        "_operating_dscr_minimum",
        "deprecated_raw_dscr_series",
    ),
    "terms": (
        "_warned_decorative_tranches",
        "_warn_if_decorative_tranches",
        "_extract_financing_terms",
        "_resolve_construction_periods",
        "_build_cfads_timeline",
        "_resolve_first_operating_period",
    ),
    "construction": ("calculate_construction_drawdowns", "calculate_idc"),
    "schedules": ("Tranche", "_solve_mix", "_annuity_schedule", "_sculpted_schedule"),
    "layer": ("apply_debt_layer",),
    "sizing": (
        "_solve_gearing_for_dscr",
        "_resolve_downside_ratio",
        "_maybe_autosolve_dscr",
        "size_debt_with_dual_dscr",
    ),
    "balloon": (
        "_maturity_period_index",
        "resolve_balloon_treatment",
        "resolve_refinance_terms",
        "_balloon_resolution_stream",
        "_refinance_disclosure",
        "_resize_for_amortization",
    ),
    "funding": ("_build_funding",),
    "plan": ("plan_debt",),
    "schema": ("_register_debt_schema",),
}

DOCSTRINGS: dict[str, str] = {
    "constants": "Balloon, amortisation and tolerance constants of the debt engine.",
    "helpers": "Lookup, coercion, annuity and discounting helpers of the debt engine.",
    "placeholders": "Placeholder warn-once state and the run-mode toy-fallback ceiling.",
    "capex": "CAPEX extraction for debt sizing, with its placeholder guard.",
    "dscr_contract": "The public DSCR series contract and its operating-period minimum.",
    "terms": "Financing terms, construction window and the debt-period taxonomy.",
    "construction": "Construction drawdowns and interest during construction.",
    "schedules": "Tranches, currency mix and the annuity and sculpted schedules.",
    "layer": "The debt layer: schedules, service, coverage ratios and fees per period.",
    "sizing": "Debt sizing: the dual-DSCR solve and the gearing autosolve.",
    "balloon": "Balloon treatment: maturity, refinance terms and resolution streams.",
    "funding": "Sources and uses of funds for the financed project cost.",
    "plan": "``plan_debt``: the debt engine's orchestrator.",
    "schema": "Required-field registration for the debt configuration section.",
}

PACKAGE_DOCSTRING = (
    "Implementation modules of the debt engine.\n\n"
    "Import from ``finance.debt_v14``, the engine's public surface. The modules here hold\n"
    "its code, moved verbatim by ``scripts/refactor/split_debt_v14.py``.\n"
)

FACADE_NOTE = (
    "\n"
    "The engine's code lives in the ``finance.debt`` package, moved there verbatim by\n"
    "``scripts/refactor/split_debt_v14.py``. This module stays the public surface and\n"
    "re-exports every name it defined before the move, so import from here.\n"
)

LOGGER_LINES = (
    "# The engine logged as ``finance.debt_v14`` before the split; keep that name so\n"
    "# log filters and caplog assertions still see these records.\n"
    'logger = logging.getLogger("finance.debt_v14")\n'
)

# Names the façade must not re-export: a module-level flag that a function rebinds with
# ``global``. A copy in the façade would go stale; read it from its owning module.
NOT_REEXPORTED = frozenset({"_warned_decorative_tranches"})


def _git_show(commit: str) -> str:
    return subprocess.run(
        ["git", "show", f"{commit}:{SOURCE_PATH}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _bound_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def _used_names(node: ast.stmt) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def split(source: str) -> dict[str, str]:
    """Return ``{repo-relative path: unformatted text}`` for the package and façade."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    body = tree.body

    owner = {name: mod for mod, names in LAYOUT.items() for name in names}
    if len(owner) != sum(len(v) for v in LAYOUT.values()):
        raise SystemExit("LAYOUT names a definition twice")

    # Header: docstring, imports and the module logger, which every module rebuilds.
    header_end = 0
    imports: dict[str, str] = {}  # bound name -> import line that binds it
    for node in body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            header_end = node.end_lineno or 0
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                header_end = node.end_lineno or 0
                continue
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if isinstance(node, ast.ImportFrom):
                    imports[bound] = f"from {node.module} import {alias.name}"
                else:
                    imports[bound] = f"import {alias.name}"
            header_end = node.end_lineno or 0
            continue
        if _bound_names(node) == ["logger"]:
            header_end = node.end_lineno or 0
            continue
        break

    chunks: dict[str, list[str]] = {mod: [] for mod in LAYOUT}
    defined: dict[str, set[str]] = {mod: set() for mod in LAYOUT}
    used: dict[str, set[str]] = {mod: set() for mod in LAYOUT}
    facade_tail: list[str] = []
    seen: set[str] = set()
    prev_end = header_end
    for node in body:
        if (node.end_lineno or 0) <= header_end:
            continue
        # The statement plus the comments and blank lines that precede it.
        text = "".join(lines[prev_end : node.end_lineno]).strip("\n") + "\n"
        prev_end = node.end_lineno or prev_end
        names = _bound_names(node)
        if not names:
            facade_tail.append(text)
            continue
        mods = {owner.get(n) for n in names}
        if None in mods or len(mods) != 1:
            raise SystemExit(f"no single LAYOUT module for {names}")
        mod = mods.pop()
        assert mod is not None
        chunks[mod].append(text)
        defined[mod].update(names)
        used[mod] |= _used_names(node)
        seen.update(names)
    trailing = "".join(lines[prev_end:]).strip("\n")
    if trailing:
        facade_tail.append(trailing + "\n")
    missing = set(owner) - seen
    if missing:
        raise SystemExit(
            f"LAYOUT names definitions the source lacks: {sorted(missing)}"
        )

    out: dict[str, str] = {}
    for mod in LAYOUT:
        need = used[mod] - defined[mod]
        stdlib = sorted(
            imports[n]
            for n in need
            if n in imports and not imports[n].startswith("from ")
        )
        froms: dict[str, list[str]] = {}
        for n in sorted(need):
            if n in imports and imports[n].startswith("from "):
                module, name = imports[n][5:].split(" import ")
                froms.setdefault(module, []).append(name)
            elif n in owner and owner[n] != mod:
                froms.setdefault(f"{PACKAGE}.{owner[n]}", []).append(n)
        uses_logger = "logger" in need
        if uses_logger and "import logging" not in stdlib:
            stdlib = sorted([*stdlib, "import logging"])
        head = [
            f'"""{DOCSTRINGS[mod]}"""\n',
            "\n",
            "from __future__ import annotations\n",
            "\n",
        ]
        # Three import groups: standard library, the rest of ``finance``, this package.
        groups: list[list[str]] = [[line + "\n" for line in stdlib], [], []]
        for module in sorted(froms):
            group = (
                2 if module.startswith(PACKAGE) else int(module.startswith("finance"))
            )
            groups[group].append(
                f"from {module} import {', '.join(sorted(froms[module]))}\n"
            )
        for group_lines in groups:
            if group_lines:
                head += [*group_lines, "\n"]
        if uses_logger:
            head += [LOGGER_LINES, "\n"]
        out[f"finance/debt/{mod}.py"] = (
            "".join(head) + "\n\n" + "\n\n".join(chunks[mod])
        )
    out["finance/debt/__init__.py"] = f'"""{PACKAGE_DOCSTRING}"""\n'

    doc = ast.get_docstring(tree, clean=False) or ""
    facade = [
        f'"""{doc.rstrip()}\n{FACADE_NOTE}"""\n',
        "\n",
        "from __future__ import annotations\n",
        "\n",
    ]
    facade.append("import logging\n\n")
    for mod in LAYOUT:
        names = sorted(n for n in LAYOUT[mod] if n not in NOT_REEXPORTED)
        if names:
            facade.append(f"from {PACKAGE}.{mod} import (  # noqa: F401\n")
            facade += [f"    {n},\n" for n in names]
            facade.append(")\n")
    facade += [
        "\n",
        "logger = logging.getLogger(__name__)\n",
        "\n\n",
        "\n\n".join(facade_tail),
    ]
    out[SOURCE_PATH] = "".join(facade)
    return out


def _write(files: dict[str, str], root: Path) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    paths = [str(root / rel) for rel in files]
    # The repository's formatting gates are isort then black, configured in pyproject.
    settings = str(REPO_ROOT / "pyproject.toml")
    isort = [sys.executable, "-m", "isort", "--quiet", "--settings-path", settings]
    black = [sys.executable, "-m", "black", "--quiet", "--config", settings]
    subprocess.run([*isort, *paths], cwd=REPO_ROOT, check=True)
    subprocess.run([*black, *paths], cwd=REPO_ROOT, check=True)


def _verbatim(source: str, root: Path, files: dict[str, str]) -> list[str]:
    """Every original top-level statement must appear once, unchanged, in the output."""
    texts = {rel: (root / rel).read_text(encoding="utf-8") for rel in files}
    problems = []
    for node in ast.parse(source).body:
        names = _bound_names(node)
        if not names or names == ["logger"]:
            continue
        segment = ast.get_source_segment(source, node) or ""
        hits = [rel for rel, text in texts.items() if segment in text]
        if len(hits) != 1:
            problems.append(f"{names}: found in {hits or 'no file'}")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2) or (len(argv) == 2 and argv[1] != "--check"):
        print(__doc__)
        return 2
    source = _git_show(argv[0])
    files = split(source)
    if len(argv) == 1:
        _write(files, REPO_ROOT)
        problems = _verbatim(source, REPO_ROOT, files)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copy(REPO_ROOT / "pyproject.toml", root / "pyproject.toml")
            _write(files, root)
            problems = _verbatim(source, root, files)
            for rel in files:
                if (root / rel).read_bytes() != (REPO_ROOT / rel).read_bytes():
                    problems.append(f"{rel}: differs from the working tree")
    for problem in problems:
        print(problem)
    print(f"{len(files)} files, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
