#!/usr/bin/env python3
"""
File Editor Utility - Go With The Flow Style
Reliable, repeatable Python-based file editing (replaces sed)

Usage:
    python3 file_editor.py --fix-e265
    python3 file_editor.py --fix-w391
    python3 file_editor.py --fix-c420
    etc.
"""

import argparse
import os
import re
from pathlib import Path
from typing import List, Tuple


class FileEditor:
    """Safe, reliable file editing with Python"""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self.repo_root = Path.cwd()

    def log(self, msg: str):
        if self.verbose:
            print(f"✓ {msg}")

    def fix_e265_block_comments(self) -> int:
        """Fix E265: Block comment should start with '# '"""
        fixed = 0
        files = [
            ("analytics/fx/correlation.py", 7),
            ("analytics/fx/processor.py", 7),
        ]

        for filepath, line_num in files:
            path = self.repo_root / filepath
            if not path.exists():
                print(f"✗ {filepath} not found")
                continue

            with open(path, "r") as f:
                lines = f.readlines()

            # Line number is 1-indexed, convert to 0-indexed
            idx = line_num - 1
            if idx < len(lines):
                line = lines[idx]
                # If line starts with #! or #/ etc, add space
                if (
                    line.startswith("#")
                    and len(line) > 1
                    and line[1] not in (" ", "\n")
                ):
                    lines[idx] = "# " + line[1:]
                    with open(path, "w") as f:
                        f.writelines(lines)
                    self.log(f"E265: {filepath}:{line_num}")
                    fixed += 1

        return fixed

    def fix_w391_blank_eof(self) -> int:
        """Fix W391: Blank line at end of file"""
        fixed = 0
        files = ["tests/contracts/test_sensitivity_edgecases.py"]

        for filepath in files:
            path = self.repo_root / filepath
            if not path.exists():
                print(f"✗ {filepath} not found")
                continue

            with open(path, "r") as f:
                content = f.read()

            # Remove trailing blank lines, keep only one newline
            original = content
            content = content.rstrip() + "\n"

            if content != original:
                with open(path, "w") as f:
                    f.write(content)
                self.log(f"W391: {filepath}")
                fixed += 1

        return fixed

    def fix_c420_dict_fromkeys(self) -> int:
        """Fix C420: Use dict.fromkeys() instead of dict comprehension"""
        fixed = 0
        files = [("analytics/executive_workbook.py", 72)]

        for filepath, line_num in files:
            path = self.repo_root / filepath
            if not path.exists():
                print(f"✗ {filepath} not found")
                continue

            with open(path, "r") as f:
                lines = f.readlines()

            idx = line_num - 1
            if idx < len(lines):
                line = lines[idx]
                # Pattern: {k: None for k in items} or {k:None for k in items}
                match = re.search(r"\{k:\s*None\s+for\s+k\s+in\s+([^}]+)\}", line)
                if match:
                    iterable = match.group(1).strip()
                    lines[idx] = re.sub(
                        r"\{k:\s*None\s+for\s+k\s+in\s+[^}]+\}",
                        f"dict.fromkeys({iterable})",
                        line,
                    )
                    with open(path, "w") as f:
                        f.writelines(lines)
                    self.log(f"C420: {filepath}:{line_num}")
                    fixed += 1

        return fixed

    def fix_c408_dict_literal(self) -> int:
        """Fix C408: Use dict literal instead of dict() call"""
        fixed = 0
        files = [("analytics/sensitivity_visualization.py", 80)]

        for filepath, line_num in files:
            path = self.repo_root / filepath
            if not path.exists():
                print(f"✗ {filepath} not found")
                continue

            with open(path, "r") as f:
                lines = f.readlines()

            idx = line_num - 1
            if idx < len(lines):
                line = lines[idx]
                # Convert dict(...) to literal {...}
                # This is complex - safer to use noqa if we can't do it cleanly
                if "dict(" in line and ")" in line:
                    # Find the dict call and its contents
                    match = re.search(r"dict\(([^)]+)\)", line)
                    if match:
                        content = match.group(1)
                        # Only convert if it's empty or a simple literal
                        if content.strip() == "" or content.strip().startswith("{"):
                            lines[idx] = re.sub(r"dict\(\)", "{}", line)
                            with open(path, "w") as f:
                                f.writelines(lines)
                            self.log(f"C408: {filepath}:{line_num}")
                            fixed += 1

        return fixed

    def fix_f841_unused_variables(self) -> int:
        """Fix F841: Unused variable - prefix with underscore"""
        fixed = 0
        files = [("tests/analytics_layer/test_sensitivity_v14.py", 259)]

        for filepath, line_num in files:
            path = self.repo_root / filepath
            if not path.exists():
                print(f"✗ {filepath} not found")
                continue

            with open(path, "r") as f:
                lines = f.readlines()

            idx = line_num - 1
            if idx < len(lines):
                line = lines[idx]
                # Rename variable to _variable to indicate intentional non-use
                if "allowed_prefixes" in line:
                    lines[idx] = line.replace("allowed_prefixes", "_allowed_prefixes")
                    with open(path, "w") as f:
                        f.writelines(lines)
                    self.log(f"F841: {filepath}:{line_num}")
                    fixed += 1

        return fixed

    def fix_all_quick_wins(self) -> int:
        """Fix all quick wins in one go"""
        total = 0
        total += self.fix_e265_block_comments()
        total += self.fix_w391_blank_eof()
        total += self.fix_c420_dict_fromkeys()
        total += self.fix_c408_dict_literal()
        total += self.fix_f841_unused_variables()
        return total


def main():
    parser = argparse.ArgumentParser(description="File Editor Utility")
    parser.add_argument(
        "--fix-e265", action="store_true", help="Fix E265 block comments"
    )
    parser.add_argument(
        "--fix-w391", action="store_true", help="Fix W391 EOF blank lines"
    )
    parser.add_argument(
        "--fix-c420", action="store_true", help="Fix C420 dict.fromkeys"
    )
    parser.add_argument("--fix-c408", action="store_true", help="Fix C408 dict literal")
    parser.add_argument(
        "--fix-f841", action="store_true", help="Fix F841 unused variables"
    )
    parser.add_argument("--fix-all", action="store_true", help="Fix all quick wins")
    parser.add_argument(
        "--verbose", action="store_true", default=True, help="Verbose output"
    )

    args = parser.parse_args()
    editor = FileEditor(verbose=args.verbose)

    total = 0
    if args.fix_all or not any(
        [args.fix_e265, args.fix_w391, args.fix_c420, args.fix_c408, args.fix_f841]
    ):
        print("=== FIXING ALL QUICK WINS ===")
        total = editor.fix_all_quick_wins()
    else:
        if args.fix_e265:
            total += editor.fix_e265_block_comments()
        if args.fix_w391:
            total += editor.fix_w391_blank_eof()
        if args.fix_c420:
            total += editor.fix_c420_dict_fromkeys()
        if args.fix_c408:
            total += editor.fix_c408_dict_literal()
        if args.fix_f841:
            total += editor.fix_f841_unused_variables()

    print(f"\n✅ Fixed {total} violations")


if __name__ == "__main__":
    main()

    def add_noqa_c420(self) -> int:
        """Add # noqa: C420 for dict comprehensions that aren't removable"""
        fixed = 0
        files = [("analytics/executive_workbook.py", 72)]

        for filepath, line_num in files:
            path = self.repo_root / filepath
            if not path.exists():
                continue

            with open(path, "r") as f:
                lines = f.readlines()

            idx = line_num - 1
            if idx < len(lines) and "# noqa" not in lines[idx]:
                lines[idx] = lines[idx].rstrip() + "  # noqa: C420\n"
                with open(path, "w") as f:
                    f.writelines(lines)
                self.log(f"C420 noqa: {filepath}:{line_num}")
                fixed += 1

        return fixed

    def fix_c408_dict_kwargs(self) -> int:
        """Fix C408: Use dict literal {**kwargs} instead of dict(kwargs=value)"""
        fixed = 0
        files = [("analytics/sensitivity_visualization.py", 80)]

        for filepath, line_num in files:
            path = self.repo_root / filepath
            if not path.exists():
                continue

            with open(path, "r") as f:
                lines = f.readlines()

            idx = line_num - 1
            if idx < len(lines):
                line = lines[idx]
                # Convert dict(polar=True) to {polar=True}
                if "dict(" in line:
                    lines[idx] = re.sub(r"dict\(([^)]+)\)", r"{\1}", line)
                    with open(path, "w") as f:
                        f.writelines(lines)
                    self.log(f"C408: {filepath}:{line_num}")
                    fixed += 1

        return fixed


# Update main to include new fixes
def fix_remaining_quick_wins():
    editor = FileEditor()
    total = 0
    total += editor.fix_c408_dict_kwargs()
    total += editor.add_noqa_c420()
    return total
