#!/usr/bin/env python3
"""
dutchbay_cleanup_analyzer.py

Pre-cleanup analysis script for DutchBay repo.
Scans and generates a detailed inventory of files to be cleaned up.

USAGE:
    python dutchbay_cleanup_analyzer.py [--output report.json]

OUTPUT:
    - JSON report with detailed file inventory
    - Grouped by category (scripts, docs, tests, scenarios)
    - Shows file paths, sizes, and archival recommendations
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class CleanupAnalyzer:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "repo_root": str(repo_root),
            "categories": {
                "duplicate_scripts": [],
                "duplicate_docs": [],
                "duplicate_tests": [],
                "old_scenarios": [],
            },
            "summary": {},
        }

    def scan_duplicate_scripts(self) -> None:
        """Scan for duplicate/experimental scripts."""
        category = "duplicate_scripts"

        # Assorted docs/scripts directory
        assorted_scripts = self.repo_root / "Assorted docs" / "scripts"
        if assorted_scripts.exists():
            count = len(list(assorted_scripts.glob("*.py")))
            size_kb = sum(f.stat().st_size for f in assorted_scripts.glob("*")) / 1024
            self.report["categories"][category].append(
                {
                    "path": "Assorted docs/scripts/",
                    "type": "directory",
                    "file_count": count,
                    "size_kb": round(size_kb, 2),
                    "reason": "DUPLICATES - Multiple versions of cashflow_v14, evaluation_v14, etc.",
                    "action": "Archive entire directory",
                }
            )

        # Experimental scripts in scripts/ root
        experimental = [
            "scripts/apply_debt_fix.py",
            "scripts/check_datalake_epc.py",
            "scripts/make_clean_zip.py",
            "scripts/test_mc_config_path.py",
        ]
        for script in experimental:
            script_path = self.repo_root / script
            if script_path.exists():
                size_kb = script_path.stat().st_size / 1024
                self.report["categories"][category].append(
                    {
                        "path": script,
                        "type": "file",
                        "size_kb": round(size_kb, 2),
                        "reason": "EXPERIMENTAL - One-off debugging utility",
                        "action": "Archive",
                    }
                )

    def scan_duplicate_tests(self) -> None:
        """Scan for duplicate/experimental test files."""
        category = "duplicate_tests"
        tests_root = self.repo_root / "tests"

        if not tests_root.exists():
            return

        # Find duplicate test files (e.g., "test_file (1).py")
        for test_file in tests_root.rglob("*"):
            if test_file.is_file() and " (" in test_file.name:
                size_kb = test_file.stat().st_size / 1024
                self.report["categories"][category].append(
                    {
                        "path": str(test_file.relative_to(self.repo_root)),
                        "type": "file",
                        "size_kb": round(size_kb, 2),
                        "reason": "DUPLICATE - Old version with (N) suffix",
                        "action": "Archive",
                    }
                )

        # Find _old.py and _beta.py files
        for test_file in tests_root.rglob("*_old.py"):
            size_kb = test_file.stat().st_size / 1024
            self.report["categories"][category].append(
                {
                    "path": str(test_file.relative_to(self.repo_root)),
                    "type": "file",
                    "size_kb": round(size_kb, 2),
                    "reason": "LEGACY - Old version",
                    "action": "Archive",
                }
            )

        for test_file in tests_root.rglob("*_beta.py"):
            size_kb = test_file.stat().st_size / 1024
            self.report["categories"][category].append(
                {
                    "path": str(test_file.relative_to(self.repo_root)),
                    "type": "file",
                    "size_kb": round(size_kb, 2),
                    "reason": "EXPERIMENTAL - Beta version",
                    "action": "Archive",
                }
            )

        # Experimental test scripts in scripts/tests/
        experimental_tests = [
            "scripts/tests/test_irr_quick.py",
            "scripts/tests/test_returns_module.py",
            "scripts/tests/test_fx_dual_regime_standalone_fixed.py",
        ]
        for test in experimental_tests:
            test_path = self.repo_root / test
            if test_path.exists():
                size_kb = test_path.stat().st_size / 1024
                self.report["categories"][category].append(
                    {
                        "path": test,
                        "type": "file",
                        "size_kb": round(size_kb, 2),
                        "reason": "EXPERIMENTAL - One-off test utility",
                        "action": "Archive",
                    }
                )

    def scan_duplicate_docs(self) -> None:
        """Scan for duplicate/draft documentation files."""
        category = "duplicate_docs"

        # Assorted docs/docs directory
        assorted_docs = self.repo_root / "Assorted docs" / "docs"
        if assorted_docs.exists():
            count = len(list(assorted_docs.glob("*")))
            size_kb = sum(f.stat().st_size for f in assorted_docs.glob("*")) / 1024
            self.report["categories"][category].append(
                {
                    "path": "Assorted docs/docs/",
                    "type": "directory",
                    "file_count": count,
                    "size_kb": round(size_kb, 2),
                    "reason": "DUPLICATES - Draft/experimental docs, multiple copies",
                    "action": "Archive entire directory",
                }
            )

        # Old docs in docs/ directory
        docs_root = self.repo_root / "docs"
        old_docs = [
            "Cashflow_v14.py refactoring notes.md",
            "executive_workbook_readme.md",
            "keystroke on mac os x to reveal hidden files.mhtml",
            "schema.md",
        ]
        for doc in old_docs:
            doc_path = docs_root / doc
            if doc_path.exists():
                size_kb = doc_path.stat().st_size / 1024
                self.report["categories"][category].append(
                    {
                        "path": f"docs/{doc}",
                        "type": "file",
                        "size_kb": round(size_kb, 2),
                        "reason": "LEGACY - Old/unrelated documentation",
                        "action": "Archive",
                    }
                )

    def scan_old_scenarios(self) -> None:
        """Scan for old/experimental scenario configurations."""
        category = "old_scenarios"
        scenarios_root = self.repo_root / "scenarios"

        if not scenarios_root.exists():
            return

        old_scenarios = [
            "dutchbay_lendercase_2025Q3.yaml",
            "example_old.yaml",
        ]
        for scenario in old_scenarios:
            scenario_path = scenarios_root / scenario
            if scenario_path.exists():
                size_kb = scenario_path.stat().st_size / 1024
                self.report["categories"][category].append(
                    {
                        "path": f"scenarios/{scenario}",
                        "type": "file",
                        "size_kb": round(size_kb, 2),
                        "reason": "OLD - Previous quarter or legacy example",
                        "action": "Archive",
                    }
                )

        # Find edge_*.yaml files
        for scenario_file in scenarios_root.glob("edge_*.yaml"):
            size_kb = scenario_file.stat().st_size / 1024
            self.report["categories"][category].append(
                {
                    "path": f"scenarios/{scenario_file.name}",
                    "type": "file",
                    "size_kb": round(size_kb, 2),
                    "reason": "EXPERIMENTAL - Edge case scenario",
                    "action": "Archive",
                }
            )

    def generate_summary(self) -> None:
        """Generate summary statistics."""
        total_files = sum(len(items) for items in self.report["categories"].values())
        total_size_kb = sum(
            item.get("size_kb", 0) + item.get("file_count", 0) * 0.5
            for items in self.report["categories"].values()
            for item in items
        )

        self.report["summary"] = {
            "total_items": total_files,
            "total_size_mb": round(total_size_kb / 1024, 2),
            "by_category": {
                category: {
                    "count": len(items),
                    "size_mb": round(
                        sum(item.get("size_kb", 0) for item in items) / 1024, 2
                    ),
                }
                for category, items in self.report["categories"].items()
            },
        }

    def print_console_report(self) -> None:
        """Print human-readable report to console."""
        print("\n" + "=" * 80)
        print("DutchBay Repository Cleanup Analysis")
        print("=" * 80)
        print(f"Generated: {self.report['timestamp']}")
        print(f"Repository: {self.report['repo_root']}")
        print()

        summary = self.report["summary"]
        print("SUMMARY")
        print("─" * 80)
        print(f"Total items to archive: {summary['total_items']}")
        print(f"Total space to reclaim: {summary['total_size_mb']} MB")
        print()

        print("BY CATEGORY")
        print("─" * 80)
        for category, stats in summary["by_category"].items():
            if stats["count"] > 0:
                cat_display = category.replace("_", " ").upper()
                print(
                    f"  {cat_display:30s}: {stats['count']:4d} items "
                    f"({stats['size_mb']:8.2f} MB)"
                )

        print()
        print("DUPLICATE SCRIPTS TO ARCHIVE")
        print("─" * 80)
        for item in self.report["categories"]["duplicate_scripts"]:
            print(f"  - {item['path']}")
            print(f"    Reason: {item['reason']}")
            print(f"    Size: {item['size_kb']} KB")
            print()

        print("DUPLICATE TESTS TO ARCHIVE")
        print("─" * 80)
        for item in self.report["categories"]["duplicate_tests"][:10]:
            print(f"  - {item['path']} ({item['size_kb']} KB)")
        if len(self.report["categories"]["duplicate_tests"]) > 10:
            print(
                f"  ... and {len(self.report['categories']['duplicate_tests']) - 10} more"
            )

        print()
        print("DUPLICATE DOCS TO ARCHIVE")
        print("─" * 80)
        for item in self.report["categories"]["duplicate_docs"][:10]:
            print(f"  - {item['path']} ({item['size_kb']} KB)")
        if len(self.report["categories"]["duplicate_docs"]) > 10:
            print(
                f"  ... and {len(self.report['categories']['duplicate_docs']) - 10} more"
            )

        print()
        print("OLD SCENARIOS TO ARCHIVE")
        print("─" * 80)
        for item in self.report["categories"]["old_scenarios"]:
            print(f"  - {item['path']} ({item['size_kb']} KB)")

        print()
        print("=" * 80)
        print()

    def save_report(self, output_path: Path) -> None:
        """Save report to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=2)

        print(f"✅ Report saved: {output_path}")

    def run(self, output_path: Path) -> int:
        """Run full analysis."""
        print("🔍 Scanning repository for cleanup candidates...")
        print()

        self.scan_duplicate_scripts()
        self.scan_duplicate_tests()
        self.scan_duplicate_docs()
        self.scan_old_scenarios()
        self.generate_summary()

        self.print_console_report()
        self.save_report(output_path)

        return 0


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze DutchBay repo for cleanup candidates"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("cleanup_analysis.json"),
        help="Output path for analysis JSON (default: cleanup_analysis.json)",
    )

    args = parser.parse_args()

    repo_root = Path.cwd()
    if not (repo_root / "pyproject.toml").exists():
        print("❌ Error: Not in DutchBay repo root", file=sys.stderr)
        return 1

    analyzer = CleanupAnalyzer(repo_root)
    return analyzer.run(args.output)


if __name__ == "__main__":
    sys.exit(main())
