#!/usr/bin/env python3
"""Dolphin D01 repository scanner.

Generates repository inventory, dependency graph, technical debt metrics, and
migration-readiness reports. Uses Hydra configuration from ``conf/scanner.yaml``.
"""

from __future__ import annotations

import ast
import json
import os
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import hydra
from omegaconf import DictConfig


@dataclass
class FileInfo:
    path: str
    category: str
    loc: int
    imports: list[str]
    todos: int
    complexity_score: float
    refactor_risk: str
    deprecated_imports: list[str]
    last_modified: str


@dataclass
class ModuleDependency:
    source: str
    target: str
    import_type: str
    is_circular: bool


@dataclass
class TechnicalDebt:
    total_todos: int
    total_complexity: float
    deprecated_imports_count: int
    orphaned_files: list[str]
    circular_dependencies: list[tuple[str, str]]
    high_risk_modules: list[str]


@dataclass
class MigrationReadiness:
    overall_score: float
    ready_modules: list[str]
    attention_modules: list[str]
    blocking_modules: list[str]
    recommendations: list[str]


class RepoScanner:
    """Enhanced repository scanner for migration analysis."""

    def __init__(self, repo_root: Path, output_dir: Path) -> None:
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.files: list[FileInfo] = []
        self.dependencies: list[ModuleDependency] = []
        self.technical_debt: Optional[TechnicalDebt] = None
        self.migration_readiness: Optional[MigrationReadiness] = None
        self.deprecated_patterns = [
            r"from analytics.engine import",
            r"import dutchbay.core",
            r"from finance.core import",
        ]

    def scan(self) -> None:
        print("=" * 80)
        print("DOLPHIN D01: ENHANCED REPOSITORY SCANNER")
        print("=" * 80)
        print(f"Repository: {self.repo_root}")
        print(f"Output: {self.output_dir}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n[1/6] Scanning files...")
        self._scan_files()
        print(f"  Found {len(self.files)} files")

        print("\n[2/6] Analyzing dependencies...")
        self._analyze_dependencies()
        print(f"  Found {len(self.dependencies)} dependencies")

        print("\n[3/6] Calculating technical debt...")
        self._calculate_technical_debt()
        assert self.technical_debt is not None
        print(f"  TODOs: {self.technical_debt.total_todos}")
        print(f"  Circular deps: {len(self.technical_debt.circular_dependencies)}")
        print(f"  Deprecated imports: {self.technical_debt.deprecated_imports_count}")

        print("\n[4/6] Assessing migration readiness...")
        self._assess_migration_readiness()
        assert self.migration_readiness is not None
        print(f"  Readiness score: {self.migration_readiness.overall_score:.1f}/100")

        print("\n[5/6] Generating reports...")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._generate_reports()

        print("\n[6/6] Validating outputs...")
        self._validate_outputs()
        print("\nSCAN COMPLETE")

    def _scan_files(self) -> None:
        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in {"__pycache__", "node_modules", "venv", ".venv"}
            ]
            for file_name in files:
                file_path = Path(root) / file_name
                relative_path = file_path.relative_to(self.repo_root)
                category = self._categorize_file(file_path)
                if category is None:
                    continue
                if category in {"python", "test"}:
                    self.files.append(
                        self._analyze_python_file(file_path, str(relative_path))
                    )
                else:
                    self.files.append(
                        FileInfo(
                            path=str(relative_path),
                            category=category,
                            loc=self._count_lines(file_path),
                            imports=[],
                            todos=self._count_todos(file_path),
                            complexity_score=0.0,
                            refactor_risk="low",
                            deprecated_imports=[],
                            last_modified=datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ).isoformat(),
                        )
                    )

    def _categorize_file(self, file_path: Path) -> Optional[str]:
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        path_text = str(file_path)
        if suffix == ".py":
            if "test_" in name or "_test.py" in name or "tests/" in path_text:
                return "test"
            return "python"
        if suffix in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}:
            return "config"
        if suffix in {".md", ".rst", ".txt"}:
            return "doc"
        if suffix in {".csv", ".xlsx"}:
            return "data"
        return None

    def _analyze_python_file(self, file_path: Path, relative_path: str) -> FileInfo:
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            imports = self._extract_imports(tree)
            deprecated = self._detect_deprecated_imports(content)
            todos = self._count_todos(file_path)
            complexity = self._calculate_complexity(tree)
            risk = self._assess_refactor_risk(complexity, len(deprecated), todos)
            return FileInfo(
                path=relative_path,
                category="python" if "test" not in relative_path else "test",
                loc=len(content.splitlines()),
                imports=imports,
                todos=todos,
                complexity_score=complexity,
                refactor_risk=risk,
                deprecated_imports=deprecated,
                last_modified=datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
            )
        except Exception as exc:
            print(f"  Failed to analyze {relative_path}: {exc}")
            return FileInfo(relative_path, "python", 0, [], 0, 0.0, "unknown", [], "")

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return sorted(set(imports))

    def _detect_deprecated_imports(self, content: str) -> list[str]:
        deprecated: list[str] = []
        for pattern in self.deprecated_patterns:
            deprecated.extend(re.findall(pattern, content))
        return deprecated

    def _count_todos(self, file_path: Path) -> int:
        try:
            return file_path.read_text(encoding="utf-8").count("TODO")
        except Exception:
            return 0

    def _count_lines(self, file_path: Path) -> int:
        try:
            return len(file_path.read_text(encoding="utf-8").splitlines())
        except Exception:
            return 0

    def _calculate_complexity(self, tree: ast.AST) -> float:
        complexity = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        return float(complexity)

    def _assess_refactor_risk(
        self, complexity: float, deprecated_count: int, todos: int
    ) -> str:
        risk_score = complexity + (deprecated_count * 5) + (todos * 2)
        if risk_score < 10:
            return "low"
        if risk_score < 30:
            return "medium"
        return "high"

    def _analyze_dependencies(self) -> None:
        module_map = self._build_module_map()
        for file_info in self.files:
            if file_info.category not in {"python", "test"}:
                continue
            source_module = self._path_to_module(file_info.path)
            for import_name in file_info.imports:
                if self._is_internal_import(import_name, module_map):
                    self.dependencies.append(
                        ModuleDependency(source_module, import_name, "direct", False)
                    )
        self._detect_circular_dependencies()

    def _build_module_map(self) -> set[str]:
        return {
            self._path_to_module(f.path)
            for f in self.files
            if f.category in {"python", "test"}
        }

    def _path_to_module(self, file_path: str) -> str:
        if file_path.endswith(".py"):
            file_path = file_path[:-3]
        module = file_path.replace("/", ".").replace("\\", ".")
        if module.endswith(".__init__"):
            module = module[:-9]
        return module

    def _is_internal_import(self, import_name: str, module_map: set[str]) -> bool:
        return import_name in module_map or import_name.split(".", 1)[0] in {
            "dutchbay",
            "finance",
            "analytics",
            "wind",
            "gis",
        }

    def _detect_circular_dependencies(self) -> None:
        graph: dict[str, list[str]] = defaultdict(list)
        for dep in self.dependencies:
            graph[dep.source].append(dep.target)
        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[tuple[str, ...]] = []

        def dfs(node: str, path: list[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
                elif neighbor in rec_stack and neighbor in path:
                    cycle_start = path.index(neighbor)
                    cycles.append(tuple(path[cycle_start:] + [neighbor]))
            rec_stack.discard(node)

        for node in list(graph):
            if node not in visited:
                dfs(node, [node])
        for dep in self.dependencies:
            dep.is_circular = any(
                dep.source in cycle and dep.target in cycle for cycle in cycles
            )

    def _calculate_technical_debt(self) -> None:
        total_todos = sum(f.todos for f in self.files)
        total_complexity = sum(
            f.complexity_score for f in self.files if f.category == "python"
        )
        deprecated_count = sum(len(f.deprecated_imports) for f in self.files)
        imported_modules = {dep.target for dep in self.dependencies}
        all_modules = {
            self._path_to_module(f.path)
            for f in self.files
            if f.category in {"python", "test"}
        }
        self.technical_debt = TechnicalDebt(
            total_todos=total_todos,
            total_complexity=total_complexity,
            deprecated_imports_count=deprecated_count,
            orphaned_files=sorted(all_modules - imported_modules - {"__main__"}),
            circular_dependencies=[
                (dep.source, dep.target) for dep in self.dependencies if dep.is_circular
            ],
            high_risk_modules=[f.path for f in self.files if f.refactor_risk == "high"],
        )

    def _assess_migration_readiness(self) -> None:
        assert self.technical_debt is not None
        todo_score = max(0.0, 100.0 - (self.technical_debt.total_todos * 2))
        complexity_score = max(0.0, 100.0 - (self.technical_debt.total_complexity / 10))
        deprecated_score = max(
            0.0, 100.0 - (self.technical_debt.deprecated_imports_count * 10)
        )
        circular_score = max(
            0.0, 100.0 - (len(self.technical_debt.circular_dependencies) * 20)
        )
        overall = (
            todo_score * 0.2
            + complexity_score * 0.3
            + deprecated_score * 0.3
            + circular_score * 0.2
        )
        recommendations = []
        if self.technical_debt.total_todos > 20:
            recommendations.append(
                f"Resolve TODOs before refactoring: {self.technical_debt.total_todos}"
            )
        if self.technical_debt.deprecated_imports_count:
            recommendations.append(
                f"Update deprecated imports: {self.technical_debt.deprecated_imports_count}"
            )
        if self.technical_debt.circular_dependencies:
            recommendations.append(
                f"Break circular dependencies: {len(self.technical_debt.circular_dependencies)}"
            )
        if len(self.technical_debt.high_risk_modules) > 5:
            recommendations.append(
                f"Refactor high-complexity modules: {len(self.technical_debt.high_risk_modules)}"
            )
        self.migration_readiness = MigrationReadiness(
            overall_score=overall,
            ready_modules=[
                f.path for f in self.files if f.refactor_risk == "low" and f.todos == 0
            ],
            attention_modules=[
                f.path
                for f in self.files
                if f.refactor_risk == "medium"
                or (f.refactor_risk == "low" and f.todos > 0)
            ],
            blocking_modules=[f.path for f in self.files if f.refactor_risk == "high"],
            recommendations=recommendations or ["Repository is ready for migration"],
        )

    def _generate_reports(self) -> None:
        self._generate_markdown_report(self.output_dir / "migration_status_report.md")
        self._generate_structure_json(self.output_dir / "repo_structure.json")
        self._generate_dependency_graph(self.output_dir / "dependency_graph.json")
        self._generate_debt_metrics(self.output_dir / "technical_debt_metrics.json")

    def _generate_markdown_report(self, output_path: Path) -> None:
        assert self.technical_debt is not None
        assert self.migration_readiness is not None
        report = f"""# Migration Status Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Repository: {self.repo_root}

## Executive Summary

**Migration Readiness Score: {self.migration_readiness.overall_score:.1f}/100**

- Ready Modules: {len(self.migration_readiness.ready_modules)}
- Attention Needed: {len(self.migration_readiness.attention_modules)}
- Blocking Issues: {len(self.migration_readiness.blocking_modules)}

## Repository Inventory

| Category | Count | LOC |
|----------|-------|-----|
| Python Modules | {len([f for f in self.files if f.category == 'python'])} | {sum(f.loc for f in self.files if f.category == 'python')} |
| Test Files | {len([f for f in self.files if f.category == 'test'])} | {sum(f.loc for f in self.files if f.category == 'test')} |
| Config Files | {len([f for f in self.files if f.category == 'config'])} | {sum(f.loc for f in self.files if f.category == 'config')} |
| Documentation | {len([f for f in self.files if f.category == 'doc'])} | {sum(f.loc for f in self.files if f.category == 'doc')} |

## Technical Debt Analysis

- TODOs: {self.technical_debt.total_todos}
- Deprecated Imports: {self.technical_debt.deprecated_imports_count}
- Circular Dependencies: {len(self.technical_debt.circular_dependencies)}
- High-Risk Modules: {len(self.technical_debt.high_risk_modules)}

## Migration Recommendations

"""
        for index, recommendation in enumerate(
            self.migration_readiness.recommendations, 1
        ):
            report += f"{index}. {recommendation}\n"
        report += "\n---\nGenerated by Dolphin D01.\n"
        output_path.write_text(report, encoding="utf-8")
        print(f"  Generated: {output_path}")

    def _generate_structure_json(self, output_path: Path) -> None:
        payload = {
            "scan_timestamp": datetime.now().isoformat(),
            "repository_root": str(self.repo_root),
            "files": [asdict(f) for f in self.files],
            "statistics": {
                "total_files": len(self.files),
                "total_loc": sum(f.loc for f in self.files),
                "python_modules": len(
                    [f for f in self.files if f.category == "python"]
                ),
                "test_files": len([f for f in self.files if f.category == "test"]),
                "config_files": len([f for f in self.files if f.category == "config"]),
            },
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  Generated: {output_path}")

    def _generate_dependency_graph(self, output_path: Path) -> None:
        payload = {
            "nodes": sorted(
                {dep.source for dep in self.dependencies}
                | {dep.target for dep in self.dependencies}
            ),
            "edges": [asdict(dep) for dep in self.dependencies],
            "statistics": {
                "total_dependencies": len(self.dependencies),
                "circular_count": len(
                    [dep for dep in self.dependencies if dep.is_circular]
                ),
            },
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  Generated: {output_path}")

    def _generate_debt_metrics(self, output_path: Path) -> None:
        assert self.technical_debt is not None
        assert self.migration_readiness is not None
        payload = {
            "scan_timestamp": datetime.now().isoformat(),
            "technical_debt": asdict(self.technical_debt),
            "migration_readiness": asdict(self.migration_readiness),
            "risk_distribution": {
                "low": len([f for f in self.files if f.refactor_risk == "low"]),
                "medium": len([f for f in self.files if f.refactor_risk == "medium"]),
                "high": len([f for f in self.files if f.refactor_risk == "high"]),
            },
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  Generated: {output_path}")

    def _validate_outputs(self) -> bool:
        required_files = [
            "migration_status_report.md",
            "repo_structure.json",
            "dependency_graph.json",
            "technical_debt_metrics.json",
        ]
        all_exist = True
        for file_name in required_files:
            file_path = self.output_dir / file_name
            ok = file_path.exists() and file_path.stat().st_size > 0
            print(f"  {'OK' if ok else 'MISSING'} {file_name}")
            all_exist = all_exist and ok
        return all_exist


@hydra.main(version_base=None, config_path="../conf", config_name="scanner")
def main(cfg: DictConfig) -> None:
    repo_root = Path(cfg.repo_root).resolve()
    output_dir = Path(cfg.output_dir)
    scanner = RepoScanner(repo_root, output_dir)
    scanner.scan()
    print("\nDolphin D01 execution complete")
    print(f"Reports available in: {output_dir}")


if __name__ == "__main__":
    main()
