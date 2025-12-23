#!/usr/bin/env python3
"""
DutchBay EPC Model - Import Fixer v2 with Debug Logging
Uses full-content string replacement to avoid multi-line import corruption.
Works directly on repository files.

ENHANCED WITH DEBUG LOGGING to help identify issues:
- File discovery tracking
- Pattern matching details
- Fix application verification
- Error handling with context
"""

import ast
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)-8s - %(message)s",
    handlers=[
        logging.FileHandler(
            f'import_fixer_debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Legacy v14 import patterns to fix
LEGACY_PATTERNS = {
    "_v14": "",
    "contracts_v14": "contracts",
    "cashflow_v14": "cashflow",
    "equity_v14": "equity",
    "irr_v14": "irr",
}

# Core relocations
CORE_RELOCATIONS = {
    "analytics.configschema": "analytics.core.configschema",
    "analytics.parametersolvers": "analytics.core.parametersolvers",
    "analytics.kpinormalizer": "analytics.core.kpinormalizer",
    "analytics.schemaguard": "analytics.core.schemaguard",
}

# Equity relocations
EQUITY_RELOCATIONS = {
    "finance.irr": "finance.equity.irr",
    "finance.irrconfig": "finance.equity.irrconfig",
}

# Files with known unfixable imports (skip these)
SKIP_FILES = {
    "cashflow_v14_tax.py",
    "evaluation_v14.py",
    "monte_carlo_v14.py",
    "legacy/**",
}


class ImportFixerV2Debug:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.fixes: List[Dict] = []
        self.errors: List[Dict] = []
        self.stats = {
            "files_scanned": 0,
            "files_skipped": 0,
            "patterns_found": 0,
            "patterns_applied": 0,
            "files_modified": 0,
            "fixes_by_pattern": defaultdict(int),
        }

        logger.info("=" * 70)
        logger.info("IMPORT FIXER V2 DEBUG - INITIALIZATION")
        logger.info("=" * 70)
        logger.info(f"Repository root: {self.repo_root}")
        logger.info(f"Working directory: {os.getcwd()}")

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        rel_path = file_path.relative_to(self.repo_root)
        rel_str = str(rel_path)

        for skip_pattern in SKIP_FILES:
            if "*" in skip_pattern:
                if skip_pattern.replace("**/", "").replace("*", "") in rel_str:
                    logger.debug(f"SKIP (pattern {skip_pattern}): {rel_path}")
                    return True
            elif skip_pattern in rel_str:
                logger.debug(f"SKIP (exact match {skip_pattern}): {rel_path}")
                return True

        return False

    def find_import_fixes(self, file_path: Path) -> List[Dict]:
        """Analyze file and find all import fixes needed."""
        fixes_for_file = []
        rel_path = file_path.relative_to(self.repo_root)

        logger.debug(f"\n→ ANALYZING: {rel_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug(f"  ✓ File read successfully ({len(content)} bytes)")
        except Exception as e:
            logger.error(f"  ✗ Failed to read file: {e}")
            self.errors.append({"file": file_path, "error": f"Read failed: {e}"})
            return []

        # Check file can be parsed as Python
        try:
            ast.parse(content)
            logger.debug("  ✓ Valid Python syntax")
        except SyntaxError as e:
            logger.warning(f"  ⚠ Syntax error (may have pre-existing issues): {e}")

        # Pattern-based fixes (simple string replacements)
        import_fixes = [
            # Legacy v14 suffix removals
            (
                "from analytics.contracts import",
                "from analytics.contracts import",
                "v14-contracts",
            ),
            (
                "from analytics.sensitivity import",
                "from analytics.sensitivity import",
                "v14-sensitivity",
            ),
            (
                "from finance.cashflow import",
                "from finance.cashflow import",
                "v14-cashflow",
            ),
            ("from finance.equity import", "from finance.equity import", "v14-equity"),
            ("from finance.debt import", "from finance.debt import", "v14-debt"),
            ("from finance.wacc import", "from finance.wacc import", "v14-wacc"),
            (
                "import analytics.sensitivity",
                "import analytics.sensitivity",
                "v14-sensitivity-import",
            ),
            ("import finance.equity", "import finance.equity", "v14-equity-import"),
            # Core module relocations
            (
                "from analytics.core.configschema import",
                "from analytics.core.configschema import",
                "core-configschema",
            ),
            (
                "from analytics.core.parametersolvers import",
                "from analytics.core.parametersolvers import",
                "core-parametersolvers",
            ),
            (
                "from analytics.core.kpinormalizer import",
                "from analytics.core.kpinormalizer import",
                "core-kpinormalizer",
            ),
            (
                "from analytics.core.schemaguard import",
                "from analytics.core.schemaguard import",
                "core-schemaguard",
            ),
            # Equity relocations
            (
                "from finance.equity.irr import",
                "from finance.equity.irr import",
                "equity-irr",
            ),
            (
                "from finance.equity.irrconfig import",
                "from finance.equity.irrconfig import",
                "equity-irrconfig",
            ),
        ]

        for old_pattern, new_pattern, pattern_id in import_fixes:
            if old_pattern in content:
                count = content.count(old_pattern)
                logger.debug(
                    f"  ✓ Found {count}x '{old_pattern}' → '{new_pattern}' [{pattern_id}]"
                )

                fixes_for_file.append(
                    {
                        "file": file_path,
                        "old": old_pattern,
                        "new": new_pattern,
                        "count": count,
                        "pattern_id": pattern_id,
                        "type": "pattern",
                    }
                )

                self.stats["patterns_found"] += count
                self.stats["fixes_by_pattern"][pattern_id] += count

        logger.debug(f"  Summary: {len(fixes_for_file)} patterns found in this file")
        return fixes_for_file

    def fix_files(self, dry_run=True) -> int:
        """Fix all imports in repository."""
        logger.info("\n" + "=" * 70)
        logger.info(
            f"{'DRY RUN' if dry_run else 'APPLYING FIXES'}: Scanning repository"
        )
        logger.info("=" * 70)

        fixed_count = 0

        for py_file in sorted(self.repo_root.rglob("*.py")):
            # Skip venv, cache, tests, legacy
            if any(part in str(py_file) for part in [".venv", "__pycache__", ".git"]):
                logger.debug(
                    f"SKIP (system dir): {py_file.relative_to(self.repo_root)}"
                )
                self.stats["files_skipped"] += 1
                continue

            if self.should_skip_file(py_file):
                self.stats["files_skipped"] += 1
                continue

            self.stats["files_scanned"] += 1
            fixes = self.find_import_fixes(py_file)

            if fixes:
                rel_path = py_file.relative_to(self.repo_root)
                logger.info(f"\n📄 {rel_path}")

                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    original_content = content
                    modified = False

                    for fix in fixes:
                        old = fix["old"]
                        new = fix["new"]
                        pattern_id = fix["pattern_id"]

                        if old in content:
                            # Count occurrences before replacement
                            count_before = content.count(old)
                            content = content.replace(old, new)
                            count_after = content.count(old)
                            replaced = count_before - count_after

                            modified = True
                            fixed_count += replaced
                            self.stats["patterns_applied"] += replaced

                            logger.info(
                                f"  ✅ [{pattern_id}] {replaced}x: '{old[:40]}...' → '{new[:40]}...'"
                            )
                        else:
                            logger.warning(
                                f"  ⚠️  [{pattern_id}] Pattern not found (already fixed?): {old[:60]}"
                            )

                    if not dry_run and modified:
                        try:
                            with open(py_file, "w", encoding="utf-8") as f:
                                f.write(content)

                            # Verify file is still valid Python
                            try:
                                ast.parse(content)
                                logger.debug("  ✓ File written and syntax verified")
                                self.stats["files_modified"] += 1
                            except SyntaxError as e:
                                logger.error(f"  ✗ SYNTAX ERROR after fix: {e}")
                                logger.error("    Reverting file...")
                                with open(py_file, "w", encoding="utf-8") as f:
                                    f.write(original_content)
                                self.errors.append(
                                    {
                                        "file": py_file,
                                        "error": f"Syntax error after fix: {e}",
                                    }
                                )
                        except Exception as e:
                            logger.error(f"  ✗ Failed to write file: {e}")
                            self.errors.append(
                                {"file": py_file, "error": f"Write failed: {e}"}
                            )

                except Exception as e:
                    logger.error(f"  ✗ Error processing file: {e}")
                    self.errors.append({"file": py_file, "error": str(e)})

        return fixed_count

    def generate_summary(self) -> str:
        """Generate detailed fix summary with statistics."""
        report = []
        report.append("\n" + "=" * 70)
        report.append("DUTCHBAY EPC MODEL - IMPORT FIX SUMMARY")
        report.append("=" * 70)

        report.append("\n📊 STATISTICS:")
        report.append(f"  Files scanned:        {self.stats['files_scanned']}")
        report.append(f"  Files skipped:        {self.stats['files_skipped']}")
        report.append(f"  Files modified:       {self.stats['files_modified']}")
        report.append(f"  Patterns found:       {self.stats['patterns_found']}")
        report.append(f"  Patterns applied:     {self.stats['patterns_applied']}")

        if self.stats["fixes_by_pattern"]:
            report.append("\n📋 FIXES BY PATTERN:")
            for pattern_id, count in sorted(
                self.stats["fixes_by_pattern"].items(), key=lambda x: -x[1]
            ):
                report.append(f"  {pattern_id:30s} {count:4d} fixes")

        if self.errors:
            report.append(f"\n⚠️  ERRORS ENCOUNTERED: {len(self.errors)}")
            for err in self.errors[:10]:  # Show first 10 errors
                report.append(f"  - {err['file'].name}: {err['error'][:60]}")
            if len(self.errors) > 10:
                report.append(f"  ... and {len(self.errors) - 10} more errors")

        report.append("\n" + "=" * 70)
        return "\n".join(report)


def main():

    # Check if running with auto-apply argument
    auto_apply = "--apply" in sys.argv

    repo_root = Path.cwd()

    logger.info(f"Current working directory: {repo_root}")
    logger.info(f"Files in directory: {list(repo_root.glob('*'))[:5]}")

    if not (repo_root / "finance").exists():
        logger.error("❌ 'finance' directory not found")
        logger.error(f"   Expected in: {repo_root}")
        logger.error(f"   Actual contents: {list(repo_root.iterdir())[:10]}")
        sys.exit(1)

    if not (repo_root / "analytics").exists():
        logger.error("❌ 'analytics' directory not found")
        sys.exit(1)

    logger.info("✅ Repository structure verified")
    logger.info("🚀 DutchBay EPC Model - Import Fixer V2 DEBUG")

    fixer = ImportFixerV2Debug(repo_root)

    # Dry run
    logger.info("\n📋 DRY RUN MODE - Scanning for fixes...")
    fixed = fixer.fix_files(dry_run=True)

    logger.info(f"\n✅ DRY RUN COMPLETE - Would fix {fixed} import statements")
    logger.info(fixer.generate_summary())

    # Ask to apply
    if fixed > 0:
        if auto_apply:
            response = "y"
            logger.info("\n✅ Auto-applying fixes (--apply flag detected)...")
        else:
            response = (
                input("\n✅ Apply these import fixes? (yes/no): ").strip().lower()
            )

        if response in ["yes", "y"]:
            logger.info("\n📝 APPLYING FIXES...")
            fixer.fix_files(dry_run=False)
            logger.info("\n✅ FIXES APPLIED!")
            logger.info(fixer.generate_summary())
            logger.info("\n📌 Next steps:")
            logger.info("  1. Run: pytest tests/ -v")
            logger.info("  2. Check git diff to verify changes")
            logger.info("  3. Run black/ruff to auto-format")
        else:
            logger.info("\n⏭️  User declined - no changes made")
    else:
        logger.info("\n✅ No fixes needed!")


if __name__ == "__main__":
    main()
