#!/usr/bin/env python3
"""
dutchbay_manifest_builder.py

Builds a comprehensive manifest of all scripts, docs, tests, and configs
relevant to v14 work in the DutchBay EPC Model repo.

Usage:
    python dutchbay_manifest_builder.py [--output manifest.json]
    python dutchbay_manifest_builder.py --output exports/manifest_2025_12_13.json

Output:
    - JSON manifest file with categorized inventory
    - Console summary with stats
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────

SCRIPT_EXTENSIONS = {".py", ".sh", ".bash", ".zsh"}
DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".env"}
TEST_PATTERNS = {"tests/", "test_", "_test.py", "conftest.py"}

# Directories to skip
SKIP_DIRS = {
    ".git",
    ".github",
    ".venv311",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".egg-info",
    "dist",
    "build",
    ".tox",
    "legacy",
    "archive",
    "temp",
    "tmp",
}

# Files to always skip
SKIP_FILES = {
    ".DS_Store",
    "*.pyc",
    "*.pyo",
    ".env.local",
    ".env.*.local",
}


# ────────────────────────────────────────────────────────────────────────────
# Core Logic
# ────────────────────────────────────────────────────────────────────────────


def should_skip_dir(path: Path) -> bool:
    """Check if directory should be skipped."""
    name = path.name
    if name.startswith("."):
        return True
    return name in SKIP_DIRS


def should_skip_file(path: Path) -> bool:
    """Check if file should be skipped."""
    name = path.name
    if name.startswith("."):
        return True
    for skip in SKIP_FILES:
        if skip.startswith("*"):
            if name.endswith(skip[1:]):
                return True
        elif name == skip:
            return True
    return False


def categorize_file(path: Path) -> Optional[str]:
    """Categorize a file by type."""
    suffix = path.suffix.lower()
    name = path.name.lower()

    # Test files
    if "test" in name or any(pattern in str(path) for pattern in TEST_PATTERNS):
        return "test"

    # Scripts
    if suffix in SCRIPT_EXTENSIONS:
        return "script"

    # Config
    if suffix in CONFIG_EXTENSIONS:
        return "config"

    # Documentation
    if suffix in DOC_EXTENSIONS:
        return "doc"

    # Data files (for reference)
    if suffix in {".csv", ".xlsx", ".xls", ".parquet"}:
        return "data"

    # Source code (non-Python scripts)
    if suffix in {".java", ".scala", ".go", ".rs", ".ts", ".js", ".rb", ".php"}:
        return "code"

    return None


def get_file_info(path: Path) -> Dict[str, Any]:
    """Extract metadata about a file."""
    try:
        stat = path.stat()
        size_kb = stat.st_size / 1024
        return {
            "path": str(path.relative_to(Path.cwd())),
            "size_kb": round(size_kb, 2),
            "is_symlink": path.is_symlink(),
        }
    except (OSError, ValueError):
        return {"path": str(path), "size_kb": 0, "is_symlink": False, "error": True}


def traverse_repo(root: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Traverse repo and collect files by category."""
    manifest: Dict[str, List[Dict[str, Any]]] = {
        "script": [],
        "doc": [],
        "config": [],
        "test": [],
        "code": [],
        "data": [],
    }

    visited_dirs: Set[Path] = set()

    def walk(directory: Path, depth: int = 0) -> None:
        """Recursively walk directory tree."""
        if depth > 10:  # Prevent infinite loops
            return

        try:
            for item in sorted(directory.iterdir()):
                if item in visited_dirs:
                    continue

                if item.is_dir():
                    if not should_skip_dir(item):
                        visited_dirs.add(item)
                        walk(item, depth + 1)
                elif item.is_file():
                    if not should_skip_file(item):
                        category = categorize_file(item)
                        if category:
                            file_info = get_file_info(item)
                            manifest[category].append(file_info)
        except (PermissionError, OSError):
            pass

    walk(root)
    return manifest


def build_summary(manifest: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Build summary statistics."""
    total_files = sum(len(files) for files in manifest.values())
    total_size_kb = sum(
        f.get("size_kb", 0)
        for files in manifest.values()
        for f in files
        if "error" not in f
    )

    return {
        "total_files": total_files,
        "total_size_mb": round(total_size_kb / 1024, 2),
        "by_category": {
            category: {
                "count": len(files),
                "size_mb": round(
                    sum(f.get("size_kb", 0) for f in files if "error" not in f) / 1024,
                    2,
                ),
            }
            for category, files in manifest.items()
        },
    }


def print_console_summary(manifest: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print human-readable summary to console."""
    summary = build_summary(manifest)

    print("\n" + "=" * 80)
    print("DutchBay EPC Model – Repo Manifest")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"Repository Root: {Path.cwd()}")
    print()

    print("SUMMARY")
    print("─" * 80)
    print(f"Total Files: {summary['total_files']}")
    print(f"Total Size: {summary['total_size_mb']} MB")
    print()

    print("BY CATEGORY")
    print("─" * 80)
    for category in ["script", "doc", "config", "test", "code", "data"]:
        stats = summary["by_category"].get(category, {})
        if stats.get("count", 0) > 0:
            print(
                f"  {category.upper():10s}: {stats['count']:4d} files "
                f"({stats['size_mb']:8.2f} MB)"
            )

    print()
    print("V14 CRITICAL FILES (MUST-HAVES)")
    print("─" * 80)

    critical_files = [
        "run_full_pipeline_v14.py",
        "analytics/pipeline_v14.py",
        "analytics/evaluation_v14.py",
        "analytics/contracts_v14.py",
        "pyproject.toml",
        "pytest.ini",
    ]

    for critical in critical_files:
        critical_path = Path(critical)
        if critical_path.exists():
            print(f"  ✅ {critical}")
        else:
            print(f"  ❌ {critical} (MISSING)")

    print()
    print("SCRIPT FILES (by directory)")
    print("─" * 80)
    script_paths = sorted(set(f["path"].split("/")[0] for f in manifest["script"]))
    for dir_name in script_paths:
        scripts_in_dir = [
            f for f in manifest["script"] if f["path"].startswith(dir_name)
        ]
        print(f"  {dir_name}/")
        for script in scripts_in_dir[:5]:  # First 5
            print(f"    - {Path(script['path']).name}")
        if len(scripts_in_dir) > 5:
            print(f"    ... and {len(scripts_in_dir) - 5} more")

    print()
    print("DOCUMENTATION FILES")
    print("─" * 80)
    doc_files = sorted(f["path"] for f in manifest["doc"])
    for doc in doc_files[:20]:  # First 20
        print(f"  - {doc}")
    if len(doc_files) > 20:
        print(f"  ... and {len(doc_files) - 20} more")

    print()
    print("TEST FILES (by directory)")
    print("─" * 80)
    test_dirs = sorted(set(Path(f["path"]).parent for f in manifest["test"]))
    for test_dir in list(test_dirs)[:10]:  # First 10 dirs
        tests_in_dir = [
            f for f in manifest["test"] if f["path"].startswith(str(test_dir))
        ]
        print(f"  {test_dir}/ ({len(tests_in_dir)} files)")
    if len(test_dirs) > 10:
        print(f"  ... and {len(test_dirs) - 10} more directories")

    print()
    print("=" * 80)


def save_manifest(manifest: Dict[str, List[Dict[str, Any]]], output_path: Path) -> None:
    """Save manifest to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "repo_root": str(Path.cwd()),
        "summary": build_summary(manifest),
        "manifest": manifest,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"✅ Manifest saved to: {output_path}")


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Build a manifest of all files in DutchBay EPC Model repo"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("manifest.json"),
        help="Output path for manifest JSON (default: manifest.json)",
    )

    args = parser.parse_args()

    # Verify we're in a repo root
    if not Path("pyproject.toml").exists() and not Path(".git").exists():
        print(
            "❌ Error: Not in a DutchBay EPC Model repo root.",
            file=sys.stderr,
        )
        print(
            "   Expected pyproject.toml or .git in current directory.",
            file=sys.stderr,
        )
        return 1

    # Build manifest
    print("🔍 Traversing repository...")
    manifest = traverse_repo(Path.cwd())

    # Print console summary
    print_console_summary(manifest)

    # Save to file
    print()
    save_manifest(manifest, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
