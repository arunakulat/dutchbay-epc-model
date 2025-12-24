#!/usr/bin/env python3
"""
Dolphin D01: Enhanced GitHub Repository Scanner
Sprint 18 - DutchBay EPC Model

Comprehensive repository analysis generating:
1. File inventory with categorization (Python, config, docs, tests)
2. Structure report with dependency graph
3. Technical debt metrics (TODOs, complexity, deprecated imports)
4. Migration readiness score
5. Refactor risk assessment per module

Enhanced based on local dev feedback:
- Detect circular dependencies
- Flag deprecated imports
- Identify orphaned files
- Calculate refactor risk score

Outputs:
- migration_status_report.md (human-readable)
- repo_structure.json (machine-readable)
- dependency_graph.json (for visualization)
- technical_debt_metrics.json (for tracking)

Usage (Hydra-based, GWTF R3 compliant):
    python scripts/01_github_repo_scanner.py
    python scripts/01_github_repo_scanner.py output_dir=custom_reports/
    python scripts/01_github_repo_scanner.py repo_root=/path/to/repo

Compliance:
- GWTF R3: Uses Hydra (no argparse)
- GWTF CLI-01: Hydra-based CLI
- GWTF ARCH-01: Config-first architecture
"""

import os
import sys
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime

import hydra
from omegaconf import DictConfig, OmegaConf


@dataclass
class FileInfo:
    """Metadata for a single file."""
    path: str
    category: str  # python, config, test, doc, other
    loc: int  # lines of code
    imports: List[str]
    todos: int
    complexity_score: float
    refactor_risk: str  # low, medium, high
    deprecated_imports: List[str]
    last_modified: str


@dataclass
class ModuleDependency:
    """Dependency relationship between modules."""
    source: str
    target: str
    import_type: str  # direct, from, star
    is_circular: bool


@dataclass
class TechnicalDebt:
    """Technical debt metrics."""
    total_todos: int
    total_complexity: float
    deprecated_imports_count: int
    orphaned_files: List[str]
    circular_dependencies: List[Tuple[str, str]]
    high_risk_modules: List[str]


@dataclass
class MigrationReadiness:
    """Migration readiness assessment."""
    overall_score: float  # 0-100
    ready_modules: List[str]
    attention_modules: List[str]
    blocking_modules: List[str]
    recommendations: List[str]


class RepoScanner:
    """Enhanced repository scanner for migration analysis."""
    
    def __init__(self, repo_root: Path, output_dir: Path):
        self.repo_root = repo_root
        self.output_dir = output_dir
        self.files: List[FileInfo] = []
        self.dependencies: List[ModuleDependency] = []
        self.technical_debt: Optional[TechnicalDebt] = None
        self.migration_readiness: Optional[MigrationReadiness] = None
        
        # Patterns for deprecated imports
        self.deprecated_patterns = [
            r'from analytics.engine import',  # Should be analytics.sensitivity.engine
            r'import dutchbay.core',  # Deprecated in favor of dutchbay.orchestrator
            r'from finance.core import',  # Should be finance.cashflow_v14
        ]
        
    def scan(self):
        """Execute full repository scan."""
        print("="*80)
        print("DOLPHIN D01: ENHANCED REPOSITORY SCANNER")
        print("="*80)
        print(f"Repository: {self.repo_root}")
        print(f"Output: {self.output_dir}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Inventory files
        print("\n[1/6] Scanning files...")
        self._scan_files()
        print(f"  ✓ Found {len(self.files)} files")
        
        # Step 2: Analyze dependencies
        print("\n[2/6] Analyzing dependencies...")
        self._analyze_dependencies()
        print(f"  ✓ Found {len(self.dependencies)} dependencies")
        
        # Step 3: Calculate technical debt
        print("\n[3/6] Calculating technical debt...")
        self._calculate_technical_debt()
        print(f"  ✓ TODOs: {self.technical_debt.total_todos}")
        print(f"  ✓ Circular deps: {len(self.technical_debt.circular_dependencies)}")
        print(f"  ✓ Deprecated imports: {self.technical_debt.deprecated_imports_count}")
        
        # Step 4: Assess migration readiness
        print("\n[4/6] Assessing migration readiness...")
        self._assess_migration_readiness()
        print(f"  ✓ Readiness score: {self.migration_readiness.overall_score:.1f}/100")
        print(f"  ✓ Ready modules: {len(self.migration_readiness.ready_modules)}")
        print(f"  ✓ Attention needed: {len(self.migration_readiness.attention_modules)}")
        print(f"  ✓ Blocking issues: {len(self.migration_readiness.blocking_modules)}")
        
        # Step 5: Generate reports
        print("\n[5/6] Generating reports...")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._generate_reports()
        
        # Step 6: Validate outputs
        print("\n[6/6] Validating outputs...")
        self._validate_outputs()
        
        print("\n" + "="*80)
        print("SCAN COMPLETE")
        print("="*80)
    
    def _scan_files(self):
        """Scan all files in repository and categorize."""
        for root, dirs, files in os.walk(self.repo_root):
            # Skip hidden dirs and common ignore patterns
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', '.venv']]
            
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(self.repo_root)
                
                # Categorize file
                category = self._categorize_file(file_path)
                if category is None:
                    continue  # Skip non-relevant files
                
                # Analyze Python files
                if category in ['python', 'test']:
                    info = self._analyze_python_file(file_path, str(relative_path))
                    self.files.append(info)
                else:
                    # Non-Python files (configs, docs)
                    info = FileInfo(
                        path=str(relative_path),
                        category=category,
                        loc=self._count_lines(file_path),
                        imports=[],
                        todos=self._count_todos(file_path),
                        complexity_score=0.0,
                        refactor_risk='low',
                        deprecated_imports=[],
                        last_modified=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    )
                    self.files.append(info)
    
    def _categorize_file(self, file_path: Path) -> Optional[str]:
        """Categorize file by type."""
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        
        if suffix == '.py':
            if 'test_' in name or '_test.py' in name or 'tests/' in str(file_path):
                return 'test'
            return 'python'
        elif suffix in ['.yaml', '.yml', '.json', '.toml', '.ini', '.cfg']:
            return 'config'
        elif suffix in ['.md', '.rst', '.txt']:
            return 'doc'
        elif suffix in ['.csv', '.xlsx']:
            return 'data'
        
        return None  # Skip other files
    
    def _analyze_python_file(self, file_path: Path, relative_path: str) -> FileInfo:
        """Deep analysis of Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content, filename=str(file_path))
            
            # Extract imports
            imports = self._extract_imports(tree)
            
            # Detect deprecated imports
            deprecated = self._detect_deprecated_imports(content)
            
            # Count TODOs
            todos = self._count_todos(file_path)
            
            # Calculate complexity
            complexity = self._calculate_complexity(tree)
            
            # Assess refactor risk
            risk = self._assess_refactor_risk(complexity, len(deprecated), todos)
            
            return FileInfo(
                path=relative_path,
                category='python' if 'test' not in relative_path else 'test',
                loc=len(content.splitlines()),
                imports=imports,
                todos=todos,
                complexity_score=complexity,
                refactor_risk=risk,
                deprecated_imports=deprecated,
                last_modified=datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            )
        
        except Exception as e:
            print(f"  ⚠️  Failed to analyze {relative_path}: {e}")
            return FileInfo(
                path=relative_path,
                category='python',
                loc=0,
                imports=[],
                todos=0,
                complexity_score=0.0,
                refactor_risk='unknown',
                deprecated_imports=[],
                last_modified=''
            )
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract all import statements from AST."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return list(set(imports))  # Deduplicate
    
    def _detect_deprecated_imports(self, content: str) -> List[str]:
        """Detect deprecated import patterns."""
        deprecated = []
        
        for pattern in self.deprecated_patterns:
            matches = re.findall(pattern, content)
            deprecated.extend(matches)
        
        return deprecated
    
    def _count_todos(self, file_path: Path) -> int:
        """Count TODO comments in file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content.count('TODO')
        except:
            return 0
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines in file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return len(f.readlines())
        except:
            return 0
    
    def _calculate_complexity(self, tree: ast.AST) -> float:
        """Calculate cyclomatic complexity score."""
        complexity = 0
        
        for node in ast.walk(tree):
            # Count decision points
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        return complexity
    
    def _assess_refactor_risk(self, complexity: float, deprecated_count: int, todos: int) -> str:
        """Assess refactor risk based on metrics."""
        risk_score = complexity + (deprecated_count * 5) + (todos * 2)
        
        if risk_score < 10:
            return 'low'
        elif risk_score < 30:
            return 'medium'
        else:
            return 'high'
    
    def _analyze_dependencies(self):
        """Build dependency graph between modules."""
        module_map = self._build_module_map()
        
        for file_info in self.files:
            if file_info.category not in ['python', 'test']:
                continue
            
            source_module = self._path_to_module(file_info.path)
            
            for import_name in file_info.imports:
                # Check if import is internal (not external library)
                if self._is_internal_import(import_name, module_map):
                    dep = ModuleDependency(
                        source=source_module,
                        target=import_name,
                        import_type='direct',
                        is_circular=False  # Will be computed later
                    )
                    self.dependencies.append(dep)
        
        # Detect circular dependencies
        self._detect_circular_dependencies()
    
    def _build_module_map(self) -> Set[str]:
        """Build set of all internal modules."""
        modules = set()
        
        for file_info in self.files:
            if file_info.category in ['python', 'test']:
                module = self._path_to_module(file_info.path)
                modules.add(module)
        
        return modules
    
    def _path_to_module(self, file_path: str) -> str:
        """Convert file path to Python module name."""
        # Remove .py extension
        if file_path.endswith('.py'):
            file_path = file_path[:-3]
        
        # Convert path separators to dots
        module = file_path.replace('/', '.').replace('\\', '.')
        
        # Remove __init__
        if module.endswith('.__init__'):
            module = module[:-9]
        
        return module
    
    def _is_internal_import(self, import_name: str, module_map: Set[str]) -> bool:
        """Check if import is internal to this repo."""
        # Check if starts with known internal packages
        internal_packages = ['dutchbay', 'finance', 'analytics', 'wind', 'gis']
        
        for package in internal_packages:
            if import_name.startswith(package):
                return True
        
        # Check if in module map
        return import_name in module_map
    
    def _detect_circular_dependencies(self):
        """Detect circular dependencies using DFS."""
        # Build adjacency list
        graph = defaultdict(list)
        for dep in self.dependencies:
            graph[dep.source].append(dep.target)
        
        # DFS to find cycles
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(tuple(cycle))
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                dfs(node, [node])
        
        # Mark circular dependencies
        for dep in self.dependencies:
            for cycle in cycles:
                if dep.source in cycle and dep.target in cycle:
                    dep.is_circular = True
    
    def _calculate_technical_debt(self):
        """Calculate overall technical debt metrics."""
        total_todos = sum(f.todos for f in self.files)
        total_complexity = sum(f.complexity_score for f in self.files if f.category == 'python')
        deprecated_count = sum(len(f.deprecated_imports) for f in self.files)
        
        # Identify orphaned files (no imports from other modules)
        imported_modules = set(dep.target for dep in self.dependencies)
        all_modules = set(self._path_to_module(f.path) for f in self.files if f.category in ['python', 'test'])
        orphaned = list(all_modules - imported_modules - {'__main__'})
        
        # Get circular dependencies
        circular = [(dep.source, dep.target) for dep in self.dependencies if dep.is_circular]
        
        # High-risk modules
        high_risk = [f.path for f in self.files if f.refactor_risk == 'high']
        
        self.technical_debt = TechnicalDebt(
            total_todos=total_todos,
            total_complexity=total_complexity,
            deprecated_imports_count=deprecated_count,
            orphaned_files=orphaned,
            circular_dependencies=circular,
            high_risk_modules=high_risk
        )
    
    def _assess_migration_readiness(self):
        """Assess overall migration readiness."""
        # Score components (0-100 each)
        todo_score = max(0, 100 - (self.technical_debt.total_todos * 2))  # Penalty: -2 per TODO
        complexity_score = max(0, 100 - (self.technical_debt.total_complexity / 10))
        deprecated_score = max(0, 100 - (self.technical_debt.deprecated_imports_count * 10))
        circular_score = max(0, 100 - (len(self.technical_debt.circular_dependencies) * 20))
        
        # Overall score (weighted average)
        overall = (todo_score * 0.2 + complexity_score * 0.3 + deprecated_score * 0.3 + circular_score * 0.2)
        
        # Categorize modules
        ready = [f.path for f in self.files if f.refactor_risk == 'low' and f.todos == 0]
        attention = [f.path for f in self.files if f.refactor_risk == 'medium' or (f.refactor_risk == 'low' and f.todos > 0)]
        blocking = [f.path for f in self.files if f.refactor_risk == 'high']
        
        # Recommendations
        recommendations = []
        if self.technical_debt.total_todos > 20:
            recommendations.append(f"Resolve TODOs before refactoring (current: {self.technical_debt.total_todos})")
        if self.technical_debt.deprecated_imports_count > 0:
            recommendations.append(f"Update {self.technical_debt.deprecated_imports_count} deprecated imports")
        if len(self.technical_debt.circular_dependencies) > 0:
            recommendations.append(f"Break {len(self.technical_debt.circular_dependencies)} circular dependencies")
        if len(self.technical_debt.high_risk_modules) > 5:
            recommendations.append(f"Refactor {len(self.technical_debt.high_risk_modules)} high-complexity modules")
        
        self.migration_readiness = MigrationReadiness(
            overall_score=overall,
            ready_modules=ready,
            attention_modules=attention,
            blocking_modules=blocking,
            recommendations=recommendations if recommendations else ["Repository is ready for migration"]
        )
    
    def _generate_reports(self):
        """Generate all output reports."""
        # 1. Migration Status Report (Markdown)
        self._generate_markdown_report(self.output_dir / "migration_status_report.md")
        
        # 2. Repository Structure (JSON)
        self._generate_structure_json(self.output_dir / "repo_structure.json")
        
        # 3. Dependency Graph (JSON)
        self._generate_dependency_graph(self.output_dir / "dependency_graph.json")
        
        # 4. Technical Debt Metrics (JSON)
        self._generate_debt_metrics(self.output_dir / "technical_debt_metrics.json")
    
    def _generate_markdown_report(self, output_path: Path):
        """Generate human-readable Markdown report."""
        report = f"""# Migration Status Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Repository: {self.repo_root}

## Executive Summary

**Migration Readiness Score: {self.migration_readiness.overall_score:.1f}/100**

- ✓ Ready Modules: {len(self.migration_readiness.ready_modules)}
- ⚠️ Attention Needed: {len(self.migration_readiness.attention_modules)}
- ✗ Blocking Issues: {len(self.migration_readiness.blocking_modules)}

## Repository Inventory

| Category | Count | LOC |
|----------|-------|-----|
| Python Modules | {len([f for f in self.files if f.category == 'python'])} | {sum(f.loc for f in self.files if f.category == 'python')} |
| Test Files | {len([f for f in self.files if f.category == 'test'])} | {sum(f.loc for f in self.files if f.category == 'test')} |
| Config Files | {len([f for f in self.files if f.category == 'config'])} | {sum(f.loc for f in self.files if f.category == 'config')} |
| Documentation | {len([f for f in self.files if f.category == 'doc'])} | {sum(f.loc for f in self.files if f.category == 'doc')} |

## Technical Debt Analysis

### Critical Issues
- **TODOs**: {self.technical_debt.total_todos} comments requiring resolution
- **Deprecated Imports**: {self.technical_debt.deprecated_imports_count} imports to update
- **Circular Dependencies**: {len(self.technical_debt.circular_dependencies)} cycles detected
- **High-Risk Modules**: {len(self.technical_debt.high_risk_modules)} modules need refactoring

### Circular Dependencies
"""
        if self.technical_debt.circular_dependencies:
            for source, target in self.technical_debt.circular_dependencies[:10]:  # Show top 10
                report += f"- {source} ↔ {target}\n"
        else:
            report += "None detected ✓\n"
        
        report += f"""
### High-Risk Modules (Top 10)
"""
        for module in self.technical_debt.high_risk_modules[:10]:
            report += f"- {module}\n"
        
        report += f"""
## Migration Recommendations

"""
        for i, rec in enumerate(self.migration_readiness.recommendations, 1):
            report += f"{i}. {rec}\n"
        
        report += f"""
## Dependency Summary

- **Total Dependencies**: {len(self.dependencies)}
- **Internal Modules**: {len(set(dep.source for dep in self.dependencies))}
- **Imported Modules**: {len(set(dep.target for dep in self.dependencies))}

## Next Steps

1. Review high-risk modules and create refactor plan
2. Resolve blocking TODOs (orchestrator cashflow logic)
3. Update deprecated imports
4. Break circular dependencies
5. Proceed with Phase 1 (Contract Generation)

---
*Generated by Dolphin D01 (Enhanced Repository Scanner)*
*Compliance: GWTF R3 (Hydra CLI), ARCH-01 (config-first), Sprint 18 Phase 0*
"""
        
        with open(output_path, 'w') as f:
            f.write(report)
        
        print(f"  ✓ Generated: {output_path}")
    
    def _generate_structure_json(self, output_path: Path):
        """Generate machine-readable structure JSON."""
        structure = {
            "scan_timestamp": datetime.now().isoformat(),
            "repository_root": str(self.repo_root),
            "files": [asdict(f) for f in self.files],
            "statistics": {
                "total_files": len(self.files),
                "total_loc": sum(f.loc for f in self.files),
                "python_modules": len([f for f in self.files if f.category == 'python']),
                "test_files": len([f for f in self.files if f.category == 'test']),
                "config_files": len([f for f in self.files if f.category == 'config'])
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(structure, f, indent=2)
        
        print(f"  ✓ Generated: {output_path}")
    
    def _generate_dependency_graph(self, output_path: Path):
        """Generate dependency graph JSON for visualization."""
        graph = {
            "nodes": list(set(
                [dep.source for dep in self.dependencies] + 
                [dep.target for dep in self.dependencies]
            )),
            "edges": [
                {
                    "source": dep.source,
                    "target": dep.target,
                    "type": dep.import_type,
                    "circular": dep.is_circular
                }
                for dep in self.dependencies
            ],
            "statistics": {
                "total_dependencies": len(self.dependencies),
                "circular_count": len([d for d in self.dependencies if d.is_circular])
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(graph, f, indent=2)
        
        print(f"  ✓ Generated: {output_path}")
    
    def _generate_debt_metrics(self, output_path: Path):
        """Generate technical debt metrics JSON."""
        metrics = {
            "scan_timestamp": datetime.now().isoformat(),
            "technical_debt": asdict(self.technical_debt),
            "migration_readiness": asdict(self.migration_readiness),
            "risk_distribution": {
                "low": len([f for f in self.files if f.refactor_risk == 'low']),
                "medium": len([f for f in self.files if f.refactor_risk == 'medium']),
                "high": len([f for f in self.files if f.refactor_risk == 'high'])
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"  ✓ Generated: {output_path}")
    
    def _validate_outputs(self):
        """Validate that all outputs were generated correctly."""
        required_files = [
            "migration_status_report.md",
            "repo_structure.json",
            "dependency_graph.json",
            "technical_debt_metrics.json"
        ]
        
        all_exist = True
        for file_name in required_files:
            file_path = self.output_dir / file_name
            if file_path.exists() and file_path.stat().st_size > 0:
                print(f"  ✓ {file_name}")
            else:
                print(f"  ✗ {file_name} missing or empty")
                all_exist = False
        
        return all_exist


@hydra.main(version_base=None, config_path="../conf", config_name="scanner")
def main(cfg: DictConfig) -> None:
    """Main entry point for Dolphin D01 scanner (Hydra-based).
    
    Args:
        cfg: Hydra configuration from conf/scanner.yaml
        
    Usage:
        python scripts/01_github_repo_scanner.py
        python scripts/01_github_repo_scanner.py output_dir=custom_reports/
        python scripts/01_github_repo_scanner.py repo_root=/path/to/repo
    """
    # Convert config to paths
    repo_root = Path(cfg.repo_root).resolve()
    output_dir = Path(cfg.output_dir)
    
    # Create scanner and run
    scanner = RepoScanner(repo_root, output_dir)
    scanner.scan()
    
    print(f"\n✓ Dolphin D01 execution complete")
    print(f"  Reports available in: {output_dir}")
    print(f"  Next: Review migration_status_report.md")


if __name__ == "__main__":
    main()
