"""LibCST boundary guard: live entrypoints must never import orphaned AEP analytics.

Issue #1551 (AEP analytics cluster boundary freeze & deprecation — Phase 0).

Boundary rule
-------------
No production entrypoint, live pipeline, finance engine, or web/API service may
import any module from the orphaned parallel AEP analytics cluster:
  - ``analytics.wind.aep_summary_builder``
  - ``analytics.wind.pipeline_aep_v14``
  - ``analytics.wind.mc_aep_weibull``
  - ``analytics.wind.aep_tornado``
  - ``analytics.wind.wind_interface_schema``
  - ``analytics.wind.era5_interface_schema``
  - ``analytics.simulation.monte_carlo_aep``

The canonical wind AEP engine feeding finance is ``wind_resource/`` via the
frozen-export contract (``wind_resource/cashflow_adapter.py``). The orphaned
cluster sits parallel to it, executed only in its own tests and legacy off-path scripts.
This guard enforces the Phase 0 boundary freeze so no live path ever newly couples to it.

Protected surfaces
------------------
1. Top-level CLIs & runners (ZERO exceptions):
   - ``run_full_pipeline_v14.py``
   - ``run_scenario_analytics_v14.py``
   - ``scripts/run_wind_analysis_v14.py``
2. Production packages:
   - ``finance/`` (all modules — ZERO exceptions)
   - ``api/`` (all modules — ZERO exceptions)
   - ``wind_resource/`` (all modules — frozen to pre-existing allowlist)
   - ``app/`` (all modules — frozen to pre-existing allowlist)
3. Production evaluation & loader core (ZERO exceptions):
   - ``analytics/evaluation_v14.py``
   - ``analytics/pipeline_v14_enhanced.py``
   - ``analytics/scenario_loader.py``
   - ``analytics/aep_provenance.py``

Run:
    pytest tests/lint/test_aep_analytics_cluster_boundary.py -v

GWTF / CCCDIR:
    - CCCDIR: One canonical wind AEP producer (``wind_resource/``).
    - CST-01: LibCST static inspection (no runtime import of target modules).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import libcst as cst

REPO_ROOT = Path(__file__).resolve().parents[2]

ORPHANED_CLUSTER_MODULES: frozenset[str] = frozenset(
    {
        "analytics.wind.aep_summary_builder",
        "analytics.wind.pipeline_aep_v14",
        "analytics.wind.mc_aep_weibull",
        "analytics.wind.aep_tornado",
        "analytics.wind.wind_interface_schema",
        "analytics.wind.era5_interface_schema",
        "analytics.simulation.monte_carlo_aep",
    }
)

PROTECTED_TOP_LEVEL_FILES: frozenset[str] = frozenset(
    {
        "run_full_pipeline_v14.py",
        "run_scenario_analytics_v14.py",
        "scripts/run_wind_analysis_v14.py",
        "analytics/evaluation_v14.py",
        "analytics/pipeline_v14_enhanced.py",
        "analytics/scenario_loader.py",
        "analytics/aep_provenance.py",
    }
)

PROTECTED_PACKAGE_DIRS: Tuple[str, ...] = (
    "finance",
    "wind_resource",
    "api",
    "app",
)

#: Pre-existing legacy callers recorded in Issue #1551 Phase 0 audit.
#: These will be eliminated in Phase 1 by extracting pure utilities
#: into wind_resource/ or a shared utility package. No new entries may be added.
PHASE_0_LEGACY_ALLOWLIST: Dict[str, frozenset[str]] = {
    "wind_resource/arco_assessment.py": frozenset(
        {"analytics.wind.aep_summary_builder"}
    ),
    "wind_resource/crossval.py": frozenset({"analytics.wind.aep_summary_builder"}),
    "app/reports/report_model.py": frozenset({"analytics.wind.aep_summary_builder"}),
}


def _dotted(node: Optional[cst.BaseExpression]) -> str:
    """Return the dotted name of an import target or attribute chain, or ''."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr.value}" if head else ""
    return ""


def _is_orphaned_module(name: str) -> bool:
    """Return True if name matches an orphaned AEP cluster module or submodule."""
    return name in ORPHANED_CLUSTER_MODULES or any(
        name.startswith(f"{mod}.") for mod in ORPHANED_CLUSTER_MODULES
    )


def _package_of(rel: str) -> List[str]:
    """The dotted package a repo-relative module path belongs to, as parts."""
    return rel.split("/")[:-1]


class _AEPClusterImportCollector(cst.CSTVisitor):
    """Collect any import of the orphaned AEP cluster."""

    def __init__(self, package_parts: Sequence[str]) -> None:
        self.package_parts = list(package_parts)
        self.orphaned_imports: List[str] = []
        self.imported_modules: Set[str] = set()
        self._import_depth = 0

    def leave_Import(self, original_node: cst.Import) -> None:
        self._import_depth -= 1

    def leave_ImportFrom(self, original_node: cst.ImportFrom) -> None:
        self._import_depth -= 1

    def _resolve_relative(self, node: cst.ImportFrom) -> str:
        module = _dotted(node.module)
        level = len(node.relative)
        if not level:
            return module
        base = self.package_parts[: len(self.package_parts) - (level - 1)]
        return ".".join([*base, module] if module else base)

    def visit_Import(self, node: cst.Import) -> None:
        self._import_depth += 1
        for alias in node.names:
            name = _dotted(alias.name)
            if _is_orphaned_module(name):
                self.orphaned_imports.append(f"import {name}")
                self.imported_modules.add(name)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        self._import_depth += 1
        module = self._resolve_relative(node)
        if _is_orphaned_module(module):
            self.orphaned_imports.append(f"from {module} import ...")
            self.imported_modules.add(module)
            return
        if not isinstance(node.names, cst.ImportStar):
            for alias in node.names:
                full = (
                    f"{module}.{_dotted(alias.name)}" if module else _dotted(alias.name)
                )
                if _is_orphaned_module(full):
                    self.orphaned_imports.append(
                        f"from {module or '.'} import {_dotted(alias.name)}"
                    )
                    self.imported_modules.add(full)

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        """Detect direct attribute chains like analytics.wind.aep_summary_builder.X."""
        name = _dotted(node)
        if self._import_depth == 0 and _is_orphaned_module(name):
            self.orphaned_imports.append(f"{name} (attribute)")
            self.imported_modules.add(name)
            return False
        return True


def _collect(source: str, rel: str) -> Tuple[List[str], Set[str]]:
    collector = _AEPClusterImportCollector(_package_of(rel))
    cst.parse_module(source).visit(collector)
    return collector.orphaned_imports, collector.imported_modules


def _scan_protected_surfaces() -> Tuple[int, List[Tuple[str, List[str]]]]:
    """Scan all protected live surfaces for any forbidden imports."""
    scanned = 0
    violations: List[Tuple[str, List[str]]] = []

    # 1. Protected top-level files
    for rel_path in sorted(PROTECTED_TOP_LEVEL_FILES):
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            continue
        try:
            hits, mods = _collect(full_path.read_text(encoding="utf-8"), rel_path)
            scanned += 1
            allowed = PHASE_0_LEGACY_ALLOWLIST.get(rel_path, frozenset())
            unauthorized = mods - allowed
            if unauthorized:
                violations.append((rel_path, hits))
        except (UnicodeDecodeError, cst.ParserSyntaxError):
            continue

    # 2. Protected package trees
    for pkg_dir in PROTECTED_PACKAGE_DIRS:
        pkg_root = REPO_ROOT / pkg_dir
        if not pkg_root.exists():
            continue
        for path in sorted(pkg_root.rglob("*.py")):
            rel_parts = path.relative_to(REPO_ROOT).parts
            if any(p.startswith(".") or p == "__pycache__" for p in rel_parts):
                continue
            rel = "/".join(rel_parts)
            try:
                hits, mods = _collect(path.read_text(encoding="utf-8"), rel)
                scanned += 1
                allowed = PHASE_0_LEGACY_ALLOWLIST.get(rel, frozenset())
                unauthorized = mods - allowed
                if unauthorized:
                    violations.append((rel, hits))
            except (UnicodeDecodeError, cst.ParserSyntaxError):
                continue

    return scanned, violations


def test_collector_flags_every_orphaned_import_spelling() -> None:
    """Negative control: all import syntax forms targeting the orphaned cluster are caught."""
    source = (
        "import analytics.wind.aep_summary_builder\n"
        "from analytics.wind import pipeline_aep_v14\n"
        "from analytics.wind.mc_aep_weibull import run_mc_weibull\n"
        "import analytics.simulation.monte_carlo_aep as mc_aep\n"
        "from analytics.wind.aep_tornado import build_tornado\n"
        "from analytics.wind.wind_interface_schema import WindInterfaceSchema\n"
        "from analytics.wind.era5_interface_schema import Era5InterfaceSchema\n"
        "def func():\n"
        "    from analytics.wind.pipeline_aep_v14 import run_aep_pipeline\n"
        "import wind_resource.bankable_aep\n"  # Allowed canonical producer
        "from analytics.wind.losses_model import DEFAULT_WIND_LOSSES\n"  # Allowed shared loss taxonomy
    )
    hits, mods = _collect(source, "finance/cashflow_v14.py")
    assert "import analytics.wind.aep_summary_builder" in hits
    assert "from analytics.wind import pipeline_aep_v14" in hits
    assert "from analytics.wind.mc_aep_weibull import ..." in hits
    assert "import analytics.simulation.monte_carlo_aep" in hits
    assert "from analytics.wind.aep_tornado import ..." in hits
    assert "from analytics.wind.wind_interface_schema import ..." in hits
    assert "from analytics.wind.era5_interface_schema import ..." in hits
    assert "from analytics.wind.pipeline_aep_v14 import ..." in hits
    # Ensure allowed modules are NOT flagged
    assert not any("losses_model" in h for h in hits)
    assert not any("bankable_aep" in h for h in hits)


def test_collector_flags_relative_imports() -> None:
    """Negative control: relative imports from within analytics/ are caught."""
    source = (
        "from .wind.aep_summary_builder import build_summary\n"
        "from .simulation.monte_carlo_aep import run_monte_carlo_aep\n"
    )
    hits, mods = _collect(source, "analytics/evaluation_v14.py")
    assert "from analytics.wind.aep_summary_builder import ..." in hits
    assert "from analytics.simulation.monte_carlo_aep import ..." in hits


def test_protected_live_surfaces_never_import_orphaned_aep_cluster() -> None:
    """Production entrypoints, finance, wind_resource, and API/app must never import orphaned AEP."""
    scanned, violations = _scan_protected_surfaces()
    assert scanned >= 40, f"scanned only {scanned} modules; check surface paths"
    assert not violations, (
        "Live production surfaces must not import from the orphaned AEP analytics cluster "
        f"({sorted(ORPHANED_CLUSTER_MODULES)}). Use canonical 'wind_resource/' instead:\n"
        + "\n".join(f"  {rel}: {', '.join(hits)}" for rel, hits in violations)
    )


def test_legacy_allowlist_is_minimal() -> None:
    """Phase 0 allowlist is locked to exactly the 3 known pre-existing legacy sites."""
    assert len(PHASE_0_LEGACY_ALLOWLIST) == 3
    assert set(PHASE_0_LEGACY_ALLOWLIST) == {
        "wind_resource/arco_assessment.py",
        "wind_resource/crossval.py",
        "app/reports/report_model.py",
    }
    for allowed_mods in PHASE_0_LEGACY_ALLOWLIST.values():
        assert allowed_mods == frozenset({"analytics.wind.aep_summary_builder"})
