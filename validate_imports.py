#!/usr/bin/env python3
"""
Validate imports by actually parsing Python files (not string matching).
"""

import ast
from collections import defaultdict
from pathlib import Path


def validate_imports():
    """Parse all Python files and check actual imports."""

    repo_root = Path.cwd()
    print(f"Validating imports in: {repo_root}")
    print("=" * 70)

    broken_imports = defaultdict(list)
    correct_imports = defaultdict(list)
    syntax_errors = []
    files_scanned = 0

    for py_file in sorted(repo_root.rglob("*.py")):
        # Skip venv, cache, git, tools
        if any(part in str(py_file) for part in [".venv", "__pycache__", ".git"]):
            continue

        files_scanned += 1
        rel_path = py_file.relative_to(repo_root)

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                syntax_errors.append((rel_path, str(e)))
                continue

            # Extract actual imports from AST
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""

                    # Check for problematic v14 imports
                    if "contractsv14" in module or "sensitivityv14" in module:
                        broken_imports["v14_modules"].append(str(rel_path))
                    elif "cashflowv14" in module or "equityv14" in module:
                        broken_imports["v14_modules"].append(str(rel_path))
                    elif "debtv14" in module or "waccv14" in module:
                        broken_imports["v14_modules"].append(str(rel_path))

                    # Check for old irrconfig
                    elif module == "finance.irrconfig":
                        broken_imports["irrconfig"].append(str(rel_path))

                    # Check for old irr location (not in equity)
                    elif module == "finance.irr":
                        broken_imports["irr_not_in_equity"].append(str(rel_path))

                    # Track correct patterns
                    elif module.startswith("finance.equity.irr"):
                        correct_imports["equity_irr"].append(str(rel_path))
                    elif module.startswith("analytics.contracts"):
                        correct_imports["contracts"].append(str(rel_path))
                    elif module.startswith("analytics.core."):
                        correct_imports["analytics_core"].append(str(rel_path))
                    elif module.startswith("finance.cashflow"):
                        correct_imports["cashflow"].append(str(rel_path))

        except Exception as e:
            print(f"Error reading {rel_path}: {e}")

    print(f"\n✅ Scanned {files_scanned} Python files")

    if syntax_errors:
        print(f"\n⚠️  {len(syntax_errors)} files with syntax errors:")
        for path, error in syntax_errors[:5]:
            print(f"    {path}: {error}")

    print("\n" + "=" * 70)
    print("ACTUAL BROKEN IMPORTS (from AST parsing):")
    print("=" * 70)

    if broken_imports:
        for issue_type, files in sorted(broken_imports.items()):
            unique_files = set(files)
            print(f"\n❌ {issue_type}: {len(unique_files)} files")
            for f in sorted(unique_files)[:5]:
                print(f"    {f}")
            if len(unique_files) > 5:
                print(f"    ... and {len(unique_files)-5} more")
    else:
        print("\n✅ NO ACTUAL BROKEN IMPORTS! All imports are correct.")

    print("\n" + "=" * 70)
    print("CORRECT IMPORTS FOUND:")
    print("=" * 70)

    for import_type, files in sorted(correct_imports.items()):
        unique_files = set(files)
        print(f"\n✅ {import_type}: {len(unique_files)} files")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_broken = sum(len(set(files)) for files in broken_imports.values())
    total_correct = sum(len(set(files)) for files in correct_imports.values())

    print(f"\nFiles with actual broken imports: {total_broken}")
    print(f"Files with correct imports:      {total_correct}")
    print(f"Total files scanned:             {files_scanned}")

    if total_broken == 0:
        print("\n🎉 ALL IMPORTS ARE CORRECT!")
        return True
    else:
        print(f"\n⚠️  {total_broken} import issues remain")
        return False


if __name__ == "__main__":
    success = validate_imports()
    exit(0 if success else 1)
