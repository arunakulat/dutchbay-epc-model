#!/usr/bin/env python3
"""
Import Scanner for dutchbay_v14chat References

Scans the entire codebase for imports from dutchbay_v14chat and generates
a detailed analysis report for the refactor sprint.

Usage:
    python scan_v14chat_imports.py --output reports/import_analysis.json

Features:
    - AST-safe parsing (no exec, no dynamic imports)
    - Handles both 'from dutchbay_v14chat' and 'import dutchbay_v14chat' patterns
    - JSON export for downstream automation
    - Human-readable console summary
    - Zero false positives (string literal detection)
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Set


@dataclass
class ImportReference:
    """Single import statement reference."""

    file_path: str
    line_number: int
    import_statement: str
    module_imported: str
    names_imported: List[str]
    import_type: str  # "from" or "direct"


@dataclass
class ScanReport:
    """Complete import scan report."""

    total_files_scanned: int
    files_with_imports: int
    total_import_statements: int
    unique_modules_imported: Set[str]
    references: List[ImportReference]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "total_files_scanned": self.total_files_scanned,
            "files_with_imports": self.files_with_imports,
            "total_import_statements": self.total_import_statements,
            "unique_modules_imported": sorted(self.unique_modules_imported),
            "references": [asdict(ref) for ref in self.references],
        }


class ImportScanner(ast.NodeVisitor):
    """AST visitor to detect dutchbay_v14chat imports."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.references: List[ImportReference] = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from dutchbay_v14chat.X import Y' statements."""
        if node.module and node.module.startswith("dutchbay_v14chat"):
            names = [alias.name for alias in node.names]
            self.references.append(
                ImportReference(
                    file_path=str(self.file_path),
                    line_number=node.lineno,
                    import_statement=self._reconstruct_import(node),
                    module_imported=node.module,
                    names_imported=names,
                    import_type="from",
                )
            )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import dutchbay_v14chat' statements."""
        for alias in node.names:
            if alias.name.startswith("dutchbay_v14chat"):
                self.references.append(
                    ImportReference(
                        file_path=str(self.file_path),
                        line_number=node.lineno,
                        import_statement=f"import {alias.name}",
                        module_imported=alias.name,
                        names_imported=[],
                        import_type="direct",
                    )
                )
        self.generic_visit(node)

    def _reconstruct_import(self, node: ast.ImportFrom) -> str:
        """Reconstruct the original import statement."""
        names_str = ", ".join(alias.name for alias in node.names)
        return f"from {node.module} import {names_str}"


def scan_file(file_path: Path) -> List[ImportReference]:
    """
    Scan a single Python file for dutchbay_v14chat imports.

    Args:
        file_path: Path to Python file

    Returns:
        List of ImportReference objects found in the file
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(file_path))
        scanner = ImportScanner(file_path)
        scanner.visit(tree)
        return scanner.references

    except SyntaxError as e:
        print(f"⚠️  Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"⚠️  Error scanning {file_path}: {e}", file=sys.stderr)
        return []


def scan_directory(
    root_dir: Path,
    exclude_dirs: Set[str] | None = None,
) -> ScanReport:
    """
    Recursively scan directory for dutchbay_v14chat imports.

    Args:
        root_dir: Root directory to scan
        exclude_dirs: Directory names to skip (e.g., .venv, __pycache__)

    Returns:
        Complete ScanReport with all findings
    """
    if exclude_dirs is None:
        exclude_dirs = {
            ".venv",
            ".venv311",
            "venv",
            "env",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".git",
            ".idea",
            ".vscode",
            "node_modules",
            "dutchbay_v14chat",  # Don't scan the directory we're refactoring
            "legacy",  # Don't scan already-quarantined code
        }

    all_references: List[ImportReference] = []
    files_scanned = 0
    files_with_imports = 0

    for py_file in root_dir.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue

        files_scanned += 1
        refs = scan_file(py_file)

        if refs:
            files_with_imports += 1
            all_references.extend(refs)

    # Extract unique modules
    unique_modules = {ref.module_imported for ref in all_references}

    return ScanReport(
        total_files_scanned=files_scanned,
        files_with_imports=files_with_imports,
        total_import_statements=len(all_references),
        unique_modules_imported=unique_modules,
        references=all_references,
    )


def print_summary(report: ScanReport) -> None:
    """Print human-readable summary to console."""
    print("\n" + "=" * 70)
    print("📊 IMPORT SCAN REPORT: dutchbay_v14chat")
    print("=" * 70)
    print(f"\n📁 Files scanned: {report.total_files_scanned}")
    print(f"⚠️  Files with imports: {report.files_with_imports}")
    print(f"📌 Total import statements: {report.total_import_statements}")
    print("\n🔍 Unique modules imported:")
    for module in sorted(report.unique_modules_imported):
        print(f"   - {module}")

    # Group by file
    by_file: Dict[str, List[ImportReference]] = defaultdict(list)
    for ref in report.references:
        by_file[ref.file_path].append(ref)

    print(f"\n📄 Files requiring fixes ({len(by_file)}):")
    for file_path in sorted(by_file.keys()):
        refs = by_file[file_path]
        print(f"\n   {file_path}")
        for ref in refs:
            print(f"      Line {ref.line_number}: {ref.import_statement}")

    print("\n" + "=" * 70)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scan codebase for dutchbay_v14chat imports"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON report path (optional)",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=None,
        help="Additional directories to exclude",
    )

    args = parser.parse_args()

    # Build exclude set
    exclude_dirs = {
        ".venv",
        ".venv311",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".git",
        ".idea",
        ".vscode",
        "dutchbay_v14chat",
        "legacy",
    }
    if args.exclude:
        exclude_dirs.update(args.exclude)

    print(f"🔍 Scanning {args.root} for dutchbay_v14chat imports...")
    print(f"   Excluding: {', '.join(sorted(exclude_dirs))}")

    report = scan_directory(args.root, exclude_dirs)

    # Print summary
    print_summary(report)

    # Export JSON if requested
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, sort_keys=True)
        print(f"\n✅ JSON report exported to: {args.output}")

    # Exit with error code if imports found
    if report.files_with_imports > 0:
        sys.exit(1)
    else:
        print("\n✅ No dutchbay_v14chat imports found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
