#!/usr/bin/env python3
"""Phase 2: Scripts Folder Cleanup - Legacy Migration (EXECUTION READY)"""

import ast
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class LegacyCategory(Enum):
    V13_LEGACY = "v13_legacy"
    MIGRATIONS = "migrations"
    DEBUG_ARCHIVE = "debug_archive"
    TESTS = "tests"
    BANNED_CLI = "banned_cli"
    KEEP_ACTIVE = "keep_active"
    UNKNOWN = "unknown"


@dataclass
class ScriptAnalysis:
    path: Path
    category: LegacyCategory
    reason: str
    has_argparse: bool = False
    has_typer: bool = False
    has_click: bool = False
    file_size: int = 0
    confidence: str = "high"


@dataclass
class MigrationPlan:
    scripts_to_move: Dict[LegacyCategory, List[ScriptAnalysis]] = field(
        default_factory=dict
    )
    total_files: int = 0
    total_size: int = 0

    def add_script(self, analysis: ScriptAnalysis) -> None:
        if analysis.category not in self.scripts_to_move:
            self.scripts_to_move[analysis.category] = []
        self.scripts_to_move[analysis.category].append(analysis)
        self.total_files += 1
        self.total_size += analysis.file_size


class LegacyScriptAnalyzer:
    MIGRATION_PREFIXES = [
        "add_",
        "fix_",
        "patch_",
        "hotfix_",
        "repair_",
        "restore_",
        "align_",
        "inject_",
        "neutralize_",
        "force_",
        "revert_",
        "append_",
        "apply_",
        "overwrite_",
        "harden_",
        "bootstrap_",
        "cleanup_",
        "commit_and_tag_",
        "emit_",
        "lower_",
        "upgrade_",
    ]

    DEBUG_PREFIXES = [
        "debug_",
        "diagnose_",
        "diagnostic_",
        "inspect_",
        "debt_diagnostic",
    ]
    V13_PATTERNS = ["v13", "_v13_", "legacy", "move_v13"]

    KEEP_ACTIVE = [
        "go_with_the_flow_ci.py",
        "fx_correlation_module.py",
        "analyze_directory.py",
        "generate_manifest.py",
        "make_clean_zip.py",
        "make_essential_zip.py",
        "gh_tools.py",
        "ci_structure_check.py",
        "wacc_engine_yaml.py",
        "gen_scenario_yaml.py",
        "parameter_validation.py",
        "model_guard.py",
        "build_zip_from_manifest.py",
        "auto_close_issues.py",
        "check_legacy_imports.py",
        "check_all_py_files.py",
        "check_staged_py_files.py",
        "validate.py",
        "cleanup_phase1.py",
        "cleanup_phase1_fixed.py",
        "cleanup_phase2.py",
    ]

    ACTIVE_TESTS = [
        "test_fx_dual_regime_standalone_fixed.py",
        "test_llcr_plcr_real_debt.py",
        "test_irr_quick.py",
        "test_returns_module.py",
        "test_markdown_report.py",
        "test_fx_complete_data.py",
    ]

    def __init__(self, scripts_dir: Path):
        self.scripts_dir = scripts_dir

    def check_banned_imports(self, file_path: Path) -> Tuple[bool, bool, bool]:
        if not file_path.suffix == ".py":
            return False, False, False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(file_path))

            has_argparse = False
            has_typer = False
            has_click = False

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", None)
                    names = [alias.name for alias in node.names]

                    if module:
                        if "argparse" in module:
                            has_argparse = True
                        if "typer" in module:
                            has_typer = True
                        if "click" in module:
                            has_click = True

                    for name in names:
                        if "argparse" in name:
                            has_argparse = True
                        if "typer" in name:
                            has_typer = True
                        if "click" in name:
                            has_click = True

            return has_argparse, has_typer, has_click

        except Exception as e:
            logger.debug(f"Could not parse {file_path}: {e}")
            return False, False, False

    def categorize_script(self, file_path: Path) -> ScriptAnalysis:
        filename = file_path.name
        file_lower = filename.lower()
        file_size = file_path.stat().st_size

        has_argparse, has_typer, has_click = self.check_banned_imports(file_path)

        analysis = ScriptAnalysis(
            path=file_path,
            category=LegacyCategory.UNKNOWN,
            reason="",
            has_argparse=has_argparse,
            has_typer=has_typer,
            has_click=has_click,
            file_size=file_size,
        )

        # Priority 1: Keep active
        if filename in self.KEEP_ACTIVE or filename in self.ACTIVE_TESTS:
            analysis.category = LegacyCategory.KEEP_ACTIVE
            analysis.reason = "Active v14 script"
            return analysis

        # Priority 2: Banned CLI
        if has_argparse or has_typer:
            analysis.category = LegacyCategory.BANNED_CLI
            violations = []
            if has_argparse:
                violations.append("argparse (R3)")
            if has_typer:
                violations.append("typer (R4)")
            analysis.reason = f"Uses banned: {', '.join(violations)}"
            return analysis

        # Priority 3: V13/legacy
        for pattern in self.V13_PATTERNS:
            if pattern in file_lower:
                analysis.category = LegacyCategory.V13_LEGACY
                analysis.reason = f"V13/legacy pattern: {pattern}"
                return analysis

        # Priority 4: Migrations
        for prefix in self.MIGRATION_PREFIXES:
            if file_lower.startswith(prefix):
                analysis.category = LegacyCategory.MIGRATIONS
                analysis.reason = f"One-time script: {prefix}*"
                return analysis

        # Priority 5: Debug
        for prefix in self.DEBUG_PREFIXES:
            if file_lower.startswith(prefix):
                analysis.category = LegacyCategory.DEBUG_ARCHIVE
                analysis.reason = f"Debug script: {prefix}*"
                return analysis

        # Priority 6: Legacy tests
        if file_lower.startswith("test_"):
            analysis.category = LegacyCategory.TESTS
            analysis.reason = "Legacy test (not in active list)"
            analysis.confidence = "medium"
            return analysis

        # Default: Unknown for manual review
        analysis.category = LegacyCategory.UNKNOWN
        analysis.reason = "Requires manual review"
        analysis.confidence = "low"
        return analysis


class LegacyMigrator:
    def __init__(self, scripts_dir: Path, dry_run: bool = True):
        self.scripts_dir = scripts_dir
        self.dry_run = dry_run
        self.legacy_base = scripts_dir.parent / "legacy" / "scripts"

    def create_directory_structure(self) -> None:
        directories = [
            self.legacy_base / "v13_legacy",
            self.legacy_base / "migrations",
            self.legacy_base / "debug_archive",
            self.legacy_base / "tests",
            self.legacy_base / "banned_cli",
            self.legacy_base / "unknown",
        ]

        for directory in directories:
            if not self.dry_run:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(
                    f"✓ Created: {directory.relative_to(self.scripts_dir.parent)}"
                )
            else:
                logger.info(
                    f"Would create: {directory.relative_to(self.scripts_dir.parent)}"
                )

    def move_script(self, analysis: ScriptAnalysis) -> bool:
        if analysis.category == LegacyCategory.KEEP_ACTIVE:
            return True

        target_dir = self.legacy_base / analysis.category.value
        target_path = target_dir / analysis.path.name

        try:
            if not self.dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["git", "mv", str(analysis.path), str(target_path)],
                    check=True,
                    capture_output=True,
                    cwd=self.scripts_dir.parent,
                )
                logger.info(f"✓ {analysis.path.name} → {analysis.category.value}/")
            else:
                logger.info(
                    f"Would move: {analysis.path.name} → {analysis.category.value}/"
                )
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"✗ Failed: {analysis.path.name}: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"✗ Failed: {analysis.path.name}: {e}")
            return False


def generate_decision_matrix(plan: MigrationPlan, output_path: Path) -> None:
    import csv

    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Filename",
                "Category",
                "Reason",
                "Argparse",
                "Typer",
                "Click",
                "Confidence",
                "Size",
                "Action",
            ]
        )

        for category, scripts in plan.scripts_to_move.items():
            for script in sorted(scripts, key=lambda s: s.path.name):
                writer.writerow(
                    [
                        script.path.name,
                        category.value,
                        script.reason,
                        "Yes" if script.has_argparse else "No",
                        "Yes" if script.has_typer else "No",
                        "Yes" if script.has_click else "No",
                        script.confidence,
                        script.file_size,
                        "MOVE" if category != LegacyCategory.KEEP_ACTIVE else "KEEP",
                    ]
                )

    logger.info(f"Decision matrix: {output_path}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2: Legacy migration")
    parser.add_argument("--scripts-dir", type=Path, default=Path("scripts"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scripts_dir = args.scripts_dir

    logger.info("=" * 80)
    logger.info("PHASE 2: LEGACY SCRIPT MIGRATION")
    logger.info("=" * 80)

    analyzer = LegacyScriptAnalyzer(scripts_dir)
    plan = MigrationPlan()

    script_files = list(scripts_dir.glob("*.py")) + list(scripts_dir.glob("*.sh"))
    logger.info(f"Analyzing {len(script_files)} scripts...")

    for script_file in sorted(script_files):
        if not script_file.name.startswith("."):
            analysis = analyzer.categorize_script(script_file)
            plan.add_script(analysis)

    # Generate decision matrix
    matrix_path = (
        scripts_dir.parent
        / "outputs"
        / f"phase2_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    generate_decision_matrix(plan, matrix_path)

    # Summary
    logger.info("")
    logger.info("SUMMARY:")
    logger.info("-" * 80)
    for category in LegacyCategory:
        scripts = plan.scripts_to_move.get(category, [])
        if scripts:
            logger.info(f"{category.value.upper()}: {len(scripts)} files")

    logger.info("")
    logger.info(f"Total: {plan.total_files} files")
    logger.info(f"Matrix: {matrix_path}")
    logger.info("=" * 80)

    if not args.execute:
        logger.info("")
        logger.info("DRY RUN - Review matrix and run with --execute to migrate")
        return 0

    # Execute migration
    logger.info("")
    logger.info("EXECUTING MIGRATION...")
    logger.info("=" * 80)

    migrator = LegacyMigrator(scripts_dir, dry_run=False)
    migrator.create_directory_structure()

    success_count = 0
    failure_count = 0

    for category, scripts in plan.scripts_to_move.items():
        if category != LegacyCategory.KEEP_ACTIVE:
            logger.info("")
            logger.info(f"Moving {len(scripts)} files to {category.value}/...")
            for script in scripts:
                if migrator.move_script(script):
                    success_count += 1
                else:
                    failure_count += 1

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"✅ Migration complete: {success_count} moved, {failure_count} failed")
    logger.info("=" * 80)

    if failure_count == 0:
        logger.info("")
        logger.info("Next steps:")
        logger.info("  git add -A")
        logger.info(
            "  git commit -m 'chore: migrate legacy scripts to legacy/scripts/ (Phase 2)'"
        )
        logger.info("  git push")

    return 0 if failure_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
