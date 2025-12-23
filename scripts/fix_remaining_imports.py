#!/usr/bin/env python3
"""
Fix remaining broken imports:
- finance.irr -> finance.equity.irr
- finance.irrconfig -> finance.equity.irrconfig
"""

import ast
from pathlib import Path


def fix_remaining():
    repo_root = Path.cwd()

    # Files to fix
    remaining_fixes = [
        ("from finance.irr import", "from finance.equity.irr import"),
        ("import finance.irr", "import finance.equity.irr"),
        ("from finance.irrconfig import", "from finance.equity.irrconfig import"),
    ]

    files_modified = 0
    total_fixes = 0

    for py_file in sorted(repo_root.rglob("*.py")):
        # Skip venv, cache, git, tools
        if any(
            part in str(py_file)
            for part in [
                ".venv",
                "__pycache__",
                ".git",
                "check_imports.py",
                "import_fixer_v2_debug.py",
                "fix_remaining_imports.py",
            ]
        ):
            continue

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            modified = False
            for old_pattern, new_pattern in remaining_fixes:
                if old_pattern in content:
                    count = content.count(old_pattern)
                    content = content.replace(old_pattern, new_pattern)
                    total_fixes += count
                    modified = True
                    print(
                        f"✅ {py_file.relative_to(repo_root)}: {count}x {old_pattern} -> {new_pattern}"
                    )

            if modified:
                # Verify syntax
                try:
                    ast.parse(content)
                    with open(py_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    files_modified += 1
                except SyntaxError as e:
                    print(f"❌ Syntax error in {py_file}: {e}")

        except Exception as e:
            print(f"⚠️  Error processing {py_file}: {e}")

    print(f"\n✅ Fixed {total_fixes} remaining imports in {files_modified} files")
    return total_fixes


if __name__ == "__main__":
    fix_remaining()
