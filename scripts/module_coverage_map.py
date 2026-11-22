"""Where each module's results end up: the static scan behind the coverage map (#1751).

``docs/MODULE_COVERAGE_MAP.md`` lists every Python module under ``analytics/``,
``finance/``, ``app/``, ``wind_resource/`` and ``solar_resource/`` with one status. This
module computes those statuses from a LibCST import scan (``CST-01``), and
``tests/lint/test_module_coverage_map.py`` checks the committed map against it.

Statuses, strongest first
-------------------------
``pipeline``
    Reached from the pipeline run: :mod:`analytics.pipeline_v14_enhanced`, or
    ``run_full_pipeline_v14.py`` without passing through an emitter module.
``emitter``
    Reached only through an emitter step of ``run_full_pipeline_v14.py``
    (:data:`EMITTER_ROOTS`): the module's results reach a run's outputs when that emitter
    runs.
``report``
    Reached from the lender report (:data:`REPORT_ROOTS`).
``web``
    Reached from the web app or the HTTP API (``api/`` and ``app/`` outside
    ``app/reports/``).
``script``
    Reached only from a script (``scripts/``, ``analysis_tools/``,
    ``feasibility_reproduce/``, ``examples/`` and the top-level ``*.py`` other than the
    pipeline CLI), or run as a script itself: a module with an
    ``if __name__ == "__main__":`` block, such as the Hydra CLIs under ``analytics/cli/``.
``unreached``
    No live root reaches it. Its results are seen only by the tests that import it, if any.
``retired``
    Declared retired in the map. The scan must agree that no live root reaches it.

A module reached from several classes takes the strongest, and the map must record exactly
that class: :func:`check_map` reports a row whose status differs from the scan's, a live
row whose entry cell names a root that does not reach it, and an ``unreached`` or
``retired`` row for a module a live root reaches.

What the scan cannot see
------------------------
The scan follows ``import`` and ``from ... import`` statements anywhere in a file
(function bodies and ``TYPE_CHECKING`` blocks included, so it over-approximates), the
packages an import runs (``a.b.c`` runs ``a`` and ``a.b``), and
``importlib.import_module`` called with a string literal. It cannot see:

* ``importlib.import_module`` or ``__import__`` with a computed name (each file that does
  this is listed by :func:`dynamic_import_sites`);
* Hydra ``_target_`` strings and other dotted paths held in YAML;
* a script started as a subprocess (``python -m``, ``subprocess.run([...])``);
* code reached only through a plugin or entry point declared in packaging metadata.

Run ``python scripts/module_coverage_map.py`` to rewrite the map from the scan. Notes
written in the map's last column are kept.
"""

from __future__ import annotations

import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import libcst as cst

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = REPO_ROOT / "docs" / "MODULE_COVERAGE_MAP.md"

#: Packages whose modules the map lists.
MAPPED_PACKAGES: Tuple[str, ...] = (
    "analytics",
    "finance",
    "app",
    "wind_resource",
    "solar_resource",
)

#: Statuses, strongest first. ``retired`` is a declared form of ``unreached``.
STATUSES: Tuple[str, ...] = (
    "pipeline",
    "emitter",
    "report",
    "web",
    "script",
    "unreached",
    "retired",
)
LIVE_STATUSES: Tuple[str, ...] = STATUSES[:5]

PIPELINE_CLI = "run_full_pipeline_v14"

#: The pipeline run.
PIPELINE_ROOTS: Tuple[str, ...] = ("analytics.pipeline_v14_enhanced", PIPELINE_CLI)

#: The emitter steps of the pipeline CLI. The pipeline traversal stops at each, so a
#: module reached only through one is classed ``emitter``.
EMITTER_ROOTS: Tuple[str, ...] = (
    "analytics.executive_workbook",
    "app.reports.capital_risk_emit",
    "app.reports.grid_screening_emit",
    "app.reports.interaction_grid_emit",
    "app.reports.lender_report_emit",
    "app.reports.tech_comparison_emit",
)

#: The lender report.
REPORT_ROOTS: Tuple[str, ...] = (
    "app.reports.report_orchestration",
    "app.reports.renderer",
    "app.reports.report_model",
)

#: Top-level directories whose files are scripts.
SCRIPT_DIRS: Tuple[str, ...] = (
    "scripts",
    "analysis_tools",
    "feasibility_reproduce",
    "examples",
)

#: Directories never scanned as importers of live code.
_EXCLUDED_TOP: Tuple[str, ...] = (
    "tests",
    "legacy",
    "legacy_scripts",
    "legacy_tests",
    "docs",
    ".devcontainer",
    ".venv",
)


@dataclass(frozen=True)
class Scan:
    """The import graph and the module inventory.

    Attributes:
        files: Dotted module name to repository-relative path, for every tracked file
            the scan reads (a package's ``__init__.py`` under the package's own name).
        edges: Module name to the module names its imports run.
        edges_outside_emitters: The same, leaving out every import statement that
            imports an emitter module, together with the packages that statement runs
            (``from app.reports.capital_risk_emit import ...`` also runs
            ``app.reports``, but only when the emitter step runs).
        dynamic: Module name to the number of dynamic imports with a computed name.
        test_importers: Mapped module name to the test files that import it.
        run_as_script: Modules with an ``if __name__ == "__main__":`` block, which are
            script roots themselves.
    """

    files: Mapping[str, str]
    edges: Mapping[str, Set[str]]
    edges_outside_emitters: Mapping[str, Set[str]]
    dynamic: Mapping[str, int]
    test_importers: Mapping[str, Set[str]] = field(default_factory=dict)
    run_as_script: Set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Reach:
    """One live class's reach: each reached module and the root that first reached it."""

    via: Mapping[str, str]


def module_name(rel: str) -> str:
    """``a/b/c.py`` to ``a.b.c``; ``a/b/__init__.py`` to ``a.b``."""
    parts = list(Path(rel).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _tracked_python_files(root: Path) -> List[str]:
    import subprocess

    out = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(line for line in out.splitlines() if line)


def mapped_modules(files: Mapping[str, str]) -> List[str]:
    """Every module the map must list: mapped packages, ``__init__`` files excluded."""
    return sorted(
        name
        for name, rel in files.items()
        if rel.split("/", 1)[0] in MAPPED_PACKAGES and not rel.endswith("__init__.py")
    )


class _ImportCollector(cst.CSTVisitor):
    def __init__(self, package: str, is_package: bool) -> None:
        self.package = package
        self.is_package = is_package
        self.targets: List[Tuple[str, Tuple[str, ...]]] = []
        self.dynamic = 0

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            self.targets.append((_dotted(alias.name), ()))

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        base = _dotted(node.module) if node.module is not None else ""
        level = len(node.relative)
        if level:
            anchor = self.package.split(".") if self.package else []
            drop = level - 1
            if drop > len(anchor):
                return
            anchor = anchor[: len(anchor) - drop] if drop else anchor
            base = ".".join([*anchor, base] if base else anchor)
        names: Tuple[str, ...] = ()
        if not isinstance(node.names, cst.ImportStar):
            names = tuple(_dotted(alias.name) for alias in node.names)
        self.targets.append((base, names))

    def visit_Call(self, node: cst.Call) -> None:
        func = node.func
        name = ""
        if isinstance(func, cst.Attribute):
            name = func.attr.value
        elif isinstance(func, cst.Name):
            name = func.value
        if name not in ("import_module", "__import__"):
            return
        if node.args and isinstance(node.args[0].value, cst.SimpleString):
            literal = node.args[0].value.evaluated_value
            if isinstance(literal, str) and not literal.startswith("."):
                self.targets.append((literal, ()))
                return
        self.dynamic += 1


def _dotted(node: cst.BaseExpression) -> str:
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        return f"{_dotted(node.value)}.{node.attr.value}"
    return ""


def _resolve(target: str, names: Sequence[str], known: Mapping[str, str]) -> Set[str]:
    """The known modules an import of ``target`` (and ``names`` from it) runs."""
    out: Set[str] = set()
    if not target:
        return out
    parts = target.split(".")
    for end in range(1, len(parts) + 1):
        prefix = ".".join(parts[:end])
        if prefix in known:
            out.add(prefix)
    for name in names:
        child = f"{target}.{name}"
        if child in known:
            out.add(child)
    return out


def scan(root: Path = REPO_ROOT) -> Scan:
    """Parse every tracked Python file and build the import graph."""
    rels = _tracked_python_files(root)
    files: Dict[str, str] = {}
    for rel in rels:
        if rel.split("/", 1)[0] in _EXCLUDED_TOP:
            continue
        files[module_name(rel)] = rel

    edges: Dict[str, Set[str]] = {}
    outside: Dict[str, Set[str]] = {}
    emitters = set(EMITTER_ROOTS)
    dynamic: Dict[str, int] = {}
    for name, rel in files.items():
        collector = _collect(root / rel, name, rel.endswith("__init__.py"))
        edges[name] = set()
        outside[name] = set()
        for target, names in collector.targets:
            group = _resolve(target, names, files)
            edges[name] |= group
            if not group & emitters:
                outside[name] |= group
        edges[name].discard(name)
        outside[name].discard(name)
        if collector.dynamic:
            dynamic[name] = collector.dynamic

    mapped = set(mapped_modules(files))
    test_importers: Dict[str, Set[str]] = {}
    for rel in rels:
        if not rel.startswith("tests/"):
            continue
        collector = _collect(root / rel, module_name(rel), rel.endswith("__init__.py"))
        for target, names in collector.targets:
            for hit in _resolve(target, names, files) & mapped:
                test_importers.setdefault(hit, set()).add(rel)
    return Scan(
        files=files,
        edges=edges,
        edges_outside_emitters=outside,
        dynamic=dynamic,
        test_importers=test_importers,
        run_as_script={
            name
            for name, rel in files.items()
            if _MAIN_GUARD.search(
                (root / rel).read_text(encoding="utf-8", errors="replace")
            )
        },
    )


_MAIN_GUARD = re.compile(r"^if __name__ == [\"']__main__[\"']\s*:", re.MULTILINE)


def _collect(path: Path, name: str, is_package: bool) -> _ImportCollector:
    package = name if is_package else name.rpartition(".")[0]
    collector = _ImportCollector(package, is_package)
    try:
        tree = cst.parse_module(path.read_text(encoding="utf-8"))
    except (cst.ParserSyntaxError, UnicodeDecodeError):
        return collector
    tree.visit(collector)
    return collector


def _bfs(
    roots: Iterable[str],
    edges: Mapping[str, Set[str]],
    stop: Optional[Set[str]] = None,
) -> Dict[str, str]:
    stop = stop or set()
    via: Dict[str, str] = {}
    for root in roots:
        if root not in edges or root in via:
            continue
        via[root] = root
        queue = deque([root])
        while queue:
            node = queue.popleft()
            for nxt in sorted(edges.get(node, ())):
                if nxt in via or nxt in stop:
                    continue
                via[nxt] = root
                queue.append(nxt)
    return via


def class_roots(found: Scan) -> Dict[str, Tuple[str, ...]]:
    """The root modules of each live class."""
    web = tuple(
        sorted(
            name
            for name, rel in found.files.items()
            if rel.startswith("api/")
            or (rel.startswith("app/") and not rel.startswith("app/reports/"))
        )
    )
    script = tuple(
        sorted(
            name
            for name, rel in found.files.items()
            if rel.split("/", 1)[0] in SCRIPT_DIRS
            or ("/" not in rel and name != PIPELINE_CLI)
            or (name in found.run_as_script and name != PIPELINE_CLI)
        )
    )
    return {
        "pipeline": PIPELINE_ROOTS,
        "emitter": EMITTER_ROOTS,
        "report": REPORT_ROOTS,
        "web": web,
        "script": script,
    }


def reaches(found: Scan) -> Dict[str, Reach]:
    """Each live class's reach over the import graph."""
    roots = class_roots(found)
    out: Dict[str, Reach] = {}
    for status in LIVE_STATUSES:
        if status == "pipeline":
            via = _bfs(roots[status], found.edges_outside_emitters, set(EMITTER_ROOTS))
        else:
            via = _bfs(roots[status], found.edges)
        out[status] = Reach(via=via)
    return out


def computed_status(module: str, reach: Mapping[str, Reach]) -> Tuple[str, str]:
    """The strongest class reaching ``module`` and the root that reached it."""
    for status in LIVE_STATUSES:
        root = reach[status].via.get(module)
        if root is not None:
            return status, root
    return "unreached", ""


def dynamic_import_sites(found: Scan) -> List[Tuple[str, int]]:
    """Files with a dynamic import the scan cannot follow, and how many each has."""
    return sorted(found.dynamic.items())


def unreached_reason(module: str, found: Scan) -> str:
    """Why an unreached module's results are seen nowhere at runtime."""
    importers = sorted(found.test_importers.get(module, ()))
    if importers:
        return f"tests only ({len(importers)} test file{'s' if len(importers) != 1 else ''})"
    importers_live = sorted(
        name for name, targets in found.edges.items() if module in targets
    )
    if importers_live:
        return "imported only by unreached modules: " + ", ".join(
            f"`{name}`" for name in importers_live
        )
    return "no importer"


# --- The committed map ---------------------------------------------------------------

_HEADER = "| Module | Status | Entry point or reason | Note |"


@dataclass(frozen=True)
class MapRow:
    module: str
    status: str
    entry: str
    note: str


def parse_map(text: str) -> List[MapRow]:
    """Read the map's module table."""
    rows: List[MapRow] = []
    in_table = False
    for line in text.splitlines():
        if line.strip() == _HEADER:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("| `"):
            if rows:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            raise ValueError(f"map row has {len(cells)} cells, not 4: {line!r}")
        rows.append(
            MapRow(
                module=cells[0].strip("`"),
                status=cells[1],
                entry=cells[2],
                note=cells[3],
            )
        )
    return rows


def entry_root(entry: str) -> Optional[str]:
    """The root module a live row's entry cell names (its first backticked name)."""
    if not entry.startswith("`"):
        return None
    return entry[1:].split("`", 1)[0]


def _reaches_from(root: str, status: str, found: Scan) -> Set[str]:
    """The modules one root of ``status`` reaches, over that class's graph."""
    if status == "pipeline":
        return set(_bfs((root,), found.edges_outside_emitters, set(EMITTER_ROOTS)))
    return set(_bfs((root,), found.edges))


def check_map(text: str, found: Scan) -> List[str]:
    """Every way the committed map disagrees with the scan; empty when it agrees.

    The map must list each mapped module once and no other. A live status must be the
    strongest class the scan finds for the module, and the entry cell must name a root of
    that class that reaches it. An ``unreached`` or ``retired`` row must be reached by no
    live root. The unreached reasons, the counts line and the notes are descriptive and
    are not checked; ``main`` regenerates them.
    """
    problems: List[str] = []
    rows = parse_map(text)
    seen: Set[str] = set()
    for row in rows:
        if row.module in seen:
            problems.append(f"`{row.module}` is listed twice")
        seen.add(row.module)
    expected = set(mapped_modules(found.files))
    for module in sorted(expected - seen):
        problems.append(f"`{module}` is not in the map; regenerate it")
    for module in sorted(seen - expected):
        problems.append(f"`{module}` is in the map but is not a mapped module")
    reach = reaches(found)
    roots = class_roots(found)
    for row in rows:
        if row.module not in expected:
            continue
        if row.status not in STATUSES:
            problems.append(f"`{row.module}` has unknown status {row.status!r}")
            continue
        status, _ = computed_status(row.module, reach)
        if row.status in LIVE_STATUSES:
            if status != row.status:
                problems.append(
                    f"`{row.module}` is mapped {row.status}, but the scan finds {status}"
                )
                continue
            root = entry_root(row.entry)
            if root not in roots[row.status]:
                problems.append(
                    f"`{row.module}` names {root!r}, which is not a {row.status} root"
                )
            elif row.module not in _reaches_from(root, row.status, found):
                problems.append(f"`{row.module}` is not reached from `{root}`")
        elif status != "unreached":
            problems.append(
                f"`{row.module}` is mapped {row.status}, but the scan finds {status}"
            )
    return problems


def render_map(found: Scan, notes: Mapping[str, Tuple[str, str]]) -> str:
    """The map's text, with each kept note and any declared ``retired`` status."""
    reach = reaches(found)
    lines: List[str] = [
        "# Module coverage map",
        "",
        "Where each module's results end up (#1751). Generated by "
        "`python scripts/module_coverage_map.py` from a LibCST import scan and checked by "
        "`tests/lint/test_module_coverage_map.py`. The statuses, the scan's rules and what "
        "it cannot see are defined in `scripts/module_coverage_map.py`. Notes in the last "
        "column are written by hand and kept when the map is regenerated.",
        "",
        "| Status | Meaning |",
        "|---|---|",
        "| `pipeline` | reached from the pipeline run (`analytics.pipeline_v14_enhanced`, "
        "or `run_full_pipeline_v14` outside its emitter steps) |",
        "| `emitter` | reached only through an emitter step of `run_full_pipeline_v14` |",
        "| `report` | reached from the lender report |",
        "| `web` | reached from the web app or the HTTP API |",
        "| `script` | reached only from a script, or run as one (it has a "
        "`__main__` block) |",
        "| `unreached` | no live root reaches it; the reason says which tests, if any, "
        "import it |",
        "| `retired` | declared retired; the scan agrees no live root reaches it |",
        "",
    ]
    counts: Dict[str, int] = {}
    body: List[str] = []
    for module in mapped_modules(found.files):
        status, root = computed_status(module, reach)
        kept_status, note = notes.get(module, ("", ""))
        if status == "unreached" and kept_status == "retired":
            status = "retired"
        if status in LIVE_STATUSES:
            entry = f"`{root}`"
        else:
            entry = unreached_reason(module, found)
        counts[status] = counts.get(status, 0) + 1
        body.append(f"| `{module}` | {status} | {entry} | {note} |")

    lines.append(
        "Counts: "
        + ", ".join(f"{status} {counts.get(status, 0)}" for status in STATUSES)
        + f" (total {sum(counts.values())})."
    )
    lines += ["", "## Modules", "", _HEADER, "|---|---|---|---|", *body, ""]
    lines += [
        "## Dynamic imports the scan cannot follow",
        "",
        "Each file below imports a module whose name is computed at runtime. A module "
        "reached only that way reads as less reached than it is.",
        "",
        "| File | Dynamic imports |",
        "|---|---|",
    ]
    for name, count in dynamic_import_sites(found):
        lines.append(f"| `{found.files[name]}` | {count} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str]) -> int:
    """Rewrite the map from the scan, keeping notes and declared retirements."""
    if len(argv) > 1:
        print("usage: python scripts/module_coverage_map.py", file=sys.stderr)
        return 2
    notes: Dict[str, Tuple[str, str]] = {}
    if MAP_PATH.exists():
        for row in parse_map(MAP_PATH.read_text(encoding="utf-8")):
            notes[row.module] = (row.status, row.note)
    MAP_PATH.write_text(render_map(scan(), notes), encoding="utf-8")
    print(f"wrote {MAP_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
